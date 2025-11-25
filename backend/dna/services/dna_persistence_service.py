"""
DNA Persistence Service
=======================
All database saving logic for DNA extraction results.

Handles:
- Parent (father/mother) saving
- Child saving (single or multiple)
- Loci saving and merging
- Duplicate detection integration
- File upload to storage (S3/local)

Supports:
- Parent + Child uploads
- Parent-only uploads
- Child-only uploads
- Loci enrichment (adding new loci to existing person)
"""
import logging
import os
from typing import Dict, Any, List
from urllib.parse import quote

from django.db import transaction
from django.core.files import File as DjangoFile

from dna.models import UploadedFile, Person, DNALocus
from dna.constants import GENDER_MARKERS
from dna.services.storage_service import get_storage_service
from dna.services.duplicate_detection_service import check_parent_and_children_duplicates
from dna.services.validation_service import count_valid_loci, validate_loci_confidence, validate_overall_quality
from dna.services.ocr_correction_service import fix_common_ocr_errors

logger = logging.getLogger(__name__)


# ============================================================
# MAIN DATABASE SAVE FUNCTION
# ============================================================

def save_dna_extraction_to_database(
        extraction_result: Dict[str, Any],
        filename: str,
        local_file_path: str,
) -> Dict[str, Any]:
    """
    Save DNA extraction result to database with validation.

    This is the main entry point for saving extracted DNA data.
    Handles duplicate detection, validation, and atomic database operations.

    Args:
        extraction_result: Extracted DNA data in format:
            {
                'parent': {'name': '...', 'loci': [{'locus_name': '...', 'allele_1': '...', 'allele_2': '...'}]},
                'parent_role': 'father' | 'mother' | 'unknown',
                'children': [{'name': '...', 'loci': [...]}],
            }
        filename: Original filename for logging and storage
        local_file_path: Path to temporary file on disk

    Returns:
        {
            'success': True/False,
            'uploaded_file_id': int (if success),
            'errors': List[str],
        }
    """
    storage_service = get_storage_service()

    logger.info(f"💾 Starting database save for: {filename}")
    logger.debug(f"Extraction result keys: {extraction_result.keys()}")

    try:
        # === STEP 1: Smart Duplicate Check ===
        duplicate_check = check_parent_and_children_duplicates(extraction_result)

        parent_exists = duplicate_check['parent_exists']
        existing_parent = duplicate_check['existing_parent']
        new_children = duplicate_check['new_children']
        duplicate_children = duplicate_check['duplicate_children']

        # === STEP 2: Extract Data ===
        parent_data = extraction_result.get('parent') or extraction_result.get('father', {})
        parent_role = extraction_result.get('parent_role', 'unknown')

        # Support both old format (single child) and new format (multiple children)
        children_data = extraction_result.get('children', [])
        if not children_data:
            single_child = extraction_result.get('child')
            if single_child and single_child.get('loci'):
                children_data = [single_child]

        parent_loci = parent_data.get('loci', []) if parent_data else []

        # === STEP 3: Determine What We Have ===
        has_parent = bool(parent_loci)
        has_children = len(children_data) > 0

        logger.info(f"Data structure: has_parent={has_parent}, children_count={len(children_data)}")

        # ═══════════════════════════════════════════════
        # ERROR CASES
        # ═══════════════════════════════════════════════

        # Case 1: Child-only upload (ACCEPT with warning)
        if not has_parent and has_children:
            logger.warning(f"⚠️ Child-only upload detected: {filename} (no parent in file)")

        # Case 2: No data at all
        if not has_parent and not has_children:
            logger.error(f"No DNA data in {filename}")
            return {
                'success': False,
                'errors': ["No DNA data found in file"],
            }

        # Case 3: Parent exists + NO new children
        if parent_exists and len(new_children) == 0:

            if len(duplicate_children) > 0:
                duplicate_names = []
                duplicate_person_ids = []

                for child in duplicate_children:
                    if isinstance(child, dict):
                        duplicate_names.append(child['name'])
                        duplicate_person_ids.append(child.get('person_id'))
                    else:
                        duplicate_names.append(child)

                # ✅ Add name to URL (encoded)
                parent_link = f"/table?personId={existing_parent.id}&name={quote(existing_parent.name)} [parent]"
                child_links = ' '.join([
                    f"/table?personId={pid}&name={quote(duplicate_names[i])} [child]"
                    for i, pid in enumerate(duplicate_person_ids) if pid
                ])

                if len(duplicate_children) == 1:
                    error_message = (
                        f"Duplicate detected: {existing_parent.name} and "
                        f"{duplicate_names[0]} already exist in database. "
                        f"View: {parent_link} {child_links}"
                    )
                else:
                    error_message = (
                        f"Duplicate detected: {existing_parent.name} and "
                        f"{', '.join(duplicate_names)} already exist in database. "
                        f"View: {parent_link} {child_links}"
                    )

                logger.error(error_message)
                return {
                    'success': False,
                    'errors': [error_message],
                }

            else:
                # Subcase B: Parent ONLY (no children in upload)
                new_loci_count = count_valid_loci(parent_loci)
                existing_loci_count = existing_parent.loci_count

                if new_loci_count > existing_loci_count:
                    # ✅ ACCEPT: New file has more loci - will merge
                    logger.info(
                        f"Accepting parent-only upload: {existing_parent.name} "
                        f"({existing_loci_count}→{new_loci_count} loci)"
                    )
                    # Continue to save section below
                else:
                    # ❌ REJECT: No benefit
                    error_message = (
                        f"Duplicate parent: {existing_parent.name} already has "
                        f"{existing_loci_count} loci (uploaded file has {new_loci_count}). "
                        f"View: /table?personId={existing_parent.id} [parent]"
                    )

                    logger.error(error_message)
                    return {
                        'success': False,
                        'errors': [error_message],
                    }

        # ═══════════════════════════════════════════════
        # VALIDATION (for SUCCESS cases only)
        # ═══════════════════════════════════════════════

        errors = []

        # Validate parent loci count (only if parent exists)
        if has_parent:
            valid_parent_count = count_valid_loci(parent_loci)
            logger.info(f"Valid parent loci: {valid_parent_count}")

            if valid_parent_count < 10:
                logger.error(f"Only {valid_parent_count} parent loci in {filename}")
                return {
                    'success': False,
                    'errors': [f"Insufficient parent data ({valid_parent_count} loci). Need at least 10 loci."],
                }
        else:
            # Child-only case
            logger.info("No parent data - child-only upload")

        # Validate each child loci count
        for idx, child_data in enumerate(children_data):
            child_loci = child_data.get('loci', [])
            valid_child_count = count_valid_loci(child_loci)
            logger.info(f"Valid child {idx + 1} loci: {valid_child_count}")

            if valid_child_count < 10:
                logger.error(f"Only {valid_child_count} loci for child {idx + 1} in {filename}")
                return {
                    'success': False,
                    'errors': [f"Insufficient child {idx + 1} data ({valid_child_count} loci). Need at least 10 loci."],
                }

        # Validate parent confidence
        if has_parent:
            parent_errors = validate_loci_confidence(
                loci=parent_loci,
                filename=filename,
                person_type="parent"
            )
            errors.extend(parent_errors)

        # Validate children confidence
        if has_children:
            for idx, child_data in enumerate(children_data):
                child_loci = child_data.get('loci', [])
                child_errors = validate_loci_confidence(
                    loci=child_loci,
                    filename=filename,
                    person_type="child",
                    person_index=idx + 1
                )
                errors.extend(child_errors)

        # Validate overall quality
        quality_errors = validate_overall_quality(extraction_result, filename)
        errors.extend(quality_errors)

        # Stop if validation errors
        if errors:
            return {
                'success': False,
                'errors': errors,
            }

        # ═══════════════════════════════════════════════
        # SAVE TO DATABASE (atomic transaction)
        # ═══════════════════════════════════════════════

        with transaction.atomic():

            # Upload file to storage (S3 or local)
            try:
                logger.info(f"📤 Uploading file: {filename}")
                with open(local_file_path, 'rb') as local_file:
                    django_file = DjangoFile(local_file, name=filename)
                    file_path = storage_service.save_file(django_file, filename)
                    logger.info(f"✅ File uploaded: {file_path}")
            except Exception as upload_error:
                logger.error(f"❌ File upload failed: {upload_error}")
                return {
                    'success': False,
                    'errors': ["Failed to upload file to storage"],
                }

            # Create uploaded file record
            uploaded_file = UploadedFile.objects.create(file=file_path)

            # Handle parent (only if exists)
            if has_parent:
                if parent_exists and existing_parent:
                    # Reuse existing parent
                    parent_person = existing_parent

                    # Merge new loci
                    new_loci_added = merge_loci_for_person(
                        person=parent_person,
                        new_loci_data=parent_loci,
                        filename=filename,
                        errors=errors,
                        source_file=uploaded_file
                    )

                    # Link parent to new file
                    parent_person.uploaded_files.add(uploaded_file)

                    if new_loci_added > 0:
                        logger.info(
                            f"✅ Linked existing parent {parent_person.name} to new file {filename} "
                            f"and added {new_loci_added} new loci (total now: {parent_person.loci_count})"
                        )
                    else:
                        logger.info(
                            f"✅ Linked existing parent {parent_person.name} to new file {filename} "
                            f"(no new loci)"
                        )

                else:
                    # Create new parent
                    parent_name = (parent_data.get('name') or '').strip() or 'Unknown'

                    # Determine parent role
                    if parent_role == 'unknown':
                        parent_role = _detect_parent_role(parent_data, parent_loci)

                    parent_person = Person.objects.create(
                        role=parent_role,
                        name=parent_name,
                        loci_count=0
                    )

                    parent_saved_count = save_person_loci(
                        person=parent_person,
                        loci_data=parent_loci,
                        filename=filename,
                        errors=errors,
                        source_file=uploaded_file
                    )

                    parent_person.loci_count = parent_saved_count
                    parent_person.save()
                    parent_person.uploaded_files.add(uploaded_file)

                    logger.info(
                        f"✅ Created new parent {parent_name} ({parent_role}) "
                        f"with {parent_saved_count} STR loci"
                    )
            else:
                # No parent in this upload
                logger.info("⚠️ No parent data in upload - saving children only")

            # Handle children (only NEW children)
            if has_children:
                for idx, child_data in enumerate(new_children):
                    child_name = (child_data.get('name') or '').strip() or f'Unknown Child {idx + 1}'
                    child_loci = child_data.get('loci', [])

                    child_person = Person.objects.create(
                        role='child',
                        name=child_name,
                        loci_count=0
                    )

                    child_saved_count = save_person_loci(
                        person=child_person,
                        loci_data=child_loci,
                        filename=filename,
                        errors=errors,
                        source_file=uploaded_file
                    )

                    child_person.loci_count = child_saved_count
                    child_person.save()
                    child_person.uploaded_files.add(uploaded_file)

                    logger.info(
                        f"✅ Saved NEW child {child_name} "
                        f"with {child_saved_count} STR loci"
                    )

            # Clean up temp file
            _cleanup_temp_file(local_file_path)

            # Success message depends on what was saved
            if has_parent and has_children:
                success_msg = f"Saved parent + {len(new_children)} children"
            elif has_parent:
                success_msg = "Saved parent only"
            else:
                success_msg = f"Saved {len(new_children)} children (no parent)"

            logger.info(f"✅ Successfully saved {filename}: Upload ID {uploaded_file.pk} - {success_msg}")

            return {
                'success': True,
                'uploaded_file_id': uploaded_file.pk,
                'errors': [],
            }

    except Exception as e:
        logger.error(f"Database save failed for {filename}: {e}", exc_info=True)
        return {
            'success': False,
            'errors': ["Server error occurred"],
        }


# ============================================================
# LOCI SAVING FUNCTIONS
# ============================================================

def save_person_loci(
        person: Person,
        loci_data: List[Dict],
        filename: str,
        errors: List[str],
        source_file: UploadedFile
) -> int:
    """
    Save loci for a person (parent or child).

    Args:
        person: Person model instance
        loci_data: List of locus dictionaries with keys:
            - locus_name: str
            - allele_1: str
            - allele_2: str
        filename: Source filename for logging
        errors: List to append error messages to
        source_file: UploadedFile instance for tracking

    Returns:
        Number of loci successfully saved
    """
    saved_count = 0
    skipped_loci = []
    corrected_loci = []

    for locus_data in loci_data:
        locus_name = locus_data.get('locus_name')
        allele_1 = locus_data.get('allele_1')
        allele_2 = locus_data.get('allele_2')

        # Skip if no locus name
        if not locus_name:
            continue

        # Skip gender markers (Amelogenin, Y indel)
        if locus_name.lower() in GENDER_MARKERS:
            logger.debug(f"Skipping gender marker: {locus_name} for {person.name}")
            continue

        # Auto-correct common OCR errors FIRST
        original_locus_name = locus_name
        locus_name = fix_common_ocr_errors(locus_name)

        if locus_name != original_locus_name:
            corrected_loci.append(f"{original_locus_name}→{locus_name}")

        # Skip empty loci (not an error - some labs don't test all loci)
        if allele_1 is None or allele_2 is None or allele_1 == '' or allele_2 == '':
            logger.info(f"Skipping {locus_name} for {person.name} (not tested by lab)")
            skipped_loci.append(locus_name)
            continue

        # Validate locus name AFTER correction
        if locus_name not in DNALocus.LOCUS_NAMES:
            error_msg = f"Invalid locus name: {locus_name}. Please re-upload clearer PDF."
            if error_msg not in errors:
                errors.append(error_msg)
            logger.error(f"❌ Invalid locus name: {locus_name} (original: {original_locus_name}) in {filename}")
            continue

        # Save locus to database
        try:
            DNALocus.objects.create(
                person=person,
                locus_name=locus_name,
                allele_1=str(allele_1),
                allele_2=str(allele_2),
                source_file=source_file
            )
            saved_count += 1

        except Exception as e:
            error_msg = f"Failed to save {locus_name}: {str(e)}"
            if error_msg not in errors:
                errors.append(error_msg)
            logger.error(f"❌ Failed to save {locus_name} for {person.name}: {e}")

    # Log results
    if corrected_loci:
        logger.info(f"✅ Auto-corrected {len(corrected_loci)} loci: {', '.join(corrected_loci)}")

    if skipped_loci:
        logger.info(f"⏭️ Skipped {len(skipped_loci)} untested loci: {', '.join(skipped_loci)}")

    return saved_count


def merge_loci_for_person(
        person: Person,
        new_loci_data: List[Dict],
        filename: str,
        errors: List[str],
        source_file: UploadedFile
) -> int:
    """
    Merge new loci data into existing person.

    Used when uploading a new file for an existing person to add
    any loci that weren't in the original file.

    Rules:
    - If locus exists: verify alleles match, keep existing
    - If locus is new: add it
    - Log warnings for allele mismatches

    Args:
        person: Existing Person model instance
        new_loci_data: List of locus dictionaries
        filename: Source filename for logging
        errors: List to append error messages to
        source_file: UploadedFile instance for tracking

    Returns:
        Number of NEW loci added
    """
    existing_loci = {
        locus.locus_name: locus
        for locus in person.loci.all()
    }

    new_loci_added = 0

    for locus_data in new_loci_data:
        locus_name = locus_data.get('locus_name')

        # Skip gender markers
        if locus_name and locus_name.lower() in GENDER_MARKERS:
            continue

        # Auto-correct OCR errors
        locus_name = fix_common_ocr_errors(locus_name)

        # Get alleles
        allele_1 = locus_data.get('allele_1')
        allele_2 = locus_data.get('allele_2')

        # Skip empty loci
        if allele_1 is None or allele_2 is None or allele_1 == '' or allele_2 == '':
            continue

        # Validate locus name
        if locus_name not in DNALocus.LOCUS_NAMES:
            error_msg = f"Invalid locus name: {locus_name}"
            if error_msg not in errors:
                errors.append(error_msg)
            continue

        # Check if this locus already exists
        if locus_name in existing_loci:
            # Verify alleles match
            existing_locus = existing_loci[locus_name]
            new_allele_1 = str(allele_1).strip()
            new_allele_2 = str(allele_2).strip()
            existing_allele_1 = str(existing_locus.allele_1).strip()
            existing_allele_2 = str(existing_locus.allele_2).strip()

            existing_alleles = set([existing_allele_1, existing_allele_2])
            new_alleles = set([new_allele_1, new_allele_2])

            if existing_alleles != new_alleles:
                source_info = existing_locus.source_file.file if existing_locus.source_file else 'unknown'
                logger.warning(
                    f"⚠️ Allele mismatch for {person.name} locus {locus_name}: "
                    f"Existing={existing_alleles} (from {source_info}), "
                    f"New={new_alleles} (from {filename}). "
                    f"Keeping existing version."
                )
            else:
                logger.debug(f"Locus {locus_name} already exists for {person.name} with matching alleles, skipping")

            continue

        # Add new locus
        try:
            DNALocus.objects.create(
                person=person,
                locus_name=locus_name,
                allele_1=str(allele_1),
                allele_2=str(allele_2),
                source_file=source_file
            )
            new_loci_added += 1
            logger.info(f"✅ Added new locus {locus_name} to existing person {person.name} (from {filename})")

        except Exception as e:
            error_msg = f"Failed to save {locus_name}: {str(e)}"
            if error_msg not in errors:
                errors.append(error_msg)

    # Update person's loci count
    if new_loci_added > 0:
        person.loci_count = person.loci.count()
        person.save()
        logger.info(
            f"✅ Updated {person.name}: added {new_loci_added} new loci from {filename} "
            f"(total now: {person.loci_count})"
        )

    return new_loci_added


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _detect_parent_role(parent_data: Dict, parent_loci: List[Dict]) -> str:
    """
    Detect parent role from data or Amelogenin marker.

    Args:
        parent_data: Parent data dictionary with optional 'role_label'
        parent_loci: List of loci data

    Returns:
        'father', 'mother', or 'father' (default)
    """
    # Try role_label first
    role_label = (parent_data.get('role_label', '') or '').lower()

    if 'mother' in role_label or 'мати' in role_label or 'мать' in role_label:
        return 'mother'
    elif 'father' in role_label or 'батько' in role_label or 'отец' in role_label:
        return 'father'

    # Check Amelogenin marker
    amelogenin = next(
        (l for l in parent_loci if l.get('locus_name', '').lower() == 'amelogenin'),
        None
    )

    if amelogenin:
        allele_1 = str(amelogenin.get('allele_1', '')).upper()
        allele_2 = str(amelogenin.get('allele_2', '')).upper()

        if 'Y' in [allele_1, allele_2]:
            return 'father'  # XY = male
        else:
            return 'mother'  # XX = female

    # Default to father
    return 'father'


def _cleanup_temp_file(file_path: str) -> None:
    """
    Safely delete temporary file.

    Args:
        file_path: Path to temporary file
    """
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"🗑️ Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to clean up temp file {file_path}: {e}")
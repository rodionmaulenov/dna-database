"""
Database Saving Logic for DNA Extraction Results
Handles: Parent (father/mother), Child, and all DNA Loci
Supports: Parent+Child, Parent-only, Child-only uploads
"""
import logging
import os
from typing import Dict, Any, List

from django.db import transaction
from django.core.files import File
from django.core.files.storage import default_storage
from django.conf import settings

from dna.models import UploadedFile, Person, DNALocus

logger = logging.getLogger(__name__)

# Gender markers to skip (not saved to database)
GENDER_MARKERS = ['amelogenin', 'y indel', 'y-indel']


def check_duplicate_by_alleles(extraction_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if same DNA data (alleles) already exists in database
    Compares allele values across critical loci

    Returns:
        {'is_duplicate': bool, 'existing_upload_id': int or None}
    """
    parent_data = extraction_result.get('parent') or extraction_result.get('father', {})
    parent_loci = parent_data.get('loci', [])

    if not parent_loci:
        return {'is_duplicate': False, 'existing_upload_id': None}

    critical_loci = ['D8S1179', 'D21S11', 'D7S820', 'D3S1358', 'FGA']
    new_fingerprint = {}

    for locus_data in parent_loci:
        locus_name = locus_data.get('locus_name')

        # Skip gender markers
        if locus_name and locus_name.lower() in GENDER_MARKERS:
            continue

        if locus_name in critical_loci:
            allele_1 = str(locus_data.get('allele_1', '')).strip()
            allele_2 = str(locus_data.get('allele_2', '')).strip()

            # Skip if empty
            if not allele_1 or not allele_2:
                continue

            alleles = tuple(sorted([allele_1, allele_2]))
            new_fingerprint[locus_name] = alleles

    if len(new_fingerprint) < 3:
        return {'is_duplicate': False, 'existing_upload_id': None}

    all_uploads = UploadedFile.objects.all()

    for upload in all_uploads:
        existing_parent = upload.persons.filter(role__in=['father', 'mother']).first()

        if not existing_parent:
            continue

        existing_loci = DNALocus.objects.filter(
            person=existing_parent,
            locus_name__in=critical_loci
        )

        existing_fingerprint = {}
        for locus in existing_loci:
            allele_1 = str(locus.allele_1).strip()
            allele_2 = str(locus.allele_2 or '').strip()

            alleles = tuple(sorted([allele_1, allele_2]))
            existing_fingerprint[locus.locus_name] = alleles

        matches = 0
        total_compared = 0

        for locus_name in critical_loci:
            if locus_name in new_fingerprint and locus_name in existing_fingerprint:
                total_compared += 1

                new_alleles = new_fingerprint[locus_name]
                existing_alleles = existing_fingerprint[locus_name]

                if new_alleles == existing_alleles:
                    matches += 1

        if total_compared >= 3 and (matches / total_compared) >= 0.8:
            logger.error(
                f"Duplicate DNA detected: Upload ID {upload.id}, "
                f"Match ratio: {matches}/{total_compared}"
            )
            return {
                'is_duplicate': True,
                'existing_upload_id': upload.id,
                'match_ratio': f"{matches}/{total_compared}"
            }

    return {'is_duplicate': False, 'existing_upload_id': None}


def _count_valid_loci(loci: List[Dict]) -> int:
    """
    Count only valid STR loci (exclude gender markers and empty loci)

    Args:
        loci: List of locus data dicts

    Returns:
        Count of valid STR loci with data
    """
    count = 0
    for locus in loci:
        locus_name = locus.get('locus_name')

        # Skip gender markers
        if locus_name and locus_name.lower() in GENDER_MARKERS:
            continue

        # Skip loci with empty alleles
        allele_1 = locus.get('allele_1')
        allele_2 = locus.get('allele_2')

        if allele_1 is None or allele_2 is None or allele_1 == '' or allele_2 == '':
            continue

        # Only count if in valid LOCUS_NAMES
        if locus_name in DNALocus.LOCUS_NAMES:
            count += 1

    return count


def _save_person_loci(
        person: Person,
        loci_data: List[Dict],
        filename: str,
        errors: List[str]
) -> int:
    """
    Save loci for a person (parent or child)
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

        # SKIP GENDER MARKERS
        if locus_name.lower() in GENDER_MARKERS:
            logger.debug(f"Skipping gender marker: {locus_name} for {person.name}")
            continue

        # Auto-correct common OCR errors FIRST
        original_locus_name = locus_name
        locus_name = _fix_common_ocr_errors(locus_name)

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


def save_dna_extraction_to_database(
        extraction_result: Dict[str, Any],
        filename: str,
        local_file_path: str,
) -> Dict[str, Any]:
    """
    Save DNA extraction result to database with validation
    Supports: Parent only, Parent + 1 child, Parent + multiple children
    """
    errors = []

    logger.info(f"Extraction result keys: {extraction_result.keys()}")

    try:
        # === STEP 1: Duplicate Check ===
        duplicate_check = check_duplicate_by_alleles(extraction_result)

        if duplicate_check['is_duplicate']:
            logger.error(
                f"Duplicate DNA detected: Upload ID {duplicate_check['existing_upload_id']}, "
                f"Match ratio: {duplicate_check['match_ratio']}, "
                f"File: {filename}"
            )
            return {
                'success': False,
                'errors': ["Duplicate DNA data detected"],
            }

        # === STEP 2: Extract Data ===
        parent_data = extraction_result.get('parent') or extraction_result.get('father', {})
        parent_role = extraction_result.get('parent_role', 'unknown')

        # ✅ Support both old format (single child) and new format (multiple children)
        children_data = extraction_result.get('children', [])
        if not children_data:
            # Backward compatibility: check for single 'child' key
            single_child = extraction_result.get('child')
            if single_child and single_child.get('loci'):
                children_data = [single_child]

        parent_loci = parent_data.get('loci', []) if parent_data else []

        # === STEP 3: Determine What We Have ===
        has_parent = bool(parent_loci)
        has_children = len(children_data) > 0

        logger.info(f"Data structure: has_parent={has_parent}, children_count={len(children_data)}")

        # Check if we have ANY data
        if not has_parent and not has_children:
            logger.error(f"No DNA data in {filename}")
            return {
                'success': False,
                'errors': ["No DNA data found in file"],
            }

        # === STEP 4: Validate Loci Counts ===
        valid_parent_count = _count_valid_loci(parent_loci) if has_parent else 0

        logger.info(f"Valid parent loci: {valid_parent_count}")

        # Validate each child
        for idx, child_data in enumerate(children_data):
            child_loci = child_data.get('loci', [])
            valid_child_count = _count_valid_loci(child_loci)
            logger.info(f"Valid child {idx + 1} loci: {valid_child_count}")

            if valid_child_count < 10:
                logger.error(f"Only {valid_child_count} loci for child {idx + 1} in {filename}")
                return {
                    'success': False,
                    'errors': [f"Insufficient child {idx + 1} data ({valid_child_count} loci). Need at least 10 loci."],
                }

        # Minimum loci validation for parent
        if has_parent and valid_parent_count < 10:
            logger.error(f"Only {valid_parent_count} parent loci in {filename}")
            return {
                'success': False,
                'errors': [f"Insufficient parent data ({valid_parent_count} loci). Need at least 10 loci."],
            }

        # === STEP 6: Check AI Confidence ===
        confidence_threshold = 0.8

        if has_parent:
            low_confidence_loci = []
            for locus in parent_loci:
                locus_name = locus.get('locus_name')
                if locus_name and locus_name.lower() in GENDER_MARKERS:
                    continue

                # Skip empty loci
                if locus.get('allele_1') is None or locus.get('allele_2') is None:
                    continue

                # Get confidence safely
                allele_1_confidence = _safe_confidence(locus.get('allele_1_confidence'))
                allele_2_confidence = _safe_confidence(locus.get('allele_2_confidence'))

                # Safe minimum
                min_confidence = _safe_min(allele_1_confidence, allele_2_confidence)

                if min_confidence < confidence_threshold:
                    low_confidence_loci.append(locus_name)

            if low_confidence_loci:
                logger.error(f"Low confidence parent extraction in {filename}: {low_confidence_loci}")
                errors.append(
                    f"AI couldn't read parent data clearly: {', '.join(low_confidence_loci)}. "
                    f"Please re-upload better quality PDF."
                )

        # ✅ Check confidence for each child
        if has_children:
            for idx, child_data in enumerate(children_data):
                child_loci = child_data.get('loci', [])
                child_low_confidence = []

                for locus in child_loci:
                    locus_name = locus.get('locus_name')
                    if locus_name and locus_name.lower() in GENDER_MARKERS:
                        continue

                    # Skip empty loci
                    if locus.get('allele_1') is None or locus.get('allele_2') is None:
                        continue

                    # Get confidence safely
                    allele_1_confidence = _safe_confidence(locus.get('allele_1_confidence'))
                    allele_2_confidence = _safe_confidence(locus.get('allele_2_confidence'))

                    # Safe minimum
                    min_confidence = _safe_min(allele_1_confidence, allele_2_confidence)

                    if min_confidence < confidence_threshold:
                        child_low_confidence.append(locus_name)

                if child_low_confidence:
                    logger.error(f"Low confidence child {idx + 1} extraction in {filename}: {child_low_confidence}")
                    errors.append(
                        f"AI couldn't read child {idx + 1} data clearly: {', '.join(child_low_confidence)}. "
                        f"Please re-upload better quality PDF."
                    )

        # === STEP 7: Check Overall Quality ===
        overall_quality = extraction_result.get('overall_quality', 1.0)
        if overall_quality and overall_quality < 0.8:
            logger.error(f"Low overall extraction quality in {filename}: {overall_quality}")
            errors.append(
                f"Poor image quality detected (score: {overall_quality:.2f}). "
                f"Please re-upload clearer PDF."
            )

        # === STEP 8: Check Gender Detection (only if parent exists) ===
        if has_parent and parent_role == 'unknown':
            logger.warning(f"Cannot determine parent role in {filename}")
            # Not a critical error - continue anyway

        # === STEP 9: Check Names ===
        parent_name = None

        if has_parent:
            parent_name = (parent_data.get('name') or '').strip() or 'Unknown'
            if parent_name == 'Unknown':
                logger.warning(f"Parent name missing in file: {filename}")

        # ✅ Check names for all children
        for idx, child_data in enumerate(children_data):
            child_name = (child_data.get('name') or '').strip()
            if not child_name:
                logger.warning(f"Child {idx + 1} name missing in file: {filename}")

        # === STOP HERE IF ERRORS ===
        if errors:
            return {
                'success': False,
                'errors': errors,
            }

        # === STEP 10: ALL VALIDATIONS PASSED - Now save everything ===
        with transaction.atomic():

            # ✅ FIRST: Upload to S3 (only if validation passed)
            s3_file_path = None

            if settings.USE_S3:
                logger.info(f"📤 Uploading to S3: {filename}")
                try:
                    with open(local_file_path, 'rb') as local_file:
                        django_file = File(local_file, name=filename)
                        # Save to S3: bucket/uploads/filename
                        s3_file_path = default_storage.save(f'uploads/{filename}', django_file)
                        logger.info(f"✅ Uploaded to S3: {s3_file_path}")
                except Exception as s3_error:
                    logger.error(f"❌ S3 upload failed: {s3_error}")
                    # S3 upload failed - abort transaction
                    return {
                        'success': False,
                        'errors': ["Failed to upload file to storage"],
                    }
            else:
                # Not using S3 - just reference local path
                s3_file_path = f'uploads/{filename}'
                logger.info(f"💾 Local storage mode - path: {s3_file_path}")

            # ✅ SECOND: Create database records
            uploaded_file = UploadedFile.objects.create(
                file=s3_file_path,  # S3 path or local reference
            )

            parent_person = None
            parent_saved_count = 0
            children_saved = []  # ✅ Track all saved children

            # Save parent (if exists)
            if has_parent:
                # ✅ Determine parent role properly
                if parent_role == 'unknown':
                    # Try to get role from role_label
                    role_label = (parent_data.get('role_label', '') or '').lower()

                    if 'mother' in role_label or 'мати' in role_label or 'мать' in role_label:
                        parent_role = 'mother'
                        logger.info(f"✅ Determined parent role: Mother (from role_label)")
                    elif 'father' in role_label or 'батько' in role_label or 'отец' in role_label:
                        parent_role = 'father'
                        logger.info(f"✅ Determined parent role: Father (from role_label)")
                    else:
                        # Check Amelogenin to determine gender
                        amelogenin = next(
                            (l for l in parent_loci if l.get('locus_name', '').lower() == 'amelogenin'),
                            None
                        )

                        if amelogenin:
                            allele_1 = str(amelogenin.get('allele_1', '')).upper()
                            allele_2 = str(amelogenin.get('allele_2', '')).upper()

                            # X, Y = Male = Father
                            # X, X = Female = Mother
                            if 'Y' in [allele_1, allele_2]:
                                parent_role = 'father'
                                logger.info(f"✅ Determined parent role: Father (Amelogenin: {allele_1}, {allele_2})")
                            else:
                                parent_role = 'mother'
                                logger.info(f"✅ Determined parent role: Mother (Amelogenin: {allele_1}, {allele_2})")
                        else:
                            # Default to father if can't determine
                            parent_role = 'father'
                            logger.warning(f"⚠️ Cannot determine parent gender in {filename}, defaulting to father")

                parent_person = Person.objects.create(
                    uploaded_file=uploaded_file,
                    role=parent_role,
                    name=parent_name,
                    loci_count=0
                )

                parent_saved_count = _save_person_loci(
                    person=parent_person,
                    loci_data=parent_loci,
                    filename=filename,
                    errors=errors
                )

                parent_person.loci_count = parent_saved_count
                parent_person.save()

                logger.info(
                    f"✅ Saved {parent_name} ({parent_role}) "
                    f"with {parent_saved_count} STR loci"
                )

            # ✅ Save ALL children (if exist)
            if has_children:
                for idx, child_data in enumerate(children_data):
                    child_name = (child_data.get('name') or '').strip() or f'Unknown Child {idx + 1}'
                    child_loci = child_data.get('loci', [])

                    child_person = Person.objects.create(
                        uploaded_file=uploaded_file,
                        role='child',
                        name=child_name,
                        loci_count=0
                    )

                    child_saved_count = _save_person_loci(
                        person=child_person,
                        loci_data=child_loci,
                        filename=filename,
                        errors=errors
                    )

                    child_person.loci_count = child_saved_count
                    child_person.save()

                    children_saved.append({
                        'id': child_person.id,
                        'name': child_name,
                        'loci_count': child_saved_count
                    })

                    logger.info(
                        f"✅ Saved {child_name} (child {idx + 1}) "
                        f"with {child_saved_count} STR loci"
                    )

            # Check for errors during loci save
            if errors:
                logger.error(f"Errors found during loci save for {filename}: {errors}")
                # Transaction will rollback automatically
                return {
                    'success': False,
                    'errors': errors,
                }

            uploaded_file.save()

            # ✅ THIRD: Everything saved successfully - clean up temp file
            _cleanup_temp_file(local_file_path)

            # ✅ Build success message
            saved_info = []
            if has_parent:
                saved_info.append(f"Parent {parent_person.id} ({parent_saved_count} loci)")
            if has_children:
                for child in children_saved:
                    saved_info.append(f"Child {child['id']} ({child['loci_count']} loci)")

            logger.info(
                f"✅ Successfully saved {filename}: "
                f"Upload ID {uploaded_file.id}, "
                f"S3 path: {s3_file_path}, "
                f"{', '.join(saved_info)}"
            )

            return {
                'success': True,
                'uploaded_file_id': uploaded_file.id,
                'errors': [],
            }

    except Exception as e:
        logger.error(f"Database save failed for {filename}: {e}", exc_info=True)

        return {
            'success': False,
            'errors': ["Server error occurred"],
        }

def _cleanup_temp_file(file_path: str):
    """Helper to safely delete temp file"""
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"🗑️ Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to clean up temp file {file_path}: {e}")


def _safe_min(val1: Any, val2: Any, default: float = 1.0) -> float:
    """
    Safely get minimum of two values, handling None
    """
    if val1 is None and val2 is None:
        return default
    if val1 is None:
        return val2 if val2 is not None else default
    if val2 is None:
        return val1 if val1 is not None else default

    try:
        return min(float(val1), float(val2))
    except (TypeError, ValueError):
        return default


def _safe_confidence(value: Any, default: float = 1.0) -> float:
    """
    Safely convert confidence value to float
    """
    if value is None:
        return default

    try:
        result = float(value)
        # Ensure between 0 and 1
        return max(0.0, min(1.0, result))
    except (TypeError, ValueError):
        return default


def _fix_common_ocr_errors(locus_name: str) -> str:
    """
    Fix common OCR errors in locus names
    """
    if not locus_name:
        return locus_name

    # Convert to uppercase for comparison
    locus_upper = locus_name.upper().strip()

    # Common OCR errors mapping (all uppercase)
    corrections = {
        # CSF1PO variations (zero vs letter O)
        'CSF1P0': 'CSF1PO',
        'CSFIPO': 'CSF1PO',
        'CSF1 PO': 'CSF1PO',
        'CSFI PO': 'CSF1PO',
        'CSFlPO': 'CSF1PO',

        # D21S11 variations (one vs letter I/L)
        'D2IS11': 'D21S11',
        'D2ISI1': 'D21S11',
        'D21SI1': 'D21S11',
        'D2LSI1': 'D21S11',
        'D2ISII': 'D21S11',

        # D10S1248 variations
        'DIOS1248': 'D10S1248',
        'DlOS1248': 'D10S1248',
        'D1OS1248': 'D10S1248',
        'DI0S1248': 'D10S1248',

        # D8S1179 variations
        'D8SI179': 'D8S1179',
        'D8S1I79': 'D8S1179',
        'D8SII79': 'D8S1179',

        # vWA variations
        'VWA': 'vWA',
        'VVA': 'vWA',
        'VVVA': 'vWA',
        'WWA': 'vWA',

        # D16S539 variations
        'D16S5539': 'D16S539',
        'D16S53g': 'D16S539',

        # Penta variations
        'PENTA D': 'Penta D',
        'PENTA E': 'Penta E',
        'PENTAD': 'Penta D',
        'PENTAE': 'Penta E',
    }

    # Check if uppercase version needs correction
    if locus_upper in corrections:
        corrected = corrections[locus_upper]
        logger.info(f"🔧 Auto-corrected locus: {locus_name} → {corrected}")
        return corrected

    # Special case for vWA (needs lowercase v)
    if locus_upper == 'VWA':
        logger.info(f"🔧 Auto-corrected locus: {locus_name} → vWA")
        return 'vWA'

    # Keep Penta capitalization correct
    if locus_upper.startswith('PENTA '):
        parts = locus_name.split()
        if len(parts) == 2:
            corrected = f"Penta {parts[1].upper()}"
            logger.info(f"🔧 Auto-corrected locus: {locus_name} → {corrected}")
            return corrected

    # Return as-is if no correction needed
    return locus_name
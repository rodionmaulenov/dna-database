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


def check_parent_and_children_duplicates(extraction_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Intelligent duplicate detection with DNA fingerprint matching

    Rules:
    1. Parent-to-Parent match: BOTH alleles must match (same person)
    2. Parent-to-Child match: AT LEAST 1 allele must match (inheritance)
    3. Role matters: Father DNA ≠ Mother DNA

    Returns:
        {
            'parent_exists': bool,
            'existing_parent': Person | None,
            'new_children': List[Dict],
            'duplicate_children': List[Dict],
        }
    """
    parent_data = extraction_result.get('parent') or extraction_result.get('father', {})
    children_data = extraction_result.get('children', [])
    parent_role = extraction_result.get('parent_role', 'unknown')

    if not children_data:
        single_child = extraction_result.get('child')
        if single_child and single_child.get('loci'):
            children_data = [single_child]

    parent_loci = parent_data.get('loci', [])
    parent_name = parent_data.get('name', 'Unknown')

    # Critical loci for matching (most reliable)
    critical_loci = ['D8S1179', 'D21S11', 'D7S820', 'D3S1358', 'FGA', 'D13S317', 'D16S539']

    result = {
        'parent_exists': False,
        'existing_parent': None,  # Type: Person | None
        'new_children': [],
        'duplicate_children': [],
    }

    # Build uploaded parent fingerprint
    uploaded_fingerprint = _build_fingerprint(parent_loci, critical_loci)

    if len(uploaded_fingerprint) < 4:
        logger.info(f"Not enough loci for duplicate detection ({len(uploaded_fingerprint)}), treating as new")
        result['new_children'] = children_data
        return result

    # ✅ STEP 1: Find matching parent (same role only)
    if parent_role == 'father':
        candidate_parents = Person.objects.filter(role='father')
    elif parent_role == 'mother':
        candidate_parents = Person.objects.filter(role='mother')
    else:
        candidate_parents = Person.objects.filter(role__in=['father', 'mother'])

    logger.info(
        f"Checking {parent_name} ({parent_role}) with {len(uploaded_fingerprint)} critical loci "
        f"against {candidate_parents.count()} existing {parent_role}s"
    )

    existing_parent = None
    best_match_score = 0.0

    for candidate in candidate_parents:
        candidate_loci = DNALocus.objects.filter(
            person=candidate,
            locus_name__in=critical_loci
        )

        candidate_fingerprint = {}
        for locus in candidate_loci:
            allele_1 = str(locus.allele_1).strip()
            allele_2 = str(locus.allele_2 or '').strip()
            alleles = tuple(sorted([allele_1, allele_2]))
            candidate_fingerprint[locus.locus_name] = alleles

        # ✅ Compare with EXACT match (both alleles)
        matches, total_compared = _compare_fingerprints_exact(
            uploaded_fingerprint,
            candidate_fingerprint,
            critical_loci
        )

        if total_compared == 0:
            continue

        match_percentage = (matches / total_compared) * 100

        logger.info(
            f"  Comparing with {candidate.name}: "
            f"{matches}/{total_compared} loci match exactly ({match_percentage:.1f}%)"
        )

        # ✅ Parent match: 80%+ exact match
        if total_compared >= 4 and match_percentage >= 80:
            if match_percentage > best_match_score:
                best_match_score = match_percentage
                existing_parent = candidate

    if existing_parent:
        logger.info(
            f"✅ Found matching parent: {existing_parent.name} "
            f"(ID: {existing_parent.id}, {best_match_score:.1f}% match)"
        )
        result['parent_exists'] = True
        result['existing_parent'] = existing_parent

        # ✅ STEP 2: Check children
        if len(children_data) > 0:
            all_files_with_parent = existing_parent.uploaded_files.all()
            existing_children = Person.objects.filter(
                uploaded_files__in=all_files_with_parent,
                role='child'
            ).distinct()

            logger.info(
                f"  Parent has {existing_children.count()} existing children, "
                f"checking {len(children_data)} uploaded children"
            )

            for child_data in children_data:
                child_loci = child_data.get('loci', [])
                child_name = child_data.get('name', 'Unknown')
                child_fingerprint = _build_fingerprint(child_loci, critical_loci)

                if len(child_fingerprint) < 4:
                    logger.info(f"  Child {child_name}: Not enough loci, accepting as new")
                    result['new_children'].append(child_data)
                    continue

                is_duplicate = False

                for existing_child in existing_children:
                    existing_child_loci = DNALocus.objects.filter(
                        person=existing_child,
                        locus_name__in=critical_loci
                    )

                    existing_child_fingerprint = {}
                    for locus in existing_child_loci:
                        allele_1 = str(locus.allele_1).strip()
                        allele_2 = str(locus.allele_2 or '').strip()
                        alleles = tuple(sorted([allele_1, allele_2]))
                        existing_child_fingerprint[locus.locus_name] = alleles

                    # ✅ Child-to-child: EXACT match (both alleles)
                    child_matches, child_total = _compare_fingerprints_exact(
                        child_fingerprint,
                        existing_child_fingerprint,
                        critical_loci
                    )

                    if child_total >= 4:
                        child_match_percentage = (child_matches / child_total) * 100

                        logger.info(
                            f"  Child {child_name} vs {existing_child.name}: "
                            f"{child_matches}/{child_total} exact match ({child_match_percentage:.1f}%)"
                        )

                        # ✅ Child duplicate: 80%+ exact match
                        if child_match_percentage >= 80:
                            is_duplicate = True
                            result['duplicate_children'].append({
                                'name': child_name,
                                'person_id': existing_child.id
                            })
                            logger.info(f"  ❌ Child {child_name} is duplicate of {existing_child.name}")
                            break

                if not is_duplicate:
                    result['new_children'].append(child_data)
                    logger.info(f"  ✅ Child {child_name} is NEW")
        else:
            logger.info("  No children in upload - parent loci enrichment")

    else:
        logger.info(f"✅ {parent_name} ({parent_role}) is NEW")
        result['new_children'] = children_data

    return result


def _compare_fingerprints_exact(fp1: Dict, fp2: Dict, critical_loci: List[str]) -> tuple[int, int]:
    """
    Compare two DNA fingerprints with EXACT allele matching
    Used for person-to-person duplicate detection (not parent-child)

    Args:
        fp1: First fingerprint {locus_name: (allele1, allele2)}
        fp2: Second fingerprint {locus_name: (allele1, allele2)}
        critical_loci: List of locus names to compare

    Returns:
        (matches, total_compared) where match = both alleles identical
    """
    matches = 0
    total = 0

    for locus_name in critical_loci:
        if locus_name in fp1 and locus_name in fp2:
            total += 1

            # ✅ EXACT match: both alleles must be identical
            if fp1[locus_name] == fp2[locus_name]:
                matches += 1

    return matches, total


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
        errors: List[str],
        source_file: UploadedFile  # ✅ NEW parameter
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
                source_file=source_file  # ✅ Track source
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
    logger.info(f"Extraction result keys: {extraction_result.keys()}")

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

        # Case 1: Child-only upload (REJECT)
        if not has_parent and has_children:
            logger.error(f"Child-only upload rejected: {filename}")
            return {
                'success': False,
                'errors': ["Cannot save child without parent. Please upload file containing parent DNA."],
            }

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
                # Subcase A: Parent + children duplicate
                duplicate_names = []
                duplicate_person_ids = []

                for child in duplicate_children:
                    if isinstance(child, dict):
                        duplicate_names.append(child['name'])
                        duplicate_person_ids.append(child.get('person_id'))
                    else:
                        duplicate_names.append(child)

                parent_link = f"/table?personId={existing_parent.id} [parent]"
                child_links = ' '.join([
                    f"/table?personId={pid} [child]"
                    for pid in duplicate_person_ids if pid
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
                new_loci_count = _count_valid_loci(parent_loci)
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

        # Validate parent loci count
        if has_parent:
            valid_parent_count = _count_valid_loci(parent_loci)
            logger.info(f"Valid parent loci: {valid_parent_count}")

            if valid_parent_count < 10:
                logger.error(f"Only {valid_parent_count} parent loci in {filename}")
                return {
                    'success': False,
                    'errors': [f"Insufficient parent data ({valid_parent_count} loci). Need at least 10 loci."],
                }

        # Validate each child loci count
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

        # Check AI confidence for parent
        if has_parent:
            low_confidence_loci = []
            for locus in parent_loci:
                locus_name = locus.get('locus_name')
                if locus_name and locus_name.lower() in GENDER_MARKERS:
                    continue

                if locus.get('allele_1') is None or locus.get('allele_2') is None:
                    continue

                allele_1_confidence = _safe_confidence(locus.get('allele_1_confidence'))
                allele_2_confidence = _safe_confidence(locus.get('allele_2_confidence'))
                min_confidence = _safe_min(allele_1_confidence, allele_2_confidence)

                if min_confidence < 0.8:
                    low_confidence_loci.append(locus_name)

            if low_confidence_loci:
                logger.error(f"Low confidence parent extraction in {filename}: {low_confidence_loci}")
                errors.append(
                    f"AI couldn't read parent data clearly: {', '.join(low_confidence_loci)}. "
                    f"Please re-upload better quality PDF."
                )

        # Check AI confidence for children
        if has_children:
            for idx, child_data in enumerate(children_data):
                child_loci = child_data.get('loci', [])
                child_low_confidence = []

                for locus in child_loci:
                    locus_name = locus.get('locus_name')
                    if locus_name and locus_name.lower() in GENDER_MARKERS:
                        continue

                    if locus.get('allele_1') is None or locus.get('allele_2') is None:
                        continue

                    allele_1_confidence = _safe_confidence(locus.get('allele_1_confidence'))
                    allele_2_confidence = _safe_confidence(locus.get('allele_2_confidence'))
                    min_confidence = _safe_min(allele_1_confidence, allele_2_confidence)

                    if min_confidence < 0.8:
                        child_low_confidence.append(locus_name)

                if child_low_confidence:
                    logger.error(f"Low confidence child {idx + 1} extraction in {filename}: {child_low_confidence}")
                    errors.append(
                        f"AI couldn't read child {idx + 1} data clearly: {', '.join(child_low_confidence)}. "
                        f"Please re-upload better quality PDF."
                    )

        # Check overall quality
        overall_quality = extraction_result.get('overall_quality', 1.0)
        if overall_quality and overall_quality < 0.8:
            logger.error(f"Low overall extraction quality in {filename}: {overall_quality}")
            errors.append(
                f"Poor image quality detected (score: {overall_quality:.2f}). "
                f"Please re-upload clearer PDF."
            )

        # Stop if validation errors
        if errors:
            return {
                'success': False,
                'errors': errors,
            }

        # ═══════════════════════════════════════════════
        # SAVE TO DATABASE
        # ═══════════════════════════════════════════════

        with transaction.atomic():

            # Upload file to S3
            if settings.USE_S3:
                logger.info(f"📤 Uploading to S3: {filename}")
                try:
                    with open(local_file_path, 'rb') as local_file:
                        django_file = File(local_file, name=filename)
                        s3_file_path = default_storage.save(f'uploads/{filename}', django_file)
                        logger.info(f"✅ Uploaded to S3: {s3_file_path}")
                except Exception as s3_error:
                    logger.error(f"❌ S3 upload failed: {s3_error}")
                    return {
                        'success': False,
                        'errors': ["Failed to upload file to storage"],
                    }
            else:
                s3_file_path = f'uploads/{filename}'
                logger.info(f"💾 Local storage mode - path: {s3_file_path}")

            # Create uploaded file record
            uploaded_file = UploadedFile.objects.create(file=s3_file_path)

            # Handle parent
            if parent_exists and existing_parent:
                # Reuse existing parent
                parent_person = existing_parent

                # Merge new loci
                new_loci_added = _merge_loci_for_person(
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
                    role_label = (parent_data.get('role_label', '') or '').lower()

                    if 'mother' in role_label or 'мати' in role_label or 'мать' in role_label:
                        parent_role = 'mother'
                    elif 'father' in role_label or 'батько' in role_label or 'отец' in role_label:
                        parent_role = 'father'
                    else:
                        # Check Amelogenin
                        amelogenin = next(
                            (l for l in parent_loci if l.get('locus_name', '').lower() == 'amelogenin'),
                            None
                        )

                        if amelogenin:
                            allele_1 = str(amelogenin.get('allele_1', '')).upper()
                            allele_2 = str(amelogenin.get('allele_2', '')).upper()

                            if 'Y' in [allele_1, allele_2]:
                                parent_role = 'father'
                            else:
                                parent_role = 'mother'
                        else:
                            parent_role = 'father'

                parent_person = Person.objects.create(
                    role=parent_role,
                    name=parent_name,
                    loci_count=0
                )

                parent_saved_count = _save_person_loci(
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

                    child_saved_count = _save_person_loci(
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

            logger.info(f"✅ Successfully saved {filename}: Upload ID {uploaded_file.id}")

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
    Enhanced with D5S818 pattern recognition
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

        # ✅ D5S818 variations (MOST COMMON ERRORS)
        'D5S8l8': 'D5S818',  # lowercase L instead of 1
        'D5S8I8': 'D5S818',  # capital I instead of 1
        'D5S81B': 'D5S818',  # capital B instead of 8
        'D5SB18': 'D5S818',  # capital B instead of first 8
        'DSS818': 'D5S818',  # missing 5
        'D5S8lB': 'D5S818',  # L and B
        'D5SB1B': 'D5S818',  # B and B
        'D5S8IB': 'D5S818',  # I and B

        # D8S1179 variations
        'D8SI179': 'D8S1179',
        'D8S1I79': 'D8S1179',
        'D8SII79': 'D8S1179',
        'D8Sl179': 'D8S1179',
        'D8S1l79': 'D8S1179',

        # D6S1043 variations
        'D6S1O43': 'D6S1043',
        'D6Sl043': 'D6S1043',
        'D6S1O4B': 'D6S1043',

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

    # ✅ NEW: Pattern-based correction for D-loci (D + numbers + S + numbers)
    if locus_name.startswith('D') and 'S' in locus_name:
        # Apply character substitution rules
        fixed_name = locus_name

        # Replace common OCR confusions in the numeric parts
        # Split by 'S'
        parts = fixed_name.split('S', 1)
        if len(parts) == 2:
            prefix, suffix = parts

            # Fix prefix (D + numbers only)
            fixed_prefix = 'D'
            for char in prefix[1:]:  # Skip 'D'
                if char in ('l', 'I'):
                    fixed_prefix += '1'
                elif char in ('O', 'o'):
                    fixed_prefix += '0'
                elif char.isdigit():
                    fixed_prefix += char
                else:
                    fixed_prefix += char  # Keep as-is if unknown

            # Fix suffix (numbers only)
            fixed_suffix = ''
            for char in suffix:
                if char in ('l', 'I'):
                    fixed_suffix += '1'
                elif char in ('O', 'o'):
                    fixed_suffix += '0'
                elif char == 'B':
                    fixed_suffix += '8'
                elif char.isdigit():
                    fixed_suffix += char
                else:
                    fixed_suffix += char  # Keep as-is if unknown

            corrected = f"{fixed_prefix}S{fixed_suffix}"

            # Check if correction was made
            if corrected != locus_name:
                # Validate corrected name is in valid loci
                if corrected in DNALocus.LOCUS_NAMES:
                    logger.info(f"🔧 Pattern-corrected locus: {locus_name} → {corrected}")
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


def _build_fingerprint(loci_data, critical_loci):
    """
    Build DNA fingerprint from loci data

    Args:
        loci_data: List of locus dictionaries
        critical_loci: List of locus names to use for fingerprint

    Returns:
        Dict mapping locus_name to sorted allele tuple
    """
    fingerprint = {}

    for locus_data in loci_data:
        locus_name = locus_data.get('locus_name')

        # Skip gender markers
        if locus_name and locus_name.lower() in GENDER_MARKERS:
            continue

        # Only use critical loci
        if locus_name in critical_loci:
            allele_1 = str(locus_data.get('allele_1', '')).strip()
            allele_2 = str(locus_data.get('allele_2', '')).strip()

            # Skip if empty
            if allele_1 and allele_2:
                alleles = tuple(sorted([allele_1, allele_2]))
                fingerprint[locus_name] = alleles

    return fingerprint


def _compare_fingerprints(fp1, fp2, critical_loci):
    """
    Compare two DNA fingerprints

    Args:
        fp1: First fingerprint dict
        fp2: Second fingerprint dict
        critical_loci: List of locus names to compare

    Returns:
        Tuple of (matches, total_compared)
    """
    matches = 0
    total = 0

    for locus_name in critical_loci:
        if locus_name in fp1 and locus_name in fp2:
            total += 1
            if fp1[locus_name] == fp2[locus_name]:
                matches += 1

    return matches, total


def _merge_loci_for_person(
        person: Person,
        new_loci_data: List[Dict],
        filename: str,
        errors: List[str],
        source_file: UploadedFile
) -> int:
    """
    Merge new loci data into existing person
    - If locus exists: verify alleles match, keep existing
    - If locus is new: add it

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
        locus_name = _fix_common_ocr_errors(locus_name)

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
            # ✅ Verify alleles match
            existing_locus = existing_loci[locus_name]
            new_allele_1 = str(allele_1).strip()
            new_allele_2 = str(allele_2).strip()
            existing_allele_1 = str(existing_locus.allele_1).strip()
            existing_allele_2 = str(existing_locus.allele_2).strip()

            existing_alleles = set([existing_allele_1, existing_allele_2])
            new_alleles = set([new_allele_1, new_allele_2])

            if existing_alleles != new_alleles:
                logger.warning(
                    f"⚠️ Allele mismatch for {person.name} locus {locus_name}: "
                    f"Existing={existing_alleles} (from {existing_locus.source_file.file if existing_locus.source_file else 'unknown'}), "
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

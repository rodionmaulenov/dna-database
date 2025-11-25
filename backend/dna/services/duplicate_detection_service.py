"""
Duplicate detection service for DNA data
Uses fingerprint matching to identify existing persons
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from dna.models import Person, DNALocus
from dna.services.ocr_correction_service import build_fingerprint
from dna.constants import CRITICAL_LOCI

logger = logging.getLogger(__name__)


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

    result: Dict[str, Any] = {  # ✅ Fixed type hint
        'parent_exists': False,
        'existing_parent': None,
        'new_children': [],
        'duplicate_children': [],
    }

    # Build uploaded parent fingerprint
    uploaded_fingerprint = build_fingerprint(parent_loci, CRITICAL_LOCI)

    if len(uploaded_fingerprint) < 4:
        logger.info(f"Not enough loci for duplicate detection ({len(uploaded_fingerprint)}), treating as new")
        result['new_children'] = children_data
        return result

    # ✅ STEP 1: Find matching parent
    existing_parent = _find_matching_parent(
        parent_name=parent_name,
        parent_role=parent_role,
        uploaded_fingerprint=uploaded_fingerprint
    )

    if existing_parent:
        result['parent_exists'] = True
        result['existing_parent'] = existing_parent

        # ✅ STEP 2: Check children
        if len(children_data) > 0:
            new_children, duplicate_children = _check_children_duplicates(
                existing_parent=existing_parent,
                children_data=children_data
            )
            result['new_children'] = new_children
            result['duplicate_children'] = duplicate_children
        else:
            logger.info("  No children in upload - parent loci enrichment")

    else:
        logger.info(f"✅ {parent_name} ({parent_role}) is NEW")
        result['new_children'] = children_data

    return result


def _find_matching_parent(
        parent_name: str,
        parent_role: str,
        uploaded_fingerprint: Dict[str, Tuple[str, str]]
) -> Optional[Person]:
    """
    Find matching parent in database using fingerprint

    Args:
        parent_name: Name of parent to search
        parent_role: 'father', 'mother', or 'unknown'
        uploaded_fingerprint: DNA fingerprint dict

    Returns:
        Matching Person or None
    """
    # Filter by role
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
        # ✅ Build fingerprint from database (extracted to helper)
        candidate_fingerprint = _build_person_fingerprint(candidate, CRITICAL_LOCI)

        # Compare fingerprints
        matches, total_compared = compare_fingerprints_exact(
            uploaded_fingerprint,
            candidate_fingerprint,
            CRITICAL_LOCI
        )

        if total_compared == 0:
            continue

        match_percentage = (matches / total_compared) * 100

        logger.info(
            f"  Comparing with {candidate.name}: "
            f"{matches}/{total_compared} loci match exactly ({match_percentage:.1f}%)"
        )

        # Parent match: 80%+ exact match
        if total_compared >= 4 and match_percentage >= 80:
            if match_percentage > best_match_score:
                best_match_score = match_percentage
                existing_parent = candidate

    if existing_parent:
        logger.info(
            f"✅ Found matching parent: {existing_parent.name} "
            f"(ID: {existing_parent.pk}, {best_match_score:.1f}% match)"
        )

    return existing_parent


def _check_children_duplicates(
        existing_parent: Person,
        children_data: List[Dict[str, Any]]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Check uploaded children against existing children

    Args:
        existing_parent: Parent person from database
        children_data: List of uploaded children data

    Returns:
        (new_children, duplicate_children)
    """
    # Get existing children
    all_files_with_parent = existing_parent.uploaded_files.all()
    existing_children = Person.objects.filter(
        uploaded_files__in=all_files_with_parent,
        role='child'
    ).distinct()

    logger.info(
        f"  Parent has {existing_children.count()} existing children, "
        f"checking {len(children_data)} uploaded children"
    )

    new_children = []
    duplicate_children = []

    for child_data in children_data:
        child_loci = child_data.get('loci', [])
        child_name = child_data.get('name', 'Unknown')
        child_fingerprint = build_fingerprint(child_loci, CRITICAL_LOCI)

        if len(child_fingerprint) < 4:
            logger.info(f"  Child {child_name}: Not enough loci, accepting as new")
            new_children.append(child_data)
            continue

        is_duplicate = False

        for existing_child in existing_children:
            # ✅ Build fingerprint from database (extracted to helper)
            existing_child_fingerprint = _build_person_fingerprint(existing_child, CRITICAL_LOCI)

            # Child-to-child: EXACT match (both alleles)
            child_matches, child_total = compare_fingerprints_exact(
                child_fingerprint,
                existing_child_fingerprint,
                CRITICAL_LOCI
            )

            if child_total >= 4:
                child_match_percentage = (child_matches / child_total) * 100

                logger.info(
                    f"  Child {child_name} vs {existing_child.name}: "
                    f"{child_matches}/{child_total} exact match ({child_match_percentage:.1f}%)"
                )

                # Child duplicate: 80%+ exact match
                if child_match_percentage >= 80:
                    is_duplicate = True
                    duplicate_children.append({
                        'name': child_name,
                        'person_id': existing_child.pk
                    })
                    logger.info(f"  ❌ Child {child_name} is duplicate of {existing_child.name}")
                    break

        if not is_duplicate:
            new_children.append(child_data)
            logger.info(f"  ✅ Child {child_name} is NEW")

    return new_children, duplicate_children


def _build_person_fingerprint(
        person: Person,
        critical_loci: List[str]
) -> Dict[str, Tuple[str, str]]:
    """
    Build DNA fingerprint from person's loci in database

    Args:
        person: Person object from database
        critical_loci: List of locus names to include

    Returns:
        Fingerprint dict {locus_name: (allele1, allele2)}
    """
    person_loci = DNALocus.objects.filter(
        person=person,
        locus_name__in=critical_loci
    )

    fingerprint = {}
    for locus in person_loci:
        allele_1 = str(locus.allele_1).strip()
        allele_2 = str(locus.allele_2 or '').strip()
        alleles = tuple(sorted([allele_1, allele_2]))
        fingerprint[locus.locus_name] = alleles

    return fingerprint


def compare_fingerprints_exact(
        fp1: Dict[str, Tuple[str, str]],
        fp2: Dict[str, Tuple[str, str]],
        critical_loci: List[str]
) -> Tuple[int, int]:
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
            # EXACT match: both alleles must be identical
            if fp1[locus_name] == fp2[locus_name]:
                matches += 1

    return matches, total
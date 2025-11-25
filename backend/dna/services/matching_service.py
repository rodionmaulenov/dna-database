"""
DNA Matching Service
====================
Finds matching persons in database based on DNA loci comparison.

Usage:
    - Upload child PDF → Find matching fathers
    - Upload father PDF → Find matching children
    - Upload mother PDF → Find matching children
"""
import logging
from typing import List, Dict, Any, Tuple

from dna.models import Person
from dna.constants import GENDER_MARKERS

logger = logging.getLogger(__name__)


def find_matches(
    extracted_persons: List[Dict],
    search_roles: List[str],
    top_n: int = 3
) -> List[Dict[str, Any]]:
    """
    Find matching persons in database.

    Args:
        extracted_persons: List of extracted person data with alleles
        search_roles: List of roles to search for (['father', 'mother'] or ['child'])
        top_n: Number of top matches to return

    Returns:
        List of matches sorted by percentage:
        [
            {
                'person_id': 1,
                'name': 'John Doe',
                'role': 'father',
                'match_percentage': 100.0,
                'matching_loci': 16,
                'total_loci': 16,
            }
        ]
    """
    # Get the first person from extraction (usually the one we want to match)
    if not extracted_persons:
        logger.warning("No persons to match")
        return []

    # Use first person for matching
    uploaded_person = extracted_persons[0]
    uploaded_alleles = uploaded_person.get('alleles', {})
    uploaded_role = uploaded_person.get('role', 'unknown')

    logger.info(f"🔍 Finding matches for {uploaded_person.get('name', 'Unknown')} ({uploaded_role})")
    logger.info(f"   Searching in roles: {search_roles}")

    # Get candidates from database (all matching roles)
    candidates = Person.objects.filter(role__in=search_roles).prefetch_related('loci')

    logger.info(f"📊 Comparing against {candidates.count()} persons in database")

    matches = []

    for candidate in candidates:
        # Build candidate's alleles dict
        candidate_alleles = {}
        for locus in candidate.loci.all():
            if locus.locus_name.lower() not in GENDER_MARKERS:
                candidate_alleles[locus.locus_name] = [
                    str(locus.allele_1),
                    str(locus.allele_2)
                ]

        # Always use parent-child comparison (one allele must match)
        matching, total = compare_parent_child(uploaded_alleles, candidate_alleles)

        if total > 0:
            percentage = (matching / total) * 100

            matches.append({
                'person_id': candidate.pk,
                'name': candidate.name,
                'role': candidate.role,
                'match_percentage': round(percentage, 2),
                'matching_loci': matching,
                'total_loci': total,
            })

    # Sort by percentage (highest first)
    matches.sort(key=lambda x: x['match_percentage'], reverse=True)

    # Return top N
    top_matches = matches[:top_n]

    # Log results
    for match in top_matches:
        logger.info(
            f"  ✅ {match['name']} ({match['role']}): {match['match_percentage']}% "
            f"({match['matching_loci']}/{match['total_loci']} loci)"
        )

    return top_matches


def compare_exact(
    alleles1: Dict[str, List[str]],
    alleles2: Dict[str, List[str]]
) -> Tuple[int, int]:
    """
    Compare two persons for EXACT match (same person detection).
    Both alleles must match.

    Args:
        alleles1: First person's alleles {locus: [allele1, allele2]}
        alleles2: Second person's alleles

    Returns:
        (matching_loci, total_compared)
    """
    matching = 0
    total = 0

    for locus_name in alleles1:
        if locus_name.lower() in GENDER_MARKERS:
            continue

        if locus_name in alleles2:
            total += 1

            # Sort alleles for comparison
            set1 = set(alleles1[locus_name])
            set2 = set(alleles2[locus_name])

            if set1 == set2:
                matching += 1

    return matching, total


def compare_parent_child(
    child_alleles: Dict[str, List[str]],
    parent_alleles: Dict[str, List[str]]
) -> Tuple[int, int]:
    """
    Compare child and parent for inheritance match.
    At least ONE allele must match (child inherits one from each parent).

    Args:
        child_alleles: Child's alleles {locus: [allele1, allele2]}
        parent_alleles: Parent's alleles

    Returns:
        (matching_loci, total_compared)
    """
    matching = 0
    total = 0

    for locus_name in child_alleles:
        if locus_name.lower() in GENDER_MARKERS:
            continue

        if locus_name in parent_alleles:
            total += 1

            child_set = set(child_alleles[locus_name])
            parent_set = set(parent_alleles[locus_name])

            # At least one allele must match (inheritance)
            if child_set & parent_set:  # Intersection
                matching += 1

    return matching, total


def extract_and_match(
    file,
    search_roles: List[str],
    top_n: int = 3
) -> Dict[str, Any]:
    """
    Full pipeline: Extract DNA from PDF and find matches.
    Does NOT save to database.

    Args:
        file: Uploaded file object
        search_roles: List of roles to search for (['father', 'mother'] or ['child'])
        top_n: Number of top matches to return

    Returns:
        {
            'success': True/False,
            'extracted_person': {...},
            'top_matches': [...],
            'cost': {...},
            'error': '...'  # if failed
        }
    """
    import os
    from dna.utils.file_helpers import save_temp_file
    from dna.services.extraction_service import extract_from_pdf

    # Step 1: Save to temp
    temp_path = save_temp_file(file)
    logger.info(f"📁 Temp file: {temp_path}")

    try:
        # Step 2: Extract from PDF
        result = extract_from_pdf(temp_path)

        if not result.get('success'):
            return {
                'success': False,
                'error': result.get('error', 'Extraction failed'),
                'top_matches': [],
            }

        persons = result.get('persons', [])

        if not persons:
            return {
                'success': False,
                'error': 'No persons found in PDF',
                'top_matches': [],
            }

        # Step 3: Find matches
        top_matches = find_matches(persons, search_roles, top_n)

        return {
            'success': True,
            'extracted_person': {
                'name': persons[0].get('name', 'Unknown'),
                'role': persons[0].get('role', 'unknown'),
                'loci_count': len(persons[0].get('alleles', {})),
            },
            'top_matches': top_matches,
            'cost': result.get('cost', {}),
        }

    finally:
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info(f"🗑️ Cleaned up temp file: {temp_path}")
"""
DNA Matching Algorithm
Compares extracted DNA loci with database records to find matches
"""
import logging
from typing import Dict, Any, List
from dna.models import Person, DNALocus

logger = logging.getLogger(__name__)


def find_matches_for_extraction(
        extraction_result: Dict[str, Any],
        expected_role: str
) -> List[Dict[str, Any]]:
    """
    Find top 3 matching people in database based on DNA loci

    Args:
        extraction_result: Extracted DNA data from AI
        expected_role: 'father', 'mother', or 'child'

    Returns:
        List of top 3 matches with percentage
    """
    # Get extracted person's loci
    parent_data = extraction_result.get('parent') or extraction_result.get('father', {})
    parent_loci = parent_data.get('loci', [])

    child_data = extraction_result.get('child', {})
    child_loci = child_data.get('loci', [])

    # Determine which loci to use for matching
    if expected_role in ['father', 'mother']:
        # User uploaded parent → Use parent loci → Search for children
        uploaded_loci = parent_loci
        search_roles = ['child']
        logger.info(f"Searching for children matching uploaded {expected_role}")
    else:  # expected_role == 'child'
        # User uploaded child → Use child loci → Search for parents
        uploaded_loci = child_loci if child_loci else parent_loci
        search_roles = ['father', 'mother']
        logger.info(f"Searching for parents matching uploaded child")

    if not uploaded_loci:
        logger.warning("No loci data to match")
        return []

    # Get all potential matches from database
    potential_matches = Person.objects.filter(
        role__in=search_roles
    ).prefetch_related('loci')

    logger.info(f"Found {potential_matches.count()} potential matches in database")

    # Calculate match percentage for each
    match_results = []

    for candidate in potential_matches:
        candidate_loci = list(candidate.loci.all())

        match_score = calculate_match_percentage(uploaded_loci, candidate_loci)

        match_results.append({
            'person_id': candidate.id,
            'name': candidate.name,
            'role': candidate.role,
            'match_percentage': match_score['percentage'],
            'matching_loci': match_score['matching_count'],
            'total_loci': match_score['total_compared']
        })

    # Sort by match percentage (highest first)
    match_results.sort(key=lambda x: x['match_percentage'], reverse=True)

    # Return top 3
    top_3 = match_results[:3]

    for idx, match in enumerate(top_3, 1):
        logger.info(
            f"Match #{idx}: {match['name']} ({match['role']}) - "
            f"{match['match_percentage']}% ({match['matching_loci']}/{match['total_loci']} loci)"
        )

    return top_3


def calculate_match_percentage(
        uploaded_loci: List[Dict],
        database_loci: List[DNALocus]
) -> Dict[str, Any]:
    """
    Compare uploaded loci with database loci

    For parent-child matching: each locus should share at least 1 allele
    Example: Parent vWA=16,13 + Child vWA=11,13 → Match (shares "13")

    Args:
        uploaded_loci: List of dicts with locus_name, allele_1, allele_2
        database_loci: QuerySet of DNALocus objects

    Returns:
        {
            'percentage': 85.5,
            'matching_count': 17,
            'total_compared': 20
        }
    """
    # Convert uploaded loci to dict
    uploaded_dict = {}
    for locus in uploaded_loci:
        locus_name = locus.get('locus_name')
        allele_1 = locus.get('allele_1')
        allele_2 = locus.get('allele_2')

        # Skip gender markers
        if locus_name and locus_name.lower() in ['amelogenin', 'y indel', 'y-indel']:
            continue

        if locus_name and allele_1 and allele_2:
            uploaded_dict[locus_name] = (str(allele_1), str(allele_2))

    # Convert database loci to dict
    database_dict = {}
    for locus in database_loci:
        # Skip gender markers
        if locus.locus_name.lower() in ['amelogenin', 'y indel', 'y-indel']:
            continue

        if locus.allele_1 and locus.allele_2:
            database_dict[locus.locus_name] = (str(locus.allele_1), str(locus.allele_2))

    # Find common loci
    common_loci = set(uploaded_dict.keys()) & set(database_dict.keys())

    if not common_loci:
        return {
            'percentage': 0.0,
            'matching_count': 0,
            'total_compared': 0
        }

    matching_count = 0

    for locus_name in common_loci:
        uploaded_alleles = set(uploaded_dict[locus_name])
        database_alleles = set(database_dict[locus_name])

        # Check if at least one allele matches
        if uploaded_alleles & database_alleles:
            matching_count += 1

    percentage = (matching_count / len(common_loci)) * 100

    return {
        'percentage': round(percentage, 2),
        'matching_count': matching_count,
        'total_compared': len(common_loci)
    }
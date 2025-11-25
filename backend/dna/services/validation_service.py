"""
Validation utilities for DNA data
"""
import logging
from typing import List, Dict, Any

from dna.models import DNALocus
from dna.constants import GENDER_MARKERS

logger = logging.getLogger(__name__)


def count_valid_loci(loci: List[Dict]) -> int:
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


def safe_confidence(value: Any, default: float = 1.0) -> float:
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


def safe_min(val1: Any, val2: Any, default: float = 1.0) -> float:
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


def validate_loci_confidence(
        loci: List[Dict],
        filename: str,
        person_type: str = "parent",
        person_index: int = None
) -> List[str]:
    """
    Validate AI confidence for loci data

    Args:
        loci: List of locus data with confidence scores
        filename: Name of file being processed (for logging)
        person_type: "parent" or "child"
        person_index: For children, the child number (1, 2, etc.)

    Returns:
        List of error messages (empty if all valid)
    """
    errors = []
    low_confidence_loci = []

    for locus in loci:
        locus_name = locus.get('locus_name')

        # Skip gender markers
        if locus_name and locus_name.lower() in GENDER_MARKERS:
            continue

        # Skip empty loci
        if locus.get('allele_1') is None or locus.get('allele_2') is None:
            continue

        # Check confidence
        allele_1_confidence = safe_confidence(locus.get('allele_1_confidence'))
        allele_2_confidence = safe_confidence(locus.get('allele_2_confidence'))
        min_confidence = safe_min(allele_1_confidence, allele_2_confidence)

        if min_confidence < 0.8:
            low_confidence_loci.append(locus_name)

    # Build error message if low confidence found
    if low_confidence_loci:
        if person_type == "parent":
            log_msg = f"Low confidence parent extraction in {filename}: {low_confidence_loci}"
            error_msg = (
                f"AI couldn't read parent data clearly: {', '.join(low_confidence_loci)}. "
                f"Please re-upload better quality PDF."
            )
        else:  # child
            log_msg = f"Low confidence child {person_index} extraction in {filename}: {low_confidence_loci}"
            error_msg = (
                f"AI couldn't read child {person_index} data clearly: {', '.join(low_confidence_loci)}. "
                f"Please re-upload better quality PDF."
            )

        logger.error(log_msg)
        errors.append(error_msg)

    return errors


def validate_overall_quality(
        extraction_result: Dict[str, Any],
        filename: str
) -> List[str]:
    """
    Validate overall extraction quality

    Args:
        extraction_result: Full extraction result dict
        filename: Name of file being processed

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    overall_quality = extraction_result.get('overall_quality', 1.0)

    if overall_quality and overall_quality < 0.8:
        logger.error(f"Low overall extraction quality in {filename}: {overall_quality}")
        errors.append(
            f"Poor image quality detected (score: {overall_quality:.2f}). "
            f"Please re-upload clearer PDF."
        )

    return errors
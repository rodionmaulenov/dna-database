import logging

from dna.models import DNALocus
from dna.constants import GENDER_MARKERS

logger = logging.getLogger(__name__)


def fix_common_ocr_errors(locus_name: str) -> str:
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

def build_fingerprint(loci_data, critical_loci):
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

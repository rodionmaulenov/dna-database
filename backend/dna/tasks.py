import logging
import os

from celery import shared_task

from dna.pdf_processor import process_dna_report_pdf
from dna.agent_extractor import extract_dna_data_agent
from dna.database_saver import save_dna_extraction_to_database
from dna.dna_matcher import find_matches_for_extraction

logger = logging.getLogger(__name__)


@shared_task
def process_file_upload(file_path, filename):
    """
    Process uploaded DNA test PDF file with smart page detection

    Args:
        file_path: Absolute path to uploaded PDF
        filename: Original filename

    Returns:
        dict with success, errors (NO warnings)
    """
    try:
        # Validate file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {
                "success": False,
                # "warnings": [],  # ❌ DELETE
                "errors": ["File upload failed"],
            }

        logger.info(f"Processing file: {filename}")

        # ⭐ STEP 1: Process PDF with smart detection
        logger.info("Step 1: Processing PDF with smart page detection")
        processed_images = process_dna_report_pdf(
            pdf_path=file_path,
            enhance=True,
            detect_tables=True
        )

        if not processed_images:
            logger.error(f"No images extracted from PDF: {filename}")
            return {
                "success": False,
                "errors": ["Could not read DNA data from file"],
            }

        logger.info(f"Processed {len(processed_images)} page(s) with DNA tables")

        # ⭐ STEP 2: Extract DNA data with AI
        logger.info("Step 2: Extracting DNA data with AI")
        extraction_result = extract_dna_data_agent(
            images=processed_images,
        )

        # Check extraction success
        if not extraction_result.get('success', False):
            error_detail = extraction_result.get('error', 'Unknown error')
            logger.error(f"AI extraction failed for {filename}: {error_detail}")
            return {
                "success": False,
                "errors": [error_detail],
            }

        logger.info(f"✅ AI extraction successful for {filename}")

        # ⭐ STEP 3: Save to database
        logger.info("Step 3: Saving to database")
        db_result = save_dna_extraction_to_database(
            extraction_result=extraction_result,
            filename=filename,
            local_file_path=file_path
        )

        if not db_result.get('success', False):
            logger.error(f"Database save failed for {filename}")
            return {
                "success": False,
                "errors": db_result.get('errors', ['Failed to save to database']),
            }

        logger.info(f"✅ Successfully processed {filename}")

        return {
            "success": True,
            "errors": [],
        }

    except FileNotFoundError as e:
        logger.error(f"FileNotFoundError: {e}", exc_info=True)
        return {
            "success": False,
            "errors": ["File upload failed"],
        }

    except ValueError as e:
        logger.error(f"ValueError for {filename}: {e}", exc_info=True)
        return {
            "success": False,
            "errors": ["Could not read DNA data from file"],
        }

    except Exception as e:
        logger.error(f"Unexpected error processing {filename}: {e}", exc_info=True)
        return {
            "success": False,
            "errors": ["An unexpected error occurred"],
        }


@shared_task
def match_file_task(file_path, filename, role):
    """
    Extract DNA and find matches - does NOT save to database

    Args:
        file_path: Absolute path to uploaded PDF
        filename: Original filename
        role: Expected role ('father', 'mother', or 'child')

    Returns:
        dict with success, errors, top_matches (NO warnings)
    """
    try:
        # Validate file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {
                "success": False,
                "errors": ["File upload failed"],
            }

        logger.info(f"Matching file: {filename} as {role}")

        # ⭐ STEP 1: Process PDF (same as upload)
        logger.info("Step 1: Processing PDF")
        processed_images = process_dna_report_pdf(
            pdf_path=file_path,
            enhance=True,
            detect_tables=True
        )

        if not processed_images:
            logger.error(f"No images extracted from PDF: {filename}")
            return {
                "success": False,
                "errors": ["Could not read DNA data from file"],
            }

        logger.info(f"Processed {len(processed_images)} page(s)")

        # ⭐ STEP 2: Extract DNA with AI
        logger.info("Step 2: Extracting DNA data with AI")
        extraction_result = extract_dna_data_agent(
            images=processed_images,
        )

        # Check extraction success
        if not extraction_result.get('success', False):
            error_detail = extraction_result.get('error', 'Unknown error')
            logger.error(f"AI extraction failed for {filename}: {error_detail}")
            return {
                "success": False,
                "errors": [error_detail],
            }

        logger.info(f"✅ AI extraction successful for {filename}")

        # ⭐ STEP 3: Find matches
        logger.info("Step 3: Finding matches in database")

        top_matches = find_matches_for_extraction(
            extraction_result=extraction_result,
            expected_role=role
        )

        logger.info(f"✅ Found {len(top_matches)} matches for {filename}")

        return {
            "success": True,
            "errors": [],
            "top_matches": top_matches
        }

    except Exception as e:
        logger.error(f"Unexpected error matching {filename}: {e}", exc_info=True)
        return {
            "success": False,
            "errors": ["An unexpected error occurred"],
        }
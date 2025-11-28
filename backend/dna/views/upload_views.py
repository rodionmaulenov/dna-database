import logging

from ninja import File, UploadedFile as NinjaUploadedFile, Router, Form

from dna.schemas import FileUploadResponse, MatchResult
from dna.services.extraction_service import extract_and_save
from dna.services.matching_service import extract_and_match

logger = logging.getLogger(__name__)
upload_router = Router()


@upload_router.post('file/', response={200: dict, 400: FileUploadResponse})
def upload_file(request, file: File[NinjaUploadedFile]):
    """
    Upload DNA PDF file, extract data, and save to database.

    Full pipeline:
    1. Extract DNA data with Textract + Claude
    2. Validate and check duplicates
    3. Save to database (S3/local + PostgreSQL)
    4. Return results
    """
    try:
        logger.info(f"📤 Received file: {file.name}")

        result = extract_and_save(file, file.name)

        if result.get('success') and result.get('saved_to_db'):
            return 200, result
        else:
            errors = result.get('save_errors') or result.get('errors') or [result.get('error', 'Unknown error')]
            links = result.get('links', [])  # ← ADD

            return 400, FileUploadResponse(
                success=False,
                errors=errors,
                links=links  # ← ADD
            )

    except Exception as e:
        logger.error(f"❌ upload_file error: {e}", exc_info=True)
        return 400, FileUploadResponse(
            success=False,
            errors=["Server error occurred"],
            links=[]  # ← ADD
        )


# ============================================================
# TEST ENDPOINT (extraction only, no save)
# ============================================================

@upload_router.post('test/', response={200: dict, 400: dict})
def test_extraction(request, file: File[NinjaUploadedFile]):
    """
    Test endpoint - extract only, don't save to database.
    """
    from dna.utils.file_helpers import save_temp_file
    from dna.services import extract_from_pdf
    import os

    try:
        logger.info(f"🧪 Test extraction: {file.name}")

        temp_path = save_temp_file(file)
        result = extract_from_pdf(temp_path)

        if os.path.exists(temp_path):
            os.remove(temp_path)

        if result.get('success'):
            return 200, result
        else:
            return 400, {'error': result.get('error', 'Extraction failed')}

    except Exception as e:
        logger.error(f"❌ test_extraction error: {e}", exc_info=True)
        return 400, {'error': str(e)}


# ============================================================
# MATCH ENDPOINT (extract + find matches, no save)
# ============================================================

@upload_router.post('match/', response={200: FileUploadResponse, 400: FileUploadResponse})
def match_file(request, file: File[NinjaUploadedFile], role: str = Form(...)):
    """
    Upload DNA PDF and find matching persons in database.
    Does NOT save to database.

    Args:
        file: PDF file to upload
        role: Role of uploaded person:
            - 'parent' (father/mother) → searches for matching children
            - 'child' → searches for matching parents (fathers AND mothers)

    Returns:
        Top 3 matches with percentages
    """
    try:
        logger.info(f"🔍 Match request: {file.name}, uploaded role: {role}")

        # Validate role
        if role not in ['parent', 'child']:
            return 400, FileUploadResponse(
                success=False,
                errors=["Invalid role. Must be 'parent' or 'child'"]
            )

        # Determine what to search for
        if role == 'parent':
            # Parent uploaded → find children
            search_roles = ['child']
        else:
            # Child uploaded → find parents (both father and mother)
            search_roles = ['father', 'mother']

        # Extract and match
        result = extract_and_match(file, search_roles, top_n=3)

        if result.get('success'):
            # Convert to MatchResult objects
            top_matches = [
                MatchResult(
                    person_id=m['person_id'],
                    name=m['name'],
                    role=m['role'],
                    match_percentage=m['match_percentage'],
                    matching_loci=m['matching_loci'],
                    total_loci=m['total_loci'],
                )
                for m in result.get('top_matches', [])
            ]

            return 200, FileUploadResponse(
                success=True,
                top_matches=top_matches,
            )
        else:
            return 400, FileUploadResponse(
                success=False,
                errors=[result.get('error', 'Matching failed')]
            )

    except Exception as e:
        logger.error(f"❌ match_file error: {e}", exc_info=True)
        return 400, FileUploadResponse(
            success=False,
            errors=["Server error occurred"]
        )

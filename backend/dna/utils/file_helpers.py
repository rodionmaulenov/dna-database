"""
File handling utilities
"""
import os
import logging
from typing import Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


def validate_pdf_file(file) -> Tuple[bool, str]:
    """
    Validate that uploaded file is PDF

    Returns:
        (is_valid, error_message)
    """
    if not file.content_type == 'application/pdf':
        logger.warning(f"Invalid file type uploaded: {file.content_type}")
        return False, "Only PDF files are allowed"
    return True, ""


def save_temp_file(file) -> str:
    """
    Save uploaded file to temporary directory

    Args:
        file: Uploaded file object

    Returns:
        Path to saved temporary file
    """
    temp_dir = os.path.join(settings.BASE_DIR, 'media/uploads')
    os.makedirs(temp_dir, exist_ok=True)

    local_file_path = os.path.join(temp_dir, file.name)

    with open(local_file_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)

    logger.info(f"✅ Saved temp file: {local_file_path}")
    return local_file_path


def cleanup_temp_file(file_path: str) -> None:
    """
    Delete temporary file

    Args:
        file_path: Path to file to delete
    """
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"🗑️ Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to cleanup {file_path}: {e}")


def delete_uploaded_files(uploaded_files) -> int:
    """
    Delete multiple UploadedFile objects and their physical files

    Args:
        uploaded_files: QuerySet of UploadedFile objects

    Returns:
        Number of files deleted
    """
    count = 0
    for file_obj in uploaded_files:
        if file_obj.file:
            file_obj.file.delete(save=False)
            logger.info(f"  Deleted file: {file_obj.file.name}")
        file_obj.delete()
        count += 1
    return count
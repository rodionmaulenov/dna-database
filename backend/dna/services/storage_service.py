"""
Unified Storage Service for S3 and Local File Storage
Handles file uploads, deletions, and URL generation
"""
import os
import glob
import logging
from typing import Optional

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


class StorageService:
    """
    Unified interface for file storage operations
    Automatically switches between S3 and local storage based on settings.USE_S3
    """

    def __init__(self):
        """Initialize storage service and cache S3 client if needed"""
        self.use_s3 = settings.USE_S3
        self._s3_client = None

        if self.use_s3:
            import boto3
            from botocore.client import Config

            self._s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
                config=Config(signature_version='s3v4')
            )
            logger.info(f"✅ S3 client initialized: {settings.AWS_STORAGE_BUCKET_NAME}")
        else:
            logger.info(f"✅ Local storage initialized: {settings.MEDIA_ROOT}")

    def save_file(self, file: File, filename: str) -> str:
        """
        Save file to storage (S3 or local)

        Args:
            file: Django File object
            filename: Desired filename

        Returns:
            str: File path in storage (e.g., 'uploads/file.pdf')
        """
        file_path = f'uploads/{filename}'

        try:
            if self.use_s3:
                # Upload to S3
                saved_path = default_storage.save(file_path, file)
                logger.info(f"✅ Uploaded to S3: {saved_path}")
                return saved_path
            else:
                # Save locally
                saved_path = default_storage.save(file_path, file)
                logger.info(f"✅ Saved locally: {saved_path}")
                return saved_path

        except Exception as e:
            logger.error(f"❌ Failed to save file {filename}: {e}")
            raise

    def delete_file(self, file_path: str) -> bool:
        """
        Delete file from storage (S3 or local)

        Args:
            file_path: Path to file in storage (e.g., 'uploads/file.pdf')

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if not file_path:
            logger.warning("⚠️ Empty file path, skipping deletion")
            return False

        try:
            if self.use_s3:
                # Delete from S3
                self._s3_client.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=file_path
                )
                logger.info(f"✅ Deleted from S3: {file_path}")
                return True
            else:
                # Delete from local filesystem
                full_path = os.path.join(settings.MEDIA_ROOT, file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
                    logger.info(f"✅ Deleted locally: {file_path}")
                    return True
                else:
                    logger.warning(f"⚠️ File not found: {file_path}")
                    return False

        except Exception as e:
            logger.error(f"❌ Failed to delete file {file_path}: {e}")
            return False

    def generate_url(self, file_path: str, expires_in: int = 3600) -> str:
        """
        Generate download URL for file (presigned for S3, local URL for filesystem)

        Args:
            file_path: Path to file in storage (e.g., 'uploads/file.pdf')
            expires_in: URL expiration time in seconds (default: 3600 = 1 hour)

        Returns:
            str: Download URL
        """
        if not file_path:
            logger.warning("⚠️ Empty file path")
            return ''

        try:
            if self.use_s3:
                # Generate presigned URL
                url = self._s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                        'Key': file_path
                    },
                    ExpiresIn=expires_in
                )
                logger.debug(f"Generated S3 URL for {file_path}")
                return url
            else:
                # Generate local URL
                url = default_storage.url(file_path)
                logger.debug(f"Generated local URL for {file_path}")
                return f"{settings.BACKEND_URL}{url}"

        except Exception as e:
            logger.error(f"❌ Failed to generate URL for {file_path}: {e}")
            return file_path  # Fallback to path

    @staticmethod
    def cleanup_temp_uploads() -> None:
        """
        Remove all temporary files from uploads folder.
        """
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')

        if not os.path.exists(upload_dir):
            return

        for file_path in glob.glob(f'{upload_dir}/*'):
            try:
                os.remove(file_path)
                logger.debug(f"🗑️ Removed temp file: {file_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to remove {file_path}: {e}")


# Singleton instance
_storage_service_instance: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """
    Get singleton instance of StorageService

    Returns:
        StorageService: Cached storage service instance
    """
    global _storage_service_instance

    if _storage_service_instance is None:
        _storage_service_instance = StorageService()

    return _storage_service_instance
import io
import logging
import boto3
from PIL import Image
from django.conf import settings

logger = logging.getLogger(__name__)


class TextractService:
    def __init__(self):
        self.client = boto3.client(
            'textract',
            region_name=settings.AWS_TEXTRACT_REGION_NAME,
            aws_access_key_id=settings.AWS_TEXTRACT_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_TEXTRACT_SECRET_ACCESS_KEY
        )
        logger.info("✅ Textract client initialized")

    def extract_raw(self, image: Image.Image) -> dict:
        """
        Extract from image, return RAW Textract response
        """
        # Convert PIL Image to bytes
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()

        # Call Textract
        response = self.client.analyze_document(
            Document={'Bytes': img_bytes},
            FeatureTypes=['TABLES']
        )

        logger.info(f"✅ Textract returned {len(response.get('Blocks', []))} blocks")

        return response
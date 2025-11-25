"""
PDF Processing Utility for DNA Report Extraction
Converts PDF to images and enhances quality for better AI recognition
"""
import os
import io
import logging
import cv2
import numpy as np

from pathlib import Path
from typing import List, Tuple
from PIL import Image
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)


def detect_dna_page_with_textract(image: Image.Image, textract_client) -> Tuple[bool, int]:
    """
    Fast detection using AWS Textract (1-2 seconds per page)

    Args:
        image: PIL Image of page
        textract_client: Boto3 Textract client

    Returns:
        (is_dna_page: bool, score: int)
    """
    try:
        # Convert PIL image to bytes
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # Call Textract
        response = textract_client.analyze_document(
            Document={'Bytes': img_bytes.read()},
            FeatureTypes=['TABLES']
        )

        # Extract all text
        text = ''
        for block in response.get('Blocks', []):
            if block.get('Text'):
                text += block['Text'].lower() + ' '

        # DNA keywords for scoring
        dna_keywords = [
            'd3s1358', 'd8s1179', 'd21s11', 'd7s820', 'vwa', 'fga',
            'tpox', 'csf1po', 'd5s818', 'd16s539', 'd13s317', 'd2s1338',
            'locus', 'allele', 'father', 'mother', 'child', 'paternity',
            'amelogenin', 'penta'
        ]

        # Count matches
        score = sum(keyword in text for keyword in dna_keywords)

        # DNA page if 3+ keywords found
        is_dna_page = score >= 3

        logger.info(f"Textract detection: score={score}, is_dna_page={is_dna_page}")
        return is_dna_page, score

    except Exception as e:
        logger.error(f"Textract detection failed: {e}")
        return True, 0  # Fallback: assume it's a DNA page


class PDFProcessor:
    """Handle PDF to image conversion and enhancement for DNA reports"""

    def __init__(self, dpi: int = 300, output_format: str = 'PNG'):
        """
        Initialize PDF processor

        Args:
            dpi: Resolution for PDF conversion (higher = better quality, default 300)
            output_format: Image format (PNG or JPEG)
        """
        self.dpi = dpi
        self.output_format = output_format.upper()

    def convert_pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """
        Convert PDF pages to PIL Images

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of PIL Image objects (one per page)
        """
        try:
            images = convert_from_path(
                pdf_path,
                dpi=self.dpi,
                fmt=self.output_format.lower(),
                thread_count=2
            )
            logger.info(f"Converted {len(images)} pages from PDF")
            return images

        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            raise

    def enhance_image(self, image: Image.Image,
                      deskew: bool = True,
                      denoise: bool = True,
                      enhance_contrast: bool = True) -> Image.Image:
        """
        Enhance image quality for better OCR/AI recognition

        Args:
            image: PIL Image object
            deskew: Apply deskewing to straighten image
            denoise: Apply denoising filter
            enhance_contrast: Enhance contrast and sharpness

        Returns:
            Enhanced PIL Image
        """
        # Convert PIL to OpenCV format
        img_cv = self._pil_to_cv2(image)

        # Convert to grayscale for processing
        if len(img_cv.shape) == 3:
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_cv

        # Apply deskewing
        if deskew:
            gray = self._deskew_image(gray)

        # Apply denoising
        if denoise:
            gray = self._denoise_image(gray)

        # Enhance contrast
        if enhance_contrast:
            gray = self._enhance_contrast(gray)

        # Convert back to PIL
        enhanced_image = Image.fromarray(gray)

        return enhanced_image

    @staticmethod
    def auto_rotate_to_portrait(image: Image.Image) -> Image.Image:
        """
        Automatically rotate image to portrait orientation if it's landscape

        Args:
            image: PIL Image object

        Returns:
            Rotated image in portrait orientation
        """
        width, height = image.size

        # If width > height, it's landscape - rotate 90 degrees
        if width > height:
            logger.info(f"Image is landscape ({width}x{height}), rotating to portrait")
            rotated = image.rotate(90, expand=True)
            logger.info(f"Rotated to portrait: {rotated.size}")
            return rotated

        logger.debug(f"Image already in portrait orientation ({width}x{height})")
        return image

    @staticmethod
    def _deskew_image(image: np.ndarray) -> np.ndarray:
        """
        Deskew (straighten) the image using text line detection

        Args:
            image: Grayscale OpenCV image

        Returns:
            Deskewed image
        """
        try:
            # Apply threshold to get binary image
            _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # Find contours
            coords = np.column_stack(np.where(binary > 0))

            if len(coords) < 10:
                return image

            # Calculate rotation angle
            angle = cv2.minAreaRect(coords)[-1]

            # Adjust angle
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            # Only apply rotation if angle is significant (> 0.5 degrees)
            if abs(angle) > 0.5:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)

                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(
                    image, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )

                logger.info(f"Deskewed image by {angle:.2f} degrees")
                return rotated

            return image

        except Exception as e:
            logger.error(f"Deskewing failed: {e}, returning original")
            return image

    @staticmethod
    def _denoise_image(image: np.ndarray) -> np.ndarray:
        """
        Apply denoising to reduce artifacts and noise

        Args:
            image: Grayscale OpenCV image

        Returns:
            Denoised image
        """
        try:
            denoised = cv2.fastNlMeansDenoising(image, None, h=10, templateWindowSize=7, searchWindowSize=21)
            logger.info("Applied denoising filter")
            return denoised

        except Exception as e:
            logger.error(f"Denoising failed: {e}, returning original")
            return image

    @staticmethod
    def _enhance_contrast(image: np.ndarray) -> np.ndarray:
        """
        Enhance contrast using adaptive histogram equalization

        Args:
            image: Grayscale OpenCV image

        Returns:
            Contrast-enhanced image
        """
        try:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(image)

            kernel = np.array([[-1, -1, -1],
                               [-1, 9, -1],
                               [-1, -1, -1]])
            sharpened = cv2.filter2D(enhanced, -1, kernel)

            logger.info("Enhanced contrast and sharpness")
            return sharpened

        except Exception as e:
            logger.error(f"Contrast enhancement failed: {e}, returning original")
            return image

    @staticmethod
    def _pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
        """Convert PIL Image to OpenCV format"""
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    @staticmethod
    def _cv2_to_pil(cv_image: np.ndarray) -> Image.Image:
        """Convert OpenCV image to PIL format"""
        return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))

    def process_pdf(self, pdf_path: str,
                    enhance: bool = True,
                    detect_tables: bool = True,
                    textract_client=None,
                    return_best_page_only: bool = False,
                    save_images: bool = False,
                    output_dir: str = None) -> List[Image.Image]:
        """
        Complete pipeline: Convert PDF to images and optionally enhance

        Args:
            pdf_path: Path to PDF file
            enhance: Apply image enhancement
            detect_tables: Use Textract detection to filter DNA table pages
            textract_client: Textract client for fast detection (if None, process all pages)
            return_best_page_only: If True, return only the best DNA page
            save_images: Save processed images to disk
            output_dir: Directory to save images

        Returns:
            List of processed PIL Images
        """
        # Convert PDF to images
        images = self.convert_pdf_to_images(pdf_path)

        # ✅ Fast Textract-based detection
        if detect_tables and textract_client:
            logger.info(f"Detecting DNA table pages with Textract...")

            dna_pages = []
            page_scores = []

            for idx, img in enumerate(images):
                is_dna, score = detect_dna_page_with_textract(img, textract_client)
                if is_dna:
                    dna_pages.append(idx)
                    page_scores.append((idx, score))
                    logger.info(f"✅ Page {idx + 1}: DNA table (score: {score})")
                else:
                    logger.info(f"⏭️ Page {idx + 1}: Not DNA table (score: {score})")

            # If no pages detected, process all
            if not dna_pages:
                logger.warning("⚠️ No DNA tables detected, processing all pages")
                dna_pages = list(range(len(images)))

            # Select best page if requested
            if return_best_page_only and len(page_scores) > 1:
                best = max(page_scores, key=lambda x: x[1])
                dna_pages = [best[0]]
                logger.info(f"🎯 Selected best page: {best[0] + 1} (score: {best[1]})")

            # Filter images
            images = [images[i] for i in dna_pages]
            logger.info(f"Processing {len(images)} DNA table pages")

        elif detect_tables:
            # No textract client provided - process all pages
            logger.info(f"No Textract client, processing all {len(images)} pages")

        # Auto-rotate and enhance each image
        processed_images = []
        for idx, img in enumerate(images):
            logger.info(f"Processing page {idx + 1}/{len(images)}")

            # Rotate to portrait
            rotated = self.auto_rotate_to_portrait(img)

            # Enhance if requested
            if enhance:
                enhanced = self.enhance_image(
                    rotated,
                    deskew=False,
                    denoise=True,
                    enhance_contrast=True
                )
                processed_images.append(enhanced)
            else:
                processed_images.append(rotated)

        # Optionally save images
        if save_images and output_dir:
            self._save_images(processed_images, pdf_path, output_dir)

        return processed_images

    @staticmethod
    def _save_images(images: List[Image.Image], pdf_path: str, output_dir: str):
        """Save images to disk"""
        os.makedirs(output_dir, exist_ok=True)
        pdf_name = Path(pdf_path).stem

        for idx, img in enumerate(images):
            output_path = os.path.join(output_dir, f"{pdf_name}_page_{idx + 1}.png")
            img.save(output_path, 'PNG')
            logger.info(f"Saved enhanced image: {output_path}")


# ⭐ STANDALONE FUNCTIONS

def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[Image.Image]:
    """Convert PDF to images"""
    processor = PDFProcessor(dpi=dpi)
    return processor.convert_pdf_to_images(pdf_path)


def enhance_image_for_ocr(image: Image.Image) -> Image.Image:
    """Enhance single image for OCR/AI"""
    processor = PDFProcessor()
    rotated = processor.auto_rotate_to_portrait(image)
    enhanced = processor.enhance_image(
        rotated,
        deskew=False,
        denoise=True,
        enhance_contrast=True
    )
    return enhanced


def process_dna_report_pdf(
    pdf_path: str,
    enhance: bool = True,
    detect_tables: bool = True,
    textract_client=None,
    best_page_only: bool = False
) -> List[Image.Image]:
    """
    Process DNA report PDF with Textract detection

    Args:
        pdf_path: Path to PDF file
        enhance: Apply image enhancement
        detect_tables: Use Textract detection
        textract_client: Textract client for detection
        best_page_only: If True, return only the best DNA page

    Returns:
        List of processed images ready for AI extraction
    """
    processor = PDFProcessor(dpi=300)
    images = processor.process_pdf(
        pdf_path,
        enhance=enhance,
        detect_tables=detect_tables,
        textract_client=textract_client,
        return_best_page_only=best_page_only
    )
    return images
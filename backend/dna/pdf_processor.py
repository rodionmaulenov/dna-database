"""
PDF Processing Utility for DNA Report Extraction
Converts PDF to images and enhances quality for better AI recognition
"""
import os
import re
import logging
import cv2
import numpy as np

from pathlib import Path
from typing import List
from PIL import Image
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)


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
            # Rotate 90 degrees counter-clockwise
            rotated = image.rotate(90, expand=True)
            logger.info(f"Rotated to portrait: {rotated.size}")
            return rotated

        logger.debug(f"Image already in portrait orientation ({width}x{height})")
        return image

    @staticmethod
    def detect_dna_table_pages(images: List[Image.Image], return_best_only: bool = False,
                               prefer_english: bool = True) -> List[int]:
        """
        Detect which pages contain DNA tables using multiple strategies

        Args:
            images: List of PIL images (one per page)
            return_best_only: If True, return only the page with highest score
            prefer_english: If True, prefer English pages over Ukrainian/other languages

        Returns:
            List of page indices that contain DNA tables
        """
        try:
            import pytesseract
        except ImportError:
            logger.warning("⚠️ pytesseract not installed, processing all pages")
            return list(range(len(images)))

        logger.info(f"Analyzing {len(images)} pages to detect DNA tables...")

        dna_table_pages = []
        page_scores = []
        page_texts = {}  # Store OCR text for language detection

        # ⭐ DEFINE KEYWORDS
        table_keywords = [
            # Column headers
            'locus', 'локус', 'locul',
            'allele', 'алель', 'allelă',
            'father', 'батько', 'alleged father', 'передбачуваний батько',
            'mother', 'мати', 'anya', 'ана',
            'child', 'дитина', 'дитя', 'copil',

            # Common locus names
            'd3s1358', 'd8s1179', 'd21s11', 'd7s820', 'd16s539',
            'vwa', 'fga', 'tpox', 'csf1po', 'd18s51', 'd5s818',
            'd13s317', 'd2s1338', 'penta', 'amelogenin', 'амелогенін',

            # Report-specific terms
            'paternity', 'батькість', 'paternitate',
            'dna test', 'днк тест', 'днк-тест',
            'genotype', 'генотип',
            'материнство', 'maternity',
            'combined paternity index', 'комбінований індекс'
        ]

        # ⭐ DEFINE PATTERNS
        locus_pattern = re.compile(r'd\d{1,2}s\d{3,4}', re.IGNORECASE)
        allele_pattern = re.compile(r'\b\d{1,2}(?:\.\d)?\s*[,/]\s*\d{1,2}(?:\.\d)?\b')

        for idx, image in enumerate(images):
            page_num = idx + 1
            score = 0

            try:
                # Quick OCR
                text = pytesseract.image_to_string(image, lang='eng+ukr+rus').lower()
                text_clean = ' '.join(text.split())
                page_texts[idx] = text_clean  # Store for language detection

                # SCORING SYSTEM

                # 1. Keyword matching (1 point per keyword, max 15)
                keyword_matches = sum(1 for keyword in table_keywords if keyword in text_clean)
                keyword_score = min(keyword_matches, 15)
                score += keyword_score

                # 2. Locus pattern matching (5 points per match, max 25)
                locus_matches = locus_pattern.findall(text_clean)
                locus_score = min(len(locus_matches) * 5, 25)
                score += locus_score

                # 3. Allele pattern matching (2 points per match, max 20)
                allele_matches = allele_pattern.findall(text)
                allele_score = min(len(allele_matches) * 2, 20)
                score += allele_score

                # 4. Table structure detection (10 points)
                if '|' in text or '\t' in text or text.count('\n') > 15:
                    score += 10

                # 5. Numbers concentration (10 points if > 10% digits)
                digit_count = sum(c.isdigit() for c in text)
                digit_ratio = digit_count / max(len(text), 1)
                if digit_ratio > 0.1:
                    score += 10

                # ⭐ DECISION LOGIC
                has_loci = len(locus_matches) > 0
                has_alleles = len(allele_matches) > 5
                threshold = 30

                if score >= threshold and (has_loci or has_alleles):
                    logger.info(
                        f"✅ Page {page_num}: DNA table detected "
                        f"(score: {score}, keywords: {keyword_matches}, "
                        f"loci: {len(locus_matches)}, alleles: {len(allele_matches)})"
                    )
                    dna_table_pages.append(idx)
                    page_scores.append((idx, score))
                else:
                    logger.info(
                        f"⏭️ Page {page_num}: Not a DNA table "
                        f"(score: {score}, keywords: {keyword_matches}, "
                        f"loci: {len(locus_matches)}, alleles: {len(allele_matches)})"
                    )

            except Exception as e:
                logger.warning(f"⚠️ Page {page_num}: Detection failed, including it: {e}")
                dna_table_pages.append(idx)
                page_scores.append((idx, 0))

        # ⭐ SELECT BEST PAGE WITH LANGUAGE PREFERENCE
        if return_best_only and len(page_scores) > 1:
            english_pages = []
            ukrainian_pages = []

            # English markers
            english_markers = ['alleged father', 'alleged mother', 'child', 'locus', 'relationship index']
            # Ukrainian markers
            ukrainian_markers = ['батько', 'мати', 'дитина', 'локус', 'індекс спорідненості']

            for idx, score in page_scores:
                text = page_texts.get(idx, '')

                # Count markers
                english_count = sum(1 for marker in english_markers if marker in text)
                ukrainian_count = sum(1 for marker in ukrainian_markers if marker in text)

                if english_count > ukrainian_count:
                    english_pages.append((idx, score))
                    logger.info(f"📄 Page {idx + 1}: English (markers: {english_count})")
                elif ukrainian_count > english_count:
                    ukrainian_pages.append((idx, score))
                    logger.info(f"📄 Page {idx + 1}: Ukrainian (markers: {ukrainian_count})")
                else:
                    # If equal, check for specific patterns
                    if 'alleged' in text:
                        english_pages.append((idx, score))
                        logger.info(f"📄 Page {idx + 1}: English (fallback)")
                    else:
                        ukrainian_pages.append((idx, score))
                        logger.info(f"📄 Page {idx + 1}: Ukrainian (fallback)")

            # Select based on preference
            if prefer_english and english_pages:
                best = max(english_pages, key=lambda x: x[1])
                logger.info(f"🎯 Selected ENGLISH page: Page {best[0] + 1} (score: {best[1]})")
                return [best[0]]
            elif ukrainian_pages:
                best = max(ukrainian_pages, key=lambda x: x[1])
                logger.info(f"🎯 Selected UKRAINIAN page: Page {best[0] + 1} (score: {best[1]})")
                return [best[0]]
            else:
                # Fallback to highest score
                best = max(page_scores, key=lambda x: x[1])
                logger.info(f"🎯 Selected page by score: Page {best[0] + 1} (score: {best[1]})")
                return [best[0]]

        # Single page or return all
        if return_best_only and len(page_scores) == 1:
            logger.info(f"🎯 Only one DNA page found: Page {page_scores[0][0] + 1}")
            return [page_scores[0][0]]

        # Fallback: if no pages detected, include all
        if len(dna_table_pages) == 0:
            logger.warning("⚠️ No DNA tables detected, processing all pages as fallback")
            dna_table_pages = list(range(len(images)))

        logger.info(f"📊 Result: {len(dna_table_pages)}/{len(images)} pages will be processed")
        return dna_table_pages

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
                # Get image dimensions
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)

                # Perform rotation
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
            # Use Non-local Means Denoising
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
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(image)

            # Apply slight sharpening
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
                    return_best_page_only: bool = False,  # ✅ NEW parameter
                    save_images: bool = False,
                    output_dir: str = None) -> List[Image.Image]:
        """
        Complete pipeline: Convert PDF to images and optionally enhance

        Args:
            pdf_path: Path to PDF file
            enhance: Apply image enhancement
            detect_tables: Use smart detection to only process DNA table pages
            return_best_page_only: If True, return only the best DNA page (not all matches)
            save_images: Save processed images to disk
            output_dir: Directory to save images (if save_images=True)

        Returns:
            List of processed PIL Images
        """
        # Convert PDF to images
        images = self.convert_pdf_to_images(pdf_path)

        # ⭐ Smart detection: Filter to only DNA table pages
        if detect_tables:
            logger.info("Detecting DNA table pages...")
            dna_page_indices = self.detect_dna_table_pages(
                images,
                return_best_only=return_best_page_only  # ✅ Pass parameter
            )
            images = [images[i] for i in dna_page_indices if i < len(images)]
            logger.info(f"Processing {len(images)} DNA table pages")

        # Auto-rotate and enhance each image
        processed_images = []
        for idx, img in enumerate(images):
            logger.info(f"Processing page {idx + 1}/{len(images)}")

            # First, rotate to portrait if needed
            rotated = self.auto_rotate_to_portrait(img)

            # Then enhance if requested
            if enhance:
                logger.info(f"Enhancing page {idx + 1}/{len(images)}")
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


# ⭐ STANDALONE FUNCTIONS (for tasks.py)

def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[Image.Image]:
    """
    Convert PDF to images

    Args:
        pdf_path: Path to PDF file
        dpi: Resolution (default 300)

    Returns:
        List of PIL Images
    """
    processor = PDFProcessor(dpi=dpi)
    return processor.convert_pdf_to_images(pdf_path)


def detect_dna_table_pages(images: List[Image.Image]) -> List[int]:
    """
    Detect which pages contain DNA tables

    Args:
        images: List of PIL images

    Returns:
        List of page indices with DNA tables
    """
    processor = PDFProcessor()
    return processor.detect_dna_table_pages(images)


def filter_images_by_pages(images: List[Image.Image], page_indices: List[int]) -> List[Image.Image]:
    """
    Filter images to only include specified pages

    Args:
        images: All page images
        page_indices: Indices to keep

    Returns:
        Filtered list of images
    """
    filtered = [images[i] for i in page_indices if i < len(images)]
    logger.info(f"Filtered to {len(filtered)} images from {len(images)}")
    return filtered


def enhance_image_for_ocr(image: Image.Image) -> Image.Image:
    """
    Enhance single image for OCR/AI

    Args:
        image: PIL Image

    Returns:
        Enhanced PIL Image
    """
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
    best_page_only: bool = False  # ✅ NEW parameter
) -> List[Image.Image]:
    """
    Convenience function to process DNA report PDF

    Args:
        pdf_path: Path to PDF file
        enhance: Apply image enhancement (recommended for DNA reports)
        detect_tables: Use smart detection to filter DNA table pages
        best_page_only: If True, return only the best DNA page

    Returns:
        List of processed images ready for AI extraction
    """
    processor = PDFProcessor(dpi=300)
    images = processor.process_pdf(
        pdf_path,
        enhance=enhance,
        detect_tables=detect_tables,
        return_best_page_only=best_page_only  # ✅ Pass parameter
    )
    return images

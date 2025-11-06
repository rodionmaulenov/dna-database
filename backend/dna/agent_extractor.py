"""
DNA Extractor with Claude Sonnet 4 (Single Model)
- Primary: Claude Sonnet 4 (extraction + validation)
- Fast, accurate, and cost-effective
"""
import logging
import base64
import io
import json
import re
import anthropic

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import List, Dict, Any, Optional
from PIL import Image
from json_repair import repair_json

from django.conf import settings

from dna.extraction_prompt import get_extraction_prompt

logger = logging.getLogger(__name__)

ANTHROPIC_RETRY_EXCEPTIONS = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
    anthropic.RateLimitError,
)


class MultiAgentDNAExtractor:
    """
    Single-stage DNA extraction with Claude Sonnet 4
    Fast, accurate, and cost-effective
    """

    VALID_LOCI = [
        'D1S1656', 'D2S441', 'D2S1338', 'D3S1358', 'D5S818',
        'D6S1043', 'D7S820', 'D8S1179', 'D10S1248', 'D12S391',
        'D13S317', 'D16S539', 'D18S51', 'D19S433', 'D21S11',
        'D22S1045', 'CSF1PO', 'FGA', 'TH01', 'TPOX', 'vWA',
        'Penta D', 'Penta E'
    ]

    def __init__(self):
        """Initialize Claude client"""
        self.anthropic_client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )

    def extract_from_images(self, images: List[Image.Image]) -> Dict[str, Any]:
        """
        Single-stage extraction with Claude

        Args:
            images: List of PIL images

        Returns:
            Extracted and validated DNA data
        """

        # Stage 1: Claude extracts
        logger.info("Starting Claude Sonnet 4 extraction")

        claude_result = self._extract_with_claude(images)

        if not claude_result.get('success', False):
            logger.error(f"❌ Claude extraction failed: {claude_result.get('error')}")
            return claude_result

        # Stage 2: Final validation
        logger.info("Validating extraction")
        validation = self._validate_extraction(claude_result)

        claude_result['validation'] = validation
        claude_result['extraction_method'] = 'claude_verified' if validation['is_valid'] else 'claude_unverified'

        if 'parent_role' in validation:
            claude_result['parent_role'] = validation['parent_role']

        logger.info(f"✅ {validation['message']}")
        return claude_result

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type(ANTHROPIC_RETRY_EXCEPTIONS),
        reraise=False
    )
    def _extract_with_claude(self, images: List[Image.Image]) -> Dict[str, Any]:
        """
        Extract DNA data using Claude Sonnet 4

        Args:
            images: List of PIL Image objects

        Returns:
            Dict with 'success', 'father', 'child' keys, or error
        """
        try:
            logger.info("Converting images to base64...")

            # Convert images to base64
            image_contents = []
            for idx, img in enumerate(images):
                try:
                    img_byte_arr = io.BytesIO()
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.save(img_byte_arr, format='PNG')
                    img_base64 = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')

                    image_contents.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_base64
                        }
                    })

                    logger.info(f"✅ Image {idx + 1}/{len(images)} converted")

                except Exception as img_error:
                    logger.error(f"❌ Failed to convert image {idx + 1}: {img_error}")
                    return {
                        "success": False,
                        "error": "Could not process image file"
                    }

            prompt = self._create_claude_prompt()

            # Call Claude API
            logger.info("Calling Claude API...")
            try:
                response = self.anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=8192,
                    temperature=0,
                    timeout=90.0,
                    messages=[{
                        "role": "user",
                        "content": image_contents + [{"type": "text", "text": prompt}]
                    }]
                )
            except Exception as api_error:
                logger.error(f"❌ Claude API call failed: {api_error}", exc_info=True)
                return {
                    "success": False,
                    "error": "Could not read DNA data from file"
                }

            # Get response text
            response_text = response.content[0].text
            logger.info(f"Claude response received: {len(response_text)} chars")

            # Parse JSON robustly
            raw_result = self._parse_json_robust(response_text, "Claude")

            if raw_result is None:
                logger.error("❌ JSON parsing failed")
                return {
                    "success": False,
                    "error": "Could not read DNA data from file"
                }

            logger.info("✅ JSON parsed successfully")

            # Normalize result format
            if 'people' in raw_result:
                logger.info("Normalizing result...")
                result = self._normalize_extraction_result(raw_result)

                if not result.get('success', False):
                    logger.error(f"❌ Normalization failed: {result.get('error')}")
                    return result
            else:
                result = raw_result
                result['success'] = True

            # Count extracted loci
            loci_count = self._count_total_loci(result)
            father_loci = len(result.get('father', {}).get('loci', []))
            child_loci = len(result.get('child', {}).get('loci', []))

            logger.info(f"✅ Extracted {loci_count} total loci")
            logger.info(f"   Father: {father_loci} loci")
            logger.info(f"   Child: {child_loci} loci")

            return result

        except Exception as e:
            logger.error(f"❌ Extraction failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": "Could not read DNA data from file"
            }

    def _create_claude_prompt(self) -> str:
        """Get extraction prompt from external file"""
        return get_extraction_prompt()

    def _parse_json_robust(self, response_text: str, source: str = "Claude") -> Optional[Dict[str, Any]]:
        """Robust JSON parsing"""
        cleaned_text = re.sub(r'```json\s*', '', response_text)
        cleaned_text = re.sub(r'```\s*', '', cleaned_text)
        cleaned_text = cleaned_text.strip()

        json_match = re.search(r'{[\s\S]*}', cleaned_text)

        if not json_match:
            logger.error(f"No JSON found in {source} response")
            return None

        json_str = json_match.group()

        # Try parsing
        try:
            result = json.loads(json_str)
            logger.info(f"✅ {source} JSON parsed")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"{source} parse failed: {e}")

            # Try cleaning
            try:
                cleaned_json = re.sub(r',(\s*[}\]])', r'\1', json_str)
                result = json.loads(cleaned_json)
                logger.info(f"✅ {source} parsed after cleaning")
                return result
            except json.JSONDecodeError:
                # Try repair library
                try:
                    repaired_json = repair_json(json_str)
                    result = json.loads(repaired_json)
                    logger.info(f"✅ {source} repaired")
                    return result
                except Exception:
                    logger.error(f"All parsing failed for {source}")
                    return None

    def _normalize_extraction_result(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert 'people' array to father/child format"""
        people = raw_result.get('people', [])
        people_with_data = [p for p in people if p.get('loci', [])]

        if len(people_with_data) == 0:
            return {
                'success': False,
                'error': 'Could not read DNA data from file'
            }

        father_data = None
        mother_data = None
        child_data = None

        for person in people_with_data:
            role_label = person.get('role_label', '').lower()

            if 'father' in role_label or 'alleged father' in role_label or 'батько' in role_label:
                father_data = person
            elif 'mother' in role_label or 'alleged mother' in role_label or 'мати' in role_label:
                mother_data = person
            elif 'child' in role_label or 'дитина' in role_label:
                child_data = person

        # Priority logic
        if father_data:
            parent_data = father_data
        elif mother_data:
            parent_data = mother_data
        elif len(people_with_data) == 1:
            parent_data = people_with_data[0]
        else:
            return {
                'success': False,
                'error': 'Could not identify person roles in the document'
            }

        if parent_data is None:
            return {
                'success': False,
                'error': 'Could not identify parent information in the document'
            }

        return {
            'success': True,
            'father': parent_data or {'name': None, 'loci': []},
            'child': child_data or {'name': None, 'loci': []},
            'raw_people': people
        }

    def _count_total_loci(self, data: Dict[str, Any]) -> int:
        """Count total loci"""
        count = 0
        for role in ['father', 'mother', 'child']:
            if data.get(role) and isinstance(data[role].get('loci'), list):
                count += len(data[role]['loci'])
        return count

    def _validate_extraction(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Final validation"""
        issues = []
        score = 1.0

        if not result.get('success', False):
            return {
                'is_valid': False,
                'message': f"Extraction failed: {result.get('error')}",
                'issues': ['extraction_failed'],
                'score': 0.0,
                'parent_role': 'unknown'
            }

        father_data = result.get('father', {})
        father_loci = father_data.get('loci', [])

        child_data = result.get('child', {})
        child_loci = child_data.get('loci', [])

        # Check completeness
        if len(father_loci) == 0 and len(child_loci) == 0:
            issues.append("No data extracted")
            score = 0.0

        if len(father_loci) > 0 and len(father_loci) < 10:
            issues.append(f"Father has only {len(father_loci)} loci")
            score -= 0.2

        if len(child_loci) > 0 and len(child_loci) < 10:
            issues.append(f"Child has only {len(child_loci)} loci")
            score -= 0.3

        parent_role = 'father' if len(father_loci) > 0 else 'unknown'

        # Check for duplicates
        for person_name, person_loci in [('father', father_loci), ('child', child_loci)]:
            if len(person_loci) == 0:
                continue

            locus_names = [l.get('locus_name') for l in person_loci]
            duplicates = [name for name in set(locus_names) if locus_names.count(name) > 1]
            if duplicates:
                issues.append(f"{person_name.capitalize()} has duplicates: {', '.join(duplicates)}")
                score -= 0.1

        score = max(0.0, min(1.0, score))
        is_valid = score >= 0.7

        return {
            'is_valid': is_valid,
            'message': f"Extraction {'valid' if is_valid else 'incomplete'} (score: {score:.2f})",
            'issues': issues,
            'score': score,
            'parent_role': parent_role
        }


def extract_dna_data_agent(images: List[Image.Image]) -> Dict[str, Any]:
    """
    Convenience function for DNA extraction

    Args:
        images: List of PIL images

    Returns:
        Extracted DNA data
    """
    extractor = MultiAgentDNAExtractor()
    return extractor.extract_from_images(images)

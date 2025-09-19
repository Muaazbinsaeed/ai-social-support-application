import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from typing import Dict, Any, List, Tuple, Optional
import re
from pathlib import Path
import asyncio
import logging

from backend.config import settings

# Configure Tesseract
pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

logger = logging.getLogger(__name__)

class OCRService:
    """
    Specialized OCR service for Emirates ID and handwritten forms
    Supports both English and Arabic text recognition
    """

    def __init__(self):
        self.tesseract_config = {
            'english': '--oem 3 --psm 6 -l eng',
            'arabic': '--oem 3 --psm 6 -l ara',
            'bilingual': '--oem 3 --psm 6 -l eng+ara'
        }

        # Emirates ID specific patterns
        self.emirates_id_patterns = {
            'id_number': r'\b\d{3}[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d{1}\b',
            'phone': r'(?:\+?971|00971|0)?[\s-]?(?:50|51|52|55|56|58|54|59)[\s-]?\d{3}[\s-]?\d{4}',
            'date': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b'
        }

    async def preprocess_image(self, image_path: str, enhance_for: str = "general") -> np.ndarray:
        """
        Preprocess image for better OCR results

        Args:
            image_path: Path to the image file
            enhance_for: Type of enhancement ('emirates_id', 'handwritten', 'general')

        Returns:
            Preprocessed image as numpy array
        """
        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")

            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            if enhance_for == "emirates_id":
                # Specific preprocessing for Emirates ID
                # Remove noise and enhance contrast
                denoised = cv2.bilateralFilter(gray, 9, 75, 75)

                # Apply adaptive thresholding
                thresh = cv2.adaptiveThreshold(
                    denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 11, 2
                )

                # Morphological operations to clean up
                kernel = np.ones((1, 1), np.uint8)
                cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

                return cleaned

            elif enhance_for == "handwritten":
                # Preprocessing for handwritten text
                # Apply Gaussian blur to smooth out pen strokes
                blurred = cv2.GaussianBlur(gray, (1, 1), 0)

                # Apply threshold to get binary image
                _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                # Dilate to make text thicker
                kernel = np.ones((1, 1), np.uint8)
                dilated = cv2.dilate(thresh, kernel, iterations=1)

                return dilated

            else:
                # General preprocessing
                # Apply Gaussian blur
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)

                # Apply threshold
                _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                return thresh

        except Exception as e:
            logger.error(f"Error preprocessing image {image_path}: {str(e)}")
            raise

    async def extract_text_from_image(
        self,
        image_path: str,
        language: str = "bilingual",
        enhance_for: str = "general"
    ) -> Dict[str, Any]:
        """
        Extract text from image using OCR

        Args:
            image_path: Path to the image file
            language: OCR language ('english', 'arabic', 'bilingual')
            enhance_for: Image enhancement type

        Returns:
            Dictionary containing extracted text and confidence scores
        """
        try:
            # Preprocess image
            processed_image = await self.preprocess_image(image_path, enhance_for)

            # Get Tesseract configuration
            config = self.tesseract_config.get(language, self.tesseract_config['bilingual'])

            # Extract text with confidence scores
            text_data = pytesseract.image_to_data(
                processed_image,
                config=config,
                output_type=pytesseract.Output.DICT
            )

            # Extract plain text
            text = pytesseract.image_to_string(processed_image, config=config)

            # Calculate average confidence
            confidences = [int(conf) for conf in text_data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            # Extract words with high confidence
            high_confidence_words = []
            for i, conf in enumerate(text_data['conf']):
                if int(conf) > 60:  # Only include words with >60% confidence
                    word = text_data['text'][i].strip()
                    if word:
                        high_confidence_words.append({
                            'text': word,
                            'confidence': int(conf),
                            'bbox': {
                                'left': text_data['left'][i],
                                'top': text_data['top'][i],
                                'width': text_data['width'][i],
                                'height': text_data['height'][i]
                            }
                        })

            return {
                'raw_text': text.strip(),
                'average_confidence': round(avg_confidence, 2),
                'high_confidence_words': high_confidence_words,
                'word_count': len(high_confidence_words),
                'language_detected': language,
                'processing_status': 'success'
            }

        except Exception as e:
            logger.error(f"Error extracting text from {image_path}: {str(e)}")
            return {
                'raw_text': '',
                'average_confidence': 0,
                'high_confidence_words': [],
                'word_count': 0,
                'language_detected': language,
                'processing_status': 'failed',
                'error': str(e)
            }

    async def extract_emirates_id_data(self, image_path: str) -> Dict[str, Any]:
        """
        Specialized extraction for Emirates ID cards

        Args:
            image_path: Path to Emirates ID image

        Returns:
            Dictionary containing structured Emirates ID data
        """
        try:
            # Extract text using bilingual OCR optimized for Emirates ID
            ocr_result = await self.extract_text_from_image(
                image_path,
                language="bilingual",
                enhance_for="emirates_id"
            )

            raw_text = ocr_result['raw_text']

            # Initialize extracted data structure
            extracted_data = {
                'id_number': None,
                'name_english': None,
                'name_arabic': None,
                'nationality': None,
                'date_of_birth': None,
                'issue_date': None,
                'expiry_date': None,
                'card_number': None,
                'extraction_confidence': ocr_result['average_confidence'],
                'raw_ocr_text': raw_text
            }

            # Extract Emirates ID number
            id_match = re.search(self.emirates_id_patterns['id_number'], raw_text)
            if id_match:
                extracted_data['id_number'] = re.sub(r'[-\s]', '', id_match.group())

            # Extract dates (birth, issue, expiry)
            dates = re.findall(self.emirates_id_patterns['date'], raw_text)
            if len(dates) >= 1:
                extracted_data['date_of_birth'] = dates[0]
            if len(dates) >= 2:
                extracted_data['expiry_date'] = dates[-1]

            # Extract phone number if present
            phone_match = re.search(self.emirates_id_patterns['phone'], raw_text)
            if phone_match:
                extracted_data['phone'] = phone_match.group()

            # Try to extract names (this is complex and may need ML model)
            lines = raw_text.split('\n')
            for line in lines:
                line = line.strip()
                if len(line) > 3 and not re.search(r'\d', line):  # Likely a name line
                    if not extracted_data['name_english'] and re.search(r'[A-Za-z]', line):
                        extracted_data['name_english'] = line

            # Validate extraction quality
            quality_score = self._calculate_extraction_quality(extracted_data)
            extracted_data['extraction_quality'] = quality_score

            return extracted_data

        except Exception as e:
            logger.error(f"Error extracting Emirates ID data from {image_path}: {str(e)}")
            return {
                'extraction_confidence': 0,
                'extraction_quality': 'poor',
                'error': str(e)
            }

    async def extract_handwritten_form_data(self, image_path: str) -> Dict[str, Any]:
        """
        Extract data from handwritten forms

        Args:
            image_path: Path to handwritten form image

        Returns:
            Dictionary containing extracted form data
        """
        try:
            # Use specific preprocessing for handwritten text
            ocr_result = await self.extract_text_from_image(
                image_path,
                language="bilingual",
                enhance_for="handwritten"
            )

            # Extract key-value pairs from form
            form_data = await self._extract_form_fields(ocr_result['raw_text'])

            return {
                'form_fields': form_data,
                'raw_text': ocr_result['raw_text'],
                'confidence': ocr_result['average_confidence'],
                'word_count': ocr_result['word_count'],
                'processing_status': 'success'
            }

        except Exception as e:
            logger.error(f"Error extracting handwritten form data from {image_path}: {str(e)}")
            return {
                'form_fields': {},
                'raw_text': '',
                'confidence': 0,
                'processing_status': 'failed',
                'error': str(e)
            }

    async def _extract_form_fields(self, text: str) -> Dict[str, str]:
        """Extract key-value pairs from form text"""
        fields = {}
        lines = text.split('\n')

        # Common form field patterns
        field_patterns = {
            'name': r'name[:\s]*(.+)',
            'age': r'age[:\s]*(\d+)',
            'phone': r'(?:phone|mobile|tel)[:\s]*([+\d\s-]+)',
            'email': r'email[:\s]*([^\s]+@[^\s]+)',
            'address': r'address[:\s]*(.+)',
            'occupation': r'occupation[:\s]*(.+)',
            'income': r'income[:\s]*([+\d\s,]+)',
            'family_size': r'family[:\s]*(?:size[:\s]*)?(\d+)'
        }

        for line in lines:
            line = line.strip().lower()
            if ':' in line or any(keyword in line for keyword in field_patterns.keys()):
                for field_name, pattern in field_patterns.items():
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        fields[field_name] = match.group(1).strip()

        return fields

    def _calculate_extraction_quality(self, extracted_data: Dict[str, Any]) -> str:
        """Calculate the quality of Emirates ID extraction"""
        required_fields = ['id_number', 'name_english', 'date_of_birth']
        found_fields = sum(1 for field in required_fields if extracted_data.get(field))

        confidence = extracted_data.get('extraction_confidence', 0)

        if found_fields >= 3 and confidence > 80:
            return 'excellent'
        elif found_fields >= 2 and confidence > 60:
            return 'good'
        elif found_fields >= 1 and confidence > 40:
            return 'fair'
        else:
            return 'poor'

    async def batch_process_images(self, image_paths: List[str], document_type: str = "general") -> List[Dict[str, Any]]:
        """Process multiple images in batch"""
        tasks = []

        for image_path in image_paths:
            if document_type == "emirates_id":
                task = self.extract_emirates_id_data(image_path)
            elif document_type == "handwritten":
                task = self.extract_handwritten_form_data(image_path)
            else:
                task = self.extract_text_from_image(image_path)

            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'image_path': image_paths[i],
                    'processing_status': 'failed',
                    'error': str(result)
                })
            else:
                result['image_path'] = image_paths[i]
                processed_results.append(result)

        return processed_results

# Singleton instance
ocr_service = OCRService()
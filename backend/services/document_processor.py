import os
import shutil
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import asyncio
import aiofiles
from datetime import datetime
import json

from unstructured.partition.auto import partition
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.image import partition_image
from unstructured.partition.xlsx import partition_xlsx
from unstructured.partition.docx import partition_docx
import pandas as pd

from backend.config import settings
from backend.models.schemas import DocumentType

class DocumentProcessor:
    """
    Unified document processing service supporting multiple file types:
    - PDFs (bank statements, credit reports)
    - Images (Emirates ID, scanned documents)
    - Excel files (assets/liabilities)
    - Word documents (resumes)
    - Plain text files
    """

    def __init__(self):
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # Supported file types and their processors
        self.processors = {
            'pdf': self._process_pdf,
            'png': self._process_image,
            'jpg': self._process_image,
            'jpeg': self._process_image,
            'tiff': self._process_image,
            'xlsx': self._process_excel,
            'xls': self._process_excel,
            'docx': self._process_docx,
            'doc': self._process_docx,
            'txt': self._process_text
        }

        # Document type specific extractors
        self.extractors = {
            DocumentType.EMIRATES_ID: self._extract_emirates_id,
            DocumentType.BANK_STATEMENT: self._extract_bank_statement,
            DocumentType.CREDIT_REPORT: self._extract_credit_report,
            DocumentType.RESUME: self._extract_resume,
            DocumentType.ASSETS_LIABILITIES: self._extract_assets_liabilities
        }

    async def save_uploaded_file(self, file_content: bytes, filename: str, application_id: int) -> str:
        """Save uploaded file to disk and return file path"""
        app_dir = self.upload_dir / str(application_id)
        app_dir.mkdir(exist_ok=True)

        # Ensure unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        safe_filename = f"{name}_{timestamp}{ext}"
        file_path = app_dir / safe_filename

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)

        return str(file_path)

    async def process_document(
        self,
        file_path: str,
        document_type: DocumentType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a document and extract structured data based on its type

        Args:
            file_path: Path to the uploaded file
            document_type: Type of document (emirates_id, bank_statement, etc.)
            metadata: Additional metadata about the document

        Returns:
            Dictionary containing extracted data and processing results
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Get file extension and processor
            file_ext = file_path_obj.suffix.lower().lstrip('.')
            if file_ext not in self.processors:
                raise ValueError(f"Unsupported file type: {file_ext}")

            # Basic file info
            file_stats = file_path_obj.stat()
            result = {
                "file_info": {
                    "name": file_path_obj.name,
                    "size": file_stats.st_size,
                    "type": file_ext,
                    "processed_at": datetime.now().isoformat()
                },
                "document_type": document_type.value,
                "extracted_data": {},
                "raw_content": "",
                "processing_status": "completed",
                "errors": []
            }

            # Process document using appropriate processor
            processor = self.processors[file_ext]
            elements = await processor(file_path)

            # Extract raw text content
            result["raw_content"] = "\n".join([str(elem) for elem in elements])

            # Apply document-type specific extraction
            if document_type in self.extractors:
                extractor = self.extractors[document_type]
                result["extracted_data"] = await extractor(elements, result["raw_content"])

            return result

        except Exception as e:
            return {
                "file_info": {"name": Path(file_path).name},
                "document_type": document_type.value,
                "extracted_data": {},
                "raw_content": "",
                "processing_status": "failed",
                "errors": [str(e)]
            }

    async def _process_pdf(self, file_path: str) -> List[Any]:
        """Process PDF documents (bank statements, credit reports)"""
        return partition_pdf(
            filename=file_path,
            strategy="hi_res",  # High resolution for better table extraction
            infer_table_structure=True,
            extract_images_in_pdf=True
        )

    async def _process_image(self, file_path: str) -> List[Any]:
        """Process image documents (Emirates ID, scanned forms)"""
        return partition_image(
            filename=file_path,
            strategy="hi_res",
            ocr_languages="eng+ara"  # English and Arabic for UAE context
        )

    async def _process_excel(self, file_path: str) -> List[Any]:
        """Process Excel files (assets/liabilities spreadsheets)"""
        return partition_xlsx(filename=file_path)

    async def _process_docx(self, file_path: str) -> List[Any]:
        """Process Word documents (resumes)"""
        return partition_docx(filename=file_path)

    async def _process_text(self, file_path: str) -> List[Any]:
        """Process plain text files"""
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        return [content]  # Return as list for consistency

    async def _extract_emirates_id(self, elements: List[Any], raw_content: str) -> Dict[str, Any]:
        """Extract structured data from Emirates ID"""
        extracted = {
            "id_number": None,
            "name_english": None,
            "name_arabic": None,
            "nationality": None,
            "date_of_birth": None,
            "issue_date": None,
            "expiry_date": None,
            "card_number": None
        }

        # Use regex patterns and text analysis to extract ID fields
        # This is a simplified implementation - in production, use specialized OCR
        import re

        # Emirates ID number pattern (15 digits)
        id_pattern = r'\b\d{3}-\d{4}-\d{7}-\d{1}\b|\b\d{15}\b'
        id_match = re.search(id_pattern, raw_content)
        if id_match:
            extracted["id_number"] = id_match.group()

        # Date patterns
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b'
        dates = re.findall(date_pattern, raw_content)
        if len(dates) >= 2:
            extracted["date_of_birth"] = dates[0]
            extracted["expiry_date"] = dates[-1]

        return extracted

    async def _extract_bank_statement(self, elements: List[Any], raw_content: str) -> Dict[str, Any]:
        """Extract financial data from bank statements"""
        extracted = {
            "account_number": None,
            "account_holder": None,
            "statement_period": {},
            "opening_balance": None,
            "closing_balance": None,
            "total_credits": 0.0,
            "total_debits": 0.0,
            "transaction_count": 0,
            "average_balance": None,
            "largest_credit": None,
            "largest_debit": None,
            "salary_payments": []
        }

        # Extract monetary amounts
        import re
        amount_pattern = r'[\d,]+\.\d{2}'
        amounts = [float(amount.replace(',', '')) for amount in re.findall(amount_pattern, raw_content)]

        if amounts:
            extracted["closing_balance"] = amounts[-1] if amounts else 0
            extracted["largest_credit"] = max(amounts) if amounts else 0
            extracted["total_credits"] = sum(amounts) if amounts else 0
            extracted["average_balance"] = sum(amounts) / len(amounts) if amounts else 0

        return extracted

    async def _extract_credit_report(self, elements: List[Any], raw_content: str) -> Dict[str, Any]:
        """Extract credit information from credit reports"""
        extracted = {
            "credit_score": None,
            "report_date": None,
            "total_accounts": 0,
            "active_accounts": 0,
            "total_credit_limit": 0.0,
            "total_outstanding": 0.0,
            "payment_history": {},
            "defaults": [],
            "credit_utilization": None
        }

        # Extract credit score
        import re
        score_pattern = r'(?:score|rating)[\s:]*(\d{3})'
        score_match = re.search(score_pattern, raw_content, re.IGNORECASE)
        if score_match:
            extracted["credit_score"] = int(score_match.group(1))

        return extracted

    async def _extract_resume(self, elements: List[Any], raw_content: str) -> Dict[str, Any]:
        """Extract professional information from resumes"""
        extracted = {
            "name": None,
            "email": None,
            "phone": None,
            "education": [],
            "work_experience": [],
            "skills": [],
            "total_experience_years": 0,
            "current_position": None,
            "highest_qualification": None
        }

        # Extract email and phone using regex
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'(?:\+?971|00971|0)?[\s-]?(?:50|51|52|55|56|58|54|55|59|58|2|3|4|6|7|9)[\s-]?\d{3}[\s-]?\d{4}'

        email_match = re.search(email_pattern, raw_content)
        phone_match = re.search(phone_pattern, raw_content)

        if email_match:
            extracted["email"] = email_match.group()
        if phone_match:
            extracted["phone"] = phone_match.group()

        return extracted

    async def _extract_assets_liabilities(self, elements: List[Any], raw_content: str) -> Dict[str, Any]:
        """Extract financial data from assets/liabilities spreadsheet"""
        extracted = {
            "total_assets": 0.0,
            "total_liabilities": 0.0,
            "net_worth": 0.0,
            "asset_categories": {},
            "liability_categories": {},
            "cash_and_equivalents": 0.0,
            "property_value": 0.0,
            "vehicle_value": 0.0,
            "investments": 0.0,
            "loans": 0.0,
            "credit_cards": 0.0
        }

        # For Excel files, try to parse using pandas if available
        # This is a simplified implementation
        import re
        amount_pattern = r'[\d,]+(?:\.\d{2})?'
        amounts = [float(amount.replace(',', '')) for amount in re.findall(amount_pattern, raw_content)]

        if amounts:
            extracted["total_assets"] = sum(amounts[:len(amounts)//2]) if amounts else 0
            extracted["total_liabilities"] = sum(amounts[len(amounts)//2:]) if amounts else 0
            extracted["net_worth"] = extracted["total_assets"] - extracted["total_liabilities"]

        return extracted

    async def cleanup_old_files(self, days_old: int = 30) -> int:
        """Clean up files older than specified days"""
        cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
        deleted_count = 0

        for app_dir in self.upload_dir.iterdir():
            if app_dir.is_dir():
                for file_path in app_dir.iterdir():
                    if file_path.stat().st_mtime < cutoff_time:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                        except Exception:
                            pass

        return deleted_count

# Singleton instance
document_processor = DocumentProcessor()
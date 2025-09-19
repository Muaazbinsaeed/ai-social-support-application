import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging
import re

from langchain_community.llms import Ollama
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.prompts import PromptTemplate

from backend.config import settings
from backend.models.schemas import AgentResponse, DocumentType
from backend.services import embedding_service

logger = logging.getLogger(__name__)

class DataExtractionAgent:
    """
    Data Extraction Agent responsible for extracting and consolidating
    structured data from multiple sources (documents, forms, OCR results)
    """

    def __init__(self):
        self.llm = Ollama(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=0.1
        )

        # Data extraction templates for different document types
        self.extraction_templates = {
            DocumentType.EMIRATES_ID: self._create_emirates_id_template(),
            DocumentType.BANK_STATEMENT: self._create_bank_statement_template(),
            DocumentType.CREDIT_REPORT: self._create_credit_report_template(),
            DocumentType.RESUME: self._create_resume_template(),
            DocumentType.ASSETS_LIABILITIES: self._create_assets_template()
        }

        # Financial data consolidation rules
        self.consolidation_rules = self._setup_consolidation_rules()

    async def extract_application_data(
        self,
        applicant_data: Dict[str, Any],
        documents: List[Dict[str, Any]]
    ) -> AgentResponse:
        """
        Extract and consolidate data from all application sources

        Args:
            applicant_data: Basic applicant information from form
            documents: List of processed documents with extraction results

        Returns:
            AgentResponse containing consolidated extracted data
        """
        start_time = datetime.now()

        try:
            logger.info("Starting data extraction process")

            # Initialize consolidated data structure
            consolidated_data = {
                "personal_info": {},
                "financial_info": {},
                "employment_info": {},
                "family_info": {},
                "document_summary": {},
                "extraction_confidence": {},
                "data_sources": {}
            }

            # Extract data from each document type
            extraction_results = {}

            for document in documents:
                doc_type = document.get("document_type")
                processing_result = document.get("processing_result", {})

                if doc_type and processing_result:
                    extracted = await self._extract_from_document(doc_type, processing_result)
                    extraction_results[doc_type] = extracted

            # Consolidate data from all sources
            consolidated_data = await self._consolidate_data(
                applicant_data,
                extraction_results
            )

            # Calculate overall confidence score
            confidence_score = self._calculate_confidence_score(consolidated_data)

            # Generate extraction summary
            summary = await self._generate_extraction_summary(consolidated_data)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(f"Data extraction completed with confidence: {confidence_score}")

            return AgentResponse(
                success=True,
                message=f"Successfully extracted data from {len(documents)} documents",
                data=consolidated_data,
                confidence_score=confidence_score,
                processing_time_ms=int(processing_time)
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Data extraction failed: {str(e)}")

            return AgentResponse(
                success=False,
                message=f"Data extraction failed: {str(e)}",
                data={"error": str(e)},
                processing_time_ms=int(processing_time)
            )

    async def _extract_from_document(
        self,
        document_type: str,
        processing_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract structured data from a specific document type"""
        try:
            extracted_data = processing_result.get("extracted_data", {})
            raw_content = processing_result.get("raw_content", "")

            if document_type in self.extraction_templates:
                # Use LLM for advanced extraction
                template = self.extraction_templates[document_type]
                extracted = await self._llm_extract_data(template, raw_content, extracted_data)
            else:
                # Use basic extraction from document processor
                extracted = extracted_data

            return {
                "extracted_data": extracted,
                "confidence": self._assess_extraction_confidence(document_type, extracted),
                "data_quality": self._assess_data_quality(extracted),
                "source": document_type
            }

        except Exception as e:
            logger.error(f"Error extracting from {document_type}: {str(e)}")
            return {
                "extracted_data": {},
                "confidence": 0.0,
                "data_quality": "poor",
                "source": document_type,
                "error": str(e)
            }

    async def _llm_extract_data(
        self,
        template: PromptTemplate,
        raw_content: str,
        existing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use LLM to extract structured data from document content"""
        try:
            # Prepare prompt with document content
            prompt = template.format(
                document_content=raw_content[:4000],  # Limit content length
                existing_data=json.dumps(existing_data, indent=2)
            )

            # Get LLM response
            response = await asyncio.to_thread(self.llm.invoke, prompt)

            # Parse JSON response
            try:
                extracted_data = json.loads(response)
                return extracted_data
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract structured data from text
                return self._parse_text_response(response)

        except Exception as e:
            logger.error(f"LLM extraction failed: {str(e)}")
            return existing_data

    def _parse_text_response(self, response: str) -> Dict[str, Any]:
        """Parse structured data from text response if JSON parsing fails"""
        data = {}

        # Look for key-value patterns
        patterns = [
            r'(\w+):\s*([^\n]+)',
            r'(\w+)\s*=\s*([^\n]+)',
            r'"(\w+)":\s*"([^"]+)"'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            for key, value in matches:
                key = key.lower().strip()
                value = value.strip().strip('"\'')
                if value and value.lower() not in ['null', 'none', 'n/a']:
                    data[key] = value

        return data

    async def _consolidate_data(
        self,
        applicant_data: Dict[str, Any],
        extraction_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Consolidate data from multiple sources with conflict resolution"""
        consolidated = {
            "personal_info": {},
            "financial_info": {},
            "employment_info": {},
            "family_info": {},
            "document_summary": {},
            "extraction_confidence": {},
            "data_sources": {}
        }

        # Start with form data as base
        consolidated["personal_info"].update(applicant_data)

        # Consolidate data from each document type
        for doc_type, extraction_result in extraction_results.items():
            extracted = extraction_result.get("extracted_data", {})
            confidence = extraction_result.get("confidence", 0.0)

            # Apply document-specific consolidation rules
            if doc_type == DocumentType.EMIRATES_ID:
                await self._consolidate_emirates_id_data(consolidated, extracted, confidence)
            elif doc_type == DocumentType.BANK_STATEMENT:
                await self._consolidate_financial_data(consolidated, extracted, confidence, "bank_statement")
            elif doc_type == DocumentType.CREDIT_REPORT:
                await self._consolidate_financial_data(consolidated, extracted, confidence, "credit_report")
            elif doc_type == DocumentType.RESUME:
                await self._consolidate_employment_data(consolidated, extracted, confidence)
            elif doc_type == DocumentType.ASSETS_LIABILITIES:
                await self._consolidate_financial_data(consolidated, extracted, confidence, "assets_liabilities")

            # Track data sources and confidence
            consolidated["data_sources"][doc_type] = {
                "confidence": confidence,
                "data_quality": extraction_result.get("data_quality", "unknown"),
                "extracted_fields": list(extracted.keys())
            }

        # Resolve conflicts and validate consistency
        consolidated = await self._resolve_data_conflicts(consolidated)

        return consolidated

    async def _consolidate_emirates_id_data(
        self,
        consolidated: Dict[str, Any],
        extracted: Dict[str, Any],
        confidence: float
    ):
        """Consolidate Emirates ID data"""
        personal_info = consolidated["personal_info"]

        # Update with higher confidence data
        if confidence > 0.7:
            if "id_number" in extracted:
                personal_info["emirates_id"] = extracted["id_number"]
            if "name_english" in extracted:
                # Split name if needed
                name_parts = extracted["name_english"].split()
                if len(name_parts) >= 2:
                    personal_info["first_name"] = name_parts[0]
                    personal_info["last_name"] = " ".join(name_parts[1:])
            if "date_of_birth" in extracted:
                personal_info["date_of_birth"] = extracted["date_of_birth"]
            if "nationality" in extracted:
                personal_info["nationality"] = extracted["nationality"]

    async def _consolidate_financial_data(
        self,
        consolidated: Dict[str, Any],
        extracted: Dict[str, Any],
        confidence: float,
        source: str
    ):
        """Consolidate financial data from various sources"""
        financial_info = consolidated["financial_info"]

        if confidence > 0.6:
            # Map extracted fields to standard financial info fields
            field_mapping = {
                "monthly_income": ["monthly_income", "salary", "income"],
                "bank_balance": ["closing_balance", "current_balance", "balance"],
                "total_assets": ["total_assets", "assets"],
                "total_liabilities": ["total_liabilities", "liabilities", "loans"],
                "credit_score": ["credit_score", "score"]
            }

            for standard_field, possible_fields in field_mapping.items():
                for field in possible_fields:
                    if field in extracted and extracted[field]:
                        # Convert to float if possible
                        try:
                            value = float(str(extracted[field]).replace(",", ""))
                            financial_info[f"{standard_field}_{source}"] = value

                            # Use highest confidence value for main field
                            current_confidence = financial_info.get(f"{standard_field}_confidence", 0)
                            if confidence > current_confidence:
                                financial_info[standard_field] = value
                                financial_info[f"{standard_field}_confidence"] = confidence
                        except (ValueError, TypeError):
                            pass

    async def _consolidate_employment_data(
        self,
        consolidated: Dict[str, Any],
        extracted: Dict[str, Any],
        confidence: float
    ):
        """Consolidate employment data from resume"""
        employment_info = consolidated["employment_info"]

        if confidence > 0.6:
            if "current_position" in extracted:
                employment_info["current_position"] = extracted["current_position"]
            if "total_experience_years" in extracted:
                employment_info["total_experience_years"] = extracted["total_experience_years"]
            if "skills" in extracted:
                employment_info["skills"] = extracted["skills"]
            if "education" in extracted:
                employment_info["education"] = extracted["education"]

    async def _resolve_data_conflicts(self, consolidated: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflicts between different data sources"""
        # Implement conflict resolution logic
        # For now, we'll use confidence-based resolution which is already implemented

        # Add data consistency checks
        personal_info = consolidated["personal_info"]
        financial_info = consolidated["financial_info"]

        # Example: Ensure income consistency
        income_sources = [k for k in financial_info.keys() if "monthly_income" in k and "_confidence" not in k]
        if len(income_sources) > 1:
            # Use the source with highest confidence
            best_source = max(income_sources, key=lambda x: financial_info.get(f"{x}_confidence", 0))
            consolidated["financial_info"]["monthly_income"] = financial_info[best_source]

        return consolidated

    def _calculate_confidence_score(self, consolidated_data: Dict[str, Any]) -> float:
        """Calculate overall confidence score for extracted data"""
        data_sources = consolidated_data.get("data_sources", {})

        if not data_sources:
            return 0.0

        # Calculate weighted average confidence
        total_confidence = 0.0
        total_weight = 0.0

        weights = {
            DocumentType.EMIRATES_ID: 1.0,
            DocumentType.BANK_STATEMENT: 0.8,
            DocumentType.CREDIT_REPORT: 0.7,
            DocumentType.RESUME: 0.6,
            DocumentType.ASSETS_LIABILITIES: 0.8
        }

        for doc_type, source_data in data_sources.items():
            confidence = source_data.get("confidence", 0.0)
            weight = weights.get(doc_type, 0.5)

            total_confidence += confidence * weight
            total_weight += weight

        return round(total_confidence / total_weight if total_weight > 0 else 0.0, 3)

    def _assess_extraction_confidence(self, document_type: str, extracted_data: Dict[str, Any]) -> float:
        """Assess confidence of extraction for a specific document type"""
        if not extracted_data:
            return 0.0

        # Define required fields for each document type
        required_fields = {
            DocumentType.EMIRATES_ID: ["id_number", "name_english", "date_of_birth"],
            DocumentType.BANK_STATEMENT: ["closing_balance", "account_holder"],
            DocumentType.CREDIT_REPORT: ["credit_score"],
            DocumentType.RESUME: ["name", "work_experience"],
            DocumentType.ASSETS_LIABILITIES: ["total_assets", "total_liabilities"]
        }

        doc_required = required_fields.get(document_type, [])
        if not doc_required:
            return 0.5  # Default confidence for unknown document types

        # Calculate percentage of required fields found
        found_fields = sum(1 for field in doc_required if field in extracted_data and extracted_data[field])
        confidence = found_fields / len(doc_required)

        return round(confidence, 3)

    def _assess_data_quality(self, extracted_data: Dict[str, Any]) -> str:
        """Assess overall quality of extracted data"""
        if not extracted_data:
            return "poor"

        non_empty_fields = sum(1 for value in extracted_data.values() if value and str(value).strip())
        total_fields = len(extracted_data)

        if total_fields == 0:
            return "poor"

        quality_ratio = non_empty_fields / total_fields

        if quality_ratio >= 0.8:
            return "excellent"
        elif quality_ratio >= 0.6:
            return "good"
        elif quality_ratio >= 0.4:
            return "fair"
        else:
            return "poor"

    async def _generate_extraction_summary(self, consolidated_data: Dict[str, Any]) -> str:
        """Generate a summary of the extraction process"""
        data_sources = consolidated_data.get("data_sources", {})
        personal_info = consolidated_data.get("personal_info", {})
        financial_info = consolidated_data.get("financial_info", {})

        summary = f"""
        Data Extraction Summary:
        - Sources processed: {len(data_sources)}
        - Personal info fields: {len(personal_info)}
        - Financial info fields: {len(financial_info)}
        - Overall confidence: {consolidated_data.get('extraction_confidence', {}).get('overall', 0.0)}
        """

        return summary.strip()

    # Template creation methods
    def _create_emirates_id_template(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=["document_content", "existing_data"],
            template="""
            Extract structured information from the Emirates ID document content below.
            Return a JSON object with the following fields: id_number, name_english, name_arabic,
            nationality, date_of_birth, issue_date, expiry_date.

            Document Content:
            {document_content}

            Existing Extracted Data:
            {existing_data}

            Return only valid JSON:
            """
        )

    def _create_bank_statement_template(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=["document_content", "existing_data"],
            template="""
            Extract financial information from the bank statement content below.
            Return a JSON object with: account_number, account_holder, closing_balance,
            opening_balance, total_credits, total_debits, statement_period, average_balance.

            Document Content:
            {document_content}

            Existing Extracted Data:
            {existing_data}

            Return only valid JSON:
            """
        )

    def _create_credit_report_template(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=["document_content", "existing_data"],
            template="""
            Extract credit information from the credit report content below.
            Return a JSON object with: credit_score, total_accounts, active_accounts,
            total_credit_limit, total_outstanding, payment_history, defaults.

            Document Content:
            {document_content}

            Existing Extracted Data:
            {existing_data}

            Return only valid JSON:
            """
        )

    def _create_resume_template(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=["document_content", "existing_data"],
            template="""
            Extract professional information from the resume content below.
            Return a JSON object with: name, email, phone, current_position,
            total_experience_years, skills, education, work_experience.

            Document Content:
            {document_content}

            Existing Extracted Data:
            {existing_data}

            Return only valid JSON:
            """
        )

    def _create_assets_template(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=["document_content", "existing_data"],
            template="""
            Extract financial asset and liability information from the document content below.
            Return a JSON object with: total_assets, total_liabilities, net_worth,
            cash_and_equivalents, property_value, vehicle_value, investments, loans, credit_cards.

            Document Content:
            {document_content}

            Existing Extracted Data:
            {existing_data}

            Return only valid JSON:
            """
        )

    def _setup_consolidation_rules(self) -> Dict[str, Any]:
        """Setup rules for data consolidation and conflict resolution"""
        return {
            "priority_sources": {
                "personal_info": [DocumentType.EMIRATES_ID, "form_data"],
                "financial_info": [DocumentType.BANK_STATEMENT, DocumentType.CREDIT_REPORT, DocumentType.ASSETS_LIABILITIES],
                "employment_info": [DocumentType.RESUME, "form_data"]
            },
            "confidence_thresholds": {
                "high": 0.8,
                "medium": 0.6,
                "low": 0.4
            }
        }
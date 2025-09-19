import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
import re
import logging
from decimal import Decimal, InvalidOperation

from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate

from backend.config import settings
from backend.models.schemas import AgentResponse
from backend.services import embedding_service

logger = logging.getLogger(__name__)

class ValidationAgent:
    """
    Validation Agent responsible for checking data consistency, completeness,
    and identifying potential discrepancies across multiple data sources
    """

    def __init__(self):
        self.llm = Ollama(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=0.1
        )

        # Validation rules and patterns
        self.validation_rules = self._setup_validation_rules()
        self.pattern_validators = self._setup_pattern_validators()

    async def validate_application_data(
        self,
        applicant_data: Dict[str, Any],
        extracted_data: Dict[str, Any]
    ) -> AgentResponse:
        """
        Validate application data for consistency and completeness

        Args:
            applicant_data: Original applicant form data
            extracted_data: Consolidated extracted data from documents

        Returns:
            AgentResponse containing validation results and issues
        """
        start_time = datetime.now()

        try:
            logger.info("Starting data validation process")

            validation_results = {
                "personal_info_validation": {},
                "financial_info_validation": {},
                "document_consistency": {},
                "completeness_check": {},
                "discrepancies": [],
                "critical_issues": [],
                "warnings": [],
                "validation_score": 0.0,
                "requires_manual_review": False
            }

            # 1. Validate personal information
            personal_validation = await self._validate_personal_info(
                applicant_data,
                extracted_data.get("personal_info", {})
            )
            validation_results["personal_info_validation"] = personal_validation

            # 2. Validate financial information
            financial_validation = await self._validate_financial_info(
                extracted_data.get("financial_info", {})
            )
            validation_results["financial_info_validation"] = financial_validation

            # 3. Check cross-document consistency
            consistency_check = await self._check_document_consistency(extracted_data)
            validation_results["document_consistency"] = consistency_check

            # 4. Perform completeness check
            completeness_check = await self._check_data_completeness(extracted_data)
            validation_results["completeness_check"] = completeness_check

            # 5. Identify discrepancies and issues
            await self._identify_discrepancies(validation_results, applicant_data, extracted_data)

            # 6. Calculate overall validation score
            validation_score = self._calculate_validation_score(validation_results)
            validation_results["validation_score"] = validation_score

            # 7. Determine if manual review is required
            validation_results["requires_manual_review"] = self._requires_manual_review(validation_results)

            # Generate validation summary
            summary = await self._generate_validation_summary(validation_results)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            success = validation_score >= 0.7 and not validation_results["critical_issues"]

            logger.info(f"Validation completed with score: {validation_score}")

            return AgentResponse(
                success=success,
                message=f"Validation completed with score {validation_score:.2f}",
                data=validation_results,
                confidence_score=validation_score,
                processing_time_ms=int(processing_time)
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Validation failed: {str(e)}")

            return AgentResponse(
                success=False,
                message=f"Validation failed: {str(e)}",
                data={"error": str(e)},
                processing_time_ms=int(processing_time)
            )

    async def _validate_personal_info(
        self,
        form_data: Dict[str, Any],
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate personal information consistency"""
        validation_result = {
            "field_consistency": {},
            "format_validation": {},
            "issues": [],
            "confidence": 1.0
        }

        # Check field consistency between form and extracted data
        personal_fields = ["emirates_id", "first_name", "last_name", "date_of_birth", "phone", "email"]

        for field in personal_fields:
            form_value = form_data.get(field)
            extracted_value = extracted_data.get(field)

            consistency_check = {
                "form_value": form_value,
                "extracted_value": extracted_value,
                "consistent": True,
                "similarity_score": 1.0
            }

            if form_value and extracted_value:
                # Check consistency
                is_consistent, similarity = self._check_field_consistency(
                    field, str(form_value), str(extracted_value)
                )
                consistency_check["consistent"] = is_consistent
                consistency_check["similarity_score"] = similarity

                if not is_consistent and similarity < 0.8:
                    validation_result["issues"].append({
                        "type": "inconsistency",
                        "field": field,
                        "form_value": form_value,
                        "extracted_value": extracted_value,
                        "severity": "medium"
                    })

            validation_result["field_consistency"][field] = consistency_check

        # Validate field formats
        format_validations = {
            "emirates_id": self._validate_emirates_id_format(extracted_data.get("emirates_id")),
            "email": self._validate_email_format(extracted_data.get("email")),
            "phone": self._validate_phone_format(extracted_data.get("phone")),
            "date_of_birth": self._validate_date_format(extracted_data.get("date_of_birth"))
        }

        validation_result["format_validation"] = format_validations

        # Calculate confidence based on issues
        if validation_result["issues"]:
            validation_result["confidence"] = max(0.5, 1.0 - (len(validation_result["issues"]) * 0.1))

        return validation_result

    async def _validate_financial_info(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate financial information for reasonableness and consistency"""
        validation_result = {
            "range_validation": {},
            "consistency_checks": {},
            "ratio_analysis": {},
            "issues": [],
            "confidence": 1.0
        }

        # Range validation for financial amounts
        financial_fields = {
            "monthly_income": (0, 100000),  # AED
            "bank_balance": (0, 10000000),  # AED
            "total_assets": (0, 50000000),  # AED
            "total_liabilities": (0, 10000000),  # AED
            "credit_score": (300, 850)
        }

        for field, (min_val, max_val) in financial_fields.items():
            value = financial_data.get(field)
            if value is not None:
                try:
                    numeric_value = float(value)
                    is_valid = min_val <= numeric_value <= max_val

                    validation_result["range_validation"][field] = {
                        "value": numeric_value,
                        "valid_range": is_valid,
                        "expected_range": f"{min_val} - {max_val}"
                    }

                    if not is_valid:
                        validation_result["issues"].append({
                            "type": "out_of_range",
                            "field": field,
                            "value": numeric_value,
                            "expected_range": f"{min_val} - {max_val}",
                            "severity": "high" if numeric_value < 0 else "medium"
                        })

                except (ValueError, TypeError):
                    validation_result["issues"].append({
                        "type": "invalid_format",
                        "field": field,
                        "value": value,
                        "severity": "high"
                    })

        # Financial consistency checks
        await self._perform_financial_consistency_checks(financial_data, validation_result)

        # Calculate confidence
        if validation_result["issues"]:
            high_severity_count = sum(1 for issue in validation_result["issues"] if issue["severity"] == "high")
            validation_result["confidence"] = max(0.3, 1.0 - (high_severity_count * 0.2))

        return validation_result

    async def _perform_financial_consistency_checks(
        self,
        financial_data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ):
        """Perform financial consistency checks"""
        # Check asset-liability consistency
        total_assets = self._safe_float(financial_data.get("total_assets"))
        total_liabilities = self._safe_float(financial_data.get("total_liabilities"))

        if total_assets is not None and total_liabilities is not None:
            if total_liabilities > total_assets * 1.5:  # Debt-to-asset ratio check
                validation_result["issues"].append({
                    "type": "high_debt_ratio",
                    "message": "Total liabilities significantly exceed assets",
                    "severity": "medium"
                })

        # Check income-balance consistency
        monthly_income = self._safe_float(financial_data.get("monthly_income"))
        bank_balance = self._safe_float(financial_data.get("bank_balance"))

        if monthly_income is not None and bank_balance is not None:
            if bank_balance > monthly_income * 100:  # More than 8 years of income in bank
                validation_result["issues"].append({
                    "type": "unusual_balance",
                    "message": "Bank balance unusually high compared to monthly income",
                    "severity": "low"
                })

    async def _check_document_consistency(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check consistency across different document sources"""
        consistency_result = {
            "cross_document_checks": {},
            "data_source_reliability": {},
            "conflicts": [],
            "confidence": 1.0
        }

        data_sources = extracted_data.get("data_sources", {})

        # Check name consistency across documents
        await self._check_name_consistency(extracted_data, consistency_result)

        # Check financial data consistency
        await self._check_financial_consistency(extracted_data, consistency_result)

        # Assess data source reliability
        for source, source_data in data_sources.items():
            reliability_score = source_data.get("confidence", 0.0)
            data_quality = source_data.get("data_quality", "unknown")

            consistency_result["data_source_reliability"][source] = {
                "confidence": reliability_score,
                "quality": data_quality,
                "reliable": reliability_score > 0.7 and data_quality in ["good", "excellent"]
            }

        # Calculate overall consistency confidence
        if consistency_result["conflicts"]:
            conflict_severity = sum(1 for conflict in consistency_result["conflicts"]
                                  if conflict.get("severity") == "high")
            consistency_result["confidence"] = max(0.4, 1.0 - (conflict_severity * 0.2))

        return consistency_result

    async def _check_name_consistency(self, extracted_data: Dict[str, Any], result: Dict[str, Any]):
        """Check name consistency across documents"""
        personal_info = extracted_data.get("personal_info", {})
        data_sources = extracted_data.get("data_sources", {})

        # Extract names from different sources
        names_by_source = {}
        for source, source_data in data_sources.items():
            if "name" in str(source_data).lower():
                # This is simplified - in practice, you'd extract names from each document
                names_by_source[source] = personal_info.get("first_name", "")

        if len(names_by_source) > 1:
            # Check for significant differences
            name_values = list(names_by_source.values())
            if len(set(name_values)) > 1:
                result["conflicts"].append({
                    "type": "name_inconsistency",
                    "sources": names_by_source,
                    "severity": "medium"
                })

    async def _check_financial_consistency(self, extracted_data: Dict[str, Any], result: Dict[str, Any]):
        """Check financial data consistency across sources"""
        financial_info = extracted_data.get("financial_info", {})

        # Check for multiple income sources with significant differences
        income_fields = [k for k in financial_info.keys() if "monthly_income" in k and "_confidence" not in k]
        if len(income_fields) > 1:
            income_values = [self._safe_float(financial_info[field]) for field in income_fields]
            income_values = [v for v in income_values if v is not None]

            if len(income_values) > 1:
                max_income = max(income_values)
                min_income = min(income_values)

                if max_income > min_income * 1.5:  # 50% difference threshold
                    result["conflicts"].append({
                        "type": "income_inconsistency",
                        "values": {field: financial_info[field] for field in income_fields},
                        "severity": "high"
                    })

    async def _check_data_completeness(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check data completeness for application processing"""
        completeness_result = {
            "required_fields": {},
            "optional_fields": {},
            "missing_critical": [],
            "completeness_score": 0.0
        }

        # Define required fields for processing
        required_fields = {
            "personal_info": ["emirates_id", "first_name", "last_name"],
            "financial_info": ["monthly_income"]
        }

        optional_fields = {
            "personal_info": ["phone", "email", "date_of_birth"],
            "financial_info": ["bank_balance", "total_assets", "credit_score"]
        }

        total_required = 0
        found_required = 0

        # Check required fields
        for category, fields in required_fields.items():
            category_data = extracted_data.get(category, {})

            for field in fields:
                total_required += 1
                value = category_data.get(field)
                is_present = value is not None and str(value).strip() != ""

                completeness_result["required_fields"][f"{category}.{field}"] = {
                    "present": is_present,
                    "value": value
                }

                if is_present:
                    found_required += 1
                else:
                    completeness_result["missing_critical"].append(f"{category}.{field}")

        # Check optional fields
        total_optional = 0
        found_optional = 0

        for category, fields in optional_fields.items():
            category_data = extracted_data.get(category, {})

            for field in fields:
                total_optional += 1
                value = category_data.get(field)
                is_present = value is not None and str(value).strip() != ""

                completeness_result["optional_fields"][f"{category}.{field}"] = {
                    "present": is_present,
                    "value": value
                }

                if is_present:
                    found_optional += 1

        # Calculate completeness score
        required_score = found_required / total_required if total_required > 0 else 1.0
        optional_score = found_optional / total_optional if total_optional > 0 else 0.0

        # Weight required fields more heavily
        completeness_result["completeness_score"] = (required_score * 0.7) + (optional_score * 0.3)

        return completeness_result

    async def _identify_discrepancies(
        self,
        validation_results: Dict[str, Any],
        applicant_data: Dict[str, Any],
        extracted_data: Dict[str, Any]
    ):
        """Identify and categorize discrepancies"""
        all_issues = []

        # Collect issues from all validation steps
        for validation_type, validation_data in validation_results.items():
            if isinstance(validation_data, dict) and "issues" in validation_data:
                all_issues.extend(validation_data["issues"])

        # Categorize issues
        critical_issues = [issue for issue in all_issues if issue.get("severity") == "high"]
        warnings = [issue for issue in all_issues if issue.get("severity") in ["medium", "low"]]

        validation_results["critical_issues"] = critical_issues
        validation_results["warnings"] = warnings
        validation_results["discrepancies"] = all_issues

    def _calculate_validation_score(self, validation_results: Dict[str, Any]) -> float:
        """Calculate overall validation score"""
        scores = []

        # Personal info validation score
        personal_validation = validation_results.get("personal_info_validation", {})
        scores.append(personal_validation.get("confidence", 0.0))

        # Financial info validation score
        financial_validation = validation_results.get("financial_info_validation", {})
        scores.append(financial_validation.get("confidence", 0.0))

        # Document consistency score
        consistency_validation = validation_results.get("document_consistency", {})
        scores.append(consistency_validation.get("confidence", 0.0))

        # Completeness score
        completeness_validation = validation_results.get("completeness_check", {})
        scores.append(completeness_validation.get("completeness_score", 0.0))

        # Calculate weighted average
        weights = [0.25, 0.25, 0.25, 0.25]  # Equal weights for now
        weighted_score = sum(score * weight for score, weight in zip(scores, weights))

        # Apply penalties for critical issues
        critical_issues = len(validation_results.get("critical_issues", []))
        penalty = min(0.3, critical_issues * 0.1)

        return max(0.0, round(weighted_score - penalty, 3))

    def _requires_manual_review(self, validation_results: Dict[str, Any]) -> bool:
        """Determine if manual review is required"""
        critical_issues = validation_results.get("critical_issues", [])
        validation_score = validation_results.get("validation_score", 0.0)
        missing_critical = validation_results.get("completeness_check", {}).get("missing_critical", [])

        return (
            len(critical_issues) > 0 or
            validation_score < 0.6 or
            len(missing_critical) > 1
        )

    async def _generate_validation_summary(self, validation_results: Dict[str, Any]) -> str:
        """Generate a summary of validation results"""
        score = validation_results.get("validation_score", 0.0)
        critical_count = len(validation_results.get("critical_issues", []))
        warning_count = len(validation_results.get("warnings", []))
        requires_review = validation_results.get("requires_manual_review", False)

        summary = f"""
        Validation Summary:
        - Overall Score: {score:.2f}/1.00
        - Critical Issues: {critical_count}
        - Warnings: {warning_count}
        - Manual Review Required: {requires_review}
        """

        return summary.strip()

    # Helper methods
    def _check_field_consistency(self, field_name: str, value1: str, value2: str) -> Tuple[bool, float]:
        """Check consistency between two field values"""
        if not value1 or not value2:
            return True, 1.0

        value1_clean = value1.strip().lower()
        value2_clean = value2.strip().lower()

        if value1_clean == value2_clean:
            return True, 1.0

        # For names, check similarity
        if field_name in ["first_name", "last_name"]:
            similarity = self._calculate_string_similarity(value1_clean, value2_clean)
            return similarity > 0.8, similarity

        # For numeric fields
        if field_name in ["emirates_id", "phone"]:
            # Remove formatting characters
            value1_digits = re.sub(r'[^\d]', '', value1)
            value2_digits = re.sub(r'[^\d]', '', value2)
            return value1_digits == value2_digits, 1.0 if value1_digits == value2_digits else 0.0

        return False, 0.0

    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings using simple ratio"""
        if not str1 or not str2:
            return 0.0

        # Simple similarity calculation
        shorter = min(len(str1), len(str2))
        longer = max(len(str1), len(str2))

        if longer == 0:
            return 1.0

        matches = sum(c1 == c2 for c1, c2 in zip(str1, str2))
        return matches / longer

    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float"""
        if value is None:
            return None
        try:
            return float(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return None

    def _validate_emirates_id_format(self, emirates_id: Any) -> Dict[str, Any]:
        """Validate Emirates ID format"""
        if not emirates_id:
            return {"valid": False, "error": "Missing Emirates ID"}

        emirates_id_str = str(emirates_id).replace("-", "").replace(" ", "")

        if len(emirates_id_str) == 15 and emirates_id_str.isdigit():
            return {"valid": True, "format": "15-digit number"}
        else:
            return {"valid": False, "error": "Invalid format - should be 15 digits"}

    def _validate_email_format(self, email: Any) -> Dict[str, Any]:
        """Validate email format"""
        if not email:
            return {"valid": True, "note": "Email not provided"}

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, str(email)):
            return {"valid": True, "format": "valid email"}
        else:
            return {"valid": False, "error": "Invalid email format"}

    def _validate_phone_format(self, phone: Any) -> Dict[str, Any]:
        """Validate UAE phone number format"""
        if not phone:
            return {"valid": True, "note": "Phone not provided"}

        phone_str = re.sub(r'[^\d+]', '', str(phone))
        uae_patterns = [
            r'^\+971[0-9]{8,9}$',  # +971 followed by 8-9 digits
            r'^00971[0-9]{8,9}$',  # 00971 followed by 8-9 digits
            r'^0[0-9]{8,9}$'       # 0 followed by 8-9 digits
        ]

        for pattern in uae_patterns:
            if re.match(pattern, phone_str):
                return {"valid": True, "format": "valid UAE number"}

        return {"valid": False, "error": "Invalid UAE phone format"}

    def _validate_date_format(self, date_value: Any) -> Dict[str, Any]:
        """Validate date format"""
        if not date_value:
            return {"valid": True, "note": "Date not provided"}

        date_patterns = [
            r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
            r'^\d{2}/\d{2}/\d{4}$',  # MM/DD/YYYY
            r'^\d{2}-\d{2}-\d{4}$'   # DD-MM-YYYY
        ]

        date_str = str(date_value)
        for pattern in date_patterns:
            if re.match(pattern, date_str):
                return {"valid": True, "format": "valid date format"}

        return {"valid": False, "error": "Invalid date format"}

    def _setup_validation_rules(self) -> Dict[str, Any]:
        """Setup validation rules"""
        return {
            "financial_limits": {
                "monthly_income": {"min": 0, "max": 100000},
                "bank_balance": {"min": 0, "max": 10000000},
                "credit_score": {"min": 300, "max": 850}
            },
            "consistency_thresholds": {
                "name_similarity": 0.8,
                "income_variance": 0.5,
                "balance_income_ratio": 100
            }
        }

    def _setup_pattern_validators(self) -> Dict[str, Any]:
        """Setup pattern validators"""
        return {
            "emirates_id": r'^\d{15}$',
            "email": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            "phone_uae": r'^(\+971|00971|0)[0-9]{8,9}$'
        }
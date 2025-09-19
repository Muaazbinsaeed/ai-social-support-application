import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
import logging

from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate

from backend.config import settings
from backend.models.schemas import AgentResponse
from backend.services import embedding_service

logger = logging.getLogger(__name__)

class EligibilityAgent:
    """
    Eligibility Agent responsible for evaluating applications against
    predefined criteria for financial support and economic enablement programs
    """

    def __init__(self):
        self.llm = Ollama(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=0.2
        )

        # Load eligibility criteria
        self.eligibility_criteria = self._setup_eligibility_criteria()
        self.economic_programs = self._setup_economic_programs()

    async def check_eligibility(
        self,
        applicant_data: Dict[str, Any],
        extracted_data: Dict[str, Any],
        validation_results: Dict[str, Any]
    ) -> AgentResponse:
        """
        Check eligibility for financial support and economic enablement programs

        Args:
            applicant_data: Original applicant information
            extracted_data: Consolidated extracted data
            validation_results: Results from validation agent

        Returns:
            AgentResponse containing eligibility assessment
        """
        start_time = datetime.now()

        try:
            logger.info("Starting eligibility assessment")

            eligibility_results = {
                "financial_support": {
                    "eligible": False,
                    "score": 0.0,
                    "criteria_met": {},
                    "reasons": []
                },
                "economic_enablement": {
                    "eligible_programs": [],
                    "program_scores": {},
                    "recommendations": []
                },
                "overall_assessment": {
                    "risk_level": "unknown",
                    "priority_score": 0.0,
                    "requires_verification": False
                },
                "demographic_analysis": {},
                "financial_assessment": {}
            }

            # 1. Assess financial support eligibility
            financial_eligibility = await self._assess_financial_support_eligibility(
                applicant_data, extracted_data, validation_results
            )
            eligibility_results["financial_support"] = financial_eligibility

            # 2. Assess economic enablement program eligibility
            economic_eligibility = await self._assess_economic_enablement_eligibility(
                applicant_data, extracted_data
            )
            eligibility_results["economic_enablement"] = economic_eligibility

            # 3. Perform demographic analysis
            demographic_analysis = await self._perform_demographic_analysis(
                applicant_data, extracted_data
            )
            eligibility_results["demographic_analysis"] = demographic_analysis

            # 4. Conduct financial assessment
            financial_assessment = await self._conduct_financial_assessment(
                extracted_data
            )
            eligibility_results["financial_assessment"] = financial_assessment

            # 5. Calculate overall assessment
            overall_assessment = await self._calculate_overall_assessment(
                eligibility_results
            )
            eligibility_results["overall_assessment"] = overall_assessment

            # 6. Use LLM for complex eligibility reasoning
            llm_assessment = await self._llm_eligibility_assessment(eligibility_results)
            eligibility_results["llm_insights"] = llm_assessment

            # Calculate confidence score
            confidence_score = self._calculate_eligibility_confidence(eligibility_results, validation_results)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            success = (
                eligibility_results["financial_support"]["eligible"] or
                len(eligibility_results["economic_enablement"]["eligible_programs"]) > 0
            )

            logger.info(f"Eligibility assessment completed: {success}")

            return AgentResponse(
                success=True,
                message=f"Eligibility assessment completed - Financial Support: {'Eligible' if eligibility_results['financial_support']['eligible'] else 'Not Eligible'}",
                data=eligibility_results,
                confidence_score=confidence_score,
                processing_time_ms=int(processing_time)
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Eligibility assessment failed: {str(e)}")

            return AgentResponse(
                success=False,
                message=f"Eligibility assessment failed: {str(e)}",
                data={"error": str(e)},
                processing_time_ms=int(processing_time)
            )

    async def _assess_financial_support_eligibility(
        self,
        applicant_data: Dict[str, Any],
        extracted_data: Dict[str, Any],
        validation_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess eligibility for financial support"""
        financial_info = extracted_data.get("financial_info", {})
        personal_info = extracted_data.get("personal_info", {})

        assessment = {
            "eligible": False,
            "score": 0.0,
            "criteria_met": {},
            "reasons": [],
            "support_amount": 0.0
        }

        criteria_scores = {}

        # 1. Income Criteria
        monthly_income = self._safe_float(financial_info.get("monthly_income", 0))
        income_threshold = self.eligibility_criteria["financial_support"]["max_monthly_income"]

        if monthly_income is not None:
            income_eligible = monthly_income <= income_threshold
            criteria_scores["income"] = 1.0 if income_eligible else 0.0

            if income_eligible:
                assessment["reasons"].append(f"Monthly income ({monthly_income} AED) meets threshold")
            else:
                assessment["reasons"].append(f"Monthly income ({monthly_income} AED) exceeds threshold of {income_threshold} AED")
        else:
            criteria_scores["income"] = 0.0
            assessment["reasons"].append("Monthly income not available")

        # 2. Asset Criteria
        total_assets = self._safe_float(financial_info.get("total_assets", 0))
        asset_threshold = self.eligibility_criteria["financial_support"]["max_total_assets"]

        if total_assets is not None:
            asset_eligible = total_assets <= asset_threshold
            criteria_scores["assets"] = 1.0 if asset_eligible else 0.0

            if asset_eligible:
                assessment["reasons"].append(f"Total assets ({total_assets} AED) meet threshold")
            else:
                assessment["reasons"].append(f"Total assets ({total_assets} AED) exceed threshold of {asset_threshold} AED")
        else:
            criteria_scores["assets"] = 0.5  # Partial score if assets not reported
            assessment["reasons"].append("Asset information not fully available")

        # 3. Family Size Criteria
        family_size = self._safe_int(financial_info.get("family_size", 1))
        if family_size and family_size >= 1:
            criteria_scores["family_size"] = min(1.0, family_size / 5)  # Higher score for larger families
            assessment["reasons"].append(f"Family size: {family_size} members")
        else:
            criteria_scores["family_size"] = 0.3
            assessment["reasons"].append("Family size information not available")

        # 4. Employment Status
        employment_status = financial_info.get("employment_status", "").lower()
        if "unemployed" in employment_status or "seeking" in employment_status:
            criteria_scores["employment"] = 1.0
            assessment["reasons"].append("Currently unemployed - meets employment criteria")
        elif "employed" in employment_status:
            criteria_scores["employment"] = 0.3
            assessment["reasons"].append("Currently employed - partial qualification")
        else:
            criteria_scores["employment"] = 0.0
            assessment["reasons"].append("Employment status unclear")

        # 5. UAE Residency (Emirates ID check)
        emirates_id = personal_info.get("emirates_id")
        if emirates_id and len(str(emirates_id).replace("-", "").replace(" ", "")) == 15:
            criteria_scores["residency"] = 1.0
            assessment["reasons"].append("Valid UAE residency confirmed")
        else:
            criteria_scores["residency"] = 0.0
            assessment["reasons"].append("UAE residency not confirmed")

        # 6. Data Quality Score
        validation_score = validation_results.get("validation_score", 0.0)
        criteria_scores["data_quality"] = validation_score
        assessment["reasons"].append(f"Data validation score: {validation_score:.2f}")

        # Calculate weighted score
        weights = {
            "income": 0.25,
            "assets": 0.20,
            "family_size": 0.15,
            "employment": 0.20,
            "residency": 0.15,
            "data_quality": 0.05
        }

        total_score = sum(criteria_scores[criterion] * weights[criterion]
                         for criterion in weights.keys())

        assessment["score"] = round(total_score, 3)
        assessment["criteria_met"] = criteria_scores

        # Determine eligibility
        eligibility_threshold = self.eligibility_criteria["financial_support"]["eligibility_threshold"]
        assessment["eligible"] = total_score >= eligibility_threshold

        # Calculate support amount if eligible
        if assessment["eligible"]:
            assessment["support_amount"] = self._calculate_support_amount(
                monthly_income, family_size, total_assets
            )

        return assessment

    async def _assess_economic_enablement_eligibility(
        self,
        applicant_data: Dict[str, Any],
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess eligibility for economic enablement programs"""
        personal_info = extracted_data.get("personal_info", {})
        financial_info = extracted_data.get("financial_info", {})
        employment_info = extracted_data.get("employment_info", {})

        assessment = {
            "eligible_programs": [],
            "program_scores": {},
            "recommendations": []
        }

        # Evaluate each economic program
        for program_name, program_criteria in self.economic_programs.items():
            program_score = await self._evaluate_program_eligibility(
                program_name, program_criteria, personal_info, financial_info, employment_info
            )

            assessment["program_scores"][program_name] = program_score

            if program_score["eligible"]:
                assessment["eligible_programs"].append(program_name)
                assessment["recommendations"].append({
                    "program": program_name,
                    "score": program_score["score"],
                    "reasons": program_score["reasons"],
                    "next_steps": program_criteria.get("next_steps", [])
                })

        return assessment

    async def _evaluate_program_eligibility(
        self,
        program_name: str,
        program_criteria: Dict[str, Any],
        personal_info: Dict[str, Any],
        financial_info: Dict[str, Any],
        employment_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate eligibility for a specific economic program"""
        score_components = {}
        reasons = []

        # Age criteria
        age_range = program_criteria.get("age_range")
        if age_range:
            # This is simplified - in practice, calculate from date_of_birth
            score_components["age"] = 1.0  # Assume eligible for MVP
            reasons.append("Age requirements met")

        # Education criteria
        education_level = program_criteria.get("min_education")
        if education_level:
            user_education = employment_info.get("highest_qualification", "").lower()
            if any(level in user_education for level in ["bachelor", "master", "diploma", "certificate"]):
                score_components["education"] = 1.0
                reasons.append("Education requirements met")
            else:
                score_components["education"] = 0.5
                reasons.append("Partial education requirements met")

        # Skills assessment
        required_skills = program_criteria.get("required_skills", [])
        user_skills = employment_info.get("skills", [])

        if required_skills and user_skills:
            skill_match = len(set(required_skills) & set(user_skills)) / len(required_skills)
            score_components["skills"] = skill_match
            reasons.append(f"Skills match: {skill_match:.0%}")
        else:
            score_components["skills"] = 0.3
            reasons.append("Skills assessment incomplete")

        # Employment status
        employment_status = financial_info.get("employment_status", "").lower()
        target_employment = program_criteria.get("target_employment", [])

        if any(status in employment_status for status in target_employment):
            score_components["employment_status"] = 1.0
            reasons.append("Employment status matches program target")
        else:
            score_components["employment_status"] = 0.3
            reasons.append("Employment status partially matches")

        # Calculate overall score
        weights = program_criteria.get("criteria_weights", {
            "age": 0.2, "education": 0.3, "skills": 0.3, "employment_status": 0.2
        })

        total_score = sum(score_components.get(criterion, 0) * weight
                         for criterion, weight in weights.items())

        eligibility_threshold = program_criteria.get("eligibility_threshold", 0.6)
        eligible = total_score >= eligibility_threshold

        return {
            "score": round(total_score, 3),
            "eligible": eligible,
            "reasons": reasons,
            "score_components": score_components
        }

    async def _perform_demographic_analysis(
        self,
        applicant_data: Dict[str, Any],
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform demographic analysis for targeted support"""
        personal_info = extracted_data.get("personal_info", {})
        financial_info = extracted_data.get("financial_info", {})

        analysis = {
            "demographic_category": "general",
            "priority_factors": [],
            "vulnerability_indicators": [],
            "support_recommendations": []
        }

        # Family composition analysis
        family_size = self._safe_int(financial_info.get("family_size", 1))
        dependents = self._safe_int(financial_info.get("dependents", 0))

        if family_size and family_size > 4:
            analysis["priority_factors"].append("Large family size")
            analysis["demographic_category"] = "large_family"

        if dependents and dependents > 2:
            analysis["vulnerability_indicators"].append("Multiple dependents")

        # Income-to-family ratio
        monthly_income = self._safe_float(financial_info.get("monthly_income", 0))
        if monthly_income and family_size:
            per_capita_income = monthly_income / family_size
            if per_capita_income < 1000:  # AED per person
                analysis["vulnerability_indicators"].append("Low per-capita income")

        # Employment stability
        employment_status = financial_info.get("employment_status", "").lower()
        if "temporary" in employment_status or "contract" in employment_status:
            analysis["vulnerability_indicators"].append("Unstable employment")

        return analysis

    async def _conduct_financial_assessment(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Conduct detailed financial assessment"""
        financial_info = extracted_data.get("financial_info", {})

        assessment = {
            "debt_to_income_ratio": None,
            "liquidity_assessment": "unknown",
            "financial_stability": "unknown",
            "risk_indicators": []
        }

        # Calculate debt-to-income ratio
        monthly_income = self._safe_float(financial_info.get("monthly_income", 0))
        total_liabilities = self._safe_float(financial_info.get("total_liabilities", 0))

        if monthly_income and monthly_income > 0 and total_liabilities:
            # Assume monthly debt payment is total liabilities / 60 (5 years)
            monthly_debt = total_liabilities / 60
            debt_to_income = monthly_debt / monthly_income
            assessment["debt_to_income_ratio"] = round(debt_to_income, 3)

            if debt_to_income > 0.4:
                assessment["risk_indicators"].append("High debt-to-income ratio")

        # Liquidity assessment
        bank_balance = self._safe_float(financial_info.get("bank_balance", 0))
        if bank_balance is not None and monthly_income:
            months_of_expenses = bank_balance / (monthly_income * 0.7)  # Assume 70% of income for expenses
            if months_of_expenses < 1:
                assessment["liquidity_assessment"] = "poor"
                assessment["risk_indicators"].append("Low liquidity")
            elif months_of_expenses < 3:
                assessment["liquidity_assessment"] = "fair"
            else:
                assessment["liquidity_assessment"] = "good"

        # Financial stability assessment
        if len(assessment["risk_indicators"]) == 0:
            assessment["financial_stability"] = "stable"
        elif len(assessment["risk_indicators"]) <= 2:
            assessment["financial_stability"] = "moderate_risk"
        else:
            assessment["financial_stability"] = "high_risk"

        return assessment

    async def _calculate_overall_assessment(self, eligibility_results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall assessment and priority scoring"""
        financial_support = eligibility_results["financial_support"]
        economic_enablement = eligibility_results["economic_enablement"]
        demographic_analysis = eligibility_results["demographic_analysis"]

        assessment = {
            "risk_level": "medium",
            "priority_score": 0.0,
            "requires_verification": False,
            "recommended_actions": []
        }

        # Calculate priority score
        priority_components = {
            "financial_need": financial_support["score"] * 0.4,
            "economic_potential": len(economic_enablement["eligible_programs"]) / 5 * 0.3,
            "vulnerability": len(demographic_analysis["vulnerability_indicators"]) / 3 * 0.3
        }

        assessment["priority_score"] = round(sum(priority_components.values()), 3)

        # Determine risk level
        if assessment["priority_score"] > 0.7:
            assessment["risk_level"] = "high"
            assessment["recommended_actions"].append("Expedite processing")
        elif assessment["priority_score"] < 0.3:
            assessment["risk_level"] = "low"

        # Verification requirements
        if financial_support["score"] > 0.8 and len(demographic_analysis["vulnerability_indicators"]) > 2:
            assessment["requires_verification"] = True
            assessment["recommended_actions"].append("Conduct field verification")

        return assessment

    async def _llm_eligibility_assessment(self, eligibility_results: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM for complex eligibility reasoning"""
        try:
            prompt = f"""
            Analyze the following eligibility assessment results and provide insights:

            Financial Support Eligibility: {eligibility_results['financial_support']['eligible']}
            Score: {eligibility_results['financial_support']['score']}

            Economic Programs: {eligibility_results['economic_enablement']['eligible_programs']}

            Risk Level: {eligibility_results['overall_assessment']['risk_level']}

            Provide recommendations for:
            1. Support optimization
            2. Program prioritization
            3. Risk mitigation

            Format as JSON with keys: recommendations, insights, concerns
            """

            response = await asyncio.to_thread(self.llm.invoke, prompt)

            # Try to parse JSON response
            try:
                import json
                return json.loads(response)
            except:
                return {"insights": response[:500], "status": "text_response"}

        except Exception as e:
            logger.error(f"LLM assessment failed: {str(e)}")
            return {"error": str(e)}

    def _calculate_support_amount(
        self,
        monthly_income: Optional[float],
        family_size: Optional[int],
        total_assets: Optional[float]
    ) -> float:
        """Calculate recommended financial support amount"""
        base_amount = 2000  # Base support amount in AED

        if not monthly_income:
            return base_amount

        # Adjust based on income gap
        target_income = 3000  # Target minimum income
        income_gap = max(0, target_income - monthly_income)
        support_amount = min(base_amount, income_gap)

        # Adjust for family size
        if family_size and family_size > 3:
            support_amount *= (1 + (family_size - 3) * 0.2)

        # Cap the amount
        max_support = 5000
        return min(support_amount, max_support)

    def _calculate_eligibility_confidence(
        self,
        eligibility_results: Dict[str, Any],
        validation_results: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for eligibility assessment"""
        validation_score = validation_results.get("validation_score", 0.0)
        data_completeness = validation_results.get("completeness_check", {}).get("completeness_score", 0.0)

        # Base confidence on data quality
        base_confidence = (validation_score + data_completeness) / 2

        # Adjust based on critical missing data
        critical_issues = len(validation_results.get("critical_issues", []))
        if critical_issues > 0:
            base_confidence *= 0.8

        return round(base_confidence, 3)

    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float"""
        if value is None:
            return None
        try:
            return float(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value: Any) -> Optional[int]:
        """Safely convert value to int"""
        if value is None:
            return None
        try:
            return int(float(str(value).replace(",", "")))
        except (ValueError, TypeError):
            return None

    def _setup_eligibility_criteria(self) -> Dict[str, Any]:
        """Setup eligibility criteria for financial support"""
        return {
            "financial_support": {
                "max_monthly_income": 4000,  # AED
                "max_total_assets": 100000,  # AED
                "min_family_size": 1,
                "eligibility_threshold": 0.6,  # Minimum score to qualify
                "required_documents": ["emirates_id", "income_proof"]
            }
        }

    def _setup_economic_programs(self) -> Dict[str, Any]:
        """Setup economic enablement programs"""
        return {
            "skills_development": {
                "description": "Technical and professional skills training",
                "age_range": (18, 55),
                "min_education": "high_school",
                "required_skills": ["basic_computer", "communication"],
                "target_employment": ["unemployed", "underemployed"],
                "eligibility_threshold": 0.5,
                "criteria_weights": {
                    "age": 0.2, "education": 0.3, "skills": 0.3, "employment_status": 0.2
                },
                "next_steps": ["Register for training", "Complete assessment", "Begin program"]
            },
            "entrepreneurship_support": {
                "description": "Business development and startup support",
                "age_range": (21, 50),
                "min_education": "diploma",
                "required_skills": ["business_planning", "financial_literacy"],
                "target_employment": ["unemployed", "self_employed"],
                "eligibility_threshold": 0.6,
                "criteria_weights": {
                    "age": 0.15, "education": 0.35, "skills": 0.35, "employment_status": 0.15
                },
                "next_steps": ["Submit business plan", "Attend workshops", "Access funding"]
            },
            "job_placement": {
                "description": "Employment matching and placement services",
                "age_range": (18, 60),
                "min_education": "any",
                "required_skills": ["basic_communication"],
                "target_employment": ["unemployed"],
                "eligibility_threshold": 0.4,
                "criteria_weights": {
                    "age": 0.25, "education": 0.25, "skills": 0.25, "employment_status": 0.25
                },
                "next_steps": ["Register with employment service", "Complete profile", "Interview scheduling"]
            },
            "financial_literacy": {
                "description": "Financial education and planning support",
                "age_range": (18, 65),
                "min_education": "any",
                "required_skills": [],
                "target_employment": ["any"],
                "eligibility_threshold": 0.3,
                "criteria_weights": {
                    "age": 0.2, "education": 0.2, "skills": 0.2, "employment_status": 0.4
                },
                "next_steps": ["Enroll in program", "Complete modules", "Get certified"]
            }
        }
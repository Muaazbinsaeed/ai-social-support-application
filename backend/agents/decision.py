import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging

from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate

from backend.config import settings
from backend.models.schemas import AgentResponse, Decision

logger = logging.getLogger(__name__)

class DecisionAgent:
    """
    Decision Agent responsible for making final recommendations
    based on all previous agent outputs and analysis
    """

    def __init__(self):
        self.llm = Ollama(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=0.1
        )

        self.decision_criteria = self._setup_decision_criteria()
        self.llm_prompt = self._create_decision_prompt()

    async def make_decision(
        self,
        applicant_data: Dict[str, Any],
        extracted_data: Dict[str, Any],
        validation_results: Dict[str, Any],
        eligibility_results: Dict[str, Any]
    ) -> AgentResponse:
        """
        Make final decision on application

        Args:
            applicant_data: Original applicant information
            extracted_data: Consolidated extracted data
            validation_results: Results from validation agent
            eligibility_results: Results from eligibility agent

        Returns:
            AgentResponse containing final decision and recommendations
        """
        start_time = datetime.now()

        try:
            logger.info("Starting decision making process")

            decision_results = {
                "financial_support_decision": Decision.DECLINE,
                "financial_support_amount": 0.0,
                "financial_support_duration_months": 0,
                "economic_enablement_programs": [],
                "priority_level": "normal",
                "requires_human_review": False,
                "decision_reasoning": "",
                "confidence_score": 0.0,
                "next_steps": [],
                "conditions": [],
                "review_schedule": None
            }

            # 1. Make financial support decision
            financial_decision = await self._make_financial_support_decision(
                applicant_data, extracted_data, validation_results, eligibility_results
            )
            decision_results.update(financial_decision)

            # 2. Recommend economic enablement programs
            economic_recommendations = await self._recommend_economic_programs(
                eligibility_results, extracted_data
            )
            decision_results["economic_enablement_programs"] = economic_recommendations

            # 3. Determine priority level
            priority_assessment = await self._assess_priority_level(
                eligibility_results, validation_results
            )
            decision_results["priority_level"] = priority_assessment

            # 4. Check if human review is required
            review_requirement = await self._assess_review_requirement(
                decision_results, validation_results, eligibility_results
            )
            decision_results["requires_human_review"] = review_requirement

            # 5. Generate comprehensive reasoning using LLM
            llm_reasoning = await self._generate_llm_reasoning(
                decision_results, applicant_data, extracted_data, eligibility_results
            )
            decision_results["decision_reasoning"] = llm_reasoning.get("reasoning", "")
            decision_results["next_steps"] = llm_reasoning.get("next_steps", [])
            decision_results["conditions"] = llm_reasoning.get("conditions", [])

            # 6. Calculate overall confidence
            confidence_score = self._calculate_decision_confidence(
                decision_results, validation_results, eligibility_results
            )
            decision_results["confidence_score"] = confidence_score

            # 7. Set review schedule if needed
            if decision_results["requires_human_review"]:
                decision_results["review_schedule"] = self._determine_review_schedule(decision_results)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            success = confidence_score >= 0.7 and not decision_results["requires_human_review"]

            logger.info(f"Decision completed: {decision_results['financial_support_decision']}")

            return AgentResponse(
                success=success,
                message=f"Decision: {decision_results['financial_support_decision'].value} - Confidence: {confidence_score:.2f}",
                data=decision_results,
                confidence_score=confidence_score,
                processing_time_ms=int(processing_time)
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Decision making failed: {str(e)}")

            return AgentResponse(
                success=False,
                message=f"Decision making failed: {str(e)}",
                data={"error": str(e)},
                processing_time_ms=int(processing_time)
            )

    async def _make_financial_support_decision(
        self,
        applicant_data: Dict[str, Any],
        extracted_data: Dict[str, Any],
        validation_results: Dict[str, Any],
        eligibility_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make financial support decision based on eligibility and validation"""
        financial_support = eligibility_results.get("financial_support", {})
        validation_score = validation_results.get("validation_score", 0.0)

        decision_data = {
            "financial_support_decision": Decision.DECLINE,
            "financial_support_amount": 0.0,
            "financial_support_duration_months": 0
        }

        # Get eligibility assessment
        eligible = financial_support.get("eligible", False)
        eligibility_score = financial_support.get("score", 0.0)
        support_amount = financial_support.get("support_amount", 0.0)

        # Decision logic
        if eligible and validation_score >= 0.7 and eligibility_score >= 0.6:
            # Full approval
            decision_data["financial_support_decision"] = Decision.APPROVE
            decision_data["financial_support_amount"] = support_amount
            decision_data["financial_support_duration_months"] = self._calculate_support_duration(
                extracted_data, eligibility_score
            )

        elif eligible and validation_score >= 0.5 and eligibility_score >= 0.5:
            # Conditional approval or review required
            if validation_score < 0.6 or eligibility_score < 0.6:
                decision_data["financial_support_decision"] = Decision.REVIEW_REQUIRED
                decision_data["financial_support_amount"] = support_amount * 0.8  # Reduced amount
            else:
                decision_data["financial_support_decision"] = Decision.APPROVE
                decision_data["financial_support_amount"] = support_amount

            decision_data["financial_support_duration_months"] = self._calculate_support_duration(
                extracted_data, eligibility_score
            )

        else:
            # Decline
            decision_data["financial_support_decision"] = Decision.DECLINE
            decision_data["financial_support_amount"] = 0.0
            decision_data["financial_support_duration_months"] = 0

        return decision_data

    async def _recommend_economic_programs(
        self,
        eligibility_results: Dict[str, Any],
        extracted_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Recommend economic enablement programs based on eligibility"""
        economic_enablement = eligibility_results.get("economic_enablement", {})
        eligible_programs = economic_enablement.get("eligible_programs", [])
        program_scores = economic_enablement.get("program_scores", {})
        recommendations = economic_enablement.get("recommendations", [])

        enhanced_recommendations = []

        for recommendation in recommendations:
            program_name = recommendation.get("program")
            program_score = recommendation.get("score", 0.0)

            enhanced_recommendation = {
                "program_name": program_name,
                "priority": self._calculate_program_priority(program_name, program_score, extracted_data),
                "score": program_score,
                "reasons": recommendation.get("reasons", []),
                "next_steps": recommendation.get("next_steps", []),
                "timeline": self._estimate_program_timeline(program_name),
                "success_probability": self._estimate_success_probability(program_name, extracted_data)
            }

            enhanced_recommendations.append(enhanced_recommendation)

        # Sort by priority and score
        enhanced_recommendations.sort(key=lambda x: (x["priority"], x["score"]), reverse=True)

        return enhanced_recommendations

    async def _assess_priority_level(
        self,
        eligibility_results: Dict[str, Any],
        validation_results: Dict[str, Any]
    ) -> str:
        """Assess priority level for case processing"""
        overall_assessment = eligibility_results.get("overall_assessment", {})
        demographic_analysis = eligibility_results.get("demographic_analysis", {})

        priority_score = overall_assessment.get("priority_score", 0.0)
        vulnerability_indicators = demographic_analysis.get("vulnerability_indicators", [])
        risk_level = overall_assessment.get("risk_level", "medium")

        # Determine priority level
        if priority_score > 0.8 or len(vulnerability_indicators) > 3 or risk_level == "high":
            return "high"
        elif priority_score > 0.6 or len(vulnerability_indicators) > 1 or risk_level == "medium":
            return "medium"
        else:
            return "low"

    async def _assess_review_requirement(
        self,
        decision_results: Dict[str, Any],
        validation_results: Dict[str, Any],
        eligibility_results: Dict[str, Any]
    ) -> bool:
        """Determine if human review is required"""
        # Check validation issues
        critical_issues = validation_results.get("critical_issues", [])
        validation_score = validation_results.get("validation_score", 0.0)

        # Check eligibility concerns
        overall_assessment = eligibility_results.get("overall_assessment", {})
        requires_verification = overall_assessment.get("requires_verification", False)

        # Check decision characteristics
        financial_decision = decision_results.get("financial_support_decision")
        financial_amount = decision_results.get("financial_support_amount", 0.0)

        return (
            len(critical_issues) > 0 or
            validation_score < 0.6 or
            requires_verification or
            financial_decision == Decision.REVIEW_REQUIRED or
            financial_amount > 4000  # High amount threshold
        )

    async def _generate_llm_reasoning(
        self,
        decision_results: Dict[str, Any],
        applicant_data: Dict[str, Any],
        extracted_data: Dict[str, Any],
        eligibility_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comprehensive reasoning using LLM"""
        try:
            # Prepare context for LLM
            context = {
                "decision": decision_results["financial_support_decision"].value,
                "amount": decision_results["financial_support_amount"],
                "programs": [p["program_name"] for p in decision_results.get("economic_enablement_programs", [])],
                "priority": decision_results["priority_level"],
                "review_required": decision_results["requires_human_review"]
            }

            # Financial summary
            financial_info = extracted_data.get("financial_info", {})
            financial_summary = {
                "monthly_income": financial_info.get("monthly_income", "N/A"),
                "family_size": financial_info.get("family_size", "N/A"),
                "employment_status": financial_info.get("employment_status", "N/A")
            }

            # Eligibility summary
            eligibility_summary = {
                "financial_eligible": eligibility_results.get("financial_support", {}).get("eligible", False),
                "eligibility_score": eligibility_results.get("financial_support", {}).get("score", 0.0),
                "eligible_programs_count": len(eligibility_results.get("economic_enablement", {}).get("eligible_programs", []))
            }

            prompt_input = {
                "context": context,
                "financial_summary": financial_summary,
                "eligibility_summary": eligibility_summary,
                "applicant_name": f"{applicant_data.get('first_name', '')} {applicant_data.get('last_name', '')}".strip()
            }

            formatted_prompt = self.llm_prompt.format(**prompt_input)

            response = await asyncio.to_thread(self.llm.invoke, formatted_prompt)

            # Try to parse JSON response
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # If JSON parsing fails, extract key information from text
                return self._parse_text_reasoning(response)

        except Exception as e:
            logger.error(f"LLM reasoning generation failed: {str(e)}")
            return {
                "reasoning": f"Decision based on eligibility assessment and validation results. Error in detailed reasoning: {str(e)}",
                "next_steps": ["Complete document verification", "Schedule follow-up"],
                "conditions": []
            }

    def _parse_text_reasoning(self, response: str) -> Dict[str, Any]:
        """Parse reasoning from text response if JSON parsing fails"""
        reasoning = response[:500]  # Take first 500 characters as reasoning

        # Extract next steps and conditions using simple patterns
        next_steps = []
        conditions = []

        lines = response.split('\n')
        in_next_steps = False
        in_conditions = False

        for line in lines:
            line = line.strip()
            if 'next steps' in line.lower() or 'actions' in line.lower():
                in_next_steps = True
                in_conditions = False
                continue
            elif 'conditions' in line.lower() or 'requirements' in line.lower():
                in_conditions = True
                in_next_steps = False
                continue

            if in_next_steps and line and not line.startswith('#'):
                next_steps.append(line.lstrip('- '))
            elif in_conditions and line and not line.startswith('#'):
                conditions.append(line.lstrip('- '))

        return {
            "reasoning": reasoning,
            "next_steps": next_steps[:5],  # Limit to 5 items
            "conditions": conditions[:5]   # Limit to 5 items
        }

    def _calculate_support_duration(self, extracted_data: Dict[str, Any], eligibility_score: float) -> int:
        """Calculate support duration in months"""
        base_duration = 6  # 6 months base

        # Adjust based on family size
        financial_info = extracted_data.get("financial_info", {})
        family_size = self._safe_int(financial_info.get("family_size", 1))

        if family_size and family_size > 4:
            base_duration += 3

        # Adjust based on eligibility score
        if eligibility_score > 0.8:
            base_duration += 3
        elif eligibility_score < 0.6:
            base_duration = max(3, base_duration - 3)

        # Cap at reasonable limits
        return min(12, max(3, base_duration))

    def _calculate_program_priority(self, program_name: str, score: float, extracted_data: Dict[str, Any]) -> float:
        """Calculate priority score for economic programs"""
        base_priority = score

        # Adjust based on program type and applicant profile
        employment_info = extracted_data.get("employment_info", {})
        financial_info = extracted_data.get("financial_info", {})

        employment_status = financial_info.get("employment_status", "").lower()

        # Prioritize job placement for unemployed
        if program_name == "job_placement" and "unemployed" in employment_status:
            base_priority += 0.2

        # Prioritize skills development for underemployed
        elif program_name == "skills_development" and ("underemployed" in employment_status or score > 0.7):
            base_priority += 0.15

        # Prioritize entrepreneurship for those with business background
        elif program_name == "entrepreneurship_support":
            skills = employment_info.get("skills", [])
            if any("business" in skill.lower() for skill in skills):
                base_priority += 0.1

        return min(1.0, base_priority)

    def _estimate_program_timeline(self, program_name: str) -> str:
        """Estimate timeline for program completion"""
        timelines = {
            "job_placement": "2-4 weeks",
            "skills_development": "3-6 months",
            "entrepreneurship_support": "6-12 months",
            "financial_literacy": "4-8 weeks"
        }
        return timelines.get(program_name, "3-6 months")

    def _estimate_success_probability(self, program_name: str, extracted_data: Dict[str, Any]) -> float:
        """Estimate probability of program success"""
        base_probabilities = {
            "job_placement": 0.75,
            "skills_development": 0.65,
            "entrepreneurship_support": 0.55,
            "financial_literacy": 0.85
        }

        base_prob = base_probabilities.get(program_name, 0.6)

        # Adjust based on applicant characteristics
        employment_info = extracted_data.get("employment_info", {})
        education_level = employment_info.get("highest_qualification", "").lower()

        if any(level in education_level for level in ["bachelor", "master", "diploma"]):
            base_prob += 0.1

        return min(1.0, base_prob)

    def _determine_review_schedule(self, decision_results: Dict[str, Any]) -> str:
        """Determine when the case should be reviewed"""
        priority = decision_results.get("priority_level", "normal")

        if priority == "high":
            return "within_24_hours"
        elif priority == "medium":
            return "within_48_hours"
        else:
            return "within_1_week"

    def _calculate_decision_confidence(
        self,
        decision_results: Dict[str, Any],
        validation_results: Dict[str, Any],
        eligibility_results: Dict[str, Any]
    ) -> float:
        """Calculate overall confidence in the decision"""
        # Base confidence on validation and eligibility scores
        validation_score = validation_results.get("validation_score", 0.0)
        eligibility_score = eligibility_results.get("financial_support", {}).get("score", 0.0)

        base_confidence = (validation_score + eligibility_score) / 2

        # Adjust based on decision characteristics
        if decision_results["requires_human_review"]:
            base_confidence *= 0.8

        # Adjust based on data quality
        critical_issues = len(validation_results.get("critical_issues", []))
        if critical_issues > 0:
            base_confidence *= (1.0 - min(0.3, critical_issues * 0.1))

        return round(base_confidence, 3)

    def _safe_int(self, value: Any) -> Optional[int]:
        """Safely convert value to int"""
        if value is None:
            return None
        try:
            return int(float(str(value).replace(",", "")))
        except (ValueError, TypeError):
            return None

    def _create_decision_prompt(self) -> PromptTemplate:
        """Create prompt template for LLM decision reasoning"""
        return PromptTemplate(
            input_variables=["context", "financial_summary", "eligibility_summary", "applicant_name"],
            template="""
            Generate a decision explanation for social support application.

            Applicant: {applicant_name}
            Decision Context: {context}
            Financial Summary: {financial_summary}
            Eligibility Summary: {eligibility_summary}

            Provide a JSON response with:
            1. "reasoning": Clear explanation of decision rationale
            2. "next_steps": List of 3-5 immediate next steps for applicant
            3. "conditions": List of any conditions or requirements

            Focus on:
            - Clear justification for financial support decision
            - Actionable recommendations for economic programs
            - Specific requirements for approval/review

            Format as valid JSON only:
            """
        )

    def _setup_decision_criteria(self) -> Dict[str, Any]:
        """Setup decision making criteria and thresholds"""
        return {
            "approval_thresholds": {
                "validation_score": 0.7,
                "eligibility_score": 0.6,
                "combined_minimum": 0.65
            },
            "review_triggers": {
                "high_amount": 4000,
                "low_validation": 0.6,
                "critical_issues": 1,
                "verification_required": True
            },
            "priority_factors": {
                "vulnerability_weight": 0.3,
                "financial_need_weight": 0.4,
                "data_quality_weight": 0.3
            }
        }
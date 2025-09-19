import asyncio
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime, timedelta
import json
import logging
from enum import Enum

from langgraph.graph import StateGraph, END
from langchain_community.llms import Ollama
from langchain.schema import BaseMessage, HumanMessage, AIMessage

from backend.config import settings
from backend.models.schemas import (
    ApplicationStatus, AgentType, AgentResponse,
    ProcessingStatus as ProcessingStatusSchema
)
from backend.services import document_processor, ocr_service, embedding_service

logger = logging.getLogger(__name__)

class ProcessingStage(str, Enum):
    INITIALIZATION = "initialization"
    DOCUMENT_PROCESSING = "document_processing"
    DATA_EXTRACTION = "data_extraction"
    VALIDATION = "validation"
    ELIGIBILITY_CHECK = "eligibility_check"
    DECISION_MAKING = "decision_making"
    FINALIZATION = "finalization"
    COMPLETED = "completed"
    FAILED = "failed"

class ApplicationState(TypedDict):
    """State object that flows through the LangGraph workflow"""
    application_id: int
    current_stage: ProcessingStage
    progress_percentage: int
    applicant_data: Dict[str, Any]
    documents: List[Dict[str, Any]]
    extracted_data: Dict[str, Any]
    validation_results: Dict[str, Any]
    eligibility_results: Dict[str, Any]
    final_decision: Dict[str, Any]
    agent_responses: List[AgentResponse]
    errors: List[str]
    metadata: Dict[str, Any]
    processing_start_time: datetime
    estimated_completion: Optional[datetime]

class MasterOrchestrator:
    """
    Master Orchestrator Agent that coordinates the entire application processing workflow
    Uses LangGraph for state management and workflow orchestration
    """

    def __init__(self):
        # Initialize LLM
        self.llm = Ollama(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=0.1
        )

        # Initialize the workflow graph
        self.workflow = self._build_workflow_graph()

        # Processing stage weights for progress calculation
        self.stage_weights = {
            ProcessingStage.INITIALIZATION: 5,
            ProcessingStage.DOCUMENT_PROCESSING: 15,
            ProcessingStage.DATA_EXTRACTION: 20,
            ProcessingStage.VALIDATION: 20,
            ProcessingStage.ELIGIBILITY_CHECK: 25,
            ProcessingStage.DECISION_MAKING: 10,
            ProcessingStage.FINALIZATION: 5
        }

    def _build_workflow_graph(self) -> StateGraph:
        """Build the LangGraph workflow for application processing"""
        workflow = StateGraph(ApplicationState)

        # Add nodes for each processing stage
        workflow.add_node("initialize", self._initialize_processing)
        workflow.add_node("process_documents", self._process_documents)
        workflow.add_node("extract_data", self._extract_data)
        workflow.add_node("validate_data", self._validate_data)
        workflow.add_node("check_eligibility", self._check_eligibility)
        workflow.add_node("make_decision", self._make_decision)
        workflow.add_node("finalize", self._finalize_processing)

        # Define the workflow edges
        workflow.add_edge("initialize", "process_documents")
        workflow.add_edge("process_documents", "extract_data")
        workflow.add_edge("extract_data", "validate_data")
        workflow.add_edge("validate_data", "check_eligibility")
        workflow.add_edge("check_eligibility", "make_decision")
        workflow.add_edge("make_decision", "finalize")
        workflow.add_edge("finalize", END)

        # Set the entry point
        workflow.set_entry_point("initialize")

        return workflow.compile()

    async def process_application(
        self,
        application_id: int,
        applicant_data: Dict[str, Any],
        documents: List[Dict[str, Any]]
    ) -> ProcessingStatusSchema:
        """
        Main entry point for processing an application

        Args:
            application_id: ID of the application to process
            applicant_data: Applicant information
            documents: List of uploaded documents

        Returns:
            ProcessingStatus with current state and results
        """
        try:
            # Initialize the application state
            initial_state = ApplicationState(
                application_id=application_id,
                current_stage=ProcessingStage.INITIALIZATION,
                progress_percentage=0,
                applicant_data=applicant_data,
                documents=documents,
                extracted_data={},
                validation_results={},
                eligibility_results={},
                final_decision={},
                agent_responses=[],
                errors=[],
                metadata={"workflow_version": "1.0"},
                processing_start_time=datetime.now(),
                estimated_completion=None
            )

            # Execute the workflow
            final_state = await self._execute_workflow(initial_state)

            # Convert to ProcessingStatus schema
            return ProcessingStatusSchema(
                application_id=application_id,
                current_stage=final_state["current_stage"].value,
                progress_percentage=final_state["progress_percentage"],
                estimated_completion=final_state.get("estimated_completion"),
                agent_responses=final_state["agent_responses"]
            )

        except Exception as e:
            logger.error(f"Error processing application {application_id}: {str(e)}")
            error_response = AgentResponse(
                success=False,
                message=f"Orchestration failed: {str(e)}",
                data={"error_type": "orchestration_error"}
            )

            return ProcessingStatusSchema(
                application_id=application_id,
                current_stage="failed",
                progress_percentage=0,
                agent_responses=[error_response]
            )

    async def _execute_workflow(self, initial_state: ApplicationState) -> ApplicationState:
        """Execute the LangGraph workflow"""
        try:
            # Run the workflow
            result = await asyncio.to_thread(
                self.workflow.invoke,
                initial_state
            )
            return result

        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            initial_state["current_stage"] = ProcessingStage.FAILED
            initial_state["errors"].append(str(e))
            return initial_state

    async def _initialize_processing(self, state: ApplicationState) -> ApplicationState:
        """Initialize the processing workflow"""
        try:
            logger.info(f"Initializing processing for application {state['application_id']}")

            state["current_stage"] = ProcessingStage.INITIALIZATION
            state["progress_percentage"] = 5

            # Estimate completion time based on number of documents
            doc_count = len(state["documents"])
            estimated_minutes = 2 + (doc_count * 0.5)  # Base 2 minutes + 30 seconds per document
            state["estimated_completion"] = datetime.now().replace(
                microsecond=0
            ) + timedelta(minutes=estimated_minutes)

            # Create initialization response
            response = AgentResponse(
                success=True,
                message=f"Initialized processing for {doc_count} documents",
                data={
                    "stage": ProcessingStage.INITIALIZATION.value,
                    "document_count": doc_count,
                    "estimated_duration_minutes": estimated_minutes
                },
                processing_time_ms=100
            )

            state["agent_responses"].append(response)

            logger.info(f"Application {state['application_id']} initialized successfully")
            return state

        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}")
            state["errors"].append(f"Initialization error: {str(e)}")
            state["current_stage"] = ProcessingStage.FAILED
            return state

    async def _process_documents(self, state: ApplicationState) -> ApplicationState:
        """Process all uploaded documents"""
        try:
            logger.info(f"Processing documents for application {state['application_id']}")

            state["current_stage"] = ProcessingStage.DOCUMENT_PROCESSING
            state["progress_percentage"] = 20

            processed_documents = []
            processing_errors = []

            for doc in state["documents"]:
                try:
                    # Process document using document processor
                    result = await document_processor.process_document(
                        file_path=doc["file_path"],
                        document_type=doc["document_type"],
                        metadata=doc.get("metadata", {})
                    )

                    # Store embeddings for semantic search
                    await embedding_service.store_document_embeddings(
                        application_id=state["application_id"],
                        document_id=doc["id"],
                        content=result["raw_content"],
                        document_type=doc["document_type"],
                        extracted_data=result["extracted_data"]
                    )

                    processed_documents.append({
                        **doc,
                        "processing_result": result
                    })

                except Exception as e:
                    error_msg = f"Error processing document {doc.get('id', 'unknown')}: {str(e)}"
                    processing_errors.append(error_msg)
                    logger.error(error_msg)

            # Update state
            state["documents"] = processed_documents
            if processing_errors:
                state["errors"].extend(processing_errors)

            # Create response
            response = AgentResponse(
                success=len(processing_errors) == 0,
                message=f"Processed {len(processed_documents)} documents, {len(processing_errors)} errors",
                data={
                    "stage": ProcessingStage.DOCUMENT_PROCESSING.value,
                    "processed_count": len(processed_documents),
                    "error_count": len(processing_errors)
                },
                processing_time_ms=len(processed_documents) * 500
            )

            state["agent_responses"].append(response)

            logger.info(f"Document processing completed for application {state['application_id']}")
            return state

        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}")
            state["errors"].append(f"Document processing error: {str(e)}")
            state["current_stage"] = ProcessingStage.FAILED
            return state

    async def _extract_data(self, state: ApplicationState) -> ApplicationState:
        """Extract structured data from processed documents"""
        try:
            logger.info(f"Extracting data for application {state['application_id']}")

            state["current_stage"] = ProcessingStage.DATA_EXTRACTION
            state["progress_percentage"] = 40

            # Import here to avoid circular imports
            from .data_extraction import DataExtractionAgent

            extraction_agent = DataExtractionAgent()
            extraction_result = await extraction_agent.extract_application_data(
                state["applicant_data"],
                state["documents"]
            )

            state["extracted_data"] = extraction_result.data or {}

            response = AgentResponse(
                success=extraction_result.success,
                message=extraction_result.message,
                data=extraction_result.data,
                confidence_score=extraction_result.confidence_score,
                processing_time_ms=extraction_result.processing_time_ms
            )

            state["agent_responses"].append(response)

            if not extraction_result.success:
                state["errors"].append(f"Data extraction failed: {extraction_result.message}")

            logger.info(f"Data extraction completed for application {state['application_id']}")
            return state

        except Exception as e:
            logger.error(f"Data extraction failed: {str(e)}")
            state["errors"].append(f"Data extraction error: {str(e)}")
            state["current_stage"] = ProcessingStage.FAILED
            return state

    async def _validate_data(self, state: ApplicationState) -> ApplicationState:
        """Validate extracted data for consistency and completeness"""
        try:
            logger.info(f"Validating data for application {state['application_id']}")

            state["current_stage"] = ProcessingStage.VALIDATION
            state["progress_percentage"] = 60

            # Import here to avoid circular imports
            from .validation import ValidationAgent

            validation_agent = ValidationAgent()
            validation_result = await validation_agent.validate_application_data(
                state["applicant_data"],
                state["extracted_data"]
            )

            state["validation_results"] = validation_result.data or {}

            response = AgentResponse(
                success=validation_result.success,
                message=validation_result.message,
                data=validation_result.data,
                confidence_score=validation_result.confidence_score,
                processing_time_ms=validation_result.processing_time_ms
            )

            state["agent_responses"].append(response)

            if not validation_result.success:
                state["errors"].append(f"Validation failed: {validation_result.message}")

            logger.info(f"Data validation completed for application {state['application_id']}")
            return state

        except Exception as e:
            logger.error(f"Data validation failed: {str(e)}")
            state["errors"].append(f"Data validation error: {str(e)}")
            state["current_stage"] = ProcessingStage.FAILED
            return state

    async def _check_eligibility(self, state: ApplicationState) -> ApplicationState:
        """Check eligibility based on extracted and validated data"""
        try:
            logger.info(f"Checking eligibility for application {state['application_id']}")

            state["current_stage"] = ProcessingStage.ELIGIBILITY_CHECK
            state["progress_percentage"] = 80

            # Import here to avoid circular imports
            from .eligibility import EligibilityAgent

            eligibility_agent = EligibilityAgent()
            eligibility_result = await eligibility_agent.check_eligibility(
                state["applicant_data"],
                state["extracted_data"],
                state["validation_results"]
            )

            state["eligibility_results"] = eligibility_result.data or {}

            response = AgentResponse(
                success=eligibility_result.success,
                message=eligibility_result.message,
                data=eligibility_result.data,
                confidence_score=eligibility_result.confidence_score,
                processing_time_ms=eligibility_result.processing_time_ms
            )

            state["agent_responses"].append(response)

            if not eligibility_result.success:
                state["errors"].append(f"Eligibility check failed: {eligibility_result.message}")

            logger.info(f"Eligibility check completed for application {state['application_id']}")
            return state

        except Exception as e:
            logger.error(f"Eligibility check failed: {str(e)}")
            state["errors"].append(f"Eligibility check error: {str(e)}")
            state["current_stage"] = ProcessingStage.FAILED
            return state

    async def _make_decision(self, state: ApplicationState) -> ApplicationState:
        """Make final decision based on all collected data"""
        try:
            logger.info(f"Making decision for application {state['application_id']}")

            state["current_stage"] = ProcessingStage.DECISION_MAKING
            state["progress_percentage"] = 90

            # Import here to avoid circular imports
            from .decision import DecisionAgent

            decision_agent = DecisionAgent()
            decision_result = await decision_agent.make_decision(
                state["applicant_data"],
                state["extracted_data"],
                state["validation_results"],
                state["eligibility_results"]
            )

            state["final_decision"] = decision_result.data or {}

            response = AgentResponse(
                success=decision_result.success,
                message=decision_result.message,
                data=decision_result.data,
                confidence_score=decision_result.confidence_score,
                processing_time_ms=decision_result.processing_time_ms
            )

            state["agent_responses"].append(response)

            if not decision_result.success:
                state["errors"].append(f"Decision making failed: {decision_result.message}")

            logger.info(f"Decision making completed for application {state['application_id']}")
            return state

        except Exception as e:
            logger.error(f"Decision making failed: {str(e)}")
            state["errors"].append(f"Decision making error: {str(e)}")
            state["current_stage"] = ProcessingStage.FAILED
            return state

    async def _finalize_processing(self, state: ApplicationState) -> ApplicationState:
        """Finalize the processing workflow"""
        try:
            logger.info(f"Finalizing processing for application {state['application_id']}")

            state["current_stage"] = ProcessingStage.FINALIZATION
            state["progress_percentage"] = 95

            # Store application summary for future reference
            summary_text = self._generate_application_summary(state)
            await embedding_service.store_application_summary(
                application_id=state["application_id"],
                summary_text=summary_text,
                application_data={
                    "applicant_data": state["applicant_data"],
                    "final_decision": state["final_decision"],
                    "processing_summary": {
                        "total_documents": len(state["documents"]),
                        "processing_time": (datetime.now() - state["processing_start_time"]).total_seconds(),
                        "error_count": len(state["errors"])
                    }
                }
            )

            # Mark as completed
            state["current_stage"] = ProcessingStage.COMPLETED
            state["progress_percentage"] = 100

            response = AgentResponse(
                success=True,
                message="Application processing completed successfully",
                data={
                    "stage": ProcessingStage.COMPLETED.value,
                    "processing_duration_seconds": (datetime.now() - state["processing_start_time"]).total_seconds(),
                    "final_decision": state["final_decision"]
                }
            )

            state["agent_responses"].append(response)

            logger.info(f"Processing finalized for application {state['application_id']}")
            return state

        except Exception as e:
            logger.error(f"Finalization failed: {str(e)}")
            state["errors"].append(f"Finalization error: {str(e)}")
            state["current_stage"] = ProcessingStage.FAILED
            return state

    def _generate_application_summary(self, state: ApplicationState) -> str:
        """Generate a summary of the application for storage"""
        applicant = state["applicant_data"]
        decision = state["final_decision"]

        summary = f"""
        Application Summary for {applicant.get('first_name', '')} {applicant.get('last_name', '')}

        Emirates ID: {applicant.get('emirates_id', 'N/A')}
        Application Type: {applicant.get('application_type', 'N/A')}

        Documents Processed: {len(state['documents'])}
        Financial Support Decision: {decision.get('financial_support_decision', 'N/A')}
        Economic Enablement Programs: {', '.join(decision.get('economic_enablement_programs', []))}

        Processing Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()

        return summary

# Singleton instance
orchestrator = MasterOrchestrator()
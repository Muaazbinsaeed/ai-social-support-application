from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import asyncio
import logging
from datetime import datetime
import json

from backend.config import settings
from backend.models import (
    get_db, init_database,
    ApplicationCreate, ApplicationComplete,
    ApplicantCreate, DocumentCreate,
    AgentResponse, ProcessingStatus,
    ApplicationDB, ApplicantDB, DocumentDB,
    ApplicationStatus, DocumentType
)
from backend.agents import orchestrator
from backend.services import document_processor, ocr_service, embedding_service, llm_service

# Setup logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Social Support Application API",
    description="Multi-agent AI system for automated social support application processing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000"],  # Streamlit and potential frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Global variables for tracking processing status
processing_status_cache: Dict[int, Dict[str, Any]] = {}

@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    try:
        init_database()
        logger.info("Database initialized successfully")

        # Initialize embedding service collections
        await embedding_service._initialize_collections()
        logger.info("Embedding service initialized")

        logger.info("API server started successfully")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "AI Social Support Application API",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "api": "healthy",
        "database": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

# Application Endpoints

@app.post("/applications/submit", response_model=Dict[str, Any])
async def submit_application(
    background_tasks: BackgroundTasks,
    applicant_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Submit a new application with applicant data"""
    try:
        # Create applicant record
        applicant = ApplicantDB(**applicant_data)
        db.add(applicant)
        db.commit()
        db.refresh(applicant)

        # Create application record
        application_data = {
            "applicant_id": applicant.id,
            "application_type": applicant_data.get("application_type", "financial_support"),
            "urgency_level": applicant_data.get("urgency_level", "normal")
        }

        application = ApplicationDB(**application_data)
        db.add(application)
        db.commit()
        db.refresh(application)

        # Initialize processing status
        processing_status_cache[application.id] = {
            "application_id": application.id,
            "status": "initialized",
            "progress": 0,
            "documents_uploaded": 0,
            "ready_for_processing": False
        }

        logger.info(f"Application {application.id} submitted successfully")

        return {
            "application_id": application.id,
            "applicant_id": applicant.id,
            "status": "submitted",
            "message": "Application submitted successfully. Please upload required documents."
        }

    except Exception as e:
        logger.error(f"Application submission failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/{application_id}/documents/upload")
async def upload_documents(
    application_id: int,
    files: List[UploadFile] = File(...),
    document_types: List[str] = None,
    db: Session = Depends(get_db)
):
    """Upload documents for an application"""
    try:
        # Verify application exists
        application = db.query(ApplicationDB).filter(ApplicationDB.id == application_id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        uploaded_docs = []

        for i, file in enumerate(files):
            # Determine document type
            doc_type = document_types[i] if document_types and i < len(document_types) else "general"

            # Validate file
            if file.size > settings.max_file_size:
                raise HTTPException(status_code=413, detail=f"File {file.filename} too large")

            # Save file
            file_content = await file.read()
            file_path = await document_processor.save_uploaded_file(
                file_content, file.filename, application_id
            )

            # Create document record
            document_data = {
                "application_id": application_id,
                "document_type": doc_type,
                "file_name": file.filename,
                "file_path": file_path,
                "file_size": file.size,
                "mime_type": file.content_type
            }

            document = DocumentDB(**document_data)
            db.add(document)
            db.commit()
            db.refresh(document)

            uploaded_docs.append({
                "document_id": document.id,
                "filename": file.filename,
                "type": doc_type,
                "size": file.size
            })

        # Update processing status
        if application_id in processing_status_cache:
            processing_status_cache[application_id]["documents_uploaded"] = len(uploaded_docs)
            processing_status_cache[application_id]["ready_for_processing"] = len(uploaded_docs) > 0

        logger.info(f"Uploaded {len(uploaded_docs)} documents for application {application_id}")

        return {
            "application_id": application_id,
            "uploaded_documents": uploaded_docs,
            "total_documents": len(uploaded_docs),
            "ready_for_processing": len(uploaded_docs) > 0
        }

    except Exception as e:
        logger.error(f"Document upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/{application_id}/process")
async def process_application(
    application_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start processing an application"""
    try:
        # Verify application exists
        application = db.query(ApplicationDB).filter(ApplicationDB.id == application_id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        # Get applicant data
        applicant = db.query(ApplicantDB).filter(ApplicantDB.id == application.applicant_id).first()
        if not applicant:
            raise HTTPException(status_code=404, detail="Applicant not found")

        # Get documents
        documents = db.query(DocumentDB).filter(DocumentDB.application_id == application_id).all()
        if not documents:
            raise HTTPException(status_code=400, detail="No documents uploaded")

        # Prepare data for orchestrator
        applicant_data = {
            "emirates_id": applicant.emirates_id,
            "first_name": applicant.first_name,
            "last_name": applicant.last_name,
            "date_of_birth": applicant.date_of_birth.isoformat() if applicant.date_of_birth else None,
            "phone": applicant.phone,
            "email": applicant.email,
            "address": applicant.address,
            "application_type": application.application_type
        }

        documents_data = [
            {
                "id": doc.id,
                "document_type": doc.document_type,
                "file_path": doc.file_path,
                "file_name": doc.file_name,
                "mime_type": doc.mime_type
            }
            for doc in documents
        ]

        # Start background processing
        background_tasks.add_task(
            process_application_background,
            application_id,
            applicant_data,
            documents_data,
            db
        )

        # Update application status
        application.status = ApplicationStatus.PROCESSING
        db.commit()

        # Update processing status
        processing_status_cache[application_id] = {
            "application_id": application_id,
            "status": "processing",
            "progress": 0,
            "current_stage": "initialization",
            "started_at": datetime.now().isoformat()
        }

        logger.info(f"Started processing application {application_id}")

        return {
            "application_id": application_id,
            "status": "processing_started",
            "message": "Application processing started. Use /status endpoint to track progress."
        }

    except Exception as e:
        logger.error(f"Failed to start processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_application_background(
    application_id: int,
    applicant_data: Dict[str, Any],
    documents_data: List[Dict[str, Any]],
    db: Session
):
    """Background task to process application using orchestrator"""
    try:
        logger.info(f"Background processing started for application {application_id}")

        # Process application using orchestrator
        result = await orchestrator.process_application(
            application_id,
            applicant_data,
            documents_data
        )

        # Update processing status
        processing_status_cache[application_id] = {
            "application_id": application_id,
            "status": "completed" if result.current_stage == "completed" else "failed",
            "progress": result.progress_percentage,
            "current_stage": result.current_stage,
            "completed_at": datetime.now().isoformat(),
            "result": result.dict()
        }

        # Update application status in database
        application = db.query(ApplicationDB).filter(ApplicationDB.id == application_id).first()
        if application:
            if result.current_stage == "completed":
                application.status = ApplicationStatus.APPROVED if result.agent_responses[-1].success else ApplicationStatus.DECLINED
            else:
                application.status = ApplicationStatus.REQUIRES_REVIEW

            application.processed_at = datetime.now()
            db.commit()

        logger.info(f"Background processing completed for application {application_id}")

    except Exception as e:
        logger.error(f"Background processing failed for application {application_id}: {str(e)}")

        # Update status to failed
        processing_status_cache[application_id] = {
            "application_id": application_id,
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        }

@app.get("/applications/{application_id}/status")
async def get_application_status(application_id: int):
    """Get current processing status of an application"""
    try:
        if application_id not in processing_status_cache:
            raise HTTPException(status_code=404, detail="Application status not found")

        status = processing_status_cache[application_id]
        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/applications/{application_id}/details", response_model=Dict[str, Any])
async def get_application_details(application_id: int, db: Session = Depends(get_db)):
    """Get detailed application information"""
    try:
        # Get application with all related data
        application = db.query(ApplicationDB).filter(ApplicationDB.id == application_id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        # Get applicant
        applicant = db.query(ApplicantDB).filter(ApplicantDB.id == application.applicant_id).first()

        # Get documents
        documents = db.query(DocumentDB).filter(DocumentDB.application_id == application_id).all()

        # Get processing status
        processing_status = processing_status_cache.get(application_id, {})

        return {
            "application": {
                "id": application.id,
                "type": application.application_type,
                "status": application.status,
                "submitted_at": application.submitted_at.isoformat(),
                "processed_at": application.processed_at.isoformat() if application.processed_at else None
            },
            "applicant": {
                "id": applicant.id,
                "emirates_id": applicant.emirates_id,
                "name": f"{applicant.first_name} {applicant.last_name}",
                "email": applicant.email,
                "phone": applicant.phone
            } if applicant else None,
            "documents": [
                {
                    "id": doc.id,
                    "type": doc.document_type,
                    "filename": doc.file_name,
                    "size": doc.file_size,
                    "uploaded_at": doc.uploaded_at.isoformat()
                }
                for doc in documents
            ],
            "processing_status": processing_status
        }

    except Exception as e:
        logger.error(f"Failed to get application details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Document Processing Endpoints

@app.post("/documents/process")
async def process_document_endpoint(
    file: UploadFile = File(...),
    document_type: str = "general"
):
    """Process a single document (for testing)"""
    try:
        # Save temporary file
        file_content = await file.read()
        temp_path = f"/tmp/{file.filename}"

        with open(temp_path, "wb") as f:
            f.write(file_content)

        # Process document
        result = await document_processor.process_document(
            temp_path,
            DocumentType(document_type)
        )

        return result

    except Exception as e:
        logger.error(f"Document processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# OCR Endpoints

@app.post("/ocr/extract")
async def extract_text_ocr(
    file: UploadFile = File(...),
    language: str = "bilingual",
    document_type: str = "general"
):
    """Extract text from image using OCR"""
    try:
        # Save temporary file
        file_content = await file.read()
        temp_path = f"/tmp/{file.filename}"

        with open(temp_path, "wb") as f:
            f.write(file_content)

        # Extract text using OCR
        if document_type == "emirates_id":
            result = await ocr_service.extract_emirates_id_data(temp_path)
        elif document_type == "handwritten":
            result = await ocr_service.extract_handwritten_form_data(temp_path)
        else:
            result = await ocr_service.extract_text_from_image(temp_path, language)

        return result

    except Exception as e:
        logger.error(f"OCR extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Search and Analytics Endpoints

@app.get("/search/similar-applications")
async def search_similar_applications(
    query: str,
    limit: int = 5
):
    """Search for similar applications using semantic search"""
    try:
        results = await embedding_service.search_similar_applications(query, limit)
        return {"query": query, "results": results}

    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/stats")
async def get_analytics_stats():
    """Get system analytics and statistics"""
    try:
        # Get embedding service stats
        embedding_stats = await embedding_service.get_collection_stats()

        # Get processing status stats
        status_counts = {}
        for status_data in processing_status_cache.values():
            status = status_data.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_applications": len(processing_status_cache),
            "status_distribution": status_counts,
            "embedding_collections": embedding_stats,
            "system_health": "healthy"
        }

    except Exception as e:
        logger.error(f"Analytics failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Chat Endpoints

@app.post("/chat/message")
async def chat_message(
    message: str,
    application_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Send a message to the AI chatbot and get an intelligent response"""
    try:
        # Build context for the LLM
        context = {}

        if application_id:
            context["application_id"] = application_id

            # Get application status if available
            if application_id in processing_status_cache:
                status_data = processing_status_cache[application_id]
                context["processing_status"] = status_data.get("status")
                context["has_documents"] = status_data.get("documents_uploaded", 0) > 0

            # Check if application exists in database
            application = db.query(ApplicationDB).filter(ApplicationDB.id == application_id).first()
            if application:
                context["application_type"] = application.application_type
                context["application_status"] = application.status

        # Get LLM response
        response = await llm_service.get_chat_response(message, context)

        return {
            "message": message,
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "context_used": bool(context)
        }

    except Exception as e:
        logger.error(f"Chat message failed: {str(e)}")
        # Return fallback response instead of error
        return {
            "message": message,
            "response": "I'm here to help with your social support application. Could you please rephrase your question? I can assist with applications, documents, eligibility, and status updates.",
            "timestamp": datetime.now().isoformat(),
            "context_used": False,
            "fallback": True
        }

@app.get("/chat/health")
async def chat_health():
    """Check if the LLM service is available"""
    try:
        is_healthy = await llm_service.check_health()
        return {
            "llm_available": is_healthy,
            "service": "Ollama" if is_healthy else "Fallback",
            "model": settings.ollama_model,
            "status": "healthy" if is_healthy else "degraded"
        }
    except Exception as e:
        logger.error(f"Chat health check failed: {str(e)}")
        return {
            "llm_available": False,
            "service": "Fallback",
            "model": "rule-based",
            "status": "degraded",
            "error": str(e)
        }

# Agent Testing Endpoints (for development)

@app.post("/agents/test/extraction")
async def test_extraction_agent(
    applicant_data: Dict[str, Any],
    documents: List[Dict[str, Any]]
):
    """Test data extraction agent directly"""
    try:
        from backend.agents.data_extraction import DataExtractionAgent

        agent = DataExtractionAgent()
        result = await agent.extract_application_data(applicant_data, documents)

        return result.dict()

    except Exception as e:
        logger.error(f"Extraction agent test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents/test/validation")
async def test_validation_agent(
    applicant_data: Dict[str, Any],
    extracted_data: Dict[str, Any]
):
    """Test validation agent directly"""
    try:
        from backend.agents.validation import ValidationAgent

        agent = ValidationAgent()
        result = await agent.validate_application_data(applicant_data, extracted_data)

        return result.dict()

    except Exception as e:
        logger.error(f"Validation agent test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
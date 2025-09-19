from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import uuid
import json
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Social Support Simple API",
    description="Basic API for testing application form submission",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data persistence
DATA_DIR = "data/temp"
APPLICATIONS_FILE = os.path.join(DATA_DIR, "applications.json")
PROCESSING_FILE = os.path.join(DATA_DIR, "processing.json")

def ensure_data_dir():
    """Create data directory if it doesn't exist"""
    os.makedirs(DATA_DIR, exist_ok=True)

def load_data():
    """Load data from files"""
    ensure_data_dir()

    applications = {}
    processing = {}
    counter = 1

    try:
        if os.path.exists(APPLICATIONS_FILE):
            with open(APPLICATIONS_FILE, 'r') as f:
                data = json.load(f)
                applications = data.get('applications', {})
                # Convert string keys back to int
                applications = {int(k): v for k, v in applications.items()}
                counter = data.get('counter', 1)
    except Exception as e:
        logger.warning(f"Failed to load applications: {e}")

    try:
        if os.path.exists(PROCESSING_FILE):
            with open(PROCESSING_FILE, 'r') as f:
                processing = json.load(f)
                # Convert string keys back to int
                processing = {int(k): v for k, v in processing.items()}
    except Exception as e:
        logger.warning(f"Failed to load processing status: {e}")

    return applications, processing, counter

def save_data():
    """Save data to files"""
    ensure_data_dir()

    try:
        with open(APPLICATIONS_FILE, 'w') as f:
            json.dump({
                'applications': applications_db,
                'counter': application_counter
            }, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save applications: {e}")

    try:
        with open(PROCESSING_FILE, 'w') as f:
            json.dump(processing_status_cache, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save processing status: {e}")

# Load data on startup
applications_db, processing_status_cache, application_counter = load_data()
logger.info(f"Loaded {len(applications_db)} applications, counter at {application_counter}")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "AI Social Support Simple API",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "api": "healthy",
        "database": "memory-based",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.1"
    }

@app.post("/applications/submit")
async def submit_application(applicant_data: Dict[str, Any]):
    """Submit a new application with applicant data"""
    global application_counter

    try:
        # Create application record
        application_id = application_counter
        application_counter += 1

        # Store application data
        applications_db[application_id] = {
            "id": application_id,
            "applicant_data": applicant_data,
            "submitted_at": datetime.now().isoformat(),
            "status": "submitted",
            "documents": []
        }

        # Initialize processing status
        processing_status_cache[application_id] = {
            "application_id": application_id,
            "status": "initialized",
            "progress": 0,
            "documents_uploaded": 0,
            "ready_for_processing": False
        }

        logger.info(f"Application {application_id} submitted successfully")

        # Save data to persistence
        save_data()

        return {
            "application_id": application_id,
            "status": "submitted",
            "message": "Application submitted successfully. Please upload required documents."
        }

    except Exception as e:
        logger.error(f"Application submission failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/{application_id}/documents/upload")
async def upload_documents(
    application_id: int,
    files_info: List[Dict[str, Any]]  # Simplified - just file info, not actual files
):
    """Simulate document upload"""
    try:
        # Verify application exists
        if application_id not in applications_db:
            raise HTTPException(status_code=404, detail="Application not found")

        # Simulate storing documents
        application = applications_db[application_id]

        uploaded_docs = []
        for i, file_info in enumerate(files_info):
            doc_data = {
                "document_id": f"{application_id}_{i+1}",
                "filename": file_info.get("filename", f"document_{i+1}"),
                "type": file_info.get("type", "general"),
                "size": file_info.get("size", 1024),
                "uploaded_at": datetime.now().isoformat()
            }
            application["documents"].append(doc_data)
            uploaded_docs.append(doc_data)

        # Update processing status
        processing_status_cache[application_id]["documents_uploaded"] = len(application["documents"])
        processing_status_cache[application_id]["ready_for_processing"] = len(application["documents"]) > 0

        logger.info(f"Uploaded {len(uploaded_docs)} documents for application {application_id}")

        # Save data to persistence
        save_data()

        return {
            "application_id": application_id,
            "uploaded_documents": uploaded_docs,
            "total_documents": len(application["documents"]),
            "ready_for_processing": len(application["documents"]) > 0
        }

    except Exception as e:
        logger.error(f"Document upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/{application_id}/process")
async def process_application(application_id: int):
    """Simulate application processing"""
    try:
        # Verify application exists
        if application_id not in applications_db:
            raise HTTPException(status_code=404, detail="Application not found")

        application = applications_db[application_id]

        if not application["documents"]:
            raise HTTPException(status_code=400, detail="No documents uploaded")

        # Simulate processing stages
        processing_status_cache[application_id] = {
            "application_id": application_id,
            "status": "processing",
            "progress": 25,
            "current_stage": "data_extraction",
            "started_at": datetime.now().isoformat()
        }

        # Simulate quick processing completion
        import asyncio
        await asyncio.sleep(2)  # Simulate processing time

        # Simulate completion
        processing_status_cache[application_id] = {
            "application_id": application_id,
            "status": "completed",
            "progress": 100,
            "current_stage": "completed",
            "completed_at": datetime.now().isoformat(),
            "result": {
                "decision": "approved",
                "support_amount": 2500,
                "message": "Application approved for financial support",
                "agent_responses": [
                    {
                        "agent": "data_extraction",
                        "success": True,
                        "message": "Successfully extracted applicant data"
                    },
                    {
                        "agent": "validation",
                        "success": True,
                        "message": "Data validation completed successfully"
                    },
                    {
                        "agent": "eligibility",
                        "success": True,
                        "message": "Applicant meets eligibility criteria"
                    },
                    {
                        "agent": "decision",
                        "success": True,
                        "message": "Approved for AED 2,500 monthly support"
                    }
                ]
            }
        }

        applications_db[application_id]["status"] = "approved"
        applications_db[application_id]["processed_at"] = datetime.now().isoformat()

        logger.info(f"Processing completed for application {application_id}")

        return {
            "application_id": application_id,
            "status": "processing_started",
            "message": "Application processing completed successfully."
        }

    except Exception as e:
        logger.error(f"Failed to process application: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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

@app.get("/applications/{application_id}/details")
async def get_application_details(application_id: int):
    """Get detailed application information"""
    try:
        # Get application
        if application_id not in applications_db:
            raise HTTPException(status_code=404, detail="Application not found")

        application = applications_db[application_id]
        applicant_data = application["applicant_data"]

        # Get processing status
        processing_status = processing_status_cache.get(application_id, {})

        return {
            "application": {
                "id": application["id"],
                "type": applicant_data.get("application_type", "financial_support"),
                "status": application["status"],
                "submitted_at": application["submitted_at"],
                "processed_at": application.get("processed_at")
            },
            "applicant": {
                "id": application_id,
                "emirates_id": applicant_data.get("emirates_id"),
                "name": f"{applicant_data.get('first_name', '')} {applicant_data.get('last_name', '')}",
                "email": applicant_data.get("email"),
                "phone": applicant_data.get("phone")
            },
            "documents": [
                {
                    "id": doc["document_id"],
                    "type": doc["type"],
                    "filename": doc["filename"],
                    "size": doc["size"],
                    "uploaded_at": doc["uploaded_at"]
                }
                for doc in application["documents"]
            ],
            "processing_status": processing_status
        }

    except Exception as e:
        logger.error(f"Failed to get application details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/stats")
async def get_analytics_stats():
    """Get system analytics and statistics"""
    try:
        # Get processing status stats
        status_counts = {}
        for status_data in processing_status_cache.values():
            status = status_data.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_applications": len(applications_db),
            "status_distribution": status_counts,
            "system_health": "healthy"
        }

    except Exception as e:
        logger.error(f"Analytics failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.simple_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
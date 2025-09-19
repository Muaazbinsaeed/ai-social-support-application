from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import uuid
import json
import os
import shutil

# Import authentication utilities
from backend.utils.auth import verify_token
from backend.models.user_database import (
    get_db_context, create_user_application, create_user_document,
    get_user_by_id, get_user_applications, get_user_documents
)

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

# Security
security = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[Dict[str, Any]]:
    """Get current authenticated user (optional for backward compatibility)"""
    if not credentials:
        return None

    try:
        token = credentials.credentials
        token_data = verify_token(token)
        return token_data
    except Exception:
        return None

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
async def submit_application(
    applicant_data: Dict[str, Any],
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Submit a new application with applicant data"""
    global application_counter

    try:
        if current_user:
            # Authenticated user - save to database
            with get_db_context() as db:
                application_data = {
                    "application_type": applicant_data.get("application_type", "financial_support"),
                    "urgency_level": applicant_data.get("urgency_level", "normal"),
                    "status": "submitted",
                    "applicant_data": json.dumps(applicant_data)
                }

                application = create_user_application(db, current_user["user_id"], application_data)

                # Also create processing status in cache for compatibility
                processing_status_cache[application.id] = {
                    "application_id": application.id,
                    "status": "initialized",
                    "progress": 0,
                    "documents_uploaded": 0,
                    "ready_for_processing": False,
                    "user_id": current_user["user_id"]
                }

                logger.info(f"Authenticated application {application.id} submitted for user {current_user['user_id']}")

                return {
                    "application_id": application.id,
                    "status": "submitted",
                    "message": "Application submitted successfully. Please upload required documents.",
                    "authenticated": True
                }
        else:
            # Anonymous user - use legacy JSON storage
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

            logger.info(f"Anonymous application {application_id} submitted")

            # Save data to persistence
            save_data()

            return {
                "application_id": application_id,
                "status": "submitted",
                "message": "Application submitted successfully. Please upload required documents.",
                "authenticated": False
            }

    except Exception as e:
        logger.error(f"Application submission failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/applications/{application_id}/update")
async def update_application(
    application_id: int,
    applicant_data: Dict[str, Any],
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Update an existing application"""
    try:
        logger.info(f"Updating application {application_id} with data: {applicant_data}")
        
        # Check if this is an authenticated user's application
        if current_user:
            # Authenticated user - update in database
            with get_db_context() as db:
                # Get user applications
                user_applications = get_user_applications(db, current_user["user_id"])
                application = None
                for app in user_applications:
                    if app.id == application_id:
                        application = app
                        break
                
                if not application:
                    raise HTTPException(status_code=404, detail=f"Application {application_id} not found for authenticated user {current_user['user_id']}")
                
                # Update application data
                application.application_type = applicant_data.get("application_type", application.application_type)
                application.applicant_data = json.dumps(applicant_data)
                
                # Save to database
                db.commit()
                
                # Also update processing cache for compatibility
                if application_id in processing_status_cache:
                    processing_status_cache[application_id]["last_updated"] = datetime.now().isoformat()
                
                logger.info(f"Updated authenticated application {application_id} for user {current_user['user_id']}")
                
                return {
                    "application_id": application_id,
                    "status": "updated",
                    "message": "Application updated successfully.",
                    "authenticated": True
                }
        else:
            # Anonymous user - update in JSON storage
            if application_id not in applications_db:
                raise HTTPException(status_code=404, detail="Application not found")
            
            # Update application data
            applications_db[application_id]["applicant_data"] = applicant_data
            applications_db[application_id]["last_updated"] = datetime.now().isoformat()
            
            # Save data to persistence
            save_data()
            
            logger.info(f"Updated anonymous application {application_id}")
            
            return {
                "application_id": application_id,
                "status": "updated",
                "message": "Application updated successfully.",
                "authenticated": False
            }
    
    except Exception as e:
        logger.error(f"Application update failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/{application_id}/documents/upload")
async def upload_documents(
    application_id: int,
    files_info: List[Dict[str, Any]],  # Simplified - just file info, not actual files
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Simulate document upload"""
    try:
        uploaded_docs = []

        # Debug logging to understand the issue
        logger.info(f"Document upload attempt - application_id: {application_id}, current_user: {current_user is not None}")
        if current_user:
            logger.info(f"Processing status cache has application: {application_id in processing_status_cache}")
            if application_id in processing_status_cache:
                logger.info(f"User ID in cache: {processing_status_cache[application_id].get('user_id')}")

        if current_user and application_id in processing_status_cache and processing_status_cache[application_id].get("user_id"):
            # Authenticated user - save to database
            with get_db_context() as db:
                for i, file_info in enumerate(files_info):
                    # Create user directory if not exists
                    user_dir = f"data/users/{current_user['user_id']}/documents"
                    os.makedirs(user_dir, exist_ok=True)

                    document_data = {
                        "application_id": application_id,
                        "document_type": file_info.get("type", "general"),
                        "filename": f"doc_{application_id}_{i+1}_{file_info.get('filename', 'document')}",
                        "original_filename": file_info.get("filename", f"document_{i+1}"),
                        "file_path": os.path.join(user_dir, f"doc_{application_id}_{i+1}_{file_info.get('filename', 'document')}"),
                        "file_size": file_info.get("size", 1024),
                        "content_type": file_info.get("content_type", "application/octet-stream")
                    }

                    document = create_user_document(db, current_user["user_id"], document_data)

                    doc_data = {
                        "document_id": document.id,
                        "filename": document.filename,
                        "type": document.document_type,
                        "size": document.file_size,
                        "uploaded_at": document.upload_date.isoformat()
                    }
                    uploaded_docs.append(doc_data)

                # Update processing status
                processing_status_cache[application_id]["documents_uploaded"] = len(uploaded_docs)
                processing_status_cache[application_id]["ready_for_processing"] = len(uploaded_docs) > 0

                logger.info(f"Uploaded {len(uploaded_docs)} documents for authenticated application {application_id}")

        elif current_user:
            # Authenticated user but application not found in cache
            # Check if the application exists in database for this user
            with get_db_context() as db:
                # Use get_user_applications and filter by application_id
                user_applications = get_user_applications(db, current_user["user_id"])
                application = None
                for app in user_applications:
                    if app.id == application_id:
                        application = app
                        break

                if not application:
                    raise HTTPException(status_code=404, detail=f"Application {application_id} not found for authenticated user {current_user['user_id']}")

                # Add missing entry to processing cache
                processing_status_cache[application_id] = {
                    "application_id": application_id,
                    "status": "initialized",
                    "progress": 0,
                    "documents_uploaded": 0,
                    "ready_for_processing": False,
                    "user_id": current_user["user_id"]
                }

                logger.info(f"Restored processing cache for application {application_id}")

                # Now process as authenticated user
                for i, file_info in enumerate(files_info):
                    # Create user directory if not exists
                    user_dir = f"data/users/{current_user['user_id']}/documents"
                    os.makedirs(user_dir, exist_ok=True)

                    document_data = {
                        "application_id": application_id,
                        "document_type": file_info.get("type", "general"),
                        "filename": f"doc_{application_id}_{i+1}_{file_info.get('filename', 'document')}",
                        "original_filename": file_info.get("filename", f"document_{i+1}"),
                        "file_path": os.path.join(user_dir, f"doc_{application_id}_{i+1}_{file_info.get('filename', 'document')}"),
                        "file_size": file_info.get("size", 1024),
                        "content_type": file_info.get("content_type", "application/octet-stream")
                    }

                    document = create_user_document(db, current_user["user_id"], document_data)

                    doc_data = {
                        "document_id": document.id,
                        "filename": document.filename,
                        "type": document.document_type,
                        "size": document.file_size,
                        "uploaded_at": document.upload_date.isoformat()
                    }
                    uploaded_docs.append(doc_data)

                # Update processing status
                processing_status_cache[application_id]["documents_uploaded"] = len(uploaded_docs)
                processing_status_cache[application_id]["ready_for_processing"] = len(uploaded_docs) > 0

                logger.info(f"Uploaded {len(uploaded_docs)} documents for recovered authenticated application {application_id}")

        else:
            # Anonymous user - check JSON storage
            if application_id not in applications_db:
                raise HTTPException(status_code=404, detail="Application not found")

            application = applications_db[application_id]

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

            logger.info(f"Uploaded {len(uploaded_docs)} documents for anonymous application {application_id}")

            # Save data to persistence
            save_data()

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
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Simulate application processing"""
    logger.info(f"Processing request for application {application_id}, user: {current_user['user_id'] if current_user else 'anonymous'}")
    try:
        # Check if this is an authenticated user's application
        if current_user and application_id in processing_status_cache and processing_status_cache[application_id].get("user_id"):
            # Authenticated user - check if they have documents uploaded
            if processing_status_cache[application_id].get("documents_uploaded", 0) == 0:
                raise HTTPException(status_code=400, detail="No documents uploaded")
        elif current_user:
            # Authenticated user but application not in cache - check database
            try:
                with get_db_context() as db:
                    user_applications = get_user_applications(db, current_user["user_id"])
                    application = None
                    for app in user_applications:
                        if app.id == application_id:
                            application = app
                            break

                    if not application:
                        error_msg = f"Application {application_id} not found for authenticated user {current_user['user_id']}"
                        logger.warning(error_msg)
                        raise HTTPException(status_code=404, detail=error_msg)

                    # Check if application has documents
                    user_documents = get_user_documents(db, current_user["user_id"])
                    app_documents = [doc for doc in user_documents if doc.application_id == application_id]

                    if not app_documents:
                        raise HTTPException(status_code=400, detail="No documents uploaded")

                    # Restore processing cache entry if missing or incomplete
                    if application_id not in processing_status_cache or not processing_status_cache[application_id].get("user_id"):
                        processing_status_cache[application_id] = {
                            "application_id": application_id,
                            "status": "initialized",
                            "progress": 0,
                            "documents_uploaded": len(app_documents),
                            "ready_for_processing": True,
                            "user_id": current_user["user_id"]
                        }
                        logger.info(f"Restored processing cache for application {application_id} with user {current_user['user_id']}")
            except HTTPException:
                # Re-raise HTTP exceptions
                raise
            except Exception as db_error:
                logger.error(f"Database error for application {application_id}: {str(db_error)}")
                raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        else:
            # Anonymous user - check JSON storage
            if application_id not in applications_db:
                raise HTTPException(status_code=404, detail="Application not found")

            application = applications_db[application_id]

            if not application["documents"]:
                raise HTTPException(status_code=400, detail="No documents uploaded")

        # Simulate processing stages
        try:
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
            logger.info(f"Processing simulation completed for application {application_id}")
        except Exception as processing_error:
            logger.error(f"Processing simulation failed for application {application_id}: {str(processing_error)}")
            raise

        # Update anonymous user database if application exists there
        if application_id in applications_db:
            try:
                applications_db[application_id]["status"] = "approved"
                applications_db[application_id]["processed_at"] = datetime.now().isoformat()
                save_data()  # Save for anonymous users
                logger.info(f"Updated anonymous application {application_id} status to approved")
            except Exception as save_error:
                logger.error(f"Failed to save anonymous application status: {str(save_error)}")
                # Don't fail the entire processing for this

        # For authenticated users, update the database
        if current_user:
            try:
                with get_db_context() as db:
                    user_applications = get_user_applications(db, current_user["user_id"])
                    for app in user_applications:
                        if app.id == application_id:
                            app.status = "approved"
                            app.processed_at = datetime.now()
                            db.commit()
                            break
            except Exception as db_error:
                logger.warning(f"Failed to update database status for application {application_id}: {str(db_error)}")

        logger.info(f"Processing completed for application {application_id}")

        return {
            "application_id": application_id,
            "status": "processing_started",
            "message": "Application processing completed successfully."
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to process application {application_id}: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception args: {e.args}")

        # Handle specific error types
        if isinstance(e, KeyError):
            error_msg = f"Application {application_id} data not found in storage"
        elif isinstance(e, AttributeError):
            error_msg = f"Database access error for application {application_id}: {str(e)}"
        else:
            error_msg = f"Internal error processing application {application_id}: {str(e)}"

        raise HTTPException(status_code=500, detail=error_msg)

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
async def get_application_details(
    application_id: int,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Get detailed application information"""
    try:
        # Check if this is an authenticated user's application
        if current_user:
            # Check database first for authenticated users
            with get_db_context() as db:
                user_applications = get_user_applications(db, current_user["user_id"])
                application = None
                for app in user_applications:
                    if app.id == application_id:
                        application = app
                        break

                if application:
                    # Get user documents
                    user_documents = get_user_documents(db, current_user["user_id"])
                    app_documents = [doc for doc in user_documents if doc.application_id == application_id]

                    # Parse applicant data
                    try:
                        applicant_data = json.loads(application.applicant_data) if isinstance(application.applicant_data, str) else application.applicant_data
                    except:
                        applicant_data = {}

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
                            "id": application.id,
                            "emirates_id": applicant_data.get("emirates_id"),
                            "name": f"{applicant_data.get('first_name', '')} {applicant_data.get('last_name', '')}",
                            "email": applicant_data.get("email"),
                            "phone": applicant_data.get("phone")
                        },
                        "documents": [
                            {
                                "id": doc.id,
                                "type": doc.document_type,
                                "filename": doc.filename,
                                "size": doc.file_size,
                                "uploaded_at": doc.upload_date.isoformat()
                            }
                            for doc in app_documents
                        ],
                        "processing_status": processing_status
                    }

        # Fall back to anonymous application storage
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

    except HTTPException:
        raise
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
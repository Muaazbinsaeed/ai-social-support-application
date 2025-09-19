"""
Authentication API server for user registration, login, and profile management
"""

from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
import logging
import os
import shutil
from datetime import datetime, timedelta
import json

# Import our models and utilities
from backend.models.user_models import (
    User, UserProfile, UserApplication, UserDocument,
    UserCreate, UserLogin, UserResponse, UserProfileUpdate,
    UserProfileResponse, Token, TokenData
)
from backend.models.user_database import (
    get_db_context, get_user_by_email, get_user_by_id, create_user,
    update_user_profile, get_user_applications, get_user_documents,
    create_user_application, create_user_document, init_database
)
from backend.utils.auth import (
    hash_password, verify_password, create_access_token, verify_token,
    validate_password_strength, get_password_requirements, get_token_expiry
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Social Support Authentication API",
    description="User authentication and profile management API",
    version="1.0.0",
    docs_url="/auth/docs",
    redoc_url="/auth/redoc"
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
security = HTTPBearer()

# Initialize database
init_database()

# User data directories
USER_DATA_DIR = "data/users"
USER_DOCUMENTS_DIR = "data/users/{user_id}/documents"
USER_PROFILE_PICS_DIR = "data/users/{user_id}/profile"

def ensure_user_directories(user_id: int):
    """Create user-specific directories"""
    user_dir = os.path.join(USER_DATA_DIR, str(user_id))
    docs_dir = os.path.join(user_dir, "documents")
    profile_dir = os.path.join(user_dir, "profile")

    os.makedirs(docs_dir, exist_ok=True)
    os.makedirs(profile_dir, exist_ok=True)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current authenticated user"""
    token = credentials.credentials
    token_data = verify_token(token)
    return token_data

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "AI Social Support Authentication API",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/auth/health")
async def health_check():
    """Detailed health check"""
    return {
        "api": "healthy",
        "database": "sqlite",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.post("/auth/register", response_model=Token)
async def register_user(user_data: UserCreate):
    """Register a new user"""
    try:
        # Validate password strength
        if not validate_password_strength(user_data.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_password_requirements()
            )

        with get_db_context() as db:
            # Check if user already exists
            existing_user = get_user_by_email(db, user_data.email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )

            # Create user
            hashed_password = hash_password(user_data.password)
            user_dict = {
                "email": user_data.email,
                "password_hash": hashed_password,
                "full_name": user_data.full_name,
                "is_active": True,
                "is_verified": True  # Auto-verify for MVP
            }

            user = create_user(db, user_dict)

            # Update profile with phone if provided
            if user_data.phone:
                update_user_profile(db, user.id, {"phone": user_data.phone})

            # Create user directories
            ensure_user_directories(user.id)

            # Create access token
            access_token = create_access_token(
                data={"sub": user.email, "user_id": user.id}
            )

            user_response = UserResponse.from_orm(user)

            logger.info(f"User registered successfully: {user.email}")

            return Token(
                access_token=access_token,
                token_type="bearer",
                expires_in=get_token_expiry(),
                user=user_response
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@app.post("/auth/login", response_model=Token)
async def login_user(user_credentials: UserLogin):
    """Login user"""
    try:
        with get_db_context() as db:
            # Get user by email
            user = get_user_by_email(db, user_credentials.email)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )

            # Verify password
            if not verify_password(user_credentials.password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )

            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is disabled"
                )

            # Create access token
            access_token = create_access_token(
                data={"sub": user.email, "user_id": user.id}
            )

            user_response = UserResponse.from_orm(user)

            logger.info(f"User logged in: {user.email}")

            return Token(
                access_token=access_token,
                token_type="bearer",
                expires_in=get_token_expiry(),
                user=user_response
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@app.post("/auth/verify")
async def verify_token_endpoint(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Verify JWT token"""
    try:
        with get_db_context() as db:
            user = get_user_by_id(db, current_user["user_id"])
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )

            user_response = UserResponse.from_orm(user)
            return {"valid": True, "user": user_response}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed"
        )

@app.get("/users/profile", response_model=UserProfileResponse)
async def get_user_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user profile"""
    try:
        with get_db_context() as db:
            user = get_user_by_id(db, current_user["user_id"])
            if not user or not user.profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Profile not found"
                )

            return UserProfileResponse.from_orm(user.profile)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get profile"
        )

@app.put("/users/profile", response_model=UserProfileResponse)
async def update_user_profile_endpoint(
    profile_data: UserProfileUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user profile"""
    try:
        with get_db_context() as db:
            # Convert pydantic model to dict, excluding None values
            profile_dict = profile_data.dict(exclude_unset=True)

            # Handle date_of_birth conversion
            if "date_of_birth" in profile_dict and profile_dict["date_of_birth"]:
                try:
                    profile_dict["date_of_birth"] = datetime.fromisoformat(
                        profile_dict["date_of_birth"]
                    )
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid date format. Use YYYY-MM-DD"
                    )

            profile = update_user_profile(db, current_user["user_id"], profile_dict)
            return UserProfileResponse.from_orm(profile)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

@app.post("/users/profile/picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload user profile picture"""
    try:
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        # Validate file size (5MB max)
        max_size = 5 * 1024 * 1024
        file_content = await file.read()
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size too large. Maximum 5MB allowed"
            )

        # Create user profile directory
        user_id = current_user["user_id"]
        profile_dir = USER_PROFILE_PICS_DIR.format(user_id=user_id)
        os.makedirs(profile_dir, exist_ok=True)

        # Save file
        file_extension = file.filename.split(".")[-1]
        filename = f"profile.{file_extension}"
        file_path = os.path.join(profile_dir, filename)

        with open(file_path, "wb") as f:
            f.write(file_content)

        # Update user profile
        with get_db_context() as db:
            update_user_profile(db, user_id, {"profile_picture": file_path})

        logger.info(f"Profile picture uploaded for user {user_id}")

        return {
            "message": "Profile picture uploaded successfully",
            "file_path": file_path
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload profile picture: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload profile picture"
        )

@app.get("/users/applications")
async def get_user_applications_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all applications for current user"""
    try:
        with get_db_context() as db:
            applications = get_user_applications(db, current_user["user_id"])

            result = []
            for app in applications:
                app_data = {
                    "id": app.id,
                    "application_type": app.application_type,
                    "status": app.status,
                    "urgency_level": app.urgency_level,
                    "submitted_at": app.submitted_at.isoformat(),
                    "processed_at": app.processed_at.isoformat() if app.processed_at else None,
                    "decision": app.decision,
                    "support_amount": app.support_amount,
                    "decision_message": app.decision_message
                }

                # Parse JSON data
                if app.applicant_data:
                    try:
                        app_data["applicant_data"] = json.loads(app.applicant_data)
                    except json.JSONDecodeError:
                        app_data["applicant_data"] = {}

                if app.processing_result:
                    try:
                        app_data["processing_result"] = json.loads(app.processing_result)
                    except json.JSONDecodeError:
                        app_data["processing_result"] = {}

                result.append(app_data)

            return {"applications": result, "total": len(result)}

    except Exception as e:
        logger.error(f"Failed to get applications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get applications"
        )

@app.get("/users/documents")
async def get_user_documents_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all documents for current user"""
    try:
        with get_db_context() as db:
            documents = get_user_documents(db, current_user["user_id"])

            result = []
            for doc in documents:
                doc_data = {
                    "id": doc.id,
                    "application_id": doc.application_id,
                    "document_type": doc.document_type,
                    "filename": doc.filename,
                    "original_filename": doc.original_filename,
                    "file_size": doc.file_size,
                    "content_type": doc.content_type,
                    "upload_date": doc.upload_date.isoformat()
                }
                result.append(doc_data)

            return {"documents": result, "total": len(result)}

    except Exception as e:
        logger.error(f"Failed to get documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get documents"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.auth_server:app",
        host="0.0.0.0",
        port=8002,
        reload=True
    )
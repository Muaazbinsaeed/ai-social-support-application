"""
Simple Authentication API server for user registration and login
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Dict, Any, Optional
import logging
import os
import bcrypt
import jwt
from datetime import datetime, timedelta
import sqlite3
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Social Support Simple Authentication API",
    description="Simple user authentication API",
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

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Database setup
DB_DIR = "data/database"
DB_FILE = os.path.join(DB_DIR, "simple_users.db")

def init_database():
    """Initialize SQLite database"""
    os.makedirs(DB_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create user profiles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            emirates_id TEXT,
            address TEXT,
            date_of_birth TEXT,
            family_size INTEGER,
            employment_status TEXT,
            monthly_income REAL,
            bank_balance REAL,
            has_existing_support BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()

# Pydantic models
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    created_at: str

class UserProfileUpdate(BaseModel):
    emirates_id: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[str] = None
    family_size: Optional[int] = None
    employment_status: Optional[str] = None
    monthly_income: Optional[float] = None
    bank_balance: Optional[float] = None
    has_existing_support: Optional[bool] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse

# Utility functions
def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: Dict[str, Any]) -> str:
    """Create JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Dict[str, Any]:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        user_id = payload.get("user_id")
        if email is None or user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"email": email, "user_id": user_id}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current user from token"""
    return verify_token(credentials.credentials)

def validate_password(password: str) -> bool:
    """Validate password strength"""
    if len(password) < 8:
        return False
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    return has_upper and has_lower and has_digit

# Initialize database
init_database()

# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "AI Social Support Simple Authentication API",
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

@app.get("/auth/me")
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current authenticated user information"""
    return {
        "user": current_user,
        "authenticated": True,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/auth/register", response_model=Token)
async def register_user(user_data: UserCreate):
    """Register new user"""
    try:
        # Validate password
        if not validate_password(user_data.password):
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters with uppercase, lowercase, and number"
            )

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (user_data.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create user
        password_hash = hash_password(user_data.password)
        cursor.execute("""
            INSERT INTO users (email, password_hash, full_name, phone, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (user_data.email, password_hash, user_data.full_name, user_data.phone))

        user_id = cursor.lastrowid

        # Create empty profile
        cursor.execute("""
            INSERT INTO user_profiles (user_id) VALUES (?)
        """, (user_id,))

        conn.commit()

        # Get user data
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        conn.close()

        user_response = UserResponse(
            id=user_row[0],
            email=user_row[1],
            full_name=user_row[3],
            is_active=bool(user_row[5]),
            created_at=user_row[6]
        )

        # Create token
        access_token = create_access_token(
            data={"sub": user_data.email, "user_id": user_id}
        )

        logger.info(f"User registered: {user_data.email}")

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/auth/login", response_model=Token)
async def login_user(credentials: UserLogin):
    """Login user"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = ?", (credentials.email,))
        user_row = cursor.fetchone()
        conn.close()

        if not user_row or not verify_password(credentials.password, user_row[2]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not user_row[5]:  # is_active
            raise HTTPException(status_code=401, detail="Account disabled")

        user_response = UserResponse(
            id=user_row[0],
            email=user_row[1],
            full_name=user_row[3],
            is_active=bool(user_row[5]),
            created_at=user_row[6]
        )

        access_token = create_access_token(
            data={"sub": credentials.email, "user_id": user_row[0]}
        )

        logger.info(f"User logged in: {credentials.email}")

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.post("/auth/verify")
async def verify_token_endpoint(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Verify JWT token"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE id = ?", (current_user["user_id"],))
        user_row = cursor.fetchone()
        conn.close()

        if not user_row:
            raise HTTPException(status_code=401, detail="User not found")

        user_response = UserResponse(
            id=user_row[0],
            email=user_row[1],
            full_name=user_row[3],
            is_active=bool(user_row[5]),
            created_at=user_row[6]
        )

        return {"valid": True, "user": user_response}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Token verification failed")

@app.get("/users/profile")
async def get_user_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user profile"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (current_user["user_id"],))
        profile_row = cursor.fetchone()
        conn.close()

        if not profile_row:
            return {}

        return {
            "user_id": profile_row[1],
            "emirates_id": profile_row[2],
            "address": profile_row[3],
            "date_of_birth": profile_row[4],
            "family_size": profile_row[5],
            "employment_status": profile_row[6],
            "monthly_income": profile_row[7],
            "bank_balance": profile_row[8],
            "has_existing_support": bool(profile_row[9]) if profile_row[9] is not None else False
        }

    except Exception as e:
        logger.error(f"Failed to get profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profile")

@app.put("/users/profile")
async def update_user_profile(
    profile_data: UserProfileUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user profile"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Get current profile
        cursor.execute("SELECT id FROM user_profiles WHERE user_id = ?", (current_user["user_id"],))
        if not cursor.fetchone():
            # Create profile if it doesn't exist
            cursor.execute("INSERT INTO user_profiles (user_id) VALUES (?)", (current_user["user_id"],))

        # Update profile
        update_fields = []
        values = []

        for field, value in profile_data.dict(exclude_unset=True).items():
            if value is not None:
                update_fields.append(f"{field} = ?")
                values.append(value)

        if update_fields:
            values.append(current_user["user_id"])
            cursor.execute(f"""
                UPDATE user_profiles
                SET {', '.join(update_fields)}
                WHERE user_id = ?
            """, values)

        conn.commit()
        conn.close()

        logger.info(f"Profile updated for user {current_user['user_id']}")
        return {"message": "Profile updated successfully"}

    except Exception as e:
        logger.error(f"Failed to update profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")

@app.get("/users/applications")
async def get_user_applications(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user applications (placeholder)"""
    return {"applications": [], "total": 0}

@app.get("/users/documents")
async def get_user_documents(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user documents (placeholder)"""
    return {"documents": [], "total": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
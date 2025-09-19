# 👥 Multi-User System Guide

## Overview

The AI Social Support Application now supports multiple users with secure authentication, personal profiles, and data isolation. Each user has their own private space for applications, documents, and profile information.

## 🔐 Authentication System

### User Registration
- **Email-based accounts** with strong password requirements
- **Profile information** including phone number and personal details
- **JWT token authentication** for secure API access
- **Automatic profile creation** for new users

### Password Requirements
- Minimum 8 characters
- Must contain uppercase letter
- Must contain lowercase letter
- Must contain at least one number

### Login Features
- **Secure JWT tokens** with 7-day expiration
- **Token verification** for all protected endpoints
- **Automatic logout** on token expiration
- **Remember session** across browser restarts

## 👤 User Profiles

### Personal Information
- **Full name** and contact details
- **Emirates ID** and date of birth
- **Address** and family size
- **Employment status** and income information
- **Profile picture** upload (up to 5MB)

### Financial Information
- **Monthly income** tracking
- **Bank balance** information
- **Existing government support** status
- **Employment status** categories

## 📊 User Dashboard

### Dashboard Features
- **Application history** with status tracking
- **Document library** with file management
- **Profile management** with real-time updates
- **Usage statistics** and insights
- **Recent activity** timeline

### Application Management
- **View all applications** submitted by the user
- **Filter by status** (submitted, processing, approved, declined)
- **Detailed application views** with decision information
- **Support amount tracking** and total calculations

### Document Management
- **Secure document storage** in user-specific directories
- **Document classification** by type and application
- **File metadata** including size and upload date
- **Document type statistics** and usage insights

## 🔒 Data Isolation & Security

### User Data Separation
- **Individual user directories** for document storage
- **Database-level isolation** using user_id foreign keys
- **Application ownership** enforced at API level
- **Document access control** based on user authentication

### File Structure
```
data/
├── users/
│   ├── {user_id}/
│   │   ├── documents/
│   │   │   ├── doc_1_emirates_id.pdf
│   │   │   └── doc_2_bank_statement.pdf
│   │   └── profile/
│   │       └── profile.jpg
│   └── {another_user_id}/
│       ├── documents/
│       └── profile/
└── database/
    └── users.db
```

### Security Features
- **JWT token validation** for all user endpoints
- **CORS protection** for cross-origin requests
- **Password hashing** using bcrypt
- **Input validation** and sanitization
- **SQL injection protection** via SQLAlchemy ORM

## 🚀 Getting Started

### 1. Start the System
```bash
# Start all services (Auth, API, Chat, Frontend)
python run_with_auth.py
```

### 2. Access the Application
- Open browser to `http://localhost:8501`
- Choose to **Register** or **Login**
- Or continue as **Anonymous** user

### 3. Create Your Account
1. Click **Register** tab
2. Enter email, password, and full name
3. Optionally add phone number
4. Click **Register** button

### 4. Complete Your Profile
1. Go to **Dashboard** tab
2. Click **Profile** sub-tab
3. Fill in personal and financial information
4. Upload profile picture (optional)
5. Save changes

## 📱 Using the Application

### Authenticated vs Anonymous

| Feature | Authenticated User | Anonymous User |
|---------|-------------------|----------------|
| **Application Submission** | ✅ Persistent | ✅ Session-only |
| **Document Upload** | ✅ Secure storage | ✅ Temporary |
| **Application History** | ✅ Full history | ❌ None |
| **Profile Management** | ✅ Complete | ❌ None |
| **Document Library** | ✅ Organized | ❌ None |
| **Data Persistence** | ✅ Permanent | ❌ Session-only |
| **Multi-device Access** | ✅ Yes | ❌ No |
| **Progress Tracking** | ✅ Real-time | ✅ Current session |
| **AI Chat** | ✅ Full features | ✅ Full features |

### Application Workflow (Authenticated)
1. **Login** to your account
2. **Submit application** via Application Form tab
3. **Upload documents** via Documents tab
4. **Track progress** in sidebar status
5. **View results** in Results tab
6. **Check history** in Dashboard → Applications

### Application Workflow (Anonymous)
1. **Continue as Guest**
2. **Submit application** (session-based)
3. **Upload documents** (temporary)
4. **Track progress** for current session
5. **View results** (session-only)

## 🔧 Technical Architecture

### Services
- **Authentication API** (Port 8002): User management and JWT tokens
- **Main API** (Port 8000): Application processing with user isolation
- **Chat API** (Port 8001): AI assistant (unchanged)
- **Frontend** (Port 8501): Streamlit UI with authentication

### Database Schema
```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    full_name VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User profiles
CREATE TABLE user_profiles (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    phone VARCHAR,
    emirates_id VARCHAR UNIQUE,
    address TEXT,
    -- ... other profile fields
);

-- User applications
CREATE TABLE user_applications (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    application_type VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'submitted',
    applicant_data TEXT, -- JSON
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User documents
CREATE TABLE user_documents (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    application_id INTEGER REFERENCES user_applications(id),
    document_type VARCHAR NOT NULL,
    filename VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### API Endpoints

#### Authentication Endpoints
- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `POST /auth/verify` - Verify JWT token
- `GET /users/profile` - Get user profile
- `PUT /users/profile` - Update user profile
- `POST /users/profile/picture` - Upload profile picture
- `GET /users/applications` - Get user applications
- `GET /users/documents` - Get user documents

#### Application Endpoints (Enhanced)
- `POST /applications/submit` - Submit application (with user context)
- `POST /applications/{id}/documents/upload` - Upload documents (with user context)
- All existing endpoints work for both authenticated and anonymous users

## 🧪 Testing

### Manual Testing
1. Start the system: `python run_with_auth.py`
2. Open browser to `http://localhost:8501`
3. Test registration, login, and features

### Automated Testing
```bash
# Run comprehensive multi-user tests
python test_multiuser.py
```

The test script verifies:
- User registration and login
- Profile management
- Application submission with user isolation
- Document upload with user-specific storage
- Data isolation between users
- Anonymous vs authenticated functionality

## 🔄 Migration from Single-User

### Existing Data
- **Anonymous applications** remain in JSON files
- **New authenticated users** use database storage
- **Backward compatibility** maintained for existing sessions

### Upgrade Path
1. Start new system with `python run_with_auth.py`
2. Existing data remains accessible
3. New users get full multi-user features
4. Optional: Migrate existing data to database

## 📈 Benefits of Multi-User System

### For Users
- **Secure personal data** with authentication
- **Application history** tracking across sessions
- **Document management** with organized storage
- **Profile customization** and management
- **Multi-device access** with account sync

### For Organizations
- **User analytics** and usage tracking
- **Data isolation** and security compliance
- **Scalable architecture** for multiple users
- **Audit trails** and user activity logs
- **Professional user experience**

### For Developers
- **Modular architecture** with separate services
- **Standard JWT authentication** patterns
- **Database-driven** data management
- **RESTful API** design
- **Easy testing** and deployment

## 🔮 Future Enhancements

### Planned Features
- **Email verification** for new accounts
- **Password reset** functionality
- **Two-factor authentication** (2FA)
- **User roles** and permissions
- **Organization accounts** for group management
- **Advanced analytics** and reporting
- **API rate limiting** per user
- **Audit logging** for compliance

### Enterprise Features
- **Single Sign-On** (SSO) integration
- **LDAP/Active Directory** authentication
- **Role-based access control** (RBAC)
- **Multi-tenant** organization support
- **Advanced security** features
- **Compliance reporting**

---

**The multi-user system provides a secure, scalable foundation for the AI Social Support Application while maintaining backward compatibility with anonymous usage.**
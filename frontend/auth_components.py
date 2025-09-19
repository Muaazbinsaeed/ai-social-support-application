"""
Authentication components for Streamlit frontend
"""

import streamlit as st
import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime
import time

# API URLs
AUTH_API_URL = "http://localhost:8002"

def restore_session_if_valid():
    """Try to restore session by checking if stored token is still valid"""
    # Check if we have query params with auth info (for basic persistence)
    query_params = st.query_params

    if "auth_token" in query_params:
        token = query_params["auth_token"]

        # First, restore the session optimistically for better UX
        st.session_state.user_token = token
        st.session_state.logged_in = True

        try:
            # Validate token with backend (shorter timeout for better UX)
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{AUTH_API_URL}/auth/me", headers=headers, timeout=3)

            if response.status_code == 200:
                user_data = response.json()
                # Update session state with comprehensive user data
                st.session_state.user_info = user_data.get("user", {})

                # Also restore application context if available
                if "application_id" in query_params:
                    try:
                        app_id = int(query_params["application_id"])
                        st.session_state.application_id = app_id
                        st.session_state.application_submitted = True

                        # Check if documents were uploaded
                        doc_response = requests.get(f"http://localhost:8000/applications/{app_id}/details",
                                                   headers=headers, timeout=3)
                        if doc_response.status_code == 200:
                            details = doc_response.json()
                            if details.get("documents"):
                                st.session_state.documents_uploaded = True

                            # Try to restore form data from backend
                            st.session_state.form_data_loaded = False  # Mark for reloading

                    except (ValueError, requests.exceptions.RequestException):
                        pass  # Ignore errors in application context restoration

                return True
            elif response.status_code in [401, 403]:
                # Token is invalid, clear it
                st.query_params.clear()
                st.session_state.logged_in = False
                st.session_state.user_token = None
                st.session_state.user_info = {}
                return False
            else:
                # Server error, keep session for offline use
                return True

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            # Network error - keep session for offline use
            return True
        except Exception:
            # Other errors - keep session
            return True

    return False

def save_session_to_url():
    """Save session token and application context to URL for basic persistence"""
    if st.session_state.logged_in and st.session_state.user_token:
        # Always ensure token is in URL for persistence across page reloads
        if st.query_params.get("auth_token") != st.session_state.user_token:
            st.query_params["auth_token"] = st.session_state.user_token

    # Save application context for both authenticated and anonymous users
    if hasattr(st.session_state, 'application_id') and st.session_state.application_id:
        if st.query_params.get("application_id") != str(st.session_state.application_id):
            st.query_params["application_id"] = str(st.session_state.application_id)
            
        # Also mark application as submitted if we have an ID
        if hasattr(st.session_state, 'application_submitted'):
            st.session_state.application_submitted = True

def init_session_state():
    """Initialize session state for authentication and application context"""
    # Initialize authentication state
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_token" not in st.session_state:
        st.session_state.user_token = None
    if "user_info" not in st.session_state:
        st.session_state.user_info = {}
    if "auth_error" not in st.session_state:
        st.session_state.auth_error = None
    if "session_restored" not in st.session_state:
        st.session_state.session_restored = False

    # Initialize application state
    if "application_id" not in st.session_state:
        st.session_state.application_id = None
    if "application_submitted" not in st.session_state:
        st.session_state.application_submitted = False
    if "documents_uploaded" not in st.session_state:
        st.session_state.documents_uploaded = False
    if "processing_started" not in st.session_state:
        st.session_state.processing_started = False
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Initialize form data persistence
    if "form_data" not in st.session_state:
        st.session_state.form_data = {}
    if "form_edit_mode" not in st.session_state:
        st.session_state.form_edit_mode = False

    # Try to restore session on first load or if not already restored
    if not st.session_state.logged_in and not st.session_state.session_restored:
        if restore_session_if_valid():
            st.session_state.session_restored = True

    # Initialize form data loading flag
    if "form_data_loaded" not in st.session_state:
        st.session_state.form_data_loaded = False

    # Check for application_id in URL params for anonymous users
    if not st.session_state.application_id:
        query_params = st.query_params
        if "application_id" in query_params:
            try:
                app_id = int(query_params["application_id"])
                st.session_state.application_id = app_id
                st.session_state.application_submitted = True
                st.session_state.form_data_loaded = False  # Mark for reloading
            except ValueError:
                pass  # Invalid application ID in URL

def parse_validation_errors(error_data):
    """Parse validation errors and return user-friendly messages"""
    if isinstance(error_data, dict):
        detail = error_data.get("detail", "")

        # Handle FastAPI validation errors
        if isinstance(detail, list):
            errors = []
            for error in detail:
                if error.get("type") == "value_error" and "email" in error.get("loc", []):
                    if "An email address must have an @-sign" in error.get("msg", ""):
                        errors.append("Please enter a valid email address with an @ sign")
                    elif "The part after the @-sign is not valid" in error.get("msg", ""):
                        errors.append("Please enter a valid email address (e.g., user@example.com)")
                    else:
                        errors.append("Please enter a valid email address")
                else:
                    # General error message
                    field = error.get("loc", [""])[-1] if error.get("loc") else "field"
                    msg = error.get("msg", "Invalid value")
                    errors.append(f"{field.title()}: {msg}")
            return "; ".join(errors) if errors else "Validation error"
        else:
            return detail

    return str(error_data)

def login_user(email: str, password: str) -> bool:
    """Login user and store token"""
    try:
        response = requests.post(
            f"{AUTH_API_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            st.session_state.user_token = data["access_token"]
            st.session_state.user_info = data["user"]
            st.session_state.logged_in = True
            st.session_state.auth_error = None

            # Save session for persistence across page reloads
            save_session_to_url()

            return True
        else:
            error_data = response.json()
            st.session_state.auth_error = parse_validation_errors(error_data)
            return False

    except requests.exceptions.ConnectionError:
        st.session_state.auth_error = "Authentication service unavailable. You can still use the app anonymously."
        return False
    except requests.exceptions.Timeout:
        st.session_state.auth_error = "Login request timed out. Please try again."
        return False
    except Exception as e:
        st.session_state.auth_error = f"Login error: {str(e)}"
        return False

def register_user(email: str, password: str, full_name: str, phone: str = "") -> bool:
    """Register new user"""
    try:
        user_data = {
            "email": email,
            "password": password,
            "full_name": full_name
        }
        if phone:
            user_data["phone"] = phone

        response = requests.post(
            f"{AUTH_API_URL}/auth/register",
            json=user_data,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            st.session_state.user_token = data["access_token"]
            st.session_state.user_info = data["user"]
            st.session_state.logged_in = True
            st.session_state.auth_error = None

            # Save session for persistence across page reloads
            save_session_to_url()

            return True
        else:
            error_data = response.json()
            st.session_state.auth_error = parse_validation_errors(error_data)
            return False

    except requests.exceptions.ConnectionError:
        st.session_state.auth_error = "Authentication service unavailable. You can still use the app anonymously."
        return False
    except requests.exceptions.Timeout:
        st.session_state.auth_error = "Registration request timed out. Please try again."
        return False
    except Exception as e:
        st.session_state.auth_error = f"Registration error: {str(e)}"
        return False

def logout_user():
    """Logout user and clear session"""
    st.session_state.logged_in = False
    st.session_state.user_token = None
    st.session_state.user_info = {}
    st.session_state.auth_error = None

    # Clear the token from URL
    if "auth_token" in st.query_params:
        st.query_params.clear()

def verify_token() -> bool:
    """Verify current token is valid"""
    if not st.session_state.user_token:
        return False

    try:
        headers = {"Authorization": f"Bearer {st.session_state.user_token}"}
        response = requests.post(
            f"{AUTH_API_URL}/auth/verify",
            headers=headers,
            timeout=3
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("valid"):
                st.session_state.user_info = data.get("user", {})
                return True

        # Token invalid - only logout if we get a clear 401/403
        if response.status_code in [401, 403]:
            logout_user()
            return False
        else:
            # Other errors (500, etc.) - keep session
            return True

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        # Network error or service unavailable - keep session for offline use
        return True
    except Exception:
        # Other errors - keep session
        return True

def get_auth_headers() -> Dict[str, str]:
    """Get authentication headers for API requests"""
    if st.session_state.user_token:
        return {"Authorization": f"Bearer {st.session_state.user_token}"}
    return {}

def validate_email(email: str) -> str:
    """Validate email format and return error message if invalid"""
    if not email:
        return "Email is required"
    if "@" not in email:
        return "Please enter a valid email address with an @ sign"
    if "." not in email.split("@")[-1]:
        return "Please enter a valid email address (e.g., user@example.com)"
    if len(email.split("@")) != 2:
        return "Please enter a valid email address"
    return ""

def show_login_form():
    """Display login form"""
    st.subheader("🔐 Login")

    with st.form("login_form"):
        email = st.text_input(
            "Email",
            placeholder="your.email@example.com",
            help="Enter your registered email address"
        )
        password = st.text_input(
            "Password",
            type="password",
            help="Enter your password"
        )
        submitted = st.form_submit_button("Login", type="primary")

        if submitted:
            # Client-side validation
            email_error = validate_email(email)
            if email_error:
                st.error(f"❌ {email_error}")
            elif not password:
                st.error("❌ Password is required")
            else:
                with st.spinner("Logging in..."):
                    if login_user(email, password):
                        st.success("Login successful!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        if st.session_state.auth_error:
                            st.error(f"❌ {st.session_state.auth_error}")

def show_register_form():
    """Display registration form"""
    st.subheader("📝 Register")

    with st.form("register_form"):
        col1, col2 = st.columns(2)

        with col1:
            full_name = st.text_input(
                "Full Name *",
                placeholder="John Doe",
                help="Enter your full name as it appears on official documents"
            )
            email = st.text_input(
                "Email *",
                placeholder="user@example.com",
                help="Enter a valid email address (must contain @ and .com/.org etc.)"
            )

        with col2:
            phone = st.text_input(
                "Phone (Optional)",
                placeholder="+971 50 123 4567",
                help="Enter your phone number (optional)"
            )
            password = st.text_input(
                "Password *",
                type="password",
                help="Must be at least 8 characters with uppercase, lowercase, and numbers"
            )

        # Enhanced password requirements
        st.info("📋 **Password Requirements**: At least 8 characters including uppercase letter, lowercase letter, and number")
        st.caption("💡 **Example**: MyPassword123")

        submitted = st.form_submit_button("Register", type="primary")

        if submitted:
            # Client-side validation
            errors = []

            # Full name validation
            if not full_name or not full_name.strip():
                errors.append("Full name is required")

            # Email validation
            email_error = validate_email(email)
            if email_error:
                errors.append(email_error)

            # Password validation
            if not password:
                errors.append("Password is required")
            elif len(password) < 8:
                errors.append("Password must be at least 8 characters")
            else:
                # Password strength check
                has_upper = any(c.isupper() for c in password)
                has_lower = any(c.islower() for c in password)
                has_digit = any(c.isdigit() for c in password)

                if not (has_upper and has_lower and has_digit):
                    errors.append("Password must contain uppercase, lowercase, and number")

            # Display errors
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                with st.spinner("Creating account..."):
                    if register_user(email, password, full_name, phone):
                        st.success("✅ Registration successful!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        if st.session_state.auth_error:
                            st.error(f"❌ {st.session_state.auth_error}")

def show_auth_page():
    """Main authentication page"""
    st.title("🤝 AI Social Support Application")
    st.markdown("**Secure Access to Your Social Support Services**")

    # Check if auth service is available
    try:
        response = requests.get(f"{AUTH_API_URL}/auth/health", timeout=3)
        auth_available = response.status_code == 200
    except:
        auth_available = False

    if not auth_available:
        st.warning("⚠️ Authentication service is currently unavailable")
        st.info("You can continue to use the application anonymously with limited features.")

        if st.button("Continue Anonymously", type="primary"):
            st.session_state.logged_in = "anonymous"
            st.rerun()

        st.divider()

    # Authentication tabs
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])

    with tab1:
        show_login_form()

        if auth_available:
            st.divider()
            if st.button("Continue as Guest", help="Use the app without an account"):
                st.session_state.logged_in = "anonymous"
                st.rerun()

    with tab2:
        if auth_available:
            show_register_form()
        else:
            st.info("Registration is not available when the authentication service is offline.")

    # Benefits section
    with st.expander("✨ Why Create an Account?"):
        st.markdown("""
        **Account Benefits:**
        - 🔒 **Secure Profile**: Your data is protected and private
        - 📊 **Application History**: Track all your applications in one place
        - 📄 **Document Library**: Store and manage your documents securely
        - 🔄 **Progress Tracking**: Real-time updates on application status
        - 💼 **Profile Management**: Update your information anytime
        - 📈 **Analytics**: View your application statistics and insights

        **Anonymous Use:**
        - ✅ Submit applications (session-based)
        - ✅ Upload documents (temporary)
        - ✅ Chat with AI assistant
        - ❌ No data persistence
        - ❌ No history tracking
        - ❌ Limited features
        """)

def show_user_info():
    """Display current user information in sidebar"""
    if st.session_state.logged_in == "anonymous":
        st.sidebar.info("🔓 Anonymous Session")
        st.sidebar.caption("Data will not be saved permanently")

        if st.sidebar.button("Create Account"):
            st.session_state.logged_in = False
            st.rerun()

    elif st.session_state.logged_in and st.session_state.user_info:
        user = st.session_state.user_info
        st.sidebar.success(f"👋 Welcome, {user.get('full_name', 'User')}")
        st.sidebar.caption(f"📧 {user.get('email', '')}")

        # User menu
        with st.sidebar.expander("👤 Account"):
            if st.button("🔓 Logout", key="logout_btn"):
                logout_user()
                st.rerun()

def check_authentication():
    """Check authentication status and show appropriate UI"""
    init_session_state()

    # Verify token if logged in (but only periodically to avoid constant network calls)
    if st.session_state.logged_in and st.session_state.logged_in != "anonymous":
        # Only verify token occasionally (every few minutes) or if user_info is missing
        if not st.session_state.user_info or not hasattr(st.session_state, 'last_token_check'):
            if not verify_token():
                st.session_state.logged_in = False
            else:
                st.session_state.last_token_check = time.time()
        elif hasattr(st.session_state, 'last_token_check'):
            # Check if it's been more than 5 minutes since last check
            if time.time() - st.session_state.last_token_check > 300:  # 5 minutes
                verify_token()
                st.session_state.last_token_check = time.time()

    # Show auth page if not logged in
    if not st.session_state.logged_in:
        show_auth_page()
        return False

    # Show user info in sidebar
    show_user_info()
    return True
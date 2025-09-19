import streamlit as st
import requests
import time
import json
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd

# Import authentication components
from auth_components import check_authentication, save_session_to_url, get_auth_headers
from user_dashboard import show_user_profile, show_application_history

# Configure Streamlit page
st.set_page_config(
    page_title="AI Social Support Application",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Backend API URLs
API_BASE_URL = "http://localhost:8000"
CHAT_API_URL = "http://localhost:8001"

# Session state is now initialized in auth_components.init_session_state()

def add_chat_message(role: str, content: str):
    """Add a message to the chat history"""
    st.session_state.chat_messages.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

def display_chat_messages():
    """Display chat messages"""
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            st.caption(f"⏰ {message['timestamp']}")

def submit_application(applicant_data: Dict[str, Any]) -> bool:
    """Submit application to backend"""
    try:
        headers = get_auth_headers()
        response = requests.post(
            f"{API_BASE_URL}/applications/submit",
            json=applicant_data,
            headers=headers
        )

        if response.status_code == 200:
            result = response.json()
            st.session_state.application_id = result["application_id"]
            add_chat_message("assistant", f"✅ Application submitted successfully! Application ID: {result['application_id']}")
            return True
        else:
            st.error(f"Failed to submit application: {response.text}")
            return False

    except Exception as e:
        st.error(f"Error submitting application: {str(e)}")
        return False

def upload_documents(files: List, document_types: List[str]) -> bool:
    """Upload documents to backend"""
    try:
        # Prepare file information for the simplified backend
        files_info = []
        for i, file in enumerate(files):
            doc_type = document_types[i] if i < len(document_types) else "general"
            files_info.append({
                "filename": file.name,
                "type": doc_type,
                "size": file.size,
                "content_type": file.type
            })

        headers = get_auth_headers()
        response = requests.post(
            f"{API_BASE_URL}/applications/{st.session_state.application_id}/documents/upload",
            json=files_info,
            headers=headers
        )

        if response.status_code == 200:
            result = response.json()

            # Create detailed upload summary
            doc_summary = []
            for doc in result.get('uploaded_documents', []):
                doc_summary.append(f"• {doc.get('filename', 'Unknown')}")

            summary_text = f"✅ Successfully uploaded {result['total_documents']} documents:\n" + "\n".join(doc_summary)
            add_chat_message("assistant", summary_text)

            # Store summary in session state for display
            st.session_state.uploaded_docs_summary = summary_text

            return True
        else:
            st.error(f"Failed to upload documents: {response.text}")
            return False

    except Exception as e:
        st.error(f"Error uploading documents: {str(e)}")
        return False

def start_processing() -> bool:
    """Start application processing"""
    try:
        headers = get_auth_headers()
        response = requests.post(
            f"{API_BASE_URL}/applications/{st.session_state.application_id}/process",
            headers=headers
        )

        if response.status_code == 200:
            result = response.json()
            add_chat_message("assistant", "🔄 Application processing started! This may take a few minutes.")
            return True
        elif response.status_code == 404:
            st.error("❌ Application not found. Please submit a new application.")
            st.info("🔄 **To fix this issue:** Go to the Application Form tab and submit your application again.")
            # Reset application state
            if st.button("🔄 Reset Application State"):
                st.session_state.application_submitted = False
                st.session_state.application_id = None
                st.session_state.documents_uploaded = False
                st.session_state.processing_started = False
                st.rerun()
            return False
        elif response.status_code == 400:
            error_detail = response.json().get("detail", "Bad request")
            st.error(f"❌ Processing error: {error_detail}")
            if "documents" in error_detail.lower():
                st.info("💡 **Tip:** Make sure you have uploaded at least one document before starting processing.")
            return False
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("detail", "Unknown error")
                # Log the full error for debugging
                st.error(f"❌ Failed to start processing: {error_msg}")
                st.error(f"🔍 Debug info: HTTP {response.status_code}, Application ID: {st.session_state.application_id}")
            except Exception as parse_error:
                st.error(f"❌ Failed to start processing (HTTP {response.status_code})")
                st.error(f"🔍 Response: {response.text}")
                st.error(f"🔍 Parse error: {str(parse_error)}")
            return False

    except Exception as e:
        st.error(f"Error starting processing: {str(e)}")
        return False

def get_processing_status() -> Dict[str, Any]:
    """Get current processing status"""
    try:
        headers = get_auth_headers()
        response = requests.get(
            f"{API_BASE_URL}/applications/{st.session_state.application_id}/status",
            headers=headers
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return {"status": "not_found", "error": "Application not found"}
        else:
            return {"status": "unknown", "error": response.text}

    except Exception as e:
        return {"status": "error", "error": str(e)}

def get_application_details() -> Dict[str, Any]:
    """Get detailed application information"""
    try:
        headers = get_auth_headers()
        response = requests.get(
            f"{API_BASE_URL}/applications/{st.session_state.application_id}/details",
            headers=headers
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return {"error": "Application not found"}
        else:
            return {"error": response.text}

    except Exception as e:
        return {"error": str(e)}

def load_application_form_data():
    """Load and restore application form data from backend"""
    if not st.session_state.application_id:
        st.error("❌ No application ID available for loading form data")
        return False

    try:
        # Get application details from backend
        details = get_application_details()
        
        if "error" not in details:
            # Extract applicant data from backend response
            applicant_info = details.get("applicant", {})
            application_info = details.get("application", {})

            # Parse applicant_data - handle both authenticated (JSON string) and anonymous (dict) formats
            applicant_data = {}
            if application_info.get("applicant_data"):
                if isinstance(application_info["applicant_data"], str):
                    # Authenticated user - data stored as JSON string
                    try:
                        import json
                        applicant_data = json.loads(application_info["applicant_data"])
                    except:
                        applicant_data = {}
                elif isinstance(application_info["applicant_data"], dict):
                    # Anonymous user - data stored as dict
                    applicant_data = application_info["applicant_data"]

            # Also check if the backend response has a different structure
            # For anonymous users, check the main response structure
            if not applicant_data and "applicant_data" in details:
                raw_data = details["applicant_data"]
                if isinstance(raw_data, dict):
                    applicant_data = raw_data
            
            # For anonymous users, check directly in the applications_db
            if not applicant_data and details.get("application", {}).get("id"):
                try:
                    app_id = details["application"]["id"]
                    # Try to get directly from backend
                    response = requests.get(f"{API_BASE_URL}/applications/{app_id}/details")
                    if response.status_code == 200:
                        app_data = response.json()
                        if app_data.get("applicant_data"):
                            applicant_data = app_data["applicant_data"]
                except:
                    pass

            # Restore form data to session state from backend
            restored_data = {
                "first_name": applicant_data.get("first_name", applicant_info.get("name", "").split(" ")[0] if applicant_info.get("name") else ""),
                "last_name": applicant_data.get("last_name", " ".join(applicant_info.get("name", "").split(" ")[1:]) if applicant_info.get("name") else ""),
                "emirates_id": applicant_data.get("emirates_id", applicant_info.get("emirates_id", "")),
                "email": applicant_data.get("email", applicant_info.get("email", "")),
                "phone": applicant_data.get("phone", applicant_info.get("phone", "")),
                "date_of_birth": applicant_data.get("date_of_birth", ""),
                "address": applicant_data.get("address", ""),
                "family_size": applicant_data.get("family_size", 1),
                "urgency_level": applicant_data.get("urgency_level", "normal"),
                "application_type": applicant_data.get("application_type", application_info.get("type", "financial_support")),
                "monthly_income": applicant_data.get("monthly_income", 0),
                "employment_status": applicant_data.get("employment_status", "employed"),
                "bank_balance": applicant_data.get("bank_balance", 0),
                "has_existing_support": applicant_data.get("has_existing_support", False)
            }

            # Log successful data restoration
            print(f"Restored form data for application {st.session_state.application_id}: {restored_data}")
            
            # Update session state with backend data
            st.session_state.form_data = restored_data
            
            # Save to session state and URL for persistence
            save_session_to_url()

            return True
        else:
            st.error(f"❌ Backend error: {details.get('error')}")
            return False
    except Exception as e:
        st.error(f"❌ Error loading application data: {str(e)}")
        return False

# Main application UI

def main():
    # Check authentication first
    if not check_authentication():
        return  # Authentication page is shown, exit main

    # Ensure session is saved to URL for persistence
    if st.session_state.logged_in and st.session_state.logged_in != "anonymous":
        save_session_to_url()

    st.title("🤝 AI Social Support Application System")
    st.markdown("**Automated Processing for Financial Support and Economic Enablement**")

    # Sidebar for navigation and status
    with st.sidebar:
        st.header("📊 Application Status")

        if st.session_state.application_id:
            st.info(f"Application ID: {st.session_state.application_id}")

            # Get current status
            status = get_processing_status()
            current_status = status.get("status", "unknown")

            if current_status == "processing":
                st.warning("🔄 Processing in progress...")
                progress = status.get("progress", 0)
                st.progress(progress / 100)
                st.text(f"Stage: {status.get('current_stage', 'Unknown')}")

            elif current_status == "completed":
                st.success("✅ Processing completed!")

            elif current_status == "failed":
                st.error("❌ Processing failed")

            elif current_status == "not_found":
                st.error("❌ Application not found")
                st.warning("Please submit a new application")
                if st.button("🔄 Reset & Start Over"):
                    st.session_state.application_submitted = False
                    st.session_state.application_id = None
                    st.session_state.documents_uploaded = False
                    st.session_state.processing_started = False
                    st.rerun()

            # Refresh button
            if st.button("🔄 Refresh Status"):
                st.rerun()

        else:
            st.info("No application submitted yet")

        st.divider()

        # System stats
        st.subheader("📈 System Statistics")
        try:
            response = requests.get(f"{API_BASE_URL}/analytics/stats", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                st.metric("Total Applications", stats.get("total_applications", 0))
                st.metric("System Health", stats.get("system_health", "Unknown"))
            else:
                st.text("API Error")
        except requests.exceptions.ConnectionError:
            st.error("🔴 Backend server offline")
        except requests.exceptions.Timeout:
            st.warning("⏱️ Backend server slow")
        except Exception:
            st.text("Stats unavailable")

        # LLM Chat Status
        st.subheader("🤖 AI Chat Status")
        try:
            response = requests.get(f"{CHAT_API_URL}/chat/health", timeout=3)
            if response.status_code == 200:
                chat_health = response.json()
                if chat_health.get("llm_available"):
                    st.success("🟢 LLM Active")
                    st.caption(f"Model: {chat_health.get('model', 'Unknown')}")
                else:
                    st.warning("🟡 Fallback Mode")
                    st.caption("Using rule-based responses")
            else:
                st.error("🔴 Chat service offline")
        except:
            st.error("🔴 Chat service offline")

    # Main content area with tabs
    # Core application tabs (as per README specifications)
    tab1, tab2, tab3, tab4 = st.tabs(["💬 Application Chat", "📋 Application Form", "📄 Documents", "📊 Results"])

    # Note: Profile and My Applications tabs removed to match README core functionality
    # They can be re-enabled when full multi-user authentication system is deployed

    with tab1:
        st.header("💬 Interactive Application Assistant")

        # Chat interface
        chat_container = st.container()

        with chat_container:
            display_chat_messages()

        # Chat input
        user_input = st.chat_input("Ask me anything about your application...")

        if user_input:
            # Immediately show user message and loading indicator
            add_chat_message("user", user_input)
            add_chat_message("assistant", "🤖 *AI is thinking...*")

            # Force display of messages
            st.rerun()

        # Check if we need to replace the loading message with actual response
        if (len(st.session_state.chat_messages) > 0 and
            st.session_state.chat_messages[-1]["role"] == "assistant" and
            st.session_state.chat_messages[-1]["content"] == "🤖 *AI is thinking...*"):

            # Get the user's last message
            user_message = st.session_state.chat_messages[-2]["content"]

            # Remove the loading message
            st.session_state.chat_messages.pop()

            # Get AI-powered response from backend
            try:
                # Create query string for the chat API
                import urllib.parse
                query_params = f"message={urllib.parse.quote(user_message)}"
                if st.session_state.application_id:
                    query_params += f"&application_id={st.session_state.application_id}"

                chat_response = requests.post(
                    f"{CHAT_API_URL}/chat/message?{query_params}",
                    timeout=8
                )

                if chat_response.status_code == 200:
                    result = chat_response.json()
                    response = result.get("response", "I'm here to help! Could you please rephrase your question?")

                    # Add indicators for LLM vs fallback
                    if result.get("fallback"):
                        response += "\n\n🔧 *Using basic responses - LLM temporarily unavailable*"
                else:
                    # Fallback to simple response if API fails
                    response = "I'm here to help with your social support application. The AI service is temporarily unavailable, but I can still assist with basic information. What would you like to know?"

            except requests.exceptions.Timeout:
                response = "⏱️ The AI is thinking... This might take a moment for complex questions. You can try asking a simpler question or wait and try again."
            except requests.exceptions.ConnectionError:
                response = "🔴 **Connection Error**: The AI chat service is currently offline. I can still help with basic information:\n\n📄 **Documents needed**: Emirates ID, bank statements, income proof\n✅ **Basic eligibility**: UAE residency, income below AED 4,000\n⚙️ **Process**: Submit form → Upload documents → AI processing → Decision"
            except Exception as e:
                # Fallback response for other errors
                if "document" in user_message.lower():
                    response = "📄 I can help with documents! You'll need Emirates ID, bank statements, and income proof. Please try again when the AI service is available for more detailed assistance."
                elif "eligibility" in user_message.lower():
                    response = "✅ Basic eligibility includes UAE residency and monthly income below AED 4,000. Please try again when the AI service is available for detailed criteria."
                elif any(word in user_message.lower() for word in ["hello", "hi", "hey"]):
                    response = "👋 Hello! I'm your AI Social Support Assistant. The AI service is temporarily slow, but I'm here to help with basic questions."
                else:
                    response = "I'm here to help! The AI service is temporarily unavailable, but I can provide basic information about documents, eligibility, or the application process."

            add_chat_message("assistant", response)
            st.rerun()

    with tab2:
        st.header("📋 Application Form")

        # Load form data from backend if application exists but form data not loaded
        if (st.session_state.application_id and
            st.session_state.application_submitted and
            not st.session_state.get("form_data_loaded", False) and
            not st.session_state.form_data):

            st.info(f"🔄 **Loading application data for ID: {st.session_state.application_id}**")

            with st.spinner("Loading your application data..."):
                if load_application_form_data():
                    st.session_state.form_data_loaded = True
                    st.success("✅ Application data loaded from backend!")
                    time.sleep(1)  # Brief pause to show success message
                    st.rerun()
                else:
                    st.warning("⚠️ Could not load application data from backend. You can still edit the form manually.")
                    st.session_state.form_data_loaded = True  # Prevent repeated attempts

        # Show edit button if application is already submitted
        if st.session_state.application_submitted and not st.session_state.form_edit_mode:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("✏️ Edit Application", type="secondary", use_container_width=True):
                    st.session_state.form_edit_mode = True
                    st.rerun()

        # Show form if not submitted or in edit mode
        if not st.session_state.application_submitted or st.session_state.form_edit_mode:
            with st.form("application_form"):
                st.info("📋 **Field Guide**: Fields marked with (*) are required. All other fields are optional but help improve processing accuracy.")

                if st.session_state.form_edit_mode:
                    st.warning("✏️ **Edit Mode**: You can modify your application details below.")

                st.subheader("Personal Information")

                col1, col2 = st.columns(2)

                # Get saved form data or use defaults
                saved_data = st.session_state.form_data

                with col1:
                    first_name = st.text_input("First Name *",
                        value=saved_data.get("first_name", ""),
                        placeholder="Enter your first name")
                    emirates_id = st.text_input("Emirates ID *",
                        value=saved_data.get("emirates_id", ""),
                        placeholder="784-XXXX-XXXXXXX-X")
                    phone = st.text_input("Phone Number (Optional)",
                        value=saved_data.get("phone", ""),
                        placeholder="+971 XX XXX XXXX")
                    family_size = st.number_input("Family Size *",
                        min_value=1,
                        value=saved_data.get("family_size", 1))

                with col2:
                    last_name = st.text_input("Last Name *",
                        value=saved_data.get("last_name", ""),
                        placeholder="Enter your last name")
                    email = st.text_input("Email (Optional)",
                        value=saved_data.get("email", ""),
                        placeholder="your.email@example.com")

                    # Handle date of birth
                    dob_value = datetime(1990, 1, 1).date()
                    if saved_data.get("date_of_birth"):
                        try:
                            dob_value = datetime.fromisoformat(saved_data["date_of_birth"]).date()
                        except:
                            pass

                    date_of_birth = st.date_input(
                        "Date of Birth (Optional)",
                        min_value=datetime(1900, 1, 1).date(),
                        max_value=datetime.now().date(),
                        value=dob_value
                    )

                    urgency_options = ["normal", "high", "critical"]
                    urgency_index = 0
                    if saved_data.get("urgency_level") in urgency_options:
                        urgency_index = urgency_options.index(saved_data["urgency_level"])

                    urgency_level = st.selectbox("Urgency Level *", urgency_options, index=urgency_index)

                address = st.text_area("Address (Optional)",
                    value=saved_data.get("address", ""),
                    placeholder="Enter your full address")

                st.subheader("Application Details")

                app_type_options = ["financial_support", "economic_enablement"]
                app_type_index = 0
                if saved_data.get("application_type") in app_type_options:
                    app_type_index = app_type_options.index(saved_data["application_type"])

                application_type = st.selectbox(
                    "Application Type *",
                    app_type_options,
                    index=app_type_index,
                    format_func=lambda x: "Financial Support" if x == "financial_support" else "Economic Enablement"
                )

                # Additional financial information
                st.subheader("Financial Information (Optional)")
                col3, col4 = st.columns(2)

                with col3:
                    monthly_income = st.number_input("Monthly Income (AED) - Optional",
                        min_value=0,
                        value=saved_data.get("monthly_income", 0))

                    emp_options = ["employed", "unemployed", "self_employed", "student", "retired"]
                    emp_index = 0
                    if saved_data.get("employment_status") in emp_options:
                        emp_index = emp_options.index(saved_data["employment_status"])

                    employment_status = st.selectbox("Employment Status (Optional)", emp_options, index=emp_index)

                with col4:
                    bank_balance = st.number_input("Current Bank Balance (AED) - Optional",
                        min_value=0,
                        value=saved_data.get("bank_balance", 0))
                    has_existing_support = st.checkbox("Currently receiving government support (Optional)",
                        value=saved_data.get("has_existing_support", False))

                # Submit button
                button_text = "Update Application" if st.session_state.form_edit_mode else "Submit Application"
                submitted = st.form_submit_button(button_text, type="primary")

                if submitted:
                    # Save form data to session state for persistence
                    form_data = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "emirates_id": emirates_id,
                        "email": email,
                        "phone": phone,
                        "date_of_birth": date_of_birth.isoformat(),
                        "address": address,
                        "family_size": family_size,
                        "urgency_level": urgency_level,
                        "application_type": application_type,
                        "monthly_income": monthly_income,
                        "employment_status": employment_status,
                        "bank_balance": bank_balance,
                        "has_existing_support": has_existing_support
                    }
                    st.session_state.form_data = form_data

                    # Enhanced validation with detailed checks
                    errors = []
                    warnings = []

                    # Required field validation
                    if not first_name or not first_name.strip():
                        errors.append("First name is required")
                    elif len(first_name.strip()) < 2:
                        errors.append("First name must be at least 2 characters")

                    if not last_name or not last_name.strip():
                        errors.append("Last name is required")
                    elif len(last_name.strip()) < 2:
                        errors.append("Last name must be at least 2 characters")

                    if not emirates_id or not emirates_id.strip():
                        errors.append("Emirates ID is required")
                    else:
                        # Emirates ID format validation (784-XXXX-XXXXXXX-X)
                        clean_emirates_id = emirates_id.replace("-", "").replace(" ", "")
                        if not clean_emirates_id.startswith("784"):
                            errors.append("Emirates ID must start with 784")
                        elif len(clean_emirates_id) != 15:
                            errors.append("Emirates ID must be exactly 15 digits (784-XXXX-XXXXXXX-X)")
                        elif not clean_emirates_id.isdigit():
                            errors.append("Emirates ID must contain only digits and dashes")

                    # Email validation (enhanced)
                    if email:
                        email = email.strip()
                        if "@" not in email:
                            errors.append("Email must contain @ symbol")
                        elif "." not in email.split("@")[-1]:
                            errors.append("Email domain must contain a period (e.g. .com)")
                        elif len(email.split("@")[0]) < 1:
                            errors.append("Email must have a username before @")
                    else:
                        warnings.append("Email is optional but recommended for updates")

                    # Phone validation (enhanced)
                    if phone:
                        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                        if not clean_phone.isdigit():
                            errors.append("Phone number must contain only digits")
                        elif len(clean_phone) < 10:
                            errors.append("Phone number must be at least 10 digits")
                        elif not (clean_phone.startswith("971") or clean_phone.startswith("0")):
                            warnings.append("UAE phone numbers typically start with +971 or 0")

                    # Address validation
                    if address and len(address.strip()) < 10:
                        warnings.append("Address seems short - please provide full address for verification")

                    # Age validation from date of birth
                    if date_of_birth:
                        from datetime import date
                        today = date.today()
                        age = today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
                        if age < 18:
                            errors.append("Applicant must be at least 18 years old")
                        elif age > 100:
                            errors.append("Please check date of birth - age seems invalid")
                    else:
                        warnings.append("Date of birth is recommended for age verification")

                    # Income and eligibility checks
                    if monthly_income > 4000:
                        warnings.append("Monthly income above AED 4,000 may affect eligibility")

                    if has_existing_support:
                        warnings.append("Existing government support may affect your application")

                    # Display validation errors and warnings
                    if errors:
                        st.error("❌ **Please fix the following errors:**")
                        for error in errors:
                            st.error(f"   • {error}")

                    if warnings:
                        st.warning("⚠️ **Please note:**")
                        for warning in warnings:
                            st.warning(f"   • {warning}")

                    if not errors:  # Only proceed if no errors
                        if warnings:
                            st.info("✅ Form validation passed with warnings. You can proceed or review the warnings above.")
                        else:
                            st.success("✅ Form validation passed - all fields look good!")

                        st.divider()
                        # Prepare application data
                        applicant_data = {
                            "first_name": first_name,
                            "last_name": last_name,
                            "emirates_id": emirates_id,
                            "phone": phone,
                            "email": email,
                            "date_of_birth": date_of_birth.isoformat() if date_of_birth else None,
                            "address": address,
                            "application_type": application_type,
                            "urgency_level": urgency_level,
                            "monthly_income": monthly_income if monthly_income > 0 else None,
                            "employment_status": employment_status,
                            "bank_balance": bank_balance if bank_balance > 0 else None,
                            "family_size": family_size,
                            "has_existing_support": has_existing_support
                        }

                        if st.session_state.form_edit_mode:
                            # Handle application update
                            try:
                                # Update application data on backend
                                headers = get_auth_headers()
                                response = requests.put(
                                    f"{API_BASE_URL}/applications/{st.session_state.application_id}/update",
                                    json=applicant_data,
                                    headers=headers
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    st.session_state.form_edit_mode = False
                                    st.success("✅ Application updated successfully!")
                                    st.info("💡 Your changes have been saved. Note: You may need to re-upload documents if there were significant changes.")
                                    # Save updated form data to session state
                                    st.session_state.form_data = form_data
                                    # Save application context to URL for persistence
                                    save_session_to_url()
                                    st.rerun()
                                else:
                                    st.error(f"Failed to update application: {response.text}")
                            except Exception as e:
                                st.error(f"Error updating application: {str(e)}")
                                st.warning("Your changes were saved locally but not on the server. Please try again.")
                        else:
                            # Handle new application submission
                            if submit_application(applicant_data):
                                st.session_state.application_submitted = True
                                # Save application context to URL for persistence (both authenticated and anonymous)
                                save_session_to_url()
                                st.success("✅ Application submitted successfully!")
                                st.rerun()

        else:
            # Show submitted application summary
            st.success("✅ Application already submitted!")
            st.info(f"**Application ID**: {st.session_state.application_id}")

            # Show application summary if form data is available
            if st.session_state.form_data:
                with st.expander("📋 View Application Details", expanded=False):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("**Personal Information:**")
                        data = st.session_state.form_data
                        if data.get("first_name") or data.get("last_name"):
                            st.write(f"• Name: {data.get('first_name', '')} {data.get('last_name', '')}")
                        if data.get("emirates_id"):
                            st.write(f"• Emirates ID: {data.get('emirates_id')}")
                        if data.get("phone"):
                            st.write(f"• Phone: {data.get('phone')}")
                        if data.get("email"):
                            st.write(f"• Email: {data.get('email')}")

                    with col2:
                        st.write("**Application Details:**")
                        if data.get("application_type"):
                            app_type = "Financial Support" if data.get("application_type") == "financial_support" else "Economic Enablement"
                            st.write(f"• Type: {app_type}")
                        if data.get("urgency_level"):
                            st.write(f"• Urgency: {data.get('urgency_level').title()}")
                        if data.get("family_size"):
                            st.write(f"• Family Size: {data.get('family_size')}")
                        if data.get("employment_status"):
                            st.write(f"• Employment: {data.get('employment_status').title()}")

            # Add some spacing and navigation hints
            st.divider()
            st.info("📄 **Next Step**: Go to the **Documents** tab to upload required documents, then **Results** tab to track progress.")

    with tab3:
        st.header("📄 Document Upload")

        if not st.session_state.application_submitted or not st.session_state.application_id:
            st.warning("⚠️ Please submit your application first before uploading documents.")
            st.info("👈 Go to the **Application Form** tab to submit your application first.")
            if st.button("🔄 Reset Application State", help="Click if you think this is an error"):
                st.session_state.application_submitted = False
                st.session_state.application_id = None
                st.session_state.documents_uploaded = False
                st.session_state.processing_started = False
                st.rerun()

        else:
            # Show upload interface regardless of previous uploads
            if st.session_state.documents_uploaded:
                st.success("✅ Documents uploaded successfully!")
                st.info("📋 You can upload additional documents if needed.")

            # Document requirements guide
            with st.expander("📖 Required Documents Guide", expanded=False):
                st.markdown("""
                **Required Documents:**
                - 🆔 **Emirates ID** (Front & Back)
                - 🏦 **Bank Statements** (Last 3 months)
                - 💼 **Salary Certificate** (If employed)
                - 🏢 **Trade License** (If self-employed)

                **Additional Supporting Documents:**
                - 📊 Credit Report
                - 💰 Assets & Liabilities Statement
                - 🏠 Rental Agreement
                - 👨‍👩‍👧‍👦 Family Book
                - ⚡ Utility Bills
                """)

            st.markdown("### 📤 Upload Multiple Documents")
            st.markdown("""
            <div style="border: 2px dashed #ccc; border-radius: 10px; padding: 20px; text-align: center; margin: 10px 0;">
                <h4>📁 Drag and Drop Files Here</h4>
                <p>Or click below to browse files</p>
            </div>
            """, unsafe_allow_html=True)

            uploaded_files = st.file_uploader(
                "Select Files",
                accept_multiple_files=True,
                type=['pdf', 'jpg', 'jpeg', 'png', 'xlsx', 'docx'],
                help="💡 Supported formats: PDF, Images (JPG, PNG), Excel, Word documents. Max 10MB per file, 50MB total.",
                label_visibility="collapsed"
            )

            # File validation
            if uploaded_files:
                max_total_size = 50 * 1024 * 1024  # 50MB total
                max_file_size = 10 * 1024 * 1024   # 10MB per file

                # Filter out invalid files instead of rejecting all
                valid_files = []
                rejected_files = []

                for file in uploaded_files:
                    if file.size > max_file_size:
                        rejected_files.append(f"'{file.name}' ({file.size/1024/1024:.1f}MB) - exceeds 10MB limit")
                    else:
                        valid_files.append(file)

                # Check total size of valid files
                if valid_files:
                    total_valid_size = sum(file.size for file in valid_files)
                    if total_valid_size > max_total_size:
                        st.error(f"❌ Total size of valid files ({total_valid_size/1024/1024:.1f}MB) exceeds 50MB limit")
                        # Keep only files that fit within the limit
                        cumulative_size = 0
                        final_valid_files = []
                        for file in valid_files:
                            if cumulative_size + file.size <= max_total_size:
                                final_valid_files.append(file)
                                cumulative_size += file.size
                            else:
                                rejected_files.append(f"'{file.name}' - would exceed total size limit")
                        valid_files = final_valid_files

                # Show rejected files
                if rejected_files:
                    st.warning("⚠️ **Some files were rejected:**")
                    for rejected in rejected_files:
                        st.warning(f"   • {rejected}")

                # Update uploaded_files to only include valid files
                uploaded_files = valid_files if valid_files else None

            if uploaded_files:
                st.subheader("📋 Document Classification & Summary")

                # Show summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📄 Files Selected", len(uploaded_files))
                with col2:
                    total_size_mb = sum(file.size for file in uploaded_files) / (1024 * 1024)
                    st.metric("💾 Total Size", f"{total_size_mb:.1f} MB")
                with col3:
                    st.metric("📦 Status", "Ready to Classify")

                st.divider()

                document_types = []
                for i, file in enumerate(uploaded_files):
                    with st.container():
                        col1, col2, col3 = st.columns([2, 2, 1])
                        with col1:
                            file_size_mb = file.size / (1024 * 1024)
                            st.markdown(f"**📄 {file.name}**")
                            st.caption(f"Size: {file_size_mb:.2f} MB | Type: {file.type}")
                        with col2:
                            doc_type = st.selectbox(
                                "Document Type",
                                ["emirates_id", "bank_statement", "credit_report", "resume", "assets_liabilities",
                                 "salary_certificate", "trade_license", "passport", "visa", "utility_bill",
                                 "rental_agreement", "family_book", "medical_report", "insurance_policy", "other"],
                                key=f"doc_type_{i}",
                                format_func=lambda x: {
                                    "emirates_id": "🆔 Emirates ID",
                                    "bank_statement": "🏦 Bank Statement",
                                    "credit_report": "📊 Credit Report",
                                    "resume": "📄 Resume/CV",
                                    "assets_liabilities": "💰 Assets & Liabilities",
                                    "salary_certificate": "💼 Salary Certificate",
                                    "trade_license": "🏢 Trade License",
                                    "passport": "📘 Passport",
                                    "visa": "🛂 Visa",
                                    "utility_bill": "⚡ Utility Bill",
                                    "rental_agreement": "🏠 Rental Agreement",
                                    "family_book": "👨‍👩‍👧‍👦 Family Book",
                                    "medical_report": "🏥 Medical Report",
                                    "insurance_policy": "🛡️ Insurance Policy",
                                    "other": "📎 Other Document"
                                }.get(x, x)
                            )
                            document_types.append(doc_type)
                        with col3:
                            if file_size_mb > 10:
                                st.error("❌ Too large")
                            else:
                                st.success("✅ Valid")
                    st.divider()

                if st.button("📤 Upload Documents", type="primary"):
                    if upload_documents(uploaded_files, document_types):
                        st.session_state.documents_uploaded = True
                        # Save context to URL for persistence
                        save_session_to_url()
                        st.rerun()

            # Show uploaded documents summary after successful upload
            if st.session_state.documents_uploaded:
                with st.expander("📄 View Uploaded Documents", expanded=True):
                    if hasattr(st.session_state, 'uploaded_docs_summary'):
                        st.text(st.session_state.uploaded_docs_summary)
                    else:
                        st.info("Document summary will appear here after upload.")

            if not st.session_state.processing_started:
                st.info("Ready to start processing your application.")

                if st.button("🚀 Start Processing", type="primary"):
                    if start_processing():
                        st.session_state.processing_started = True
                        add_chat_message("assistant", "🔄 Your application is now being processed by our AI agents. This typically takes 2-5 minutes.")
                        # Save context to URL for persistence
                        save_session_to_url()
                        st.rerun()

            else:
                st.info("Processing in progress... Check the status in the sidebar.")

    with tab4:
        st.header("📊 Application Results")

        # Debug info for troubleshooting
        if st.session_state.application_id:
            st.info(f"🔍 **Application ID**: {st.session_state.application_id}")

            # Check processing status first
            status = get_processing_status()
            current_status = status.get("status", "unknown")

            if current_status != "unknown" and current_status != "error":
                # Show processing status
                st.subheader("📊 Processing Status")

                if current_status == "initialized":
                    st.info("🔄 **Status**: Initialized - Ready for processing")
                elif current_status == "processing":
                    st.warning("⏳ **Status**: Processing in progress...")
                    progress = status.get("progress", 0)
                    st.progress(progress / 100)
                    if status.get("current_stage"):
                        st.text(f"Current Stage: {status.get('current_stage')}")
                elif current_status == "completed":
                    st.success("✅ **Status**: Processing completed!")
                elif current_status == "failed":
                    st.error("❌ **Status**: Processing failed")
                else:
                    st.warning(f"⚠️ **Status**: {current_status}")

                st.divider()

            # Get detailed application information
            details = get_application_details()

            if "error" not in details:
                # Display application summary
                app_info = details.get("application", {})
                applicant_info = details.get("applicant", {})

                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("👤 Applicant Information")
                    if applicant_info:
                        st.text(f"Name: {applicant_info.get('name', 'N/A')}")
                        st.text(f"Emirates ID: {applicant_info.get('emirates_id', 'N/A')}")
                        st.text(f"Email: {applicant_info.get('email', 'N/A')}")
                        st.text(f"Phone: {applicant_info.get('phone', 'N/A')}")

                with col2:
                    st.subheader("📋 Application Status")
                    st.text(f"Type: {app_info.get('type', 'N/A').replace('_', ' ').title()}")
                    st.text(f"Status: {app_info.get('status', 'N/A').title()}")
                    st.text(f"Submitted: {app_info.get('submitted_at', 'N/A')[:19] if app_info.get('submitted_at') else 'N/A'}")

                # Display documents
                documents = details.get("documents", [])
                if documents:
                    st.subheader("📄 Uploaded Documents")
                    doc_df = pd.DataFrame(documents)
                    st.dataframe(doc_df[['type', 'filename', 'size', 'uploaded_at']], use_container_width=True)

                # Display processing results if available
                processing_status = details.get("processing_status", {})
                if processing_status.get("status") == "completed":
                    st.subheader("🎯 Processing Results")

                    result_data = processing_status.get("result", {})
                    if result_data:
                        # Display agent responses
                        agent_responses = result_data.get("agent_responses", [])
                        if agent_responses:
                            st.success("✅ **Processing Complete**")
                            for i, response in enumerate(agent_responses):
                                agent_name = response.get('agent', f'Agent {i+1}').replace('_', ' ').title()
                                with st.expander(f"🤖 {agent_name}: {response.get('message', 'No message')[:50]}..."):
                                    col1, col2 = st.columns([1, 3])
                                    with col1:
                                        if response.get('success'):
                                            st.success("✅ Success")
                                        else:
                                            st.error("❌ Failed")
                                    with col2:
                                        st.write(response.get('message', 'No message available'))

                        # Display final decision
                        if result_data.get('decision'):
                            decision = result_data['decision']
                            if decision.lower() == 'approved':
                                st.success(f"🎉 **Application Approved**")
                                if result_data.get('support_amount'):
                                    st.info(f"💰 **Monthly Support**: AED {result_data['support_amount']:,}")
                            elif decision.lower() == 'declined':
                                st.error("❌ **Application Declined**")
                            else:
                                st.warning("⏳ **Under Review**")

                            if result_data.get('message'):
                                st.write(result_data['message'])

                # Real-time status updates
                if st.button("🔄 Refresh Results"):
                    st.rerun()

            else:
                st.error(f"❌ Error loading application details: {details.get('error')}")

                # Show basic info from session state if available
                if st.session_state.form_data:
                    st.warning("📋 **Showing basic information from your session:**")
                    with st.expander("Application Information", expanded=True):
                        data = st.session_state.form_data
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write("**Personal Information:**")
                            if data.get("first_name") or data.get("last_name"):
                                st.write(f"• Name: {data.get('first_name', '')} {data.get('last_name', '')}")
                            if data.get("emirates_id"):
                                st.write(f"• Emirates ID: {data.get('emirates_id')}")

                        with col2:
                            st.write("**Application Details:**")
                            if data.get("application_type"):
                                app_type = "Financial Support" if data.get("application_type") == "financial_support" else "Economic Enablement"
                                st.write(f"• Type: {app_type}")
                            if data.get("urgency_level"):
                                st.write(f"• Urgency: {data.get('urgency_level').title()}")

                # Show instructions for troubleshooting
                st.info("💡 **Troubleshooting:**")
                st.write("1. Make sure you have submitted an application")
                st.write("2. Upload documents in the Documents tab")
                st.write("3. Start processing to see results")

        else:
            st.info("📋 **No application found.** Please submit an application first.")

            # Show helpful next steps
            st.markdown("""
            ### 🚀 **How to see results:**
            1. **📋 Go to Application Form** - Submit your application
            2. **📄 Go to Documents** - Upload required documents
            3. **🚀 Start Processing** - Begin application review
            4. **📊 Return here** - View your results

            ### 📈 **What you'll see here:**
            - ✅ Application processing status
            - 📊 Progress indicators
            - 🎯 Final decision (Approved/Declined)
            - 💰 Support amount (if approved)
            - 🤖 Detailed agent analysis
            """)

    # Profile and application history functionality removed for core MVP
    # These features can be re-enabled when multi-user authentication is fully deployed

if __name__ == "__main__":
    # Add some custom CSS
    st.markdown("""
    <style>
    .stApp {
        max-width: 1200px;
    }
    .chat-message {
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
    .user-message {
        background-color: #e3f2fd;
        margin-left: 20px;
    }
    .assistant-message {
        background-color: #f5f5f5;
        margin-right: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    main()
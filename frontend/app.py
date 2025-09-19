import streamlit as st
import requests
import time
import json
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd

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

# Initialize session state
if "application_id" not in st.session_state:
    st.session_state.application_id = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "application_submitted" not in st.session_state:
    st.session_state.application_submitted = False
if "documents_uploaded" not in st.session_state:
    st.session_state.documents_uploaded = False
if "processing_started" not in st.session_state:
    st.session_state.processing_started = False

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
        response = requests.post(
            f"{API_BASE_URL}/applications/submit",
            json=applicant_data
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

        response = requests.post(
            f"{API_BASE_URL}/applications/{st.session_state.application_id}/documents/upload",
            json=files_info
        )

        if response.status_code == 200:
            result = response.json()
            add_chat_message("assistant", f"✅ Uploaded {result['total_documents']} documents successfully!")
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
        response = requests.post(
            f"{API_BASE_URL}/applications/{st.session_state.application_id}/process"
        )

        if response.status_code == 200:
            result = response.json()
            add_chat_message("assistant", "🔄 Application processing started! This may take a few minutes.")
            return True
        else:
            st.error(f"Failed to start processing: {response.text}")
            return False

    except Exception as e:
        st.error(f"Error starting processing: {str(e)}")
        return False

def get_processing_status() -> Dict[str, Any]:
    """Get current processing status"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/applications/{st.session_state.application_id}/status"
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "unknown", "error": response.text}

    except Exception as e:
        return {"status": "error", "error": str(e)}

def get_application_details() -> Dict[str, Any]:
    """Get detailed application information"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/applications/{st.session_state.application_id}/details"
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}

    except Exception as e:
        return {"error": str(e)}

# Main application UI

def main():
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
    tab1, tab2, tab3, tab4 = st.tabs(["💬 Application Chat", "📋 Application Form", "📄 Documents", "📊 Results"])

    with tab1:
        st.header("💬 Interactive Application Assistant")

        # Chat interface
        chat_container = st.container()

        with chat_container:
            display_chat_messages()

        # Chat input
        user_input = st.chat_input("Ask me anything about your application...")

        if user_input:
            add_chat_message("user", user_input)

            # Get AI-powered response from backend
            try:
                # Create query string for the chat API
                import urllib.parse
                query_params = f"message={urllib.parse.quote(user_input)}"
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
                if "document" in user_input.lower():
                    response = "📄 I can help with documents! You'll need Emirates ID, bank statements, and income proof. Please try again when the AI service is available for more detailed assistance."
                elif "eligibility" in user_input.lower():
                    response = "✅ Basic eligibility includes UAE residency and monthly income below AED 4,000. Please try again when the AI service is available for detailed criteria."
                elif any(word in user_input.lower() for word in ["hello", "hi", "hey"]):
                    response = "👋 Hello! I'm your AI Social Support Assistant. The AI service is temporarily slow, but I'm here to help with basic questions."
                else:
                    response = "I'm here to help! The AI service is temporarily unavailable, but I can provide basic information about documents, eligibility, or the application process."

            add_chat_message("assistant", response)
            st.rerun()

    with tab2:
        st.header("📋 Application Form")

        if not st.session_state.application_submitted:
            with st.form("application_form"):
                st.subheader("Personal Information")

                col1, col2 = st.columns(2)

                with col1:
                    first_name = st.text_input("First Name *", placeholder="Enter your first name")
                    emirates_id = st.text_input("Emirates ID *", placeholder="784-XXXX-XXXXXXX-X")
                    phone = st.text_input("Phone Number", placeholder="+971 XX XXX XXXX")
                    family_size = st.number_input("Family Size", min_value=1, value=1)

                with col2:
                    last_name = st.text_input("Last Name *", placeholder="Enter your last name")
                    email = st.text_input("Email", placeholder="your.email@example.com")
                    date_of_birth = st.date_input("Date of Birth")
                    urgency_level = st.selectbox("Urgency Level", ["normal", "high", "critical"])

                address = st.text_area("Address", placeholder="Enter your full address")

                st.subheader("Application Details")
                application_type = st.selectbox(
                    "Application Type",
                    ["financial_support", "economic_enablement"],
                    format_func=lambda x: "Financial Support" if x == "financial_support" else "Economic Enablement"
                )

                # Additional financial information
                st.subheader("Financial Information (Optional)")
                col3, col4 = st.columns(2)

                with col3:
                    monthly_income = st.number_input("Monthly Income (AED)", min_value=0, value=0)
                    employment_status = st.selectbox("Employment Status",
                        ["employed", "unemployed", "self_employed", "student", "retired"])

                with col4:
                    bank_balance = st.number_input("Current Bank Balance (AED)", min_value=0, value=0)
                    has_existing_support = st.checkbox("Currently receiving government support")

                submitted = st.form_submit_button("Submit Application", type="primary")

                if submitted:
                    # Enhanced validation
                    errors = []

                    # Required field validation
                    if not first_name or not first_name.strip():
                        errors.append("First name is required")
                    if not last_name or not last_name.strip():
                        errors.append("Last name is required")
                    if not emirates_id or not emirates_id.strip():
                        errors.append("Emirates ID is required")

                    # Emirates ID format validation
                    if emirates_id and len(emirates_id.replace("-", "").replace(" ", "")) < 15:
                        errors.append("Emirates ID format appears invalid (should be 784-XXXX-XXXXXXX-X)")

                    # Email validation
                    if email and "@" not in email:
                        errors.append("Please enter a valid email address")

                    # Phone validation
                    if phone and not phone.replace("+", "").replace(" ", "").replace("-", "").isdigit():
                        errors.append("Please enter a valid phone number")

                    # Display validation errors
                    if errors:
                        for error in errors:
                            st.error(f"❌ {error}")
                    else:
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

                        if submit_application(applicant_data):
                            st.session_state.application_submitted = True
                            st.success("✅ Application submitted successfully!")
                            st.rerun()

        else:
            st.success("✅ Application already submitted!")
            st.info(f"Application ID: {st.session_state.application_id}")

    with tab3:
        st.header("📄 Document Upload")

        if not st.session_state.application_submitted:
            st.warning("Please submit your application first before uploading documents.")

        elif not st.session_state.documents_uploaded:
            st.info("Please upload the required documents for your application.")

            uploaded_files = st.file_uploader(
                "Select Documents",
                accept_multiple_files=True,
                type=['pdf', 'jpg', 'jpeg', 'png', 'xlsx', 'docx'],
                help="Supported formats: PDF, Images (JPG, PNG), Excel, Word documents. Max 10MB per file."
            )

            # File validation
            if uploaded_files:
                total_size = sum(file.size for file in uploaded_files)
                max_total_size = 50 * 1024 * 1024  # 50MB total
                max_file_size = 10 * 1024 * 1024   # 10MB per file

                if total_size > max_total_size:
                    st.error(f"❌ Total file size ({total_size/1024/1024:.1f}MB) exceeds 50MB limit")
                    uploaded_files = None

                for file in uploaded_files:
                    if file.size > max_file_size:
                        st.error(f"❌ File '{file.name}' ({file.size/1024/1024:.1f}MB) exceeds 10MB limit")
                        uploaded_files = None
                        break

            if uploaded_files:
                st.subheader("Document Classification")

                document_types = []
                for i, file in enumerate(uploaded_files):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.text(f"📄 {file.name}")
                    with col2:
                        doc_type = st.selectbox(
                            "Type",
                            ["emirates_id", "bank_statement", "credit_report", "resume", "assets_liabilities"],
                            key=f"doc_type_{i}",
                            format_func=lambda x: {
                                "emirates_id": "Emirates ID",
                                "bank_statement": "Bank Statement",
                                "credit_report": "Credit Report",
                                "resume": "Resume/CV",
                                "assets_liabilities": "Assets & Liabilities"
                            }.get(x, x)
                        )
                        document_types.append(doc_type)

                if st.button("📤 Upload Documents", type="primary"):
                    if upload_documents(uploaded_files, document_types):
                        st.session_state.documents_uploaded = True
                        st.rerun()

        else:
            st.success("✅ Documents uploaded successfully!")

            if not st.session_state.processing_started:
                st.info("Ready to start processing your application.")

                if st.button("🚀 Start Processing", type="primary"):
                    if start_processing():
                        st.session_state.processing_started = True
                        add_chat_message("assistant", "🔄 Your application is now being processed by our AI agents. This typically takes 2-5 minutes.")
                        st.rerun()

            else:
                st.info("Processing in progress... Check the status in the sidebar.")

    with tab4:
        st.header("📊 Application Results")

        if st.session_state.application_id:
            # Get application details
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
                st.error(f"Error loading application details: {details.get('error')}")

        else:
            st.info("Submit an application to see results here.")

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
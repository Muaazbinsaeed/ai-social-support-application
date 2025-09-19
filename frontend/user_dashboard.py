"""
User dashboard components for profile management and application history
"""

import streamlit as st
import requests
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
import json

# API URLs
AUTH_API_URL = "http://localhost:8002"

def get_auth_headers() -> Dict[str, str]:
    """Get authentication headers"""
    if st.session_state.user_token:
        return {"Authorization": f"Bearer {st.session_state.user_token}"}
    return {}

def get_user_profile() -> Dict[str, Any]:
    """Get user profile data"""
    try:
        headers = get_auth_headers()
        response = requests.get(f"{AUTH_API_URL}/users/profile", headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return {}
    except Exception as e:
        st.error(f"Failed to load profile: {e}")
        return {}

def update_user_profile(profile_data: Dict[str, Any]) -> bool:
    """Update user profile"""
    try:
        headers = get_auth_headers()
        response = requests.put(
            f"{AUTH_API_URL}/users/profile",
            headers=headers,
            json=profile_data,
            timeout=10
        )

        if response.status_code == 200:
            return True
        else:
            error_data = response.json()
            st.error(f"Failed to update profile: {error_data.get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        st.error(f"Failed to update profile: {e}")
        return False

def get_user_applications() -> List[Dict[str, Any]]:
    """Get user applications"""
    try:
        headers = get_auth_headers()
        response = requests.get(f"{AUTH_API_URL}/users/applications", headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return data.get("applications", [])
        else:
            return []
    except Exception as e:
        st.error(f"Failed to load applications: {e}")
        return []

def get_user_documents() -> List[Dict[str, Any]]:
    """Get user documents"""
    try:
        headers = get_auth_headers()
        response = requests.get(f"{AUTH_API_URL}/users/documents", headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return data.get("documents", [])
        else:
            return []
    except Exception as e:
        st.error(f"Failed to load documents: {e}")
        return []

def show_user_profile():
    """Display and edit user profile"""
    st.header("👤 User Profile")

    try:
        # Load current profile
        profile = get_user_profile()

        if not profile:
            st.warning("Profile not found. Please update your information.")
            profile = {}

    except Exception as e:
        st.error(f"Error loading profile: {e}")
        st.info("You can still update your profile information below.")
        profile = {}

    # Profile form
    try:
        with st.form("profile_form"):
            st.info("👤 **Profile Guide**: All fields are optional. Complete your profile to save time on future applications.")
            st.subheader("Personal Information")

            col1, col2 = st.columns(2)

            with col1:
                phone = st.text_input(
                    "Phone Number (Optional)",
                    value=profile.get("phone", ""),
                    placeholder="+971 XX XXX XXXX"
                )
                emirates_id = st.text_input(
                    "Emirates ID (Optional)",
                    value=profile.get("emirates_id", ""),
                    placeholder="784-XXXX-XXXXXXX-X"
                )
                # Safe family size conversion
                try:
                    family_size_value = int(profile.get("family_size", 1)) if profile.get("family_size") else 1
                except (ValueError, TypeError):
                    family_size_value = 1

                family_size = st.number_input(
                    "Family Size (Optional)",
                    min_value=1,
                    value=family_size_value
                )

            with col2:
                # Safe date parsing
                date_of_birth_value = None
                if profile.get("date_of_birth"):
                    try:
                        date_of_birth_value = datetime.fromisoformat(profile["date_of_birth"]).date()
                    except (ValueError, TypeError):
                        date_of_birth_value = None

                date_of_birth = st.date_input(
                    "Date of Birth (Optional)",
                    value=date_of_birth_value,
                    min_value=datetime(1900, 1, 1).date(),
                    max_value=datetime.now().date()
                )

                # Safe employment status selection
                employment_options = ["employed", "unemployed", "self_employed", "student", "retired"]
                current_employment = profile.get("employment_status", "employed")

                # Find index safely, default to 0 (employed) if not found
                try:
                    employment_index = employment_options.index(current_employment) if current_employment in employment_options else 0
                except (ValueError, TypeError):
                    employment_index = 0

                employment_status = st.selectbox(
                    "Employment Status (Optional)",
                    employment_options,
                    index=employment_index
                )

                # Safe monthly income conversion
                try:
                    monthly_income_value = int(profile.get("monthly_income", 0)) if profile.get("monthly_income") else 0
                except (ValueError, TypeError):
                    monthly_income_value = 0

                monthly_income = st.number_input(
                    "Monthly Income (AED) - Optional",
                    min_value=0,
                    value=monthly_income_value
                )

        address = st.text_area(
            "Address (Optional)",
            value=profile.get("address", ""),
            placeholder="Enter your full address"
        )

        st.subheader("Financial Information (Optional)")

        col3, col4 = st.columns(2)

        with col3:
            # Safe bank balance conversion
            try:
                bank_balance_value = int(profile.get("bank_balance", 0)) if profile.get("bank_balance") else 0
            except (ValueError, TypeError):
                bank_balance_value = 0

            bank_balance = st.number_input(
                "Current Bank Balance (AED) - Optional",
                min_value=0,
                value=bank_balance_value
            )

        with col4:
            has_existing_support = st.checkbox(
                "Currently receiving government support (Optional)",
                value=profile.get("has_existing_support", False)
            )

        submitted = st.form_submit_button("Update Profile", type="primary")

        if submitted:
            profile_data = {
                "phone": phone if phone else None,
                "emirates_id": emirates_id if emirates_id else None,
                "date_of_birth": date_of_birth.isoformat() if date_of_birth else None,
                "address": address if address else None,
                "family_size": family_size,
                "employment_status": employment_status,
                "monthly_income": float(monthly_income) if monthly_income > 0 else None,
                "bank_balance": float(bank_balance) if bank_balance > 0 else None,
                "has_existing_support": has_existing_support
            }

            if update_user_profile(profile_data):
                st.success("✅ Profile updated successfully!")
                st.rerun()

    except Exception as e:
        st.error(f"Error in profile form: {e}")
        st.info("Please refresh the page and try again.")

def show_application_history():
    """Display user application history"""
    st.header("📋 Application History")

    applications = get_user_applications()

    if not applications:
        st.info("No applications found. Submit your first application to see it here.")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Applications", len(applications))

    with col2:
        approved = len([app for app in applications if app.get("decision") == "approved"])
        st.metric("Approved", approved, delta=f"{approved/len(applications)*100:.1f}%" if applications else "0%")

    with col3:
        pending = len([app for app in applications if app.get("status") in ["submitted", "processing"]])
        st.metric("Pending", pending)

    with col4:
        total_support = sum([app.get("support_amount", 0) for app in applications if app.get("support_amount")])
        st.metric("Total Support (AED)", f"{total_support:,.0f}")

    st.divider()

    # Applications table
    if applications:
        df_data = []
        for app in applications:
            df_data.append({
                "ID": app["id"],
                "Type": app["application_type"].replace("_", " ").title(),
                "Status": app["status"].title(),
                "Decision": app.get("decision", "Pending").title(),
                "Support (AED)": f"{app.get('support_amount', 0):,.0f}" if app.get("support_amount") else "N/A",
                "Submitted": datetime.fromisoformat(app["submitted_at"]).strftime("%Y-%m-%d"),
                "Urgency": app.get("urgency_level", "Normal").title()
            })

        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)

        # Detailed view
        st.subheader("Application Details")
        selected_id = st.selectbox(
            "Select Application",
            options=[app["id"] for app in applications],
            format_func=lambda x: f"Application #{x}"
        )

        if selected_id:
            selected_app = next((app for app in applications if app["id"] == selected_id), None)
            if selected_app:
                show_application_details(selected_app)

def show_application_details(application: Dict[str, Any]):
    """Show detailed application information"""
    with st.expander(f"📄 Application #{application['id']} Details", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Basic Information:**")
            st.write(f"Type: {application['application_type'].replace('_', ' ').title()}")
            st.write(f"Status: {application['status'].title()}")
            st.write(f"Urgency: {application.get('urgency_level', 'Normal').title()}")
            st.write(f"Submitted: {datetime.fromisoformat(application['submitted_at']).strftime('%Y-%m-%d %H:%M')}")

        with col2:
            st.write("**Decision Information:**")
            decision = application.get("decision", "Pending")
            if decision.lower() == "approved":
                st.success(f"✅ {decision.title()}")
            elif decision.lower() == "declined":
                st.error(f"❌ {decision.title()}")
            else:
                st.warning(f"⏳ {decision.title()}")

            if application.get("support_amount"):
                st.write(f"Support Amount: AED {application['support_amount']:,.0f}")

            if application.get("decision_message"):
                st.write(f"Message: {application['decision_message']}")

        # Applicant data
        if application.get("applicant_data"):
            st.write("**Applicant Data:**")
            applicant_data = application["applicant_data"]
            if isinstance(applicant_data, str):
                try:
                    applicant_data = json.loads(applicant_data)
                except:
                    pass

            if isinstance(applicant_data, dict):
                # Show key information
                key_fields = ["first_name", "last_name", "email", "phone", "monthly_income", "employment_status"]
                for field in key_fields:
                    if field in applicant_data and applicant_data[field]:
                        st.write(f"{field.replace('_', ' ').title()}: {applicant_data[field]}")

def show_document_library():
    """Display user document library"""
    st.header("📄 Document Library")

    documents = get_user_documents()

    if not documents:
        st.info("No documents found. Upload documents through your applications to see them here.")
        return

    # Summary
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Documents", len(documents))

    with col2:
        total_size = sum([doc.get("file_size", 0) for doc in documents])
        st.metric("Total Size", f"{total_size / (1024*1024):.1f} MB")

    with col3:
        doc_types = len(set([doc.get("document_type") for doc in documents]))
        st.metric("Document Types", doc_types)

    st.divider()

    # Documents table
    if documents:
        df_data = []
        for doc in documents:
            df_data.append({
                "ID": doc["id"],
                "Filename": doc["filename"],
                "Type": doc["document_type"].replace("_", " ").title(),
                "Size (KB)": f"{doc.get('file_size', 0) / 1024:.1f}",
                "Application": doc.get("application_id", "N/A"),
                "Uploaded": datetime.fromisoformat(doc["upload_date"]).strftime("%Y-%m-%d %H:%M")
            })

        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)

        # Document type breakdown
        st.subheader("📊 Document Types")
        doc_type_counts = {}
        for doc in documents:
            doc_type = doc["document_type"].replace("_", " ").title()
            doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1

        type_df = pd.DataFrame(list(doc_type_counts.items()), columns=["Type", "Count"])
        st.bar_chart(type_df.set_index("Type"))

def show_user_dashboard():
    """Main user dashboard"""
    st.title("📊 User Dashboard")

    if st.session_state.logged_in == "anonymous":
        st.warning("⚠️ You are using the app anonymously. Create an account to access the dashboard.")
        return

    if not st.session_state.logged_in or not st.session_state.user_info:
        st.error("Please log in to access the dashboard.")
        return

    # Workflow guidance
    st.info("💡 **Tip**: As a registered user, you can manage your profile and applications here. To submit new applications, use the 'Application Form' tab above.")

    # Dashboard tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "👤 Profile", "📋 Applications", "📄 Documents"])

    with tab1:
        # Overview
        st.header("📊 Dashboard Overview")

        user = st.session_state.user_info
        st.markdown(f"### Welcome back, {user.get('full_name', 'User')}! 👋")

        # Quick stats
        col1, col2 = st.columns(2)

        with col1:
            applications = get_user_applications()
            st.metric("Total Applications", len(applications))

            if applications:
                recent_app = max(applications, key=lambda x: x["submitted_at"])
                st.write(f"**Most Recent:** Application #{recent_app['id']}")
                st.write(f"Status: {recent_app['status'].title()}")

        with col2:
            documents = get_user_documents()
            st.metric("Total Documents", len(documents))

            if documents:
                total_size = sum([doc.get("file_size", 0) for doc in documents])
                st.write(f"**Total Size:** {total_size / (1024*1024):.1f} MB")

        # Recent activity
        if applications:
            st.subheader("🕒 Recent Activity")
            recent_apps = sorted(applications, key=lambda x: x["submitted_at"], reverse=True)[:3]

            for app in recent_apps:
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.write(f"**Application #{app['id']}** - {app['application_type'].replace('_', ' ').title()}")
                    with col2:
                        status = app['status'].title()
                        if status == "Submitted":
                            st.info(status)
                        elif status == "Processing":
                            st.warning(status)
                        elif status == "Approved":
                            st.success(status)
                        else:
                            st.error(status)
                    with col3:
                        st.caption(datetime.fromisoformat(app["submitted_at"]).strftime("%Y-%m-%d"))

    with tab2:
        show_user_profile()

    with tab3:
        show_application_history()

    with tab4:
        show_document_library()
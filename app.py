import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# Set page config
st.set_page_config(
    page_title="WhatsApp Failure Analytics",
    page_icon="📊",
    layout="wide"
)

st.title("📊 WhatsApp Failure Analysis Dashboard")

# File uploader
uploaded_file = st.file_uploader("Upload your WhatsApp report (CSV)", type=["csv"])

def load_data(file):
    if file is not None:
        try:
            df = pd.read_csv(file, dtype={'phone_number': str})  # Force phone_number as string
            
            # Standardize column names
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
            
            # Clean up phone_number formatting early
            if 'phone_number' in df.columns:
                df['phone_number'] = df['phone_number'].astype(str).str.extract(r'(\d+)')[0]
            
            # Convert to datetime if available
            if all(col in df.columns for col in ['sent_date', 'sent_time']):
                df['datetime'] = pd.to_datetime(
                    df['sent_date'].astype(str) + ' ' + df['sent_time'].astype(str),
                    errors='coerce'
                )
            
            return df
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")
    return None

def analyze_failures(df):
    """Identify failed messages and show exact reasons"""
    if 'delivery_status' not in df.columns:
        st.warning("Delivery Status column not found")
        return pd.DataFrame()
    
    # Filter failed messages (anything not SUCCESS/DELIVERED/READ)
    success_statuses = ['SUCCESS', 'DELIVERED', 'READ']
    failed = df[~df['delivery_status'].str.upper().isin(success_statuses)].copy()
    
    if not failed.empty:
        # Use existing phone_number column if available
        if 'phone_number' in df.columns:
            failed['phone_number'] = failed['phone_number'].astype(str).str.extract(r'(\d+)')[0]
        else:
            st.warning("Phone Number column not found in the data")
        
        # Use exact delivery description
        failed['failure_reason'] = failed.get('delivery_description', 'No reason provided')
    
    return failed

# Main analysis flow
if uploaded_file:
    df = load_data(uploaded_file)
    
    if df is not None:
        st.header("1. Campaign Overview")
        
        # Calculate metrics
        total_messages = len(df)
        success = len(df[df['delivery_status'].str.upper().isin(['SUCCESS', 'DELIVERED', 'READ'])])
        failed = total_messages - success
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Messages", total_messages)
        col2.metric("Successful", success, f"{success/total_messages*100:.1f}%")
        col3.metric("Failed", failed, f"{failed/total_messages*100:.1f}%", delta_color="inverse")
        
        # Pie chart
        fig = px.pie(
            names=['Success', 'Failure'],
            values=[success, failed],
            hole=0.4,
            color_discrete_sequence=['#4CAF50', '#F44336']
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.header("2. Detailed Failure Analysis")
        failed_messages = analyze_failures(df)
        
        if not failed_messages.empty:
            # Show exact failure reasons
            st.subheader("All Failure Reasons (Raw from Report)")
            
            # Group by failure reason
            failure_counts = failed_messages['failure_reason'].value_counts().reset_index()
            failure_counts.columns = ['Failure Reason', 'Count']
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.dataframe(
                    failure_counts,
                    use_container_width=True,
                    height=400
                )
            
            with col2:
                st.bar_chart(
                    failure_counts.set_index('Failure Reason'),
                    use_container_width=True
                )
            
            # Show all failed messages
            st.subheader("Failed Messages Details")
            st.dataframe(
                failed_messages[['phone_number', 'delivery_status', 'failure_reason']]
                .rename(columns={
                    'phone_number': 'Phone Number',
                    'delivery_status': 'Status',
                    'failure_reason': 'Failure Reason'
                }),
                use_container_width=True,
                height=400
            )
            
            # Download option
            csv = failed_messages.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Failed Messages",
                data=csv,
                file_name="failed_messages.csv",
                mime="text/csv"
            )
            
            # ✅ Filter by failure reason and extract contacts
            st.subheader("📥 Extract Contacts by Failure Reason")

            selected_reason = st.selectbox(
                "Select a Failure Reason to extract contacts",
                options=failure_counts['Failure Reason'].tolist()
            )

            filtered_contacts = failed_messages[failed_messages['failure_reason'] == selected_reason]

            if not filtered_contacts.empty:
                st.write(f"Showing {len(filtered_contacts)} contacts with reason: **{selected_reason}**")
                st.dataframe(
                    filtered_contacts[['phone_number', 'delivery_status', 'failure_reason']]
                    .rename(columns={
                        'phone_number': 'Phone Number',
                        'delivery_status': 'Status',
                        'failure_reason': 'Failure Reason'
                    }),
                    use_container_width=True
                )
                
                # Download filtered contacts
                contact_csv = filtered_contacts[['phone_number']].drop_duplicates().to_csv(index=False).encode('utf-8')
                st.download_button(
                    label=f"📥 Download Contacts with '{selected_reason}'",
                    data=contact_csv,
                    file_name=f"{selected_reason.replace(' ', '_')}_contacts.csv",
                    mime="text/csv"
                )
        else:
            st.success("✅ No failed messages found in this report")
        
        st.header("3. Phone Number Validation")
        if 'phone_number' in df.columns:
            # Clean and validate phone numbers
            df['phone_clean'] = df['phone_number'].astype(str).str.replace(r'\D', '', regex=True)
            df['is_valid'] = df['phone_clean'].apply(lambda x: len(x) >= 10)
            
            valid_count = df['is_valid'].sum()
            invalid_count = len(df) - valid_count
            
            col1, col2 = st.columns(2)
            col1.metric("Valid Numbers", valid_count, f"{valid_count/len(df)*100:.1f}%")
            col2.metric("Invalid Numbers", invalid_count, f"{invalid_count/len(df)*100:.1f}%", 
                       delta_color="inverse")
            
            # Show invalid numbers
            if invalid_count > 0:
                st.subheader("Invalid Phone Numbers (<10 digits)")
                invalid_numbers = df[~df['is_valid']][['phone_number', 'phone_clean']]
                st.dataframe(
                    invalid_numbers,
                    column_config={
                        "phone_number": "Original Number",
                        "phone_clean": "Cleaned Number"
                    },
                    use_container_width=True
                )
                # WhatsApp alert template
            st.subheader("📩 WhatsApp Alert Template")
            st.markdown("""
**Subject:** Action Required: Update Your Phone Number for WhatsApp Alerts

**Dear Intern,**

We tried to reach you on WhatsApp, but it seems your number may be invalid or not linked to a WhatsApp account.

To continue receiving important updates and notifications, please verify or update your phone number.

👉 [Update Phone Number Link]

Thank you,  
**Team Summer of AI 2025**
    """)
    
    # Download invalid numbers CSV
            invalid_csv = invalid_numbers.to_csv(index=False).encode('utf-8')
            st.download_button(
            label="📤 Download Invalid Phone Numbers",
            data=invalid_csv,
            file_name="invalid_numbers.csv",
            mime="text/csv"
            )
        else:
            st.warning("Phone Number column not found in the data")

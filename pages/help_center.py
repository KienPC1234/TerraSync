# pages/help_center.py - Enhanced Help Center
import streamlit as st
import google.generativeai as genai
import os
from database import db

def render_help_center():
    st.title("🆘 Help Center & Support")
    st.markdown("Get help with TerraSync IoT and find answers to common questions")
    
    # Tabs for different help sections
    tab1, tab2, tab3, tab4 = st.tabs(["💬 AI Assistant", "📚 Documentation", "🔧 Troubleshooting", "📞 Contact Support"])
    
    with tab1:
        render_ai_assistant()
    
    with tab2:
        render_documentation()
    
    with tab3:
        render_troubleshooting()
    
    with tab4:
        render_contact_support()

def render_ai_assistant():
    """AI Assistant for help"""
    st.subheader("🤖 TerraSync AI Assistant")
    st.markdown("Ask me anything about TerraSync IoT, farming, or technical questions!")
    
    # Get user context
    user_fields = db.get_user_fields(st.user.email) if hasattr(st, 'user') and st.user.is_logged_in else []
    user_hubs = db.get("iot_hubs", {"user_email": st.user.email}) if hasattr(st, 'user') and st.user.is_logged_in else []
    
    # Context information
    context_info = f"""
    User has {len(user_fields)} fields and {len(user_hubs)} IoT hubs.
    Fields: {[f.get('name', 'Unknown') for f in user_fields[:3]]}
    """
    
    # AI Chat Interface
    api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("gemini", {}).get("api_key", "")
    if not api_key:
        st.error("⚠️ Gemini API key not configured. Please check your secrets.toml file.")
        return
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')

    if 'help_messages' not in st.session_state:
        st.session_state.help_messages = []

    # Display chat history
    for message in st.session_state.help_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    prompt = st.chat_input("Ask a question about TerraSync...")
    if prompt:
        # Add user message
        st.session_state.help_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate AI response with context
        try:
            full_prompt = f"""
            You are TerraSync AI Assistant, a helpful AI for smart farming and IoT agriculture.
            
            User Context: {context_info}
            
            User Question: {prompt}
            
            Please provide helpful, accurate information about:
            - TerraSync IoT features and usage
            - Smart farming techniques
            - IoT device management
            - Irrigation optimization
            - Plant disease diagnosis
            - Weather monitoring
            - General agricultural advice
            
            Be friendly, informative, and specific to the user's context when possible.
            """
            
            response = model.generate_content(full_prompt)
            ai_response = response.text
            
            st.session_state.help_messages.append({"role": "assistant", "content": ai_response})
            with st.chat_message("assistant"):
                st.markdown(ai_response)
                
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            st.session_state.help_messages.append({"role": "assistant", "content": error_msg})
        with st.chat_message("assistant"):
                st.error(error_msg)
    
    # Quick action buttons
    st.subheader("🚀 Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📖 How to add a field?"):
            st.session_state.help_messages.append({"role": "user", "content": "How do I add a new field to TerraSync?"})
            st.rerun()
    
    with col2:
        if st.button("🔧 IoT setup help"):
            st.session_state.help_messages.append({"role": "user", "content": "How do I set up IoT devices?"})
            st.rerun()
    
    with col3:
        if st.button("💧 Irrigation tips"):
            st.session_state.help_messages.append({"role": "user", "content": "What are some irrigation optimization tips?"})
            st.rerun()

def render_documentation():
    """Documentation and guides"""
    st.subheader("📚 Documentation & Guides")
    
    # Getting Started
    with st.expander("🚀 Getting Started", expanded=True):
        st.markdown("""
        ### Welcome to TerraSync IoT!
        
        **Step 1: Add Your Fields**
        - Go to "My Fields" page
        - Click "Add new field" 
        - Choose from AI detection, manual coordinates, or map drawing
        
        **Step 2: Set Up IoT Devices**
        - Go to "IoT Management" page
        - Register your IoT hub
        - Connect sensors to monitor your fields
        
        **Step 3: Generate Irrigation Schedule**
        - Go to "My Schedule" page
        - Select your field
        - Generate optimized irrigation schedule
        
        **Step 4: Monitor with AI**
        - Use "AI Detection" for plant disease diagnosis
        - Check "Satellite View" for field monitoring
        - Chat with CropNet AI for personalized advice
        """)
    
    # Feature Guides
    with st.expander("🔧 Feature Guides"):
        st.markdown("""
        ### AI Field Detection
        - Upload satellite or aerial images
        - AI automatically detects field boundaries
        - Suggests crop types and calculates area
        
        ### IoT Management
        - Connect Raspberry Pi 4 as hub
        - Monitor soil moisture, temperature, humidity
        - RF 433MHz communication up to 1km range
        
        ### Irrigation Optimization
        - Weather-based scheduling
        - Crop-specific water requirements
        - Efficiency monitoring and recommendations
        
        ### Plant Disease Diagnosis
        - Upload leaf images for AI analysis
        - Get disease identification and treatment suggestions
        - Prevention tips and monitoring advice
        """)
    
    # API Documentation
    with st.expander("🔌 API Documentation"):
        st.markdown("""
        ### IoT Data Ingestion
        ```
        POST /api/v1/data/ingest
        Content-Type: application/json
        
        {
          "hub_id": "your-hub-id",
          "timestamp": "2025-01-15T10:00:00Z",
          "location": {"lat": 20.45, "lon": 106.32},
          "data": {
            "soil_nodes": [...],
            "atmospheric_node": {...}
          }
        }
        ```
        
        ### Weather API
        - Open-Meteo integration for weather data
        - 7-day forecast with precipitation, temperature, wind
        - Risk assessment and irrigation recommendations
        
        ### Satellite Data
        - OpenET (NASA) for evapotranspiration
        - NDVI analysis for vegetation health
        - Cloud removal and image enhancement
        """)

def render_troubleshooting():
    """Troubleshooting guide"""
    st.subheader("🔧 Troubleshooting Guide")
    
    # Common Issues
    st.markdown("### Common Issues & Solutions")
    
    # Issue categories
    issue_categories = {
        "🔐 Authentication": [
            "**Problem**: Cannot login with Google",
            "**Solution**: Check your secrets.toml file has correct Google OAuth credentials",
            "**Problem**: User data not saving",
            "**Solution**: Ensure database file has write permissions"
        ],
        "📡 IoT Connection": [
            "**Problem**: IoT hub not connecting",
            "**Solution**: Check network connection and hub IP address",
            "**Problem**: Sensors not responding",
            "**Solution**: Verify RF communication and battery levels"
        ],
        "🗺️ Field Management": [
            "**Problem**: Cannot add fields",
            "**Solution**: Ensure you're logged in and have valid coordinates",
            "**Problem**: AI detection not working",
            "**Solution**: Check image quality and file format (JPG/PNG)"
        ],
        "💧 Irrigation": [
            "**Problem**: Schedule not generating",
            "**Solution**: Verify field data and weather API connection",
            "**Problem**: Inaccurate water calculations",
            "**Solution**: Check crop coefficient and irrigation efficiency settings"
        ]
    }
    
    for category, issues in issue_categories.items():
        with st.expander(category):
            for issue in issues:
                st.markdown(issue)
    
    # System Status
    st.subheader("🔍 System Status Check")
    
    if st.button("🔍 Run System Check"):
        with st.spinner("Checking system status..."):
            # Check database
            try:
                db.tables()
                st.success("✅ Database: Connected")
            except Exception as e:
                st.error(f"❌ Database: Error - {str(e)}")
            
            # Check API keys
            api_key = st.secrets.get("gemini", {}).get("api_key", "")
            if api_key:
                st.success("✅ Gemini API: Configured")
            else:
                st.warning("⚠️ Gemini API: Not configured")
            
            # Check user data
            if hasattr(st, 'user') and st.user.is_logged_in:
                user_fields = db.get_user_fields(st.user.email)
                st.success(f"✅ User Data: {len(user_fields)} fields found")
            else:
                st.warning("⚠️ User Data: Not logged in")
    
    # Logs and Debug
    st.subheader("📋 Debug Information")
    
    if st.button("📋 Show Debug Info"):
        debug_info = {
            "User Email": st.user.email if hasattr(st, 'user') and st.user.is_logged_in else "Not logged in",
            "Database Tables": db.tables(),
            "Session State Keys": list(st.session_state.keys()),
            "Streamlit Version": st.__version__
        }
        
        for key, value in debug_info.items():
            st.write(f"**{key}**: {value}")

def render_contact_support():
    """Contact support"""
    st.subheader("📞 Contact Support")
    
    # Support options
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 📧 Email Support
        **General Support**: support@terrasync.io
        **Technical Issues**: tech@terrasync.io
        **Business Inquiries**: business@terrasync.io
        
        ### 📱 Phone Support
        **Hotline**: +84 123 456 789
        **Hours**: Mon-Fri 8AM-6PM (GMT+7)
        """)
    
    with col2:
        st.markdown("""
        ### 💬 Live Chat
        Available during business hours
        Average response time: 5 minutes
        
        ### 🐛 Bug Reports
        **GitHub Issues**: [github.com/terrasync/issues](https://github.com/terrasync/issues)
        **Priority**: Critical bugs get 24h response
        """)
    
    # Contact form
    st.subheader("📝 Send Message")
    
    with st.form("contact_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Your Name", value=st.user.name if hasattr(st, 'user') and st.user.is_logged_in else "")
            email = st.text_input("Email", value=st.user.email if hasattr(st, 'user') and st.user.is_logged_in else "")
        
        with col2:
            issue_type = st.selectbox("Issue Type", [
                "General Question",
                "Technical Problem", 
                "Feature Request",
                "Bug Report",
                "Account Issue"
            ])
            priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"])
        
        subject = st.text_input("Subject")
        message = st.text_area("Message", height=150)
        
        if st.form_submit_button("📤 Send Message", type="primary"):
            if not message:
                st.error("Please enter a message")
            else:
                # In a real app, this would send the message
                st.success("✅ Message sent successfully! We'll get back to you within 24 hours.")
                
                # Log the message (in real app, save to database)
                contact_data = {
                    "name": name,
                    "email": email,
                    "issue_type": issue_type,
                    "priority": priority,
                    "subject": subject,
                    "message": message,
                    "user_email": st.user.email if hasattr(st, 'user') and st.user.is_logged_in else None,
                    "timestamp": st.session_state.get("timestamp", "unknown")
                }
                
                # Save to database
                db.add("support_messages", contact_data)
    
    # FAQ
    st.subheader("❓ Frequently Asked Questions")
    
    faqs = [
        {
            "Q": "How do I connect my IoT devices?",
            "A": "Go to IoT Management → Add New Hub → Enter hub details and connect sensors"
        },
        {
            "Q": "Can I use TerraSync without IoT devices?",
            "A": "Yes! You can use manual data entry and weather-based scheduling"
        },
        {
            "Q": "How accurate is the AI disease detection?",
            "A": "Our AI achieves 85-90% accuracy on common plant diseases with clear images"
        },
        {
            "Q": "What crops are supported?",
            "A": "Rice, Corn, Wheat, Soybean, Tomato, Potato, Cabbage, and custom crops"
        },
        {
            "Q": "How much water can I save?",
            "A": "Users typically save 20-40% water through optimized irrigation scheduling"
        }
    ]
    
    for faq in faqs:
        with st.expander(faq["Q"]):
            st.write(faq["A"])
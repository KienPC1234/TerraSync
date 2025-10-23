"""
TerraSync AI Field Detection Page
AI YOLO để tự động khoanh vùng ruộng và chẩn đoán bệnh cây
"""

import streamlit as st
import io
from PIL import Image
import json
from typing import Dict, List, Any
from api_placeholders import terrasync_apis
from database import db

def render_ai_field_detection():
    """Trang AI Field Detection"""
    st.title("🤖 AI Field Detection & Disease Diagnosis")
    st.markdown("Sử dụng AI YOLO để tự động khoanh vùng ruộng và chẩn đoán bệnh cây trồng")
    
    # Tabs cho các chức năng
    tab1, tab2, tab3 = st.tabs(["🗺️ Field Boundary Detection", "🌿 Plant Disease Diagnosis", "📊 Analysis Results"])
    
    with tab1:
        render_field_boundary_detection()
    
    with tab2:
        render_plant_disease_diagnosis()
    
    with tab3:
        render_analysis_results()

def render_field_boundary_detection():
    """AI tự động khoanh vùng ruộng"""
    st.subheader("🗺️ AI Field Boundary Detection")
    st.markdown("Upload ảnh vệ tinh hoặc ảnh thực tế để AI tự động detect và khoanh vùng ruộng")
    
    # Upload image
    uploaded_file = st.file_uploader(
        "Choose an image file",
        type=['png', 'jpg', 'jpeg'],
        help="Upload satellite image or aerial photo of your field"
    )
    
    if uploaded_file is not None:
        # Display uploaded image
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_column_width=True)
        
        # Image info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Image Size", f"{image.size[0]}x{image.size[1]}")
        with col2:
            st.metric("File Size", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("Format", uploaded_file.type.split('/')[-1].upper())
        
        # Processing options
        st.subheader("🔧 Processing Options")
        col1, col2 = st.columns(2)
        
        with col1:
            detection_confidence = st.slider("Detection Confidence", 0.5, 0.95, 0.8)
            crop_type_hint = st.selectbox(
                "Crop Type Hint (Optional)",
                ["Auto-detect", "Rice", "Corn", "Wheat", "Soybean", "Vegetables", "Fruits"]
            )
        
        with col2:
            min_field_size = st.number_input("Minimum Field Size (hectares)", 0.1, 10.0, 0.5)
            merge_small_fields = st.checkbox("Merge Small Adjacent Fields", value=True)
        
        # Process button
        if st.button("🔍 Detect Field Boundaries", type="primary"):
            with st.spinner("AI is analyzing the image..."):
                # Convert image to bytes
                img_bytes = io.BytesIO()
                image.save(img_bytes, format='JPEG')
                img_bytes = img_bytes.getvalue()
                
                # Call AI API
                result = terrasync_apis.detect_field_boundaries(img_bytes)
                
                if result["status"] == "success":
                    st.session_state.detection_result = result
                    st.success("✅ Field detection completed!")
                    st.rerun()
                else:
                    st.error("❌ Detection failed. Please try again.")
    
    # Display detection results
    if "detection_result" in st.session_state:
        result = st.session_state.detection_result
        st.subheader("🎯 Detection Results")
        
        detected_fields = result.get("detected_fields", [])
        
        if detected_fields:
            st.success(f"Found {len(detected_fields)} field(s)")
            
            for i, field in enumerate(detected_fields):
                with st.expander(f"Field {i+1}: {field.get('crop_type_suggestion', 'Unknown Crop')}", expanded=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("Confidence", f"{field['confidence']*100:.1f}%")
                        st.metric("Area", f"{field['area_hectares']:.2f} hectares")
                        st.metric("Crop Type", field.get('crop_type_suggestion', 'Unknown'))
                    
                    with col2:
                        # Display polygon coordinates
                        st.write("**Field Coordinates:**")
                        polygon = field.get('polygon', [])
                        for j, coord in enumerate(polygon):
                            st.write(f"Point {j+1}: {coord[0]:.6f}, {coord[1]:.6f}")
                    
                    # Action buttons
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"✅ Accept Field {i+1}", key=f"accept_{i}"):
                            # Add to user's fields
                            field_data = {
                                "name": f"AI Detected Field {i+1}",
                                "crop": field.get('crop_type_suggestion', 'Unknown'),
                                "area": field['area_hectares'],
                                "polygon": polygon,
                                "center": [
                                    sum(p[0] for p in polygon) / len(polygon),
                                    sum(p[1] for p in polygon) / len(polygon)
                                ],
                                "detection_confidence": field['confidence'],
                                "user_email": st.user.email,
                                "created_by": "AI Detection"
                            }
                            
                            db.add("fields", field_data)
                            st.success(f"✅ Field {i+1} added to your fields!")
                            st.rerun()
                    
                    with col2:
                        if st.button(f"✏️ Edit Field {i+1}", key=f"edit_{i}"):
                            st.session_state.editing_field = field
                            st.session_state.editing_field_index = i
                    
                    with col3:
                        if st.button(f"❌ Reject Field {i+1}", key=f"reject_{i}"):
                            st.info(f"Field {i+1} rejected")
        else:
            st.warning("No fields detected. Try adjusting the detection parameters.")

def render_plant_disease_diagnosis():
    """AI chẩn đoán bệnh cây trồng"""
    st.subheader("🌿 Plant Disease Diagnosis")
    st.markdown("Upload ảnh lá cây để AI chẩn đoán bệnh và đưa ra lời khuyên điều trị")
    
    # Upload image
    uploaded_file = st.file_uploader(
        "Choose a plant image",
        type=['png', 'jpg', 'jpeg'],
        help="Upload clear image of plant leaves showing symptoms",
        key="disease_upload"
    )
    
    if uploaded_file is not None:
        # Display uploaded image
        image = Image.open(uploaded_file)
        st.image(image, caption="Plant Image", use_column_width=True)
        
        # Diagnosis options
        st.subheader("🔧 Diagnosis Options")
        col1, col2 = st.columns(2)
        
        with col1:
            crop_type = st.selectbox(
                "Crop Type",
                ["Auto-detect", "Rice", "Corn", "Wheat", "Tomato", "Potato", "Cabbage", "Other"]
            )
            plant_part = st.selectbox(
                "Plant Part",
                ["Leaf", "Stem", "Fruit", "Root", "Flower"]
            )
        
        with col2:
            growth_stage = st.selectbox(
                "Growth Stage",
                ["Seedling", "Vegetative", "Flowering", "Fruiting", "Maturity"]
            )
            severity_hint = st.selectbox(
                "Severity Hint",
                ["Mild", "Moderate", "Severe", "Unknown"]
            )
        
        # Process button
        if st.button("🔍 Diagnose Disease", type="primary"):
            with st.spinner("AI is analyzing the plant image..."):
                # Convert image to bytes
                img_bytes = io.BytesIO()
                image.save(img_bytes, format='JPEG')
                img_bytes = img_bytes.getvalue()
                
                # Call AI API
                result = terrasync_apis.diagnose_plant_disease(img_bytes, crop_type)
                
                if result["status"] == "success":
                    st.session_state.diagnosis_result = result
                    st.success("✅ Disease diagnosis completed!")
                    st.rerun()
                else:
                    st.error("❌ Diagnosis failed. Please try again.")
    
    # Display diagnosis results
    if "diagnosis_result" in st.session_state:
        result = st.session_state.diagnosis_result
        diagnosis = result.get("diagnosis", {})
        
        st.subheader("🏥 Diagnosis Results")
        
        # Main diagnosis
        col1, col2, col3 = st.columns(3)
        with col1:
            disease = diagnosis.get("disease", "Unknown")
            confidence = diagnosis.get("confidence", 0)
            st.metric("Disease", disease)
        with col2:
            severity = diagnosis.get("severity", "Unknown")
            st.metric("Severity", severity)
        with col3:
            affected_area = diagnosis.get("affected_area_percent", 0)
            st.metric("Affected Area", f"{affected_area}%")
        
        # Confidence indicator
        confidence_color = "🟢" if confidence > 0.8 else "🟡" if confidence > 0.6 else "🔴"
        st.markdown(f"**Confidence:** {confidence_color} {confidence*100:.1f}%")
        
        # Treatment suggestions
        st.subheader("💊 Treatment Suggestions")
        treatment_suggestions = diagnosis.get("treatment_suggestions", [])
        if treatment_suggestions:
            for i, suggestion in enumerate(treatment_suggestions, 1):
                st.write(f"{i}. {suggestion}")
        else:
            st.info("No specific treatment suggestions available.")
        
        # Prevention tips
        st.subheader("🛡️ Prevention Tips")
        prevention_tips = diagnosis.get("prevention_tips", [])
        if prevention_tips:
            for i, tip in enumerate(prevention_tips, 1):
                st.write(f"{i}. {tip}")
        else:
            st.info("No prevention tips available.")
        
        # Save diagnosis
        if st.button("💾 Save Diagnosis Report", type="primary"):
            diagnosis_data = {
                "disease": disease,
                "confidence": confidence,
                "severity": severity,
                "affected_area_percent": affected_area,
                "treatment_suggestions": treatment_suggestions,
                "prevention_tips": prevention_tips,
                "crop_type": crop_type,
                "plant_part": plant_part,
                "growth_stage": growth_stage,
                "user_email": st.user.email,
                "image_filename": uploaded_file.name if uploaded_file else "unknown"
            }
            
            db.add("disease_diagnoses", diagnosis_data)
            st.success("✅ Diagnosis report saved!")

def render_analysis_results():
    """Kết quả phân tích tổng hợp"""
    st.subheader("📊 Analysis Results & History")
    
    # User's AI analysis history
    user_diagnoses = db.get("disease_diagnoses", {"user_email": st.user.email})
    user_fields = db.get("fields", {"user_email": st.user.email, "created_by": "AI Detection"})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🗺️ AI Detected Fields")
        if user_fields:
            for field in user_fields:
                with st.container():
                    st.write(f"**{field.get('name', 'Unnamed Field')}**")
                    st.caption(f"Crop: {field.get('crop', 'Unknown')} | Area: {field.get('area', 0):.2f} ha")
                    st.caption(f"Confidence: {field.get('detection_confidence', 0)*100:.1f}%")
                    st.divider()
        else:
            st.info("No AI-detected fields yet.")
    
    with col2:
        st.subheader("🌿 Disease Diagnoses")
        if user_diagnoses:
            for diagnosis in user_diagnoses[-5:]:  # Show last 5
                with st.container():
                    st.write(f"**{diagnosis.get('disease', 'Unknown Disease')}**")
                    st.caption(f"Severity: {diagnosis.get('severity', 'Unknown')} | Confidence: {diagnosis.get('confidence', 0)*100:.1f}%")
                    st.caption(f"Crop: {diagnosis.get('crop_type', 'Unknown')}")
                    st.divider()
        else:
            st.info("No disease diagnoses yet.")
    
    # Statistics
    st.subheader("📈 AI Analysis Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Fields Detected", len(user_fields))
    
    with col2:
        st.metric("Total Diagnoses", len(user_diagnoses))
    
    with col3:
        if user_diagnoses:
            avg_confidence = sum(d.get('confidence', 0) for d in user_diagnoses) / len(user_diagnoses)
            st.metric("Avg Diagnosis Confidence", f"{avg_confidence*100:.1f}%")
        else:
            st.metric("Avg Diagnosis Confidence", "N/A")
    
    with col4:
        if user_fields:
            total_area = sum(f.get('area', 0) for f in user_fields)
            st.metric("Total Detected Area", f"{total_area:.2f} ha")
        else:
            st.metric("Total Detected Area", "0 ha")
    
    # Export data
    if st.button("📤 Export Analysis Data", type="secondary"):
        export_data = {
            "ai_detected_fields": user_fields,
            "disease_diagnoses": user_diagnoses,
            "export_date": st.session_state.get("export_date", "unknown"),
            "user_email": st.user.email
        }
        
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
        st.download_button(
            label="Download JSON",
            data=json_str,
            file_name=f"terrasync_ai_analysis_{st.user.email}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )

# Import datetime for export
from datetime import datetime

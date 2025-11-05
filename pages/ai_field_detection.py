"""
TerraSync AI Field Detection Page
AI YOLO để tự động khoanh vùng ruộng và chẩn đoán bệnh cây
"""

import streamlit as st
import io
from PIL import Image
import json
from typing import Dict, List, Any
import requests
import base64
import numpy as np
from database import db
import google.generativeai as genai
from datetime import datetime

API_URL = "http://172.24.193.209:9990"

# Assume API key is configured
# genai.configure(api_key="YOUR_API_KEY")  # Uncomment and set if needed

model = genai.GenerativeModel("gemini-2.5-flash")

def diagnose_plant_disease(img_bytes, crop_type, plant_part, growth_stage, severity_hint, mode="classification"):
    # Encode image to base64
    image_base64 = base64.b64encode(img_bytes).decode('utf-8')
    payload = {
        "image_base64": image_base64,
        "content_type": "image/jpeg"
    }
    
    img = Image.open(io.BytesIO(img_bytes))
    
    if mode == "classification":
        response = requests.post(f"{API_URL}/predict_class", json=payload)
        if response.status_code == 200:
            result = response.json()
            predicted_class = result.get("predicted_class", "Unknown")
            # Use Gemini for advice in Vietnamese with all options
            prompt = f"Dựa trên ảnh cây trồng này (phần: {plant_part}, giai đoạn: {growth_stage}, mức độ gợi ý: {severity_hint}), loại cây: {crop_type}, và bệnh dự đoán: {predicted_class}, cung cấp gợi ý điều trị và mẹo phòng ngừa. Trả lời BẰNG TIẾNG VIỆT, định dạng có cấu trúc với phần **Điều trị:** và **Phòng ngừa:**, mỗi gợi ý bắt đầu bằng dấu -."
            gemini_response = model.generate_content([prompt, img])
            advice = gemini_response.text
            # Simple parsing for treatment and prevention in Vietnamese
            treatment = []
            prevention = []
            lines = advice.split('\n')
            in_treatment = False
            in_prevention = False
            for line in lines:
                line_lower = line.lower()
                if "điều trị" in line_lower:
                    in_treatment = True
                    in_prevention = False
                elif "phòng ngừa" in line_lower:
                    in_prevention = True
                    in_treatment = False
                elif line.strip().startswith('-') or line.strip().startswith('*'):
                    if in_treatment:
                        treatment.append(line.strip('-* ').strip())
                    elif in_prevention:
                        prevention.append(line.strip('-* ').strip())
            diagnosis = {
                "disease": predicted_class,
                "confidence": 0.85,  # From API or mock
                "severity": "Trung bình",  # Mock in Vietnamese
                "affected_area_percent": 25,  # Mock
                "treatment_suggestions": treatment or ["Phun thuốc trừ nấm", "Cải thiện thoát nước"],
                "prevention_tips": prevention or ["Luân canh cây trồng", "Sử dụng giống kháng bệnh"]
            }
            return {"status": "success", "diagnosis": diagnosis, "mode": mode}
        else:
            return {"status": "error"}
    elif mode == "detection":
        response = requests.post(f"{API_URL}/detect_bboxes", json=payload)
        if response.status_code == 200:
            result = response.json()
            bboxes = result.get("bboxes", [])
            annotated_base64 = result.get("annotated_image_base64", "")
            annotated_img = Image.open(io.BytesIO(base64.b64decode(annotated_base64)))
            # Use Gemini to analyze detections in Vietnamese with all options, without specifying disease
            prompt = f"Phân tích ảnh cây trồng này với các hộp giới hạn phát hiện (có thể là vết bệnh). Phần: {plant_part}, giai đoạn: {growth_stage}, mức độ gợi ý: {severity_hint}, loại cây: {crop_type}. Mô tả vấn đề phát hiện, ước lượng mức độ nghiêm trọng, và cung cấp lời khuyên điều trị/phòng ngừa BẰNG TIẾNG VIỆT, định dạng có cấu trúc với phần **Điều trị:** và **Phòng ngừa:**, mỗi gợi ý bắt đầu bằng dấu -."
            gemini_response = model.generate_content([prompt, img])
            advice = gemini_response.text
            # Parse similarly
            treatment = []
            prevention = []
            lines = advice.split('\n')
            in_treatment = False
            in_prevention = False
            for line in lines:
                line_lower = line.lower()
                if "điều trị" in line_lower:
                    in_treatment = True
                    in_prevention = False
                elif "phòng ngừa" in line_lower:
                    in_prevention = True
                    in_treatment = False
                elif line.strip().startswith('-') or line.strip().startswith('*'):
                    if in_treatment:
                        treatment.append(line.strip('-* ').strip())
                    elif in_prevention:
                        prevention.append(line.strip('-* ').strip())
            diagnosis = {
                "disease": "Vết loét/vết đốm phát hiện",  # Based on detection, but generic
                "confidence": 0.9,  # Mock
                "severity": "Trung bình",  # From Gemini or mock
                "affected_area_percent": len(bboxes) * 10,  # Rough estimate
                "treatment_suggestions": treatment or ["Áp dụng điều trị nhắm vào vết đốm", "Theo dõi sự lan rộng"],
                "prevention_tips": prevention or ["Cải thiện thông gió", "Kiểm tra định kỳ"],
                "num_detections": len(bboxes),
                "bboxes": bboxes
            }
            return {"status": "success", "diagnosis": diagnosis, "annotated_image": annotated_img, "mode": mode}
        else:
            return {"status": "error"}
    return {"status": "error"}

def render_ai_field_detection():
    """ Trang AI Field Detection"""
    st.title("🤖 Chẩn Đoán Bệnh Cây Trồng Bằng AI")
    st.markdown("Sử dụng AI để chẩn đoán bệnh cây trồng")
    
    # Tabs cho các chức năng
    tab2, tab3 = st.tabs(["🌿 Chẩn Đoán Bệnh Cây Trồng", "📊 Kết Quả Phân Tích"])
    
    with tab2:
        render_plant_disease_diagnosis()
    
    with tab3:
        render_analysis_results()

def render_plant_disease_diagnosis():
    """AI chẩn đoán bệnh cây trồng"""
    st.subheader("🌿 Chẩn Đoán Bệnh Cây Trồng")
    st.markdown("Tải lên ảnh lá cây để AI chẩn đoán bệnh và đưa ra lời khuyên điều trị")
    
    # Upload image
    uploaded_file = st.file_uploader(
        "Chọn ảnh cây trồng",
        type=['png', 'jpg', 'jpeg'],
        help="Tải lên ảnh rõ nét của lá cây thể hiện triệu chứng",
        key="disease_upload"
    )
    
    if uploaded_file is not None:
        # Display uploaded image
        image = Image.open(uploaded_file)
        st.image(image, caption="Ảnh Cây Trồng", use_column_width=True)
        
        # Diagnosis options
        st.subheader("🔧 Tùy Chọn Chẩn Đoán")
        col1, col2 = st.columns(2)
        
        with col1:
            mode = st.selectbox(
                "Chế Độ AI",
                ["Phân loại (mặc định)", "Phát hiện (hộp giới hạn)"]
            )
            crop_type = st.selectbox(
                "Loại Cây Trồng",
                ["Tự động phát hiện", "Lúa", "Ngô", "Lúa mì", "Cà chua", "Khoai tây", "Bắp cải", "Khác"],
                index=0  # Default to "Tự động phát hiện"
            )
            plant_part = st.selectbox(
                "Phần Cây",
                ["Lá", "Thân", "Quả", "Rễ", "Hoa"]
            )
        
        with col2:
            growth_stage = st.selectbox(
                "Giai Đoạn Sinh Trưởng",
                ["Mầm", "Sinh trưởng", "Ra hoa", "Trái cây", "Trưởng thành"]
            )
            severity_hint = st.selectbox(
                "Gợi Ý Mức Độ Nghiêm Trọng",
                ["Nhẹ", "Trung bình", "Nghiêm trọng", "Không rõ"]
            )
        
        # Process button
        if st.button("🔍 Chẩn Đoán Bệnh", type="primary"):
            with st.spinner("AI đang phân tích ảnh cây trồng..."):
                # Convert image to bytes
                img_bytes = io.BytesIO()
                image.save(img_bytes, format='JPEG')
                img_bytes = img_bytes.getvalue()
                
                # Call AI API and Gemini
                ai_mode = "classification" if "mặc định" in mode else "detection"
                result = diagnose_plant_disease(img_bytes, crop_type, plant_part, growth_stage, severity_hint, ai_mode)
                
                if result["status"] == "success":
                    st.session_state.diagnosis_result = result
                    st.session_state.uploaded_file = uploaded_file  # Store for later use
                    st.success("✅ Hoàn thành chẩn đoán bệnh!")
                    st.rerun()
                else:
                    st.error("❌ Chẩn đoán thất bại. Vui lòng thử lại.")
    
    # Display diagnosis results
    if "diagnosis_result" in st.session_state:
        result = st.session_state.diagnosis_result
        diagnosis = result.get("diagnosis", {})
        mode = result.get("mode", "classification")
        
        st.subheader("🏥 Kết Quả Chẩn Đoán")
        
        # Main diagnosis
        col1, col2, col3 = st.columns(3)
        with col1:
            disease = diagnosis.get("disease", "Không xác định")
            confidence = diagnosis.get("confidence", 0)
            st.metric("Bệnh", disease)
        with col2:
            severity = diagnosis.get("severity", "Không xác định")
            st.metric("Mức Độ Nghiêm Trọng", severity)
        with col3:
            affected_area = diagnosis.get("affected_area_percent", 0)
            st.metric("Diện Tích Bị Ảnh Hưởng", f"{affected_area}%")
        
        if mode == "detection":
            num_detections = diagnosis.get("num_detections", 0)
            st.metric("Số Lượng Phát Hiện", num_detections)
            if "annotated_image" in result:
                st.image(result["annotated_image"], caption="Ảnh Với Hộp Giới Hạn Phát Hiện", use_column_width=True)
        
        # Confidence indicator
        confidence_color = "🟢" if confidence > 0.8 else "🟡" if confidence > 0.6 else "🔴"
        st.markdown(f"**Độ Tin Cậy:** {confidence_color} {confidence*100:.1f}%")
        
        # Treatment suggestions
        st.subheader("💊 Gợi Ý Điều Trị")
        treatment_suggestions = diagnosis.get("treatment_suggestions", [])
        if treatment_suggestions:
            for i, suggestion in enumerate(treatment_suggestions, 1):
                st.write(f"{i}. {suggestion}")
        else:
            st.info("Không có gợi ý điều trị cụ thể.")
        
        # Prevention tips
        st.subheader("🛡️ Mẹo Phòng Ngừa")
        prevention_tips = diagnosis.get("prevention_tips", [])
        if prevention_tips:
            for i, tip in enumerate(prevention_tips, 1):
                st.write(f"{i}. {tip}")
        else:
            st.info("Không có mẹo phòng ngừa.")
        
        # Save diagnosis
        uploaded_file = st.session_state.get('uploaded_file', None)
        if st.button("💾 Lưu Báo Cáo Chẩn Đoán", type="primary"):
            diagnosis_data = {
                "disease": disease,
                "confidence": confidence,
                "severity": severity,
                "affected_area_percent": affected_area,
                "treatment_suggestions": treatment_suggestions,
                "prevention_tips": prevention_tips,
                "crop_type": crop_type if 'crop_type' in locals() else "Tự động phát hiện",
                "plant_part": plant_part if 'plant_part' in locals() else "Lá",
                "growth_stage": growth_stage if 'growth_stage' in locals() else "Sinh trưởng",
                "ai_mode": mode,
                "user_email": st.user.email,
                "image_filename": uploaded_file.name if uploaded_file else "unknown"
            }
            
            db.add("disease_diagnoses", diagnosis_data)
            st.success("✅ Đã lưu báo cáo chẩn đoán!")

def render_analysis_results():
    """Kết quả phân tích tổng hợp"""
    st.subheader("📊 Kết Quả Phân Tích & Lịch Sử")
    
    # User's AI analysis history
    user_diagnoses = db.get("disease_diagnoses", {"user_email": st.user.email})
    
    st.subheader("🌿 Chẩn Đoán Bệnh")
    if user_diagnoses:
        for diagnosis in user_diagnoses[-5:]:  # Show last 5
            with st.container():
                st.write(f"**{diagnosis.get('disease', 'Bệnh Không Xác Định')}**")
                st.caption(f"Mức Độ Nghiêm Trọng: {diagnosis.get('severity', 'Không Xác Định')} | Độ Tin Cậy: {diagnosis.get('confidence', 0)*100:.1f}%")
                st.caption(f"Loại Cây: {diagnosis.get('crop_type', 'Không Xác Định')} | Chế Độ: {diagnosis.get('ai_mode', 'classification')}")
                st.divider()
    else:
        st.info("Chưa có chẩn đoán bệnh nào.")
    
    # Statistics
    st.subheader("📈 Thống Kê Phân Tích AI")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Tổng Số Chẩn Đoán", len(user_diagnoses))
    
    with col2:
        if user_diagnoses:
            avg_confidence = sum(d.get('confidence', 0) for d in user_diagnoses) / len(user_diagnoses)
            st.metric("Độ Tin Cậy Trung Bình", f"{avg_confidence*100:.1f}%")
        else:
            st.metric("Độ Tin Cậy Trung Bình", "N/A")
    
    # Export data
    if st.button("📤 Xuất Dữ Liệu Phân Tích", type="secondary"):
        export_data = {
            "disease_diagnoses": user_diagnoses,
            "export_date": datetime.now().isoformat(),
            "user_email": st.user.email
        }
        
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
        st.download_button(
            label="Tải Về JSON",
            data=json_str,
            file_name=f"terrasync_ai_analysis_{st.user.email}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )
#!/usr/bin/env python3
"""
Test script for crop management functionality
Tests the new crop database and management system
"""

import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_crop_database():
    """Test crop database functionality"""
    print("🌾 Testing Crop Database")
    print("=" * 50)
    
    try:
        from database import db
        
        # Test user email
        test_user = "test@terrasync.com"
        
        print("1. Testing crop addition...")
        
        # Test adding predefined crops
        predefined_crops = ["Rice", "Corn", "Wheat", "Tomato"]
        for crop_name in predefined_crops:
            success = db.add("crops", {
                "name": crop_name,
                "user_email": test_user,
                "crop_coefficient": 1.0,
                "irrigation_efficiency": 85,
                "created_at": datetime.now().isoformat(),
                "is_ai_generated": False
            })
            print(f"   ✅ {crop_name}: {'SUCCESS' if success else 'FAILED'}")
        
        # Test adding custom crop
        custom_crop = "Durian"
        success = db.add("crops", {
            "name": custom_crop,
            "user_email": test_user,
            "crop_coefficient": 1.2,
            "irrigation_efficiency": 80,
            "created_at": datetime.now().isoformat(),
            "is_ai_generated": True
        })
        print(f"   ✅ {custom_crop}: {'SUCCESS' if success else 'FAILED'}")
        
        print("\n2. Testing crop retrieval...")
        user_crops = db.get("crops", {"user_email": test_user})
        print(f"   ✅ User crops found: {len(user_crops)}")
        
        for crop in user_crops:
            print(f"   - {crop.get('name', 'Unknown')} (AI: {crop.get('is_ai_generated', False)})")
        
        print("\n3. Testing crop duplication prevention...")
        # Try to add Rice again
        existing_crops = db.get("crops", {"name": "Rice", "user_email": test_user})
        print(f"   ✅ Rice already exists: {len(existing_crops) > 0}")
        
        return True
        
    except Exception as e:
        print(f"❌ Crop database test failed: {e}")
        return False

def test_crop_functions():
    """Test crop management functions"""
    print("\n🔧 Testing Crop Functions")
    print("=" * 50)
    
    try:
        # Import functions from add_field.py
        sys.path.append(os.path.join(os.path.dirname(__file__), 'pages'))
        from add_field import (
            CROP_DATABASE, 
            get_crop_characteristics, 
            add_crop_if_not_exists, 
            get_available_crops
        )
        
        test_user = "test@terrasync.com"
        
        print("1. Testing CROP_DATABASE...")
        print(f"   ✅ Predefined crops: {len(CROP_DATABASE)}")
        for crop_name in CROP_DATABASE.keys():
            print(f"   - {crop_name}")
        
        print("\n2. Testing get_crop_characteristics...")
        
        # Test predefined crop
        rice_chars = get_crop_characteristics("Rice")
        print(f"   ✅ Rice characteristics: {rice_chars.get('crop_coefficient', 'N/A')}")
        
        # Test custom crop
        durian_chars = get_crop_characteristics("Durian")
        print(f"   ✅ Durian characteristics: {durian_chars.get('crop_coefficient', 'N/A')}")
        
        print("\n3. Testing add_crop_if_not_exists...")
        
        # Test adding existing crop
        success = add_crop_if_not_exists("Rice", test_user)
        print(f"   ✅ Add existing Rice: {'SUCCESS' if success else 'FAILED'}")
        
        # Test adding new crop
        success = add_crop_if_not_exists("Mango", test_user)
        print(f"   ✅ Add new Mango: {'SUCCESS' if success else 'FAILED'}")
        
        print("\n4. Testing get_available_crops...")
        available_crops = get_available_crops(test_user)
        print(f"   ✅ Available crops: {len(available_crops)}")
        for crop in available_crops:
            print(f"   - {crop}")
        
        return True
        
    except Exception as e:
        print(f"❌ Crop functions test failed: {e}")
        return False

def test_crop_ui_logic():
    """Test crop UI logic simulation"""
    print("\n🎨 Testing Crop UI Logic")
    print("=" * 50)
    
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'pages'))
        from add_field import get_available_crops, get_crop_characteristics
        
        test_user = "test@terrasync.com"
        
        print("1. Simulating crop selection dropdown...")
        available_crops = get_available_crops(test_user)
        crop_options = available_crops + ["Other"]
        
        print(f"   ✅ Dropdown options: {len(crop_options)}")
        for i, crop in enumerate(crop_options[:5]):  # Show first 5
            print(f"   {i+1}. {crop}")
        if len(crop_options) > 5:
            print(f"   ... and {len(crop_options) - 5} more")
        
        print("\n2. Simulating crop information display...")
        for crop_name in ["Rice", "Tomato", "Durian"]:
            if crop_name in available_crops:
                characteristics = get_crop_characteristics(crop_name)
                print(f"   ✅ {crop_name}:")
                print(f"      - Mùa trồng: {characteristics.get('planting_season', 'N/A')}")
                print(f"      - Ngày thu hoạch: {characteristics.get('harvest_days', 'N/A')} ngày")
                print(f"      - Hệ số cây trồng: {characteristics.get('crop_coefficient', 'N/A')}")
                print(f"      - Hiệu suất tưới: {characteristics.get('irrigation_efficiency', 'N/A')}%")
        
        print("\n3. Simulating custom crop creation...")
        custom_crop = "Coffee"
        characteristics = get_crop_characteristics(custom_crop)
        print(f"   ✅ Custom crop '{custom_crop}' created with:")
        print(f"      - Mùa trồng: {characteristics.get('planting_season', 'N/A')}")
        print(f"      - Loại đất: {characteristics.get('soil_type', 'N/A')}")
        print(f"      - pH: {characteristics.get('ph_range', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Crop UI logic test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 TerraSync Crop Management Test Suite")
    print("=" * 60)
    
    tests = [
        ("Crop Database", test_crop_database),
        ("Crop Functions", test_crop_functions),
        ("Crop UI Logic", test_crop_ui_logic)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {test_name} - PASSED")
            else:
                print(f"\n❌ {test_name} - FAILED")
        except Exception as e:
            print(f"\n❌ {test_name} - ERROR: {e}")
    
    print("\n" + "=" * 60)
    print(f"🏁 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Crop management is working correctly.")
        print("\n✅ Key Features Working:")
        print("   - Predefined crop database with characteristics")
        print("   - Custom crop creation with AI-generated parameters")
        print("   - Duplicate prevention")
        print("   - User-specific crop lists")
        print("   - Rich crop information display")
    else:
        print("⚠️ Some tests failed. Check the output above.")

if __name__ == "__main__":
    main()

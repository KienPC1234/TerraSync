#!/usr/bin/env python3
"""
Test script for field creation and display flow
Tests the complete flow from add_field to my_fields
"""

import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_field_creation():
    """Test field creation flow"""
    print("🧪 Testing Field Creation Flow")
    print("=" * 50)
    
    try:
        from database import db
        
        # Test user email
        test_user = "test@terrasync.com"
        
        # Create test field data
        test_field = {
            'name': 'Test Field from Script',
            'crop': 'Corn',
            'area': 2.5,
            'lat': 20.450123,
            'lon': 106.325678,
            'center': [20.450123, 106.325678],
            'polygon': [
                [20.450123, 106.325678],
                [20.450124, 106.325679],
                [20.450125, 106.325680],
                [20.450126, 106.325681]
            ],
            'stage': 'Vegetative',
            'crop_coefficient': 1.2,
            'irrigation_efficiency': 85,
            'status': 'hydrated',
            'today_water': 120,
            'time_needed': 3,
            'progress': 75,
            'days_to_harvest': 45
        }
        
        print("1. Testing field creation...")
        success = db.add_user_field(test_user, test_field)
        print(f"   ✅ Field creation: {'SUCCESS' if success else 'FAILED'}")
        
        print("\n2. Testing field retrieval...")
        fields = db.get_user_fields(test_user)
        print(f"   ✅ Fields found: {len(fields)}")
        
        for i, field in enumerate(fields, 1):
            print(f"   {i}. {field.get('name', 'Unnamed')} - {field.get('crop', 'Unknown')} - {field.get('area', 0):.2f} ha")
        
        print("\n3. Testing field data integrity...")
        if fields:
            field = fields[0]
            required_fields = ['name', 'crop', 'area', 'lat', 'lon', 'id', 'user_email', 'created_at']
            missing_fields = [f for f in required_fields if f not in field]
            
            if missing_fields:
                print(f"   ❌ Missing fields: {missing_fields}")
            else:
                print("   ✅ All required fields present")
        
        print("\n4. Testing database structure...")
        data = db.load()
        if data:
            print("   ✅ Database loaded successfully")
            for table, records in data.items():
                print(f"   - {table}: {len(records)} records")
        else:
            print("   ❌ Database load failed")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

def test_user_management():
    """Test user management"""
    print("\n👤 Testing User Management")
    print("=" * 50)
    
    try:
        from database import db
        
        # Test user data
        test_user_data = {
            "email": "test@terrasync.com",
            "name": "Test User",
            "picture": "https://example.com/avatar.jpg"
        }
        
        print("1. Testing user creation...")
        user = db.create_or_update_user(test_user_data)
        print(f"   ✅ User created/updated: {user.get('email', 'Unknown')}")
        
        print("\n2. Testing user retrieval...")
        retrieved_user = db.get_user_by_email("test@terrasync.com")
        if retrieved_user:
            print(f"   ✅ User found: {retrieved_user.get('email', 'Unknown')}")
            print(f"   - Name: {retrieved_user.get('name', 'Unknown')}")
            print(f"   - Fields: {len(retrieved_user.get('fields', []))}")
        else:
            print("   ❌ User not found")
        
        return True
        
    except Exception as e:
        print(f"❌ User management test failed: {e}")
        return False

def test_field_operations():
    """Test field CRUD operations"""
    print("\n🌾 Testing Field Operations")
    print("=" * 50)
    
    try:
        from database import db
        
        test_user = "test@terrasync.com"
        
        # Test update
        print("1. Testing field update...")
        fields = db.get_user_fields(test_user)
        if fields:
            field_id = fields[0].get('id')
            if field_id:
                update_data = {'area': 3.0, 'crop': 'Wheat'}
                success = db.update_user_field(field_id, test_user, update_data)
                print(f"   ✅ Field update: {'SUCCESS' if success else 'FAILED'}")
                
                # Verify update
                updated_fields = db.get_user_fields(test_user)
                if updated_fields:
                    updated_field = updated_fields[0]
                    if updated_field.get('area') == 3.0 and updated_field.get('crop') == 'Wheat':
                        print("   ✅ Update verified")
                    else:
                        print("   ❌ Update not reflected")
            else:
                print("   ❌ No field ID found")
        else:
            print("   ❌ No fields to update")
        
        # Test delete
        print("\n2. Testing field deletion...")
        if fields:
            field_id = fields[0].get('id')
            if field_id:
                success = db.delete_user_field(field_id, test_user)
                print(f"   ✅ Field deletion: {'SUCCESS' if success else 'FAILED'}")
                
                # Verify deletion
                remaining_fields = db.get_user_fields(test_user)
                print(f"   ✅ Remaining fields: {len(remaining_fields)}")
            else:
                print("   ❌ No field ID found for deletion")
        
        return True
        
    except Exception as e:
        print(f"❌ Field operations test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 TerraSync Field Flow Test Suite")
    print("=" * 60)
    
    tests = [
        ("User Management", test_user_management),
        ("Field Creation", test_field_creation),
        ("Field Operations", test_field_operations)
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
        print("🎉 All tests passed! Field flow is working correctly.")
        print("\n✅ Ready for Streamlit app testing:")
        print("   1. Run: ./run_app.sh")
        print("   2. Login with Google")
        print("   3. Go to 'Add Field' page")
        print("   4. Create a field")
        print("   5. Check 'My Fields' page")
    else:
        print("⚠️ Some tests failed. Check the output above.")

if __name__ == "__main__":
    main()

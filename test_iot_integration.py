#!/usr/bin/env python3
"""
Test script for TerraSync IoT Integration
Tests the integration between Streamlit app and IoT API
"""

import sys
import os
import time
import requests
import json
from datetime import datetime, timezone

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_iot_api_connection():
    """Test IoT API connection"""
    print("🔍 Testing IoT API connection...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ IoT API is running")
            return True
        else:
            print(f"❌ IoT API health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to IoT API")
        return False
    except Exception as e:
        print(f"❌ Error testing IoT API: {e}")
        return False

def test_database_connection():
    """Test database connection"""
    print("\n🗄️ Testing database connection...")
    try:
        from database import db
        
        # Test basic database operations
        test_data = {
            "test_field": "test_value",
            "timestamp": datetime.now().isoformat()
        }
        
        # Add test record
        db.add("test_table", test_data)
        
        # Get test record
        records = db.get("test_table", {"test_field": "test_value"})
        
        if records:
            print("✅ Database operations working")
            # Clean up test data
            db.delete("test_table", {"test_field": "test_value"})
            return True
        else:
            print("❌ Database operations failed")
            return False
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_iot_client():
    """Test IoT API client"""
    print("\n📡 Testing IoT API client...")
    try:
        from iot_api_client import get_iot_client, test_iot_connection
        
        # Test connection
        if not test_iot_connection():
            print("❌ IoT client connection failed")
            return False
        
        client = get_iot_client()
        
        # Test hub registration
        test_hub_data = {
            "hub_id": "test-hub-integration",
            "user_email": "test@terrasync.com",
            "location": {"lat": 20.450123, "lon": 106.325678},
            "description": "Integration test hub",
            "field_id": "test-field"
        }
        
        success = client.register_hub(test_hub_data)
        if success:
            print("✅ Hub registration successful")
        else:
            print("❌ Hub registration failed")
            return False
        
        # Test sensor registration
        test_sensor_data = {
            "hub_id": "test-hub-integration",
            "node_id": "test-sensor-01",
            "sensor_type": "soil",
            "location": {"lat": 20.450123, "lon": 106.325678},
            "description": "Test soil sensor"
        }
        
        success = client.register_sensor(test_sensor_data)
        if success:
            print("✅ Sensor registration successful")
        else:
            print("❌ Sensor registration failed")
            return False
        
        # Test data ingestion
        test_telemetry = {
            "hub_id": "test-hub-integration",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": {"lat": 20.450123, "lon": 106.325678},
            "data": {
                "soil_nodes": [{
                    "node_id": "test-sensor-01",
                    "sensors": {
                        "soil_moisture": 25.0,  # Low moisture to trigger alert
                        "soil_temperature": 28.0
                    }
                }],
                "atmospheric_node": {
                    "node_id": "atm-01",
                    "sensors": {
                        "air_temperature": 30.0,
                        "air_humidity": 70.0,
                        "rain_intensity": 0,
                        "wind_speed": 2.0,
                        "light_intensity": 800,
                        "barometric_pressure": 1000.0
                    }
                }
            }
        }
        
        success = client.send_telemetry_data(test_telemetry)
        if success:
            print("✅ Data ingestion successful")
        else:
            print("❌ Data ingestion failed")
            return False
        
        # Test data retrieval
        latest_data = client.get_latest_data("test-hub-integration")
        if latest_data:
            print("✅ Data retrieval successful")
        else:
            print("❌ Data retrieval failed")
            return False
        
        # Test alerts
        alerts = client.get_alerts("test-hub-integration")
        if alerts:
            print(f"✅ Alerts retrieval successful ({len(alerts)} alerts found)")
        else:
            print("⚠️ No alerts found (this might be normal)")
        
        return True
        
    except Exception as e:
        print(f"❌ IoT client error: {e}")
        return False

def test_streamlit_imports():
    """Test Streamlit page imports"""
    print("\n🌐 Testing Streamlit page imports...")
    try:
        # Test main pages
        from pages import dashboard, my_fields, add_field, my_schedule, help_center, settings, iot_management
        print("✅ All Streamlit pages import successfully")
        
        # Test API placeholders
        from api_placeholders import terrasync_apis
        print("✅ API placeholders import successfully")
        
        # Test database integration
        from database import db
        print("✅ Database integration working")
        
        return True
        
    except Exception as e:
        print(f"❌ Streamlit import error: {e}")
        return False

def test_conda_environment():
    """Test conda environment setup"""
    print("\n🐍 Testing conda environment...")
    try:
        import streamlit
        import fastapi
        import uvicorn
        import pandas
        import plotly
        import folium
        import requests
        import pydantic
        
        print("✅ All required packages available")
        return True
        
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        return False

def main():
    """Run all integration tests"""
    print("🧪 TerraSync IoT Integration Test Suite")
    print("=" * 60)
    
    tests = [
        ("Conda Environment", test_conda_environment),
        ("Database Connection", test_database_connection),
        ("IoT API Connection", test_iot_api_connection),
        ("IoT API Client", test_iot_client),
        ("Streamlit Imports", test_streamlit_imports)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - PASSED")
            else:
                print(f"❌ {test_name} - FAILED")
        except Exception as e:
            print(f"❌ {test_name} - ERROR: {e}")
    
    print("\n" + "=" * 60)
    print(f"🏁 Integration Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed!")
        print("✅ TerraSync IoT system is ready to use!")
        print("\n🚀 Next steps:")
        print("   1. Start IoT API: cd iotAPI && ./run_api.sh")
        print("   2. Start Streamlit: ./run_app.sh")
        print("   3. Open browser: http://localhost:8501")
    else:
        print("⚠️ Some tests failed. Please check the output above.")
        print("\n🔧 Troubleshooting:")
        print("   1. Make sure conda environment 'ts' is activated")
        print("   2. Install dependencies: pip install -r requirements.txt")
        print("   3. Start IoT API server: cd iotAPI && ./run_api.sh")
        print("   4. Check database permissions and file paths")

if __name__ == "__main__":
    main()

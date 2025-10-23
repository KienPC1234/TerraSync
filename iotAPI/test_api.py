#!/usr/bin/env python3
"""
Test script for TerraSync IoT API
This script tests the main API endpoints with sample data
"""

import requests
import json
from datetime import datetime, timezone
import time

# API Configuration
API_BASE_URL = "http://localhost:8000"
API_KEY = "terrasync-iot-2024"  # Default API key

def test_api_connection():
    """Test basic API connection"""
    print("🔍 Testing API connection...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API is running and healthy")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Make sure the server is running.")
        return False

def test_root_endpoint():
    """Test root endpoint"""
    print("\n📋 Testing root endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code == 200:
            data = response.json()
            print("✅ Root endpoint working")
            print(f"   API Version: {data.get('data', {}).get('version', 'Unknown')}")
            return True
        else:
            print(f"❌ Root endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Root endpoint error: {e}")
        return False

def test_hub_registration():
    """Test hub registration"""
    print("\n🏠 Testing hub registration...")
    
    hub_data = {
        "hub_id": "test-hub-001",
        "user_email": "test@terrasync.com",
        "location": {
            "lat": 20.450123,
            "lon": 106.325678
        },
        "description": "Test IoT Hub for TerraSync",
        "field_id": "test-field-001"
    }
    
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/hub/register",
            json=hub_data,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Hub registration successful")
            print(f"   Hub ID: {data.get('data', {}).get('hub_id', 'Unknown')}")
            return True
        else:
            print(f"❌ Hub registration failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Hub registration error: {e}")
        return False

def test_sensor_registration():
    """Test sensor registration"""
    print("\n📡 Testing sensor registration...")
    
    # Register soil sensors
    soil_sensors = [
        {
            "hub_id": "test-hub-001",
            "node_id": "soil-01",
            "sensor_type": "soil",
            "location": {"lat": 20.450123, "lon": 106.325678},
            "description": "Soil sensor node 1"
        },
        {
            "hub_id": "test-hub-001",
            "node_id": "soil-02",
            "sensor_type": "soil",
            "location": {"lat": 20.450124, "lon": 106.325679},
            "description": "Soil sensor node 2"
        }
    ]
    
    # Register atmospheric sensor
    atm_sensor = {
        "hub_id": "test-hub-001",
        "node_id": "atm-01",
        "sensor_type": "atmospheric",
        "location": {"lat": 20.450125, "lon": 106.325680},
        "description": "Atmospheric sensor node"
    }
    
    headers = {"Authorization": f"Bearer {API_KEY}"}
    all_sensors = soil_sensors + [atm_sensor]
    
    success_count = 0
    for sensor in all_sensors:
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/v1/sensor/register",
                json=sensor,
                headers=headers
            )
            
            if response.status_code == 200:
                print(f"✅ Sensor {sensor['node_id']} registered successfully")
                success_count += 1
            else:
                print(f"❌ Sensor {sensor['node_id']} registration failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Sensor {sensor['node_id']} registration error: {e}")
    
    return success_count == len(all_sensors)

def test_data_ingestion():
    """Test telemetry data ingestion"""
    print("\n📊 Testing data ingestion...")
    
    # Sample telemetry data
    telemetry_data = {
        "hub_id": "test-hub-001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {
            "lat": 20.450123,
            "lon": 106.325678
        },
        "data": {
            "soil_nodes": [
                {
                    "node_id": "soil-01",
                    "sensors": {
                        "soil_moisture": 25.5,  # Low moisture - should trigger alert
                        "soil_temperature": 28.3
                    }
                },
                {
                    "node_id": "soil-02",
                    "sensors": {
                        "soil_moisture": 45.2,
                        "soil_temperature": 26.9
                    }
                }
            ],
            "atmospheric_node": {
                "node_id": "atm-01",
                "sensors": {
                    "air_temperature": 31.3,
                    "air_humidity": 68.4,
                    "rain_intensity": 0,
                    "wind_speed": 2.1,
                    "light_intensity": 820,
                    "barometric_pressure": 1008.5
                }
            }
        }
    }
    
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/data/ingest",
            json=telemetry_data,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Data ingestion successful")
            print(f"   Alerts triggered: {data.get('data', {}).get('alert_count', 0)}")
            if data.get('data', {}).get('alerts_triggered'):
                for alert in data['data']['alerts_triggered']:
                    print(f"   🚨 {alert}")
            return True
        else:
            print(f"❌ Data ingestion failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Data ingestion error: {e}")
        return False

def test_data_retrieval():
    """Test data retrieval endpoints"""
    print("\n📈 Testing data retrieval...")
    
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    # Test latest data
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/v1/data/latest?hub_id=test-hub-001",
            headers=headers
        )
        
        if response.status_code == 200:
            print("✅ Latest data retrieval successful")
        else:
            print(f"❌ Latest data retrieval failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Latest data retrieval error: {e}")
    
    # Test data history
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/v1/data/history?hub_id=test-hub-001&limit=10",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Data history retrieval successful")
            print(f"   Records returned: {data.get('data', {}).get('returned_count', 0)}")
        else:
            print(f"❌ Data history retrieval failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Data history retrieval error: {e}")
    
    # Test alerts
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/v1/alerts?hub_id=test-hub-001&limit=10",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Alerts retrieval successful")
            print(f"   Alerts returned: {data.get('data', {}).get('returned_count', 0)}")
        else:
            print(f"❌ Alerts retrieval failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Alerts retrieval error: {e}")

def test_hub_status():
    """Test hub status endpoint"""
    print("\n📊 Testing hub status...")
    
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/v1/hub/status?hub_id=test-hub-001",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Hub status retrieval successful")
            hubs = data.get('data', {}).get('hubs', [])
            if hubs:
                hub = hubs[0]
                print(f"   Hub ID: {hub.get('hub', {}).get('hub_id', 'Unknown')}")
                print(f"   Sensor count: {hub.get('sensor_count', 0)}")
                print(f"   Last data time: {hub.get('last_data_time', 'Never')}")
        else:
            print(f"❌ Hub status retrieval failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Hub status retrieval error: {e}")

def main():
    """Run all tests"""
    print("🧪 TerraSync IoT API Test Suite")
    print("=" * 50)
    
    # Test API connection first
    if not test_api_connection():
        print("\n❌ Cannot proceed with tests. Please start the API server first.")
        print("   Run: cd iotAPI && ./run_api.sh")
        return
    
    # Run all tests
    tests = [
        test_root_endpoint,
        test_hub_registration,
        test_sensor_registration,
        test_data_ingestion,
        test_data_retrieval,
        test_hub_status
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"🏁 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! IoT API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Test script to verify all imports work correctly
"""

def test_imports():
    """Test all critical imports"""
    try:
        # Test database
        from database import db
        print("✅ Database import: OK")
        
        # Test API placeholders
        from api_placeholders import terrasync_apis
        print("✅ API placeholders import: OK")
        
        # Test utils
        from utils import get_default_fields, get_fields_from_db
        print("✅ Utils import: OK")
        
        # Test database operations
        tables = db.tables()
        print(f"✅ Database tables: {tables}")
        
        # Test API functionality
        weather = terrasync_apis.get_weather_forecast(20.45, 106.32, 3)
        print(f"✅ Weather API: {weather['status']}")
        
        print("\n🎉 All tests passed! The application is ready to run.")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_imports()

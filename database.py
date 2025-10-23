"""
TerraSync Database Manager
Quản lý database thống nhất cho toàn bộ ứng dụng
"""
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid

class TerraSyncDB:
    def __init__(self, db_file: str = "terrasync_db.json"):
        self.db_file = db_file
        self.data: Dict[str, List[Dict[str, Any]]] = {}
        self.load()
        
    def load(self):
        """Load dữ liệu từ database file"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.data = self._init_default_data()
        else:
            self.data = self._init_default_data()
        self.save()
    
    def _init_default_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Khởi tạo dữ liệu mặc định"""
        return {
            "users": [],
            "fields": [],
            "iot_hubs": [],
            "sensors": [],
            "alerts": [],
            "telemetry_history": []
        }
    
    def save(self):
        """Lưu dữ liệu vào database file"""
        try:
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving database: {e}")
    
    def add(self, table: str, data: Dict[str, Any]) -> bool:
        """Thêm record vào table"""
        if table not in self.data:
            self.data[table] = []
        
        # Thêm timestamp và ID nếu chưa có
        if "id" not in data:
            data["id"] = str(uuid.uuid4())
        if "created_at" not in data:
            data["created_at"] = datetime.now().isoformat()
        
        self.data[table].append(data)
        self.save()
        return True
    
    def get(self, table: str, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Lấy records từ table với filter tùy chọn"""
        if table not in self.data:
            return []
        
        records = self.data[table]
        if filter_dict:
            return [rec for rec in records if all(rec.get(k) == v for k, v in filter_dict.items())]
        return records
    
    def get_by_id(self, table: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Lấy record theo ID"""
        records = self.get(table, {"id": record_id})
        return records[0] if records else None
    
    def update(self, table: str, filter_dict: Dict[str, Any], update_data: Dict[str, Any]) -> int:
        """Cập nhật records theo filter"""
        if table not in self.data or not self.data[table]:
            return 0
        
        updated_count = 0
        for rec in self.data[table]:
            if all(rec.get(k) == v for k, v in filter_dict.items()):
                rec.update(update_data)
                rec["updated_at"] = datetime.now().isoformat()
                updated_count += 1
        
        if updated_count > 0:
            self.save()
        return updated_count
    
    def delete(self, table: str, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Xóa records theo filter"""
        if table not in self.data:
            return 0
        
        if filter_dict is None:
            deleted_count = len(self.data[table])
            self.data[table] = []
        else:
            original_count = len(self.data[table])
            self.data[table] = [rec for rec in self.data[table] 
                              if not all(rec.get(k) == v for k, v in filter_dict.items())]
            deleted_count = original_count - len(self.data[table])
        
        if not self.data[table]:
            del self.data[table]
        
        if deleted_count > 0:
            self.save()
        return deleted_count
    
    def tables(self) -> List[str]:
        """Lấy danh sách các table"""
        return list(self.data.keys())
    
    # User Management Methods
    def create_or_update_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Tạo hoặc cập nhật user từ Google OAuth"""
        email = user_data.get("email")
        if not email:
            raise ValueError("Email is required")
        
        existing_users = self.get("users", {"email": email})
        
        if existing_users:
            # Cập nhật user hiện tại
            user = existing_users[0]
            user.update({
                "name": user_data.get("name", user.get("name")),
                "picture": user_data.get("picture", user.get("picture")),
                "last_login": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            })
            self.update("users", {"email": email}, user)
            return user
        else:
            # Tạo user mới
            new_user = {
                "email": email,
                "name": user_data.get("name", ""),
                "picture": user_data.get("picture", ""),
                "first_login": datetime.now().isoformat(),
                "last_login": datetime.now().isoformat(),
                "is_active": True
            }
            self.add("users", new_user)
            return new_user
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Lấy user theo email"""
        users = self.get("users", {"email": email})
        return users[0] if users else None
    
    # Fields Management Methods
    def get_user_fields(self, user_email: str) -> List[Dict[str, Any]]:
        """Lấy danh sách fields của user"""
        return self.get("fields", {"user_email": user_email})
    
    def add_user_field(self, user_email: str, field_data: Dict[str, Any]) -> bool:
        """Thêm field mới cho user"""
        field_data["user_email"] = user_email
        return self.add("fields", field_data)
    
    def update_user_field(self, field_id: str, user_email: str, update_data: Dict[str, Any]) -> bool:
        """Cập nhật field của user"""
        updated = self.update("fields", {"id": field_id, "user_email": user_email}, update_data)
        return updated > 0
    
    def delete_user_field(self, field_id: str, user_email: str) -> bool:
        """Xóa field của user"""
        deleted = self.delete("fields", {"id": field_id, "user_email": user_email})
        return deleted > 0

# Global database instance
db = TerraSyncDB()

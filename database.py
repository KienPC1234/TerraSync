"""
TerraSync Database Manager
Quản lý database thống nhất cho toàn bộ ứng dụng
"""
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import uuid4
import uuid


"""
Gửi Kiên,
Đây là cấu trúc dữ liệu chat history trong database nhé
{
    "id": str,
    "user_email": str,                | Email chủ
    "messages": List[Dict],
    "context": Dict,                  | Context
    "timestamp": str,                 | ISO
    "shared_with": List[str]          | Email những người được chia sẻ cùng
}
"""


class TerraSyncDB:
    def __init__(self, db_file: str = "terrasync_db.json"):
        self.db_file = db_file
        self.data: Dict[str, List[Dict[str, Any]]] = {}
        self.load()
        # Ensure chat_history table exists
        if "chat_history" not in self.data:
            self.data["chat_history"] = []
        
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
        # First try to get from fields table
        fields = self.get("fields", {"user_email": user_email})
        
        # If no fields in fields table, try to get from user's fields array
        if not fields:
            user = self.get_user_by_email(user_email)
            if user and "fields" in user:
                fields = user["fields"]
        
        return fields
    
    def add_user_field(self, user_email: str, field_data: Dict[str, Any]) -> bool:
        """Thêm field mới cho user"""
        # Generate unique ID for the field
        field_id = str(uuid.uuid4())
        field_data["id"] = field_id
        field_data["user_email"] = user_email
        field_data["created_at"] = datetime.now().isoformat()
        
        # Add to fields table
        success = self.add("fields", field_data)
        
        if success:
            # Also add to user's fields array for backward compatibility
            user = self.get_user_by_email(user_email)
            if user:
                if "fields" not in user:
                    user["fields"] = []
                user["fields"].append(field_data)
                self.update("users", {"email": user_email}, {"fields": user["fields"]})
        
        return success
    
    def update_user_field(self, field_id: str, user_email: str, update_data: Dict[str, Any]) -> bool:
        """Cập nhật field của user"""
        updated = self.update("fields", {"id": field_id, "user_email": user_email}, update_data)
        return updated > 0
    
    def delete_user_field(self, field_id: str, user_email: str) -> bool:
        return self.delete("fields", {"id": field_id, "user_email": user_email}) > 0

    # Chat History Management Methods
    def save_chat_history(self, user_email: str, messages: List[Dict[str, Any]], context: Dict[str, Any] = None) -> bool:
        """Save chat history for a user"""
        chat_data = {
            "id": str(uuid4()),
            "user_email": user_email,
            "messages": messages,
            "context": context or {},
            "timestamp": datetime.now().isoformat(),
            "shared_with": []
        }
        return self.add("chat_history", chat_data)

    def get_user_chat_history(self, user_email: str) -> List[Dict[str, Any]]:
        """Get all chat histories for a user including those shared with them"""
        own_chats = self.get("chat_history", {"user_email": user_email})
        shared_chats = self.get("chat_history", {"shared_with": user_email})
        return own_chats + shared_chats

    def delete_chat_history(self, chat_id: str, user_email: str) -> bool:
        """Delete a specific chat history"""
        return self.delete("chat_history", {"id": chat_id, "user_email": user_email}) > 0

    def share_chat_history(self, chat_id: str, owner_email: str, share_with_email: str) -> bool:
        """Share a chat history with another user"""
        chat = self.get_by_id("chat_history", chat_id)
        if chat and chat.get("user_email") == owner_email:
            shared_with = chat.get("shared_with", [])
            if share_with_email not in shared_with:
                shared_with.append(share_with_email)
                return self.update("chat_history", {"id": chat_id}, {"shared_with": shared_with}) > 0
        return False

    def unshare_chat_history(self, chat_id: str, owner_email: str, unshare_with_email: str) -> bool:
        """Remove sharing of a chat history with a user"""
        chat = self.get_by_id("chat_history", chat_id)
        if chat and chat.get("user_email") == owner_email:
            shared_with = chat.get("shared_with", [])
            if unshare_with_email in shared_with:
                shared_with.remove(unshare_with_email)
                return self.update("chat_history", {"id": chat_id}, {"shared_with": shared_with}) > 0
        return False

# Global database instance
        """Xóa field của user"""
        deleted = self.delete("fields", {"id": field_id, "user_email": user_email})
        return deleted > 0

# Global database instance
db = TerraSyncDB()

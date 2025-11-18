"""
TerraSync Database Manager
Quản lý database thống nhất cho toàn bộ ứng dụng
(Phiên bản JSON - Tối ưu cho demo)
"""
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid


class JsonDB:
    """
    Một lớp cơ sở để quản lý dữ liệu trong một tệp JSON.
    Cung cấp các hoạt động CRUD cơ bản.
    """
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.data: Dict[str, List[Dict[str, Any]]] = {}
        self.load()

    def load(self):
        """Tải dữ liệu từ tệp cơ sở dữ liệu."""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.data = {}
        else:
            self.data = {}

    def save(self):
        """Lưu dữ liệu vào tệp cơ sở dữ liệu."""
        try:
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Lỗi khi lưu cơ sở dữ liệu: {e}")

    def add(self, table: str, data: Dict[str, Any]) -> bool:
        """Thêm một bản ghi vào một bảng."""
        if table not in self.data:
            self.data[table] = []

        if "id" not in data:
            data["id"] = str(uuid.uuid4())
        if "created_at" not in data:
            data["created_at"] = datetime.now().isoformat()

        self.data[table].append(data)
        self.save()
        return True

    def get(self, table: str,
            filter_dict: Optional[Dict[str, Any]] = None
            ) -> List[Dict[str, Any]]:
        """Lấy các bản ghi từ một bảng với bộ lọc tùy chọn."""
        if table not in self.data:
            return []

        records = self.data[table]
        if filter_dict:
            return [rec for rec in records
                    if all(rec.get(k) == v for k, v in filter_dict.items())]

        return records.copy()

    def get_by_id(self, table: str,
                  record_id: str) -> Optional[Dict[str, Any]]:
        """Lấy một bản ghi theo ID."""
        records = self.get(table, {"id": record_id})
        return records[0] if records else None

    def update(self, table: str, filter_dict: Dict[str, Any],
               update_data: Dict[str, Any]) -> int:
        """Cập nhật các bản ghi dựa trên một bộ lọc."""
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

    def delete(self, table: str,
               filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Xóa các bản ghi dựa trên một bộ lọc."""
        if table not in self.data:
            return 0

        if filter_dict is None:
            deleted_count = len(self.data[table])
            self.data[table] = []
        else:
            original_count = len(self.data[table])
            self.data[table] = [
                rec for rec in self.data[table]
                if not all(rec.get(k) == v for k, v in filter_dict.items())
            ]
            deleted_count = original_count - len(self.data[table])

        if deleted_count > 0:
            self.save()
        return deleted_count

    def overwrite_table(self, table: str, data: List[Dict[str, Any]]):
        """Ghi đè toàn bộ dữ liệu của một bảng."""
        self.data[table] = data
        self.save()

    def tables(self) -> List[str]:
        """Lấy danh sách các bảng."""
        return list(self.data.keys())


class TerraSyncDB(JsonDB):
    """
    Một lớp cơ sở dữ liệu cụ thể cho TerraSync, kế thừa từ JsonDB.
    Bao gồm các phương thức để quản lý người dùng, vườn và lịch sử trò chuyện.
    """
    def __init__(self, db_file: str = "terrasync_db.json"):
        super().__init__(db_file)
        self._ensure_default_tables()

    def _init_default_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Khởi tạo dữ liệu mặc định."""
        return {
            "users": [], "fields": [], "iot_hubs": [], "sensors": [],
            "alerts": [], "telemetry": [], "chat_history": []
        }

    def _ensure_default_tables(self):
        """Đảm bảo các bảng mặc định tồn tại trong dữ liệu đã tải."""
        defaults = self._init_default_data()
        for table_name in defaults.keys():
            if table_name not in self.data:
                self.data[table_name] = []
        self.save()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Lấy người dùng theo email."""
        users = self.get("users", {"email": email})
        return users[0] if users else None

    def get_fields_by_user(self, user_email: str) -> List[Dict[str, Any]]:
        """Lấy danh sách các vườn của người dùng."""
        fields = self.get("fields", {"user_email": user_email})
        if not fields:
            user = self.get_user_by_email(user_email)
            if user and "fields" in user:
                fields = user["fields"]
        return fields

    def add_user_field(self, user_email: str,
                       field_data: Dict[str, Any]) -> bool:
        """Thêm một vườn mới cho người dùng."""
        field_data["user_email"] = user_email
        success = self.add("fields", field_data)

        if success:
            user = self.get_user_by_email(user_email)
            if user:
                if "fields" not in user:
                    user["fields"] = []
                new_field_data = self.get_by_id("fields", field_data["id"])
                if new_field_data:
                    user["fields"].append(new_field_data)
                    self.update("users", {"email": user_email},
                                {"fields": user["fields"]})
        return success

    def update_user_field(self, field_id: str, user_email: str,
                          update_data: Dict[str, Any]) -> bool:
        """Cập nhật một vườn của người dùng."""
        updated = self.update("fields",
                              {"id": field_id, "user_email": user_email},
                              update_data)
        return updated > 0

    def delete_user_field(self, field_id: str, user_email: str) -> bool:
        """Xóa một vườn của người dùng."""
        deleted = self.delete("fields",
                              {"id": field_id, "user_email": user_email})
        return deleted > 0


# Khởi tạo các đối tượng cơ sở dữ liệu toàn cục
db = TerraSyncDB()
crop_db = JsonDB("cropdb.json")

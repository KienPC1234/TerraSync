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
from filelock import FileLock


class JsonDB:
    """
    Một lớp cơ sở để quản lý dữ liệu trong một tệp JSON.
    Cung cấp các hoạt động CRUD cơ bản với cơ chế khóa tệp để đảm bảo an toàn cho luồng.
    """
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.lock_file = f"{db_file}.lock"
        self.lock = FileLock(self.lock_file)
        # Không tải dữ liệu ở đây nữa, sẽ tải bên trong ngữ cảnh khóa

    def _load_unsafe(self) -> Dict[str, List[Dict[str, Any]]]:
        """Tải dữ liệu từ tệp mà không cần khóa (chỉ sử dụng nội bộ)."""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {}
        return {}

    def _save_unsafe(self, data: Dict[str, List[Dict[str, Any]]]):
        """Lưu dữ liệu vào tệp mà không cần khóa (chỉ sử dụng nội bộ)."""
        try:
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Lỗi khi lưu cơ sở dữ liệu: {e}")

    def add(self, table: str, data: Dict[str, Any]) -> bool:
        """Thêm một bản ghi vào một bảng một cách an toàn."""
        with self.lock:
            db_data = self._load_unsafe()
            if table not in db_data:
                db_data[table] = []

            if "id" not in data:
                data["id"] = str(uuid.uuid4())
            if "created_at" not in data:
                data["created_at"] = datetime.now().isoformat()

            db_data[table].append(data)
            self._save_unsafe(db_data)
        return True

    def get(self, table: str,
            filter_dict: Optional[Dict[str, Any]] = None
            ) -> List[Dict[str, Any]]:
        """Lấy các bản ghi từ một bảng một cách an toàn."""
        with self.lock:
            db_data = self._load_unsafe()
            if table not in db_data:
                return []

            records = db_data[table]
            if filter_dict:
                return [rec for rec in records
                        if all(rec.get(k) == v for k, v in filter_dict.items())]
            return records.copy()

    def get_by_id(self, table: str,
                  record_id: str) -> Optional[Dict[str, Any]]:
        """Lấy một bản ghi theo ID một cách an toàn."""
        records = self.get(table, {"id": record_id})
        return records[0] if records else None

    def update(self, table: str, filter_dict: Dict[str, Any],
               update_data: Dict[str, Any]) -> int:
        """Cập nhật các bản ghi dựa trên một bộ lọc một cách an toàn."""
        with self.lock:
            db_data = self._load_unsafe()
            if table not in db_data or not db_data[table]:
                return 0

            updated_count = 0
            for rec in db_data[table]:
                if all(rec.get(k) == v for k, v in filter_dict.items()):
                    rec.update(update_data)
                    rec["updated_at"] = datetime.now().isoformat()
                    updated_count += 1

            if updated_count > 0:
                self._save_unsafe(db_data)
            return updated_count

    def delete(self, table: str,
               filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Xóa các bản ghi dựa trên một bộ lọc một cách an toàn."""
        with self.lock:
            db_data = self._load_unsafe()
            if table not in db_data:
                return 0

            if filter_dict is None:
                deleted_count = len(db_data[table])
                db_data[table] = []
            else:
                original_count = len(db_data[table])
                db_data[table] = [
                    rec for rec in db_data[table]
                    if not all(rec.get(k) == v for k, v in filter_dict.items())
                ]
                deleted_count = original_count - len(db_data[table])

            if deleted_count > 0:
                self._save_unsafe(db_data)
            return deleted_count

    def overwrite_table(self, table: str, data: List[Dict[str, Any]]):
        """Ghi đè toàn bộ dữ liệu của một bảng một cách an toàn."""
        with self.lock:
            db_data = self._load_unsafe()
            db_data[table] = data
            self._save_unsafe(db_data)

    def tables(self) -> List[str]:
        """Lấy danh sách các bảng một cách an toàn."""
        with self.lock:
            db_data = self._load_unsafe()
            return list(db_data.keys())


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
            "alerts": [], "telemetry": [], "chat_history": [],
            "support_messages": [], "crop_requests": []
        }

    def _ensure_default_tables(self):
        """Đảm bảo các bảng mặc định tồn tại trong dữ liệu đã tải."""
        with self.lock:
            db_data = self._load_unsafe()
            defaults = self._init_default_data()
            needs_save = False
            for table_name in defaults.keys():
                if table_name not in db_data:
                    db_data[table_name] = []
                    needs_save = True
            if needs_save:
                self._save_unsafe(db_data)


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

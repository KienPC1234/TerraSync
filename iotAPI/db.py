import json
import os
from typing import Dict, List, Any, Optional

DB_FILE = "db.json"

class DatabaseManager:
    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self.data: Dict[str, List[Dict[str, Any]]] = {}
        self.load()

    def load(self):
        """Load dữ liệu từ db.json"""
        if os.path.exists(self.db_file):
            with open(self.db_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            # Khởi tạo mặc định với bảng users
            self.data = {"users": []}
            self.save()

    def save(self):
        """Lưu dữ liệu vào db.json"""
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def add(self, table: str, data: Dict[str, Any]) -> bool:
        """Thêm record vào table. Tự tạo table nếu chưa có."""
        if table not in self.data:
            self.data[table] = []
        self.data[table].append(data)
        self.save()
        return True

    def get(self, table: str, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Lấy records từ table. Nếu filter_dict, filter theo exact match."""
        if table not in self.data:
            return []
        records = self.data[table]
        if filter_dict:
            return [rec for rec in records if all(rec.get(k) == v for k, v in filter_dict.items())]
        return records

    def update(self, table: str, filter_dict: Dict[str, Any], update_data: Dict[str, Any]) -> int:
        """
        Cập nhật records trong table theo filter_dict (exact match).
        Merge update_data vào các records khớp (override keys nếu trùng).
        Trả về số lượng records đã cập nhật.
        """
        if table not in self.data or not self.data[table]:
            return 0
        records = self.data[table]
        updated_count = 0
        for rec in records:
            if all(rec.get(k) == v for k, v in filter_dict.items()):
                # Merge: update_data override rec
                rec.update(update_data)
                updated_count += 1
        if updated_count > 0:
            self.save()
        return updated_count

    def delete(self, table: str, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """
        Xóa records từ table theo filter_dict (exact match).
        Nếu filter_dict là None, xóa toàn bộ table (cẩn thận!).
        Trả về số lượng records đã xóa.
        """
        if table not in self.data:
            return 0
        records = self.data[table]
        if filter_dict is None:
            # Xóa toàn bộ table
            deleted_count = len(records)
            self.data[table] = []
        else:
            # Xóa theo filter
            to_delete = [rec for rec in records if all(rec.get(k) == v for k, v in filter_dict.items())]
            deleted_count = len(to_delete)
            self.data[table] = [rec for rec in records if rec not in to_delete]  # Xóa exact match dict
        if not self.data[table]:  # Nếu table rỗng, xóa table
            del self.data[table]
        self.save()
        return deleted_count

    def tables(self) -> List[str]:
        """Lấy danh sách các table hiện có."""
        return list(self.data.keys())

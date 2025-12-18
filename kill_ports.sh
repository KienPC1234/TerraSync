#!/bin/bash

# Danh sách port cần kill
PORTS=("8502" "8000" "3000")

for PORT in "${PORTS[@]}"; do
    echo "🔍 Kiểm tra port $PORT..."
    PID=$(lsof -t -i:$PORT)

    if [ -n "$PID" ]; then
        echo "❌ Tìm thấy PID $PID đang dùng port $PORT — tiến hành kill..."
        kill -9 $PID
        echo "✔️ Đã kill process $PID trên port $PORT"
    else
        echo "✔️ Không có process nào chạy trên port $PORT"
    fi
done

echo "🎉 Hoàn tất!"

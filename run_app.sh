#!/bin/bash

# TerraSync IoT Application Launcher
echo "🌱 Starting TerraSync IoT Application..."

# Check if conda environment exists
if ! conda env list | grep -q "ts"; then
    echo "❌ Conda environment 'ts' not found. Please run ./setup_conda.sh first."
    exit 1
fi

# Activate conda environment
echo "🔄 Activating conda environment 'ts'..."
source $(conda info --base)/etc/profile.d/conda.sh
conda activate ts

# Check if required files exist
if [ ! -f ".streamlit/secrets.toml" ]; then
    echo "⚠️  Warning: .streamlit/secrets.toml not found. Please configure your API keys."
    echo "   Copy .streamlit/secrets.toml.example and fill in your API keys."
fi

# Start IoT API server in background
echo "🚀 Starting IoT API server..."
cd iotAPI
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
cd ..

# Wait a moment for API server to start
sleep 3

# Start Streamlit app
echo "🌐 Starting Streamlit application..."
streamlit run streamlit_app.py --server.port 8502 --server.address 0.0.0.0

# Cleanup function
cleanup() {
    echo "🛑 Shutting down..."
    kill $API_PID 2>/dev/null
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Wait for background processes
wait

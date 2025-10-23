#!/bin/bash

# TerraSync IoT API Runner Script
# This script starts the IoT API server for data ingestion from IoT hubs

echo "🚀 Starting TerraSync IoT API Server..."

# Check if conda environment exists
if ! conda env list | grep -q "ts"; then
    echo "❌ Conda environment 'ts' not found. Please run setup_conda.sh first."
    exit 1
fi

# Activate conda environment
echo "📦 Activating conda environment 'ts'..."
source $(conda info --base)/etc/profile.d/conda.sh
conda activate ts

# Install IoT API dependencies if not already installed
echo "📥 Installing IoT API dependencies..."
pip install -r requirements.txt

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)/.."

# Start the API server
echo "🌐 Starting IoT API server on http://localhost:8000"
echo "📚 API Documentation available at http://localhost:8000/docs"
echo "🔍 Alternative docs at http://localhost:8000/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the FastAPI server
python main.py

#!/bin/bash

# TerraSync Conda Environment Setup Script
echo "🌱 Setting up TerraSync Conda Environment..."

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "❌ Conda is not installed. Please install Anaconda or Miniconda first."
    exit 1
fi

# Create conda environment from environment.yml
echo "📦 Creating conda environment 'ts'..."
conda env create -f environment.yml

# Activate environment
echo "🔄 Activating environment..."
conda activate ts

# Verify installation
echo "✅ Verifying installation..."
python -c "import streamlit; print('Streamlit version:', streamlit.__version__)"
python -c "import google.generativeai; print('Google Generative AI imported successfully')"

echo "🎉 TerraSync environment setup complete!"
echo "To activate the environment, run: conda activate ts"
echo "To run the app, use: streamlit run streamlit_app.py"

#!/bin/bash

echo "🔥 Starting Hephaestus Node..."

if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Copying from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your configuration."
fi

if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created."
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

if [ ! -f "venv/bin/pip" ] || [ ! -f "venv/lib/python*/site-packages/fastapi/__init__.py" ]; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
    echo "✅ Dependencies installed."
fi

echo "🏥 Checking LLM backend..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Warning: Ollama is not responding at http://localhost:11434"
    echo "   Please ensure Ollama is running: ollama serve"
    echo "   Or update LLM_HOST in .env to point to your LLM backend"
fi

echo ""
echo "🚀 Starting Hephaestus node..."
echo "   Dashboard: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""

python -m backend.app

#!/usr/bin/env bash
set -e

export PYTHONPATH=/app:${PYTHONPATH:-}

echo "================================================================================"
echo "Starting Annapurna Stores Analytics Platform"
echo "================================================================================"

# Run automated evaluation suite (Tasks A-F)
python run_all.py

echo "================================================================================"
echo "Starting Interactive Executive Web Dashboard on port 8501..."
echo "================================================================================"

exec streamlit run dashboard/app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true

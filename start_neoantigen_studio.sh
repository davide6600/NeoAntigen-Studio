#!/usr/bin/env bash

set -euo pipefail

# NeoAntigen-Studio — Local Startup (fallback mode)
echo "===================================================="
echo " NeoAntigen-Studio — Local Startup (fallback mode)"
echo "===================================================="
echo ""

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "[1/2] Starting FastAPI backend on http://localhost:8000 ..."
# Start uvicorn in the background
uvicorn services.api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

echo "Waiting 8 seconds for initialization..."
sleep 8

echo ""
echo "[2/2] Running end-to-end dry_run smoke test..."
echo "----------------------------------------------------"
python3 scripts/run_pipeline_cli.py \
  --patient-id PT-001 \
  --hla-alleles "HLA-A*02:01" \
  --peptides "SIINFEKL,NLVPMVATV" \
  --run-mode dry_run \
  --predictor auto \
  --api-url http://localhost:8000
echo "----------------------------------------------------"

echo ""
echo "API running at:   http://localhost:8000"
echo "Swagger docs at:  http://localhost:8000/docs"
echo "Audit trail at:   http://localhost:8000/jobs/{job_id}/audit-trail"
echo ""
echo "The API is running in the background (PID: $API_PID)."
echo "Utility to stop it: kill $API_PID"
echo ""

#!/bin/bash
set -e

echo "========================================="
echo "NeoAntigen-Studio - Full Approval E2E Test"
echo "========================================="

# Start the API server in the background
echo "Starting API server..."
uvicorn services.api.main:app --port 8000 &
API_PID=$!

# Give it a few seconds to start
sleep 3

echo "Running E2E CLI in full mode..."
# Feed an HMAC generated token into the script automatically!
# First we need the proposal ID! But run_pipeline_cli.py expects interactive input if mode is full.
# Let's use a Python script to do it.

cat << 'EOF' > /tmp/test_runner.py
import subprocess
import time
import httpx
import re

print("Starting E2E run in background...")
# Run the pipeline without the CLI blocking, or interact with it
# Actually, the simplest way is to hit the API directly matching what the CLI does.
with httpx.Client(base_url="http://localhost:8000") as client:
    res = client.post("/jobs", json={
        "requested_by": "e2e_tester",
        "run_mode": "full",
        "metadata": {
            "patient_id": "PT-E2E-FULL",
            "hla_alleles": ["HLA-A*02:01"],
            "pipeline_engine": "dummy",
            "peptides": ["SIINFEKL"]
        }
    })
    job_id = res.json()["job_id"]
    print(f"Job created: {job_id}")
    
    while True:
        r = client.get(f"/jobs/{job_id}")
        status = r.json()["status"]
        if status in ["completed", "failed"]:
            print(f"Job finished: {status}")
            break
            
        if status == "awaiting_approval":
            print(f"Job is awaiting approval!")
            r = client.get("/approvals")
            pending = r.json().get("pending_approvals", [])
            my_prop = next((p for p in pending if p["details"].get("job_id") == job_id), None)
            prop_id = my_prop["proposal_id"]
            
            # Generate the HMAC token
            import sys
            sys.path.append('.')
            from scripts.generate_approval_token import generate_token
            token = generate_token("safe_export", prop_id, "dev-secret")
            print(f"Generated token: {token}")
            
            res = client.post(f"/approvals/{prop_id}/approve", json={"approved_by": "e2e_tester", "token": token})
            if res.status_code == 200:
                print("Approval accepted!")
                client.post(f"/jobs/{job_id}/steps/safe_export/resume")
            else:
                print(f"Approval failed: {res.text}")
                break
        time.sleep(1)
EOF

python /tmp/test_runner.py

echo "Killing API server..."
kill $API_PID
echo "Done!"

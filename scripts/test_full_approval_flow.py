import subprocess
import time
import httpx
import sys
import os

print("Starting API server...")
api_process = subprocess.Popen(["uvicorn", "services.api.main:app", "--port", "8000"])
time.sleep(3)

print("Starting E2E run...")
try:
    with httpx.Client(base_url="http://localhost:8000") as client:
        res = client.post("/jobs", json={
            "requested_by": "e2e_tester",
            "run_mode": "full",
            "metadata": {
                "patient_id": "PT-E2E-FULL",
                "hla_alleles": ["A*02:01"],
                "pipeline_engine": "dry_run",
                "peptides": ["SIINFEKL"]
            }
        })
        if res.status_code != 200:
            print(f"Failed to create job: {res.text}")
            sys.exit(1)
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
finally:
    print("Killing API server...")
    api_process.terminate()
    print("Done!")

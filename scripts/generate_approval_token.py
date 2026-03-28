#!/usr/bin/env python3
import sys
import hmac
import hashlib

def generate_token(action: str, proposal_id: str, secret: str = "dev-secret") -> str:
    payload = f"{action}:{proposal_id}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"APPROVE_HMAC: {sig}"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/generate_approval_token.py <action> <proposal_id> [secret]")
        sys.exit(1)
    
    action = sys.argv[1]
    proposal_id = sys.argv[2]
    secret = sys.argv[3] if len(sys.argv) > 3 else "dev-secret"
    
    print(generate_token(action, proposal_id, secret))

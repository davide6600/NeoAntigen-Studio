# NeoAntigen-Studio — Quick Reference

## Local Startup (No Docker)

```bash
uvicorn services.api.main:app --reload
```
API available at: http://localhost:8000
Swagger docs at: http://localhost:8000/docs

---

## Docker Startup

```bash
bash scripts/docker_start.sh   # Linux/macOS
# or
docker compose up -d
```

Stop:
```bash
bash scripts/docker_stop.sh
# or
docker compose down
```

---

## Run Pipeline (CLI)

### Basic dry-run
```bash
python scripts/run_pipeline_cli.py \
  --patient-id P001 \
  --hla-alleles "HLA-A*02:01" \
  --peptides "SIINFEKL,NLVPMVATV" \
  --run-mode dry_run \
  --api-url http://localhost:8000
```

### With VCF file
```bash
python scripts/run_pipeline_cli.py \
  --patient-id P001 \
  --hla-alleles "HLA-A*02:01,HLA-B*07:02" \
  --vcf pipelines/nextflow/neoantigen_pipeline/test_data/sample.vcf \
  --run-mode dry_run
```

### Force predictor
```bash
# Always sklearn (no NetMHCpan)
  --predictor sklearn

# Use NetMHCpan if installed, fallback to sklearn
  --predictor netmhcpan

# Auto-detect (default)
  --predictor auto
```

### Full run with HMAC approval
```bash
# 1. Submit full job
python scripts/run_pipeline_cli.py \
  --patient-id P001 \
  --hla-alleles "HLA-A*02:01" \
  --peptides "SIINFEKL" \
  --run-mode full

# 2. Generate approval token
python scripts/generate_approval_token.py <proposal_id>

# 3. Approve via API
curl -X POST http://localhost:8000/approvals/<proposal_id>/approve \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "researcher_01", "token": "<token>"}'
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/health` | Health check |
| POST | `/jobs` | Create new job |
| GET  | `/jobs/{id}` | Job status |
| GET  | `/jobs/{id}/audit-trail` | Full audit trail |
| GET  | `/jobs/{id}/results` | Results + provenance |
| GET  | `/jobs/{id}/report.md` | Scientific report (Markdown) |
| GET  | `/jobs/{id}/report.pdf` | Scientific report (PDF) |
| GET  | `/jobs/{id}/report` | Auto-format redirect |
| GET  | `/approvals` | Pending approvals |
| POST | `/approvals/{id}/approve` | Approve with HMAC token |

---

## NetMHCpan Installation (Optional)

```bash
# 1. Register and download from:
#    https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/
# 2. Place archive in project root, then:
bash scripts/install_netmhcpan.sh
# 3. Add to .env:
#    NETMHCPAN_PATH=/usr/local/bin/netMHCpan
```

---

## Run Tests

```bash
pytest tests/ -v --tb=short
```

---

## Environment Variables (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEOANTIGEN_APPROVAL_SECRET` | `dev-secret` | HMAC signing key |
| `NEOANTIGEN_REPORT_FORMAT` | `markdown` | `markdown` \| `pdf` \| `html` |
| `CELERY_BROKER_URL` | *(empty)* | Redis URL for Celery |
| `NETMHCPAN_PATH` | *(auto-detect)* | Path to netMHCpan binary |
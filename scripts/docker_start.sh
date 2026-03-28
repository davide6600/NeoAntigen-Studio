#!/bin/bash
set -e

echo "=== NeoAntigen-Studio Docker Startup ==="

# Copia .env se non esiste
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[INFO] Created .env from .env.example — review before production use"
fi

# Build e avvio
docker compose build --no-cache
docker compose up -d

# Attendi health check API
echo "Waiting for API to be healthy..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API is ready at http://localhost:8000"
        echo "✅ Docs at http://localhost:8000/docs"
        break
    fi
    sleep 2
done

# Smoke test
echo ""
echo "Running smoke test..."
python scripts/run_pipeline_cli.py \
    --patient-id DOCKER-TEST \
    --hla-alleles "HLA-A*02:01" \
    --peptides "SIINFEKL" \
    --run-mode dry_run \
    --api-url http://localhost:8000

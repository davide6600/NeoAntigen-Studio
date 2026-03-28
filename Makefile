# NeoAntigen-Studio Automation Makefile

.PHONY: up down restart migrate test-dry-run logs

# Start all services in the background
up:
	docker-compose up -d

# Stop all services
down:
	docker-compose down

# Restart all services
restart:
	docker-compose restart

# Apply PostgreSQL migrations
migrate:
	docker-compose exec api python scripts/apply_postgres_migrations.py

# Run a dry-run E2E test with TESLA-P001 peptides INSIDE the api container
test-dry-run:
	docker-compose exec api python scripts/run_pipeline_cli.py --patient-id TESLA-P001 --hla-alleles "HLA-A*02:01" --peptides "GILGFVFTL,SIINFEKL" --run-mode dry_run

# Show logs from all services
logs:
	docker-compose logs -f

"""
Verifica che i file Docker siano sintatticamente corretti
senza richiedere Docker installato.
"""
import yaml
from pathlib import Path

def test_docker_compose_valid():
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())
    assert "services" in compose
    assert "api" in compose["services"]
    assert "worker" in compose["services"]
    assert "redis" in compose["services"]
    assert "volumes" in compose

def test_env_example_exists():
    assert Path(".env.example").exists()
    content = Path(".env.example").read_text()
    assert "NEOANTIGEN_APPROVAL_SECRET" in content
    assert "NEOANTIGEN_REPORT_FORMAT" in content

def test_dockerignore_exists():
    assert Path(".dockerignore").exists()
    content = Path(".dockerignore").read_text()
    assert ".env" in content
    assert ".git" in content

def test_dockerfiles_exist():
    assert Path("containers/Dockerfile.api").exists()
    assert Path("containers/Dockerfile.worker").exists()

# Contributing to NeoAntigen-Studio


Thank you for your interest in contributing to NeoAntigen-Studio! This project aims to democratize access to state-of-the-art neoantigen discovery and mRNA design tools. Every contribution helps advance personalized medicine research.

## Development Setup

1. Clone the repository and create a virtual environment:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -e ".[dev]"
   ```
2. Start the local stack:
   ```bash
   docker-compose up -d
   ```
3. Run the test suite:
   ```bash
   pytest
   ```

---

## ⚠️ Important: Research Use Only

All contributions must respect the platform's **Research Use Only (RUO)** status. Contributions that introduce clinical or diagnostic claims, or bypass biosecurity safety gates, will not be accepted.

---

## Getting Started

### Prerequisites

- **Python 3.12+**
- **Node.js 20+** (for frontend development)
- **Docker & Docker Compose** (for full-stack local testing)

### Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<org>/NeoAntigen-Studio.git
   cd NeoAntigen-Studio
   ```

2. **Install Python dependencies:**
   ```bash
   python -m pip install -e .
   ```

3. **Run unit tests:**
   ```bash
   pytest -q
   ```

4. **Start the full local stack (optional):**
   ```bash
   docker compose up -d --build
   ```
   This starts the API (`localhost:8000`), frontend (`localhost:8080`), Redis, and MinIO.

### Frontend Development

```bash
cd services/frontend
npm install
npm run dev
```

---

## How to Contribute

### Reporting Bugs

- Search [existing issues](https://github.com/<org>/NeoAntigen-Studio/issues) to avoid duplicates.
- Use the bug report template if available, or include:
  - Steps to reproduce
  - Expected vs. actual behavior
  - Python/Node.js version, OS, Docker version
  - Relevant logs

### Suggesting Features

- Open an issue with the `enhancement` label.
- Describe the use case and why it benefits neoantigen research.
- Reference relevant literature or tools if applicable.

### Submitting Code

1. **Fork** the repository and create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Write code** following the project conventions:
   - Python code follows PEP 8.
   - Use type hints consistently.
   - Use Pydantic v2 models for data validation.
   - Frontend code uses TypeScript and React best practices.

3. **Write tests** for new functionality. Place tests in `tests/`.

4. **Run the full test suite** before submitting:
   ```bash
   pytest -q
   ```

5. **Submit a Pull Request** against `main`:
   - Provide a clear description of what your PR does and why.
   - Reference any related issues.
   - Ensure CI checks pass.

---

## Code Review Process

- All PRs require at least one review before merging.
- Maintainers may request changes or ask clarifying questions.
- PRs that modify biosecurity controls, safety gates, or approval workflows require review by a designated security maintainer.

---

## Safety-Critical Contributions

The following areas require **extra scrutiny** and explicit maintainer approval:

| Area | Additional Reviewer |
|---|---|
| Sequence export logic | Biosecurity maintainer |
| RBAC / approval token logic | Security maintainer |
| ML model promotion pipeline | ML lead |
| Patient data handling | Data governance lead |
| Biosecurity blacklist rules | Biosecurity maintainer |

See [`agent/checklist.md`](agent/checklist.md) for the full list of gated actions and required approvers.

---

## Coding Conventions

- **Python:** PEP 8, type hints, Pydantic v2 models, `structlog` for logging.
- **TypeScript/React:** ESLint config in `services/frontend/eslint.config.js`.
- **SQL migrations:** Place in `migrations/postgresql/` with sequential numbering.
- **Tests:** pytest, one test file per module, descriptive test names.
- **Commits:** Use clear, descriptive commit messages. Reference issue numbers where applicable.

---

## Documentation

- If your change affects architecture or governance, update [`DOC_INDEX.md`](DOC_INDEX.md).
- If adding new endpoints, update the API documentation.
- If modifying schemas, update `schemas/` and related Pydantic models.

---

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).

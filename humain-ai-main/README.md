# HumaNai Platform — YDAYS 2026

HumaNai is a secure, modern AI-driven Human Resources platform designed for employee lifecycle management, onboarding/offboarding workflows, absence tracking, and engagement metrics.

---

## 🚀 Project Architecture

The project is structured as a mono-repo containing the following main directories:

- **[`humanai_backend/`](file:///c:/Users/Rayane/OneDrive/Bureau/ydays/humanai_backend)**: Core backend application built with **FastAPI**, **SQLAlchemy 2.0**, and **Firebase Auth**.
- **[`infra/`](file:///c:/Users/Rayane/OneDrive/Bureau/ydays/infra)**: Infrastructure configurations including **Docker Compose**, **PostgreSQL (with pgvector)**, **Redis**, **Nginx**, and monitoring tools (**Prometheus**, **Grafana**).

---

## 🛠️ Stack Technique

- **Backend**: Python 3.13+, FastAPI, SQLAlchemy 2.0, Async Pydantic v2
- **Authentication**: Firebase Authentication with custom RBAC claims
- **Database**: PostgreSQL 16 with pgvector & Row-Level Security (RLS)
- **Caching & Queue**: Redis 7
- **Storage**: MinIO (S3-compatible object storage)
- **Proxy**: Nginx
- **Monitoring**: Prometheus & Grafana

---

## ⚙️ Getting Started

### 1. Prerequisities
- Docker & Docker Compose
- Python 3.13+

### 2. Infrastructure Startup
Navigate to the `infra/` directory and run:
```bash
cd infra
make up
```
This will pull and run all the required containers, and automatically execute the SQL initialization scripts:
- `00_extensions.sql` (enables pgcrypto, vector, pg_trgm)
- `01_schema.sql` (database schema for all tables)
- `02_rls.sql` (Row-Level Security policies)
- `03_seed.sql` (demo data for development)

### 3. Backend Setup
Navigate to `humanai_backend/` directory:
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Configure `.env` using `.env.example` as a template.
3. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload
   ```

---

## 🧪 Testing

The backend includes a comprehensive suite of **20 unit and integration tests** covering authorization, employee management, absence requests, admin features, and assistant prompts.

To execute tests:
```bash
cd humanai_backend
python -m pytest
```
*Note: The test suite uses an asynchronous in-memory SQLite database (`StaticPool`) with a custom monkeypatch to safely simulate PostgreSQL UUID column types.*

---

## 🔁 CI/CD Pipeline (GitHub Actions)

A GitHub Actions pipeline is configured under [`.github/workflows/ci.yml`](file:///c:/Users/Rayane/OneDrive/Bureau/ydays/.github/workflows/ci.yml) to run on every commit or pull request to the `main` branch.

It automates:
1. **Linting & Quality Checks**: Standard check with `flake8` to identify potential syntax errors, code complexity, and formatting issues.
2. **Automated Testing**: Executes the full **20-test** suite using pytest.
3. **Docker Image Builds**: Builds the production Docker images for both `backend` (FastAPI) and `nginx` (proxy).
4. **Image Registry Storage**: Publishes the built images to the **GitHub Container Registry (GHCR)** tagged with `latest` and the commit SHA.
5. **Deployment Template**: A CD SSH deployment template that automates SSH logins to your target server, pulls updated containers, and restarts the environment.

To enable the deployment script, populate the following secrets in GitHub Repository Settings:
- `DEPLOY_HOST`: Staging/Production server IP or Hostname.
- `DEPLOY_USER`: Deployment user credentials.
- `DEPLOY_SSH_KEY`: Private key allowing deployment user to authenticate on the target server.


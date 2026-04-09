# ML Platform

A comprehensive, production-ready Machine Learning serving platform designed for high performance, reliability, scalability, and robust observability.

## Architecture

The platform architecture is built around a microservices pattern, encompassing the following components:

- **API Gateway**: A FastAPI-based centralized entry point for all ML predictions. It handles routing, distributed OpenTelemetry tracing, and exposes unified Prometheus metrics.
- **Model Services**:
  - **Toxicity Classifier**: Evaluates the toxicity of text inputs.
  - **Comment Ranker**: Ranks texts or comments based on relevance or quality.
- **MLflow**: Central model registry and tracking server used for tracking experiments and versioning models for reproducibility.
- **Observability Stack**:
  - **Prometheus** for pulling metrics such as `REQUEST_LATENCY` and `ERROR_COUNT`.
  - **OpenTelemetry Collector** for generating and exporting distributed traces.
  - **Grafana** for visualizations and alerting dashboards.

## Project Structure

- `gateway/`: The FastAPI API Gateway routing requests to underlying model services.
- `models/`: Containerized implementations of individual ML model services (Toxicity and Ranker) wrapped in API endpoints.
- `infra/`: Infrastructure as Code (IaC) and Kubernetes deployment manifests using Helm, ArgoCD, and Terraform.
- `docs/`: Additional documentation and architecture decision records.
- `tests/`: Automated tests, including k6 load testing scripts (`k6-500rps.js`).
- `scripts/`: Helpful utility scripts.
- `fault-injection/`: Scripts for testing system resilience, timeouts, and chaos engineering.

## Quick Start

You can run the entire platform locally using Docker Compose, which seamlessly sets up the gateway, the models, MLflow, and the observability stack.

1. Ensure you have Docker and Docker Compose installed.
2. Start the services:
   ```bash
   docker-compose up --build -d
   ```
3. The services will become available at:
   - **API Gateway**: http://localhost:8000
   - **Gateway Swagger Docs**: http://localhost:8000/docs
   - **MLflow Tracking**: http://localhost:5000
   - **Prometheus**: http://localhost:9090

### Testing an Endpoint

Send a POST request to the Gateway to classify text:

```bash
curl -X POST "http://localhost:8000/v1/toxicity/predict" \
     -H "Content-Type: application/json" \
     -d '{"text": "This is a great platform!", "threshold": 0.5}'
```

## MLOps Guidelines & Principles

This repository strictly adheres to established MLOps best practices:
1. **Reproducibility & Versioning**: All code and datasets are versioned. Trained models and metadata reside securely in MLflow.
2. **CI/CD**: Features automated testing and continuous training/deployment pipelines utilizing containerized deployments.
3. **Monitoring & Observability**: Includes real-time performance tracking, data drift detection, and automated alerting.
4. **Infrastructure**: Fully containerized pipeline enforcing proper resource management for multi-model serving.
5. **Governance**: Includes continuous bias audits and security/privacy protections at the gateway level.

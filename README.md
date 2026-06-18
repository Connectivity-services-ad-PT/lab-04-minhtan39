# FIT4110 Lab 04 - Dockerized Camera Stream

This repository submits Lab 04 for `team-camera`.

## Service

Camera Stream accepts campus camera frames, stores frame metadata in memory for lab verification, and exposes an analyze endpoint that calls AI Vision and Analytics through configurable URLs.

## Main Artifacts

```text
Dockerfile
.env.example
RUN_LOCAL.md
src/camera_app/main.py
contracts/camera-stream.openapi.yaml
postman/collections/FIT4110_lab04_camera_docker.postman_collection.json
postman/environments/FIT4110_lab04_local.postman_environment.json
reports/verification-summary.md
```

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn camera_app.main:app --app-dir src --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn camera_app.main:app --app-dir src --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

## Run With Docker

```bash
docker build -t fit4110/camera-stream:lab04 .
docker run --rm --name fit4110-camera-lab04 -p 8000:8000 --env-file .env.example fit4110/camera-stream:lab04
```

## Verify

```bash
npm install
npm run lint:openapi
npm run test:local
```

## Buoi 6 Notes

- The API binds to `0.0.0.0` and publishes port `8000`.
- Partner URLs are read from `.env.example`: `VISION_SERVICE_URL`, `ANALYTICS_URL`.
- Dependency failures return controlled Problem Details responses with `502` or `503`.

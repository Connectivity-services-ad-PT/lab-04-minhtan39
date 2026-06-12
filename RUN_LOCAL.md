# Run Local - Lab 04 Camera Stream

## 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Start API

```bash
uvicorn iot_app.main:app --app-dir src --host 0.0.0.0 --port 8000
```

## 3. Check health

```bash
curl http://localhost:8000/health
```

## 4. Build and run Docker image

```bash
docker build -t fit4110/camera-stream:lab04 .
docker run --rm --name fit4110-camera-lab04 -p 8000:8000 --env-file .env.example fit4110/camera-stream:lab04
```

## 5. Run Newman

```bash
npm install
npm run test:local
```

The API exposes `8000:8000`, binds to `0.0.0.0`, and reads partner URLs from `.env.example`.

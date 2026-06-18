# Docker Lab Guide - Camera Stream

## Build

```bash
docker build -t fit4110/camera-stream:lab04 .
```

## Run

```bash
docker run --rm --name fit4110-camera-lab04 -p 8000:8000 --env-file .env.example fit4110/camera-stream:lab04
```

## Health

```bash
curl http://localhost:8000/health
```

## Test

```bash
npm run test:local
```

## Expected Configuration

- `SERVICE_NAME=camera-stream`
- `APP_HOST=0.0.0.0`
- `APP_PORT=8000`
- `VISION_SERVICE_URL` points to AI Vision.
- `ANALYTICS_URL` points to Analytics.

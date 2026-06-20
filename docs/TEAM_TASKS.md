# Team Camera Lab 04 Tasks

## Required Work

- Package Camera Stream with Docker.
- Run as a non-root user.
- Expose `GET /health`.
- Publish host port `8000`.
- Use `.env.example` for runtime configuration.
- Run Newman against the Dockerized service.

## Camera Endpoints

- `GET /health`
- `POST /api/v1/frames`
- `GET /api/v1/frames`
- `GET /api/v1/frames/{frame_id}`
- `POST /api/v1/frames/{frame_id}/analyze`

## Business Analysis

See `docs/BUSINESS_ANALYSIS_CAMERA.md` for the detailed Camera Stream responsibilities from the 7-service document: validate frame, detect motion, throttle calls, preprocess snapshot, send `image_base64` to AI Vision, and publish the analyzed camera event.

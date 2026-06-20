# Camera Stream Business Analysis

Nguon tham chieu: `Nghiep vu 7 service.pdf`.

Tai lieu nay chot phan nghiep vu cua `team-camera` trong Smart Campus Operations Platform, dac biet luong Camera Stream phat hien chuyen dong va gui anh base64 sang `team-vision`.

## 1. Vai tro trong 7 service

Camera Stream khong phai service trung chuyen video thuan tuy. Gia tri nghiep vu cua service la bien luong camera lien tuc thanh nhung snapshot co y nghia de AI Vision phan tich dung luc.

```text
MJPEG stream -> validate frame -> detect motion -> throttle -> preprocess snapshot
-> POST /api/v1/detect sang AI Vision
-> publish camera event cho Analytics
-> neu risk cao/unknown_person thi cap tin hieu cho Core Business
```

Trong dependency map:

- Camera Stream -> AI Vision: REST sync, vi Camera can ket qua detect ngay.
- Camera Stream -> Analytics: Queue async/MQTT ve sau; trong lab hien tai mo phong bang event-shaped payload.
- Camera Stream -> Core Business: chi gui khi ket qua AI co rui ro cao hoac can tao alert.

## 2. Input cua Camera Stream

Theo PDF, input that la luong MJPEG do giang vien cap. Stream chi co frame, khong co metadata day du. Vi vay Camera Stream phai tu gan:

- `frame_id`: ma frame noi bo, vi du `FR-20260620-0001`.
- `camera_id`: camera nguon, vi du `CAM-A01`.
- `timestamp`/`captured_at`: thoi diem chup frame theo ISO 8601.
- `location`: khu vuc camera.
- `motion_score`: diem khac biet giua frame hien tai va frame truoc, tu `0` den `1`.
- `image_base64`: anh da resize/nen, encode base64 de gui cho AI Vision trong pham vi lab.

Quyet dinh cua nhom: cac lab 02-05 dung `image_base64` thay vi `snapshot_url` de khong phu thuoc shared file hosting giua cac may/nhom.

## 3. Xu ly nghiep vu bat buoc

### CHECK ket noi stream

- Doc duoc frame tu URL camera.
- Frame khong rong, khong den toan bo, kich thuoc hop le.
- Neu stream timeout/mat ket noi: log `camera_stream_unavailable`, khong lam service crash.

### DETECT motion

- Chuyen frame ve grayscale.
- So sanh voi frame truoc bang frame difference.
- Tinh `motion_score`.
- Chi khi `motion_score` vuot nguong moi coi la co chuyen dong.

Nguong de xuat:

```text
0.00              -> none
0.01 - 0.39       -> low
0.40 - 0.74       -> medium
0.75 - 1.00       -> high
```

### THROTTLE

Khong duoc gui moi frame sang AI Vision. Sau moi lan goi AI thanh cong/that bai, ap cooldown 5-10 giay cho moi camera.

Ly do: neu gui 30 FPS sang AI Vision thi service Vision se qua tai va sai tinh than nghiep vu.

### PREPROCESS

Truoc khi gui:

- Resize ve kich thuoc hop ly, vi du 640x480.
- Nen JPEG quality 70-85.
- Loai frame rong/den/qua lon.
- Gioi han `image_base64` trong contract de tranh payload qua lon.

### CALL AI Vision

Endpoint thong nhat:

```http
POST /api/v1/detect
Content-Type: application/json
```

Payload Camera gui sang Vision:

```json
{
  "request_id": "vision-FR-20260620-0001",
  "camera_id": "CAM-A01",
  "timestamp": "2026-06-20T08:30:00+07:00",
  "location": "Main lobby",
  "motion_score": 0.82,
  "image_base64": "dGVzdC1pbWFnZS1mcmFtZQ==",
  "snapshot_url": null
}
```

Yeu cau quan trong: payload khong chi co anh. Vision can `request_id`, `camera_id`, `timestamp`, `location`, `motion_score` de log, danh gia ngu canh va tra ket qua doi soat duoc.

### HANDLE Vision result

Vision tra response co cau truc:

```json
{
  "request_id": "vision-FR-20260620-0001",
  "camera_id": "CAM-A01",
  "timestamp": "2026-06-20T08:30:01+07:00",
  "detections": [
    {
      "label": "person",
      "confidence": 0.92,
      "bbox": { "x": 120, "y": 80, "width": 210, "height": 430 }
    }
  ],
  "unknown_person": true,
  "risk_level": "high"
}
```

Camera Stream phai xu ly:

- Timeout: retry toi da 2 lan, sau do tra Problem Details `503`.
- Vision tra 5xx: tra Problem Details `502`.
- Vision khong reachable: khong crash, ghi ro dependency unavailable.
- Ket qua `risk_level = high/critical` hoac `unknown_person = true`: tao `alert_candidate = true` de Core Business co the ap policy.

## 4. Output cho Analytics/Core

Event Camera gui di sau khi co ket qua AI:

```json
{
  "event_type": "camera.motion.analyzed",
  "source_service": "team-camera",
  "request_id": "vision-FR-20260620-0001",
  "frame_id": "FR-20260620-0001",
  "camera_id": "CAM-A01",
  "location": "Main lobby",
  "occurred_at": "2026-06-20T08:30:02+07:00",
  "timestamp": "2026-06-20T08:30:00+07:00",
  "motion_detected": true,
  "motion_score": 0.82,
  "motion_level": "high",
  "risk_level": "high",
  "unknown_person": true,
  "alert_candidate": true
}
```

Analytics dung event nay de tinh:

- So lan camera co motion theo khu vuc/ngay.
- Ty le motion high/medium/low.
- So event co `unknown_person`.
- So `alert_candidate` theo khu vuc.

Core Business dung event nay de ap policy:

- `unknown_person = true` va Access co denied cung khu vuc trong thoi gian ngan -> nghi dot nhap.
- `risk_level = high/critical` -> tao alert cho Notification.
- Motion binh thuong, risk low -> chi ghi nhan, khong can alert.

## 5. Loi thuong gap can tranh

- Gui ca video stream hoac moi frame sang Vision.
- Gui payload thieu `request_id`, `timestamp`, `camera_id`, `location`.
- Chi forward anh ma khong tinh `motion_score`.
- Khong throttle, lam Vision qua tai.
- De service crash khi Vision/Analytics offline.
- Dung mock Vision nhung khong ghi ro trong tai lieu.

## 6. Mapping voi bai lab

- Lab 02: `openapi.yaml`, negotiation log, analysis docs chot contract Camera -> Vision.
- Lab 03: Postman/Newman kiem thu frame hop le, auth, invalid image, motion boundary, dependency behavior.
- Lab 04: Docker hoa service va dam bao dependency error tra Problem Details.
- Lab 05: Compose stack co API, AI Vision mock, Analytics mock; test duoc luong upload frame -> analyze -> Vision -> Analytics.


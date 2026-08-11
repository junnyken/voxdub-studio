# API.md — control_server (VoxDub Studio)

Base: Fastify 5. Mọi route dưới `/v1/*`. Auth thiết bị: header
`Authorization: Bearer <deviceToken>` (JWT do `/v1/device/register` cấp).
Auth admin: header `X-Admin-Token`. Không có tài khoản người dùng — định danh
duy nhất là `fingerprint` (SHA-256 machine fingerprint, 64 hex).

Tài liệu này sinh từ đọc trực tiếp `src/routes/*.js` (2026-08-10, sau khi dựng
lại `src/models/` — xem `docs/TEST_LOG.md` mục V0). Sai lệch với code thật thì
code luôn đúng — báo lại để cập nhật file này.

## `/v1/config` (không cần token)

### `GET /v1/config/app`
App gọi lúc khởi động để biết trạng thái vận hành + đơn giá công khai.

Response 200:
```json
{
  "creditEnabled": true,
  "maintenanceMode": false,
  "maintenanceMessage": "",
  "minAppVersion": "3.0.0",
  "forceUpdateVersion": "",
  "maxSegmentsPerRequest": 120,
  "pricing": { "segmentBase": 10, "segmentAutoTranslate": 2, "metadata": 20 },
  "webUrl": "http://localhost:3001",
  "serverVersion": "3.0.0"
}
```

## `/v1/device`

### `POST /register` (không cần token — đây là bước lấy token)
Body: `{ fingerprint (64 hex, required), name?, appVersion? }`
Response: `{ token, isNew, device: {fingerprint,name,balance,status,firstSeenAt}, creditEnabled }`
Lỗi: `400 BAD_FINGERPRINT`, `403 DEVICE_BLOCKED`.

### `GET /me` (token)
Response: `{ device: {...publicView, balance}, creditEnabled }`

### `POST /refresh` (token)
Response: `{ token, device }`

### `POST /activate` (token)
Body: `{ code (8-40 ký tự, required) }`
Response: `{ vox, balanceAfter, keyCode, alreadyActivated }`
Lỗi: `400 BAD_KEY_FORMAT`, `403 DEVICE_BLOCKED`, `404 KEY_NOT_FOUND`,
`404 DEVICE_NOT_FOUND`, `409 KEY_REVOKED`, `409 KEY_ALREADY_USED`.

### `GET /balance` (token)
Response: `{ balance, creditEnabled }`

### `GET /history?page&limit` (token)
Response: `{ items: [{delta,balanceAfter,type,description,createdAt,metadata}], total, page, limit }`

### `POST /estimate` (token)
Body: `{ sentences (int, default 0), autoTranslate? (bool), metadata? (bool) }`
Response: `{ estimated, balance, sufficient, creditEnabled }`

## `/v1/holds` (mọi route cần token)

### `POST /` — tạo hold (idempotent theo `holdId`)
Body: `{ holdId (8-100 ký tự, required), sentences (1-20000, required), videoDurationS?, autoTranslate? (default true), metadata? (default true) }`
Response: `{ hold: {holdId,status,estimatedVox,usedVox,usage,expiresAt,autoCommitted,meta,encKeyHex}, balance, created }`
Lỗi: `402 INSUFFICIENT_CREDIT` (kèm `balance`,`required`), `403 HOLD_FORBIDDEN`,
`409 HOLD_FINISHED`, `409 HOLD_CONFLICT`, `409 HOLD_DISABLED`.

### `GET /:holdId`
Response: `{ hold (kèm encKeyHex nếu active/committed), balance }`
Lỗi: `404 HOLD_NOT_FOUND`.

### `POST /:holdId/commit` — chốt hold (idempotent)
Response: `{ committed, replayed, usedVox, chargedVox, balance, encKeyHex, autoCommitted }`
Lỗi: `404 HOLD_NOT_FOUND`, `409 HOLD_FINISHED`.

## `/v1/ai` (mọi route cần token, chặn khi `maintenance.mode`)

Nguyên tắc chung 4 route dưới: idempotent theo `jobId` (retry an toàn, không
tính phí lại) → kiểm trần cứng → kiểm số dư/hold → gọi model → trừ credit
(chỉ khi model trả về thành công) → lưu `JobResult` + ghi `UsageLog`. Response
KHÔNG BAO GIỜ chứa tên provider/model/token/chi phí nội bộ.

### `POST /translate`
Body: `{ jobId, holdId?, sourceLang? (default zh-CN), cpsBudget? (4-40, default 12.5), segments: [{id,text,duration?,max_chars?}], prevContext?, context?: {videoTitle,domain,context,pronouns,glossary,styleNotes} }`
Response: `{ jobId, segments: [{id,text_vi}], creditCharged, balanceAfter }`
Lỗi: `400 BATCH_TOO_LARGE`, `400 SEGMENT_TOO_LONG`, `402 INSUFFICIENT_CREDIT`,
`503 AI_UNAVAILABLE`/khác (kèm `retryAfter`).

### `POST /analyze`
Body: `{ jobId, holdId?, sourceLang?, videoTitle?, lines: string[] (max 400) }`
Response: `{ jobId, analysis: object|null, creditCharged, balanceAfter }` — lỗi
model KHÔNG throw ra ngoài, trả `analysis: null, creditCharged: 0` (bước phụ
trợ, không được chặn luồng dịch chính).

### `POST /review`
Body: `{ jobId, holdId?, sourceLang?, cpsBudget?, context?, items: [{id,reason(enum cjk|over_budget|too_short),text,current,duration?,max_chars?,neighbors?}] (max 60) }`
Response: `{ jobId, segments: [{id,text_vi}] (chỉ câu sửa được), creditCharged, balanceAfter }`

### `POST /generate-post`
Body: `{ jobId, holdId?, scriptOriginal (max 20000), scriptVi (max 20000), videoTitle? }`
Response: `{ jobId, metadata: object, creditCharged, balanceAfter }`
Lỗi: `402 INSUFFICIENT_CREDIT`, `503 AI_UNAVAILABLE`.

## `/v1/jobs` (mọi route cần token) — mini-spec V9, POC hẹp: CHỈ stage Demucs

Không thay thế luồng local — TUỲ CHỌN thêm, chỉ dùng khi người dùng chủ động
bật (chưa có UI, xem docs/TEST_LOG.md mục V9 "Remaining Limits"). Chính sách
dữ liệu: file input/output XOÁ NGAY sau khi tải xong CẢ HAI stem (hoặc theo
TTL `cloud.render.ttl.hours`, mặc định 2 giờ, làm lưới an toàn dự phòng).

### `POST /jobs/demucs` — nộp job (upload audio, xử lý ĐỒNG BỘ trong request)
Multipart, field `file` (audio, tối đa 200 MB).
Response: `{ jobId, status: "done"|"failed", error?, balanceAfter }`
Lỗi: `400 NO_FILE`/`EMPTY_FILE`, `402 INSUFFICIENT_CREDIT`, `409 CLOUD_RENDER_DISABLED`.
Trừ Vox theo `credit.cost.cloud.demucs` (mặc định 50) TRƯỚC khi xử lý — mất
tiền cả khi job fail (đã tốn tài nguyên máy chủ), không hoàn.

### `GET /jobs/:jobId`
Response: `{ jobId, stage, status, error?, creditCharged, expiresAt }`

### `GET /jobs/:jobId/result/:stem` (`stem` = `vocals` | `no_vocals`)
Trả file `.wav` (`Content-Disposition: attachment`). Sau khi CẢ HAI stem đã
được tải, server tự xoá thư mục job.
Lỗi: `400 BAD_STEM`, `404 NOT_FOUND`/`RESULT_NOT_FOUND`, `409 NOT_READY`,
`410 RESULT_EXPIRED` (đã bị dọn — tải trước đó hoặc quá TTL).

## `/v1/billing` (không cần token thiết bị — public storefront)

### `GET /packages`
Response: `{ packages: [{id,label,vnd,vox,bonus,totalVox,popular}], custom: {enabled,voxPerVnd,vndPerVox,minVnd,maxVnd,stepVnd}, creditEnabled }`

### `POST /orders`
Body: `{ packageId? | amountVnd?, email? }`
Response: `{ orderCode, amountVnd, vox, packageId, packageLabel, status, keyCode:'', createdAt, expiresAt, paidAt, accessToken, payment: {checkoutUrl,qrCode,amount,description} }`
`accessToken` chỉ trả về **đúng một lần** ở đây — trình duyệt phải tự lưu.
Lỗi: `404 PACKAGE_NOT_FOUND`, `400 AMOUNT_TOO_LOW`/`AMOUNT_TOO_HIGH`,
`409 CREDIT_DISABLED`, `503 PAYMENT_GATEWAY_ERROR`.

### `GET /orders/:orderCode?token=`
Response: `orderView` — `keyCode` chỉ khớp khi `token` đúng VÀ `status=paid`.

### `POST /orders/:orderCode/resend`
Body: `{ token (required), email? }` → gửi lại email chứa key.
Lỗi: `404 ORDER_NOT_FOUND`, `409 NOT_PAID`, `400 NO_EMAIL`, `503 MAIL_FAILED`.

### `POST /webhook/payos`
PayOS gọi, chữ ký HMAC-SHA256 verify bằng `PAYOS_CHECKSUM_KEY`. Luôn trả 2xx
trừ khi sai chữ ký (`401`) hoặc chưa cấu hình (`503`) — kể cả xử lý lỗi nội
bộ vẫn trả `{success:true}` (giao dịch đã ghi ở PayOS, đối chiếu tay sau).

## `/v1/admin` (header `X-Admin-Token`)

| Route | Việc |
|---|---|
| `GET /whoami` | Kiểm token đúng/sai (rate-limit chặt, đây là điểm dò token) |
| `GET /devices?search&status&page&limit` | Danh sách thiết bị |
| `GET /devices/:fingerprint` | Chi tiết + 50 dòng ledger/usage gần nhất + key đã dùng |
| `PATCH /devices/:fingerprint/status` | `{status:active\|blocked, reason?}` — khóa tăng `tokenVersion` (thu hồi token ngay) |
| `POST /devices/:fingerprint/credit` | `{delta (int), reason}` — cộng/trừ tay, ghi AuditLog |
| `POST /devices/:fingerprint/transfer` | `{toFingerprint, reason}` — chuyển toàn bộ số dư, khóa máy nguồn |
| `GET /keys?status&code&page&limit` | Danh sách key |
| `POST /keys` | `{vox, count? (default 1, max 100), note?}` — phát key tay |
| `DELETE /keys/:code` | Thu hồi key (`409` nếu đã `used`) |
| `GET /orders?status&orderCode&page&limit` | Danh sách đơn (ẩn `accessToken`) |
| `POST /orders/:orderCode/approve` | Duyệt tay đơn khi webhook lỗi |
| `GET /holds?status&page&limit` | Danh sách hold (ẩn `encKeyHex`) |
| `GET /reconcile` | Đối soát ví ↔ sổ cái, chỉ đọc + báo |
| `GET /config` / `PUT /config/:key` | Đọc/sửa `AppConfig`, ghi AuditLog kèm before/after |
| `GET /providers` | Danh sách AI provider (ẩn `apiKeyEnc`, chỉ báo `hasApiKey`) |
| `POST /providers` | Tạo provider — `409 DUPLICATE_NAME` nếu trùng `name` |
| `PATCH /providers/:id` | Sửa — `apiKey` rỗng = giữ nguyên key cũ |
| `DELETE /providers/:id` | Xoá |
| `GET /analytics/overview?days` | Revenue/orders/devices/credit/ai/keys tổng hợp |
| `GET /analytics/usage?days` | Usage theo ngày × action |
| `GET /analytics/retention?weeks` | Cohort retention theo tuần đăng ký (V10, xem docs/PLAN.md) — `{weeks, cohorts: [{cohortWeek, cohortSize, retention:[{offsetWeeks,active,pct}]}]}`, dùng lại `Device.firstSeenAt`/`lastSeenAt`, không thu thập gì mới |
| `GET /audit-log?action&target&page&limit` | Nhật ký hành động |

## Model (`src/models/`) — dựng lại 2026-08-10, xem `docs/TEST_LOG.md` V0

`Device`, `ActivationKey`, `Order`, `CreditLedger`, `CreditHold`, `AiProvider`,
`AppConfig`, `UsageLog`, `AuditLog`, `JobResult` — field/enum/index chi tiết
nằm trực tiếp trong từng file (comment giải thích lý do mỗi ràng buộc).

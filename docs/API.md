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

**`targetLang` (mini-spec V15, thêm 2026-08-11)** — `/translate`, `/analyze`,
`/review` giờ nhận `targetLang` (2-3 ký tự thường, vd `"vi"`/`"en"`, mặc định
`"vi"` — **0 regression** cho client cũ không gửi field này). BUG THẬT đã
sửa: trước đây KHÔNG có field này, prompt hardcode dịch sang tiếng Việt bất
kể client đang lồng tiếng ngôn ngữ nào — lồng tiếng tiếng Anh (mini-spec
V8/V11) qua SaaS thực chất vẫn nhận về tiếng Việt (field `text_vi` thay vì
`text_en` client đang tìm). Field response đổi theo: `text_<targetLang>`,
không còn cố định `text_vi`. Xem `docs/TEST_LOG.md` mục V15.

### `POST /translate`
Body: `{ jobId, holdId?, sourceLang? (default zh-CN), targetLang? (default vi), cpsBudget? (4-40, default 12.5), segments: [{id,text,duration?,max_chars?}], prevContext?, context?: {videoTitle,domain,context,pronouns,glossary,styleNotes} }`
Response: `{ jobId, segments: [{id,text_<targetLang>}], creditCharged, balanceAfter }`
Lỗi: `400 BATCH_TOO_LARGE`, `400 SEGMENT_TOO_LONG`, `402 INSUFFICIENT_CREDIT`,
`503 AI_UNAVAILABLE`/khác (kèm `retryAfter`).

### `POST /analyze`
Body: `{ jobId, holdId?, sourceLang?, targetLang?, videoTitle?, lines: string[] (max 400) }`
Response: `{ jobId, analysis: object|null, creditCharged, balanceAfter }` — lỗi
model KHÔNG throw ra ngoài, trả `analysis: null, creditCharged: 0` (bước phụ
trợ, không được chặn luồng dịch chính).

### `POST /review`
Body: `{ jobId, holdId?, sourceLang?, targetLang?, cpsBudget?, context?, items: [{id,reason(enum cjk|over_budget|too_short),text,current,duration?,max_chars?,neighbors?}] (max 60) }`
Response: `{ jobId, segments: [{id,text_<targetLang>}] (chỉ câu sửa được), creditCharged, balanceAfter }`

### `POST /generate-post`
Body: `{ jobId, holdId?, scriptOriginal (max 20000), scriptVi (max 20000), videoTitle? }`
Response: `{ jobId, metadata: object, creditCharged, balanceAfter }`
Lỗi: `402 INSUFFICIENT_CREDIT`, `503 AI_UNAVAILABLE`.

### `POST /translate-subtitle` (mini-spec V14, thêm 2026-08-11)
Dịch phụ đề rời (`.srt`/`.vtt` độc lập, không gắn video nào đang lồng tiếng) —
TÁCH KHỎI `/translate` ở trên (payload đó gắn `duration`/`max_chars`/
`cpsBudget` cho ràng buộc tốc độ đọc TTS, không áp dụng cho phụ đề thuần).
Ngôn ngữ là mã **FLORES-200** (vd `"vie_Latn"`), KHÔNG phải khoá ngắn "vi"/"en"
như `/translate` — xem `autodub/text/flores200.py`.
Body: `{ jobId, holdId?, sourceFlores, targetFlores, sourceName?, targetName?, items: [{id,text}] }`
Response: `{ jobId, segments: [{id,text}], creditCharged, balanceAfter }`
Billing: mỗi dòng tính giá `credit.cost.segment.autotranslate` — KHÔNG cộng
`credit.cost.segment.base` (phần đó gắn xử lý ASR/dub segment, không áp dụng
ở đây).
Lỗi: `400 BATCH_TOO_LARGE`, `400 SEGMENT_TOO_LONG`, `402 INSUFFICIENT_CREDIT`,
`503 AI_UNAVAILABLE`/khác (kèm `retryAfter`).

## `/v1/jobs` (mọi route cần token) — mini-spec V9 → V12, CHỈ stage Demucs

Không thay thế luồng local — TUỲ CHỌN thêm (`autodub.cloud_render`, GUI: ô
"Xử lý tách nhạc trên cloud" ở bước Nghe và chép lời). Chính sách dữ liệu:
file input/output XOÁ NGAY sau khi tải xong CẢ HAI stem (hoặc theo TTL
`cloud.render.ttl.hours`, mặc định 2 giờ, làm lưới an toàn dự phòng).

V12 BREAKING CHANGE so với V9: job xử lý BẤT ĐỒNG BỘ thật (trước đây `POST
/jobs/demucs` giữ HTTP mở tới khi Demucs chạy xong — không chịu được video
dài, timeout HTTP). Xem docs/PLAN.md mục V12 "Audit Before Build" cho lý do
an toàn để đổi contract ngay bây giờ.

### `POST /jobs/demucs` — nộp job, TRẢ VỀ NGAY (không đợi xử lý)
Multipart, field `file` (audio, tối đa 200 MB).
Response: `{ jobId, status: "queued", async: true, balanceAfter }` — client
PHẢI tự poll `GET /jobs/:jobId` tới khi `status` là `"done"`/`"failed"`.
Lỗi: `400 NO_FILE`/`EMPTY_FILE`, `402 INSUFFICIENT_CREDIT`, `409 CLOUD_RENDER_DISABLED`.
Trừ Vox theo `credit.cost.cloud.demucs` (mặc định 50) NGAY LÚC NỘP — mất
tiền cả khi job fail (đã tốn tài nguyên máy chủ), không hoàn.

### `GET /jobs/:jobId`
Response: `{ jobId, stage, status, error?, creditCharged, expiresAt }`.
`status`: `queued` → `running` (worker đã nhận, xem `/internal/jobs/claim`)
→ `done`/`failed`. `running` quá lâu không thấy heartbeat (mặc định 5 phút,
`cloud.render.heartbeat.stale.minutes`) tự chuyển `failed` — worker chết
giữa chừng không treo job mãi.

### `GET /jobs/:jobId/result/:stem` (`stem` = `vocals` | `no_vocals`)
Trả file `.wav` (`Content-Disposition: attachment`). Sau khi CẢ HAI stem đã
được tải, server tự xoá thư mục job.
Lỗi: `400 BAD_STEM`, `404 NOT_FOUND`/`RESULT_NOT_FOUND`, `409 NOT_READY`,
`410 RESULT_EXPIRED` (đã bị dọn — tải trước đó hoặc quá TTL).

## `/internal/jobs` (header `X-Worker-Token`, KHÔNG dưới `/v1`) — mini-spec V12

API nội bộ cho `control_server/worker/render_worker.py` (container Python
riêng, torch+demucs) — poll job, báo tiến độ, trả kết quả. KHÔNG bao giờ gọi
từ client thiết bị/website; secret riêng (`WORKER_INTERNAL_TOKEN`) tách hẳn
khỏi token thiết bị và `ADMIN_TOKEN`.

### `POST /internal/jobs/claim` — `{ workerId }`
Nhận 1 job `queued` cũ nhất (FIFO, atomic). Response:
`{ job: { jobId, stage, inputPath, vocalsPath, noVocalsPath } | null }`.

### `POST /internal/jobs/:jobId/heartbeat` — `{ workerId }`
Báo còn sống trong lúc xử lý dài. `409 JOB_NOT_OWNED` nếu sweeper đã coi job
là chết (heartbeat quá trễ) và chuyển `failed` rồi — worker dừng xử lý.

### `POST /internal/jobs/:jobId/complete` — `{ workerId, resultPaths: {vocals, no_vocals} }`
### `POST /internal/jobs/:jobId/fail` — `{ workerId, error }`
Cả hai `409 JOB_NOT_OWNED` nếu `workerId` không khớp worker đang giữ job.

## `/v1/config` — bổ sung mini-spec V12
`GET /config/app` giờ có thêm `cloudRenderEnabled: bool` và
`pricing.cloudRenderDemucs: number` — GUI đọc TRƯỚC khi cho bật ô "Xử lý
trên cloud" để hiện đúng giá (guardrail 4 của V12, không trừ Vox rồi mới báo).

## `/v1/telemetry` (mọi route cần token) — mini-spec V13

Trạng thái tiến trình lồng tiếng — CHỈ gửi khi client ở chế độ SaaS
(`saas_client.is_configured()==True`, guardrail 5, xem
`autodub/telemetry.py`). Banner minh bạch (`autodub_gui/first_run.py`,
`help_page.py`) đã cập nhật nói rõ việc này TRƯỚC KHI tính năng gửi bất kỳ
dữ liệu thật nào (guardrail 1).

### `POST /telemetry/pipeline-event`
Body: `{ runId, status: "started"|"completed"|"failed", stage, errorStage? }`.
`stage` phải là 1 trong `autodub.progress.STEPS` (acquire/extract/separate/
asr/translate/tts/merge_audio/merge_video/content/done). `fingerprint` lấy
từ token đã xác thực, KHÔNG đọc từ body. Upsert theo `(fingerprint, runId)`
— gọi nhiều lần với `status:"started"` chỉ cập nhật `stage`/`updatedAt`
(điểm dừng mới nhất), KHÔNG tạo document mới.

**Guardrail 2 — chặn nội dung THẬT, không chỉ quy ước**: field nào ngoài
`runId`/`status`/`stage`/`errorStage` đều bị từ chối `400 FORBIDDEN_FIELD`
— server validate nghiêm, không âm thầm bỏ qua field lạ. Event KHÔNG BAO
GIỜ được chứa nội dung video/transcript/audio/đường dẫn file.

Lỗi: `400 BAD_RUN_ID`/`BAD_STATUS`/`BAD_STAGE`/`FORBIDDEN_FIELD`.

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
| `GET /keys?status&code&note&page&limit` | Danh sách key (`note` lọc theo ghi chú, không phân biệt hoa/thường — tìm lại cả lô key phát cho 1 khách) |
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
| `GET /analytics/pipeline-funnel?days&staleHours` | Phễu hoàn thành/bỏ dở (V13, xem docs/PLAN.md) — `{days, staleHours, funnel:[{stage,count}], started, completed, failed, abandoned}`. `funnel` là 6 chặng `acquire→separate→asr→translate→tts→merge_video`, đếm số run PHÂN BIỆT đã từng đạt tới mỗi chặng. `abandoned` = ước lượng (`started` không cập nhật quá `staleHours` giờ, mặc định 6) — KHÔNG phải sự thật tuyệt đối, không có sự kiện "abandoned" tường minh. Nguồn: `PipelineEvent`, chỉ ghi từ client ở chế độ SaaS. |
| `GET /audit-log?action&target&page&limit` | Nhật ký hành động |
| `GET /api-keys?status&page&limit` | Danh sách API key developer bên thứ 3 (V31 — ẩn `keyHash`) |
| `POST /api-keys` | `{orgName, contactEmail?, quota? (default 1000)}` — tạo key mới, trả `apiKey` PLAINTEXT đúng 1 LẦN (không đọc lại được sau) |
| `DELETE /api-keys/:id` | Thu hồi key (`404` nếu không tồn tại) |

## `/api/v1` — API dịch thuật công khai cho developer bên thứ 3 (mini-spec V31, docs/PLAN.md Phase G)

Auth: header `Authorization: Bearer <apiKey>` (`vx_live_...`, cấp qua
`POST /v1/admin/api-keys` — hiện chưa có self-service portal). Đây là lớp
identity THỨ 2, SONG SONG với device-fingerprint của app desktop — hoàn
toàn tách biệt, không đụng `/v1/ai/*`.

**Phạm vi ban đầu (V31) CHỦ ĐÍCH hẹp: CHỈ dịch văn bản** (tái dùng đúng luồng
dịch phụ đề V14, không gắn "video context"). **Mở rộng ở V34a→V34b**: thêm
`/dub*` — ASR+dịch+TTS+mux đầy đủ, chạy trên `control_server/worker-dub/`
(Docker, CPU-only) — KHÔNG còn đúng câu "KHÔNG có ASR/TTS/video qua API
này" của bản audit V31 gốc nữa, xem "Audit Before Build" của V34a trong
docs/PLAN.md để biết bối cảnh mở rộng.

Billing: mỗi API key có `quota`/`usageCount` riêng cho `/translate` (KHÔNG
dùng chung ví Vox với app desktop). `/dub*` dùng CẶP FIELD RIÊNG
`dubMinutesQuota`/`dubMinutesUsed` (đơn vị PHÚT video, khác "lượt gọi") —
2 hệ billing độc lập trên cùng 1 `ApiKey`, xem Constraint 2 của V34b.

### `GET /me`
Xem thông tin + quota của CHÍNH API key đang xác thực (không lộ key khác).

Response 200: `{orgName, status, quota, usageCount, remaining, dubMinutesQuota,
dubMinutesUsed, dubMinutesReserved, dubMinutesRemaining, lastUsedAt}`
— `dubMinutesReserved` (V43) là phút đang giữ chỗ cho job `queued`/`running`
của chính key này; `dubMinutesRemaining` đã trừ luôn phần này.

### `POST /translate`
Body: `{sourceFlores, targetFlores (mã FLORES-200, vd "vie_Latn"), sourceName?, targetName?, items: [{id, text}]}`

Response 200: `{segments: [{id, text}], quota, usageCount}`

Lỗi:
- `401 NO_API_KEY` / `401 BAD_API_KEY` — thiếu/sai API key
- `403 API_KEY_REVOKED` — key đã bị admin thu hồi
- `400 BATCH_TOO_LARGE` / `400 SEGMENT_TOO_LONG` — vượt trần cấu hình (dùng
  chung `ai.max.segments.per.request`/`ai.max.chars.per.segment` với
  `/v1/ai/translate-subtitle`)
- `429 QUOTA_EXCEEDED` — hết quota, kèm `{quota, usageCount}`
- `503 AI_UNAVAILABLE` — mô hình dịch tạm thời không phản hồi

### `POST /dub?sourceLang&targetLang&voice?&bgMode?&estimatedMinutes?` (mini-spec V34a→V34b→V43)
Upload video (`multipart/form-data`, field bất kỳ có `filename`, giới hạn
`cloud.dub.max.upload.mb`). `bgMode` = `none` | `demucs`. `estimatedMinutes`
(V43, tuỳ chọn) — caller tự khai thời lượng ước tính (phút) để giữ chỗ
quota chính xác hơn; không khai thì dùng mặc định cấu hình
`cloud.dub.reservation.default.minutes` (kẹp trần
`cloud.dub.reservation.max.minutes`). Đây CHỈ là ngưỡng chặn submit tràn
lan — **Vox/phút trừ thật luôn tính lại SAU** theo `durationS` worker đo
được (`chargeDubUsage`), không phụ thuộc số đã khai.

TRẢ VỀ NGAY (không đợi xử lý xong — dub mất nhiều phút):
Response 200: `{jobId, status:"queued", async:true, bgMode, estimatedCostVoxPerMinute, reservedMinutes}`

**Định dạng 2 tham số ngôn ngữ KHÁC NHAU** (dễ nhầm vì đứng cạnh nhau):
`sourceLang` nhận khoá ngắn HOẶC BCP-47 (`vi` và `vi-VN` đều hợp lệ);
`targetLang` CHỈ nhận khoá ngắn (`vi`, không phải `vi-VN`). Danh sách hợp
lệ nằm ở `control_server/src/utils/dub-langs.js` — bản sao TAY của
`autodub/languages.py`, có `tests/dub-langs.test.js` đọc thẳng file Python
để chặn trôi lệch.

Lỗi:
- `409 CLOUD_DUB_DISABLED` — tính năng đang tắt
- `402 DUB_QUOTA_EXCEEDED` — không đủ quota phút còn trống (đã dùng + đang
  giữ chỗ cho job khác + job này ước tính > hạn mức)
- `400 MISSING_LANG` / `400 BAD_BG_MODE` / `400 NO_FILE` / `400 EMPTY_FILE`
- `400 BAD_SOURCE_LANG` / `400 BAD_TARGET_LANG` (2026-08-17) — mã ngôn ngữ
  không hỗ trợ, response kèm luôn danh sách hợp lệ. Chặn NGAY tại cửa vào:
  trước đây chuỗi bất kỳ cũng lọt, job chạy hết bước ASR (tốn quota + vài
  phút CPU worker) mới hỏng với lỗi mơ hồ không chỉ ra được sai ở đâu
- `413 UPLOAD_TOO_LARGE` (mini-spec V44) — file vượt
  `cloud.dub.max.upload.mb`. Server nhận theo dòng nên chỉ biết khi đã đọc
  quá hạn mức: bản cụt trên đĩa bị xoá, quota giữ chỗ được trả lại, KHÔNG
  job nào được tạo. Cùng mã lỗi này áp dụng cho `POST /v1/jobs/demucs`
  (hạn mức 200 MB) — cũng chuyển sang nhận theo dòng ở V44, và ở đó thứ tự
  đã đảo thành "ghi file xong mới trừ Vox" để upload hỏng không mất tiền

### `GET /dub/:jobId`
Response 200: `{jobId, status, error?, metrics? (khi done), costVox? (khi done), expiresAt}`

### `GET /dub/:jobId/result`
Tải video kết quả — **xoá file NGAY sau khi trả** (chính sách dữ liệu V9).
`409 NOT_READY` nếu chưa `done`; `410 RESULT_EXPIRED` nếu đã tải/quá TTL.

**`410 RESULT_LOST_REFUNDED` + tự hoàn phí (2026-08-17)** — nền tảng đang
chạy (Vibe Host) KHÔNG có volume bền vững: redeploy là mất sạch file kết
quả trong khi bản ghi Mongo vẫn `done` và quota phút ĐÃ bị trừ. Đã chứng
minh bằng thực nghiệm trên prod (job done → tải được → redeploy → cùng job
đó mất file). Vì vậy khi job `done` mà file biến mất **trước khi khách kịp
tải**, server tự hoàn số phút đã trừ và trả:

```json
{"code":"RESULT_LOST_REFUNDED","minutesRefunded":1,"message":"..."}
```

Phân biệt với 2 ca mất file CHÍNH ĐÁNG (không hoàn): đã tải xong rồi
`cleanupJob` dọn (nhận biết bằng field mới `deliveredAt`, đặt lúc stream
đóng) và hết TTL (`now >= expiresAt`) — 2 ca này vẫn trả `410
RESULT_EXPIRED` như cũ. Quyền hoàn nằm trong điều kiện `findOneAndUpdate`
nên poll nhiều lần chỉ hoàn ĐÚNG 1 lần; dòng hoàn ghi số ÂM vào
`DubUsageLedger` để sổ cái giữ nguyên tính append-only.

### `POST /internal/dub-jobs/*` — API nội bộ cho `worker-dub` (không public)
Xác thực `X-Worker-Token` (`WORKER_INTERNAL_TOKEN`), tách hẳn API key
developer và device token. `claim` (nhận job) / `heartbeat` / `complete` /
`fail` như `/internal/jobs/*` của V12, **cộng 2 đường truyền file thêm
2026-08-17** khi bỏ phụ thuộc volume dùng chung:

- `GET /internal/dub-jobs/:id/input` — stream video nguồn xuống worker
- `POST /internal/dub-jobs/:id/output` — worker gửi video kết quả lên

Cả hai gác bằng `getRunningJobForWorker()` (cùng điều kiện
`{_id, workerId, status:'running'}` mà heartbeat/complete đã dùng), bẫy
`CastError` → `409` để jobId sai định dạng không thành `500`. Stream 2
chiều, KHÔNG `toBuffer()` (video hàng trăm MB); upload bị cắt do vượt hạn
mức thì xoá file cụt + trả `413` thay vì báo "xong" với video hỏng. Đây là
đường DUY NHẤT, không rẽ nhánh theo môi trường — chạy đúng cả trong
`docker-compose` lẫn khi 2 service ở 2 máy khác nhau.

## Model (`src/models/`) — dựng lại 2026-08-10, xem `docs/TEST_LOG.md` V0

`Device`, `ActivationKey`, `Order`, `CreditLedger`, `CreditHold`, `AiProvider`,
`AppConfig`, `UsageLog`, `AuditLog`, `JobResult` — field/enum/index chi tiết
nằm trực tiếp trong từng file (comment giải thích lý do mỗi ràng buộc).
`RenderJob` (V9→V12) và `PipelineEvent` (V13) thêm sau, cùng quy ước.
`ApiKey`/`ApiUsageLedger` (V31, docs/PLAN.md Phase G) — API key developer
bên thứ 3 + sổ cái lượt gọi, TÁCH HẲN khỏi `Device`/`CreditLedger`.

# ARCH.md — VoxDub Studio (voidmix)

Status: Draft (sinh từ audit code 2026-08-10, cần chủ dự án review)

## 1. Tổng quan hệ thống

VoxDub Studio là ứng dụng desktop Windows lồng tiếng Việt tự động cho video nước ngoài
(YouTube/TikTok/Douyin/Bilibili hoặc file local), chạy pipeline AI hoàn toàn trên máy
người dùng (offline-first), có thêm một lớp SaaS tuỳ chọn (`control_server` + `website`)
cho dịch tự động qua AI và hệ thống tín dụng "Vox".

```
                      ┌─────────────────────────────┐
                      │        autodub_gui           │  PySide6 desktop app (14 trang)
                      │  (entrypoint: autodub-gui)    │  duy nhất — không có CLI
                      └──────────────┬────────────────┘
                                     │ import
                      ┌──────────────▼────────────────┐
                      │           autodub/             │  core pipeline, thuần Python
                      │  (importable as a library)      │  ~16k LOC
                      │  DubPipeline.run() — pipeline.py │
                      └──────────────┬────────────────┘
     Download │ Audio split │ Demucs │ ASR │ Translate │ TTS │ Timing │ Subtitle │ Mux
                                     │
                                     │ optional (VOXDUB_API_URL set)
                      ┌──────────────▼────────────────┐
                      │        control_server           │  Node 20 + Fastify 5 + Mongoose 8
                      │  licensing / Vox credit / AI     │  ~4.7k LOC
                      │  gateway / billing (PayOS)        │  serves website/dist cùng process
                      └──────────────┬────────────────┘
                                     │
                      ┌──────────────▼────────────────┐
                      │            website               │  React 18 + Vite + Tailwind + Zustand
                      │  storefront + /admin panel        │  ~5.2k LOC
                      └─────────────────────────────────┘
```

## 2. Thành phần

### 2.1 `autodub/` — Core pipeline (thư viện Python, không phụ thuộc GUI)

Orchestrator: `pipeline.py` (`DubPipeline.run()`, ~1946 dòng).

| Giai đoạn | Module chính | Kỹ thuật |
|---|---|---|
| Download | `media/downloader.py`, `media/douyin.py` | yt-dlp; Douyin qua Playwright/Chromium custom (yt-dlp extractor gãy) |
| Audio extraction | `media/audio.py` | ffmpeg dual-extract (16kHz mono ASR + 44.1kHz stereo HQ mix), 1 lần decode |
| Tách nhạc nền | `media/vocal_separator.py`, `media/demucs_worker.py` | Demucs (`htdemucs`) qua subprocess `.venv-gpu` (CUDA) hoặc fallback CPU (Demucs Python API + `soundfile`) |
| ASR (nghe-chép) | `speech/transcriber.py`, `asr_whisper_worker.py`, `paraformer_transcriber.py` | faster-whisper (GPU fp16→int8→CPU int8 fallback chain, subprocess `.venv-whisper`); Paraformer (sherpa-onnx, CPU-only, tiếng Trung) làm engine thay thế, tự fallback về Whisper khi lỗi |
| Dịch | `text/translate_saas.py`, `translate_hint.py`, `translate_review.py` | (A) thủ công: ghi `TRANSLATE_PENDING.txt`, người dùng tự dịch bằng ChatGPT/Gemini; (B) tự động: gọi `control_server` `/v1/ai/*` (3-pass analyze→translate→review), gate bởi `saas_client.is_configured()`. **Không có MT engine local** — auto-translate chỉ chạy khi có server. |
| TTS | `speech/tts/vieneu_vi.py`, `vieneu_worker.py`, `capcut_vi.py` | VieNeu (ONNX, CPU, subprocess `.venv-vieneu`, hỗ trợ voice-cloning từ WAV 5-10s); CapCut (API không chính thức, network-based) — 2 engine độc lập, không fallback lẫn nhau |
| Timing/khớp thời gian | `speech/align.py`, `media/timing.py`, `media/retime.py` | Render 1:1 theo segment; "soft timing fit" đẩy đoạn tràn vào khoảng lặng trước, nén `atempo` là phương án cuối (có trần); karaoke chạy lại Whisper `base` trên chính audio TTS để lấy word-level timestamp |
| Phụ đề | `text/srt.py`, `text/ass_karaoke.py`, `media/subtitle.py` | SRT + ASS karaoke (word-pop/fade/highlight), 6 preset style |
| Mux video | `media/video.py` | ffmpeg, auto-detect hardware encoder (NVENC→QSV→AMF→libx264, test bằng encode thật 1 frame) |
| Đồng bộ khẩu hình (tuỳ chọn) | `media/lipsync.py`, `media/lipsync_worker.py` | MuseTalk qua subprocess `.venv-lipsync` — **NGOẠI LỆ kiến trúc: GPU-only, không có đường CPU fallback** (mọi engine khác trong bảng này đều GPU-optional). Mặc định TẮT (`DubRequest.lipsync`), phạm vi CỐ TÌNH hẹp (1 khuôn mặt, video ≤12s) — xem `docs/TEST_LOG.md` mục V32a/V32b, **CHƯA live-verify GPU thật trên đường code production, CHƯA có GUI**. |
| "Che chữ gốc" | `media/subtitle.py` (`blur_filter`) | **Chỉ là `boxblur` ffmpeg trên rectangle người dùng tự vẽ tay trong GUI (`style_dialog.py`) — không phải OCR/inpainting tự động.** |
| Editor | `editor.py` (~1200 dòng) | Sửa từng câu: split/merge/add/delete, re-synth từng đoạn, đổi giọng riêng đoạn, lịch sử export |
| Batch | `batch.py` | Xử lý nhiều URL, prefetch pipelining, resume an toàn (`batch_state.json`) |
| Content/metadata | `content/generator.py` | Sinh title/description/hashtag — **chỉ chạy khi có server** (server-side) |
| Licensing/credit (Vox) | `billing.py` (`HoldBillingAdapter`, tách khỏi `pipeline.py` ở mini-spec V2), `securestore.py`, `device_id.py`, `keystore.py` | Hold credit sau ASR, mã hoá AES-256-GCM artifact trung gian đến khi export/commit hold. `pipeline.py` chỉ còn gọi delegate sang `billing.py`. **Global `HOLD`/`USAGE` (`text/translate_common.py`) vẫn được đọc trực tiếp ở nhiều module khác (`translate_saas.py`, `translate_review.py`, `translate_hint.py`, `content/generator.py`, và ngay trong `DubPipeline.run()`) — chưa tách hoàn toàn khỏi core, xem `docs/TEST_LOG.md` mục V2 cho lý do và giới hạn.** |

Ngôn ngữ đích: tiếng Việt (mặc định) + tiếng Anh (mini-spec V8→V11, đánh dấu
"thử nghiệm" trong GUI — engine giọng đọc chỉ CapCut qua mạng, chưa có giọng
offline như VieNeu tiếng Việt). `languages.TARGETS` là registry duy nhất
(`autodub/languages.py`); `voices.catalog()`/GUI đều target-aware, xem
`docs/TEST_LOG.md` mục V11. Nguồn giới hạn ~8 lựa chọn trong GUI (zh-CN/
en-US/zh-HK/zh-TW/ko-KR/ja-JP/th-TH/id-ID, mini-spec V4) dù Whisper hỗ trợ
~100 ngôn ngữ.

**Dịch phụ đề rời (mini-spec V14, 2026-08-11):** tính năng ĐỘC LẬP với pipeline
dub ở trên — dịch 1 file `.srt`/`.vtt` rời, không cần dự án lồng tiếng nào.
`text/subtitle_parse.py` (đọc/ghi, bỏ qua khối hỏng) + `text/subtitle_translate.py`
(orchestrate: parse → dịch local (`translate_local.run_local_worker()`, dùng
lại từ pipeline dub) hoặc SaaS (`saas_client.translate_subtitle()`, endpoint
RIÊNG `/v1/ai/translate-subtitle`, KHÔNG dùng chung `/translate` vì payload đó
gắn `cpsBudget`/prosody cho TTS không áp dụng ở đây) → ghi file mới, KHÔNG bao
giờ ghi đè). Ngôn ngữ = mã FLORES-200 (`text/flores200.py`, ~200 mã, nguồn từ
`facebookresearch/flores` repo) — KHÔNG dùng `languages.TargetLang` (gắn chặt
dub, chỉ 2 giá trị). CLI: `scripts/translate_subtitle.py`. GUI: trang "Dịch
phụ đề" riêng (`autodub_gui/pages/subtitle_translate_page.py`,
`SubtitleTranslateWorker` trong `workers.py`). CHỈ `vie_Latn`/`eng_Latn` đã
live-verify chất lượng dịch — ~190 mã còn lại trong bảng chỉ là mã hợp lệ NLLB
nhận, CHƯA kiểm chứng chất lượng thật, xem `docs/TEST_LOG.md` mục V14.

### 2.2 `autodub_gui/` — Desktop GUI

PySide6, dark theme (`theme.py` QSS + `tokens.py` là nguồn màu duy nhất). Entry:
`app.py:main()`. 15 trang, tất cả wire đầy đủ tới `autodub/` (không có mock/orphan feature).
Có prewarm trang, preflight machine check, crash handler + file log, smoke-test mode
(`AUTODUB_SMOKE=1`), setup wizard lần đầu, update checker (GitHub releases).

### 2.3 `control_server/` — SaaS backend (tuỳ chọn)

Node 20 + Fastify 5 + MongoDB/Mongoose 8. Giữ toàn bộ API key nhà cung cấp AI (desktop
app không bao giờ thấy provider/key). Định danh thiết bị = SHA-256 machine fingerprint
(không có tài khoản người dùng). Luồng: device tự đăng ký → nhận Vox trial → mua gói qua
PayOS → webhook cấp activation key → dán key vào app → cộng Vox → mỗi lần dub trừ Vox
theo segment (+ phụ phí auto-translate + phí metadata). Debit dùng `findOneAndUpdate`
atomic (không có Mongo transaction — single-node). API key nhà cung cấp AI mã hoá
AES-256-GCM tại rest.

**Cloud rendering (mini-spec V9 → V12, production-ready 2026-08-11):** tách nhạc nền
(Demucs) trên cloud thay máy người dùng, xử lý BẤT ĐỒNG BỘ thật — 2 image Docker RIÊNG:
`control_server` (Node) và `control_server/worker/render_worker.py` (Python, container
riêng, torch+demucs — build/deploy không phụ thuộc lẫn nhau). `POST /v1/jobs/demucs`
trả `{status:"queued"}` ngay, worker poll job qua API nội bộ `/internal/jobs/*`
(`X-Worker-Token`, tách hẳn token thiết bị/admin), spawn nguyên văn
`autodub/media/demucs_worker.py` qua subprocess — KHÔNG rebuild logic tách nhạc. Mongo
(`RenderJob`, có `workerId`/`heartbeatAt`) vẫn là nguồn sự thật duy nhất, không thêm
Redis/broker; worker chết giữa chừng (heartbeat quá hạn) tự động chuyển job `failed`,
không treo mãi. File input/output xoá ngay sau khi trả kết quả (chính sách dữ liệu đã
chủ dự án duyệt từ V9). GUI: ô "Xử lý tách nhạc trên cloud" ở bước Nghe và chép lời
(`autodub/cloud_render.py`), hiện giá TRƯỚC khi chạy, lỗi cloud tự fallback Demucs máy.
Live-verify thật qua worker chạy trực tiếp + `control_server` thật trong Docker — build
`docker compose` full 3-service CHƯA tự xác nhận được (mạng build torch quá chậm trong
môi trường audit, không phải lỗi thiết kế) — xem `docs/TEST_LOG.md` mục V12.

**Telemetry tiến trình (mini-spec V13, 2026-08-11):** `PipelineEvent` (1 document/run,
upsert theo fingerprint+runId) ghi trạng thái `started`/`completed`/`failed` + giai đoạn
mới nhất — CHỈ khi client ở chế độ SaaS (`autodub/telemetry.py`, cổng
`saas_client.is_configured()`, không bao giờ ở local-only). `POST /v1/telemetry/
pipeline-event` chặn NGHIÊM field ngoài runId/status/stage/errorStage (400, không âm
thầm bỏ qua) — không bao giờ nội dung video/transcript/audio. Banner minh bạch
(`autodub_gui/first_run.py`, `help_page.py`) đã cập nhật TRƯỚC khi tính năng gửi dữ
liệu. Dashboard admin có phễu 6 chặng (tải video→tách nhạc→nghe-chép→dịch→đọc giọng→
ghép video) + số bỏ dở (ước lượng theo `updatedAt` quá cũ, không phải sự thật tuyệt
đối). Xem `docs/TEST_LOG.md` mục V13.

**Dịch phụ đề rời (mini-spec V14, 2026-08-11):** `POST /v1/ai/translate-subtitle` —
endpoint RIÊNG khỏi `/v1/ai/translate` (payload/prompt của `/translate` gắn
`cpsBudget`/prosody cho TTS dub, không áp dụng phụ đề thuần). Billing: mỗi dòng
tính giá `credit.cost.segment.autotranslate` (KHÔNG cộng `segment.base`). Prompt
riêng `prompts/subtitle-translate.js` (không có bảng `LANGUAGE_RULES` theo tên
như `translate.js` — nhận `sourceName`/`targetName` hiển thị từ client, vì
không khả thi soạn luật riêng cho ~200 ngôn ngữ FLORES-200). Xem
`docs/API.md`/`docs/TEST_LOG.md` mục V14.

**Hosted dub API (mini-spec V31 → V34a → V34b → V43, hoàn thiện 2026-08-17):** lớp
identity THỨ 2 song song device-fingerprint — API key developer (`Authorization: Bearer
vx_live_…`, prefix `/api/v1/*`, middleware `requireApiKey` tách hẳn `requireDevice` của
`/v1/ai/*`). V31 chỉ mở dịch văn bản; **V34b mở ASR+dịch+TTS+mux đầy đủ chạy hoàn toàn
trên hạ tầng máy chủ** qua image Docker RIÊNG thứ 3: `control_server/worker-dub/
dub_worker.py` (Python, CPU-only, poll `/internal/dub-jobs/*` bằng `X-Worker-Token`, spawn
lại chính `autodub/` — KHÔNG rebuild pipeline). `POST /api/v1/dub` trả `{status:"queued"}`
ngay; `DubApiJob` trong Mongo là nguồn sự thật duy nhất (không Redis/broker), heartbeat
quá hạn thì `sweepStaleRunning` tự fail job. Billing dùng CẶP FIELD RIÊNG
`dubMinutesQuota`/`dubMinutesUsed` (đơn vị PHÚT) trên cùng `ApiKey` — độc lập hoàn toàn
với `quota`/`usageCount` của `/translate` và với ví Vox của desktop app. V43 thêm lớp giữ
chỗ `dubMinutesReserved` để job `queued`/`running` không cho submit tràn hạn mức, nhưng
tiền trừ THẬT vẫn tính lại sau theo `durationS` worker đo được.

**Truyền file worker ⇄ server qua HTTP, KHÔNG volume dùng chung (2026-08-17):** bản V34b
gốc giả định 2 container thấy chung 1 thư mục — sai ngay khi rời `docker-compose` (nền
tảng hiện tại là Vibe Host, mỗi service 1 container độc lập). Đã thay bằng
`GET /internal/dub-jobs/:id/input` + `POST /internal/dub-jobs/:id/output`, stream 2 chiều,
không `toBuffer()`. Đây là đường DUY NHẤT — không rẽ nhánh theo môi trường, nên
`docker-compose` local và deploy tách máy chạy CÙNG mã. Bẫy đã tránh: bản cũ tắt heartbeat
TRƯỚC khi ghi kết quả, upload trăm MB mất vài phút nên sweeper sẽ fail job giữa chừng →
upload phải nằm TRONG lúc heartbeat còn sống.

**Kết quả job không bền vững + tự hoàn phí (2026-08-17):** Vibe Host không có volume bền
vững (đã xác nhận dứt điểm qua dashboard + MCP), redeploy là mất file kết quả trong khi
Mongo vẫn `done` và quota đã trừ — tức khách trả tiền mà không nhận được hàng. Giảm đau
bằng `refundLostResult()` (`dub-job.service.js`): job `done` + file mất + CHƯA giao
(`deliveredAt` rỗng) + chưa hết TTL → hoàn phút đã trừ, ghi dòng ÂM vào `DubUsageLedger`,
trả `410 RESULT_LOST_REFUNDED`. Đây là lưới an toàn, KHÔNG phải cách chữa — chữa thật cần
object storage (xem `docs/PLAN.md` Remaining Limits).

### 2.4 `website/` — Storefront + Admin

React 18 + Vite + Tailwind + Zustand + react-router. Build ra static asset, được
`control_server` serve trực tiếp cùng origin (không cần CORS). Trang: Landing, Pricing,
Buy, Checkout, MyOrders (localStorage, không có tài khoản server-side), Download, Docs,
Faq, Contact + `/admin` SPA (Dashboard, Devices, Orders, Keys, Providers, Config, AuditLog).

## 3. Data model chính

**Không có SQL/Postgres.** MongoDB (control_server, qua Mongoose) là kho dữ liệu duy nhất
phía server: Device, ActivationKey, Order/Billing, AuditLog, ProviderConfig (đọc code
`control_server/src/models/` để lấy schema chi tiết — chưa liệt kê đủ trong audit này,
cần bổ sung khi làm mini-spec S1 "Docs & Foundation").

Phía client: không có DB — toàn bộ state là file trên đĩa dưới `output/VN/<timestamp>_vi/`
(bao gồm `data/` chứa mọi artifact trung gian để resume/cache), `.env` cho settings,
`securestore` (AES-256-GCM) cho artifact bị "hold" bởi credit system.

## 4. Điểm cần lưu ý khi maintain/nâng cấp

- Đóng gói GUI (`autodub_gui`, PyInstaller onedir) **vẫn chỉ Windows**. `control_server`
  đã Docker hoá (mini-spec V7, `docker-compose.yml` ở root) — `docker compose up` chạy
  control_server+website+mongo, verify live 2026-08-10.
- **Nền tảng chạy thật đã đổi Coolify → Vibe Host (2026-08-17).** 2 service:
  `voxdub-app` (1 container = control_server + `website/dist` cùng port) và
  `voxdub-dub-worker`; MongoDB do nền tảng tự provision. Vibe Host build theo model
  "1 subdir = build context" và subdir CHỈ nhận thư mục con ở NGAY GỐC repo — cả 2
  service đều cần context rộng hơn subdir của mình, nên deploy qua 2 nhánh phẳng SINH
  TỰ ĐỘNG: `scripts/gen_vays_dub_worker_branch.sh` → `deploy/vays-dub-worker`,
  `scripts/gen_vays_control_server_branch.sh` → `deploy/vays-control-server`. **Đổi code
  trên `main` xong PHẢI chạy lại script tương ứng rồi mới redeploy** — không sửa tay file
  sinh ra. 3 bug portability đã lộ ra và sửa trong lần chuyển này (worker không mở HTTP
  nên bị health-check giết; `HOST=127.0.0.1` mặc định trong container; `APP_ENCRYPTION_KEY`
  nền tảng tự sinh không đúng 64 hex).
- **Vibe Host không có volume bền vững** — mọi thứ ghi ra đĩa (file job, kết quả dub, cache)
  mất sau mỗi lần redeploy. Đừng thiết kế tính năng mới dựa trên giả định file sống lâu.
- Audit Linux cho `autodub/` core (V7): **614/617 test pass trên Ubuntu Linux thuần**,
  không cần patch code. Chỉ 2 điểm khoá Windows thật sự (`ctypes.windll`/`nvidia-smi` cho
  GPU trong `speech/transcriber.py`) — không phải rào cản kiến trúc lớn để chạy Linux, chỉ
  chưa ai live-verify 3 venv con nặng (Demucs GPU/VieNeu/Paraformer, cần tải model lớn).
  Xem `docs/TEST_LOG.md` mục V7 cho chi tiết.
- README định vị sản phẩm là "free/offline" nhưng bản `.exe` chính thức (build qua
  `scripts/build_exe.py`, bake sẵn `VOXDUB_API_URL`) mặc định chạy trên hệ Vox trả phí —
  chưa được README làm rõ.
- Logic thương mại (hold/credit) nằm xen trong `pipeline.py` chứ chưa tách lớp rõ ràng
  khỏi core OSS.
- Test (2026-08-11, sau Phase D V11-V13): `autodub/` (pytest) **690 test pass**;
  `control_server` **132 test pass** (integration thật, MongoDB in-memory); `website/`
  **31 test** (Vitest, chỉ logic thuần — utils/store, CHƯA test render/tương tác UI React).
  Tổng **853 test, 0 fail** — xem `docs/TEST_LOG.md` cho log live-verify chi tiết từng
  mini-spec.
- Sau V14/V15 (2026-08-11, cùng ngày): +59 test `autodub/` (749 — cộng dồn theo số test
  MỚI thêm, không tự đếm lại toàn repo trong sandbox viết mini-spec này vì thiếu
  `PySide6`/`numpy`/`ctranslate2`, xem `docs/TEST_LOG.md` mục V14), +25 test
  `control_server` (**157 pass, 1 skip, xác nhận chạy thật** `node --test tests/*.test.js`
  trong sandbox này).

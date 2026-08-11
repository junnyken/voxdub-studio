# TEST_LOG.md — VoxDub Studio

## V0 (phát sinh ngoài kế hoạch) — Dựng lại `control_server/src/models/`

**2026-08-10.** Khi bắt đầu audit-before-build cho V1 (test foundation cho
`control_server`), phát hiện `control_server` **không khởi động được**:
thư mục `src/models/` (10 file Mongoose schema) hoàn toàn thiếu trong bản
source tải về.

Bằng chứng trước khi sửa:
- `npm test` (chạy `node --test tests/*.test.js`): 43 test tổng, **5 fail**
  với `Cannot find module '../models/Order'` / `'../models/CreditHold'`.
- `node -e "require('./src/routes/holds.js')"` → crash `MODULE_NOT_FOUND`
  ngay lập tức (route billing.js tương tự với `../models/Order`).

Đây không phải lỗ hổng bảo mật (đối chiếu với audit phone-home/leak-key cùng
ngày — không có gì độc hại), mà là thiếu file khi export/chia sẻ mã nguồn.

**Xử lý** (theo lựa chọn của chủ dự án — reverse-engineer từ usage pattern,
KHÔNG có bản gốc để đối chiếu): đọc toàn bộ service/route dùng từng model
(`hold.service.js`, `credit.service.js`, `device.service.js`,
`activation.service.js`, `billing.service.js`, `config.service.js`,
`audit.service.js`, `ai-gateway.service.js`, `routes/ai.js`, `routes/admin.js`,
`routes/device.js`, `middleware/auth.middleware.js`) + 3 file test có sẵn
(nguồn ràng buộc mạnh nhất — `hold.test.js` khẳng định enum/index/unique cụ
thể) để suy ra field, type, enum, default, index, unique constraint của
10 model: `Device`, `ActivationKey`, `Order`, `CreditLedger`, `CreditHold`,
`AiProvider`, `AppConfig`, `UsageLog`, `AuditLog`, `JobResult`.

**Kết quả sau khi ghi 10 file `control_server/src/models/*.js`:**
- `npm test` → **59/59 pass** (tăng từ 43 test tổng lên 59 — các file test đã
  thấy các case liên quan Order/CreditHold trước đó không parse được do lỗi
  require chặn cả file).
- `node -e "require('./src/app.js')"` và require từng route (`admin.js`,
  `ai.js`, `billing.js`, `config.js`, `device.js`, `holds.js`) đều load sạch,
  exit 0.

**⚠️ Giới hạn quan trọng — CẦN chủ dự án review trước khi dùng với tiền
thật/production:** schema này được suy ra từ cách code ĐỌC/GHI field, không
phải từ định nghĩa gốc. Rủi ro cụ thể:
- Có thể thiếu validation/ràng buộc mà bản gốc có nhưng không lộ qua usage
  (vd giới hạn độ dài field, validator tùy chỉnh).
- Enum có thể thiếu giá trị lịch sử không còn xuất hiện trong code hiện tại
  nhưng vẫn tồn tại trong dữ liệu cũ thật (nếu có DB production từ trước).
- Index ngoài những cái được test hoặc query pattern xác nhận trực tiếp
  (`{status:1, expiresAt:1}` trên CreditHold, unique trên các code/key) có
  thể thiếu — cần benchmark lại trên dữ liệu thật trước khi tin hiệu năng.

**Bug phụ phát hiện, CHƯA sửa (đúng nguyên tắc "không tự sửa khi thấy lệch,
ghi lại"):** `control_server/scripts/create-indexes.js` liệt kê 9 model để
tạo index tường minh nhưng **thiếu `CreditHold`** — nghĩa là index
`{status:1, expiresAt:1}` (bắt buộc cho sweeper `expireSweep()`, đã được
`hold.test.js` khẳng định) hiện chỉ được tạo qua `autoIndex` lúc runtime chứ
không qua script deploy tường minh. Đây là gap có sẵn trong code gốc, không
phải do việc dựng lại model gây ra — để dành xử lý trong mini-spec V1 (không
mở rộng phạm vi V0 tự ý sửa script deploy).

**Live verification (2026-08-10, Docker `mongo:7` cục bộ, không phải dữ liệu
thật):** boot `node server.js` thật, gọi tuần tự qua HTTP:
`POST /v1/device/register` → nhận trial 500 Vox đúng cấu hình `trial.upfront.
vox` → `GET /v1/device/balance` khớp → `POST /v1/device/estimate` (10 câu,
autoTranslate+metadata) ra 140 Vox = 10×12 + 20, đúng công thức
`credit.cost.*` → `POST /v1/holds` trừ ví còn 360, breakdown khớp →
`POST /v1/holds/:id/commit` chốt đúng `chargedVox:140`, không hoàn/không truy
thu → `GET /v1/admin/reconcile` → `{checked:1, mismatches:[]}` (ví khớp sổ cái
tuyệt đối) → `GET /v1/admin/analytics/overview` → `issued:500, consumed:140,
outstanding:360` khớp chính xác. Toàn bộ luồng tiền thật (trial → hold →
commit → đối soát → analytics) hoạt động đúng trên schema dựng lại.

## Môi trường test Python cho `autodub/` (dev-only, không phải app package)

Sandbox này ban đầu KHÔNG có deps nào cài — dựng 1 venv nhẹ để chạy được gần
như toàn bộ 581+ test hiện có (không cần Demucs/VieNeu/Paraformer/torch —
những cái đó chạy trong venv con riêng lúc runtime thật, xem `docs/ARCH.md`):

```bash
python3 -m venv .venv-dev   # venv KHÁC .venv-whisper/.venv-vieneu/.venv-gpu
source .venv-dev/bin/activate
pip install pydub numpy python-dotenv requests cryptography pytest \
            PySide6 yt-dlp faster-whisper
# Hệ thống (Ubuntu/Debian) cần thêm để PySide6 (Qt) và ffmpeg chạy được:
sudo apt-get install -y libegl1 libgl1 libxkbcommon0 ffmpeg
QT_QPA_PLATFORM=offscreen pytest tests/ -q
```

Kết quả baseline (2026-08-10, trước khi sửa gì): **581 passed, 3 skipped, 0
failed** — đây là nền để đối chiếu "không regression" cho V2 trở đi. Demucs/
torch KHÔNG cần cài cho việc này — không có test nào trong `tests/` phụ thuộc
trực tiếp (test_demucs_chunking.py test logic chunking thuần, không chạy model
thật). `.venv-dev` không nằm trong `requirements.txt`/`.venv-*` chính thức của
app — chỉ để dev/CI chạy test nhanh không cần GPU.

## V1 — Test & API Docs Foundation cho control_server

**2026-08-10.** Thêm `mongodb-memory-server` (devDependency) + helper
`tests/helpers/db.js` (Mongo in-memory, mỗi file test chạy tiến trình riêng
theo cơ chế `node --test` nên không đụng nhau).

4 file integration test mới, tổng 25 test, tất cả chạm MongoDB thật (không
mock credit.service/hold.service/billing.service):

- `credit.integration.test.js` (6 test): race condition trừ ví đồng thời
  (đúng 1 thắng, ví không âm), idempotency deduct/grant, từ chối rút quá số
  dư, reconcile khớp tuyệt đối, idempotencyKey bắt buộc.
- `hold.integration.test.js` (7 test): vòng đời đầy đủ tạo→accrue→commit,
  commit idempotent, resume sau crash (tạo lại cùng holdId), hold thuộc máy
  khác bị từ chối, không đủ Vox bị từ chối, expireSweep tự commit hold quá
  hạn (không đụng hold còn hạn), canAbsorb/accrue nhất quán.
- `activation.integration.test.js` (5 test): kích hoạt hợp lệ, key dùng
  rồi bị từ chối trên máy khác, kích hoạt lại trên chính máy đó idempotent,
  key không tồn tại, race hai máy tranh cùng key (đúng 1 thắng).
- `payos-webhook.integration.test.js` (7 test, qua HTTP thật bằng
  `fastify.inject`): chữ ký đúng → chốt đơn + sinh key, chữ ký sai → 401 +
  đơn không đổi, replay không sinh key lần hai, lệch số tiền không tự chốt,
  payload thiếu field không crash 500, đơn không tồn tại vẫn 2xx (payload
  test PayOS gửi lúc đăng ký webhook), `success:false` bị bỏ qua.

**Kết quả:** `npm test` (`node --test tests/*.test.js`) → **84/84 pass**
(59 cũ từ V0 + 25 integration mới). `docs/API.md` viết xong, khớp 100% với
`src/routes/*.js` đọc trực tiếp.

**Cập nhật 2026-08-10 (theo yêu cầu chủ dự án): đã fix cả hai bug ghi nhận ở
trên**, không còn để ngỏ:
- `scripts/create-indexes.js`: thêm `../src/models/CreditHold` vào `MODELS`.
  Verify thật: chạy script trên Mongo Docker sạch → in đủ `CreditHold: 4
  index` (bao gồm `{status:1,expiresAt:1}` bắt buộc cho sweeper).
- `nodemailer`: `^6.9.16` → `^9.0.5` (bản `^7.x`/`^8.x` KHÔNG đủ — advisory
  ghi rõ bản vá thật chỉ từ `9.0.5`, đã thử `^7.0.9` trước và `npm audit`
  vẫn báo HIGH nên nâng thẳng lên 9). API `createTransport({host,port,
  secure,auth})` + `sendMail({from,to,subject,text,html})` dùng trong
  `email.service.js` không đổi qua các major version này — verify bằng
  smoke-require + gọi `createTransport` thật (không có SMTP thật để gửi mail
  test end-to-end, xem đây là giới hạn của việc verify trong môi trường này).
  `npm audit` → **0 vulnerabilities**. `npm test` → vẫn 84/84 pass sau nâng cấp.

**Chưa làm trong V1** (không phải lỗi, ngoài phạm vi mini-spec): đo % code
coverage chính xác cho credit.js/hold.js/payos.js (`node --test` không có
coverage report tích hợp sẵn không cần thêm tool) — có thể bổ sung sau nếu
cần con số cụ thể.

## V2 — Tách billing/credit khỏi core pipeline (THU HẸP phạm vi, xem lý do)

**2026-08-10.** Audit trước khi build phát hiện: `HOLD` (trạng thái hold hiện
tại của lượt chạy) là **global state** trong `autodub/text/translate_common.py`,
được đọc trực tiếp ở ~15 điểm trải trên **6 file** (kể cả ngay trong
`DubPipeline.run()` để quyết định mã hóa transcript, và trong
`translate_saas.py`/`translate_review.py`/`translate_hint.py`/
`content/generator.py`) — không chỉ trong 3-4 hàm hold-specific như mini-spec
gốc giả định. Đây là thiết kế cố ý (ambient state), không phải lỗi. Tách hẳn
"core OSS" khỏi billing theo đúng nghĩa DI interface sẽ phải đụng vào logic mã
hóa ở nhiều điểm, không thể regression-test đầy đủ trong sandbox này (không
ffmpeg thật lúc đầu, không GPU, không control_server thật, không có
`test_pipeline.py` nào bảo vệ đúng luồng hold trước đó).

**Quyết định (đã hỏi chủ dự án, chọn phương án thu hẹp):** chỉ **di chuyển
nguyên văn** (không đổi 1 dòng logic) 5 hàm hold-specific — `_setup_hold`,
`_stop_for_export`, `_settle_hold_inline`, `_money_note_for_manual`,
`_unlock_after_commit` — từ `pipeline.py` sang module mới `autodub/billing.py`
(class `HoldBillingAdapter`). `pipeline.py` giữ nguyên tên 4 phương thức cũ,
chỉ còn 1 dòng delegate; mọi call site khác trong `run()` (vd `HOLD.active`,
`HOLD.key` đọc trực tiếp để quyết định mã hóa) **không đổi gì**. Global
`HOLD`/`USAGE` giữ nguyên 100% — KHÔNG bị đụng tới.

**Verify:**
- Dựng được venv dev (xem mục trên) → baseline trước khi sửa: **581 passed, 3
  skipped**.
- Sau khi tách: `python3 -m py_compile` cả 2 file sạch, `import autodub.pipeline`
  + `import autodub.billing` OK.
- `pytest tests/ -q` sau khi tách: **vẫn 581 passed, 3 skipped** (identical) —
  0 regression trên toàn bộ suite hiện có.
- Thêm `tests/test_billing.py` — **14 test mới**, lần đầu tiên có coverage
  trực tiếp cho `_setup_hold`/`_stop_for_export`/`_settle_hold_inline`
  (trước đây 0%): thành công tạo hold, thiếu Vox chặn đúng, `HOLD_FINISHED`
  tự mở khóa lượt cũ, `HOLD_DISABLED`/`OfflineError` rơi về luồng cũ êm,
  thiếu `encKeyHex` không set HOLD, commit lỗi mạng vẫn mở khóa bằng key
  RAM, `stop_for_export` mã hóa đúng file audio ghép. Dùng file thật qua
  `tmp_path` cho phần securestore (crypto thuần, không cần mock).
- Tổng sau V2: **595 passed, 3 skipped, 0 failed**.

**Remaining limits (ghi rõ, không giấu):** `HOLD`/`USAGE` vẫn là global state
đọc trực tiếp ở 5 file khác — nếu sau này muốn tách "core OSS" thật sự khỏi
billing, cần 1 mini-spec riêng, có môi trường staging đầy đủ (ffmpeg+GPU+
control_server thật) để regression-test luồng hold end-to-end, không chỉ unit
test như V2 này.

## V3 — Minh bạch Local-vs-SaaS

**2026-08-10.** Audit `autodub_gui/first_run.py` (màn chào lần đầu) phát
hiện **1 bug thật, không phải giả định**: mục "Dịch tự động" trong `_CHECKS`
chỉ kiểm `settings.translate_enabled` (một công tắc bật/tắt trong Cài đặt,
mặc định `True`), **không kiểm `saas_client.is_configured()`** (có
`VOXDUB_API_URL` hay không). Hậu quả: người tự chạy từ mã nguồn (không cấu
hình server nào — trường hợp phổ biến nhất) vẫn thấy "✔ đã sẵn sàng — chạy
qua máy chủ VoxDub" ngay từ màn chào đầu tiên, dù thực tế lượt dịch sẽ tự
rơi về dịch tay (TRANSLATE_PENDING.txt). Đây chính xác là khoảng trống minh
bạch mà mini-spec V3 nhắm tới, không phải suy đoán.

**Đã sửa:**
- `autodub_gui/first_run.py`: tách `translate_mode_check()` — đọc đúng
  `is_configured()`, mô tả khác nhau rõ ràng cho 2 trường hợp (có server:
  nói rõ tốn Vox + phần lồng tiếng chính vẫn free; không có server: nói rõ
  dùng dịch tay, 100% free/offline).
- Thêm `mode_banner_text()` — 1 dòng chip hiển thị NGAY sau tiêu đề màn
  chào, nói thẳng "Chế độ: local-only" hay "Chế độ: có kết nối máy chủ"
  trước khi người dùng đọc bất kỳ mục nào khác.
- `autodub_gui/pages/help_page.py`: thêm mục FAQ "Ứng dụng này có tốn phí
  không?" vào `EXTRA_PROBLEMS` (mục khắc phục sự cố/FAQ đã có sẵn khung).
- `README.md`: thêm khối cảnh báo ngay đầu mục "1. Cài đặt trong 5 phút"
  nêu rõ 2 lựa chọn (tự build = 100% offline, hay bản `.exe` từ tác giả =
  có thể có máy chủ) trước khi người đọc bắt tay vào cài.

**Verify:**
- `tests/test_first_run_mode.py` (5 test mới): probe đúng False khi không
  configured, đúng True khi configured + translate_enabled, đúng False khi
  configured nhưng translate_enabled=False (case chưa ai test trước đây),
  banner text đúng nội dung cho cả 2 trạng thái.
- Live-verify thật (không chỉ đọc code): khởi tạo `QApplication` +
  `FirstRunDialog` thật ở chế độ `offscreen`, set/unset `VOXDUB_API_URL`
  thật, in ra banner + kết quả probe cho cả 2 trạng thái — khớp kỳ vọng.
  `FirstRunDialog(settings)` dựng lên không lỗi.
- `pytest tests/ -q` toàn bộ: **600 passed, 3 skipped, 0 failed** (595 +
  5 mới) — phát hiện và tự sửa 1 regression thật giữa chừng: comment giải
  thích bug lỡ chứa emoji "✅", bị `test_no_emoji_in_gui` (guard có sẵn của
  dự án) bắt được ngay — đúng như thiết kế của test đó.

**Chưa làm** (BA⇄DEV convention — xem CLAUDE.md tổ chức): toàn bộ câu chữ
viết trong mini-spec này (banner, FAQ, README) do tôi tự soạn khi không có
BA trong vòng lặp của phiên này — cần BA review lại đúng theo quy trình
trước khi coi là final wording, đặc biệt nếu công bố ra bản chính thức.

## V4 — Mở rộng ngôn ngữ nguồn ASR trong GUI

**2026-08-10.** Thêm 4 ngôn ngữ nguồn: Hàn (ko-KR), Nhật (ja-JP), Thái
(th-TH), Indonesia (id-ID) — cạnh 4 lựa chọn cũ (zh-CN/en-US/zh-HK/zh-TW).
Cập nhật `autodub/languages.py` (`SOURCE_LANG_MAP`, `WHISPER_LANG_MAP`) và
`autodub_gui/dub_constants.py` (`SOURCE_LANGS`). Không đổi `transcriber.py`
— Whisper đã nhận mọi code này từ trước (đúng như audit ban đầu ghi nhận).

Phát hiện thêm khi audit: `RecognizeStep` (bước 2, trang Tạo dự án) cho
phép chọn Paraformer + bất kỳ ngôn ngữ nào mà không cảnh báo gì — backend
(`transcriber.transcribe()`) đã tự fallback về Whisper an toàn (log warning,
không crash), nhưng GUI im lặng. Thêm `paraformer_language_mismatch()` (hàm
thuần, test được) + 1 label cảnh báo ẩn/hiện theo lựa chọn thật trong
`RecognizeStep`.

**Verify:**
- `tests/test_source_languages.py` (11 test): 8 ngôn ngữ nguồn đều có mặt
  trong `SOURCE_LANGS`, mỗi ngôn ngữ resolve đúng qua `SOURCE_LANG_MAP` →
  `WHISPER_LANG_MAP` (bắt lỗi ngay nếu ai thêm sai định dạng sau này), toàn
  bộ ma trận Paraformer × 8 ngôn ngữ đúng kỳ vọng.
- `tests/test_recognize_step_warning.py` (2 test, dựng `RecognizeStep` thật
  qua `QApplication` offscreen): cảnh báo ẩn mặc định, hiện đúng lúc chọn
  Paraformer+ngôn ngữ khác Trung, tự ẩn lại khi đổi về đúng hoặc đổi engine.
- `pytest tests/ -q` toàn bộ: **614 passed, 3 skipped, 0 failed** (600 + 14).

**Giới hạn quan trọng — CHƯA live-verify (ghi rõ theo đúng guardrail của
chính mini-spec này, không giả vờ đã kiểm chứng):** đây là thay đổi Ở TẦNG
CODE/WIRING (map ngôn ngữ đúng, GUI hiện đúng lựa chọn), KHÔNG phải xác
nhận CHẤT LƯỢNG ASR thật của Whisper trên 4 ngôn ngữ mới. Môi trường build
này không có video thật + không tải model Whisper lớn để chạy nghe-chép
thật. Trước khi công bố 4 ngôn ngữ này là "chính thức hỗ trợ", cần chạy
thật ≥1 video mỗi ngôn ngữ và đánh giá chất lượng — đúng yêu cầu Guardrail 4
của mini-spec V4 trong docs/PLAN.md. Việc này để ngỏ cho người có máy chạy
được Whisper thật (GPU hoặc đủ kiên nhẫn chạy CPU) xác nhận.

## V7 — Docker hoá control_server + audit Linux cho pipeline

**2026-08-10.** Thêm `control_server/Dockerfile` (multi-stage: build
`website/` React/Vite ở stage 1, copy `dist/` vào image chạy Node ở stage 2
— đúng layout tương đối mà `app.js` đã tự tìm `website/dist`, không đổi
code), `docker-compose.yml` ở root (control_server + mongo:7, network riêng,
volume cho dữ liệu Mongo), `.dockerignore`.

**Verify thật (không chỉ đọc Dockerfile):**
- `docker compose build` → build sạch cả 2 stage, không lỗi.
- `docker compose up -d` từ repo sạch (chỉ cần `control_server/.env`) →
  cả 2 container **healthy** (mongo qua `mongosh ping`, control_server qua
  chính endpoint `/health` có sẵn trong `app.js`).
- `GET /health` → `{"ok":true,...}`; `GET /v1/config/app` → đúng dữ liệu;
  `HEAD /` → 200 (website tĩnh được serve đúng qua cùng process, đúng thiết
  kế gốc).
- Log container xác nhận `MongoDB đã kết nối` qua network compose (tên
  service `mongo`, không phải localhost) — đúng như biến `MONGODB_URI` bị
  ghi đè trong compose.
- `docker compose down` dọn sạch sau khi verify.

**Audit khả năng Linux cho `autodub/` (phần pipeline Python, không phải
`control_server`):** sandbox build này BẢN THÂN LÀ Ubuntu Linux (không phải
Windows) — nên toàn bộ việc chạy `pytest tests/` xuyên suốt V0-V4 ở trên
**đã chính là bằng chứng Linux thật**, không cần dựng thêm container Python
riêng (sẽ trùng lặp). Số liệu thật, không suy đoán:

- **614/617 test pass trên Linux thuần** — với đầy đủ PySide6 (Qt,
  offscreen), ffmpeg, faster-whisper, yt-dlp cài qua `pip`/`apt` bình
  thường, KHÔNG cần patch code nào. 3 skip đã xác nhận cụ thể (2026-08-11,
  `pytest -rs`): cả 3 đều trong `test_no_console_flash.py`, lý do skip ghi
  rõ trong code "chỉ có ý nghĩa trên Windows" (kiểm tra không loé cửa sổ
  console — khái niệm không tồn tại trên Linux) — KHÔNG phải gap thật, là
  hành vi đúng theo thiết kế.
- KHÔNG kiểm chứng được trong sandbox này: Demucs GPU-venv
  (`.venv-gpu`, cần CUDA), VieNeu (`.venv-vieneu`, cần tải model ONNX
  ~300MB), Paraformer (`.venv-asr`, cần tải model ~500MB+VAD+punctuation)
  — 3 venv con này KHÔNG được cài trong đợt audit này (ngoài phạm vi thời
  gian), nhưng bản thân chúng đã được thiết kế chạy subprocess cô lập nên
  không có lý do kiến trúc để tin chúng phụ thuộc Windows — cần xác nhận
  thật ở người có thời gian tải đủ 3 bộ model.
- **Windows-specific CONFIRMED** (đọc code, không phải suy đoán): chỉ
  2 chỗ thật sự khoá vào Windows — `autodub/speech/transcriber.py`
  (`ctypes.windll`, `os.add_dll_directory` để nạp cuBLAS/cuDNN cho GPU) và
  `_gpu_total_vram_gb()` (shell ra `nvidia-smi`, chạy được trên Linux có
  driver NVIDIA nhưng `creationflags=CREATE_NO_WINDOW` là no-op vô hại trên
  Linux, không phải lỗi). Không có gì khác trong `autodub/` core khoá cứng
  vào Windows.

**Kết luận cho quyết định đầu tư (V9 sau này):** không có rào cản kiến trúc
lớn để `autodub/` chạy Linux — rào cản thật là 3 bộ model chưa được
live-verify (không phải "không chạy được", mà là "chưa ai thử"). Đây là
input thật, không phải ước lượng, cho quyết định V9 (cloud rendering).

## V6 — Local/offline MT engine (path C)

**2026-08-10.** Thêm đường dịch tự động thứ 3 — chạy hoàn toàn local,
không cần máy chủ, không tốn Vox — bên cạnh path A (dịch tay) và path B
(máy chủ VoxDub, 3-pass).

**Quyết định kỹ thuật quan trọng, đổi giữa chừng dựa trên bằng chứng thật:**
mini-spec V6 gốc (docs/PLAN.md) đề xuất "NLLB-200 distilled hoặc argos-
translate". Thử cài `argostranslate` trước — phát hiện nó kéo theo
`stanza`+`torch`+**toàn bộ CUDA toolkit** (nvidia-cublas, nvidia-cudnn...,
nhiều GB) chỉ để tách câu, dù bản thân việc dịch dùng ctranslate2 (CPU
thuần). Đi ngược hẳn nguyên tắc "CPU-viable, không phình bundle" của chính
mini-spec này — **đã bỏ, không dùng argostranslate**. Chuyển sang dùng
thẳng `ctranslate2` + `sentencepiece` (không torch, không CUDA) với model
NLLB-200-distilled-600M bản chuyển đổi ctranslate2 int8 cộng đồng
(`JustFrederik/nllb-200-distilled-600M-ct2-int8` trên HuggingFace, 622 MB —
đã kiểm tra file thật tồn tại, không suy đoán).

**Kiến trúc:** theo đúng convention có sẵn của dự án (mỗi engine nặng có
venv con riêng) — `.venv-mt` + `models/translate-local/` + subprocess
worker JSON-line protocol (giống hệt `asr_whisper_worker.py`). Thêm:
- `autodub/text/translate_local.py` — caller, map BCP-47→FLORES-200 cho cả
  8 ngôn ngữ nguồn (V4), gọi subprocess qua `bundled_file()` (đúng cách
  PyInstaller đã dùng cho các worker khác — không dùng `__file__.replace()`
  như bản nháp đầu, phát hiện lỗi này qua review chính mình trước khi test).
- `autodub/text/translate_local_worker.py` — chạy trong `.venv-mt`.
- `scripts/setup_translate_local.py` — tải model, smoke test, ghi
  `installed_ok.json`, theo đúng khuôn `setup_vieneu.py`.
- `autodub/config.py`: `translate_local_enabled` (mặc định `false`) +
  3 hàm path/configured theo khuôn `vieneu_configured()`.
- `autodub/pipeline.py`: `_auto_translate()` — path C chỉ kích hoạt khi
  `is_configured()==False` (SaaS luôn ưu tiên trước) VÀ
  `translate_local_enabled` VÀ đã cài — `is_configured()` vẫn là cổng SaaS
  duy nhất, path C là nhánh con của "không SaaS", không phải cổng thứ hai.
- `autodub_gui/pages/settings_fields.py`: checkbox trong tab Dịch thuật,
  nêu rõ giới hạn chất lượng ngay trong mô tả.
- `autodub.spec`: thêm worker vào `datas`, module vào `hiddenimports`
  (đã có sẵn `collect_all("ctranslate2")` từ trước — dùng ctranslate2 hoá
  ra khớp hạ tầng đóng gói có sẵn, không phải lựa chọn ngẫu nhiên).

**Verify thật (đã tải THẬT 622 MB model, chạy inference THẬT — không giả
lập):**
- `tests/test_translate_local.py` (7 test): 6 test logic thuần (map ngôn
  ngữ, `is_available`) + **1 test integration end-to-end thật**, qua đúng
  `translate_segments_local()` + subprocess worker + model NLLB thật, dịch
  2 câu tiếng Trung → tiếng Việt, assert kết quả không rỗng và không còn
  chữ Hán. Test tự skip nếu không có model (622MB không commit vào repo).
- **Thêm 1 lần verify riêng qua chính `DubPipeline._auto_translate()`
  thật** (không phải gọi thẳng `translate_local.py`) — mock `is_configured
  =False`, trỏ settings về model thật, gọi đúng API pipeline.py dùng: trả
  về đúng segment đã dịch, không phải `None` (fallback dịch tay). Xác nhận
  wiring trong `pipeline.py` đúng, không chỉ module đứng riêng đúng.
- Ví dụ dịch thật (không dàn dựng): "你好，欢迎来到我们的视频。" →
  "Xin chào, chào mừng bạn đến với video của chúng tôi." (câu dài, fluent).
  "你好，欢迎观看。" (câu ngắn) → "Xin chào, xin chào xem." — **chất lượng
  rõ ràng kém hơn hẳn với câu ngắn/cụt** — ghi nhận trung thực, đúng đúng
  cảnh báo Guardrail 5 của mini-spec ("không giả vờ ngang hàng path A/B").
- `pytest tests/ -q` toàn bộ: **621 passed, 3 skipped, 0 failed** (614 + 7).

**Giới hạn/rủi ro cần chủ dự án biết trước khi bật mặc định:**
- **Giấy phép CC-BY-NC-4.0** (Meta, kế thừa từ `facebook/nllb-200-distilled-
  600M`) — model NLLB-200 KHÔNG được dùng cho mục đích thương mại theo
  license gốc. Vì tính năng này miễn phí (không thu Vox) nên rủi ro thấp,
  nhưng đây là quyết định pháp lý cần chủ dự án xác nhận, không phải quyết
  định kỹ thuật thuần túy — đã ghi rõ trong code + script cài đặt, KHÔNG
  tự ý quyết thay.
- Chất lượng dịch câu ngắn/cụt kém hơn rõ rệt so với câu dài có ngữ cảnh —
  đúng như dự đoán (dịch 1-pass, không có ngữ cảnh video như path B).
- Chưa test với 6/8 ngôn ngữ nguồn (chỉ live-verify zh-CN qua 2 câu) — độ
  phủ ngôn ngữ đúng về mặt kỹ thuật (map FLORES-200 đúng, model NLLB hỗ
  trợ chính thức cả 8) nhưng CHƯA đo chất lượng thật cho ko/ja/th/id/
  zh-HK/zh-TW/en-US — cần thêm nếu muốn công bố "đã kiểm chứng" cho từng
  ngôn ngữ.
- `translate_local_worker.py` dùng `beam_size=4` cố định — chưa tối ưu
  tốc độ/chất lượng, đủ dùng nhưng có thể cần điều chỉnh sau khi có phản
  hồi thật từ người dùng CPU yếu (622 MB model + beam search có thể chậm
  trên máy cấu hình thấp — chưa đo thời gian thật trên CPU giới hạn).

**Cập nhật 2026-08-10 (quyết định chủ dự án, trong phiên):** đã quyết định
cả 2 điểm mở để ngỏ ở trên —
1. Chấp nhận giấy phép CC-BY-NC-4.0 vì dự án **hiện chưa thương mại hoá**
   tính năng dịch local. `translate_local_enabled` đổi mặc định
   `False→True` trong `config.py`/`.env.example`/`settings_fields.py`.
   **Cần xem lại quyết định này nếu sau này tính phí trực tiếp cho bản
   dịch** (dù hiện tại tính năng SaaS trả phí vẫn là path B riêng, không
   đụng NLLB).
2. Xác nhận không cần tối ưu nhẹ bằng mọi giá — giữ nguyên lựa chọn
   ctranslate2+NLLB-200 (đã verify tốt, 622MB) thay vì quay lại
   argostranslate (kéo theo stanza+torch+CUDA, nhiều GB) vì lựa chọn hiện
   tại đã chạy đúng, KHÔNG có lý do kỹ thuật để đổi sang bản nặng hơn chỉ
   vì "đầy đủ" — nhẹ hơn ở đây không đánh đổi chất lượng, đã verify thật.
Verify lại sau khi đổi default: `pytest tests/ -q` → **621 passed, 3
skipped** (không đổi số lượng, chỉ đổi giá trị mặc định).

## V5 — Tự động phát hiện vùng chữ overlay (OCR) thay boxblur thủ công

**2026-08-10.** Thêm bước tự động ĐỀ XUẤT vùng che chữ (watermark, tiêu đề
kênh, phụ đề cứng gốc) thay vì bắt người dùng tự vẽ rectangle từ đầu trên 1
frame tĩnh. Đúng đúng phạm vi mini-spec V5: **chỉ đổi nguồn toạ độ
rectangle**, KHÔNG đổi cách áp blur (vẫn `ffmpeg boxblur` qua
`build_filter_complex` — không sửa 1 dòng nào ở đó).

**Chọn OCR engine:** RapidOCR (ONNX Runtime, model PP-OCRv4 ~16 MB **kèm
sẵn trong gói pip**, không cần tải thêm) — không dùng EasyOCR (kéo torch)
hay PaddleOCR (kéo paddlepaddle), khớp đúng triết lý ONNX-only đã có sẵn
của dự án (VieNeu, Paraformer). Kiến trúc: `.venv-ocr` cô lập + subprocess
worker JSON, đúng convention; có đường dự phòng in-process cho dev/test.

**Thêm:**
- `autodub/media/text_regions.py` — `detect_text_regions()` (dispatcher
  subprocess/in-process), `merge_regions()` (gộp box chồng lấn qua nhiều
  frame bằng IoU), padding quanh mỗi vùng phát hiện.
- `autodub/media/text_regions_worker.py` — chạy trong `.venv-ocr`.
- `scripts/setup_ocr.py` — cài đặt + smoke test (không cần tải model riêng,
  nhẹ hơn hẳn Whisper/VieNeu/Paraformer/dịch local).
- `autodub/config.py`: `ocr_venv_python_path()`, `ocr_configured()`.
- `autodub_gui/style_dialog.py`: nút "Quét chữ tự động" (chỉ hiện khi có
  video thật — không hợp lý với khung mẫu), `_OcrWorker` (QThread, trích 3
  frame đại diện rồi quét), cộng dồn kết quả vào vùng người dùng đã tự vẽ
  (không xoá, không ép buộc — guardrail 2 của mini-spec).
- `autodub.spec`: thêm worker vào `datas`, module vào `hiddenimports`.

**Verify thật (ảnh tổng hợp bằng PIL + font CJK hệ thống, KHÔNG PHẢI video
thật — xem giới hạn bên dưới):**
- `tests/test_text_regions.py` (9 test): 5 test `merge_regions()`/`_iou()`
  thuần + 4 test integration qua **RapidOCR thật**: ảnh sạch không phát
  hiện gì (guardrail 4), phát hiện đúng 2 vùng chữ (watermark góc + tiêu đề
  dưới) đúng toạ độ tương đối, watermark lặp lại 3 frame gộp đúng thành 1
  vùng, đường subprocess (`.venv-ocr` giả lập bằng `sys.executable`) cho
  kết quả giống hệt đường in-process.
- **Verify thêm qua chính GUI thật** (không chỉ module đứng riêng): dựng
  `QApplication` + `StyleDialog` offscreen, tạo 1 video `.mp4` thật (ffmpeg,
  3 giây, ảnh tĩnh có chữ Trung), **bấm nút thật** (`.click()`), chờ
  `_OcrWorker` chạy xong qua vòng lặp `processEvents()` — canvas cập nhật
  đúng 2 vùng, nút disable lúc quét/enable lại lúc xong, đúng như thiết kế.
- `pytest tests/ -q` toàn bộ: **630 passed, 3 skipped, 0 failed** (621 + 9).

**Giới hạn quan trọng — CHƯA live-verify trên video thật (đúng nguyên tắc
"không giả vờ đã kiểm chứng" của chính phiên làm việc này):**
- Ảnh test là PIL tự vẽ (nền đơn sắc + chữ CJK render sạch), KHÔNG PHẢI
  frame video thật (nén lossy, watermark bán trong suốt, font lạ, chữ
  cong/nghiêng theo hiệu ứng, nền phức tạp — tất cả đều khó hơn nhiều cho
  OCR so với ảnh test). Guardrail của mini-spec V5 yêu cầu đo IoU trên
  video test thật trước khi coi là "đã kiểm chứng chất lượng" — **chưa làm
  được vì sandbox không có video thật nào** (chỉ có 1 file `.mp4` 3 giây tự
  tạo cho mục đích test kỹ thuật, không đại diện cho watermark/phụ đề thật
  của TikTok/Douyin/YouTube).
- Chưa đo thời gian quét thật trên video dài/độ phân giải cao (chỉ test
  video 3 giây, độ phân giải nhỏ).
- Model PP-OCRv4 kèm theo tối ưu cho tiếng Trung + Anh (`ch_PP-OCRv4`) —
  chưa xác nhận độ chính xác cho watermark/phụ đề chữ Hàn/Nhật/Thái/
  Indonesia (4 ngôn ngữ nguồn thêm ở V4) — nhiều khả năng vẫn phát hiện
  được VÙNG có chữ (text detection không phân biệt ngôn ngữ) dù có thể đọc
  sai NỘI DUNG (không quan trọng cho việc blur — chỉ cần đúng vị trí).

## V8 — Kiến trúc TTS pluggable đa ngôn ngữ đích (PROOF OF CONCEPT)

**2026-08-10/11.** Audit trước khi build (bắt buộc theo chính mini-spec
này) phát hiện 2 điều đổi hẳn đánh giá rủi ro ban đầu:

1. Interface `Synthesizer` (Protocol) **đã có sẵn** trong
   `autodub/speech/tts/base.py` — VieNeu và CapCut đã cùng tuân theo. Phần
   "kiến trúc pluggable ở tầng engine" coi như đã tồn tại.
2. **Phát hiện lớn**: `autodub/speech/tts/capcut_api/Voice.json` (catalog
   giọng CapCut) chứa **127 giọng trải 12 ngôn ngữ** (Anh 40, Trung 16+8,
   Tây Ban Nha 9, Thái 6, Indonesia 5, Pháp/Đức/Bồ Đào Nha...) nhưng
   `capcut_catalog.py` dòng 67 (cũ) lọc cứng chỉ giữ `lang == "vi-VN"` —
   105 giọng bị vứt bỏ trước khi tới tay người dùng.

**Quyết định chủ dự án (trong phiên, sau khi báo audit):** thử thật với
tiếng Anh qua CapCut API — chấp nhận rủi ro gọi API không chính thức ngoài
phạm vi ngôn ngữ ban đầu.

**Live-verify THẬT (gọi mạng thật tới CapCut, không giả lập):**
```
device profile: {aid, app_name, appvr, ..., device_id, iid, region, loc,
                  lan, pf, tdid}  (đúng hồ sơ thiết bị app đang dùng thật)
gọi CapCutClient.generate_speech(
    "Hello, welcome to our channel. Today we will talk about something
     interesting.",
    voice="en_us_006", resource_id="7114563482518819329")
→ {"status": "succeed", "text": "Hello, welcome to our channel.",
   "speaker_id": "en_us_006", "duration": 2352, "speech_url": "https://
   v16m-default.tiktokcdn.com/.../oMPpNTAY0HYQGfFvMOQAnrn8fCeGPWQMAeAKAf/"}
```
Tải file thật về (`speech_url` — CDN TikTok, không phải endpoint lạ):
**37677 byte, `ffprobe` xác nhận `duration=2.352000`** — khớp chính xác số
liệu API báo (2352 ms). **Xác nhận: CapCut TTS API thật sự tạo được audio
tiếng Anh hợp lệ**, không phải giả định — engine không hề bị khoá cứng
vào tiếng Việt ở tầng API, chỉ là app chưa từng khai thác.

**Đã làm (registry + catalog, KHÔNG đụng pipeline/GUI):**
- `autodub/languages.py`: thêm `TARGETS["en"]` (đầy đủ field
  `TargetLang`) — đánh dấu rõ trong comment là proof-of-concept, chưa dùng
  trong pipeline thật.
- `autodub/speech/tts/capcut_catalog.py`: `entries()`/`names()`/`lookup()`
  nhận tham số `lang` tuỳ chọn (mặc định `LANG = "vi-VN"` — **0 thay đổi
  hành vi cho mọi lời gọi cũ không truyền tham số**, xác nhận bằng test).

**Verify:**
- `tests/test_multilang_target.py` (7 test): `TargetLang("vi")` giữ
  nguyên y hệt trước V8, `TargetLang("en")` đăng ký đúng, `entries()`
  không tham số = hành vi cũ (đọc thật `Voice.json`, không mock), giọng
  en-US và vi-VN không trùng tên, `lookup(name, lang=...)` đúng theo ngôn
  ngữ, ngôn ngữ lạ trả về rỗng thay vì lỗi.
- Audit code: xác nhận `TARGETS` chỉ được đọc ở `languages.py` (qua
  `get_target()`), **không có nơi nào trong GUI enumerate `TARGETS.values()`
  để dựng dropdown** — nghĩa là thêm `"en"` vào registry an toàn tuyệt
  đối, không có khả năng bất ngờ lộ ra chỗ nào khác trong app.
- `pytest tests/ -q` toàn bộ: **637 passed, 3 skipped, 0 failed** (630+7).

**Remaining Limits — CHƯA làm, ghi rõ để không ai hiểu nhầm "đã xong đa
ngôn ngữ" (đúng nguyên tắc trung thực của toàn phiên làm việc này):**
- **`voices.catalog(settings)` CHƯA nhận tham số target** — vẫn trộn
  chung VieNeu (chỉ tiếng Việt) + CapCut (hiện vẫn gọi `entries()` không
  tham số = vi-VN mặc định trong `voices.py:203`). Muốn GUI thật sự chọn
  được giọng tiếng Anh, `_capcut_voices()`/`catalog()`/`resolve()`/
  `CapCutSynthesizer.__init__` đều cần nhận `target`/`lang` — chưa làm.
- **KHÔNG có UI nào để chọn ngôn ngữ đích** — trang Tạo dự án/Batch/Cài
  đặt hiện cứng `get_target("vi")` ở nhiều nơi, chưa audit hết để đổi
  sang dropdown.
- **~16 điểm trong `timing.py`/`ass_karaoke.py`/`editor.py`** giả định
  ngầm đích là tiếng Việt (CPS budget, dấu thanh, ...) — đã đếm được số
  lượng qua grep nhưng CHƯA audit từng điểm cụ thể có breaking hay không
  với văn bản tiếng Anh.
- **CHƯA chạy được 1 video thật nào lồng tiếng sang tiếng Anh end-to-end**
  — mới verify tới tầng "TTS engine tạo được audio tiếng Anh hợp lệ cho 1
  câu", chưa verify timing/ghép/xuất video cho ngôn ngữ đích mới.

**Kết luận:** V8 trong đợt này là **proof-of-concept có bằng chứng thật**
(không phải suy đoán) rằng hướng đi khả thi về mặt kỹ thuật — nền tảng
đúng để làm tiếp, nhưng KHÔNG PHẢI "đã có tính năng dịch sang tiếng Anh"
cho người dùng cuối. Việc hoàn thiện (voices.catalog target-aware + GUI
dropdown + audit timing/ass_karaoke/editor + live test 1 video thật) cần
1 mini-spec riêng, quy mô tương đương V8 gốc.

## V9 — Cloud/hybrid rendering (POC hẹp: chỉ Demucs)

**2026-08-11.** Chính sách dữ liệu **đã chủ dự án duyệt bằng văn bản
trước khi build** (đúng guardrail 2 + Success Criteria của mini-spec):
**xoá file input/output NGAY sau khi trả kết quả**, TTL `cloud.render.
ttl.hours` (mặc định 2h) chỉ là lưới an toàn dự phòng.

**Đã thêm (control_server, không đụng gì bên `autodub_gui`):**
- `src/models/RenderJob.js` — job Demucs (queued→running→done/failed),
  gắn Device, TTL + index `{status,expiresAt}` giống `CreditHold`.
- `src/services/render-job.service.js` — `submitDemucsJob()` (trừ Vox
  trước qua `credit.service` có sẵn — KHÔNG viết luồng tính phí song
  song, đúng guardrail 3; spawn **nguyên văn**
  `autodub/media/demucs_worker.py` qua subprocess — KHÔNG viết lại logic
  tách nhạc bằng Node, đúng guardrail 1), `cleanupJob()`, `sweepExpired()`
  (giống hệt mẫu `hold.service.expireSweep()`).
- `src/routes/jobs.js` — `POST /v1/jobs/demucs` (upload multipart, xử lý
  đồng bộ), `GET /v1/jobs/:id`, `GET /v1/jobs/:id/result/:stem` (tự xoá
  sau khi tải hết cả 2 stem — theo dõi qua field `downloaded`, KHÔNG suy
  luận qua sự tồn tại file).
- `config.service.js`: `cloud.render.enabled`, `credit.cost.cloud.demucs`
  (50 Vox/lượt, giá công khai mới — cập nhật test guard
  `hold.test.js` "giá nội bộ không lẫn công khai" để chấp nhận khóa mới
  này CÓ CHỦ ĐÍCH), `cloud.render.ttl.hours`.
- `@fastify/multipart` — dependency mới, cần cho upload file.

**Verify THẬT — toàn bộ chuỗi, không có bước nào giả lập:**
1. Cài `torch` (CPU build) + `demucs` + `soundfile` thật vào venv dev
   (`docs/TEST_LOG.md` mục "Môi trường test Python").
2. Chạy trực tiếp `demucs_worker.py` trên 1 file audio thật (ffmpeg sinh
   sóng sine 5s) → model Demucs tải thật từ HuggingFace, tách thật, output
   `{"ok": true, "device": "cpu"}`, sinh đúng 2 file `vocals.wav`/
   `no_vocals.wav` hợp lệ (ffprobe xác nhận duration khớp).
3. Dựng `control_server` thật (Docker Mongo + `node server.js`, biến môi
   trường `DEMUCS_PYTHON`/`DEMUCS_WORKER_SCRIPT` trỏ đúng venv/script thật)
   → **luồng HTTP đầy đủ qua curl thật**: đăng ký thiết bị → check balance
   500 Vox → `POST /v1/jobs/demucs` upload file thật → **server tự spawn
   Demucs thật, xử lý xong trong request** → trả `status:"done"`, trừ
   đúng 50 Vox (500→450, rồi 450→400 ở lượt thử 2) → `GET .../result/
   vocals` và `.../result/no_vocals` tải về 2 file `.wav` hợp lệ (ffprobe
   xác nhận duration=5.0s đúng) → **sau khi tải hết cả 2 stem, thư mục
   job trên server tự động biến mất** (đúng chính sách dữ liệu đã duyệt —
   xác nhận bằng `ls` thật, không phải đọc code).
4. Test số dư không đủ: trừ ví admin còn 10 Vox, nộp job cần 50 → nhận
   đúng `402 INSUFFICIENT_CREDIT`, ví giữ nguyên 10 (không bị trừ thêm),
   không tạo job/file mồ côi nào.
5. Viết `tests/render-job.integration.test.js` (6 test, mongodb-memory-
   server) — **1 test chạy Demucs thật** (`skip` mặc định vì cần torch+
   demucs cài sẵn, chạy thật bằng `VOXDUB_TEST_DEMUCS_PYTHON=...`) đã xác
   nhận PASS thật trong đợt audit này (16.3 giây, không mock).
6. Trong lúc verify, tự bắt được **2 bug thật** ở chính code V9 mới viết
   (không phải test giả cho qua):
   - `RenderJob.create({inputPath: ''})` — Mongoose `required: true` từ
     chối chuỗi rỗng → sửa bằng cách sinh `_id` trước, ghi file trước, rồi
     mới tạo document với `inputPath` đã có giá trị thật ngay từ đầu.
   - `test.beforeEach(() => { clearDb(); ... })` thiếu `await` — Promise
     trôi nổi gây `MongoClientClosedError` sau khi `test.after(stopDb)`
     đóng kết nối — sửa thành `async () => { await clearDb(); ... }`.
7. `npm test` (control_server) toàn bộ: **90 passed, 0 skipped, 0 failed**
   khi có `VOXDUB_TEST_DEMUCS_PYTHON` (89 passed + 1 skip khi không có).

**Remaining Limits — CHƯA làm (ghi rõ, đây là POC hẹp đúng Design Choice
gốc của mini-spec, không phải full tính năng):**
- **Xử lý ĐỒNG BỘ trong request** (không có queue/worker pool đa tiến
  trình thực sự) — mini-spec Scope B nói "worker pool", nhưng POC hẹp chỉ
  cần chứng minh khả thi kỹ thuật trước; 1 request Demucs dài (video vài
  phút) sẽ giữ HTTP connection mở lâu — cần queue thật (BullMQ hay tương
  đương) nếu mở rộng ra khỏi POC.
- **Không có UI** (toggle "Xử lý trên cloud" trong Cài đặt/Tạo dự án —
  Scope D của mini-spec) — chỉ verify qua API trực tiếp.
- **KHÔNG đo được lợi ích thời gian thật** (Test Plan mục Live verification
  của mini-spec yêu cầu so sánh ≥2 profile máy) — sandbox không có video
  dài/thật, chỉ test với audio tổng hợp 1-5 giây.
- **Docker (V7) CHƯA cập nhật** để chạy được Demucs — `docker-compose.yml`
  hiện tại chỉ có Node, không có Python/torch/demucs. Thêm vào sẽ làm
  image nặng thêm đáng kể (torch CPU ~1.2GB) — cần cân nhắc image riêng
  cho worker thay vì nhét vào chung image control_server.
- Chỉ test được stage Demucs với audio ngắn (1-5 giây) — chưa test video
  dài thật hay các stage khác (Whisper/VieNeu) mà mini-spec có thể mở
  rộng sau này.

**Kết luận:** đúng như Design Choice gốc của mini-spec — POC hẹp đã
**chứng minh được khả thi kỹ thuật thật sự** (không phải suy đoán): server
Node có thể tái dùng nguyên vẹn worker Python hiện có, luồng tiền qua
`credit.service` hoạt động đúng, chính sách xoá dữ liệu hoạt động đúng
như đã duyệt. Quyết định mở rộng thành tính năng đầy đủ (queue thật + UI +
benchmark thời gian) để dành cho 1 mini-spec riêng sau khi có số liệu thật
từ POC này.

## V10 — Analytics/dashboard SaaS thật

**2026-08-11.** Audit trước khi build: `website/src/pages/admin/
Dashboard.jsx` **đã tồn tại và khá đầy đủ** — doanh thu, thiết bị hoạt
động, Vox tiêu/lưu hành, biểu đồ Vox theo ngày, lượt gọi AI thành công/
thất bại, đơn hàng, mã kích hoạt (đọc `/v1/admin/analytics/overview` +
`/analytics/usage`, cả 2 đã có sẵn từ trước, không phải V10 tạo). Gap thật
sự (đúng như PRD §7 đã nêu): (1) phễu hoàn thành/bỏ dở pipeline — cần
telemetry MỚI từ client, chưa có trong `saas_client.py` (đã grep xác
nhận: 0 hàm nào gửi event dạng "pipeline started/completed/failed"); (2)
retention thiết bị theo thời gian — chưa có UI nào dù dữ liệu cần thiết
(`Device.firstSeenAt`/`lastSeenAt`) đã có sẵn.

**Quyết định phạm vi (tự quyết, có căn cứ từ guardrail 2 của mini-spec —
"không thu thập thêm dữ liệu cá nhân ngoài phạm vi đã công bố ở V3"):**
chỉ làm phần (2) — retention cohort, vì dùng ĐÚNG dữ liệu đã có sẵn, không
mở rộng bề mặt thu thập dữ liệu, không cần quyết định minh bạch mới. Phần
(1) phễu hoàn thành/bỏ dở cần thêm telemetry client thật — đây là thay đổi
sản phẩm/quyền riêng tư cần chủ dự án quyết định riêng, KHÔNG tự làm
(nhất quán với cách xử lý các quyết định tương tự trong V6/V9 của đợt
audit này).

**Đã thêm:**
- `control_server/src/services/retention.service.js` —
  `computeWeeklyRetention()`, hàm thuần (dễ test, không đụng DB trực
  tiếp): nhóm thiết bị theo tuần đăng ký (`firstSeenAt`), tính % còn
  `lastSeenAt` tới từng tuần sau đó.
- `GET /v1/admin/analytics/retention?weeks=` (route mới trong `admin.js`).
- `website/src/api/client.js`: `adminApi.retention()`.
- `website/src/pages/admin/Dashboard.jsx`: bảng cohort retention (heatmap
  CSS thuần, không kéo thư viện — đúng phong cách `UsageChart` đã có).

**Verify:**
- `tests/retention.test.js` (9 test): `startOfWeek()` luôn ra đúng Thứ
  Hai, cohort tuần đăng ký = offset 0 luôn 100%, thiết bị không quay lại
  → 0% tuần sau (tính tay, không đoán), thiết bị hoạt động liên tục →
  100% mọi tuần, nhiều cohort không trộn lẫn (tính tay ra đúng 50%),
  thiết bị thiếu `firstSeenAt` bị bỏ qua an toàn, giới hạn đúng số tuần
  yêu cầu. Bắt được 1 lỗi test fixture của chính mình khi viết (không
  phải bug service) — sửa và xác nhận lại.
- `npm run build` (website): biên dịch sạch, không lỗi JSX.
- **Live-verify thật qua HTTP**: dựng Mongo Docker + `control_server`
  thật, **chèn thẳng 4 Device vào MongoDB thật** qua `mongosh` với
  `firstSeenAt`/`lastSeenAt` biết trước (21 ngày trước tách 2 nhóm), gọi
  `GET /v1/admin/analytics/retention?weeks=4` thật qua curl → kết quả
  đúng 100% so với tính tay (cohort 2026-07-20: offset0=100%,
  offset1-3=50%; cohort 2026-08-03: offset0=100%, offset1=50%).
- `npm test` (control_server) toàn bộ: **98 passed, 1 skipped, 0 failed**
  (89 + 9 mới, skip là test Demucs thật của V9 cần biến môi trường riêng).

**Remaining Limits:**
- **Phễu hoàn thành/bỏ dở pipeline theo stage — CHƯA làm**, cần quyết
  định thêm telemetry client + cập nhật minh bạch cho người dùng (mở rộng
  banner V3) trước khi build, đúng guardrail của chính mini-spec V10.
- Retention tính trên TOÀN BỘ Device (không phân biệt máy đã kích hoạt
  Vox hay chỉ dùng thử) — có thể muốn tách theo đã-mua/chưa-mua sau này.
- Chưa test với dữ liệu quy mô lớn (hàng nghìn/chục nghìn Device) —
  `computeWeeklyRetention()` hiện chạy hoàn toàn trong Node process (không
  phải MongoDB aggregation), có thể cần chuyển sang aggregation pipeline
  nếu số Device thật lớn hơn nhiều so với vài nghìn.

## Re-audit 2026-08-11 — dọn các gap đã ghi nhận từ đầu nhưng chưa quay lại

Theo yêu cầu chủ dự án ("kiểm tra 1 lần nữa, thấy hình như còn thiếu") —
rà lại `docs/ARCH.md` §4 (điểm cần lưu ý, ghi từ audit ban đầu 2026-08-10)
đối chiếu với những gì đã thực sự đóng, tìm ra 3 việc có thật, đã ghi
nhận nhưng CHƯA từng có mini-spec nào quay lại xử lý:

**1. Dependency thừa `google-genai`** — đã xoá khỏi `pyproject.toml`
(0 reference trong code, xác nhận lại bằng grep trước khi xoá). `pytest`
vẫn 637/637 sau khi xoá.

**2. Lỗ hổng bảo mật chưa xử lý** (`npm audit`, cả 2 sub-project):
- `website`: `react-router-dom` dính CVE-2025-68470 (open redirect) +
  arbitrary constructor injection (moderate) — bump `^6.28.0 → ^7.18.2`
  (major, nhưng app chỉ dùng API "library mode" ổn định qua các bản: 
  `BrowserRouter/Routes/Route/Link/NavLink/useNavigate/useParams/
  useSearchParams/useLocation/Outlet/Navigate` — không dùng loader/action
  của v7). Verify: `npm run build` sạch, `npm audit` hết báo react-router.
- `website`: còn 1 lỗ hổng `esbuild`/`vite` (moderate) — advisory ghi rõ
  CHỈ khai thác được khi chạy `vite dev` server và để lộ ra mạng ngoài
  (không phải rủi ro production build). Fix cần `vite@8` (breaking) — để
  lại có chủ đích, ghi rõ lý do thay vì im lặng bỏ qua.
- `control_server`: `npm audit` → 0 vulnerabilities (đã xử lý xong ở V0/V1,
  xác nhận lại lần này vẫn sạch sau khi thêm `@fastify/multipart` ở V9).

**3. `website/` có 0 test — gap có thật từ audit đầu tiên, chưa mini-spec
nào xử lý (V1/V9/V10 chỉ thêm test cho `control_server`).** Thêm:
- `vitest` + `jsdom` (Vite-native, không cần cấu hình phức tạp).
- `src/api/format.test.js` (14 test) — 6 hàm định dạng dùng khắp UI
  (tiền VNĐ, Vox, ngày, tương đối "X phút trước", đếm ngược, rút gọn mã
  máy) — biên rỗng/null/giá trị hỏng đều được test, không throw.
- `src/store/orders.test.js` (9 test) — **bảo vệ đúng luồng lưu
  `accessToken`** (localStorage, xem comment gốc trong `orders.js`: mất
  token = mất đường lấy mã kích hoạt): ghi/đọc, ghi đè khi trùng mã đơn
  (không nhân đôi), giới hạn 20 đơn gần nhất (đơn cũ bị loại đúng, không
  loại nhầm đơn mới), `markOrderPaid` không đụng đơn khác, localStorage
  hỏng/rác không crash.
- `src/data/packages.test.js` (4 test) — công thức ước tính năng lực từ
  Vox, đủ 5 gói công khai đều có mô tả. Bắt được 1 lỗi tính tay của chính
  mình khi viết test (120000 Vox → 100 video, không phải 10) — sửa ngay,
  đúng tinh thần verify-thật xuyên suốt đợt audit này.
- `npm run build` (website) vẫn sạch sau toàn bộ thay đổi.

**Kết quả cuối cùng — cả 3 test suite của monorepo cùng xanh:**
`pytest` (autodub) **637/637 pass** + `npm test` (control_server)
**98/98 pass** + `vitest` (website) **31/31 pass** = **766 test, 0 fail**.

**Vẫn còn để ngỏ có chủ đích** (không phải bỏ sót — đã cân nhắc và quyết
định KHÔNG làm trong đợt này, lý do ghi rõ):
- `esbuild`/`vite` dev-only vulnerability (website) — rủi ro thấp, fix
  cần major bump rủi ro cao hơn lợi ích ở giai đoạn này.
- Test cho các trang React thật (component/E2E, vd Playwright) — mini-spec
  này chỉ đóng gap "0 test" bằng unit test cho logic thuần (utils/store),
  chưa test render/tương tác UI — cần 1 mini-spec riêng nếu muốn coverage
  sâu hơn (thêm `@testing-library/react`, nặng hơn đáng kể).

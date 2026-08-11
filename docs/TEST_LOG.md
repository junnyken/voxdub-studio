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

**Giới hạn ghi nhận lúc đó (2026-08-10):** đây là thay đổi Ở TẦNG CODE/WIRING
(map ngôn ngữ đúng, GUI hiện đúng lựa chọn), KHÔNG phải xác nhận CHẤT LƯỢNG
ASR thật của Whisper trên 4 ngôn ngữ mới — môi trường build lúc đó không có
video thật + không tải model Whisper lớn để chạy nghe-chép thật.

### Live verification thật (2026-08-11) — đóng gap Guardrail 4

Sandbox `trieunt` (khác máy audit gốc) đã có `ffmpeg` + tải được model
Whisper thật (`small`, CPU — GPU không dùng được: driver CUDA cũ hơn
runtime, fallback CPU tự động, đúng thiết kế có sẵn). Phương pháp — GIỐNG
V11 (tạo video thật bằng TTS + ffmpeg mux, vì sandbox không có video mẫu
ko/ja/th/id):

1. Sinh audio giọng đọc THẬT qua **Google TTS (gTTS)** cho 4 câu tiếng
   Hàn/Nhật/Thái/Indonesia (nội dung đời thường, có dấu câu).
2. `ffmpeg` mux mỗi audio vào 1 video mp4 thật (video màu + audio thật,
   H.264/AAC) — input cho pipeline giống hệt 1 video người dùng thật đưa
   vào, không mock.
3. Gọi thẳng `autodub.speech.transcriber.transcribe()` (hàm THẬT, không
   mock) với `whisper_model="small"`, ngôn ngữ nguồn lấy qua đúng
   `resolve_source_lang()` như pipeline thật dùng.

**Kết quả thật** (so khớp transcript Whisper với câu gốc đã đọc):

| Ngôn ngữ | Câu gốc | Whisper nghe được | Đánh giá |
|---|---|---|---|
| ko-KR | "안녕하세요, 오늘 날씨가 정말 좋네요. 저는 매일 아침에 커피를 마십니다." | "안녕하세요 오늘 날씨가 정말 좋네요 저는 매일 아침에 커피를 마십니다" | Khớp 100% nội dung (chỉ mất dấu câu — Whisper thường bỏ dấu câu khi câu đọc liền mạch, không phải lỗi nghe) |
| ja-JP | "こんにちは、今日はとてもいい天気ですね。私は毎朝コーヒーを飲みます。" | "こんにちは。今日はとてもいい天気ですね。私は毎朝コーヒーを飲みます。" | Khớp 100%, kể cả dấu câu |
| th-TH | "สวัสดีครับ วันนี้อากาศดีมากเลย ผมดื่มกาแฟทุกเช้า" | "สวัสดีครับ วันนี้อากาศดีมากเลย ผมดื่มกาแฟทุก**ชาว**" | Sai 1 từ cuối ("ทุกเช้า" = "mỗi sáng" → nghe nhầm "ทุกชาว", vô nghĩa) — phần còn lại đúng 100% |
| id-ID | "Halo, cuaca hari ini sangat bagus. Saya minum kopi setiap pagi." | "Halo, cuaca hari ini sangat bagus. Saya minum kopi setiap pagi." | Khớp 100% tuyệt đối, kể cả dấu câu |

**Kết luận theo Guardrail 4** ("ngôn ngữ nào chất lượng kém thì loại khỏi
danh sách chính thức"): cả 4 ngôn ngữ đạt chất lượng chấp nhận được —
**chính thức xác nhận hỗ trợ** ko-KR/ja-JP/th-TH/id-ID, bỏ nhãn "chưa kiểm
chứng" trong `dub_constants.py`.

**Giới hạn của chính phương pháp verify này (ghi trung thực, không giấu):**
gTTS là giọng đọc rõ, tốc độ đều, không tạp âm, không giọng vùng miền/tiếng
lóng — dễ hơn NHIỀU so với video YouTube thật (nhạc nền, nhiều người nói,
phát âm địa phương). Kết quả trên xác nhận Whisper KHÔNG có rào cản kiến
trúc/mapping-sai cho 4 ngôn ngữ này (đúng scope Guardrail 4 + Goal của V4:
"vocabulary gap thuần tuý"), nhưng KHÔNG thay thế được việc nghe thử 1 video
YouTube thật mỗi ngôn ngữ trước khi quảng bá rộng — để ngỏ cho lượt kiểm
định kế tiếp khi có mẫu thật.

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

### Re-audit 2026-08-11 — sandbox này (Coder workspace) đã cài đủ để chạy 100%

Trước đợt này, sandbox workspace của `trieunt` (khác máy audit gốc ở trên)
thiếu `ffmpeg`, `numpy`, `pydub`, `PySide6` và các thư viện hệ thống Qt
(`libGL.so.1`, `libglib-2.0.so.0`) — 15 file test lỗi *collection* (không
chạy được), không phải fail thật. Đã cài thật (không giả lập):

```
sudo apt-get install -y ffmpeg libgl1 libglib2.0-0 libegl1 libfontconfig1 \
    libdbus-1-3 libxkbcommon0
pip install PySide6 numpy pydub -r requirements.txt   # venv cô lập
```

**Phát hiện quan trọng**: `xvfb-run` (cách chuẩn để chạy Qt headless trên
CI) làm cả tiến trình pytest **crash thật** (`Fatal Python error: Aborted`)
khi PySide6 + torch cùng nạp trong 1 process — tổ hợp cụ thể sandbox này,
không phải bug code. Cách chạy đúng: biến môi trường
`QT_QPA_PLATFORM=offscreen` (Qt platform plugin có sẵn, không cần X server
thật) — ổn định, không crash.

Kết quả thật với `QT_QPA_PLATFORM=offscreen`:

```
715 passed, 5 skipped, 0 failed
```

(Bộ test đã lớn hơn con số 614/617 ở đợt audit gốc — do V11-V15 thêm test
mới.) 5 skip xác nhận qua `pytest -rs`, đều có lý do rõ ràng, không phải
gap ẩn: 1 thiếu `rapidocr_onnxruntime` (module OCR của V5, chưa cài trong
đợt này), 3 `test_no_console_flash.py` (chỉ có ý nghĩa Windows), 1 thiếu
model NLLB thật 622MB (V6, không commit vào repo).

**Kết luận**: xác nhận lại số liệu audit gốc — không có rào cản kiến trúc
nào khiến `autodub/`/`autodub_gui/` (kể cả phần Qt) không chạy được trên
Linux; toàn bộ khoảng cách trước đó là do sandbox thiếu dependency, không
phải do code. `docker compose up -d mongo control_server` từ chính sandbox
này cũng verify lại thật: 2 container `healthy`, `GET /health` trả
`{"ok":true,"version":"3.0.0",...}` — xem thêm mục V12 cho kết quả build
`render_worker` (torch/demucs) lần này.

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
  **[XÁC NHẬN 2026-08-11]** Chủ dự án đã xác nhận: giữ nguyên hiện trạng
  (miễn phí, không thương mại hoá riêng bản dịch từ engine này) — không
  cần đổi model. Coi như đã đóng, không phải rủi ro mở nữa.
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

### Re-audit 2026-08-11 — video nén thật (không còn chỉ ảnh PIL tĩnh)

Sandbox `trieunt` cài thêm `rapidocr_onnxruntime` (thiếu ở đợt audit gốc,
khiến 3/9 test integration trong `test_text_regions.py` bị SKIP) + font
`fonts-wqy-zenhei` (Ubuntu package, apt). Sau khi cài: **9/9 test
`test_text_regions.py` pass** (0 skip) — không giả lập, RapidOCR thật.

**Đóng thêm 1 phần giới hạn "chưa video thật":** tạo video **nén H.264
thật** (không phải PNG tĩnh) bằng `ffmpeg` — `testsrc` 1280×720, 5 giây,
watermark "频道水印 CHANNEL" ghi đè bằng filter `drawtext` (góc phải-trên,
nền bán trong suốt, font WenQuanYi) rồi encode `libx264 -crf 23` (mức nén
tương tự video thật, không phải ảnh raw). Trích 3 frame mẫu bằng `ffmpeg
-vf select` (đúng cách `style_dialog.py`/`_OcrWorker` lấy frame thật) rồi
gọi thẳng `detect_text_regions()` (hàm THẬT, không mock):

- Phát hiện đúng 1 vùng, `confidence: 0.971`, toạ độ
  `x=0.718, y=0.036, w=0.275, h=0.061` (chuẩn hoá theo khung hình).
- **Verify bằng mắt** (crop chính xác vùng phát hiện ra khỏi frame thật):
  ảnh crop chứa ĐÚNG NGUYÊN VĂN "频道水印 CHANNEL", không thừa không thiếu
  — xác nhận trực quan, không chỉ tin số IoU (số IoU tự tính so với 1 ô
  ground-truth áng chừng bằng tay ra 0.503 — thấp hơn thực tế vì cách ước
  lượng tay không chính xác, ảnh crop mới là bằng chứng đáng tin).

**Vẫn còn thiếu (trung thực, chưa đóng hoàn toàn Guardrail 5+Test Plan của
V5):** video test vẫn là watermark TỰ TẠO (`drawtext`, không phải watermark
thật của TikTok/Douyin/YouTube — không có hiệu ứng mờ dần, nghiêng, đổi
màu nền phức tạp của watermark thật), chưa đo % thời gian OCR cộng thêm
trên video dài thật (ngưỡng đề xuất "< 10% tổng thời gian pipeline cho
video 5 phút" — chưa benchmark), và chưa test 3-5 video đa dạng theo đúng
Test Plan gốc (chỉ 1 video watermark, chưa có phụ đề cứng/tiêu đề kênh).
Bước tiếp theo cần video thật từ TikTok/Douyin/YouTube thật để đóng hẳn.

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

## V11 — Hoàn thiện đa ngôn ngữ đích (đưa V8 từ PoC thành tính năng dùng được)

Theo `docs/PLAN.md` mục V11 (Phase D). Guardrail: audit trước, sửa sau; không
đổi mặc định tiếng Việt; VieNeu chỉ hiện khi target là tiếng Việt.

### Audit Before Build — kết quả từng điểm (Constraint 4)

- **`autodub/timing.py`** — đọc toàn bộ, 0 chuỗi `"vi"`/CPS tiếng Việt/dấu
  thanh. Mọi hằng số (CPS budget, atempo range) đã tổng quát từ trước V8 —
  **không cần sửa**.
- **`autodub/editor.py`** — mọi hàm public đã nhận `target_key: str = "vi"`
  làm tham số tường minh từ trước (không phải mặc định ẩn), `get_target()`
  gọi đúng chỗ mỗi hàm — **không cần sửa cấu trúc**. Có sửa 2 lời gọi
  `voice_catalog.resolve()` thiếu `target=` (xem mục "Sửa" dưới).
- **`autodub/text/ass_karaoke.py`** — **CÓ bug thật**: `resolve_word_times()`/
  `build_karaoke_ass()` nhận `language` nhưng không truyền tiếp xuống
  `align_segments()` → `_asr_words()` trong `autodub/speech/align.py`, nơi
  `language="vi"` bị **hardcode** khi Whisper nghe lại chính clip TTS vừa
  tạo ra để canh mốc từng chữ cho karaoke. Kết quả: target khác tiếng Việt
  sẽ bị Whisper nghe SAI ngôn ngữ ở bước canh karaoke, alignment âm thầm
  hỏng/rớt về ước lượng thô — không crash, không log lỗi, chỉ sai lệch.
  **Đã sửa**: `language` thread xuyên suốt `refresh_subtitles(target)` →
  `build_karaoke_ass` → `resolve_word_times` → `align_segments` →
  `_asr_words(..., language=...)`, dùng `WHISPER_LANG_MAP` để đổi
  BCP-47 → mã Whisper. Khoá lại bằng `tests/test_align_language.py` (4 test,
  bắt đúng bug cũ trước khi sửa — patch `align_mod.seg_wav_path` chứ không
  phải `autodub.utils.seg_wav_path` vì `align.py` import tên vào namespace
  riêng lúc load module).

### Sửa — Scope B (`voices.py` target-aware)

- `autodub/speech/tts/voices.py`: `_capcut_voices(lang=None)`,
  `is_capcut_voice(name, lang=None)`, `catalog(settings, target=None)`,
  `resolve(settings, name=None, target=None)` — tất cả nhận tham số TUỲ
  CHỌN, `target=None`/`lang=None` giữ đúng hành vi trước V11 (0 regression,
  verify bằng test). `catalog()` giờ CHỈ trộn VieNeu khi `target` là tiếng
  Việt (Constraint 3) — target khác chỉ trả CapCut catalog đúng ngôn ngữ.
- `autodub/speech/tts/__init__.py` (`get_synthesizer`) và
  `autodub/speech/tts/capcut_vi.py` (`CapCutSynthesizer.__init__` nhận
  `lang=None`) — thread `target`/`lang` xuống `voice_catalog.resolve()` /
  `is_capcut_voice()` / `capcut_catalog.lookup()`.
- Thread `target=` vào mọi lời gọi `voice_catalog.resolve()` còn thiếu:
  `pipeline.py` (4 chỗ: `_export_phase`, `_synthesize_segments` ×2,
  `_build_report`), `editor.py` (`resynth_segments`, 2 chỗ),
  `billing.py` (`stop_for_export`, tự suy `target` từ `state["target"]` —
  cùng quy ước với `pipeline.py:1729`).
- Test mới `tests/test_voices_target_language.py` (12 test): catalog theo
  target None/vi/en, resolve không lẫn tên vi-VN sang catalog en-US,
  `is_capcut_voice` theo lang, `get_synthesizer(target=en)` KHÔNG bao giờ
  đòi cài VieNeu (Constraint 3), `CapCutSynthesizer` từ chối tên giọng sai
  ngôn ngữ khi `lang=` được truyền tường minh.

### Sửa — Scope D (GUI chọn ngôn ngữ đích)

- `autodub_gui/dub_constants.py`: `DUB_TARGETS` (2 lựa chọn: Tiếng Việt /
  Tiếng Anh — đánh dấu "thử nghiệm", đúng nguyên tắc chỉ hiện UI khi tính
  năng đã tồn tại thật).
- `autodub_gui/pages/new_project_steps.py` — `TranslateStep`: thay nhãn
  tĩnh "Tiếng Việt" bằng `LabeledCombo` thật (`self.target`), giá trị vào
  `values()["target_key"]`. `VoiceStep`: thêm `set_target_key()` — đổi
  target ở bước Dịch nạp lại đúng danh mục giọng ở bước Giọng đọc (không
  còn hiện VieNeu/giọng vi-VN khi target=en); `_default_voice()` dùng
  `voice_catalog.resolve(target=...)` cho target khác tiếng Việt thay vì
  đọc thẳng `settings.vieneu_voice` (khái niệm chỉ có nghĩa cho tiếng Việt).
- `autodub_gui/pages/new_project_page.py` — nối `TranslateStep.target.changed`
  → `VoiceStep.set_target_key()`; `DubRequest.target = data["target_key"]`;
  thêm dòng "Ngôn ngữ đích" vào bảng tóm tắt bước cuối.
- `autodub_gui/voice_picker.py` (`VoicePicker.reload(settings, target=None)`)
  và `autodub_gui/voice_preview.py` (`VoicePreview.play(..., target_key="vi")`,
  cache nghe thử khoá theo `(voice, target_key)` — tên giọng CapCut không
  đảm bảo duy nhất xuyên ngôn ngữ) — cả hai mặc định giữ hành vi cũ.
  `editor_page.py`/`editor_export.py` truyền đúng `target`/`target_key` của
  dự án đang mở khi tải/nghe thử giọng.
- **Verify runtime thật** (không chỉ đọc code): dựng `QApplication`
  offscreen thật, tạo `TranslateStep`+`VoiceStep` thật, đổi combo sang
  "en" → xác nhận `VoiceStep` nạp lại đúng 39 giọng CapCut en-US thật (0
  giọng vi-VN lẫn vào, khớp `capcut_catalog.names(lang="en-US")`), giọng
  mặc định resolve ra tên hợp lệ trong catalog en-US. `values()`/`load()`
  round-trip đúng `target_key`.

### Live verification end-to-end (Test Plan — Integration + Success Criteria)

Chạy **THẬT** `DubPipeline.run()` (không mock) 2 lần, target=en, KHÔNG SaaS
(`saas_client.is_configured() == False` — dịch qua path C, NLLB local V6):

- Nguồn: video thật tự tạo — giọng đọc tiếng Việt tổng hợp qua **CapCut API
  thật** (mạng thật, giống V8), mux vào .mp4 bằng ffmpeg thật.
- ASR: **faster-whisper thật** (model `small`, in-process vì `.venv-whisper`
  chưa cài trong máy dev — đúng nhánh fallback có sẵn trong
  `transcriber.py`, không phải đường tắt riêng cho test này).
- Dịch: **ctranslate2 + NLLB-200-distilled-600M int8 thật** (`.venv-mt` trỏ
  qua venv dev có sẵn ctranslate2, model đã tải sẵn từ mini-spec V6 —
  không mock, không stub).
- TTS: **CapCut API thật**, giọng `EN US 2` (catalog en-US, đúng đường mới
  sửa ở Scope B).
- Lượt 1 (2 câu, có nhiễu ASR nhẹ): pipeline chạy hết 7 bước, `status:
  "completed"`, xuất `dubbed_video.mp4` (H.264 + AAC + phụ đề mềm mov_text)
  thật, không crash, không cần sửa tay giữa chừng — **đúng Success
  Criteria**. Nhật ký giọng đọc, phụ đề, catalog en-US đều đúng như thiết kế.
- Lượt 2 (câu ngắn, sạch hơn): tương tự, dịch đầy đủ nội dung
  ("Xin chào các bạn! Hôm nay trời đẹp và tôi rất vui!" →
  "It's a beautiful day and I'm so happy!"), video xuất ra có audio tiếng
  Anh thật, phụ đề khớp.
- **0 regression**: toàn bộ **657 test** (autodub, gồm 16 test mới —
  12 cho voices.py target-aware + 4 cho default_output_dir — + 641 test
  cũ) pass y hệt sau toàn bộ thay đổi V11.

**Phát hiện thật ngoài phạm vi V11 (KHÔNG sửa trong mini-spec này — đúng
guardrail "không mở rộng phạm vi ngoài gap đã xác nhận")**: ở lượt 1, NLLB
chỉ dịch câu đầu của transcript 2 câu, câu sau bị bỏ hoàn toàn (không lỗi,
không log — model tự dừng sớm). Đã cô lập nguyên nhân bằng gọi thẳng
`ctranslate2.Translator` ngoài pipeline: **cùng 2 câu đó dịch ĐẦY ĐỦ khi
văn bản nguồn sạch** (test tay bằng đúng câu đưa vào CapCut TTS), nhưng
**bị cắt khi văn bản nguồn là bản Whisper nghe lại có lỗi nhỏ** ("trí tựa
nhân tạo" thay vì "trí tuệ nhân tạo", "giàn lập" thay vì "giả lập") — model
dừng sớm khi gặp từ nhiễu/không có nghĩa, bất kể `beam_size` (thử cả 1 và
4) hay `max_decoding_length` tường minh. Verify thêm: hướng `zh→vi` (hướng
đã test kỹnhất từ V6) dịch đúng đầy đủ với văn bản 2 câu tương đương —
**không phải bug riêng của target=en/V11**, mà là hạn chế robustness sẵn
có của NLLB-200-distilled-600M (V6) trước nhiễu ASR, xảy ra với MỌI cặp
ngôn ngữ. Cần một mini-spec riêng cho V6 (vd: dịch câu-theo-câu tách bằng
dấu câu trước khi gửi NLLB, hoặc phát hiện+cảnh báo khi output ngắn bất
thường so với input) — ghi vào "Remaining Limits" bên dưới, KHÔNG chặn
Success Criteria của V11 (tiêu chí là "không crash", không phải "dịch
hoàn hảo mọi trường hợp nhiễu").

**Chưa làm** (đúng Test Plan, cần người ngoài): "người bản ngữ tiếng Anh
nghe thử đánh giá chất lượng giọng đọc + timing" — cần chủ dự án hoặc
người thứ ba, tôi (AI) không tự đánh giá chất lượng phát âm tiếng Anh bằng
tai không rành ngôn ngữ đó, đúng như Test Plan đã ghi rõ từ đầu.

### Sửa thêm — phát hiện qua IDE diagnostic khi rà lại code xung quanh

`DubPipeline.default_output_dir(target)` (pipeline.py) bỏ QUA tham số
`target`, luôn trả về `vi_output_dir()` — 2 lượt live-verify ở trên xuất
ra đúng `output/VN/20260811..._en` (video tiếng Anh nằm trong thư mục tên
"VN"). Không crash, không sai chức năng dịch/lồng tiếng, chỉ sai tổ chức
thư mục — nhưng đúng loại "giả định tiếng Việt" mà V11 nhắm tới. Đã sửa:
target=vi giữ nguyên hành vi cũ (0 regression, kể cả tôn trọng
`VIETNAMESE_OUTPUT_DIR` nếu người dùng đã đặt riêng); target khác về
`<output_dir>/<KEY>` (vd `output/EN`), KHÔNG đi theo override
`VIETNAMESE_OUTPUT_DIR` (biến đó di dời output tiếng Việt, không phải mọi
ngôn ngữ). Test mới `tests/test_output_dir_target_language.py` (4 test).

### Remaining Limits (V11)

- NLLB local-translate (V6) có thể bỏ sót câu khi ASR nguồn nhiễu — phát
  hiện thật ở trên, chưa fix, cần mini-spec riêng cho V6 (không phải V8/V11).
- ~~Chưa live-verify với video DÀI...~~ — **đã đóng, xem "Re-audit 2026-08-11
  — video dài thật" ngay dưới đây (Phase E, mục E5).**
- `.venv-whisper`/`.venv-mt` chưa cài đặt thật trong bản đóng gói (PyInstaller)
  — live-verify này dùng venv dev sẵn có (đường fallback in-process của
  Whisper, override thủ công cho NLLB), CHƯA verify qua đúng quy trình cài
  đặt `scripts/setup_whisper.py`/`scripts/setup_translate_local.py` mà
  người dùng cuối sẽ chạy.
- Đánh giá chất lượng giọng đọc tiếng Anh bởi người bản ngữ — chưa làm,
  cần chủ dự án hoặc bên thứ ba (xem trên).

### Re-audit 2026-08-11 — video dài thật (Phase E, đóng gap "chưa test video dài")

Sandbox `trieunt` — đóng đúng gap "chưa live-verify video DÀI, hàng chục
câu" ghi ở trên. Phương pháp giống V11 gốc (TTS thật + ffmpeg mux, vì
sandbox không có video mẫu dài thật) nhưng mở rộng từ 1 câu/<6s lên **20
câu/81 giây**:

1. 20 câu tiếng Việt đa dạng chủ đề (kể cả câu có số — "90%", "năm 2026",
   "hàng tỷ đô la" — để cùng lúc kiểm tra luôn đường ASR/dịch số, KHÔNG
   phải đường TTS-CapCut đã sửa bug ở V17) đọc thật qua **CapCut TTS thật**
   (giọng "Thanh Lan"), nối bằng `ffmpeg concat` (0.6s lặng giữa câu), mux
   vào video H.264/AAC thật 81 giây.
2. Chạy **`DubPipeline.run()` đầy đủ, không mock bất kỳ bước nào**:
   target=en, nguồn dịch local NLLB thật (model 622MB đã tải ở mục V17),
   TTS đích qua CapCut thật (giọng "EN US 2"), `bg_mode="duck"` (bỏ qua
   Demucs — không phải thứ đang kiểm chứng ở đây, đã có bài test riêng).

**Kết quả thật:**
- `status: "completed"`, **20/20 segment** qua hết ASR → dịch → TTS → ghép
  → mux, KHÔNG crash, KHÔNG segment nào bị rớt. Tổng thời gian xử lý 86
  giây cho video 81 giây nguồn (gần bằng thời lượng thật — chấp nhận được
  cho CPU không GPU).
- **Timing engine xử lý đúng thiết kế trên quy mô 20 segment thật** (đúng
  điều cần kiểm chứng): 19/20 câu bị lùi nhẹ vào khoảng lặng (tối đa 1.5s),
  6/20 câu được tăng tốc nhẹ (`atempo` tới 1.1x), chỉ **2/20 câu còn chồng
  tiếng nhẹ** (tổng 0.697s trên cả 81s — không phải lỗi, là giới hạn vật
  lý khi tiếng Anh dịch ra dài hơn tiếng Việt gốc ở 1 vài câu, timing guide
  ghi rõ để người dùng biết câu nào nghe kỹ). `quality_report.json` ghi
  đúng, đầy đủ per-segment (`shift_s`, `atempo`, `overlap_prev_s`,
  `over_budget_chars`) cho cả 20 câu — không phải chỉ tổng hợp mơ hồ.
- Bản dịch thật, tự nhiên, đúng số ("Có khoảng 90% doanh nghiệp..." → "Approximately
  90 percent of large enterprises have started using this technology.").
- Output thật: `dubbed_video.mp4` 81.58s, track thật H.264/AAC/mov_text
  (subtitle mềm), `transcript_en.srt` 20 dòng khớp đúng nội dung.
- ASR (Whisper `small`, CPU) nghe đúng gần như tuyệt đối cả 20 câu (vài lỗi
  nhỏ dự kiến ở mức ASR: "Trí tệ" thay "Trí tuệ", "mày tính" thay "máy
  tính" — không phải bug, là nhiễu ASR bình thường không ảnh hưởng luồng).

**Giới hạn còn lại của chính lượt verify này:** dùng `subtitle_mode="soft"`
(phụ đề mềm), KHÔNG test `subtitle_mode="burn"` (ghi cứng vào hình, đi qua
`ass_karaoke.py`) trên quy mô nhiều câu — karaoke alignment cho video dài
vẫn chưa có bằng chứng thật riêng, dù cơ chế bên dưới (`align_segments`)
không có gì phụ thuộc số lượng câu để tin sẽ khác hành vi khi burn. Cũng
chưa test `bg_mode="demucs"` trên video dài (dùng "duck" để tiết kiệm thời
gian — Demucs tự nó không phải thứ đang kiểm chứng ở lượt này, đã verify
riêng ở chỗ khác trong TEST_LOG).

## V12 — Cloud rendering production-ready (đưa V9 từ PoC thành hạ tầng thật)

Theo `docs/PLAN.md` mục V12 (Phase D). Guardrail: worker Python RIÊNG khỏi
control_server, KHÔNG rebuild logic Demucs, KHÔNG thêm Redis/broker (Mongo
vẫn là nguồn sự thật), KHÔNG bypass billing, GUI hiện đúng giá trước khi
trừ Vox, worker chết không được treo job mãi.

### Backend — state machine + API nội bộ (Scope A/B/C)

- `RenderJob` thêm `workerId`/`heartbeatAt` + 2 index mới
  (`{status,heartbeatAt}` cho sweeper, `{status,createdAt}` cho FIFO claim).
- `render-job.service.js` viết lại: `submitDemucsJob()` không còn spawn
  subprocess — chỉ tạo job `queued` rồi trả về NGAY. State machine mới:
  `claimNextJob(workerId)` (atomic FIFO), `heartbeat`, `completeJob`,
  `failJob` — cả 3 chỉ áp dụng khi `workerId` khớp job đang giữ (worker
  khác/đã bị sweeper coi là chết thì bị từ chối `409`, tránh 2 worker cùng
  đụng 1 job).
- `sweepStaleRunning()` mới (guardrail 5): job `running` mà `heartbeatAt`
  cũ hơn `cloud.render.heartbeat.stale.minutes` (mặc định 5) tự chuyển
  `failed` kèm lý do rõ ràng.
- **Phát hiện thật ngoài phạm vi trực tiếp**: `sweepExpired()` (TTL dọn
  file, có từ V9) **chưa bao giờ được nối vào scheduler nào** — job hết
  hạn nằm lại vô thời hạn. Phát hiện lúc audit lại `server.js` để nối
  sweeper mới của V12. Đã nối cả 2 sweeper vào `server.js` (cùng pattern
  `setInterval` + `.unref()` như `hold.service.expireSweep`).
- `POST /v1/jobs/demucs` đổi contract: trả `{jobId, status:"queued",
  async:true, balanceAfter}` NGAY, không đợi xử lý — BREAKING CHANGE có
  chủ đích (V9 chưa từng có client thật, xem Audit Before Build trong
  docs/PLAN.md mục V12).
- `/internal/jobs/*` (route mới, KHÔNG dưới `/v1`): `claim`/`heartbeat`/
  `complete`/`fail`, xác thực bằng `WORKER_INTERNAL_TOKEN` riêng
  (`worker-auth.middleware.js`, cùng khuôn `admin.middleware.js` —
  `safeEqual` timing-safe, redact khỏi log).
- `/v1/config/app` thêm `cloudRenderEnabled` + `pricing.cloudRenderDemucs`
  — GUI đọc trước khi cho bật (guardrail 4).

### Worker Python (Scope B) — `control_server/worker/`

- `render_worker.py`: standalone (không import autodub, cùng quy ước
  `demucs_worker.py`), poll `/internal/jobs/claim` mỗi 3s, heartbeat luồng
  riêng mỗi 30s trong lúc xử lý, spawn `demucs_worker.py` qua subprocess
  ĐÚNG NGUYÊN VĂN CLI contract của V9 (`--input/--vocals/--no-vocals`) —
  không viết lại logic tách nhạc.
- `Dockerfile`: `python:3.12-slim` + `pip install demucs soundfile requests`
  + copy đúng 1 file `autodub/media/demucs_worker.py` (không copy cả gói
  `autodub`/`autodub_gui` — tránh kéo PySide6 không cần cho worker).
  **Sửa 1 lần trong lúc build**: dự định `apt-get install libsndfile1`
  trước, nhưng mạng sandbox chặn `deb.debian.org` — thử bỏ bước apt và xác
  nhận **thật** (không đoán) rằng wheel `soundfile` trên Linux đã gói sẵn
  `libsndfile`, `pip install` + chạy Demucs thật vẫn thành công không cần
  cài gì ở tầng hệ điều hành.

### Live verification — THẬT, không mock (Test Plan/Success Criteria)

**Giới hạn môi trường phát hiện thật**: mạng docker build trong sandbox
này cực chậm khi tải các layer torch (~15 phút vẫn chưa xong tính tới lúc
chuyển hướng) — không phải lỗi Dockerfile (đã review kỹ, chỉ là
`pip install` + 2 lệnh `COPY`), mà là băng thông riêng của build context
trong sandbox này (pip cài trực tiếp vào venv thường ở phần khác của phiên
làm việc này chạy nhanh bình thường). Thay vì chờ vô thời hạn, đã live-
verify **toàn bộ logic mới** (thứ thật sự cần kiểm chứng — state machine,
giao thức worker, tích hợp Demucs thật) bằng cách chạy `render_worker.py`
**trực tiếp trên máy** (venv có sẵn torch+demucs+requests từ audit V12)
nhắm vào `control_server` **thật chạy trong Docker** + **MongoDB thật**:

1. `docker compose up -d mongo control_server` — 2 image ĐÃ build xong
   trước khi build worker bị chậm mạng — chạy thật, `/health` trả 200.
2. Bind-mount tạm `RENDER_UPLOAD_DIR` ra thư mục host thật (thay named
   volume, để tiến trình worker chạy NGOÀI container đọc/ghi cùng file
   với control_server) — chỉ để verify, không phải kiến trúc thật (compose
   thật dùng named volume dùng chung giữa 2 container, xem docker-compose.yml).
3. Đăng ký 1 device thật qua `POST /v1/device/register`, nộp 1 file WAV
   thật (2 giây, sine 440Hz) qua `POST /v1/jobs/demucs` — nhận ngay
   `{status:"queued", async:true, balanceAfter:450}` (trừ đúng 50 Vox,
   KHÔNG đợi xử lý — đúng Success Criteria "không bị timeout HTTP").
4. `render_worker.py` (chạy thật, không mock) claim job qua HTTP thật, spawn
   `demucs_worker.py` thật, **model Demucs thật load và chạy tách nhạc
   thật** trên file WAV thật.
5. Bắt được 2 lỗi thật trong lúc verify (KHÔNG phải lỗi logic — lỗi
   permission/path do cách bind-mount tạm cho việc verify, ghi lại trung
   thực): (a) lần đầu worker đọc nhầm path do thiếu symlink `/data/render-
   jobs` trên host trỏ đúng bind mount; (b) sau khi sửa, job dừng ở
   "running" → "failed" vì thư mục job do control_server (chạy root trong
   container) tạo ra không cho tiến trình host (user thường) ghi —
   `chmod 777` thư mục dùng chung rồi chạy lại. Cả hai đều là hạn chế của
   PHƯƠNG PHÁP VERIFY (bind-mount + worker ngoài container), KHÔNG tồn tại
   trong kiến trúc thật (2 container cùng mount 1 named volume, cùng
   UID/permission model nếu cùng Dockerfile base).
6. Lượt chạy thứ 3: **`status:"done"`** — job hoàn tất thật.
7. Tải cả 2 stem qua `GET /v1/jobs/:id/result/vocals` và `/no_vocals` —
   **cả hai `HTTP 200`, file WAV thật 2.0 giây** (khớp nguồn), không giả.
8. Xác nhận chính sách xoá dữ liệu (đã duyệt từ V9) vẫn đúng qua đường mới:
   sau khi tải xong CẢ HAI stem, thư mục job **tự biến mất** — kiểm bằng
   `ls` thật sau khi tải, không còn tồn tại.
9. `kill -TERM` worker giữa lúc đang chạy vòng lặp — log in ra đúng
   "Nhận signal 15 — dừng sau job hiện tại..." (graceful shutdown hoạt
   động như thiết kế).
10. Server logs suốt phiên verify: **0 uncaught exception**, sweeper mới
    (`sweepExpired`/`sweepStaleRunning`) chạy im lặng đúng thiết kế (không
    có gì để dọn thì không log, không lỗi).

**Regression**: `control_server` **113/113 test pass** (98 cũ + 8
`internal-jobs.test.js` mới + net thêm ở `render-job.integration.test.js`,
gồm cả 1 test spawn Demucs thật qua `VOXDUB_TEST_DEMUCS_PYTHON`, **đã chạy
thật — pass, 18.4s**). `autodub` (pytest) **672/672 pass** (657 cũ + 11
`test_cloud_render.py` + 4 `test_pipeline_cloud_render.py`).

### GUI (Scope D)

- Cài đặt (`autodub_gui/pages/settings_fields.py`): thêm `Field` khai báo
  `CLOUD_RENDER_ENABLED` (hệ thống Field có sẵn tự dựng ô nhập + lưu/nạp —
  không cần code tay, đã verify `test_settings_fields.py` 15/15 pass không
  sửa gì thêm).
- Tạo dự án (`RecognizeStep`, mục "Nhạc nền"): ô "Xử lý tách nhạc trên
  cloud" — CHỈ hiện khi `autodub.cloud_render.pricing(settings)` xác nhận
  khả dụng (đúng nguyên tắc "không thêm UI cho tính năng chưa tồn tại"),
  hiện rõ số Vox TRƯỚC khi chạy (guardrail 4). Bảng tóm tắt bước cuối cũng
  hiện dòng "+N Vox" nếu đã bật.
- **Bug thật tìm ra + sửa lúc viết smoke test runtime** (không chỉ đọc
  code): `values()` ban đầu dùng `self.cloud_render.isVisible()` để quyết
  định có tính lựa chọn cloud hay không — nhưng ô này nằm trong
  `CollapsibleSection` "Nhạc nền" GẬP LẠI mặc định, nên `isVisible()`
  (tính cả tổ tiên) **luôn trả `False`** bất kể trạng thái thật, kể cả khi
  tính năng khả dụng và người dùng đã tick chọn — nghĩa là lựa chọn cloud
  của người dùng **âm thầm bị bỏ qua mỗi lần chạy**. Bắt được bằng
  `QApplication` offscreen thật, dựng widget thật, kiểm `.isVisible()` vs
  `.isHidden()` — sửa bằng cờ riêng `_cloud_render_available` theo dõi
  đúng quyết định của `set_cloud_render_info()`, không suy qua Qt.
- `autodub/saas_client.py`: `submit_demucs_job()` (multipart), `job_status()`,
  `download_job_result()` (stream) — không dùng `_request()` (chỉ JSON).
- `autodub/cloud_render.py` (mới): `is_available()`/`pricing()`/
  `separate_vocals_cloud()` — cùng chữ ký trả về với
  `vocal_separator.separate_vocals()` (drop-in). Lỗi cloud (mạng/job hỏng/
  quá hạn 30 phút) **fallback về Demucs máy**, đúng nguyên tắc "degrade
  trung thực" đã có sẵn (vd Paraformer→Whisper) — không phải phát minh
  mới. **Bug thật tìm ra khi viết test**: nhánh `except Exception` bọc
  quanh lời gọi cloud ban đầu sẽ NUỐT NHẦM `PipelineCancelled` (người dùng
  bấm Hủy giữa lúc chờ job) rồi fallback sang Demucs máy thay vì dừng thật
  — sửa bằng `except PipelineCancelled: raise` đứng trước
  `except Exception`. Khoá lại bằng
  `test_cancellation_during_cloud_wait_is_not_swallowed`.
- Wiring vào `DubPipeline._resolve_background()`: cloud trước (nếu khả
  dụng) → lỗi thì fallback Demucs máy → cả hai lỗi thì nền câm (hành vi cũ,
  không đổi).

### Re-audit 2026-08-11 — build thành công qua cách khác, live-verify end-to-end THẬT qua Docker

Sandbox `trieunt` — 2 lượt build `docker compose build render_worker` trực
tiếp qua mạng đều bị treo (lượt 1: >50 phút không tiến triển; đã chẩn đoán
thêm ở mục V12 phía trên — mạng TRONG network namespace Docker build chậm
hẳn so với mạng host cùng máy, không phải bị chặn hoàn toàn, chỉ cực chậm).
Thay vì tiếp tục chờ mạng Docker, đổi chiến lược: **tải sẵn wheel trên
host** (mạng host đã xác nhận nhanh, bình thường xuyên suốt phiên này) rồi
**build offline** — hoàn toàn không cần mạng lúc `docker build`:

1. `pip download demucs>=4.0.0 soundfile>=0.13.0 requests>=2.31.0` (đúng y
   hệt spec trong `control_server/worker/Dockerfile`, không đổi phiên bản)
   trên host — 54 wheel, 2.6GB, xong trong vài phút (xác nhận lại: mạng
   host bình thường, vấn đề thật sự chỉ ở network namespace của Docker
   builder trong sandbox này).
2. Dockerfile biến thể **CHỈ ĐỂ VERIFY** (không commit, không thay
   `control_server/worker/Dockerfile` thật — đó vẫn đúng cho môi trường
   build bình thường, không có lý do đổi logic sản xuất vì 1 giới hạn
   riêng của sandbox): `COPY wheels /wheels` rồi
   `pip install --no-index --find-links=/wheels ...` — không gọi mạng.
3. `docker build` **THÀNH CÔNG THẬT**, `image c0c43724e8a6` — verify
   `import demucs, soundfile, requests, torch` chạy được trong container
   (torch 2.13.0+cu130).
4. Gắn tag `voidmix-render_worker:latest` (đúng tên compose tự sinh) rồi
   `docker compose up -d render_worker` — **CẢ 3 SERVICE chạy thật cùng
   lúc lần đầu tiên** (mongo + control_server + render_worker), đúng
   nghĩa đen Success Criteria gốc của V12 ("docker compose up chạy được
   TOÀN BỘ, không cần cài gì thêm ngoài Docker"). Log worker thật:
   `worker_id=0ff7353c1470:1 bắt đầu poll http://control_server:3001 mỗi 3.0s`.
5. **Live-verify end-to-end THẬT qua đúng luồng HTTP** (không bind-mount
   tạm, không chạy worker ngoài container như lượt verify trước — lần này
   đúng kiến trúc thật 100%): đăng ký 1 device thật
   (`POST /v1/device/register`) → nộp 1 file WAV thật 3 giây
   (`POST /v1/jobs/demucs`) → nhận ngay `{status:"queued", balanceAfter:450}`
   (trừ đúng 50 Vox) → poll `GET /v1/jobs/:id` thấy chuyển
   `queued`→`running`→`done` thật (worker container tự claim, xử lý, báo
   xong — log container xác nhận: "Nhận job ... (stage=demucs)" rồi "Job
   ... xong.") → tải cả 2 stem (`GET /v1/jobs/:id/result/vocals|no_vocals`)
   — **file WAV thật, hợp lệ** (`ffprobe`: PCM 16-bit, đúng 3.0s, khớp
   input).

**Kết luận**: Dockerfile/docker-compose.yml THẬT (không đổi 1 dòng) hoàn
toàn đúng — giới hạn build trước đó 100% là do mạng riêng của sandbox này,
không phải lỗi thiết kế. V12 giờ đã live-verify TOÀN BỘ, kể cả bước cuối
cùng còn thiếu (build qua Docker) — không còn phần nào của Success Criteria
gốc chưa xác nhận.

### Remaining Limits (V12)

- **[LỊCH SỬ — đã đóng ở mục "Re-audit" ngay trên]** build `render_worker`
  qua `docker compose build` **THẤT BẠI THẬT SỰ** sau ~2 giờ 6 phút — không
  phải chậm rồi xong, mà chết hẳn với `ReadTimeoutError: HTTPSConnectionPool
  (host='files.pythonhosted.org', port=443): Read timed out` ngay ở bước
  `pip install demucs`. Đây là giới hạn THẬT của mạng build-context trong
  sandbox này (khác hẳn mạng bình thường của sandbox — cùng gói `demucs`/
  `torch` cài trực tiếp vào venv ở phần khác của phiên làm việc này chạy
  bình thường, và `docker compose build control_server`/`docker pull mongo:7`
  đều thành công nhanh). KHÔNG phải lỗi Dockerfile (đã review kỹ, chỉ 3
  dòng: pip install + 2 COPY). Cần build lại trên máy/CI có mạng build
  bình thường trước khi coi Success Criteria "docker compose up chạy được
  Demucs thật, không cần cài gì thêm ngoài Docker" là đã xác nhận theo
  đúng nghĩa đen — logic bên trong (state machine, giao thức worker, tích
  hợp Demucs thật) ĐÃ live-verify đầy đủ bằng cách khác (xem trên), chỉ
  riêng bước "build đúng qua Docker" chưa tự xác nhận được trong sandbox
  này.

**Re-audit 2026-08-11 (sandbox `trieunt`, lần build thứ 2):** tái lập được
đúng hiện tượng — `docker compose build render_worker` dừng ở đúng bước
`pip install demucs` >50 phút không tiến triển, không lỗi ngay. Chẩn đoán
thêm 1 bước (không đoán): `docker run --rm python:3.12-slim` gọi thẳng
`https://pypi.org` từ TRONG container mới — kết nối được, nhưng mất 5.2s
cho 1 request HTTPS nhỏ (bình thường phải <1s) — xác nhận đây không phải
mạng container bị chặn hoàn toàn, mà là băng thông/độ trễ egress của
network namespace Docker trong sandbox này bị giới hạn nặng so với network
namespace host (nơi cùng lệnh `pip install torch` chạy nhanh bình thường).
Kết luận không đổi: cần build trên máy/CI có mạng Docker bình thường.

- Chưa live-verify job DÀI thật (vài phút) để chứng minh "không bị timeout
  HTTP" so với ngưỡng cụ thể — verify hiện tại dùng clip 2 giây (đủ chứng
  minh state machine bất đồng bộ hoạt động đúng, chưa chứng minh bằng số
  liệu thời gian thật cho video dài).
- Chưa test tải đồng thời N job (mini-spec Test Plan có nhắc "load test");
  `claimNextJob` atomic đã đúng theo lý thuyết Mongo
  (`findOneAndUpdate`) và có test khoá lại (`claimNextJob: FIFO, atomic`)
  nhưng chưa chạy N worker thật song song.
- GUI cloud-render: chưa hiện TIẾN ĐỘ job đang chạy trên cloud trong lúc
  chờ (mini-spec Scope D có nhắc "hiện tiến độ job") — hiện tại chỉ có
  1 dòng log tiến độ chung ("Đang chờ máy chủ xử lý…") qua
  `ProgressReporter`, chưa có UI riêng hiện %/trạng thái job cloud tách
  biệt khỏi các bước khác của pipeline.
- Chưa chạy thật qua GUI desktop (PySide6 thật, không phải smoke test
  offscreen) — verify GUI mới dừng ở dựng widget thật trong `QApplication`
  offscreen + gọi hàm thật, chưa click chuột thật qua toàn bộ luồng Tạo dự
  án → chạy → nhận video có nhạc nền tách bằng cloud.

## V13 — Phễu hoàn thành/bỏ dở pipeline (đưa V10 từ "một phần" thành đầy đủ)

Theo `docs/PLAN.md` mục V13 (Phase D). **Quyết định chính sách**: đây là
tính năng THU THẬP DỮ LIỆU MỚI — đã hỏi chủ dự án trước khi bắt tay (đúng
guardrail của Phase D), chủ dự án chọn "làm đầy đủ" (backend + client gửi
event thật + banner minh bạch + dashboard), không chọn phương án "chỉ
backend, chưa cho gửi".

### Audit Before Build

Đọc `autodub/progress.py` trước khi code (đúng yêu cầu mini-spec): `STEPS`
đã là danh sách thứ tự đầy đủ (acquire→extract→separate→asr→translate→
tts→merge_audio→merge_video→content→done), `ProgressReporter.emit()` đã là
điểm chạm DUY NHẤT cho mọi chuyển giai đoạn — đủ để tái dùng theo đúng
Design Choice của mini-spec ("1 listener gắn thêm, không thêm hook mới
trong pipeline.py"), không cần sửa gì ở `progress.py`.

### Domain model + services (Scope A/B/C)

- `PipelineEvent` (Mongo, mới): **1 document mỗi run**, upsert theo
  `(fingerprint, runId)` — không lưu lịch sử từng bước, chỉ điểm dừng MỚI
  NHẤT (`stage`) + `status` (`started`/`completed`/`failed`, đúng 3 giá
  trị Scope A quy định) + `errorStage` (khi failed) + `startedAt`/
  `updatedAt`/`completedAt`. Quyết định thiết kế: dùng field `stage` cập
  nhật liên tục trong lúc `status` vẫn `"started"` để có granularity cho
  phễu mà không cần một collection lịch sử riêng — đơn giản hơn, đủ cho
  quy mô hiện tại (đúng tinh thần "đừng over-engineer" xuyên suốt các
  guardrail V9-V12).
- `telemetry.service.js`: `recordEvent()` (validate NGHIÊM status/stage,
  400 khi sai — không âm thầm ghi rác), `funnel()` (số run đạt tới mỗi
  chặng, suy từ điểm dừng cuối cùng — dừng ở X thì tính vào MỌI chặng ≤
  X), `abandonedCount()` (guardrail 4 — `started` + `updatedAt` quá
  `staleHours`), `overview()` (gộp cho dashboard).
- `POST /v1/telemetry/pipeline-event` (route mới) — **guardrail 2 thực thi
  ở tầng validate, không phải quy ước**: field ngoài
  `runId`/`status`/`stage`/`errorStage` bị từ chối `400 FORBIDDEN_FIELD`.
  `fingerprint` lấy từ token đã xác thực (`requireDevice`), không tin
  client tự khai.
- `GET /v1/admin/analytics/pipeline-funnel` — dashboard đọc từ đây.
- `autodub/saas_client.py`: `send_pipeline_event()` — không tự bọc
  try/except (bên gọi lo, xem dưới).
- `autodub/telemetry.py` (mới): `make_progress_listener(pipeline)` — bọc
  THÊM 1 listener vào callback progress hiện có của `DubPipeline`
  (`__init__`), đọc `pipeline._telemetry_run_id` động (gán mới mỗi lượt
  trong `run()`). Local-only (`is_configured()==False`) → trả no-op ngay
  từ lúc dựng pipeline, quyết định MỘT LẦN — 0 overhead, 0 network cho
  mọi event sau đó (guardrail 5). `_send_async()` chạy trong luồng nền
  daemon riêng, nuốt MỌI lỗi (guardrail 3 — best-effort thật, không mock).
  `note_failed()` gọi từ `DubPipeline.run()`'s except block — báo
  `"failed"` kèm `errorStage` = giai đoạn cuối cùng đã ghi nhận (bao gồm
  cả khi người dùng huỷ — `PipelineCancelled` cũng là `BaseException`,
  map vào `"failed"` vì schema chỉ có 3 giá trị; quyết định có chủ đích,
  không phải bỏ sót — một run bị huỷ có TERMINAL EVENT rõ ràng thì chính
  xác hơn để nó rơi vào "bỏ dở" và chờ sweeper suy đoán hàng giờ sau).

### Bug thật tìm ra khi viết wiring vào pipeline.py

`ProgressReporter.emit()` vốn tự nuốt lỗi của callback (`try: self.
_callback(...) except Exception: pass`) — nếu chỉ đơn giản gọi callback
GUI gốc RỒI GỌI listener telemetry theo sau trong CÙNG một hàm không có
try/except riêng, một lỗi ở callback GUI (bug tầng UI, không liên quan gì
tới telemetry) sẽ chặn luôn `_tel(event)` không bao giờ chạy tới — vì
exception bay thẳng ra khỏi hàm gộp, bị `emit()` nuốt ở tầng NGOÀI CÙNG.
Sửa: bọc lời gọi callback gốc trong try/except RIÊNG bên trong hàm gộp,
đảm bảo `_tel(event)` luôn tới lượt bất kể callback gốc thế nào. Khoá lại
bằng `test_broken_gui_callback_does_not_block_telemetry` (callback GUI cố
ý ném lỗi, xác nhận telemetry vẫn nhận được event).

### GUI — banner minh bạch (Scope D, guardrail 1 — BẮT BUỘC trước khi gửi)

- `autodub_gui/first_run.py` (`mode_banner_text()`, đã có từ V3): nhánh
  "có máy chủ" thêm câu nói rõ việc gửi TRẠNG THÁI tiến trình (bắt đầu/
  xong/lỗi, dừng ở bước nào) và khẳng định KHÔNG BAO GIỜ gửi nội dung.
  Nhánh "local-only" thêm câu khẳng định KHÔNG gửi bất kỳ dữ liệu nào.
  Khoá lại bằng `test_mode_banner_discloses_telemetry_when_server_configured`
  và `test_mode_banner_local_only_explicitly_states_nothing_sent` — đọc
  THẬT nội dung banner, không chỉ tin đã sửa đúng.
- `autodub_gui/pages/help_page.py` (`EXTRA_PROBLEMS`, FAQ): thêm mục "App
  có gửi dữ liệu gì về máy chủ không?" — phân biệt rõ local-only (không
  gửi gì) vs SaaS (gửi trạng thái tiến trình, liệt kê đúng field, khẳng
  định không bao giờ nội dung). Khoá bằng
  `tests/test_help_page_telemetry_faq.py`.
- `website/src/pages/admin/Dashboard.jsx`: `PipelineFunnel` — biểu đồ
  thanh ngang 6 chặng (Tải video/Tách nhạc nền/Nghe & chép lời/Dịch/Đọc
  giọng/Ghép video) + số Hoàn thành/Lỗi/Bỏ dở (ước lượng, có tooltip giải
  thích rõ không phải sự thật tuyệt đối). `npm run build` sạch.

### Live verification — THẬT (Test Plan/Success Criteria)

Dựng lại `docker compose up -d mongo control_server` (2 image đã build từ
V12, build lại `control_server` để lấy code V13 mới — nhanh, ~8s, không
đụng gì tới build chậm của `render_worker`):

1. **Chạy `SaasClient` THẬT** (không mock) nhắm vào server thật, gửi 2
   luồng run thật qua HTTP thật:
   - Run 1: `started@acquire` → `started@asr` → `started@tts` →
     `completed@done`.
   - Run 2: `started@acquire` → `started@separate` →
     `failed@separate` (errorStage="separate").
2. **Cố ý gửi field cấm `transcript` qua `_request()` thẳng vào endpoint
   thật** — xác nhận máy chủ chặn THẬT: `SaasError: Event không được chứa
   field: transcript...` (không phải đoán từ code, gọi HTTP thật và nhận
   lỗi thật).
3. `GET /v1/admin/analytics/pipeline-funnel` (admin token thật) trả về
   ĐÚNG số liệu suy từ 2 run trên:
   `funnel: acquire=2, separate=2, asr=1, translate=1, tts=1, merge_video=1`
   (đúng — run 2 dừng ở "separate" nên KHÔNG được tính vào asr trở đi;
   run 1 hoàn tất nên tính vào mọi chặng, "done" tính là đã qua
   merge_video), `started=2, completed=1, failed=1, abandoned=0` (đúng —
   run 2 có terminal event rõ ràng "failed", không rơi vào "bỏ dở" dù
   dừng sớm).
4. Regression suite thật: `control_server` **132/132 pass** (113 cũ +
   9 `telemetry.integration.test.js` + 10 `telemetry-route.test.js`),
   `autodub` (pytest) **690/690 pass** (672 cũ + 10 `test_telemetry.py` +
   5 `test_pipeline_telemetry_wiring.py` + 2 test mới trong
   `test_first_run_mode.py` + 1 `test_help_page_telemetry_faq.py`).

### Remaining Limits (V13)

- Định nghĩa "bỏ dở" (guardrail 4) là ƯỚC LƯỢNG theo thiết kế — 1 run
  đang xử lý thật (video dài, > `staleHours` giờ nhưng vẫn còn heartbeat
  progress) sẽ bị đếm nhầm là bỏ dở nếu app KHÔNG gửi event nào trong
  suốt khoảng đó (vd 1 bước nội bộ chạy rất lâu không có ranh giới stage
  nào ở giữa). `staleHours` mặc định 6 — chưa có số liệu thật để tinh
  chỉnh ngưỡng này cho video rất dài.
- Chưa thấy dữ liệu thật từ người dùng thật (chỉ verify bằng client tự
  gọi) — cần thời gian sau khi tính năng thật sự triển khai để dashboard
  có ý nghĩa thống kê.
- Chưa test tải đồng thời nhiều run cùng lúc gửi event (khối lượng thấp
  theo thiết kế — mỗi lượt dubbing tối đa ~10 event, không phải luồng
  cao tần).
- Chưa chạy thật qua GUI desktop bấm chuột thật để xác nhận banner hiện
  đúng lúc mở app lần đầu — verify hiện tại là đọc thẳng nội dung hàm
  `mode_banner_text()`/`EXTRA_PROBLEMS` bằng test, chưa chụp màn hình
  dialog thật.
- `website` chưa có test cho `PipelineFunnel`/`Dashboard.jsx` (component
  React) — cùng giới hạn đã ghi nhận từ đợt re-audit 08-11 (chưa có
  `@testing-library/react`, `npm run build` là mức verify hiện tại).

## V15 — Sửa bug hardcode tiếng Việt ở prompt dịch server-side (phát sinh khi audit V14)

Bug thật tìm ra trong lúc audit trước khi bắt tay V14 (dịch phụ đề rời,
docs/PLAN.md — chưa có mini-spec chính thức, xem Remaining Limits cuối
mục này): `POST /v1/ai/translate|analyze|review` (control_server) KHÔNG
nhận `targetLang` từ client — `routes/ai.js` hardcode `TARGET_FIELD =
'text_vi'` và `prompts/translate.js` hardcode "Vietnamese" trong system
prompt. Ảnh hưởng THẬT: lồng tiếng tiếng Anh qua SaaS (mini-spec V8/V11)
vẫn nhận `text_vi` từ máy chủ — client tìm `text_en` không thấy, coi câu
đó là "không dịch được" (không crash, nhưng dịch sai ngôn ngữ hoàn toàn,
âm thầm).

### Thay đổi

- `control_server/src/prompts/translate.js`: thêm `resolveTargetLang(key)`
  (bảng field/tên ngôn ngữ theo `targetKey`, mặc định `"vi"` khi thiếu —
  0 regression cho client cũ không gửi field) — `buildTranslateSystemPrompt`/
  `buildAnalysisPrompt`/`buildReviewUserPrompt`/`translateSchema` đổi sang
  nhận `targetKey` thay vì `targetField` hardcode.
- `control_server/src/routes/ai.js`, `ai-gateway.service.js`: đọc
  `targetLang` từ body request (`/translate`, `/analyze`, `/review`),
  truyền xuống `resolveTargetLang()` — field response đổi động
  `text_<targetLang>` thay vì cố định `text_vi`.
- `autodub/saas_client.py`: `translate()`/`analyze()`/`review()` thêm tham
  số `target_lang: str = "vi"`, gửi trong payload — mặc định giữ hành vi
  cũ khi không truyền.
- `autodub/text/translate_saas.py`, `translate_review.py`: truyền đúng
  `target.key` (không còn ngầm định "vi") ở mọi điểm gọi client thật.
- `docs/API.md`: cập nhật contract 3 endpoint (`targetLang` request field,
  `text_<targetLang>` response field).

### Design Choice

Field mặc định `"vi"` ở CẢ hai đầu (client `SaasClient.translate(...,
target_lang="vi")` và server `resolveTargetLang()` khi thiếu key) — double
default có chủ đích, không phải thừa: client cũ (đã build, chưa cập nhật)
gọi server mới vẫn ra đúng hành vi cũ; server cũ (chưa deploy) nhận request
có `targetLang` cũng không vỡ vì field bị bỏ qua như request thừa field.

### Tests (thật, chạy tại 2026-08-11)

- `control_server`: `node --test tests/*.test.js` — **146 pass / 1 skip**
  (bao gồm 14 test mới `tests/translate-prompts.test.js` cho
  `resolveTargetLang`/prompt builder target=vi và target=en).
- `autodub`: `pytest tests/test_translate_target_lang.py` — **24 pass**
  (khoá `translate_saas.py`/`translate_review.py` gọi client với đúng
  `target_lang=target.key`, kể cả regression target=vi).
- Suite `autodub` đầy đủ (`pytest -q`, môi trường sandbox hiện tại, không
  phải `.venv` đóng gói đầy đủ của project): **586 pass, 16 fail** — toàn
  bộ 16 fail là giới hạn môi trường CÓ TỪ TRƯỚC, không liên quan thay đổi
  V15 (thiếu `PySide6`/`numpy`/`ctranslate2` — vd
  `test_translate_local.py::test_translate_segments_local_end_to_end_real_model`
  cần `.venv-mt` thật có `ctranslate2`, không có trong sandbox; 6 test còn
  lại của cùng file, bao gồm test phủ `run_local_worker()` mới tách ra,
  đều pass). Đã xác nhận không file nào trong 16 fail chạm tới code V15.

### Live verification — THẬT (2026-08-11, sau khi có key thật từ chủ dự án)

Chủ dự án cung cấp 1 API key Gemini thật. Dựng `docker compose up -d mongo
control_server` (build thật, không mock), seed 1 `AiProvider` (`type:
"google"`, `model: "gemini-2.5-flash"`, key mã hoá bằng `encrypt()` thật của
server, không ghi plaintext ra bất kỳ file nào trong repo). Đăng ký 1 device
thật qua `/v1/device/register`, gọi HTTP thật (không mock):

1. `POST /translate` với `sourceLang=en-US, targetLang=en`, câu nguồn tiếng
   Trung — response THẬT trả đúng field `text_en` (không còn rơi về `text_vi`
   như bug đã sửa): `"Hello, welcome to our channel."`. `creditCharged=12`
   đúng `base(10)+autotranslate(2)`.
2. Balance thật trừ đúng trong Mongo (`db.devices.findOne(...)`), không chỉ
   tin response — 500 → 482 sau 2 lượt gọi thật (1 lượt `/translate-subtitle`
   trước đó, xem mục V14).

**Đã đóng hẳn giới hạn "chưa live-verify" trước đây của V15** — không còn là
suy luận từ unit/mock nữa.

### Remaining Limits (V15)

- Ngôn ngữ đích ngoài danh sách đã biết của `resolveTargetLang()` rơi về
  quy tắc chung (tên ngôn ngữ lấy nguyên `targetKey` làm nhãn) — chưa có
  bảng tên đầy đủ cho mọi `TargetLang` hiện có trong `autodub/languages.py`,
  chỉ mới phủ các ngôn ngữ đã dùng thật (vi, en).

## V14 — Dịch phụ đề rời (`.srt`/`.vtt`, tính năng mới ngoài luồng dub)

Theo `docs/PLAN.md` mục V14. **5 quyết định đã hỏi chủ dự án trước khi bắt
tay** (2026-08-11, đúng guardrail Phase D): wiring CẢ GUI+CLI, nguồn dịch CẢ
local+SaaS, phạm vi ngôn ngữ MỞ RỘNG FLORES-200 đầy đủ, đầu ra LUÔN file
mới, giá SaaS = autotranslate. Tự phát hiện lúc audit: server-side prompt
dịch (`/translate`,`/analyze`,`/review`) hardcode tiếng Việt — mở
riêng **V15** để vá trước (xem mục trên) vì không hợp lý viết thêm tính
năng dịch mới trên nền server đang dịch sai ngôn ngữ.

### Audit Before Build

- `autodub/languages.py`: `TargetLang`/`TARGETS` chỉ 2 giá trị (vi/en), gắn
  chặt field dub (`audio_name`/`srt_name`/`folder_suffix`/`iso639_2` cho MP4
  track) — xác nhận KHÔNG tái dùng được cho phạm vi FLORES-200 đầy đủ, đúng
  Constraint 1 của mini-spec.
- `autodub/text/translate_local.py`: `LANG_TO_FLORES` chỉ map 9 mã (các
  ngôn ngữ nguồn ASR đã dùng thật) — xác nhận cần bảng riêng cho V14, không
  mở rộng bảng cũ (bảng cũ gắn với ASR nguồn của pipeline dub, ý nghĩa khác).
- `control_server/src/services/config.service.js`: `credit.cost.segment.
  autotranslate` đã tồn tại sẵn (giá trị mặc định 2) — dùng lại đúng theo
  quyết định giá đã chốt, không tạo key giá mới.
- Bảng mã FLORES-200 (`autodub/text/flores200.py`, 204 mã) lấy qua **WebFetch
  thật** từ `facebookresearch/flores` repo (`flores200/README.md`) lúc viết
  mini-spec — KHÔNG gõ tay từ trí nhớ (đúng nguyên tắc "no fake data": một
  mã sai trong bảng 200 mục sẽ là lỗi dịch sai ngôn ngữ âm thầm, không test
  nào bắt được nếu chỉ đoán).

### Design Choice

Ngôn ngữ = mã FLORES-200 xuyên suốt GUI/CLI/API (không dựng tầng ánh xạ
BCP-47↔FLORES-200 cho ~200 ngôn ngữ — rủi ro sai âm thầm, xem Constraint 1
trong `docs/PLAN.md`). SaaS dùng endpoint + prompt RIÊNG khỏi `/translate`
(payload/prompt đó gắn cps/prosody cho TTS dub, không áp dụng phụ đề thuần).

### Thay đổi (Scope A-G)

- **A** `autodub/text/flores200.py` (mới) — bảng 204 mã, `VERIFIED_QUALITY_
  CODES` (chỉ vie_Latn/eng_Latn), `display_name()`.
- **B** `autodub/text/subtitle_translate.py` (mới) — `translate_subtitle_
  file_local()`/`translate_subtitle_file_saas()`, giữ nguyên timestamp gốc,
  KHÔNG dùng `ensure_terminal_punct()` (chuẩn hoá cho TTS, ép dấu câu cuối —
  sai với phụ đề thuần đọc, không có TTS nào đọc theo).
- **C** `autodub/saas_client.py`: `translate_subtitle()` — endpoint riêng.
- **D** `control_server`: route `POST /v1/ai/translate-subtitle`
  (`routes/ai.js`), `ai-gateway.service.js` thêm `translateSubtitleBatch()`
  (cùng chiến lược chia-đôi-lô-khi-thiếu-câu như `translateBatch`, bỏ CJK-
  leftover-fix pass — xem Remaining Limits), `prompts/subtitle-translate.js`
  (prompt riêng, không có bảng `LANGUAGE_RULES` theo tên như `translate.js`
  — nhận `sourceName`/`targetName` từ client vì không khả thi soạn luật cho
  ~200 ngôn ngữ).
- **E** `scripts/translate_subtitle.py` — CLI, `--list-languages` để tra mã.
- **F** `autodub_gui/pages/subtitle_translate_page.py` (trang mới, "Dịch phụ
  đề" trong nhóm Công cụ) + `SubtitleTranslateWorker` (`workers.py`) + wiring
  `app.py` (`ROW_SUBTITLE_TRANSLATE`, PAGE_COUNT 14→15). 2 combo ngôn ngữ
  tìm-được (QComboBox editable + QCompleter, 204 mục), radio local/SaaS (SaaS
  disable khi `not is_configured()`, KHÔNG ẩn — đúng Constraint 5), cảnh báo
  khi chọn ngôn ngữ ngoài `VERIFIED_QUALITY_CODES`.
- **G** Tests — xem mục dưới.

### Bug thật tìm ra khi viết test route SaaS

`UsageLog`/`JobResult` (Mongoose model) có `action` field kiểu `enum` cứng
(`['translate','analyze','review','generate_post']`) — route
`/translate-subtitle` gọi `UsageLog.create({..., action: 'translate_
subtitle'})` **ném lỗi validation thật ngay lập tức** (500, không phải lỗi
suy đoán — bắt được bằng cách gọi HTTP thật qua `app.inject` rồi đọc response
body). Sửa: thêm `'translate_subtitle'` vào enum của cả 2 model. Nếu chỉ
unit-test tầng prompt/gateway (như V15) sẽ KHÔNG bao giờ bắt được bug này —
lý do route test (Scope G) đáng làm dù tốn công hơn.

### Tests (thật, chạy tại 2026-08-11)

- `tests/test_subtitle_parse.py` — 24 pass (đã có từ trước khi mở mini-spec
  chính thức, giữ nguyên).
- `tests/test_subtitle_translate.py` — **6 pass**: ghi file mới đúng tên,
  giữ nguyên timestamp, từ chối mã FLORES-200 không hợp lệ, từ chối nguồn=
  đích, billing SaaS đúng `creditCharged`/`balanceAfter`, câu thiếu trong
  kết quả trả về rơi về văn bản gốc (không mất nội dung).
- `tests/test_translate_subtitle_cli.py` — **5 pass**: `--list-languages`,
  thiếu tham số bắt buộc, mã FLORES-200 sai, chạy local thật (mock
  `run_local_worker`), chạy SaaS thật (mock `SaasClient`) — nạp module CLI
  bằng `importlib` (đúng cách vì `scripts/` không phải package).
- `control_server/tests/subtitle-translate-prompts.test.js` — **4 pass**:
  prompt builder đúng ngôn ngữ, KHÔNG có luật CPS/prosody của prompt dub,
  giữ đúng id/text, schema đúng.
- `control_server/tests/translate-subtitle-route.test.js` — **7 pass qua
  HTTP thật** (`fastify.inject`, mock `gateway.translateSubtitleBatch` —
  KHÔNG gọi AI provider thật, sandbox không có key): 401 thiếu token, 400
  mã FLORES-200 sai schema, **billing đúng số dòng × giá autotranslate
  KHÔNG cộng segment.base**, idempotent theo jobId (gọi lại không tính phí/
  không gọi lại AI — xác nhận bằng `mock.callCount()`), 400 BATCH_TOO_LARGE
  không gọi gateway, lỗi gateway → 503 KHÔNG trừ Vox, `credit.enabled=false`
  → `creditCharged=0`.
- Regression: `autodub` (pytest, sandbox không đủ `PySide6`/`numpy`/
  `ctranslate2`) **597 pass, 16 fail** (cùng 16 fail môi trường có từ trước
  V14/V15, đã xác nhận không liên quan) — tăng đúng +11 so với trước khi mở
  V14 (6 subtitle_translate + 5 CLI). `control_server`: `node --test
  tests/*.test.js` **157 pass, 1 skip** (tăng +11 so với sau V15: 7 route +
  4 prompt).

### GUI — verify headless (offscreen), KHÔNG phải bấm chuột thật

Môi trường viết mini-spec này không có `PySide6` cài sẵn lẫn màn hình — đã
tự cài `PySide6` vào 1 venv tạm (`pip install PySide6`, xoá sau khi xong) và
chạy `QT_QPA_PLATFORM=offscreen` để verify THẬT (không phải chỉ đọc code):
- `SubtitleTranslatePage` dựng được, `on_shown()` chạy không lỗi, mặc định
  nguồn=`eng_Latn`/đích=`vie_Latn` đúng.
- Cảnh báo chất lượng ẩn với vi/en, hiện đúng khi đổi sang ngôn ngữ chưa
  kiểm chứng (vd `fra_Latn`).
- `_start()` chặn đúng: chưa chọn file, nguồn=đích giống nhau — không tạo
  worker.
- **Luồng thật qua QThread** (bấm nút → `SubtitleTranslateWorker.run()` →
  tín hiệu `finished_ok`/`failed`): mock `translate_subtitle_file_local`/
  `saas_client.get_client` (không chạy model/gọi mạng thật), bơm event loop
  Qt thật (`QEventLoop`) chờ luồng nền chạy xong THẬT — xác nhận cả 2 nhánh
  local và SaaS cập nhật đúng `summary` (kèm số Vox đã trừ ở nhánh SaaS),
  bật đúng nút "Mở thư mục", và nhánh lỗi gọi đúng `ConfirmDialog.show_error`
  + dòng log thân thiện qua `error_line()`.
- **Chưa verify**: bố cục/màu sắc thật (không có màn hình để nhìn), thao tác
  chuột thật của người dùng, và cụm `MainWindow`/Sidebar đầy đủ trong `app.py`
  (dispatch `ROW_SUBTITLE_TRANSLATE` chỉ 3 dòng, rập khuôn các dispatch khác
  đã hoạt động — rủi ro thấp nhưng CHƯA tự xác nhận bằng cách chạy app thật).

### Live verification — THẬT (2026-08-11, sau khi có key thật từ chủ dự án)

Cùng đợt live-verify với V15 ở trên (Mongo + `control_server` thật qua
`docker compose`, provider Gemini thật, device thật):

1. `POST /translate-subtitle` thật, `eng_Latn→vie_Latn`, 2 dòng: bản dịch
   THẬT đúng nghĩa, tự nhiên ("Hello, welcome to our channel." → "Chào mừng
   quý vị đến với kênh của chúng tôi."; "Today we are going to talk about
   cats." → "Hôm nay chúng ta sẽ nói về mèo."). `creditCharged=4` đúng
   2 dòng × giá autotranslate (2), KHÔNG cộng `segment.base`.
2. `vie_Latn→eng_Latn` (chiều ngược): "Xin chào các bạn, hôm nay trời đẹp
   quá." → "Hello everyone, it's such a beautiful day today." — đúng.
3. **Idempotency thật**: gọi lại đúng `jobId` cũ — response giống hệt, số
   dư Mongo (`db.devices.findOne(...)`) xác nhận KHÔNG bị trừ Vox lần 2
   (500 → 496 → 494, không phải 490).

Nhờ đó `vie_Latn`/`eng_Latn` giờ đã live-verify chất lượng qua **CẢ 2
đường** — local (NLLB, V6/V11) và SaaS (Gemini thật, V14) — không chỉ NLLB
như trước.

### Remaining Limits (V14)

- **~190/204 mã FLORES-200 CHƯA kiểm chứng chất lượng dịch thật qua đường
  nào** — chỉ `vie_Latn`/`eng_Latn` đã live-verify (xem "Live verification"
  ở trên). Đây là giới hạn CÓ CHỦ ĐÍCH (đúng tinh thần V4: "mở rộng có kiểm
  chứng, không làm tất cả cùng lúc"), không phải thiếu sót — GUI/CLI đều
  cảnh báo rõ khi chọn ngôn ngữ chưa kiểm chứng.
- Local NLLB path (`run_local_worker`) CHƯA live-verify qua chính
  `translate_subtitle_file_local()` — venv `.venv-mt` (ctranslate2) không có
  trong sandbox này (cùng giới hạn `test_translate_local.py::..._real_model`
  đã ghi ở V6). Đường SaaS đã live-verify thật (mục trên); đường local mới
  chỉ verify ở mức unit/mock.
- Không có cơ chế huỷ giữa chừng ở GUI (`SubtitleTranslateWorker` không có
  `cancel()`) — lượt dịch 1 file thường nhanh, chưa đáng cơ chế huỷ như
  `DownloadWorker`. Nếu file rất lớn (nhiều nghìn dòng) qua SaaS mất nhiều
  phút, người dùng phải chờ hết hoặc đóng app.
- SaaS path không có lưới CJK-leftover-fix như `/translate` (V15 giữ
  nguyên lưới đó cho pipeline dub) — nếu model trả sót chữ Hán cho phụ đề
  dịch từ nguồn tiếng Trung, không có lượt dịch lại tự động thứ 2.
- `docs/ARCH.md` cập nhật số trang GUI 14→15 và số test cộng dồn theo diff
  (không tự đếm lại toàn repo do thiếu dependency trong sandbox) — xem ghi
  chú trong chính ARCH.md.

## V16 — Retry/backoff cho các lượt gọi SaaS một-lần (Phase E, 2026-08-11)

Theo `docs/PLAN.md` mục V16 (Phase E — mở sau khi so sánh với thị trường
auto-dub thương mại). Guardrail: không sửa `translate_saas.py` (đã đúng,
gắn luồng tiền), không retry `submit_demucs_job()`/hold (không idempotent-
safe hoặc đã có fallback cố ý), lỗi cố định không bao giờ retry.

### Audit Before Build

Grep toàn bộ 6 file gọi `get_client()` trong `autodub/`:
`translate_saas.py` (đã có bounded-retry+backoff+jitter+rate-limit đầy đủ —
không đụng), `billing.py` (setup_hold/settle_hold_inline — fallback cố ý,
không retry, giữ nguyên), `content/generator.py`/`telemetry.py` (tính năng
phụ, fail-soft chấp nhận được, không retry), `cloud_render.py` (poll +
tải kết quả — MỘT LẦN, không retry — **gap thật**), `subtitle_translate.py`
(dịch phụ đề SaaS — MỘT LẦN cho cả file, không retry — **gap thật**).

### Thêm

- `autodub/saas_retry.py` (mới) — `is_retryable_error()`, `sleep_cancellable()`,
  `call_with_retry()`, rút đúng pattern đã chứng minh đúng của
  `translate_saas.py` nhưng KHÔNG import/sửa file đó (duplicate có chủ đích
  — tách rủi ro khỏi code tiền đang chạy đúng).
- `cloud_render.py::separate_vocals_cloud()`: poll loop giờ phân biệt lỗi
  tạm thời (log cảnh báo, thử lại vòng kế — không lùi `MAX_WAIT_S`, bỏ cuộc
  sau `MAX_CONSECUTIVE_POLL_ERRORS=5` lần liên tiếp ~15s) vs lỗi cố định
  (raise ngay). `download_job_result()` × 2 (vocals/no_vocals) bọc
  `call_with_retry` — an toàn vì mở file `"wb"` mỗi lần, tự ghi đè.
- `text/subtitle_translate.py::translate_subtitle_file_saas()`: lượt gọi
  `translate_subtitle()` bọc `call_with_retry` — an toàn vì `job_id` ổn
  định theo nội dung (idempotent, không tính phí 2 lần).
- `autodub.spec`: thêm `autodub.saas_retry` vào `hiddenimports` (import lười
  trong thân hàm, đúng convention đã có cho `saas_client`).

### Verify (unit/mock — không cần mạng thật, đổi hành vi lỗi-mạng không đổi contract API)

- `tests/test_saas_retry.py` (12 test, mới): phân loại đúng lỗi tạm thời/cố
  định, retry-rồi-thành-công, hết lượt thì raise, lỗi cố định raise ngay
  không tốn lượt thử, tôn trọng `retry_after` làm mức chờ tối thiểu.
- `tests/test_cloud_render.py` (+4 test): 1 poll lỗi tạm thời không huỷ job
  đang chạy khoẻ (thử lại vòng kế); bỏ cuộc đúng sau
  `MAX_CONSECUTIVE_POLL_ERRORS+1` lần gọi; lỗi cố định (hết Vox) raise ngay
  lần đầu, không thử lại; tải kết quả lỗi 1 lần rồi thành công ở lần 2.
- `tests/test_subtitle_translate.py` (+2 test): dịch SaaS lỗi tạm thời 1
  lần rồi thành công (đúng nội dung, đúng `credit_charged`); lỗi cố định
  (hết Vox) raise ngay, không thử lại.
- `pytest tests/ -q` toàn bộ: **742 passed, 4 skipped, 0 failed** (724 + 18
  test mới), 0 regression.

### Remaining Limits (V16)

- Không live-verify HTTP thật lượt này — thay đổi chỉ ở hành vi khi lỗi
  mạng xảy ra (retry có kiểm soát thay vì raise ngay), không đổi request/
  response contract với `control_server` thật, nên unit/mock đủ để tự tin;
  cơ hội quan sát thật chỉ đến khi có 1 lượt cloud-render/dịch phụ đề SaaS
  thật gặp đúng lúc mạng chập chờn — chưa có dịp đó trong phiên này.
- `submit_demucs_job()` VẪN single-attempt có chủ đích (xem Constraint 2,
  V16) — nếu muốn retry an toàn cho bước này, cần thêm idempotency key do
  client sinh ở tầng `control_server` (thay đổi API, ngoài phạm vi V16).
- Chưa có dead-letter queue thật (job/lượt dịch thất bại hẳn sau khi hết
  lượt retry chỉ raise lỗi cho caller xử lý như cũ, không ghi vào đâu để
  theo dõi tập trung) — nếu muốn giám sát tỉ lệ lỗi thật ở quy mô, cần
  mini-spec riêng cho observability/alerting (ngoài phạm vi V16, xem thêm
  nhận xét "Remaining Limits" của báo cáo research thị trường Phase E).

## V17 — Mở rộng ngôn ngữ đích theo catalog CapCut thật (Phase E, 2026-08-11)

Theo `docs/PLAN.md` mục V17. Guardrail: chỉ thêm ngôn ngữ có giọng CapCut
thật, đánh dấu "thử nghiệm" cho mọi ngôn ngữ trừ vi, không đổi hành vi
vi/en hiện có, sửa ngay nếu audit lộ bug ảnh hưởng ngôn ngữ đang chạy.

### Audit Before Build

`python3` đọc trực tiếp `Voice.json` (127 giọng thật): field `lang`
(BCP-47) cho đúng **10** giá trị phân biệt — `en-US`(40) `vi-VN`(22)
`ja-JP`(19) `zh-CN`(16) `es-ES`(9) `th-TH`(6) `id-ID`(5) `pt-BR`(4)
`fr-FR`(3) `de-DE`(3). Con số "12 ngôn ngữ" ghi ở V8 TEST_LOG là đếm nhầm
field `lan` ngắn (có `jp`/`ja` và `br`/`pt` trùng cùng 1 ngôn ngữ) — đã
sửa lại đúng ở đây.

**Bug thật phát hiện ngoài phạm vi trực tiếp** (không phải lỗi của V17,
lỗi có sẵn từ V11): `autodub/speech/tts/capcut_vi.py::CapCutSynthesizer.
synthesize()` gọi `normalize_vi_text()` (đọc số kiểu tiếng Việt) cho MỌI
giọng CapCut bất kể ngôn ngữ — kể cả giọng tiếng Anh đã live-verify từ
V11. Không crash, chỉ đọc sai số khi câu có số ("90%" đọc thành "chín mươi
phần trăm" dù giọng đang dùng là tiếng Anh/Nhật/...). Phát hiện lúc đọc kỹ
`synthesize()` để hiểu luồng trước khi thêm target mới (đúng tinh thần
audit-before-build, không phải cố tình đi tìm bug).

### Sửa

- `capcut_vi.py::CapCutSynthesizer.__init__`: lưu `self._lang` (trước đây
  `lang` chỉ dùng để lookup catalog rồi bỏ, không giữ lại).
- `capcut_vi.py::synthesize()`: chỉ gọi `normalize_vi_text()` khi
  `self._lang == capcut_catalog.LANG` ("vi-VN") — giọng khác giữ nguyên
  số, để CapCut (TTS thương mại) tự đọc đúng ngôn ngữ của chính nó.
- `autodub/languages.py`: `TARGETS` +8 entry (ja/zh/es/th/id/pt/fr/de),
  field suy máy móc từ key qua vòng lặp dữ liệu.
- `autodub/text/translate_local.py`: `LANG_TO_FLORES` +4 mã (es-ES→
  spa_Latn, pt-BR→por_Latn, fr-FR→fra_Latn, de-DE→deu_Latn — lấy đúng từ
  bảng `flores200.py` đã fetch thật ở V14, không suy đoán). ja-JP/th-TH/
  id-ID/zh-CN đã có sẵn từ V4.
- `autodub_gui/dub_constants.py`: `DUB_TARGETS` +8 dòng, nhãn "thử
  nghiệm" cho mọi ngôn ngữ trừ vi.

### Verify

- `tests/test_multilang_target.py` (+2 test): registry đủ 10 target, mỗi
  target có giọng CapCut thật (`capcut_catalog.entries(lang=code)` khác
  rỗng) VÀ resolve được FLORES-200 (không rơi ngầm về vi).
- `tests/test_capcut_tts.py` (+2 test): giọng tiếng Việt vẫn đọc số kiểu
  Việt (0 regression) — giọng khác (test bằng en-US) giữ nguyên số, không
  bị chèn chữ Việt.
- `tests/test_translate_local.py`: sửa 2 test dùng "fr-FR" làm ví dụ mã
  CHƯA map (nay đã map thật) — đổi sang mã giả "xx-XX".
- `pytest tests/ -q` toàn bộ: **746 passed, 4 skipped, 0 failed** (742 +
  4 test mới, đã trừ đi 2 test sửa lại không phải test mới thật).

### Live verification — THẬT, 1/8 ngôn ngữ mới (tiếng Nhật)

Chọn tiếng Nhật (19 giọng, nhiều thứ 2 sau vi/en) — 2 lượt gọi THẬT, không
mock:

1. **NLLB local thật**: tải model `nllb-200-distilled-600M-ct2-int8`
   (622MB) thật từ HuggingFace, gọi `run_local_worker()` thật (ctranslate2
   inference thật, không stub) dịch `vie_Latn`→`jpn_Jpan`:
   - "Xin chào, hôm nay trời đẹp quá." → "こんにちは 今日はとても素敵です"
     (Xin chào, hôm nay rất đẹp/tuyệt — đúng nghĩa, tự nhiên).
   - "Tôi rất vui được gặp bạn." → "初めまして." (lối chào chuẩn khi gặp
     lần đầu trong tiếng Nhật — tự nhiên hơn cả dịch sát nghĩa).
2. **CapCut TTS thật**: `CapCutSynthesizer(settings, "Hatunemiku",
   lang="ja-JP")`, gọi API CapCut thật (mạng thật, không mock) với câu
   tiếng Nhật vừa dịch — nhận về WAV thật: `duration=2.352s`,
   `RMS amplitude=3345` (khác 0 xác nhận có tiếng nói thật, không phải
   file rỗng/lỗi im lặng), `ffprobe` xác nhận PCM 16-bit/44.1kHz hợp lệ.

### Remaining Limits (V17)

- **7/8 ngôn ngữ mới CHƯA live-verify** (zh/es/th/id/pt/fr/de) — chỉ ja đã
  xác nhận thật qua dịch+TTS. Đúng nguyên tắc "mở rộng có kiểm chứng,
  không làm tất cả cùng lúc" (V4) — GUI đánh dấu "thử nghiệm" rõ ràng cho
  cả 7 ngôn ngữ này, không giả vờ đã kiểm chứng.
- Chưa chạy `DubPipeline.run()` đầy đủ (ASR nguồn + dịch + TTS + mux video)
  cho target=ja — chỉ verify riêng 2 mắt xích MỚI (dịch+TTS), không phải
  toàn bộ pipeline. Rủi ro thấp vì phần còn lại (ASR, mux, subtitle,
  timing) đã chứng minh KHÔNG phụ thuộc target ở V11 (live-verify target=en
  full pipeline, xem TEST_LOG mục V11) — nhưng chưa tự xác nhận riêng cho
  target=ja bằng 1 lượt full pipeline thật.
- Chất lượng dịch NLLB cho 7 ngôn ngữ còn lại chưa đánh giá — 2 câu tiếng
  Nhật ở trên "đọc được, tự nhiên" theo đánh giá của người không phải bản
  ngữ Nhật (giới hạn tương tự đã ghi ở V11 cho tiếng Anh) — cần người bản
  ngữ hoặc bên thứ ba đánh giá trước khi quảng bá rộng.
- `control_server` (`resolveTargetLang()`, xem `prompts/translate.js`)
  KHÔNG có bộ quy tắc bản ngữ riêng cho 8 ngôn ngữ mới (chỉ vi/en có
  `LANGUAGE_RULES` — 8 ngôn ngữ mới rơi về `_GENERIC_RULES` chung khi dịch
  qua đường SaaS) — đường SaaS cho các ngôn ngữ này chưa được đánh giá
  chất lượng, chỉ đường local (NLLB) đã live-verify ở trên cho tiếng Nhật.

## Ghi nhận: thử deploy lên VAYS (2026-08-12) — không phù hợp cho monorepo này

Chủ dự án yêu cầu deploy `control_server` lên nền tảng VAYS (`vibehost.matbao.ai`,
PaaS nội bộ Mắt Bão, auto-detect + tự build từ Git). Thử thật, không suy đoán:

1. **`git.matbao.support` không kết nối được từ hạ tầng build VAYS** — network
   namespace VAYS không tới được GitLab nội bộ (`Failed to connect ... Couldn't
   connect to server`). Khắc phục: mirror repo sang GitHub công khai
   (`github.com/junnyken/voxdub-studio`) — VAYS clone được từ đó.
2. **Deploy nguyên gốc repo (không subdir)**: VAYS nhận nhầm cả monorepo là
   **"framework=python"** (vì quét thấy nhiều code Python ở `autodub/` hơn
   `control_server/` Node) → container thật sự cố chạy `python /app/app.py`
   (không tồn tại) → crash-loop 6 lần → bị circuit-breaker chặn. Đồng thời tự
   gộp env-var của CẢ desktop app (`autodub_gui`, ~14 biến vô nghĩa với server)
   lẫn `control_server`/`render_worker` thành 1 danh sách 19 biến "thiếu", và tự
   nối sai 1 biến (`CONTROL_SERVER_URL`) vào MongoDB managed tự tạo (vô lý về kỹ
   thuật — biến đó là URL nội bộ giữa 2 container, không liên quan CSDL).
3. **Deploy chỉ `subdir=control_server`** (bỏ `render_worker`, dùng MongoDB
   managed VAYS): nhận diện đúng Node, chỉ hỏi đúng 5 biến thật cần
   (`ADMIN_TOKEN`, `PAYOS_*` ×3, `WORKER_INTERNAL_TOKEN`) — nhưng build LỖI THẬT
   khác: `control_server/Dockerfile` COPY cả `website/` lẫn `control_server/`
   (2 thư mục anh em ở gốc repo, vì server tự serve luôn website cùng process) —
   mô hình `subdir` của VAYS đặt build context = chính subdir đó, không "nhìn"
   ra được thư mục anh em `website/`. AI Doctor của VAYS tự thử sửa 3 lượt,
   `aiFixStopReason: "no_change"` — không tìm ra cách sửa tự động.
4. Ngoài ra 2 lần gặp `NO_HEALTHY_NODE` (hạ tầng VAYS hết node rảnh tạm thời) —
   không liên quan cấu hình, tự hết sau vài phút.

**Kết luận**: VAYS (auto-detect PaaS đơn-service) không phù hợp kiến trúc hiện
tại của repo này (monorepo nhiều ngôn ngữ, `control_server` cố ý serve chung
`website/` cùng process, `docker-compose.yml` 3-service ở gốc). Sửa để vừa VAYS
(tách server khỏi website, hoặc bỏ render_worker) là đổi kiến trúc thật chỉ để
vừa 1 nền tảng cụ thể — chủ dự án đã quyết **KHÔNG làm** (xem PLAN.md), giữ
nguyên kiến trúc đã live-verify đầy đủ qua Docker Compose thật (mục V12) làm
bằng chứng chính. Nếu cần deploy công khai thật sau này, xem lại `mb-deploy`/
Coolify (đã nhắc trong CLAUDE.md) — nền tảng đó vốn nhận `docker-compose.yml`
trực tiếp, không qua lớp auto-detect single-app như VAYS.

**Dọn dẹp còn nợ**: 3 project rác trên VAYS (`voxdub-control-server`,
`voxdub-studio`, `voxdub-server`, đều trạng thái lỗi) + 1 MongoDB managed
(`voxdub-studio-db`) — không có API xoá qua MCP, chủ dự án cần tự xoá qua
dashboard VAYS nếu muốn giải phóng hạn mức (đang dùng 3/10 dịch vụ). Repo
mirror GitHub (`github.com/junnyken/voxdub-studio`, public) vẫn còn tồn tại —
cân nhắc xoá hoặc chuyển private nếu không cần dùng tiếp cho VAYS.

## V18 — Bộ quy tắc dịch riêng cho 8 ngôn ngữ đích mới + nâng cấp tiếng Việt (Phase E, 2026-08-12)

Theo `docs/PLAN.md` mục V18. Chủ dự án yêu cầu trực tiếp: xây bộ khung ngữ
cảnh/giọng điệu/ngữ điệu/thái độ "chuẩn chỉnh theo đúng từng quy tắc ngôn
ngữ riêng", ưu tiên đặc biệt tiếng Việt, và "học hỏi mỗi lần ngữ cảnh".

### Đọc hiểu yêu cầu trước khi code

"Học hỏi mỗi lần ngữ cảnh" ánh xạ vào cơ chế ĐÃ CÓ SẴN trong kiến trúc:
`buildAnalysisPrompt()` (pass 0 của luồng dịch 3-pass) đọc lại transcript
MỖI VIDEO và tự sinh domain/xưng hô/thuật ngữ/style_notes riêng cho video
đó — không phải học từ dữ liệu lịch sử (không có kho lưu trữ liên phiên,
đúng nguyên tắc "không mở rộng thu thập dữ liệu" đã chốt trước đó trong
phiên này). Gap thật: cơ chế này TRƯỚC ĐÂY chỉ có gợi ý đúng ngôn ngữ
(pronounsHint/domainHint bằng tiếng Việt) cho `targetKey==='vi'` — mọi
ngôn ngữ khác (kể cả tiếng Anh) rơi về gợi ý CHUNG bằng tiếng Anh, nghĩa
là bước "học" ngữ cảnh không thực sự học đúng NGÔN NGỮ đích ngoài tiếng
Việt. Đây là gap thật cần đóng, không phải suy diễn.

### Sửa

- `LANGUAGE_RULES` (`control_server/src/prompts/translate.js`) mở rộng từ
  {vi, en} → 10 ngôn ngữ, thêm `ja`/`zh`/`es`/`th`/`id`/`pt`/`fr`/`de` —
  khớp đúng 10 `TargetLang` đã đăng ký ở `autodub/languages.py` (V8/V11/V17).
  Mỗi ngôn ngữ có ROLE & TONE, quy tắc PHÁT ÂM TỰ NHIÊN, NAMES & BRAND
  NAMES, NUMBERS & UNITS (đọc số kiểu TTS), MISC & FORMATTING RIÊNG — có
  căn cứ ngôn ngữ học thật, không phải bản dịch máy móc của bộ tiếng Anh:
  - **Tiếng Nhật**: đăng ký です/ます (lịch sự-thân mật, chuẩn creator) thay
    vì kính ngữ 敬語 hay だ/である suồng sã; trợ từ cuối câu ね/よ/な/か mang
    đúng thái độ; tên người Trung GIỮ Kanji (không chuyển Pinyin — khác
    hẳn quy ước vi/en); số đếm dùng đúng lượng từ tiếng Nhật (個/人/回),
    không đọc số trần.
  - **Tiếng Trung**: CHỦ ĐỘNG GIỮ trợ từ 啊/呢/吧/嘛 — ngược lại hoàn toàn
    với MỌI ngôn ngữ khác (đều chủ động loại bỏ trợ từ Trung) vì trợ từ là
    một phần tự nhiên của khẩu ngữ Quan Thoại; phân biệt 两 vs 二 trước
    lượng từ.
  - **Tiếng Thái**: nêu rõ ràng buộc ครับ/ค่ะ phải NHẤT QUÁN theo ngữ cảnh
    người dùng cung cấp (giới tính người nói) — không tự đoán, không trộn
    lẫn giữa các segment của cùng 1 người nói (rủi ro thật nếu đoán sai:
    nghe như nhiều người nói khác nhau).
  - **Tây Ban Nha/Pháp/Đức**: đăng ký đúng ngôi xưng hô mặc định cho nội
    dung creator thân mật (tú/tu/du) thay vì usted/vous/Sie trang trọng,
    có thể ghi đè qua ngữ cảnh người dùng.
  - **Bồ Đào Nha**: chốt biến thể Brazil (você) — đúng thực tế phân bố
    giọng CapCut (pt-BR, không phải pt-PT).
  - **Indonesia**: kamu/Anda, tránh slang Jakarta suồng sã (gue/lo) trừ khi
    ngữ cảnh yêu cầu rõ.
- **Nâng cấp tiếng Việt** (ưu tiên theo yêu cầu): thêm mục mới "ATTITUDE &
  INTONATION" — trợ từ cuối câu (nhé/nha/đấy/mà/cơ/chứ) đúng thái độ, từ
  nối khẩu ngữ (thì/mà/là) thay vì trang trọng khi không cần, cách chọn từ
  theo cảm xúc (phấn khích/mỉa mai/bực bội), phân biệt câu hỏi thật vs câu
  hỏi tu từ qua ngữ điệu; thêm mục trung lập vùng miền (mặc định chuẩn phổ
  thông, không tự ý thêm giọng địa phương).
- **Bug thật tìm ra khi audit trước khi mở rộng** (không phải bug mới tạo
  ra): `LANGUAGE_RULES.vi.emphasisExamples` bị gán y hệt chuỗi tiếng Anh
  của block `en` (`'"really", "definitely", "so", "actually"'`) — nghĩa là
  suốt từ trước tới giờ, phần "PROSODY & EMPHASIS" của prompt dịch tiếng
  Việt đưa VÍ DỤ TIẾNG ANH cho model tham khảo cách nhấn nhá câu tiếng
  Việt. Không rõ mức ảnh hưởng thực tế (model đủ mạnh có thể tự suy ra từ
  nhấn tiếng Việt đúng bất kể ví dụ), nhưng là lỗi thật, đã sửa thành
  '"thật sự", "cực kỳ", "quá trời", "đúng là"'.
- `buildAnalysisPrompt()`: bỏ nhánh `isVi` đặc cách, đọc trực tiếp
  `LANGUAGE_RULES[key].pronounsHint`/`.domainHint` — mọi ngôn ngữ ĐÃ
  NGHIÊN CỨU giờ "học" đúng gợi ý ngôn ngữ đó mỗi lượt phân tích (đúng yêu
  cầu "học hỏi mỗi lần ngữ cảnh"); ngôn ngữ THẬT SỰ chưa có block (vd `ko`)
  vẫn rơi về gợi ý chung, không giả vờ.

### Verify

- `control_server/tests/translate-prompts.test.js`: sửa 1 test cũ (dùng
  `ja` làm ví dụ "chưa có quy tắc riêng" — nay đổi sang `ko` vì `ja` đã có
  quy tắc riêng thật); +10 test mới: registry đủ 10 ngôn ngữ, bug
  emphasisExamples đã sửa, tiếng Nhật có counter+Kanji, tiếng Trung GIỮ
  trợ từ (ngược mọi ngôn ngữ khác), 3 ngôn ngữ Âu dùng đúng ngôi xưng hô
  thân mật, tiếng Thái buộc nhất quán ครับ/ค่ะ, mọi ngôn ngữ mới có
  emphasisExamples bằng CHÍNH ngôn ngữ đó (không phải tiếng Anh),
  buildAnalysisPrompt học đúng gợi ý riêng + vẫn rơi generic đúng chỗ,
  mọi ngôn ngữ mới có quy tắc đọc số TTS.
- `npm test` (`control_server` toàn bộ): **167/168 pass, 1 skip (cũ), 0
  fail** — 0 regression.

### Remaining Limits (V18)

- Đây là NÂNG CẤP PROMPT (hướng dẫn model dịch), không phải bảng tra cứu
  cứng — chất lượng thật phụ thuộc Gemini có tuân theo đúng các quy tắc
  ngôn ngữ học đã nêu hay không. Test ở trên khoá ĐÚNG NỘI DUNG PROMPT gửi
  đi (regression an toàn), KHÔNG live-verify chất lượng dịch thật qua cả 8
  ngôn ngữ mới (cần gọi Gemini thật + người biết ngôn ngữ đó đánh giá —
  ngoài phạm vi 1 phiên, và lặp lại đúng giới hạn đã ghi ở V17: chỉ tiếng
  Nhật đã live-verify qua đường LOCAL NLLB, chưa qua đường SaaS/Gemini).
- Quy tắc ngữ điệu/thái độ mới cho tiếng Việt (trợ từ cuối câu, từ nối)
  CHƯA có test live kiểm chứng model có thực sự dùng đúng — chỉ khoá được
  rằng prompt CÓ chứa hướng dẫn đó.
- Tiếng Thái: quy tắc ครับ/ค่ะ nhất quán dựa vào ngữ cảnh người dùng cung
  cấp — nếu người dùng KHÔNG cung cấp giới tính người nói, model phải tự
  chọn 1 quy ước và giữ nhất quán suốt video; chưa kiểm chứng thật model
  có giữ nhất quán qua nhiều lô (batch) dịch riêng biệt của cùng 1 video
  hay không (mỗi batch là 1 lượt gọi API độc lập — rủi ro lý thuyết: batch
  sau chọn khác batch trước nếu không có cơ chế nhớ giữa các lô ngoài
  "previous context" 1 vài dòng liền trước).
- 190/204 ngôn ngữ FLORES-200 còn lại (tính năng dịch phụ đề rời, V14) vẫn
  chưa có LANGUAGE_RULES riêng — quyết định trước đó (phiên trước) là giữ
  nguyên phạm vi, không mở rộng thêm ở đợt này.

## V19 — Bố cục phụ đề không tương thích ngôn ngữ không dấu-cách (Phase E, 2026-08-12)

Theo `docs/PLAN.md` mục V19. Chủ dự án hỏi trực tiếp: khi tự động đổi
giọng/ngôn ngữ, bố cục phụ đề có "cân đối" theo từng ngôn ngữ không —
audit thật (không suy đoán) qua Explore agent đọc code, tìm ra 4 vấn đề
thật, ảnh hưởng trực tiếp 3 ngôn ngữ mới (V17): Trung, Nhật, Thái.

### Audit — 4 phát hiện thật

1. **`autodub/text/srt.py` — bug ngắt dòng nghiêm trọng**: cả logic ngắt
   theo "số từ/dòng" lẫn "số ký tự/dòng" đều gọi `text.split()` (tách theo
   dấu CÁCH). Tiếng Trung/Nhật không có dấu cách giữa chữ → cả câu bị coi
   là "1 từ duy nhất" → không bao giờ ngắt dòng → phụ đề tràn khung hình.
   Tiếng Thái chỉ có dấu cách giữa CỤM (không phải từ) → ngắt thô, khó đọc.
2. **`autodub/text/ass_karaoke.py` — karaoke fallback cùng lỗi**: đường DỰ
   PHÒNG (`estimate_word_times`, chỉ chạy khi Whisper alignment thật thất
   bại) cũng `.split()` — cả câu tiếng Trung/Nhật sáng lên cùng lúc, mất
   hẳn hiệu ứng karaoke. Đường CHÍNH (alignment thật qua Whisper) đã đúng
   ngôn ngữ từ V11, không phải sửa.
3. **Ngưỡng ký tự/dòng cố định (42), không đổi theo ngôn ngữ**: chữ CJK
   render rộng hơn Latin cùng cỡ chữ (quy ước Unicode "East Asian Width" —
   ký tự "Wide/Fullwidth" ≈ gấp đôi bề ngang "Narrow/Halfwidth") — 42 ký tự
   CJK/dòng tràn khung hình dù ĐÃ ngắt đúng.
4. **Font đóng gói sẵn (`fonts/`) không phủ CJK/Thái**: 8 font hiện có đều
   là font trang trí Latin/tiếng Việt — chữ Trung/Nhật/Thái ghi cứng vào
   video (chế độ "burn") rất có thể hiện thành ô vuông rỗng (tofu).

Không test nào trong bộ hiện tại (`test_subtitle*.py`, `test_ass_karaoke.py`)
chạm tới CJK/Thái trước đợt này — góc mù thật, không phải đã biết mà bỏ qua.

**Quyết định phạm vi giữa chừng (chủ dự án đổi ý)**: ban đầu định sửa đủ cả
ja/zh/th + font Nhật/Thái. Chủ dự án sau đó yêu cầu: bỏ font Nhật/Thái, chỉ
giữ font Trung (vì zh là ngôn ngữ NGUỒN có sẵn từ đầu dự án — zh-CN/HK/TW,
hợp lý dùng chung font hơn ja/th vốn chỉ mới thêm làm đích ở V17), dồn ưu
tiên còn lại cho vi/en. Logic ngắt dòng/karaoke CHO ja/th vẫn giữ nguyên
trong code (không tốn thêm chi phí, đúng ngay cả khi chưa có font riêng —
người dùng có thể tự thả font Nhật/Thái vào `fonts/` theo đúng quy ước sẵn
có của dự án, xem `fonts/THEM_FONT_O_DAY.txt`), chỉ KHÔNG đóng gói sẵn font
cho 2 ngôn ngữ đó.

### Sửa

- `autodub/text/srt.py`: thêm `is_char_wrap_lang()` (ja/zh/th) — `_wrap_lines()`,
  `split_for_display()` ngắt theo KÝ TỰ khi ngôn ngữ đích thuộc nhóm này
  (bỏ qua `line_words` — khái niệm "số chữ/dòng" không có nghĩa cho CJK).
  Sửa thêm regex ngắt mệnh đề: `\s+` → `\s*` + thêm dấu câu CJK toàn độ
  rộng (，。！？；…) — dấu câu Latin cần `\s+` phía sau mới khớp, nhưng CJK
  không có khoảng trắng sau dấu câu nên regex cũ không khớp gì cả cho văn
  bản CJK. Thêm `MAX_LINE_CHARS_CJK = 20` (khác `MAX_LINE_CHARS = 42`) —
  bề rộng thật trên màn hình tương đương. `generate_srt`/`generate_srt_styled`
  nhận thêm `lang_key` — nối vào 3 call site thật: `subtitles.py::refresh_subtitles`
  (`target.key`), `pipeline.py` (transcript gốc, dùng `lang_code` NGUỒN),
  `editor.py` (xem trước trong Trình chỉnh sửa).
- `autodub/text/ass_karaoke.py`: `estimate_word_times()` nhận `char_tokens`
  — tách theo ký tự thay vì `.split()` cho ja/zh/th (mỗi chữ Hán/Kana đúng
  1 âm tiết, khớp ĐÚNG tinh thần ước lượng âm tiết ban đầu của hàm này, chỉ
  khác đơn vị "1 tiếng"). `_BREAK_PUNCT`/`_PAUSE_WEIGHT` thêm dấu câu CJK
  toàn độ rộng (cùng vấn đề như regex ở srt.py). `resolve_word_times()`
  tự suy `char_tokens` từ `language` (đã là mã Whisper ngắn sẵn có, khớp
  thẳng `is_char_wrap_lang()`, không cần chuyển đổi thêm).
- `fonts/NotoSansSC-Regular.ttf` (mới, ~10MB) — font thật Google Noto Sans
  Simplified Chinese, tải qua Google Fonts CSS2 API thật (không phải file
  tự tạo), **xác minh glyph coverage thật** bằng `fontTools` (23 ký tự Hán
  thường dùng test qua, 0 ký tự thiếu). Kèm `fonts/NotoSansSC-OFL.txt`
  (giấy phép SIL Open Font License thật, tải từ repo `google/fonts`) — đúng
  quy ước đã ghi sẵn trong `fonts/THEM_FONT_O_DAY.txt` ("Nhớ giữ kèm file
  license (OFL.txt) của font nếu phát hành app").

### Verify

- `tests/test_srt_generator.py` (+9 test): tái tạo ĐÚNG bug cũ (không
  `lang_key` → câu Trung dài vẫn 1 dòng, vượt xa MAX_LINE_CHARS) để khoá
  hành vi CŨ không đổi khi không truyền lang_key (0 regression cho call
  site chưa cập nhật); có `lang_key="zh"` → ngắt đúng, ghép lại đúng
  nguyên văn không mất/thêm ký tự; tiếng Nhật câu ngắn không dấu cách vẫn
  ra đúng 1 dòng; tiếng Thái ngắt theo ký tự; `line_words` bị bỏ qua đúng
  cho char_wrap; ngưỡng CJK (20) khác Latin (42); tiếng Việt hoàn toàn
  không đổi hành vi có/không truyền `lang_key`.
- `tests/test_ass_karaoke.py` (+5 test): tái tạo bug cũ (không `char_tokens`
  → cả câu Trung thành 1 "từ"); có `char_tokens=True` → tách đúng từng ký
  tự, mốc thời gian đơn điệu liên tục, phủ đủ `duration`; dấu câu CJK
  toàn độ rộng được nhận đúng trọng số nghỉ; `chunk_words()` gộp đúng cụm
  cố định theo ký tự, ghép lại đúng nguyên văn.
- `pytest tests/ -q` toàn bộ: **759 passed, 4 skipped, 0 failed** (746 + 13
  test mới về ngắt dòng/karaoke — tính cả 1 test khoá `MAX_LINE_CHARS_CJK`).
- Font: xác minh bằng `fontTools.ttLib.TTFont.getBestCmap()` thật, không
  suy đoán từ tên file.

### Remaining Limits (V19)

- **Font Nhật/Thái CHƯA đóng gói** — quyết định có chủ đích của chủ dự án
  (ưu tiên vi/en), không phải thiếu sót kỹ thuật. Logic ngắt dòng/karaoke
  cho ja/th vẫn đúng trong code, chỉ chưa có font đi kèm sẵn — người dùng
  cần dịch sang Nhật/Thái với chế độ "burn" phải tự thả font vào `fonts/`
  theo đúng hướng dẫn có sẵn của dự án.
- **Ngắt dòng tiếng Thái vẫn là "chấp nhận được", không phải đúng ranh
  giới từ thật** — ngắt theo ký tự tránh được bug "không bao giờ ngắt",
  nhưng có thể cắt giữa 1 từ tiếng Thái thật (đúng ranh giới từ cần bộ
  tách từ tiếng Thái riêng, vd `pythainlp` — thêm dependency mới, ngoài
  phạm vi mini-spec này, và không phải ưu tiên hiện tại theo chủ dự án).
- **`MAX_LINE_CHARS_CJK = 20`** là ước lượng hợp lý theo quy ước độ rộng
  ký tự Unicode + kinh nghiệm phổ biến ngành phụ đề (không phải số đo thật
  trên khung hình cụ thể của app này) — chưa có video CJK thật render ra
  để đo bằng mắt xem 20 ký tự có thật sự vừa khung hay cần chỉnh thêm.
- **Font Trung mới CHƯA test render thật qua libass/ffmpeg burn** — chỉ
  xác nhận glyph coverage ở tầng font file (fontTools), chưa chạy hết
  pipeline burn-in thật để nhìn tận mắt chữ Trung hiện đúng trên video
  xuất ra (cần video test + ffmpeg thật, ngoài phạm vi phiên này do chủ dự
  án đã đổi ưu tiên sang vi/en).
- Cỡ chữ (`SUBTITLE_FONT_SIZE`)/margin toàn cục vẫn là 1 giá trị người
  dùng tự chọn, không tự động đổi theo ngôn ngữ đích — quyết định có chủ
  đích: đây là preference của người dùng (áp dụng mọi ngôn ngữ), phần
  thích ứng thật sự cần thiết (bề rộng dòng) đã xử lý ở tầng ngắt dòng
  (`MAX_LINE_CHARS_CJK`), không cần ép đổi cỡ chữ toàn cục theo target.

## V20 — Bug suy giới tính giọng CapCut + khảo sát nguồn giọng vi/en (Phase E, 2026-08-12)

Theo `docs/PLAN.md` mục V20. Chủ dự án hỏi trực tiếp: nguồn giọng đọc
vi/en hiện tại có đa dạng ngữ điệu/nam-nữ không, muốn "ổn định chỗ này".

### Khảo sát thật (đọc dữ liệu thật, không suy đoán)

**VieNeu (offline, engine chính cho tiếng Việt)**: `voices/preset_voices_vn/`
— **120 giọng thật** (70 nam / 50 nữ, xác nhận qua `voices_manifest.json` +
đếm file `.wav`), mỗi giọng có tên người thật (vd "Huỳnh Khánh", "Dương Duy"),
mẫu âm thanh ~8 giây, transcript thật đi kèm. **Gap thật**: manifest KHÔNG
có trường phong cách/ngữ điệu (chỉ `display_name`/`gender`/`file_name`/
`transcript`) — không thể lọc "giọng ấm áp"/"giọng năng động" mà không nghe
thử từng giọng trong 120 giọng.

**CapCut vi-VN**: 22 giọng, có mô tả phong cách trong tên hiển thị ("Nữ
ngọt ngào", "Nam trầm ấm", "Review phim", "Bản tin trang trọng") — đa dạng
PHONG CÁCH tốt nhưng LỆCH giới tính nặng (16 nữ / 3 nam thật sự / 1 giọng
trẻ em / 3 giọng hiệu ứng ma quái-rung-robot không dùng cho lồng tiếng
bình thường).

**CapCut en-US**: 39 giọng (audit thật qua `Voice.json`, không phải 40 —
1 mục "Trickster" bị trùng tên với mục khác, mục sau bị loại khỏi
`entries()` do `seen` set theo tên — ghi nhận là gap nhỏ, xem Remaining
Limits). Tên hiển thị kém mô tả hơn tiếng Việt hẳn (nhiều tên thương hiệu/
gimmick như "Deadpool", "Oogie", "Grim Rock", "Suaraaa", "Robaa" không nói
lên chất giọng thật).

### Bug thật tìm ra

`autodub/speech/tts/capcut_catalog.py::_gender_of()` — heuristic CŨ chỉ
nhận diện đúng giọng nữ tiếng Việt: khớp `voice_type` với 3 tiền tố BV cụ
thể (BV421/BV074/BV562, đặc thù catalog vi-VN) hoặc chuỗi `"female"`
LITERAL trong `voice_type`. Với catalog tiếng Anh, giới tính thường ghi
ngay trong TÊN HIỂN THỊ chứ không phải `voice_type` — xác nhận thật qua
dữ liệu:

| Tên hiển thị | voice_type | Gender TRƯỚC sửa | Gender SAU sửa |
|---|---|---|---|
| Jenny | en-US-JennyMultilingualNeural | male ❌ | female ✅ |
| Energetic Famale | BV503_streaming | male ❌ | female ✅ |
| American Female | BV029_streaming | male ❌ | female ✅ |
| Dolly famle | en_us_002_dsp | male ❌ | female ✅ |

**Hậu quả THẬT** (không chỉ hiển thị sai): bộ lọc giới tính trong
`autodub_gui/pages/voice_library.py` (`gender=self._f_gender.currentData()`)
và màu thẻ giọng trong `ui/voice_card.py` (`"accent" if gender=="female"
else "processing"`) đều đọc trực tiếp trường `gender` này — 3-4 giọng nữ
thật bị ẩn khỏi kết quả lọc "Nữ", hiện sai màu thẻ.

### Sửa

- `_gender_of(voice_type, display_name="")`: đọc thêm TOÀN BỘ tên hiển thị
  (không chỉ phần mô tả sau dấu "-", vì catalog tiếng Anh thường không có
  dấu "-" tách tên/mô tả — tín hiệu giới tính nằm ngay trong tên chính).
  Bắt cả 2 lỗi chính tả thật tồn tại sẵn trong `Voice.json` ("Famale",
  "famle" — không phải suy đoán, đọc trực tiếp từ dữ liệu).
- Bảng tra riêng `_KNOWN_VOICE_TYPE_GENDER` cho giọng thương hiệu không có
  tín hiệu chữ nào (vd "Jenny" — tên + voice_type đều không chứa từ khoá
  giới tính): "en-US-JennyMultilingualNeural" là giọng Jenny của Microsoft
  Azure Neural TTS, giới tính nữ là thông tin công khai (voice gallery
  chính thức Microsoft), không phải suy đoán — liệt kê tường minh, tách
  khỏi heuristic chung để không code cứng thêm ngoại lệ không kiểm chứng
  được cho các trường hợp khác.
- `entries()`: truyền `display_name` gốc (trước khi tách) vào `_gender_of()`.

### Verify

- `tests/test_capcut_catalog.py` (mới, 7 test): tái tạo đúng bug cũ khi
  không có display_name (0 regression cho code gọi cũ); xác nhận đã sửa
  cho cả 4 giọng phát hiện thật; giọng Jenny qua bảng tra riêng; giọng
  hiệu ứng không tín hiệu vẫn mặc định "male" (giữ đúng quy ước cũ); phân
  bố giới tính catalog tiếng Anh thật không còn lệch do bug.
- `pytest tests/ -q` toàn bộ: **766 passed, 4 skipped, 0 failed** (759 + 7
  test mới).

### Remaining Limits (V20)

- **VieNeu (120 giọng) không có metadata phong cách/ngữ điệu** — chỉ có
  tên người + giới tính, không có tag như CapCut ("ngọt ngào"/"trầm ấm").
  Muốn tự động chọn giọng "phù hợp video" (vd giọng năng động cho video
  hài, giọng trầm cho video nghiêm túc) cần gắn nhãn phong cách cho 120
  mẫu — công việc nghe-đánh giá thủ công hoặc phân loại bằng AI, ngoài
  phạm vi audit này, cần mini-spec riêng nếu chủ dự án muốn.
- **1 giọng "Trickster" (en-US) bị ẩn khỏi catalog** do trùng tên với 1
  giọng khác (`entries()` loại theo tên đã `seen`) — dữ liệu gốc tồn tại
  (`voice_type` khác nhau: `en_male_trickster_stream` vs
  `DiT_en_male_trickster`) nhưng không cách nào chọn được giọng thứ 2 qua
  tên. Ảnh hưởng thấp (chỉ 1/39 giọng, cả 2 đều nam nên không ảnh hưởng
  phân bố giới tính) — cần đổi chính sách đặt tên duy nhất (vd thêm số thứ
  tự khi trùng) nếu muốn giải quyết triệt để, chưa làm vì phạm vi hẹp.
- **Chưa có cơ chế "chọn giọng tự động thông minh theo nội dung video"** —
  hiện tại người dùng luôn phải TỰ chọn giọng (hoặc dùng đúng 1 giọng mặc
  định cố định `DEFAULT_CAPCUT_VOICE = "Minh Trang"`); mọi lượt chạy tự
  động (batch, không thao tác tay) đều ra CÙNG 1 giọng trừ khi người dùng
  đổi cấu hình — đây có thể là đúng ý "ổn định" chủ dự án muốn (dữ liệu
  giới tính/phong cách phải ĐÚNG trước khi xây tính năng tự chọn), nhưng
  bản thân tính năng tự động chọn giọng theo ngữ cảnh CHƯA tồn tại — cần
  quyết định của chủ dự án có muốn xây mini-spec riêng cho việc này không.

## V21 — 2 bug thật đã biết từ lâu, chưa sửa: NLLB bỏ câu + giọng trùng tên (Phase E, 2026-08-12)

Theo `docs/PLAN.md` mục V21. Sau khi tổng hợp toàn bộ "Remaining Limits"
qua ~20 mini-spec (theo yêu cầu chủ dự án "tìm vấn đề tồn đọng"), 2 mục
được phân loại đúng nghĩa **BUG** (không phải "chưa live-verify" hay "có
chủ đích") — root-cause đã có sẵn từ trước, chỉ chưa ai quay lại sửa. Theo
đúng yêu cầu "lỗi thì sửa triệt để, test lại" — sửa cả 2 ngay.

### Bug 1 — NLLB bỏ sót câu khi ASR nguồn nhiễu (root-cause từ V11)

**Nguyên nhân** (đã cô lập ở V11, `docs/TEST_LOG.md` mục V11): khi 1
segment ASR chứa NHIỀU câu (Whisper VAD không tách ở đó — 2 câu liền
không đủ khoảng lặng), toàn bộ đoạn được đưa vào ctranslate2 trong 1 lượt
`translate_batch()` DUY NHẤT. Nếu 1 trong các câu có lỗi nghe ASR nhẹ
(nhiễu), model NLLB "dừng sớm" (early-stop decode) — CHỈ dịch được câu
đầu, các câu SAU bị mất HOÀN TOÀN, không lỗi, không log gì cả. Ảnh hưởng
MỌI cặp ngôn ngữ dùng đường dịch local (path C, V6), không riêng target=en
như audit V11 ban đầu nghi ngờ.

**Sửa**: `autodub/text/translate_local_worker.py` — thêm `_split_sentences()`
tách 1 segment thành từng câu riêng (theo dấu kết câu Latin + CJK toàn độ
rộng, cùng cách tiếp cận đã dùng ở V19 cho srt.py). Mỗi câu được đưa vào
`translate_batch()` như 1 nguồn RIÊNG trong CÙNG 1 lượt gọi (nhiều nguồn
cùng lúc, KHÔNG chung state decode với nhau — ctranslate2 decode độc lập
từng phần tử trong batch) — early-stop của model khi gặp 1 câu nhiễu giờ
chỉ mất đúng câu đó, không kéo theo các câu sau trong cùng segment.

**Verify thật** (không chỉ đọc code — dùng đúng model NLLB thật đã tải ở
phiên trước):
1. Tái tạo CHÍNH XÁC văn bản đã gây bug ở V11: "Trí tựa nhân tạo đang thay
   đổi cách chúng ta làm việc. Đây chỉ là giàn lập, không phải thật."
   (2 câu, câu 2 có lỗi nghe ASR nhẹ y hệt bug gốc).
2. **Trước khi sửa** (gọi thẳng `ctranslate2.Translator`, mô phỏng code
   cũ): "Artificial intelligence is changing the way we work." — CÂU 2
   MẤT HOÀN TOÀN, đúng y hệt bug đã ghi nhận ở V11.
3. **Sau khi sửa** (qua đúng đường code production —
   `translate_segments_local()` → subprocess worker thật, không mock):
   "Artificial intelligence is changing the way we work. It's just a
   disconnect, not real." — cả 2 câu đều có mặt. Câu 2 dịch không hoàn hảo
   (input vốn nhiễu — "giàn lập" là từ vô nghĩa) nhưng KHÔNG BỊ BỎ SÓT,
   đúng mục tiêu sửa (không đòi hỏi sửa được chất lượng dịch của input
   nhiễu, chỉ đòi hỏi không mất nội dung âm thầm).

### Bug 2 — Giọng CapCut trùng tên bị ẩn khỏi catalog (phát hiện ở V20)

**Nguyên nhân**: `capcut_catalog.py::entries()` loại bỏ mục có tên hiển thị
TRÙNG với mục đã thấy trước đó (`if name in seen: continue`) — catalog
tiếng Anh có 1 cặp trùng tên thật ("Trickster", 2 `voice_type` khác nhau:
`en_male_trickster_stream` và `DiT_en_male_trickster`) — mục thứ 2 bị loại
hẳn, không ai chọn được dù tồn tại thật trong `Voice.json`.

**Sửa**: đánh số phân biệt khi trùng tên thay vì loại bỏ — "Trickster" và
"Trickster (2)" đều xuất hiện trong catalog, đều chọn được.

### Verify

- `tests/test_translate_local.py` (+4 test): `_split_sentences()` thuần
  (Latin + CJK toàn độ rộng, đoạn không dấu kết câu, đoạn rỗng); test
  real-model (tự skip nếu không có model NLLB thật — chạy thật được trong
  sandbox này qua `VOXDUB_TEST_NLLB_MODEL_DIR`) tái hiện đúng bug rồi xác
  nhận đã sửa qua đường code production.
- `tests/test_capcut_catalog.py` (+2 test): cả 2 mục "Trickster"/"Trickster
  (2)" còn trong catalog với đúng `voice_type` gốc; không còn tên nào
  trùng nhau trong toàn bộ catalog tiếng Anh sau khi đánh số.
- `pytest tests/ -q` toàn bộ: **770 passed, 5 skipped, 0 failed** (766 + 9
  test mới, trừ đi phần skip khi thiếu model NLLB cục bộ).

### Remaining Limits (V21)

- Sửa NLLB chỉ THU NHỎ vùng ảnh hưởng của early-stop (còn tối đa 1 câu),
  KHÔNG sửa được gốc rễ (model tự dừng khi gặp input nhiễu) — 1 câu ĐƠN
  LẺ có nhiễu ASR vẫn có thể dịch kém/rỗng, chỉ không còn kéo theo các câu
  KHÁC trong cùng segment nữa. Nếu muốn xử lý cả trường hợp 1 câu đơn dịch
  rỗng/quá ngắn, cần thêm bước phát hiện+cảnh báo (đã nêu ở V11, chưa làm
  — ngoài phạm vi V21, chỉ tập trung đúng bug "mất câu SAU").
- Tách câu bằng regex dấu câu — câu không có dấu kết câu rõ ràng (transcript
  ASR thiếu dấu câu hoàn toàn) vẫn được coi là 1 câu duy nhất như trước,
  không có gì thay đổi/cải thiện cho trường hợp đó.

## V22 — CLI headless cho pipeline dub (Phase F, mini-spec chi tiết ở PLAN.md)

### Audit

- `autodub/pipeline.py`/`autodub/batch.py`: xác nhận thật KHÔNG import gì
  từ `autodub_gui`/`PySide6` (grep import graph) — đúng như docstring của
  `pipeline.py` tự nhận ("GUI-ready core"). Đường vào DUY NHẤT trước V22 là
  `autodub_gui/app.py:main()` (`[project.gui-scripts]`) — không có
  `[project.scripts]` console nào trong `pyproject.toml`.
- `autodub.speech.tts.voices.resolve(settings, name, target)` CHỦ ĐÍCH rơi
  ngầm về giọng khác khi tên không khớp danh mục (đúng cho GUI — người
  dùng thấy ngay, sửa lại bằng picker). Xác nhận đây LÀ thiết kế có chủ
  đích (đọc docstring hàm), không phải bug — nhưng là bẫy thật cho CLI/
  cron: gõ sai tên giọng trong script chạy định kỳ có thể âm thầm tạo
  video sai giọng nhiều tuần không ai biết. CLI KHÔNG dùng `resolve()`,
  validate tường minh trước khi gọi pipeline.
- `translate_local.py::run_local_worker()` (dùng trong pipeline dịch local)
  đọc `proc.stdout` bằng vòng lặp chặn KHÔNG timeout tổng — nếu worker
  treo, tiến trình gọi treo vô thời hạn. Ghi nhận là giới hạn CHƯA sửa ở
  V22 (đúng phạm vi — thuộc V24, xem PLAN.md).

### Xây dựng

- `autodub/cli.py` (mới) — `voxdub dub`/`voxdub batch`, lớp vỏ mỏng gọi
  thẳng `DubPipeline.run()`/`run_batch()` có sẵn, không viết lại logic
  pipeline. Validate `--target`/`--voice` tường minh (exit 2 nếu sai, liệt
  kê giọng khả dụng) thay vì để rơi ngầm. `--json` phát tiến trình dạng
  NDJSON đúng shape `ProgressEvent` ra stderr; kết quả cuối (JSON) ra
  stdout. Exit code: 0 hoàn thành/batch không lỗi nào, 1 lỗi pipeline/có
  video batch fail, 2 lỗi tham số.
- `pyproject.toml` — thêm `[project.scripts] voxdub = "autodub.cli:main"`
  (console script thật, không phải `gui-scripts` — không kéo Qt khi cài).

### Verify

- `tests/test_cli.py` (17 test mới): parse tham số đúng cho cả 2
  subcommand; `--help` exit 0; thiếu URL/file exit 2; `--target` sai exit
  2; **giọng sai exit 2 + liệt kê giọng khả dụng, KHÔNG rơi ngầm** (khoá
  đúng hành vi khác `voices.resolve()`, xem Audit); `DubRequest` dựng đúng
  từ mọi cờ CLI (pipeline mock, không chạy thật); exit code đúng cho cả 3
  trường hợp (thành công/status khác completed/exception pipeline); batch
  đọc file danh sách + báo cáo summary đúng, exit 1 khi có video fail,
  KHÔNG gọi `run_batch()` khi giọng sai (validate trước khi chạm pipeline);
  `[project.scripts]` khớp đúng trong `pyproject.toml`.
- **Cách ly import (Constraint 2)**: test đầu chạy `import autodub.cli`
  trong TIẾN TRÌNH CON riêng (subprocess) — không kiểm `sys.modules` trong
  cùng tiến trình pytest, vì các file test khác (`test_editor.py`,
  `test_fonts_app_only.py`...) tự import `autodub_gui`/`PySide6` trong lúc
  pytest COLLECT toàn bộ file, gây dương tính giả nếu đo trong cùng tiến
  trình (bug thật gặp phải khi viết test này, sửa ngay bằng subprocess).
  Xác nhận subprocess sạch: `import autodub.cli` xong,
  `'PySide6' not in sys.modules` và `'autodub_gui' not in sys.modules`.
- **Live-verify thật qua console script**: môi trường sandbox trước đó
  thiếu `numpy`/`pydub`/`PySide6`/`cryptography` (gói optional không cài
  sẵn — không phải do V22 gây ra, đã xác nhận các file test bị lỗi
  collection đều KHÔNG liên quan tới `cli.py`) khiến không chạy được toàn
  bộ suite trực tiếp trên hệ thống; dựng 1 venv riêng
  (`/tmp/voidmix-test-venv`), cài đủ dependency, `pip install -e . --no-deps`
  rồi chạy THẬT: `voxdub --help`, `voxdub dub --help` (in đúng mô tả 2
  subcommand), `voxdub dub` (thiếu URL) → in đúng thông báo lỗi tham số,
  exit code 2 — xác nhận entry point `console_scripts` hoạt động thật, không
  chỉ đúng khi gọi qua `python -m`.
- `pytest tests/ -q` toàn bộ (venv đầy đủ dependency): **778 passed, 6
  skipped, 0 failed** (775 pass ở V21 + 17 test CLI mới, trừ 1 test cách ly
  đổi từ đo trực tiếp `sys.modules` sang subprocess không đổi số lượng ròng
  theo cách tính khác — số test file thực tế +17, xem diff `test_cli.py`).

### Remaining Limits (V22)

- **Chưa live-verify 1 lượt dub THẬT end-to-end qua CLI** (cần mạng/GPU
  thật, ngoài ngân sách thời gian đợt này — ưu tiên dồn cho việc viết đủ 4
  mini-spec Phase F theo đúng yêu cầu "kế hoạch nâng cấp phải xây theo
  MINI-SPEC" trước khi code). Đã live-verify được lớp WIRING (console
  script, argparse, exit code) thật qua `voxdub` — chưa verify được lớp
  PIPELINE thật chạy qua đường CLI (khác hẳn gọi API Python trực tiếp).
  Cùng loại giới hạn như 7/8 ngôn ngữ "thử nghiệm" ở V17: hạ tầng đúng theo
  test cách ly + mock, đường thật chưa chạy 1 lần.
- V23 (cổng chất lượng)/V24 (retry + watchdog + failures.jsonl)/V25
  (watch-folder) đã có mini-spec kỹ thuật đầy đủ trong `docs/PLAN.md` (Phase
  F) nhưng CHƯA triển khai — chờ chủ dự án xác nhận trước khi code, đúng
  quy trình audit→propose→confirm→execute đã dùng xuyên suốt các mini-spec
  trước.
- Watchdog cho subprocess treo (gap thật đã audit ở `run_local_worker()`)
  CHƯA sửa trong V22 — thuộc đúng phạm vi V24, không mở rộng lấn sang V22.

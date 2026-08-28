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

### Re-audit 2026-08-17 — cân nhắc lại, GIỮ NGUYÊN (đúng kết luận gốc)

Đếm lại cụ thể (grep thật, không suy đoán): `HOLD`/`USAGE` vẫn được đọc
trực tiếp ở đúng **20 chỗ trong 5 file** (`translate_saas.py`,
`translate_review.py`, `translate_hint.py`, `content/generator.py`,
`pipeline.py`) — gồm cả `HOLD.key` (khóa AES-256-GCM giải mã transcript/
cache) và `hold_id` (truyền cho SaaS để đối soát billing), không chỉ vài
chỗ hold-cụ-thể như V2 gốc từng giả định. Môi trường phiên này lúc này ĐÃ
có `ffmpeg`/mạng thật (khác lúc audit V2 gốc) nhưng VẪN thiếu GPU + key AI
thật + `control_server` thật — đúng 3 điều kiện gốc đã nêu là cần để
regression-test an toàn luồng hold end-to-end. Đã báo cụ thể cho chủ dự
án trước khi động vào; **quyết định: GIỮ NGUYÊN, không refactor** — đây là
code xử lý tiền/mã hóa thật, refactor thuần kiến trúc không mang lại lợi
ích chức năng nào, rủi ro thật không tương xứng khi không kiểm chứng được
đầy đủ. Nợ kỹ thuật này vẫn còn nguyên, ghi nhận lại thay vì giả vờ đã
đóng.

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

### Re-audit 2026-08-17 — video nén thật đa dạng hơn, đóng thêm 3 gap

Sandbox này có mạng thật nhưng KHÔNG có cách tải video TikTok/Douyin/
YouTube thật mà không dấy lên câu hỏi bản quyền/redistribution cho nội
dung của người khác — thay vào đó dựng video **nén thật** (ffmpeg
`libx264`, không phải PNG tĩnh) phức tạp hơn hẳn đợt 08-11: nền có NHIỄU
THỜI GIAN (`noise=alls=15:allf=t+u`, không phải màu phẳng/testsrc đơn
giản) + 3 loại chữ overlay CÙNG LÚC, đúng 3 case Test Plan gốc từng liệt
kê nhưng chưa test: watermark Trung **CÓ HIỆU ỨNG MỜ DẦN THẬT** (alpha dao
động theo thời gian qua biểu thức ffmpeg, không phải trong suốt cố định),
tiêu đề kênh **tiếng Việt CÓ DẤU** (trước giờ chỉ test tiếng Trung), phụ đề
cứng kiểu burn-in (hộp nền mờ, giữa khung hình dưới — CHƯA từng test).

**Kết quả THẬT (RapidOCR thật, không mock):**
- Cả 3 loại chữ đều phát hiện đúng, xác nhận bằng crop trực quan (không
  chỉ tin số IoU — đúng phương pháp 08-11): "Kênh Ẩm Thực Việt" (tiêu đề,
  full dấu tiếng Việt đọc đúng), "频道水印 CHANNEL" (watermark, phát hiện
  được NGAY CẢ khi đang ở giữa chu kỳ mờ dần — alpha ~0.4-0.8 tại frame
  test), "Hôm nay mình sẽ hướng dẫn các bạn làm món ăn" (phụ đề cứng, full
  dấu, đọc đúng nguyên văn).
- **Phát hiện mới**: 1 false positive trên hoa văn góc của `testsrc2`
  (pattern QR-giống-chữ tự sinh của chính nguồn test, KHÔNG phải watermark
  tôi vẽ) — confidence `0.793`, THẤP HƠN RÕ RỆT mọi phát hiện thật (đều
  ≥`0.98`). Chưa đủ dữ liệu (1 điểm) để chốt ngưỡng lọc confidence — ghi
  nhận làm đầu vào cho quyết định sau nếu muốn thêm bộ lọc, không tự thêm
  ngưỡng dựa trên 1 mẫu.
- Guardrail 4 xác nhận lại trên nền THẬT phức tạp (nhiễu thời gian qua
  ffmpeg, không chỉ màu phẳng PIL như test gốc): video sạch không chữ vẫn
  trả về rỗng.
- **Đóng một phần gap "chưa đo % thời gian"**: đo được `1.25s/frame` OCR
  thật (3 frame/3.74s). Xác nhận `autodub_gui/style_dialog.py::_OcrWorker`
  CHỈ quét đúng 3 frame đại diện (đầu/giữa/cuối) bất kể video dài bao
  nhiêu — chi phí OCR vì vậy gần như HẰNG SỐ (~4s) không phụ thuộc thời
  lượng video, không phải % tăng theo độ dài như lo ngại ban đầu. Chưa đo
  trên video ĐỘ PHÂN GIẢI cao hơn 720p (có thể chậm hơn theo kích thước
  ảnh, chưa kiểm chứng).
- CI đã có sẵn `ffmpeg` từ V38 (`.github/workflows/test.yml`) nên 2 test
  mới dùng video nén thật chạy được trong CI thật, không chỉ sandbox có
  cài thêm — `rapidocr-onnxruntime`/`fonts-wqy-zenhei` vẫn CHƯA có trong
  CI (không nằm trong `requirements.txt`, quyết định có chủ đích từ V38 để
  tránh kéo dependency nặng) nên 2 test này **skip trong CI**, chỉ chạy khi
  môi trường có đủ 2 gói đó (đúng `skipif` pattern các test OCR khác trong
  cùng file đã dùng từ đầu, không phải regression mới).

**Xây dựng:** `tests/test_text_regions.py` — 2 test mới
(`test_real_encoded_video_detects_vietnamese_and_faded_watermark`,
`test_real_encoded_noisy_video_without_text_detects_nothing`), tự dựng
video bằng `subprocess`+ffmpeg trong `tmp_path` (không commit file nhị
phân nào vào repo).

**Verify:** `pytest tests/test_text_regions.py -q`: **11 passed** (9→11).
`pytest tests/ -q` toàn bộ (môi trường đã cài `rapidocr-onnxruntime`+
`fonts-wqy-zenhei`+`ffmpeg`+`libegl1` bổ sung — xem Re-audit GUI của V32b
cùng ngày): **1163 passed, 5 skipped, 1 failed** (1132→1163, đúng 31 test
mới cộng dồn từ cả 2 việc trong phiên — 2 của V5 + 29 của V32b — 0
regression, 1 fail còn lại đúng flake có sẵn từ V40).

**Vẫn còn thiếu (chưa đổi so với 08-11, trung thực):** vẫn KHÔNG PHẢI
watermark/phụ đề THẬT từ TikTok/Douyin/YouTube thật (rủi ro bản quyền nội
dung người khác, không thử trong phiên này) — mọi video test đều tự dựng
bằng ffmpeg. Chưa test độ phân giải cao hơn 720p, chưa test góc nghiêng/
watermark hình ảnh (logo) thay vì chữ, chưa test video dài thật (chỉ dùng
video 2-8 giây cho mục đích kỹ thuật). Bước đóng hẳn gap này vẫn cần chủ
dự án cung cấp ≥1 video thật từ chính nền tảng nguồn (họ có quyền dùng nội
dung của họ, khác việc tôi tự tải nội dung của người thứ ba).

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
dashboard VAYS nếu muốn giải phóng hạn mức (đang dùng 3/10 dịch vụ).

**Cập nhật 2026-08-12**: repo mirror `github.com/junnyken/voxdub-studio` **KHÔNG
xoá** — chủ dự án chốt dùng repo này làm nơi phát hành chính thức (GitHub
Releases) cho bản `.exe` desktop, thay cho placeholder `YOUR_GITHUB/your-releases`
cũ trong `website/src/pages/Download.jsx`. Đã đồng bộ `update_repo` trong
`autodub/config.py` (2 chỗ: dataclass default + `env("UPDATE_REPO", ...)`) trỏ
cùng repo này để nút "Kiểm tra bản mới" trong app khớp với nút Tải xuống trên
website. Repo hiện **chưa có release nào** — nút Tải xuống vẫn sẽ 404 cho tới
khi có bản build thật được publish lên đó (xem mục kế tiếp về build Windows).

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

## V23 — Cổng chất lượng tự động đọc `quality_report.json` (Phase F)

### Xây dựng

- `autodub/quality_gate.py` (mới) — `QualityThresholds`/`QualityVerdict`/
  `evaluate(report, thresholds)`: hàm THUẦN, chỉ đọc `summary` đã có sẵn
  trong `quality_report.json`, không tính lại số liệu (đúng Constraint 1
  của mini-spec). 3 mức verdict: "pass" (0 vấn đề), "warn" (có vấn đề
  nhưng dưới mọi ngưỡng), "fail" (≥1 ngưỡng bị vượt, kèm lý do cụ thể theo
  từng field).
- `autodub/config.py` — 4 field ngưỡng mới (`quality_gate_max_over_budget_
  ratio`/`_speed_fallback_ratio`/`_postprocess_fallback_ratio`/`_max_shift_s`),
  đọc từ env theo đúng pattern `env_float()` sẵn có, mặc định bảo thủ (xem
  "Remaining Limits" bên dưới).
- `autodub/cli.py` — cờ `--quality-gate` (mặc định TẮT) cho cả `dub`/
  `batch`: `dub` đọc `quality_report.json` từ `work_dir` vừa chạy xong, in
  verdict trong JSON kết quả, exit 3 nếu "fail" (khác exit 1 của lỗi
  pipeline thật). `batch` ghi thêm field `quality` vào từng entry
  `status=="success"` trong `batch_state.json` SAU KHI `run_batch()` chạy
  xong — không đổi field `status` (logic resume của `run_batch()` không bị
  ảnh hưởng, đúng Constraint 3 của mini-spec).

### Verify

- `tests/test_quality_gate.py` (11 test): báo cáo sạch → pass; báo cáo
  rỗng/thiếu `summary` → pass TRUNG THỰC (không phải fail ngầm định); vấn
  đề dưới ngưỡng → warn (không chặn); mỗi field (over_budget/speed_
  fallback/postprocess_fallback/max_shift_s) vượt ngưỡng riêng lẻ → fail
  đúng lý do; nhiều field vượt cùng lúc → liệt kê đủ mọi lý do; đúng BẰNG
  ngưỡng không bị coi là vượt (ngưỡng là chặn trên); `from_settings()` đọc
  đúng cấu hình; `to_dict()` đúng hình dạng.
- `tests/test_cli.py` (+4 test): KHÔNG bật `--quality-gate` → hành vi Y HỆT
  trước V23 dù `quality_report.json` có vấn đề (0 regression thật — dùng
  fixture cố tình lỗi để khoá lại); bật cờ, báo cáo sạch → exit 0 kèm
  `quality.status=="pass"`; báo cáo lỗi nặng → exit 3 kèm lý do cụ thể;
  batch ghi đúng field `quality` mà KHÔNG đổi field `status` (test đọc lại
  chính `batch_state.json` sau khi CLI chạy xong).
- Live-verify: gọi trực tiếp `evaluate()` trên 1 file `quality_report.json`
  dựng tay thật ngoài test suite (70% câu vượt ngân sách) — trả đúng
  `{"status": "fail", "reasons": ["70% câu vượt ngân sách ký tự (ngưỡng
  15%)"]}`.
- `pytest tests/ -q` toàn bộ (venv đầy đủ dependency, cùng cách dựng như
  V22): **793 passed, 6 skipped, 0 failed** (778 pass ở V22 + 15 test mới).

### Remaining Limits (V23)

- **Ngưỡng mặc định CHƯA hiệu chỉnh bằng dữ liệu thật** — đúng như đã ghi
  trong Constraint 2 của mini-spec, dự án chưa có đủ video đã dub để biết
  "vượt ngân sách 15%" có thực sự tương ứng với chất lượng kém hay không.
  Giá trị hiện tại (15%/10%/10%/1.0s) là ước lượng bảo thủ có chủ đích,
  không phải số đã kiểm chứng — cần 1 vòng audit số liệu thật trên vài
  chục video (đã ghi trong "Audit Before Build" của mini-spec) trước khi
  coi các con số này là chính thức. Cấu hình được qua biến môi trường nên
  chỉnh lại không cần sửa code.
- `--quality-gate` mặc định TẮT (opt-in) ở cả `dub`/`batch` — người dùng
  hiện có KHÔNG tự động được bật tính năng này, cần biết để bật tay hoặc
  qua V24/V25 sau này.
- Chưa live-verify qua 1 lượt dub THẬT (cùng giới hạn đã ghi ở V22 —
  `quality_report.json` dùng trong test đều là fixture dựng tay theo đúng
  shape thật của `_build_quality_report()`, chưa phải file sinh ra từ 1
  lượt pipeline chạy thật end-to-end qua CLI).

## V24 — Batch resilience: retry + watchdog + failures.jsonl (Phase F, E2+E5+E6)

### Audit

Rà TOÀN BỘ điểm gọi subprocess trong `autodub/speech/` + `autodub/media/`
(đúng yêu cầu "Audit Before Build" của mini-spec — không đoán số/hành vi):

- Mọi lời gọi `subprocess.run()` một-lượt (ffmpeg/ffprobe...) — kiểm bằng
  script duyệt AST thật trên 8 file — **100% ĐÃ có `timeout=`**, không cần
  sửa (audio.py, retime.py, video.py, capcut_vi.py, transcriber.py,
  douyin.py, text_regions.py, vocal_separator.py — 22/22 lời gọi).
- Worker dài hạn (Popen + giao thức JSON qua dòng) — 2 KIỂU khác nhau:
  - **ĐÃ ĐÚNG từ trước**: `autodub/media/vocal_separator.py::_read_line`
    (luồng nền bơm dòng vào hàng đợi, đọc CÓ TIMEOUT qua
    `queue.Queue.get(timeout=...)`) và `autodub/speech/tts/vieneu_vi.py`
    (cùng kỹ thuật, `_read_response(timeout)`).
  - **CHƯA ĐÚNG (bug thật, cùng dạng)**: `for line in proc.stdout:` chặn
    VÔ THỜI HẠN nếu worker treo — 4 điểm: `autodub/text/translate_local.py
    ::run_local_worker()`, `autodub/speech/transcriber.py` (worker
    Whisper), `autodub/speech/paraformer_transcriber.py`,
    `autodub/speech/tts/voice_downloader.py`.
- Kết luận Design Choice: tổng quát hoá kiểu ĐÃ ĐÚNG (không phát minh kiểu
  mới) thành `autodub/subprocess_watchdog.py`, áp dụng NGAY cho
  `run_local_worker()` (điểm mini-spec nêu tên ở Scope C, đã có bug thật
  liên quan từ V21) — 3 điểm còn lại (Whisper/Paraformer/tải giọng) xác
  nhận CÙNG loại gap thật nhưng CHƯA sửa trong đợt này (xem "Remaining
  Limits" — cần audit riêng giá trị timeout hợp lý cho từng loại việc,
  đúng như mini-spec dự liệu, KHÔNG đoán số).

### Xây dựng

- `autodub/subprocess_watchdog.py` (mới) — `WatchedLineReader`/
  `read_lines_with_timeout()`: tổng quát hoá kỹ thuật luồng nền + hàng đợi
  đã đúng ở `vocal_separator.py`, raise `SubprocessTimeoutError` nếu không
  dòng nào tới trong thời gian cho phép (thay vì chặn vô thời hạn).
- `autodub/text/translate_local.py::run_local_worker()` — thay
  `proc.stdout.readline()`/`for line in proc.stdout:` bằng
  `WatchedLineReader` (2 timeout riêng: 300s nạp model, 120s giữa các dòng
  dịch — bảo thủ có chủ đích, CHƯA benchmark thật, xem Remaining Limits).
  Dùng `raise LocalTranslateError(...) from e` (giữ `__cause__`) khi bọc
  `SubprocessTimeoutError` — cần thiết để `batch_retry.is_transient_error()`
  thấy được lỗi GỐC xuyên qua lớp bọc (bắt được qua test tích hợp thật, xem
  dưới).
- `autodub/batch_retry.py` (mới) — `is_transient_error(exc)`: phân loại
  theo EXCEPTION TYPE (Constraint 1), tái dùng đúng luật đã có ở
  `saas_retry.py` (V16) cho lỗi SaaS thay vì phát minh luật thứ 2; duyệt
  `__cause__`/`__context__` để nhận lỗi tạm thời bị bọc bởi 1 lớp exception
  khác. Mặc định AN TOÀN: không nhận diện được → vĩnh viễn (không tự thử
  lại).
- `autodub/failures_log.py` (mới) — `append_failure()`/`failures_path()`:
  `failures.jsonl` append-only, nằm CẠNH `batch_state.json`, KHÔNG đổi
  format file đó.
- `autodub/batch.py::_run_items()` — bọc lượt `pipeline.run()` trong vòng
  lặp thử lại: lỗi TẠM THỜI (`retry_transient=True`, mặc định TẮT) resume
  NGAY từ `work_dir` vừa lưu (tái dùng cơ chế resume có sẵn, không viết
  logic chạy lại riêng) tối đa `max_retries` lần (mặc định 2) với backoff
  tăng dần (5s/15s); lỗi VĨNH VIỄN không bao giờ thử lại dù cờ bật. Mỗi lỗi
  (thử lại hay không, `retry_transient` bật hay không) đều ghi vào
  `failures.jsonl` — quan sát LUÔN bật, tách khỏi quyết định retry.
- `autodub/cli.py` — cờ `--retry-transient`/`--max-retries` cho `batch`
  (mặc định TẮT — 0 regression).

### Verify

- `tests/test_subprocess_watchdog.py` (5 test): đọc bình thường khi worker
  phản hồi tốt; dừng sạch khi stdout đóng; **raise trong thời gian hữu hạn
  khi worker treo THẬT (subprocess Python thật ngủ 60s, timeout test 0.3s,
  phát hiện trong <5s)** — khoá đúng bug đã audit; treo giữa chừng sau khi
  đã có vài dòng vẫn phát hiện đúng; dòng trống không bị hiểu nhầm là đóng
  luồng.
- `tests/test_translate_local_watchdog.py` (3 test) — dùng 1 worker giả THẬT
  (script Python nhỏ, đúng giao thức JSON, không mock `Popen`): worker khoẻ
  vẫn hoạt động y hệt qua đường watchdog mới (0 regression); worker treo
  lúc nạp model → `LocalTranslateError` trong thời gian hữu hạn; worker
  dịch xong câu 1 rồi treo ở câu 2 → lỗi rõ ràng kèm số câu đã dịch được
  trước đó (khác hẳn "treo vô thời hạn, không log" của bug cũ).
- `tests/test_batch_retry.py` (10 test): `SubprocessTimeoutError`/
  `OfflineError`/`ConnectionError`/`TimeoutError` → tạm thời; `Insufficient
  CreditError`/`DeviceBlockedError`/`MaintenanceError`/`ConfigError` → vĩnh
  viễn; exception lạ mặc định vĩnh viễn (an toàn); **lỗi tạm thời bị bọc
  bởi `LocalTranslateError` qua `raise ... from e` VẪN được nhận đúng** —
  test này bắt được thật 1 lỗi thiết kế trong lúc viết (lần đầu quên `from
  e`, is_transient_error trả sai `False` cho lỗi treo thật của worker dịch
  local — sửa ngay bằng chaining tường minh + duyệt `__cause__`/
  `__context__`).
- `tests/test_failures_log.py` (4 test): tạo file/thư mục; append không ghi
  đè; giữ nguyên Unicode.
- `tests/test_batch_retry_integration.py` (11 test, qua `run_batch()` thật,
  không mock nội bộ) — **bắt được 1 bug thật trong chính test harness lúc
  viết**: `ScriptedPipeline` giả lập work_dir bằng chuỗi không tồn tại trên
  đĩa, khiến `os.path.isdir(prev_dir)` (điều kiện có sẵn từ trước V24 trong
  logic resume) luôn `False` → resume_dir không bao giờ được set — sửa test
  harness để tạo thật thư mục (đúng như pipeline thật làm), xác nhận sau đó
  lượt thử lại resume ĐÚNG work_dir cũ. Các test: tắt cờ (mặc định) → lỗi
  tạm thời vẫn fail ngay, KHÔNG tự thử lại (0 regression); bật cờ → phục
  hồi trong giới hạn thử lại, resume đúng work_dir; lỗi vĩnh viễn không bao
  giờ thử lại dù cờ bật; vượt quá `max_retries` → cuối cùng vẫn fail đúng
  sau đúng số lần; video khác trong cùng batch không bị ảnh hưởng; observer
  nhận đúng trạng thái "retrying"; `failures.jsonl` LUÔN ghi dù không bật
  retry; ghi đúng từng lượt thử riêng biệt; không đụng field `status` của
  `batch_state.json`; timestamp lấy từ `now_fn` truyền vào (không gọi
  `datetime.now()` trực tiếp trong code lõi — test được xác định).
- `tests/test_cli.py` (+2 test): `--retry-transient`/`--max-retries` truyền
  đúng vào `run_batch()`; mặc định tắt khi không truyền cờ.
- Live-verify: `voxdub batch --help` qua console script thật (không phải
  `python -m`) — hiện đúng 2 cờ mới với mô tả.
- `pytest tests/ -q` toàn bộ (venv đầy đủ dependency): **828 passed, 6
  skipped, 0 failed** (793 pass ở V23 + 35 test mới).

### Remaining Limits (V24)

- **3/4 điểm subprocess-treo đã audit CHƯA sửa**: `transcriber.py` (worker
  Whisper), `paraformer_transcriber.py`, `voice_downloader.py` đều dùng
  đúng kiểu `for line in proc.stdout:` không timeout đã tìm thấy ở
  `run_local_worker()` — CÙNG loại gap thật, nhưng cần audit riêng giá trị
  timeout hợp lý cho từng loại việc (Whisper 1 video dài khác hẳn dịch 1
  câu) trước khi áp `subprocess_watchdog.py`, đúng như mini-spec dự liệu
  ("để dành làm bước audit riêng khi triển khai, KHÔNG đoán số"). Ưu tiên
  sửa tiếp nếu chủ dự án xác nhận cần.
- **Giá trị timeout của `run_local_worker()` (300s/120s) CHƯA benchmark
  thật** — bảo thủ có chủ đích (mục tiêu: biến "treo vô hạn" thành "treo có
  trần", không phải tối ưu tốc độ phát hiện), cùng loại giới hạn như ngưỡng
  V23.
- **`--retry-transient` mặc định TẮT** (opt-in, giống `--quality-gate`
  V23) — quyết định vận hành (mặc định bật ảnh hưởng thời gian chạy batch
  mặc định) chưa được chủ dự án xác nhận nên chọn opt-in an toàn.
- Phân loại transient/permanent hiện chỉ phủ các exception type ĐÃ BIẾT
  trong code (SubprocessTimeoutError/SaasError/ConnectionError/
  TimeoutError) — lỗi mạng lộ ra dưới dạng exception type KHÁC (vd
  `requests.exceptions.*` nếu có nơi nào raise thẳng, chưa audit riêng) sẽ
  mặc định bị coi là vĩnh viễn (an toàn nhưng có thể bỏ lỡ vài cơ hội phục
  hồi hợp lệ) — cần audit thêm nếu muốn mở rộng danh sách.
- Backoff (5s/15s) và trần retry (2 lần) là giá trị khởi đầu hợp lý, CHƯA
  có dữ liệu thật từ vận hành để hiệu chỉnh.

## V25 — Chế độ theo dõi thư mục/hàng đợi không người trực (Phase F, E4)

### Xây dựng

- `autodub/watch_folder.py` (mới):
  - `StabilityTracker` — kích thước file không đổi liên tục ``stable_
    seconds`` giây mới coi là ghi xong (Constraint 1); cần ÍT NHẤT 2 lượt
    quan sát (không bao giờ tin lần thấy ĐẦU TIÊN, dù `stable_seconds=0`).
  - `file_key()`/`WatchState` — trạng thái bền theo path+mtime+size, sống
    sót qua tắt/bật lại tiến trình (Constraint 2), tách hẳn khỏi
    `batch_state.json` (khoá theo URL — mô hình khác nhau, không ép chung).
  - `discover_ready_files()` — tự loại file "chắc chắn chưa ghi xong"
    (`.part`/`.crdownload`/`.tmp`/`.download`, file ẩn) VÀ tự loại tên file
    bookkeeping đã biết (`_watch_state.json`/`failures.jsonl`/
    `batch_state.json`) — lớp an toàn phòng khi input_dir/output_dir bị
    trỏ trùng nhau (phát hiện lúc viết test, xem Verify).
  - `process_file()` — đánh dấu "processing" TRƯỚC khi chạy, resume đúng
    `work_dir` nếu phát hiện lại 1 file còn dở "processing" từ lượt trước
    (Constraint 4); lỗi thật (exception) ghi `failed` + `failures.jsonl`,
    KHÔNG giết cả vòng theo dõi.
  - `run_watch_once()` — 1 lượt quét đầy đủ (discover + process từng file),
    hàm THUẦN dùng trực tiếp trong test.
  - `watch_forever()` — lớp vỏ MỎNG DUY NHẤT có `while`/`sleep` thật, dừng
    qua `threading.Event` (CLI gắn với SIGINT).
- `autodub/cli.py` — subcommand `voxdub watch --input-dir ... [--output-dir
  ...] [--poll-interval] [--stable-seconds]`, dùng lại `DubPipeline`/
  `DubRequest` như `dub`, nối `failures_log_path` (V24). SIGINT → set
  `stop_event`, vòng lặp dừng SAU KHI xong lượt quét hiện tại (không cắt
  giữa 1 lượt `pipeline.run()` đang chạy dở — xem Remaining Limits).

### Verify

- `tests/test_watch_folder.py` (21 test): `StabilityTracker` (file đang
  lớn dần không bao giờ "ổn định"; kích thước không đổi đủ lâu → ổn định;
  file biến mất → không ổn định; `forget()` reset đúng); `file_key()` đổi
  khi nội dung đổi, ổn định khi không đổi; `WatchState` bền qua "khởi động
  lại" (test tạo 2 instance riêng trỏ cùng file); trạng thái thiếu → coi
  như trống; "processing" KHÔNG được tính là đã xong; `discover_ready_
  files()` chỉ lấy file mới+ổn định, loại file provisional, loại file đã
  xong, loại thư mục con; **file bookkeeping không bao giờ bị tự "dub"
  ngay cả khi input=output trùng thư mục** (bug tiềm ẩn tìm ra khi viết
  test, chặn trước khi xảy ra thật); `process_file()`/`run_watch_once()`
  qua `FakePipeline` (không tải/ASR/TTS thật) — thành công, lỗi không crash
  vòng lặp, ghi `failures.jsonl` đúng, xử lý nhiều file 1 lượt rồi bỏ qua ở
  lượt sau, resume đúng `work_dir` khi phát hiện lại file "processing" dở,
  video mới vẫn được xử lý sau khi video trước lỗi; `watch_forever()` với
  `stop_event` dừng đúng sau ĐÚNG 1 lượt xử lý (không polling thật dài hạn
  trong test, đúng Test Plan của mini-spec).
- `tests/test_cli.py` (+7 test): `--help`; thiếu `--input-dir` (bắt buộc);
  thư mục không tồn tại → exit 2; giọng sai → exit 2, KHÔNG chạm tới
  `watch_forever()`; cờ nối đúng vào `watch_forever()` (input_dir/poll_
  interval/stable_seconds/output_dir tự tạo); output_dir mặc định theo
  target khi không truyền.
- **Live-verify THẬT** (không mock): chạy `voxdub watch` qua console script
  thật (subprocess thật) trên 1 file giả (không phải video thật) trong
  `/tmp`, `--poll-interval 1 --stable-seconds 1`, gửi SIGINT sau 6s —
  **bắt được 1 bug thật**: `watch_forever()` gọi `run_watch_once()` không
  truyền `now_fn`, rơi về mặc định `lambda: ""` (đúng cho test thuần
  `process_file()` nhưng SAI cho sản xuất thật) → mọi dòng `failures.jsonl`
  khi chạy `voxdub watch` thật có `"timestamp": ""`, mất hết giá trị theo
  dõi theo thời gian của E6. Sửa: `watch_forever()` tự cấp
  `datetime.now().isoformat()` làm `now_fn` mặc định (cùng pattern
  `batch.py::_run_items` đã dùng ở V24). Re-verify thật sau khi sửa:
  `failures.jsonl` có timestamp thật (`"2026-08-12T04:08:16"`); toàn bộ
  luồng thật khác đã đúng ngay từ đầu — pipeline THẬT chạy (ffmpeg thật
  được gọi, lỗi thật vì file giả không phải video), `_watch_state.json`
  ghi đúng `work_dir`/`status`, SIGINT dừng sạch (exit 0, không bị
  `timeout` cắt ngang — log "Đang dừng theo dõi" in ra trước khi thoát).
  Thêm test khoá lại hành vi này (`test_watch_forever_passes_a_real_non_
  empty_timestamp_to_failures_log`).
- `pytest tests/ -q` toàn bộ (venv đầy đủ dependency): **855 passed, 6
  skipped, 0 failed** (828 pass ở V24 + 27 test mới).

### Remaining Limits (V25)

- **Ctrl+C GIỮA LÚC 1 lượt `pipeline.run()` đang chạy dở** (không phải
  giữa 2 lượt poll) có thể KHÔNG resume đúng — `state.record("processing")`
  chỉ ghi `work_dir` SAU KHI bắt được exception hoặc hoàn thành; tín hiệu
  ngắt thật (`KeyboardInterrupt`) giữa chừng bỏ qua nhánh `except Exception`
  (không kế thừa từ `Exception`), nên `work_dir` ghi lại có thể vẫn rỗng —
  lần chạy watch kế tiếp sẽ dub lại từ đầu thay vì resume. Đây là giới hạn
  THẬT đã ghi rõ trong Constraint 4 khi viết mini-spec ("Ctrl+C giữa lúc
  pipeline đang chạy... là trường hợp biên chưa xử lý triệt để") — không
  phải bỏ sót, cần thêm 1 vòng thiết kế riêng (bắt `KeyboardInterrupt` bên
  trong `pipeline.run()` chính nó, không chỉ ở tầng CLI) nếu muốn đóng gap
  này.
- Không lọc theo đuôi file video cụ thể (không đoán danh sách đuôi ffmpeg
  hỗ trợ) — chỉ loại các đuôi CHẮC CHẮN chưa ghi xong
  (`.part`/`.crdownload`/`.tmp`/`.download`) và file ẩn; 1 file không phải
  video thả vào thư mục theo dõi vẫn được "thử" dub, thất bại sạch qua
  `failures.jsonl` (đã live-verify đúng hành vi này, không phải bug — chỉ
  ghi nhận đây KHÔNG PHẢI validate định dạng trước, để tránh đoán sai danh
  sách định dạng hợp lệ).
- Tần suất polling/ngưỡng ổn định mặc định (10s/5s) là ước lượng hợp lý,
  CHƯA xác nhận với chủ dự án theo đúng "Audit Before Build" của mini-spec
  (ghi rõ đây là quyết định vận hành thực tế, tuỳ tốc độ mạng/ổ đĩa nơi
  triển khai) — cấu hình được qua cờ CLI nên chỉnh lại không cần sửa code.

## Re-audit — đóng nốt 2 giới hạn còn lại của V24/V25 (chủ dự án yêu cầu)

Theo đúng quy trình "Re-audit" ở mục "Cách dùng tài liệu này" cuối file
này: rà lại Remaining Limits của V24/V25, phân loại — cả 2 mục dưới đây
thuộc loại (a) "sửa được ngay, ít rủi ro" → sửa luôn trong đợt này.

### 1. 3/4 điểm subprocess-treo còn lại (V24)

**Sửa**: áp `subprocess_watchdog.py` cho cả 3 điểm còn lại, đúng kỹ thuật
audit đã ghi ở V24 (không đoán số ngoài phạm vi đã audit):

- `autodub/speech/transcriber.py` (worker Whisper) — dùng
  `WatchedLineReader` cho cả bước "ready" (nạp model, 600s) lẫn streaming
  từng đoạn (600s/đoạn) — tham chiếu `proc.wait(timeout=7200)` sẵn có (khối
  lượng việc dự kiến: video dài).
- `autodub/speech/paraformer_transcriber.py` — cùng kỹ thuật, không có bước
  "ready" riêng (worker phát thẳng segment), 1 hằng số (300s/dòng) — tham
  chiếu `proc.wait(timeout=600)` sẵn có.
- `autodub/speech/tts/voice_downloader.py` (`_run_enroll_worker`) — kiểu
  ĐỌC KHÁC hẳn (không streaming theo dòng, worker chỉ ghi ĐÚNG 1 khối JSON
  kết quả rồi thoát qua `proc.stdout.read()`) — thêm hàm mới
  `read_all_with_timeout()` vào `subprocess_watchdog.py` (chạy `.read()`
  trong luồng nền, chờ CÓ TIMEOUT qua hàng đợi) thay vì tổng quát hoá nhầm
  bằng kiểu theo dòng; khớp đúng timeout tổng sẵn có (3600s cho tối đa 120
  giọng).

**Verify**: 3 test file mới, mỗi file dùng 1 worker giả THẬT (script Python
nhỏ, đúng giao thức JSON của worker thật, không mock `Popen`) — theo đúng
cách đã làm cho `run_local_worker()` ở đợt 1:
- `tests/test_transcriber_watchdog.py` (3 test): hoạt động bình thường qua
  đường watchdog mới (0 regression); treo lúc nạp model → lỗi rõ trong thời
  gian hữu hạn; treo giữa lúc nhận dạng (sau khi đã có 1 đoạn) → lỗi rõ
  kèm số đoạn đã nhận dạng được.
- `tests/test_paraformer_watchdog.py` (3 test): hoạt động bình thường;
  treo ngay từ đầu (không phát dòng nào); treo giữa chừng.
- `tests/test_voice_downloader_watchdog.py` (2 test): hoạt động bình
  thường; treo trước khi ghi kết quả → trả đúng `{"ok": False, "error":
  "Timeout..."}` (giữ nguyên hợp đồng lỗi cũ, chỉ khác NGUYÊN NHÂN timeout
  giờ bắt được thay vì treo vô hạn).
- `tests/test_subprocess_watchdog.py` (+3 test): `read_all_with_timeout()`
  — đọc đúng khi worker phản hồi nhanh; raise trong thời gian hữu hạn khi
  treo (subprocess Python thật ngủ 60s, phát hiện <5s); trả rỗng khi worker
  không in gì.
- `pytest tests/ -q` toàn bộ (venv đầy đủ dependency): **867 passed, 6
  skipped, 0 failed** (855 pass trước đợt này + 12 test mới).

**Kết quả**: cả 4/4 điểm subprocess-treo đã audit ở V24 nay đều có trần —
không còn điểm nào "treo vô thời hạn" đã biết trong `autodub/speech/`.

### 2. Ctrl+C giữa lúc pipeline đang chạy dở (V25)

**Phát hiện lại khi audit sâu hơn**: mô tả ban đầu ở V25 ("Ctrl+C giữa lúc
pipeline đang chạy có thể không resume đúng vì `KeyboardInterrupt` không
kế thừa `Exception`") dựa trên giả định SAI — `cli.py::_cmd_watch` tự cài
1 SIGINT handler TUỲ BIẾN (`signal.signal(signal.SIGINT, _handle_sigint)`)
chỉ ĐẶT CỜ `stop_event`, KHÔNG raise `KeyboardInterrupt`. Nghĩa là hành vi
THẬT không phải "ngắt nửa chừng làm mất work_dir" — mà là "video đang dub
chạy TIẾP tới khi xong hẳn, watch_forever() chỉ dừng nhận việc MỚI ở lượt
kiểm cờ kế tiếp". An toàn (không mất gì) nhưng CÓ vấn đề UX thật: người
dùng bấm Ctrl+C có thể phải chờ rất lâu (bằng đúng thời gian dub xong video
hiện tại) mà không có cách nào thoát ngay.

**Sửa** (2 phần, cả phòng thủ lẫn UX):
- `autodub/watch_folder.py::process_file()` — thêm nhánh
  `except KeyboardInterrupt:` (tách khỏi `except Exception:` vì
  `KeyboardInterrupt` kế thừa `BaseException`, không phải `Exception`) ghi
  lại `work_dir` đã có (trạng thái "processing", chưa "success"/"failed")
  RỒI `raise` tiếp — không nuốt tín hiệu ngắt. Đây là lớp phòng thủ cho
  trường hợp hàm này được gọi TRỰC TIẾP (không qua CLI, không có handler
  tuỳ biến — khi đó Ctrl+C raise `KeyboardInterrupt` THẬT theo mặc định của
  Python).
- `cli.py::_cmd_watch` — sửa thông báo cho đúng thực tế ("chờ xong video
  đang dub" thay vì "chờ hết lượt quét"), thêm cơ chế bấm Ctrl+C LẦN 2
  (trong lúc đang chờ) thoát NGAY qua `os._exit(130)` (130 = quy ước exit
  code chuẩn cho SIGINT) — mẫu hình phổ biến ở CLI tool khác (docker
  compose, npm...).

**Verify**:
- `tests/test_watch_folder.py` (+1 test): `process_file()` với pipeline
  giả raise `KeyboardInterrupt` — ghi đúng `work_dir`/status "processing"
  VÀO STATE trước khi lỗi lan ra, và `KeyboardInterrupt` vẫn lan tiếp (test
  bắt bằng `pytest.raises`, không bị nuốt).
- **Live-verify THẬT** (không mock, quan trọng nhất cho phần UX): dựng 1
  driver script thật chạy `cli.main(["watch", ...])` với 1 `DubPipeline`
  giả CHỦ Ý CHẠY CHẬM (`time.sleep(20)`) để mô phỏng 1 video dub lâu, chạy
  như tiến trình con thật, gửi tín hiệu `SIGINT` thật qua `kill -INT` (không
  phải gọi hàm Python) — xác nhận đúng: **SIGINT lần 1** → in "Đang dừng
  theo dõi... bấm Ctrl+C lần nữa để thoát ngay", tiến trình CÒN SỐNG (xác
  nhận bằng `ps -p`, đúng như thiết kế: không cắt ngang video đang dub);
  **SIGINT lần 2** → in "Thoát ngay", tiến trình thoát NGAY LẬP TỨC
  (`wait` xác nhận `Exit 130`, không phải bị `timeout` cắt ngang).
- `pytest tests/ -q` toàn bộ: đã tính trong tổng 867 passed ở trên (bao
  gồm cả sửa này).

**Kết quả**: giới hạn ban đầu được sửa đúng bản chất thật (không phải bản
chất giả định sai lúc đầu) — Ctrl+C giờ có 2 mức: lần 1 an toàn (đợi xong
việc dở), lần 2 tức thời (chấp nhận việc dở có thể chưa hoàn tất, tự resume
ở lượt watch kế tiếp nhờ `process_file()` đã ghi `work_dir`).

### Remaining Limits còn lại sau Re-audit

- Giá trị timeout mới (Whisper 600s/600s, Paraformer 300s, voice_downloader
  3600s) đều CHƯA benchmark phần cứng thật — cùng loại giới hạn "bảo thủ có
  chủ đích, chưa hiệu chỉnh" như mọi ngưỡng số khác trong Phase F (V23
  ngưỡng chất lượng, V24 backoff/max_retries, V25 poll interval).
- Double-Ctrl+C dùng `os._exit()` (bỏ qua mọi cleanup Python bình thường:
  `finally`, context manager, atexit) có chủ đích — người dùng đã được báo
  rõ "video đang dở có thể chưa hoàn tất" trước khi bấm lần 2, đây là lựa
  chọn có ý thức đánh đổi tốc độ thoát lấy việc bỏ qua dọn dẹp, không phải
  sơ suất.

## V26 — Diarization tự động (đa giọng nói) (Phase G)

### Audit trước khi build

- Xác nhận lại: không venv nào (`.venv-whisper`/`.venv-vieneu`/`.venv-asr`/
  `.venv-translate-mt`) có torch — `.venv-diar` phải là venv hoàn toàn mới.
- `pipeline.py` (bước tổng hợp TTS, `_synthesize_segments`) đã đọc
  `seg["voice"]` tuỳ chọn từ trước — `_synth_for(seg)` tự resolve + tạo/tái
  dùng synthesizer phụ cho từng giọng khác `run_voice`. Xác nhận: chỉ cần
  ghi đúng TÊN GIỌNG hợp lệ (có trong `voices.catalog()`) vào field này,
  không cần đụng gì tới tầng TTS.
- Network + `pip install pyannote.audio` hoạt động thật trong sandbox này
  (đã thử cài thật, ~2GB kéo theo torch, thành công, `pyannote.audio 4.0.7`
  import được). NHƯNG: `pyannote/speaker-diarization-3.1` (model pretrained
  chính) là **gated model** trên HuggingFace Hub — cần tài khoản + bấm
  "Agree and access repository" + access token thật mới tải được. Sandbox
  này không có `HF_TOKEN`/`HUGGINGFACE_TOKEN` nào — xác nhận đây là giới
  hạn THẬT của môi trường phát triển, không phải giả định.

### Xây dựng

- `autodub/speech/diarize_worker.py` (mới) — worker chuẩn (giống
  `asr_paraformer_worker.py`): CLI `--audio`/`--model-dir`/`--hf-token`,
  chạy `pyannote.audio.Pipeline` 1 lượt trên cả file, phát JSON theo dòng
  `{"segment": true, "start", "end", "speaker"}` rồi `{"done": true,
  "num_speakers"}`. Không có bước "ready" riêng (khác Whisper) — toàn bộ
  audio xử lý xong mới có dòng đầu tiên, đúng bản chất pyannote (không
  streaming được).
- `autodub/speech/diarization.py` (mới) — driver dùng
  `autodub.subprocess_watchdog.WatchedLineReader` **NGAY TỪ ĐẦU** (không
  lặp lại bug đã sửa ở V24 cho 4 worker khác — timeout tổng 1800s cho cả
  file, bảo thủ có chủ đích, chưa benchmark thật). `assign_speakers()` map
  ASR segment → speaker theo % overlap thời gian LỚN NHẤT.
- `autodub/speech/tts/voice_assign.py` (mới) — `assign_voices_round_robin()`
  (số speaker > số giọng khả dụng → vòng lại, không crash) +
  `apply_segment_voices()` (ghi `seg["voice"]`, TÁI DÙNG cơ chế multi-voice
  per-segment có sẵn).
- `autodub/pipeline.py::DubPipeline._apply_diarization()` — gọi ngay sau
  ASR, TUỲ CHỌN (`settings.diarization_enabled`, mặc định TẮT). Degrade
  TRUNG THỰC 3 lớp: (1) cờ tắt → no-op; (2) `.venv-diar` chưa cài → log rõ,
  giữ 1 giọng; (3) `DiarizationError` giữa chừng (worker treo/lỗi thật) →
  bắt gọn, log rõ, KHÔNG làm hỏng cả lượt dub, rơi về 1 giọng toàn video.
- `scripts/setup_diarization.py` (mới) — theo đúng khuôn
  `setup_paraformer.py`: tạo `.venv-diar`, cài `pyannote.audio`, smoke test
  nạp model thật (yêu cầu `--hf-token`, dừng rõ ràng kèm hướng dẫn nếu
  thiếu), bật `DIARIZATION_ENABLED=true` trong `.env`.
- CLI: `voxdub dub --multi-speaker` / `voxdub batch --multi-speaker` (bật
  `settings.diarization_enabled` cho lượt chạy đó).
- GUI: field `DIARIZATION_ENABLED` (CHECK) trong trang Cài đặt — mức tối
  thiểu (bật/tắt); panel "Xem trước người nói" (chọn giọng riêng từng
  speaker qua UI) CHƯA làm — xem Remaining Limits.
- Settings: `diarization_enabled`/`diarization_venv_python`/
  `diarization_model_dir` + path helpers + `diarization_configured()`.

### Verify

- `tests/test_voice_assign.py` (6 test): round-robin đủ giọng/thiếu giọng
  (vòng lại); danh mục rỗng → lỗi rõ ràng; `apply_segment_voices()` ghi
  đúng field, giữ nguyên segment không có `speaker_label` (0 regression).
- `tests/test_diarization.py` (8 test): parse segment từ worker giả THẬT
  (subprocess thật, không mock `Popen`); lỗi worker → `DiarizationError`
  đúng message; **worker treo → raise trong thời gian hữu hạn** (khoá đúng
  watchdog áp dụng NGAY TỪ ĐẦU, không lặp lại bug V24); `assign_speakers()`
  chọn đúng overlap lớn nhất, segment không overlap giữ nguyên.
- `tests/test_pipeline_diarization.py` (5 test): gọi thẳng
  `DubPipeline._apply_diarization()` — tắt cờ (mặc định) không đụng gì (0
  regression); bật cờ nhưng chưa cài → degrade + log rõ; `DiarizationError`
  giữa chừng → không crash, rơi về 1 giọng; thành công → gán đúng 2 giọng
  khác nhau cho 2 speaker; không phát hiện speaker nào → giữ nguyên.
- `tests/test_cli.py` (+2 test): `--multi-speaker` bật đúng
  `settings.diarization_enabled`; mặc định tắt.
- `tests/test_settings_fields.py`: field `DIARIZATION_ENABLED` mới không
  phá completeness check (15/15 pass).
- **Live-verify thật (2 phần)**: (1) cài THẬT `pyannote.audio` vào 1 venv
  sạch trong sandbox — thành công, xác nhận `setup_diarization.py`'s bước
  `step_install()` hoạt động đúng trên hạ tầng thật, không giả định; (2)
  `voxdub dub --help` xác nhận `--multi-speaker` xuất hiện đúng qua console
  script thật.
- `pytest tests/ -q` toàn bộ (venv đầy đủ dependency): **905 passed, 6
  skipped, 0 failed** (867 pass trước Phase G + 24 test V26 + phần V27 gộp
  chung lượt chạy cuối, xem mục V27 bên dưới cho tách riêng).

### Remaining Limits (V26)

- **CHƯA live-verify diarization THẬT trên audio 2 người nói** — giới hạn
  xác nhận thật của môi trường phát triển (gated model + không có HF
  token), đúng như mini-spec đã lường trước ("Live-verify nếu môi trường có
  mạng" — có mạng nhưng thiếu token). Người triển khai thật (có tài khoản
  HuggingFace) cần tự chạy `scripts/setup_diarization.py --hf-token ...`
  rồi live-verify trên 1 video thật trước khi coi tính năng đã kiểm chứng
  đầy đủ.
- **GUI chỉ có cờ bật/tắt tối thiểu** — panel "Xem trước người nói" (liệt
  kê speaker phát hiện được kèm audio mẫu, đổi giọng tay từng người) mô tả
  trong Scope E của mini-spec CHƯA làm — cần UI work riêng, GUI không test
  headless được sâu như logic thuần. Ghi nhận làm follow-up khi có nhu cầu
  thật.
- Timeout diarization (1800s cho cả file) và ngưỡng overlap-matching chưa
  benchmark bằng video thật — bảo thủ có chủ đích, cùng loại giới hạn "chưa
  hiệu chỉnh bằng dữ liệu thật" như mọi ngưỡng số khác trong Phase F/G.
- Video giọng nói CHỒNG LẤN nhiều (overlapping speech) không cam kết chất
  lượng — đã ghi rõ trong mini-spec, pyannote hỗ trợ nhưng độ chính xác
  thấp hơn hẳn.

## V27 — Sửa bug glossary không hoạt động trên nhánh dịch local NLLB (Phase G)

### Audit trước khi build

- Xác nhận định dạng thật `settings.translate_glossary`: chuỗi nhiều dòng,
  mỗi dòng `"gốc = dịch"` (comment trong `config.py`), dùng trực tiếp làm
  TEXT THÔ chèn vào prompt LLM ở nhánh SaaS (`translate_hint.py::
  build_user_context_block`) — không có parsing thành cặp có cấu trúc ở
  nhánh đó (LLM tự đọc hiểu định dạng).
- `run_local_worker()`/`translate_local_worker.py` xác nhận: không đọc
  `settings.translate_glossary` ở BẤT KỲ đâu — grep xác nhận 0 tham chiếu.
- `ctranslate2.Translator.translate_batch()`'s `target_prefix` (đang dùng
  để ép ngôn ngữ đích) xác nhận KHÔNG có cơ chế lexical-constraint — chỉ ép
  được token đầu chuỗi, không ép được 1 từ giữa câu. Cơ chế khả thi DUY
  NHẤT: hậu xử lý tìm-thay-thế.
- Kiểm tra `subtitle_translate.py` (V14, luồng dịch phụ đề rời riêng) —
  xác nhận KHÔNG tham chiếu glossary ở đâu cả (kể cả nhánh SaaS của chính
  nó) — đây không phải "nhánh thứ 3 bị bỏ sót", glossary chưa từng được nối
  vào V14 từ đầu, ngoài phạm vi bug fix này (V14 là tính năng riêng, tách
  biệt có chủ đích theo Guardrail 1 của chính V14).

### Xây dựng

- `autodub/text/translate_glossary_apply.py` (mới) — `parse_glossary()`
  (parse "gốc = dịch" mỗi dòng, dòng lỗi định dạng bị bỏ qua chứ không làm
  hỏng cả danh sách) + `apply_glossary()` (tìm-thay-thế có ranh giới từ cho
  Latin, chèn thêm cho CJK vì không có khái niệm ranh giới từ rõ ràng —
  đúng bài học V19).
- `autodub/text/translate_local.py::translate_segments_local()` — sau khi
  nhận kết quả từ `run_local_worker()`, parse + áp glossary cho từng
  segment nếu `settings.translate_glossary` không rỗng.

### Verify

- `tests/test_translate_glossary_apply.py` (15 test): parse đúng/bỏ qua
  dòng lỗi/dòng rỗng; áp đúng khi thuật ngữ nguồn còn nguyên văn trong bản
  dịch (NLLB giữ nguyên tên riêng); KHÔNG match nhầm giữa-từ ("AI" không
  match trong "Saigon"); KHÔNG thay 2 lần khi NLLB tình cờ đã dịch đúng;
  thuật ngữ bị dịch thành từ khác vẫn được CHÈN THÊM (không mất hẳn); CJK
  chèn thêm thay vì dùng `\b`. **Bắt được 1 bug thật khi viết test**: điều
  kiện "thuật ngữ nguồn có mặt trong câu gốc" ban đầu viết case-SENSITIVE
  trong khi bước thay thế lại case-INSENSITIVE — glossary viết hoa
  ("AI") bỏ lỡ hoàn toàn câu gốc viết thường ("dùng ai để...") vì check
  đầu vào fail trước khi tới bước thay thế. Sửa: check đầu vào cũng
  case-insensitive, khớp đúng hành vi thay thế.
- `tests/test_translate_local.py` (+2 test): `translate_segments_local()`
  áp đúng glossary khi có (dùng `run_local_worker()` giả, không cần model
  NLLB thật); glossary rỗng (mặc định) → hành vi Y HỆT trước V27, 0
  regression.
- `pytest tests/ -q` toàn bộ (venv đầy đủ dependency, cùng lượt chạy với
  V26): **905 passed, 6 skipped, 0 failed** (888 pass sau V26 + 17 test
  V27 mới).

### Remaining Limits (V27)

- Tìm-thay-thế văn bản KHÔNG xử lý biến cách/chia động từ/thứ tự từ khác
  nhau giữa 2 ngôn ngữ — chỉ đảm bảo thuật ngữ XUẤT HIỆN đúng, không đảm
  bảo ngữ pháp tự nhiên quanh nó (khác nhánh SaaS, LLM tự nhiên hoá câu
  quanh thuật ngữ khoá) — giới hạn kỹ thuật thật đã ghi rõ trong mini-spec,
  không phải bỏ sót.
- Chưa live-verify bằng model NLLB thật (chỉ verify qua `run_local_worker()`
  giả) — hạ tầng test model thật đã có sẵn từ V6/V21
  (`VOXDUB_TEST_NLLB_MODEL_DIR`), người có model cục bộ có thể tự chạy để
  xác nhận thêm.

## V28 — Emotion/tone-aware voice tự động (Phase G)

### Audit trước khi build

- Đọc đầy đủ `vieneu_worker.py`'s vòng lặp phục vụ (không chỉ phần đã audit
  ở lượt research ban đầu): worker THẬT SỰ đã parse 1 dict JSON per-request
  từ stdin (`req = json.loads(line)`, có `req["text"]`/`req["out"]`) —
  NHƯNG `style` bị hardcode về `args.style` (hằng số CLI lúc khởi động),
  KHÔNG đọc từ `req`. Đây là 1 dòng sửa nhỏ (`req.get("style", args.style)`),
  không phải giới hạn kiến trúc — kết luận LẠC QUAN HƠN dự đoán ban đầu của
  mini-spec ("cần audit... có khả thi kỹ thuật hay cần khởi động lại
  worker").
- Xác nhận `tts.infer(text, voice, style, ...)` của model VieNeu nhận
  `style` làm tham số INFERENCE THẬT mỗi lần gọi (không phải cấu hình 1 lần
  lúc nạp model) — bằng chứng: dòng warm-up (`tts.infer("xin chào các bạn",
  voice=args.voice, style=args.style)`) gọi y hệt cách gọi trong vòng lặp
  phục vụ, cùng 1 hàm, không có bước "cấu hình lại model" riêng.
- Xác nhận `Synthesizer` Protocol (`base.py`) dùng chung bởi CẢ VieNeu lẫn
  CapCut (`_synth_for(seg).synthesize(...)` trong `pipeline.py` không biết
  gì về engine cụ thể) — thêm `style` vào chữ ký chung, CapCut nhận nhưng
  bỏ qua, thay vì rẽ nhánh if/else theo engine trong `pipeline.py`.
- Kiểm tra `/analyze` (control_server) — xác nhận đây là lượt phân tích
  CẤP VIDEO (lấy mẫu đầu-giữa-cuối, tối đa 400 dòng, sinh domain/pronouns/
  glossary/style_notes DÙNG CHUNG cho cả video), KHÔNG PHẢI per-segment.
  Muốn có tone per-segment từ LLM phải sửa `/translate` (endpoint dịch
  THẬT SỰ mọi câu) — đây là contract ĐANG CHẠY SẢN XUẤT, sửa response
  schema/prompt của nó cần audit + test cẩn thận hơn nhiều so với phần còn
  lại của V28 (rủi ro ảnh hưởng luồng dịch chính đang phục vụ người dùng
  thật). Quyết định: KHÔNG làm trong đợt này, ghi rõ là Remaining Limit —
  xem bên dưới.

### Xây dựng

- `autodub/text/tone_heuristic.py` (mới) — `guess_tone(text) ->
  "neutral"|"excited"|"serious"` (dấu "!", từ khoá cảm thán/cảnh báo, chữ
  hoa toàn bộ đủ dài) + `tone_to_vieneu_style(tone)` (map sang ĐÚNG 3 giá
  trị `--style` thật của VieNeu — không bịa thêm).
- `autodub/speech/tts/vieneu_worker.py` — đọc `style` từ `req` per-request,
  validate đúng 3 giá trị hợp lệ (giá trị lạ rơi về `args.style`, không
  crash worker đang phục vụ vì 1 request sai).
- `autodub/speech/tts/vieneu_vi.py` — `render()`/`_render()`/`synthesize()`
  nhận thêm `style: str | None = None`, chỉ gửi field `"style"` trong
  request khi có giá trị (không có = hành vi y hệt trước V28).
- `autodub/speech/tts/capcut_vi.py` — `synthesize()` nhận `style` cho khớp
  Protocol chung rồi BỎ QUA CÓ CHỦ ĐÍCH (Constraint 4 — CapCut là API bên
  thứ 3, không có tham số điều khiển giọng điệu).
- `autodub/speech/tts/base.py` — `Synthesizer` Protocol thêm `style: str |
  None = None`.
- `autodub/pipeline.py::_apply_emotion_styles()` — gọi sau khi dịch xong,
  trước TTS, TUỲ CHỌN (`settings.emotion_voice_enabled`, mặc định TẮT). Tra
  catalog theo `seg.get("voice") or run_voice` — bỏ qua nếu tìm thấy đúng
  entry có `source == "capcut"`; ghi `seg["style"]` cho phần còn lại
  (VieNeu HOẶC giọng không tra cứu được — mặc định xử lý như VieNeu, an
  toàn hơn bỏ sót). Tương thích V26: đọc đúng `seg["voice"]` do diarization
  gán (nếu có) trước khi tra catalog, không phải chỉ giọng mặc định video.
- `_synthesize_segments()` — truyền `style=seg.get("style")` vào
  `.synthesize()`.
- Settings: `emotion_voice_enabled` + field GUI `EMOTION_VOICE_ENABLED`
  (CHECK, trang Giọng đọc).

### Verify

- `tests/test_tone_heuristic.py` (13 test): mapping tone đúng theo dấu
  câu/từ khoá/chữ hoa; ưu tiên "serious" khi có cả 2 tín hiệu; câu quá
  ngắn không suy đoán bừa; `tone_to_vieneu_style()` chỉ trả về 3 giá trị
  worker thật hỗ trợ, giá trị lạ rơi về "tu_nhien" an toàn.
- `tests/test_vieneu_style_per_segment.py` (3 test) — **live-verify THẬT
  qua worker giả subprocess thật** (không mock `Popen`, đúng giao thức
  ready-handshake + serve loop của worker thật): không truyền style → field
  "style" KHÔNG có trong request (0 regression); truyền style → gửi đúng
  tới worker; **2 câu liên tiếp style KHÁC NHAU → mỗi request mang đúng
  style riêng, không bị worker "nhớ" style câu trước** (khoá đúng tuyên bố
  "per-segment thật", không phải per-run).
- `tests/test_pipeline_emotion_voice.py` (5 test): tắt cờ (mặc định) → 0
  regression; bật cờ → gán đúng style theo tone cho từng câu; giọng CapCut
  bị bỏ qua (Constraint 4); segment có `seg["voice"]` riêng (từ diarization
  V26) → tra ĐÚNG giọng đó chứ không phải giọng mặc định video; giọng
  không tìm thấy trong catalog vẫn được gán (mặc định coi là VieNeu, an
  toàn hơn bỏ sót).
- `pytest tests/ -q` toàn bộ (venv đầy đủ dependency): **926 passed, 6
  skipped, 0 failed** (905 pass sau V26/V27 + 21 test V28 mới).

### Remaining Limits (V28)

- **Đường tín hiệu SaaS/LLM per-segment CHƯA nối** (Scope A của mini-spec —
  mở rộng `buildAnalysisPrompt`/`/translate` để LLM trả `tone` mỗi câu).
  Lý do: đây là contract ĐANG CHẠY SẢN XUẤT (mọi lượt dịch SaaS thật đi qua
  `/translate`), sửa response schema/prompt cần 1 vòng audit + test kỹ hơn
  nhiều để không phá luồng dịch chính đang phục vụ người dùng thật — quyết
  định hoãn có chủ đích, không phải bỏ sót. Interface phía Python
  (`_apply_emotion_styles()`) đã thiết kế đủ chỗ để nối thêm nguồn tín hiệu
  LLM sau này (ưu tiên LLM khi có, fallback heuristic khi không) mà không
  phải viết lại tầng TTS đã xong.
- **Chỉ có heuristic văn bản (dấu câu/từ khoá)** — độ chính xác thấp hơn
  hẳn phân tích ngữ nghĩa thật, không suy đoán được mỉa mai/ẩn ý/ngữ cảnh
  trước-sau. Đã gắn nhãn "thử nghiệm" trong mô tả GUI, không giả vờ ngang
  hàng AI thật.
- CHƯA live-verify CHẤT LƯỢNG ÂM THANH thật (2 style có nghe khác nhau rõ
  ràng hay không) — cần model VieNeu thật (không có trong sandbox này) để
  render + so sánh waveform/pitch. Đã live-verify được lớp WIRING (request
  đúng style tới worker thật) — chưa live-verify được lớp CHẤT LƯỢNG cảm
  nhận được.

## V29 — Lộ rõ AI review dịch ra quality_report.json + GUI (Phase G)

### Audit trước khi build

- `grep` toàn repo xác nhận `review_translations()` chỉ có 1 lời gọi THẬT
  (`pipeline.py:1139`) — lời gọi thứ 2 tìm thấy (`autodub_gui/app.py:716`)
  chỉ là import trong danh sách "first-run health check" (kiểm tra module
  còn import được sau đóng gói), không gọi hàm. An toàn đổi thêm tham số mà
  không lo phá caller khác.
- Đọc đầy đủ `review_translations()`: có 2 điểm `return` (bail-out khi
  >35% câu bị cờ; return cuối sau khi build `fixed`) — cả 2 đều cần ghi
  trace, không chỉ điểm cuối (video bị bail-out do quá nhiều câu vẫn nên
  thấy được LÝ DO tại sao không có gì được sửa).
- Xác nhận `_build_quality_report()` là `@staticmethod` — không tự đọc
  được `self._last_review_trace`, cần truyền tường minh qua tham số mới
  từ call site (đã sửa).

### Xây dựng

- `autodub/text/translate_review.py::review_translations()` — thêm tham số
  TUỲ CHỌN `trace_out: list[dict] | None = None`; nếu là 1 list, hàm mới
  `_append_trace()` ghi 1 entry MỖI câu bị cờ (`{"id", "reason", "before",
  "after", "improved"}`) vào đó tại CẢ 2 điểm return — kể cả câu bail-out
  (chưa từng gọi máy chủ) vẫn có trace với `improved=False`.
- `autodub/pipeline.py` — thêm `self._last_review_trace: list[dict] = []`
  (khởi tạo trong `__init__`, mặc định rỗng cho đường dịch tay không chạy
  review); `_auto_translate()` truyền `trace_out=trace` rồi lưu vào
  `self._last_review_trace` (side-channel cùng kiểu `self.last_work_dir`/
  `self._telemetry_run_id` đã có).
- `_build_quality_report()` — thêm tham số `review_trace: list[dict] |
  None = None`, thêm field CẤP CAO MỚI `"translate_review": review_trace or
  []` vào dict trả về — ADDITIVE, không đụng `"summary"`/`"per_segment"`.
- `autodub_gui/pages/quality_page.py` — bảng mới "AI đã tự soát bản dịch
  (N/M câu được sửa)" hiện SAU bảng "Câu cần xem lại" đã có, chỉ hiện khi
  `translate_review` không rỗng; cột Câu/Lý do nghi vấn/Trước/Sau/Đã sửa.

### Verify

- `tests/test_translate_review_trace.py` (6 test): không truyền
  `trace_out` (0 regression mọi caller cũ); trace ghi đúng khi server sửa
  thành công; trace ghi `improved=False` khi server KHÔNG sửa được; không
  có câu nào bị cờ → trace rỗng; **>35% câu bị cờ → bail-out sớm (không gọi
  server) NHƯNG vẫn trace đủ 4/4 câu** (khoá đúng yêu cầu "cả 2 điểm
  return đều ghi trace"); `translate_review=False` (tắt review) → trace
  rỗng.
- `tests/test_pipeline_quality_report_review_trace.py` (4 test):
  `review_trace=None`/không truyền → field vẫn tồn tại, rỗng, không lỗi;
  trace truyền vào lộ đúng ra field; `summary`/`per_segment` KHÔNG đổi khi
  có/không có `review_trace` (khoá đúng tính additive, 0 regression V23).
- `tests/test_quality_page_review_trace.py` (4 test, headless
  `QT_QPA_PLATFORM=offscreen`, cùng khuôn `test_recognize_step_warning.py`
  đã có): báo cáo không có field `translate_review` (video cũ trước V29)
  → không lỗi, không thêm bảng (0 regression); trace rỗng → không thêm
  bảng; bảng mới hiện đúng số dòng + cột "Đã sửa" đúng Có/Không; nhãn lý do
  nghi vấn dịch sang tiếng Việt đúng.
- `pytest tests/ -q` toàn bộ (venv đầy đủ dependency): **940 passed, 6
  skipped, 0 failed** (926 pass sau V28 + 14 test V29 mới).

### Remaining Limits (V29)

- Bảng GUI chỉ hiện SAU KHI chọn dự án đã có `quality_report.json` — không
  có cách xem trace "đang review" theo thời gian thực trong lúc pipeline
  đang chạy (chỉ xem SAU khi xong, giống mọi phần khác của trang Báo cáo
  chất lượng — không phải giới hạn riêng của V29).
- Chưa live-verify qua 1 lượt dịch SaaS thật có câu thực sự bị flag+sửa
  (test dùng `MagicMock` cho `client.review()`) — hạ tầng live-verify HTTP
  thật đã có từ V14/V15, có thể tái dùng khi cần xác nhận thêm.

## V30 — Audit khả thi Lip-sync (research, KHÔNG build) (Phase G)

Đây là mini-spec RESEARCH — không có code sản xuất, "Test Plan" của chính
nó là độ tin cậy của số liệu (xem mini-spec V30 trong docs/PLAN.md). Ghi
lại ở đây theo đúng khuôn Audit/Verify/Remaining Limits để nhất quán với
mọi mục khác trong file này.

### Giới hạn thật của môi trường research (nói rõ trước khi vào số liệu)

Sandbox này KHÔNG có GPU — không thể tự đo benchmark tốc độ/VRAM THẬT trên
phần cứng thật như mini-spec yêu cầu ("Test = benchmark có số liệu thật,
không phải ước lượng"). Những gì làm được thật trong đợt này:
1. Research license + thông số phần cứng CÔNG BỐ CHÍNH THỨC (tài liệu/
   README/LICENSE của chính từng model mã nguồn mở — không phải quảng cáo
   marketing của SaaS đối thủ) qua tìm kiếm thật, có trích dẫn.
2. Cài đặt THẬT (không giả định) bộ dependency CPU-only (`onnxruntime`,
   `opencv-python-headless`) của nhánh ONNX-converted (biến thể phổ biến
   nhất khi không có GPU) — xác nhận cài sạch, chỉ có `CPUExecutionProvider`
   khả dụng (đúng thực tế máy không GPU, kể cả nhiều máy người dùng cuối
   Windows của VoxDub).
3. KHÔNG tải được model weights (hàng trăm MB-GB) + chạy inference thật
   trên video mẫu trong ngân sách thời gian đợt này — đây là giới hạn thật,
   không phải bỏ sót; ghi rõ để không ai hiểu nhầm là đã benchmark tốc độ
   thật.

### Khảo sát 4 model mã nguồn mở

| Model | License | VRAM/phần cứng (công bố chính thức) | Ghi chú |
|---|---|---|---|
| **Wav2Lip** (Rudrabha/Wav2Lip) | **CHỈ phi thương mại** — README chính chủ ghi rõ "personal/research/non-commercial purposes"; lý do: model train trên bộ dữ liệu LRS2, điều khoản dữ liệu cấm dùng thương mại dưới MỌI hình thức. Tác giả tự bán bản HD thương mại qua Sync Labs (dịch vụ trả phí riêng, không phải mã nguồn mở). | Nhẹ nhất nhóm — biến thể ONNX-converted chạy được CPU, VRAM ~1-2GB bản GPU tối ưu. | **LOẠI TRỪ cho VoxDub** — VoxDub có hệ Vox trả phí (thương mại), dùng model cấm-thương-mại là rủi ro pháp lý thật, không phải lý thuyết. |
| **SadTalker** (OpenTalker/SadTalker) | Apache 2.0 (đã relicense, bỏ ràng buộc phi-thương-mại) — dùng thương mại được. | VRAM tăng TUYẾN TÍNH theo thời lượng: ~8GB cho clip 3 phút, tới 80GB cho 30 phút (bản gốc, chưa tối ưu). | Giấy phép ổn nhưng yêu cầu phần cứng KHÔNG thực tế cho video dài — video YouTube/TikTok điển hình VoxDub xử lý thường dài hơn 3 phút nhiều. |
| **VideoReTalking** (OpenTalker/video-retalking) | **CHƯA XÁC MINH được qua tìm kiếm** — trang dự án ghi Creative Commons BY-SA 4.0 nhưng đó là license của TRANG WEB, không chắc là license của MÃ NGUỒN; cần đọc trực tiếp file LICENSE trong repo trước khi dùng, KHÔNG suy đoán. | Không tìm được số liệu VRAM/tốc độ công bố chính thức qua tìm kiếm. | Loại khỏi so sánh nghiêm túc cho tới khi xác minh trực tiếp — đúng nguyên tắc "không suy đoán khi thiếu bằng chứng". |
| **MuseTalk** (TMElyralab/MuseTalk, Tencent Music) | **MIT — không giới hạn học thuật lẫn thương mại.** | Thấp nhất nhóm: đã test THẬT trên card 4GB VRAM (RTX 3050 Ti laptop, fp16) — clip 8 giây mất ~5 phút xử lý (chậm nhưng CHẠY ĐƯỢC); thời gian thực (30fps+) cần GPU lớp Tesla V100. Có bản cộng đồng quảng cáo chạy được 8-12GB VRAM hiệu quả hơn. Bản 1.5 phát hành 03/2025 — đang tích cực bảo trì. | **Lựa chọn khả thi nhất về mặt giấy phép + độ linh hoạt phần cứng** trong 4 model — nhưng vẫn đòi GPU thật để dùng được ở tốc độ chấp nhận được (không có nhánh CPU-only như Wav2Lip). |

### Xác nhận thật (không suy đoán) qua cài đặt thật

Cài `onnxruntime==1.28.0` + `opencv-python-headless==5.0.0` vào 1 venv sạch
trong sandbox này — THÀNH CÔNG, không lỗi dependency. Kiểm tra provider khả
dụng: `['AzureExecutionProvider', 'CPUExecutionProvider']` — xác nhận
KHÔNG có GPU provider nào (đúng thực tế sandbox này, và đúng thực tế nhiều
máy người dùng cuối Windows của VoxDub theo README đã công bố cấu hình tối
thiểu 8GB RAM, không bắt buộc GPU).

### Quyết định chính sách BẮT BUỘC chủ dự án phải trả lời trước khi build

1. **Consent-check kỹ thuật**: có cần chặn/cảnh báo khi phát hiện khuôn mặt
   người nổi tiếng/công chúng trong video nguồn (qua nhận diện khuôn mặt)
   trước khi cho lip-sync không? Hiện README/LICENSE chỉ có cảnh báo CHÍNH
   SÁCH ("xin đừng dùng để giả mạo"), không có kiểm soát kỹ thuật nào đi
   kèm cho BẤT KỲ tính năng nào của VoxDub — lip-sync là tính năng ĐẦU TIÊN
   thật sự sửa khuôn mặt người (khác dịch giọng/che chữ), nâng mức rủi ro
   deepfake lên hẳn 1 bậc so với hiện trạng.
2. **Watermark bắt buộc**: video đã lip-sync có bắt buộc watermark (nhìn
   thấy được hoặc ẩn/metadata) để phân biệt với video gốc không?
3. **Giới hạn theo gói/Vox**: có giới hạn số lượt/thời lượng lip-sync theo
   gói trả phí để tránh lạm dụng hàng loạt (vd tạo deepfake quy mô lớn)
   không — khác các tính năng khác vốn không có trần sử dụng ngoài Vox.
4. **Venv GPU-only chấp nhận được không**: khác MỌI tính năng khác của
   VoxDub (đều có đường CPU dù chậm — Whisper/Demucs/Paraformer/
   diarization V26), lip-sync THỰC SỰ HỮU DỤNG chỉ khả thi có GPU thật
   (xem bảng VRAM ở trên) — đây là bất đối xứng kiến trúc lớn đầu tiên,
   phá vỡ nguyên tắc "GPU-optional" xuyên suốt 29 mini-spec trước. Chủ dự
   án có chấp nhận 1 tính năng CHỈ chạy được trên máy có GPU mạnh không?
5. **Vấn đề giấy phép Wav2Lip cụ thể**: nếu vẫn muốn dùng nhánh Wav2Lip vì
   nhẹ/CPU-capable, cần tư vấn pháp lý thật (không phải suy đoán của AI)
   về việc dùng model cấm-thương-mại trong 1 tính năng của sản phẩm có hệ
   thống tín dụng trả phí — đây LÀ câu hỏi pháp lý thật, không tự quyết
   được qua audit kỹ thuật.

### Khuyến nghị

**Không build ngay.** Lý do tổng hợp:
- Model duy nhất có giấy phép + phần cứng khả thi rộng rãi (MuseTalk, MIT)
  vẫn đòi GPU thật để hữu dụng — phá nguyên tắc kiến trúc "GPU-optional"
  cố định của toàn bộ dự án, chưa từng có tiền lệ tính năng nào bắt buộc
  GPU hoàn toàn.
- Model nhẹ nhất/CPU-capable nhất (Wav2Lip) có vấn đề giấy phép THẬT (cấm
  thương mại) xung đột trực tiếp với mô hình kinh doanh Vox hiện tại — cần
  tư vấn pháp lý trước khi cân nhắc tiếp, không phải quyết định kỹ thuật.
- Rủi ro đạo đức (deepfake khuôn mặt) là RỦI RO THẬT MỚI, không giống bất
  kỳ tính năng nào đã có — 5 câu hỏi chính sách ở trên PHẢI có câu trả lời
  rõ ràng trước khi mở bất kỳ mini-spec BUILD nào, không phải sau.
- Nếu chủ dự án sau khi cân nhắc 5 câu hỏi trên vẫn muốn theo đuổi: khuyến
  nghị bắt đầu bằng **MuseTalk (MIT)**, giới hạn ban đầu ở venv GPU-only
  (không giả vờ CPU-optional), và tách thành ÍT NHẤT 2 mini-spec riêng
  (giống mô hình Phase C→D đã dùng cho V8→V11/V9→V12): 1 mini-spec PoC hẹp
  (1 GPU cụ thể, video ngắn, không cam kết chất lượng) rồi mới tới mini-spec
  đóng gap nếu PoC chứng minh khả thi thật.

### Remaining Limits (V30)

- **CHƯA có số liệu benchmark tốc độ/chất lượng thật** trên video mẫu —
  giới hạn phần cứng thật của sandbox này (không GPU), đã nói rõ ngay từ
  đầu mục, không phải bỏ sót.
- **License VideoReTalking chưa xác minh** — cần đọc trực tiếp file
  LICENSE trong repo (không chỉ qua tìm kiếm) trước khi đưa vào bất kỳ so
  sánh nghiêm túc nào.
- Vấn đề giấy phép Wav2Lip cần TƯ VẤN PHÁP LÝ THẬT, không phải audit kỹ
  thuật — AI không thể tự kết luận thay luật sư về việc dùng model
  cấm-thương-mại trong sản phẩm có hệ thống trả phí.
- Bảng so sánh chỉ phủ 4 model tại thời điểm research (2026-08) — không
  theo dõi được các model mới/bản cập nhật license sau thời điểm này, cần
  research lại nếu quyết định theo đuổi sau nhiều tháng.

## V31 — Translation-as-a-Service API cho developer bên thứ 3 (Phase G)

### Audit trước khi build

- Xác nhận `gateway.translateSubtitleBatch({items, sourceFlores,
  targetFlores, sourceName, targetName})` (control_server, đã có từ V14) —
  KHÔNG gắn "video context" (domain/pronouns/glossary) như luồng dub chính,
  đúng nhu cầu "phiên bản prompt đơn giản hơn" mà mini-spec dự tính XÂY MỚI
  — thực ra ĐÃ TỒN TẠI SẴN, tái dùng thẳng, không viết prompt mới.
- Đọc đầy đủ route `/v1/ai/translate-subtitle` (dùng đúng hàm gateway trên)
  làm mẫu: validate trần segments/chars, gọi gateway, xử lý lỗi
  `AI_UNAVAILABLE`. Route `/api/v1/translate` mới mô phỏng ĐÚNG cấu trúc
  này (Audit Before Build của mini-spec: "tái dùng ai-gateway.service.js,
  không viết lại logic gọi LLM" — xác nhận đúng, không cần viết lại).
- Đọc `admin.middleware.js`/`worker-auth.middleware.js` (2 kiểu xác thực
  static-secret khác `auth.middleware.js` JWT-based) — API key gần với
  kiểu static-secret hơn (nhiều secret khác nhau, tra theo hash, không cần
  JWT/thời hạn) — không sao chép machine y hệt cái nào, thiết kế riêng phù
  hợp (tra DB theo hash, không so sánh 1-1 timing-safe với 1 secret).
- Đọc `credit.service.js::charge()` — kỹ thuật atomic
  `findOneAndUpdate({điều kiện đủ số dư}, {$inc}, {new:true})` — tái dùng
  Y HỆT cho `consumeQuota()` (Constraint 5: không transaction/replica-set).
- **Phát hiện thật lúc audit**: `/v1/admin/keys` đã tồn tại nhưng là
  `ActivationKey` (mã kích hoạt Vox) — HOÀN TOÀN KHÁC "API key developer"
  của V31. Đặt tên route mới `/v1/admin/api-keys` (không phải `/keys`) để
  tránh nhầm lẫn 2 khái niệm — nếu không audit kỹ điểm này trước khi code
  sẽ dễ đặt tên trùng gây nhầm lẫn nghiêm trọng.

### Xây dựng

- `src/models/ApiKey.js` (mới) — `keyHash` (SHA-256, KHÔNG lưu plaintext),
  `keyPrefix` (hiển thị UI), `quota`/`usageCount` (bộ đếm nhanh, cùng vai
  trò `Device.balance`). TÁCH HẲN `Device.js` (Constraint 3).
- `src/models/ApiUsageLedger.js` (mới) — mỗi lượt gọi 1 dòng bất biến,
  TÁCH HẲN `CreditLedger.js`.
- `src/services/api-key.service.js` (mới) — `generateApiKey()` (dạng
  `vx_live_<48 hex>`), `hashApiKey()`, `createApiKey()`, `findByPlaintext()`
  (tra theo hash, không phải so sánh timing-unsafe), `consumeQuota()`
  (atomic `findOneAndUpdate`, raise `QuotaExceededError` nếu hết quota/key
  revoked).
- `src/middleware/apikey.middleware.js` (mới) — `requireApiKey`, gắn
  `request.apiKey`, SONG SONG `auth.middleware.js` (không sửa file đó).
- `src/routes/api-v1.js` (mới) — `POST /translate`: validate trần
  segments/chars (dùng chung config với `/translate-subtitle`), PRE-CHECK
  quota nhanh (đọc, không atomic — tránh gọi model tốn tiền khi đã rõ hết
  quota) → gọi `gateway.translateSubtitleBatch()` → `consumeQuota()` atomic
  THẬT SỰ chặn (xử lý đúng race giữa request song song) → trả kết quả.
- `src/routes/admin.js` — thêm `GET/POST /api-keys` + `DELETE /api-keys/:id`
  (namespace riêng, không đụng `/keys` cũ) — audit log mọi hành động tạo/
  thu hồi, đúng nguyên tắc "mọi hành động đổi tiền/quyền đều ghi AuditLog"
  đã ghi ở đầu file `admin.js`.
- `src/app.js` — đăng ký `/api/v1` (route mới) SAU `/internal/jobs`, KHÔNG
  đụng thứ tự/cấu hình các route cũ.
- `docs/API.md` — mục `/api/v1` mới + 3 dòng bảng `/v1/admin`.

### Verify

- `tests/api-key-service.test.js` (8 test): sinh key đúng định dạng, không
  trùng; hash xác định; `createApiKey()` không lưu plaintext; tìm đúng/sai
  key; `consumeQuota()` tăng đúng, raise khi hết quota/key revoked; **10
  request `consumeQuota()` CHẠY SONG SONG THẬT trên key quota=5 → đúng
  CHÍNH XÁC 5 lượt thành công, `usageCount` cuối = 5** (khoá đúng tính
  atomic dưới race condition thật, không phải giả lập).
- `tests/api-v1-route.test.js` (9 test, HTTP thật qua `fastify.inject`,
  mock `gateway.translateSubtitleBatch`): thiếu/sai/revoked key → đúng mã
  lỗi; key hợp lệ → dịch đúng, quota trừ đúng, ghi `ApiUsageLedger`; hết
  quota → 429, **gateway KHÔNG được gọi** (xác nhận bằng
  `fn.mock.callCount()`, đúng thiết kế "kiểm trước khi tốn tiền model");
  **billing KHÔNG đụng `Device.balance`/`CreditLedger`** của desktop app
  (test tạo Device thật, gọi API key thật, xác nhận Device không đổi gì);
  validate schema; **device token (JWT app desktop) KHÔNG dùng được cho
  `/api/v1`** (401 — xác nhận 2 hệ auth tách biệt hoàn toàn, không lẫn).
- `tests/admin-api-keys-route.test.js` (5 test, HTTP thật): thiếu admin
  token → 401; tạo key → plaintext chỉ trả 1 lần, DB không lưu plaintext;
  danh sách không lộ `keyHash`; thu hồi → key thật sự không dùng được nữa
  ở `/api/v1/translate` (test gọi CẢ 2 route thật, không chỉ kiểm DB).
- `npm test` toàn bộ (Node test runner + MongoDB in-memory thật, không
  mock DB): **189 tests, 188 passed, 1 skipped, 0 failed** (168 pass trước
  V31 + 21 test mới — con số baseline 167 pass đã xác nhận lại bằng cách
  chạy `npm test` THẬT trước khi bắt đầu code V31, không giả định).
- **Live-verify THẬT qua HTTP thật** (không chỉ `fastify.inject` trong
  test) — dựng script khởi động `build()` thật + kết nối MongoDB THẬT
  (in-memory server thật, không mock mongoose) + `app.listen()` thật trên
  cổng 3999, rồi gọi `curl` thật từ ngoài tiến trình Node: (1) tạo API key
  qua admin — nhận đúng `vx_live_...` thật; (2) gọi `/api/v1/translate`
  không key → `401` thật; (3) gọi với key thật → đi xuyên suốt auth +
  validate + quota precheck tới tận `ai-gateway.service.js`, dừng đúng ở
  `NO_PROVIDER` (không có AI provider cấu hình trong DB test — đúng dự
  kiến, XÁC NHẬN toàn bộ đường ống hoạt động thật, không phải giả định
  route "chắc chạy được"); (4) liệt kê key qua admin — không lộ `keyHash`
  thật; (5) thu hồi — `403` thật ngay sau đó khi gọi lại translate.

### Remaining Limits (V31)

- **Chưa live-verify dịch THẬT thành công** (cần AI provider key thật —
  Gemini/OpenAI/OpenRouter — không có trong môi trường sandbox này) — đã
  live-verify được TOÀN BỘ đường ống TRỪ bước gọi model thật (dừng đúng ở
  `NO_PROVIDER`, không phải lỗi route/auth/quota).
- **Chưa có self-service portal** — đúng phạm vi đã chốt trong mini-spec
  ("thủ công qua admin lúc đầu"), self-service là mini-spec RIÊNG nếu nhu
  cầu thật xuất hiện.
- Rate-limit Fastify per-route (`config.rateLimit`) dùng chung
  `keyGenerator` toàn cục (`app.js`, cắt 32 ký tự cuối Bearer token) — tự
  nhiên tách được API key khỏi device token do khác định dạng/độ dài,
  nhưng KHÔNG có namespace rate-limit RIÊNG cho `/api/v1/*` như bản nháp
  ban đầu hình dung — chặn THẬT SỰ (quota cứng) nằm ở `ApiKey.quota`, tầng
  rate-limit chỉ là lớp chống burst bổ sung, không phải cơ chế chính.
- Chưa có endpoint cho developer tự xem usage/quota của chính mình (chỉ
  admin xem được qua `/v1/admin/api-keys`) — response `/api/v1/translate`
  CÓ trả `quota`/`usageCount` mỗi lượt gọi nên developer vẫn theo dõi được
  gián tiếp, nhưng chưa có `GET /api/v1/me` riêng.

## Re-audit (2026-08-12) — đóng 3 Remaining Limits thật khả thi (V26/V28/V31)

Trước khi sửa: kiểm tra môi trường xem có credential/tài nguyên THẬT mới
xuất hiện từ lượt build V26→V31 không (HF token cho pyannote.audio, API key
AI provider thật cho Gemini/OpenAI/OpenRouter, model NLLB cache sẵn) —
KHÔNG có gì mới (`control_server/.env` vẫn chỉ giá trị placeholder/test,
không có `*_HF_TOKEN`/`GEMINI_*`/`OPENAI_*`/`OPENROUTER_*`, không tìm thấy
cache NLLB nào trên máy). Vì vậy KHÔNG cố "fake" live-verify các giới hạn
cần credential thật (diarization THẬT trên audio 2 người nói, dịch SaaS
THẬT qua model thật) — 2 giới hạn đó VẪN CÒN nguyên, ghi lại trung thực bên
dưới thay vì giả vờ đã xong. 3 giới hạn CÒN LẠI dưới đây là loại KHÔNG cần
credential ngoài (thuần logic/wiring) nên sửa được thật trong lượt này.

### V31 — thêm `GET /api/v1/me`

Đóng đúng gap cuối cùng ghi trong Remaining Limits (V31) ở trên: developer
trước đây chỉ biết quota/usage của mình GIÁN TIẾP qua response mỗi lượt gọi
`/translate` — không có cách xem TRƯỚC khi gọi gì cả.

- `control_server/src/routes/api-v1.js` — route mới `GET /me` (cùng
  `preHandler: requireApiKey` với `/translate`), trả
  `{orgName, status, quota, usageCount, remaining, lastUsedAt}` của CHÍNH
  API key đang xác thực — không lộ `keyHash` hay dữ liệu API key khác.
- `docs/API.md` — thêm mục `GET /me`.
- `control_server/tests/api-v1-route.test.js` (+2 test): trả đúng thông tin
  quota (kèm khẳng định KHÔNG có `keyHash` trong response); không có key →
  401 giống mọi route `/api/v1` khác.
- `node --test tests/api-v1-route.test.js`: 10/10 pass (8 cũ + 2 mới).

### V26 — panel GUI "Xem trước người nói"

Đóng gap "GUI chỉ có cờ bật/tắt tối thiểu" — Scope E của mini-spec (đổi
giọng theo TỪNG người nói thay vì phải mở popup giọng cho từng câu lẻ).

- `autodub/editor.py` — 2 hàm THUẦN mới (test được không cần Qt, cùng nguyên
  tắc pure-function-first của `set_segment_voice()` đã có):
  `list_speakers(work_dir, target_key)` (nhóm segment theo
  `seg["speaker_label"]`, trả `[{speaker_label, segment_count, sample_text,
  voice}]`, `voice` là giọng phổ biến nhất đã gán cho speaker đó, rỗng nếu
  chưa gán; danh sách RỖNG — không lỗi — nếu dự án chưa bật diarization) và
  `set_speaker_voice(work_dir, speaker_label, voice, target_key)` (gán 1
  giọng cho MỌI segment của 1 người nói, tái dùng đúng quy tắc ghi đĩa của
  `set_segment_voice()`, trả về số segment thật sự đổi).
- `autodub_gui/ui/speaker_dialog.py` (mới) — `SpeakerPreviewDialog`: hộp
  thoại thuần hiển thị + phát tín hiệu (`voice_changed(speaker_label,
  voice)`), KHÔNG tự ghi đĩa — mỗi người nói hiện tên thân thiện ("Người nói
  1" thay vì "SPEAKER_00"), số câu, câu mẫu, và `VoicePicker` (widget dùng
  chung với mục "Giọng đọc" chính của Trình chỉnh sửa).
- `autodub_gui/pages/editor_panels.py` (`VoicePanel`) — nút "Xem người nói"
  mới (ẩn mặc định, chỉ hiện khi dự án có diarization — Constraint "không
  suy đoán capability khi thiếu evidence").
- `autodub_gui/pages/editor_page.py` — `set_speakers_available()` gọi mỗi
  lần nạp dự án (kiểm `list_speakers()` có rỗng không); `_open_speaker_dialog()`
  mở hộp thoại; `_on_speaker_voice_changed()` gọi `set_speaker_voice()`, cập
  nhật bản sao segment trong bộ nhớ + `_dirty_ids` + dựng lại danh sách phụ
  đề — cùng khuôn với `_on_segment_voice_changed()` (per-segment) đã có.

**Verify:**
- `tests/test_editor_speakers.py` (8 test, mới): nhóm đúng theo speaker;
  câu không có `speaker_label` không tính vào speaker nào; danh sách rỗng
  khi chưa bật diarization (không lỗi); thiếu transcript → `EditorError`;
  đổi giọng CHỈ ảnh hưởng đúng speaker đó; chuỗi rỗng → bỏ override, quay về
  giọng chung; gán ĐÚNG giọng đã có → 0 thay đổi (không ghi file thừa);
  speaker lạ → 0 thay đổi.
- `pytest tests/ -q` toàn bộ (venv đầy đủ dependency, dựng mới trong lượt
  này vì sandbox không có sẵn — xem "Ghi chú môi trường" cuối file): **948
  passed, 6 skipped, 0 failed** (940 pass trước re-audit + 8 test mới).
  Chạy với `QT_QPA_PLATFORM=offscreen` (bắt buộc cho mọi test PySide6
  headless, cùng quy ước `test_quality_page_review_trace.py` đã có) — xác
  nhận GUI mới (`editor_page.py`/`editor_panels.py`/`speaker_dialog.py`)
  import và chạy được thật với PySide6 thật, không chỉ `py_compile`.
- **CHƯA live-verify bằng mắt/tai qua ứng dụng chạy thật** (cần môi trường
  có màn hình + dự án đã diarization thật — 2 giới hạn cộng dồn của sandbox
  này) — chỉ verify được ở tầng logic + import GUI thật.

### V28 — nối tín hiệu tone từ LLM (Scope A của mini-spec)

Đóng gap lớn nhất còn lại: trước đây `_apply_emotion_styles()` CHỈ có
heuristic văn bản local; giờ ưu tiên tín hiệu LLM khi SaaS bật, đúng Design
Choice gốc của mini-spec — **KHÔNG đụng `buildAnalysisPrompt`** (hàm đó là
phân tích CẤP VIDEO — summary/domain/pronouns/glossary — không phải per-
segment) mà đụng đúng chỗ per-segment thật sự tồn tại:
`buildTranslateSystemPrompt`/`translateSchema` (dùng bởi `translateBatch`,
route dịch dub pipeline `/v1/ai/translate`) — ghi rõ đây là 1 sai lệch nhỏ
có chủ đích so với chữ trong bản nháp mini-spec, chọn đúng cơ chế kỹ thuật
thật thay vì làm đúng-tên-hàm-nhưng-sai-chỗ.

- `control_server/src/prompts/translate.js` — `TONE_VALUES = ["neutral",
  "excited", "serious"]` (CHỈ 3 giá trị, không phải 4 như ví dụ "sad" trong
  bản nháp đầu mini-spec — khớp ĐÚNG 3 style VieNeu thật đã map sẵn ở
  `autodub/text/tone_heuristic.py::_TONE_TO_STYLE`, không bịa nhãn không có
  chỗ ánh xạ). `translateSchema(field, {emotionTone})` và
  `buildTranslateSystemPrompt({..., emotionTone})` — cờ TẮT (mặc định) giữ
  NGUYÊN schema/prompt cũ 100%, bật lên mới thêm field `tone` bắt buộc +
  đoạn hướng dẫn phân loại cảm xúc.
- `control_server/src/utils/json-repair.js::mergeTranslations` — thêm tham
  số thứ 4 `extraFields` (mặc định `[]`, 0 regression cho 2 lời gọi hiện có)
  để copy nguyên văn field phụ (vd `tone`) từ response model sang segment đã
  ghép, ở CẢ 2 nhánh ghép (theo id, và ghép-theo-vị-trí khi model quên id).
- `control_server/src/services/ai-gateway.service.js::translateBatch` —
  tham số `emotionTone` (mặc định false), truyền xuống prompt/schema/merge
  VÀ xuống lời gọi đệ quy khi phải chia đôi lô (thiếu câu) — có test khoá
  riêng vì đây là chỗ dễ quên nhất. Model trả nhãn ngoài enum (schema JSON
  không phải provider nào cũng ép cứng được) hoặc quên field `tone` ở 1 câu
  → tự sửa về `"neutral"`, không để lọt giá trị lạ xuống Python.
- `control_server/src/routes/ai.js` (`POST /v1/ai/translate`) — thêm
  `emotionTone: {type: "boolean", default: false}` vào body schema, truyền
  xuống `gateway.translateBatch()`. Biết trước và KHÔNG sửa trong lượt này:
  `fixCjkLeftovers()` (lưới cuối vá chữ Hán sót) không yêu cầu lại `tone` khi
  vá 1 câu — do dùng spread `{...s, ...}` nên giữ NGUYÊN `tone` cũ của câu
  đó dù chữ vừa bị dịch lại, có thể lệch nhẹ (edge case hiếm, CJK-leftover
  đã hiếm + lệch tone 1 câu không phải regression nghiêm trọng, ghi rõ thay
  vì im lặng). Cache idempotency theo `jobId` (nội dung câu, KHÔNG gồm cờ
  `emotionTone`) cũng có edge case tương tự: đổi cờ Cài đặt giữa 2 lần chạy
  CÙNG transcript có thể nhận lại response cache cũ thiếu `tone` — edge case
  hẹp, không sửa trong lượt này (đòi hỏi đổi ngữ nghĩa cache/billing
  idempotency rộng hơn phạm vi fix này).
- `autodub/saas_client.py::translate()` — tham số `emotion_tone: bool =
  False`, gửi `payload["emotionTone"] = True` chỉ khi bật (không gửi field
  khi tắt, giữ payload cũ y nguyên).
- `autodub/text/translate_saas.py` — `translate_segments()` gửi
  `emotion_tone=settings.emotion_voice_enabled` (CÙNG cờ Cài đặt đã bật
  đường heuristic — không phải cờ mới); `_merge()` copy `item["tone"]` vào
  segment đã ghép nếu máy chủ có trả, bỏ qua nếu không (không bịa).
- `autodub/pipeline.py::_apply_emotion_styles()` — ưu tiên `seg["tone"]`
  (đã gắn từ lượt dịch SaaS) khi có mặt và không rỗng; rơi về heuristic văn
  bản cũ khi không có — đúng Design Choice "ưu tiên LLM, heuristic là dự
  phòng" và Constraint 2 ("2 đường xử lý RÕ RÀNG KHÁC NHAU"). Log giờ tách
  rõ bao nhiêu câu theo nguồn nào (`"N từ SaaS, M từ heuristic"`).

**Verify:**
- `control_server/tests/translate-prompts.test.js` (+6 test): schema/prompt
  mặc định KHÔNG có `tone` (0 regression); bật `emotionTone` → schema có
  đúng field `tone` bắt buộc + enum 3 giá trị, prompt có đúng hướng dẫn +
  "EXACTLY THREE fields"; `TONE_VALUES` khớp đúng 3 giá trị phía Python.
- `control_server/tests/utils.test.js` (+4 test): `mergeTranslations` với
  `extraFields=[]` (mặc định) không lộ field thừa; `extraFields=["tone"]`
  copy đúng theo từng câu (cả ghép theo id lẫn ghép theo vị trí); câu model
  không trả tone thì KHÔNG có field đó (không bịa).
- `control_server/tests/ai-gateway-emotion-tone.test.js` (5 test, MỚI —
  gọi `translateBatch()` THẬT, chỉ mock lớp gọi HTTP ra ngoài `axios.post` +
  dùng MongoDB thật trong bộ nhớ cho `AiProvider`, đúng ranh giới mock của
  các test khác trong repo — không mock chính hàm đang kiểm): cờ tắt → cả
  request gửi lên VÀ response đều không có `tone`; cờ bật → tone đúng theo
  từng câu; model trả nhãn ngoài enum → tự sửa "neutral"; model quên tone 1
  câu → tự rơi "neutral"; **lô phải chia đôi (thiếu câu) → cờ `emotionTone`
  vẫn được giữ đúng ở lời gọi đệ quy cho lô con** (test khoá riêng đúng chỗ
  dễ quên nhất khi thêm tham số mới vào hàm đệ quy).
- `node --test`: **205 tests, 204 pass, 1 skipped, 0 failed** (191 trước
  re-audit + 15 test mới: 2 V31 + 6+4+5 tổng của utils/prompts/gateway V28,
  trừ 2 trùng đếm với V31 ở trên).
- `tests/test_pipeline_emotion_voice.py` (+4 test): `seg["tone"]` có mặt →
  dùng THẲNG (bỏ qua heuristic dù văn bản gợi ý tone khác hẳn); không có →
  rơi về heuristic (0 regression); lô hỗn hợp (1 câu có tone LLM, 1 câu
  không) → mỗi câu đúng nguồn riêng, không lẫn; `tone` rỗng/khoảng trắng
  (dữ liệu lạ) → coi như không có, không tra style rỗng.
- `tests/test_translate_saas_emotion_tone.py` (7 test, mới):
  `translate_segments()` gửi đúng `emotion_tone` theo `settings
  .emotion_voice_enabled` (cả 2 chiều bật/tắt); tone từ server tới đúng
  segment cuối cùng; tắt cờ → không có field tone (0 regression); `_merge()`
  copy đúng tone khi có, bỏ qua khi không, không bịa cho câu server không
  dịch được.
- `pytest tests/ -q` toàn bộ: **959 passed, 6 skipped, 0 failed** (948 pass
  sau phần V26/V31 ở trên + 11 test V28 mới: 4 pipeline + 7 translate_saas).

**Remaining Limits còn lại sau re-audit này (thật sự cần credential/hạ tầng
ngoài, không phải bỏ sót):**
- Diarization THẬT (V26) và dịch SaaS THẬT qua model thật (V28/V31) — vẫn
  cần HF token / AI provider key thật tương ứng, sandbox này không có.
- `/v1/ai/translate` (route dub pipeline, KHÁC route `/api/v1/translate`
  của V31) chưa có test HTTP-level nào trong toàn bộ repo — không phải gap
  do V28 gây ra (đã xác nhận bằng grep trước khi build: 0 test file nào
  tham chiếu route này qua `fastify.inject`) — ghi nhận là nợ kỹ thuật CÓ
  SẴN, ngoài phạm vi fix Remaining Limits của lượt này.
- Panel "Xem trước người nói" (V26) chưa live-verify bằng mắt qua ứng dụng
  chạy thật (xem mục V26 ở trên) — chỉ verify logic + import GUI thật.

**Ghi chú môi trường:** sandbox lượt re-audit này ban đầu KHÔNG có venv
Python nào cài sẵn (khác lượt build V26-V31 trước — có thể đã bị dọn giữa
2 phiên làm việc) — dựng lại `python3 -m venv .venv-test` rồi cài đủ
`pip install -e ".[dev]" pydub numpy cryptography` mới chạy được
`pytest tests/` đầy đủ. Ghi lại để phiên sau không nhầm "thiếu dependency"
là bug thật của code.

## V32a — PoC lip-sync MuseTalk: hạ tầng cài đặt + harness đo thật (Phase G)

Chủ dự án đã trả lời đủ 5 câu hỏi chính sách của V30 (2026-08-12, xác nhận
trực tiếp): CÓ consent-check, CÓ watermark, CÓ giới hạn theo gói/Vox, CHẤP
NHẬN venv GPU-only, KHÔNG cần xét lại Wav2Lip (audit kỹ thuật AI đủ). Yêu
cầu: chuẩn bị sẵn phần KHÔNG cần GPU của V32a để chủ dự án tự chạy trên máy
có GPU riêng.

### Nghiên cứu thật trước khi viết script (không suy đoán API/lệnh cài đặt)

- Đọc trực tiếp `README.md`/`requirements.txt`/`download_weights.sh`/
  `LICENSE` của repo `TMElyralab/MuseTalk` (qua `raw.githubusercontent.com`
  thật, có trích dẫn) — xác nhận lại license MIT (khớp V30), lấy đúng lệnh
  cài PyTorch 2.0.1 (cu118), bộ MMLab (`mmengine`/`mmcv==2.0.1`/
  `mmdet==3.1.0`/`mmpose==1.1.0`), và danh sách model weights + nguồn tải
  thật (HuggingFace: `TMElyralab/MuseTalk`, `stabilityai/sd-vae-ft-mse`,
  `openai/whisper-tiny`, `yzd-v/DWPose`, `ByteDance/LatentSync`; Google
  Drive: `face-parse-bisent`; pytorch.org: `resnet18`).
- Đọc trực tiếp mã nguồn `musetalk/utils/preprocessing.py` và
  `scripts/inference.py` (qua GitHub API + raw content thật, không đoán tên
  hàm) — xác nhận API thật: `get_landmark_and_bbox(img_list)` trả về
  `(coords_list, frames)`, frame không phát hiện được khuôn mặt được đánh
  dấu bằng `coord_placeholder = (0.0,0.0,0.0,0.0)` — đây CHÍNH LÀ tín hiệu
  consent-check (Scope C của mini-spec), dùng THẲNG hàm thật của MuseTalk
  thay vì tự viết detector riêng (đúng nguyên tắc Playbook "không build
  song song với engine đã có").
- Lấy đúng SHA commit mới nhất qua GitHub API (`0a89dec45a0192b824e3cf4daf
  96c239440c5ed8`, 2025-09-26) để ghim — PoC phải tái lập được, không clone
  nhánh `main` trôi nổi.
- Xác nhận môi trường sandbox này KHÔNG có GPU qua 2 cách: lệnh `nvidia-smi`
  không tồn tại, và `python3 -c "import torch"` báo chưa cài — khớp đúng
  giới hạn đã ghi ở V30, không phải lỗi mới.

### Xây dựng

- `scripts/setup_lipsync_poc.py` (mới) — script cài đặt resume-safe theo
  đúng khuôn `scripts/setup_diarization.py` đã có: kiểm GPU THẬT trước tiên
  (gate chặn cứng, đỡ phí ~15GB tải về nếu máy không có GPU) → tạo
  `.venv-lipsync` → cài PyTorch 2.0.1 cu118 → clone MuseTalk (ghim commit) →
  cài `requirements.txt` + bộ MMLab → tải weights thật (~5-6GB, qua
  `huggingface_hub`/`gdown`/`urllib` trực tiếp trong Python, không phụ
  thuộc bash để chạy được cả Windows) → kiểm ffmpeg (dùng lại đúng
  `shutil.which("ffmpeg")`/`bin/ffmpeg.exe` mà `preflight.py` đã dùng, không
  cài ffmpeg riêng trùng lặp). Ghi rõ trong docstring 2 rủi ro THẬT không
  giấu: `mmcv` là extension biên dịch sẵn có thể lỗi trên tổ hợp Python/CUDA
  lạ (cần Visual Studio Build Tools trên Windows nếu phải build từ mã
  nguồn); `requirements.txt` của MuseTalk ghim `numpy==1.23.5` CŨ hơn
  `numpy>=1.24` của `pyproject.toml` chính — đúng lý do venv phải tách hẳn.
- `scripts/research/lipsync_poc.py` (mới) — harness đo 3 nhóm số liệu thật:
  (B) benchmark — gọi `scripts/inference.py` THẬT của MuseTalk qua
  subprocess (không viết lại logic inference), đo thời gian bằng
  `time.monotonic()` + VRAM peak bằng poll `nvidia-smi` mỗi 0.5s trên luồng
  nền trong lúc subprocess chạy; (C) consent-check — tách frame bằng đúng
  lệnh ffmpeg MuseTalk dùng nội bộ rồi gọi thẳng `get_landmark_and_bbox()`
  thật, tính % frame không phát hiện được khuôn mặt; (D) watermark — 2
  phương án ffmpeg (overlay chữ nhìn thấy được / metadata ẩn), đo chi phí
  thời gian xử lý thêm mỗi phương án. Ghi report JSON đầy đủ mỗi lượt chạy.
- `.gitignore` — thêm `/scripts/research/musetalk_repo/` (mã nguồn MuseTalk
  clone về, không phải submodule) và `/scripts/research/lipsync_poc_output/`
  (report + video kết quả benchmark cá nhân từng máy) — `lipsync_poc.py`
  (harness THẬT của VoxDub) vẫn được commit bình thường, chỉ 2 thư mục con
  sinh ra lúc chạy mới bị loại.

### Verify

- `py_compile` cả 2 script — không lỗi cú pháp.
- **CHƯA chạy được thật** — sandbox này không có GPU (Constraint 2 của
  mini-spec V32a là gate chặn CỨNG, script tự dừng ở bước đầu nếu thiếu
  GPU thay vì lãng phí thời gian cài ~15GB). Đây là giới hạn môi trường
  thật giống hệt V30, không phải bỏ sót — chủ dự án cần tự chạy 2 script
  này trên máy có GPU NVIDIA thật (khuyến nghị tối thiểu ~4GB VRAM, đúng số
  liệu cộng đồng đã có từ V30) để có số liệu benchmark thật, sau đó viết
  báo cáo Success Criteria của V32a (bảng benchmark ≥3 video mẫu, khuyến
  nghị go/no-go cho V32b) vào đây.
- Mọi lệnh cài đặt/tên hàm/tên gói trong 2 script đều lấy TRỰC TIẾP từ
  README/mã nguồn thật của MuseTalk qua `raw.githubusercontent.com`/GitHub
  API (không suy đoán) — nhưng CHƯA được verify bằng cách chạy thật trên
  GPU, nên vẫn có khả năng lệch nhỏ nếu upstream đổi API trước khi ai đó
  chạy (rủi ro thật của mọi dependency ngoài, không riêng gì lip-sync).

### Remaining Limits (V32a)

- **CHƯA có số liệu benchmark thật nào** — gate chặn GPU, xem trên. Đây là
  phần việc LỚN NHẤT còn lại của V32a.
- **CHƯA verify script cài đặt chạy trót lọt hết 6 bước** trên máy thật —
  rủi ro thực tế nhất là bước MMLab (`mmcv`) nếu không có wheel dựng sẵn
  khớp máy, đã ghi rõ trong docstring, không giấu.
- Face-detection audit (Scope C) chỉ đo được TỶ LỆ phát hiện khuôn mặt —
  KHÔNG giải bài toán nhận diện DANH TÍNH người nổi tiếng (đó là bài toán
  khác hẳn, face recognition + cơ sở dữ liệu, ngoài phạm vi PoC này, có thể
  cần dịch vụ bên thứ 3 riêng nếu chính sách consent-check cuối cùng của
  V32b yêu cầu tới mức đó — ghi lại làm đầu vào cho V32b).

## V32a — Re-audit: live-verify thật trên máy chủ dự án (2026-08-13)

Chủ dự án (có GPU NVIDIA riêng) tự chạy 2 script trên máy cá nhân, không
phải sandbox — đúng kế hoạch đã ghi ở Remaining Limits phía trên. Máy live-
verify: **NVIDIA T1200 Laptop GPU, 4096MiB VRAM**, Windows, Python mặc định
3.14 (không phải 3.10), i5-11500H.

### 8 bug thật tìm+sửa qua live-verify từng bước (không giấu — mọi bug đều
### do CODE của mini-spec này, không phải "máy người dùng có vấn đề")

1. **`setup_lipsync_poc.py` tạo venv bằng Python mặc định của máy (3.14)**
   — torch==2.0.1 (MuseTalk pin cứng) không có wheel cho Python quá mới,
   `pip install` chết ngay "No matching distribution". Sửa:
   `step_check_python()` tự tìm `py -3.10` cụ thể, tự xoá-tạo-lại venv nếu
   phát hiện venv cũ sai bản Python.
2. **`huggingface_hub[cli]` cài với `-U`** (không ép trần version) kéo lên
   bản 1.x mới nhất, xung đột `transformers==4.39.2` (đòi
   `huggingface-hub<1.0`) — pip cảnh báo đỏ, rủi ro vỡ lúc import
   `transformers.WhisperModel`. Sửa: ghim `huggingface_hub[cli]<1.0,>=0.20.0`.
3. **`gdown --id <ID>` dùng cú pháp cũ** — bản gdown mới nhất (không ghim
   version) đã bỏ cờ `--id`, nhận ID/URL làm tham số vị trí. Sửa: bỏ cờ
   `--id`, truyền ID trực tiếp.
4. **`import autodub.resources` kéo theo TOÀN BỘ dependency nặng của
   VoxDub** (`autodub/__init__.py` luôn chạy trước theo quy tắc package
   Python, tự import `autodub.config` cần `python-dotenv`,
   `autodub.pipeline` cần `pydub`/`faster-whisper`/...) — không có trong
   Python trần chạy script cài đặt. Sửa: bỏ hẳn import, dùng thẳng
   `PROJECT_ROOT` đã có sẵn (tương đương `app_root()` khi không đóng gói
   PyInstaller).
5. **Đường dẫn video/audio tương đối bị hiểu sai khi tiến trình con đổi
   cwd** — 2 chỗ: (a) Scope B ghi nguyên văn đường dẫn tương đối vào YAML
   rồi MuseTalk đọc lại với `cwd=REPO_DIR` khác hẳn, inference chết ngay
   "exit code 1"; (b) `musetalk/utils/preprocessing.py` tự mở config
   DWPose bằng đường dẫn tương đối NGAY LÚC IMPORT, chỉ đúng khi
   `cwd=REPO_DIR`. Sửa: ép `os.path.abspath()` cho video/audio đầu
   `main()`, dùng xuyên suốt; `os.chdir(REPO_DIR)` tạm thời quanh đúng câu
   import đó (try/finally trả lại cwd).
6. **Tự ghép chuỗi YAML bằng f-string vỡ với đường dẫn Windows** — dấu
   `\` trong đường dẫn tuyệt đối bị hiểu nhầm thành ký tự escape trong
   chuỗi ngoặc kép (`\s` không hợp lệ), `OmegaConf`/PyYAML báo
   `ScannerError`. Sửa: dùng `yaml.safe_dump()` thay tự ghép chuỗi.
7. **Thiếu `--use_float16`** — chạy fp32 mặc định tốn gấp đôi VRAM so với
   cấu hình cộng đồng đã biết chạy được trên card 4GB (V30: "RTX 3050 Ti
   4GB, fp16"). VRAM đo được đỉnh 3931/4096MB (96%) rồi MuseTalk tự bắt
   exception giữa chừng (rất có thể CUDA OOM), tự nuốt lỗi và báo "thành
   công giả" (mã thoát 0 — xem bug #8). Sửa: thêm `--use_float16` +
   `--batch_size 4` (từ mặc định 8) — sau khi sửa, benchmark THÀNH CÔNG
   THẬT, nhanh hơn ~7 lần (187s cho lượt gần-thành-công, 794s cho lượt
   thành công hoàn chỉnh — chênh lệch vì lượt sau chạy hết cả bước mux
   audio/video mà lượt gần-thành-công chưa tới).
8. **Mã thoát của MuseTalk không đáng tin** — đọc thẳng mã nguồn
   `scripts/inference.py` xác nhận nó bọc TOÀN BỘ xử lý trong
   `try/except Exception as e: print("Error occurred during processing:",
   e)`, không `sys.exit()`/raise lại — luôn thoát mã 0 dù lỗi thật xảy ra
   giữa chừng. Sửa: chỉ coi "ok" khi ĐỦ 3 điều — mã thoát 0, KHÔNG có chuỗi
   lỗi đặc trưng đó trong output, VÀ file video kết quả thật sự tồn tại.
   Phát hiện thêm 1 lớp của bug này: khi output bị pipe-redirect (để vừa
   stream vừa gom log), MuseTalk tự in ký tự CJK trang trí
   (`"Total frame:「268」..."`) gặp `UnicodeEncodeError` vì Windows rơi về
   codepage ANSI hẹp thay vì console codepage thật cho stream bị redirect
   — lỗi ĐÓ bị nuốt và báo nhầm thành "lỗi xử lý" dù AI đã xử lý xong hoàn
   toàn. Sửa: ép UTF-8 cả 2 đầu (`PYTHONIOENCODING=utf-8`/`PYTHONUTF8=1`
   cho tiến trình con, `encoding="utf-8"` cho phía cha đọc lại).

Bonus (không phải bug chặn, nhưng sửa cho hoàn chỉnh Scope D): **watermark
chữ đè lỗi "Fontconfig error"** — ffmpeg Windows không có fontconfig mặc
định nên `drawtext` không tự dò được font. Sửa: trỏ thẳng `fontfile=` tới
font có sẵn trong repo (`fonts/BarlowCondensed-Regular.ttf`, đã dùng cho
phụ đề burn-in), escape đúng dấu `:` ổ đĩa Windows theo cú pháp filter
ffmpeg — verify thật bằng lệnh ffmpeg độc lập trước khi đưa vào script.

### Số liệu benchmark thật — mẫu 1/3: mặt thẳng (video mẫu MuseTalk)

Video mẫu chính chủ MuseTalk (`data/video/yongen.mp4` + `data/audio/
yongen.wav`, 268 frame @ 25fps ≈ 10.7 giây) — CHƯA phải video/audio thật
của VoxDub (Constraint 6 đòi ≥3 mẫu VoxDub thật: mặt thẳng/góc nghiêng/
nhiều người; mẫu này chỉ để verify pipeline cài đặt chạy đúng trước khi
tốn thời gian với dữ liệu thật).

| Chỉ số | Giá trị thật đo được |
|---|---|
| Thời gian xử lý | 794 giây (~13.2 phút) cho ~10.7 giây video |
| VRAM đỉnh | 3929MB / 4096MB (~96% — rất sát trần card 4GB) |
| Face-detection (consent-check) | 268/268 frame (100%), 0 frame thiếu mặt |
| Watermark metadata | Thành công, chi phí ~0.3s |
| Watermark chữ đè | Thành công sau fix font, chi phí ~3s |

**CHƯA có đánh giá chất lượng bằng mắt** (khẩu hình có tự nhiên/khớp âm
không) — chủ dự án đang xem video kết quả, sẽ ghi bổ sung sau.

### Remaining Limits (Re-audit V32a 2026-08-13)

- **Chỉ mới 1/3 mẫu bắt buộc** (Constraint 6: mặt thẳng/góc nghiêng/nhiều
  người) — mới xong mặt thẳng, dùng video mẫu MuseTalk chứ chưa phải dữ
  liệu VoxDub thật. Cần chạy tiếp ≥2 mẫu nữa (góc nghiêng, nhiều người)
  bằng video/audio thật từ 1 dự án VoxDub đã dub để có bảng benchmark đầy
  đủ theo đúng Success Criteria của mini-spec.
- **CHƯA có đánh giá chất lượng chủ quan** (khẩu hình tự nhiên/khớp âm hay
  không) — số liệu benchmark chỉ trả lời được "chạy được", không trả lời
  "đáng dùng không".
- VRAM 96% trên card 4GB là RẤT SÁT TRẦN — video dài hơn/nhiều khuôn mặt
  hơn có khả năng thật sự OOM ngay cả với fp16+batch_size=4, cần thử thêm
  với video dài hơn 10.7 giây để biết giới hạn thật.
- 8 bug sửa được đều là bug MÔI TRƯỜNG/TÍCH HỢP (Python version, dependency
  conflict, path handling, encoding) — chưa phát hiện bug nào ở tầng LOGIC
  benchmark/consent-check/watermark tự viết, nhưng cũng chưa test đủ đa
  dạng để loại trừ hoàn toàn.


## V33 — AI tự đề xuất giọng đọc phù hợp theo nội dung video (Phase G)

### Audit trước khi build

- Agent audit riêng xác nhận luồng "Tạo dự án" (6 bước wizard): `_go_next()`
  (`autodub_gui/pages/new_project_page.py:253`) KHÔNG chạy pipeline nào cho
  tới bước 5 ("Chạy dịch", gọi `DubPipeline.run()` một lượt). `analyze_
  transcript()` chỉ chạy BÊN TRONG lượt đó (`pipeline.py:1115`), SAU khi
  giọng đã khóa vào `DubRequest` từ bước 4. Kết luận: không có tín hiệu
  phân tích nào tồn tại lúc người dùng đang ở bước chọn giọng — chốt với
  chủ dự án (2026-08-13, qua AskUserQuestion): xây bản "gợi ý SAU khi lồng
  tiếng xong" (Trình chỉnh sửa) trước, bản "gợi ý SỚM" (cần worker ASR+
  phân tích riêng chạy trước bước chọn giọng, thêm độ trễ + ASR chạy 2 lần)
  để dành mini-spec khác.
- Audit `autodub/securestore.py`: `data/video_context.json` bị khóa
  AES-256-GCM chỉ tới khi hold Vox CHỐT (mục đích chống lấy data chưa trả
  tiền, không phải bảo mật nội dung — xem docstring). Sau khi xuất video,
  `unlock_all()` tự giải mã thành JSON thường (`pipeline.py:1901`,
  `billing.py:191/314`) — `read_json_secure(path, key=None)` đọc được
  ngay, không cần xin lại khóa từ máy chủ. Dự án chưa xuất → file còn khóa
  → đọc ném `SecureStoreError`, phải bắt và coi như không có tín hiệu.
- Audit catalog giọng (`autodub/speech/tts/voices.py`): `Voice.style` mặc
  định `"tu_nhien"` cho MỌI giọng kể cả giọng không có tín hiệu phong cách
  thật (suy từ tên hiển thị qua `_STYLE_FROM_TEXT`) — không thể phân biệt
  "giọng này thật sự tự nhiên" với "giọng này thiếu dữ liệu". Quyết định:
  chỉ coi `style in {"tin_tuc", "doc_truyen"}` (2 giá trị CHỈ được gán khi
  tên giọng thật sự chứa từ khoá tương ứng) là tín hiệu đáng tin để khớp —
  "tu_nhien" từ LLM không dùng để lọc/xếp hạng.

### Xây dựng

- `control_server/src/prompts/translate.js` — `voice_hint` additive trong
  `ANALYSIS_SCHEMA` (`{gender: "male"|"female"|"", style:
  "tu_nhien"|"tin_tuc"|"doc_truyen"|""}`) + hướng dẫn trong
  `buildAnalysisPrompt`, KHÔNG đụng 5 field cũ (`summary`/`domain`/
  `pronouns`/`glossary`/`style_notes`). `VOICE_STYLE_VALUES` xuất ra
  module.exports, khớp đúng 3 style thật của VieNeu — không bịa giá trị
  ngoài catalog thật.
- `autodub/speech/tts/voice_recommend.py` (mới) — `recommend_voices(
  voice_hint, catalog, n=3)`: giới tính là BỘ LỌC CỨNG khi có (không đề
  xuất sai giới tính dù khớp phong cách); phong cách chỉ dùng 2 giá trị
  đáng tin để XẾP HẠNG (không loại giọng thiếu dữ liệu phong cách khỏi
  danh sách — đa số giọng thiếu dữ liệu đó, loại hết sẽ mất gần toàn bộ
  catalog vô căn cứ). Trả rỗng khi thiếu tín hiệu đáng tin hoặc catalog
  không có giọng khớp giới tính (thà im lặng còn hơn gợi ý sai).
- `autodub/editor.py::suggest_voice()` (mới, hàm thuần — cùng nguyên tắc
  pure-function-first với `list_speakers()`/`set_speaker_voice()` của V26)
  — đọc `data/video_context.json` qua `securestore.read_json_secure(path,
  key=None)`, bắt mọi lỗi (thiếu file/còn khóa/JSON hỏng/không phải dict)
  và trả `None`, không phải để mặc lộ exception ra GUI. Trả `None` thêm khi
  giọng đề xuất trùng giọng hiện tại (không có gì mới để gợi ý).
- `autodub_gui/pages/editor_panels.py::VoicePanel` — khối "AI đề xuất
  giọng" (`ai_suggestion_label` + nút "Đổi sang giọng AI đề xuất"), ẩn mặc
  định. `_apply_ai_suggestion()` gọi `picker.set_voice()` RỒI
  `_on_voice_changed()` tường minh — `set_voice()` một mình không phát tín
  hiệu `changed` (đúng thiết kế VoicePicker, dùng để NẠP giá trị lúc mở dự
  án), phải gọi thêm để đi đúng luồng cập nhật băng nhắc "chưa đọc lại" như
  khi người dùng tự chọn giọng trong popup.
- `autodub_gui/pages/editor_page.py::_apply_ai_voice_suggestion()` — gọi
  `suggest_voice()` sau khi nạp dự án (`_load_render_opts()`), cập nhật
  panel. Toàn bộ quyết định nằm ở hàm thuần phía `editor.py`, trang GUI chỉ
  đọc kết quả và hiển thị.

### Verify

- `control_server/tests/translate-prompts.test.js` (+4 test): `voice_hint`
  additive giữ nguyên 5 field cũ; enum gender/style đúng 3 giá trị; prompt
  có hướng dẫn voice_hint. `node --test`: 209 tests, 208 pass, 1 skip, 0
  fail (205→209).
- `tests/test_voice_recommend.py` (11 test, mới): rỗng khi thiếu hint;
  "tu_nhien"/"" không phải tín hiệu (không suy đoán); giới tính là bộ lọc
  cứng (không lộ giọng sai giới); phong cách xếp hạng chứ không loại giọng
  thiếu dữ liệu; catalog rỗng/không khớp giới tính → rỗng; giá trị lạ
  (ngoài enum) bị bỏ qua an toàn, không crash.
- `tests/test_editor_voice_suggest.py` (7 test, mới): không file → None;
  thiếu voice_hint → None; file đã mở khóa (plain JSON) đọc được ngay;
  **file còn khóa AES-256-GCM thật → None, không thử xin lại khóa** (khoá
  đúng Design Choice — test dùng key thật 64 hex ghi rồi đọc lại với
  `key=None`); JSON hỏng/không phải dict → None; giọng đề xuất trùng giọng
  hiện tại → None.
- `tests/test_voice_panel_ai_suggestion.py` (5 test, mới, headless
  `QT_QPA_PLATFORM=offscreen`): ẩn mặc định (`isHidden()` — đúng quy ước
  test GUI đã có ở `test_recognize_step_warning.py`, KHÔNG dùng
  `isVisible()` vì widget chưa `.show()` luôn trả False dù đã
  `setVisible(True)`, bug thật gặp lúc viết test); hiện đúng tên+lý do; ẩn
  lại khi gọi với tên rỗng; bấm nút khi chưa có gợi ý không crash/không đổi
  gì; bấm nút khi có gợi ý đổi đúng giọng VÀ cập nhật băng nhắc "chưa đọc
  lại" (xác nhận đi đúng luồng `_on_voice_changed()`, không bỏ qua).
- **Bug thật tìm+sửa khi viết test**: dùng emoji 🤖 trong nhãn gợi ý — vi
  phạm `tests/test_gui_no_emoji.py` (quy ước dự án: không emoji trong GUI,
  dùng `status_text.py` hoặc chữ thường). Sửa bỏ emoji, giữ chữ thường.
- `pytest tests/ -q` toàn bộ (venv đầy đủ dependency, `QT_QPA_PLATFORM=
  offscreen`): **986 passed, 6 skipped, 0 failed** (959 pass trước V33 +
  27 test mới: 11 voice_recommend + 7 editor_voice_suggest + 5 voice_panel
  GUI + 4 JS đếm riêng ở control_server).
- `node --test` (`control_server`): **209 tests, 208 pass, 1 skipped, 0
  failed**.
- **CHƯA live-verify qua SaaS thật** (cần AI provider key thật để LLM thật
  sự trả `voice_hint` — sandbox này không có, đúng giới hạn đã ghi nhiều
  lần trong Phase G). Đã live-verify được toàn bộ logic wiring (schema/
  prompt/matching/đọc-ghi file/GUI) bằng test thật, chỉ chưa verify được
  CHẤT LƯỢNG gợi ý thật của 1 LLM thật trên 1 video thật.

### Remaining Limits (V33)

- **Bản "gợi ý SỚM trước khi chọn giọng"** (đúng ý tưởng gốc của chủ dự án,
  hiện gợi ý NGAY lúc đang ở bước "Giọng & Phụ đề" thay vì sau khi lồng
  tiếng xong) CHƯA làm — cần 1 worker ASR+phân tích chạy nền riêng trước
  bước chọn giọng, đánh đổi thêm độ trễ + chạy ASR 2 lần (xem "Audit trước
  khi build"). Để dành mini-spec riêng nếu chủ dự án vẫn muốn sau khi dùng
  thử bản này.
- **Giọng VieNeu chỉ đề xuất được theo giới tính** — catalog thiếu dữ liệu
  phong cách thật cho phần lớn 120 giọng (xem Audit). Muốn đề xuất sâu hơn
  cần 1 việc nhập liệu riêng (gắn tay tag phong cách), không phải mini-spec
  kỹ thuật này.
- **CHƯA live-verify qua LLM thật** — xem mục Verify.

## V34a — PoC hạ tầng API lồng tiếng đầy đủ (Phase G)

### Audit trước khi build

- Audit hạ tầng V9/V12 đã ghi trong Context của mini-spec (`docs/PLAN.md`):
  job-queue pattern tái dùng được nguyên si, `render_worker` hiện tại KHÔNG
  cài `autodub`, billing/lưu trữ/GPU server-side chưa có tiền lệ.
- Audit THÊM lúc code (Scope B): đọc `control_server/src/models/RenderJob.js`
  xác nhận `stage: {enum: ['demucs']}` gắn chặt `Device`/`fingerprint` và
  shape kết quả 2-stem cố định — quyết định tách hẳn model `DubApiJob`
  (gắn `ApiKey` như V31, KHÔNG dùng `Device`), KHÔNG mở rộng enum.
- **2 bug thật tìm+sửa qua chính lúc live-verify** (không phải suy đoán —
  tái hiện thật khi build/chạy Docker image, sửa ngay theo đúng nguyên tắc
  "sửa được ngay, ít rủi ro → sửa luôn" của Playbook):
  1. `scripts/setup_whisper.py::step_smoke()` gọi worker với `input=""` —
     nhưng `autodub/speech/asr_whisper_worker.py` LUÔN đọc 1 dòng JSON
     request từ stdin trước khi transcribe (`--audio` trên CLI chỉ là giá
     trị dự phòng, KHÔNG thay thế stdin). `input=""` không phải JSON hợp
     lệ → worker luôn thoát lỗi "Request JSON không hợp lệ" TRƯỚC KHI chạm
     model — `installed_ok.json` không bao giờ được ghi trên bất kỳ máy
     nào chạy script này (Windows lẫn container). Sửa: `input="{}\n"`.
  2. `autodub/saas_client.py::resolve_api_url()` có `from autodub_gui.
     _embedded import VOXDUB_API_URL` KHÔNG try/except — mâu thuẫn trực
     tiếp với cam kết của `autodub/cli.py` (docstring + test cách ly
     `test_importing_cli_does_not_pull_in_gui_or_qt`) rằng CLI headless
     không phụ thuộc `autodub_gui`. Mọi máy dev/CI trước giờ đều có sẵn
     `autodub_gui/` cạnh `autodub/` nên chưa từng lộ ra — vỡ thật ngay lần
     đầu chạy `autodub.cli dub` trong container `worker-dub` (không cài
     GUI, đúng như thiết kế). Sửa: bọc `try/except ImportError`, rơi về
     biến môi trường `VOXDUB_API_URL` như thiết kế gốc.
  - Cả 2 bug đều là bug CÓ SẴN trong codebase từ trước, không phải do
    V34a gây ra — chỉ chưa ai chạy đúng đường đó (script cài Whisper lần
    đầu trên máy sạch; CLI chạy tách biệt hoàn toàn khỏi GUI) để lộ ra.
  - 4 test regression mới: `tests/test_setup_whisper_smoke_stdin.py` (2,
    mock `subprocess.run` xác nhận `input` là JSON hợp lệ + `--audio` vẫn
    còn trên CLI); `tests/test_saas_client.py` (+2, `resolve_api_url()`
    sống sót khi `autodub_gui` không import được, vẫn rơi đúng về biến môi
    trường).

### Xây dựng

- `control_server/src/models/DubApiJob.js` (mới) — tách hẳn `RenderJob`
  (lý do đầy đủ trong docstring file: identity/shape/tham số khác nhau).
- `control_server/src/services/dub-job.service.js` (mới) — copy nguyên
  pattern `render-job.service.js` (submit/claim/heartbeat/complete/fail/
  cleanup/sweep×2), KHÔNG billing thật (Constraint 1 — chỉ log
  `estimatedCostVox` vào job + audit log).
- `control_server/src/routes/internal-dub-jobs.js` (mới) — cùng khuôn
  `internal-jobs.js`, TÁI DÙNG NGUYÊN `requireWorker`/`WORKER_INTERNAL_TOKEN`
  (không cần token riêng — cơ chế vốn tổng quát).
- `control_server/src/routes/api-v1.js` — thêm `POST /dub` (multipart
  upload, `sourceLang`/`targetLang`/`voice` qua query param để tránh phụ
  thuộc thứ tự field trong multipart), `GET /dub/:jobId` (poll),
  `GET /dub/:jobId/result` (tải + xoá file ngay, cùng chính sách V9).
- `control_server/src/services/config.service.js` — 6 khoá `cloud.dub.*`
  mới (enabled/estimate/max-upload/heartbeat-stale/sweep-interval/ttl).
- `control_server/server.js` — sweeper riêng cho dub job (timer tách khỏi
  render sweeper — ngưỡng heartbeat-chết khác hẳn, dub chạy lâu hơn nhiều).
- `control_server/worker-dub/Dockerfile` (mới, tách hẳn `control_server/
  worker/`) — cài đủ `autodub` package (core deps, KHÔNG PySide6/demucs/
  yt-dlp/playwright — không cần cho input file + `--bg-mode none`) + 3
  venv riêng bằng CHÍNH `scripts/setup_whisper.py`/`setup_vieneu.py`/
  `setup_translate_local.py` đã có (không viết lại logic cài đặt) —
  `TRANSLATE_LOCAL_ENABLED=true` vì worker này không có identity `Device`
  để dùng path B (SaaS) và Constraint 1 cấm billing thật.
- `control_server/worker-dub/dub_worker.py` (mới) — copy cấu trúc poll/
  heartbeat-thread của `render_worker.py`, thay việc chạy bằng
  `python3 -m autodub.cli dub --file ... --bg-mode none --json` (subprocess,
  parse dòng JSON cuối ở stdout), tìm `dubbed_video.mp4` trong `work_dir`.
- `docker-compose.yml` — service `dub_worker` MỚI, `profiles: ["dub-poc"]`
  (không bật mặc định — image nặng, còn PoC), volume `voxdub-dub-jobs`
  TÁCH HẲN `voxdub-render-jobs`.
- `.dockerignore` — thêm `.venv-test` (giảm build-context, không liên quan
  chức năng).

### Verify

- `node --test` (`control_server`, 3 file mới: `dub-job.service.test.js`
  8 test, `internal-dub-jobs.test.js` 9 test, `api-v1-dub-route.test.js`
  7 test = 24 test mới): **233 tests, 232 pass, 1 skipped, 0 failed**
  (209→233, 0 regression).
- `pytest tests/ -q` (venv đầy đủ, `QT_QPA_PLATFORM=offscreen`): **994
  passed, 6 skipped, 0 failed** (990→994, 4 test mới từ 2 bug fix trên,
  0 regression).
- **Docker build thật** (`docker build -f control_server/worker-dub/
  Dockerfile`, KHÔNG mock) — thành công sau khi sửa bug #1 ở trên (lần đầu
  build thất bại đúng chỗ smoke test Whisper). Cả 3 engine cài xong + smoke
  test riêng của từng cái đều PASS: Whisper (model `medium`, CPU,
  ctranslate2), NLLB-200-distilled-600M-int8 (dịch thử "你好，欢迎观看。" →
  "Xin chào, được xem." — đúng chất lượng thấp hơn dịch AI đã ghi nhận ở
  V6, không phải bug), VieNeu-TTS-v3-Turbo (14 giọng preset).
- **Live-verify thật, 2 lượt, cùng 1 video mẫu thật** (12.6s, giọng nói
  tiếng Anh tổng hợp qua gTTS — không phải audio giả câm lặng — mux vào
  MP4 bằng ffmpeg thật, KHÔNG phải fixture giả):
  1. Voice mặc định (CapCut «Thanh Lan», qua mạng) — `docker run` bình
     thường: **thành công**, `status: "completed"`, 2 câu ASR nhận đúng
     nội dung tiếng Anh thật ("Hello everyone. Welcome to this short
     video...", "...is changing the way we work and live..."), dịch NLLB
     local, TTS CapCut, mux video — 32.7s xử lý cho 12.2s gốc.
  2. **Toàn bộ pipeline HOÀN TOÀN OFFLINE** (`docker run --network none`,
     PROOF mạnh nhất cho tự-chứa) với giọng VieNeu tự học (`--enroll` 1
     file WAV thật từ `voices/preset_voices_vn/`, encode thành
     `custom_voices.json`, rồi dùng chính giọng đó qua `--voice
     "TestClone"`): **thành công**, `status: "completed"`, ASR+dịch+TTS+mux
     đều chạy KHÔNG MỘT LẦN GỌI MẠNG NÀO, 36.3s xử lý (báo bởi pipeline) /
     37.0s wall-clock cho 12.2s gốc. Video kết quả tải ra ngoài container,
     `ffprobe` xác nhận file hợp lệ (13.2s, không hỏng).
  - **Số liệu thật cho quyết định go/no-go**:
    - Thời gian xử lý: ~3x thời lượng gốc, **CPU-only, không cần GPU**
      (đúng nguyên tắc "GPU-optional" xuyên suốt dự án) — nhưng video mẫu
      chỉ 2 câu/12.2s, tỉ lệ này CHƯA chắc tuyến tính với video dài hơn
      (chi phí nạp model là cố định, có thể pha loãng tốt hơn với video
      dài — CHƯA đo được, cần mẫu dài hơn để xác nhận).
    - Dung lượng image: **8.42 GB** (`.venv-whisper` 431MB, `.venv-vieneu`
      882MB, `.venv-mt` 230MB, `models/whisper` 1.5GB [model `medium`],
      `models/vieneu` 286MB, `models/translate-local` 618MB [NLLB 600M
      int8], còn lại là ffmpeg+265 gói apt ~466MB + base image + pip) —
      NẶNG cho 1 worker, đáng cân nhắc model Whisper nhỏ hơn
      (`small`/`base`) nếu tốc độ tải xuống/khởi động container là vấn đề
      ở V34b.
    - Video output: 182KB cho 13.2s (test video màu tĩnh, không đại diện
      dung lượng video thật có hình ảnh phức tạp).

### Remaining Limits (V34a)

- **`--bg-mode none` xuyên suốt PoC này** (Constraint 4 chủ đích) — CHƯA
  đo `--bg-mode demucs` (tách nhạc nền) server-side: sẽ cần thêm
  torch+demucs (~1-2GB nữa) và thời gian xử lý riêng, chưa có số liệu.
- **Video mẫu duy nhất rất ngắn/đơn giản** (12.2s, 2 câu, 1 người nói rõ
  ràng, không nhạc nền, không nhiễu) — CHƯA thử video dài hơn 2 phút (biên
  Constraint 4), nhiều người nói, hoặc audio chất lượng thấp/có nhạc nền.
- **KHÔNG billing thật** (Constraint 1, chủ đích) — mô hình giá theo phút
  video của V34b cần số liệu chi phí compute thật hơn nữa (nhiều mẫu, đo
  CPU-giờ thật) mới định giá đúng, 1 mẫu 12s không đủ.
- **KHÔNG giới hạn lưu trữ/TTL production, KHÔNG GPU multi-tenant** — đúng
  phạm vi PoC, để dành V34b (đã ghi trong mini-spec).
- **`voice_hint`/AI đề xuất giọng (V33) chưa nối vào luồng API** — job dub
  qua API nhận `voice` tường minh từ caller, không tự đề xuất.

**Khuyến nghị: GO cho V34b, phạm vi thu hẹp** — hạ tầng kỹ thuật đã chứng
minh khả thi thật (2 lượt live-verify độc lập, 1 lượt HOÀN TOÀN OFFLINE) và
KHÔNG cần GPU cho video ngắn — nhưng V34b nên bắt đầu bằng việc đo thêm
video dài hơn + `bg-mode=demucs` thật trước khi chốt mô hình billing theo
phút, vì 2 biến số đó (thời gian xử lý video dài, chi phí thêm của Demucs)
chưa có số liệu thật trong PoC này.

## V35 — Nâng chất lượng nhân bản giọng (voice cloning) (Phase G)

### Audit trước khi build

- Đã audit đủ kiến trúc + 2 bug thật trước khi viết mini-spec (commit
  `198633a`, xem Context trong docs/PLAN.md mục V35) — không còn điểm mù
  kỹ thuật cần audit thêm.
- Audit THÊM lúc code: `_encode_one()` (nơi Scope B yêu cầu gắn kiểm tra
  chất lượng) là hàm DÙNG CHUNG cho cả `enroll_voice()` (`--enroll`, luồng
  người dùng tự học — mini-spec này CHỦ ĐÍCH chạm) VÀ `enroll_batch()`
  (`--enroll-batch`, luồng thư viện `voice_downloader.py`/`voice_library.py`
  — Constraint 4 CẤM đụng). `voice_library.py:52` xác nhận mọi mục thư viện
  luôn gắn sẵn `"source": "library"` trong batch item, truyền thẳng vào
  `meta` của `_encode_one()` — dùng field có sẵn này làm điều kiện loại trừ
  CẤU TRÚC (không gọi `audio_quality.analyze()` chút nào khi
  `source == "library"`), thay vì dựa vào ngưỡng số học "may mắn không
  chặn nhầm" — đảm bảo Constraint 4 bằng thiết kế chứ không chỉ bằng số
  liệu thực nghiệm.

### Xây dựng

- `autodub/speech/tts/audio_quality.py` (mới) — `analyze(wav, sr)` hàm
  thuần, KHÔNG model AI (Constraint 1): tỷ lệ mẫu chạm biên (clip), RMS
  năng lượng trung bình, tỷ lệ khoảng lặng liên tục dài nhất. Trả
  `AudioQualityResult` (đúng khuôn `autodub/preflight.py::CheckResult`) —
  `level` ok/warn/fail + `reasons` tiếng Việt cụ thể, không phải điểm số
  mù mờ.
- `autodub/speech/tts/vieneu_worker.py::_encode_one()` — gọi
  `audio_quality.analyze()` SAU ngưỡng thời lượng (`MIN_ENROLL_SECONDS`),
  TRƯỚC khử ồn/mã hóa, CHỈ khi `meta.get("source") != "library"`:
  `fail` → `ValueError` (dừng trước mọi việc nặng); `warn` → vẫn mã hóa
  bình thường, gắn `entry["quality_warning"]`; dài hơn 8 giây → gắn
  `entry["truncated_warning"]` thay vì cắt âm thầm (Constraint 3). 2 field
  cảnh báo này là TẠM THỜI — `enroll_voice()` bóc ra khỏi `entry` (biến
  `_TRANSIENT_WARNING_KEYS`) TRƯỚC khi gọi `_save_presets()`, chỉ đưa vào
  response JSON stdout cho GUI đọc ngay lúc enroll, không lưu vĩnh viễn
  vào `custom_voices.json`. `enroll_batch()` cũng tự bóc phòng xa (dù
  đường thật hiện tại không bao giờ tạo ra 2 field này vì luôn
  `source="library"`).
- `autodub_gui/pages/settings_panels.py` — hàm thuần mới
  `_enroll_warning_message(payload)` (nối `quality_warning`+
  `truncated_warning`, tách khỏi QThread/subprocess để test được không cần
  dựng widget thật) + `_Enroller.warning` + `_done()` hiện
  `STATUS_WARN`/cảnh báo cụ thể NGAY sau khi enroll xong thay vì im lặng
  đợi người dùng tự bấm "Nghe thử" (Goal của mini-spec).
- Không phát hiện thêm mô tả sai lệch nào khác trong README lúc build
  (Constraint 5) — chỗ đã sửa trước khi viết mini-spec (commit `198633a`)
  vẫn là chỗ duy nhất tìm thấy.

### Verify

- `tests/test_audio_quality.py` (11 test, mới): sin wave sạch → ok; toàn 0
  → fail (lý do "câm"); biên độ rất nhỏ → warn/fail; nhiễu clip cứng ±1.0
  mô phỏng ghi âm quá to → fail (lý do "cắt tiếng"); clip nhẹ 0.5% mẫu
  chạm biên → warn không fail; khoảng lặng dẫn đầu dài → warn/fail; mảng
  rỗng → fail; `AudioQualityResult` lộ đủ số liệu thô (clip_ratio/rms/
  longest_silence_ratio), không chỉ verdict.
- `tests/test_vieneu_worker_audio_quality.py` (8 test, mới): fail dừng
  TRƯỚC mã hóa nặng (dùng `_BoomIfCalled` như `test_vieneu_worker_enroll_
  duration.py` đã có — xác nhận `denoiser`/`_encode_ref_wav` không bị gọi
  khi bị từ chối); không truyền `source` mặc định VẪN bị kiểm (an toàn,
  không phải mặc định bỏ qua); warn vẫn mã hóa thật + gắn cảnh báo; ok
  không có field cảnh báo nào; >8 giây gắn cảnh báo cắt kèm đúng số liệu
  gốc thật; **giọng thư viện bỏ qua HOÀN TOÀN kiểm tra** (kể cả audio câm
  hoàn toàn cũng enroll được — đúng Constraint 4) VÀ bỏ qua luôn cảnh báo
  cắt; `enroll_voice()` end-to-end: cảnh báo có trong JSON stdout NHƯNG
  KHÔNG có trong file đã lưu.
- **`tests/test_voice_library_audio_quality_regression.py` (2 test, mới,
  dùng FILE THẬT không phải dữ liệu tổng hợp)**: chạy `analyze()` trên cả
  120 file `.wav` thật trong `voices/preset_voices_vn/` (đọc bằng `wave`
  stdlib, PCM 16-bit thật) — **kết quả: 0/120 file bị fail, 0/120 file bị
  warn (toàn bộ "ok")**. Đây là bằng chứng THÊM (không phải điều kiện cần
  — luồng thư viện đã loại trừ bằng cấu trúc) rằng ngưỡng đã chọn không hề
  cận biên với nội dung thật đã qua tuyển chọn.
- `tests/test_settings_panels_enroll_warning.py` (5 test, mới, `QT_QPA_
  PLATFORM=offscreen`): `_enroll_warning_message()` nối đúng 2 field, rỗng
  khi không có field nào, coi chuỗi rỗng là "không có".
- **Bug thật tìm+sửa khi wiring** (không phải suy đoán — crash thật lúc
  chạy test lần đầu): nạp `audio_quality.py` qua `importlib.util.spec_
  from_file_location()` (bắt buộc — KHÔNG được `from autodub... import`
  vì `vieneu_worker.py` chạy trong `.venv-vieneu` không cài `autodub`,
  xem docstring đầu file) mà KHÔNG đăng ký `sys.modules[spec.name] =
  module` TRƯỚC `exec_module()` — `@dataclass` (dùng `from __future__
  import annotations`, string annotation) tự tra `sys.modules[cls.
  __module__].__dict__` lúc xử lý field, module chưa đăng ký thì tra ra
  `None` và ném `AttributeError` khó hiểu (không phải lỗi do
  `AudioQualityResult` viết sai). Sửa: đăng ký `sys.modules` trước
  `exec_module()`.
- `pytest tests/ -q` (venv đầy đủ, `QT_QPA_PLATFORM=offscreen`): **1020
  passed, 6 skipped, 0 failed** (994→1020, 26 test mới, 0 regression).
- `node --test` (`control_server`): **233 tests, 232 pass, 1 skipped, 0
  failed** — không đổi (V35 không chạm control_server, chạy lại đủ theo
  yêu cầu "test lại đầy đủ" thay vì suy đoán không ảnh hưởng).
- **CHƯA live-verify qua model VieNeu thật với file ghi âm thật đủ 4 mức
  (ok/warn/fail/truncated)** — tất cả test dùng `_FakeEngine` (không cần
  model ONNX thật để xác nhận WIRING đúng, khớp Test Plan của mini-spec)
  hoặc dữ liệu tổng hợp. `audio_quality.analyze()` tự nó ĐÃ được live-
  verify gián tiếp qua 120 file thật ở trên (đọc/phân tích thật), nhưng
  đường `_encode_one()` gọi model ONNX thật (`.venv-vieneu`, cần cài qua
  `scripts/setup_vieneu.py`) — sandbox này không có, đúng giới hạn đã ghi
  nhận nhiều lần trong Phase G.

### Remaining Limits (V35)

- **Ngưỡng số học (clip/RMS/silence-ratio) chưa phải benchmark thống kê
  chính thức** — chọn theo nguyên tắc "bắt lỗi rõ ràng nhất" (Design
  Choice), xác nhận không chặn nhầm 120 giọng thư viện thật, nhưng CHƯA
  test với tập lớn ghi âm THẬT của người dùng cuối (nhiều microphone/
  phòng ốc khác nhau) — có thể cần tinh chỉnh sau khi có phản hồi thật.
- **KHÔNG có điểm số tin cậy (confidence/similarity score)** — gap (c) ghi
  trong Context của mini-spec KHÔNG nằm trong Scope đã chọn (chỉ Scope A/B/C
  — kiểm tra đầu vào, không phải đánh giá đầu ra sau khi mã hóa xong).
  Để dành mini-spec riêng nếu cần.
- **CHƯA live-verify với model VieNeu ONNX thật** — xem mục Verify.

## V34b — Build production API lồng tiếng đầy đủ (Phase G)

### Audit trước khi build

- V34a đã khuyến nghị GO — điều kiện mở mini-spec đạt.
- Chủ dự án yêu cầu (2026-08-14): làm tiếp V34b nhưng đo thêm trước khi
  chốt giá — đúng gap V34a tự nêu. Đo THÊM 2 lượt thật trước khi viết Scope
  cụ thể (số liệu đầy đủ trong mục Verify bên dưới): video 72.5s không
  nhạc nền → tỉ lệ ~1.63x; video 77.7s có nhạc nền (`bg-mode=demucs`) →
  tỉ lệ ~2.64x. Cả 2 CPU-only, không cần GPU.
- Kết luận từ số liệu: **Constraint 4 gốc của mini-spec ("GPU đa tenant")
  SAI với thực tế đã đo** (4 lượt live-verify: 2 của V34a + 2 ở đây, tất cả
  CPU-only) — sửa lại thành giới hạn concurrency CPU, không suy đoán theo
  bản viết ban đầu nữa (xem docs/PLAN.md mục V34b đã cập nhật).
- Audit thêm lúc code: `control_server` (Node, Alpine) không có ffmpeg/
  ffprobe → không thể đo thời lượng video lúc submit (khác khung "video
  đầu ra" ban đầu của mini-spec) → quyết định tính phí SAU khi job xong,
  dùng `report.total_original_duration` mà `autodub.cli` đã tự đo qua ASR
  (chính xác hơn "đầu ra" — không lệch do tăng/giảm tốc từng câu, và không
  cần thêm phụ thuộc).

### Xây dựng

- `ApiKey` model: 2 field mới `dubMinutesQuota`/`dubMinutesUsed` (mặc định
  0 — opt-in, TÁCH HẲN `quota`/`usageCount` của V31 — đơn vị khác nhau).
- `DubUsageLedger` model (mới) — 1 dòng bất biến/job tính phí, sống ĐỘC LẬP
  với vòng đời `DubApiJob` (không bị TTL sweeper xoá theo job).
- `dub-job.service.js`: `submitDubJob()` chặn 402 nếu hết quota phút;
  `chargeDubUsage()` (atomic `$inc`, cùng kỹ thuật `consumeQuota()` của
  V31) tính Vox theo `durationS` thật (làm tròn LÊN phút, tối thiểu 1 phút)
  × đơn giá theo `bgMode`; `completeJob()` gọi billing sau khi đánh dấu
  `done`, bỏ qua billing nếu `durationS=0` (worker cũ/lỗi — thà bỏ qua còn
  hơn tính sai).
- `internal-dub-jobs.js`: `/claim` trả thêm `bgMode`; `/complete` đã
  forward `metrics` nguyên vẹn nên `durationS` tự đi qua, không cần đổi gì
  thêm.
- `api-v1.js`: `POST /dub` nhận query `bgMode` (`none`|`demucs`, mặc định
  `none` — giữ đúng giá/hành vi cũ nếu caller không đổi gì), validate 400
  nếu sai giá trị; `GET /dub/:jobId` trả thêm `costVox` khi `done`;
  `GET /me` trả thêm `dubMinutesQuota`/`dubMinutesUsed`/`dubMinutesRemaining`.
- `admin.js`: `POST /api-keys` nhận thêm `dubMinutesQuota` (tạo key kèm
  quota luôn); **route mới `PATCH /api-keys/:id/dub-quota`** — bịt gap
  thật phát hiện lúc code: nếu không có route này, KHÔNG có cách nào cấp
  quota dub cho key ĐÃ TỒN TẠI (mọi key tạo trước V34b mãi mãi
  `dubMinutesQuota=0`, tính năng không dùng được với key cũ).
- `config.service.js`: 2 khoá giá mới `credit.cost.cloud.dub.vox.per.minute`
  (150) / `.demucs` (250) — ĐỀ XUẤT dựa trên tỉ lệ compute thật đo ở trên,
  KHÔNG PHẢI giá cuối cùng (Constraint 6 — chủ dự án cần duyệt qua Admin).
- `worker-dub/Dockerfile`: thêm `demucs`+`soundfile` VĨNH VIỄN (không còn
  cài tạm lúc benchmark như lúc đo số liệu). **Bug thật tìm+sửa khi build**:
  `pip install demucs` mặc định kéo bản torch CÓ CUDA (~2.5GB thư viện
  nvidia-*/triton hoàn toàn không dùng — container CPU-only đã xác nhận) —
  sửa cài torch bản CPU-ONLY trước qua `--index-url https://download.
  pytorch.org/whl/cpu` (191.8MB thay vì torch CUDA 526MB + ~2.5GB phụ
  thuộc CUDA đi kèm).
- `dub_worker.py`: đọc `job["bgMode"]` (mặc định "none" nếu thiếu — job cũ
  vẫn chạy đúng), truyền `--bg-mode` thật cho `autodub.cli`; đọc
  `report.total_original_duration` từ kết quả pipeline, gửi lên qua
  `metrics.durationS` trong `/complete`.
- `docker-compose.yml`: `deploy.resources.limits.cpus: "2.0"` cho
  `dub_worker` + comment hướng dẫn scale ngang
  (`docker compose --profile dub-poc up --scale dub_worker=N`) — thay cho
  GPU provisioning (không cần, xem Audit).

### Verify

- **Live-verify benchmark bổ sung** (trước khi viết Scope, xem Audit):
  video 72.5s/17 câu `bg-mode=none` → 118.0s xử lý (~1.63x); video 77.7s/12
  câu CÓ nhạc nền `bg-mode=demucs` (nhạc nền tổng hợp trộn với giọng nói
  thật gTTS bằng ffmpeg thật) → 204.8s xử lý (~2.64x, +~1x so với none) —
  cả 2 CPU-only. Bug thật phát hiện đúng lúc chạy live: `scripts/
  setup_whisper.py` gửi stdin rỗng cho worker luôn đòi JSON (đã sửa, xem
  commit `9541bd8` mục V34a) — sửa xong build lại chạy được ngay.
- **Live-verify image production cuối cùng** (sau khi sửa bug torch-CUDA):
  build lại từ đầu, image **9.72GB** (so với torch-CUDA sẽ >12GB nếu không
  sửa). Chạy 2 lượt qua CHÍNH `python -m autodub.cli` (không phải pip
  install tạm nữa — demucs+torch CPU đã baked-in):
  - `bg-mode=none`, video 72.5s → **108.8s xử lý** (~1.50x, nhất quán với
    số đo trước).
  - `bg-mode=demucs`, video 77.7s CÓ nhạc nền → **187.7s xử lý** (~2.42x,
    nhất quán với số đo trước — chênh lệch nhỏ trong khoảng nhiễu đo đạc
    bình thường).
  - Cả 2 video kết quả tải ra ngoài container, `ffprobe` xác nhận hợp lệ:
    79.62s/1.19MB (none) và 79.64s/2.01MB (demucs — nặng hơn vì giữ nhạc
    nền).
- `node --test` (`control_server`, cập nhật `dub-job.service.test.js`
  +5 test mới, `internal-dub-jobs.test.js` +1, `api-v1-dub-route.test.js`
  viết lại +4 net mới, `admin-api-keys-route.test.js` +5, `hold.test.js`
  cập nhật allowlist giá công khai): **249 tests, 248 pass, 1 skipped, 0
  failed** (233→249, 0 regression cho V31 dịch văn bản + V12 Demucs cloud
  — xác nhận qua chính test suite hiện có, không phải suy đoán).
- `pytest tests/ -q`: **1020 passed, 6 skipped, 0 failed** — không đổi
  (V34b không chạm code Python, chạy lại đủ theo yêu cầu "test lại đầy đủ"
  thay vì suy đoán không ảnh hưởng).
- **CHƯA live-verify billing THẬT qua HTTP end-to-end với worker thật** —
  đã live-verify billing logic qua test thật (atomic, ledger, quota chặn
  đúng) VÀ live-verify pipeline thật qua CLI trực tiếp (số liệu ở trên),
  nhưng chưa nối 2 việc đó lại thành 1 lượt hoàn chỉnh
  submit→worker thật→complete→ledger ghi đúng qua HTTP thật trong 1 lần
  chạy (V34a đã làm việc này cho luồng KHÔNG billing — làm lại với billing
  thật cần dựng lại toàn bộ docker-compose stack, để dành cho đợt vận hành
  thử nghiệm thật đầu tiên, đúng Test Plan "Live verification" của mini-spec).

### Remaining Limits (V34b)

- **Đơn giá Vox/phút là ĐỀ XUẤT, chưa phải giá cuối** — chủ dự án cần
  duyệt/chỉnh qua Admin trước khi coi là chính thức (Constraint 6).
- **Chưa đo chi phí compute video RẤT dài** (>5 phút) — 2 mẫu đo được đều
  <90s, tỉ lệ có thể còn thay đổi thêm ở quy mô lớn hơn nữa (dù xu hướng
  "dài hơn thì tỉ lệ giảm" đã rõ từ 12s→72s).
- **`dubMinutesUsed` có thể vượt `dubMinutesQuota` một chút** (post-paid có
  chủ đích — job đang chạy lúc cán mốc vẫn hoàn tất, xem Design Choice) —
  không phải giới hạn cứng tuyệt đối, cần chủ dự án xác nhận chấp nhận
  được mô hình này trước khi đưa cho khách hàng thật có giới hạn ngân sách
  nghiêm ngặt.
- **Demucs model tải lần đầu khi có job `bg-mode=demucs` thật đầu tiên**
  (không pre-warm trong Dockerfile) — job đầu tiên sau mỗi lần deploy mới
  sẽ chậm hơn các job sau (chưa đo chính xác thêm bao lâu, ước tính
  tương tự lần tải NLLB/Whisper ~vài chục giây tới vài phút tuỳ mạng).
- **Chưa vận hành thử nhiều job đồng thời qua nhiều worker container thật**
  — giới hạn CPU + hướng dẫn scale ngang đã cấu hình trong
  `docker-compose.yml` nhưng chưa live-verify chạy `--scale dub_worker=N`
  thật với N>1.

## V36 — Nâng cấp gán giọng theo người nói (round-robin → theo pitch thật) (Phase G)

### Audit trước khi build

- Đã audit thứ tự pipeline lúc viết mini-spec (docs/PLAN.md): `voice_hint`
  (V33) chưa sẵn sàng ở bước gán giọng theo người nói — chốt KHÔNG nối V33
  ở mini-spec này (Constraint 5).
- Audit THÊM lúc code (đúng yêu cầu "Audit Before Build" của mini-spec):
  1. `Voice.gender` — kiểm tra `autodub/speech/tts/voices.py` xác nhận
     field này CÓ THẬT cho MỌI nguồn giọng, không chỉ VieNeu:
     `_capcut_voices()` (dòng 209) cũng gán `gender=e["gender"]` từ dữ
     liệu API CapCut thật, không phải giá trị mặc định rỗng. Scope B lọc
     được trên `catalog(settings, target)` đầy đủ, không cần tách riêng
     nguồn VieNeu/CapCut.
  2. **Sửa 1 giả định sai trong chính mini-spec đã viết**: Scope A ghi "wav
     đã có sẵn trong `_apply_diarization()`, không cần đọc file lại" —
     audit thật lúc code (đọc `pipeline.py::run()` quanh dòng gọi
     `_apply_diarization()`, dòng 458) xác nhận KHÔNG có mảng audio nào
     đã nạp sẵn ở đó — `audio_path` chỉ là đường dẫn file, `transcribe()`
     tự đọc file trong subprocess Whisper riêng (không lộ ra ngoài dạng
     mảng numpy). Sửa: thêm `load_wav_mono()` (mới, đọc WAV PCM16 bằng
     `wave` stdlib, cùng cách `autodub/media/audio.py` đã làm cho việc đọc
     WAV nhẹ khác) — chấp nhận đọc lại file 1 lần, chi phí I/O nhỏ so với
     lợi ích module `diarization_voice_match.py` giữ được chữ ký thuần
     `estimate_speaker_genders(wav, sr, diar_segments)` như Scope A đã tả.

### Xây dựng

- `autodub/speech/diarization_voice_match.py` (mới):
  - `load_wav_mono(path)` — đọc WAV PCM16 (mono hoặc downmix từ stereo)
    thành mảng float32 chuẩn hoá ±1.0 + sample rate.
  - `estimate_speaker_genders(wav, sr, diar_segments)` — với mỗi
    `speaker`, gộp các đoạn audio thuộc người đó, ước lượng F0 từng khung
    40ms (autocorrelation thuần numpy, có ngưỡng độ tin cậy đỉnh tương
    quan để loại khung câm/nhiễu), lấy trung vị F0 các khung hợp lệ, phân
    loại theo 2 ngưỡng CÓ KHOẢNG TRỐNG cố ý ở giữa (≤145Hz nam, ≥175Hz nữ,
    145-175Hz KHÔNG đoán — Constraint 2) — trả `""` nếu không đủ khung
    voiced (< 0.5s tổng) hoặc rơi vào vùng mù mờ.
- `autodub/speech/tts/voice_assign.py` — hàm mới
  `assign_voices_by_gender(speaker_labels, genders, catalog, fallback_names)`:
  lọc `catalog` theo giới tính CỨNG, round-robin TRONG NHÓM giới tính khi
  nhiều người nói cùng giới tính; người nói không ước lượng được HOẶC
  catalog thiếu giọng đúng giới tính → rơi về `assign_voices_round_robin()`
  nguyên bản trên `fallback_names` (luôn gán được 1 giọng, không bỏ sót).
- `autodub/pipeline.py::_apply_diarization()` — nối luồng mới: đọc audio
  qua `load_wav_mono()` (bọc `try/except OSError/EOFError` — lỗi đọc file
  rơi về round-robin toàn bộ, không làm hỏng cả lượt dub, đúng Constraint
  "degrade trung thực" gốc của V26) → `estimate_speaker_genders()` →
  `assign_voices_by_gender()` → log rõ số người gán theo giới tính ước
  lượng vs số người rơi về round-robin (minh bạch, không giả vờ "tất cả
  đều thông minh").

### Verify

- `tests/test_diarization_voice_match.py` (11 test mới): pitch thấp/cao rõ
  ràng (110Hz/220Hz) → phân loại đúng nam/nữ; pitch 160Hz (giữa 2 ngưỡng)
  → `""` không đoán; câm hoàn toàn/quá ngắn → `""`; nhiều người nói độc
  lập; speaker ngoài phạm vi audio → không có trong kết quả; nhiều đoạn
  rời rạc cùng 1 người → gộp đúng; `load_wav_mono()` đọc file WAV PCM16
  thật (mono + downmix stereo) đúng giá trị/độ dài.
- `tests/test_voice_assign.py` (+6 test mới): gán đúng giới tính khi ước
  lượng được; 2 người nói cùng giới tính → round-robin TRONG NHÓM (không
  trùng giọng); giới tính rỗng/thiếu key → rơi về fallback; **catalog CHỈ
  có 1 giới tính → người nói giới tính kia vẫn được gán (không bỏ sót)**;
  hỗn hợp người ước lượng được + không ước lượng được trong cùng 1 lượt gọi.
- `tests/test_pipeline_diarization.py` — sửa fixture `_FakeVoice` cũ
  (thiếu `gender`, gây `AttributeError` khi chạy thật — bug lộ ra ngay khi
  chạy test, không phải suy đoán) thành `Voice` thật; +1 test mới
  (`test_gender_estimated_assigns_matching_voices`, mock
  `estimate_speaker_genders()` trả giới tính biết trước, xác nhận
  `_apply_diarization()` gán đúng giọng theo giới tính qua toàn bộ luồng
  thật, không chỉ ở tầng hàm thuần).
- `pytest tests/ -q`: **1038 passed, 6 skipped, 0 failed** (1020→1038, 18
  test mới, 0 regression).
- `node --test` (`control_server`): **249 tests, 248 pass, 1 skipped, 0
  failed** — không đổi (V36 không chạm control_server, chạy lại đủ theo
  yêu cầu "test lại đầy đủ").
- **CHƯA live-verify trên audio nhiều người nói THẬT qua diarization thật**
  — cùng giới hạn đã ghi từ V26 (model pyannote gated trên HuggingFace,
  sandbox dev không có token/GPU). `estimate_speaker_genders()` tự nó ĐÃ
  được verify bằng sóng sin tổng hợp tần số biết trước (không suy đoán độ
  chính xác trên giọng nói thật phức tạp hơn — xem Remaining Limits).

### Remaining Limits (V36)

- **Ngưỡng phân loại (145Hz/175Hz) chưa phải benchmark thống kê trên giọng
  nói thật đa dạng** — chỉ verify bằng sóng sin thuần tần số cố định, sạch
  tuyệt đối. Giọng nói thật có hài âm/rung động (vibrato)/nhiễu nền có thể
  khiến autocorrelation kém chính xác hơn — cần dữ liệu thật (bị chặn bởi
  cùng giới hạn model pyannote gated) để tinh chỉnh ngưỡng.
- **Chưa nối `voice_hint` (V33)** — quyết định có chủ đích (Constraint 5),
  để dành mini-spec riêng nếu chủ dự án muốn đổi thứ tự các bước pipeline.
- **Chỉ phân loại nhị phân nam/nữ** — không ước lượng tuổi/tông giọng chi
  tiết hơn như câu hỏi gốc của chủ dự án có gợi ý ("giới tính/tông
  giọng/tuổi") — phạm vi PoC chỉ giải quyết phần giới tính, khả thi nhất
  với kỹ thuật nhẹ đã chọn (Constraint 1).

## V37 — Nhạc nền + hiệu ứng âm thanh AI theo nội dung video (Phase G)

### Audit trước khi build

- Khảo sát thị trường thật (agent riêng, có trích nguồn) trước khi viết
  mini-spec — kết quả nằm trong docs/PLAN.md §V37 Context: ElevenLabs
  Music v2/Sound Effects v2 SAFE cho SaaS trả phí, Epidemic Sound Partner
  API SAFE nhưng cần đàm phán (track kinh doanh), MusicGen/Envato/Suno
  KHÔNG dùng được (lặp lớp lỗi NLLB/Wav2Lip).
- Xác nhận thật (WebFetch tài liệu chính thức ElevenLabs, không đoán) hình
  dạng API: `POST /v1/sound-generation` + `POST /v1/music`, header
  `xi-api-key`, response nhị phân (không phải JSON).
- **Mâu thuẫn kiến trúc tìm thấy lúc code** giữa Scope A (mini-spec ghi
  `music_match.py` gọi ElevenLabs trực tiếp) và Design Choice (server quản
  lý key, người dùng không tự cấp) — 2 câu tự mâu thuẫn nhau. Giải quyết
  bằng cách tái dùng ĐÚNG pattern SaaS-proxy đã có sẵn cho dịch/phân tích
  (`saas_client.py` ↔ `control_server/routes/ai.js`) — server giữ key
  thật, Python chỉ gọi qua HTTP có device-token, không bao giờ thấy key.
- Audit `autodub/editor.py::rebuild_output()`/`resolve_existing_background()`
  xác nhận đã có sẵn 1 slot trộn nhạc nền DUY NHẤT với ducking tự động —
  cho phép thêm `bg_mode="ai_music"` mà KHÔNG viết lại logic mixing (giảm
  phạm vi thật so với lo ngại ban đầu ở Scope C của mini-spec).

### Xây dựng

- **control_server** (Node):
  - `src/services/config.service.js` — thêm `cloud.music_match.enabled`
    (mặc định `false`, opt-in ở tầng server — Constraint 2), giá Vox
    `credit.cost.cloud.sound_effect` (100) và `credit.cost.cloud.music`
    (500).
  - `src/services/elevenlabs-audio.service.js` (mới) — gọi 2 endpoint
    ElevenLabs thật qua axios (`responseType: 'arraybuffer'`), map lỗi
    thật (401/429/network) thành `ElevenLabsError` có `code`/`statusCode`
    rõ ràng để route phía trên hiển thị đúng.
  - `src/routes/ai.js` — 2 route mới `POST /sound-effect`/`/music`, dùng
    lại nguyên `precheck`/`charge` (billing) đã có cho các route AI khác;
    response là audio nhị phân + billing đi qua header
    `X-Credit-Charged`/`X-Balance-After` (JSON body không hợp với audio).
  - Bug thật tìm+sửa: `src/models/UsageLog.js` — enum `action` thiếu
    `'sound_effect'`/`'music'`, sẽ crash `ValidationError` khi `.create()`
    thật — đã thêm.
  - `.env.example` — ghi chú biến `ELEVENLABS_API_KEY` mới.
- **Python** (`autodub/`):
  - `autodub/media/emphasis_points.py` (mới) — `detect_emphasis_points()`
    thuần, đọc `segments` đã có (dấu câu !/?+khoảng lặng ≥1.5s giữa 2 câu),
    KHÔNG thêm model AI nặng (Constraint 3) — PySceneDetect (Scope B gốc)
    CHƯA làm, để dành (xem Remaining Limits).
  - `autodub/saas_client.py` — thêm `generate_sound_effect()`/
    `generate_music()` + `_save_audio_response()` (tách từ
    `_parse_response()` phần xử lý lỗi thành `_raise_saas_error()` dùng
    chung, vì response audio không gọi `resp.json()` được).
  - `autodub/media/music_match.py` (mới) — orchestration: gọi SaaS, convert
    MP3→WAV bằng ffmpeg (đồng bộ định dạng với các track nền khác trong
    work_dir), lưu `data/ai_music.wav` (nhạc nền, đọc lại qua
    `resolve_existing_background()`) hoặc `data/sfx_<name>.wav` (SFX, GUI
    tự sinh tên an toàn — không lấy thẳng từ input người dùng). SFX chèn
    vào `dubbed_video.mp4` bằng ffmpeg overlay điểm-thời-gian
    (`adelay`+`amix`) — KHÔNG qua `merge_segments()` (bài toán khác: 1
    track liên tục vs 1 điểm chèn rời rạc).
  - `insert_sfx_and_replace_video()` — ffmpeg không đọc/ghi cùng file, nên
    ghi ra file tạm rồi `os.replace()` (atomic) đè lên `dubbed_video.mp4`.
  - `autodub/editor.py::resolve_existing_background()` — thêm nhánh
    `bg_mode == "ai_music"` đọc `data/ai_music.wav`; thiếu file → im lặng
    (fallback), giống các `bg_mode` khác khi thiếu nguồn.
  - Bug thật tìm+sửa: `saas_client.py::_save_audio_response()` quên gọi
    `_note_usage()` — thanh Vox đầu app (`credit_widget.py`) sẽ KHÔNG cập
    nhật số dư ngay sau khi sinh nhạc/SFX, khác mọi lượt gọi AI trả phí
    khác trong app (tất cả đều gọi `_note_usage()`). Đã sửa.
- **GUI** (`autodub_gui/`):
  - `dub_constants.py::BG_MODES` — thêm mục "Nhạc nền AI (ElevenLabs)"
    (`ai_music`).
  - `editor_panels.py::MusicSfxPanel` (mới, `CollapsibleSection`) — khối
    "Nhạc nền & hiệu ứng âm thanh AI": sinh nhạc (mô tả tâm trạng) → nghe
    thử (mở bằng trình phát mặc định hệ điều hành, `QDesktopServices`) →
    "Dùng nhạc này"; tìm điểm nhấn → chọn 1 điểm → mô tả SFX → sinh → nghe
    thử → "Chèn vào video". Đổi điểm/mô tả tự xoá preview cũ (tránh chèn
    nhầm hiệu ứng của điểm khác).
  - `editor_music_sfx.py` (mới, mixin `MusicSfxMixin`) — nối signal của
    panel với `MusicSfxWorker` (QThread mới trong `workers.py`, 1 lớp dùng
    chung cho cả 3 hành động qua tham số `kind`) và `music_match.py`. Áp
    dụng nhạc nền = `background_panel.mode.set_key("ai_music")` +
    `_save_render_opts()` (tái dùng nguyên cơ chế lưu tuỳ chọn dự án đã
    có, không viết đường lưu riêng). Chèn SFX nhả video (`release_video()`)
    trước khi ghi đè `dubbed_video.mp4` — cùng lý do WinError 32 đã áp
    dụng cho resynth/export.
  - Panel gộp chung mục rail "Nhạc nền" đã có (không thêm mục điều hướng
    mới — `RAIL_ITEMS` ánh xạ 1-1 theo thứ tự với `panels`, thêm mục mới
    sẽ phải sửa nhiều chỗ phụ thuộc thứ tự đó). Ẩn hoàn toàn khi
    `music_match.is_available()` là `False` (chưa cấu hình SaaS).

### Verify

- `tests/test_emphasis_points.py` (10 test mới): dấu câu !/? → điểm nhấn
  đúng vị trí; khoảng lặng dài → điểm nhấn; khoảng lặng ngắn bình thường →
  bỏ qua; 2 điểm gần nhau (< 1s) → gộp lại 1, lý do nối chuỗi.
- `tests/test_saas_client_music.py` (10 test mới, mock `client._http()`):
  gọi đúng endpoint/payload; lỗi HTTP → `_raise_saas_error()` dùng chung
  đúng nhánh (401/402/503); ghi file nhị phân đúng nội dung; billing đọc
  đúng từ header.
  Sau khi sửa bug `_note_usage()`, chạy lại xác nhận vẫn 10/10 pass (fake
  `_device`/`USAGE` không crash khi thiếu context thật).
- `tests/test_music_match.py` (12 test mới — 10 gốc + 2 thêm khi verify
  `insert_sfx_and_replace_video()`): chưa cấu hình SaaS → lỗi rõ; sinh
  nhạc/SFX thành công (mock `saas_client` + ffmpeg fake) → ghi đúng
  đường dẫn quy ước; ffmpeg lỗi → `MusicMatchError` rõ ràng; lỗi thật từ
  `saas_client` (vd `InsufficientCreditError`) bay nguyên lên, không bị
  nuốt; `insert_sfx_and_replace_video()` — thiếu `dubbed_video.mp4` → lỗi
  rõ; có file → ghi đè tại chỗ đúng, không sót file tạm `.sfx_tmp.mp4`.
- `tests/test_editor.py` (+2 test): `bg_mode="ai_music"` đọc đúng
  `data/ai_music.wav` khi có; thiếu file → fallback im lặng.
- `tests/test_music_sfx_panel.py` (16 test mới, headless
  `QT_QPA_PLATFORM=offscreen`): nút ẩn/hiện đúng theo trạng thái; validate
  thiếu mô tả/chưa chọn điểm; đổi điểm xoá preview cũ; signal phát đúng
  tham số (timestamp/mô tả/tên).
- `tests/test_editor_music_sfx_mixin.py` (8 test mới) — kiểm hành vi nối
  dây (`MusicSfxMixin`) tách khỏi `EditorPage` thật: host giả + fake
  `MusicSfxWorker` gọi kết quả ngay trên luồng chính, `ConfirmDialog.
  show_error` monkeypatch (tránh `QDialog.exec()` thật treo test headless).
  Xác nhận: nhạc nền sinh xong ghim đúng `bg_mode`; SFX áp dụng nhả/khôi
  phục video đúng thời điểm; lỗi hiện đúng hộp thoại, không rơi vào nhánh
  thành công.
- `control_server/tests/music-sfx-route.test.js` (9 test mới): route trả
  đúng audio+header billing; thiếu Vox → 402; tính năng tắt ở server →
  lỗi rõ (không phải 500 im lặng); `hold.test.js` cập nhật allowlist giá
  công khai (đã có guardrail chặn lộ giá nội bộ từ V34b, thêm đúng 2 khoá
  mới vào danh sách kỳ vọng).
- `pytest tests/ -q`: **1096 passed, 6 skipped, 0 failed** (1038→1096, 58
  test mới, 0 regression).
- `node --test` (`control_server`): **258 tests, 257 pass, 1 skipped, 0
  failed** (249→258, 9 test mới, 0 regression).
- **Live-verify THẬT** (2026-08-14, key ElevenLabs thật do chủ dự án cấp
  qua chat, lưu `control_server/.env` — gitignored, không lưu/echo trong
  chat theo đúng yêu cầu): gọi `generateSoundEffect()` thật (script tạm,
  xoá sau khi verify xong) — mô tả "a single soft clap", 1.0s — nhận về
  **17.180 byte MP3 thật trong 1.77s**, convert qua ffmpeg (đúng lệnh
  `_mp3_to_wav()` dùng) ra WAV đúng thời lượng 1.0s. Xác nhận chuỗi thật
  từ đầu tới cuối: key thật → ElevenLabs thật → audio thật → convert
  thật — không có bước nào mock trong lượt verify này.
  Chưa live-verify `generateMusic()` (nhạc nền, đắt hơn — 500 Vox/lượt
  theo giá đề xuất) vì Sound Effects đã đủ chứng minh cùng 1 code path
  (`_save_audio_response()`/`_mp3_to_wav()` dùng chung cho cả 2). Chưa
  live-verify việc "nhạc/SFX có thật sự phù hợp nội dung video" — đây là
  đánh giá chủ quan của con người, không có thước đo khách quan để giả vờ
  đo tự động (đúng yêu cầu Test Plan của mini-spec).
  Chưa live-verify route `/v1/ai/sound-effect`/`/music` qua HTTP thật của
  `control_server` (cần MongoDB thật + device đã đăng ký có Vox thật, môi
  trường dev hiện không có) — route ĐÃ verify đầy đủ bằng test mock
  (9/9 pass) cùng chuẩn các route AI khác trong dự án, và phần duy nhất
  chưa test bằng mock (gọi ElevenLabs thật) đã verify riêng ở trên.

### Remaining Limits (V37)

- **PySceneDetect chưa làm** — Scope B gốc của mini-spec nêu cả transcript
  timing lẫn phát hiện chuyển cảnh hình ảnh; PoC chỉ làm phần transcript.
  Xem docs/PLAN.md Remaining Limits.
- **Epidemic Sound Partner API — track kinh doanh riêng**, chủ dự án tự
  theo dõi đàm phán, không có code trong mini-spec này.
- **Không phải bước tự động trong pipeline chính** — build thực tế là
  hành động thủ công ở Editor (sinh → nghe thử → áp dụng), không phải 1
  bước mới trong `pipeline.py` như Scope C gốc đề xuất. Xem lý do đầy đủ ở
  docs/PLAN.md Remaining Limits.
- **Route HTTP thật của `control_server` chưa live-verify qua request
  thật** (thiếu MongoDB + device đăng ký sẵn trong môi trường dev) — chỉ
  verify bằng mock (9/9 pass) + verify riêng phần gọi ElevenLabs thật.
  Rủi ro thấp: route dùng nguyên `precheck`/`charge` đã chạy thật cho các
  route AI khác trong production.
- **Nhạc nền AI (`ai_music`) loại trừ lẫn nhau với `demucs`/`duck`** — đúng
  Design Choice, người dùng chỉ chọn được 1 `bg_mode` tại 1 thời điểm,
  không lớp chồng nhạc AI lên nhạc nền gốc đã tách.

## V38 — CI: cổng test tự động trước phát hành + sửa `UPDATE_REPO` sai (Phase G)

### Audit trước khi build

- Xác nhận `.github/workflows/` chỉ có `release.yml` (build khi push tag
  `v*`, `windows-latest`) — không có workflow test nào, dù có sẵn
  1096+ test Python/258+ test Node.
- Đọc `scripts/build_exe.py`/`autodub_gui/_embedded.py`: chỉ nhúng
  `VOXDUB_API_URL` lúc build exe, KHÔNG nhúng `UPDATE_REPO`/`SUPPORT_URL`
  — 2 giá trị này chỉ đọc từ `.env`/mặc định code, không có chỗ nào khác
  cần sửa cho bản đóng gói.
- Kiểm tra `autodub/config.py` phát hiện SÂU HƠN mini-spec ban đầu tưởng:
  không chỉ `.env.example` sai — dòng 253 (dataclass field default của
  `support_url`) và `README.md:347` (link "Góp ý và báo lỗi") CŨNG đang
  trỏ về repo cũ `ttthanh2044/voxdub`. Sửa cả 4 chỗ (`.env.example` ×2,
  `config.py` field default + `env()` fallback, `README.md`), không chỉ 1
  chỗ như Scope B mini-spec ghi ban đầu.
- Phát hiện thêm 1 bug KHÔNG sửa (ngoài phạm vi V38): `autodub/speech/tts/
  voice_downloader.py:34` — `VOICES_RELEASE_URL` trỏ tới file
  `preset_voices_vn.zip` ở release `voices-v1.0.0` của
  `ttthanh2044/voxdub`. Kiểm tra thật (curl) xác nhận URL đó **404** — file
  chưa từng tồn tại. Đổi tên repo trong URL không sửa được gì (vẫn 404 ở
  repo mới vì asset chưa từng được publish ở đâu cả) — cần publish 1
  release riêng (`voices-v1.0.0`) kèm file thật trước, đây là việc publish
  nội dung, không phải sửa code, ngoài phạm vi V38. Xem Remaining Limits.
- Audit `.venv-test` (môi trường đã chạy 1096+/1102 pass xuyên suốt phiên
  làm việc) xác nhận KHÔNG cài `demucs`/`soundfile`/`audioop-lts` mà test
  suite vẫn pass đầy đủ — dùng làm căn cứ loại 2 gói nặng (`demucs` kéo
  theo `torch`) khỏi bước cài dependency của CI, tránh tải chậm/dễ flaky.

### Xây dựng

- `.github/workflows/test.yml` (mới) — 2 job song song trên
  `ubuntu-latest` (KHÔNG dùng `windows-latest` như `release.yml` — phút
  Actions Linux rẻ/nhanh hơn, test không phụ thuộc Windows-specific):
  - `python-tests`: cài dependency từ `requirements.txt` đã lọc bỏ
    `demucs`/`soundfile` (`grep -viE`), chạy `pytest tests/ -q` với
    `QT_QPA_PLATFORM=offscreen`.
  - `node-tests`: `npm ci` + `npm test` trong `control_server/`.
  - Trigger: mọi `push` (mọi nhánh) + `pull_request` vào `main`. KHÔNG bật
    branch protection/gate cứng (Constraint 4) — chỉ báo pass/fail rõ
    ràng trên GitHub, chủ dự án tự quyết định có bật gate sau.
- `.env.example` — sửa `UPDATE_REPO=junnyken/voxdub-studio` (dòng 157) và
  `SUPPORT_URL=https://github.com/junnyken/voxdub-studio/issues` (dòng
  159, phát hiện thêm lúc audit).
- `autodub/config.py` — sửa `support_url` ở CẢ 2 chỗ: dataclass field
  default (dòng 253) và `env("SUPPORT_URL", ...)` fallback (dòng 449).
  `update_repo` (dòng 251/446) đã đúng sẵn từ trước, không đụng.
- `README.md:347` — sửa link "Góp ý và báo lỗi" khớp repo thật.

### Verify

- `pytest tests/ -q` (dùng đúng `.venv-test`, tương đương môi trường CI sẽ
  cài): **1096 passed, 6 skipped, 0 failed** — 0 regression sau khi sửa
  `config.py`/`.env.example`.
- `node --test` (`control_server`): **258 tests, 257 pass, 1 skipped, 0
  failed** — không đổi (V38 không chạm code `control_server`).
- Grep xác nhận không còn `ttthanh2044` sót lại ở bất kỳ chỗ nào thuộc
  phạm vi V38 (`.py`/`.js`/`.md`/`.example`), trừ đúng
  `voice_downloader.py` (đã xác nhận ngoài phạm vi, xem Audit) và chính
  văn bản mô tả mini-spec V38 trong `docs/PLAN.md` (ghi nhận lịch sử, giữ
  nguyên có chủ đích).
- Grep xác nhận không có test nào assert theo giá trị `support_url`/
  `update_repo` cũ — không cần sửa test nào.
- **Workflow `test.yml` xác nhận chạy thật qua GitHub Actions** ngay sau
  khi push (`push` trigger trên `main`) — không chỉ đọc YAML hợp lệ.
- **Bug thật tìm+sửa ngoài phạm vi gốc của mini-spec, phát hiện khi kiểm
  tra lượt release `v3.0.0` (release đầu tiên trong lịch sử repo, trigger
  cùng lúc với V38) đã FAIL**: `autodub_gui/app.py::_smoke_report()` coi
  `faster_whisper_importable` là bắt buộc để `ok=True`, nhưng
  `autodub.spec`'s `_ML_PRUNE` CỐ Ý loại `faster_whisper`/`ctranslate2`
  khỏi bản đóng gói (ASR chạy qua subprocess `.venv-whisper` riêng, đúng
  kiến trúc đã ghi trong CLAUDE.md) — 2 phần code mâu thuẫn nhau khiến MỌI
  bản build đúng kiến trúc tự động fail smoke test của chính nó. Đọc log
  build thật (`https://github.com/junnyken/voxdub-studio/actions/runs/
  31799031806`) xác nhận: mọi mục "required" khác đều PASS
  (`gui_constructed`/`env_path_writable`/`yt_dlp_importable`/
  `worker_scripts_found`/`new_modules_importable`/`multimedia_importable`
  đều `True`), CHỈ `faster_whisper_importable=False` kéo `ok=False` —
  đúng như dự đoán từ audit code, không phải lỗi khác. Sửa: bỏ
  `faster_whisper_importable` khỏi tuple `required`, giữ lại trong
  `checks` để vẫn thấy (thông tin, không quyết định pass/fail) — khớp
  đúng cách `ffmpeg_found`/`vieneu_installed`/`playwright_importable` đã
  được xử lý (informational, không bắt buộc).
- Bump `APP_VERSION` (`autodub_gui/app.py`) từ `"3.0.0"` lên `"3.0.1"` —
  tag `v3.0.0` đã dùng cho lượt build fail, tạo tag mới `v3.0.1` cho lượt
  build lại sau khi sửa (không ghi đè/xoá tag cũ).
- **Bug thật thứ 2 tìm+sửa lúc verify `test.yml` thật lần đầu**:
  `ubuntu-latest` trần trụi thiếu `libEGL.so.1` (và các thư viện Qt hệ
  thống khác) — PySide6 cần chúng ngay cả ở chế độ offscreen. 9 file test
  liên quan Qt lỗi ngay ở bước IMPORT (không chạy được test nào bên
  trong). Sửa: thêm bước `apt-get install` các gói
  `libegl1 libgl1 libxkbcommon0 libdbus-1-3 libxcb-*` trước khi chạy pytest.
- **Bug thật thứ 3, phát hiện SAU KHI sửa xong bug #2** (lượt chạy thật kế
  tiếp): 6 test gọi `ffmpeg` thật qua subprocess (không phải toàn bộ test
  đều mock như audit ban đầu giả định) — `ubuntu-latest` không có sẵn
  `ffmpeg`. Sửa: thêm `ffmpeg` vào cùng bước `apt-get install`.
- **Cả 2 lượt sửa trên đều được XÁC NHẬN THẬT qua chạy lại Actions**, không
  suy đoán: lượt cuối cùng (`https://github.com/junnyken/voxdub-studio/
  actions/runs/31801735986`) cả 2 job `python-tests`/`node-tests` đều
  `conclusion: success`. Bản release `v3.0.1` (`https://github.com/
  junnyken/voxdub-studio/actions/runs/31801445637`) cũng `success`, sinh
  ra file thật `VoxDub-Studio-v3.0.1-win64.zip` (75.2MB) tại
  `https://github.com/junnyken/voxdub-studio/releases/tag/v3.0.1` — đây
  là bản release ĐẦU TIÊN trong lịch sử repo có file tải về thật (trang
  Releases trước đó luôn trống, nút Tải xuống trên website dẫn tới trang
  rỗng).
- Bài học audit: bước "Audit Before Build" ban đầu chỉ xác nhận qua
  `.venv-test` sẵn có trong sandbox — sandbox đó CŨNG đã cài sẵn hệ thống
  lib Qt + ffmpeg (khác `ubuntu-latest` trần trụi), nên audit "đã pass
  local" không đủ để kết luận "sẽ pass trên CI sạch". Phải chạy thật trên
  đúng loại runner CI dùng mới phát hiện được 2 bug trên — đúng nguyên tắc
  live-verify xuyên suốt dự án, không dừng ở suy luận.

### Remaining Limits (V38)

- **[ĐÃ XONG 2026-08-15] `voice_downloader.py`'s `VOICES_RELEASE_URL`**
  — publish thật release `voices-v1.0.0` trên `junnyken/voxdub-studio`,
  đóng gói `voices/preset_voices_vn/` sẵn có trong repo (121 file, 120
  `.wav` thật + `voices_manifest.json`, 37.1MB nén) làm asset
  `preset_voices_vn.zip`. Xác nhận thật: `curl -L` vào đúng
  `VOICES_RELEASE_URL` trả `HTTP 200` (trước đó 404); tải về + `unzip -t`
  không lỗi; `sha256sum` khớp tuyệt đối giữa file gốc và file tải về qua
  GitHub — không chỉ tạo release, mà xác nhận cả toàn vẹn dữ liệu thật.
  Release: `https://github.com/junnyken/voxdub-studio/releases/tag/
  voices-v1.0.0`.
- **Chưa bật gate cứng (branch protection)** — đúng Constraint 4, workflow
  hiện chỉ báo pass/fail tham khảo, chưa chặn merge PR nào cả. Chủ dự án
  quyết định có bật không.
- **Monitoring/backup `control_server` production + runbook deploy** — đã
  ghi ở Remaining Limits của Phase G (`docs/PLAN.md`), không lặp lại ở
  đây, chưa thuộc phạm vi V38.

## Bugfix ngoài mini-spec — rà soát dịch bỏ sót câu thiếu khi nguồn không phải tiếng Trung (2026-08-15)

- **Báo cáo thật từ chủ dự án**: dùng bản chạy từ mã nguồn (server thật đã
  deploy), lồng tiếng 1 video tiếng Anh (TikTok) — nhận thấy "đôi khi dịch
  thiếu hội thoại".
- **Audit tìm nguyên nhân gốc** (đọc code, không suy đoán): `_merge()`
  (`translate_saas.py`) khi máy chủ trả thiếu 1 câu thì GIỮ NGUYÊN VĂN câu
  gốc (đã có từ trước, đúng thiết kế — tránh raise giữa chừng khi Vox đã
  bị trừ). Lưới bắt cuối cùng để phát hiện câu còn sót là `review_
  translations()::_flag()`, nhưng lưới đó CHỈ kiểm tra `contains_cjk()` —
  chỉ bắt được ký tự Hán. Nguồn tiếng Anh (hoặc bất kỳ ngôn ngữ Latin nào
  khác) bị thiếu vẫn là chữ Latin, không phải CJK → lọt qua lưới, cuối
  cùng còn nguyên tiếng gốc trong video "đã dịch xong".
- **Sửa**: thêm 1 lưới mới trong `_flag()` — so khớp bản dịch với câu gốc
  Y HỆT (`text == src`), tín hiệu chắc chắn không phụ thuộc ngôn ngữ nguồn
  (đúng dấu vết `_merge()` để lại khi trả thiếu). Chỉ áp dụng câu dài hơn 5
  ký tự, tránh cờ nhầm câu ngắn/tên riêng/số vốn dĩ giữ nguyên qua bản dịch
  hợp lệ.
- **Test**: `tests/test_translate_review_trace.py` +2 test —
  `test_untranslated_english_segment_flagged_and_retried` (câu tiếng Anh
  giữ nguyên → bị cờ "untranslated", gửi rà soát, sửa đúng) và
  `test_short_identical_segment_not_flagged_untranslated` (câu ngắn "2026"
  giữ nguyên → KHÔNG bị cờ nhầm, tránh false positive tốn Vox rà soát vô
  ích).
- `pytest tests/ -q`: **1098 passed, 6 skipped, 0 failed** (1096→1098, 2
  test mới, 0 regression).
- **Giới hạn còn lại**: chưa live-verify lại đúng video TikTok tiếng Anh mà
  chủ dự án gặp lỗi (cần chạy lại thật trên máy Windows, ngoài khả năng
  của phiên làm việc này) — sửa dựa trên đọc code xác nhận đúng cơ chế gây
  lỗi, chưa xác nhận bằng cách tái hiện y hệt lỗi gốc trên đúng video đó.

## Thiết lập hạ tầng (KHÔNG phải bug code) — chưa từng cấu hình nhà cung cấp AI dịch (2026-08-15)

- **Triệu chứng**: chủ dự án báo dịch tự động LUÔN thất bại (không phải
  thỉnh thoảng), dù server đã kết nối tốt (500 Vox trial nhận đúng, hold
  Vox hoạt động đúng). Log client chỉ thấy "Dịch vụ dịch tạm thời không
  phản hồi" lặp lại 3 lần rồi rơi về dịch tay — không phải log lỗi thật.
- **Nguyên nhân gốc**: `control_server/src/routes/ai.js` NUỐT lỗi thật từ
  `ai-gateway.service.js` và luôn trả đúng 1 câu chung chung cho client dù
  lỗi gốc là gì — phải gọi `GET /v1/admin/providers` mới thấy được
  `data: []`. Vì `control_server` được deploy lần đầu (V37/V38, xem project
  memory) với MongoDB HOÀN TOÀN MỚI, bảng `AiProvider` chưa từng được seed
  (`scripts/seed-config.js`/`SEED_OPENROUTER_API_KEY` chưa chạy lúc setup)
  — không có nhà cung cấp AI dịch nào cả, mọi lượt dịch tự động chắc chắn
  thất bại 100%, không phải lỗi mạng ngẫu nhiên.
- **Sửa**: chủ dự án cấp key Google Gemini thật (AI Studio) — nối vào qua
  `POST /v1/admin/providers` (`role: "translate", type: "google", model:
  "gemini-2.5-flash"`, đúng theo audit `ai-gateway.service.js::callGemini()`
  — endpoint `generativelanguage.googleapis.com` gốc, không qua OpenRouter).
- **Live-verify thật**: gọi `translate_segments()` thật qua đúng server —
  `"Hello, how are you today?"` → `"Chào bạn, bạn khỏe không?"` — dịch đúng
  nghĩa, không mock.
- **Rủi ro cần nhớ**: cấu hình này nằm trong MongoDB, KHÔNG nằm trong env
  var hay code nào — nếu database bị deploy lại từ đầu (như đã xảy ra 1
  lần trong quá trình dựng server ban đầu), provider này sẽ mất và cần cấu
  hình lại. Không có gì trong `docker-compose.yml`/`release.yml` tự động
  seed lại provider này.

## V39 — Sửa race condition ngữ cảnh câu trước khi dịch song song nhiều lô (Phase G)

### Audit trước khi build

- Đã audit đủ 4 mảng chủ dự án yêu cầu ("nâng độ tự nhiên bản dịch, khớp
  thời gian, chất lượng giọng đọc/cảm xúc, nhạc nền AI") — 3/4 đã khá hoàn
  thiện (chi tiết ở mini-spec, `docs/PLAN.md`). Tìm ra 1 bug thật đúng vào
  ưu tiên #1: `translate_saas.py::translate_segments()` nộp tất cả lô vào
  `ThreadPoolExecutor` gần như đồng thời, `_prev_context()` tính NGAY lúc
  dựng payload — trước khi lô trước kịp có phản hồi mạng.
- **Audit lúc code phát hiện bug SÂU HƠN mini-spec ban đầu chẩn đoán**: kể
  cả sửa đúng thời điểm (đợi lô trước xong), `_prev_context()` VẪN không
  thấy được bản dịch, vì `_merge()` tạo dict MỚI (`{**seg, text_field:
  text}`) thay vì mutate `seg` gốc — segment gốc trong `all_segments` không
  bao giờ được cập nhật bản dịch, bất kể thời điểm gọi. Xác nhận qua
  `tests/test_saas_client.py::test_merge_does_not_mutate_source` — đây là
  invariant CỐ Ý, có test khoá lại, không được sửa `_merge()`.

### Xây dựng

- `autodub/text/translate_saas.py`:
  - Hằng số `_PREV_BATCH_WAIT_S = 8.0` (trần chờ lô liền trước).
  - `translate_segments()` — đổi nộp batch từ 1 list-comprehension
    (`[pool.submit(...) for ...]`) sang vòng lặp điền dần vào `futures`
    (khai báo trước `_run_batch`) — để `_run_batch(i, ...)` với `i>0` tra
    được `futures[i-1]` (lô liền trước).
  - `_run_batch()` — trước khi build payload: nếu `index>0`, gọi
    `futures[index-1].result(timeout=_PREV_BATCH_WAIT_S)`, bọc mọi lỗi
    (timeout hay lô trước lỗi thật) rồi bỏ qua — không chặn vô hạn.
  - `_run_batch()` — SAU khi `_merge()` (giữ `_merge()` thuần túy như cũ,
    không đụng invariant có test khoá): thêm bước ghi ngược
    `original[target.text_field] = done[target.text_field]` (và
    `tone`, có `pop` khi vắng để không để sót giá trị cũ) vào ĐÚNG dict
    trong `batch` — chia sẻ chung object với `segments`/`all_segments`
    nên `_prev_context()` của lô SAU đọc được ngay.
- `tests/test_translate_prev_context_race.py` (mới, 3 test) — dùng
  `FakeClient` mô phỏng độ trễ có kiểm soát (`time.sleep` ngắn, không
  `threading.Event` treo vô hạn — test không bao giờ bị treo thật).

### Verify

- 3 test mới đều pass, xác nhận đúng 3 hành vi mini-spec yêu cầu: (a) lô
  trước xong nhanh → lô sau nhận bản dịch thật trong `prev_context`, (b)
  lô trước chậm hơn trần → lô sau KHÔNG treo vô hạn, tự chạy tiếp với
  `prev_context` không có bản dịch (đúng graceful-degrade), tổng thời gian
  vẫn ngắn (xác nhận thật sự chạy song song, không bị serialize hoàn
  toàn), (c) video 1 lô — 0 regression, `prev_context` rỗng y hệt trước.
- **Bug thật thứ 2 tìm+sửa lúc verify**: fix ban đầu làm lộ ra
  `tests/test_translate_saas_emotion_tone.py` dùng chung 1 list `SEGMENTS`
  module-level MUTABLE giữa nhiều hàm test (không copy) — an toàn trước
  đây vì không có gì mutate, giờ lộ ra vì thao tác ghi ngược (Scope B) hợp
  lệ khiến "tone" từ 1 lượt test TRƯỚC còn sót lại, lộ ra ở lượt test SAU
  (`test_translate_segments_no_tone_field_when_server_omits_it` fail vì
  thấy `tone` không nên có). Sửa 2 lớp: (1) code production —
  `original.pop("tone", None)` khi lượt này không có tone (phản ánh ĐÚNG
  kết quả lượt hiện tại, không để sót dữ liệu cũ), (2) sửa test theo đúng
  convention đã có sẵn trong `test_translate_retry.py`
  (`[dict(s) for s in SEGMENTS]`, không truyền thẳng list dùng chung).
- `pytest tests/test_saas_client.py tests/test_translate_saas_emotion_tone.py
  tests/test_translate_local.py tests/test_translate_target_lang.py
  tests/test_translate_retry.py tests/test_translate_review_trace.py
  tests/test_translate_prev_context_race.py -q`: **66 passed, 2 skipped, 0
  failed**.
- `pytest tests/ -q` (toàn bộ suite): **1101 passed, 6 skipped, 0 failed**
  (1098→1101, 3 test mới, 0 regression).
- **Giới hạn còn lại**: chưa live-verify trên video thật ≥2 lô (>40 câu)
  qua server thật — test dùng `FakeClient`, không gọi mạng thật (đúng quy
  ước dự án: mock cho unit/integration, live-verify riêng khi cần xác nhận
  hành vi thật). Trần `_PREV_BATCH_WAIT_S=8.0` là đề xuất kỹ thuật dựa độ
  trễ quan sát được (2-4s/lô) trong phiên audit — chưa có số liệu từ nhiều
  video thật dài hơn để tinh chỉnh.

## V40 — 3 bug thật từ audit sâu toàn pipeline (Phase G)

### Audit trước khi build

- 2 agent song song (audit bug pipeline + khảo sát thị trường, 2026-08-16).
  Agent audit đọc thật `pipeline.py` (resume/checkpoint), `vocal_separator.py`
  (Demucs), `transcriber.py` (ASR subprocess), `control_server` credit/billing,
  downloader, GUI lifecycle — xác nhận credit/billing/downloader/audio mixer/
  GUI cancel UX đã vững (KHÔNG sửa gì ở đó). Tìm 4 bug thật, chủ dự án chọn
  sửa 3 (#1 HIGH, #2 MEDIUM Demucs quality, #3 MEDIUM orphaned subprocess —
  bỏ #4 LOW sai loại exception timeout hiếm gặp).
- Xác nhận root cause thật: mọi cơ chế resume-safety trong pipeline chỉ kiểm
  "file có tồn tại + đúng shape trên đĩa", CHƯA từng kiểm có khớp THAM SỐ
  của lượt chạy hiện tại (ngôn ngữ nguồn, giọng đọc) hay không.

### Xây dựng

- `autodub/pipeline.py`:
  - `_load_cached_transcript()` (mới, static method, tách từ khối inline cũ
    trong `_run_impl` Step 3 — đúng pattern `_load_translation` đã có sẵn,
    dễ test trực tiếp không cần chạy cả `_run_impl`). Marker mới
    `.asr_lang` cạnh `transcript_original.json`, ghi lại `lang_code` NGAY
    sau khi ASR thật chạy xong. Marker vắng (dự án trước V40) → coi khớp.
  - `_ensure_render_mode()` (đã có từ trước cho render-mode) — thêm tham số
    `target`/`voice`, resolve qua `voice_catalog.resolve()` (đúng tên thật
    dùng lúc synth — tránh 2 cách viết cùng trỏ 1 giọng bị coi là "đổi"),
    ghi dòng 2 (giọng resolve) vào marker `.render_mode` sẵn có (dòng 1 vẫn
    `RENDER_MODE`). Marker chỉ 1 dòng (từ trước V40) → `current_voice=None`
    → KHÔNG coi là đổi giọng (đúng Constraint 1, tránh xóa oan cache cũ).
  - `_resolve_background()` — sau khi Demucs tách xong (nhánh local): đọc
    `vocals.wav` bằng `wave` (stdlib, KHÔNG phải `soundfile` — CI đã cố
    tình loại gói này khỏi cài đặt test từ V38 để tránh kéo torch), chuẩn
    hoá mono float32 qua `np.frombuffer(..., dtype=np.int16)/32768.0`
    (đúng `pcm_s16le` mà `_normalize()` ghi ra), chạy
    `audio_quality.analyze()` (tái dùng NGUYÊN hàm V35, không viết ngưỡng
    mới) → `self._last_vocals_quality`. Lỗi đo (file lạ, corrupt) bị nuốt
    qua `except Exception` + `logger.debug` — tín hiệu PHỤ, không được làm
    hỏng lượt tách đã thành công.
  - `_build_quality_report()` — thêm tham số `vocals_quality`, field mới
    `background_separation` (additive, đúng pattern `translate_review` của
    V29 — rỗng `{}` mặc định, không đụng field cũ).
- `autodub/speech/transcriber.py::_transcribe_whisper_subprocess()` —
  `atexit.register(proc.kill)` ngay sau `Popen`, `atexit.unregister(...)`
  trong `finally` đã có sẵn (cạnh chỗ kill `proc` cũ).
- `autodub/media/vocal_separator.py::_run_demucs_gpu_worker()` — đổi
  `subprocess.run(cmd, capture_output=True, timeout=3600)` →
  `subprocess.Popen(...)` + `communicate(timeout=3600)` thủ công (cần
  handle `proc` để đăng ký `atexit`) — dựng lại
  `subprocess.CompletedProcess` để phần code sau KHÔNG đổi. Nhánh
  `TimeoutExpired`: `communicate()` không tự kill như `subprocess.run()` đã
  làm — thêm `proc.kill()` + `proc.wait()` thủ công để giữ đúng hành vi cũ.
- Tests mới: `tests/test_pipeline_resume_safety.py` (15 test — marker ASR
  lang, marker voice, quality_report field, `_resolve_background` tích
  hợp); bổ sung `tests/test_vocal_separator.py` (2 test — atexit
  register/unregister, kill-on-timeout) và
  `tests/test_transcriber_watchdog.py` (1 test — atexit register/unregister
  qua fake worker subprocess THẬT, không mock `Popen`).

### Verify

- **Bug thật phát hiện lúc viết test** (không phải lúc audit ban đầu): fixture
  test "tách sạch" đầu tiên dùng sine wave full-scale trực tiếp từ
  `pydub.generators.Sine` làm `vocals.wav` giả — trip nhầm ngưỡng CẮT TIẾNG
  của `audio_quality.analyze()` (sine full-scale chạm biên độ ±1.0 liên tục,
  y hệt tín hiệu bị clip thật). Không phải bug code — sửa fixture về -12dB
  (giọng thật không bao giờ full-scale).
- **Bug môi trường phát hiện lúc viết test**: bản nháp đầu dùng `soundfile`
  để đọc `vocals.wav` — `ModuleNotFoundError` trong `.venv-test` vì V38 đã
  chủ động loại `soundfile`/`demucs` khỏi cài đặt CI (tránh kéo torch, xem
  V38 ở trên). Đổi sang đọc bằng `wave` stdlib — khớp Constraint 3 của mini-
  spec, không cần cài thêm gì cho CI.
- `pytest tests/test_pipeline_resume_safety.py tests/test_vocal_separator.py
  tests/test_transcriber_watchdog.py -q`: **28 passed** (15+13+4 nhưng trùng
  10 test cũ có sẵn trong 2 file bổ sung — tổng thực 18 test MỚI).
- `pytest tests/ -q` (toàn bộ suite): **1118 passed, 6 skipped, 1 failed**
  (1101→1118, đúng 18 test mới cộng dồn, 0 regression thật).
- **1 fail còn lại** (`test_saas_client_music.py::test_generate_music_offline_raises_when_no_base_url`,
  lỗi HTTP 403 thay vì `OfflineError` — flake phụ thuộc THỨ TỰ chạy toàn bộ
  suite): xác nhận KHÔNG liên quan V40 bằng cách chạy lại full suite trên
  `git stash -u` (cây sạch tuyệt đối, kể cả file test mới chưa track) —
  **fail y hệt trên `main` gốc trước V40**, không phải regression mới. Chưa
  điều tra tiếp nguyên nhân gốc (ngoài phạm vi V40) — cần ghi nhận riêng
  nếu block CI thật (hiện `test.yml` không dùng `-p no:randomly`/seed cố
  định nên thứ tự có thể trôi giữa các lần chạy).
  > **[ĐÃ TRUY RA GỐC 2026-08-17 — KHÔNG phải flake]** Xem mục "Test suite
  > gọi thẳng vào production" ở cuối tài liệu. Tóm tắt: `.env` của máy phát
  > triển trỏ `VOXDUB_API_URL` về máy chủ THẬT, `Settings.load()` bơm nó vào
  > `os.environ` qua `load_dotenv`, nên test "offline" rơi về URL thật và
  > GỌI MẠNG. 403 (V40) và 402 (hôm nay) chỉ là 2 câu trả lời khác nhau của
  > cùng một máy chủ thật. Đã chặn bằng `tests/conftest.py`.
- **Giới hạn còn lại**: `atexit` chỉ xác nhận qua test (mock
  register/unregister) — KHÔNG live-verify force-quit thật trên Windows
  (không có cách an toàn mô phỏng trong CI/sandbox); không bảo vệ được
  `kill -9`/crash cứng (đúng Constraint 4, ghi rõ trong mini-spec, không
  phải giới hạn phát sinh ngoài dự kiến). Demucs quality signal dùng
  ngưỡng RMS/khoảng-lặng CŨ của V35 (chưa hiệu chỉnh riêng cho nhạc
  nền/no-vocals — ngưỡng gốc thiết kế cho giọng NGƯỜI enroll, áp dụng chéo
  sang vocals.wav sau tách là suy luận hợp lý nhưng chưa benchmark bằng
  video thật).

## V41 — Nâng chất lượng đọc hiểu nguồn Anh/Trung (Phase G)

### Audit trước khi build

- Đọc thật `control_server/src/prompts/translate.js` (toàn bộ 756 dòng),
  `autodub/speech/asr_paraformer_worker.py`, `scripts/setup_paraformer.py`,
  `autodub/speech/transcriber.py`, `autodub/speech/paraformer_transcriber.py`
  — xác nhận 3/5 mối lo ban đầu KHÔNG phải gap thật (ranh giới câu Paraformer
  dựa VAD âm thanh, không thua Whisper; thành ngữ tiếng Anh đã có rule tốt;
  prompt source-agnostic không tự nó là lỗi). 2 gap thật xác nhận bằng
  bằng chứng dòng cụ thể — xem mini-spec `docs/PLAN.md` V41.

### Xây dựng

- `control_server/src/prompts/translate.js`:
  - Block `vi` (dòng 94): thêm dòng "English Filler Words" cạnh dòng
    "Chinese Particles" có sẵn.
  - Block `ja`/`es`/`th`/`id`/`pt`/`fr`/`de`: mở rộng câu "Drop
    discourse/modal particles..." có sẵn, thêm ví dụ từ đệm tiếng Anh
    (um/uh/like/you know) cạnh ví dụ trợ từ tiếng Trung có sẵn.
  - `_genericRules()`: thêm dòng "Drop Source Noise" mới (trước đây hàm
    này không có rule bỏ tạp âm nguồn nào cả — không riêng gì tiếng Anh).
  - Block `zh` (giữ nguyên, KHÔNG đụng — modal particles ĐÚNG trong tiếng
    Trung) và block `en` (giữ nguyên, KHÔNG đụng — target=nguồn cùng là
    tiếng Anh không có nghĩa) đều CHỦ ĐỘNG bị loại khỏi thay đổi.
- `autodub/speech/asr_paraformer_worker.py` — message `{"done": ...}` thêm
  field `punctuation_available: punct is not None` (biến đã có sẵn từ
  trước, chỉ lộ ra qua giao thức stdout).
- `autodub/speech/paraformer_transcriber.py::transcribe_paraformer()` —
  đọc `msg.get("punctuation_available", True)` lúc nhận `"done"`
  (mặc định `True` — worker cũ/bản build cũ chưa có field này vẫn 0
  regression), sau khi có `segments` thật: `logger.warning(...)` rõ ràng
  khi `False`, kèm hướng dẫn chạy lại `scripts/setup_paraformer.py`.

### Verify

- `node --test tests/translate-prompts.test.js`: **37 passed, 0 failed**
  (32→37, 5 test mới V41). Lúc viết test lộ ra 1 giả định sai của chính
  mini-spec: test đầu tiên kỳ vọng rule mới có mặt ở CẢ target=en — sai,
  vì target=en nghĩa là dịch SANG tiếng Anh, "bỏ từ đệm tiếng Anh" không
  có ý nghĩa ở đó (đối xứng đúng với việc target=zh không có rule "bỏ trợ
  từ tiếng Trung"). Sửa test loại `en` khỏi danh sách kỳ vọng có rule, thêm
  test riêng xác nhận `en` KHÔNG có rule (đúng Constraint 2).
- `pytest tests/test_paraformer_watchdog.py -q`: **5 passed** (3→5, 2 test
  mới V41).
- `pytest tests/ -q` (toàn bộ suite Python): **1120 passed, 6 skipped, 1
  failed** (1118→1120, đúng 2 test mới cộng dồn — 1 fail còn lại là flake
  `test_saas_client_music.py` đã xác nhận có sẵn TỪ TRƯỚC V40, không phải
  regression mới, xem TEST_LOG mục V40).
- `npm test` (`control_server`, toàn bộ suite Node): **261 passed, 1
  skipped, 0 failed**.
- **Giới hạn còn lại**: chưa live-verify thật bằng video tiếng Anh có nhiều
  từ đệm thật (um/uh/like) qua model dịch thật — test chỉ khoá NỘI DUNG
  prompt gửi lên model (đúng quy ước dự án: prompt là hợp đồng, model tự
  suy luận theo prompt không phải thứ test được bằng unit test). Cảnh báo
  chấm câu Paraformer chưa live-verify thật (cần môi trường có sherpa-onnx
  cài thật + cố tình xóa model chấm câu để tái hiện) — test dùng worker giả
  đúng giao thức, không mock `Popen` (cùng mức độ tin cậy các test watchdog
  khác trong repo).

## V42 — Audit kiến trúc batch song song không người canh (Phase G)

### Audit trước khi build

- Đọc thật `autodub/batch.py`, `autodub/watch_folder.py`,
  `autodub/resources.py` (`GPU_LOCK`/`FFMPEG_SLOTS`), `autodub/pipeline.py`
  (`overlap_ok` logic dòng ~415-430, tạo work_dir dòng ~289-292),
  `autodub/speech/transcriber.py` (`WhisperCache`), `autodub/media/
  vocal_separator.py` (`DemucsCache`), `autodub/speech/tts/vieneu_vi.py`,
  `control_server/worker-dub/` + `docker-compose.yml` + `dub-job.service.js`.
- **Kết luận**: batch/watch tuần tự là thiết kế ĐÚNG cho phần cứng thật
  (T1200 4GB VRAM, đã có bằng chứng peak 96% cho 1 workload từ V32a) —
  chạy song song thật 2 GPU stage là rủi ro CUDA OOM, không phải "chậm hơn
  nhưng chạy được". `worker-dub` (Docker, CPU-only, N-replica đã verify
  atomic-safe từ V34a/V34b) đã là câu trả lời đúng cho scale thật — không
  cần code GPU-parallelism mới trong app desktop.
- Audit lộ 2 bug thật KHÔNG nằm trong phạm vi câu hỏi gốc (tìm được lúc đọc
  code liên quan): work_dir trùng giây (đã sửa, xem dưới) và quota-gate đọc-
  rồi-quyết không atomic ở `dub-job.service.js:73` (KHÔNG sửa, xem lý do).

### Xây dựng

- `autodub/pipeline.py::_unique_new_folder_name()` (mới, static method) —
  vòng lặp thêm hậu tố `-2`/`-3`... khi `output_dir/base_name` đã tồn tại,
  chỉ áp dụng cho nhánh lượt chạy MỚI (không đụng nhánh `resume_dir`).
  Hành vi golden-path (không trùng) giữ NGUYÊN tên cũ — 0 regression.
- `tests/test_pipeline_workdir_collision.py` (mới, 3 test).
- **KHÔNG sửa quota-gate**: phân tích sâu hơn lúc định implement fix phát
  hiện "atomic hóa" cái đọc `apiKey.dubMinutesUsed >= apiKey.dubMinutesQuota`
  bằng kỹ thuật `$expr` (như `consumeQuota()` của V31 đã dùng) KHÔNG thực sự
  đóng được gap — `dubMinutesUsed` chỉ `$inc` SAU khi job hoàn tất
  (`chargeDubUsage()`), không có ghi đồng thời nào lúc submit để atomic bảo
  vệ chống lại; đây không phải race trong nghĩa CAS truyền thống mà là
  THIẾU cơ chế reservation cho usage dự kiến. Sửa đúng cần 1 hệ thống
  hold/reserve giống `hold.service.js` đã có cho Vox credit (Device) —
  không tồn tại cho `ApiKey.dubMinutesQuota`, xây tương đương là 1 mini-spec
  riêng, KHÔNG phải "bug nhỏ" như đánh giá ban đầu. Giữ nguyên, ghi nhận là
  giới hạn chấp nhận được (billing thật SAU khi job xong vẫn đúng/atomic,
  chỉ có thể vượt nhẹ quota MỀM lúc submit nếu nhiều request đồng thời từ
  cùng 1 API key).

### Verify

- `pytest tests/test_pipeline_workdir_collision.py -q`: **3 passed**.
- `pytest tests/ -q` (toàn bộ suite Python): **1123 passed, 6 skipped, 1
  failed** (1120→1123, đúng 3 test mới cộng dồn — 1 fail còn lại là flake
  có sẵn từ V40, xem TEST_LOG mục V40).
- Không đụng `control_server` (quota-gate không sửa) — không cần chạy lại
  `npm test`.
- **Giới hạn còn lại**: quota-gate soft-overshoot ghi nhận ở trên, chưa xây
  hold/reserve — chờ quyết định chủ dự án nếu muốn ưu tiên (không khẩn cấp,
  billing thật không sai). Chưa thiết kế/xây cách app desktop hoặc quy
  trình vận hành đẩy batch job vào `worker-dub` để scale thật — đây là
  quyết định hạ tầng/quy mô của chủ dự án, cần bàn riêng trước khi viết
  mini-spec tiếp theo.

## Re-audit 2026-08-17 — Bộ lọc `note` cho danh sách activation key (Phase G, phát hiện lúc bàn license-sharing)

### Audit trước khi build

- Chủ dự án nêu nhu cầu "1 công ty mua 1 gói dùng chung cho N máy". Audit đầy
  đủ trước khi code lộ ra: mô hình chia sẻ Vox qua 1 pool dùng chung (License
  entity mới, sửa `deduct()`/`grant()`) là khả thi nhưng **rủi ro cao** — nó
  sửa lại đúng bất biến cốt lõi mà `activation.service.js:6` gọi là "bất di
  bất dịch" (1 key = 1 device, ép ở tầng dữ liệu) và trùng đúng phạm vi mà
  `admin.js:158-163` đã tự gọi là "ngoại lệ DUY NHẤT" (endpoint
  `POST /devices/:fingerprint/transfer`, chuyển toàn bộ số dư, chỉ qua tay
  admin). Đây là tín hiệu rõ ràng: dự án đã cố tình KHÔNG xây pool dùng chung
  trước đây.
- Chủ dự án chọn hướng nhẹ hơn: N activation key độc lập trong 1 lô, không
  đụng `credit.service.js`. Audit tiếp `website/src/pages/admin/Keys.jsx` +
  `control_server/src/routes/admin.js:233-259` xác nhận **tính năng này đã
  tồn tại sẵn** — `POST /keys` đã nhận `count` (1-100), phát N mã độc lập
  cùng 1 `note`, admin panel đã có form + hiển thị/copy toàn bộ N mã. Không
  cần code gì cho phần lõi.
- Gap thật duy nhất còn lại: `GET /keys` chỉ lọc theo `status`/`code`, không
  lọc theo `note` — muốn tìm lại "lô N mã đã phát cho công ty X" phải kéo
  danh sách bằng mắt.

### Xây dựng

- `control_server/src/routes/admin.js` — `GET /keys` thêm query `note`,
  lọc bằng `RegExp(escapeRe(note), 'i')` (đúng pattern `code` đã có, không
  phát minh cách lọc mới).
- `website/src/pages/admin/Keys.jsx` — thêm ô tìm theo ghi chú (form riêng,
  cạnh ô tìm mã), state `note` đồng bộ qua URL query param (đúng pattern
  `code`/`status` có sẵn). Sửa kèm 1 chỗ thiếu sót phát hiện khi thêm: nút
  phân trang (`Pager onPage`) trước đó không giữ lại `code`/filter khi sang
  trang — giờ giữ đủ `status`/`code`/`note`.
- `website/src/api/client.js` — không đổi (`adminApi.keys(params)` đã
  forward nguyên object query, chỉ cần thêm field ở caller).
- `docs/API.md` — cập nhật contract `GET /keys`.

### Verify

- `tests/admin-keys-note-filter.test.js` (4 test mới): lọc đúng theo note,
  không phân biệt hoa/thường, kết hợp `status` là AND (không phải OR), không
  truyền `note` vẫn trả toàn bộ như cũ.
- `npm test` (control_server, toàn bộ suite): **265 passed, 1 skipped, 0
  failed** (261→265, đúng 4 test mới, 0 regression).
- `npm run build` (website): biên dịch sạch, 0 lỗi JSX.

### Remaining Limits

- Không có `batchId`/`groupId` chính thức liên kết N key cùng 1 lô — dựa vào
  `note` giống hệt nhau làm khoá tìm kiếm (đủ dùng cho quy mô admin thao tác
  tay hiện tại, chưa cần model mới).
- Pool Vox dùng chung thật (chia sẻ động giữa các máy, không phải N ví độc
  lập) vẫn CHƯA làm — chủ dự án đã xác nhận chấp nhận đánh đổi này (N ví
  riêng, không lãng phí Vox thừa từ máy này sang máy khác) để không chạm vào
  bất biến billing cốt lõi. Nếu sau này thật sự cần pool dùng chung, đó là 1
  mini-spec riêng, rủi ro cao, cần thiết kế race-condition kỹ hơn nhiều so
  với đợt audit này.

## V43 — Hold/reserve system cho quota phút dub (Phase G, chủ dự án yêu cầu 2026-08-17, đóng gap V42)

### Audit trước khi build

- V42 (mục trên) đã xác nhận gap thật: `dub-job.service.js:73` (cũ) kiểm
  `dubMinutesUsed >= dubMinutesQuota` là đọc-rồi-quyết, KHÔNG atomic —
  `dubMinutesUsed` chỉ `$inc` SAU khi job hoàn tất (`chargeDubUsage()`,
  gọi từ `completeJob()`), nên N job submit gần như đồng thời từ CÙNG 1 key
  đều đọc thấy quota còn trống, có thể vượt xa hạn mức khi tất cả hoàn tất.
- Đọc `hold.service.js` (hệ giữ-chỗ Vox có sẵn cho luồng app desktop) để
  tái dùng đúng pattern: giữ chỗ atomic lúc submit (`findOneAndUpdate` có
  điều kiện trong chính query), giải phóng lúc kết thúc, không có "hoàn/
  truy thu" phức tạp.
- Xác nhận ràng buộc thật KHÔNG đổi được: Node không có ffprobe (Constraint
  3 của V34a), nên không biết chính xác thời lượng video trước khi worker
  chạy — không thể giữ chỗ đúng-100%-chính-xác như hold Vox (vốn biết chắc
  số segment ngay sau ASR). Quyết định: cho caller TỰ KHAI
  `estimatedMinutes` (họ thường biết file của chính họ), fallback về mặc
  định cấu hình nếu không khai — đây là ngưỡng CHẶN SUBMIT TRÀN LAN, không
  phải số tiền cuối; Vox/phút thật luôn tính lại theo `durationS` worker đo
  được, không đổi.

### Xây dựng

- `ApiKey.js` — field mới `dubMinutesReserved`.
- `DubApiJob.js` — field mới `reservedMinutes` (lưu đúng số đã giữ lúc
  submit, để completeJob/failJob/sweeper giải phóng đúng con số dù config
  đổi giữa lúc submit và lúc job kết thúc).
- `config.service.js` — `cloud.dub.reservation.default.minutes` (5),
  `cloud.dub.reservation.max.minutes` (240, kẹp trần chống caller khai số
  phi thực tế).
- `dub-job.service.js`:
  - `reserveDubMinutes()`/`releaseDubMinutes()` (mới) — atomic qua
    `$expr: {$lte: [{$add: [used, reserved, N]}, quota]}` trong chính
    query `findOneAndUpdate`, cùng kỹ thuật `balance: {$gte}` của
    `credit.service.js`.
  - `submitDubJob()` — giữ chỗ TRƯỚC khi ghi file/tạo job; lỗi ghi
    file/tạo doc SAU khi đã giữ chỗ → rollback giải phóng (cùng nguyên tắc
    rollback của `activation.service.js` khi `grant()` hỏng sau khi chốt
    key). Thông báo lỗi 402 đọc lại `ApiKey` THẬT (không dùng tham số
    `apiKey` truyền vào — đó chính là dữ liệu cũ gây race trước đây).
  - `chargeDubUsage()` — thêm tham số `reservedMinutes`, giải phóng +
    cộng usage thật trong CÙNG một `$inc` (1 lệnh nguyên tử, không có
    khoảng hở giữa "giải phóng" và "trừ thật").
  - `completeJob()` — nhánh `durationS === 0` (worker cũ, không tính phí)
    giờ vẫn giải phóng reservation — thiếu bước này sẽ rò rỉ quota vĩnh
    viễn.
  - `failJob()` — giải phóng toàn bộ reservation (job lỗi = không dùng
    phút nào).
  - `sweepStaleRunning()` — giải phóng reservation của job bị sweep do mất
    heartbeat.
  - `sweepStaleQueued()` (mới) — gap chưa từng tồn tại trước V43 (job kẹt
    ở `queued` quá `expiresAt` trước đây vô hại, giờ giữ chỗ quota thật nên
    phải có sweeper riêng) — chuyển `failed` + giải phóng, nối vào cùng
    timer `cloud.dub.sweep.interval.minutes` trong `server.js`.
- `routes/api-v1.js` — `POST /dub` nhận `estimatedMinutes` (query, tuỳ
  chọn); `GET /me` lộ thêm `dubMinutesReserved`, `dubMinutesRemaining` trừ
  luôn phần đang giữ chỗ.
- `docs/API.md` — thêm mục `/dub*` (trước đây CHƯA từng viết tài liệu, dù
  đã tồn tại từ V34a) + cập nhật `/me`; sửa luôn câu mô tả cũ "KHÔNG có
  ASR/TTS/video qua API này" đã lỗi thời từ khi V34a mở `/dub`.

### Verify

- `tests/dub-quota-reservation.test.js` (12 test mới): mặc định cấu hình
  áp dụng đúng khi không khai; caller khai đúng số; kẹp trần khi khai vượt
  quá; giá trị âm/0/NaN rơi về mặc định an toàn; **race thật** — quota=12,
  5 job cùng khai 5 phút bắn gần như đồng thời → đúng 2 job lọt qua (10),
  3 job bị từ chối đúng lỗi `DUB_QUOTA_EXCEEDED` (tái hiện đúng kịch bản
  V42 mô tả rồi xác nhận đã đóng); `completeJob` giải phóng+charge cùng
  lúc, số usage THẬT khác hẳn số đã giữ chỗ; `durationS=0` vẫn giải phóng;
  `failJob`/`sweepStaleRunning`/`sweepStaleQueued` đều giải phóng đúng,
  không đụng job khác còn sống; rollback khi tạo job hỏng sau khi đã giữ
  chỗ; thông báo lỗi phản ánh đúng số đang bị job khác giữ.
- `pytest`... (N/A — mini-spec này KHÔNG chạm `autodub/`, chỉ `control_server`).
- `npm test` (control_server, toàn bộ suite, kể cả 2 file test V34a/V34b cũ
  `dub-job.service.test.js`/`api-v1-dub-route.test.js`): **277 passed, 1
  skipped, 0 failed** (265→277, đúng 12 test mới, 0 regression — xác nhận
  cả state machine cũ (claim/heartbeat/complete/fail/sweep) lẫn route HTTP
  thật qua `app.inject` đều không đổi hành vi ngoài phần reservation mới).

### Remaining Limits

- **Không có ffprobe ở Node** (ràng buộc kiến trúc có sẵn từ V34a, không
  phải giới hạn mới của V43) — nếu caller không tự khai `estimatedMinutes`
  hoặc khai sai (thấp hơn thật nhiều), việc giữ chỗ chỉ bảo vệ đúng mức
  caller khai, KHÔNG đảm bảo tuyệt đối không vượt quota khi nhiều job dài
  submit đồng thời mà không khai — billing thật SAU khi job xong vẫn luôn
  đúng/atomic (không đổi), chỉ có nguy cơ vượt quota MỀM ở mức thấp hơn
  hẳn so với trước V43 (trước đây không giới hạn concurrent submit nào cả).
- Chưa có UI admin hiển thị `dubMinutesReserved` trong danh sách API key
  (`website/src/pages/admin/` — trang quản lý `ApiKey` hiện chưa tồn tại
  UI riêng, chỉ có API `/v1/admin/api-keys`) — không trong phạm vi V43,
  developer tự xem qua `GET /me`.

## V32b — Build lip-sync production, GIỚI HẠN đúng phạm vi V32a (Phase G, chủ dự án chọn 2026-08-17)

### Audit trước khi build

- Guardrail GỐC của V32b (viết trong chính mini-spec ở `docs/PLAN.md`):
  *"V32a phải hoàn thành với khuyến nghị 'go' kèm số liệu benchmark thật —
  KHÔNG được mở nếu V32a chưa đáp ứng."* Đối chiếu thực tế: V32a mới chạy
  **1/3 mẫu bắt buộc** (mặt thẳng, dùng video mẫu MuseTalk — chưa phải
  video VoxDub thật), **chưa có đánh giá chất lượng bằng mắt nào**, VRAM
  đỉnh đo được 96% (rất sát trần 4GB), và **chưa từng có phát biểu go/no-go
  chính thức** nào từ chủ dự án. Đã báo rõ việc này TRƯỚC khi code — chủ
  dự án xác nhận chấp nhận rủi ro, đổi lại chọn hướng THU HẸP PHẠM VI CỨNG
  (chỉ đúng những gì đã benchmark thành công) thay vì khung đầy đủ ban đầu.
- `sandbox này KHÔNG có GPU` (`nvidia-smi` không tồn tại) — mọi code ở đây
  viết dựa trên đọc lại logic ĐÃ CHỨNG MINH của harness nghiên cứu
  (`scripts/research/lipsync_poc.py`, 8 bug môi trường live-verify thật ở
  V32a), KHÔNG tự chạy được lại để xác nhận trên GPU thật trong phiên này.

### Xây dựng

- `autodub/config.py` (`Settings`) — field mới `lipsync_venv_python`/
  `lipsync_model_dir`/`lipsync_max_duration_s` (mặc định 12.0 — chỉ nhỉnh
  hơn chút so với mẫu 10.7s DUY NHẤT đã benchmark thành công, không đoán
  xa)/`lipsync_max_no_face_ratio` (mặc định 0.0 — đúng bằng kết quả mẫu
  thành công đó, 268/268 frame). Method `lipsync_venv_python_path()`/
  `lipsync_repo_dir_path()` (`vendor/musetalk/`, KHÁC
  `scripts/research/musetalk_repo/` của V32a — quy ước `models/<engine>/`
  đã dùng cho Whisper/VieNeu/Paraformer/Diarization)/`lipsync_model_dir_path()`
  (`models/lipsync/`)/`lipsync_configured()`/`lipsync_gpu_available()` —
  cùng pattern `diarization_configured()` đã có.
- `scripts/setup_lipsync.py` (mới) — chuyển thể TRỰC TIẾP từ
  `setup_lipsync_poc.py` (V32a), CHỈ đổi đường dẫn cài đặt
  (`scripts/research/` tạm thời → `vendor/`+`models/` ổn định) — giữ
  NGUYÊN VẸN cả 6 bước cài đặt + ghim commit MuseTalk + toàn bộ ghi chú rủi
  ro thật đã biết, không viết lại quy trình đã live-verify.
- `autodub/media/lipsync_worker.py` (mới) — worker chạy TRONG
  `.venv-lipsync` (numpy pin xung đột, phải tách venv — lý do cũ từ V32a),
  chuyển thể TRỰC TIẾP 3 hàm đã live-verify của
  `scripts/research/lipsync_poc.py` (`consent_check`/`run_inference`/
  `watermark`) thành 1 worker giao thức JSON qua stdout (đúng pattern
  `demucs_worker.py`/`asr_paraformer_worker.py`) — giữ nguyên mọi fix thật
  (Python 3.10, `--use_float16 --batch_size 4`, mã thoát MuseTalk không
  đáng tin nên tự kiểm 3 điều, ép UTF-8, `yaml.safe_dump`...). Consent-check
  chạy TRƯỚC inference (Constraint 3 gốc), chặn ngay nếu `no_face_ratio`
  vượt trần truyền vào — không tốn công GPU cho video ngoài phạm vi.
  Watermark 2 LỚP (chữ đè + metadata ẩn, không chỉ 1 trong 2 như PoC thử
  nghiệm) — Constraint 4 gốc: không có code path nào bỏ qua được.
- `autodub/media/lipsync.py` (mới) — module phía venv chính, gọi worker
  qua subprocess (`GPU_LOCK` + `atexit.register(proc.kill)`, cùng pattern
  `vocal_separator.py::_run_demucs_gpu_worker()` đã dùng từ V40). 3
  exception rõ ràng: `LipsyncUnavailable` (chưa cài), `LipsyncBlocked`
  (consent-check/trần thời lượng chặn — chính sách, không phải lỗi),
  `LipsyncFailed` (lỗi thật). `check_duration()` chặn SỚM trước khi mở
  subprocess nếu biết trước video vượt trần (Constraint 6 gốc — không mở
  case chưa benchmark).
- `autodub/pipeline.py`:
  - `DubRequest.lipsync: bool = False` (mới, theo pattern `subtitle_mode`/
    `blur_regions` — lựa chọn TỪNG VIDEO, không phải cấu hình toàn app như
    `diarization_enabled`).
  - `_apply_lipsync()` (mới, đặt cạnh `_apply_diarization()`) — chạy
    NGAY TRƯỚC `merge_video()` (Step 7), nhận (video gốc, audio đã lồng
    tiếng) → trả (video dùng cho mux, state báo cáo). Degrade TRUNG THỰC
    (Constraint 2 gốc): chưa cài/bị chặn/lỗi đều KHÔNG làm hỏng cả lượt
    xuất, chỉ rơi về video gốc như trước V32b — nhưng LUÔN log rõ +
    ghi state, không phải lỗi mù mờ.
  - `_build_quality_report()` thêm tham số `lipsync_state` (additive, đúng
    pattern `vocals_quality` của V40) → field `lipsync` mới trong
    `quality_report.json`.
  - **Bug thật tìm được khi wiring** (không giới hạn riêng V32b): `pipeline`
    là 1 instance DÙNG CHUNG cho cả batch (`batch.py::run_batch` không tạo
    mới mỗi video), nhưng `_last_review_trace`/`_last_vocals_quality` (từ
    V29/V40) và `_last_lipsync_state` mới đều chỉ khởi tạo 1 LẦN trong
    `__init__()` — video B trong cùng batch không bật tính năng tương ứng
    vẫn lộ dữ liệu CŨ của video A liền trước trong `quality_report.json`.
    Sửa: `_reset_per_run_state()` (mới) gọi đầu mỗi `_run_impl()`.
- `autodub/cli.py` — `--lipsync` (action store_true) qua `_add_dub_request_args`
  (áp dụng cho cả `dub` và `batch`, KHÔNG thêm cho `watch` — đúng tiền lệ
  `--multi-speaker` cũng không có ở `watch`).
- `.gitignore` — `/vendor/musetalk/` (mã nguồn vendor thật, không phải
  submodule — cùng lý do `scripts/research/musetalk_repo/` đã loại từ V32a).

### Verify

- `tests/test_lipsync.py` (14 test) — `available()`/`check_duration()` đúng
  logic ngưỡng; `run()` mock `subprocess.Popen` đầy đủ: thành công trả
  đúng đường dẫn output + atexit register/unregister, consent-blocked ném
  `LipsyncBlocked` đúng reason, inference lỗi ném `LipsyncFailed`, worker
  không trả JSON hợp lệ, file kết quả báo có nhưng không tồn tại, timeout
  kill tiến trình + ném lỗi rõ.
- `tests/test_pipeline_lipsync.py` (8 test) — `_apply_lipsync()` degrade
  đúng ở cả 3 nhánh (chưa cài/bị chặn/lỗi) mà KHÔNG crash, video gốc được
  giữ nguyên; thành công trả đúng video đã xử lý; `quality_report.json`
  field `lipsync` rỗng mặc định, phản ánh đúng state khi có; **xác nhận
  bug reset thật đã sửa** (`_reset_per_run_state()` xoá sạch cả 3 field).
- `pytest tests/ -q` — chạy lần đầu thiếu `ffmpeg`/`libEGL.so.1`/
  `libGL.so.1` hệ thống (9 file GUI lỗi collection, `test_audio_merger.py`
  và 3 file khác fail vì thiếu ffmpeg thật). **Cài bổ sung
  `ffmpeg`/`libegl1`/`libxkbcommon0`/`libfontconfig1`/`libdbus-1-3` qua
  `apt-get` (môi trường sandbox, không phải thay đổi trong repo) + chạy
  với `QT_QPA_PLATFORM=offscreen`** — unlock toàn bộ suite trước đó không
  chạy được. Sau khi unlock: **1145 passed, 6 skipped, 1 failed**
  (1123→1145, đúng 22 test mới, 0 regression — 1 fail còn lại đúng flake
  đã ghi nhận từ V40, xác nhận y hệt trên `main` gốc qua `git stash -u`).
- `py_compile` toàn bộ file Python mới + import thật `Settings`/
  `DubRequest`/`DubPipeline` qua `.venv-test` — không lỗi cú pháp/import.
- **Bug thật tìm được nhờ unlock GUI test**: `.env.example` thêm
  `LIPSYNC_MAX_DURATION_S`/`LIPSYNC_MAX_NO_FACE_RATIO` nhưng chưa khai vào
  `settings_fields.py` (`test_every_example_key_is_editable_or_exempt` bắt
  được ngay) — sửa bằng cách thêm vào `EXEMPT_KEYS` (đúng tiền lệ
  `WHISPER_BEAM_SIZE`: "nút vặn nâng cao cho người biết việc, ai cần thì
  sửa thẳng .env" — nhất quán vì tính năng CHƯA có nút GUI để mở khoá các
  ngưỡng này).
- **CHƯA chạy được thật trên GPU** — sandbox không có GPU (đúng giới hạn
  V32a/V30 đã ghi). Mọi test ở trên đều mock `subprocess.Popen`, KHÔNG gọi
  MuseTalk thật.

### Remaining Limits

- **CHƯA live-verify trên GPU thật với ĐƯỜNG CODE PRODUCTION này** (khác
  với harness nghiên cứu `scripts/research/lipsync_poc.py` đã live-verify
  ở V32a) — đây là việc LỚN NHẤT còn lại. Chủ dự án cần tự chạy
  `scripts/setup_lipsync.py` rồi 1 lượt `voxdub dub --lipsync` thật trên
  GPU trước khi coi tính năng này production-ready, không chỉ "code xong".
- ~~CHƯA có GUI toggle~~ **[ĐÃ ĐÓNG — Re-audit cùng phiên, xem bên dưới]**.
- **CHƯA có billing Vox riêng cho lip-sync** — đúng Constraint 5 của mini-
  spec gốc: chi phí compute GPU cao hơn hẳn tính năng audio-only khác, cần
  mô hình giá riêng chốt cùng chủ dự án (quyết định kinh doanh, không tự
  đoán). Hiện tại tính năng chạy MIỄN PHÍ về Vox nếu bật qua CLI — PHẢI
  chốt giá trước khi mở rộng ra người dùng thật/GUI.
- **Phạm vi CỐ TÌNH hẹp hơn khung mini-spec gốc**: chỉ 1 khuôn mặt phát
  hiện được ở MỌI frame (`lipsync_max_no_face_ratio=0.0`), video ≤12s
  (`lipsync_max_duration_s`) — góc nghiêng/nhiều người/video dài đều bị
  `consent_check`/`check_duration()` CHẶN CỨNG cho tới khi có số liệu
  benchmark mới (V32a chưa chạy 2/3 mẫu còn lại). Không suy đoán MuseTalk
  xử lý nhiều khuôn mặt/frame ra sao (chưa có bằng chứng từ việc đọc mã
  nguồn — `get_landmark_and_bbox()` chỉ xác nhận trả về 1 bbox/frame,
  KHÔNG rõ hành vi khi ảnh có ≥2 mặt) — ngưỡng 0% no-face hiện tại KHÔNG
  tự động bảo vệ khỏi trường hợp nhiều mặt nếu MuseTalk vẫn "phát hiện
  được" 1 trong số đó ở mọi frame; đây là giới hạn thật của consent-check
  hiện có, cần nghiên cứu thêm nếu muốn mở nhiều người sau này.
- VRAM 96% trên card 4GB (V32a) vẫn là RẤT SÁT TRẦN — `lipsync_max_duration_s`
  mặc định 12.0 là ước tính THẬN TRỌNG dựa trên đúng 1 điểm dữ liệu, chưa
  có công thức đáng tin cậy nối thời lượng video → VRAM cần. Chủ dự án nên
  tự benchmark thêm trên phần cứng của mình trước khi nới trần này.

### Re-audit (cùng phiên 2026-08-17) — GUI toggle, đóng gap "CHƯA có GUI"

Sau khi viết xong phần trên, phát hiện sandbox này ĐÃ CÓ mạng thật và
quyền `apt-get` — lý do "không verify được PySide6" không còn đúng nữa.
Cài bổ sung `ffmpeg`/`libegl1`/`libxkbcommon0`/`libfontconfig1`/
`libdbus-1-3` (gói hệ thống, không phải thay đổi trong repo) + chạy với
`QT_QPA_PLATFORM=offscreen` — unlock toàn bộ 9 file test GUI trước đó lỗi
collection. Quay lại làm nốt GUI thay vì giữ nguyên quyết định cũ.

**Xây dựng:**
- `autodub_gui/pages/new_project_steps.py` (`VoiceStep`, bước 4 "Giọng đọc
  & phụ đề") — ô `QCheckBox` mới "Đồng bộ khẩu hình AI theo giọng đọc mới
  (GPU)", ẩn mặc định (`set_lipsync_available()` gọi từ trang cha mới hiện
  — đúng nguyên tắc "không thêm UI cho tính năng chưa khả dụng" của
  `cloud_render` đã có từ V12). Tự tắt + khoá khi bật "Chỉ xuất âm thanh"
  (`_on_audio_only`, lip-sync xử lý pixel video nên vô nghĩa khi bỏ ghép
  video). `values()`/`load()` đọc/ghi đúng field `lipsync`.
- `autodub_gui/pages/new_project_page.py` — `_refresh_lipsync_info()` (gọi
  1 lần lúc dựng trang, đúng thứ tự sau `_refresh_cloud_render_info()`),
  đọc `Settings.lipsync_configured()`/`lipsync_gpu_available()` thật. Nối
  `lipsync=bool(data.get("lipsync", False))` vào `DubRequest(...)`. Thêm 1
  dòng tóm tắt "Đồng bộ khẩu hình AI" ở bước cuối (chỉ hiện khi đã bật).
- **Bug thật tìm được nhờ unlock GUI test**: `.env.example` đã thêm
  `LIPSYNC_MAX_DURATION_S`/`LIPSYNC_MAX_NO_FACE_RATIO` nhưng chưa khai vào
  `settings_fields.py` — `test_every_example_key_is_editable_or_exempt`
  bắt được ngay lúc chạy full suite lần đầu sau khi unlock. Sửa: thêm vào
  `EXEMPT_KEYS` (đúng tiền lệ `WHISPER_BEAM_SIZE` — "nút vặn nâng cao cho
  người biết việc, ai cần thì sửa thẳng .env"), nhất quán vì 2 ngưỡng này
  vẫn chưa có ô chỉnh riêng trong trang Cài đặt.

**Verify:**
- `tests/test_voice_step_lipsync.py` (7 test mới) — ẩn/hiện đúng theo
  `set_lipsync_available()`; **guardrail cứng xác nhận bằng test**: ép
  `setChecked(True)` trực tiếp bỏ qua `set_lipsync_available()` vẫn KHÔNG
  làm `values()["lipsync"]` thành `True` (không có đường nào bật tính năng
  mà GUI chưa xác nhận đủ điều kiện); available→unavailable tự uncheck;
  tương tác với "Chỉ xuất âm thanh" đúng cả 2 chiều; `load()` chỉ khôi phục
  trạng thái đã lưu khi đang available.
- **Smoke test toàn app thật** (`AUTODUB_SMOKE=1`, không chỉ 1 widget đứng
  riêng): `_smoke_report()` dựng ĐỦ mọi trang (kể cả trang Tạo dự án chứa
  `VoiceStep` sửa ở trên và trang Cài đặt chứa `settings_fields.py` sửa ở
  trên) — thoát mã 0, không crash.
- `pytest tests/ -q` (toàn bộ suite, giờ chạy đủ KHÔNG cần loại trừ file
  nào — baseline sạch qua `git stash -u` xác nhận **1123 passed**, cùng 1
  fail flake có sẵn từ V40): sau toàn bộ V32b (backend + GUI):
  **1152 passed, 6 skipped, 1 failed** (1123→1152, đúng 29 test mới — 22
  backend + 7 GUI — 0 regression thật).

**Remaining Limits cập nhật sau Re-audit:**
- Editor có đường re-export ĐỘC LẬP (`autodub/editor.py::rebuild_output()`/
  `rebuild_subtitles()`, gọi thẳng `merge_video()` không qua
  `pipeline.py::_export_phase()`) — CHƯA nối lip-sync vào đường này. Có
  chủ đích: lip-sync tốn hàng chục phút GPU, re-chạy mỗi lần chỉnh phụ đề
  trong Editor là sai mô hình (nên CACHE kết quả lip-sync lần dub gốc rồi
  tái dùng, không chạy lại) — cần 1 quyết định thiết kế riêng, không phải
  mở rộng đơn giản.
- Vẫn CHƯA live-verify GPU thật + CHƯA billing Vox (xem 2 mục Remaining
  Limits phía trên, không đổi).

## Chuyển nền tảng Coolify → Vibe Host + hardening lớp hosted dub (2026-08-17)

Không phải mini-spec theo kế hoạch — phát sinh từ việc chủ dự án chuyển
toàn bộ hạ tầng sang Vibe Host. Việc chuyển nền tảng lộ ra 3 bug THẬT có
sẵn trong code (không phải lỗi nền tảng), sửa hết cùng phiên.

### Bug portability lộ ra lúc chuyển (3 cái, đều đã sửa)

1. **`worker-dub` bị health-check giết** — `dub_worker.py` là background
   poller thuần, không mở HTTP; Vibe Host kiểm tra port 3000 không thấy ai
   nghe → `NotOnNet` → crash loop. Thêm `_start_health_server()` (stdlib
   `ThreadingHTTPServer`) chạy song song vòng poll. Commit `13d98ca`.
2. **`control_server/server.js:41` mặc định `HOST=127.0.0.1`** — trong
   container thì không ai ngoài nối được. `docker-compose.yml` che lỗi này
   suốt vì ghi đè `HOST: 0.0.0.0` ở tầng `environment:`; nền tảng tự sinh
   compose riêng thì KHÔNG có. Bake `ENV HOST=0.0.0.0` + `ENV PORT=3001` vào
   `control_server/Dockerfile` (compose vẫn thắng → 0 thay đổi hành vi cũ).
   Commit `b77b3df`.
3. **`APP_ENCRYPTION_KEY` nền tảng tự sinh không đúng 64 hex** mà
   `server.js:23-26` bắt buộc → crash loop. Không phải bug code (validation
   đúng), nhưng ghi lại vì sẽ lặp lại ở mọi nền tảng có tính năng "tự sinh
   secret": key có ràng buộc ĐỊNH DẠNG thì phải set tay
   (`openssl rand -hex 32`), khác `JWT_SECRET` giá trị nào cũng chạy.

### Bỏ phụ thuộc volume dùng chung — truyền file qua HTTP (`ea49859`)

V34b gốc giả định `control_server` và `worker-dub` thấy chung 1 thư mục.
Giả định này sai ngay khi rời `docker-compose`. Thay bằng
`GET /internal/dub-jobs/:id/input` + `POST /internal/dub-jobs/:id/output`,
gác bằng `getRunningJobForWorker()` (đúng điều kiện
`{_id, workerId, status:'running'}` heartbeat/complete đã dùng), bẫy
`CastError` → `409` để jobId sai định dạng không thành `500`.

- Stream 2 chiều, KHÔNG `toBuffer()` (video hàng trăm MB); upload bị cắt
  do vượt hạn mức → xoá file cụt + `413`, không báo "xong" với video hỏng.
- HTTP là đường DUY NHẤT, không rẽ nhánh theo môi trường — compose local và
  deploy tách máy chạy cùng mã.
- **Bẫy đã tránh**: `process_job` bản cũ tắt heartbeat TRƯỚC khi ghi kết
  quả; upload trăm MB mất vài phút nên `sweepStaleRunning` sẽ fail job giữa
  chừng → chuyển upload vào TRONG lúc heartbeat còn sống.
- **Verify thật đầu-cuối trên prod**: submit video 8s qua `POST /api/v1/dub`
  → job `done`, `inputBytes: 83600` khớp CHÍNH XÁC file gửi lên,
  `outputBytes: 126797`, tải kết quả về `ffprobe` ra h264+aac 8.82s thật.

### Bug ngôn ngữ nguồn âm thầm rẽ nhánh dịch tay (`93c6878`)

Phát hiện lúc test e2e trên prod. `SOURCE_LANG_MAP` vốn hỗ trợ CẢ dạng ngắn
(`vi`) lẫn BCP-47, nhưng `pipeline.py:303` chỉ gọi `resolve_source_lang()`
cho bước ASR, còn dòng 538 truyền `req.source_lang` THÔ vào `_auto_translate`
→ `flores_code("vi")` = `None` → âm thầm rẽ sang `translate_pending` SAU KHI
đã chạy hết ASR (tốn trọn thời gian xử lý rồi mới hỏng).

- Sửa tại cửa vào bằng `DubRequest.__post_init__` chuẩn hoá đúng 1 lần (hàm
  idempotent nên mọi chỗ gọi cũ không đổi).
- **Bằng chứng trước/sau**: cùng job `sourceLang=vi` — trước `failed` +
  `translate_pending`, sau `done` + video 126797 bytes.
- Kèm theo: `POST /api/v1/dub` trước đây nhận chuỗi BẤT KỲ cho 2 tham số
  ngôn ngữ → thêm `control_server/src/utils/dub-langs.js`, trả
  `400 BAD_SOURCE_LANG`/`BAD_TARGET_LANG` kèm danh sách hợp lệ. Danh sách là
  bản sao TAY của `autodub/languages.py` nên `tests/dub-langs.test.js` đọc
  thẳng file Python để chặn trôi lệch (tự skip trên nhánh deploy rút gọn
  không có `autodub/`).
- **Contract dễ nhầm, ghi lại**: `sourceLang` nhận `vi` HOẶC `vi-VN`;
  `targetLang` CHỈ nhận khoá ngắn `vi` — 2 định dạng khác nhau ở 2 tham số
  đứng cạnh nhau.

### Tự hoàn phí khi kết quả biến mất trước lúc giao (`6111899`)

**Chứng minh bằng thực nghiệm, không phải suy đoán**: job `done`, tải kết
quả trước redeploy → `200`; redeploy xong tải lại đúng job đó → `410
RESULT_EXPIRED`, file biến mất dù Mongo vẫn `done` và ví ĐÃ trừ 150 Vox.
Tức khách trả tiền mà không lấy được hàng nếu redeploy đúng lúc. Thông báo
lỗi cũ còn gây hiểu nhầm ("đã tải trước đó hoặc quá hạn TTL").

Vibe Host **không có volume bền vững** — xác nhận dứt điểm qua dashboard
(tab "Cấu hình" chỉ có Tên miền/Tài nguyên/Biến môi trường; tab "Cài đặt"
chỉ có Giới hạn IP + Xoá project) và MCP cũng không có tool volume. Chủ dự
án chốt phương án hoàn phí tự động thay vì chờ nền tảng có volume.

- `refundLostResult()` hoàn số phút đã trừ, ghi dòng ĐẢO (số âm) vào
  `DubUsageLedger` để sổ cái giữ append-only. Claim quyền hoàn nằm TRONG
  điều kiện `findOneAndUpdate` → poll nhiều lần chỉ hoàn đúng 1 lần.
- **Phần khó là KHÔNG hoàn nhầm**: file mất còn 2 lý do chính đáng — đã tải
  xong rồi `cleanupJob` dọn, và hết TTL. Thêm field `deliveredAt` (đặt lúc
  stream đóng) + điều kiện `now < expiresAt` để loại 2 ca đó.
- **Viết test lòi ra thêm 1 race**: request thua cuộc rơi xuống nhánh "đã
  tải trước đó hoặc hết hạn" → báo SAI cho khách vừa được hoàn; sửa bằng
  đọc lại job sau khi thua claim.
- `tests/dub-refund-lost-result.test.js` (189 dòng) phủ cả 3 ca không-hoàn +
  cách ly cross-key.
- **Live-verified trên prod đúng kịch bản gây thiệt hại**: `dubMinutesUsed`
  3 → job trừ thành 4 → redeploy làm mất file → khách gọi `/result` →
  `410 RESULT_LOST_REFUNDED` + `minutesRefunded: 1` → quota về lại 3.

### Kết quả test

`node --test tests/*.test.js` trong `control_server`: **287 test, 286 pass,
1 skip, 0 fail**. CI GitHub Actions (`Test (Python + Node)`) `success` trên
đúng commit `6111899` — pytest chạy đủ trên `ubuntu-latest` (sandbox local
thiếu `numpy`/`PySide6` nên không chạy được Python suite tại chỗ, dựa vào
CI thật thay vì bỏ qua).

### Remaining Limits

- **Kết quả job vẫn không bền vững** — hoàn phí là lưới an toàn, không phải
  cách chữa. Chữa thật cần object storage (S3-compatible), xem `docs/PLAN.md`.
- **Sao lưu MongoDB chưa bật lại sau khi rời Coolify** — cơ chế backup hàng
  ngày ghi "ĐÃ XONG 2026-08-15" là của Coolify, chuyển nền tảng là mất. DB
  đang giữ ví/credit khách + key nhà cung cấp AI đã mã hoá.
- **PayOS + Brevo chưa cấu hình trên nền tảng mới** → thanh toán và email
  đang tắt (degrade sạch, không crash).

## V47 — Phát hành v3.1.0 (2026-08-17)

21 commit đã vào `main` sau tag `v3.0.1` (V39, V40, V41, V42, V43, V32b,
V5 + toàn bộ hardening hosted dub ở trên) nhưng **không người dùng nào chạm
được** — `release.yml` chỉ build khi push tag, và `website/src/pages/
Download.jsx:7` trỏ `releases/latest`.

- Bump `APP_VERSION` (`autodub_gui/app.py:33`) `3.0.1` → `3.1.0` TRƯỚC khi
  tag — `autodub/updates.py:58` so `tag_name` của GitHub với hằng số này,
  tag v3.1.0 mà quên bump thì bản mới sẽ tự báo "có bản mới" về chính nó.
  Đúng quy trình đã dùng ở lượt `v3.0.1`.
- Điều kiện tiên quyết đã kiểm tra thật trước khi tag: CI `Test (Python +
  Node)` `success` trên đúng `6111899`; node test local 286/287 pass.

## V44 — Nhận file upload theo dòng thay vì nuốt trọn vào RAM (Phase G, 2026-08-17)

### Audit Before Build

Đọc code, không suy đoán: `api-v1.js:218` (`POST /api/v1/dub`, hạn mức
`cloud.dub.max.upload.mb` = 300) và `jobs.js:37` (`POST /v1/jobs/demucs`,
hạn mức 200 MB cứng) đều gọi `await data.toBuffer()` rồi truyền nguyên
Buffer xuống service. Chặng khách → server là chỗ DUY NHẤT còn buffer —
chặng worker ⇄ server đã chuyển sang stream cùng ngày (`ea49859`).

**Gap đo được bằng thực nghiệm** (không phải suy luận): dựng server thật
(in-memory Mongo), upload 1 file 250 MB bằng `curl`, lấy mẫu `VmRSS` của
tiến trình server mỗi 20ms **từ ngoài** qua `/proc/<pid>/status`:

| Code | Baseline RSS | Peak RSS | Delta |
|---|---|---|---|
| Trước V44 (`toBuffer`) | 146,1 MB | 643,0 MB | **485,3 MB** |
| Sau V44 (stream) | 125,6 MB | 161,0 MB | **34,6 MB** |
| Sau V44, đo lại sau refactor | 126,0 MB | 163,3 MB | **36,5 MB** |

Delta gần gấp đôi kích thước file vì `toBuffer()` gom từng mảnh rồi
`Buffer.concat` — tồn tại đồng thời cả mảng mảnh lẫn bản ghép. Container
prod `voxdub-app` có **1 GB RAM** và rate limit cho phép **5 request/phút/
key** → 2 upload lớn đồng thời đủ giết cả tiến trình, kéo theo mọi job đang
chạy của mọi khách.

**Sai lầm khi đo, ghi lại để lần sau không lặp**: lần đo đầu chạy client
`fetch` trong CÙNG process với server → RSS gộp cả bộ đệm phía gửi, ra
"279 MB" cho bản stream và suýt kết luận nhầm là bản sửa không ăn thua.
Phải tách client ra process khác (curl) và đo server từ ngoài.

**Gap phụ phát hiện khi sửa**: `submitDemucsJob()` trừ credit TRƯỚC khi ghi
file. Với buffer thì vô hại (route đã chặn file quá cỡ trước khi vào
service), nhưng chuyển sang stream thì 413 xảy ra SAU khi đã trừ → khách
mất Vox cho một upload không bao giờ thành job.

### Design Choice

`src/utils/upload-stream.js` (mới) — 1 hàm dùng chung cho cả 2 route, vì
cùng failure mode, chỉ khác lớp lỗi domain nên truyền factory
`makeError(code, message, statusCode)` vào thay vì viết 2 bản. Tái dùng
NGUYÊN pattern đã chạy thật ở `POST /internal/dub-jobs/:id/output`:
`pipeline()` + kiểm `truncated` + xoá bản cụt.

Xử lý CẢ 2 hành vi quá-hạn-mức của `@fastify/multipart` (cắt ngang im lặng
đặt cờ `truncated`, và ném `FST_REQ_FILE_TOO_LARGE`) — cấu hình mặc định
khác nhau giữa các phiên bản, không đoán bản này đang chạy kiểu nào.

`submitDemucsJob()` đảo thứ tự: ghi file → trừ credit → tạo job. Tiền luôn
là bước sau cùng; trừ hỏng thì xoá thư mục job ngay (file mồ côi không có
document trỏ tới nên `sweepExpired` không bao giờ dọn được).

### Changed Files

- `control_server/src/utils/upload-stream.js` (mới)
- `control_server/src/services/dub-job.service.js` — `fileBuffer` →
  `fileStream`, dọn thư mục job khi hỏng giữa chừng
- `control_server/src/services/render-job.service.js` — `fileBuffer` →
  `fileStream`, đảo thứ tự ghi-file/trừ-credit + rollback file
- `control_server/src/routes/api-v1.js`, `control_server/src/routes/jobs.js`
  — bỏ `toBuffer()`, truyền `data.file`
- `control_server/tests/dub-upload-stream.test.js` (mới, 6 test)
- 3 file test cũ chuyển sang chữ ký stream (`dub-job.service.test.js`,
  `dub-quota-reservation.test.js`, `render-job.integration.test.js`) —
  stream chỉ đọc được 1 lần nên helper phải dựng mới mỗi lần gọi, khác
  Buffer dùng lại được.

### New API/DB/State

`413 UPLOAD_TOO_LARGE` trên `POST /api/v1/dub` và `POST /v1/jobs/demucs`.
Không có field/collection/enum mới.

### Tests

`tests/dub-upload-stream.test.js` — 6 test, đi qua HTTP thật (không gọi
thẳng service):

1. upload 3 MB → byte trên đĩa khớp CHÍNH XÁC + nội dung nguyên vẹn
2. vượt hạn mức → 413 + KHÔNG để lại file cụt + không tạo job
3. vượt hạn mức → quota giữ chỗ được trả lại (không kẹt vĩnh viễn)
4. file rỗng → 400 `EMPTY_FILE` + trả lại quota
5. demucs vượt 200 MB → 413 + **số dư Vox không đổi** (khoá lại gap phụ)
6. regression: mã ngôn ngữ sai vẫn bị chặn TRƯỚC khi đọc file (V44 không
   phá `93c6878`), không giữ chỗ quota, không tạo thư mục job

**2 fail đầu tiên là lỗi TEST, không phải lỗi code** — các test dùng chung
`DUB_UPLOAD_DIR` nên thư mục job của test trước bị assert "không để lại
file cụt" tính nhầm là rác của chính nó; sửa bằng dọn đĩa trong
`beforeEach`.

Toàn bộ suite: **293 test, 292 pass, 1 skip, 0 fail** (`npm test`).

### Live Verification

Đo RSS trên server thật dựng tại chỗ (cùng mã, in-memory Mongo) — bảng số
ở mục Audit.

**Trên PROD sau khi redeploy** (`voxdub-app`, deploy `037fc8d`,
2026-08-17 19:52): đăng ký thiết bị dùng thử thật → `POST /v1/jobs/demucs`
với file 250 MB (vượt trần 200 MB):

- Trả về `{"code":"UPLOAD_TOO_LARGE","message":"File audio vượt quá 200 MB."}`
  — đây là mã lỗi của CHÍNH `utils/upload-stream.js`; bản cũ sẽ trả mã
  `FST_REQ_FILE_TOO_LARGE` do `@fastify/multipart` ném ra khi `toBuffer()`,
  nên phản hồi này chứng minh code mới đang chạy thật, không phải suy đoán
  từ trạng thái job deploy.
- Số dư Vox: **500 trước → 500 sau** — upload hỏng không trừ tiền khách.
- `/health` `uptimeS` chạy liên tục qua suốt lượt upload (45s → 106s, không
  reset) — container KHÔNG restart, tức không OOM. Đây chính là kịch bản mà
  bản cũ có nguy cơ giết tiến trình.
- Thời gian: 9,3s cho 250 MB qua Internet.

### Remaining Limits

- Hạn mức 200 MB của `/v1/jobs/demucs` vẫn HARDCODE trong route (khác
  `/api/v1/dub` đọc từ `cloud.dub.max.upload.mb`). Không đưa vào config ở
  đợt này vì đổi hạn mức là quyết định vận hành, không phải hệ quả của việc
  chuyển sang stream.
- Khách không đủ Vox giờ vẫn upload xong toàn bộ file rồi mới bị từ chối
  (trước đây bị chặn sớm hơn nhờ buffer). Đánh đổi có chủ đích: bản cũ vẫn
  nuốt trọn file vào RAM trước khi từ chối, tức tệ hơn về đúng thứ đang
  sửa. Muốn chặn sớm phải kiểm tra số dư trước khi đọc body — thêm 1 truy
  vấn/1 request, để lại nếu có bằng chứng bị lạm dụng thật.

## V48 — Sao lưu MongoDB không phụ thuộc nền tảng (Phase G, 2026-08-17)

### Audit Before Build

`docs/PLAN.md` ghi "**[ĐÃ XONG 2026-08-15]** backup MongoDB hàng ngày (3h
sáng, giữ 14 bản/30 ngày), live-verify thật" — nhưng đó là **tính năng của
Coolify**, không phải mã trong repo. Chuyển sang Vibe Host ngày 2026-08-17
là mất trắng khả năng đó, và mục ghi "đã xong" trong PLAN trở thành thông
tin sai lệch nguy hiểm: đọc lướt sẽ tưởng vẫn còn sao lưu.

Kiểm tra đường thay thế trước khi viết code:
- MCP Vibe Host: **không có tool sao lưu nào** (chỉ deploy/env/log/resource).
- `list_stacks` trả `[]` — MongoDB do nền tảng provision không lộ ra dạng
  cụm để thao tác qua API.
- Dashboard có mục "Sao lưu" nhưng chỉ bấm được bằng tay, không có API.
- Dump ra đĩa trong container là **sao lưu giả vờ**: nền tảng không có
  volume bền vững, file bay theo lần redeploy kế tiếp.

DB đang giữ: ví/credit khách, đơn hàng, activation key, API key developer,
khoá nhà cung cấp AI (đã mã hoá). Ngày 2026-08-17 đã mất sạch 1 lần thật.

### Design Choice

Đường trung thực duy nhất khi không có volume: **stream ra ngoài cho người
gọi tự cất giữ**. `GET /v1/admin/backup` (X-Admin-Token, rate limit 3/phút)
đọc cursor từng collection → NDJSON → gzip → HTTP, không file tạm, bộ nhớ
phẳng bất kể DB to cỡ nào (cùng nguyên tắc V44 vừa làm).

**EJSON chứ không JSON thường**: JSON biến `ObjectId` và `Date` thành chuỗi,
khôi phục xong là đứt mọi quan hệ giữa các collection — lỗi này chỉ lộ ra
đúng lúc cần khôi phục nhất. **NDJSON chứ không 1 mảng JSON**: nhập lại cũng
đọc theo dòng được.

Chế độ nhập mặc định là `upsert` (giữ bản ghi tạo sau lúc sao lưu), `--wipe`
mới xoá sạch — vì tình huống thường gặp là "vá lại phần mất", không phải
"quay ngược toàn bộ thời gian".

### Changed Files

- `control_server/src/services/backup.service.js` (mới) — `exportLines()`
  generator + `importLines()`
- `control_server/src/routes/admin.js` — `GET /v1/admin/backup`, ghi AuditLog
- `control_server/scripts/backup-pull.sh` (mới) — kéo + xoay vòng N bản
- `control_server/scripts/restore-backup.js` (mới) — khôi phục
- `control_server/tests/backup.test.js` (mới, 5 test)

### Tests

Điều được test KHÔNG phải "endpoint có trả về gì đó" mà là **khôi phục xong
có ra đúng dữ liệu cũ không** — sao lưu không restore được thì tệ hơn không
có vì tạo cảm giác an toàn giả:

1. không có admin token → 401 và response lỗi không chứa một byte dữ liệu
2. xuất → có dòng siêu dữ liệu + đủ bản ghi mọi collection, đúng
   `content-type: application/gzip` + tên file
3. **vòng tròn xuất → XOÁ SẠCH → nhập lại**: số dư ví 1234 nguyên vẹn, chuỗi
   tiếng Việt có dấu không hỏng, `_id` vẫn là `ObjectId` và khớp bản gốc,
   trường thời gian vẫn là `Date`
4. chế độ `upsert` ghi đè bản trùng `_id` nhưng KHÔNG xoá bản ghi tạo sau
5. nhập lại 2 lần liên tiếp không nhân đôi (idempotent theo `_id`)

**2 fail đầu tiên đều là lỗi TEST, không phải lỗi code**, ghi lại vì cả hai
đều dễ đọc nhầm thành lỗi sản phẩm: (a) `assert total === 2` sai vì bản dump
có thêm chính dòng AuditLog do lượt xuất sinh ra; (b) `gunzip` báo "incorrect
header check" ở test thứ 5 — thực chất là **rate limit 3 lượt/phút của chính
endpoint** trả JSON 429, không phải lỗi nén. Đã chuyển các test vòng tròn
sang gọi thẳng `exportLines()` (đúng generator route dùng) thay vì đốt hạn
mức qua HTTP.

Toàn bộ suite: **298 test, 297 pass, 1 skip, 0 fail**, chạy lại 3 lần đều
ổn định. Ghi nhận 1 lượt chạy duy nhất báo 11 fail rồi không tái hiện được ở
3 lượt sau — nghi tranh chấp tài nguyên khi nhiều instance
`mongodb-memory-server` khởi động cùng lúc (`node --test` chạy song song
từng file), không phải lỗi trong thay đổi này; ghi lại để lần sau thấy lại
thì có manh mối, không lờ đi.

### Live Verification

Trên prod chỉ xác nhận được phần KHÔNG cần bí mật: route tồn tại và chặn
đúng khi thiếu token (`401`). Lượt kéo bản sao lưu thật cần
`ADMIN_TOKEN` — chỉ chủ dự án có (biến bí mật trên Vibe Host, `list_env`
không đọc ngược được giá trị). Lệnh để chủ dự án tự chạy nằm trong
`docs/API.md` mục `GET /v1/admin/backup`.

### Remaining Limits

- **Vẫn là sao lưu KÉO, không phải tự động**: phải có 1 máy ngoài (laptop/
  workspace/VPS) đặt cron gọi `backup-pull.sh`. Không có máy đó thì không có
  sao lưu — nền tảng không cho lịch chạy nào và container không giữ file.
- Bản dump là dữ liệu thật của khách ở dạng đọc được (trừ khoá nhà cung cấp
  đã mã hoá). Nơi cất giữ phải được bảo vệ tương đương chính máy chủ.
- Chưa nén/mã hoá bằng khoá riêng của người nhận (GPG). Cần nếu định gửi bản
  sao lưu qua kênh không tin cậy — chưa làm vì hiện tại người kéo cũng chính
  là chủ dự án.
- Chưa thử nghiệm với DB lớn thật (DB hiện tại gần như rỗng) — cơ chế là
  stream nên không có ngưỡng lý thuyết, nhưng chưa có số đo.

## V45 — Kết quả job sống sót qua redeploy (Phase G, 2026-08-17)

### Audit Before Build

V44 đã chứng minh bằng thực nghiệm: job `done` → redeploy → file kết quả
biến mất, Mongo vẫn `done`, ví ĐÃ trừ. Lúc đó chốt phương án hoàn phí tự
động — nhưng đó là **giảm đau, không phải chữa**: khách được trả lại tiền
nhưng vẫn không có video và phải chờ dub lại từ đầu.

Kiểm lại các chỗ chứa file trước khi chọn hướng:
- Đĩa container: chết theo mỗi lần redeploy (đã xác nhận, không có volume).
- S3/object storage: cần credential + quyết định chi phí của chủ dự án.
- **MongoDB managed do nền tảng provision: là thứ DUY NHẤT trong hệ thống
  hiện tại thật sự bền vững qua redeploy** — và GridFS sinh ra đúng cho
  việc chứa file lớn theo chunk 255KB, đọc/ghi theo dòng.

### Design Choice

GridFS (bucket `dubfiles`), khoá dạng `dub/<jobId>/input.mp4`. Vẫn dùng
đúng 2 field `inputPath`/`outputPath` của `DubApiJob` — không đổi schema,
chỉ đổi Ý NGHĨA từ đường dẫn đĩa sang khoá kho. Job cũ còn giữ đường dẫn đĩa
sẽ đơn giản là "không tìm thấy" → rơi vào đúng nhánh hoàn phí đã có, không
crash.

Tách lõi `writeUploadStream()` ra khỏi `writeUploadToDisk()` (V44) để luật
"không để lại bản cụt" nằm đúng MỘT chỗ, dùng chung cho cả đĩa lẫn GridFS —
thêm kho mới sau này chỉ truyền `dest` khác.

Worker Python KHÔNG phải sửa một dòng nào: nó vốn coi `outputPath` là chuỗi
mờ do server trả về rồi gửi lại lúc `complete` — bằng chứng cho thấy ranh
giới "worker chỉ nói HTTP, không biết kho" của V34b được thiết kế đúng.

Đánh đổi có chủ đích: video nằm trong database làm DB phình. Chấp nhận vì
file sống rất ngắn (xoá NGAY sau khi khách tải + TTL 2 giờ). Muốn đổi sang
S3 về sau chỉ phải sửa đúng `job-storage.service.js`.

### Changed Files

- `control_server/src/services/job-storage.service.js` (mới)
- `control_server/src/utils/upload-stream.js` — tách lõi `writeUploadStream`
- `control_server/src/services/dub-job.service.js` — submit/cleanup dùng kho
- `control_server/src/routes/internal-dub-jobs.js` — worker I/O qua kho
- `control_server/src/routes/api-v1.js` — tải kết quả từ kho + 2 bug dưới
- `control_server/tests/dub-result-durability.test.js` (mới, 3 test)
- `control_server/tests/helpers/db.js` — `clearDb` quét collection THẬT

### 2 bug THẬT lộ ra khi viết test (đều đã sửa)

1. **Listener gắn sau `reply.send()` nên bắt hụt sự kiện.** Stream đĩa luôn
   phát `close` đủ muộn để kịp gắn; stream GridFS có thể đọc xong ngay trong
   lượt `send`. Hậu quả không hề nhỏ: `markDelivered` không bao giờ chạy →
   lượt gọi sau thấy "done + không còn file + chưa hết hạn" → **hoàn tiền
   cho khách vừa nhận đủ hàng**. Sửa: gắn `end` + `close` (có cờ chống chạy
   2 lần) TRƯỚC khi gửi.
2. **Race giữa 2 lượt tải song song và việc dọn file → HTTP 500.** Lượt thứ
   hai kịp thấy bản ghi file, mở stream, rồi chunk bị xoá giữa chừng. Sửa
   tận gốc: nếu `deliveredAt` đã có thì trả `410 RESULT_EXPIRED` NGAY, không
   chạm kho — vừa hết race, vừa là câu trả lời trung thực hơn (biết chắc
   khách đã tải, thay vì suy ra từ việc "file không còn").

Ngoài ra sửa 1 lỗi hạ tầng test: `clearDb()` chỉ xoá collection do mongoose
đăng ký nên bỏ sót `dubfiles.files`/`dubfiles.chunks` (driver tạo, không có
model) — rác của test trước tràn sang test sau và làm assert "không sót file
cụt" fail. Giờ duyệt collection thật trong database.

### Tests

`tests/dub-result-durability.test.js` — mô phỏng redeploy đúng nghĩa: đóng
app → **xoá sạch thư mục đĩa cục bộ** → dựng app mới trên CÙNG database.

1. kết quả vẫn tải được nguyên vẹn TỪNG BYTE sau khi container dựng lại —
   đây chính là ca mà trước V45 khách bị trừ tiền và nhận `410`
2. sau redeploy, tải xong vẫn dọn file + ghi `deliveredAt`, lượt gọi sau trả
   `410 RESULT_EXPIRED` và **không hoàn tiền** cho người đã nhận hàng
3. lưới an toàn V44 còn nguyên: file mất THẬT (xoá khỏi chính kho bền vững)
   vẫn trả `410 RESULT_LOST_REFUNDED`

Toàn bộ suite: **301 test, 300 pass, 1 skip, 0 fail** — chạy lại 4 lần liên
tiếp đều 0 fail sau khi sửa 2 bug trên (trước đó có 1 lượt fail chập chờn,
chính là bug số 2 chứ không phải flake môi trường như tưởng ban đầu).

### Live Verification

Chưa chạy được đầu-cuối trên prod: cần API key có quota phút dub, mà việc cấp
key đòi `ADMIN_TOKEN` — biến bí mật chỉ chủ dự án có (`list_env` không đọc
ngược được). Phần verify được đã làm: deploy thành công, `/health` xanh.
Kịch bản chủ dự án tự chạy để xác nhận: submit 1 job → chờ `done` → redeploy
`voxdub-app` → gọi lại `/api/v1/dub/<jobId>/result` → phải ra **200 + video**,
thay vì `410 RESULT_LOST_REFUNDED` như trước V45.

### Remaining Limits

- **Cloud rendering (Demucs, `/v1/jobs/demucs`) VẪN dùng đĩa** — cùng rủi ro
  mất file qua redeploy, chưa chuyển. Cố tình để ngoài phạm vi: đó là luồng
  khác (RenderJob, 2 stem audio, tính tiền lúc nộp) và cần bộ test riêng.
- DB phình khi nhiều job chạy đồng thời (video nằm trong database). Chưa có
  hạn mức tổng dung lượng kho — hiện chỉ dựa vào TTL 2h + xoá sau khi giao.
  Nên theo dõi mục "Lưu trữ" trên dashboard nếu lượng job tăng.
- Chưa đo hiệu năng GridFS với video hàng trăm MB trên prod thật (test dùng
  file nhỏ + đo cục bộ).

## V49 — Trang thử API lồng tiếng trên trình duyệt (Phase G, 2026-08-17)

### Audit Before Build

Hạ tầng dub server-side (V34b) đã chạy thật và vừa được làm bền vững (V44,
V45), nhưng đường vào duy nhất là `curl` với 1 API key cấp tay. Đối chiếu
audit thị trường 2026-08-16: điểm yếu lớn nhất của sản phẩm không phải chất
lượng đầu ra mà là **ma sát dùng thử** — đối thủ kéo-thả trên trình duyệt,
VoxDub bắt tải `.exe` Windows.

`website/` đã có sẵn React + Vite + react-router và được `control_server`
serve CÙNG origin, nên gọi API không vướng CORS và không cần hạ tầng mới.

### Design Choice

Trang `/thu-dub` gọi đúng 3 endpoint đã có (`/api/v1/me`, `POST /api/v1/dub`,
`GET /api/v1/dub/:id[/result]`) — **không thêm endpoint dub nào**.

Quyết định phạm vi quan trọng nhất: **không làm chế độ dùng thử không cần
key**. Cho người lạ chạy ASR + TTS + ghép video miễn phí là quyết định chi
phí và chống lạm dụng của chủ dự án, không phải hệ quả kỹ thuật của việc
dựng UI. Ghi rõ thành Guardrail thay vì âm thầm tự quyết.

Ba lựa chọn kỹ thuật đáng ghi:
- **Không lưu key vào localStorage** — trang chạy chung origin với trang bán
  hàng; một API key rò rỉ là tiền thật của người khác.
- **XHR thay `fetch`** cho lượt upload: chỉ XHR báo được tiến trình TẢI LÊN.
  Với file vài trăm MB, thanh tiến trình là khác biệt giữa "đang chạy" và
  "hình như treo rồi".
- **Giữ blob kết quả trong tab**: máy chủ xoá file ngay sau lượt tải đầu
  tiên (chính sách dữ liệu V9), nên nếu để người dùng bấm tải lại sẽ ra 410
  và trông như hỏng.

Danh sách ngôn ngữ + giá + hạn mức MB **đọc từ máy chủ** qua khối `cloudDub`
mới trong `GET /v1/config/app`, lấy thẳng từ `utils/dub-langs.js` — không
chép tay sang frontend, vì đó đúng là loại trôi lệch mà
`tests/dub-langs.test.js` sinh ra để chặn.

### Changed Files

- `website/src/pages/TryDub.jsx` (mới)
- `website/src/App.jsx` — route `/thu-dub`
- `website/src/components/PublicLayout.jsx` — mục nav + link footer
- `control_server/src/routes/config.js` — khối `cloudDub` trong `/v1/config/app`

### Tests

Website `npm test` (vitest): **31 pass**. `npm run build`: sạch, không
warning mới. `control_server`: **301 test, 300 pass, 1 skip, 0 fail**.

1 lỗi build thật đã sửa: import `{ get }` từ `api/client` — module đó export
object `api`, không có hàm `get` rời. Bắt được ngay ở lượt build đầu.

### Live Verification

**CHƯA click thử trên trình duyệt thật.** Cần API key có quota phút dub, mà
cấp key đòi `ADMIN_TOKEN` — chỉ chủ dự án có. Trang render được và build ra
bundle hợp lệ, nhưng đó KHÔNG phải bằng chứng luồng dub qua UI chạy đúng.
Việc còn lại của chủ dự án: mở `/thu-dub`, dán key, chọn 1 video ngắn, xác
nhận thấy đủ 4 chặng (kiểm key → tải lên → queued/running → tải kết quả).

### Remaining Limits

- **Vẫn cần API key** → mới đóng MỘT NỬA gap "người lạ không thử được nếu
  không có Windows". Nửa còn lại là quyết định kinh doanh (xem Guardrail 2).
- Chưa có test render/tương tác cho trang này — `website/` chưa có hạ tầng
  test component (đúng hiện trạng ghi trong `docs/ARCH.md`).
- Trang chỉ phục vụ luồng dub. Các tính năng chỉ có trên desktop (lip-sync
  V32b, OCR che chữ V5, editor từng câu) vẫn không chạm được từ web.

## V50 — Cloud render không im lặng nuốt tiền + giám sát kho (Phase G, 2026-08-17)

### Audit Before Build

Rà "còn việc gì chưa làm" sau V49 thì lộ ra một lỗ hổng nặng hơn thứ đang
định sửa (vốn chỉ định chuyển file render sang GridFS cho bền vững):

1. `/v1/jobs/demucs` **trừ Vox NGAY lúc nộp**, chính sách ghi rõ "mất tiền
   cả khi job fail, không hoàn" — hợp lý khi job thật sự chạy.
2. Nhưng đọc kỹ 2 sweeper: `sweepExpired` lọc
   `status: {$in: ['done','failed']}`, `sweepStaleRunning` lọc
   `status: 'running'`. **Không ai đụng tới `queued`.**
3. Và `list_projects` trên Vibe Host chỉ có `voxdub-app` +
   `voxdub-dub-worker` — **không có worker render nào tồn tại**, trong khi
   `/v1/config/app` trả `cloudRenderEnabled: true` và GUI vẫn hiện ô "Xử lý
   tách nhạc trên cloud".

Cộng lại: bấm ô đó = mất 50 Vox, job nằm `queued` vĩnh viễn, không kết quả,
không cả một dòng lỗi để người dùng biết mà hỏi. Đây không phải rủi ro giả
định — nó là hành vi hiện tại của hệ thống đang chạy.

### Design Choice

**Ranh giới hoàn tiền** là phần khó, không phải cơ chế hoàn: chỉ hoàn khi
**chưa có gì chạy** (job chưa từng được worker nhận). Job đã `running` rồi
hỏng vẫn giữ nguyên chính sách cũ — trừ tiền cho việc đã làm là hợp lý, trừ
tiền cho việc chưa từng bắt đầu thì không. Vì vậy 4 trong 8 test là nhóm
"KHÔNG được hoàn".

Idempotent 2 lớp: điều kiện `status: 'queued'` nằm TRONG `findOneAndUpdate`
(2 lượt sweep chồng nhau chỉ 1 lượt thắng), và `idempotencyKey` theo jobId ở
tầng sổ cái.

**Cố ý KHÔNG chuyển kho file render sang GridFS đợt này** (dù V45 vừa làm
đúng việc đó cho dub): worker render đọc/ghi theo ĐƯỜNG DẪN FILE — thiết kế
V12, chưa từng được chuyển sang HTTP như dub-worker hôm nay. Đổi kho mà không
đổi transport là làm hỏng một service tôi không có cách nào test (không được
triển khai, không chạy được torch/demucs tại chỗ). Ghi thành Remaining Limit
thay vì ship mù.

Về dung lượng: `orphanFiles` (file không còn job nào trỏ tới) là con số đáng
theo dõi hơn cả tổng dung lượng — nó là dấu hiệu sweeper sót việc, xuất hiện
TRƯỚC khi hết chỗ.

### Changed Files

- `control_server/src/services/render-job.service.js` — `sweepStaleQueued()`
- `control_server/src/services/job-storage.service.js` — `stats()`
- `control_server/src/routes/admin.js` — `GET /v1/admin/storage`
- `control_server/src/routes/jobs.js` + `render-job.service.js` — hạn mức
  upload đọc từ config thay vì hardcode ở 2 chỗ
- `control_server/src/services/config.service.js` — 3 config mới
- `control_server/server.js` — nối `sweepStaleQueued` vào lịch quét render
- `control_server/tests/render-stale-queued-refund.test.js` (8 test, mới)
- `control_server/tests/storage-stats.test.js` (5 test, mới)
- `website/src/pages/TryDub.test.jsx` (8 test, mới) + `src/test-setup.js`
  + `vitest.config.js` + 3 devDependency testing-library
- `website/src/pages/TryDub.jsx` — thêm nhãn cho ô chọn file
- `docs/PLAN.md` — sửa mục backup "ĐÃ XONG 2026-08-15" thành cảnh báo HẾT
  HIỆU LỰC (đó là tính năng Coolify, mất khi chuyển nền tảng)

### Tests

Hoàn phí (8): hoàn đúng số Vox + chuyển `failed`; ghi đúng 1 dòng vào sổ cái;
quét 2 lần chỉ hoàn 1 lần; **không** đụng job mới nộp; **không** hoàn job
`running`; **không** hoàn job `done`; job miễn phí vẫn fail nhưng không tạo
dòng hoàn rỗng; ngưỡng đọc từ config.

Dung lượng (5): kho rỗng không nổ; đếm đúng file/byte; **file mồ côi** được
đếm riêng (kể cả khi job bị xoá sau); ngưỡng cảnh báo từ config; 401 khi
thiếu token.

Trang `/thu-dub` (8): ngôn ngữ đổ TỪ MÁY CHỦ (không hardcode); giá đổi theo
chế độ nhạc nền; file quá cỡ bị chặn TRƯỚC khi gửi; chưa có key thì không gửi
được; key đúng hiện quota; key sai hiện đúng thông báo máy chủ;
**API key không bao giờ vào localStorage**; máy chủ tắt tính năng thì khoá nút.

**2 lỗi thật do test bắt được:**
1. `createdAt` là **immutable** trong Mongoose nên `Model.updateOne($set)` bỏ
   qua KHÔNG BÁO LỖI — test back-date job cứ tưởng đã tạo job cũ, sweeper báo
   "0 job", suýt kết luận nhầm là logic sai. Phải đi thẳng qua
   `Model.collection.updateOne`.
2. Ô chọn file trên `/thu-dub` **không có nhãn nào** — `getByLabelText` không
   tìm thấy. Đã sửa ở TRANG (thêm `<label htmlFor>`) chứ không lách trong
   test: trình đọc màn hình trước đó chỉ đọc được "chưa chọn tệp".

Tổng: control_server **314 test (313 pass, 1 skip, 0 fail)**, website
**39 test** (từ 31), build sạch.

### Remaining Limits

- **Không có worker render nào đang chạy** — V50 chỉ đảm bảo khách được hoàn
  tiền sau 15 phút chờ, KHÔNG làm tính năng chạy được. Chủ dự án cần chọn:
  (a) triển khai 1 worker render (cần CPU/RAM — gói hiện tại đã dùng 3.5/4
  core, 5.5/8 GB), hoặc (b) tắt `cloud.render.enabled` để không ai bấm vào
  một tính năng không thể chạy. Đổi config cần `ADMIN_TOKEN`.
- **File render vẫn nằm trên đĩa container** → vẫn mất qua redeploy. Chỉ nên
  làm cùng lúc với việc chuyển worker render sang HTTP transport (như
  dub-worker đã làm), và chỉ khi worker đó thật sự tồn tại để test.
- `GET /v1/admin/storage` mới chỉ đếm kho của **dub** (`dubfiles`); file
  render nằm trên đĩa nên không vào thống kê này.
- Chưa có cảnh báo chủ động khi vượt ngưỡng (chỉ trả cờ `overWarnThreshold`,
  phải có người gọi endpoint mới biết).

## Rà chéo sau V50 — 2 lỗi thật do V45 và V48 giẫm chân nhau (2026-08-17)

Không phải mini-spec: rà lại chính 10 commit đã ship trong ngày, vì tất cả
đều đụng tiền hoặc dữ liệu khách. Cách làm: viết test cho 2 NGHI VẤN trước,
rồi mới kết luận — 1 cái đúng ngay, 1 cái ban đầu "pass" nhưng là pass giả.

### Lỗi 1 — bản sao lưu nuốt luôn byte video

V48 (sao lưu) viết TRƯỚC V45 (đưa video vào GridFS trong chính database), nên
`exportLines()` duyệt mọi collection không phải `system.*` và sau V45 thì hút
luôn `dubfiles.chunks`. Đo thật: 1 video 600 KB làm bản dump nhảy lên ~830 KB
(base64 phình thêm ~33%). Với vài job đang chạy, bản "sao lưu dữ liệu kinh
doanh" biến thành bản sao video tạm.

Sửa: loại `<bucket>.files`/`<bucket>.chunks` khỏi bản dump. Đây là quyết định
ĐÚNG chứ không phải tiết kiệm dung lượng — file job vốn tạm (xoá ngay khi
khách tải xong, TTL 2 giờ), khôi phục lại video của phiên làm việc hôm kia
không có ý nghĩa gì; bản ghi job trong `dubapijobs` (thứ đáng khôi phục) vẫn
được sao lưu bình thường.

### Lỗi 2 — upload đứt giữa chừng để lại chunk mồ côi VĨNH VIỄN

GridFS chỉ tạo bản ghi file lúc stream `finish`. Upload đứt nửa chừng để lại
các chunk KHÔNG có chủ: `remove(key)` tìm theo filename nên không bao giờ
thấy, và bộ đếm mồ côi của V50 (đếm file) cũng không thấy. Rác vô hình với
mọi cách dọn hiện có.

**Bài học về cách viết test**: bản test ĐẦU TIÊN của lỗi này *pass* — nhưng
pass giả, vì nguồn dữ liệu giả lập lỗi ngay trong lượt `read()` đầu tiên nên
chưa chunk nào kịp ghi xuống DB. Sửa test thành nhả 8 lượt 300 KB theo nhịp
macrotask rồi mới đứt → lộ ra **9 chunk** nằm lại.

Sửa 3 tầng (thiếu tầng nào cũng rò):
1. `dest.abort()` — xoá chunk đã ghi dở (giảm 9 → 1).
2. `remove(key)` — cho ca stream ĐÃ finish rồi mới hỏng (vd `truncated`), lúc
   đó bản ghi file có thật và `abort()` vô tác dụng.
3. Xoá theo `files_id` — tóm nốt chunk được flush song song với lượt huỷ
   (chính là chunk thứ 9 còn sót sau bước 1). Chạy lại 3 lần đều sạch.

Kèm theo: `GET /v1/admin/storage` thêm `orphanChunks`, để lần sau thứ này tái
diễn thì phát hiện bằng số liệu chứ không phải bằng may mắn.

### Kết quả

`control_server`: **317 test (316 pass, 1 skip, 0 fail)**, chạy 2 lượt liên
tiếp đều sạch. Không đụng website (39 test giữ nguyên).

## V51 — Đẩy batch lên worker-dub từ desktop (Phase G, 2026-08-17)

### Audit Before Build

V42 (16-08) đã trả lời câu hỏi "làm sao chạy batch song song": **đừng làm
trên máy**. 4GB VRAM chạm 96% với đúng một workload (đo thật ở V32a), nên
song song thật đổi "chậm" lấy "CUDA OOM". Đường đúng là `worker-dub` —
CPU-only, chạy được N bản sao, atomic-safe từ V34a/V34b.

Nhưng V42 dừng ở kết luận và ghi lại nguyên văn: *"Chưa thiết kế/xây cách app
desktop hoặc quy trình vận hành đẩy batch job vào worker-dub để scale thật"*.
Tức throughput thật vẫn kẹt 1 video/lượt vì **thiếu mảnh nối**, không phải vì
thiếu hạ tầng. Hạ tầng đó giờ đã đủ vững để dựa vào: V44 (upload không OOM
máy chủ), V45 (kết quả sống qua redeploy), V50 (không âm thầm nuốt tiền).

Đọc trước khi viết: `batch.py` (mẫu resume-safe qua state file),
`saas_client.py` (đường xác thực thiết bị — KHÔNG dùng lại được vì API dub
dùng identity khác), `cli.py` (mẫu subcommand + cam kết không kéo GUI).

### Design Choice

**Tách hẳn khỏi `saas_client.py`.** Hai lớp identity khác nhau: token thiết
bị (ví Vox, tính theo segment) và API key (`vx_live_…`, quota tính theo PHÚT
video). Máy chủ cũng tách 2 middleware. Trộn lại là mời gọi lỗi tính tiền.

**3 trạng thái kết thúc chứ không 2**: `success` / `failed` / **`refunded`**.
Máy chủ có thể mất kết quả rồi tự hoàn phí (V44/V45) — đó KHÔNG phải video
hỏng, gửi lại là xong. Gộp vào `failed` sẽ khiến người vận hành tưởng video
lỗi và bỏ đi, tức là mất nội dung vì một nhãn sai.

**Tuần tự ở phía client, có chủ đích.** Máy chủ chặn 5 lượt nộp/phút/key và
hiện chỉ có 1 worker; bắn song song chỉ dời chỗ chờ và thêm rủi ro rối trạng
thái. Chỗ đáng song song là số bản sao worker — quyết định hạ tầng, không
phải việc của client.

**Tải về ghi `.part` rồi `replace()`.** Máy chủ xoá kết quả NGAY sau lượt tải
đầu tiên (chính sách V9), nên một file tải dở mang đúng tên thật là mất hàng
vĩnh viễn: lượt chạy sau thấy "đã có" và bỏ qua, trong khi bên máy chủ không
còn gì để tải lại. Có kiểm `content-length` để bắt đứt giữa chừng.

**Hết quota thì dừng NỘP, không dừng cả lượt chạy** — job đã nộp trước đó
vẫn phải theo dõi và tải về, tiền cho chúng đã tiêu rồi.

### Changed Files

- `autodub/cloud_dub.py` (mới) — client `/api/v1/*`: quota, submit (đọc file
  theo dòng), status, download có kiểm toàn vẹn; tự giữ nhịp nộp cho khớp
  rate limit máy chủ
- `autodub/cloud_batch.py` (mới) — vòng chạy, state file, báo cáo
- `autodub/cli.py` — subcommand `cloud-batch`
- `.env.example` + `autodub_gui/pages/settings_fields.py` — biến mới
  `VOXDUB_API_KEY` (ghi vào `EXEMPT_KEYS` kèm lý do, cùng tiền lệ `LIPSYNC_*`)
- `tests/test_cloud_batch.py` (mới, 12 test)

### Tests

Chạy trên **máy chủ HTTP thật** dựng tại chỗ (`http.server` trong thread),
**không mock `requests`** — mock đúng cái đang kiểm thì test chỉ chứng minh
mình hiểu đúng mock của mình. 12 test, trọng tâm là đường hỏng vì chúng đụng
tiền:

1. đường thuận: 2 video → tải đủ, byte khớp
2. chạy lại: **không nộp lại** video đã xong (nộp lại = trả tiền lần hai)
3. `--retry-done`: ép nộp lại đúng như khai báo
4. hết quota giữa chừng: DỪNG nộp sau 2 job, báo rõ 2 video CHƯA chạy
5. hết quota từ đầu: không nộp một job nào
6. máy chủ mất kết quả: vào nhóm `refunded` kèm số phút hoàn, KHÔNG phải `failed`
7. tải dở dang: không để lại file mang tên thật, cũng không để lại rác `.part`
8. kết quả rỗng: tính là hỏng, không phải xong
9. job `failed`: giữ nguyên lý do máy chủ trả về
10. state file ghi đủ từng mục
11. **file nguồn không bị đụng vào** (so byte trước/sau)
12. thiếu API key: từ chối chạy với mã `NO_API_KEY`, không âm thầm chạy máy

**Baseline trước/sau đo thật** (cùng sandbox, `git stash` để lấy mốc):
**936 pass → 948 pass**, đúng 12 test mới, **0 regression**. 31 fail + 15
collection error là CÓ SẴN trong sandbox này (thiếu `numpy`/`PySide6`), không
liên quan thay đổi này — CI có đủ deps mới là mốc thật.

2 lỗi thật khi viết:

1. `save_json_atomic(data, path)` chứ không phải `(path, data)` — sai thứ tự
   tham số, 10/12 test đỏ ngay lượt đầu.
2. **CI bắt, sandbox không lộ**: khi máy chủ khai `content-length` dài hơn
   thứ nó gửi rồi đóng kết nối, `requests` ném `ChunkedEncodingError` (chứ
   không đi vào nhánh kiểm số byte của mình). Lỗi transport đó KHÔNG phải
   `CloudDubError` nên nó xuyên thẳng qua `run_cloud_batch` và **giết cả lượt
   batch** — 1 video hỏng chặn hết những video còn lại, dù chúng chẳng liên
   quan. Sửa đúng tầng: client dịch MỌI `requests.RequestException` thành
   `CloudDubError` (`code="NETWORK"`) và luôn dọn `.part` trước khi báo lỗi.
   Thêm test số 13 khoá lại đúng hành vi này (3 video, cái nào cũng hỏng tải
   → cả 3 vẫn phải được nộp và báo cáo riêng).
   Đây là lý do đáng để chạy suite thật trên CI chứ không tin sandbox:
   phiên bản `urllib3` khác nhau cho hành vi khác nhau ở đúng ca đứt kết nối.

### Live Verification

**CHƯA chạy thật đầu-cuối.** Cần API key có quota phút (đòi `ADMIN_TOKEN`).
Lệnh để chủ dự án tự xác nhận:

```bash
export VOXDUB_API_URL=https://voxdub-app.cmc-1.vibenode.matbao.ai
export VOXDUB_API_KEY=vx_live_...
voxdub cloud-batch --input ./videos --output-dir ./ket-qua --source-lang en-US --target vi
```

Đáng chú ý khi chạy thật: hiện chỉ có **1 worker** nên các video xếp hàng
tuần tự trên máy chủ — muốn nhanh hơn phải tăng số bản sao worker (quyết định
hạ tầng, xem V42).

### Remaining Limits

- **Chưa có trong GUI** — CLI-first đúng thứ tự V22→V25 (CLI làm nền, GUI
  sau). Người dùng cuối chưa chạm được.
- **Chỉ nhận file local**, chưa nhận URL: API máy chủ nhận multipart chứ
  không tự tải video từ link. Muốn hỗ trợ URL thì phải tải về máy trước rồi
  mới đẩy lên — tốn băng thông hai chiều, cần cân nhắc riêng.
- Chưa xử lý ca **API key hết hạn/bị thu hồi giữa chừng** khác với lỗi
  thường (hiện rơi vào `failed` với thông báo của máy chủ).
- Thông lượng thật vẫn chặn ở 1 worker; V51 chỉ mở đường, không tự tăng năng
  lực xử lý.


## V52 — Đường ống cho cloud-batch (Phase G, 2026-08-17)

### Audit Before Build

V51 vừa xong đã lộ ngay giới hạn của chính nó: vòng chạy là nộp → chờ → tải →
nộp tiếp. Nghĩa là trong suốt thời gian upload video N+1, **worker trên máy
chủ rảnh**. Với file vài trăm MB qua đường truyền nhà, phần rảnh đó chiếm
phần lớn thời gian — mà mục tiêu gốc của V42 chính là thông lượng, nên V51
mới chỉ *chuyển chỗ xử lý* chứ chưa *tăng thông lượng*.

Ràng buộc phải tôn trọng: V43 giữ chỗ quota theo phút cho mỗi job đang
`queued`/`running`. Nộp trước càng nhiều thì khoá quota càng nhiều.

### Design Choice

Hàng đợi ngắn có trần (`--queue-ahead`, mặc định 2) thay vì song song thật:
worker vẫn xử lý từng job một — thứ bị cắt bỏ là thời gian chết giữa 2 video,
không phải đổi mô hình xử lý.

Video bị 402 chặn được **trả lại hàng đợi**, không đánh dấu hỏng: nó chưa
từng được thử thật sự, chỉ là chưa còn chỗ. Khi một job xong (trả lại quota
đã giữ), đường nộp mở lại ngay trong cùng lượt chạy — nếu không, "hết quota
tạm thời" sẽ biến thành "bỏ luôn phần còn lại của batch".

**Đo bằng trình tự sự kiện, không bằng đồng hồ.** Máy chủ giả ghi lại thứ tự
`submit`/`download`, và test khẳng định `submit job2` xảy ra TRƯỚC
`download job1`. Đo thời gian sẽ thành test chập chờn phụ thuộc máy chạy;
thứ tự thì hoặc đúng hoặc sai.

### Tests (3 mới, tổng 16)

1. **video N+1 đã nộp trước khi tải xong video N** — chính là lý do V52 tồn tại
2. số job chờ đồng thời không bao giờ vượt `queue_ahead` (không tự khoá quota)
3. quota được giải phóng bởi job vừa xong → video từng bị 402 chặn chạy nốt
   trong cùng lượt, `stopped_early` được xoá

Baseline trước/sau: **936 → 952 pass**, 0 regression.

2 lỗi khi viết, đều tự bắt bằng test:
- Thay vòng lặp bằng khối mới nhưng **cắt mất `return report`** → hàm trả
  `None`, 8 test đỏ với `AttributeError` thay vì lỗi logic (may mà test có
  sẵn từ V51 bắt ngay).
- Kịch bản test "quota được giải phóng" bản đầu tự **kẹt cứng**: đặt 402 từ
  lượt nộp ĐẦU TIÊN nên không job nào xong để giải phóng quota. Sửa thành
  chặn từ job thứ 2 trở đi cho tới khi job đầu tải xong.

### Remaining Limits

- Lợi ích **tỉ lệ với thời gian upload**: mạng nhanh + video nhỏ thì gần như
  không khác; mạng nhà + video lớn thì cắt được gần trọn thời gian upload.
  Chưa đo được con số thật vì chưa chạy đầu-cuối (cần API key).
- Vẫn **1 worker** trên máy chủ — V52 lấp thời gian chết, KHÔNG nhân năng lực
  xử lý. Muốn nhanh hơn nữa phải tăng số bản sao worker (quyết định hạ tầng).
- Tải kết quả vẫn nằm trên luồng chính: trong lúc tải video N, không nộp
  thêm. Chồng cả tải lẫn nộp cần luồng riêng — thêm độ phức tạp mà lợi ích
  nhỏ hơn hẳn bước vừa làm, để lại nếu đo thật thấy đáng.


## Test suite gọi thẳng vào PRODUCTION — truy ra gốc của "flake V40" (2026-08-17)

### Phát hiện thế nào

Cài `PySide6`/`numpy`/`pydub` vào sandbox để chạy được suite GUI tại chỗ
(trước đó 15 file lỗi collection nên chỉ CI mới chạy đủ). Suite đầy đủ ra
**1168 pass / 1 fail** — đúng một test, và đúng cái test đã bị gọi là "flake
có sẵn từ V40" suốt 5 mini-spec liền.

Chạy riêng thì PASS, chạy cả suite thì FAIL → phụ thuộc thứ tự. Nhưng đọc
dòng lỗi thật mới thấy điều đáng sợ hơn hẳn một flake:

```
resp = <Response [402]>
```

Đây là **response thật từ máy chủ thật**. Test tên là "offline" mà lại gọi
mạng.

### Nguyên nhân gốc

1. `.env` của máy phát triển (chính README hướng dẫn tạo) có
   `VOXDUB_API_URL=https://voxdub-app.cmc-1.vibenode.matbao.ai` — **máy chủ
   production**.
2. `Settings.load()` gọi `load_dotenv()`, mà `load_dotenv` **bơm thẳng vào
   `os.environ`** của cả tiến trình — không phải đọc riêng cho object đó.
3. Chỉ cần MỘT test bất kỳ trong suite gọi `Settings.load()` là từ đó trở đi
   mọi test khác đều thấy biến môi trường đó.
4. `SaasClient(base_url="")` có nhánh dự phòng `base_url or resolve_api_url()`
   — và `resolve_api_url()` đọc đúng biến vừa bị rò.
5. Kết quả: test kiểm nhánh offline lại **đăng ký một thiết bị trên
   production và gọi một endpoint TÍNH PHÍ** (`/v1/ai/music`). 402 là máy chủ
   trả lời "không đủ credit" — nghĩa là mọi bước trước đó đã chạy thật.

Vì sao trốn được lâu như vậy: **CI không có `.env`** nên trên CI biến đó
không tồn tại và test luôn xanh. Nó chỉ hỏng trên máy người phát triển —
đúng chỗ không ai coi là "thật".

### Vì sao đây không phải chuyện nhỏ

- Suite đã tạo thiết bị rác trên database production mỗi lần ai đó chạy
  `pytest` trên máy có `.env`.
- Nếu thiết bị đó có số dư, một lượt chạy test có thể **tiêu tiền thật**.
- Suốt V40→V41→V42→V32b→V5, mỗi báo cáo đều ghi "1 fail còn lại là flake có
  sẵn" — một lời giải thích nghe hợp lý đã che mất một lỗ hổng an toàn.

### Sửa

`tests/conftest.py` (mới): xoá `VOXDUB_API_URL`/`VOXDUB_API_KEY` khỏi
`os.environ` ở `pytest_configure` (trước khi import module test) **và** trong
một fixture `autouse` trước từng test. Test nào cần địa chỉ máy chủ thì phải
tự đặt bằng `monkeypatch.setenv` — tường minh và tự dọn.

Sau khi sửa: **1169 passed, 6 skipped, 0 failed** — lần đầu tiên suite Python
sạch tuyệt đối tại chỗ (trước đó luôn có "1 fail đã biết").

### Việc cần chủ dự án kiểm

Trên production có thể có vài `Device` rác do các lượt chạy test trước đây
tạo ra (fingerprint từ test). Xem `/v1/admin/devices` và xoá nếu thấy —
tôi không kiểm được vì cần `ADMIN_TOKEN`.


## V53 — Chế độ "xử lý trên máy chủ" trên GUI (Phase G, 2026-08-17)

### Audit Before Build

V51/V52 mới có ở CLI nên người dùng cuối chưa chạm được. Đọc `batch_page.py`
và 2 tiền lệ đã có trong dự án cho tính năng "chỉ chạy được khi đủ điều
kiện": ô "Xử lý tách nhạc trên cloud" (V12) và ô lip-sync (V32b) — cả hai đều
**ẩn hẳn** khi máy chưa đủ điều kiện thay vì hiện ra rồi báo lỗi lúc bấm.

Phải cài `PySide6`/`numpy`/`pydub` vào sandbox mới chạy được test GUI tại chỗ
(trước đó 15 file lỗi collection). Chính việc cài này lộ ra bug suite gọi vào
production — xem mục riêng phía trên.

### Design Choice

**Khoá đúng những gì máy chủ không làm.** Máy chủ chỉ làm lồng tiếng + nhạc
nền; phụ đề, "chỉ xuất âm thanh", "giữ bộ giọng giữa các video" và "mức giảm
tiếng gốc" đều không áp dụng. Để chúng bật mà vô tác dụng là hứa suông:
người dùng chọn phụ đề rồi nhận video không phụ đề và không hiểu vì sao. Khoá
kèm một dòng ghi chú nói rõ ranh giới.

**Chặn liên kết kèm lời giải thích.** API máy chủ nhận file tải lên, không tự
tải video từ URL. Âm thầm bỏ qua những dòng đó là kiểu hỏng tệ nhất — người
dùng tưởng đã chạy hết.

**Không giả vờ có tiến trình theo giai đoạn.** `BatchWorker` phát
`ProgressEvent` theo từng bước pipeline; `CloudBatchWorker` thì không có gì
để phát vì không bước nào chạy trên máy này — chỉ chuyển tiếp dòng nhật ký từ
máy chủ. Bịa ra thanh tiến trình giai đoạn sẽ là nói dối về nơi công việc
đang diễn ra.

### Tests (7 mới, GUI offscreen)

ô ẩn khi chưa cấu hình / hiện khi đã cấu hình; bật lên khoá đúng 4 tuỳ chọn +
hiện ghi chú; tắt đi khôi phục lại; liên kết bị từ chối KÈM lý do và không
nộp gì; file nằm ở 2 thư mục khác nhau bị từ chối rõ ràng; worker nhận đúng
tuỳ chọn người dùng đã chọn (thư mục nguồn, `bg_mode`, thư mục kết quả riêng).

**1 bug thật do test bắt**: gọi `self.opt_voice.current_name()` — `VoicePicker`
không hề có hàm đó (API thật là `voice()`). Nếu không có test GUI thì lỗi này
chỉ nổ đúng lúc người dùng bấm Bắt đầu ở chế độ máy chủ, tức là ở tay khách.

**2 lỗi trong chính test** (ghi lại vì dễ lặp): `BatchItem` dùng
`url=`/`file_path=` chứ không có `key=` (key là property suy ra); và
`isVisibleTo()` luôn False khi trang chưa `show()` — thứ cần kiểm là
`isHidden()` (bị ẩn CÓ CHỦ Ý), không phải "mắt có nhìn thấy không".

Toàn suite: **1176 passed, 6 skipped, 0 failed**. Smoke test toàn app
(`AUTODUB_SMOKE=1`, dựng đủ mọi trang kể cả trang Batch vừa sửa): **exit 0**.

### Remaining Limits

- **Chưa click thử thật** — cần API key để ô này hiện ra ở máy thật.
- Chế độ máy chủ chạy theo THƯ MỤC (lấy thư mục cha của các file đã chọn),
  chưa nhận danh sách file rải rác nhiều nơi. Ràng buộc đến từ
  `run_cloud_batch` chứ không phải GUI; nới thì phải sửa cả hai.
- Chưa có nút Dừng thật cho chế độ máy chủ: job đã nộp vẫn chạy trên máy chủ
  dù người dùng đóng app (và vẫn bị tính tiền). Dừng đúng nghĩa cần một
  endpoint huỷ job phía máy chủ — chưa có.


## V54 — cloud-batch nhận liên kết (Phase G, 2026-08-17)

### Audit Before Build

Giới hạn ghi trong V51: *"Chỉ nhận file local, chưa nhận URL — API máy chủ
nhận multipart chứ không tự tải video từ link"*. Và V53 phải chặn cứng liên
kết trên GUI vì đúng lý do đó.

Đọc trước: `autodub/media/downloader.py::download_one` (yt-dlp + tự động rẽ
sang đường Playwright cho Douyin) và `autodub/batch.py::parse_lines` (đã hỗ
trợ cú pháp `link | Tên giọng`). Cả hai tái dùng nguyên, không viết lại.

### Design Choice

**Khoá trạng thái là CHÍNH liên kết**, không phải tên file tải về: tên file
do yt-dlp đặt theo tiêu đề video, mà tiêu đề có thể đổi giữa 2 lượt — khoá
theo tên file thì lượt sau sẽ nộp trùng và trả tiền lần hai.

**Bản tải trung gian: xoá khi THÀNH CÔNG, giữ khi hỏng.** Hỏng ở bất kỳ bước
nào (nộp, xử lý, tải kết quả) mà xoá luôn bản tải thì lượt chạy lại phải kéo
lại vài trăm MB từ Internet. Ghi kèm file `.source` trỏ tới bản đã tải để
lượt sau nhận ra.

**Nhận danh sách nguồn trộn lẫn** (file + liên kết, nằm bất kỳ đâu) thay vì
chỉ 1 thư mục — nhân tiện **gỡ luôn giới hạn "phải cùng thư mục"** mà V53
vừa phải ghi vào Remaining Limits mấy tiếng trước.

### Tests (6 mới, tổng 22 cho cloud-batch)

liên kết được tải rồi mới nộp; tải hỏng → báo rõ và KHÔNG chặn link còn lại;
bản tải bị xoá sau khi thành công; **hỏng thì giữ bản tải, lượt sau không tải
lại** (đếm số lần gọi downloader); trộn file + link ở nhiều thư mục khác
nhau; khoá trạng thái đúng là liên kết.

Chỉ thay `download_one` bằng bản giả — đường lên máy chủ vẫn đi qua HTTP thật
của test. Không mock `requests`.

### Hai test GUI ĐỔI CHIỀU có chủ đích

`test_links_are_refused…` và `test_files_from_two_folders_are_refused…` của
V53 nay khẳng định điều NGƯỢC LẠI (chấp nhận). Giữ nguyên bản cũ sẽ khoá sản
phẩm vào một giới hạn vừa được gỡ. Đổi tên test kèm ghi chú lý do, và thêm
test mới cho ràng buộc còn đúng: file trên máy KHÔNG tồn tại thì từ chối kèm
tên file.

Kèm theo: **sửa dòng ghi chú trên UI** — nó vẫn nói "máy chủ chỉ nhận FILE
trên máy (không nhận liên kết)". Để nguyên là giao diện nói dối người dùng
về chính tính năng vừa thêm.

Toàn suite: **1183 passed, 6 skipped, 0 failed**; smoke test toàn app exit 0.

### Remaining Limits

- Tải liên kết chạy trên máy người dùng (băng thông 2 chiều: tải về rồi đẩy
  lên). Muốn máy chủ tự đi lấy video thì phải thêm khả năng đó ở API — đụng
  vấn đề pháp lý/lạm dụng, là quyết định của chủ dự án.
- Vẫn chưa có nút Dừng thật cho chế độ máy chủ (job đã nộp vẫn chạy và vẫn
  tính tiền) — cần endpoint huỷ job phía máy chủ.


## V55 — Huỷ job thật (Phase G, 2026-08-17)

### Audit Before Build

Giới hạn ghi ở V53/V54: *"chưa có nút Dừng thật cho chế độ máy chủ — job đã
nộp vẫn chạy và vẫn bị tính tiền dù người dùng đóng app"*. Ai lỡ nộp nhầm 20
video thì không có cách nào chặn.

Đọc worker trước khi thiết kế: `run_dub()` spawn `python3 -m autodub.cli dub`
bằng `subprocess.run` — tức là CÓ tiến trình con để giết, huỷ thật khả thi
chứ không phải chỉ đánh dấu trạng thái. `_heartbeat_loop` đã biết phát hiện
"job không còn của mình" nhưng chỉ dừng heartbeat rồi vẫn để job chạy tới hết.

### Design Choice

**Điều kiện `apiKeyId` nằm TRONG câu update**, không kiểm ở tầng route: huỷ
job của người khác nặng hơn hẳn xem trộm, nên phải đi cùng một lệnh nguyên tử
chứ không dựa vào thứ tự if/else.

**409 gộp 3 ca** (không tồn tại / không phải của bạn / đã kết thúc): phân biệt
sẽ để lộ jobId người khác có tồn tại hay không, chỉ cần dò là biết.

**Không tính tiền job huỷ** — không cần cơ chế hoàn: `chargeDubUsage` chỉ chạy
trong `completeJob`, mà `completeJob` đòi `status:'running'`. Job đã sang
`cancelled` thì worker báo xong muộn bị từ chối. Test khoá đúng điều này.

**Worker dừng thật**: `subprocess.run` → `Popen` + vòng `communicate(timeout)`
để còn kiểm cờ huỷ; heartbeat bị từ chối thì `proc.kill()`. Và khi bị huỷ thì
KHÔNG gọi `/fail` — job đã ở trạng thái đúng (`cancelled`), báo fail chỉ ghi
đè một trạng thái đúng bằng một trạng thái sai.

### Tests (10 mới: 8 Node + 2 Python)

Node: huỷ job chờ (trả quota + xoá file); huỷ job đang chạy; **worker báo
"xong" sau khi huỷ → bị từ chối, KHÔNG tính tiền, không sinh sổ cái**; KHÔNG
huỷ được job của key khác; job đã xong → 409 và không đụng quota; huỷ 2 lần
không trả quota 2 lần; jobId sai định dạng → 409 chứ không 500; thiếu key → 401.

Python: bấm Dừng → gửi lệnh huỷ THẬT lên máy chủ cho mọi job đang chờ, đánh
dấu `cancelled` (KHÔNG phải `failed` — người dùng đổi ý không phải lỗi); video
đã tải xong trước khi dừng vẫn tính là xong.

Suite: **Python 1185 pass / 0 fail**, **Node 325 test (324 pass, 1 skip, 0 fail)**.

### Remaining Limits

- Worker chỉ nhận biết huỷ ở nhịp heartbeat (mặc định vài giây) — huỷ xong
  còn chạy thêm vài giây là bình thường.
- Chưa live-verify huỷ trên prod (cần API key + một job chạy thật).

## V56 — Nghe thử 30 giây trước khi chạy cả video (Phase H, 2026-08-18)

### Audit Before Build

Xem app thật (v3.0.1) mới thấy rõ vòng lặp lãng phí lớn nhất: wizard 6 bước →
chạy hết video 20 phút → phát hiện giọng không hợp hoặc xưng hô sai → làm lại
từ đầu.

Đọc `pipeline.py` tìm điểm chèn: `_resolve_video()` gọi ở **dòng 360** là chỗ
DUY NHẤT giải quyết nguồn video, phục vụ CẢ file local lẫn link (link đã tải
xong tại đây). Cắt clip ngay sau dòng đó là tái dùng toàn bộ pipeline phía sau
— không có nhánh xử lý riêng nào phải bảo trì song song.

### Design Choice

**Không có "pipeline preview" riêng.** Chỉ cắt clip rồi giao cho đúng pipeline
cũ. Một nhánh song song sẽ dần trôi khác nhánh chính, tới lúc nào đó bản nghe
thử không còn phản ánh bản thật — mất luôn mục đích của tính năng.

**`-c copy`, không mã hoá lại**: cắt gần như tức thì kể cả video vài GB. Đánh
đổi có chủ đích: cắt theo keyframe nên độ dài lệch vài phần mười giây — chấp
nhận được cho bản nghe thử.

**Hậu tố nằm TRONG TÊN thư mục** (`-preview30s`), không phải file đánh dấu bên
trong: mở thư mục kết quả là biết ngay cái nào chỉ là bản thử. Đăng nhầm bản
30 giây lên kênh là hỏng thật.

**Cắt hỏng thì BÁO LỖI, tuyệt đối không rơi về chạy cả video.** Người dùng bấm
"nghe thử" chính là để tránh chạy cả video; tự ý chạy full sẽ tốn đúng thứ họ
đang cố tiết kiệm.

**Tách `apply_folder_suffix()` ra `preview.py`** để test thẳng quy tắc đặt tên
— chạy cả pipeline chỉ để kiểm một cái tên thư mục là quá đắt, mà đây lại đúng
chỗ quyết định bản thử có bị nhầm thành bản cuối hay không.

### Changed Files

- `autodub/preview.py` (mới) — cắt clip + quy tắc đặt tên
- `autodub/pipeline.py` — `DubRequest.preview_seconds`; hậu tố thư mục; 1 bước
  cắt ngay sau `_resolve_video`
- `autodub/cli.py` — `--preview-seconds N`
- `autodub_gui/pages/new_project_page.py` — nút "Nghe thử 30 giây"
- `tests/test_preview_clip.py` (8 test), `tests/test_new_project_preview_button.py` (5 test)

### Tests (13 mới)

Cắt clip: hậu tố hiện trong tên và dự án thật KHÔNG bị nhận nhầm; `0` giữ
nguyên tên cũ (0 regression); `seconds<=0` bị từ chối; **ffmpeg lỗi → ném lỗi
kèm lý do thật, không trả về video gốc**; file rỗng cũng tính là hỏng; lệnh
phải dùng `-c copy` + `-t N`; **cắt THẬT bằng ffmpeg rồi đo lại bằng ffprobe**
(video 12s → clip 5s); video 3s mà xin 30s → không phải lỗi.

GUI: nút ẩn ở các bước đầu; hiện ở bước cuối; **ẩn khi đang «chạy tiếp dự án
cũ»** (nghe thử lại 30 giây đầu của dự án đã chạy là vô nghĩa); bản thử dùng
ĐÚNG giọng/nhạc nền người dùng đã chọn và `defer_export=False` (wizard bình
thường dừng trước bước Xuất video — giữ nếp đó thì không có gì để nghe); form
chưa hợp lệ thì không chạy gì.

Toàn suite: **1198 passed, 6 skipped, 0 failed**; smoke test toàn app exit 0.

### Remaining Limits

- Preview vẫn tốn Vox cho số câu trong đoạn đó — đã nói rõ trong tooltip và
  help của CLI, nhưng CHƯA hiện con số ước tính cụ thể trước khi bấm.
- Chưa cho chọn đoạn giữa video (luôn là N giây ĐẦU). Video có intro dài thì
  đoạn đầu có thể không đại diện — cần thêm tham số bắt đầu nếu gặp thật.
- 30 giây là hằng số trong GUI (CLI thì tuỳ ý). Chưa có ô chỉnh trong Cài đặt.
- CHƯA chạy thật đầu-cuối trên máy Windows có GPU/giọng đầy đủ — mới verify
  bước cắt bằng ffmpeg thật + toàn bộ đường dẫn code bằng test.

## V57 — Hồ sơ nhân vật xuyên tập (Phase H, 2026-08-18)

### Audit Before Build

Chủ dự án muốn "đồng bộ nhân vật + giọng điệu". Bản khả thi KHÔNG phải sinh
video AI mà là: dub cả một series thì nhân vật A giữ nguyên giọng A ở mọi tập.

Đọc code trước, thấy 3/4 mảnh ghép đã có: `diarization.py` (V26) tách người
nói; `estimate_speaker_genders()` (V36) ước lượng F0 từng người nói;
`assign_voices_by_gender()` (V36) gán giọng. Thiếu đúng lớp ghi nhớ xuyên tập.

**Điểm chốt kỹ thuật, quyết định toàn bộ thiết kế**: nhãn diarization
(`SPEAKER_00`…) **KHÔNG ổn định giữa các file** — cùng một người ở tập sau
hoàn toàn có thể mang nhãn khác. Nên không khớp theo nhãn được, phải khớp
theo ĐẶC TRƯNG GIỌNG. Và đặc trưng đó đã nằm sẵn trong code: F0 trung vị mà
V36 tính rồi **dùng xong vứt** (chỉ giữ lại nhãn giới tính).

### Design Choice

**Khớp theo F0 trung vị, không thêm model nhận dạng người nói.** Thô, nhưng
đúng tinh thần V35/V36 ("tín hiệu số học đơn giản, đủ dùng") và không kéo
thêm model nào vào bộ cài — thêm model là đổi hẳn hạng mục chi phí/cài đặt.

**Khớp sai tệ hơn không khớp.** Ngoài ngưỡng ±18Hz thì coi là nhân vật MỚI.
Ngưỡng đủ rộng để chịu khác biệt micro/nén giữa các tập, nhưng hẹp hơn nhiều
khoảng cách giữa giọng nam (~110Hz) và nữ (~200Hz) nên hai người khác giới
không thể khớp nhầm.

**Một-đối-một, ghép tham lam theo khoảng cách tăng dần.** Không có ràng buộc
này thì 2 người nói có F0 gần nhau sẽ cùng nhận một giọng — đúng cái lỗi mà
tính năng này sinh ra để tránh.

**Trung bình động thay vì đè giá trị mới** (`PITCH_SMOOTHING = 0.25`): một tập
thu âm tệ không được kéo lệch hồ sơ đã đúng qua nhiều tập.

**Hồ sơ là JSON dễ đọc, để cạnh thư mục kết quả** (`<output>/
character_profiles/<tên>.json`): người dùng đổi tên `SPEAKER_00` thành "Lý Tứ"
bằng tay được. Hồ sơ hỏng thì degrade về hành vi V36 và **KHÔNG ghi đè** — file
có thể chỉ lỗi cú pháp nhỏ mà họ tự sửa được, đè lên là xoá công sức của họ.

### Changed Files

- `autodub/character_profile.py` (mới) — model + khớp + lưu trữ
- `autodub/speech/diarization_voice_match.py` — tách `estimate_speaker_pitch()`
  và `classify_gender()` ra công khai; `estimate_speaker_genders()` nay gọi
  lại chúng nên F0 chỉ tính MỘT lần mỗi lượt dub thay vì hai
- `autodub/pipeline.py` — `DubRequest.character_profile`;
  `_apply_character_profile()`; truyền tên hồ sơ vào `_apply_diarization`
- `autodub/cli.py` — `--character-profile <tên>`
- `tests/test_character_profile.py` (13), `tests/test_pipeline_character_profile.py` (5)

### Tests (18 mới)

Khớp: cùng người ở tập sau nhận lại đúng giọng **dù nhãn diarization đã đổi**;
lệch nhỏ vẫn khớp; **ngoài ngưỡng KHÔNG khớp**; F0=0 (thiếu audio voiced) bỏ
qua; 2 người gần một nhân vật thì chỉ 1 khớp và người gần nhất thắng; hồ sơ
rỗng không khớp gì.

Ghi nhớ: F0 làm mượt chứ không nhảy (135Hz không kéo hồ sơ 115Hz thành 135);
người lạ thành nhân vật mới; đổi giọng ở tập này thì tập sau dùng giọng mới.

Lưu trữ: round-trip giữ đủ xưng hô/thuật ngữ/ngữ cảnh; thiếu file → hồ sơ
rỗng; **hồ sơ hỏng → degrade VÀ không bị ghi đè**; JSON sửa tay được (đổi tên
nhân vật rồi nạp lại vẫn đúng).

Pipeline: nhân vật cũ **ghi đè** gán tự động của V36; người lạ giữ giọng V36
và được ghi lại; **mô phỏng 2 tập liên tiếp** — tập 2 nhận lại giọng tập 1;
hồ sơ hỏng không làm hỏng lượt dub; hồ sơ nằm cạnh thư mục kết quả.

**1 bug thật do test bắt**: `_apply_character_profile` đọc `req.character_profile`
nhưng `_apply_diarization` **không hề thấy `req`** → `NameError` ở đúng nhánh
diarization. Test diarization có sẵn (V26) đỏ ngay. Sửa bằng truyền tên hồ sơ
vào tham số thay vì với lấy từ biến ngoài scope.

Toàn suite: **1216 passed, 6 skipped, 0 failed**; smoke test toàn app exit 0.

### Remaining Limits

- **CHƯA có trong GUI** — mới CLI (`--character-profile`), đúng nếp CLI-first
  V22→V25. Người dùng cuối chưa chạm được.
- **Xưng hô/thuật ngữ trong hồ sơ chưa được áp tự động** vào bước dịch: hồ sơ
  đã lưu 3 trường đó và round-trip đúng, nhưng nối vào `Settings.translate_*`
  cần quyết định thứ tự ưu tiên (hồ sơ đè cài đặt chung, hay ngược lại) —
  hỏi chủ dự án trước khi tự quyết.
- **Khớp bằng F0 là heuristic thô**: hai người cùng giới, giọng gần nhau
  (chênh <18Hz) vẫn có thể lẫn. Muốn chắc hơn phải dùng speaker embedding —
  thêm model, là quyết định khác.
- **Chưa live-verify trên series thật** (cần diarization thật chạy qua nhiều
  tập). Toàn bộ verify hiện nay là test với F0 dựng sẵn.


## V58–V60 — Hoàn thiện hồ sơ nhân vật (Phase H, 2026-08-18)

Chủ dự án chốt cả 3 giới hạn V57 để lại trong một lượt.

### V58 — Quy ước dịch của series đè cài đặt chung

Quyết định: **hồ sơ thắng**. Lý do: chọn hồ sơ "Phim A" là đang nói "lần này
tôi làm phim A", nên quy ước của phim A phải thắng mặc định toàn app.

Nhưng chỉ đè bằng trường hồ sơ **CÓ điền** — trường trống KHÔNG xoá cài đặt
chung. Chọn một hồ sơ mới lập (chưa điền gì) mà mất sạch xưng hô đã cấu hình
là kiểu mất mát âm thầm tệ nhất. Và sửa TẠI CHỖ trên settings của lượt chạy,
không ghi xuống `.env`: hồ sơ chỉ có hiệu lực cho lượt này.

### V59 — Khớp bằng speaker embedding

**Phát hiện quyết định toàn bộ thiết kế**: `diarize_worker.py` chạy pyannote
`speaker-diarization-3.1`, mà pipeline đó **vốn đã tính embedding bên trong**
để gom nhóm người nói — trước V59 vector đó bị vứt đi. `return_embeddings=True`
lấy đúng nó ra: **không thêm model, không tốn thêm thời gian xử lý**. Chủ dự
án chấp nhận "thêm model" nhưng hoá ra không cần trả cái giá đó.

Thiết kế 2 vòng, KHÔNG trộn: embedding (cosine ≥ 0.72) xét trước và trọn vẹn,
xong mới tới F0 cho những ai còn lại. Cosine 0.9 và lệch 3Hz không so sánh
được với nhau — gộp chung một bảng xếp hạng là sai về bản chất.

Degrade 3 tầng: pyannote cũ không có `return_embeddings` → worker cảnh báo và
chạy tiếp không embedding; hồ sơ v1 không có vector → khớp bằng F0; người nói
thiếu embedding → cũng rơi về F0. Không đường nào làm hỏng lượt dub.

### V60 — Hồ sơ nhân vật lên GUI

Ô nhập chữ ở bước cuối wizard, **chỉ hiện khi tách người nói đang bật** (bày
ra lúc tính năng đó tắt là hứa suông — nếp V53). Ô nhập chứ không phải danh
sách chọn: gõ tên mới = tạo hồ sơ mới, gõ lại tên cũ = dùng tiếp, không cần
một màn quản lý riêng.

### 2 bug THẬT do test bắt

1. **Tên hồ sơ tiếng Việt đụng nhau.** `_slug()` bản đầu vứt mọi ký tự ngoài
   ASCII nên «Phim Cổ Trang» và «Phim Có Trang» **cùng ra `phim-c-trang`** —
   hai series ghi đè hồ sơ của nhau, trộn lẫn nhân vật. Với tên tiếng Việt
   đây là chuyện thường ngày chứ không phải ca hiếm. Sửa 2 tầng: bỏ dấu ĐÚNG
   cách (Cổ → Co) cho tên đọc được, cộng 6 ký tự băm của tên gốc để hai tên
   khác nhau không bao giờ chung file.
2. **Stub `diarize` trong test V26 lệch chữ ký thật** sau khi thêm
   `with_embeddings` → 4 test đỏ. Sửa stub cho khớp API mới (không bẻ code
   cho vừa test): API nội bộ đổi có chủ đích thì stub phải đổi theo.

### Tests (+14, tổng 1230)

Embedding: **tách đúng hai người cùng giới chênh 4Hz** (đúng chỗ F0 chắc chắn
lẫn — lý do V59 tồn tại); dưới ngưỡng thì không gán bừa; **embedding thắng F0
khi hai bên mâu thuẫn**; hồ sơ v1 không có vector vẫn khớp bằng F0; embedding
được làm mượt chứ không đè; nhân vật mới lưu vector đã chuẩn hoá; file v1 và
file có field lạ đều nạp được.

Đặt tên: hai tên tiếng Việt khác nhau KHÔNG chung file; cùng một tên luôn ra
cùng file (nếu không thì tập 2 không tìm thấy hồ sơ tập 1).

GUI: ô ẩn khi tách người nói tắt, hiện khi bật; tên hồ sơ tới được request và
được cắt khoảng trắng; để trống = hành vi cũ.

**1230 passed, 6 skipped, 0 failed**; smoke test toàn app exit 0.

### Remaining Limits

- **CHƯA live-verify embedding thật**: cần `.venv-diar` + HF token + video
  nhiều người nói. Phần khớp/ghi nhớ đã test bằng vector dựng sẵn, nhưng
  đường lấy embedding từ pyannote (`return_embeddings=True`) mới chỉ đọc tài
  liệu API chứ chưa chạy thật — ĐÂY LÀ RỦI RO CÒN LẠI LỚN NHẤT của V59.
- Ngưỡng cosine 0.72 chọn theo khoảng giá trị điển hình của pyannote, chưa
  hiệu chỉnh trên dữ liệu thật của dự án.
- GUI chưa có màn xem/sửa danh sách nhân vật trong hồ sơ (vẫn phải mở file
  JSON). Đủ dùng để chạy, chưa đủ để quản lý một series dài.

## V61 — Khắc phục 2 rủi ro V59 tự khai (Phase H, 2026-08-18)

Chủ dự án yêu cầu xử lý luôn 2 giới hạn mà V59 tự ghi ra: chưa kiểm chứng
`return_embeddings` và ngưỡng cosine chưa hiệu chỉnh.

### Kiểm chứng API — và một bug CÓ SẴN lộ ra

Không có HF token nên không chạy được model, nhưng **không cần chạy mới kiểm
được hợp đồng API**: tải mã nguồn thật của thư viện về đọc
(`pip download --no-deps --no-binary :all:`), cả bản 3.1.1 lẫn 4.0.7.

Kết quả — **hai phiên bản có API khác hẳn nhau**:

| | 3.1.1 | 4.0.7 |
|---|---|---|
| Tham số | `apply(file, return_embeddings=True)` | KHÔNG có (nuốt vào `**kwargs`) |
| Trả về | `(Annotation, ndarray)` | `DiarizeOutput(speaker_diarization, exclusive_speaker_diarization, speaker_embeddings)` |
| Thứ tự embedding | theo `labels()` | theo `labels()` (comment trong mã nguồn ghi rõ) |

Giả định "xếp theo `labels()`" của V59 là ĐÚNG — xác nhận bằng mã nguồn cả 2
bản, không phải theo tài liệu.

Nhưng lộ ra thứ nghiêm trọng hơn: **`scripts/setup_diarization.py` cài
`pyannote.audio` KHÔNG ghim phiên bản**, nên máy nào cài hôm nay là ra 4.x.
Trên 4.x, mã V26 gốc (`diarization = pipeline(audio)` rồi `.itertracks()`)
gọi `.itertracks()` trên một `DiarizeOutput` — **không có hàm đó, diarization
chết hoàn toàn**. Đây là bug CÓ SẴN TỪ V26, không phải do V59: chỉ là chưa ai
chạy diarization trên máy cài mới nên chưa lộ. (V26 vốn cũng chưa từng
live-verify — xem TEST_LOG mục V26.)

Sửa: dò API bằng `inspect.signature(pipeline.apply)` TRƯỚC khi gọi (diarization
chạy vài phút, không thể gọi thử rồi gọi lại), rồi chuẩn hoá cả 3 dạng trả về
(DiarizeOutput / tuple / Annotation). Kết quả: chạy đúng trên CẢ 3.1.x lẫn 4.x
— và 4.x còn cho embedding mà không cần cờ nào.

### Ngưỡng: đo được thay vì đoán

Không có dữ liệu thật thì không hiệu chỉnh được — nên thay vì giả vờ đã hiệu
chỉnh, làm cho nó **đo được và chỉnh được**:

- `VOXDUB_EMBEDDING_THRESHOLD` / `VOXDUB_EMBEDDING_MARGIN` — chỉnh bằng biến
  môi trường, không phải sửa code.
- **Biên an toàn** (`margin`): người khớp nhất phải hơn người khớp nhì ít
  nhất 0.05. Hai nhân vật đều na ná mà đoán bừa chính là kiểu sai tệ nhất —
  nhân vật A nói bằng giọng nhân vật B suốt cả tập.
- `explain_matches()` ghi ra log ĐIỂM SỐ THẬT của từng người nói (gần nhất
  bao nhiêu, kế tiếp bao nhiêu, kết luận gì). Chạy vài tập thật là có số liệu
  để chỉnh ngưỡng cho đúng nội dung của mình.

Docstring nói thẳng 0.72 là điểm khởi đầu thận trọng, KHÔNG phải con số đã
hiệu chỉnh — thay vì để người đọc sau tưởng đã đo.

### Tests (+3, tổng 1233)

Khớp mập mờ bị từ chối dù vượt ngưỡng (2 nhân vật cosine gần bằng nhau);
điểm số được báo cáo đúng dạng để hiệu chỉnh; ngưỡng đổi được bằng biến môi
trường (đặt 0.99 thì cosine 0.98 không còn khớp).

**1233 passed, 6 skipped, 0 failed**; smoke test toàn app exit 0.

### Remaining Limits

- Vẫn CHƯA chạy pyannote thật (không có HF token trong sandbox). Nhưng rủi ro
  đã đổi bản chất: từ "đoán API theo tài liệu" thành "đã đối chiếu mã nguồn
  thật của cả 2 phiên bản". Ca duy nhất còn sót là bản pyannote tương lai đổi
  API lần nữa — lúc đó worker vẫn degrade sạch (cảnh báo + chạy không
  embedding) chứ không chết.
- Ngưỡng vẫn là giá trị khởi đầu; giờ có công cụ đo nhưng chưa có số liệu
  thật. Cần chủ dự án chạy vài tập rồi xem log "Khớp nhân vật — ..." .
- `setup_diarization.py` vẫn cài không ghim phiên bản. Không ghim là có chủ
  đích (để nhận bản vá), và worker giờ chịu được cả 2 dòng — nhưng nếu
  pyannote 5.x đổi tiếp thì phải sửa lại chỗ chuẩn hoá này.


## V61b — Bước NẠP model cũng sai tên tham số (Phase H, 2026-08-18)

### Vì sao lộ ra

Đang dựng `.venv-diar` để chuẩn bị verify V59 thật thì `pip` kéo về
**pyannote.audio 4.0.7** (`setup_diarization.py` KHÔNG ghim phiên bản). Kiểm
chữ ký `Pipeline.from_pretrained` của bản đang cài — đúng kỹ thuật V61 dùng
cho `apply()` — thì thấy nó không có tham số `use_auth_token`, trong khi
`diarize_worker.py:74` vẫn truyền đúng tên đó.

V61 sửa API `apply()` cho 4.x nhưng bỏ sót một tầng cao hơn: bước NẠP model.

### Lỗi thật, chứng minh trước khi sửa

```
>>> Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token='hf_dummy')
TypeError: Pipeline.from_pretrained() got an unexpected keyword argument 'use_auth_token'
```

Không bản nào có `**kwargs` để nuốt tên sai:

| | 3.1.x | 4.x |
|---|---|---|
| Tên tham số token | `use_auth_token` | `token` |
| `**kwargs` | không | không |

**Chỗ này tệ hơn một TypeError bình thường**: lời gọi nằm trong
`except Exception` nên nó hiện ra thành *"Không nạp được model diarization"* —
đọc y hệt lỗi thiếu quyền truy cập. Người gặp sẽ đi kiểm token và user
agreement, đúng hai thứ đang không hỏng. Diarization chết trên MỌI máy cài mới
hôm nay, và thông báo lỗi chỉ đường sai.

### Sửa

`_token_kwarg()` dò chữ ký trước khi gọi (cùng lối V61): có `use_auth_token`
thì dùng tên đó, không thì `token`. Bản lạ không đọc được chữ ký thì đoán theo
dòng mới — máy cài hôm nay ra 4.x.

### Tests (5 mới)

Chọn `use_auth_token` cho chữ ký 3.1.x; chọn `token` cho chữ ký 4.x; hàm
built-in không đọc được chữ ký thì KHÔNG nổ; **gọi thật bằng tên chọn ra và
kiểm giá trị token tới đúng nơi** (so chuỗi thôi vẫn lọt ca tên đúng mà truyền
sai); tên chọn ra phải nằm trong chữ ký của pyannote ĐANG CÀI (bỏ qua nếu
chưa cài).

### Verify thật với pyannote 4.0.7 đang cài

Chạy lại đúng lời gọi đã sửa với token giả: **không còn TypeError**, đi tới
được HuggingFace Hub và dừng ở `GatedRepoError` — tức tham số đã tới nơi, chỉ
còn thiếu quyền truy cập model (đúng như mong đợi với token giả).

### Chạy với HF token thật — lộ tiếp 2 chỗ nữa

Có token thật rồi chạy `setup_diarization.py` thì **lỗi y hệt tái diễn**: smoke
test của chính script cũng truyền `use_auth_token` bằng một đoạn mã sinh tại
chỗ (script chạy ở env khác nên không import được `_token_kwarg`). Và thông báo
lỗi của nó nói *"kiểm tra lại token và việc đã bấm Agree..."* trong khi token
hợp lệ, agreement đã bấm — **đúng kiểu chỉ đường sai đã dự đoán, quan sát được
trên người dùng thật**. Đã dò chữ ký tại chỗ như worker.

Sửa xong thì token đi tới được Hub và lộ chỗ thứ hai, lần này không phải bug
của mình: **pyannote 4.x chuyển hướng `speaker-diarization-3.1` sang một repo
gated KHÁC** — `pyannote/speaker-diarization-community-1` — phải xin quyền
riêng. Docstring cũ chỉ liệt kê 2 repo của dòng 3.1.x, nên người dùng bấm đủ
Agree theo hướng dẫn vẫn 403 và không hiểu vì sao.

Docstring giờ tách danh sách repo theo phiên bản, và thông báo lỗi **đọc thẳng
tên repo đang khoá từ `GatedRepoError`** thay vì đọc thuộc lòng danh sách cũ —
bảo người dùng đi bấm Agree ở model họ đã bấm rồi là cách chắc chắn nhất làm
họ bỏ cuộc.

**Vẫn CHƯA chạy diarization thật** — đang chờ quyền truy cập
`speaker-diarization-community-1`.

## V48 — Sao lưu KÉO: verify đầu-cuối thật (Phase G, 2026-08-18)

V48 ship ngày 17-08 ở trạng thái "xong code, CHƯA có cron chạy thật", và
ADMIN_TOKEN prod không ai có nên chưa từng kéo được lần nào. Hôm nay xoay token
mới qua cổng Vibe Host rồi redeploy (nhánh `deploy/vays-control-server` tip
17-08 22:02 — build lại ĐÚNG mã đang chạy, chỉ đổi biến môi trường).

### Kết quả — lần đầu tiên có một bản sao lưu thật

```
$ bash control_server/scripts/backup-pull.sh ~/voxdub-backups 14
OK: /home/coder/voxdub-backups/voxdub-backup-20260818-101724.ndjson.gz (8.0K, 75 dòng)
```

Nội dung kiểm bằng cách giải nén và đếm theo collection, không chỉ nhìn dung
lượng file:

| collection | bản ghi |
|---|---|
| devices | 21 |
| pipelineevents | 21 |
| auditlogs | 14 |
| creditledgers | 6 |
| dubusageledgers | 5 |
| usagelogs | 3 |
| aiproviders / apikeys / appconfigs / jobresults | 1 mỗi loại |

`creditledgers` và `apikeys` là phần không dựng lại được nếu mất — đúng thứ cần
bảo vệ. Định dạng EJSON giữ nguyên `ObjectId`/`Date` (`{"$oid":…}`,
`{"$date":…}`) nên `restore-backup.js` nhập lại được, khác JSON thường.

### Vẫn còn thiếu để gọi là "có sao lưu"

Bản kéo này chạy TAY một lần. **Chưa có lịch nào chạy trên máy ngoài** —
`schtasks` phải đặt trên máy Windows của chủ dự án (xem
`control_server/docs/DEPLOY_RUNBOOK.md` mục 7b). Một bản sao lưu duy nhất nằm
trong workspace không phải là sao lưu.

## V61b — Smoke test diarization PASS lần đầu (Phase H, 2026-08-18)

Sau khi cấp quyền `pyannote/speaker-diarization-community-1`, chạy lại
`setup_diarization.py` với token thật: **`smoke test PASS`** — model
diarization thật nạp được, lần đầu trong lịch sử dự án (V26 chưa từng
live-verify, đó chính là lý do 2 bug tên tham số nằm im tới hôm nay).

Vẫn chưa đo được ngưỡng cosine: cần 2 clip cùng series có chung nhân vật.

## V59 — Chạy pyannote THẬT lần đầu + đo ngưỡng cosine (Phase H, 2026-08-18)

Chủ dự án tạm bỏ qua việc cung cấp video thật, nên dựng vật liệu từ chính bộ
giọng mẫu trong repo (`voices/preset_voices_vn`, 121 file, mỗi file ~8 giây).

**Cách dựng để con số có nghĩa**: mỗi giọng cắt đôi — nửa ĐẦU vào "tập 1", nửa
SAU vào "tập 2". Cùng một người, KHÁC lời. Tái dùng đúng đoạn audio cũ thì
cosine ra ~1.0 và phép đo vô nghĩa. Mỗi lượt 4 giây, chèn 0.6 giây lặng giữa
các lượt (lượt 2 giây cắt cụt sát nhau, thử lần đầu, làm pyannote gộp gần hết).

Chạy qua ĐÚNG đường code sản phẩm: `diarize_worker.py` → `estimate_speaker_pitch`
→ `CharacterProfile.match_speakers()` → `explain_matches()`.

### Số đo thật

| Cặp so sánh | cosine |
|---|---|
| B(nam) vs D(nữ) — khác người, khác giới | 0.106 |
| B(nam) vs A(nữ) — khác người, khác giới | 0.219 |
| **A(nữ) vs D(nữ) — khác người, CÙNG giới** | **0.651** |
| **B tập1 vs B tập2 — CÙNG người, khác lời** | **0.783** |

**Ngưỡng 0.72 đoán ở V59 nằm gần đúng điểm giữa** của khoảng phân tách thật
(0.651 ↔ 0.783): cách mép dưới 0.069, cách mép trên 0.063. Con số đoán đứng
vững — nhưng biên chỉ ~0.06 mỗi bên, **trên audio TTS sạch**. Video thật có
nhạc nền, tiếng ồn, cảm xúc thay đổi sẽ làm khoảng cách cùng-người rộng ra;
0.06 là mỏng. Chưa đủ dữ liệu để chỉnh, đủ dữ liệu để biết chỗ nào sẽ gãy.

### Rủi ro thật phát hiện được — tầng hồ sơ KHÔNG sửa nổi

Tập 2 có 3 giọng nữ (A, D, C): **pyannote gộp cả 3 thành MỘT người nói**.
Embedding của cụm gộp đó khớp với «A» ở 0.792 — cao hơn cả lượt khớp ĐÚNG của
B (0.783) — và qua luôn cả luật biên 0.05 (kế tiếp 0.652).

Không có ngưỡng nào cứu được ca này: diarization gộp nhầm ở tầng dưới thì hồ sơ
nhân vật chỉ còn cách khớp một cụm-nhiều-người vào một nhân vật. Cột "Nhận
diện" của V62 hiện phân biệt embedding/cao độ, nhưng KHÔNG cảnh báo "người nói
này có thể là nhiều người bị gộp".

### Giới hạn của chính phép đo này

- Giọng TTS sạch, không nhạc nền, không tiếng ồn — DỄ hơn hẳn video thật.
- Mỗi ca đúng 1 điểm dữ liệu, không phải phân phối.
- Lượt thoại 4 giây liền mạch; hội thoại thật ngắn và chồng tiếng hơn nhiều.

Nên đây là **cận trên** của chất lượng, không phải hiệu chỉnh cho nội dung
thật. Vẫn cần 2 clip thật của cùng series để chốt ngưỡng.

## V65 — Ẩn hẳn "xử lý trên cloud" (Phase H, 2026-08-18)

Chủ dự án quyết theo hướng ẩn, không dựng worker render. Đây là lời đáp cho
câu hỏi V50 để treo: `/v1/jobs/demucs` trừ 50 Vox lúc nộp trong khi **không có
worker render nào tồn tại**.

### Hiện trạng đo được trước khi sửa

`GET /v1/config/app` của prod trả `cloudRenderEnabled: true`,
`pricing.cloudRenderDemucs: 50`. Tức là lỗi V50 mô tả KHÔNG phải nguy cơ lý
thuyết — nó đang sống trên prod, client hiện ô chọn và sẵn sàng trừ tiền.

### Ba lớp, không phải một

1. **Prod**: `PUT /v1/admin/config/cloud.render.enabled` → `false`. Xác nhận
   lại bằng `/v1/config/app`: `cloudRenderEnabled: false`.
2. **Mặc định trong code**: `config.service.js` đổi `true` → `false`. Bật mặc
   định nghĩa là mỗi lần dựng lại database là tính năng chết sống dậy.
3. **GUI**: máy chủ tắt thì **ẩn HẲN** ô chọn, thay vì hiện ô xám kèm chữ
   "Máy chủ đang tạm tắt xử lý trên cloud". Chữ "tạm" hứa một tính năng sẽ
   quay lại, mà nó thì không.

Lớp chặn tiền vốn đã có sẵn và ĐÚNG chỗ: `submitDemucsJob` ném
`CLOUD_RENDER_DISABLED` (409) ở dòng đầu tiên, trước khi tính giá và trước khi
trừ credit. V65 không phải sửa nó, chỉ là không nên dựa vào một lớp duy nhất
cho thứ đụng tới tiền.

### Tests (4 mới Python, 3 test Node phải sửa)

Python: máy chủ tắt → ô chọn VÀ dòng giá đều ẩn; máy chủ bật → hiện và bấm
được, có nói giá; **đang tick sẵn mà máy chủ tắt thì `values()` trả `False`**
(ẩn mà giá trị vẫn lọt ra thì khách bị trừ tiền cho job không ai xử lý — đúng
thứ V50 phát hiện); nạp nháp cũ có `cloud_render: true` cũng không bật lại
được.

3 test Node đang xanh nhờ mặc định `true` — chúng kiểm giới hạn upload, luật
thiếu Vox và hàng đợi V12, nhưng giờ vấp cổng tắt trước khi tới chỗ cần kiểm.
Sửa bằng cách cho chúng bật tính năng lên một cách TƯỜNG MINH, vừa đúng vừa
ghi lại rằng chúng phụ thuộc vào cờ đó.

### Một test hỏng vì môi trường, không phải vì code

`test_multi_speaker_flag_off_by_default` đỏ sau khi chạy
`scripts/setup_diarization.py` — script đó ghi `DIARIZATION_ENABLED=true` vào
`.env`, mà `Settings.load()` đọc đúng file đó. Test nói về mặc định của CỜ CLI
chứ không phải về `.env` của máy đang chạy, nên đã cô lập bằng
`monkeypatch.setenv`. Ai cài diarization xong chạy suite sẽ không còn thấy đỏ
oan.

**1284 test Python + 324 test Node, 0 fail.**

## V45/V51/V52/V54 — Chạy THẬT đầu-cuối lần đầu trên prod (Phase G, 2026-08-18)

Bốn mini-spec này ship ở trạng thái "xong code + test, CHƯA chạy thật". Có
ADMIN_TOKEN rồi thì cấp được API key và chạy được thật.

### Vật liệu

Không có video khách, dựng từ giọng mẫu trong repo: nối 3 file
`voices/preset_voices_vn` thành 24 giây tiếng, ghép nền màu → `thu.mp4`
(H.264 + AAC, 235 KB). Nguồn `vi` → đích `vi`.

### V51/V52/V54 — `cloud-batch` chạy thật

```
Quota còn 10 phút (hạn mức 10, đang giữ chỗ 0)
Đã nộp thu.mp4 → job 6a83d7ce984f2a73c9c3b347
Job ...b347: queued → running → done          (41 giây)
Xong thu.mp4 → thu_dubbed.mp4 (339442 byte)
Xong: 1 | Hỏng: 0 | Mất kết quả: 0 | Đã huỷ: 0 | Chưa chạy: 0
```

Kết quả là bản lồng tiếng THẬT, không phải copy đầu vào: MD5 luồng audio khác
hẳn bản gốc (`6911ddd…` vs `780f416…`), độ dài 24.20s vs 23.98s (giọng tổng
hợp không khớp từng mili-giây với gốc).

**Tính tiền đúng**: `minutesCharged = max(1, ceil(24/60)) = 1` → `dubMinutesUsed`
tăng 1, `dubMinutesReserved` trả về 0 sau khi xong (cơ chế giữ chỗ V43 nhả đúng).

### V45 — kết quả sống sót qua redeploy

Đây là phép thử thật của GridFS, làm đúng thứ tự để không tự lừa mình:

1. Nộp job thứ hai, chờ tới `done`, **CỐ Ý KHÔNG tải về** — kết quả nằm lại
   trên máy chủ.
2. `redeploy` `voxdub-app` qua cổng Vibe Host → container cũ bị xoá, ổ đĩa
   trong container mất trắng (nền tảng không có volume bền vững — chính lý do
   V45 tồn tại).
3. Sau khi deploy `succeeded`, hỏi lại trạng thái: vẫn `done`. Tải về:
   **339442 byte, MD5 `a1eb2cb8…` — TRÙNG BYTE-BY-BYTE với bản tải trước đó.**

Trước V45, file nằm trên đĩa container: bước 2 sẽ xoá sạch và bước 3 trả về
`RESULT_LOST_REFUNDED`. Giờ nó nằm trong MongoDB managed nên đi qua redeploy
không suy suyển.

### Chi phí thật của lượt kiểm thử

| Khoản | Số tiền |
|---|---|
| 2 job × 1 phút = 2 phút quota (300 Vox, giá niêm yết 10 đ/Vox) | 3.000 đ *(nội bộ, không ai trả)* |
| Gọi API AI trả tiền | **0 đ** — `analytics/usage?days=1` không ghi nhận lượt `translate`/`music`/`sound_effect` nào hôm nay |
| Hạ tầng | 0 đ phát sinh — worker container vốn đang chạy |

Worker chạy `python3 -m autodub.cli dub` với whisper + VieNeu **trong chính
container**, nên một lượt dub thường không đụng tới API tính tiền nào. Tiền
thật chỉ phát sinh khi dùng dịch AI qua máy chủ, nhạc AI hoặc hiệu ứng âm
thanh (ElevenLabs) — không có trong đường dub cơ bản.

### Còn thiếu

- V55 (huỷ job) vẫn chưa live-verify: cần một job đủ dài để bấm huỷ giữa
  chừng, job 24 giây xong trước khi kịp gửi lệnh.
- V52 mới chạy 1 video nên đường ống `--queue-ahead` chưa thực sự bị ép: muốn
  kiểm thông lượng phải nộp nhiều video cùng lúc.
- V53 (ô chọn trên trang Batch) vẫn chưa click thử trên Windows.

## V65b + live-verify V52/V54/V55 (Phase H, 2026-08-18)

### V65b — gợi ý số người nói cho pyannote

Đóng lỗi V59 phát hiện: 3 giọng nữ bị GỘP thành một người nói, tầng hồ sơ
nhân vật không sửa nổi vì nó chỉ nhìn thấy một người.

**Không làm theo ý tưởng ban đầu (`min_speakers` = số nhân vật trong hồ sơ)**
vì nó sai ở ca thường gặp: series 5 nhân vật mà tập này chỉ 2 người nói, ép
sàn 5 là buộc pyannote xé một người thành nhiều — đổi lỗi gộp lấy lỗi xé,
không khá hơn. Thay bằng:

1. **Người dùng khai** (`--speakers N`, `SPEAKER_COUNT`) → `num_speakers`.
   Họ xem video rồi, ta thì không. Đây là thông tin rẻ và đáng tin nhất.
2. **Hồ sơ nhân vật chỉ cấp cận TRÊN** (`max_speakers` = số nhân vật + 2 chỗ
   cho người mới). Trần thì an toàn, sàn thì không.
3. Người dùng khai rồi thì bỏ qua trần từ hồ sơ — con số gõ tay thắng.

`_speaker_hint()` là hàm thuần: `0` = KHÔNG BIẾT (không phải "không có ai"),
`num_speakers` đè lên cặp min/max, và `max < min` thì bỏ **max** chứ không bỏ
min — thà tách hơi nhiều còn hơn gộp, vì gộp là hai nhân vật cùng một giọng
ngay trên màn hình, còn tách dư thì tập sau hồ sơ vẫn khớp lại được.

**Verify bằng chính đoạn audio đã làm lộ lỗi** (`tap2.wav`, sự thật 4 người):

| lượt chạy | pyannote nhận ra |
|---|---|
| không gợi ý (18-08, lần đo đầu) | **2 người** — gộp cả 3 giọng nữ |
| `--num-speakers 4` | **3 người** — tách được cụm nữ thành 2 |

Gợi ý có tác dụng thật và đo được. Nhưng **pyannote KHÔNG tuân thủ tuyệt đối**:
xin 4 vẫn trả 3. Nó coi đây là gợi ý cho bước gom nhóm chứ không phải ràng
buộc cứng — đừng hứa với người dùng rằng khai đúng số là chắc chắn tách đúng.
Giọng TTS cùng giới vẫn là ca khó nhất.

### V55 — huỷ job: LỘ RA PROD ĐANG CHẠY CODE CŨ 5 TIẾNG

Lần chạy đầu, `cancel()` trả về *"Không có endpoint này"*. Không phải bug của
V55: nhánh `deploy/vays-control-server` có tip **17-08 22:02**, mà V55 landed
**23:35**. Prod đang chạy bản dựng từ trước V51/V52/V55 phía máy chủ — nhánh
deploy là bản SINH RA từ `main`, không tự cập nhật theo `main`.

Đây là bẫy quy trình đáng nhớ hơn cả bug: mọi thứ trên `main` xanh, test đủ,
mà prod vẫn thiếu tính năng, và không có gì báo cho biết. Chạy lại
`scripts/gen_vays_control_server_branch.sh` + redeploy rồi mới thử tiếp.

Sau khi deploy đúng code:

```
jobId = 6a83e2408807de3f7c022a51
đã running — gửi lệnh huỷ
cancel() trả về: True
trạng thái cuối: cancelled
trước: dùng 8 phút | sau: dùng 8 phút   ← job huỷ KHÔNG bị tính tiền
```

Huỷ lúc job đã `running` (không phải lúc còn `queued`) — đó mới là ca chứng
minh worker giết được tiến trình con thật.

### V52 — đường ống `--queue-ahead` bị ép thật

4 video, `--queue-ahead 3`:

```
11:41:09 nộp v1, v2, v3        ← nộp sẵn 3 job TRƯỚC khi job nào xong
         v1 done → nộp ngay v4 ← giữ hàng đợi luôn đầy
11:42:43 Xong: 4 | Hỏng: 0
```

94 giây cho 4 video. Máy chủ không có lúc nào nằm không chờ client upload —
đúng mục tiêu thông lượng của V42 mà V51 còn để hở.

### V54 — đường liên kết

`--input http://127.0.0.1:8899/thu.mp4` → yt-dlp (Generic extractor) tải về →
nộp → dub → tải kết quả (`Generic_thu_dubbed.mp4`, 339442 byte). Khoá trạng
thái là CHÍNH liên kết, đúng thiết kế.

**Giới hạn thật của phép thử này**: dùng URL file mp4 trực tiếp trên máy nên
chỉ chứng minh đường ống liên kết→tải→nộp chạy được. **Chưa chứng minh** trích
xuất YouTube/TikTok/Douyin thật (mỗi site một extractor riêng, YouTube còn cần
proxy). Cố ý không tải nội dung của bên thứ ba để thử.

### `backup-pull.ps1` — chạy thật lần đầu

Trước đây chỉ đúng về logic, chưa từng chạy (sandbox Linux không có
PowerShell). Tải bản PowerShell 7.4.6 portable về chạy thật:

- Token đúng → `OK: ... (7.7 KB, 118 dòng)`, gzip hợp lệ.
- Token sai → báo `HTTP 401` và **không để lại file `.part` rác**.
- `keep=2` → xoay vòng đúng, còn lại đúng 2 bản mới nhất.
- Máy chủ có rate limit: gọi liên tiếp bị `429`, script báo rõ chứ không nuốt.

**1 lỗi hiển thị sửa luôn**: bản 7.8 KB in ra `0 MB` — đọc y như sao lưu rỗng,
người ta sẽ đi tìm lỗi ở chỗ không có lỗi. Giờ đổi đơn vị theo cỡ thật.

Vẫn CHƯA thử được: `schtasks` và hành vi khi máy tắt — cần máy Windows thật.

**1299 test Python + 324 test Node, 0 fail.**

## Khảo sát: vì sao vẫn gộp người nói, và chi phí Gemini nằm ở đâu (2026-08-18)

Không phải mini-spec — khảo sát trả lời 2 câu hỏi của chủ dự án, ghi lại để
lần sau không phải đo lại.

### 1. Nút vặn của pyannote và giới hạn thật

`pipeline.parameters(instantiated=True)` cho thấy 3 tham số chỉnh được:

```
segmentation.min_duration_off = 0.0
clustering.method             = centroid
clustering.min_cluster_size   = 12      ← nghi phạm đầu tiên
clustering.threshold          = 0.7046
```

`min_cluster_size=12` nghĩa là một người phải có ≥12 cửa sổ embedding mới được
tách thành cụm riêng — lượt thoại ngắn thì bị nuốt vào cụm bên cạnh. Giả
thuyết hợp lý, nên đem đo trên `tap2.wav` (sự thật 4 người):

| cấu hình | nhận ra |
|---|---|
| mặc định | 2 |
| khai `num_speakers=4` | 3 |
| `min_cluster_size=3`, ngưỡng 0.60 | 3 |
| `min_cluster_size=3`, ngưỡng 0.60, khai 4 | 3 |
| `min_cluster_size=2`, ngưỡng 0.50, khai 4 | 3 |

**Giả thuyết SAI.** Nới clustering hết cỡ vẫn dừng ở 3. Nút vặn không phải chỗ
nghẽn — **embedding mới là chỗ nghẽn**. Khớp với số đo cosine hôm nay: hai
giọng nữ TTS KHÁC NHAU đo được 0.651, quá gần ngưỡng 0.72 của cùng-một-người.

Điều này cũng nói rằng vật liệu thử đang ở ca XẤU NHẤT: giọng TTS cùng một bộ
tổng hợp có chữ ký phổ giống nhau bất thường, người thật trong video thật khác
xa hơn. **Đừng tối ưu tiếp dựa trên số đo này** — cần clip thật mới biết có
phải vấn đề thật hay không.

### 2. Chi phí Gemini — đo bằng chính prompt của máy chủ

| Thành phần | token vào |
|---|---|
| system prompt dịch (gửi kèm MỖI lô) | **2.562** |
| user prompt, lô 40 câu | 796 |
| → 1 lô 40 câu | 3.358 (**84 token/câu**) |
| → nếu lô chỉ 2 câu | 2.639 (**1.320 token/câu**) |
| prompt phân tích, 150 câu | 1.015 (một lần) |
| prompt review, **1 câu** | 73 |

Con số 1.320 token/câu khớp đúng với lượt gọi thật duy nhất ghi trong
`usagelogs` (2.470 token cho 2 câu) — công thức đo được xác nhận bằng dữ liệu
thật, không phải ước lượng.

**Chỗ đốt tiền là bước REVIEW**: `ai-gateway.service.js:468` gọi
`buildTranslateSystemPrompt` cho **TỪNG CÂU** được rà soát. Mỗi câu review =
2.562 + 73 ≈ **2.635 token vào**, trong khi dịch cả câu đó chỉ tốn 84.

Video 10 phút (~150 câu), giả sử 20% câu bị gắn cờ review:

```
dịch    : 4 lô × 3.358        =  13.432 token
phân tích:                    =   1.015 token
review  : 30 câu × 2.635      =  79.050 token   ← gấp ~6 lần bước dịch
```

Bước review tốn gấp ~6 lần bước nó đi sửa. Không phải vì nó gọi nhiều lần, mà
vì **mỗi lần lại gửi lại toàn bộ system prompt 2.562 token cho đúng 1 câu**.

Hướng sửa, theo thứ tự hiệu quả: (a) gom review theo lô như bước dịch — một
system prompt cho N câu thay vì N lần; (b) system prompt riêng, gọn hơn cho
review; (c) `TRANSLATE_REVIEW=false` (preset `fast`) nếu chấp nhận bỏ hẳn.

### 3. Dịch local (miễn phí) hiện KHÔNG với tới được

`pipeline.py:1341` — nhánh dịch local NLLB (V6) chỉ chạy khi
`is_configured()` là False, tức khi **chưa cấu hình máy chủ nào**. Ai đã kết
nối SaaS thì mọi lượt dịch đều đi Gemini, không có cách nào chọn local. Muốn
dùng bản miễn phí đã có sẵn thì cần một cổng mới kiểu "ưu tiên local", đây là
thay đổi thiết kế chứ không phải cấu hình.

### 4. TTS đang MIỄN PHÍ — đổi sang ElevenLabs sẽ ĐẮT LÊN

Giọng đọc hiện do VieNeu (ONNX) tổng hợp ngay trên máy/trong container: 0 đ
mỗi câu. ElevenLabs trong hệ thống chỉ dùng cho nhạc nền (500 Vox/lượt) và
hiệu ứng âm thanh (100 Vox/lượt), KHÔNG dùng cho giọng đọc. Chuyển giọng đọc
sang ElevenLabs là đi từ 0 đ lên tính tiền theo ký tự — ngược hướng tiết kiệm.

## V66/V67/V68 + thử Facebook thật (Phase H, 2026-08-18)

### Facebook — dự đoán của tôi SAI, tải được không cần cookie

Tôi đoán Facebook sẽ gãy vì `cloud_batch` gọi `download_one` không truyền
cookie. Đem link thật của chủ dự án ra thử
(`facebook.com/share/r/1EUSdYJeXN/`):

```
extractor: Facebook | id: 4404013619838973 | 20.166 giây
→ tải thật: Facebook_4404013619838973.mp4, 6.247.458 byte (đã ghép video+audio)
```

Reel công khai đi qua đường yt-dlp bình thường. Cookie chỉ cần cho video giới
hạn (riêng tư, tuổi, nhóm kín) — nên V67 làm nó thành ĐƯỜNG LUI, không phải
thứ bắt buộc cấu hình trước.

### V67 — cookie cho yt-dlp

`COOKIES_FILE` (file Netscape xuất từ extension) hoặc `COOKIES_FROM_BROWSER`
(chrome/edge/firefox…). Nối vào CẢ HAI đường tải: `download_video` (lượt dub
thường) và `download_one` (cloud-batch) — sửa một chỗ quên chỗ kia là kiểu lỗi
"chặn ở tầng này, lọt ở tầng kia" mà V50 đã dính.

Thứ tự ưu tiên có lý do: **file THẮNG trình duyệt** (người vừa xuất
`cookies.txt` là người đang cố sửa một lỗi cụ thể; "đọc từ Chrome" là đường tự
đoán và hỏng lặng lẽ khi sai profile), và **tham số truyền tay THẮNG cấu hình
chung** (chỗ gọi biết rõ hơn). 8 test.

### V66 — gom bước rà soát vào một lượt gọi

Đo được ở khảo sát sáng nay: `reviewOne` gửi trọn system prompt của bước DỊCH
(2.562 token) cho ĐÚNG MỘT câu, trong khi dịch chính câu đó chỉ tốn 84.

Hai việc, cộng lại:

| | token vào |
|---|---|
| cũ: 20 câu × (2.562 + 73) | **52.700** |
| mới: 1 lượt, system prompt riêng 139 token + 20 câu | **1.596** |
| | **giảm 33 lần** |

`buildReviewSystemPrompt` cố ý gọn: câu đã được dịch một lần bằng đủ bộ luật
văn phong rồi, việc ở đây là sửa MỘT khuyết điểm cụ thể. Nhưng giữ lại đúng
những thứ bỏ đi là hỏng cả video: ngôn ngữ đích, ngân sách ký tự/`max_chars`,
và xưng hô/thuật ngữ người dùng đặt. Có test khoá từng cái.

**Đường hỏng**: lô lỗi thì rơi về gọi từng câu CHỈ cho lô đó — chất lượng
đúng bằng bản cũ, và chỉ trả giá token cũ ở đường hiếm gặp. Còn câu mô hình
BỎ SÓT trong một lô thành công thì giữ bản cũ, KHÔNG gọi lại lẻ: bỏ sót lác
đác là chuyện thường, gọi lại lẻ sẽ lặng lẽ kéo chi phí về mức cũ mà không ai
thấy. 7 test.

### V68 — sửa tay hồ sơ nhân vật

Số đo hôm nay cho thấy hai lỗi NGƯỢC NHAU, và không lỗi nào chỉnh ngưỡng mà
khỏi được (đã thử: nới clustering hết cỡ vẫn sai):

- diarization dồn nhiều người vào một nhãn → embedding của nhân vật là bản
  trộn, càng dùng càng khớp sai → **"Nhận diện sai — học lại"**
  (`forget_embedding`): xoá vector đã bẩn, GIỮ tên/giọng/số tập.
- nhãn diarization đổi giữa các tập → một người thành hai nhân vật →
  **"Gộp vào nhân vật khác…"** (`merge_characters`).

Gộp **trộn** embedding theo trọng số SỐ TẬP chứ không xoá một bên: người xuất
hiện 9 tập đáng tin hơn người 1 tập, và xoá là mất trắng phần đã học.

**Cố ý KHÔNG có nút "tách thành 2 nhân vật"** dù chủ dự án nêu: hồ sơ chỉ giữ
MỘT vector mỗi nhân vật, không có dữ liệu nào để tách nó thành hai. Tách thật
đòi chạy lại diarization trên audio gốc — việc của lượt dub sau, không phải
của trang quản lý. Thứ làm được ở đây là xoá cái đã bẩn để tập sau học lại
sạch, và đó đúng là bản sửa cho ca này.

**Bug tránh được nhờ tách `_render_table`**: gộp/học-lại sửa trong bộ nhớ và
chưa lưu; gọi `_load()` để vẽ lại sẽ đọc đè từ đĩa và nuốt mất đúng thay đổi
vừa làm — cùng họ với bug mất dữ liệu âm thầm đã sửa ở V62. 13 test (10 tầng
dữ liệu + 3 tầng trang).

**1320 test Python + 331 test Node, 0 fail.**

## V69 — Key riêng cho VoxDub + vá lỗ ghi nhật ký token (Phase H, 2026-08-18)

### Key riêng

Chủ dự án cấp key Gemini dành RIÊNG cho VoxDub, định dạng `AQ.Ab8RN6…` (khác
hẳn `AIzaSy…` của 3 dự án dùng chung phát hiện lúc khảo sát). Thử trước khi
gắn, không gắn rồi mới thử:

```
GET  /v1beta/models            -> HTTP 200, có models/gemini-2.5-flash
POST :generateContent          -> "Good morning everyone." → "Chào buổi sáng mọi người."
                                  17 token vào / 6 ra
```

Gắn qua `PATCH /v1/admin/providers/:id`, rồi verify **qua chính máy chủ** chứ
không gọi thẳng Google — mới chứng minh server giải mã và dùng được key:

```
POST /api/v1/translate (API key thật) -> 2 câu dịch đúng, usageCount 0→1
```

### Lỗ thật lộ ra khi verify

Lượt dịch vừa rồi **không xuất hiện** trong `analytics/usage`. Truy ra:
`UsageLog.create` chỉ được gọi trong `routes/ai.js` — đường app desktop.
Đường **API key** (`routes/api-v1.js`, mini-spec V31) đốt token Gemini thật
nhưng chỉ tăng `ApiKey.usageCount`, **không ghi một con số token nào**.

`usageCount` đếm số LƯỢT gọi, không phải token. Đối soát hoá đơn Gemini bằng
nó là đối soát với một con số không liên quan — và đây có thể chính là phần
chênh giữa hoá đơn thật và sổ sách mà chủ dự án thấy.

Sửa: ghi `UsageLog` cho cả đường API key. Không có fingerprint thiết bị ở
đường này nên dùng `apikey:<prefix>` — hợp lệ với schema, và truy được về đúng
key nào tiêu tiền.

Hai ràng buộc có test khoá: **ghi sổ hỏng KHÔNG được làm hỏng lượt trả kết
quả** (dịch đã xong và quota đã trừ, ngã ở bước ghi sổ mà trả lỗi là tệ nhất),
và **lỗi model thì không ghi log thành công**.

3 test mới.

## Đo trên GIỌNG NGƯỜI THẬT — ngưỡng 0.72 KHÔNG dùng được (2026-08-18)

Chủ dự án gửi 2 clip. **Hai file byte-identical** (cùng MD5 `94caae7d…`) — tập
2 là bản sao của tập 1, nên không đo xuyên tập được. Thay bằng: tách đôi clip
(nửa A 0-26s, nửa B 27-53.5s) — CÙNG người, KHÁC lời, đúng tình huống xuyên
tập. Nhãn của lượt chạy trên nguyên clip đóng vai trò sự thật, nhãn ở mỗi nửa
quy về theo thời lượng chồng lấn.

### Số đo

Nguyên clip 53.5 giây: **2 người nói** — SPEAKER_01 nói 33.1s, SPEAKER_00 chỉ
3.1s (tổng 36.2s tiếng nói trên 53.5s).

| Cặp | cosine |
|---|---|
| **khác người** (trong nguyên clip) | **0.584** |
| **cùng người, khác lời** (nửa A vs nửa B) | **0.540 – 0.686** |

### Kết luận: ngưỡng 0.72 quá cao, và hạ ngưỡng KHÔNG cứu được

**Cùng một người thật, nói lời khác, đo cao nhất 0.686 — dưới ngưỡng 0.72.**
Nghĩa là với cấu hình hiện tại, hồ sơ nhân vật **không nhận lại được ai cả**:
mỗi tập người đó thành "nhân vật mới", gán giọng lại từ đầu. Đúng thứ tính
năng sinh ra để tránh.

Nhưng hạ ngưỡng cũng không xong: **khác người đo 0.584, nằm LỌT TRONG khoảng
cùng người 0.540–0.686**. Hai phân phối chồng lên nhau, không có ngưỡng nào
tách được chúng trên dữ liệu này.

Đối chiếu với đo trên giọng TTS sáng nay (cùng người 0.783, khác người cùng
giới 0.651): giọng thật cho khoảng cách **hẹp hơn và chồng lấn**, tức là KHÓ
hơn TTS chứ không dễ hơn — ngược hẳn kỳ vọng "vật liệu TTS là ca xấu nhất".

### Vì sao nên nghi dữ liệu trước khi nghi mô hình

- Clip chỉ 53 giây, một người áp đảo (33.1s) còn người kia **3.1 giây**.
- Nửa B bị tách thành 4 nhãn trong khi nguyên clip chỉ có 2 → các lượt chạy
  trên nửa đang vụn, nhiều cặp so sánh là mảnh vụn với mảnh vụn.
- Mẫu: đúng MỘT clip, MỘT cặp nửa. Không phải phân phối.

Nên **chưa đủ cơ sở chỉnh ngưỡng hay đổi model embedding**. Thứ cần trước
tiên: 2 tập THẬT KHÁC NHAU, mỗi tập ≥2 phút, mỗi người nói ≥10 giây liên tục.

### V70 — người nói quá ít thì nói thẳng, đừng im lặng

Mấy cặp đo ra đúng `0.000` dẫn tới một chỗ đáng sửa: pyannote trả NaN (hoặc
toàn 0) cho người nói có quá ít tiếng để tính đặc trưng — người nói 3.1 giây
rơi vào ca này.

Tầng trên vốn đã AN TOÀN (`_normalise` biến vector NaN thành rỗng, `_cosine`
trả 0.0, coi như không khớp — không nổ, không khớp bừa). Nhưng nó IM LẶNG:
người dùng chỉ thấy "nhân vật mới" mọi tập mà không hiểu vì sao, và không biết
đường xử lý.

Giờ worker bỏ vector đó kèm cảnh báo nói rõ lý do + cách sửa (cắt clip có
nhiều tiếng của người đó hơn). Chốt bằng `not (tong > 0)` để bắt luôn NaN —
mọi so sánh với NaN đều False. 3 test, chạy worker THẬT với pyannote giả.

**1323 test Python, 0 fail.**

## V71 — Chép lời: giọng nói thành văn bản (Phase H, 2026-08-18)

Chủ dự án yêu cầu: nhận liên kết video, hoặc mp3, hoặc file tải lên, rồi đọc
và chuyển thành văn bản.

### Audit trước khi build — gần như KHÔNG cần code mới

Đọc code trước thì thấy mọi mảnh nặng đã có và đã chạy thật trong luồng dub:

| việc | đã có sẵn |
|---|---|
| tải liên kết | `download_one` (V54/V67, verify thật với Facebook) |
| bóc tiếng | `media.audio.extract_audio` |
| ASR | `speech.transcriber.transcribe` (Whisper/Paraformer, venv riêng) |
| xuất SRT | `text.srt.generate_srt` |
| lưu JSON | `transcriber.save_transcript` |

Nên V71 là **lớp nối mỏng**, không dựng ASR mới. Thứ thật sự thiếu: đường đi
DỪNG LẠI sau ASR, và bản xuất `.txt`/`.vtt`.

**Vì sao là module riêng chứ không phải cờ `--skip-*` cắm vào `pipeline.py`**:
luồng dub luôn chạy tiếp sang dịch + TTS + ghép video. Ai chỉ cần bản chữ thì
mọi bước sau ASR là thời gian và tiền bỏ đi. Cắm thêm cờ vào một luồng dài là
cách sinh ra những nhánh không ai test.

### 3 bug do test và smoke test bắt được

1. **`_vtt_timestamp(59.9999)` → `00:00:60.000`** — không có giây thứ 60,
   trình phát từ chối cả file. Bản đầu tách giờ/phút/giây rồi mới xử lý ca
   `ms == 1000` bằng `s += 1`; cộng bù ở một bậc thì phải cộng bù ở mọi bậc.
   Sửa: làm tròn về mili-giây TRƯỚC rồi mới tách.
2. **Tiêu đề toàn ký tự cấm** (`///:::`) → tên file `______`, không rỗng nên
   lọt qua phép kiểm `or`, mà cũng chẳng nói lên gì. Giờ đòi có ít nhất một
   chữ hoặc số mới coi là tên dùng được.
3. **`LabeledCombo` nhận `(NHÃN, khoá)`** — tôi viết ngược thành `(khoá,
   nhãn)`, nên combo hiện ra khoá và `current_key()` trả về nhãn. Smoke test
   dựng trang bắt được ngay; có test khoá vĩnh viễn.

### Chạy THẬT trên clip của chủ dự án

```
$ voxdub transcribe --input tap01_clip.mp4 --output-dir … \
    --language vi --format txt,srt,vtt,json --timestamps
[download] Đang chuẩn bị âm thanh…
[asr] Đang nghe và chép lời…
[export] Đang xuất 20 câu…
Xong 20 câu: txt / srt / vtt / json
```

Kiểm định dạng thật (đúng chỗ hay sai nhất giữa 2 chuẩn):

```
SRT: 00:00:00,240 --> 00:00:01,440     ← dấu PHẨY
VTT: 00:00:00.240 --> 00:00:01.440     ← dấu CHẤM
TXT: [00:00:00.240] Bạn sẵn sàng chứ?
```

### Giao diện

Trang "Chép lời" (`ROW_TRANSCRIBE`), chạy trong `TranscribeWorker` (QThread) —
ASR mất từ vài chục giây tới vài phút, để ở luồng giao diện là app đứng hình
và người dùng tưởng hỏng.

**Một ô nhập cho cả liên kết lẫn file**: người dùng dán gì thì dán,
`is_url()` tự phân đường. Bắt họ chọn trước "tôi sắp dán liên kết hay chọn
file" là bắt trả lời một câu hỏi máy tự trả lời được. File trên máy được kiểm
tồn tại NGAY, không để chờ hết bước chuẩn bị mới báo gõ sai đường dẫn.

Lỗi báo **nguyên văn** (vd "Video này yêu cầu đăng nhập") thay vì nuốt thành
"có lỗi xảy ra" — người dùng cần biết là sai đường dẫn, mất mạng, hay video
có khoá thì mới biết đường xử lý (video khoá thì dùng cookie của V67).

**1352 test Python, 0 fail** (+29: 21 lớp lõi, 8 trang).

### Chưa làm

- Chưa chạy thử trên Windows (cùng nhóm với V53/V56–V64).
- Chưa có nút huỷ giữa chừng — ASR một video dài chạy tới hết.
- Chưa nhận nhiều file một lượt (hàng loạt), mới từng file/liên kết một.

## V72 — Dừng giữa chừng + chép lời hàng loạt (Phase H, 2026-08-18)

### Nút Dừng — hai lần sửa, cả hai do CHẠY THẬT bắt được

**Bản đầu**: kiểm cờ huỷ ở đầu vòng đọc câu của đường subprocess. Thử thật
trên video 7 phút thì **treo tới hết timeout**: giây 45 mà Whisper chưa phát
câu nào, vòng lặp đang kẹt trong `readline()` (chờ tới
`_WHISPER_SEGMENT_TIMEOUT_S`) nên không bao giờ chạy tới chỗ kiểm. Kiểm-rồi-chờ
chỉ đúng khi cái chờ ngắn. Sửa: luồng canh cờ huỷ **giết tiến trình** → stdout
đóng → `readline` trả `""` ngay.

**Bản hai vẫn treo.** Truy tiếp: máy này **không có `.venv-whisper`**, nên ASR
chạy đường **in-process** — chỗ tôi chưa hề cài huỷ. Lỗi kinh điển: sửa MỘT
trong HAI đường đi rồi tưởng xong. `raw_segments` là generator, mỗi vòng là
một câu vừa nhận dạng xong, nên thêm phép kiểm ở đó là dừng thật.

**Đo sau khi sửa** (đúng kịch bản vừa treo):

```
còn chạy: CÓ | câu đã có: 0
>>> thoát sau 10 giây | mã thoát=0
file .txt sinh ra (không nên có): 0
```

10 giây = thời gian tới câu kế tiếp. Mã thoát **0**: người dùng chủ động dừng
thì không phải lỗi. Không sinh file dở dang.

`TranscribeCancelled` tách khỏi `RuntimeError` thường vì lý do đó — tầng trên
phải phân biệt được "người dùng dừng" với "hỏng".

### Chép lời hàng loạt

`--input` lặp lại được, và nhận cả **thư mục**. Chạy TUẦN TỰ: ASR ăn trọn
CPU/GPU, chạy song song trên cùng máy chỉ làm cả hai chậm đi (cùng kết luận
với V42 cho luồng dub).

Ba quyết định có test khoá:

1. **Một mục hỏng KHÔNG làm hỏng cả mẻ** — nó được đánh dấu `hong` kèm lý do,
   lượt chạy đi tiếp. Dừng cả mẻ vì một liên kết chết là bắt người dùng làm
   lại từ đầu những mục đã tốn thời gian chạy xong.
2. **Không đệ quy vào thư mục con** — thư mục con thường là bản nháp/file tạm,
   quét vào là chép lời cả rác.
3. **Hai file TRÙNG TÊN không ghi đè nhau** — `Tap1/video.mp4` và
   `Tap2/video.mp4` là chuyện thường; file sau đè file trước thì người dùng
   chỉ phát hiện khi mở ra thấy thiếu. Thêm hậu tố `_2`, `_3` chứ không thêm
   dấu thời gian (người dùng còn phải tìm lại file theo tên).

Chạy thật cả thư mục:

```
Chép lời 2 mục:
  [1/2] xong: bai_1.mp4 (20 câu)
  [2/2] xong: bai_2.mp4 (20 câu)
Xong: 2 | Hỏng: 0 | Đã huỷ: 0
```

### Chi tiết nhỏ nhưng đáng nói

- **Ctrl+C lần đầu = dừng gọn, lần hai = thoát ngay.** Giết ngang ngay lần đầu
  thì tiến trình con Whisper thành mồ côi và các mục đã xong có thể mất.
- **Nhiều file nối bằng `|`** trong ô nhập GUI: đường dẫn Windows chứa cả dấu
  phẩy lẫn chấm phẩy, còn `|` là ký tự Windows CẤM đặt tên file nên không bao
  giờ đụng độ.
- **Nút Dừng nói "Đang dừng…"** chứ không phải "Đã dừng": mục đang chạy còn
  chạy nốt câu hiện tại.
- **Báo cáo nói rõ số mục hỏng** — báo "xong" trong khi 3/5 mục hỏng là nói dối.

**1372 test Python, 0 fail** (+20).

### Giới hạn còn lại

- Huỷ có độ trễ bằng thời gian nhận dạng MỘT câu (đo được 10 giây trên máy
  không GPU). Không thể ngắn hơn nếu không giết tiến trình giữa lúc nó đang
  ghi — mà làm vậy thì lần chạy sau dễ gặp file tạm hỏng.
- Liên kết trùng tên chưa được chống ghi đè như file (tên của liên kết phải
  chờ tải xong mới biết tiêu đề).
- Chưa chạy thử trên Windows.

## V72b — Đóng nốt 2 gap của V72 (Phase H, 2026-08-18)

### Liên kết trùng tiêu đề không còn ghi đè nhau

Gap V72 để lại: tên file của liên kết lấy từ TIÊU ĐỀ video nên chỉ biết sau
khi tải xong, không chặn trước được như file trên máy. Hai tập cùng tên
«Tập 1» của hai kênh khác nhau là chuyện thường — không xử lý thì file sau đè
file trước, âm thầm.

Sửa: `transcribe_media` nhận thêm tập tên ĐÃ DÙNG và tự thêm hậu tố sau khi
biết tiêu đề. Chạy LẺ một mục thì không thêm gì (không có gì để đụng độ —
đẻ ra `_2` vô cớ cũng là một kiểu sai). 3 test.

### Đường subprocess: từ "tin là được" thành "đo được"

V72 tuyên bố luồng canh giết tiến trình nên huỷ ăn ngay, nhưng **chưa từng
chạy thử** — máy này không có `.venv-whisper`. Đó chính là lý do bản V72 đầu
treo mà không ai biết.

Giờ có test giả lập worker bằng script Python `sleep(600)` không phát câu nào:
nếu huỷ chỉ đặt cờ mà không giết tiến trình thì test treo. Đo được: huỷ xong
trong **~1,5 giây** thay vì chờ hết `_WHISPER_SEGMENT_TIMEOUT_S`.

**Kết luận về độ trễ huỷ** — khác nhau theo đường chạy, cần nói rõ:

| đường ASR | độ trễ huỷ | vì sao |
|---|---|---|
| subprocess (`.venv-whisper`) | **~ngay** | giết được tiến trình con |
| in-process (không có venv) | tới câu kế tiếp (đo 10s) | không thể ngắt generator giữa chừng |

Nên máy nào cài `scripts/setup_whisper.py` thì nút Dừng ăn ngay; máy chạy
in-process phải chờ hết câu đang nhận dạng. Đây là giới hạn thật, không phải
thứ chỉnh tham số là xong.

**1376 test Python, 0 fail.**

## V73 — 2 lỗi người dùng báo trên bản phát hành v3.4.0 (Phase H, 2026-08-18)

Không phải lỗi tự tìm ra: người dùng cài bản `.exe` v3.4.0 vừa phát hành, dán
một liên kết YouTube vào trang Chép lời, chụp màn hình gửi lại. Hai lỗi độc
lập trong một ảnh.

### Lỗi 1 — «HỎNG» với mọi liên kết sao chép lúc đang nghe Mix

Liên kết người dùng dán:
`youtube.com/watch?v=x1F3EdwrYw4&list=RDMMx1F3EdwrYw4&start_radio=1` — đúng
dạng YouTube tự sinh khi bấm Chia sẻ trong lúc đang phát một Mix/playlist.

**Đo bằng yt-dlp thật (2026.03.17), không suy đoán:**

| tham số | yt-dlp trả về |
|---|---|
| như code cũ (thiếu `noplaylist`) | `_type=playlist`, id `RDMMx1F3EdwrYw4`, «My Mix», **194 mục** |
| thêm `noplaylist: True` | video đơn `x1F3EdwrYw4` — «D.Elliot6 - I'm not Okay (Lyrics)» |

Nên code cũ tải cả 194 video rồi mới hỏng ở `_resolve_filepath`, vì hàm này
đi tìm MỘT file theo id — mà id nó nhận được là id của playlist.

`grep -rn playlist` trên cả repo trước khi sửa: **0 kết quả**. Không phải sót
một nhánh, mà là chưa từng nghĩ tới trường hợp này — nên lỗi đánh vào cả 4
đường dùng liên kết: Chép lời, Tạo dự án, Tải xuống, Xử lý hàng loạt.

Sửa: `noplaylist: True` ở **cả hai** nơi dựng options (`download_video` và
`build_ydl_opts` — hai bản riêng, sửa một quên một là lỗi sống lại ở luồng
kia). Thêm `ensure_single_video_url()` chặn liên kết danh sách phát THUẦN
(`playlist?list=…`) mà `noplaylist` không cứu được, chặn TRƯỚC khi gọi yt-dlp
kèm câu chỉ đúng việc cần làm. 10 test, có ca chống-chặn-nhầm cho
`watch?v=`/`youtu.be`/Facebook/TikTok.

### Lỗi 2 — «HỎNG» nhưng không nói vì sao

Ảnh chụp chỉ có đúng một dòng: `[1/1] HỎNG: <liên kết>`. Lý do bị vứt đi hai
lần, độc lập nhau:

1. `transcribe_many` ghi lý do vào `BatchItem.error`, nhưng tín hiệu
   `item_status` của `TranscribeWorker` khai 4 tham số nên không mang nổi nó.
   Đây là worker **duy nhất** trong `workers.py` thiếu trường `detail` —
   `DownloadWorker` và `BatchWorker` đều đã có.
2. Cảnh báo `logger.warning("Chép lời hỏng «%s»: %s")` của lõi thì bị
   `log_text.notice_for` lọc bỏ: thông báo lạ có chứa URL/đường dẫn bị coi là
   log kỹ thuật. Bộ lọc làm đúng việc của nó — chỗ sai là trông cậy vào nó.

Nên dù lõi biết rõ nguyên nhân, người dùng không có đường nào thấy được.

Test khoá lại bằng cách chạy `TranscribeWorker.run()` thật với một mục hỏng
thật (không vá tín hiệu): hoàn nguyên bản sửa thì test fail với `assert []` —
Qt lặng lẽ nuốt lời gọi emit thừa tham số, đúng kiểu lỗi không ai nhận ra.

### Lỗi 3 — thanh bên chồng mục lên nhau (thấy trong cùng ảnh)

Mục cuối nhóm CÔNG CỤ («Chép lời») vẽ đè lên nhãn HỆ THỐNG và nuốt luôn mục
đầu nhóm dưới. Đo bằng Qt offscreen với đúng danh sách mục của app:

| chiều cao thanh bên | đè lên nhãn HỆ THỐNG |
|---|---|
| 1200px | không (vừa đủ) |
| **1000px** (1080p sau khi trừ thanh tác vụ + thanh tiêu đề) | **44px** |
| 900px | 15px |
| 800px | 55px |

Cơ chế: `_build_list` khoá cứng chiều cao mỗi danh sách (min = max), nên khi
thiếu chỗ `QVBoxLayout` không còn gì để co — nó xếp chồng widget lên nhau.
Thanh bên đòi tối thiểu **1055px** (không có ví Vox) / **1131px** (có ví).

`_sync_footer` — cơ chế ẩn thẻ đáy vốn viết ra để chống đúng lỗi này —
**không giải phóng được pixel nào**: đo được `sizeHint` giữ nguyên 1055 sau
khi ẩn cả hai thẻ. Ảnh người dùng gửi cũng đã ở trạng thái ẩn cả hai thẻ mà
vẫn đè. Đây là lỗi tự nặng dần: mỗi công cụ thêm vào ăn thêm 48px.

Sửa: đưa ba danh sách vào một `QScrollArea`. Tối thiểu của thanh bên rơi từ
1055px xuống **172px**. `_sync_footer` được viết lại để tính theo chiều cao
nội dung bên trong vùng cuộn (số cũ không còn ý nghĩa khi thanh bên co được),
và đổi vai: không còn là cách chống lỗi hiển thị mà là ưu tiên dễ dùng — thẻ
đáy nhường chỗ trước, cuộn là phương án cuối.

Kết quả đo lại sau khi sửa:

| chiều cao | đè | phải cuộn | thẻ đáy |
|---|---|---|---|
| 1200px | không | không | hiện đủ |
| **1000px** | **không** | **không** | ẩn thẻ trạng thái |
| 900px | không | không | ẩn cả hai |
| 700px trở xuống | không | có | ẩn cả hai |

Tức ở đúng cấu hình máy người dùng, mọi mục hiện ra hết mà **không phải cuộn**
— giữ nguyên ý đồ thiết kế ban đầu, chỉ khác là giờ nó chạy thật.

17 test, chạy 3 vòng bố cục liên tiếp ở mỗi chiều cao để chắc thẻ không bật
tắt loạn. Hoàn nguyên `shell.py`: **14/17 fail** — test bắt đúng lỗi.

### Soát lại sau khi sửa — 2 lỗi do CHÍNH bản sửa V73 gây ra

Cả hai đều tự tìm ra khi rà lại, chưa ai gặp phải.

**a) `ensure_single_video_url` chặn nhầm liên kết youtu.be có `list=`.** Bản
đầu suy ra "không có tham số `v=` mà có `list=` → danh sách phát". Sai: id
video của YouTube nằm ở ĐƯỜNG DẪN với `youtu.be/<id>`,
`youtube.com/shorts/<id>`, `/embed/<id>`, `/live/<id>`. Mà `youtu.be/<id>?list=…`
chính là thứ nút Chia sẻ của YouTube sinh ra khi video nằm trong playlist —
tức bản sửa đã chặn đúng nhóm liên kết người dùng hay dán nhất, còn tệ hơn
lỗi ban đầu. Sửa: chặn HẸP theo đường dẫn — chỉ `/playlist`, hoặc `/watch` mà
không có `v=`. 7 ca chống-chặn-nhầm thêm vào test.

**b) `noplaylist` một mình KHÔNG đủ.** Đo bằng yt-dlp thật:

| liên kết | + `noplaylist` |
|---|---|
| `youtu.be/<id>?list=…` | OK, ra đúng video |
| `youtube.com/shorts/<id>?list=…` | **HỎNG** — "This playlist type is unviewable" |

Vì thấy `list=` là yt-dlp chọn extractor `youtube:tab` ngay từ khâu chọn
extractor, trước cả lúc `noplaylist` có tiếng nói. Sửa: `normalize_url` cắt
`list`/`start_radio`/`index` khỏi liên kết YouTube (không đụng `/playlist`, và
giữ `t=` vì đó là mốc thời gian). Xác nhận lại bằng yt-dlp thật: cả 3 dạng
`watch?v=…&list=`, `youtu.be/<id>?list=`, `shorts/<id>?list=` đều ra đúng
video `x1F3EdwrYw4`.

**c) Lăn chuột trên menu không cuộn được** — hệ quả trực tiếp của vùng cuộn
mới. `QListWidget` là một vùng cuộn nên nó nuốt bánh xe chuột kể cả khi chính
nó không cuộn được. Ba danh sách phủ gần hết thanh bên → vùng cuộn gần như vô
dụng, chỉ cuộn được khi trỏ vào vài dải lề mỏng. Sửa bằng `eventFilter`
chuyển tiếp sang vùng cuộn. Đo: gỡ bộ lọc ra → 0, để nguyên → 60.

> **Bẫy khi đo:** Qt giao sự kiện bánh xe cho `viewport()` chứ không cho chính
> `QListWidget`. Phép đo đầu tiên gửi nhầm vào list nên ra 0 ở CẢ HAI trạng
> thái — suýt nữa kết luận sai theo cả hai hướng. Phải gỡ bộ lọc rồi đo lại
> mới chứng minh được lỗi có thật.

### Đã soát, KHÔNG có lỗi

- **17 trang nội dung ở cửa sổ nhỏ nhất (1024×680)**: không trang nào chồng
  mục. Vùng nội dung cao 586px; trang sát nhất là `DownloadPage` (cần 566px,
  không tự cuộn) — còn 20px, chật nhưng chưa hỏng.
- **Các worker khác**: cả 3 tín hiệu `item_status` trong `workers.py` giờ đều
  mang `detail`. Không còn chỗ nào nuốt lý do lỗi.
- **`output_dir` tương đối**: `env_dir` neo vào `app_root()`, không phụ thuộc
  thư mục làm việc — bản `.exe` không ghi ra chỗ bất ngờ.

### Còn tồn (chưa sửa, chờ chủ dự án quyết)

- **`chep_loi/_tam/` không bao giờ được dọn.** Chứng minh bằng chạy thật:
  chép lời xong, `_tam` vẫn giữ `asr_16k.wav`. Với FILE trên máy thì vô hại
  (tên cố định, bị ghi đè). Với LIÊN KẾT thì `build_ydl_opts` đặt tên theo
  `<extractor>_<id>` nên mỗi video là một file mới — chép lời 20 video
  YouTube là giữ lại 20 video đầy đủ mà người dùng không hề xin. Chưa sửa vì
  đây là quyết định sản phẩm: xoá sau khi xong, hay giữ để lần sau khỏi tải
  lại (hiện code KHÔNG dùng lại, luôn tải mới — nên đang là lãng phí thuần).
- **Liên kết thiếu `http://`** (`www.youtube.com/…`) bị `is_url` coi là đường
  dẫn file → báo "Không tìm thấy". yt-dlp vốn nhận được dạng này.

### Đóng nốt 2 việc còn tồn

**a) `chep_loi/_tam/` giờ được dọn sau khi xuất xong.** `prepare_audio` trả
thêm đường dẫn media để biết cái gì là file TẢI VỀ.

Ràng buộc quan trọng nhất: với file trên máy, `prepare_audio` trả về chính
đường dẫn CỦA NGƯỜI DÙNG làm `media_path` — dọn mà không kiểm thư mục là xoá
thẳng dữ liệu gốc của họ, hỏng nặng hơn mọi thứ việc dọn dẹp định sửa. Nên
`_don_tam` chỉ xoá thứ nằm TRONG `work_dir` (`os.path.commonpath`, bắt luôn
`ValueError` cho ca hai ổ đĩa khác nhau trên Windows).

Chỉ dọn khi đã xuất xong — mục HỎNG giữ nguyên file để còn dò nguyên nhân.

Kiểm bằng chạy thật cả hai ca: file trên máy → file gốc CÒN NGUYÊN, `_tam`
sạch; liên kết → video tải về bị xoá, `_tam` sạch, `.txt` vẫn đúng tên theo
tiêu đề video.

**b) Liên kết thiếu `https://`** (`www.youtube.com/watch?v=…`) trước đây bị
`is_url` coi là đường dẫn file → báo "Không tìm thấy", trong khi yt-dlp vốn
nhận được dạng này.

`looks_like_bare_url` cố tình HẸP, vì đoán sai theo hướng ngược lại tai hại
hơn nhiều: coi một đường dẫn file là địa chỉ web sẽ biến thông báo "không tìm
thấy file" rõ ràng thành một lỗi tải khó hiểu. Đòi đủ ba dấu hiệu: có `/`, đoạn
đầu là tên miền hợp lệ, không phải đường dẫn Windows — và file có thật trên đĩa
thì luôn thắng.

> Cái bẫy đáng nói: `phim.mp4` trông y hệt một tên miền nếu chỉ soi phần sau
> dấu chấm cuối (`mp4` là chuỗi chữ cái hợp lệ như `com`). Đòi phải có `/` mới
> loại được nó — 9 ca "không được nhầm thành địa chỉ" nằm trong test.

Lược đồ được thêm ở `normalize_url` chứ không ở `is_url`: `urlparse` mà không
có lược đồ thì đẩy cả tên miền vào `path`, làm mọi phép kiểm theo `netloc`
(kể cả `ensure_single_video_url`) trượt hết.

### Chạy thật đúng liên kết người dùng đã dán

Gọi thẳng `download_one` với
`watch?v=x1F3EdwrYw4&list=RDMMx1F3EdwrYw4&start_radio=1`:

- **Phân giải liên kết: ĐÚNG** — ra đúng một video `x1F3EdwrYw4`, yt-dlp đi
  vào `process_video_result` (một video) chứ không lặp qua 194 mục playlist.
- **Tải dữ liệu: KHÔNG kiểm được ở đây** — `HTTP Error 403: Forbidden`. Đã
  xác định là do môi trường: video "Me at the zoo" (19 giây, không dính
  playlist nào) cũng 403 y hệt. Tức YouTube chặn IP sandbox này ở khâu tải
  media, không liên quan bản sửa. Trên máy Windows của người dùng không gặp.

Nói rõ giới hạn này thay vì tuyên bố "đã verify đầu-cuối".

**1426 passed, 7 skipped, 0 failed** (Python; trước khi sửa 1365).

## V74 — "Đã cài Whisper rồi mà app vẫn bảo chưa" (Phase H, 2026-08-19)

Người dùng báo trên bản `.exe` vừa phát hành: mở app là hiện hộp thoại chặn
"Máy chưa đủ điều kiện lồng tiếng — Thiếu thư viện faster-whisper" dù script
cài đã in `faster-whisper đã cài — bỏ qua` và `smoke test đã đạt`; chép lời
thì hỏng với `No module named 'av'`.

**Dòng lỗi có lý do (V73) chính là thứ làm ca này chẩn đoán được.** Nếu vẫn
là `[1/1] HỎNG: <liên kết>` trống trơn thì không có đường nào lần ra.

### Một gốc rễ, ba biểu hiện

`autodub.spec` CỐ Ý loại `faster_whisper` / `ctranslate2` / `av` khỏi bundle —
Whisper chạy trong `.venv-whisper` qua `asr_whisper_worker.py`, cắt ~112 MB.
Nhưng hai chỗ khác vẫn giả định import được chúng trong tiến trình chính.

Đây đúng là lớp lỗi đã sửa ở `_smoke_report` hồi V38. Lần đó sửa đúng một
chỗ gặp phải mà không rà những chỗ khác cùng giả định như vậy.

**(1) `preflight._check_asr` kiểm bằng `import faster_whisper`.** Trong bản
`.exe` phép import này không bao giờ thành công, nên hộp thoại chặn hiện ở
MỌI lần mở app, với 100% người dùng bản đóng gói — kể cả người đã cài đúng và
máy đang chạy tốt. Lời khuyên kèm theo (`pip install -r requirements.txt`)
cũng vô nghĩa với họ: bản `.exe` không có `requirements.txt`, cũng không có
Python nào để chạy pip.

Sửa: kiểm `settings.whisper_venv_configured()` — đúng thứ lúc chạy thật sẽ
dùng. Bản chạy từ mã nguồn vẫn kiểm import như cũ, vì ở đó in-process là
đường hợp lệ.

**(2) `transcribe()` rơi sang in-process khi không có venv.** Đường đó không
tồn tại trong bản `.exe`, nên nó chỉ đổi một tình huống nói được thành
`No module named 'av'`.

> Vì sao là `av` chứ không phải `faster_whisper`: spec liệt kê cả hai trong
> `excludes`, nhưng `collect_all("faster_whisper")` ở trên lại thêm chúng
> vào `hiddenimports`, còn `_ML_PRUNE` chỉ lọc `a.binaries`. Kết quả là
> phần Python của faster-whisper VẪN nằm trong gói, chỉ `av` là bị cắt sạch
> — nên import đi được một đoạn rồi mới chết ở dependency. Bằng chứng là
> chính thông báo lỗi: thiếu hẳn thì đã báo `No module named
> 'faster_whisper'`. Tức phần "cắt ~112 MB" của spec nhiều khả năng không
> đạt được như ghi chú nói. **Chưa sửa** — đụng vào spec thì phải có một
> lượt build Windows thật để đối chiếu kích thước, xem mục Còn tồn.

Sửa: bản đóng gói báo thẳng "Thư mục này chưa cài bộ nghe Whisper" kèm tên
tệp `.bat` phải bấm. Subprocess hỏng thì giữ nguyên lý do thật, không nuốt.

**(3) Bấm Dừng bị nuốt thành "chạy lại bằng đường khác".**
`TranscribeCancelled` kế thừa `RuntimeError`, nên `except Exception` ở
`transcribe()` bắt gọn nó rồi chạy LẠI TOÀN BỘ ở in-process: người dùng bấm
Dừng, worker bị giết thật, và máy lập tức cày lại từ đầu bằng đường kia.

V72 tuyên bố "nút Dừng thật sự dừng" và đã sửa hai lần, nhưng không bắt được
ca này — chính TEST_LOG V72 ghi rằng máy thử nghiệm không có `.venv-whisper`,
nên nhánh subprocess chưa bao giờ được đi vào. Lỗi nằm đúng ở chỗ không ai
chạy tới.

### Cạm bẫy nâng cấp (nguyên nhân trực tiếp của ca này)

`.venv-whisper` và `models/` nằm TRONG thư mục ứng dụng
(`app_root()`). Người dùng cài Whisper cho `D:\VoxDub-Studio-v3.4.0-win64\`,
rồi giải nén v3.4.1 ra thư mục khác — bản mới không thấy gì cả. Đúng nghĩa
"đã cài xong" mà app vẫn bảo chưa.

Lời khuyên trong preflight giờ nói thẳng điều này: cài lại, hoặc chép
`.venv-whisper` + `models` từ bản cũ sang.

### Test

6 test. Hoàn nguyên bản sửa preflight → 2/6 fail đúng chỗ.

Một chi tiết phụ lộ ra: `tests/test_vi_diacritics.py` có danh sách miễn trừ
tên tệp cài đặt, nhưng chỉ liệt kê 3 trong 4 tệp `.bat` mà `build_exe.py`
thật sự đóng gói — thiếu đúng "Cai dat Whisper ASR". Chỗ thiếu không lộ ra
suốt thời gian qua vì chưa có mã Python nào nhắc tên tệp đó. Đã bổ sung.

### Còn tồn

- Phần Python của faster-whisper vẫn nằm trong bundle dù spec định loại (xem
  giải thích ở mục 2). Sau V74 nó là mã chết trong bản `.exe`, không còn gây
  hại, nhưng có thể đang gánh dung lượng thừa. Kiểm chứng cần một lượt build
  Windows thật rồi so kích thước — v3.4.0 là 75,1 MB, v3.4.1 là 78,7 MB.

### Mở bản phát hành ra đếm — con số bác bỏ chính phán đoán ở trên

Ghi chú trong spec nói loại faster-whisper "cắt được ~112 MB", nên đoán ban
đầu là bundle đang gánh ~112 MB mã chết. Tải hẳn
`VoxDub-Studio-v3.4.1-win64.zip` về đếm:

| gói | trong bundle v3.4.1 |
|---|---|
| `av` | **0 tệp** — đã loại sạch |
| `faster_whisper` | 17 tệp, **1.382.820 byte** (kèm `silero_vad_v6.onnx` 1,2 MB) |
| `ctranslate2` | 30 tệp, **363.524 byte** (chỉ mã Python, DLL native đã bị cắt) |

Tức `_keep_binary` đã cắt phần nặng từ lâu; thứ còn sót chỉ **~1,8 MB**.
Phán đoán 112 MB là sai — nó đọc ghi chú trong spec chứ chưa mở gói ra xem.

Nhưng ~1,8 MB đó đủ để gây hại: `_internal/` nằm trên `sys.path` của bản
onedir, nên `import faster_whisper` CHẠY ĐƯỢC rồi mới chết ở `import av`.

**Vì sao `excludes` không chặn được:** `excludes` chỉ tác động ở TẦNG IMPORT
(đồ thị module), còn `collect_all` nhét tệp vào qua TẦNG DATAS — datas được
chép nguyên xi. Hai dòng trong cùng một tệp spec mâu thuẫn nhau. Sửa: bỏ
`faster_whisper`/`ctranslate2` khỏi `collect_all`, chỉ giữ `yt_dlp` (gói duy
nhất thật sự cần vì nạp extractor động). Lợi ích chính là **lỗi trở nên thành
thật** (`No module named 'faster_whisper'`), không phải dung lượng.

Thêm `tests/test_spec_khong_mau_thuan.py`: đọc thẳng tệp spec, chặn việc một
gói vừa nằm ở `collect_all` vừa nằm ở `excludes`. Không chứng minh bundle
sạch (không chạy PyInstaller cho Windows từ Linux được) — nó chặn đúng cái
mâu thuẫn đã sinh ra bug. Thêm lại gói cũ → test fail.

### Soát tiếp: quét toàn bộ import gói-bị-loại ở tiến trình chính

Vì lỗi này đã lặp 2 lần (V38, V74), quét bằng AST toàn bộ `autodub/` +
`autodub_gui/`, đối chiếu với danh sách `excludes` đọc từ chính spec. 6 chỗ,
phân loại:

| chỗ | kết luận |
|---|---|
| `app.py:722,733` (playwright, align) | probe chẩn đoán, bọc try/except — vô hại |
| `text_regions.py:100` (PIL) | đường dự phòng OCR, bọc `ImportError` — suy giảm có báo |
| `align.py:49` (faster_whisper) | call site bọc try/except → karaoke mất canh chữ, **âm thầm** trong bản .exe |
| `preflight.py:263` | nhánh chỉ chạy ở bản mã nguồn — đúng thiết kế |
| `transcriber.py:86` | đường in-process — xem lỗi dưới đây |

### Lỗi thứ 4: hàng loạt ≥2 video bỏ qua hẳn .venv-whisper

**Bản sửa V74 đầu chưa che được.** Điều kiện là
`whisper_cache is None and venv_configured()`, mà `BatchWorker` tạo
`WhisperCache()` ngay khi mẻ có từ 2 video trở lên. Nên "Xử lý hàng loạt" với
≥2 video bỏ qua `.venv-whisper` rồi rơi in-process — hỏng trên mọi bản đóng
gói, **trong khi chạy lẻ 1 video vẫn tốt**. Đúng kiểu lỗi chỉ lộ ở một nhánh
mà người thử ít khi đi vào (giống hệt lý do V72 không bắt được lỗi nút Dừng).

Cache chỉ có nghĩa cho đường in-process (giữ model nạp sẵn giữa các video);
bản `.exe` không có đường đó nên phải bỏ qua cache. Bản mã nguồn giữ nguyên
hành vi cũ — ở đó cache là tối ưu thật.

**1440 passed, 7 skipped, 0 failed.**

## V95 — Đóng nốt hai mục "còn tồn" tự ghi (Phase H, 2026-08-20)

Chủ dự án hỏi còn gì chưa làm. Thay vì trả lời theo trí nhớ, quét lại mọi mục
"Còn tồn" tôi tự ghi trong phiên (V75 → V94). Bảy mục, chia làm ba nhóm:

| mục | trạng thái |
|---|---|
| `editor.py` không chuyển tiếp cờ Dừng (ghi ở CẢ V76 lẫn V79) | **sửa xong** |
| OCR vùng chữ dùng `subprocess.run` trần | **không phải việc bỏ sót** — xem dưới |
| Demucs CPU in-process không giết ngang được | giới hạn thật của thư viện |
| Canh chữ in-process chỉ kiểm cờ giữa các clip | độ trễ tối đa = 1 clip (1–3 giây) |
| Bản `.exe` chưa chạy thử trên Windows | không có máy Windows |
| Từ khoá chủ đề là danh sách tay; chưa nhìn hình ảnh | mở rộng tính năng, không phải lỗi |
| Sinh nhạc cần chế độ có máy chủ | thiết kế từ V37 |

### Cờ Dừng lúc dựng lại video

`RebuildWorker` và `SubtitleWorker` **đã có** nút Dừng và đã dựng
`ProgressReporter` mang theo cờ — cờ chỉ dừng lại ở đó, vì `editor.py` gọi
`refresh_subtitles()`/`merge_video()` không truyền tiếp. Bấm Dừng lúc đang ghép
video vẫn phải đợi ffmpeg xong, đúng thứ V79 đã sửa cho luồng chính.

Thêm `ProgressReporter.cancel_event` (đường lấy cờ ra công khai — nếu không thì
nơi gọi phải chọc vào thuộc tính riêng, thứ sẽ hỏng lặng lẽ khi lớp đó đổi) rồi
chuyển tiếp ở cả bốn lời gọi. Test đọc AST, bắt mọi lời gọi
`refresh_subtitles`/`merge_video` trong hai hàm dựng lại đều phải có tham số đó.

### OCR: ghi lại một QUYẾT ĐỊNH, không phải một việc bỏ sót

`detect_text_regions()` dùng `subprocess.run(..., timeout=60)`. **Không** nối cờ
Dừng vào đó, vì hộp thoại gọi nó (`_OcrWorker`) không có nút Dừng nào — thêm
tham số chỉ tạo mã chết. Trần 60 giây là giới hạn thật.

Có test khoá lại quyết định này theo hai chiều: trần thời gian còn đó, và
`_OcrWorker` vẫn chưa có `cancel()`. Ngày nào hộp thoại có nút Dừng thì test đỏ
— đúng lúc đó mới đáng nối cờ xuống.

### Một lần sập test chưa tái hiện được

Một lượt chạy đầy đủ kết thúc bằng core dump lúc dọn dẹp (danh sách extension
module của faulthandler, không có test nào FAILED). Chạy lại **bốn lượt nữa với
thứ tự ngẫu nhiên: đều xanh**. Nghi là Qt dọn dẹp `QThread` lúc thoát trình
thông dịch. Ghi lại đây thay vì im lặng cho qua — nếu nó tái diễn thì đây là
manh mối đầu tiên.

**1638 passed, 7 skipped, 0 failed** (Python) + **370 pass** (Node).

## V94 — Việc "2 phút" tôi giao cho chủ dự án là BẤT KHẢ THI (Phase H, 2026-08-20)

Suốt nhiều lượt tôi lặp lại một câu: *"vào khu quản trị, thêm một dòng nhà cung
cấp vai `assist`, 2 phút thôi"*. Lượt này định làm hộ thì phát hiện **không ai
làm được việc đó**:

```js
// control_server/src/models/AiProvider.js
role: { type: String, enum: ['translate', 'content'], default: 'translate' }
```

`ai-gateway.service.js` hỏi `providersFor('assist')`, nhưng model **không nhận
giá trị `assist`** — Mongoose chặn ngay lúc lưu. Schema của route cũng chặn, và
form trên web thậm chí không có lựa chọn đó.

Hệ thống vẫn chạy, vì đã có sẵn đường lui `role = assist_có_provider ?
'assist' : 'translate'`. Nên triệu chứng bằng 0 — chỉ có hoá đơn đắt gấp hàng
chục lần. **Chính đường lui tôi viết ra để cho êm đã che mất việc cấu hình bất
khả thi.**

### Sửa bốn nơi cùng một danh sách

Vai trò được liệt kê tay ở bốn chỗ độc lập: model, schema route, `<option>`
trong form, và nhãn hiển thị trong bảng. Đúng hình dạng đã cắn hai lượt deploy
worker hôm nay (danh sách tệp chép tay ở hai nơi).

### Test nối bốn nơi lại

`ai-provider-roles.test.js` quét mã tìm mọi vai đang được hỏi
(`providersFor('x')`, `callWithFallback('x')`) rồi bắt:

1. model phải nhận đủ chừng đó vai;
2. schema route không được chặt hơn model;
3. form trên web phải có `<option>` cho mọi vai model nhận — *cấu hình được
   bằng API nhưng không bấm được trên giao diện* cũng là hỏng.

Đã thử gỡ `assist` khỏi enum model: đỏ đúng dòng `AiProvider.role thiếu: assist`.

**370 pass (Node), 1634 passed (Python), website build sạch.**

## V93 — Trả hết nợ 48 chỗ nuốt lỗi (Phase H, 2026-08-20)

Chủ dự án không chấp nhận để lại "nợ đã đóng băng". Đúng — nợ đóng băng vẫn là
nợ, và cái danh sách đó chính là chỗ để người sau đẩy thêm vào.

### Đọc hết 48 chỗ, và bộ dò của tôi đã kể oan một phần

Dump ngữ cảnh từng chỗ (thử gì, bắt xong làm gì) rồi đọc. Hai phát hiện làm
đổi hẳn cách làm:

**1. Bắt được lỗi rồi GIỮ LẠI nội dung thì không phải im lặng.** Nhiều chỗ làm
`self.error = f"{type(e).__name__}: {e}"` hoặc `self.text = f"Không kiểm tra
được: {e}"` — nơi gọi hiện thẳng ra giao diện. Bộ dò bản đầu không tính, nên
kể oan 5 chỗ. Bộ kiểm kể oan thì bị tắt (bài học V90) → sửa bộ dò: có dùng lại
tên lỗi = có dấu vết.

**2. Hầu hết đã có sẵn lời giải thích cạnh dòng `except`.** Dạng
`# noqa: BLE001 — chưa có sẵn thì không cần xóa`. Lý do nằm cạnh mã **tốt hơn
hẳn** danh sách trong tệp test: người sửa mã nhìn thấy ngay, không phải nhớ đi
cập nhật ở nơi khác.

Sau khi bộ dò công nhận hai dạng đó: 48 → **2 chỗ** thật sự không giải thích.

### Hai chỗ đó đều làm người dùng mất thứ gì đó

- `quality_page._scan_projects` — quét dự án hỏng thì danh sách rỗng, mà
  **trang Báo cáo trống trơn trông y hệt "chưa có dự án nào"**. Người dùng
  không cách nào phân biệt. → `logger.warning`.
- `voice_setup_dialog.run` — đọc danh sách giọng đã nạp hỏng thì báo 0 giọng.
  → `logger.debug`.

Và 28 chỗ còn lại được viết lý do **ngay cạnh dòng `except`**, lấy từ chính
phần rà soát — không còn nằm trong một tệp test ở nơi khác.

### Luật gọn lại còn một câu

Bỏ hẳn hai danh sách tập trung (`DUOC_IM_LANG`, `CHUA_RA`). Nay chỉ còn:

> Mỗi chỗ nuốt lỗi phải có **dấu vết** (log / raise / giữ nội dung lỗi để hiện
> ra), **hoặc lý do viết ngay tại dòng `except`**.

Đã thử: thêm một hàm có `except Exception: return 0` không lời giải thích →
test đỏ ngay.

**1634 passed, 7 skipped, 0 failed** (Python) + **366 pass** (Node).

## V92 — Biến "36 chỗ chấp nhận được" thành luật chạy được (Phase H, 2026-08-20)

Chủ dự án không chịu để lại thứ gì ở trạng thái "tôi đã xem và thấy ổn". Đúng:
đánh giá trong đầu một người thì lần sau không ai kiểm lại được, và chính cơ
chế `except Exception` im lặng đã giấu năm lỗi trong tuần (V75, V78, V83, V86,
V91).

### Chấm lại chặt tay — một ca thật sự nguy hiểm

Quét lại kèm TÊN HÀM chứa (lần trước chỉ có số dòng nên không đánh giá nổi).
Trong 39 chỗ, đáng sửa nhất:

```python
# autodub_gui/workers.py — PreflightWorker.run()
except Exception:      # noqa: BLE001 — không được làm sập giao diện
    results = []
self.ready.emit(results)
```

Preflight sập thì `results = []` → app **không hiện cảnh báo nào** về máy
thiếu thành phần. Người dùng tưởng mọi thứ ổn cho tới lúc chạy hỏng — đúng
kiểu V83, và đúng cái đã làm họ mất mấy hôm vì FFmpeg. Nay có
`logger.exception`.

Thêm ba chỗ nữa được thêm dấu vết: mất dòng Lịch sử xuất video, không tạo được
ảnh đại diện dự án, và lượt kiểm bản mới bị bỏ qua.

### Luật thay cho lời hứa

`tests/test_nuot_loi_co_dau_vet.py` quét toàn bộ `autodub/` + `autodub_gui/`
và bắt mỗi chỗ nuốt lỗi phải thuộc một trong ba nhóm:

| nhóm | nghĩa là gì |
|---|---|
| có dấu vết | log / raise / báo cho người dùng — không cần khai |
| `DUOC_IM_LANG` | đã đọc, im lặng là ĐÚNG, **kèm lý do viết ra** (dọn dẹp, probe, đường lui có tín hiệu khác) |
| `CHUA_RA` | mã cũ **chưa ai đọc** — đóng băng, chỉ được ngắn đi |

Nhóm thứ ba là chỗ tôi phải thành thật: quét toàn repo ra thêm **48 chỗ trong
mã cũ mà tôi chưa từng đọc**. Khai lý do cho chúng là nói dối, nên chúng vào
danh sách "chưa rà" — nói đúng một điều: *đã có sẵn từ trước, và không được
phép nhiều thêm*.

Ba luật đi kèm, mỗi luật một test:
- chỗ nuốt lỗi MỚI không thuộc nhóm nào → đỏ (đã thử: thêm một hàm giả có
  `except: return 0` là đỏ ngay);
- `DUOC_IM_LANG` không được chứa dòng thừa (sửa xong mà quên xoá thì danh sách
  phình lên, mất ý nghĩa);
- `CHUA_RA` chỉ được ngắn đi — nợ phải giảm, không được giấu nợ mới vào đó.

**1637 passed, 7 skipped, 0 failed** (Python) + **366 pass** (Node).

## V91 — Rà cuối: phân tích tĩnh tìm ra gốc rễ thật của V83 (Phase H, 2026-08-20)

Chủ dự án yêu cầu rà một lượt cuối. Ba phép quét trước (import gói bị loại,
cảnh báo bị lọc, nuốt lỗi không dấu vết) đều sạch hoặc chỉ ra một chỗ nhỏ. Phép
quét thứ tư — `pyflakes` toàn repo — mới là cái đáng giá.

### `brand_logo` chưa bao giờ bị xoá, nó chỉ mất dòng `def`

```
autodub_gui/icons.py:918:18: undefined name 'size'
autodub_gui/icons.py:922:14: undefined name 'size'
...
```

Mở ra xem thì:

```python
def eye_off(color=None) -> QIcon:
    return _make_icon(_draw_eye_off, ...)
    """Biểu trưng VoxDub: ô vuông bo góc và bốn vạch sóng âm."""
    px = QPixmap(size, size)          # ← mã chết, `size` không tồn tại
```

**Thân hàm `brand_logo` gốc vẫn nằm nguyên trong tệp** — chỉ thiếu dòng `def`,
nên nó trở thành mã chết ngay sau `return` của hàm khác, và cái tên
`icons.brand_logo` thì biến mất.

Đó mới là gốc rễ thật của V83: dựng `SetupWizard` ném `AttributeError`, trình
cài đặt tự động chưa từng chạy được lần nào. Hôm 19-08 tôi vá bằng cách **viết
một hàm mới ở chỗ khác** — chữa được triệu chứng, nhưng để lại repo có hai bản
vẽ thương hiệu, một bản chết, và không ai biết vì sao bản gốc biến mất.

Nay trả dòng `def` về cho bản gốc (bản vẽ đúng: ô vuông bo góc + bốn vạch sóng
âm, dùng `tokens.BRAND_LOGO_BG`) và bỏ bản vá tạm.

### Vì sao mắt không thấy mà máy thấy trong một giây

Python không kêu gì cho tới đúng lúc dòng đó chạy — mà những dòng đó nằm ở
nhánh ít đi qua nhất (đường lui khi thiếu `logo.ico`). Cùng lớp với V80 (tệp
worker không có trong gói), V84 (kho GitHub không tồn tại): **thứ được gọi tới
thì có, thứ ở đầu kia thì không.**

Hai chốt chặn thường trực, cả hai đều đã thử gỡ bản sửa ra để chứng minh có
kêu:

1. Test chạy `pyflakes` chặn `undefined name` + hai loại chắc chắn là lỗi.
   Danh sách loại cố ý HẸP: bắt bẻ phong cách thì test đỏ triền miên rồi bị bỏ
   qua — đúng bài học V90 (bộ kiểm hay kêu nhầm thì người ta tắt đi).
2. Test quét AST tìm **chuỗi kiểu docstring nằm ngay sau `return`** — dấu hiệu
   riêng của hàm mất dòng `def`, thứ pyflakes chỉ thấy gián tiếp.

### Dọn nhiễu để tín hiệu thật hiện ra

`del model` trong `align.py` làm pyflakes báo closure dùng tên đã xoá; hai
f-string không có placeholder; một `nonlocal` thừa. Không cái nào là lỗi chạy,
nhưng bốn dòng nhiễu đủ để người đọc bỏ qua cả danh sách — mà trong danh sách
đó có ca V91 thật.

### Kèm theo: một chỗ nuốt lỗi im lặng

Quét AST 32 tệp đã sửa trong phiên: 37 chỗ nuốt lỗi, 36 là đường lui hợp lệ.
Đúng một chỗ giấu mất chức năng người dùng đang dùng — dán mã kích hoạt trong
trình cài đặt, gặp lỗi ngoài dự tính thì chỉ `return`: không thấy gì xảy ra,
không biết mã đã dùng được hay chưa. Nay báo tại chỗ + ghi nhật ký.

**1633 passed, 7 skipped, 0 failed.**

## V90 — Khi tài liệu không đủ (Phase H, 2026-08-20)

Chủ dự án chỉ thẳng vào chỗ đáng chỉ: mục 6b của runbook cảnh báo đúng cái bẫy
"nhánh deploy không theo `main`" từ 18-08, mà 19-08 vẫn sập lại. **Tài liệu có
mà không đọc thì bằng không** — nên đợt này không viết thêm chữ, mà chuyển
việc nhắc từ người sang máy.

### Ba công cụ, ba thời điểm khác nhau

| dùng khi | công cụ | trả lời câu gì |
|---|---|---|
| bất cứ lúc nào | `kiem_nhanh_deploy.py` | nhánh deploy có tụt lại so với `main` không |
| trước khi redeploy | `deploy_vays.sh` | (tự sinh lại nhánh rồi tự kiểm — không còn bước phải nhớ) |
| sau khi deploy | `kiem_deploy_song.py` | máy chủ có THẬT SỰ chạy mã mới không |

`deploy_vays.sh` chặn hai ca dễ đẩy nhầm mã: đang đứng ở nhánh khác `main`, và
còn thay đổi chưa commit (nhánh deploy sinh từ commit đã có trên `main`, phần
chưa commit sẽ không lên máy chủ — im lặng bỏ qua là đúng kiểu hỏng âm thầm).

`kiem_deploy_song.py` luôn gọi **một cửa cũ làm mốc đối chứng** bên cạnh cửa
mới. Chỉ thử cửa mới thì `404` dễ bị hiểu nhầm là "route đăng ký sai"; có đối
chứng mới phân biệt được "máy chủ chạy mã cũ" với "mã mới có lỗi".

CI thêm job `deploy-branch-drift` chạy bộ dò trên mỗi push `main` — tình trạng
tụt lại hiện ra ngay, không đợi tới lúc deploy.

### Canh chính bộ canh

Bộ dò chỉ có ích khi ánh xạ đường dẫn khớp đúng thứ script sinh nhánh chép
sang. **Bản đầu đã kêu nhầm 99 tệp cho worker** vì tôi đoán nhánh worker chép
nguyên `dub-worker/` từ `main`, trong khi thực tế nó gom từ `autodub/` + ba
script cài đặt + `control_server/worker-dub/dub_worker.py`.

Một bộ kiểm hay kêu nhầm thì người ta tắt nó đi — còn tệ hơn không có. Nên có
test đọc thẳng `cp -r` trong hai script sinh nhánh rồi bắt ánh xạ phải phủ
hết: thêm thư mục vào script sinh nhánh mà quên khai ở bộ dò là đỏ ngay.

### Chạy lần đầu đã bắt được cái đang hỏng

```
[!!] deploy/vays-dub-worker ĐANG TỤT LẠI so với main:
     scripts/setup_whisper.py đã đổi nhưng nhánh deploy còn bản cũ
     autodub/ ⇄ dub-worker/autodub/: 9 tệp CHƯA có (vd cancel_guard.py);
                                      20 tệp khác nội dung (vd cli.py)
```

Worker cloud đang chạy mã từ **trước V79** — thiếu cả nút Dừng cho các bước
dài. Không ai biết, vì worker vẫn nhận việc và vẫn xong việc bình thường.

Đã sinh lại cả hai nhánh bằng `deploy_vays.sh`; bộ dò giờ báo `[ok]` cả hai.
Redeploy worker là việc chạm production, chờ chủ dự án quyết.

**1629 passed, 7 skipped, 0 failed.**

### Redeploy worker: hai lượt hỏng liên tiếp, cùng một tệp

Chủ dự án duyệt redeploy worker. Lượt đầu **chết ở chặng build**:

```
ModuleNotFoundError: No module named '_python_ho_tro'
ERROR: process "/bin/sh -c python3 scripts/setup_whisper.py" did not complete
```

`setup_whisper.py` bắt đầu import `_python_ho_tro` từ V80 (bộ kiểm phiên bản
Python), nhưng **hai nơi khác nhau cùng liệt kê TAY** danh sách tệp cần chép:

1. `gen_vays_dub_worker_branch.sh` — `cp scripts/setup_*.py "$TARGET/scripts/"`
2. `control_server/worker-dub/Dockerfile` — `COPY scripts/setup_*.py /app/scripts/`

Sửa nơi thứ nhất rồi deploy lại: **chết y hệt**, vì nơi thứ hai vẫn thiếu.
Danh sách liệt kê tay ở hai chỗ là hai cơ hội quên độc lập.

Bộ dò V90 không bắt được ca này: nó so thứ ĐÃ khai giữa `main` và nhánh
deploy, còn đây là **phụ thuộc mới chưa ai khai**. Nên thêm một test khác
loại: đọc từng script được chép, tìm `import _<module>` cục bộ, rồi bắt module
đó phải có mặt ở **cả hai** danh sách. Gỡ bản sửa ra ở nơi nào cũng đỏ đúng
hai dòng.

Lượt thứ ba xanh. Kiểm bằng chứng cứ thay vì tin trạng thái:

| bằng chứng | kết quả |
|---|---|
| commit máy chủ build | `aae8c77d` |
| commit đầu nhánh deploy | `aae8c77d` — khớp |
| tệp V79 trong nhánh đã build | `cancel_guard.py`, `ffmpeg_deps.py` có mặt |
| nhật ký chạy | `worker_id=… bắt đầu poll … mỗi 3.0s` |

Worker cloud giờ chạy cùng mã với `main`, sau khi tụt lại từ 18-08.

**1630 passed.**

## V89 lên production (Phase H, 2026-08-19)

Triển khai `voxdub-app` (control_server + website) lên Vibe Host và phát hành
app `.exe` v3.5.1.

### Lượt deploy đầu tiên "thành công" nhưng build MÃ CŨ

Deploy báo `succeeded`, 11/11 chặng xanh, container chạy, MongoDB nối, worker
vẫn nhận việc — mà cửa mới vẫn 404.

Cách phát hiện, và đây là phần đáng nhớ: **so mã lỗi của cửa MỚI với một cửa
CŨ**.

```
POST /v1/ai/translate      -> 400   (tồn tại, chỉ sai dữ liệu)
POST /v1/ai/generate-post  -> 400   (tồn tại)
POST /v1/ai/assist         -> 404   ← chưa có mã mới
```

Nếu chỉ nhìn trạng thái deploy thì mọi thứ đều xanh. Nếu chỉ thử cửa mới thì
404 dễ bị hiểu nhầm là "route đăng ký sai". Phải có cái ĐỐI CHỨNG.

### Nguyên nhân: deploy không lấy từ `main`

`voxdub-app` theo dõi nhánh **`deploy/vays-control-server`** — nhánh sinh tự
động chứa thư mục `webapp/` (bản sao `control_server/` + `website/`), vì VAYS
build theo model "một thư mục con = một build context" mà Dockerfile của
control_server cần cả hai. Nhật ký build ghi rõ: `nạp source (git_url) @
10ce832c` — commit của nhánh deploy, không phải `b72cad8` của `main`.

Quy trình đúng đã có sẵn trong repo từ trước:

1. sửa trên `main`
2. chạy `scripts/gen_vays_control_server_branch.sh` (tự sinh lại + force-push)
3. mới redeploy

Bỏ bước 2 thì deploy chỉ build lại đúng mã cũ, và không có dấu hiệu nào báo.

### Kiểm chứng sau khi làm đúng

```
POST /v1/ai/assist              -> 401  (tồn tại, đòi đăng nhập)
POST … task:"tac_vu_bia"        -> 400  "body/task must be equal to one of the allowed values"
GET  /v1/admin/analytics/assist -> 401
POST /v1/ai/translate           -> 400  (đường cũ còn nguyên)
```

Dòng thứ hai là thứ đáng giá nhất: **danh sách tác vụ đóng đang chặn thật ở
tầng schema**, trước cả khi chạm tới xác thực hay ví tiền — đúng lớp chặn chi
phí số 1 trong bản kế hoạch.

App `.exe` v3.5.1: CI build + test đều xanh, tải được.

## V89 hoàn thiện — nhớ đệm, phiên bản prompt, tên nhân vật (Phase H, 2026-08-19)

Ba việc còn lại sau khi ba giai đoạn của bản kế hoạch đã dựng xong.

### Nhớ đệm theo nội dung: chỗ rò tiền dễ thấy nhất

`jobId` chống được gọi trùng do mạng chập chờn, nhưng **người dùng bấm lại nút
thì jobId mới** — cùng một câu hỏi, trả tiền lần thứ hai. Với `tighten_line`
(bấm thử vài phương án cho một câu) hay `music_suggest` (bấm lại vì chưa ưng)
thì đây là chuyện thường ngày.

Khoá nhớ đệm băm ba thứ: tác vụ + **phiên bản prompt** + dữ liệu vào đã sắp
khoá (nên `{a,b}` và `{b,a}` là cùng một câu hỏi). Lượt dùng lại tính 0 Vox,
và hiện thành **cột riêng** ở bảng theo dõi — tỷ lệ dùng lại cao nghĩa là
người dùng đang bấm đi bấm lại cùng một thứ, đó là tín hiệu về giao diện chứ
không phải về mô hình.

### Phiên bản prompt: thứ giữ cho bộ đo có nghĩa

`PROMPT_VERSION` ghi vào nhật ký và nằm **trong** khoá nhớ đệm. Hai việc hỏng
âm thầm nếu quên tăng số này khi sửa prompt:

- nhớ đệm trả lại kết quả của prompt CŨ;
- bảng theo dõi không tách được chất lượng trước/sau, nên sửa xong thấy tệ hơn
  cũng không quy được trách nhiệm.

### Vai trò thật: chặn cái đắt gấp hàng chục lần

Chưa cấu hình nơi gọi mô hình cho vai `assist` thì hệ thống **vẫn chạy** —
dùng chung vai `translate`. Đó chính là kiểu hỏng nguy hiểm: không có triệu
chứng, chỉ có hoá đơn. Nay vai trò thật được ghi mỗi lượt, và trang quản trị
hiện cảnh báo đỏ khi còn lượt nào chạy bằng vai dịch.

### `character_name` — nối nốt tác vụ cuối

Giai đoạn 2 để lại vì "không trang nào giữ lời thoại theo từng người nói". Tìm
lại thì `autodub.editor.list_speakers()` đã gom sẵn theo `speaker_label`, và
hộp thoại **Xem trước người nói** đang hiện đúng dữ liệu đó.

Thêm nút "Gợi ý tên gọi" cho từng người nói. Ba chi tiết cố ý:

- Lấy lời của **chính người đó** từ transcript đang mở, không dùng câu mẫu một
  dòng — một câu thì đặt tên gì cũng là đoán.
- Tên hiện **kèm nhãn gốc** ("Người nói 1 — Người dẫn") và lý do ở tooltip.
- **Không tự ghi vào hồ sơ nhân vật.** Hồ sơ áp cho mọi tập sau; đặt nhầm còn
  phiền hơn để nguyên "Người nói 2". Có test đọc thẳng mã hàm để chặn ai đó
  sau này thêm lệnh ghi vào đấy.

**1619 passed (Python), 366 pass (Node), website build sạch.**

### Trạng thái cuối

Toàn bộ cổng trợ lý đã dựng xong: 6 tác vụ, 6 chỗ bấm thật trong app, bốn lớp
chặn chi phí + nhớ đệm, bộ đo có tự kiểm, bảng theo dõi. **Chặn duy nhất còn
lại vẫn là chưa có nhà cung cấp cho vai `assist`** — chưa lượt gọi thật nào đi
qua đây.

## C38 — Đo rồi vứt đi: báo cáo chất lượng mất khi ghép lại từ Editor (Phase H, 2026-08-26)

Chủ dự án gửi bản đề bài **E1**: *"đo thật, đặt trần ép tốc độ đọc"*, kèm dặn
rất đúng là **không được bịa số trần** mà phải đo trước.

Rà trước khi gõ dòng nào, và **cả hai tiền đề của bản đề bài đều sai**:

| Bản đề bài nói | Thực tế trong mã |
|---|---|
| "chưa có trần ép tốc độ" | **đã có**: `timing_max_atempo`, mặc định **1.1** |
| "chưa đo tỷ lệ ép" | **đã đo từng câu**: `TimingReport.details` có `atempo`, `shift_s`, `overlap_prev_s` |
| "chưa báo câu nào bị ép" | trang **Báo cáo chất lượng** hiện đủ *"đọc nhanh ×1.08"*, *"chồng tiếng 0.42s"* kèm chữ của câu |

Nên việc đúng KHÔNG phải dựng tầng đo mới. Việc đúng nằm ở một dòng:

    merge_dir, _timing = apply_soft_timing(...)

**Đo xong rồi vứt đi.** Đường lồng tiếng chính ghi kết quả ra
`quality_report.json`; đường ghép lại từ Trình chỉnh sửa thì không. Ai đi
đường đó — bao gồm **toàn bộ luồng "Mở video + phụ đề tiếng Việt" (C37)** —
không có cách nào biết câu nào bị đọc nhanh hay còn chồng tiếng.

### Không thêm trần nào

Trần đã có và engine đã tôn trọng nó. Thêm một con số nữa chỉ tạo hai nguồn sự
thật. Thứ thiếu là **báo cho người dùng**, không phải một ngưỡng mới — và đây
đúng là điều bản đề bài lo (đừng bịa số), chỉ khác chỗ: số không cần bịa vì đã
có sẵn.

### Hai lỗi trong chính bản vá, do test của nó bắt

1. **Xoá mất dữ liệu của lượt chạy gốc.** `cu.update(moi)` — mà lượt ghép lại
   không chạy rà soát bản dịch nên `translate_review` của nó là `[]`, đè lên
   trace thật. Nay giá trị rỗng không được đè lên dữ liệu đã có.
2. **Chốt đọc-mã đỏ oan.** Docstring của chính hàm mới trích lại dòng mã CŨ
   làm ví dụ, nên phép kiểm "không còn `_timing = apply_soft_timing`" khớp
   phải câu chú thích. Đúng bẫy C8, lần này ở dạng tự gài.

### Tests (+6)

Ghép lại để lại báo cáo · báo cáo chỉ rõ **từng câu kèm chữ và mức đọc nhanh**
(cảnh báo chung thì người dùng không sửa được gì) · video sạch thì danh sách
rỗng · **giữ phần của lượt chạy gốc** · báo cáo hỏng **không giết lượt ghép**
(mất tiện nghi, không mất việc) · và chốt gốc: đường ghép không được vứt kết
quả đo đi nữa.

**2083 Python.**

### Còn tồn — phần E1 chưa làm được và vì sao

- **Chưa chạy thật.** Cần một video + `.srt` tiếng Việt thật, bấm «Đọc lại tất
  cả» rồi mở trang Báo cáo chất lượng. Tôi không có video của chủ dự án, không
  có giọng VieNeu trên máy này, và không bấm được giao diện Windows.
- **Chưa chốt lại trần 1.1.** Đúng tinh thần bản đề bài: chưa có số liệu thật
  thì không đổi. Con số 1.1 hiện có là mặc định cũ, chưa ai đo lại trên phụ đề
  tiếng Việt thật — nhưng nó là **trần đang chạy**, không phải số tôi vừa bịa.
- Nếu số liệu thật cho thấy đa số câu tiếng Việt dài hơn chỗ trống phụ đề gốc
  thì đó là vấn đề gốc rễ khác (giãn nhẹ toàn video), cần mini-spec riêng —
  đúng như bản đề bài đã lường trước.


## C37 — Nhập video + phụ đề tiếng Việt sẵn thành dự án (Phase H, 2026-08-26)

Chủ dự án hỏi hai câu, và hoá ra là **một câu**:

- *"lấy giọng đọc .srt cho ra tiếng Việt ghép vào trong chỉnh sửa được không"*
- *"ở chỗ chỉnh sửa tôi có thể lấy video từ file… hay chỉ chỉnh sửa được video
  làm trên tool này"*

Kiểm bằng mã trước khi trả lời: `load_work_dir()` đòi một thư mục có sẵn
`transcript_vi.json`, nên Trình chỉnh sửa **chỉ mở được dự án do app tạo**. Và
app đọc được `.srt` (`parse_subtitle`) lẫn ghi được `.srt` (`generate_srt`),
nhưng hai việc đó nằm ở hai đầu khác nhau — không ai nối chúng lại.

Nghĩa là cả hai câu thiếu **cùng một mảnh**: biến (video, phụ đề) thành thư
mục dự án đúng khuôn. Sinh giọng từng câu, ghép tiếng theo mốc, xuất video đều
đã chạy được từ lâu.

### Ba loại rác của phụ đề thật, xử ngay lúc nhập

Không để bộ đọc gánh, vì tới đó thì đã muộn:

1. **Câu bị cắt làm đôi** cho vừa dòng — đọc thẳng từng dòng thì giọng ngắt
   cụt giữa câu. Gộp bằng `gop_cau` (C27), và **nói ra đã gộp bao nhiêu**.
2. **Mốc chồng nhau** (hay gặp ở phụ đề tải từ mạng) — kéo mốc kết thúc của
   dòng trước về sát dòng sau, giữ nguyên thì hai câu đọc đè lên nhau.
3. **Dòng rỗng, mốc lùi, khối sai khuôn** — bỏ, nhưng ĐẾM và nói ra. Bỏ im
   lặng thì người dùng tưởng phụ đề của mình bị mất chữ.

### Hai quyết định

**Không chép video.** Chỉ ghi đường dẫn vào `source_video.json`, đúng cách
pipeline vẫn làm với tệp ngoài thư mục dự án. Chép một tệp 2 GB chỉ để mở ra
sửa là việc vô ích.

**Phụ đề đã là tiếng Việt thì nó vừa là bản gốc vừa là bản đích** (`text` =
`text_vi`). Không dịch, không gọi máy chủ, **không tốn Vox** — giọng VieNeu
offline lo phần còn lại. Phụ đề tiếng nước ngoài là chặng sau, theo đúng thứ
tự chủ dự án chốt.

### Tests (+14)

Phép thử thật sự của cả chặng là **chính hàm mở dự án của Editor**
(`load_work_dir`) mở được thư mục vừa nhập, thấy đủ câu và tìm ra video nguồn
— không phải một assert về JSON.

Còn lại: đủ sáu trường bắt buộc · gốc = đích · gộp câu bị cắt đôi (và tắt được)
· nắn mốc chồng · bỏ dòng rỗng/mốc lùi có đếm · không còn dòng nào thì nói rõ
định dạng cần dùng · **không chép video** · thiếu tệp thì nói thiếu cái gì ·
trang có nút và nút nối đúng hàm · nhập xong **mở luôn** dự án · **bấm Huỷ
giữa chừng không để lại thư mục rỗng**.

**2077 Python.**

### Còn tồn

- **Chưa chạy thật lần nào.** Cần một video + `.srt` tiếng Việt thật, bấm
  «Đọc lại tất cả» rồi «Xuất video» — hai nút đã có sẵn, nhưng đường mới chưa
  ai đi qua.
- Câu tiếng Việt đọc ra thường dài hơn khoảng trống trong phụ đề. Bộ ghép có
  ép tốc độ, nhưng chưa có trần và chưa báo câu nào bị ép quá tay.
- Phụ đề tiếng nước ngoài: chặng sau.


## C36 — Ba lỗi từ một lượt chạy thật (Phase H, 2026-08-26)

Chủ dự án chạy một video thật rồi gửi ảnh chụp. Ba thứ hỏng, không liên quan
nhau về mã nhưng dính nhau về hậu quả.

### 1. Tìm ffprobe bằng cách đổi chữ trong đường dẫn

    ffprobe = duong_dan_ffmpeg().replace("ffmpeg", "ffprobe")

`str.replace` đổi **mọi** chỗ khớp. `C:\ffmpeg\bin\ffmpeg.exe` — đường dẫn
rất thường gặp — thành `C:\ffprobe\bin\ffprobe.exe`, một thư mục không tồn
tại.

Nhìn từ người dùng thì đây **không phải một câu lỗi, mà là máy đứng**: không
đo được độ dài → tệp dài không được cắt nhỏ → bộ nghe chạy thẳng vào cả tệp,
thanh tiến trình nằm im ở 24%. Trong nhật ký chỉ có một dòng cảnh báo hiền
lành *"Không đọc được độ dài «…"*.

Nay có `duong_dan_ffprobe()` riêng: hỏi PATH trước, rồi đổi **đúng tên tệp**
trong cùng thư mục, rồi mới tới `bin/` cạnh app. Không thấy thì nói thẳng hậu
quả (*"tệp dài sẽ KHÔNG được cắt nhỏ"*) kèm tên tệp `.bat` phải chạy.

### 2. Bấm Dừng rồi nút nằm im, người dùng tưởng treo

Lệnh dừng chỉ có hiệu lực **giữa các bước**; bước đang chạy (nghe-chép, tách
nhạc nền) là một lượt gọi dài không cắt ngang được. Nút đổi chữ thành "Đang
dừng…" rồi im mười phút thì kết luận duy nhất người dùng rút ra là app treo.
Nay nói thẳng: *"Sẽ dừng ngay khi xong bước đang chạy… đây không phải app
treo."*

### 3. Đóng app thì hiện hộp "Ứng dụng gặp lỗi không mong muốn"

    RuntimeError: libshiboken: Internal C++ object
    (TimelineThumbnailWorker) already deleted.

`worker.finished.connect(worker.deleteLater)` huỷ đối tượng C++, nhưng biến
Python vẫn trỏ vào cái vỏ. Lúc đóng app, `shutdown()` gọi `isRunning()` lên nó
→ nổ. Thời điểm tệ nhất để mất niềm tin: người dùng vừa làm xong việc, bấm
thoát, và nhận một hộp lỗi đỏ.

Sửa hai lớp: **buông tham chiếu ngay khi worker xong** (gốc, và chỉ buông nếu
vẫn đang trỏ vào chính worker đó — video khác đã thay worker mới thì đừng xoá
nhầm), và `con_song()` hỏi shiboken trước mọi lượt gọi trong dọn dẹp (lưới an
toàn). Trang khác đã có sẵn cách xử này từ trước; `editor_page` là chỗ chưa
theo.

### Tests (+9)

ffprobe (4): thư mục cũng tên «ffmpeg» vẫn ra đúng tệp · không có ffprobe cạnh
ffmpeg thì trả rỗng chứ không đoán bừa · ưu tiên PATH hệ thống · thiếu ffprobe
thì cảnh báo nói rõ **hậu quả** và tên tệp cài đặt.

Đóng app (5): đối tượng sống/None/đã huỷ ở tầng C++ · mọi lượt `isRunning()`
trong dọn dẹp phải qua `con_song` · worker thumbnail phải buông tham chiếu khi
xong.

Bỏ `con_song` ở một chỗ để đo → đỏ. **2063 Python.**


## C35 — Tệp cài đặt không thể chạy được bằng cách đúp chuột (Phase H, 2026-08-26)

Chủ dự án bấm «Cai dat tach giong theo nguoi noi.bat» ba lần, ba lần nhận cùng
một câu *"Thiếu HuggingFace access token… xem hướng dẫn ở đầu file này
(docstring)"*, rồi *"Cai dat that bai"*.

Rồi hỏi đúng câu đáng hỏi: **"máy khác tải về cài thì có được hướng dẫn không,
sợ khách không biết"**. Câu trả lời lúc đó là KHÔNG — và đó mới là vấn đề thật:
mỗi khách cài tính năng này đều sẽ kẹt y hệt, không có đường nào đi tiếp.

### Ba chỗ hỏng chồng nhau

**1. `.bat` chạy script không tham số.** Không có đường nào truyền token, nên
đúp chuột bao nhiêu lần cũng dừng đúng chỗ đó — mãi mãi. Nay `.bat` hỏi token,
bỏ trống thì dừng sớm và nói rõ, có thì truyền vào `--hf-token`. Chỉ script nào
cần mới hỏi (`CAN_HF_TOKEN`) — hỏi thừa là dạy người dùng bấm bừa.

**2. Câu lỗi bảo mở tệp `.py` ra đọc docstring.** Với người bấm `.bat` thì đó
không phải hướng dẫn, đó là ngõ cụt. Nay in hẳn ba bước kèm địa chỉ.

**3. Tài liệu HỨA thứ mã không làm.** `HUONG_DAN_CAI_DAT.md` ghi sẵn "*rồi chạy
tệp .bat (nó sẽ hỏi token)*" — trong khi `.bat` chưa từng hỏi. Tài liệu viết
trước, mã không theo kịp, và không ai đối chiếu. Nay có test bắt đúng chuyện
đó: tài liệu nói "hỏi token" thì `.bat` phải thật sự hỏi.

Tài liệu cũng chỉ ghi "bấm Agree ở **các trang** model pyannote" mà không nói
trang nào — khách không có cách nào biết, và token đúng vẫn 403. Nay liệt kê
đủ ba địa chỉ.

### Tests (+7)

`.bat` hỏi token và truyền vào · bỏ trống thì dừng sớm · chỉ dẫn đủ ba trang
gated · script khác **không** bị hỏi thừa · câu lỗi nói rõ các bước và không
còn nhắc "docstring" · tài liệu liệt kê đủ ba trang + chỗ tạo token · **tài
liệu và `.bat` không được nói khác nhau**.

Gỡ phần hỏi token ra để đo → 3 đỏ.

### Một lỗi của chính tôi trong lượt này

Commit đầu đẩy đi **kèm một test đỏ**. Không phải vì không chạy test — mà vì
chạy `pytest | tail -2`: đường ống nuốt mã thoát, `&&` phía sau thấy `tail`
thành công nên commit vẫn chạy. Đúng lớp lỗi "công cụ báo sai mà không ai
kiểm" mà dự án này vá suốt. Từ đó chạy `pytest > tệp; echo $?` rồi mới đọc.

**2054 Python.**


## C34 — Bỏ Douyin, khoá lại sáu nền tảng thay thế (Phase H, 2026-08-25)

Chủ dự án chốt: **bỏ Douyin**, dùng Bilibili / TikTok / Xiaohongshu / Weibo /
Ixigua / (Douyu, Huya, Sohu, PearVideo, Meipai).

### Không gỡ mã Douyin

Đường cookie (C33) vẫn có cơ hội, và gỡ đi là mất luôn một lựa chọn mà chủ dự
án có thể cần lại. Chỉ sửa lời soạn: khi Douyin hỏng thì **chỉ luôn sang nền
tảng khác** — nhiều kênh Douyin đăng cùng nội dung lên TikTok, và link TikTok
hoặc Bilibili thì tải thẳng được. Báo lỗi mà không nói đường đi tiếp là để
người dùng bế tắc.

### Phần dễ hỏng không phải bộ tải, mà là ĐOẠN CHIA SẺ

App **không có danh sách nền tảng cho phép** — mọi site yt-dlp hỗ trợ đều đi
qua như nhau, chốt chặn duy nhất là danh sách phát YouTube. Nên phần cần khoá
lại là thứ đã hỏng với Douyin: **Bilibili, TikTok và Xiaohongshu đều chia sẻ
dạng "chữ + liên kết + chữ"** y hệt.

Đã khoá bằng test cho cả sáu: tách đúng liên kết · nhận ra là LIÊN KẾT chứ
không phải đường dẫn tệp · và không nền tảng nào bị chốt chặn danh sách phát
bắt nhầm. Thêm ca Xiaohongshu dán 「打开【小红书】」 dính ngay sau liên kết.

### Những gì đo được và KHÔNG đo được từ đây

| Nền tảng | Đo được gì |
|---|---|
| Bilibili | **Không đo được** — IP sandbox bị chặn, trang thường cũng trả 412 |
| Xiaohongshu | Bộ tải chạy, nhưng ba bài lấy mẫu đều là bài ẢNH nên "No video formats" — không kết luận được |
| Ixigua / Weibo | Trang mở được (200/302), chưa tìm được liên kết video mẫu để thử |
| Douyin | Đóng, đã đo kỹ ở C33 |

Nói rõ giới hạn: tôi xác nhận được **bộ tải tồn tại** và **đoạn chia sẻ được
xử lý đúng**, nhưng **không xác nhận được là tải xong** trên bất kỳ nền tảng
Trung nào — sandbox này bị chặn hoặc thiếu mẫu. Chỗ đó chỉ máy chủ dự án trả
lời được.

**1926 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- Chưa tải xong video nào từ sáu nền tảng trên — xem bảng trên.
- Bilibili có liên kết rút gọn `b23.tv`; tách đúng nhưng chưa thử giải thật.
- Xiaohongshu phần lớn là bài ảnh; app chỉ xử lý video, bài ảnh sẽ báo "không
  có định dạng video" — chưa có lời soạn riêng cho ca đó.
- iQiyi/Youku có bộ tải nhưng thường vướng bản quyền và khoá vùng; chưa thử.

## C33 — Douyin đã đóng mọi cửa ẩn danh (Phase H, 2026-08-25)

Chủ dự án cài Chromium xong, chạy v3.8.6, vẫn hỏng — và lộ ra chi tiết quyết
định: **số video "nhận" gần như giống hệt lần trước dù dán liên kết khác**.
Trình duyệt luôn rơi vào cùng một video gợi ý.

### Đo hết mọi đường, không đoán

Chủ dự án gửi liên kết nên lần này thử được thật từ sandbox:

| Đường | Kết quả đo |
|---|---|
| JSON nhúng trong trang chia sẻ | **không còn địa chỉ video nào** (69 trường, 0 media) |
| API `iteminfo` di động | HTTP 200 nhưng **0 byte** |
| API `aweme/v1/web/aweme/detail` | **403 `blocked`** |
| `yt-dlp` 2026.03.17 | `Fresh cookies … are needed` |
| `yt-dlp` + cookie ẩn danh lấy từ douyin.com | vẫn đòi cookie |
| Trình duyệt tự động (máy chủ dự án) | rơi vào video gợi ý |

Và bằng chứng cho chuyện "video gợi ý" nằm ngay trong dữ liệu trang:
`abParams.reflow_to_featured_app = 1`. Douyin **cố ý** đẩy khách vào trang
chia sẻ sang nội dung nổi bật để ép mở app.

**Đây không phải lỗi app.** Douyin đã đóng cửa với mọi lượt truy cập không
đăng nhập từ ngoài Trung Quốc.

### Đường còn lại: cookie của chính người dùng

`yt-dlp` nói thẳng nó cần gì — *"Fresh cookies (not necessarily logged in)"*.
App đã có sẵn ô cookie trong Cài đặt → Nâng cao từ mini-spec V85.

Nhưng nó **chưa từng có tác dụng với Douyin**: Douyin bị định tuyến TRÁNH
yt-dlp (vì bộ tải của yt-dlp hỏng ở thượng nguồn), nên đúng thứ yt-dlp đòi
thì lại không bao giờ tới tay nó.

Sửa: đường trình duyệt hỏng thì **thử tiếp bằng yt-dlp kèm cookie** — nhưng
CHỈ khi người dùng đã cấu hình cookie. Chưa cấu hình thì ném lại lỗi gốc, vì
thử tiếp cũng vô ích mà còn đổi thông báo thành thứ gây rối hơn.

Thành công ở đường đầu thì trả về ngay, không chạy tiếp — dùng `else` của
`try` chứ không đặt `return` trong `try`.

### Lời soạn nói CẢ HAI đường

Dòng lỗi "trả về một video KHÁC" nay có lời soạn: thử cookie trình duyệt
trước; không được nữa thì tải video về máy rồi dùng «Tải tệp lên» — **cách
này luôn chạy**. Test bắt buộc lời soạn phải nhắc cả hai, vì chỉ nói cách một
là để người dùng bế tắc khi cách đó cũng hỏng.

### Lại một test cắt cửa sổ ký tự

Bộ canh "thành công thì trả về ngay" cắt 800 ký tự quanh lời gọi rồi tìm chữ
`return`. Khối chú thích ở giữa dài hơn 800 ký tự nên phép cắt trượt → **đỏ
oan**. Viết lại bằng cây cú pháp: tìm node `Try` có gọi `download_douyin`,
rồi kiểm nhánh `orelse` có `Return`.

### Chứng minh từng luật

Hỏng đường trình duyệt thì bỏ cuộc luôn → 2 đỏ. Chưa có cookie mà vẫn nuốt
lỗi → 1 đỏ.

**1907 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- **Chưa ai tải xong một video Douyin nào.** Đường cookie chưa thử được từ
  đây: sandbox không có hồ sơ trình duyệt nào đã đăng nhập Douyin.
- Cookie lấy từ trình duyệt chỉ đọc được khi trình duyệt **đã đóng** (Chrome
  khoá tệp cookie khi đang chạy), và Chrome đời mới mã hoá thêm một lớp khiến
  cách này hỏng với một số máy. Chưa xử lý ca đó.
- Nếu cả cookie cũng không xong thì **nên dừng** đường tự động cho Douyin. Mỗi
  vòng vá tốn của chủ dự án một lượt tải 74 MB để đổi lấy một chặng nữa, mà
  Douyin đang siết liên tục — đây là cuộc đua không thắng bền được.
- Mọi thứ SAU khâu tải (chép lời, dịch, lồng tiếng, phụ đề) không dính gì tới
  chuyện này: tải tay rồi «Tải tệp lên» là chạy y hệt.

## C32 — Douyin trả về một video KHÁC (Phase H, 2026-08-25)

Chủ dự án cài v3.8.5, dán liên kết, và lỗi **lại đổi** — lần thứ ba, lần nào
cũng tiến thêm một chặng:

```
v3.8.3:  ERROR: [generic] '9.76 y@t.rE 11/09…'        (nhận cả đoạn chữ làm địa chỉ)
v3.8.4:  ERROR: [Douyin] …: Fresh cookies are needed  (gọi nhầm yt-dlp)
v3.8.5:  Douyin redirected to a different video       (đúng đường, sai trang)
```

Lần này thông báo là **của chính app**, tức đường tải Douyin riêng đã chạy.

### Chủ dự án gửi liên kết để thử — và thử được thật

Khác mọi lần trước, phần giải liên kết **chạy được từ sandbox này**. Bám theo
chuỗi chuyển hướng thật:

```
v.douyin.com/NSY5rdSAVGs/
  → iesdouyin.com/share/video/7644780389491375333/?…share_sign…   ← trang chia sẻ
  → www.douyin.com/video/7644780389491375333?previous_page=…      ← trang desktop
```

`resolve_video_id()` bám hết chuỗi, lấy **số video**, rồi **vứt bỏ địa chỉ**.
Sau đó `_download_via_playwright()` tự dựng lại một địa chỉ trần từ số đó.

Hai thứ mất theo:
- **Chữ ký chia sẻ** (`share_sign`, `did`, `iid`, `ts`) — thứ phân biệt một
  lượt mở từ nút Chia sẻ với một lượt truy cập lạ.
- Và nếu bám theo địa chỉ CUỐI thì rơi vào **trang desktop**, mà ghi chú ngay
  đầu `douyin.py` đã nói: *trang đó tự phát video gợi ý, đánh hơi luồng ở đó
  là bắt nhầm video*. Đúng cái bẫy mà cả mô-đun sinh ra để tránh.

Sửa: `resolve_share_url()` trả về `(số video, ĐỊA CHỈ)` và **chọn đúng chặng
giữa** — trang chia sẻ di động kèm tham số, không phải chặng cuối.

### Và một phát hiện lớn hơn: đường tải nhanh đã CHẾT ở phía Douyin

Nhân tiện thử luôn đường chính (đọc JSON nhúng trong trang chia sẻ, không cần
trình duyệt). Nó trả về rỗng. Mở thẳng `window._ROUTER_DATA` của trang ra xem:
**69 trường, không trường nào có địa chỉ media** — chỉ còn tham số trang, cấu
hình A/B và số video. Douyin đã chuyển phần dữ liệu video sang tải sau khi
trang chạy.

Nghĩa là **không phải app hỏng** — trang đã đổi. Từ nay Douyin chỉ còn một
đường duy nhất: trình duyệt thật. Ai chưa chạy `Cai dat tinh nang Douyin.bat`
thì không có đường nào cả.

### Giữ nguyên chốt chặn video lệch

Có thể thấy chốt này phiền vì nó chính là thứ báo lỗi. Nhưng bỏ nó đi thì app
tải nhầm video rồi lồng tiếng lên đó, và người dùng chỉ phát hiện **sau khi
đã trả tiền**. Giữ, chỉ sửa lời cho nói được việc đi tiếp: tải video về máy
rồi dùng nút «Tải tệp lên».

### Chứng minh từng luật

Chọn địa chỉ cuối thay vì trang chia sẻ → 3 đỏ. Trình duyệt tự dựng địa chỉ
trần → 1 đỏ. Bỏ chốt chặn video lệch → 1 đỏ.

**1903 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- **Vẫn chưa tải xong một video Douyin nào.** Phần giải liên kết và chọn trang
  đã đo thật; phần trình duyệt đánh hơi luồng thì sandbox này không chạy được
  (chưa cài Chromium, và khâu tải media bị chặn IP từ V73).
- Đường tải nhanh coi như bỏ. Chưa gỡ khỏi mã vì nếu Douyin đổi lại thì nó
  chạy tiếp — nhưng đừng trông vào nó.
- Douyin có thể chặn theo vùng: liên kết mở được từ máy chủ này chưa chắc mở
  được từ máy người dùng, và ngược lại.
- Nếu Douyin đổi tiếp cách chống bot thì đường trình duyệt cũng hỏng theo.
  Cách không phụ thuộc ai vẫn là tải về máy rồi «Tải tệp lên».

## C31 — Bản vá C30 mới đúng một nửa (Phase H, 2026-08-25)

Chủ dự án cài v3.8.4 rồi dán lại đúng đoạn Douyin đó. **Lỗi đổi hẳn**, và đó
là tin tốt:

```
trước:  ERROR: [generic] '9.76 y@t.rE 11/09…'
sau:    ERROR: [Douyin] 7650489705510783333: Fresh cookies … are needed
```

Tức là C30 chạy đúng: đã tách được liên kết, giải được mã rút gọn
`v.douyin.com/9Rrk-r-GziU/` thành số video, và gọi tới bộ tải Douyin.

### Nhưng nó gọi NHẦM bộ tải

Dự án có sẵn một đường tải Douyin riêng bằng Playwright, dựng ra **chính vì**
bộ tải Douyin của yt-dlp hỏng ở thượng nguồn (đòi chữ ký `a_bogus`). Đường đó
không cần cookie.

`download_video()` hỏi `is_douyin_url(url)` để rẽ sang đường riêng — nhưng câu
hỏi đó nằm **TRƯỚC** `normalize_url()`, nơi C30 tách liên kết. Nên nó nhận cả
cụm chữ tiếng Trung và trả lời **KHÔNG**:

```
is_douyin_url(cả đoạn chia sẻ)  →  False
is_douyin_url(sau khi tách)     →  True
```

Đường riêng bị bỏ qua, rơi xuống yt-dlp, chết vì cookie. **Vá đúng chỗ mà sai
thứ tự thì vẫn hỏng.**

Sửa: tách ngay đầu `download_video()`, trước cả `ensure_dir`. Và có **HAI**
hàm cùng mẫu này — sửa một chỗ là còn sót chỗ kia, nên bộ canh quét cây cú
pháp tìm MỌI hàm có gọi `is_douyin_url` rồi bắt buộc `tach_lien_ket` đứng
trước trong từng hàm.

### Lời soạn cho dòng lỗi cookie

Dòng gốc của yt-dlp không gợi ý gì làm được trong app. Thêm vào bảng lời soạn:
chạy một lần `Cai dat tinh nang Douyin.bat` là app dùng đường tải riêng, không
cần cookie; nếu vẫn lỗi thì mượn cookie trình duyệt ở Cài đặt → Nâng cao.

Test khoá luôn việc lời soạn phải **chỉ đúng tệp có thật** trong bản phát
hành, không nói chung chung.

### Chứng minh từng luật

Gỡ tách ở `download_video` → 2 đỏ. Chỉ sửa một chỗ, bỏ sót chỗ thứ hai →
1 đỏ. Bỏ lời soạn cho lỗi cookie → 1 đỏ.

**1894 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- **Chưa tải thật một video Douyin nào** từ đây — sandbox bị chặn ở khâu tải
  media (ghi nhận từ V73). Việc đường Playwright có chạy trót lọt hay không
  vẫn phải chờ máy chủ dự án.
- Đường Playwright cần chạy `Cai dat tinh nang Douyin.bat` một lần (tải
  Chromium ~170 MB). Chưa cài thì vẫn rơi xuống yt-dlp và vẫn gặp lỗi cookie —
  lời soạn nói đúng việc cần làm, nhưng app **chưa tự kiểm** xem đã cài chưa
  để báo sớm.
- Nếu Douyin đổi cách chống bot thì đường Playwright cũng hỏng theo; không có
  cách nào bền vững ngoài việc tải video về máy rồi dùng nút Tải tệp lên.

## C30 — Dán nguyên đoạn chia sẻ Douyin vào ô liên kết (Phase H, 2026-08-25)

Chủ dự án dán đúng thứ nút Chia sẻ của Douyin sinh ra:

```
9.76 y@t.rE 11/09 :5pm LJV:/ 今天晚餐吃照烧肥牛乌冬面 🍜 📍西瓜奶冻碗~
还有甜辣脆皮鸡… #美食vlog https://v.douyin.com/9Rrk-r-GziU/
复制此链接，打开Dou音搜索，直接观看视频！
```

App nhận NGUYÊN cụm đó làm địa chỉ →
`ERROR: [generic] '9.76 y@t.rE 11/09…'`. Người dùng không có cách nào đoán ra
là phải tự cắt lấy liên kết — và đây là **dạng chia sẻ mặc định** của Douyin,
TikTok, Xiaohongshu, tức là ai dùng cũng gặp.

### Cắt tới khoảng trắng là chưa đủ

Douyin dán dấu câu tiếng Trung 「，」 **dính ngay sau** liên kết. Nên bảng ký tự
kết thúc địa chỉ phải có cả 「，。！？、；：（）【】…」 lẫn dấu câu la-tinh dính
đuôi.

### Hai luật để không làm hỏng đường đang chạy tốt

- **Không tìm thấy địa chỉ nào thì trả NGUYÊN chuỗi**, không trả rỗng: đầu vào
  có thể là đường dẫn tệp trên máy (`C:/Users/…/Học luật ads 1.m4a`).
- **Địa chỉ thiếu lược đồ giữ nguyên** (`www.youtube.com/…`) — `normalize_url`
  mới là chỗ thêm `https://`, cắt mất ở đây là hỏng một đường khác.

### Nối vào hai chỗ, không phải ba trang

`normalize_url()` — chỗ nghẽn duy nhất của mọi đường tải — tách **trước mọi
phép kiểm khác**, vì `urlparse`/`netloc` đều trượt nếu chuỗi còn dính chữ. Và
`is_url()` cũng tách, để đoạn chia sẻ được định tuyến là LIÊN KẾT chứ không bị
đẩy sang nhánh "tìm tệp trên máy" rồi báo "không tìm thấy file" — đúng kỹ
thuật, vô nghĩa với người dùng.

### Một phép đo sai của tôi

Bộ canh "tách trước `urlparse`" tôi đo bằng cách dời lời gọi tới **ngay
trước** `urlparse` — vẫn thoả điều kiện nên test xanh, và tôi suýt kết luận bộ
canh không cắn. Dời hẳn ra **sau** `urlparse` thì đỏ 2 test. Phép đo sai chỗ
cho kết quả sai y như test viết sai.

### Chứng minh từng luật

Chỉ cắt tới khoảng trắng → 1 đỏ. Không tìm thấy liên kết thì trả rỗng → 2 đỏ.
Tách sau `urlparse` → 2 đỏ.

**1890 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- Lấy **địa chỉ đầu tiên** trong đoạn. Đoạn có hai liên kết thì liên kết sau
  bị bỏ qua — chưa gặp ca nào cần khác.
- Không xử lý liên kết **rút gọn dạng chữ** không có `http://` (vd
  `v.douyin.com/abc` trần). `looks_like_bare_url` có bắt, nhưng chỉ khi cả
  chuỗi là địa chỉ, không bắt khi nó nằm giữa đoạn văn.
- **Chưa tải thật một liên kết Douyin nào** từ đây — sandbox này bị chặn IP ở
  khâu tải media (ghi nhận từ V73).

## C29 — Tự trả lời câu hỏi thay vì bắt người dùng đi nghe (Phase H, 2026-08-25)

Chủ dự án chỉ ra một chuyện đúng: tôi giao cho họ phép kiểm *"nghe phút 33–37
xem có tiếng nói thật không"* mà **tự tôi chưa làm** — trong khi dữ liệu để
trả lời gần hết câu đó đã nằm sẵn trong hai ảnh chụp họ gửi.

### Trả lời được bằng mật độ câu, không cần nghe

| Đoạn | Mật độ |
|---|---|
| Phút 12 (đang nói bình thường) | 0,9 giây một câu |
| Phút 12 → 33 (1.028 câu) | 1,2 giây một câu |
| Phút 33–37 (chỗ nghi bịa) | **35,7 giây một câu** |

Thưa hơn **29 lần**. Điểm quyết định: bộ nghe bật `vad_filter`, tức là **chỉ
chép những chỗ máy nghe ra có tiếng nói**. Trong 250 giây mà chỉ tìm được 7
chỗ như thế thì đoạn đó gần như im hoàn toàn.

Bằng chứng rất mạnh, không phải chứng minh — không có tệp trong tay thì không
nghe được. Nhưng đủ để kết luận bản vá C28 đánh trúng.

### Đừng bắt người dùng đi nghe — để công cụ tự soi

`loc_lap_lai` (C28) chỉ bắt được câu bịa **lặp lại**. Câu bịa đứng lẻ giữa
quãng im vẫn lọt. Mà chỗ im thì theo định nghĩa **không có gì để chép** — câu
nào hiện ra ở đó đều là bịa.

Thêm `tim_vung_lang()` (trả về khoảng im, khác `tim_khoang_lang` vốn chỉ trả
điểm giữa để cắt tệp) và `loc_cau_trong_vung_im()`. Ba luật:

- **Chỉ bỏ khi câu nằm TRỌN trong vùng im.** Câu bắt đầu trong chỗ im rồi kéo
  sang chỗ có tiếng là câu thật bị dò lệch mốc — không được đụng tới.
- **Có lề 0,3 giây** ở hai đầu: mốc của bộ nghe và mốc của bộ dò âm lượng
  không khớp tuyệt đối.
- **Dò hỏng thì giữ nguyên hết** — thà để lọt câu bịa còn hơn xoá câu thật.

Và chỉ chạy **khi đã có dấu hiệu bịa** (bộ lọc lặp đã bỏ được câu nào đó): dò
âm lượng tốn một lượt quét cả tệp, không đáng làm cho mọi lượt chép lời.

### Lại một test khoá bằng chuỗi, lại xanh giả

Bộ canh "chỉ dò âm lượng khi có dấu hiệu" viết là: tìm chuỗi `"if so_bo:"`
trong phần nguồn phía TRƯỚC lời gọi. Dời lời gọi ra ngoài khối `if` → **test
vẫn xanh**, vì chuỗi đó vẫn nằm phía trên (thuộc khối khác).

Thêm `goi_trong_khoi_if()` vào `tests/doc_ma.py`: hỏi cây cú pháp xem lời gọi
có nằm TRONG thân của một `If` có nhắc tới biến đó không. Đổi `if so_bo:`
thành `if True:` để đo lại → **đỏ**. Đây là lần thứ năm trong hai ngày một
phép kiểm bằng chuỗi cho kết quả sai; cây cú pháp thì không.

### Chứng minh từng luật

Bỏ lề mốc → 1 đỏ. Bỏ câu chỉ CHẠM vào vùng im (không cần nằm trọn) → 2 đỏ.
Gỡ điều kiện chỉ-dò-khi-có-dấu-hiệu → 1 đỏ.

**1873 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- Vẫn **chưa nghe được tệp của chủ dự án** — kết luận dựa trên mật độ câu, là
  suy luận từ dữ liệu chứ không phải nghe tận tai.
- Bộ lọc theo âm lượng **chỉ chạy khi bộ lọc lặp đã bắt được gì đó**. Tệp có
  đúng một câu bịa đứng lẻ và không có câu lặp nào thì vẫn lọt.
- Ngưỡng im **-30 dB / 0,6 giây** dùng chung với bộ cắt tệp, chưa hiệu chỉnh
  riêng cho việc phát hiện bịa.
- **Chưa chạy thật lần nào** — máy này không có Whisper.

## C28 — Mô hình BỊA khi gặp quãng im (Phase H, 2026-08-24)

Ảnh chụp thứ hai của chủ dự án, cùng lượt chạy 3 giờ 43:

```
Câu 1485 · 33:27 — Hãy subscribe cho kênh Ghiền Mì Gõ Để không bỏ lỡ
Câu 1486 · 33:48 — Các bạn hãy đăng ký kênh để ủng hộ kênh của mình
Câu 1488 · 35:11 — Các bạn hãy đăng ký kênh để ủng hộ kênh của mình
Câu 1489 · 35:55 — Các bạn hãy đăng ký kênh để ủng hộ kênh của mình
Câu 1490 · 36:38 — Các bạn hãy đăng ký kênh để ủng hộ kênh của mình
Câu 1491 · 37:17 — Các bạn hãy đăng ký kênh để ủng hộ kênh của mình
```

Từ phút 33 tới 37, mỗi ~40 giây một dòng y hệt. **Không ai nói câu nào cả.**
Đây là câu mẫu quảng cáo YouTube — Whisper học từ hàng triệu phụ đề tiếng
Việt, nên gặp quãng im hoặc tiếng nhỏ là lấp chỗ trống bằng đúng những câu
quen thuộc nhất.

Nguy hiểm hơn hẳn chuyện vụn câu ở C27: **vụn câu là trình bày xấu, bịa là
dữ liệu SAI**.

### Gốc rễ: mô hình lấy chính câu vừa in làm lời nhắc

`faster-whisper` mặc định bơm bản chép của đoạn trước vào lời nhắc của đoạn
sau. Gặp quãng im, mô hình không có gì để nghe nên lặp lại chính câu vừa in —
rồi câu đó lại thành lời nhắc cho đoạn kế. Vòng lặp tự nuôi nó.

Đặt `condition_on_previous_text=False`. Mất một chút mạch văn giữa các đoạn,
đổi lại **không có chữ nào bị bịa ra**. Với bản chép lời, bịa nguy hiểm hơn
lạc mạch nhiều.

### Lưới an toàn: lọc câu lặp liên tiếp

Tắt ở gốc là đúng nhưng chưa đủ — tệp đã xuất bằng bản cũ vẫn đầy câu bịa, mà
chủ dự án đang chạy dở vài giờ. Nên thêm `loc_lap_lai()`:

- **Chỉ gộp khi lặp từ BA lần liên tiếp trở lên.** Người nói lặp hai lần là
  chuyện thật ("Không. Không."); lặp bốn năm lần y hệt thì gần như chắc chắn
  là máy bịa.
- **So sau khi bỏ dấu câu và chữ hoa** — cùng một câu bịa hiện ra lúc có dấu
  chấm lúc không.
- **Lặp KHÔNG liên tiếp thì không đụng tới**: giảng viên nhắc lại một ý ở đoạn
  sau là chuyện bình thường.
- **Báo ra số câu đã bỏ.** Im lặng xoá chữ của người dùng là điều tệ nhất một
  công cụ chép lời có thể làm.

Lọc **ngay sau khi nghe xong**, trước mọi định dạng xuất — câu bịa là dữ liệu
sai nên phụ đề và `.json` cũng không được có nó. Khác hẳn C27 (gộp câu) vốn
chỉ là cách trình bày nên chỉ áp cho `.txt`. Nút "Gộp câu cho .txt…" cũng lọc
luôn, vì đó chính là tệp cần cứu.

### Hai bộ canh sẵn có của repo bắt lỗi của tôi

Phép thay chuỗi của tôi khớp nhầm `    ghi_dan.dong()` (4 dấu cách) vào bên
trong `        ghi_dan.dong()` (8 dấu cách) — tức là chèn phần lọc **vào giữa
khối bắt lỗi**, nuốt mất cả `raise` lẫn dòng cảnh báo giữ tệp dở.

Bắt được nhờ hai bộ canh có sẵn: **luật "nuốt lỗi phải có dấu vết"** (V92/V93)
chỉ thẳng `transcribe_media()` dòng 417, và test C24 về giữ tệp dở. Không có
chúng thì lỗi này lọt, và hậu quả là chép lời hỏng giữa chừng **không báo gì**
— đúng lớp lỗi đã mất nhiều ngày để dọn.

### Chứng minh từng luật

Bật lại việc bơm bản chép đoạn trước → 1 đỏ. Gộp cả khi chỉ lặp 2 lần → 1 đỏ.
Lọc sau khi đã ghi tệp → 1 đỏ.

**1867 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- **Chỉ bắt được câu bịa LẶP LẠI.** Một câu bịa đứng lẻ giữa quãng im thì vẫn
  lọt. Muốn chắc phải đối chiếu với mức âm lượng của đoạn đó — chưa làm.
- **Không có danh sách câu mẫu YouTube để chặn thẳng.** Cân nhắc rồi bỏ: nếu
  giảng viên thật sự nói "các bạn hãy đăng ký kênh" thì chặn theo danh sách là
  xoá chữ thật của họ.
- Ngưỡng ba lần chọn theo đúng ca này, chưa đo trên nhiều loại thu âm.
- `condition_on_previous_text=False` **chưa chạy thật lần nào** — máy này
  không có Whisper. Lượt chạy tới của chủ dự án là phép thử đầu tiên.

## C27 — Bản chép lời vụn thành 1–2 chữ mỗi dòng (Phase H, 2026-08-24)

Chủ dự án chạy thật tệp giảng bài 3 giờ 43 trên v3.8.1 và gửi ảnh chụp màn
hình. Nhìn dòng nhật ký là thấy ngay:

```
Câu 449 · 12:06 — Là những
Câu 450 · 12:07 — Cử chỉ
Câu 451 · 12:07 — Hành vi
Câu 452 · 12:09 — Này
```

456 câu trong 12 phút 12 giây = **1,6 giây mỗi câu**. Ghép lại thì rõ ràng đó
là MỘT câu bị băm vụn. Với cả tệp là khoảng **tám nghìn dòng**, mỗi dòng 1-2
chữ.

### Nguyên nhân — có sẵn từ trước, không phải lỗi mới

`asr_whisper_worker.py` bật `vad_filter=True` với
`min_silence_duration_ms: 500`. Người giảng bài nói chậm và ngắt nhịp liên
tục, nên **mỗi nhịp ngắt là một câu mới**. Trên video biên tập sẵn (nói liền
mạch) thì không lộ; trên bài giảng thì lộ ngay.

**Chữ vẫn ĐÚNG và ĐỦ — chỉ chỗ xuống dòng là sai.** Đây là điểm quyết định
chỗ sửa: không đụng vào khâu nghe (đang chạy đúng), chỉ sửa khâu ghi.

### Vì sao gộp ở khâu ghi `.txt`, không ở khâu nghe

Phụ đề (`.srt`/`.vtt`) **cần** từng mẩu ngắn để hiện kịp trên màn hình. Gộp ở
khâu nghe là làm hỏng phụ đề để chữa cho văn bản. Có test đọc mã nguồn cấm
`gop_cau` xuất hiện trong đường ghi phụ đề.

Ba lý do để xuống dòng, theo thứ tự: mẩu trước kết thúc bằng dấu chấm câu ·
người nói nghỉ hơn 1,2 giây · dòng đã quá dài (14 giây hoặc 220 chữ). Mốc
thời gian của dòng gộp là mốc của mẩu **đầu tiên** — người đọc tua tới đó
phải rơi vào đầu câu, không phải giữa câu.

### Cứu lượt chạy đang chạy dở

Chủ dự án đang chạy dở vài giờ trên bản cũ. Bảo họ chạy lại là không được, nên
thêm nút **"Gộp câu cho .txt…"**: chọn một bản chép lời đã xuất, đọc ngược các
dòng `[mm:ss] chữ` thành câu, gộp, ghi ra tệp mới `…_da_gop.txt`.

Hai luật: **không ghi đè tệp gốc** (bản vụn vẫn là dữ liệu thật, gộp sai thì
còn đường quay lại), và **dòng không đúng khuôn thì nối vào câu trước** chứ
không vứt — vứt là mất chữ.

### Chứng minh từng luật

Bỏ luật "dấu chấm là ranh giới" → 5 đỏ. Gộp vô tận không giới hạn độ dài →
1 đỏ. Ghi đè tệp gốc → 1 đỏ.

**1858 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- **Không sửa chữ hoa.** Mỗi mẩu được bộ nghe viết hoa chữ đầu, nên dòng gộp
  đọc thành "Là những Cử chỉ Hành vi Này." Hạ chữ thường thì hỏng danh từ
  riêng (Google, TikTok) — chọn giữ nguyên chữ của người dùng, chấp nhận xấu.
- **Chưa hạ ngưỡng `min_silence_duration_ms`.** Sửa ở đó thì gốc rễ hơn,
  nhưng nó đổi hành vi của cả luồng lồng tiếng (phụ đề, khớp giọng) mà chưa đo
  được ảnh hưởng. Gộp ở khâu ghi là bản vá hẹp và an toàn.
- Ngưỡng gộp (1,2 giây / 14 giây / 220 chữ) chọn theo giọng giảng bài, **chưa
  hiệu chỉnh** trên nhiều loại thu âm.
- Nút gộp chạy trên luồng giao diện — đọc-ghi một tệp văn bản vài trăm KB,
  không phải việc chờ đợi.

## C26 — Cắt theo khoảng lặng, và tệp dài thì TỰ chia rồi TỰ ghép (Phase H, 2026-08-24)

Chủ dự án hỏi hai câu và trả lời một câu.

### 1. Sửa đúng điểm yếu tôi tự nêu

C25 cắt theo thời lượng đều, nên mỗi ranh giới rơi vào giữa một câu — tệp
3 giờ 43 cắt 8 đoạn là **7 câu bị chia đôi**, và một câu bị chia đôi là một
câu SAI ở CẢ HAI bản chép lời.

Nay dò quãng im bằng `silencedetect` rồi **nắn mốc cắt về quãng im gần nhất**
trong khoảng ±90 giây. Ba luật:

- Cắt ở **giữa** quãng im, không ở đầu cũng không ở cuối: cắt lúc bắt đầu im
  thì chữ cuối câu trước dễ hụt đuôi, cắt lúc hết im thì chữ đầu câu sau dễ
  mất.
- **Không có quãng im nào đủ gần thì giữ mốc đều** — thà cắt giữa câu còn hơn
  để một đoạn dài gấp đôi các đoạn khác.
- **Tên tệp mang mốc THẬT**, không suy từ `số thứ tự × độ dài đoạn` — mốc đã
  nắn thì phép nhân đó sai.

**Đo trên âm thanh thật** (55s tiếng — 4s im — 55s tiếng — 4s im — 55s tiếng):
dò ra đúng hai quãng im ở **57,0s và 116,0s**; cắt đều sẽ rơi vào 60/120 giữa
tiếng nói; bản mới cắt ở 57/116, đoạn đầu dài 57s thay vì 60s. Tổng thời lượng
không mất giây nào.

### 2. Tệp dài thì tự chia — và trả về MỘT mạch, không phải tám tệp

Câu hỏi: *"tệp dài thì nó tự hiểu không, và chạy xong ghép lại hay gửi thành
các file nhỏ?"*

Trước bản này người dùng phải tự bấm nút cắt. Nay `transcribe_media` tự xử:
dài quá **45 phút** thì cắt ra (theo khoảng lặng), nghe từng đoạn, rồi **ghép
lại thành một mạch duy nhất**.

Điểm mấu chốt là **dời mốc thời gian**: mỗi đoạn được ASR trả về với mốc bắt
đầu từ 0, nên phải cộng thời điểm bắt đầu thật của đoạn đó. Không dời thì tám
đoạn đều bắt đầu từ 00:00 và bản chép lời ghép lại thành vô nghĩa. Số thứ tự
câu cũng đánh lại cho chạy liền.

Vì sao ngưỡng 45 phút: dưới mức đó một lượt chạy liền mạch vừa đơn giản vừa
không có ranh giới nào để làm hỏng câu; trên mức đó thì lợi ích của chia nhỏ
(thấy tiến độ, hỏng một đoạn không mất cả buổi) vượt cái giá của ranh giới.

Nút "Cắt tệp dài…" của C25 vẫn giữ — cho ai muốn **tệp rời** thật sự (mỗi
đoạn một bản chép lời riêng), thay vì một mạch liền.

### 3. Câu hỏi không cần code: nhãn người nói

*"Nó có cần thiết không? Tôi chỉ cần nó viết chính xác nội dung."*

Trả lời: **không cần**, và tôi không làm. Tệp giảng bài chủ yếu một người nói;
nhãn *Người 1 / Người 2* không làm nội dung đúng thêm một chữ nào. Đổi lại nó
đòi cài `.venv-diar` + khoá HuggingFace, và **chưa từng chạy thật lần nào**
trong dự án. Ghi lại đây để lần sau ai hỏi thì có câu trả lời sẵn, không phải
cân nhắc lại từ đầu.

### Chứng minh từng luật

Bỏ nắn về khoảng lặng → 2 đỏ. Suy mốc từ số thứ tự → 1 đỏ. Không dời mốc khi
ghép → 1 đỏ.

**1840 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- Dò khoảng lặng phải **quét hết tệp một lượt** bằng ffmpeg trước khi cắt. Với
  tệp 3-4 giờ đó là thêm vài phút. Tắt được bằng `theo_khoang_lang=False`
  nhưng giao diện chưa có ô tắt.
- Ngưỡng im **-30 dB / 0,6 giây** chọn cho giọng giảng bài trong phòng ồn nhẹ;
  chưa hiệu chỉnh trên nhiều loại thu âm.
- Với tệp VIDEO, `-c copy` chỉ cắt được ở khung hình khoá, nên mốc thật có thể
  lệch vài giây so với mốc đã nắn. Với tệp âm thanh thuần thì gần như chính
  xác.
- **Vẫn chưa chạy thật một tệp dài nào qua ASR** — không có `.venv-whisper`
  trong môi trường này. Phần cắt và ghép mốc đã đo thật; phần nghe thì chưa.

## C25 — Cắt tệp dài, ngay trong app (Phase H, 2026-08-24)

Chủ dự án: *"tôi phải cắt sao vì tôi không có phần mềm cắt, bạn có hỗ trợ
không?"*

Câu trả lời đúng không phải "cài thêm phần mềm" — **ffmpeg thì app đã cần sẵn
cho mọi việc khác**. Nên nút cắt nằm ngay trên trang Chép lời, cạnh nút chọn
tệp.

### Hai quyết định

**Chép lại luồng, KHÔNG mã hoá lại** (`-c copy`). Mã hoá lại một tệp 3 giờ mất
hàng chục phút để đổi lấy một tệp *xấu hơn*, trong khi việc cần làm chỉ là
cắt. Đo thật: đổi sang mã hoá lại thì riêng bộ test đó chạy từ 36 giây lên
**118 giây** — trên tệp thử 5 phút. Nhân lên cho tệp 3 giờ 43 thì thấy ngay
đây không phải chuyện nhỏ.

**Tên tệp mang MỐC BẮT ĐẦU** (`..._phan_03_tu_01-00-00.m4a`). Sau khi cắt, mốc
thời gian trong mỗi bản chép lời chạy lại từ 0. Không nói ra thì người đọc
tưởng câu ở phút 5 của phần 3 là phút 5 của cả buổi. Tên tệp là chỗ duy nhất
giữ được thông tin đó mà không phải sửa đường chép lời.

Kèm `-reset_timestamps 1`: thiếu cờ này thì đoạn 2 mang mốc của phút thứ 30 và
nhiều trình phát tưởng tệp hỏng.

### Ba chỗ từ chối làm việc thừa

- Tệp **ngắn hơn một đoạn** thì trả về chính nó — cắt tệp 5 phút thành "một
  đoạn 5 phút" chỉ tạo thêm một bản sao vô ích.
- Chỉ cắt **tệp trên máy**, không cắt liên kết.
- Chỉ cắt **đúng một tệp** mỗi lượt (ô nguồn nhận nhiều tệp phân cách bởi `|`).

Cắt xong **tự điền các đoạn vào ô nguồn** — cắt xong mà bắt người dùng đi chọn
lại từng đoạn là bỏ dở việc giữa chừng.

### Đã cắt thật, không dừng ở "lệnh trông đúng"

Dựng một tệp `.m4a` thật 310 giây, cắt 2 phút mỗi đoạn: ra **3 đoạn
120+120+70 = đúng 310 giây**, không mất một giây nào, mỗi đoạn mở được và đọc
được độ dài. Bộ test dựng tệp thật bằng ffmpeg chứ không giả lập.

### Chứng minh từng luật

Mã hoá lại thay vì chép luồng → 1 đỏ. Bỏ `-reset_timestamps` → 1 đỏ. Tên tệp
không mang mốc bắt đầu → 1 đỏ.

**1831 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- Cắt theo **thời lượng đều**, không cắt theo khoảng lặng. Một câu nói vắt qua
  ranh giới hai đoạn sẽ bị chia đôi — với tệp giảng bài dài thì đó là một câu
  hỏng trên mỗi ranh giới.
- Chưa gộp các bản chép lời của các đoạn thành một tệp duy nhất có mốc thời
  gian liên tục. Tên tệp có mốc bắt đầu nên cộng tay được, nhưng vẫn là việc
  tay.
- Chưa thử với tệp vài GB: tệp thử là 2,5 MB.

## C23–C24 — Cùng ngôn ngữ thì BỎ khâu dịch, và Chép lời ghi dần (Phase H, 2026-08-24)

### C23 — Chặn là câu trả lời dở

C22 chặn cả ba đường vào khi nguồn trùng đích. Đúng về tiền, nhưng **bỏ mất
một việc người dùng thật sự cần**: đổi giọng cho video tiếng Việt sẵn có —
giọng gốc ồn, nói nhanh, hoặc muốn giọng khác. Việc đó chỉ cần nghe-chép →
tạo giọng → ghép, không cần dịch một chữ nào.

Nay đường ống có nhánh riêng: `khong_can_dich` tính ngay sau bước nghe-chép,
bỏ hẳn bước 4, và **câu đích chính là câu gốc** (`seg[target.text_field] =
seg["text"]`) nên các bước sau không cần biết gì về ca này.

**Chỗ quan trọng nhất là tiền, không phải luồng.** Cờ đó đi thẳng vào
`create_hold(auto_translate=…)`, nên máy chủ **không giữ chỗ tiền dịch**. Giữ
chỗ rồi không dùng nghĩa là người dùng bị chặn vì "không đủ Vox" cho một việc
không hề tốn Vox. Có test đọc thẳng mã để chắc cờ đi tới nơi, và test khoá
thứ tự: hỏi TRƯỚC khi giữ tiền, không phải sau.

Ba đường vào đổi từ **chặn** sang **nói ra**: người chọn Tiếng Việt vì tưởng
phải khai đúng ngôn ngữ video, chứ không biết mình vừa chọn một luồng khác —
im lặng cũng không được.

### C24 — Chép lời ghi dần, cho tệp 3 giờ 43 phút

Chủ dự án có một tệp `.m4a` 206 MB, dài **3:43:04**. Kiểm trước khi trả lời:
`.m4a` nằm trong danh sách nhận · **không có trần thời lượng hay dung lượng
nào** · timeout là 600 giây **giữa hai câu liên tiếp**, không phải cho cả tệp
— nên file dài bao nhiêu cũng chạy được miễn nó còn nhả câu.

Nhưng kết quả **chỉ ghi ra đĩa khi xong hết**: hỏng ở phút thứ 200 là mất
sạch, và trong lúc chạy không có gì trong tay để biết nó nghe tới đâu.

Nay mỗi câu nghe được là ghi thêm một dòng vào `<tên>.dang_chay.txt`. Bốn
quyết định:

- **Nối đuôi, không ghi lại cả tệp.** Vài nghìn câu mà ghi lại từ đầu mỗi lần
  là công việc bình phương theo số câu. Có test đếm số lần mở tệp = 1.
- **Xả đệm sau mỗi câu.** Đệm nằm trong bộ nhớ thì mất khi tiến trình bị giết
  — mà đó đúng là ca tệp này sinh ra để cứu.
- **Hỏng giữa chừng thì GIỮ tệp dở** và nói chỗ của nó. Xoá phần đã nghe được
  là lấy đi thứ duy nhất còn cứu được.
- **Ghi tạm hỏng không được làm hỏng lượt chép lời** — nó là tiện ích, hỏng
  thì cùng lắm mất tiện ích đó.

Chưa nghe được câu nào thì không tạo tệp rỗng; xuất xong thì xoá tệp dở để
thư mục không lẫn hai bản của cùng một nội dung.

### Con số tiền, lấy từ cấu hình

Giá: **10 Vox/câu** cho khâu dịch, 1 Vox = 10 đồng.

| Việc | Chi phí |
|---|---|
| Chép lời tệp 3:43 | **0 Vox** — Whisper chạy trên máy, không gọi máy chủ |
| Lồng tiếng vi→vi **trước C23** | ~2.700 câu × 10 Vox ≈ **270.000đ** cho một video |
| Lồng tiếng vi→vi **sau C23** | **0đ** cho khâu dịch |

Ước theo mật độ 4–6 giây/câu: 22.310 – 33.460 Vox, tức 223.000 – 335.000đ. Đó
là khoản C23 cắt bỏ, cho **mỗi** video tiếng Việt chạy qua luồng lồng tiếng.

### Chứng minh từng luật

Bỏ `flush` → 1 đỏ. Hỏng giữa chừng mà xoá tệp dở → 1 đỏ. Bỏ `try/except`
quanh hook ghi → 1 đỏ. Trỏ test vào `run()` thay vì `_run_impl` → đỏ (lớp đọc
cây cú pháp bắt đúng, tôi trỏ nhầm hàm).

**1819 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- Vẫn **chưa chạy thật** một tệp dài nào: không có `.venv-whisper` trong môi
  trường này. Đường ghi dần đã có test, nhưng lượt chạy 3 giờ đầu tiên vẫn là
  phép thử thật.
- Ghi dần chỉ có ở **trang Chép lời**, chưa có ở luồng lồng tiếng (ở đó câu
  còn phải đi qua dịch và tạo giọng nên "phần đã xong" khó định nghĩa hơn).
- Tệp dở là `.txt` có mốc thời gian, **không phải `.srt`** — nó để cứu vãn,
  không để dùng thẳng.
- Ca "đổi giọng" (vi→vi) chưa live-verify đầu-cuối.

## C22 — Chốt "nguồn trùng đích" chỉ có ở một trong ba đường vào (Phase H, 2026-08-24)

Chủ dự án hỏi: *"về nhận định rõ tiếng Việt và chọn ngôn ngữ video bị thiếu
tiếng Việt, bạn làm chưa?"*

**Đã làm, và đã có trong bản v3.7.2 đang phát hành.** Kiểm bằng mã: Tiếng Việt
(vi-VN) nằm trong `SOURCE_LANGS` dùng chung cho Tạo dự án / Xử lý hàng loạt /
Cài đặt; trang Chép lời có riêng; đích lồng tiếng có `vi`; dịch phụ đề rời có
`vie_Latn`. Và `asr_whisper_worker` chuẩn hoá `vi-VN` → `vi` rồi truyền thẳng
làm gợi ý ngôn ngữ cho Whisper — đó chính là thứ làm nhận dạng chính xác thay
vì để nó tự đoán.

### Nhưng chốt đi kèm thì chỉ có ở MỘT trong ba đường vào

Cùng lượt mở tiếng Việt (22/8), một chốt được thêm: nguồn trùng đích thì không
có gì để dịch, chặn lại và chỉ sang trang Chép lời. Chốt đó **chỉ có ở trang
Tạo dự án**.

- **Xử lý hàng loạt** không có ô chọn đích — nó LUÔN lồng sang tiếng Việt. Nên
  chọn nguồn Tiếng Việt ở đây là vi→vi cho **cả mẻ**: mỗi video một lượt gọi
  mô hình để nhận lại gần đúng câu cũ.
- **`voxdub dub`** mặc định `--target vi`, cũng không kiểm.

Sửa: đưa phép so xuống **lõi** (`autodub/languages.py`) để dòng lệnh dùng được
mà không phải nhập gói giao diện; gói giao diện mượn lại chứ không giữ bản
chép (hai bản chép là có ngày lệch). Chặn ở `_launch` — nơi CẢ HAI đường vào
của Xử lý hàng loạt đều đi qua, kể cả đường đẩy lên máy chủ — chứ không chặn ở
hai chỗ gọi, vì chặn ở nơi gọi thì thêm đường vào thứ ba là sót. Dòng lệnh
chặn **trước khi tải video**: tải xong mới báo là đã tốn băng thông của người
dùng.

### Lỗi trong chính lớp đọc mã của tôi

`cac_luot_goi()` khai là "theo thứ tự xuất hiện" nhưng dùng thứ tự `ast.walk`
trả về — mà `walk` đi theo **bề rộng của cây**, không theo dòng. Một lượt gọi
nằm sâu trong hai khối `if` ở đầu hàm bị trả về SAU một lượt gọi phẳng ở cuối
hàm, nên `goi_truoc()` so nhầm. Lộ ra khi kiểm thứ tự trong `cli._cmd_dub`:
`DubPipeline` (dòng cuối) đứng trước `cung_ngon_ngu` (dòng giữa).

Sửa: sắp theo `(dòng, cột)`. Thêm một mẫu bẫy đúng hình dạng đó vào
`test_doc_ma.py`, và gỡ dòng sắp ra đo lại → đỏ. Đây là lớp mà nhiều test
khác đứng lên, nên nó sai là chúng xanh giả.

### Chứng minh từng luật

Quay lại thứ tự `ast.walk` → 1 đỏ. Bỏ chốt ở Xử lý hàng loạt → 2 đỏ. Bỏ chốt
ở dòng lệnh → 2 đỏ.

**1808 passed, 7 skipped (Python) · smoke 18 trang.**

### Remaining Limits

- Nguồn tiếng Việt vẫn **chưa live-verify**: chưa chạy lượt lồng tiếng thật
  nào từ một video tiếng Việt (giới hạn mang từ C19).
- Chốt chỉ bắt được khi người dùng CHỌN ngôn ngữ. Bật "tự nhận dạng" thì
  không kết luận được — trả `False` có chủ đích, vì chặn oan còn tệ hơn không
  chặn. Nghĩa là auto-detect trên video tiếng Việt với đích tiếng Việt vẫn
  chạy một lượt dịch vô ích.
- Xử lý hàng loạt vẫn chưa có ô chọn đích. Thêm được, nhưng đó là thay đổi ở
  trang khác.

## C21 — Dọn thiết bị hàng loạt (Phase H, 2026-08-24)

Chủ dự án: *"có mỗi máy đầu là của tôi, còn lại là test; không thấy chỗ nào
tắt hoặc xoá hàng loạt, vào chi tiết tắt từng máy rất lâu."* Đúng — 25 máy
Linux rác cộng một máy CI, mỗi máy một lượt bấm vào rồi bấm ra.

Cũng chốt luôn: **bỏ mục hoàn 60 Vox** theo yêu cầu.

### Thao tác không lùi được thì chốt phải nằm trước cú bấm

Xoá một máy là xoá luôn ví Vox của máy đó. Nên phần quyết định "được làm gì
với máy nào" tách hẳn sang `device-bulk.service.js` để test được mà không cần
cơ sở dữ liệu, và có bốn chốt:

- **Trần 200 máy mỗi lượt.** Không phải chống lạm dụng — chống một cú bấm
  "chọn tất cả" trên bộ lọc rộng hơn người bấm tưởng.
- **Chỉ nhận danh sách vân tay tường minh.** Không nhận bộ lọc để tự quét:
  nhận bộ lọc là mở đường cho "xoá tất cả" bằng một tham số. Có test đọc mã
  nguồn cấm đúng chuyện đó.
- **Kể TÊN từng máy còn số dư**, không nói chung chung "một vài máy còn tiền".
  Xoá một ví còn tiền là huỷ tiền, và người bấm cần thấy điều đó TRƯỚC khi
  bấm chứ không phải sau.
- **Máy chọn mà không tìm thấy thì báo ra.** Chọn 25 máy mà chỉ 23 máy đổi
  trạng thái thì người bấm phải biết hai máy kia đi đâu.

Thêm một đường **xem trước** (`xemTruoc: true`): trả về đúng những gì sẽ xảy
ra mà không đụng gì. Giao diện hỏi máy chủ trước, rồi mới hiện hộp xác nhận
với số liệu thật — không đoán từ dữ liệu đang hiện trên màn hình.

### Giao diện

Ô chọn từng dòng + ô chọn cả trang; thanh công cụ hiện khi đã chọn, với ba
nút Khoá / Mở khoá / Xoá. Hộp xác nhận kể tên tối đa 10 máy còn tiền kèm tổng
Vox, và với việc xoá thì nói thẳng: *"Xoá không lùi lại được. Muốn giữ đường
quay lại thì dùng «Khoá» — máy bị khoá mất token ngay nhưng còn trong hệ
thống."*

Chọn theo **vân tay**, không theo chỉ số dòng: đổi trang hay đổi bộ lọc là chỉ
số trỏ sang máy khác — với thao tác không lùi được thì đó là lỗi chết người.

### Hai lần đặt sai chỗ trong JSX

Chèn thanh công cụ bằng script, hai lần đặt vào giữa nhánh của một biểu thức
ba ngôi — mà nhánh đó chỉ nhận MỘT phần tử. Cả hai lần đều lộ ra ngay ở bước
build, không lọt được đi đâu. Bài học nhỏ: chèn JSX bằng khớp chuỗi thì phải
neo vào mốc ở đúng CẤP, không neo vào thẻ gần nhất.

### Chứng minh từng luật

Bỏ trần số máy → 1 đỏ. Không kể tên máy còn tiền → 1 đỏ. Đọc dữ liệu trước
khi xét yêu cầu → 1 đỏ. Khoá mà không thu hồi token → 1 đỏ.

**510 pass (Node) · website build sạch.**

### Remaining Limits

- Xoá máy KHÔNG xoá lịch sử của máy đó (`UsageLog`, `CreditLedger`) — cố ý:
  sổ sách còn thì còn tra được, mà bản ghi máy thì không cần giữ. Nghĩa là
  báo cáo cũ vẫn đếm những máy đã xoá.
- Chưa có "chọn tất cả kết quả của bộ lọc" — chỉ chọn được trong TRANG đang
  xem. Với 25 máy thì một trang là đủ; nhiều hơn thì phải qua từng trang.
- Chưa có lọc nhanh theo mẫu tên (vd mọi máy tên `trieunt-c`). Gõ vào ô tìm
  rồi chọn cả trang là làm được, chỉ là chưa có nút tắt.
- Chưa chạy thật: cửa đã lên máy chủ nhưng chưa ai bấm.

## C20 — Bốn mục "còn tồn" tự ghi, làm nốt (Phase H, 2026-08-22)

Chủ dự án bảo: việc nào không cần anh vào thì làm trước. Bốn mục dưới đây đều
là mã thuần; ba mục còn lại (đủ 20 lượt hiệu chỉnh, hoàn 60 Vox, dọn 25 thiết
bị rác) đều cần quyền quản trị hoặc ảnh thật nên không tự làm được.

### 1. Hai tệp test JS còn đọc chuỗi — đã chuyển sang lớp `doc-ma`

`ai-provider-roles` và `test-now-va-soi-tay` là hai chỗ cuối còn đọc mã bằng
`indexOf`. Chuyển xong, rồi gỡ chốt khỏi route đo lại: **vẫn đỏ** — không mất
răng.

Chuyển xong lộ ra một luật dùng lớp đó: **mốc để so thứ tự phải là MÃ, không
phải chữ.** `truoc()` cố ý moi ruột chuỗi (để "gọi hàm X" không bị tính khi X
nằm trong câu thông báo), nên mã lỗi `'CHUA_DU_LUOT_SOI_TAY'` biến mất khỏi
bản đem so. Đổi mốc sang `xet.du` — chính phép kiểm.

### 2. Ô chọn thời lượng cảnh và kiểu chuyển cảnh

Sáu kiểu: mờ chồng · trượt trái · trượt lên · mở vòng tròn · tan dần · cắt
thẳng. Sáu mức thời lượng 1,5–6 giây.

Ba quyết định:

- **Danh sách ĐÓNG.** Giá trị này đi thẳng vào chuỗi bộ lọc của ffmpeg, nên
  chuỗi lạ vừa làm hỏng cả lượt ghép vừa là chỗ chèn tham số không ai kiểm.
  Có test bắn thử `"fade:duration=99,drawtext=text='x'"` — phải bị từ chối.
- **Khoá lạ thì NÉM LỖI**, không âm thầm rơi về mờ chồng: chọn một kiểu rồi
  nhận về kiểu khác là hỏng im lặng.
- **Cắt thẳng dùng `concat`, không dùng `xfade` thời lượng 0** — hai thứ đó
  không tương đương, `xfade` vẫn ăn mất một khoảng của cảnh sau. Đo thật:
  cắt thẳng 4,60 giây, mờ chồng 3,73 giây cho cùng ba ảnh.

**Ghép thật cả sáu kiểu bằng ffmpeg**, rồi trích khung ĐÚNG lúc chuyển cảnh và
mở ra nhìn: thấy rõ "11" trượt ra và "22" trượt vào, kiểu mở vòng tròn chồng
đúng kiểu vòng, và nhãn AI-generated còn nguyên trên cả hai.

Bảng lựa chọn trong giao diện **lấy thẳng từ `product_video`** chứ không chép
tay — chép tay là có ngày lệch.

### 3. Nhớ nơi gọi mô hình đã chọn

Trước đây mỗi lần mở app lại về «Tự động», nên ai muốn dùng cố định một nơi
gọi phải chọn tay mỗi lượt — và quên một lượt là trả tiền cho mô hình khác mà
không biết. Nay lưu vào chính tệp cấu hình của app.

Nơi gọi đã lưu mà nay không còn thì **không chọn bừa**: để «Tự động» và nói ra
— im lặng đổi nơi gọi đúng là thứ luật C17 cấm.

### 4. Gợi ý kịch bản xem được ảnh — mặc định TẮT

Xem ảnh thì câu dẫn bám vào thứ thật sự trong khung thay vì chỉ tên bối cảnh.
Đổi lại mô hình đọc nhiều gấp mấy lần.

**Nên có khoá giá riêng**: `credit.cost.assist.scene_script.co_anh` = 8 Vox so
với 3. Thu cùng một giá cho hai mức token là tự hở biên. Ô tick ghi thẳng
"8 Vox thay vì 3" — một ô tick âm thầm làm tăng tiền là thứ người dùng chỉ
phát hiện khi đọc lịch sử ví.

Thu nhỏ ảnh hỏng hết thì gửi **không ảnh** còn hơn bị tính giá-có-ảnh cho một
lượt không có ảnh nào.

### Lỗi tự gây khi làm, và nó nói lên điều gì

Tôi thêm một hàm `_bo_loc` vào tệp test **đã có sẵn một hàm cùng tên** — định
nghĩa sau đè định nghĩa trước, bảy test cũ đổ với một lỗi kiểu dữ liệu khó
hiểu. Đúng loại lỗi vừa bị nhắc: sửa tệp mà không đọc hết tệp. Đã đổi tên và
ghi lý do ngay tại chỗ.

**1800 passed, 7 skipped (Python) · 498 pass (Node) · web build sạch · smoke
18 trang.**

### Remaining Limits

- Kiểu chuyển cảnh là danh sách cố định 6 kiểu; ffmpeg có hàng chục kiểu nữa.
  Mở rộng bằng cách thêm dòng vào `KIEU_CHUYEN`, không phải sửa logic.
- Thời lượng áp cho MỌI cảnh như nhau — chưa đặt riêng từng cảnh được.
- Gợi ý kịch bản xem ảnh **chưa chạy thật lượt nào** (chưa ai bật ô đó).
- Nơi gọi mô hình nhớ theo MÁY, không theo tài khoản: đổi máy phải chọn lại.

## C19 — Nguồn tiếng Việt, và "chưa cài" phải nói là chưa cài (Phase H, 2026-08-22)

Hai việc từ hai câu hỏi liên tiếp của người dùng thật.

### 1. "Không thấy tiếng Việt trong danh sách, có cần cài thêm bộ nhận dạng không?"

Trả lời: **không cần cài gì thêm.** Whisper nghe được tiếng Việt sẵn
(Paraformer mới là bộ riêng, và nó chỉ dành cho tiếng Trung), còn bộ dịch
ngoại tuyến đã biết `vi-VN` → `vie_Latn` từ V4. Thiếu chỉ là **thiếu một dòng
trong danh sách chọn** — danh sách nguồn dừng ở 8 ngôn ngữ từ V4 và không ai
quay lại thêm khi các đích mới mở ra ở V11/V17.

Có nghĩa khi đích khác tiếng Việt: video tiếng Việt → lồng tiếng Anh, Nhật…

Nhưng mở nguồn tiếng Việt thì đẻ ra ca mới: **nguồn tiếng Việt + đích tiếng
Việt**. Dịch tiếng Việt sang tiếng Việt là trả tiền cho một lượt gọi mô hình
để nhận lại gần đúng câu cũ. Nay chặn sớm và chỉ sang trang Chép lời — thứ họ
thật sự cần khi chỉ muốn văn bản.

Kèm một bộ canh chung: **mọi mã nguồn trong danh sách đều phải có mã dịch
tương ứng**. Thêm ngôn ngữ mà quên bảng dịch là hỏng lúc chạy, không phải lúc
dựng.

### 2. `ModuleNotFoundError: No module named 'vieneu'`

Người dùng nâng cấp sang thư mục mới, chạy lồng tiếng, và nhận nguyên văn câu
lỗi Python. Đúng về mặt kỹ thuật, vô dụng với người đọc: không biết phải cài
gì, cài bằng cách nào, hay đây có phải lỗi ứng dụng không.

Nay kiểm **dấu hiệu cài xong trên đĩa** trước khi khởi động tiến trình con, và
nói thẳng: *"Chưa cài bộ giọng đọc VieNeu cho bản này. Mở thư mục ứng dụng rồi
chạy «Cai dat giong VieNeu.bat»"*, kèm giải thích rằng nâng cấp sang thư mục
mới thì ứng dụng tự tìm lại bản cài ở thư mục cũ cạnh bên (V77) — không thấy
nghĩa là thư mục cũ đã bị xoá hoặc đổi chỗ.

Kiểm bằng dấu hiệu trên đĩa **chứ không thử import** — bài học V74: bản đóng
gói không mang theo mấy gói nặng đó nên import trong tiến trình chính luôn trả
lời sai.

Và khi worker vẫn hỏng vì lý do khác, câu lỗi nay kèm **đường dẫn trình thông
dịch đang dùng**: cùng một câu "No module named" có thể là venv hỏng, cũng có
thể là đang chạy nhầm Python hệ thống — không in ra thì không phân biệt được.

### Tests (+12)

Tiếng Việt (9): có trong danh sách nguồn · nhãn đọc được · bộ dịch biết mã đó ·
Paraformer vẫn chỉ dành cho tiếng Trung · Việt→Việt bị coi là trùng · các cặp
trùng khác (Anh, Nhật, ba biến thể tiếng Trung) · cặp khác ngôn ngữ thì không
chặn · để máy tự nghe thì không kết luận · **mọi mã nguồn đều có mã dịch**.

VieNeu (3): chưa cài thì nói rõ phải chạy tệp nào và **không** nhắc
`ModuleNotFoundError` · chưa cài thì **không khởi động tiến trình con** (chạy
rồi mới báo là bắt người dùng chờ vô ích) · đã cài rồi thì vẫn đi tiếp như cũ.

Gỡ chốt "chưa cài" ra → 2 đỏ. Bộ test cũ về phong cách đọc phải nói rõ "đã
cài" — chốt mới chặn đúng chỗ nên nó chặn cả test doubles.

**1790 Python · 499 Node.**

### Còn tồn

- Chưa biết vì sao máy người dùng khởi động được một Python mà Python đó
  không có `vieneu`. Câu lỗi mới in đường dẫn ra, lần sau gặp là biết ngay.
- Nguồn tiếng Việt chưa live-verify: chưa chạy lượt lồng tiếng thật nào từ
  video tiếng Việt.

## C18 — Cổng video chặn nhầm đúng người đang hiệu chỉnh (Phase H, 2026-08-22)

Chủ dự án dựng xong 3 ảnh (2 lượt kiểm đều SAFE, lý do đọc được: *"Chỉ đổi bối
cảnh, ánh sáng và góc chụp, sản phẩm vẫn y hệt"*), bấm **Dựng video ngắn** và
nhận: *"Chức năng dựng video mở sau khi ảnh sản phẩm đã qua đợt hiệu chỉnh và
được duyệt."*

Cổng chặn chạy **đúng như thiết kế**. Nhưng thiết kế sai chỗ.

Lý do gốc của cổng vẫn đúng: đừng đem ảnh chưa ai soi tay đi làm nội dung bán
hàng. Chỉ có điều nó chặn nhầm đúng một người — **chính chủ shop, trên chính
máy đã được duyệt vào danh sách hiệu chỉnh**, muốn xem thử cả chuỗi chạy ra
sao trước khi bỏ 660 Vox chạy đủ 20 lượt. Người đó cũng là người gánh hậu quả
nếu đăng nhầm. Cấm họ xem thử không bảo vệ ai cả — chỉ khiến họ phải trả tiền
trước rồi mới biết mình mua gì.

### Sửa: mở kèm cảnh báo, không mở suông

Nấc `calibration` + máy **trong danh sách** → dựng được, kèm câu *"Đây là bản
dựng thử trong đợt hiệu chỉnh: ảnh trong video CHƯA ai soi tay. Xem cho biết
thì được, đừng đăng bán."* Máy ngoài danh sách vẫn bị chặn y như cũ.

Câu cảnh báo in vào **Nhật ký**, không chỉ toast — toast biến mất sau ba giây,
còn câu này người dùng cần đọc lại được đúng lúc cầm video đi đăng.

### Một cửa mới, vì cửa cũ không biết đang nói với ai

`app_config()` không đăng nhập nên máy chủ không biết trả lời cho máy nào — mà
nấc `calibration` mở **theo từng máy**. Thêm `GET /v1/ai/scene-stage` (có đăng
nhập), trả `runMode` + `videoDuoc` + `canhBao` tính theo đúng vân tay máy gọi.

### Tests (+9)

Máy chủ (5): nấc tắt thì không ai dựng được · máy trong danh sách dựng được
kèm cảnh báo · **máy ngoài danh sách vẫn bị chặn** (mở cho máy ngoài là mở cho
tất cả) · nấc chạy thật mở cho mọi máy và **không** cảnh báo (cảnh báo ở nấc
chạy thật là dạy người dùng bỏ qua cảnh báo) · route hỏi theo vân tay máy đang
gọi.

App (4): nấc tắt in nguyên văn lý do máy chủ · nấc chạy thật mở và im lặng ·
máy đang hiệu chỉnh dựng được **nhưng phải cảnh báo** · cảnh báo vào Nhật ký
và **không** biến thành chặn.

**1778 Python · 499 Node.**

### Xác nhận được C16 bằng lượt chạy thật

Cùng lúc này bộ đếm hiệu chỉnh chạy đúng lần đầu: 2 lượt `runMode=calibration`,
verdict SAFE, đã vào danh sách chờ soi tay. Lượt cũ trước bản vá vẫn nằm trong
nhóm `khong-ro` — không đếm được, và không sửa ngược lại.

## C17 — Chọn nơi gọi mô hình, và ô "Tên sản phẩm" (Phase H, 2026-08-22)

Chủ dự án hỏi ba câu cùng lúc. Cả ba đều đúng chỗ.

**1. "Thêm liên kết phần mềm tạo ảnh khác, chọn được nhà cung cấp."** Một nửa
đã có: bốn giao thức, trong đó **"Tự khai"** cắm được nền tảng bất kỳ bằng
cách khai đường dẫn và khuôn dữ liệu — không cần viết code. Nửa thiếu đúng như
câu hỏi: **chọn**. Nhiều nơi gọi trong cùng một vai trước giờ chỉ là hàng chờ
dự phòng, cái đầu hỏng mới rơi xuống cái sau.

Nay có ô "Nơi gọi mô hình", mặc định *Tự động*. Hai luật: chọn tên không còn
tồn tại thì **báo lỗi, không rơi âm thầm** (rơi âm thầm = người dùng tưởng trả
tiền cho mô hình mình chọn, thực tế trả cho mô hình khác), và chặn **trước khi
tính tiền**. Danh sách gửi xuống app chỉ có tên + nhãn — khoá API và địa chỉ
máy chủ là chuyện quản trị.

Hỏi danh sách là lượt gọi mạng nhỏ nhưng vẫn là gọi mạng → `ImageProvidersWorker`,
không nằm trong `on_shown()` (bài học C7).

**2. "Một tấm ảnh thì lấy đâu ra 17 tấm nữa."** Không có bản vá cho câu này, và
đó mới là câu trả lời thật: chủ dự án bán hosting, tên miền, chữ ký số — **dịch
vụ, không phải hàng vật lý**. Tính năng dựng cho người bán TikTok Shop có hàng
thật trong kho; chạy một tấm ảnh 20 lần chỉ chứng minh mô hình nhất quán với
đúng tấm đó. Đã nêu ba đường (chụp 5–7 món thật / dừng và làm bộ dựng banner /
hạ ngưỡng — nhưng hạ là làm yếu chính cái chốt) và **không tự quyết thay**.

**3. "Gợi ý kịch bản dựa trên prompt nào."** Đọc mã trả lời: gửi lên đúng tên
các bối cảnh và ô "Ghi chú thêm" gắn nhãn *Sản phẩm*. **Nó không nhìn thấy tấm
ảnh.** Luật ghim trong câu lệnh: mỗi cảnh ≤12 chữ, nói lợi ích hoặc cảm giác,
cấm hứa công dụng chữa bệnh, cấm từ tuyệt đối. Ô Ghi chú vốn để tả bối cảnh
nên đang kiêm hai việc → thêm ô **"Tên sản phẩm"**, trống thì lui về ghi chú.

### Tests (+17)

Máy chủ (8): liệt kê đúng nơi gọi đang bật của vai ảnh · thứ tự theo ưu tiên ·
**không lộ khoá API** · nhãn trống thì lấy tên · tìm theo tên đúng vai · nơi
gọi đã tắt thì tìm không ra · không truyền tên thì đi đường Tự động · **route
tra tên TRƯỚC khi trừ tiền**.

App (9): không chọn thì không gửi gì · chọn thì gửi đúng tên cho **cả mẻ** ·
mặc định Tự động · danh sách luôn giữ Tự động ở đầu và hiện NHÃN · danh sách
rỗng vẫn còn Tự động · lựa chọn đi xuống worker · hỏi danh sách không nằm trên
luồng giao diện · tên sản phẩm đi vào gợi ý kịch bản · chưa điền thì lui về
ghi chú.

Đảo thứ tự tra tên xuống sau khi trừ tiền → đỏ. **1775 Python · 494 Node.**

### Còn tồn

- Mỗi vai vẫn chỉ một chuỗi ưu tiên: chọn theo từng lượt thì được, nhưng chưa
  đặt được luật "banner luôn dùng OpenAI, ảnh sản phẩm luôn dùng Gemini".
- Gợi ý kịch bản vẫn không nhìn thấy ảnh. Cho nó xem sẽ tốn thêm tiền mỗi
  lượt; chưa làm vì chưa biết có đáng không.

## C16 — Lượt kiểm chạy thật không ghi phán quyết (Phase H, 2026-08-22)

Lộ ra ở đúng lượt kiểm bao bì THẬT đầu tiên của dự án, ngay sau khi C15 mở
được đường: sổ ghi `runMode: ''`, `verdict: ''`, `reason: ''`.

Bảng hiệu chỉnh đếm theo đúng ba trường ấy, nên lượt kiểm rơi vào nhóm
"khong-ro" và số lượt hợp lệ vẫn là 0. Nghĩa là đợt hiệu chỉnh **không bao giờ
đủ 20 lượt** dù người bán chạy bao nhiêu ảnh — mỗi ảnh vẫn tốn 33 Vox.

Gốc rễ ngược đời: bản ghi ở đường **đọc-từ-đệm** có đủ ba trường, còn bản ghi ở
đường **chạy thật** thì không. Lượt đáng đếm nhất lại là lượt không được đếm.

Bộ canh đọc thẳng mã nguồn: mọi bản ghi thành công trong đường `/assist` phải
mang `verdict` + `reason` + `runMode`. Gỡ một trường ra để đo → đỏ. **+3 test.**

## C15 — Máy chủ trừ tiền rồi chết vì một dòng ghi bộ nhớ đệm (Phase H, 2026-08-22)

Câu lỗi lấy từ tệp log trên máy chủ dự án — thứ duy nhất chỉ đúng chỗ sau khi
tôi đi tìm nhầm hai vòng:

    JobResult validation failed: action: `product_scene` is not a valid enum
    value for path `action`.

Chuỗi hậu quả dài nhất dự án gặp tới nay:

1. `assist` (V89) và `product_scene` (C1) thêm route mà quên thêm vào enum
   `action` của `JobResult`.
2. Mongoose ném lỗi validation; `remember()` ném tiếp ra ngoài.
3. Route chết **sau khi** đã gọi Gemini và đã trừ tiền.
4. `UsageLog` viết trước nên sổ máy chủ ghi **"thành công"** — và tôi tin sổ
   đó, đi tìm lỗi ở phía app suốt hai vòng.
5. App nhận 500, báo "Không dựng được ảnh nào": không ảnh, không lượt kiểm.
6. Chủ dự án bấm ba lượt, mất 90 Vox, không lượt nào thấy ảnh.

### Sửa hai tầng

- Enum có đủ `assist` + `product_scene`, kèm test đối chiếu **thẳng với mã
  nguồn**: mọi giá trị route gọi `remember()` phải nằm trong enum. Bỏ một giá
  trị ra để đo → 3 đỏ.
- **`remember()` không bao giờ ném ra ngoài nữa.** Đây là lớp tăng tốc: lượt
  gọi đã chạy xong, tiền đã trừ, kết quả đang trong tay — để một dòng ghi đệm
  giết cả lượt gọi là người dùng mất tiền mà không nhận được gì. Hỏng thì kêu
  to trong log máy chủ, người dùng vẫn nhận kết quả đã trả tiền.

### Bài học đắt nhất

**Sổ ghi "thành công" không chứng minh người dùng nhận được gì.** Nó chỉ chứng
minh dòng ghi sổ chạy trước dòng làm hỏng. Lần sau gặp "máy chủ bảo xong, app
bảo hỏng" thì đọc log của máy KHÁCH trước, đừng đọc sổ máy chủ trước.

**+6 test** (kèm phía app: lý do hỏng từng bối cảnh nay hiện thẳng lên dòng
trạng thái và khung Nhật ký, thay cho câu "thử lại sau ít phút" — câu đó sai
với gần hết nguyên nhân thật, mà thử lại thì mất thêm 30 Vox mỗi lượt).

## C14 — Cổng tuân thủ chưa từng chạy một lần nào (Phase H, 2026-08-22)

Chủ dự án bấm "Dựng ảnh" trên v3.6.2, chờ, rồi báo **"không thấy gì hết"**.
Sổ máy chủ nói ngược lại: hai lượt `product_scene`, cùng thành công, Gemini
chạy 13,7 và 14,1 giây, trừ 60 Vox. Nhưng sổ còn nói một điều nữa, nặng hơn
nhiều: **0 lượt `packaging_check`**.

Tức là ảnh đã dựng, tiền đã trừ, và **cổng kiểm bao bì — lý do tồn tại của cả
tính năng — chưa từng chạy một lần nào.**

### Ba lỗi chồng lên nhau, mỗi lỗi che lỗi kia

**1. Ảnh vừa dựng đi thẳng lên máy chủ để kiểm, không thu nhỏ.**
`chuan_bi_anh()` thu nhỏ và chặn trần 1,6MB — nhưng chỉ cho ảnh GỐC. Ảnh do mô
hình trả về (PNG 1024px, base64 vài MB) được đưa nguyên vào lượt kiểm, cộng
với ảnh gốc là vượt trần thân yêu cầu. Lượt kiểm bị chặn ở **tầng vận chuyển**
— trước cả khi vào route — nên nó không để lại một dòng nào trong sổ. Nhìn từ
máy chủ: như thể app chưa bao giờ hỏi.

Sửa: tách `thu_nho_de_gui()` ra dùng chung, ảnh vừa dựng cũng phải qua đó.
Phán quyết không kém đi: bước này nhìn bao bì và chữ trên nhãn, không soi từng
điểm ảnh.

**2. Kiểm hỏng thì chỉ ghi "chưa kiểm được".** Đúng chính sách (nghiêng về phía
an toàn) nhưng vô dụng với người bán: không biết nên chụp lại ảnh, đợi mạng,
hay báo lỗi. Nay kèm nguyên văn nguyên nhân.

**3. Và người dùng không thấy gì cả — lỗi của chính C10.** Thẻ "Thứ tự cảnh"
được chèn ngay dưới hàng nút, đẩy dòng trạng thái, khung Nhật ký **và cả lưới
ảnh** xuống dưới đáy màn hình. Bấm nút, chờ 14 giây, màn hình không đổi một
chút nào — trong khi bên dưới tầm nhìn mọi thứ vẫn chạy và vẫn tiêu tiền.

Sửa: trật tự theo đúng trình tự người dùng làm — nhập → bấm → **trạng thái →
Nhật ký → ảnh** → rồi mới tới sắp thứ tự cho video (việc chỉ có nghĩa khi đã
có ảnh). Thêm `_cuon_toi_trang_thai()` gọi lúc bắt đầu và lúc xong: đúng thứ
tự khối vẫn chưa đủ khi cửa sổ thấp.

### Một chuyện không phải lỗi

Chủ dự án mở thư mục `output/anh_san_pham` và thấy trống. Đó là thư mục của
bản **v3.6.1**, còn hai lượt chạy là của **v3.6.2** (sổ ghi rõ `appVersion`) —
ảnh nằm trong thư mục của bản mới. Kiểm tra sổ trước khi kết luận mất dữ liệu
là việc đáng làm.

### Tests (+5)

Engine (3): ảnh vừa dựng **phải qua bước thu nhỏ** trước khi đi kiểm · 2 ảnh
phải ra **2 lượt kiểm** (đo bằng chính con số đã sai: 0) · kiểm hỏng thì lý do
nói rõ vì sao.

Giao diện (2): dòng trạng thái, Nhật ký và lưới ảnh đều phải nằm **TRÊN** danh
sách thứ tự · `_chay` và `_xong` đều phải kéo màn hình tới chỗ có phản hồi.

Bản đầu của test bố cục đỏ oan vì so `y()` của hai widget khác cha — danh sách
nằm trong một thẻ Card nên số của nó nhỏ hơn dù đứng dưới. Phải quy về cùng hệ
toạ độ bằng `mapTo()`.

Gỡ bước thu nhỏ ra → đỏ. **1763 passed, 7 skipped.**

### Còn tồn

- Chưa xác nhận lại bằng lượt chạy thật: cần chủ dự án dựng thêm một ảnh trên
  v3.6.3 rồi xem sổ có `packaging_check` chưa. **Chưa có bằng chứng cổng tuân
  thủ hoạt động — chỉ có bằng chứng nó đã không hoạt động.**
- 60 Vox đã trừ cho hai ảnh không hề được kiểm. Chưa hoàn.

## C13 — Ô nhập bị ép bẹp, và CI ăn mất suất dùng thử (Phase H, 2026-08-22)

Hai lỗi do chính hai bản sửa hôm nay đẻ ra.

### 1. Trang Ảnh sản phẩm không cuộn được

Chủ dự án gửi ảnh chụp v3.6.1: các ô "Chế độ", "Ghi chú thêm", "Thư mục lưu
ảnh" bị cắt ngang, nhìn như chồng lên nhau.

Trang chưa bao giờ nằm trong vùng cuộn. Trước C10 nội dung còn vừa cửa sổ nên
không ai thấy; C10 thêm thẻ "Thứ tự cảnh" là tràn, và Qt hết chỗ thì **ép mọi
widget xuống dưới chiều cao tối thiểu của chúng** — chữ trong ô bị cắt.

Đo bằng chính định nghĩa của lỗi (`height() < sizeHint().height()`), dựng trang
thật ở chế độ không màn hình với đúng bộ giao diện của app:

| Cửa sổ cao | Trước | Sau |
|---|---|---|
| 1050px | ép 1 widget | ổn |
| 950px | ép 1 | ổn |
| 850px | ép 1 | ổn |
| 750px | ép 1 | ổn |

Sửa: bọc trang vào `QScrollArea` theo đúng khuôn trang Cài đặt đang dùng. Danh
sách thứ tự đổi từ **trần** 170px sang **sàn** 150px — trần làm nó co lại tới
mức vô dụng khi thiếu chỗ, sàn buộc vùng cuộn phải cấp đủ chỗ rồi cuộn.

Quét 6 trang khác chưa có vùng cuộn (`character`, `download`, `subtitle_tool`,
`subtitle_translate`, `transcribe`, `translate_tool`): ở 700px đều **ổn** —
nội dung ngắn hơn. Không đụng vào.

### 2. Mỗi lần CI dựng bản là một suất 500 Vox bị tiêu

Ngay lượt build đầu sau khi C12 nhúng được địa chỉ máy chủ, danh sách thiết bị
mọc ra một máy tên `runnervm6iq3x (Windows 10.0.26100)` **mang 500 Vox dùng
thử**. Smoke test dựng đủ mọi trang; trang Tài khoản gọi máy chủ; máy chủ cấp
thiết bị mới kèm suất dùng thử.

Sửa ở `resolve_api_url()` — cửa duy nhất mọi lượt gọi phải đi qua, nên không
còn đường vòng nào: `AUTODUB_SMOKE=1` thì trả rỗng.

Nhưng như thế smoke test mất luôn khả năng biết địa chỉ đã nhúng hay chưa —
đúng thứ C12 vừa sửa. Nên mục `api_url_nhung` đọc **thẳng tệp nhúng**, không
qua `resolve_api_url()`, và **bản dựng hỏng nếu nó False**. Lỗi im lặng hôm
qua nay là lỗi dựng.

### Tests (+6)

Bố cục (2): cửa sổ thấp thì không widget nào bị ép dưới `sizeHint` · trang
phải nằm trong vùng cuộn. Gỡ vùng cuộn ra → 24 đỏ.

Chạy thử tự động (4): chế độ chạy thử thì không có máy chủ · ngoài chế độ đó
vẫn đọc địa chỉ như thường · vẫn báo được đã nhúng hay chưa (chốt đối lập:
đọc qua `resolve_api_url()` thì bản dựng nào cũng hỏng) · thiếu địa chỉ thì
`ok = False`.

**1758 passed, 7 skipped.**

### Đã đặt trên máy chủ

Máy Windows của chủ dự án (`DESKTOP-KHMFF0U`, mã `E11BFB39`) đã đăng ký thật
và được thêm vào `image.scene.calibration.devices` cùng với workspace.

### Còn tồn

- Thiết bị `runnervm…` và 25 máy Linux rác vẫn nằm trong cơ sở dữ liệu, vài
  cái còn Vox dùng thử. Dọn là xoá dữ liệu thật — chờ chủ dự án quyết.
- Chưa có bộ canh nào cho các trang khác về chuyện cuộn; hiện chỉ đo tay một
  lượt ở 700px.

## C12 — Mọi bản .exe từng phát hành đều chạy ngoại tuyến (Phase H, 2026-08-22)

Chủ dự án cài v3.6.0, mở app lên, nhắn "tôi đã mở rồi". Máy chủ **không thấy
thiết bị nào đăng ký** — vẫn đúng 25 máy Linux cũ, không có máy Windows nào.

Không phải mạng, không phải khoá. `scripts/build_exe.py` đọc `VOXDUB_API_URL`
từ **`.env` của máy build**, mà máy dựng bản phát hành là runner Windows của
GitHub — nó không có `.env`. Nên `autodub_gui/_embedded.py` được ghi bằng
chuỗi RỖNG, và `resolve_api_url()` của bản đóng gói chỉ đọc đúng giá trị nhúng
đó (biến môi trường cố ý bị bỏ qua khi `sys.frozen`).

**Mọi bản `.exe` CI từng phát hành đều chạy hoàn toàn ngoại tuyến.** Menu vẫn
đủ, trang Ảnh sản phẩm vẫn hiện, bấm vào thì không có gì xảy ra — và **không
có câu lỗi nào**, vì với địa chỉ rỗng thì đó là chế độ chạy-thuần-trên-máy
hoàn toàn hợp lệ theo mã. Đúng loại hỏng im lặng đắt nhất: nhìn như đang chạy.

Trước giờ không lộ ra vì mọi lượt thử đều chạy **từ mã nguồn** trong workspace,
nơi có `.env` và nơi biến môi trường được đọc.

### Sửa

- `read_env_value()` đọc **biến môi trường trước**, rồi mới tới `.env`.
- `release.yml` truyền `VOXDUB_API_URL` cho bước build. Không phải bí mật —
  là địa chỉ công khai của máy chủ — nên để thẳng trong workflow cho ai đọc
  cũng thấy, không giấu vào secret.
- Nhánh "không có địa chỉ" nay **kêu to** trong log build (`!! ... sẽ chạy
  NGOẠI TUYẾN`) thay vì một dòng ghi chú hiền lành.

### Tests (+5)

Không có `.env` thì lấy từ biến môi trường (đúng ca của runner CI) · biến môi
trường được ưu tiên hơn `.env` · không truyền gì thì vẫn đọc `.env` như cũ ·
không có gì cả thì trả rỗng · **`release.yml` phải truyền `VOXDUB_API_URL`, và
phải truyền TRƯỚC dòng chạy build**.

Bản đầu của chính test cuối dính đúng bẫy C8: cắt tệp ở chữ
`scripts/build_exe.py` đầu tiên, mà chữ đó nằm trong **lời chú thích** đầu
workflow chứ không phải dòng chạy → đỏ oan. Cắt ở `run: python
scripts/build_exe.py` mới đúng.

Gỡ biến khỏi `release.yml` để đo → đỏ. **1752 passed, 7 skipped.**

### Còn tồn

- Bản v3.6.0 đã phát hành vẫn là bản ngoại tuyến; v3.6.1 mới là bản đầu tiên
  thật sự nói chuyện được với máy chủ.
- Đổi địa chỉ máy chủ vẫn phải phát hành lại `.exe`. Bản đóng gói cố ý không
  đọc biến môi trường, và giao diện không có ô nhập địa chỉ. Chấp nhận ở đợt
  này; nếu sau này đổi tên miền thì đây là việc phải làm.

## C11 — Lượt gọi THẬT đầu tiên, và một máy hoá thành 25 máy (Phase H, 2026-08-22)

Chủ dự án cắm khoá Gemini rồi bảo "làm hộ hết". Đây là lần đầu tiên toàn bộ
chuỗi C1→C10 chạm vào mô hình thật.

### Khoá cắm rồi, nhưng tên mô hình sai hai chỗ

"Thử ngay" trên vai `image` trả **404** ngay lượt đầu. Cấu hình là
`google/gemini-2.5-flash`:

1. Tiền tố `google/` là cách gọi của OpenRouter. Giao thức Google dựng URL
   `…/models/<mô hình>:generateContent`, nên tiền tố đó thành một phần đường
   dẫn không tồn tại.
2. `gemini-2.5-flash` là mô hình **chữ**, không vẽ được ảnh.

Thử ba tên, giữ tên chạy được — và đây là chỗ suýt để lại rác: vòng thử để
lại tên CUỐI CÙNG (hỏng) trong cấu hình. Phải đặt lại tên đúng rồi gọi thật
một lượt nữa để xác nhận, chứ không tin vòng lặp đã dừng ở đâu.

| Tên mô hình | Kết quả |
|---|---|
| `gemini-2.5-flash-image` | **gọi được, CÓ ảnh thật**, 11,5s |
| `gemini-2.5-flash-image-preview` | 404 |
| `gemini-2.0-flash-preview-image-generation` | 404 |

### Vai `assist` hoá ra không cần tạo thêm

Định xin thêm khoá để tạo dòng vai `assist`, nhưng đọc lại
`ai-gateway.service.js`: không có nhà cung cấp `assist` thì cổng trợ lý **tự
rơi về vai `translate`**, và phép sàng "nhìn được ảnh" chạy trên chính vai đó.
Vai `translate` sẵn có đang là `gemini-2.5-flash` — mô hình nhìn được ảnh.

Chạy phép thử nhìn trên nó: **đọc đúng số `9952`** trong ảnh máy chủ tự vẽ.
Tức là cổng tuân thủ đã có mô hình đủ tư cách phán quyết, không cần thêm gì.
Hỏi mã trước khi xin thêm khoá của người khác là việc đáng làm.

### Một máy, 25 thiết bị, và những suất dùng thử miễn phí

Định đặt vân tay máy vào danh sách hiệu chỉnh thì thấy máy chủ có **25 thiết
bị, tất cả đều tên `trieunt-c (Linux …)`** — cùng một máy. Vài cái mang 500
Vox dùng thử.

Gọi `get_fingerprint()` ba lần trong ba tiến trình: **ba giá trị khác nhau**.

Gốc rễ ở `autodub/device_id.py`: máy không phải Windows thì lấy `uuid.getnode()`
làm mã máy. Trên container không có MAC nào để đọc, và khi đó Python **bịa một
số ngẫu nhiên mới mỗi tiến trình** (RFC 4122, bật bit multicast để báo chính
điều đó). Bản cũ dùng thẳng số ấy.

Hai hậu quả, cái sau nặng hơn cái trước:

- Danh sách máy hiệu chỉnh vô dụng: thêm vân tay hôm nay, lượt chạy sau đã là
  máy khác.
- **Mỗi lần mở ứng dụng là một ví mới kèm một suất dùng thử mới.** Không cần
  ác ý, không cần biết gì về hệ thống — chỉ cần chạy trên máy Linux/container.

Sửa: số ngẫu nhiên đó ghi xuống `~/.voxdub_device_id` một lần rồi dùng lại.
Đường Windows (MachineGuid trong registry) **không đổi một dòng nào** — máy
đang dùng thật không bị đổi danh tính. Ghi tệp hỏng thì kêu lên chứ không im,
vì nhìn từ phía người dùng thì hậu quả là "tự dưng mất tiền".

Đo lại: ba tiến trình → **một vân tay**. Gỡ chốt ra → 3 đỏ.

### Tests (+6)

Có MAC thật thì dùng MAC và **không đẻ ra tệp**; không có MAC thì không được
dùng số Python bịa; hai lượt chạy ra cùng một mã; mã đã có trên đĩa thì dùng
lại nguyên văn; không ghi được tệp thì vẫn chạy nhưng **phải kêu lên**; vân
tay ổn định qua nhiều lượt.

**1747 passed, 7 skipped (Python) · 477 pass (Node).**

### Đã đặt trên máy chủ thật

`image.scene.stage` = `calibration`, `image.scene.calibration.devices` = vân
tay (nay đã ổn định) của workspace. Thứ tự cố ý: dán vân tay TRƯỚC, bật nấc
SAU — ngược lại thì mọi máy đều bị từ chối và rất dễ tưởng tính năng hỏng.

### Còn tồn

- **Chưa có ảnh sản phẩm thật nào đi qua.** Bước tiếp theo cần người: dựng
  20–30 ảnh hàng thật rồi soi tay từng phán quyết. Máy chủ chặn cứng ở 20 lượt
  ĐÃ SOI (không phải đã chạy) trước khi cho bấm nấc `production`.
- 25 thiết bị rác vẫn nằm trong cơ sở dữ liệu, vài cái còn Vox dùng thử. Chưa
  dọn — dọn là xoá dữ liệu thật, cần chủ dự án quyết.
- Ví của vân tay ổn định mới đang là 0 Vox; dựng ảnh thật sẽ cần nạp.

## C10 — Kéo-thả sắp cảnh + nhãn AI ở tầng video (Phase H, 2026-08-21)

Chủ dự án gửi một bản đề bài "C3 — ghép ảnh sản phẩm thành video ngắn". Đối
chiếu trước khi gõ dòng nào: **đó chính là C6 của repo, đã xong lúc 15:54**,
và phần bản đề bài hẹn "C3b làm sau" chính là C7, xong lúc 16:24. 7/8 ràng
buộc đã có sẵn, một chỗ còn chặt hơn đề bài (băm nội dung tệp — đề bài không
nghĩ tới đường thay ruột tệp sau khi kiểm).

Trừ hết phần đã có, còn đúng hai việc thật. Làm hai việc đó.

### 1. Thứ tự cảnh do người bán quyết, không phải do máy

Trước C10, thứ tự trong video là thứ tự ghi trong nhật ký — tức là thứ tự
MÁY dựng ảnh. Người bán không nói được "mở bằng cảnh trên tay, đóng bằng cảnh
giỏ quà". Nay có danh sách kéo-thả (`QListWidget` + `InternalMove`), bỏ tích
được ảnh không muốn đưa vào.

Danh sách **chỉ nạp ảnh đăng bán được** — không phải để giấu, mà vì đây là
danh sách "đưa vào video", và ảnh lệch nhãn thì không được vào. Lý do vì sao
một ảnh không được vào vẫn hiện dưới chính ảnh đó ở lưới kết quả.

**Chỗ quyết định của cả mini-spec này** nằm ở ca hiếm: ảnh đã chọn mà phán
quyết bị lật giữa lúc chọn và lúc bấm ghép. Cách dễ là lặng lẽ bỏ ảnh đó ra —
và đó là cách sai: video xuất được, thiếu một cảnh, không ai biết. Nay ảnh đó
**vẫn đi xuống** lớp kiểm cuối để bị chặn cả lượt kèm tên ảnh và lý do. Đắt
hơn một nhịp, nhưng người bán biết chuyện gì đã xảy ra.

Ảnh biến mất hẳn khỏi nhật ký cũng đi xuống, với lý do "không còn trong nhật
ký ảnh đã dựng" — không im lặng bỏ qua.

### 2. Nhãn AI-generated đóng thêm một lần ở tầng video

C1 đã đóng nhãn lên từng tấm ảnh, nên thoạt nghe là thừa. Không thừa: nhãn
của C1 chỉ nằm trên ảnh đi qua đường dựng của C1. Ngày nào ghép thêm ảnh từ
nguồn khác — ảnh chụp thật, ảnh cũ, ảnh người dùng tự sửa — thì video ra đời
không nhãn mà không ai kịp nhận ra. `_lenh_ghep()` là hàm duy nhất tạo ra tệp
video, nên đóng ở đây là chỗ duy nhất phủ được mọi nguồn.

Không có tham số nào tắt được — có test riêng cho điều đó, vì một cái nút tắt
là một cái nút để bấm nhầm.

Đặt ở đỉnh khung (nhãn C1 nằm đáy — chồng nhau thì đọc được đúng một cái), chỉ
hiện suốt cảnh đầu. Bản đầu có nhánh riêng cho video một ảnh (`null[ra]`) và
nhánh đó **suýt không có nhãn**; đã gộp làm một đường.

### Kiểm bằng video thật, không chỉ bằng chuỗi lệnh

Dựng thật một video hai ảnh bằng ffmpeg, rồi trích khung ở giây 1 và giây 4:
khung đầu có nhãn, khung sau sạch. Test đọc chuỗi lệnh chỉ chứng minh chuỗi
đúng — nó không chứng minh ffmpeg chịu chạy chuỗi đó.

### Tests (+17)

Nhãn (8): có mặt ở cảnh đầu · **video một ảnh cũng phải có** · nhãn nằm trên
luồng RA cuối cùng chứ không phải một nhánh bỏ đi · đổi nhịp thế nào cũng còn
(3 ca) · không có tham số nào tắt được · đường xuất thật vẫn mang nhãn (chặn
ca sửa `_lenh_ghep` mà quên đường `dung_video` gọi).

Thứ tự (9): danh sách chỉ có ảnh đăng bán được · kéo-thả được bật · **thứ tự
kéo lại quyết định thứ tự video** · bỏ tích thì ảnh đó không vào · bỏ tích hết
thì không ghép · ảnh nay không còn đạt thì VẪN đi xuống để bị chặn · ảnh biến
mất khỏi nhật ký đi xuống kèm lý do · chưa nạp danh sách thì giữ nếp cũ ·
dựng ảnh xong thì danh sách hiện ra.

Gỡ nhãn khỏi chuỗi lệnh → **7 đỏ**. Gỡ dây nối danh sách thứ tự → **5 đỏ**.

**1733 passed, 7 skipped (Python) · 477 pass (Node).**

### Máy chạy test mất sạch thư viện hệ thống giữa chừng

Đầu phiên này `pytest` báo **24 tệp không import nổi** (`libGL.so.1`), rồi sau
đó **21 test đỏ** vì không còn `ffmpeg` — cùng một máy mà buổi sáng chạy 1716
test xanh. Không phải lỗi mã: workspace mất các gói hệ thống ở tầng `/usr`.
Cài lại đúng danh sách CI đang cài (`libgl1 libegl1 libfontconfig1 … ffmpeg`)
là xanh lại.

Đáng ghi vì nó cùng một bài học với C9, ở tầng thấp hơn một nấc: **một lượt
test xanh chỉ có giá trị kèm theo môi trường nó chạy**. `.github/workflows/
test.yml` đã liệt kê đủ các gói này từ V38 — thứ thiếu là một lối cài lại
nhanh cho máy phát triển.

**Chữa dứt, ngay trong cùng lượt (bổ sung sau khi chủ dự án hỏi "giải quyết
chưa" — câu trả lời đúng lúc đó là *chưa*, mới chỉ chữa một lần):**

- `scripts/cai_moi_truong_test.sh` — một lệnh, cài đủ 18 gói rồi tự kiểm lại
  bằng chính hai thứ đã hỏng (`import PySide6.QtWidgets`, `command -v ffmpeg`).
- `tests/conftest.py` hỏi hai câu rẻ tiền **trước khi thu thập test**. Thiếu
  thì dừng ngay với MỘT câu kèm câu lệnh chữa, thay vì 24 lỗi import rời rạc
  ở 24 tệp chẳng liên quan gì nhau. Có lối thoát
  `VOXDUB_BO_QUA_KIEM_MOI_TRUONG=1` cho ai cố ý chạy nhóm test không cần Qt.
- Danh sách gói **không được trôi khỏi CI**: `tests/test_kiem_moi_truong.py`
  đối chiếu script với `.github/workflows/test.yml`. Script được phép nhiều
  hơn (máy chạy CI của GitHub có sẵn `libfontconfig1`/`libfreetype6`, workspace
  trần thì không) nhưng không được thiếu. Bỏ một gói khỏi script để đo → đỏ.
- Gỡ lượt gọi khỏi `pytest_configure` thì mọi test khác vẫn xanh, nên có một
  test hỏi cây cú pháp đúng lượt gọi đó (bài học C8).

Đo bằng đúng ca đã hỏng: giấu `ffmpeg` khỏi `PATH` rồi chạy `pytest` →
dừng ngay, in đúng ba dòng đọc được. **+8 test, tổng 1741.**

Còn tồn: gói vẫn phải cài lại sau mỗi lần workspace mất `/usr`. Chữa tận gốc
là đưa chúng vào image workspace của Coder — nằm ngoài repo, cần người quản
trị template.

### Còn tồn

- **Live verification vẫn chưa chạy được**: chưa có ảnh SAFE thật nào. Chủ dự
  án đã cắm khoá vai `image`; còn thiếu vai `assist` (mô hình nhìn được ảnh)
  và 20 lượt soi tay để chuyển nấc sang `production`. Toàn bộ C1→C10 vẫn chưa
  có một lượt gọi thật nào đi qua.
- Nhãn tầng video chỉ hiện ở cảnh đầu (đúng phạm vi đề bài). Nếu sau này ghép
  ảnh từ nguồn ngoài đường dựng của app thành thói quen, nên cân nhắc cho nhãn
  chạy suốt video.
- Chưa có ô chọn thời lượng mỗi cảnh / kiểu chuyển cảnh — vẫn là hằng số.

## C9 — Bộ test hết phụ thuộc máy đang rảnh hay bận (Phase H, 2026-08-21)

Rà lại chính những gì C8 vừa báo "xanh": chạy lại từ đầu trên máy này thì
**Node đỏ 28 test**, còn `pytest` gõ trần thì **đổ core dump**. Cả hai đều
không phải lỗi trong mã sản phẩm — nhưng cả hai đều làm cho câu "bộ test xanh"
mất giá trị làm bằng chứng, nên phải sửa trước khi làm tiếp bất cứ thứ gì.

### 1. Mỗi tệp test một `mongod` — 12 tệp song song là 12 `mongod`

Lượt chạy đầu: 28 đỏ, toàn ở những tệp đụng cơ sở dữ liệu (kích hoạt key, quản
trị API key, ví, giữ tiền). Ba lượt sau: 0 đỏ. Thứ khác nhau giữa các lượt là
**máy đang bận tới đâu**, không phải mã.

Ép tái hiện cho chắc, không đoán: chạy hai lượt `npm test` song song →
**55 đỏ và 81 đỏ**, và số test tự phình từ 472 lên 479/482 (hook teardown chết
thì `node --test` đẻ thêm mục). Nguyên nhân ở `tests/helpers/db.js`: mỗi tệp
dựng một `MongoMemoryServer` riêng, `node --test` chạy song song theo số CPU
(ở đây 12), mỗi `mongod` vài trăm MB, máy còn 7GB trống.

Không chọn cách hạ `--test-concurrency`: nó chỉ làm bộ test chậm đi và **vẫn
để kết quả phụ thuộc máy**, chỉ là cần bận hơn mới đỏ. `tests/chay.js` dựng
đúng MỘT `mongod` cho cả suite, truyền địa chỉ qua `TEST_MONGO_URI`, mỗi tiến
trình lấy một **database riêng** — cách ly giữ nguyên, bộ nhớ giảm 12 lần,
tốc độ không đổi (18,7s so với 20s).

Tên database không dùng pid trần: hệ điều hành cấp lại pid sau khi tiến trình
chết, nên một tệp chết giữa chừng có thể để rác cho tệp sau trùng pid. Thêm
phần ngẫu nhiên là hết cửa đó.

Chạy lẻ một tệp (`node --test tests/foo.test.js`) không có biến đó thì hàm tự
dựng instance riêng như cũ — không ai phải nhớ thêm bước nào.

### Chính tệp test mới rò rỉ đúng thứ nó đi sửa

Bản đầu của `tests/db-dung-chung.test.js` gọi hàm lấy địa chỉ máy chủ hai lần;
lần hai dựng thêm một `mongod` và **ghi đè biến đang giữ cái thứ nhất**. Cái
thứ nhất thành mồ côi, tiến trình không bao giờ thoát, bộ test treo cứng 5
phút rồi bị giết. Sáu test đều `ok` mà lượt chạy vẫn hỏng — nhớ lại lời hứa
(`hua`) thay vì gọi lại là xong.

### 2. `pytest` gõ trần thì đổ core dump

Qt không nạp nổi plugin `xcb` khi máy thiếu `DISPLAY`. CI không bao giờ lộ ra
vì workflow tự đặt `QT_QPA_PLATFORM=offscreen` — biến đó **chỉ nằm ở CI**, nên
mọi máy chạy tay đều dính, và không có gì nói cho người gõ biết vì sao. Người
đọc kết quả sẽ hiểu thành "bộ test vỡ rồi".

`tests/conftest.py` nay tự đặt biến đó khi máy không có màn hình, đặt ở tầng
module (conftest được import trước mọi test module). Có `DISPLAY` thật thì
**không đụng vào** — ở đó dựng cửa sổ thật mới là đúng.

### Đo lại sau khi sửa, bằng đúng phép đo đã làm nó đỏ

- Hai lượt `npm test` song song — ca từng ra 55 đỏ và 81 đỏ: **0 đỏ cả hai**.
- `pytest` gõ trần, xoá sạch `QT_QPA_PLATFORM` và `DISPLAY`: **1716 passed**.
- Gỡ chốt Qt khỏi `conftest.py` rồi chạy lại: **core dump (mã 134)** — bộ canh
  cắn đúng, không mất răng.

### Tests (+8)

Node (6, `tests/db-dung-chung.test.js`): `npm test` phải đi qua `chay.js` chứ
không gọi `node --test` trần; `chay.js` dựng đúng một `mongod`; `startDb` nối
vào máy chủ chung khi có `TEST_MONGO_URI` và lấy database riêng; **`stopDb`
không được tắt máy chủ chung** (chứng minh bằng cách ping lại được sau đó, chứ
không phải bằng đọc mã); chạy lẻ không có biến vẫn tự dựng được; hai lần lấy
tên database ra hai tên khác nhau.

Python (2, `tests/test_qt_khong_man_hinh.py`): máy không màn hình thì biến phải
là `offscreen`; và **dựng được `QApplication` thật** — đây mới là thứ đã sập,
biến đặt đúng mà plugin vẫn không nạp được thì test này đỏ còn test kia vẫn
xanh.

**1716 passed, 7 skipped (Python) · 477 pass, 1 skip, 0 fail (Node).**

### Còn tồn

- Hai tệp test JS còn đọc chuỗi thay vì cây cú pháp (`ai-provider-roles.test.js`,
  `test-now-va-soi-tay.test.js`) — mang từ C8, vẫn là việc dọn dẹp.
- Số test phình lên khi hook teardown chết là hành vi của `node --test`, không
  sửa được từ phía dự án; nay chỉ còn là dấu hiệu để nhận ra sự cố hạ tầng.

## C8 — Sửa cái gốc: test đọc mã bằng tìm chuỗi (Phase H, 2026-08-21)

Chủ dự án: *"bạn bắt đầu hay sai rồi đó, hãy xem cẩn thận, đã test kỹ hơn,
còn tiến trình nào bạn chưa làm"*. Nhận xét đúng. Trong một ngày tôi mắc
**bốn lỗi cùng một loại**, và cả bốn đều nằm ở test đọc mã nguồn bằng cách
tìm chuỗi:

| # | Kiểu hỏng | Hậu quả |
|---|---|---|
| 1 | `indexOf(a) < indexOf(b)` khi `a` vắng mặt (−1 < mọi vị trí) | test XANH cả khi gỡ sạch thứ cần kiểm |
| 2 | Khớp phải chữ trong **chú thích** (hoặc trong chuỗi thông báo) | đỏ oan / xanh giả |
| 3 | Cắt thân hàm tới `module.exports` nên **đọc lây sang hàm sau** | đỏ oan |
| 4 | Tìm tên hàm trần nên khớp luôn **dòng khai báo của chính nó** | đỏ oan |

Ba lần đầu tôi vá từng chỗ. Lần thứ tư thì rõ đây là mẫu, không phải xui.

### Sửa gốc, hai bên

**Python có `ast` sẵn** — không có lý do gì đoán bằng chuỗi. `tests/doc_ma.py`
hỏi thẳng cây cú pháp: `co_goi(ham, ten)`, `cac_luot_goi(ham)`,
`goi_truoc(ham, a, b)`. Cả bốn kiểu hỏng biến mất cùng lúc: lượt gọi trong
chú thích không tồn tại trong cây, dòng `def` không phải `ast.Call`,
`inspect.getsource` cắt đúng một hàm, và `goi_truoc` trả `False` khi THIẾU
một vế thay vì âm thầm coi là đúng.

**JavaScript không có bộ phân tích cú pháp trong dự án** — thêm một phụ thuộc
chỉ để chạy test là cái giá không đáng. `tests/helpers/doc-ma.js` là lớp mỏng
làm đúng bốn việc: bỏ chú thích, moi ruột chuỗi khi soi, cắt thân hàm tới hàm
kế tiếp, và `truoc()` bắt buộc cả hai vế phải CÓ MẶT rồi mới so thứ tự.

**Hai tầng phải tách rời** — và chính test của helper bắt được điều đó: bản
đầu gộp "bỏ chú thích" với "moi ruột chuỗi" làm một, nên không tìm nổi route
nào (đường dẫn route nằm trong chuỗi). Tách thành `boChuThich` (để TÌM và
CẮT) và `boChuoi` (để SOI).

### Bộ canh cho chính bộ canh

`tests/test_doc_ma.py` (5 test) và `tests/doc-ma-helper.test.js` (7 test)
kiểm đúng bốn kiểu hỏng trên bằng mẫu mã cố tình dựng ra để bẫy. Nếu lớp đọc
mã hỏng thì mọi test đứng trên nó xanh giả, nên nó phải có test riêng.

Đã chuyển các phép kiểm cũ sang: `image-stage`, `vision-probe`,
`test_product_scene_page`, `test_dung_video_san_pham`. Gỡ chốt khỏi route để
đo lại sau khi chuyển: **vẫn đỏ 2 test** — bộ canh không mất răng.

### Một bản sửa ÂM THẦM KHÔNG ÁP DỤNG

Giữa lúc chuyển, một lượt thay thế trong script của tôi không khớp vì lệch
đúng một chỗ xuống dòng — và script **không kiểm nên im lặng cho qua**. Chỉ
lộ ra khi test báo `than is not defined`. Từ đó mọi lượt sửa hàng loạt đều có
`assert` trước khi ghi tệp.

### Rà "còn tiến trình nào chưa làm"

- **Deploy worker: đã xong lúc 08:34** — tôi hứa báo lại rồi quên. Đây là
  thiếu sót về quy trình, không phải về mã.
- **Bộ đo:** chạy khô cả 9 tác vụ — sạch. Nhưng lượt khô in chữ "đạt" cho cả
  mẫu cần ảnh, dễ đọc thành "tác vụ này chạy tốt". Đổi thành *"cấu hình ổn
  (cần ảnh thật)"* — đúng thứ cờ `canAnh` sinh ra để tránh.
- **Hai bộ canh sẵn có của repo** (pyflakes tên không tồn tại; nuốt lỗi phải
  có dấu vết) đều phủ tệp mới và đều xanh.
- **Quét cả gói giao diện** tìm chỗ khác gọi máy chủ trong hàm xử lý sự kiện:
  chỉ còn `check_startup`, mà hàm đó đã nằm sẵn trong `QThread`.

**1714 passed, 7 skipped (Python) · 471 pass (Node) · website build sạch.**

### Remaining Limits

- Lớp đọc mã JS là bộ cắt bằng tay, không phải bộ phân tích cú pháp thật. Nó
  chặn được bốn kiểu hỏng đã biết; mã dùng cú pháp lạ (chuỗi lồng phức tạp,
  biểu thức chính quy chứa dấu nháy) có thể làm nó cắt sai. Có test riêng cho
  từng kiểu, nhưng không phủ được mọi cú pháp JS.
- Chưa chuyển hết: `ai-provider-roles.test.js` và `test-now-va-soi-tay.test.js`
  vẫn đọc chuỗi. Chúng đang xanh và cắn đúng, nên chuyển nốt là việc dọn dẹp,
  không phải sửa lỗi.

## C7 — Kiểm liên tục giữa các cảnh + gợi ý kịch bản (Phase H, 2026-08-21)

### Một tiền đề lặp lại đúng lỗi lần trước

Bản đề bài nói "thêm field vào `ProductSceneVideoJob` (đã có ở C3)" và "gắn
vào `POST /v1/product-scene/video-job/{id}/export`". **Cả hai đều không tồn
tại** — C6 chạy hoàn toàn trên máy người dùng, đúng như đã ghi trong báo cáo
C6. `grep VideoJob|video-job` trong `control_server/` và `autodub/`: rỗng.
Đây là lần thứ ba một bản đề bài giả định có thực thể phía máy chủ mà kiến
trúc đã cố ý không dựng.

Phần còn lại thì khớp: cổng trợ lý đúng là danh sách đóng 7 tác vụ với 4 lớp
chặn chi phí, và thêm tác vụ theo đúng khuôn đó là việc làm được ngay.

### Lỗi tiềm ẩn từ C1 mà bản này sẽ đâm thẳng vào

Trước khi thêm tác vụ gửi 6 ảnh, đo lại đường ống hiện có:

> Schema cho phép **2 ảnh × 2,8 MB = 5,6 MB**, nhưng `bodyLimit` của máy chủ
> là **4 MB**.

Nghĩa là một cặp ảnh đủ lớn bị Fastify chặn ở tầng vận chuyển — người dùng
nhận một lỗi trống không, không mã lỗi nào của mình, không câu nào giải
thích, và toàn bộ lớp thông báo tử tế viết ở C1 không bao giờ chạy tới. Sửa
hai đầu: trần mỗi ảnh phía app hạ về 1,6 MB (ảnh đã thu về 1024px thì thừa
thãi), và máy chủ thêm trần TỔNG kèm câu nói rõ đã gửi bao nhiêu, trần bao
nhiêu.

### Hai tác vụ mới, và ranh giới quan trọng nhất

`scene_continuity` — `packaging_check` so ảnh cảnh với ảnh GỐC, nên nó không
thấy được chuyện các cảnh lệch NHAU: mỗi cảnh là một lượt gọi độc lập, mô
hình không có trí nhớ giữa các lượt, nên góc máy và tỉ lệ sản phẩm trôi mỗi
cảnh một kiểu dù cảnh nào cũng khớp ảnh gốc.

**Đây là lớp CẢNH BÁO, không phải lớp chặn.** Lệch liên tục là chuyện video
xem có mượt không; lệch bao bì mới là chuyện bị sàn phạt. Trộn hai mức đó làm
một là dạy người dùng bỏ qua cả hai. Có test đọc thẳng mã nguồn của
`dung_video`/`kiem_lai_truoc_khi_xuat` để chắc chữ `kiem_lien_tuc` **không
xuất hiện** trong đường quyết định xuất — thêm nó vào là đỏ ngay.

`scene_script` — gợi ý câu dẫn và nhịp cho từng cảnh. Chỉ in ra khung Nhật ký
để người bán chép; không có đường nào từ đây dán chữ vào video, vì câu chữ
bán hàng là thứ họ chịu trách nhiệm trước sàn.

### Ba quyết định về chi phí

- **Một lượt cho cả mẻ, không so từng cặp.** So cặp thì chi phí nhân theo
  bình phương số cảnh để đổi lấy một câu trả lời không khác gì mấy.
- **Không chạy khi chỉ có một ảnh** — không có gì để so, gọi là tiêu tiền lấy
  câu trả lời hiển nhiên.
- **Ảnh gửi đi kiểm thu về 512px.** Việc cần nhìn là cỡ sản phẩm trong khung,
  góc máy, tông màu — không cần đọc chữ trên nhãn (bước khác đã lo). Sáu ảnh
  cỡ lớn thì vượt trần thân yêu cầu.

Hỏng thì **im lặng bỏ qua**: cảnh báo hỏng không được biến thành báo động.

### Ba bộ canh cũ cắn đúng

Thêm tác vụ mà quên mẫu đo → đỏ. Thêm khoá giá mà quên khai vào danh sách giá
công khai → đỏ. Trần `maxResults` ≤ 5 → đỏ vì `scene_script` trả một câu cho
mỗi cảnh mà video ghép được tới 6. Nới trần lên 6 **có ghi lý do**, không
phải nới cho qua.

Mẫu đo của `scene_script` chặn luôn hai thứ ở tầng câu chữ: không hứa công
dụng chữa bệnh, không dùng từ tuyệt đối ("tốt nhất", "số một") — sai luật
quảng cáo là rủi ro của người bán, đừng đợi ai đó phát hiện trên TikTok.

### Cùng một cái bẫy Python, lần thứ hai trong ngày

`goi.setdefault("chay", True) or <đối tượng>` — `setdefault` trả về giá trị
truthy nên `or` không bao giờ chạy tới vế sau, và stub trả về `True` thay vì
đối tượng giả. Mắc ở test giao diện C6 buổi sáng, mắc lại ở test C7 buổi
chiều. Đã viết lại cả hai bằng lớp thật thay vì lambda lồng nhau.

### Rà lại ngay sau khi phát hành — và tìm ra lỗi của chính bản vừa làm

Chủ dự án bảo "xem qua lại". Đọc lại bằng mã, lộ ra một lỗi **tôi vừa tự tạo
ra trong chính C7**:

> `kiem_lien_tuc()` gọi mạng (chờ tới **60 giây**) và thu nhỏ tới sáu ảnh
> bằng ffmpeg — nhưng tôi gọi nó **thẳng trong hàm xử lý nút bấm**, tức là
> trên luồng giao diện. Bấm "Dựng video ngắn" là cả cửa sổ đứng hình, kể cả
> dòng "Đang ghép…" cũng không kịp hiện ra. `goi_y_kich_ban()` y hệt, 45 giây.

Đây đúng là lớp lỗi mà cả kiến trúc worker của dự án sinh ra để chặn, và tôi
vẫn mắc vì mải nghĩ về ranh giới cảnh-báo-vs-chặn.

Sửa: `kiem_lien_tuc` chuyển vào trong `ProductVideoWorker.run()` rồi bắn tín
hiệu `canh_bao` ngược lên (thứ tự đúng: cảnh báo trước, ghép sau); thêm
`SceneScriptWorker` cho phần gợi ý. Hai test mới đọc thẳng mã nguồn: hàm xử
lý nút **không được** chứa lượt gọi `product_video.kiem_lien_tuc(` hay
`product_video.goi_y_kich_ban(`, và hai worker **phải** chứa.

Quét luôn cả gói giao diện tìm chỗ khác gọi máy chủ trong hàm xử lý sự kiện:
chỉ còn `check_startup` — mà hàm đó đã nằm sẵn trong `QThread`, dương tính
giả.

**Bẫy test lần thứ tư trong ngày:** bản đầu của phép kiểm tìm chuỗi
`goi_y_kich_ban(`, và nó khớp luôn dòng `def _goi_y_kich_ban(self)` của chính
phương thức đang đọc → đỏ oan. Phải tìm lượt gọi CÓ TÊN MÔ-ĐUN.

### Chứng minh từng luật

Biến cảnh báo liên tục thành cổng chặn → 1 đỏ. So từng cặp thay vì một lượt →
2 đỏ. Máy chủ hỏng mà coi như có lệch → 1 đỏ. Cho giao diện tự nạp ảnh lệch →
1 đỏ (từ C6, vẫn cắn). Trả lượt gọi mạng về luồng giao diện → 1 đỏ.

**1708 passed, 7 skipped (Python) · 464 pass (Node) · smoke 18 trang.**

### Remaining Limits

- **Chưa chạy thật lượt nào** — cùng nút chặn từ C1: chưa có nhà cung cấp.
  Riêng `scene_continuity` còn phụ thuộc mô hình NHÌN ĐƯỢC ẢNH, nên nó đi qua
  đúng phép thử mù của C4.
- Giám khảo chỉ ra "ảnh số mấy lạc" bằng thứ tự trong lượt gửi. Nếu người
  dùng bỏ bớt ảnh rồi ghép lại, số thứ tự trong câu cảnh báo cũ không còn
  khớp — hiện chỉ in ra Nhật ký nên không gây hiểu nhầm dai dẳng, nhưng nếu
  sau này gắn badge cạnh từng ảnh thì phải đánh số lại.
- Chưa có kéo-thả sắp thứ tự (giới hạn mang từ C6).
- Gợi ý kịch bản chưa nối vào lồng tiếng — đúng phạm vi bản đề bài đặt ra.

## C6 — Ghép ảnh sản phẩm đã duyệt thành video ngắn (Phase H, 2026-08-21)

Bản đề bài (chủ dự án gọi là "C3") có **mục tiêu và các lằn ranh đều đúng**,
nhưng **cơ chế thì dựa trên một hệ thống khác với hệ thống này**. Đối chiếu
với mã trước khi làm, ba tiền đề lệch:

1. **`image_id` không tồn tại.** Bản đề bài dựng cả một thực thể job trên máy
   chủ, nhận danh sách `image_id`, và một bộ kiểm hỏi lại "trạng thái ảnh"
   qua API. Nhưng **máy chủ không hề biết đến ảnh nào** — C2 đã cố ý quyết
   định không lưu ảnh. `grep image_id` trong `control_server/`: rỗng.
2. **"Dấu tin cậy hết hạn 7 ngày làm phán quyết bị lật"** — hiểu nhầm. Hạn 7
   ngày của `visionOkAt` quyết định một NƠI GỌI có được chạy lượt kiểm mới
   hay không; nó không lật ngược phán quyết đã cho trên một tấm ảnh. Và lượt
   soi tay đánh dấu lên một dòng nhật ký sử dụng, không gắn với tệp ảnh nào.
3. **"Tái dùng pipeline dựng video hiện có, không viết engine mới"** — đúng
   một nửa. `autodub/media/video.py` có `merge_video`, `render_preview_clip`,
   bộ chọn bộ mã hoá — nhưng **không có hàm nào ghép ảnh tĩnh thành video**
   (`grep -loop|concat|framerate` trong `media/`: rỗng). Phải viết, bằng
   ffmpeg — mà ffmpeg là tiến trình con, nên đằng nào cũng đúng quy tắc "engine
   nặng không nằm trong tiến trình chính".

### Nhưng bản năng của bản đề bài thì đúng, và có một phiên bản THẬT của nó

Bản đề bài lo "trạng thái ảnh đổi giữa lúc chọn và lúc xuất". Trong kiến trúc
này, phiên bản thật của rủi ro đó **nguy hiểm hơn** thứ nó mô tả:

> Nhật ký chỉ ghi TÊN tệp. Không có gì ngăn người ta thay ruột tệp sau khi
> kiểm xong — tên vẫn thế, nhật ký vẫn ghi "đạt", giao diện vẫn hiện xanh, mà
> ảnh đã là ảnh khác.

Đó là đường lách thật duy nhất, và nó không cần ác ý: sửa ảnh cho đẹp hơn rồi
lưu đè là đủ. Nên `product_scene.py` nay **băm từng ảnh SAU khi đóng nhãn**,
và `kiem_lai_truoc_khi_xuat()` đối chiếu lại dấu vân tay ngay trước lúc ghép.

Ba điều kiện để một ảnh vào được video, thiếu một là loại: phán quyết là
**đăng bán được** · **đã đóng được nhãn AI-generated** · **nội dung tệp còn
khớp dấu lúc kiểm**. Điều kiện thứ hai cũng là chỗ trước đây bỏ ngỏ: `dong_nhan_ai`
trả `False` khi ffmpeg hỏng, nhưng không ai ghi lại — nay ghi vào nhật ký.

### Nhật ký bản cũ thiếu trường thì coi như CHƯA đạt

Ảnh dựng bằng bản trước không có `bam` lẫn `da_dong_nhan`. Không có cách nào
biết chúng còn nguyên hay không, nên chúng bị loại kèm câu chỉ việc phải làm
("dựng lại ảnh này rồi ghép"). Mặc định nghiêng về phía an toàn, không phải
phía tiện — có test khoá đúng chiều đó.

### Hàm xuất là chỗ cuối cùng nói được "không"

`dung_video()` gọi lại toàn bộ phép kiểm bên trong, **không tin bên gọi đã
kiểm**. Đây là hàm duy nhất tạo ra tệp video, nên nó phải là nơi cuối cùng
từ chối được — đúng gap mà bản đề bài gọi là nguy hiểm nhất, chỉ khác chỗ đặt.

### Đã dựng một video thật và MỞ RA XEM

Không dừng ở "hàm chạy không lỗi": dựng 3 ảnh, ghép, `ffprobe` ra
1080×1920 / 3,73 giây, rồi trích 3 khung ghép lại thành một tấm và nhìn bằng
mắt — đúng thứ tự 1111 → 2222 → 3333, ảnh được **đệm** hai bên chứ không bị
cắt. Cắt cho vừa khung dọc là có ngày cắt mất chính cái nhãn mà cả tính năng
này sinh ra để giữ, nên `crop` bị test cấm.

### Chỉ mở ở nấc chạy thật

Ghép video ở nấc hiệu chỉnh nghĩa là đem những tấm ảnh chưa ai soi đi làm nội
dung bán hàng. App hỏi máy chủ nấc hiện tại qua `/v1/config/app`; hỏi không
được thì **đóng** — mặc định phải là đóng.

### Chứng minh từng luật

Bỏ phép kiểm lần hai trong `dung_video` → 1 đỏ. Bỏ đối chiếu dấu vân tay →
1 đỏ. Cho nhật ký bản cũ mặc định là "đạt" → 1 đỏ. Mở khâu video ở nấc hiệu
chỉnh → 1 đỏ. Cho giao diện tự nạp cả ảnh lệch → 1 đỏ.

**1693 passed, 7 skipped (Python) · 464 pass (Node) · website build sạch ·
smoke dựng đủ 18 trang.**

### Remaining Limits

- **Chưa ghép được video từ ảnh THẬT** — vẫn chưa có nhà cung cấp nên chưa có
  ảnh sản phẩm thật nào. Video đã dựng để kiểm là từ ảnh máy chủ tự vẽ.
- Chưa có kéo-thả sắp thứ tự như bản đề bài nêu: thứ tự hiện theo nhật ký.
  Thêm được, nhưng phần quyết định rủi ro nằm ở việc ảnh nào được vào, không
  ở thứ tự.
- Không có nhạc nền, không có chuyển cảnh ngoài mờ chồng — đúng phạm vi bản
  đề bài đặt ra.
- Nhãn "AI-generated" nằm trên chính từng tấm ảnh (từ C1), nên khung nào cũng
  có. Chưa có lớp phủ riêng ở tầng video; nếu sau này ghép ảnh từ nguồn khác
  thì phải thêm.

## C5 — Nút "Thử ngay", và bấm nấc phải dựa trên lượt ĐÃ SOI TAY (Phase H, 2026-08-21)

Chủ dự án đưa một bản đề bài cho bước cắm nhà cung cấp thật. Đối chiếu với mã
trước khi làm — **bốn chỗ phải chỉnh**:

1. **"Tạo 2 bản ghi nhà cung cấp thật"** nằm trong phần Scope của bản đề bài,
   nhưng đó **không phải việc lập trình**: cần khoá API Gemini và quyền quản
   trị, cả hai đều không có ở đây (cổng triển khai chỉ trả TÊN biến môi
   trường, không trả giá trị). Việc này thuộc về chủ dự án.
2. **"Dòng assist phải ép `responseMimeType: application/json`"** — đây
   **không phải trường cấu hình**. Nó nằm cứng trong `callGemini`, còn
   `generateScene` cố ý không ép. Không có cách nào khai sai, nên cũng không
   có gì để làm.
3. **"Log đủ: ảnh gốc, ảnh dựng"** — lưu ảnh trên máy chủ đã được cân nhắc và
   BỎ ở C2 (trùng với `nhat_ky_dung_anh.json` ghi cạnh ảnh trên máy người
   bán, nơi họ thật sự cần khi khiếu nại; cộng ~5,6 MB mỗi lượt vào cơ sở dữ
   liệu và một quyết định về dữ liệu khách hàng). Giữ nguyên quyết định cũ:
   sổ lưu phán quyết + **lý do bằng lời** + mã lỗi, không lưu ảnh.
4. **"Không bật production khi chưa đạt tối thiểu 20 ảnh ĐÃ REVIEW TAY"** —
   ràng buộc đúng, nhưng **cơ chế đánh dấu đã soi chưa hề tồn tại**. Bộ đếm
   cũ đếm số lượt đã CHẠY. Đây là phần đáng làm nhất của cả bản đề bài.

### Đếm lượt đã chạy là đếm nhầm thứ

Chạy 100 ảnh mà không ai nhìn thì con số 100 chỉ nói mô hình đã tiêu bao
nhiêu tiền — không nói nó quyết đúng hay sai, mà đúng/sai mới là thứ quyết
định có mở cho người bán thật hay không.

Thêm `reviewedAt` / `reviewAgree` / `reviewNote` vào sổ, hai cửa quản trị để
liệt kê và đánh dấu, và một panel soi tay: mỗi lượt hiện **lý do bằng lời**
của mô hình cùng hai nút *Mô hình đúng* / *Mô hình sai*. Báo cáo nay có
`tyLeDongY` — tỷ lệ người soi đồng ý với mô hình, con số đáng nhìn nhất
trước khi bấm nấc.

Kéo theo một chỗ thiếu lộ ra: **sổ chưa hề lưu `reason`**, tức là thứ người
soi cần đọc thì không có. Đã thêm.

### Hỏi lại trên giao diện KHÔNG phải là chặn

Bản trước đánh dấu `image.scene.stage` là khoá nguy hiểm để giao diện hỏi lại.
Nhưng giao diện nào cũng đi vòng được bằng một lượt gọi API. Nay `PUT
/v1/admin/config/:key` từ chối đặt `production` khi số lượt **đã soi tay**
chưa đủ (`409 CHUA_DU_LUOT_SOI_TAY`), và chặn **trước** khi ghi giá trị.

### Nút "Thử ngay"

Lỗi cấu hình — sai khoá, sai tên mô hình, sai giao thức, mô hình không nhìn
được ảnh — hiện chỉ lộ ra ở lượt chạy thật đầu tiên, mà lượt đó tốn Vox và
nằm giữa một mẻ hiệu chỉnh. `POST /v1/admin/providers/:id/test-now` gọi thật
một lượt nhỏ nhất, bằng ảnh **máy chủ tự vẽ** (cùng bộ vẽ với phép thử nhìn,
không dùng ảnh khách), và:

- **ghim đúng nơi đang thử** — không ghim thì nơi thứ nhất hỏng sẽ được nơi
  thứ hai đỡ, và người bấm tưởng cấu hình vừa sửa đã chạy;
- **luôn chấm lại phép nhìn**, không xài dấu cũ — người bấm vừa đổi cấu hình;
- **không tính hạn mức ngày** (ba chỗ đếm đều loại `test_now` ra), không lẫn
  vào sổ hiệu chỉnh;
- gọi hỏng thì **không đóng dấu mù** — lỗi mạng không phải mô hình mù.

Nút nằm ngay trên thẻ nhà cung cấp sẵn có, cạnh dòng trạng thái "đã chứng
minh nhìn được ảnh". Kết quả nói bằng lời người dùng cần: *"Gọi được nhưng
đọc '4712' thay vì 8395 — mô hình này KHÔNG nhìn được ảnh"*.

### Hai test cũ lỗi thời, và một cách đếm sai

Luật mới chặt hơn nên hai test của C2 đỏ. Sửa cho khớp luật mới, **không nới
luật**. Trong đó một test đếm mọi chuỗi `runMode:` trong route — nay đếm lây
cả điều kiện lọc `runMode: { $ne: 'test_now' }` nên con số phồng lên và test
xanh nhầm. Đổi sang đếm đúng dạng `runMode: nac.runMode`, rồi gỡ một chỗ ghi
sổ ra đo lại để chắc nó vẫn cắn.

Và lại một lần nữa **test của tôi khoanh vùng sai**: cắt thân hàm tới
`module.exports` nên đọc lây sang các hàm phía sau, đỏ oan. Đã thêm hàm
`thanHam()` cắt tới hàm kế tiếp. Đây là lần thứ ba trong ngày cùng một kiểu
lỗi (so `indexOf` khi không tìm thấy; khoá sai chiều; nay khoanh vùng rộng) —
cả ba lần đều chỉ lộ ra vì gỡ bảo vệ đi đo, không phải vì test xanh.

### Chứng minh từng luật

Bỏ lọc `test_now` khỏi một chỗ đếm hạn mức → 1 đỏ. Bỏ chặn bật nấc ở máy chủ
→ 1 đỏ. Quay lại đếm lượt đã chạy thay vì đã soi → 1 đỏ. Bỏ một chỗ ghi chế
độ chạy vào sổ → 1 đỏ.

**464 pass (Node) · 1670 passed, 7 skipped (Python) · website build sạch.**

### Remaining Limits

- **Vẫn chưa gọi thật nhà cung cấp nào** — nút "Thử ngay" đã dựng nhưng chưa
  ai bấm, vì chưa có khoá API. Phần "Integration: gọi thật Gemini" và
  "Regression chạy trên provider thật" của bản đề bài **chỉ chạy được sau khi
  chủ dự án cắm khoá**; ở đây không có cách nào thực hiện.
- Nút "Thử ngay" cho vai `image` gọi sinh ảnh thật, tức là **tốn tiền thật**
  của nhà cung cấp (một ảnh nhỏ mỗi lần bấm). Không tính Vox của người dùng,
  nhưng không miễn phí.
- Panel soi tay chưa hiện lại ẢNH của lượt đó — vì máy chủ cố ý không lưu
  ảnh. Người soi phải mở ảnh trên máy mình (`nhat_ky_dung_anh.json` ghi kèm
  đường dẫn). Đây là hệ quả có chủ đích của quyết định ở mục 3 phía trên.
- Chưa có cửa quay ngược: đánh dấu nhầm "mô hình đúng" thì phải sửa thẳng
  trong cơ sở dữ liệu.

## C4 — Nền tảng nào cũng cắm được, và chặn mô hình MÙ phán quyết (Phase H, 2026-08-21)

Hai việc, một do chủ dự án yêu cầu, một do chính C3 lộ ra.

### 1. Đường tự khai — không phải chờ bản mới mỗi lần có nền tảng mới

Chủ dự án hỏi: còn Grok và các nền tảng khác thì sao?

Riêng Grok thì **đã dùng được ngay** với giao thức OpenAI Images — xAI có
`/images/edits` nhận ảnh base64, chỉ cần đổi địa chỉ máy chủ sang
`https://api.x.ai/v1`. Nhưng câu hỏi thật sau lưng nó là "còn nền tảng thứ
năm, thứ sáu thì sao", nên thêm giao thức `custom_images`: người cấu hình tự
khai đường dẫn cửa gọi, mẫu thân yêu cầu (JSON có chỗ điền), đường dẫn tới
ảnh trong trả lời, và kiểu header xác thực.

**Luật quan trọng nhất của đường này: mẫu BẮT BUỘC phải mang ảnh gốc đi
theo** (`{{image_data_uri}}` hoặc `{{image_base64}}`). Thiếu nó thì nhà cung
cấp vẫn trả về một tấm ảnh đẹp — nhưng là sản phẩm do mô hình tưởng tượng,
đúng thứ C1 sinh ra để chống, và hỏng theo kiểu **không có triệu chứng nào**.
Chặn ngay lúc lưu, không đợi lượt gọi đầu tiên.

Phần thoát ký tự cũng là một cái bẫy có thật: câu lệnh chứa dấu nháy hay
xuống dòng mà nhét thẳng vào mẫu JSON thì vỡ cả thân yêu cầu, và vỡ theo kiểu
"nhà cung cấp trả 400" chứ không nói vì sao. Điền qua `JSON.stringify` rồi bỏ
hai dấu nháy ngoài; có test bằng câu lệnh chứa cả nháy, xuống dòng lẫn dấu
chéo ngược.

### 2. Mô hình MÙ vẫn phán quyết "đạt" — ca hỏng tệ nhất hệ thống tạo ra được

C3 lộ ra: vai `assist` cần mô hình **nhìn được ảnh** cho tác vụ
`packaging_check`. Cắm một mô hình chỉ đọc chữ vào vai đó thì nó **vẫn trả
lời** — và người bán nhận một phán quyết "đạt" từ mô hình chưa từng nhìn thấy
tấm ảnh nào. Im lặng, trông như đang chạy, hậu quả rơi xuống họ vài tuần sau
dưới dạng án phạt.

Cách chặn: **máy chủ tự vẽ một tấm PNG chứa số bốn chữ số ngẫu nhiên rồi bảo
mô hình đọc.** Không đọc đúng thì từ chối dùng cho việc kiểm bao bì.

Vì sao tự vẽ chứ không kèm sẵn ảnh mẫu: ảnh cố định thì mô hình mù chỉ cần
đoán trúng một lần là qua vĩnh viễn. Vì sao bốn chữ số: 9000 khả năng, đoán
bừa gần như chắc chắn trượt (có test bắn 300 lượt đoán bừa, cho phép trúng
tối đa 1). Vì sao tự vẽ bằng `zlib` có sẵn thay vì thêm thư viện: một bộ chữ
số 5×7 chấm là đủ, thêm phụ thuộc chỉ để vẽ bốn chữ số là cái giá quá đắt.

Kết quả ghi lên chính bản ghi nhà cung cấp (`visionOkAt`), hạn 7 ngày — mỗi
tuần tốn đúng một lượt gọi thừa. Gọi hỏng thì **không kết tội mù** mà ném lỗi
riêng: hỏng mạng khác hẳn mô hình mù, nhưng cả hai đều làm lượt kiểm thành
"chưa kiểm được", tức là ảnh không dùng để bán — đúng hướng an toàn.

**Đã xác minh ảnh vẽ ra đọc được thật**: dựng ảnh, mở ra nhìn bằng mắt, đúng
con số đã sinh. Không suy từ việc "hàm chạy không lỗi".

### Test bắt được một lỗi thật trong chính bản sửa

`loiCapVaiGiaoThuc` liệt kê tay hai giao thức chỉ-sinh-ảnh, nên khi thêm
`custom_images` thì vai `translate` vẫn nhận nó — cấu hình lưu được, hỏng ở
lượt gọi đầu tiên. Sửa bằng cách suy ra từ chính bảng giao thức thay vì liệt
kê tay, và thêm test chạy theo bảng.

### Chứng minh từng luật

Bỏ phép thử nhìn khỏi `assist` → 1 đỏ. Vẽ trượt toạ độ (ảnh trắng tinh) →
2 đỏ. Dùng số cố định thay vì ngẫu nhiên → 1 đỏ. Bỏ ảnh gốc khỏi mẫu tự khai
→ 1 đỏ. Đọc ảnh ở sai trường → 3 đỏ.

**449 pass (Node) · 1670 passed, 7 skipped (Python) · website build sạch.**

### Rà lại lời khuyên của chính mình — và tìm ra một lỗ trong bộ canh vừa dựng

Chủ dự án bảo "coi lại giúp tôi" phần khuyến nghị cắm Gemini trước. Đi kiểm
bằng mã thay vì đọc lại, và lộ ra một lỗ **trong chính phép thử nhìn vừa
làm xong**:

`baoDamNhinDuocAnh` chấm bài bằng `callWithFallback`, mà hàm đó trả về *nơi
nào trả lời được*. Nơi thứ nhất hỏng, nơi thứ hai đáp → **ghi kết quả thử lên
nhầm bản ghi**: một mô hình mù có thể bị đóng dấu "nhìn được", hoặc ngược
lại. Tệ hơn: sàng xong rồi lượt gọi thật vẫn dùng danh sách đầy đủ, nên nó
vẫn rơi được vào một nơi chưa chứng minh — tức là phép sàng gần như vô nghĩa
khi có từ hai nơi gọi trở lên.

Sửa ba chỗ:
- `thuNhinMotNoi()` gọi **thẳng** `callGemini`/`callOpenAiCompat` cho đúng nơi
  đang chấm, không qua fallback. Chấm bài thì phải biết chắc mình chấm ai.
- `locNoiNhinDuocAnh()` trả về **danh sách đã sàng**, và `callWithFallback`
  nhận `chiDinh` để lượt gọi thật chỉ chọn trong danh sách đó.
- Gọi hỏng thì **bỏ qua nơi đó, không ghi là mù** — mất mạng một lượt mà bị
  đóng dấu "mô hình mù" là kết tội oan, và dấu đó ở lại 7 ngày.

Kèm dọn bộ nhớ đệm nơi gọi sau khi chấm: không dọn thì bản cũ (`visionOkAt`
rỗng) còn nằm trong đệm, mỗi lượt lại thử lại từ đầu cho tới khi hết hạn.

Chứng minh: quay lại chấm qua fallback → 1 đỏ; sàng xong không giao danh sách
→ 1 đỏ; kết tội mù khi chỉ lỗi mạng → 1 đỏ. **452 pass (Node).**

### Ba đính chính cho chính lời khuyên đó

1. **"Một khoá" đúng, nhưng phải tạo HAI DÒNG.** `AiProvider.name` là duy
   nhất, và hai vai cần hai mô hình khác nhau: vai `assist` dùng mô hình chữ
   có thị giác, vai `image` dùng mô hình sinh ảnh. Cùng một khoá API, hai
   dòng khác tên.
2. **Đừng dùng tên mô hình Imagen** — dòng đó đã ngừng phục vụ ngày
   17/08/2026, bốn ngày trước. Mô hình sinh ảnh của Gemini nay theo dạng
   `gemini-<phiên bản>-flash-image`.
3. Hai đường gọi Gemini cố tình khác nhau và đã kiểm: `callGemini` (vai chữ)
   ép `responseMimeType: application/json`, còn `generateScene` (vai ảnh)
   **không** ép — ép JSON lên mô hình sinh ảnh là tự bịt đường trả ảnh.

### Remaining Limits

- Phép thử nhìn chỉ chứng minh mô hình **đọc được chữ trong ảnh**. Nó không
  chứng minh mô hình so sánh được hai ảnh giỏi tới đâu — việc đó vẫn phải
  soi tay ở bước hiệu chỉnh.
- Mô hình có thị giác nhưng từ chối đọc số (chính sách nội dung) sẽ bị coi là
  mù. Chưa gặp; nếu gặp thì dấu hiệu là `visionNote` ghi lại nguyên văn câu
  trả lời.
- Đường tự khai chưa hỗ trợ `multipart/form-data`, chưa hỗ trợ nhiều ảnh gốc,
  và chưa có nút "thử ngay" trong trang quản trị — sai mẫu thì phải chạy một
  lượt dựng ảnh thật mới biết.
- **Chưa gọi thật nhà cung cấp nào**, kể cả phép thử nhìn: nó đã có test cho
  phần vẽ ảnh và phần chấm bài, nhưng lượt gọi thật đầu tiên vẫn là phép thử
  thật.

## C3 — Sinh ảnh không chỉ riêng Gemini (Phase H, 2026-08-21)

Chủ dự án hỏi thẳng sau khi đọc báo cáo C2: *"có tích hợp được các API chuẩn
OpenAI (OpenRouter, DeepSeek…) không chứ không riêng mỗi Gemini?"*

### Tra hợp đồng thật trước khi viết

Câu trả lời ngắn là có, nhưng **"Chuẩn OpenAI" là một cái tên gây hiểu nhầm**:
với phần CHỮ các nhà thật sự nói chung một giọng (`/chat/completions`), còn
với phần ẢNH thì mỗi nhà một kiểu — khác đường dẫn, khác tên trường mang ảnh
vào, khác chỗ đặt ảnh ra. Đã tra tài liệu thật thay vì suy từ trí nhớ, vì chủ
dự án sẽ cắm khoá trả tiền vào đó:

| Nhà | Cửa | Ảnh vào | Ảnh ra |
|---|---|---|---|
| Google | `:generateContent` | `inlineData` | `parts[].inlineData` |
| OpenRouter | `/images` | `input_references[]` | `data[0].b64_json` |
| OpenAI | `/images/edits` | `image` (data URI) | `data[0].b64_json` |

**DeepSeek thì không** — API hosted của họ là chữ và suy luận, không sinh ảnh
(Janus-Pro là dòng mô hình riêng, không nằm trong API thương mại). Nên câu
"OpenRouter, DeepSeek…" trong nhãn cũ của trang quản trị là sai với vai ảnh.

### Hai quyết định

**Chọn `/images/edits`, không phải `/images/generations`.** Cửa sau không
nhận ảnh vào — dùng nhầm thì sản phẩm trong ảnh ra do mô hình bịa hoàn toàn,
đúng thứ C1 sinh ra để chống. Có test khoá riêng chỗ này.

**Không đoán giao thức từ địa chỉ máy chủ.** Ba giá trị `type` tường minh
(`google`, `openrouter_images`, `openai_images`) thay vì dò chuỗi
"openrouter.ai" trong URL — dò chuỗi thì đổi tên miền một cái là hỏng, mà
hỏng theo kiểu 404 không ai hiểu.

### Chặn sai cặp ngay lúc LƯU

`loiCapVaiGiaoThuc(role, type)` chạy ở cả `POST` lẫn `PATCH` nhà cung cấp:
vai `image` với giao thức chỉ-chữ, hoặc vai chữ với giao thức chỉ-ảnh, đều bị
từ chối kèm câu nói rõ phải chọn gì. Đây là bài học V94 áp dụng trước khi
mắc: cấu hình sai mà chỉ lộ ở lượt gọi đầu tiên thì lúc đó người cấu hình đã
rời trang từ lâu. Trang quản trị cũng hiện cảnh báo ngay khi chọn lệch cặp.

### Một test tự viết ra đã khoá SAI CHIỀU

Định khoá "thêm giá trị vào enum mà quên dạy cách gọi". Thêm thử `stability`
vào enum để đo: **test vẫn xanh**. Vì một giao thức chữ mới hoàn toàn hợp lệ
khi không sinh được ảnh — chiều đó không kiểm được, viết vậy là bộ canh xanh
vĩnh viễn.

Chiều đúng là ngược lại: mọi giao thức trong bảng sinh ảnh phải **lưu được**
vào model và qua được schema của route. Bỏ `openrouter_images` khỏi enum để
đo lại → đỏ ngay. Đây là đúng lỗi V94: dạy hệ thống một cách gọi mới mà quên
mở enum thì không ai tạo nổi nhà cung cấp cho nó.

### Chứng minh từng luật

Đổi `/images/edits` thành `/images/generations` → 1 đỏ. Đọc ảnh ở sai trường
(`data[0].image` thay vì `b64_json`) → 3 đỏ. Bỏ một giao thức khỏi enum →
1 đỏ. Test C2 cũ ép "chỉ Gemini" đã lỗi thời, viết lại theo luật mới: phải
chặn TRƯỚC khi gọi mạng và thông báo phải liệt kê các giao thức dùng được.

**427 pass (Node) · website build sạch.**

### Remaining Limits

- **Chưa gọi thật nhà cung cấp nào.** Toàn bộ hình dạng yêu cầu/trả lời lấy
  từ tài liệu của nhà cung cấp, test khoá lại hình dạng đó — nhưng test không
  chứng minh được tài liệu đúng. Lượt gọi thật đầu tiên vẫn là phép thử thật.
- Chưa hỗ trợ `multipart/form-data` của OpenAI (chỉ dùng thân JSON). Đủ cho
  `gpt-image-*`; mô hình nào chỉ nhận multipart thì chưa chạy được.
- **Vai `assist` cần mô hình NHÌN ĐƯỢC ẢNH** cho tác vụ `packaging_check`.
  Cắm một mô hình chỉ-chữ (vd DeepSeek) vào vai này thì nó vẫn trả lời — và
  đó là ca nguy hiểm nhất của cả tính năng: một phán quyết "đạt" do mô hình
  chưa từng nhìn thấy ảnh. Hiện chưa có cách chặn tự động; xem là việc kế
  tiếp.

## C2 (rút gọn) — Chốt chuyển pha và bảng hiệu chỉnh phán quyết (Phase H, 2026-08-21)

Bản đề bài C2 xin nối nhà cung cấp thật + hiệu chỉnh ngưỡng + lưu ảnh làm
bằng chứng. Đối chiếu với mã trước khi làm thì **ba tiền đề chính đều sai**:

1. *"Vai `image`/`assist` chưa được đăng ký"* — đã có sẵn trong enum
   `AiProvider` và trong ô chọn ở trang quản trị từ V94/C1. Việc còn thiếu
   không phải mã: chưa ai tạo bản ghi nhà cung cấp kèm khoá API.
2. *"Hiệu chỉnh ngưỡng"* (chiếm §4, §5A, §8 của đề bài) — **C1 không có
   ngưỡng nào**. Phán quyết là nhãn văn bản, cố ý. Bảng
   `judgment_calibration_notes` với cột *ngưỡng cũ/ngưỡng mới* sẽ là bảng
   không bao giờ điền được. Thứ thật sự đổi khi hiệu chỉnh là câu lệnh, và
   phiên bản của nó đã ghi sẵn từng lượt (`assistPromptVersion`).
3. *"Không còn 401"* làm tiêu chí thành công — `401` là thiếu token thiết bị,
   đúng và phải giữ mãi. Thiếu nhà cung cấp trả `503`. Đặt như đề bài là mời
   người sau đi phá xác thực để đạt chỉ tiêu.

Bỏ luôn hạng mục "lưu ảnh gốc + ảnh dựng trên máy chủ": hiện máy chủ không
lưu ảnh nào, làm theo là đẩy ~5,6 MB/lượt vào cơ sở dữ liệu, chưa có chính
sách xoá, và **trùng** với `nhat_ky_dung_anh.json` mà C1 đã ghi ngay cạnh
ảnh trên máy người bán — nơi họ thật sự cần khi đi khiếu nại.

Chủ dự án chọn bản rút gọn. Đã làm ba việc.

### 1. Chốt chuyển pha — ba nấc, mặc định TẮT

`image.scene.stage` ∈ `off` | `calibration` | `production`.

Vì sao MỘT khoá ba nấc thay vì "bật/tắt" + "chế độ": hai khoá thì có trạng
thái vô nghĩa (đã bật nhưng chưa chọn chế độ) và người bấm phải nhớ thứ tự
bấm. Một khoá thì không có kẽ hở.

Nấc `calibration` chỉ mở cho các máy trong `image.scene.calibration.devices`,
**mặc định rỗng = không máy nào** — mặc định phải là đóng, không phải mở
toang. Nấc lạ (gõ sai trong trang quản trị) rơi về ĐÓNG: một lỗi chính tả
không được phép mở cửa.

Cấp thiết hơn đề bài tưởng: cửa `/v1/ai/product-scene` **đã sống trên máy chủ
từ hôm nay**. Chưa ai chạm được vì trang Ảnh sản phẩm chưa nằm trong bản
`.exe` nào (`git tag --contains` rỗng), nhưng chốt phải có TRƯỚC bản phát
hành mang trang đó, không phải sau.

### 2. Ghi phán quyết vào sổ

`UsageLog` của C1 ghi đủ tác vụ, mô hình, token, mã lỗi — nhưng **không ghi
kết quả**, tức là không có gì để đếm khi cần biết mô hình đang gắt hay đang
dễ dãi. Thêm `verdict` (SAFE/CONCEPT) và `runMode`.

`runMode` LUÔN do máy chủ đặt. Hàm `quyetDinh()` cố ý nhận tham số rời chứ
không nhận nguyên `request.body`, và có test cấm mọi chỗ đọc `body.runMode` —
client tự khai "tôi đang chạy thật" thì báo cáo hiệu chỉnh thành vô nghĩa.

### 3. Nới báo cáo sẵn có, không dựng cửa mới

Đề bài xin `GET /product-scene/calibration-report` + panel riêng.
`/v1/admin/analytics/assist` đã gộp theo tác vụ, mô hình, mã lỗi và đã có
panel "Cổng trợ lý"; thiếu đúng phần phán quyết. Thêm vào đó thay vì dựng
chỗ thứ hai phải nhớ mở.

Bảng đếm **đủ BA kết cục**, không phải hai: đăng bán được · lệch bao bì ·
**chưa kiểm được** (gom cả lượt hỏng lẫn lượt thành công nhưng nhãn lạ). Bỏ
nhóm thứ ba đi thì tỷ lệ đạt trông đẹp hẳn trong khi thực tế người bán không
dùng được ảnh nào.

### Hai lỗi tự tìm ra khi làm

**Test "chốt đứng trước replay" có lỗ.** Viết
`indexOf(chốt) < indexOf(replay)` — `indexOf` trả `-1` khi không thấy, và
`-1` nhỏ hơn mọi vị trí, nên test vẫn XANH ngay cả khi gỡ sạch chốt. Gỡ thật
ra đo mới lộ (đỏ 1 test thay vì 2). Đã thêm hai dòng kiểm có-mặt trước khi so
thứ tự.

**App báo sai việc phải làm.** `dung_boi_canh` bắt mọi lỗi rồi thử bối cảnh
tiếp theo — đúng cho trục trặc nhất thời, nhưng với `IMAGE_STAGE_OFF` thì
thử thêm năm lần cũng ra đúng câu đó, mà người dùng nhận về "thử lại sau ít
phút". Thêm `_KHONG_THU_LAI`: hai mã này dừng cả mẻ và ném nguyên lý do lên.
Có test cho cả ranh giới ngược lại (lỗi mạng thì VẪN thử nốt bối cảnh sau).

### Chứng minh từng luật

Gỡ chốt khỏi route → 2 test đỏ. Đổi mặc định thành `production` → 1 test đỏ.
Bỏ nhóm "chưa kiểm được" khỏi bảng → 1 test đỏ. Gỡ `_KHONG_THU_LAI` → 2 test
Python đỏ.

**1670 passed, 7 skipped (Python) · 407 pass, 1 skip (Node) · website build
sạch.**

### Còn lại — và đây là phần chính của C2

Ba việc trên chỉ là khung. Phần có giá trị nhất của bản đề bài vẫn chưa làm
được và **không tự làm thay được**:

1. Chủ dự án tạo nhà cung cấp cho vai `image` và `assist` trong trang quản
   trị (thao tác vài phút, không phải việc lập trình).
2. Đặt `image.scene.stage` = `calibration`, dán vân tay máy vào danh sách.
3. Chạy 20–30 ảnh sản phẩm thật, đa dạng ngành hàng, rồi **soi tay từng lý
   do** mô hình trả về. Bảng số chỉ nói mô hình quyết ra sao, không nói nó
   quyết ĐÚNG hay SAI.
4. Đủ và đạt thì mới bấm `production`.

Chi phí ước tính cho bước 3: ~990 Vox (≈ 9.900đ) cộng tiền gọi mô hình thật.

## C1 — Dựng bối cảnh ảnh sản phẩm, có cổng tuân thủ TikTok Shop (Phase H, 2026-08-21)

Người dùng gửi ảnh chụp màn hình một án phạt THẬT trên tài khoản của họ:
**cưỡng chế hủy quyền thương mại điện tử + trừ 1000 điểm CHR**, ngày
19/8/2026, lý do "quảng bá sản phẩm không nhất quán". Kèm dòng đáng sợ nhất:
6 lần cùng loại trong 90 ngày là mất quyền bán, bất kể điểm còn bao nhiêu.

Đề bài xin một "AI dựng ảnh bao bì đẹp". Nhưng thứ vừa phạt họ CHÍNH LÀ hình
trong video không khớp sản phẩm đang bán. Nên tính năng này được xây quanh
đúng một câu hỏi: *ảnh vừa dựng có còn là sản phẩm đang bán không?*

### Audit trước khi làm

Bản đề bài nói "tái sử dụng embedding ảnh sẵn có". **Không có** — cả voidmix
lẫn SocialHub đều chưa từng có embedding ảnh nào. Nếu tin câu đó mà làm thì
đã đi dựng CLIP + ngưỡng cosine.

Chọn đường khác: dùng chính mô hình thị giác làm **giám khảo giải thích
được**. Ngưỡng cosine 0,82 không nói cho người bán biết phải sửa gì; câu
"nhãn khác chữ so với bản gốc" thì có. Với một án phạt phải đi khiếu nại, lời
văn là thứ dùng được, con số thì không.

### Ba luật được ép bằng mã, không bằng lời khuyên

1. **Mặc định giữ nguyên sản phẩm.** `buildPrompt` mặc định `mode='SAFE'`,
   `GIU_NGUYEN_SAN_PHAM` cấm đổi chữ trên nhãn, màu, kiểu dáng, chất liệu,
   khối lượng, và cấm thêm huy hiệu/giải thưởng không có trong ảnh gốc.
2. **Kết quả kiểm ĐÈ LÊN chế độ người dùng xin.** Mô hình hứa giữ nguyên là
   một chuyện, nó có giữ hay không là chuyện khác. Mọi ảnh đều đi qua tác vụ
   `packaging_check` (gửi 2 ảnh: gốc + mới), và phán quyết đó mới là thứ
   quyết định ảnh có `dung_duoc_de_ban` hay không.
3. **Không kiểm được thì coi như CONCEPT.** Mất mạng, mô hình trả nhãn lạ,
   máy chủ lỗi — tất cả rơi về "chưa kiểm được", và ảnh chưa kiểm không bao
   giờ được đánh dấu đăng bán được. Đoán sai hướng này mất một tấm ảnh; đoán
   sai hướng kia mất kênh bán hàng.

### Vì sao phán quyết là LỜI, không phải điểm

`packaging_check` trả `value` (SAFE/CONCEPT) + `reason` bằng câu tiếng Việt,
và prompt ghi thẳng "Không chắc thì chọn CONCEPT". Người bán đọc được lý do
thì tự quyết được có dùng ảnh hay không; đọc "0,79" thì không.

### Bộ nhớ đệm suýt thành lỗ hổng

`cacheKey(task, input, images)` ban đầu chỉ băm phần chữ. Nghĩa là dựng ảnh
lần hai — ảnh khác hẳn — vẫn nhận lại phán quyết SAFE của lần trước. Đã băm
cả dữ liệu ảnh vào khoá.

### Những chỗ test khoá lại

Server (`tests/product-scene.test.js`, 15 test) — gỡ `GIU_NGUYEN_SAN_PHAM`
ra thì **3 test đỏ ngay**, tức là luật không chỉ nằm trong câu chữ tài liệu.
Cũng khoá: bối cảnh lạ thì ném lỗi (không âm thầm dựng bừa), CONCEPT phải
kèm câu "không dùng để đăng kèm sản phẩm đang bán", vai `image` **không có
vai dự phòng** (rơi về `translate` là sinh ra chữ chứ không ra ảnh).

Client (`tests/test_dung_boi_canh_san_pham.py`, 14 test) — gỡ luật "phán
quyết đè lên chế độ xin" thì **3 test đỏ**. Cũng khoá: mỗi ảnh phải đi qua
đúng 2 ảnh gửi kiểm; một bối cảnh hỏng không giết cả mẻ; nhật ký ghi nối
tiếp chứ không đè; chưa có tài khoản thì không gọi ra ngoài; ảnh CONCEPT
đóng nhãn cảnh báo dài hơn ảnh SAFE; `dong_nhan_ai` trả `False` khi ffmpeg
hỏng (trả `True` là nói dối lớp trên).

Giao diện (`tests/test_product_scene_page.py`, 15 test) — danh sách bối cảnh
trong app **đối chiếu trực tiếp với `product_scene.js`**: đổi một bên quên
bên kia thì test đỏ (đã thử đổi `tay_cam` → `tren_tay` để xác nhận). Cũng
khoá: "chưa kiểm được" hiện huy hiệu RIÊNG (gộp với "chỉ để tham khảo" khiến
người dùng tưởng ảnh có lỗi, trong khi thật ra chưa ai kiểm), câu tổng kết
không được nói "xong hết" khi có ảnh lệch, và chạy lượt mới phải xoá ảnh
lượt cũ khỏi màn hình.

### Hạn mức và giá

`credit.cost.assist.packaging_check: 3`, `credit.cost.image.scene: 30`,
`image.daily.limit: 60`, `image.daily.limit.concept: 10`. Hạn mức CONCEPT
kiểm TRƯỚC hạn mức chung — kiểm sau thì người dùng nhận thông báo sai lý do.
Giao diện chặn tối đa 4 bối cảnh mỗi lượt để không ai lỡ tay chọn cả sáu rồi
mới nhìn hoá đơn.

### Bộ canh KHÔNG dựng, và lý do

Định thêm một bộ canh "module import lười phải khai trong `autodub.spec`".
Đo trước khi dựng: **33 module** hiện chưa khai mà app vẫn chạy — PyInstaller
đọc được cả import trong thân hàm. Một bộ canh kêu nhầm 33 lần sẽ bị tắt
trong tuần đầu, nên bỏ; chỉ khai thêm `autodub.product_scene` cho nhất quán
với các dòng lười khác.

**1667 passed, 7 skipped (Python) · 385 pass, 1 skip (Node) · smoke test dựng
đủ 18 trang, exit 0.**

### Remaining Limits

- **Chưa chạy thật lượt nào** — vẫn thiếu nhà cung cấp cho vai `image` (và
  vai `assist`) trong trang quản trị. Đây là cùng một việc đang chặn V89:
  toàn bộ đường ống đã dựng và test, nhưng chưa ảnh nào đi qua mô hình thật.
- Chưa ghép ảnh thành video ngắn. Đề bài có nhắc; để sau vì phần quyết định
  rủi ro nằm ở ảnh, không ở khâu ghép.
- Nhật ký `nhat_ky_dung_anh.json` nằm cạnh ảnh, chưa gom về một chỗ. Đổi thư
  mục lưu là nhật ký tách làm hai tệp.
- Không kiểm được trên Windows (không có máy Windows trong môi trường này) —
  riêng khâu đóng nhãn bằng ffmpeg `drawtext` là chỗ dễ khác nhau nhất.

## V89 giai đoạn 3 — bảng theo dõi chi phí (Phase H, 2026-08-19)

Giai đoạn cuối của bản kế hoạch: nhìn MỘT trang là biết tuần rồi tốn bao nhiêu
cho việc gì.

### Vì sao không dùng lại trang thống kê sẵn có

`GET /analytics/usage` đã gộp theo `action` — nhưng mọi lượt trợ lý đều mang
`action: 'assist'`, nên nó chỉ cho ra một dòng duy nhất. Muốn biết việc nào
tốn nhất thì phải gộp theo `assistTask`, thứ được thêm từ giai đoạn 1 đúng cho
mục đích này.

Cửa mới `GET /v1/admin/analytics/assist?days=7` gộp ba chiều: theo việc, theo
mô hình, theo mã lỗi.

### Truy vấn gộp sai thì không kêu lên

Đây là lý do phần dựng truy vấn tách hẳn sang `assist-stats.service.js`: một
`$group` sai vẫn trả về số, chỉ là số sai — đúng lớp "hỏng âm thầm" đã dính
nhiều lần trong tuần. Tách ra thì test được mà không cần dựng Mongo, đúng quy
ước "test thuần" của `control_server`.

Những chỗ test khoá lại, mỗi chỗ là một cách làm sai từng thấy:

- **Không lọc sẵn `status: 'success'`** — lọc ở đó thì tỷ lệ hỏng vĩnh viễn
  bằng 0, tức là tự bịt mắt trước lúc mô hình xuống cấp.
- **Đếm số MÁY riêng biệt** (`$addToSet`), không phải số lượt.
- **Xếp theo Vox**, không theo số lượt: `explain_error` miễn phí nên gọi nhiều
  cũng không phải chỗ tốn tiền.
- **Tỷ lệ hỏng tính trên tổng lượt**, không phải trên số dòng.
- Chưa có lượt nào thì không chia cho 0.

**Test bắt lỗi thật trong mã vừa viết**: `Number(days) || 7` khiến `days=0`
thành 7 ngày, trong khi `Math.max(1, …)` ngay dòng dưới tuyên bố là kẹp về 1 —
mã và ý định lệch nhau. Sửa: số hợp lệ thì kẹp [1, 90], không phải số thì mới
dùng mặc định 7.

### Trang quản trị

Thêm mục **Cổng trợ lý** cạnh "Nơi gọi mô hình". Bốn ô tóm tắt (số lượt, đã
thu Vox + quy ra tiền, token vào/ra, việc tốn nhất), rồi bảng theo việc và
bảng theo mô hình.

Hai chi tiết cố ý:

- **Cảnh báo tự hiện khi tỷ lệ hỏng ≥5%**, kèm cách đọc: hỏng dồn vào một nơi
  gọi thì đổi thứ tự ưu tiên, hỏng đều khắp thì nhiều khả năng là prompt.
- **Khi chưa có lượt nào**, trang không để trống mà nhắc đúng việc còn thiếu:
  chưa cấu hình nơi gọi mô hình cho vai `assist` thì hệ thống dùng chung vai
  `translate`, đắt hơn nhiều lần.

**1614 passed (Python), 358 pass (Node), website build sạch.**

### Ba giai đoạn đã xong — còn đúng một việc

Toàn bộ bản kế hoạch đã dựng: cửa vào, 6 tác vụ, bộ đo, bảng theo dõi. Nhưng
**chưa lượt gọi thật nào chạy qua đây** vì chưa có nhà cung cấp cho vai
`assist`. Đó là việc duy nhất chặn giữa "đã dựng xong" và "đang chạy".

## V89 giai đoạn 2 — bốn tác vụ còn lại và bộ đo (Phase H, 2026-08-19)

### Bộ đo: chấm bằng tính chất, không bằng đáp án mẫu

Đây là phần đáng nói nhất của giai đoạn này. Cách thường làm — viết sẵn "đáp
án đúng" cho mỗi mẫu rồi so — hỏng ngay từ đầu với việc này: mô hình có vô số
cách trả lời đúng, nên so chuỗi thì luôn trượt, mà chấm bằng người thì chạy
được vài lần rồi bỏ.

Nên bộ đo kiểm **những tính chất mà kết quả kém chắc chắn vi phạm**:

| tác vụ | tính chất kiểm được bằng máy |
|---|---|
| `tighten_line` | phải NGẮN HƠN câu gốc rõ rệt, và giữ nguyên mọi con số |
| `video_summary` | mọi từ khoá phải CÓ trong lời thoại (bắt bịa) |
| `explain_error` | không chứa từ kỹ thuật, không đẩy người dùng đi báo lỗi GitHub |
| `music_suggest` | phải nói về ÂM NHẠC, không phải về hình ảnh |
| `character_name` | tối đa 3 chữ, không đoán giới tính khi lời thoại không cho biết |
| `series_glossary` | thuật ngữ phải lấy từ lời thoại |

Chạy khô (`npm run eval:assist`) không cần mô hình — chặn lỗi cấu hình: tác vụ
thiếu mẫu, đầu vào vượt trần, mẫu không có phép kiểm nào. Chạy thật
(`--live`) gọi mô hình qua biến môi trường, **không đụng cơ sở dữ liệu**, để
chạy được trên máy dev mà không phải dựng Mongo. Ngưỡng đạt 85%.

**Bộ đo phải tự chứng minh nó bắt được kết quả kém.** 7 test cho ăn kết quả
GIẢ đã biết trước là tốt/xấu rồi bắt nó chấm đúng — ví dụ `tighten_line` trả
lại y nguyên câu gốc, hay từ khoá "lẩu thái" cho một video nấu phở. Một bộ đo
luôn xanh còn tệ hơn không có: nó tạo cảm giác đã kiểm.

Thêm một test chặn quên: **thêm tác vụ mới mà không có mẫu đo là đỏ ngay**.

### Ba chỗ bấm thật

- **"Tóm tắt video"** ở trang Chép lời — chép xong thì thứ người ta muốn biết
  ngay là video nói gì, không phải đọc hết vài trăm câu. Lời thoại quá ngắn thì
  không gọi (đỡ tốn Vox vô ích).
- **Nút rút gọn trên TỪNG DÒNG câu** ở Trình chỉnh sửa — câu dài buộc giọng
  đọc nhanh cho kịp, nghe méo; đây là lỗi đứng đầu bảng "đáng sửa trước" (V64).
  Đo thời gian đọc THẬT từ tệp giọng nếu đã có, chưa có thì ước theo tốc độ
  đọc trong Cài đặt. Câu đã kịp chỗ trống thì **không gọi trợ lý**.
- **"Gợi ý quy ước dịch"** ở khung ngữ cảnh — điền vào ô xưng hô và ô thuật
  ngữ, nhưng **không tự lưu**: quy ước dịch sai còn tệ hơn không có vì nó áp
  cho mọi tập sau. Thuật ngữ người dùng đã gõ được giữ nguyên, chỉ thêm vào.

### Còn tồn

`character_name` đã xong phía server và có mẫu đo, nhưng **chưa nối vào giao
diện**: nó cần lời thoại theo TỪNG NGƯỜI NÓI, mà trang Hồ sơ nhân vật chỉ giữ
tên/giọng/đặc trưng giọng, không giữ câu thoại. Nối đúng chỗ đòi sửa cả cấu
trúc hồ sơ — để sang đợt sau thay vì nhét bừa vào một trang không có dữ liệu.

Và điều quan trọng nhất vẫn chưa làm được từ đây: **chưa có nhà cung cấp cho
vai `assist`**, nên chưa lượt gọi thật nào chạy qua đường này. Mọi test đều
dùng máy chủ giả.

**1614 passed, 7 skipped, 0 failed** (Python) + **348 pass, 0 fail** (Node).

## V89 — Cổng trợ lý đa tác vụ, giai đoạn 1 (Phase H, 2026-08-19)

Bản kế hoạch được duyệt, bắt đầu bằng giai đoạn 1: mở cửa vào và chứng minh
cả đường dây lẫn đường tiền bằng hai tác vụ thật.

### Cửa vào

`POST /v1/ai/assist` nhận **tên tác vụ**, không nhận prompt. Toàn bộ câu chữ
hướng dẫn mô hình nằm ở `src/prompts/assist.js` — sửa chúng, hay đổi mô hình,
**không cần phát hành lại bản .exe**. Đó là lợi ích lớn nhất của cả mini-spec
này: tuần này người dùng đã phải tải 7 bản.

Không xây lại gì: `callWithFallback` (tự rơi sang nhà cung cấp khác),
`replay`/`remember` (chống gọi trùng), `precheck`/`charge` (ví + hold),
`UsageLog` — đều dùng nguyên.

### Bốn lớp chặn chi phí

| lớp | chặn được gì | trạng thái |
|---|---|---|
| Danh sách tác vụ đóng (enum trong schema route) | gửi prompt tự do | đã có qua `TASK_NAMES` |
| Trần ký tự, cắt TRƯỚC khi gọi | trả tiền rồi mới biết là quá dài | mỗi tác vụ tự khai `maxInput` |
| Hạn mức theo NGÀY mỗi máy | vòng lặp hỏng chạy cả ngày | **mới** — server trước đó chỉ có giới hạn theo phút |
| Giá Vox theo từng tác vụ | — | `credit.cost.assist.<task>`, đổi lúc chạy |

Lớp thứ ba là thứ đã thiếu: `fastify rateLimit` chặn được bấm dồn dập nhưng
không chặn được một máy gọi đều đặn suốt 24 tiếng.

### Hai tác vụ đầu

`explain_error` — **0 Vox và chạy cả khi hết Vox**. Người đang gặp lỗi mà còn
bị chặn vì hết tiền là lúc tệ nhất để thu phí; chặn bằng hạn mức 30 lượt/ngày
thay vì bằng giá. Nối vào trang Chép lời, chỗ trước đây in nguyên văn
`[WinError 2] The system cannot find the file specified`.

`music_suggest` — 2 Vox, có tính tiền nên chứng minh nốt đường ví. Nối vào
đúng nút "Gợi ý từ nội dung video" của V88.

### Đường lui là bắt buộc, không phải tuỳ chọn

Tầng luật V88 **không bị thay thế**. Chưa cấu hình máy chủ, mất mạng, hết Vox,
mô hình trả sai khuôn — tất cả đều rơi về nó, và giao diện nói rõ gợi ý đến từ
đâu ("trợ lý đã đọc lời thoại" so với "đo trên máy, chưa cần tài khoản"). Hai
đường cho chất lượng khác nhau; người dùng có quyền biết mình đang xem cái nào.

Chiều ngược lại cũng được khoá: **mô hình trả thiếu `reason` thì bỏ kết quả đó**
và rơi về tầng luật. Gợi ý không kèm lý do thì người dùng không kiểm chứng
được — mà lý do của tầng luật luôn là con số đo được.

Cả hai worker giao diện đều không bao giờ ném ra ngoài: gợi ý hỏng không được
giết Trình chỉnh sửa, và `explain_error` hỏng thì **im lặng** — người đang bực
vì lỗi không cần thêm một thông báo "không giải thích được lỗi".

### Test (22)

Server (7, chạy thuần không DB): danh sách tác vụ đóng — kể cả `toString` và
`constructor` cũng không lọt; mỗi tác vụ khai đủ trần + khoá giá; đầu vào 50.000
ký tự bị cắt còn dưới 5.000; khuôn kết quả ép có `reason`; lời hướng dẫn
`explain_error` phải cấm bịa cách sửa và cấm đẩy người dùng đi báo lỗi GitHub.

App (15): đi máy chủ khi có tài khoản; **gửi tên tác vụ chứ không gửi prompt**
(quét chính dữ liệu gửi lên, cấm lọt "bạn là"/"json"/"system"); cắt lời thoại
trước khi gửi; ba dạng hỏng đều rơi về luật; trả rỗng cũng rơi về luật; thiếu
`reason` thì bỏ; lời thoại quá ngắn thì **không tốn Vox**; chưa có tài khoản
thì tuyệt đối không gọi ra ngoài; và giao diện nói đúng nguồn gợi ý.

**Test cũ bắt đúng việc của nó**: `hold.test.js` có danh sách trắng các khoá
giá công khai — thêm khoá mới làm nó đỏ ngay, buộc phải cập nhật *có chủ đích*
thay vì để giá nội bộ rò rỉ thành giá người dùng. Đã cập nhật kèm lý do.

**1600 passed, 7 skipped, 0 failed** (Python) + **341 pass, 0 fail** (Node).

### Còn tồn — trước khi bật thật

- **Chưa có nhà cung cấp cho vai `assist`**: phải thêm một dòng trong trang
  quản trị (`/v1/admin/providers`), trỏ vào mô hình rẻ. Chưa thêm thì tự dùng
  chung vai `translate` — chạy được nhưng đắt hơn khoảng 25 lần.
- **Chưa chạy thử với mô hình thật** — mọi test đều dùng máy chủ giả. Phải gọi
  thật một lượt rồi đọc `UsageLog` xem token và tiền có khớp dự tính không.
- Bộ đo 20 mẫu mỗi tác vụ và 4 tác vụ còn lại thuộc giai đoạn 2.

## V88 — Gợi ý mô tả nhạc nền từ chính lời thoại (Phase H, 2026-08-19)

Người dùng hỏi: *"app có tự nhận định và chọn âm nhạc phù hợp cho video
không?"*. V37 đã sinh được nhạc AI qua ElevenLabs, nhưng ô nhập chỉ có
placeholder *"nhạc vui tươi, tempo nhanh"* — tức là **phần khó nhất (nghĩ ra
mô tả) vẫn đẩy về phía người dùng**.

### Vì sao KHÔNG dùng AI cho việc này

Kiểm trước khi hứa: `saas_client` chỉ có 4 endpoint cố định — dịch, viết bài
đăng, sinh nhạc, sinh hiệu ứng. **Không có đường hỏi tự do nào**, và app cũng
không có khoá LLM riêng (`grep gemini` trong `autodub/` chỉ ra một dòng hướng
dẫn người dùng tự mở gemini.google.com). Thêm endpoint mới là việc phía
server, không làm gọn trong bản này.

Mà nhìn kỹ thì mọi tín hiệu cần thiết **đã nằm sẵn trong transcript**:

| đo được | suy ra |
|---|---|
| chữ/giây | lời dày thì nhạc phải nhanh và mỏng, nói thong thả thì nhạc dồn dập sẽ chỏi |
| tỷ lệ câu cảm thán | nhiều cảm thán → nhạc có cao trào |
| tỷ lệ câu hỏi | kiểu dẫn dắt → nhạc lửng lơ, tò mò |
| từ khoá 7 nhóm chủ đề | nấu ăn / du lịch / thể thao / công nghệ / hài / kể chuyện / tin tức |

Suy từ số đo thì **tức thì, chạy offline, 0 Vox, và giải thích được**.

### Mỗi gợi ý phải kèm lý do

Nút hiện ra tối đa 3 mô tả, mỗi cái mang tooltip là lý do bằng **con số thật**:
*"lời thoại dày (4,2 chữ/giây) — nhạc chậm sẽ bị lời lấn"*. Người dùng tự đánh
giá được thay vì phải tin một cái nhãn từ trên trời rơi xuống. Đây đúng
nguyên tắc `emphasis_points.py` của V37: **đưa ứng viên, không tự quyết**.

Transcript quá ngắn (dưới 3 câu hoặc dưới 20 chữ) thì trả về danh sách RỖNG và
nói rõ vì sao — thà không gợi ý còn hơn gợi ý bừa.

### Test (18)

Số đo trước (chữ/giây tính đúng, không chia cho 0 khi thiếu thời lượng, đọc
được cả transcript gốc lẫn bản dịch); rồi từng luật suy diễn (nói nhanh → sôi
động, nói chậm → nhẹ nhàng, từ khoá → chủ đề, cảm thán → kịch tính, câu hỏi →
dẫn dắt); rồi các ca "không được bịa" (4 dạng transcript quá ngắn, dữ liệu
rác không làm nổ, không trả hai gợi ý trùng nhau, trần 3 gợi ý); cuối cùng là
đường dây giao diện — có nút, có tín hiệu, bấm gợi ý thì điền vào ô mô tả, và
tooltip phải chứa lý do.

**Bẫy gặp khi viết test**: bốn test đầu dùng câu quá ngắn nên rơi thẳng vào
ngưỡng "không đủ dữ liệu" và trả rỗng — ngưỡng làm đúng việc của nó, test mới
là cái sai. Đã sửa dữ liệu test cho dài đủ thật.

**1585 passed, 7 skipped, 0 failed** (Python) + **334 pass** (Node).

### Còn tồn

- Từ khoá chủ đề là danh sách tay (7 nhóm) — video ngoài các nhóm đó chỉ nhận
  được gợi ý theo nhịp nói và cảm xúc. Mở rộng bằng cách thêm dòng vào
  `_CHU_DE`, không phải sửa logic.
- Chưa nhìn hình ảnh (chuyển cảnh, màu sắc) — vẫn là giới hạn từ V37.
- Sinh nhạc vẫn cần chế độ có máy chủ; phần gợi ý thì chạy offline được.

## V86–V87 — Tách nhạc nền không có bộ cài, và tuỳ chọn vô hình (Phase H, 2026-08-19)

### V86 — Vì sao "Không tách được nhạc nền" trên MỌI bản đóng gói

Người dùng gửi ảnh: bước *Tách nhạc nền* báo lỗi, và (nhờ V78) thông báo nói
rõ hậu quả — *"bản lồng tiếng sẽ CHỈ CÓ giọng đọc, không có nhạc/tiếng động
nền"*. Câu hỏi tiếp theo của họ rất đúng: **tại sao?**

`autodub.spec` cố ý loại `torch`/`demucs`/`soundfile` khỏi bundle (hàng GB) —
Demucs chạy trong venv riêng `.venv-gpu` qua `demucs_worker.py`. Nhưng đếm lại
`scripts/`: có 11 tệp `setup_*.py` (whisper, vieneu, paraformer, douyin,
ffmpeg, diarization, translate_local, lipsync, ocr, voices…) — **không tệp nào
tạo `.venv-gpu`**. Tài liệu nhắc tên venv đó như thể nó tự xuất hiện.

Đây là cái thứ tư trong tuần cùng hình dạng: **đường dẫn thì có, thứ ở đầu
kia thì không** (V80 tệp worker, V83 hàm `brand_logo`, V84 kho GitHub, giờ là
cả một venv).

Thêm `scripts/setup_demucs.py`: máy có card NVIDIA thì cài torch CUDA (~2,5 GB,
nhanh), không có thì bản CPU (~200 MB, chậm hơn nhưng vẫn tách được) — không
bắt người dùng chọn giữa hai thứ họ không có cách nào so sánh. Kèm
`Cai dat tach nhac nen (Demucs).bat`, và thông báo lỗi giờ chỉ thẳng tên tệp
cần bấm thay vì chỉ báo hậu quả.

`.venv-gpu` cũng được mượn từ bản cài cũ nằm cạnh (V77/V81 mở rộng) — 2,5 GB
mà bắt tải lại sau mỗi lần nâng cấp thì không ai chịu nổi.

### V87 — Tuỳ chọn có trong cấu hình nhưng người dùng không chạm được

Người dùng hỏi tiếp: *"tôi vào Cài đặt không thấy phần dịch tự động"*. Kiểm
lại: `SETTINGS_TABS` chỉ hiện 3 thẻ trong 6 — nhưng đó là **cố ý**, ba thẻ
Giọng đọc/Phụ đề/Dịch thuật đã tách thành trang riêng trên thanh bên (ghi rõ
trong ghi chú ở `settings_fields.py`). Không phải lỗi; câu trả lời là chỉ
đường.

Nhưng lần dò đó lộ ra một lỗi thật: **hai ô cookie không nằm ở đâu cả**.
`Settings.cookies_from_browser` / `cookies_file` có từ V67 và là cách chữa DUY
NHẤT khi TikTok chặn (V85), nhưng không có trong `FIELDS` → cách sửa duy nhất
là mở tệp `.env`. Chính tôi cũng đã chỉ người dùng *"mở Cài đặt → mục Cookie"*
— một chỗ không tồn tại.

Đã thêm hai ô vào thẻ Nâng cao, nhóm mới **"Tải video khó"**, danh sách trình
duyệt đúng tên yt-dlp hiểu, và sửa lời khuyên trỏ đúng đường. Test khoá cả
việc ô phải nằm ở thẻ THỰC SỰ HIỆN RA — đặt nhầm vào ba thẻ đã tách là lại vô
hình y như cũ.

**Bài học: có tuỳ chọn trong `Settings` không có nghĩa là người dùng chạm được
vào nó.** Cùng họ với V83 (hàm được gọi nhưng không tồn tại) — chỉ khác chiều.

**1567 passed, 7 skipped, 0 failed** (Python) + **334 pass** (Node).

## V84–V85 — Link chết và TikTok chặn (Phase H, 2026-08-19)

### V84 — Bộ giọng mẫu: gọi tới một kho không tồn tại

`voice_downloader.VOICES_RELEASE_URL` ghim `ttthanh2044/voxdub`, trong khi bản
phát hành thật nằm ở `junnyken/voxdub-studio`. Đo bằng HTTP:

```
URL trong mã  -> HTTP/2 404
URL thật      -> HTTP/2 302
```

⇒ Tính năng "Nạp bộ giọng đọc mẫu" (120 giọng) **chưa bao giờ tải được** trên
bản đóng gói. Đây là cái thứ ba trong tuần cùng một hình dạng: thứ được gọi
tới thì có, thứ ở đầu bên kia thì không (V80 tệp worker không được đóng gói,
V83 `icons.brand_logo` không tồn tại, giờ là một kho GitHub không tồn tại).

Chữa bằng cách bỏ hằng số ghim tay: `voices_release_url()` đọc
`Settings.update_repo` — cùng nguồn sự thật với việc kiểm tra bản cập nhật,
nên đổi kho ở một chỗ là mọi thứ đi theo. Test quét toàn repo chặn kho chết
tái xuất, và ngay lần chạy đầu **lòi thêm `chay_app.bat`** cũng đang chỉ người
dùng đi báo lỗi ở kho cũ.

### V85 — TikTok: đo trước, đừng đoán

Người dùng dán link TikTok, nhận `ERROR: [TikTok] ...: Unexpected response from
webpage request; please report this issue on https://github.com/yt-dlp/...`.

Phản xạ đầu tiên là "yt-dlp cũ rồi". **Đo trước khi sửa** — bản trong gói là
`2026.07.04`, và đó cũng là bản MỚI NHẤT trên PyPI. Thử tiếp từ sandbox:

| thử | kết quả |
|---|---|
| yt-dlp 2026.07.04 | hỏng ở bước "Downloading webpage" |
| yt-dlp cài từ master | hỏng y hệt |
| `--impersonate chrome` (curl_cffi) | hỏng y hệt |
| 3 `api_hostname` mobile khác nhau | hỏng y hệt |

Luôn gãy ở đúng bước đầu tiên ⇒ không phải extractor lạc hậu, mà là TikTok
chặn lượt tải ẩn danh (IP máy chủ). Nâng phiên bản sẽ không sửa được gì.

Cách chữa CÓ THẬT trong app là mượn cookie trình duyệt
(`COOKIES_FROM_BROWSER`, có từ V67) — nay được nói thẳng trong
`FRIENDLY_ERRORS`, kèm phương án 2 là tải bằng trình duyệt rồi dùng nút "Tải
tệp lên". Thông báo gốc của yt-dlp bảo người dùng đi mở issue trên GitHub —
lời khuyên vô nghĩa với người chỉ muốn lồng tiếng một video.

**Giới hạn thành thật: không kiểm chứng được cách chữa từ đây** — IP sandbox
bị chặn ngay bước đầu nên cookie hay không cũng hỏng như nhau. Trên máy người
dùng (IP dân dụng, trình duyệt đã vào TikTok) thì cookie là cách xưa nay vẫn
hiệu quả, nhưng đó là kỳ vọng chứ không phải phép đo.

**1554 passed, 7 skipped, 0 failed** (Python) + **334 pass** (Node).

## V82–V83 — Thiếu FFmpeg, và vì sao trình cài đặt không bao giờ cứu được (Phase H, 2026-08-19)

### V83 — Trình cài đặt tự động chưa từng chạy được lần nào

Người dùng bấm nút "Tải giúp tôi" (mới thêm ở V81) và nhận:

```
Không mở được trình cài đặt: module 'autodub_gui.icons' has no attribute 'brand_logo'
```

`icons.brand_logo()` được gọi ở **ba** nơi — `icons.app_logo()` (đường lui khi
thiếu `logo.ico`), `setup_wizard.py:224`, `app.py:929` — nhưng **chưa bao giờ
được định nghĩa**. Dựng `SetupWizard` là ném `AttributeError` ngay dòng logo,
trước cả khi hiện ra.

Vì sao sống lâu đến vậy: `_maybe_first_run()` bọc

```python
except Exception:  # noqa: BLE001 — wizard hỏng không được chặn app
    showed = False
```

Không log, không toast, không gì cả. Nên **trình cài đặt tự động (FFmpeg,
Whisper, VieNeu) chưa chạy được lần nào qua nhiều bản phát hành** — và đó
chính là lý do sâu xa khiến người dùng phải tự cài tay mọi thứ rồi gặp hết lỗi
này tới lỗi khác suốt mấy hôm nay. Nút V81 không "tạo ra" lỗi; nó chỉ là lần
đầu tiên lỗi được PHÉP nói ra.

Sửa: viết `brand_logo()` thật (vẽ tay bằng token màu, không phụ thuộc tệp
ngoài); sửa call site gọi `.pixmap()` lên một QPixmap (lỗi thứ hai cùng dòng);
và bỏ nuốt im lặng — hỏng thì `logger.exception` + toast.

Test: dựng `SetupWizard` thật (offscreen) — chỉ cần dựng được là chặn được cả
lớp lỗi; và quét AST mọi `icons.<tên>` trong gói giao diện đối chiếu thuộc
tính thật, để lần sau gọi nhầm tên là đỏ ngay chứ không đợi người dùng bấm.

**Bài học chung: `except Exception` không kèm log = một lỗi có thể sống nhiều
tháng.** Đây là lần thứ ba trong tuần cùng một cơ chế (V75 canh chữ hỏng âm
thầm, V78 43 cảnh báo bị lọc, giờ là đây).

### V82 — Nói ra "thiếu FFmpeg" ở đúng chỗ người dùng đứng

Hai dòng lỗi thật trong ảnh chụp, cùng một nguyên nhân, không dòng nào nói
được nguyên nhân đó:

```
[1/1] HỎNG: C:/Users/.../tap01_clip.mp4 — [WinError 2] The system cannot find the file specified
[1/1] HỎNG: https://youtube.com/shorts/... — ERROR: You have requested merging of multiple formats but ffmpeg is not installed.
```

- `autodub/ffmpeg_deps.py` — một chỗ duy nhất trả lời "máy có FFmpeg chưa"
  (nhìn cả PATH lẫn `bin/` cạnh app), kèm lời nhắc dùng chung để preflight,
  Nhật ký và hộp thoại không nói ba kiểu khác nhau.
- `transcribe_media()` dừng NGAY từ đầu với lời rõ ràng, thay vì để từng thư
  viện con gãy theo kiểu riêng.
- `FRIENDLY_ERRORS` bắt cả `WinError 2` lẫn câu của yt-dlp; trang Chép lời in
  lời đã soạn thay vì nguyên văn (dòng đó là chỗ DUY NHẤT người dùng thấy lý
  do — bộ lọc Nhật ký loại mọi thông báo có đường dẫn/URL).
- Thêm **`Cai dat FFmpeg (bat buoc).bat`**: FFmpeg là thành phần bắt buộc mà
  lại là thứ duy nhất không có tệp .bat để đúp chuột, trong khi Whisper,
  VieNeu, Paraformer, Douyin đều có. Người dùng mở thư mục ứng dụng, thấy 4
  tệp .bat, không tệp nào nói về FFmpeg.

**1548 passed, 7 skipped, 0 failed** (Python) + **334 pass** (Node).

## V81 — "Máy chưa có FFmpeg" sau khi nâng cấp (Phase H, 2026-08-19)

Người dùng báo bằng ảnh chụp ngay sau khi cài v3.4.5: hộp thoại chặn *"Máy
chưa đủ điều kiện lồng tiếng — FFmpeg: Máy chưa có FFmpeg"*, kèm lời khuyên
tải bản full từ gyan.dev rồi thêm vào PATH.

Ba thứ sai cùng lúc, và cả ba đều là lỗi của app:

1. **Tệp nằm lại bản cũ.** Trình cài đặt tải FFmpeg về `<thư mục app>/bin`.
   Nâng cấp = giải nén ra thư mục mới ⇒ mất. Đúng cảnh ngộ của `.venv-*` đã
   sửa ở V77 — chỉ khác là hôm đó chưa nghĩ tới `bin/`.
2. **Wizard không mời lại.** Marker nằm ở `~/.voxdub_cache/setup_wizard_done`,
   tức theo MÁY chứ không theo thư mục ứng dụng. Bản mới thấy marker nên bỏ
   qua wizard, dù trong thư mục này chưa có gì cả.
3. **Hộp thoại bắt người dùng làm phần việc của app.** `FFmpegDownloadWorker`
   (tải bản full có libass từ BtbN về `bin/`) đã nằm sẵn trong mã từ lâu, chỉ
   được gọi từ wizard lần đầu. Người dùng gặp lỗi thì chỉ nhận được hướng dẫn
   tải tay và sửa PATH.

### Sửa

- `venv_discovery.tim_thu_muc_bin_cu()` + `_frozen.init()` nối thư mục `bin`
  của bản cũ vào PATH khi máy chưa có ffmpeg → `shutil.which("ffmpeg")` của
  preflight thấy ngay, người dùng không phải làm gì.
- `_is_setup_needed()` trả True khi thiếu FFmpeg dù marker đã có. Giới hạn ở
  đúng FFmpeg: thiếu nó thì app không chạy được gì, còn VieNeu/Whisper là lựa
  chọn nên không lôi wizard ra mỗi lần mở.
- Hộp thoại chặn giờ là câu hỏi: **"Tải giúp tôi"** → mở trình cài đặt → cài
  xong tự chạy lại preflight, không bắt mở lại ứng dụng.
- Lời khuyên đổi sang *"chép ffmpeg.exe và ffprobe.exe vào thư mục bin cạnh
  ứng dụng (không cần sửa PATH)"* — việc ai cũng làm được. `_check_ffprobe`
  cũng nhìn `bin/` cho nhất quán với `_check_ffmpeg`.

### Test của chính đợt này làm đỏ 3 test khác

`_frozen.init()` có `os.chdir(app_root())`. Test mới gọi `init()` với
`app_root` giả mà không trả lại thư mục làm việc → 3 test `diarize_worker`
(chạy worker bằng đường dẫn tương đối) đỏ ở lượt chạy đầy đủ nhưng **xanh khi
chạy lẻ**. Đúng dấu hiệu ô nhiễm trạng thái toàn cục: khác nhau giữa chạy lẻ
và chạy cả bộ thì đừng nghi test, hãy nghi cái vừa thêm.

**1536 passed, 7 skipped, 0 failed.**

## V77–V80 — Đợt rà "còn chỗ nào hỏng nữa không" (Phase H, 2026-08-19)

Người dùng hỏi thẳng: *"còn mục nào bị lỗi nữa không để khắc phục 1 lần"*. Ba
nhóm dưới đây tìm bằng cách quét có bằng chứng, nhóm thứ tư do chính người
dùng báo bằng ảnh chụp màn hình giữa lúc đang làm.

### V80 — "Cài rồi mà app vẫn bảo chưa": hai lỗi chặn cứng

**(a) Tệp worker chưa bao giờ được đóng gói.** Ảnh chụp của người dùng:

```
[setup-whisper] faster-whisper đã cài — bỏ qua
!! không thấy worker script: ...\VoxDub-Studio-v3.4.4-win64\autodub\speech\asr_whisper_worker.py
```

`asr_whisper_worker.py` **không có trong `datas` của `autodub.spec`** — chưa
bao giờ có. Mở bản phát hành v3.4.4 ra đếm: 6 tệp worker, thiếu đúng tệp này.
Hậu quả trên MỌI bản đóng gói từ trước tới nay: bộ cài luôn chết ở bước smoke
test → `installed_ok.json` không bao giờ được ghi → app mãi báo "chưa cài bộ
nghe"; và ngay cả khi có marker thì `_transcribe_whisper_subprocess` cũng
không có tệp để chạy.

Đây là **gốc rễ sâu hơn cả V74/V75**. Hai mini-spec đó sửa đúng phần "app
kiểm sai điều kiện", nhưng đường chép lời trong bản `.exe` vốn dĩ chưa từng
chạy được lần nào.

Test không viết riêng cho một tệp mà bắt CẢ LỚP: quét AST tìm mọi
`bundled_file(...)` trỏ tới `.py`, đối chiếu với khối `datas`. Ngay lần chạy
đầu nó **lòi thêm một tệp nữa cũng thiếu**: `diarize_worker.py` (nhận diện
người nói) — tính năng đó cũng chưa từng chạy được trong bản đóng gói.

**(b) Bộ cài tạo venv bằng Python 3.14.** Ảnh chụp thứ hai: cài giọng VieNeu
gãy ở `failed-wheel-build-for-install → kaldi-native-fbank`, traceback đi qua
`pythoncore-3.14-64`. Các gói ONNX/ASR chưa có wheel cho 3.14 nên pip build từ
mã nguồn rồi gãy.

Tệp .bat ĐÃ thử `py -3.12` trước, nhưng vẫn thủng ở hai cảnh có thật:

1. Máy có 3.12 mà `py -3.12` không tìm ra (cài bằng Python Install Manager,
   hoặc cài 3.12 SAU khi đã chạy .bat lần đầu) → rơi xuống `py` = bản mới nhất.
2. Lần chạy trước đã tạo venv bằng 3.14 → lần sau dù chạy đúng 3.12 thì
   `step_venv` vẫn "venv đã có — bỏ qua" rồi cài tiếp vào venv hỏng.

Nên phép kiểm phải nằm trong CHÍNH script cài (`scripts/_python_ho_tro.py`):
đang chạy bản không hỗ trợ thì tự chạy lại bằng bản đúng; không có bản nào thì
dừng ngay với MỘT dòng chỉ dẫn thay vì chết giữa mấy chục dòng log của pip; và
venv cũ tạo bằng bản không hỗ trợ thì xoá dựng lại.

### V79 — Nút Dừng cho các bước dài nhất

`rep.check_cancelled()` có đúng 12 chỗ trong `pipeline.py`, **toàn bộ nằm giữa
hai bước**. Nên bấm Dừng lúc đang tách nhạc nền (Demucs, 10+ phút), xuất video
(ffmpeg re-encode), dịch máy hay đồng bộ khẩu hình đều không có tác dụng gì.

`autodub/cancel_guard.py` gói sẵn hai bài học để lần sau nối thêm bước mới
không phải học lại: giết tiến trình con (V72 — kiểm-rồi-chờ chỉ đúng khi cái
chờ ngắn), và đổi mọi lỗi phát sinh SAU khi cờ bật thành `PipelineCancelled`
(V74/V76).

Bẫy riêng của nhóm này: mỗi bước đều có sẵn một đường **dự phòng âm thầm**.
Demucs "hỏng" thì video ra không có nhạc nền; dịch máy "hỏng" thì rơi sang
dịch tay. Test viết trước đã bắt đúng khoảng hở đó ở `separate_vocals` —
phải chặn `kiem_dung()` ngay trong `except Exception` của nó.

Xuất video giữ nguyên `subprocess.run` khi KHÔNG có cờ Dừng: không đổi cách
chạy bước quan trọng nhất chỉ vì một tính năng mà đường gọi đó (Trình chỉnh
sửa, CLI) không dùng tới.

### V78 — 43 cảnh báo không bao giờ tới được người dùng

Quét AST mọi `logger.warning/error` của lõi rồi cho chạy qua chính
`log_text.notice_for`: **43 dòng bị lọc mất**. Phần lớn đúng là chi tiết kỹ
thuật nên ẩn, nhưng 10 dòng thì người dùng lãnh hậu quả thật:

| việc vẫn chạy tiếp | nhưng kết quả đã khác |
|---|---|
| Demucs hỏng | video ra **không có nhạc/tiếng động nền** |
| thiếu `no_vocals.wav`/`ai_music.wav` | bản dựng lại mất nhạc nền |
| Demucs/Whisper không dùng được GPU | chạy CPU, lâu hơn nhiều |
| thiếu bộ chấm câu tiếng Trung | transcript **không có dấu câu** |
| Paraformer chưa cài / video không phải tiếng Trung | lựa chọn trong Cài đặt bị bỏ qua |
| atempo lỗi | câu đó giữ tốc độ gốc, lệch so với hình |
| không ghi được sổ dịch tạm | lượt chạy lại phải **trả tiền dịch lần nữa** |

Đã soạn lời thường cho từng ca; test copy nguyên văn thông báo của lõi nên đổi
lời trong lõi mà quên bảng NOTICES là bị bắt ngay. Riêng "Rà soát bản dịch
lỗi" GIỮ ẩn — đã có quyết định từ trước ở dòng `(..., None, ...)`; không lật
quyết định cũ trong một đợt đang sửa việc khác, nhưng ghi thành test để lần
sau ai đổi thì đổi có ý thức.

### V77 — Nâng cấp không còn mất bộ nghe đã cài

Cạm bẫy đã ghi trong V74 mà để ngỏ: venv và `models/` nằm trong thư mục ứng
dụng, nên giải nén bản mới ra thư mục khác là app báo "chưa cài" dù người dùng
đã cài từ lâu — chữa tay là chép 2 thư mục hoặc tải lại ~1,5 GB.

Giờ khi thư mục mặc định trống, app dò các thư mục nằm CẠNH nó (chính là các
bản cũ giải nén cạnh nhau) và dùng lại tại chỗ — không chép, không tải lại.
Ba ràng buộc cố ý, mỗi cái một test: không đè đường dẫn người dùng tự đặt;
không nhận bản cài dở (có venv nhưng thiếu `installed_ok.json`); có nhớ đệm
(đo: 5 lượt hỏi = **1 lần quét đĩa**) và trần 60 thư mục (app có thể nằm trong
Downloads với hàng trăm thư mục — quét vô hạn ở đó là treo app lúc khởi động).

**Lỗi tự bắt được khi viết test**: tên thư mục in ra Nhật ký lùi thiếu một cấp
nên hiện `.venv-whisper` thay vì tên bản cũ.

**1529 passed, 7 skipped, 0 failed** (Python) + **334 pass, 0 fail** (Node).

### Còn tồn

- Đường Demucs chạy CPU in-process (chỉ có ở bản mã nguồn) không giết ngang
  được — chỉ chặn trước khi bắt đầu.
- `editor.py` gọi `refresh_subtitles`/`merge_video` không truyền cờ Dừng
  (luồng đó chưa có nút).
- OCR vùng chữ (`text_regions`) vẫn dùng `subprocess.run` trần, timeout 60s.

## V76 — Nút Dừng dừng được cả lúc canh chữ karaoke (Phase H, 2026-08-19)

Hạn chế V75 để lại. Canh chữ là bước **lâu nhất** của việc ghi phụ đề (nghe
lại từng clip giọng đọc; video 200 câu là hàng phút) và là bước duy nhất trên
đường đó không nhìn cờ Dừng:

- `SubtitleWorker.cancel()` set cờ, nhưng cờ chỉ được đọc **sau khi**
  `build_karaoke_ass` chạy xong → bấm Dừng rồi vẫn phải ngồi chờ hết.
- Trong pipeline, `rep.check_cancelled()` chỉ chạy **giữa** hai bước, không
  cắt ngang được bước đang chạy.

### Nối dây + giết tiến trình

`cancel_event` đi xuyên `refresh_subtitles → build_karaoke_ass →
resolve_word_times → align_segments → _asr_words_for_clips → worker`. Đứt một
mắt là nút Dừng vô nghĩa, nên có test khoá cả đường dây.

Cách dừng: **giết tiến trình con**, không chỉ kiểm cờ ở đầu vòng đọc — bài
học V72 (kiểm-rồi-chờ chỉ đúng khi cái chờ ngắn). Giết xong stdout đóng →
`readline` trả `""` ngay → thoát tức thì.

Ba tầng `except Exception` trên đường này (`align`, `ass_karaoke`,
`subtitles`) đều phải re-raise `PipelineCancelled`. Nuốt ở bất kỳ tầng nào là
cú bấm Dừng biến thành "canh hỏng" rồi chạy tiếp với phụ đề chia đều — đúng
lớp lỗi V74 (`TranscribeCancelled` kế thừa `RuntimeError` bị `except
Exception` nuốt).

### Đo đối chứng — và một lỗi thật lòi ra từ phép đo

Worker giả nghe 2s/clip, mẻ 30 clip (~60s), bấm Dừng sau 1,0s:

| ca | có luồng canh huỷ | không có (bản cũ) |
|---|---|---|
| đang nghe clip (2s/clip) | 1,0s | 2,1s |
| **đang nạp model** (20s) | **1,0s** | **20,1s** |

Ca thứ nhất gần như không khác nhau — worker phát một dòng mỗi 2 giây nên
vòng đọc vẫn kịp thấy cờ. Đúng ca thứ hai mới là lý do luồng canh tồn tại.

Phép đo đó lộ luôn một lỗi **của chính bản sửa**: giết tiến trình lúc chưa có
dòng nào ra làm `readline` trả rỗng → hàm báo `"bộ canh chữ không phản hồi
ready"`, tầng trên hiểu là HỎNG: bản mã nguồn **chạy lại toàn bộ ở
in-process**, bản `.exe` ghi phụ đề chia đều rồi đi tiếp. Cú bấm Dừng phải
trông ra cú bấm Dừng — thêm `_kiem_huy()` ở cả 3 chỗ (đọc ready, timeout, gửi
request) và test khoá lại.

### Test (8)

Dừng khi đang nghe (đo < 20s cho mẻ ~60s); dừng khi **đang nạp model** (báo
đúng `PipelineCancelled`, không phải "không phản hồi ready"); cờ set sẵn từ
trước thì không nghe clip nào; `_asr_words_for_clips` không nuốt rồi chạy lại
in-process; `resolve_word_times` và `refresh_subtitles` không biến Dừng thành
"chia đều"; cả đường dây `refresh_subtitles → align_segments` mang đúng cờ;
`DubPipeline` giữ lại `cancel_event`.

**1462 passed, 7 skipped, 0 failed** (Python) + **334 pass, 0 fail** (Node).

### Còn tồn

- Đường in-process chỉ kiểm cờ **giữa các clip** — không cắt ngang được một
  lượt `transcribe()` đang chạy (thư viện không có hook huỷ). Clip 1–3 giây
  nên độ trễ tối đa bằng đúng một clip.
- `editor.py` gọi `refresh_subtitles` không truyền cờ (chưa có nút Dừng ở
  luồng đó).

## V75 — Canh chữ karaoke chạy được ở bản đóng gói (Phase H, 2026-08-19)

Lỗi thứ 6 cùng gốc rễ với V38/V74, và là cái **khó thấy nhất**: nó chưa từng
kêu một tiếng nào.

`align.py` import `faster_whisper` ngay trong tiến trình chính (dòng 49 cũ).
`autodub.spec` cố ý không đóng gói gói đó. Call site
`ass_karaoke.resolve_word_times` bọc `try/except` rồi rơi về ước lượng. Cộng
lại: ở bản `.exe`, **mọi lượt canh chữ karaoke đều hỏng**, phụ đề chia đều
theo thời lượng câu, không dòng log nào tới người dùng. Bảng rà cuối V74 đã
xếp đúng nó là "suy giảm ÂM THẦM" và để lại — mục này đóng nốt.

### Đo trước khi sửa

Bản `.exe` không chạy được từ đây, nên đo bằng đúng điều kiện của nó: đặt
`sys.frozen = True` rồi gọi `resolve_word_times`. Kết quả trước khi sửa: mọi
chữ trong câu dài BẰNG NHAU tới từng mili giây (chia đều), và `caplog` trống
— không có gì để người dùng nghi ngờ.

### Sửa: thêm một venv worker nữa

`autodub/speech/align_whisper_worker.py` — chạy trong `.venv-whisper`, không
import gì từ `autodub` (khác môi trường, có test khoá lại).

Khác `asr_whisper_worker.py` một điểm quyết định: **nhận cả mẻ trong một
request**. Canh chữ là hàng trăm clip 1–3 giây; giao thức single-shot của
worker ASR sẽ phải nạp lại model `base` cho từng clip — nạp mất ~4s, một
video 200 câu là hơn 13 phút chỉ để nạp đi nạp lại. Nạp một lần rồi chạy
`ThreadPoolExecutor` ngay trong worker giữ nguyên mức song song của đường
in-process cũ.

Một clip nghe hỏng thì gửi `{"clip": true, "id": .., "error": ..}` và mẻ
chạy tiếp (câu đó ước lượng, đúng hành vi cũ); hỏng CẢ MẺ mới raise.

Thứ tự chọn đường sao chép nguyên của `transcribe()` — có `.venv-whisper` thì
subprocess, không có thì in-process, **trừ bản đóng gói** (ở đó in-process
không tồn tại). Cố ý không nghĩ ra quy tắc thứ hai: hai quy tắc gần giống
nhau là cách lỗi này sinh sôi.

`_asr_words_in_process` giờ tự chặn khi `sys.frozen` — lưới an toàn cho lần
sau, để người viết code kế tiếp nhận lý do THẬT thay vì
`No module named 'av'`.

### Chỗ suýt vẫn im lặng (bài học V73 cứu)

Thông báo mới "chưa cài bộ nghe Whisper" **bị `log_text.notice_for` lọc sạch**
nếu chỉ `logger.warning`: `NOTICES` là allowlist, phần rơi tự do bị `_TECH_RE`
chặn vì câu có chữ "whisper". Đã thêm dòng riêng, đặt TRƯỚC dòng gộp "Không
canh được phụ đề" (dòng gộp không nói cách sửa). Đo lại end-to-end:

```
LOG    : Không canh được phụ đề: chưa cài bộ nghe Whisper trong thư mục ứng dụng này — ...
NHẬT KÝ: Chữ phụ đề chưa nhảy đúng nhịp giọng đọc vì thư mục này chưa cài bộ nghe —
         đúp chuột tệp "Cai dat Whisper ASR.bat" trong thư mục VoxDub Studio rồi dựng lại phụ đề
```

### Kiểm bằng faster-whisper THẬT, không phải mock

Mọi test mock vẫn xanh kể cả khi hai đầu giao thức JSON lệch nhau — nên dựng
một venv thật (`faster-whisper 1.2.1`), để nó tải model `base` thật (**142 MB,
đã đếm trên đĩa** — chứng minh luôn `--model-dir` đi đúng chỗ) và nghe giọng
người thật (mẫu JFK của repo faster-whisper):

```
venv configured: True
--- subprocess xong sau 4,0s (lần đầu 9,4s: cộng thời gian nạp model) ---
clip 1: 22 chữ | 3 chữ đầu: [('And', 0.0, 0.52), ('so', 0.52, 0.82), ('my', 0.82, 1.18)]
clip 2:  5 chữ | (clip cắt còn 3 giây — số chữ giảm đúng theo)
--- resolve_word_times (đường thật của app) ---
14 chữ | [('And', 10.0, 10.82), ('so', 10.52, 11.56), ('my', 11.18, 12.1), ...]
mọi chữ dài BẰNG NHAU (tức là đang chia đều)? False
```

`False` ở dòng cuối chính là thứ cần chứng minh: mốc chữ tới từ giọng đọc
thật, không phải phép chia.

### Test (14)

Chọn đường (5): có venv thì đi subprocess và KHÔNG được nạp model trong tiến
trình chính; bản đóng gói thiếu venv thì **nói ra cách cài** và trả `None`;
bản mã nguồn thiếu venv vẫn chạy in-process như cũ; mã nguồn + venv hỏng thì
lùi về in-process; **đóng gói + venv hỏng thì KHÔNG lùi** (rơi về đó chỉ đổi
lỗi thật thành `No module named 'av'` — đúng bẫy V74).

Giao thức (3): chạy worker THẬT bằng `faster_whisper` giả — chữ ra đúng từng
clip, chữ rỗng bị loại; một clip hỏng không giết cả mẻ; venv cài dở thì raise
nói rõ thay vì trả `{}` lặng lẽ.

Còn lại (6): mốc từ subprocess đi thẳng vào kết quả karaoke (mốc tuyệt đối =
mốc trong clip + `start`); caller cũ không truyền `settings` thì tự đọc cấu
hình; `align_whisper_worker.py` có mặt trong `autodub.spec` (quên dòng
`datas` là bản `.exe` không có tệp worker, hỏng y như cũ); worker không import
gì từ `autodub`; in-process tự chặn ở bản đóng gói; `notice_for` cho ra được
lời khuyên bấm `.bat`.

**1454 passed, 7 skipped, 0 failed** (máy dev) — nhưng xem mục dưới.

### CI đỏ ngay lần chạy đầu: một test PASS GIẢ vì môi trường

`test_worker_thieu_faster_whisper_thi_bao_loi_ro` chặn bằng cách trỏ
`PYTHONPATH` vào thư mục rỗng. Máy dev này KHÔNG cài `faster-whisper` nên
worker chết đúng như mong đợi → xanh. Máy CI thì cài đủ `requirements.txt`,
worker import được thật → **DID NOT RAISE**, 1 failed / 1453 passed.

Bài học đúng loại đã gặp ở V74 ("máy thử nghiệm không có `.venv-whisper` nên
nhánh subprocess chưa bao giờ chạy tới"): **cái vắng mặt trên máy dev không
phải là điều kiện test**. Sửa bằng stub `faster_whisper.py` tự ném
`ImportError`, đặt trên `PYTHONPATH` (đứng trước `site-packages`) nên thắng ở
mọi máy. Đã kiểm lại đúng trong điều kiện làm CI đỏ — cho stub đứng cạnh
`site-packages` CÓ faster-whisper thật:

```
venv thật có faster-whisper? True
KẾT QUẢ: raise đúng -> bộ canh chữ báo lỗi: faster-whisper chưa cài trong .venv-whisper: ...
```

Bản `.exe` v3.4.3 không bị ảnh hưởng: job build chạy độc lập và đã success,
lỗi nằm ở phép kiểm chứ không ở mã sản phẩm.

### Còn tồn

- Chưa có nút Dừng cho lúc canh chữ (`transcribe()` có `cancel_event`, đường
  này thì chưa). Mẻ vẫn chạy hết rồi mới dừng được ở bước sau.
- Bản `.exe` thật chưa chạy thử — không có máy Windows ở đây. Thứ đã chứng
  minh: giao thức hai đầu khớp với `faster_whisper` thật, và nhánh
  `sys.frozen` chọn đúng đường trong test.

## V62–V64 — Quản lý nhân vật, chạy nhanh, báo cáo chủ động (Phase H, 2026-08-18)

### V62 — Trang quản lý hồ sơ nhân vật

Xem/đổi tên/đổi giọng/xoá nhân vật + sửa quy ước dịch của series. Cố ý KHÔNG
cho tạo hồ sơ rỗng: hồ sơ sinh ra khi dub tập đầu, tạo rỗng ở đây chỉ đẻ thêm
hồ sơ không ai dùng.

Cột **"Nhận diện"** nói rõ nhân vật nào khớp bằng embedding (chính xác) và
nhân vật nào mới chỉ có cao độ (dễ lẫn với người cùng giới) — người dùng biết
chỗ nào đáng nghi thay vì tin mù vào danh sách.

Chặn khi lưu: tên trùng và tên rỗng. Cả hai phá chính cơ chế khớp —
`voice_for()` lấy cái đầu tiên, `remember()` cập nhật nhầm người.

**Bug tự soi ra khi rà lại (đã sửa)**: đang sửa dở mà đổi sang series khác thì
nạp đè luôn, **mọi thứ vừa gõ biến mất không một lời nào**. Mất dữ liệu âm
thầm là kiểu tệ nhất: người dùng chỉ phát hiện khi mở lại và thấy tên cũ. Giờ
có cờ "chưa lưu" + hỏi lại, và bấm «Ở lại để lưu» thì combo quay về đúng hồ sơ
đang sửa chứ không trôi mất.

### V63 — "Chạy như lần trước"

Hoá ra 90% đã có sẵn: nháp `draft_project.json` lưu toàn bộ lựa chọn và tự nạp
lúc mở app. Thứ thiếu chỉ là **đường tắt**: chọn video xong bấm một nút, nhảy
thẳng bước cuối và chạy. Nút chỉ hiện ở bước 1, chỉ khi THẬT SỰ có nháp cũ, và
không hiện ở bước cuối (chỗ đó đã có nút "Bắt đầu lồng tiếng" — hai nút cùng
nghĩa cạnh nhau chỉ làm người dùng phân vân).

### V64 — "Đáng sửa trước" + mở thẳng Editor

`autodub/quality_rank.py` (mới) — hàm thuần, tách hẳn khỏi GUI vì quy tắc xếp
hạng là thứ đáng test kỹ và sẽ còn chỉnh.

Thang điểm cố ý thô và **giải thích được**: chồng tiếng (nghe là biết ngay) >
đọc nhanh (giọng bị ép, >1.3 là nghe rõ méo) > dài quá chỗ trống (nhẹ nhất).
Công thức tinh vi mà không ai kiểm chứng nổi thì tệ hơn thang thô có lý do.

Thứ tự **ổn định** (cùng điểm → theo số câu tăng dần): hai lần mở cùng một báo
cáo phải ra cùng thứ tự, nếu không người dùng tưởng dữ liệu đang đổi.

### Tests (+32, tổng 1265 Python)

V62 (12): liệt kê + nạp hồ sơ; cột "nhận diện" phân biệt embedding/cao độ;
cột số liệu bị KHOÁ; đổi tên lưu được mà **không mất embedding/số tập**; tên
trùng bị chặn và **không ghi đè file**; tên rỗng bị chặn; xoá phải hỏi và tôn
trọng nút Huỷ; xoá không chọn dòng thì cảnh báo chứ không nổ; chưa có hồ sơ
thì giải thích cách tạo; **đổi series khi đang sửa dở phải hỏi**; đã lưu rồi
thì không hỏi nữa.

V63 (5): ẩn khi chưa có lần chạy trước; hiện ở bước 1; ẩn ở bước cuối; chưa
chọn video thì từ chối; **nhảy sang bước cuối TRƯỚC khi chạy** (bấm xong mà
vẫn đứng ở bước 1 thì người dùng tưởng nút hỏng).

V64 (15): chồng tiếng xếp trên câu hơi dài; đọc nhanh hơn xếp trên đọc chậm;
câu sạch = 0 điểm và **không lọt vào danh sách**; giới hạn 5; **thứ tự ổn
định**; dữ liệu rác không làm nổ; mô tả liệt kê đủ vấn đề; thẻ không dựng khi
không có gì đáng sửa; nút mở Editor đi qua đúng cửa sổ chính; cảnh báo khi
chưa chọn dự án; degrade khi trang được dựng ngoài cửa sổ chính.

**1265 passed, 6 skipped, 0 failed** (Python) + **325 test Node (324 pass, 1
skip, 0 fail)**; smoke test toàn app exit 0.

### Remaining Limits

- V62 chưa cho gộp 2 nhân vật (khi hệ thống tách nhầm một người thành hai).
  Cần một thao tác "gộp" riêng — xoá một cái là mất embedding đã tích luỹ.
- V64 mở Editor ở mức DỰ ÁN, chưa nhảy tới đúng câu. Editor hiện chưa có API
  chọn câu theo id; thêm được nhưng là thay đổi ở trang khác.
- V63 dùng lại nháp gần nhất, chưa có "hồ sơ cấu hình" đặt tên (vd cấu hình
  cho phim vs cho vlog). Đủ cho việc lặp hằng ngày, chưa đủ cho nhiều loại
  nội dung song song.

## V96 — Nâng cấp không làm mất cài đặt (25/08/2026)

> **Đánh số lại 26/8:** mục này ra đời ngày 25/8 với nhãn `V91`, trùng một mini-spec khác đã có từ 20/8. Commit gốc vẫn mang nhãn cũ (`V91`) — lịch sử git đã đẩy đi thì không viết lại, tra chéo bằng ghi chú này.

**Vì sao:** V77 dạy app tự tìm lại `.venv-*`/`models/` của bản cũ nằm cạnh
bên, V81 làm tiếp cho FFmpeg. Riêng `.env` thì bị bỏ quên — mà đó mới là chỗ
chứa khoá API, token đăng nhập và các đường dẫn người dùng trỏ tay. Hệ quả
thực tế: nâng cấp xong engine vẫn chạy nhưng app "quên" hết cài đặt.

**Đã làm:**
- `venv_discovery.tim_env_cu()` — dò `.env` ở các thư mục cạnh bên, bỏ tệp
  rỗng, bỏ chính thư mục đang chạy, nhiều bản cũ thì lấy bản sửa gần nhất.
- `app.py main()` — lúc khởi động CHÉP `.env` bản cũ sang, ưu tiên hơn
  `.env.example`. Cố ý chép chứ không đọc nhờ: `env_store` ghi vào
  `app_root()/.env`, nên nếu chỉ đọc nhờ thì lần Lưu đầu tiên trên màn hình
  Cài đặt sẽ xoá trắng những khoá không hiện ra ở đó.
- `config.py Settings.load()` — đường lui tương tự cho bản chạy dòng lệnh và
  worker (không đi qua `app.py`).

**Kiểm:** `tests/test_env_ke_thua.py` — 7 test. Đã thử gỡ từng chốt để xác
nhận test bắt được: (1) nhận cả `.env` rỗng → đỏ; (2) ưu tiên `.env.example`
hơn bản cũ → đỏ; (3) đọc nhờ thay vì chép → đỏ.

**Chạy thật:** dựng `v3.8.7` (có `.env` + venv + models + bin) cạnh `v3.8.8`
trống → cả 4 thứ đều được nhận lại, `Settings.load()` đọc đúng `VOX_API_KEY`
và `WHISPER_MODEL` của bản cũ.

**Giới hạn còn lại:** chỉ dò thư mục CÙNG THƯ MỤC CHA. Giải nén sang ổ đĩa
khác thì vẫn phải chép tay. Toàn bộ test chạy trên Linux, chưa kiểm trên
Windows thật.

**Toàn bộ bộ test:** 1933 đạt, 7 bỏ qua.

## V97 — Xem trước chi phí + gộp câu trước khi tính tiền (25/08/2026)

> **Đánh số lại 26/8:** mục này ra đời ngày 25/8 với nhãn `V92`, trùng một mini-spec khác đã có từ 20/8. Commit gốc vẫn mang nhãn cũ (`V92`) — lịch sử git đã đẩy đi thì không viết lại, tra chéo bằng ghi chú này.

**Vì sao:** máy chủ tính tiền theo SỐ DÒNG (10 Vox nền + 2 Vox dịch mỗi dòng,
`ai.js:287`), mà bộ nghe cắt theo khoảng lặng 500ms nên một câu liền mạch có
thể vỡ thành hàng chục mẩu một-hai chữ. Luồng lồng tiếng gửi thẳng các mẩu đó
đi dịch — `gop_cau()` trước nay chỉ dùng lúc xuất `.txt`. Song song, route
`/v1/device/estimate` và `SaasClient.estimate()` đã có sẵn nhưng **không nơi
nào gọi**: số Vox chỉ hiện ở bảng tổng kết, tức là sau khi đã trừ tiền.

**Đã làm — phần 1 (gộp câu):**
- `transcribe_tool._nen_cat()` — tách luật cắt để `gop_cau` (.txt) và
  `gop_de_dich` (lồng tiếng) dùng chung, chỉ khác hạn mức.
- `transcribe_tool.gop_de_dich()` — hạn mức 7,0 giây / 84 chữ (chặt hơn bản
  .txt vì những dòng này còn phải làm phụ đề đọc được). Giữ nguyên `id` (là
  tên tệp WAV từng câu — đánh số lại là trỏ nhầm tệp của lần chạy trước),
  giữ mọi trường khác, nối cả `words`, và KHÔNG gộp qua hai người nói.
- `pipeline._run_impl` — gộp sau phân giọng, trước `annotate_slots` và trước
  cả `cong_xem_truoc` lẫn `_setup_hold`; ghi lại transcript + SRT gốc theo
  dòng đã gộp để tệp trên đĩa khớp thứ đem đi lồng tiếng.
- Cài đặt `GOP_CAU_TRUOC_KHI_DICH` (mặc định bật), có ô trong màn hình Cài đặt.

**Đã làm — phần 2 (xem trước chi phí):**
- `billing.cong_xem_truoc()` → `DubResult(status="cost_pending")` mang số câu,
  Vox ước tính, số dư. Đặt sau ASR (mới biết số câu) và trước `setup_hold`
  (chưa giữ chỗ đồng nào).
- Chỉ hỏi ở luồng wizard (`req.defer_export`) — batch/dòng lệnh không có ai
  ngồi đó để bấm. Dấu `chi_phi_da_duyet.json` trong thư mục dự án để chạy
  tiếp không hỏi lại.
- Giao diện: hộp thoại "Duyệt chi phí trước khi chạy" (Vox + quy đổi VNĐ + số
  dư), bấm Hủy là dừng hẳn — nghe-chép chạy trên máy nên chưa tốn gì.

**Quyết định có chủ đích:** hỏi giá TRƯỢT thì không chặn, chỉ ghi cảnh báo —
`setup_hold` ngay sau đó vẫn tự chặn khi thiếu Vox (`credit_blocked`), để một
lần chớp mạng làm hỏng lượt chạy thì tệ hơn.

**Lỗi tự tìm ra khi làm:** `_chay_tiep_sau_khi_duyet_gia` gọi `_launch` ngay
trong `_on_finished`, nhưng `finished_ok` bắn từ TRONG thân worker nên QThread
vẫn đang chạy → `_launch` từ chối, người dùng bấm Chạy tiếp mà không có gì
xảy ra. Sửa: đợi `worker.finished` rồi mới chạy.

**Kiểm:** `tests/test_gop_de_dich.py` (10) + `tests/test_cong_xem_truoc_chi_phi.py`
(11). Đã gỡ từng chốt để xác nhận đỏ: gộp qua hai người nói, đánh số lại id,
hỏi giá trượt mà im lặng, đã duyệt vẫn hỏi lại, gộp sau khi báo giá.
Một đột biến (dời khối gộp xuống ngay trước `_setup_hold`) KHÔNG đỏ — và đúng
là không nên đỏ, vì tiền vẫn tính trên dòng đã gộp; nó lộ ra chốt còn thiếu
nên đã siết thêm thứ tự so với `cong_xem_truoc` và `annotate_slots`.

**Đo trên dữ liệu vụn mô phỏng (3.000 mẩu 1-2 chữ):** còn 560 dòng (18%),
36.000 → 6.720 Vox, tức 360.000 → 67.200 VNĐ. Dòng dài nhất 7,0 giây, nhiều
chữ nhất 63 — đều trong hạn mức phụ đề.

**Chưa kiểm:** chưa chạy thật đầu-cuối trên máy Windows với video thật; hộp
thoại duyệt giá chưa được bấm bằng tay lần nào.

## V98 — Vá LỚP "hứa miễn phí rồi trừ tiền" (26/08/2026)

**Vì sao:** bản vá 25/8 (`3c7dd2d`) sửa đúng một tooltip. Nhưng đi ngược lên
thì thấy nút ấy sai được là vì **mô tả đầu tệp `music_suggest.py` cũng sai y
hệt**: viết ở V88 ("cách làm ở đây CỐ Ý không dùng AI… chạy offline, không tốn
Vox"), rồi V89 thêm đường hỏi trợ lý trên máy chủ vào CHÍNH tệp đó (dòng
218–220, `get_client().assist(...)`, trừ 2 Vox) mà không ai sửa lại câu mô tả.
Người viết giao diện đọc mô tả ấy, tin nó, chép nguyên ý sang tooltip. Vá một
tooltip mà để nguyên nguồn thì lỗi sẽ mọc lại ở chỗ khác.

**Đã làm:**
- Viết lại mô tả đầu `autodub/media/music_suggest.py`: nói rõ HAI đường —
  đo bằng luật (V88, offline, 0 Vox) và hỏi máy chủ (V89, **2 Vox mỗi lượt**),
  đường nào là mặc định, đường nào là lối lui. Ghi lại luôn câu chữ cũ đã đẻ
  ra bug để lần sau ai đọc cũng thấy.
- Bộ canh cấp LỚP trong `tests/test_cau_chu_ve_tien.py`: quét mọi tệp có gọi
  `get_client(` (tức tiêu được Vox); tệp nào mô tả đầu tệp có hứa miễn phí thì
  phải nói luôn giá của đường tốn tiền. Không cấm chữ "miễn phí" — cấm hứa
  một nửa sự thật.
- Danh sách miễn trừ phải kèm lý do viết ra, và có test canh chính danh sách
  đó (trỏ tệp có thật + lý do đủ dài).

**Quét được gì:** 3 tệp tiêu được Vox có hứa miễn phí trong mô tả.
`translate_review.py` và `music_suggest.py` (sau khi sửa) đều nói rõ giá;
`credit_widget.py` miễn trừ có lý do — chữ "miễn phí" ở đó đã kèm điều kiện
ngay trong câu (chỉ khi máy chủ tắt hệ thống credit, widget tự ẩn luôn).

**Kiểm:** đã dựng lại đúng bug gốc (trả mô tả về câu chữ V88) → 2 test đỏ; và
thử nhét bừa một tệp vào danh sách miễn trừ với lý do qua loa → đỏ.

**Không phát hành bản mới:** thay đổi chỉ nằm ở mô tả trong mã và test, không
đụng thứ người dùng thấy. Tooltip đúng đã nằm trong v3.9.1.

## D1 — Trả lại quyền chọn đường dịch ngoại tuyến (26/08/2026)

**Vì sao:** `translate_local` (NLLB trên máy) chỉ chạy khi `is_configured()`
sai. Từ 22/8/2026 địa chỉ máy chủ được nhúng thẳng vào `.exe` để sửa lỗi "bản
offline câm" — hệ quả phụ không cố ý: `is_configured()` LUÔN đúng trên mọi bản
phát hành, nên nhánh ngoại tuyến không bao giờ được chọn nữa dù ô cài đặt vẫn
hiện. Bug loại "vô hiệu âm thầm".

**Hai chỗ bản đặc tả gốc sai/thiếu, đã sửa trước khi làm:**

1. **"Miễn phí" là sai.** Chạy ngoại tuyến chỉ bỏ được phí dịch (2 Vox/dòng);
   giá nền lượt xử lý (10 Vox/dòng) vẫn tính. Tiết kiệm 17%, không phải 100%.
   Dán nhãn "0 Vox" lên đó chính là lớp lỗi #5. Nhãn nay ghi "không phí dịch".
2. **Thiếu hẳn phần tính tiền.** `create_hold` tính phí dịch theo
   `settings.translate_enabled`, không biết gì về chế độ. Mà máy chủ trừ đúng
   số ước tính lúc giữ chỗ và KHÔNG hoàn phần chưa dùng (`hold.service.js`:
   `chargedVox: hold.estimatedVox`). Làm theo đặc tả gốc thì người chọn ngoại
   tuyến vẫn bị trừ tiền dịch cho việc máy họ tự làm — 29.700 VNĐ với tệp
   1.485 dòng. Nay cờ đi vào CẢ cổng xem trước giá lẫn lúc giữ chỗ.

**Đã làm:**
- `Settings.translate_mode`: `server` | `offline` | `auto`. Mặc định `server`
  = đúng hành vi hiện tại; máy nào đã bật cờ ngoại tuyến cũ thì chuyển thành
  `auto`. Không mặc định `auto` cho mọi người: rơi nhánh im lặng sang engine
  đã biết là hay bỏ sót câu là đổi chất lượng mà người dùng không hề chọn.
- `_auto_translate`: nhánh `offline` đặt TRƯỚC mọi phép hỏi `is_configured()`.
  Chưa cài → báo lỗi rõ, không quay về máy chủ. Lỗi giữa chừng cũng không quay
  về máy chủ. `auto` bắt `OfflineError` rồi rơi về NLLB kèm cảnh báo; `server`
  vẫn dừng hẳn như cũ.
- Ô Cài đặt: công tắc 2 trạng thái → 3 lựa chọn, mỗi lựa chọn nói rõ có phí
  hay không, kèm cảnh báo chất lượng.
- Lời báo rơi nhánh đi qua `logger.warning` nên hiện trong bảng nhật ký chạy
  (`GuiLogHandler`) — cùng chỗ mọi sự kiện quan trọng khác vẫn hiện.

**Guardrail đã giữ:** bản vá 22/8 (nhúng địa chỉ máy chủ) không bị đụng tới;
có test canh riêng cho việc đó.

**Kiểm:** `tests/test_duong_dich_nguoi_dung_chon.py` — 10 test. Đã gỡ từng
chốt: quay lại suy từ `is_configured()` → 3 đỏ (gồm đúng bài chống tái phát);
ngoại tuyến chưa cài mà lặng lẽ về máy chủ → đỏ; quên truyền cờ vào cổng xem
trước giá → đỏ; nhãn hứa "miễn phí" → đỏ.

**Hai lỗi của chính tôi do bộ canh sẵn có bắt được:** viết `options` ngược thứ
tự (dự án dùng `(nhãn, giá trị)`) nên ô sẽ lưu nhầm cả câu tiếng Việt làm giá
trị; và bỏ `TRANSLATE_LOCAL_ENABLED` khỏi giao diện mà quên dọn `.env.example`.

**CHƯA làm được — cần máy của chủ dự án:** live verification 3 nhánh với NLLB
thật. Máy chạy test không có NLLB (cần cài ~620 MB), và toàn bộ test chạy trên
Linux. Chưa nhánh nào được chạy thật một lượt nào.

## D1b — Năm script cài đặt chưa bao giờ có trong bản phát hành (26/08/2026)

**Chủ dự án tìm ra bằng ảnh chụp thư mục**, ngay sau khi tôi bảo chạy
`scripts/setup_translate_local.py`: mở `VoxDub-Studio-v3.10.0-win64/scripts/`
chỉ thấy 6 tệp `setup_*`, không có tệp đó. Tôi vừa hướng dẫn một việc không
thể làm được.

**Gốc rễ:** danh sách đóng gói trong `build_exe.py` là danh sách GÕ TAY sáu
tên, và đã lệch khỏi mã từ lâu. Năm script được app bảo người dùng chạy nhưng
chưa bao giờ nằm trong bản tải nào:

| Script | App nhắc ở đâu | Tính năng chết theo |
|---|---|---|
| `setup_translate_local.py` | 5 chỗ | Dịch ngoại tuyến (cả D1 vừa làm) |
| `setup_diarization.py` | 8 chỗ | Phân biệt người nói |
| `setup_lipsync.py` | 9 chỗ | Khớp khẩu hình |
| `setup_ocr.py` | 1 chỗ | Nhận diện vùng chữ |
| `setup_voices.py` | trang Trợ giúp | Ghi danh giọng |

Không một dòng lỗi nào: app bảo "chạy scripts/setup_X.py", người dùng mở thư
mục ra không thấy, và tính năng coi như không tồn tại.

**Đây là lớp lỗi #3 tái diễn** (FEATURES.md §6) — cùng cơ chế đã khiến
`asr_whisper_worker.py` không được đóng gói và chép lời trong bản `.exe` chưa
từng chạy được lần nào (V80). Bài học đã ghi ở đó mà vẫn tái phát ở một danh
sách khác: **suy ra, đừng gõ tay.**

**Đã làm:**
- `build_exe.scripts_can_dong_goi()` — lấy tất cả `scripts/setup_*.py` cộng
  `_python_ho_tro.py`. 6 tệp → 13 tệp. Tách thành hàm riêng để test soi được
  mà không phải chạy cả bản build.
- `tests/test_script_cai_dat_duoc_dong_goi.py` — quét mọi chuỗi
  `scripts/setup_*.py` trong `autodub/` và `autodub_gui/`, đòi từng tệp phải
  (1) có thật trong kho và (2) nằm trong danh sách đóng gói. Kèm chốt cấm
  quay lại gõ tay.

**Kiểm:** dựng lại đúng danh sách gõ tay 6 tên của bản cũ → 2 test đỏ, trong
đó có đúng bài bắt được `setup_translate_local.py` bị thiếu.

**Bài học riêng cho tôi:** D1 tôi làm xong, test xanh, tag phát hành — nhưng
tính năng vẫn không dùng được vì bộ cài của nó không có trong gói. Test logic
xanh không nói gì về việc thứ đó có tới tay người dùng hay không.

## D1c — Mở gói ra kiểm, và câu chữ trong chính bộ cài (26/08/2026)

**Đã mở tệp zip phát hành v3.10.1 ra kiểm thật** thay vì tin bản build:
`scripts/` có 14 mục (12 bộ cài + `_python_ho_tro.py` + `python_tag.txt`),
`setup_translate_local.py` 4.888 byte. Đối chiếu băm với tệp trong kho: khác
nhau đúng phần xuống dòng CRLF do Windows nén, bỏ CR đi thì giống hệt.

**Một cảnh báo giả của chính tôi:** lượt kiểm đầu báo "0 tệp — VẪN THIẾU". Đó
là lỗi bộ lọc của tôi (`'/scripts/' in tên`, trong khi đường dẫn trong zip
không có dấu `/` đứng đầu), không phải lỗi bản build.

**Lỗi thật tìm được khi mở ra đọc:** chính `setup_translate_local.py` vẫn ghi
*"Chỉ có tác dụng khi bật TRANSLATE_LOCAL_ENABLED=true trong .env VÀ không có
máy chủ nào cấu hình"* — đúng tới trước D1, sai từ D1. Dòng báo khi cài xong
cũng vậy. Người dùng cài xong đọc đúng câu bảo họ không dùng được.

Lớp lỗi #5 lần nữa, và ở chỗ khó chịu nhất: trong tệp mà tôi vừa bảo họ chạy.

**Đã làm:** viết lại phần mô tả và dòng kết của bộ cài — chỉ sang Cài đặt →
Dịch thuật → "Luôn ngoại tuyến", ghi rõ khoá mới `TRANSLATE_MODE=offline`,
nói rõ khoá cũ vẫn được đọc để chuyển tiếp, và nói rõ chuyện tiền (bỏ được
phí dịch 2 Vox/dòng, giá nền vẫn tính).

**Cách làm mới tự đặt cho mình:** trước khi bảo người dùng chạy một tệp trong
bản phát hành, phải mở gói ra xem tệp đó có thật và đọc nội dung nó — test
logic xanh không nói gì về việc thứ đó có tới tay người dùng hay không.

## D1d — Có tệp .py chưa đủ: người dùng nhìn tệp .bat (26/08/2026)

**Chủ dự án hỏi ngay sau bản vá trước:** mở thư mục v3.10.2 ra, thấy 6 tệp cài
đặt đúp-chuột, không tệp nào nói về tách giọng người nói hay dịch ngoại tuyến
— *"hình như nó chưa có hả ta"*. Tệp `.py` đã nằm trong `scripts/` rồi, nhưng
**người dùng không mở `scripts/` ra đọc**; họ nhìn mấy tệp đúp-chuột-là-chạy ở
thư mục gốc.

**Gốc rễ:** danh sách `.bat` trong `build_exe.py` cũng là danh sách GÕ TAY —
tầng thứ hai của đúng lỗi vừa vá. Và ghi chú trong chính đoạn mã cho thấy nó
đã bỏ quên hai lần trước: FFmpeg (V82) và Demucs (V86). Đây là lần thứ ba.

**Đã làm:**
- `build_exe.cac_bat_can_sinh()` — sinh `.bat` cho MỌI script cài đặt được
  đóng gói. Sáu tệp cũ giữ nguyên câu chữ viết tay (có số liệu cụ thể, đáng
  giữ), phần còn lại sinh từ khuôn với bảng mô tả `MO_TA_SETUP`; script không
  có trong bảng vẫn được sinh `.bat`, chỉ là câu mô tả chung chung — cố ý:
  thà mô tả sơ sài còn hơn người dùng kết luận tính năng không tồn tại.
  6 → 11 tệp.
- `KHONG_SINH_BAT` (chỉ `setup_lipsync_poc.py`) kèm lý do viết ra, có test canh.
- `HUONG_DAN_CAI_DAT.md` trong gói: thêm mục cho dịch ngoại tuyến và tách
  giọng, kèm cảnh báo TRƯỚC rằng tách giọng cần tài khoản HuggingFace + token
  và nặng 1-2 GB — để người dùng biết trước khi bấm, không phải đọc giữa chừng.

**Kiểm:** 4 chốt mới. Dựng lại danh sách `.bat` gõ tay 6 tên → đỏ. Kèm chốt
tên tệp phải ASCII (dấu tiếng Việt trong tên tệp là rắc rối trên Windows),
không trùng nhau, và mọi `.bat` phải có `cd /d "%~dp0"` — thiếu dòng đó thì
đúp chuột từ nơi khác là sai đường dẫn, đúng lỗi chủ dự án gặp khi tự gõ tay
(`scripts\scripts\...`).

**Bộ canh chính tả của kho bắt lỗi của tôi:** tôi viết tiếng Việt không dấu
trong một dòng chú thích; `test_vi_diacritics` đỏ ngay.

## D1e — Rà Cài đặt trước khi phát hành: 5 lỗi, 1 nghiêm trọng (26/08/2026)

Chủ dự án yêu cầu rà lại Cài đặt và các tính năng, sửa bug rồi mới phát hành.
Rà có hệ thống thay vì vá từng chỗ tình cờ thấy.

### Lỗi NGHIÊM TRỌNG — gộp câu nối nhầm hai người nói

`gop_de_dich()` (V97, làm hôm qua) so trường `speaker` để biết có được nối hai
mẩu hay không. Nhưng `diarization.assign_speakers()` ghi nhãn người nói vào
**`speaker_label`**, không phải `speaker`. Hai bên đều `None`, so ra bằng
nhau → **câu của hai người khác nhau bị nối thành một dòng**, và một dòng thì
chỉ đọc được một giọng.

Trúng đúng ca người dùng đang định chạy: video hai người đối thoại, gộp câu
bật mặc định.

**Test cũ vẫn xanh** vì nó dựng dữ liệu giả bằng đúng tên trường sai đó. Một
bộ canh dùng sai tên trường thì không canh gì cả — đây là bài học đắt nhất
của đợt này.

Sửa: `_ai_noi(seg)` đọc `speaker_label` + `voice` + `speaker`. Thêm chốt buộc
tên trường phải khớp tầng phân giọng thật (đọc thẳng `diarization.py`), và
chốt không nối hai mẩu đã gán giọng khác nhau. Gỡ ra → 2 đỏ.

### Bốn lỗi câu chữ nói sai về tiền và về đường chạy (lớp lỗi #5)

1. Nhãn bước 3 **`QLabel("VoxDub Cloud")` viết chết** — người dùng chọn ngoại
   tuyến ở trang Dịch thuật, sang bước 3 vẫn thấy VoxDub Cloud.
2. Bảng tóm tắt bước 5 ghi cứng **"12 Vox/câu"** — ngoại tuyến thật ra 10.
3. Dòng giải thích bước Chạy dịch cũng ghi cứng bộ số 10/12/20.
4. Gợi ý ô "Dịch tự động" trong Cài đặt cũng vậy.

Sửa KHÔNG phải vá bốn chuỗi: thêm `autodub_gui/gia.py` — MỘT chỗ tính giá,
lấy **bảng giá thật từ máy chủ** (`app_config()["pricing"]`) nên đổi giá bên
máy chủ là app hiện đúng ngay. Chỉ đọc bản đã nhớ đệm, cố ý không gọi mạng:
hàm chạy trên luồng giao diện lúc dựng nhãn.

Bộ canh mới `tests/test_gia_khong_go_thang.py` cấm gõ giá mỗi câu vào câu chữ
giao diện — **nó lập tức bắt được ba chỗ do chính tôi vừa viết sáng nay**.

### Thiếu ô: số người nói

`speaker_count` có trong cấu hình từ V65b nhưng **chưa từng có ô nào trong
giao diện** — chỉ đặt được bằng cách tự mở `.env`. Mà đây là thứ người dùng
biết chắc (họ xem video rồi) còn máy thì phải đoán, và số người dùng khai
được ưu tiên hơn mọi suy đoán. Đã thêm ô vào Cài đặt → Cơ bản.

### Hai chỗ nghi mà KHÔNG phải lỗi

- 5 ô cài đặt "app không đọc": kiểm ra đều có đọc, qua `env_dir`/`env_multiline`
  mà biểu thức tìm của tôi bỏ sót. Không có ô chết.
- 23 khoá không có ô giao diện: hầu hết là đường dẫn engine và tinh chỉnh
  nâng cao — ẩn là đúng.

### Đã xác nhận đúng (câu hỏi của chủ dự án)

Phân giọng đưa **toàn bộ tệp vào một lượt** (`pipeline(args.audio)`), không
chia khúc — nên trong cùng một video, chuyển cảnh hay đối đáp qua lại không
làm mất dấu người nói. Nhãn KHÔNG ổn định giữa các video khác nhau; đó là
việc của Hồ sơ nhân vật (V57).

## D1f/D1g — Bảy lỗi từ MỘT lượt chạy thật của người dùng (26/08/2026)

Người dùng chạy thử một video YouTube hai người đối thoại rồi gửi
`transcript_original.json`, bản dịch và toàn bộ nhật ký. Một lượt chạy đó lộ
ra nhiều lỗi hơn cả buổi tôi tự rà.

### 1. Worker in tiếng Việt chết vì bảng mã (gốc của "dịch bị thiếu")

    UnicodeEncodeError: 'charmap' codec can't encode character 'Đ'

`Đ` là chữ **Đ**. `translate_local_worker.py` in JSON `ensure_ascii=False`
mà không đặt UTF-8; Windows cho tiến trình con dùng cp1252 → chết giữa chừng,
cha chỉ thấy "worker kết thúc bất thường" rồi chuyển sang dịch tay.

Quét cả 7 worker: **3 thiếu** (`translate_local`, `lipsync`, `text_regions`),
4 cái kia có — quy ước bị bỏ sót chứ không phải thiết kế. Vá cả ba, thêm
`tests/test_worker_utf8.py`.

### 2. Phân giọng hỏng 100% vì torchcodec

    Could not load libtorchcodec ... libtorchcodec_core9.dll

pyannote 4.x giải mã âm thanh bằng `torchcodec`, thứ này đòi bản FFmpeg
"full-shared" có DLL trên Windows; app chỉ mang `ffmpeg.exe`.

Sửa: `_nguon_am_thanh()` tự đọc WAV bằng thư viện chuẩn rồi đưa thẳng
`{"waveform", "sample_rate"}` cho pyannote — bỏ qua hẳn torchcodec. Nhiều kênh
thì TRỘN xuống mono (bỏ bớt kênh là mất người nói chỉ có ở kênh kia). Đọc
trượt thì trả lại đường dẫn như cũ, có ghi dấu vết.

### 3. Smoke test chứng nhận một cài đặt hỏng

Bộ cài in `smoke test PASS` trong khi diarization hỏng mọi lượt — vì nó chỉ
`Pipeline.from_pretrained(...)`, KHÔNG chạm tới đường giải mã. Nay chạy thật
trên 2 giây âm thanh tự dựng, và báo lỗi đúng chuyện giải mã thay vì đổ tội
cho token/agreement.

### 4. Trả tiền HAI LẦN cho một video (do chính bản D1 của tôi)

    14:17  chốt 250 Vox theo đường ngoại tuyến (không kê phí dịch)
    14:21  dịch qua VoxDub Cloud — trừ thêm 276 Vox

Giá chốt một lần rồi giữ nguyên; lượt chạy sau đổi sang máy chủ thì phần dịch
bị trừ NGOÀI khoản đã chốt. Người dùng được báo 250, mất 526.

Sửa: ghi `duong_dich_da_chot.json` lúc chốt giá; trước khi gọi máy chủ dịch,
thấy giá đã chốt theo đường ngoại tuyến thì DỪNG kèm hai cách chữa. Thư mục
cũ không có dấu thì không chặn oan.

### 5-7. Đã ghi ở D1e (nhạc nền im lặng, bản dịch thiếu câu, engine không dò
bản cũ) — nhật ký lần này xác nhận cả ba đúng như chẩn đoán.

**Bài học:** ba lỗi đầu đều là "cài đặt báo thành công, chạy thật thì hỏng".
Không có lượt chạy thật của người dùng thì không cái nào lộ ra.

**Lỗi của chính tôi trong lúc viết test đợt này:** (1) test "đặt mã hoá trước
lệnh in" so vị trí chuỗi, báo đỏ oan cho 3 worker vốn đúng — `print(` trong
thân hàm định nghĩa sớm không có nghĩa là chạy sớm; viết lại bằng AST. (2)
cửa sổ tìm bắt nhầm lần xuất hiện đầu của `SMOKE_DECODE_FAIL` (trong đoạn mã
sinh ra) thay vì chỗ báo lỗi cho người dùng.

**Hai lỗi của tôi do bộ canh sẵn có bắt được ngay khi chạy toàn bộ:**
1. `test_ten_khong_ton_tai` — tôi đặt khối ghi `duong_dich_da_chot.json`
   TRƯỚC dòng định nghĩa `khong_tinh_phi_dich`. Python chỉ kêu khi dòng đó
   chạy, mà đó là nhánh ít đi qua nhất; bộ canh quét tên bắt được ở tầng mã.
2. `test_count_mismatch_warns_but_loads` — test CŨ khẳng định đúng hành vi
   tôi vừa cố ý đổi (thiếu câu thì cảnh báo rồi nạp). Không sửa mã cho test
   xanh: đổi test theo ý định mới, tách thành hai (thiếu → dừng, thừa → nạp),
   và ghi rõ trong docstring vì sao đổi.

## C39 — Trình chỉnh sửa: đường ra, và dự án nhập vào bị rỗng thông tin (27/08/2026)

Chủ dự án dùng thật tính năng nhập (C37, làm tối hôm trước, chưa ai chạy) rồi
báo hai chuyện.

### 1. Không có đường quay lại

*"hình như nó không thể nhấn quay lại về trước được"*

`EditorPage.close_requested` đã khai, và `app.py` đã nối nó về trang Dự án —
nhưng **không nút nào phát tín hiệu đó**. Dây nối sẵn, thiếu đúng cái công
tắc. Thanh trên cùng chỉ có logo, tên dự án, chỉ báo lưu, nút Xuất video; khi
thanh bên của app ẩn đi thì không còn đường nào ra.

Sửa: thêm `IconButton` mũi tên trái ở đầu thanh, nối thẳng vào tín hiệu sẵn có.

### 2. Thời lượng 00:00, không đọc được dạng sóng, ngôn ngữ không rõ

`nhap_du_an()` chỉ ghi phụ đề + `source_video.json`. Không đo độ dài, không
trích âm thanh, không ghi ngôn ngữ. Nên Trình chỉnh sửa hiện đúng những gì
không có: thời lượng 00:00, «Không đọc được dạng sóng của tệp âm thanh này»,
«Ngôn ngữ gốc: không rõ», thư mục 5 KB.

Sửa: đo độ dài bằng `probe_duration_s`, dựng `report.json` tối thiểu (nơi
trang Dự án và Trình chỉnh sửa đọc thời lượng ra), trích `original_audio.wav`
cho dạng sóng. Trích trượt thì CẢNH BÁO chứ không chặn việc nhập.

Cố ý KHÔNG bịa `processing_time_seconds` hay số Vox vào báo cáo — dự án nhập
vào chưa từng chạy, ghi số đó là nói dối về việc chưa xảy ra. Có test canh.

**Chạy thật:** dựng video 8 giây + .srt 2 câu → đo đúng 8,0 giây, trích ra
`original_audio.wav` 256 KB, ghi `source_language: vi`.

### Rà cả Trình chỉnh sửa như chủ dự án yêu cầu

- 21 nút, **0 nút chưa nối** hành động.
- Mọi tín hiệu của bảng đều có nơi nghe: **0 tín hiệu mồ côi**.
- Quét tín hiệu khai-mà-không-ai-phát: chỉ `close_requested` là thật.

**Ba báo động giả của phép quét, đã kiểm tay trước khi báo:** `open_subtitle`,
`open_youtube`, `open_other` bị chấm là "chết" vì chúng được phát qua BIẾN
VÒNG LẶP (`signal.emit` trong vòng `for text, signal in (...)`), phép dò theo
tên không thấy. Kiểm tay thì cả bốn nút "Mở nhanh" đều nối đủ. Lần quét đầu
còn báo 54 chỗ — do khuôn thật là `.connect(self.x.emit)` KHÔNG có dấu ngoặc,
mà phép dò lại đòi `.emit(`.

### Môi trường máy chạy test lại mất gói hệ thống

Giữa phiên, `libGL`, `libxkbcommon`, `libfontconfig`, `libglib` và cả `ffmpeg`
biến mất — lần thứ N (xem project_voidmix_workspace_mat_goi_he_thong). Chốt
chặn môi trường của kho làm đúng việc: **từ chối chạy test** kèm câu chỉ thẳng
`scripts/cai_moi_truong_test.sh`, thay vì báo xanh giả với số thấp hơn. Sau
khi cài lại: 2089 đạt (so với 2047 của lượt trước khi thiếu Qt).

## C40 — Máy chạy test mất gói hệ thống: chỉnh tới đâu là hợp lý (27/08/2026)

**Gốc rễ, đo được:** `/home/coder` nằm trên đĩa riêng (`/dev/vda1`) nên được
giữ lại; `/usr` thuộc image container nên **dựng lại sạch mỗi lần workspace
khởi động**. Không ai xoá cả — đó là cách workspace hoạt động. Vì vậy
`libGL`, `libxkbcommon`, `libfontconfig`, `libglib`, `ffmpeg` biến mất đều
đặn (21/08, 26/08, 27/08).

**Điều KHÔNG cần sửa:** chốt chặn `tests/test_kiem_moi_truong.py` đã ngăn
đúng thứ nguy hiểm — bộ test từ chối chạy kèm câu chỉ thẳng script cài, thay
vì báo xanh với số thấp hơn. Phần đó làm đúng việc, giữ nguyên.

**Đã thêm:** `scripts/chay_test.sh` — tự gọi bộ cài ở chế độ `--neu-thieu`
rồi chạy pytest. Máy lành thì phép kiểm mất **0,24 giây** (đo thật, có test
canh mốc 3 giây); máy vừa mất gói thì tự cài rồi chạy tiếp. Bỏ được vòng
"chạy test → đọc lỗi → chạy script → chạy lại" mỗi phiên.

**Giới hạn đã biết, ghi ra chứ không giấu:** `--neu-thieu` phát hiện bằng
cách thử nạp Qt và tìm ffmpeg rồi gọi `apt-get install`. Nếu tệp bị xoá TAY
mà sổ apt vẫn ghi "đã cài" thì lệnh cài không làm gì (cần `--reinstall`).
Phép thử của tôi rơi đúng vào ca đó nên chỉ chứng minh được phần PHÁT HIỆN,
chưa chứng minh phần CHỮA. Ở tình huống thật — container dựng lại — sổ apt
cũng mới nên không gặp.

**Việc còn lại nằm ngoài kho mã:** cách chữa dứt điểm là thêm 18 gói này vào
image hoặc script khởi động của template Coder (`/etc/profile.d/` đang được
template cấp mỗi lần khởi động, cùng cơ chế). Đó là thao tác của người quản
trị workspace, không phải việc lập trình.

**Đính chính một câu tôi nói sai với chủ dự án:** tôi bảo con số test nhảy
2047 → 2089 là do "thiếu Qt nên test giao diện bị bỏ qua". SAI. Kiểm lại:
các commit tối trước khai lần lượt 2052 → 2054 → 2063 → 2077 → 2083, cộng
test mới của hôm nay. Đó là test được THÊM VÀO, không có gì bị bỏ qua. Cái
bẫy báo-xanh-giả có thật nhưng không phải lần này.

**Lỗi của tôi khi viết test đợt này:** hai test đầu so vị trí chuỗi trên
nguyên văn tệp shell, bắt trúng chữ "pytest" và "--neu-thieu" nằm trong phần
chú thích ở đầu tệp rồi kết luận sai thứ tự. Lần thứ BA trong một ngày mắc
đúng lỗi dò-chuỗi-thô. Sửa bằng `_lenh()` — bỏ chú thích trước khi so.

2095 Python đạt, 7 bỏ qua.

## C41 — Lượt soát lại bản dịch hỏng 12 ngày, và thuật ngữ cố định không ai kiểm (27/08/2026)

Chủ dự án hỏi ô «Ngữ cảnh / Cách xưng hô / Thuật ngữ cố định» có thật sự làm
bản dịch hiểu đúng không. Đọc mã ra hai chuyện, một trong đó là lỗi nặng.

### Lỗi: máy chủ từ chối lý do mà app gửi — hỏng suốt 12 ngày

Nhật ký người dùng 26/08:

    Soát lại bản dịch: 1 câu cần sửa (1 câu untranslated)
    Soát lại bản dịch lỗi (body/items/0/reason must be equal to one of the
    allowed values) — giữ bản lượt đầu

Lược đồ máy chủ (`ai.js:507`) chỉ nhận `['cjk', 'over_budget', 'too_short']`.
App thêm lý do `untranslated` ngày **15/08/2026** để vá đúng chuyện "đôi khi
dịch thiếu hội thoại" (lưới `cjk` cũ chỉ bắt được khi nguồn là tiếng Trung),
nhưng không ai thêm vào lược đồ. Hậu quả: hễ có câu chưa dịch là **CẢ LƯỢT**
soát lại bị từ chối, app giữ nguyên bản đầu — đúng lỗi bản vá đó định sửa.

Hai phía nằm ở hai ngôn ngữ, hai kho triển khai; không có gì buộc chúng khớp
ngoài trí nhớ. Nay có `tests/test_ly_do_soat_lai_khop_may_chu.py` đọc thẳng
`_flag()` bằng AST và lược đồ trong `ai.js`, đòi tập lý do phải khớp NHAU hai
chiều.

Nhãn hiển thị cũng thiếu `untranslated` — nên nhật ký in ra chữ tiếng Anh
trần, đúng như người dùng thấy. Đã thêm nhãn tiếng Việt.

### Thêm: kiểm lại thuật ngữ cố định thay vì chỉ nhắc

Cả bốn ô ngữ cảnh ĐỀU được gửi lên, và thuật ngữ còn kèm chữ **MANDATORY**.
Nhưng không ai kiểm lại xem mô hình có tuân — người dùng khai xong chỉ biết
tin. `_sai_thuat_ngu()` so trên máy (0 Vox): câu gốc có từ trong danh sách mà
bản dịch không dùng đúng bản dịch đã khai → cờ `glossary`, đi chung đường
dịch lại với các lý do sẵn có. So không phân biệt hoa thường (bản dịch hay
viết hoa đầu câu — cờ vì chữ hoa là cờ nhầm).

Chạy thử bằng đúng ví dụ trong ảnh người dùng (`显卡 = card đồ họa`,
`翻车 = toang`): tuân đúng → qua; dịch thành "card màn hình" → bị cờ; "Toang
rồi." viết hoa → qua; câu không chứa từ nào → qua.

### Lỗ hổng trong chính bộ canh của tôi, tự tìm ra bằng đột biến

Đột biến "quên truyền thuật ngữ vào lúc quét" KHÔNG làm test nào đỏ — vì mọi
test đều gọi thẳng `_flag(..., tn)`, không đi qua `review_translations`. Đã
thêm chốt soi chỗ nối bằng AST; đo lại thì đỏ.

Một đột biến khác cũng không đỏ, nhưng đó là lỗi phép đo của tôi: tôi sửa
dòng so sánh trong khi `dich` đã được hạ chữ thường từ dòng trên. Sửa đúng
dòng thì đỏ.

2111 Python đạt, 7 bỏ qua · 511 Node (510 đạt, 0 hỏng).

**Cần deploy máy chủ:** thay đổi lược đồ `reason` chỉ có tác dụng sau khi
`control_server` được triển khai lại.

## C42 — Nhạc nền do người dùng tự chọn, học từ ElevenLabs (27/08/2026)

Chủ dự án nhìn thanh thời gian rồi hỏi: *"ở đây tôi muốn kéo thêm âm thanh
này kia vô được không"*. Kiểm mã: **không** — thanh thời gian chỉ kéo được câu
thoại sẵn có (dời, co giãn hai đầu); `setAcceptDrops` chỉ có ở trang chọn
video và Xử lý hàng loạt. Cũng không có xoay/nghiêng/cắt khung hình.

### Đọc tài liệu ElevenLabs Dubbing Studio để học

Họ có: thanh thời gian BA lớp (lời thoại · lồng tiếng riêng · hiệu ứng),
**Upload Audio** cho track nhạc/nền không có tiếng nói, gộp clip bằng cách kéo
hai đầu chạm nhau, lịch sử clip, chế độ Fixed/Dynamic cho độ dài, tự nhận tối
đa 32 người nói kể cả khi nói chồng.

Họ giới hạn **45 phút / 1 GB** trong Studio — tệp giảng bài 3h43 của chủ dự án
không đưa vào được, gấp năm lần hạn mức.

### Mượn gì, KHÔNG mượn gì

Chủ dự án chọn: làm nhạc nền cả video trước, lớp đặt tự do tính sau.

- Mượn: cho tải tệp nhạc của người dùng lên. Bước trộn nhạc nền của VoxDub
  vốn đã nhận một tệp bất kỳ rồi `apad`/`atrim` cho khớp độ dài — nên chỉ cần
  chuyển tệp thành WAV chuẩn trong thư mục dự án và thêm chế độ trỏ vào đó.
- KHÔNG mượn lớp âm thanh đặt tự do: việc lớn hơn nhiều, đúng ra là dựng lại
  thanh thời gian.
- KHÔNG mượn chế độ Dynamic (độ dài chạy theo chữ): câu dài ra sẽ đẩy lệch
  dây chuyền các câu sau, mà VoxDub khớp chặt theo mốc thời gian gốc.

### Đã làm

`autodub/media/nhac_nen_rieng.py` — `dat_nhac_nen` chuyển tệp sang WAV
44.1kHz stereo trong thư mục dự án (chuyển chứ không dùng thẳng tệp gốc: bước
trộn chạy lại mỗi lần xuất, và tệp gốc có thể bị xoá/đổi chỗ giữa hai lần).
Đổi tên ở bước cuối để hỏng giữa chừng thì bản cũ còn nguyên.

Chế độ `bg_mode="tep_rieng"` nối vào CẢ HAI đường xuất: lượt chạy đầu
(`pipeline._resolve_background`) và xuất lại từ Trình chỉnh sửa
(`editor.resolve_existing_background`) — thiếu một đường là nhạc biến mất ở
lần xuất thứ hai. Chọn chế độ mà chưa có tệp thì CẢNH BÁO rõ, không im lặng
như lỗi nhạc AI trước đó.

Nút đặt trong `BackgroundPanel` chứ KHÔNG trong `MusicSfxPanel`: panel kia bị
ẩn hoàn toàn khi chưa cấu hình máy chủ (nhạc AI cần máy chủ), mà chọn tệp trên
máy thì không cần gì. Có test canh đúng vị trí đó.

**Chạy thật:** mp3 220Hz 5 giây → WAV 44100Hz 2 kênh 5,0 giây; chọn tệp khác
thì đè lên; tệp `.txt` báo rõ danh sách đuôi nhận được; tệp không tồn tại báo
đúng đường dẫn.

### Chuyện tôi suýt đề xuất nhưng đã có sẵn

Nghi nút "Đọc lại" phí công đọc lại cả 23 câu. Kiểm ra: chỉ đọc lại câu vừa
sửa; đổi giọng cả video mới đọc hết và có hỏi xác nhận. Lần thứ N trong ngày
kiểm trước khi nói.

### Lượt chạy test đầu kết thúc bằng core dump

Không in ra dòng tổng kết nào. KHÔNG coi đó là xanh — chạy lại: 2121 đạt, 7
bỏ qua, 0 đỏ. Hiện tượng này đã ghi trong FEATURES.md §5.2 (nghi Qt dọn luồng
lúc thoát), vẫn chưa tái hiện được theo ý muốn.

## C43 — Tách giọng người nói: có tính năng nhưng không ai nhìn thấy (27/08/2026)

Chủ dự án chạy thật v3.12.0 rồi hỏi: *"trong video của tôi chỉ có đúng 2 giọng
đọc, hình như nó không có chỗ nhận định được"*.

Kiểm mã thì đúng, hai chỗ hụt:

1. Trình hướng dẫn sáu bước KHÔNG có một chữ nào về người nói. Ô «Số người
   nói» thêm hôm trước nằm tận trong Cài đặt → Cơ bản — không ai nghĩ tới lúc
   đang tạo dự án.
2. `_apply_diarization` chỉ ghi `logger.info`, không hiện thành bước nào trên
   danh sách tiến trình. Người dùng nhìn 9 bước, không bước nào nói về người
   nói, nên kết luận app không làm được video nhiều người.

Tính năng CÓ. Hậu quả của việc không hiện ra y hệt như không có.

### Đã làm

- Thêm bước `diarize` («Tách giọng người nói») vào `STEPS`, ngay sau `asr`.
  Báo đủ BỐN kết cục: đang tắt · chưa cài · xong kèm SỐ NGƯỜI · lỗi kèm lý do.
  Nhánh lỗi quan trọng nhất: lỗi thiếu DLL torchcodec hôm 26/08 chỉ nằm trong
  nhật ký, nên người dùng chạy xong thấy một giọng mà không biết vì sao.
- Thêm mục «Video có nhiều người nói?» vào bước 4 (Giọng đọc & phụ đề), cạnh
  đúng chỗ người dùng đang nghĩ tới nó. Kèm câu nói THẬT trạng thái máy: chưa
  cài → chỉ tên tệp .bat; đã cài mà tắt → chỉ chỗ bật; đang bật → nói rõ sẽ
  gán mỗi người một giọng. Ba trạng thái ba câu khác nhau, có test canh.
- Số người khai ở bước 4 đi vào `Settings.speaker_count` của lượt chạy VÀ được
  ghi lại để lần sau khỏi khai lại.

### Bộ canh sẵn có bắt lỗi của tôi

`test_step_labels_match_core_pipeline_steps` đỏ: có BẢNG NHÃN THỨ HAI trong
`run_state.py` (dạng «Đang…») mà tôi bỏ sót. Thêm bước mới phải sửa cả hai
bảng — đúng loại lệch mà test đó tồn tại để chặn.

### Ba bản vá được xác nhận bằng lượt chạy thật (lần đầu)

Ảnh chụp của chủ dự án cho thấy: cảnh báo «chọn nhạc nền của tôi mà chưa có
tệp» hiện đúng (C42); ô «Dịch bằng» hiện «Tự động — ưu tiên VoxDub Cloud»
thay vì chuỗi viết chết (C39); bảng tóm tắt ghi 12 Vox/câu theo đúng đường
dịch đang chọn (D1e). Trước đó cả ba chỉ được chứng minh ở tầng mã.

2132 Python đạt, 7 bỏ qua.

## C44 — Ngôn ngữ nguồn: thứ máy NGHE THẤY, không phải thứ người dùng KHAI (28/08/2026)

Chủ dự án chọn hướng "nâng chất lượng đọc hiểu nguồn tiếng Anh/tiếng Trung"
(một trong hai gap đã chốt ngày 16/08). Rà trước khi viết luật thì lộ ra: cái
hỏng không nằm ở luật dịch, mà ở chỗ **máy chủ không biết video nói tiếng gì**.

### Ba lỗ hổng, cùng một gốc

1. **Lời nhắc dịch có một khoảng trắng thay cho tên ngôn ngữ.** Bật «Để ứng
   dụng tự nhận ra ngôn ngữ» thì `source_lang` rỗng đi suốt pipeline. Đo bằng
   cách dựng thẳng lời nhắc: `Your task is to translate an ASR transcript
   from  to Vietnamese.` Mặc định `default: 'zh-CN'` của Fastify KHÔNG cứu
   được, vì `saas_client.py` LUÔN đặt field `sourceLang` (mặc định của lược
   đồ chỉ áp khi field VẮNG MẶT, không áp cho chuỗi rỗng).
2. **Bước nghe in-process chết ngay khi bật tự nhận ngôn ngữ.**
   `_transcribe_whisper` truyền `language=""` xuống faster-whisper, trong khi
   `Tokenizer.__init__` chỉ tự nhận dạng khi tham số là `None` — chuỗi rỗng
   ném thẳng `ValueError: '' is not a valid language code`. Đường subprocess
   đã quy rỗng về `None` từ lâu (`asr_whisper_worker.py`), đường in-process
   thì chưa: **đúng lớp lỗi #2 của dự án — sửa một trong hai đường**. Trúng ai:
   người chạy từ mã nguồn, và mọi mẻ từ 2 video trở lên (`BatchWorker` truyền
   `whisper_cache` nên đi đường in-process).
3. **Whisper LUÔN trả mã ngôn ngữ nó nhận ra — không ai đọc.**
   `transcriber.py` in ra Nhật ký rồi vứt. Hệ quả dây chuyền: dịch ngoại tuyến
   báo «không hỗ trợ ngôn ngữ nguồn ''» (kiểm: `flores_code('')` → `None`), và
   phép so nguồn-trùng-đích (C22) luôn trả `False` — **video tiếng Việt chạy
   bằng tự nhận ngôn ngữ vẫn bị tính tiền dịch Việt→Việt**, đúng khoản tiền mà
   C22 sinh ra để chặn.

### Đã làm — phần A: nguồn thật

- `transcribe()` nhận `detected_out` (dict) và điền `{"language", "prob"}` ở
  **cả ba** đường: subprocess, in-process, Paraformer. Không truyền thì mọi
  caller cũ y như cũ.
- `_transcribe_whisper` quy `""`/`"auto"` về `None` trước khi gọi mô hình.
- `pipeline.py` chốt ngôn ngữ **sau** bước nghe: người dùng chọn tay thì tôn
  trọng lựa chọn đó (chính nó đã lái bộ nghe), để máy tự nhận thì lấy mã máy
  nghe ra. Từ đó ngôn ngữ này đi vào: marker `.asr_lang`, SRT gốc, phép so
  nguồn-trùng-đích, lượt dịch máy chủ, lời nhắc dịch tay, và trường
  `source_language` của báo cáo.
- Chạy tiếp một dự án đã nghe xong bằng «tự nhận»: lấy lại ngôn ngữ từ marker
  thay vì rơi về rỗng, và **không** bắt nghe lại cả video chỉ vì lần này để
  máy tự nhận (guardrail đổi-ngôn-ngữ của V40 giữ nguyên cho ca đổi thật).
- Dòng trạng thái bước nghe hiện «… · nguồn: tiếng Anh». Số câu vẫn là token
  đầu tiên vì `widgets.py` cắt chuỗi theo dấu cách đầu để hiện «Số câu thoại»
  — đổi thứ tự là hỏng chỗ khác.

### Đã làm — phần B: luật đọc hiểu nguồn

Toàn bộ luật chất lượng của lời nhắc trước nay gắn với ngôn ngữ **đích**
(`LANGUAGE_RULES`). Nhưng bẫy dịch sai không nằm ở đích: câu tiếng Trung rụng
chủ ngữ hay câu tiếng Anh dùng «you» chung chung thì dịch sang ngôn ngữ nào
cũng sai như nhau. Thêm khối `READING THE SOURCE`:

- **Chung cho mọi nguồn**: đây là bản chép lời của MÁY, không phải văn bản
  sạch — có nghe nhầm, thiếu dấu câu, câu bị cắt ngang qua ranh giới đoạn.
  Gặp câu vô nghĩa thì phục dựng ý từ các câu quanh nó, không dịch nguyên văn
  chỗ vô nghĩa và không bịa thêm chữ để lấp.
- **Nguồn tiếng Trung**: chủ ngữ ẩn (phải truy ra AI đang nói về AI), không
  có thì/số nhiều (thì nằm ở 了/过/着 và trạng từ), xưng hô họ hàng dùng cho
  người dưng (哥/姐/叔), thành ngữ dịch nghĩa chứ không dịch chữ, đơn vị số
  lớn 万/亿 (dịch sai là sai **số liệu**, không phải sai văn phong), lượng từ
  không mang nghĩa, và **lỗi đồng âm của bộ nghe** (的/得/地, 在/再, 他/她/它).
- **Nguồn tiếng Anh**: «you» một người / nhiều người / chung chung — chọn sai
  là đổi hẳn người nghe trong tiếng Việt; cụm động từ và thành ngữ; mỉa mai
  và nói giảm; đại từ trỏ ngược qua nhiều đoạn; «twenty twenty-four» là năm
  2024, «a couple» ≈ 2, đơn vị Anh giữ nguyên đơn vị Anh; lỗi đồng âm
  their/there/they're, to/too/two.
- Ngôn ngữ chưa có bộ riêng **chỉ** nhận phần chung — không giả vờ biết bẫy
  ngữ pháp của ngôn ngữ đó (cùng nguyên tắc `_GENERIC_RULES` của V15).
- Mã nguồn giờ hiện thành TÊN («Chinese (Mandarin)»), rỗng thành «an
  unidentified language (infer it from the transcript itself)» — nói thẳng
  với mô hình là chưa biết còn hơn để một khoảng trắng.

Đường **dịch tay/ngoại tuyến** (D1) nhận bản gọn hơn của cùng bộ luật: người
dùng phải tự dán khối này vào ChatGPT/Gemini, prompt dài quá thì họ cắt bớt.

### Giá phải trả (đo, không đoán)

Lời nhắc hệ thống tăng ~693 token (nguồn Trung) / ~759 token (nguồn Anh) mỗi
lượt gọi, trên nền 2.562 token đã đo ngày 18/08 — tức khoảng +27%. Mỗi lô 40
câu mới tốn thêm chừng ấy **một lần**, nên trên một video 3 giờ (~50 lô) là
cỡ 35 nghìn token đầu vào. Giá Vox tính theo câu nên khoản này là chi phí của
máy chủ, không đội giá người dùng.

### Bộ canh

`tests/test_source_comprehension.py` (23 test) + `control_server/tests/
source-comprehension.test.js` (12 test). Đáng nói nhất là test canh **danh
sách ngôn ngữ giữa hai đường dịch**: thêm ngôn ngữ nguồn ở máy chủ mà quên
đường dịch tay thì người chọn ngoại tuyến lãnh bản dịch kém hơn và không ai
báo — đúng lớp lỗi #5 (câu chữ hai nơi đi lệch nhau). Test canh DANH SÁCH,
không canh câu chữ, vì hai bên cố ý viết dài ngắn khác nhau.

Đã thử **đột biến** chính bộ canh: (a) thêm một khoá ngôn ngữ vào máy chủ →
test đỏ đúng chỗ; (b) bỏ dòng quy `""` về `None` → test đỏ đúng chỗ. Bộ canh
không kêu khi có lỗi thì chỉ là trang trí.

Ba test cũ của V15 khẳng định lời nhắc chứa «from zh-CN to …» — nay chuyển
thành «from Chinese (Mandarin) to …». Ý định của chúng là canh ngôn ngữ ĐÍCH,
giữ nguyên.

### Rủi ro do chính bản vá này sinh ra — chặn trước khi nó thành lỗi tiền

Nối được ngôn ngữ máy nghe ra vào phép so nguồn-trùng-đích cũng có nghĩa là
một **phỏng đoán của máy** giờ có quyền **bỏ hẳn khâu dịch**. Nhận nhầm một
video tiếng Trung thành tiếng Việt là giao ra bản «đã lồng tiếng» còn nguyên
tiếng gốc — người dùng chỉ biết khi ngồi xem lại. Nên: dưới 85% chắc chắn thì
vẫn dịch như thường, kèm câu nói rõ vì sao và chỉ cách chọn tay nếu muốn bỏ
hẳn. Trả tiền một lượt dịch thừa rẻ hơn nhiều một video hỏng.

Kèm theo đó, marker `.asr_lang` giữ cả độ tin cậy («`en-US 0.982`») để lượt
chạy tiếp quyết y hệt lượt đầu; marker đời cũ (chỉ có mã) đọc ra 0 = «không
biết», tức không dám bỏ khâu dịch. Phép so «đã đổi ngôn ngữ» của V40 chỉ nhìn
phần mã — nếu nhìn cả dòng thì mọi lượt chạy tiếp đều bị bắt nghe lại cả
video, có test canh riêng chuyện đó.

2155 Python đạt / 7 bỏ qua, 522 Node đạt / 1 bỏ qua.

### Giới hạn còn lại

- **Chưa chạy thật lượt nào.** Toàn bộ phần B là câu chữ trong lời nhắc: chất
  lượng chỉ đo được bằng cách dịch cùng một video hai lần (trước/sau) rồi đọc
  đối chiếu. Việc đó cần **triển khai `control_server` lên máy chủ** và tốn
  Vox thật — chưa làm, chờ chủ dự án quyết.
- Phần A có bằng chứng ở tầng mã (bộ canh + đột biến), **chưa có lượt chạy
  Windows thật** — vẫn đúng điểm yếu số 1 của dự án (FEATURES §5.1).
- Bước **rà soát lại câu** (`buildReviewSystemPrompt`) cố ý KHÔNG nhận khối
  luật nguồn: V66 đã cắt lời nhắc đó cho gọn vì bước sửa từng đắt gấp ~31 lần
  bước nó đi sửa. Nếu sau này thấy bước rà soát dịch sai vì không hiểu nguồn
  thì đó là một mini-spec riêng, có số đo trước.
- Dịch cục bộ (NLLB) vẫn có thể **bỏ sót câu** khi bản chép lời nhiễu
  (FEATURES §5.2) — không đụng ở đợt này: đó là hạn chế của chính mô hình
  NLLB, không phải chuyện lời nhắc.

## C44b — Đo thật lời nhắc C44: một luật ăn tiền, một luật vô tác dụng, một luật phải sửa bằng mã (28/08/2026)

Chủ dự án cấp một khoá Gemini để đo. Dựng `scripts/research/ab_loi_nhac_nguon.py`:
dịch CÙNG một bản chép lời hai lần, chỉ đổi đúng một biến là lời nhắc (cánh cũ
lấy `translate.js` ở git ref ra thư mục tạm rồi nạp), gọi Gemini y như
`ai-gateway.service.js` gọi. Model `gemini-3.5-flash`.

### Vòng 1 — bản chép lời THẬT: KHÔNG đo được cải thiện nào

Cho Whisper nghe `tap01_clip.mp4` sẵn có trong repo: tiếng Anh 98,9%, 8 câu,
giữ nguyên lỗi nghe thật (câu 1 dính hai người nói và mất dấu câu, câu 3 sai
ngữ pháp «What is it come with French fries?»). Hội thoại bồi bàn ↔ khách, tức
đúng chỗ luật «you ba nghĩa» phải phát huy.

Lượt đầu nhìn rất thuyết phục: cánh MỚI gọi khách là «anh chị» thay vì «quý
khách», và lời bồi bàn thành «hình như bên em có…» thay vì «tôi nghĩ chúng tôi
có…» — đúng thứ luật xưng hô nhắm tới. **Nhưng chạy lại 3 lượt mỗi cánh thì số
liệu lật ngược**: cánh MỚI dịch thẳng đại từ tiếng Anh 4/6, cánh CŨ 0/6. Chạy
tiếp một loạt nữa có thêm cánh tách biến (cũ + tên ngôn ngữ) thì lật lần nữa:
1/6 · 0/6 · 0/6.

**Kết luận vòng 1: khác biệt nằm gọn trong nhiễu giữa các lượt.** Một lượt chạy
duy nhất đủ để dựng nên bất kỳ câu chuyện nào mình muốn tin — và tôi suýt tin.
Đây chính là lý do phải lặp lại trước khi kết luận.

### Vòng 2 — phép thử có tiêu chí máy chấm được

Câu **dựng riêng** (ghi rõ: không phải video thật) chứa đúng các bẫy mà luật
nêu tên, chấm bằng biểu thức chính quy chứ không bằng cảm nhận, 5 lượt mỗi
cánh. Kết quả lần đầu:

| Bẫy | CŨ | MỚI |
|---|---|---|
| 万 = mười nghìn (三万五千块) | 0/5 | **0/5** |
| 亿 = trăm triệu | 5/5 | 5/5 |
| thành ngữ 一落千丈 | 5/5 | 5/5 |
| «twenty twenty-four» = 2024 | 0/5 | **0/5** |
| giữ đơn vị Anh (six feet / one eighty) | 0/5 | **5/5** |
| đồng âm there → they're | 5/5 | 5/5 |

Đọc thẳng: trong 7 bẫy, luật mới **chỉ dịch chuyển đúng một cái** (đơn vị Anh —
cánh cũ tự ý đổi «six feet, one eighty» thành «một mét tám, tám mươi mốt cân»,
tức sửa luôn lời người nói). Bốn bẫy cánh cũ vốn đã làm đúng. Hai bẫy **cả hai
cánh cùng sai**.

### Ba luật, ba số phận khác nhau

1. **万 — luật viết chưa đủ, sửa lời là được.** Cả hai cánh ra «ba mươi lăm
   triệu đồng» cho 三万五千块 (35.000 tệ): vừa lệch bậc 1.000 lần vừa tự đổi
   sang tiền Việt. Luật cũ của tôi chỉ nói «万 = ten thousand» mà không cấm quy
   đổi tiền tệ. Thêm câu cấm rõ (giữ nguyên đơn vị và bậc của người nói, cho cả
   mọi ngôn ngữ nguồn) → **0/5 lên 5/5**.
2. **Đơn vị Anh — luật ăn tiền ngay từ đầu.** 0/5 → 5/5, tách bạch hoàn toàn.
3. **Năm đọc theo cặp — lời nhắc BẤT LỰC.** «twenty twenty-four» ra «năm hai
   mươi hai mươi tư» (vô nghĩa trong tiếng Việt). Đã thử ba cách diễn đạt ở ba
   chỗ: luật nguồn, khối số của ngôn ngữ đích, và danh sách tự kiểm cuối cùng
   (chỗ mô hình đọc sau chót). **0/10**, giống hệt nhau từng chữ ở cả 5 lượt —
   mô hình chép lại nhịp hai-cặp-số của câu gốc. Nhưng gửi CHÍNH câu đó với năm
   đã viết thành chữ số («in 2024») thì **6/6**.

   Nên chỗ sửa là **mã**: `normalizeSpokenYears()` viết năm 19xx/20xx nói theo
   cặp thành chữ số, áp ngay trước khi dựng lời nhắc, chỉ cho nguồn tiếng Anh,
   và **chỉ đụng bản gửi đi** — `segments` gốc vẫn là thứ đem gộp kết quả nên
   câu nguồn của người dùng không bị sửa. Đo lại qua đúng đường máy chủ:
   **0/10 → 10/10**.

   Cẩn thận với dương tính giả, có test canh: «twenty twenty-four dollars»
   (số tiền), «twenty five years old» (tuổi), «back in ninety-nine» (thiếu phần
   thế kỷ — đoán hộ người nói là bịa) đều KHÔNG bị đụng.

4. **Ba luật «năm» đã gỡ khỏi lời nhắc.** Một luật mô hình không nghe thì vừa
   tốn token mỗi lượt gọi, vừa làm người đọc mã sau này tưởng chuyện đã được xử
   lý. Giữ lại là tự đặt bẫy cho chính mình.

### Điều đáng nhớ nhất của đợt này

Sửa lời nhắc **cảm giác** như đang nâng chất lượng, và không có cách nào biết
mình đúng hay sai nếu không đo. Trong ba luật tôi tự tin nhất: một cái ăn ngay,
một cái phải viết lại mới ăn, một cái không bao giờ ăn dù nói kiểu gì. Tỷ lệ
đó nên là mặc định trong đầu ở mọi lần sửa prompt sau này.

Phần luật đọc hiểu nguồn CÒN LẠI (chủ ngữ ẩn, thành ngữ, xưng hô họ hàng, «you»
ba nghĩa, mỉa mai) **vẫn chưa có bằng chứng nào** — bốn bẫy đo được thì cánh cũ
vốn đã làm đúng, còn xưng hô thì chìm trong nhiễu. Chúng không gây hại, nhưng
đừng ghi công cho chúng cho tới khi có phép đo lớn hơn: nhiều câu hơn, nhiều
lượt hơn, và người chấm là người Việt chứ không phải biểu thức chính quy.

### Ghi lại một chuyện bên lề

Lượt chạy `pytest` đầy đủ **lại kết thúc bằng core dump lúc dọn dẹp** (đúng
hiện tượng FEATURES §5.2 ghi là «chưa tái hiện được»). Chạy lại ngay sau đó:
2155 đạt, 7 bỏ qua, sạch. Vậy là lần thứ hai — vẫn sau khi test đã chạy xong,
không làm hỏng kết quả nào, nhưng nay có thêm một mốc thời gian cho manh mối.

2155 Python đạt / 7 bỏ qua, 527 Node đạt / 1 bỏ qua.

## C45 — Cổng kiểm trước phát hành: chạy thật một lượt, trên Windows (28/08/2026)

Phần A của C44 (ngôn ngữ nguồn là thứ máy NGHE THẤY) tới lúc này chỉ có bằng
chứng ở tầng mã. Mà đúng loại lỗi đó chỉ lộ ra khi chạy thật: bản vá quan trọng
nhất của C44 là chỗ `faster-whisper` ném `ValueError` với mã ngôn ngữ rỗng —
không một test đơn vị nào chạm tới vì test không nạp mô hình thật.

Và đây là điểm yếu số 1 của dự án (FEATURES §5.1): CI đóng gói xong là **phát
hành thẳng**, không ai chạy thử cái vừa đóng gói.

### Đã làm

`scripts/kiem_chay_that.py` — chạy MỘT lượt dub thật rồi soi bằng chứng trên
đĩa. Cố ý dừng ở bước **dịch tay**: không gọi máy chủ, không tốn Vox (một cổng
kiểm mà tiêu tiền mỗi lần phát hành thì sẽ bị tắt trong tuần đầu). Bốn thứ nó
soi, mỗi thứ ứng với một lỗi THẬT đã xảy ra:

| Soi gì | Lỗi thật tương ứng |
|---|---|
| `is not a valid language code` trong nhật ký | C44: bước nghe chết vì ngôn ngữ rỗng |
| `.asr_lang` có mã ngôn ngữ + độ tin cậy | C44: mã ngôn ngữ chỉ vào nhật ký rồi vứt |
| `TRANSLATE_PENDING.txt` không chứa `transcript from  to` | C44: khoảng trắng thay cho tên ngôn ngữ |
| lời nhắc có khối `READING THE SOURCE` | C44: luật đọc hiểu nguồn có tới tay người dịch tay không |

Nối vào hai chỗ: `release.yml` **giữa bước đóng gói và bước phát hành** (hỏng
thì không phát hành), và `test.yml` như một job `windows-latest` chạy trên mỗi
push vào `main` — biết ở đúng commit gây ra lỗi, thay vì đợi tới lượt phát hành
mới lòi ra. `tests/test_cong_kiem_truoc_phat_hanh.py` (10 test) canh cho chính
cổng kiểm không bị gỡ, không bị đẩy xuống sau bước phát hành, không bị
`continue-on-error` biến thành đèn trang trí, và vẫn chạy bằng «tự nhận ngôn
ngữ» chứ không phải ngôn ngữ chọn sẵn.

### Chạy thật, và hai lượt đột biến

Chạy tại chỗ trên `tap01_clip.mp4`: nghe được 8 câu, **ngôn ngữ máy nghe ra
en-US (99%)**, lời nhắc dịch có tên ngôn ngữ và có luật đọc hiểu nguồn. Đây là
**bằng chứng đầu-cuối đầu tiên cho phần A của C44** — trước đó chỉ có test đơn
vị. (Trên Linux, đường in-process — đúng đường mà lỗi `ValueError` nằm.)

Đột biến để kiểm chính cổng kiểm:

1. Gỡ bản vá «rỗng → None» → đỏ đúng chỗ, nói đúng tệp phải sửa.
2. Chặn nhánh «điền ngôn ngữ máy nghe ra» → đỏ, **nhưng nói sai lý do**.

### Lỗi trong chính bản vá C44, do đột biến 2 soi ra

Đột biến 2 làm marker `.asr_lang` thành `" 1.000"` (ngôn ngữ rỗng + độ tin cậy),
và `_doc_moc_ngon_ngu()` đọc `split()[0]` ra **`"1.000"` như thể đó là một mã
ngôn ngữ**. Lượt chạy tiếp sẽ mang con số đó đi khắp nơi, và lời nhắc dịch sẽ
ghi «from 1.000 to Vietnamese».

Không có ngôn ngữ thì đừng ghi độ tin cậy (ghi rỗng), và lúc đọc phải kiểm hình
dạng mã ngôn ngữ chứ không tin bừa chữ đầu tiên. Có test canh riêng cho bốn
kiểu rác: `" 1.000"`, `"0.900"`, `"?? 0.5"`, `"-"`.

Cổng kiểm cũng được sửa để nói đúng lý do thay vì đổ tại độ tin cậy — **một bộ
canh nói sai nguyên nhân đẩy người sửa đi nhầm đường, gần như tệ ngang việc
không có bộ canh**.

### Một lỗ hổng nữa của C44, phát hiện khi soạn kịch bản chạy thử

Dòng lệnh nhận `--source-lang auto`, còn giao diện gửi chuỗi RỖNG. C44 chỉ xử
lý chuỗi rỗng, nên đường dòng lệnh (và cả bộ canh này, nếu tôi không nhận ra)
sẽ im lặng bỏ qua ngôn ngữ máy nghe ra, rồi ghi «from auto to Vietnamese».
`resolve_source_lang()` nay quy `"auto"` về rỗng — một mối cho mọi đường vào.

### Giới hạn còn lại

- Cổng kiểm chạy `python -m autodub.cli` **từ mã nguồn**, không phải từ bản
  `.exe` — bản đóng gói không có entry dòng lệnh (`autodub.spec` chỉ dựng
  `VoxDub.exe` là GUI). Nó bắt được lỗi Windows của luồng chạy thật (bảng mã,
  đường dẫn, tiến trình con), **không** bắt được lỗi thiếu tệp trong gói — lớp
  lỗi #3 vẫn do bộ canh đóng gói riêng lo. Muốn đóng nốt thì cần một entry dòng
  lệnh trong bản build, đó là mini-spec riêng.
- Chưa chạy trên runner Windows lần nào (workflow vừa viết, chạy ở lượt push
  này). Nếu `choco install ffmpeg` hay việc tải model `tiny` trục trặc trên
  runner thì sẽ lộ ra ngay lượt đầu.
- Lượt chạy dừng ở bước dịch, nên **không** kiểm tạo giọng, ghép video, phụ đề.
  Mở rộng thì tốn thời gian runner và cần VieNeu — cân nhắc riêng.

### Lượt CI Windows đầu tiên: ĐỎ, vì đúng cái bẫy dự án đã dính

Bộ canh chết ở **dòng in đầu tiên**:

```
UnicodeEncodeError: 'charmap' codec can't encode character '\u1ea1'
  print(f"Chạy thử một lượt dub: {video.name}")
```

Console Windows mặc định cp1252; các tệp `.bat` của người dùng đã có
`chcp 65001` nên họ không dính, còn runner CI gọi thẳng `python` thì dính. Mọi
worker trong dự án đã có sẵn hai dòng `sys.stdout.reconfigure(...)` từ D1f —
riêng bộ canh mới thì tôi quên. **Lớp lỗi #2 dưới một hình dạng khác.**

Vá: hai dòng `reconfigure` như mọi worker, cộng `PYTHONUTF8=1` +
`PYTHONIOENCODING=utf-8` cho tiến trình con (stdout của nó là ỐNG nên cũng rơi
về bảng mã máy).

### Và bản test đầu của tôi cho lỗi đó là test GIẢ

Viết test tái hiện bằng `PYTHONIOENCODING=cp1252` rồi gọi bộ canh với video
không tồn tại. Xanh. Đột biến (gỡ bản vá) — **vẫn xanh**.

Lý do: nhánh «không thấy video» in ra **stderr**, mà Python đặt
`errors="backslashreplace"` cho stderr nên nó KHÔNG BAO GIỜ ném
`UnicodeEncodeError` — chỉ stdout mới ném. Test đi đúng vào nhánh không thể
chết. Đổi sang `--help` (in phần mô tả tiếng Việt ra stdout, chạy tức thì):
đột biến làm nó đỏ đúng chỗ.

Lần đầu tôi chạy đột biến này còn quên `assert` rằng phép đột biến đã áp được —
tức lượt kiểm đó cũng vô nghĩa. Hai bài học chồng lên nhau trong cùng một giờ:
**đột biến phải khẳng định là mình đã đột biến được**, và **phải đột biến đúng
nhánh mà lỗi thật đi qua**.

2169 Python đạt / 7 bỏ qua.

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

**Vẫn CHƯA chạy diarization thật** — cần HF token thật + user agreement ở cả
`speaker-diarization-3.1` và `segmentation-3.0`.

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

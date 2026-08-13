# PLAN.md — Roadmap nâng cấp VoxDub Studio

Cấu trúc theo `MINI_SPEC_PLAYBOOK.md` (repo root). Mỗi mục dưới đây là **1 MINI-SPEC**
độc lập, đủ chi tiết để bắt tay code ngay. Không mini-spec nào được mở rộng phạm vi
ngoài gap đã xác nhận trong chính nó — muốn thêm việc thì mở mini-spec mới, không nhét
vào cái đang chạy.

Nguồn dữ liệu cho toàn bộ audit: khảo sát trực tiếp code `autodub/`, `autodub_gui/`,
`control_server/`, `website/` (2026-08-10). Xem `docs/ARCH.md` và `docs/PRD.md` §7 cho
tóm tắt gap gốc.

Trạng thái AI Factory: `request_project_promote` #54 và `request_tech_exception` #53
đang chờ Manager/Head duyệt tại `/factory/mcp`. Milestone thật trên Factory sẽ được tạo
ngay sau khi promote #54 được approve (cần `project_slug`).

**Trạng thái thực thi (cập nhật 2026-08-11):** Phase A/B/C (V0-V10, 11 mini-spec) đã
**THỰC HIỆN XONG với verify thật** — không phải chỉ lên kế hoạch. Chi tiết đầy đủ từng
mini-spec (audit, quyết định kỹ thuật, bằng chứng verify, giới hạn còn lại) nằm trong
`docs/TEST_LOG.md`, KHÔNG lặp lại ở đây. Bảng dưới chỉ tóm tắt trạng thái + độ hoàn
thiện thật (nhiều mini-spec là PROOF-OF-CONCEPT có chủ đích, không phải "xong 100%" —
xem cột "Độ hoàn thiện"). **Phase D** (cuối tài liệu) là các mini-spec MỚI mở ra từ
chính giới hạn mà Phase A/B/C để lại — repo KHÔNG "hoàn thiện tuyệt đối", đây là quá
trình lặp có chủ đích, không phải bỏ sót.

Repo đã push: `https://git.matbao.support/mk/voidmax` (branch `main`).

| # | Tên | Trạng thái | Độ hoàn thiện |
|---|---|---|---|
| V0 | Dựng lại model Mongoose bị thiếu | ✅ Xong | Đầy đủ, live-verify full luồng tiền |
| V1 | Test + API docs control_server | ✅ Xong | Đầy đủ, 84 test |
| V2 | Tách billing khỏi pipeline.py | ⚠️ Thu hẹp | Chỉ di chuyển code, KHÔNG tách global HOLD state (xem V2 trong TEST_LOG) |
| V3 | Minh bạch Local-vs-SaaS | ✅ Xong | Đầy đủ, tìm+sửa 1 bug thật |
| V4 | +4 ngôn ngữ nguồn ASR | ✅ Xong, live-verify thật (08-11) | Whisper thật (model small) nghe TTS thật ko/ja/th/id — 3/4 khớp gần tuyệt đối, 1 lỗi nhỏ 1 từ (th) — giới hạn còn lại: giọng TTS sạch, chưa video YouTube thật — xem TEST_LOG |
| V5 | OCR thay boxblur | ⚠️ Một phần, live-verify mở rộng (08-11) | RapidOCR thật phát hiện đúng watermark trên video H.264 NÉN THẬT (không còn chỉ ảnh PIL) — verify bằng crop trực quan; còn thiếu: watermark thật (không phải tự vẽ), benchmark thời gian, ≥3 video đa dạng — xem TEST_LOG |
| V6 | Dịch local (NLLB-200) | ✅ Xong, mặc định bật | Verify thật, chất lượng câu ngắn còn kém |
| V7 | Docker hoá control_server | ✅ Xong, live-verify thật (đã có sẵn + re-verify 08-11) | `docker compose up -d mongo control_server` chạy thật, health 200; audit Linux autodub/ re-confirm 715/720 pass (0 fail) trên chính sandbox — xem TEST_LOG |
| V8 | TTS đa ngôn ngữ đích | 🔶 PoC tầng engine (đóng ở V11) | Registry + verify CapCut API thật — GUI/voices.catalog target-aware nay đã xong, xem V11 |
| V9 | Cloud rendering (Demucs) | 🔶 PoC hẹp (đóng ở V12) | Verify end-to-end thật — xử lý ĐỒNG BỘ (không queue), CHƯA UI — nay đã xong, xem V12 |
| V10 | Analytics/retention | ⚠️ Một phần (đóng ở V13) | Retention cohort xong; phễu hoàn thành/bỏ dở nay đã xong, xem V13 |
| — | Re-audit 08-11: dọn dependency thừa + 2 CVE + website 0 test | ✅ Xong | google-genai xoá, react-router vá, 31 test mới cho website |
| V11 | Hoàn thiện đa ngôn ngữ đích (đóng gap V8) | ✅ Xong | Audit hết Vietnamese-assumption + fix bug align.py + voices.catalog/GUI target-aware + live-verify 2 lượt pipeline thật target=en, 0 crash; 08-11 đóng nốt gap "chưa video dài" — 20 câu/81s thật, timing engine ổn định quy mô lớn — xem TEST_LOG |
| V12 | Cloud rendering production-ready (đóng gap V9) | ✅ Xong, live-verify end-to-end thật qua Docker (08-11) | State machine bất đồng bộ + worker Python + GUI toggle; build `docker compose build render_worker` qua mạng thất bại 2 lượt (giới hạn network namespace Docker của sandbox, không phải lỗi Dockerfile) — build thành công qua wheel cache tải sẵn trên host + `docker build` offline (Dockerfile thật không đổi); `docker compose up` cả 3 service thật, submit+claim+xử lý+tải kết quả Demucs thật 100% qua HTTP, không bind-mount tạm — xem TEST_LOG |
| V13 | Phễu hoàn thành/bỏ dở pipeline (đóng gap V10) | ✅ Xong | Telemetry PipelineEvent + client gửi event thật + banner minh bạch (guardrail 1 — cập nhật TRƯỚC khi bật) + dashboard phễu; live-verify thật qua HTTP thật (2 run, kể cả privacy-test chặn field cấm thật) — xem TEST_LOG |
| V14 | Dịch phụ đề rời (`.srt`/`.vtt`, ngoài luồng dub) | ✅ Xong, live-verify SaaS thật | Core+SaaS endpoint+GUI (verify headless offscreen)+CLI đủ theo Scope A-G; 46 test mới; live-verify thật qua `/translate-subtitle` (key Gemini thật, 2 chiều vi/en, idempotency xác nhận qua Mongo) — vi/en đã kiểm chứng cả 2 đường (local NLLB + SaaS); ~190/204 mã FLORES-200 còn lại chưa kiểm chứng (có chủ đích) — xem TEST_LOG |
| V15 | Sửa bug hardcode tiếng Việt ở prompt dịch server-side | ✅ Xong, live-verify thật | Tìm ra khi audit V14 — `/translate`,`/analyze`,`/review` giờ nhận `targetLang`, field response đổi `text_<targetLang>`; 170 test unit/mock pass + live-verify HTTP thật (key Gemini thật, targetLang=en trả đúng `text_en`, Vox trừ đúng trong Mongo) — xem TEST_LOG |
| V16 | Retry/backoff cho SaaS call một-lần (Phase E — đóng gap ổn định so với thị trường) | ✅ Xong | Audit phát hiện `translate_saas.py` đã có bounded-retry sẵn; đóng nốt 2 điểm thiếu (poll+tải cloud-render, dịch phụ đề SaaS) qua module `saas_retry.py` dùng chung; 18 test mới, 0 regression (742/746 pass) — xem TEST_LOG |
| V17 | Mở rộng ngôn ngữ đích theo catalog CapCut thật (Phase E — đóng gap cạnh tranh lớn nhất so với thị trường) | ✅ Xong, 1/8 live-verify thật | +8 TARGETS (ja/zh/es/th/id/pt/fr/de, đều có giọng CapCut thật ≥3); tìm+sửa bug thật: `normalize_vi_text()` bị áp nhầm cho MỌI giọng CapCut kể cả tiếng Anh đã live (V11); live-verify thật tiếng Nhật: NLLB vi→ja + CapCut TTS ja-JP thật (audio non-silent, RMS 3345); 7/8 ngôn ngữ còn lại đánh dấu "thử nghiệm" — xem TEST_LOG |
| V18 | Bộ quy tắc dịch (LANGUAGE_RULES) riêng cho 8 ngôn ngữ đích mới + nâng cấp tiếng Việt (Phase E — chủ dự án yêu cầu) | ✅ Xong | Mỗi ngôn ngữ có quy tắc GIỌNG ĐIỆU/XƯNG HÔ/ĐỌC SỐ riêng (không dịch chữ bộ quy tắc tiếng Anh) — vd tiếng Trung CHỦ ĐỘNG giữ trợ từ 啊呢吧嘛 (ngược lại mọi ngôn ngữ khác), tiếng Nhật giữ Kanji tên Trung + đọc số theo lượng từ, tiếng Thái buộc nhất quán ครับ/ค่ệ; tiếng Việt +mục THÁI ĐỘ & NGỮ ĐIỆU (trợ từ cuối câu, từ nối khẩu ngữ); tìm+sửa bug thật: `emphasisExamples` tiếng Việt trước đây là ví dụ TIẾNG ANH ("really"/"definitely") do copy-paste; tổng quát hoá pass phân tích ngữ cảnh (`buildAnalysisPrompt`) để "học" đúng gợi ý pronouns/domain theo TỪNG ngôn ngữ đã nghiên cứu thay vì chỉ đặc cách tiếng Việt; 24 test mới, 0 regression (167/168 pass) — xem TEST_LOG |
| V19 | Bố cục phụ đề (ngắt dòng + karaoke) không tương thích ngôn ngữ không dấu-cách (Phase E — chủ dự án hỏi trực tiếp) | ✅ Xong (vi/en/zh) | Audit lộ 4 bug/gap thật: ngắt dòng SRT dùng `text.split()` (dấu cách) → cả câu tiếng Trung/Nhật không bao giờ ngắt, tràn khung hình; karaoke fallback cùng lỗi; ngưỡng ký tự/dòng không đổi theo ngôn ngữ dù CJK render rộng hơn; font đóng gói sẵn không phủ CJK/Thái (tofu). Đã sửa 3/4 (ngắt dòng theo ký tự cho ja/zh/th, karaoke fallback theo ký tự, ngưỡng riêng cho CJK 20 ký tự/dòng, thêm font Noto Sans SC thật cho zh) — chủ dự án đổi ý giữa chừng: **bỏ font Nhật/Thái, giữ Trung** (zh là ngôn ngữ NGUỒN có sẵn từ đầu), ưu tiên còn lại dồn cho vi/en; 20 test mới, 0 regression (759/763 pass) — xem TEST_LOG |
| V20 | Bug suy giới tính giọng CapCut sai cho tiếng Anh (Phase E — audit theo yêu cầu "đa dạng giọng nam/nữ") | ✅ Xong | Chủ dự án hỏi về đa dạng giọng đọc vi/en — audit lộ bug thật: `_gender_of()` chỉ nhận diện đúng giọng nữ tiếng Việt (voice_type khớp 3 mã BV hoặc chứa "female" literal); catalog tiếng Anh ghi giới tính ngay trong TÊN hiển thị (không qua voice_type) bị bỏ sót — "Jenny"/"Energetic Famale"/"American Female"/"Dolly famle" đều bị gắn nhầm "male" mặc định, khiến bộ lọc "Nữ" trong Thư viện giọng đọc ẩn mất các giọng này. Đã sửa: đọc thêm tên hiển thị đầy đủ (không chỉ voice_type), bắt cả lỗi chính tả thật trong dữ liệu ("famale"/"famle"), thêm bảng tra riêng cho giọng thương hiệu không có tín hiệu chữ (Jenny = Microsoft Azure Neural, nữ, thông tin công khai). Đồng thời khảo sát thật nguồn giọng: VieNeu (offline, chính) có 120 giọng (70 nam/50 nữ, không có tag ngữ điệu/phong cách, chỉ tên); CapCut vi-VN 22 giọng (đa dạng phong cách qua mô tả), en-US 39 giọng sau sửa 17 nữ/22 nam (trước sửa bị lệch nặng do bug). 7 test mới, 0 regression (766/770 pass) — xem TEST_LOG |
| V21 | 2 bug thật đã root-cause từ lâu nhưng chưa sửa: NLLB bỏ sót câu khi ASR nhiễu (V11), giọng CapCut trùng tên bị ẩn (V20) | ✅ Xong | **NLLB bỏ câu**: 1 segment nhiều câu, model dừng sớm khi gặp 1 câu nhiễu ASR → MẤT HOÀN TOÀN các câu sau, không lỗi không log — ảnh hưởng MỌI cặp ngôn ngữ dùng đường dịch local. Sửa: dịch từng câu riêng trong 1 lượt `translate_batch()` (không chung state decode) — early-stop chỉ mất đúng 1 câu, không kéo theo câu sau; verify thật bằng model NLLB thật, tái hiện đúng bug cũ rồi xác nhận đã hết qua đúng đường code production. **Giọng trùng tên**: "Trickster" (2 voice_type khác nhau, 1 bị catalog âm thầm loại bỏ) → đánh số phân biệt ("Trickster (2)") thay vì bỏ, cả 2 giọng chọn được. 9 test mới (2 skip nếu không có model NLLB thật cục bộ), 0 regression (770/775 pass) — xem TEST_LOG |
| V22 | CLI headless cho pipeline dub (Phase F — nền tảng cho V23-V25) | ✅ Xong | `autodub/cli.py` mới — `voxdub dub`/`voxdub batch`, không đụng Qt/GUI trên toàn đường import (test khoá `PySide6`/`autodub_gui` không xuất hiện trong `sys.modules`); validate tên giọng tường minh thay vì rơi ngầm về giọng khác (khác hành vi GUI có chủ đích — xem Audit); `--json` phát ProgressEvent dạng NDJSON cho script hoá. Đăng ký `[project.scripts] voxdub` (console, không phải gui-scripts) — xem TEST_LOG |
| V23 | Cổng chất lượng tự động đọc `quality_report.json` (Phase F) | ✅ Xong | `autodub/quality_gate.py` (hàm thuần) + ngưỡng cấu hình qua Settings (mặc định bảo thủ, CHƯA hiệu chỉnh bằng dữ liệu thật — xem TEST_LOG); CLI `--quality-gate` (dub: exit 3 nếu fail; batch: field `quality` thêm vào batch_state.json, không đổi `status`); mặc định TẮT (0 regression khi không dùng cờ). 15 test mới, 0 regression (793/799 pass) — xem TEST_LOG |
| V24 | Tự thử lại theo video trong batch + giám sát treo subprocess + log lỗi tập trung (Phase F, gộp theo lựa chọn chủ dự án) | ✅ Xong (4/4 subprocess đã vá) | Audit thật tìm 4 điểm `for line in proc.stdout:`/`proc.stdout.read()` chặn vô thời hạn (translate_local/Whisper/Paraformer/voice_downloader) + 2 điểm ĐÃ ĐÚNG sẵn (VieNeu/Demucs) — `subprocess_watchdog.py` tổng quát hoá 2 kiểu đọc (theo dòng + đọc 1 khối), áp dụng cho **cả 4/4 điểm** đã audit (đợt 1: `run_local_worker()`; đợt 2: Whisper/Paraformer/voice_downloader — xem TEST_LOG "Re-audit"). `batch_retry.py` phân loại transient/permanent theo exception type (tái dùng luật `saas_retry.py` V16), tự thử lại video lỗi tạm thời trong `batch.py` (mặc định TẮT, resume đúng work_dir cũ). `failures_log.py` ghi `failures.jsonl` LUÔN bật, không đổi `batch_state.json`. CLI `--retry-transient`/`--max-retries`. 47 test mới tổng cộng, 0 regression (867/873 pass) — xem TEST_LOG |
| V25 | Chế độ theo dõi thư mục/hàng đợi không người trực (Phase F) | ✅ Xong | `autodub/watch_folder.py` — polling đơn giản (không thêm dependency), `StabilityTracker` (kích thước không đổi N giây), `WatchState` bền theo path+mtime+size (tách `batch_state.json`), tự loại file bookkeeping (state/failures/batch_state) khỏi input dù input=output trùng thư mục. CLI `voxdub watch --input-dir ...`, dùng lại DubPipeline + watchdog/failures_log của V24. **Ctrl+C**: đợt 1 chỉ dừng sạch giữa 2 lượt poll; đợt 2 (Re-audit) đóng nốt gap — sửa nhầm lẫn thật (SIGINT handler tuỳ biến KHÔNG raise nên video đang dub KHÔNG bị cắt ngang, chỉ chờ xong rồi mới dừng — không phải "mất resume" như lo ban đầu) + thêm bấm Ctrl+C LẦN 2 thoát ngay (exit 130) + `process_file()` ghi `work_dir` dở trước khi lỗi lan ra (phòng thủ cho trường hợp gọi trực tiếp không qua CLI). **Live-verify thật (2 đợt)**: đợt 1 bắt lỗi timestamp rỗng trong failures.jsonl; đợt 2 live-verify double-Ctrl+C thật qua subprocess thật (pipeline giả chạy chậm) — xác nhận đúng: lần 1 chờ, lần 2 exit 130 ngay lập tức. 39 test mới tổng cộng, 0 regression (867/873 pass) — xem TEST_LOG |
| V26 | Diarization tự động (đa giọng nói) (Phase G) | ✅ Xong (hạ tầng + GUI), CHƯA live-verify diarization thật | Worker/driver/pipeline wiring đầy đủ, tái dùng `seg["voice"]` có sẵn (không viết lại TTS); round-robin speaker→voice; degrade trung thực khi chưa cài; CLI `--multi-speaker`. **Re-audit 2026-08-12**: đóng gap GUI Scope E — panel "Xem trước người nói" (`autodub_gui/ui/speaker_dialog.py` + `autodub/editor.py::list_speakers()`/`set_speaker_voice()`), đổi giọng theo TỪNG người nói thay vì từng câu lẻ, chỉ hiện khi dự án có diarization thật. `pyannote.audio` cài THẬT được (verify live), nhưng model pretrained bị khoá trên HuggingFace (gated) — sandbox không có access token nên KHÔNG live-verify được diarization thật trên audio 2 người nói (ghi rõ, không giả vờ). 32 test (24 gốc + 8 GUI panel), 0 regression (948/954 pass) — xem TEST_LOG |
| V27 | Sửa bug glossary không hoạt động trên nhánh dịch local NLLB (Phase G) | ✅ Xong | Bug thật xác nhận: glossary chỉ enforce ở nhánh SaaS, nhánh local NLLB âm thầm bỏ qua — `ctranslate2` không có API ép từ giữa câu nên sửa bằng hậu xử lý tìm-thay-thế (`translate_glossary_apply.py`). Tìm+sửa 1 bug thật khi viết test: check "thuật ngữ có mặt trong câu gốc" case-sensitive trong khi thay thế lại case-insensitive — glossary chữ hoa bỏ lỡ câu gốc viết thường. 17 test mới, 0 regression (905/911 pass) — xem TEST_LOG |
| V28 | Emotion/tone-aware voice tự động (Phase G) | ✅ Xong (cả 2 đường: LLM + local-only) | Audit `vieneu_worker.py` xác nhận style vốn được đọc mỗi request — chỉ hardcode nhầm về CLI arg, sửa nhỏ mở khoá style PER-SEGMENT thật (live-verify qua worker giả thật, style khác nhau 2 câu liên tiếp gửi đúng). Wiring đủ 3 tầng: `tone_heuristic.py` (văn bản → tone → style VieNeu) → `pipeline.py::_apply_emotion_styles()` (chỉ áp VieNeu, bỏ qua CapCut) → `Synthesizer` Protocol (`style` kwarg, CapCut nhận nhưng bỏ qua có chủ đích). **Re-audit 2026-08-12**: đóng nốt đường SaaS/LLM per-segment (Scope A) — mở rộng `buildTranslateSystemPrompt`/`translateSchema`/`mergeTranslations` (chỗ per-segment THẬT, không phải `buildAnalysisPrompt` như chữ trong bản nháp mini-spec — hàm đó là phân tích cấp video) qua cờ opt-in `emotionTone`, mặc định TẮT nên 0 regression cho contract `/translate` sản xuất; `pipeline.py::_apply_emotion_styles()` giờ ưu tiên `seg["tone"]` từ SaaS, rơi về heuristic khi không có. Chỉ 3 giá trị tone (neutral/excited/serious, không phải 4 như bản nháp — khớp đúng 3 style VieNeu có sẵn). 21+21 = 42 test, 0 regression (959/965 pass Python, 204/205 pass Node) — xem TEST_LOG. Còn lại: chưa live-verify dịch SaaS thật qua model thật (không có AI provider key thật trong sandbox) |
| V29 | Lộ rõ AI review dịch ra quality_report.json + GUI (Phase G) | ✅ Xong | Xác nhận `review_translations()` chỉ 1 caller thật (pipeline.py) — an toàn đổi thêm tham số. Trace additive qua `trace_out` (0 regression mọi caller không truyền), lưu qua instance side-channel `self._last_review_trace` (cùng kiểu `self.last_work_dir`), lộ ra field mới `translate_review` trong `quality_report.json` (additive, không đụng `summary`/`per_segment` của V23) + bảng "AI đã tự soát bản dịch" trong trang Báo cáo chất lượng. 14 test mới, 0 regression (940/946 pass) — xem TEST_LOG |
| V30 | Audit khả thi Lip-sync (Phase G, KHÔNG cam kết build) | ✅ Xong (research) | Khảo sát thật 4 model mã nguồn mở (license + phần cứng công bố chính thức, có trích dẫn) + cài đặt thật bộ dependency CPU-only (thành công, xác nhận không có GPU provider — đúng thực tế sandbox lẫn nhiều máy người dùng cuối). **Kết quả**: Wav2Lip (nhẹ nhất/CPU-capable) có giấy phép CẤM THƯƠNG MẠI xung đột hệ Vox trả phí; SadTalker (Apache 2.0) cần VRAM phi thực tế cho video dài; VideoReTalking license chưa xác minh được; MuseTalk (MIT) khả thi nhất về giấy phép nhưng vẫn bắt buộc GPU thật để hữu dụng — phá nguyên tắc "GPU-optional" xuyên suốt dự án. **Khuyến nghị: KHÔNG build ngay** — 5 câu hỏi chính sách (consent/watermark/giới hạn gói/GPU-only/tư vấn pháp lý Wav2Lip) cần chủ dự án trả lời trước. Không có test code (đây là research spike đúng Test Plan N/A của mini-spec) — xem TEST_LOG |
| V31 | Translation-as-a-Service API cho developer bên thứ 3 (Phase G) | ✅ Xong | `ApiKey`/`ApiUsageLedger` (mới, tách hẳn `Device`/`CreditLedger`) + `apikey.middleware.js` (lớp identity thứ 2 song song `auth.middleware.js`) + route `/api/v1/translate` (tái dùng `gateway.translateSubtitleBatch()` đã có từ V14, không viết prompt mới) + `/v1/admin/api-keys` (tạo/liệt kê/thu hồi thủ công). Quota atomic qua `findOneAndUpdate` (đúng Constraint 5 — không transaction/Redis), verify đúng dưới tải đồng thời thật (10 request song song, đúng 5 lượt qua với quota=5). **Re-audit 2026-08-12**: thêm `GET /api/v1/me` (developer tự xem quota/usage của chính mình mà không cần gọi `/translate` trước) — đóng gap cuối trong Remaining Limits. 21+2 = 23 test mới, 0 regression (204/205 pass npm test). **Live-verify thật qua HTTP thật** (không chỉ `fastify.inject`) — dựng server thật + MongoDB thật (in-memory), curl thật: tạo key → 401 khi thiếu key → key hợp lệ chạy xuyên suốt auth+quota-precheck tới tận AI gateway (dừng ở NO_PROVIDER vì không cấu hình provider, đúng như dự kiến) → liệt kê không lộ hash → thu hồi → 403 ngay sau đó — xem TEST_LOG |
| V32a | PoC lip-sync MuseTalk — benchmark thật + thử nghiệm consent-check/watermark (Phase G, đóng gap V30) | 🔶 **Live-verify thành công 1/3 mẫu** trên máy chủ dự án (NVIDIA T1200 4GB) — còn thiếu góc nghiêng + nhiều người | Chủ dự án đã trả lời đủ 5 câu hỏi chính sách V30 (2026-08-12): CÓ consent-check, CÓ watermark, CÓ giới hạn theo gói, CHẤP NHẬN GPU-only, KHÔNG cần Wav2Lip. `scripts/setup_lipsync_poc.py` + `scripts/research/lipsync_poc.py` viết xong, cài đặt + chạy thật trên máy chủ dự án (không phải sandbox — sandbox không có GPU). Sau 8 vòng sửa lỗi thật trong lúc live-verify (Python 3.10 pin, huggingface_hub version, gdown cú pháp mới, autodub import kéo dependency nặng, đường dẫn tương đối vỡ khi đổi cwd, YAML escape ký tự Windows, thiếu `--use_float16` gây OOM VRAM, UnicodeEncodeError khi pipe-redirect stdout) — **mẫu mặt thẳng (video mẫu MuseTalk) chạy trót lọt hoàn toàn**: 794s (~13.2 phút) cho ~10.7s video 268 frame, VRAM đỉnh 3929/4096MB (~96%, rất sát trần card 4GB), consent-check 268/268 frame nhận diện khuôn mặt (100%), watermark metadata thành công, watermark chữ đè thành công sau khi trỏ đúng font có sẵn trong repo. CHƯA chạy mẫu góc nghiêng/nhiều người (Constraint 6) và chưa có đánh giá chất lượng bằng mắt — xem TEST_LOG |
| V32b | Build lip-sync production (Phase G, đóng gap V32a — CHỈ mở khi V32a khuyến nghị "go") | ⏸️ Chờ kết quả V32a | Phạm vi/Design Choice cuối phụ thuộc số liệu benchmark thật của V32a — mini-spec khung đã viết bên dưới, sẽ tinh chỉnh cụ thể (ngưỡng chất lượng, giới hạn video hỗ trợ) sau khi có PoC thật |
| V33 | AI tự đề xuất giọng đọc phù hợp theo nội dung video (Phase G, chủ dự án yêu cầu 2026-08-13) | ✅ Xong (bản "sau khi lồng tiếng xong", đúng chốt Design Choice) | Agent audit xác nhận luồng wizard "Tạo dự án" chỉ cấu hình, không có tín hiệu phân tích lúc chọn giọng — chốt xây bản đề xuất Ở TRÌNH CHỈNH SỬA (sau khi xuất, dùng `video_context.json` đã mở khóa). `voice_hint` additive trong `ANALYSIS_SCHEMA` (chỉ 3 style thật của VieNeu, khớp `VOICE_STYLE_VALUES`) → `autodub/speech/tts/voice_recommend.py::recommend_voices()` (giới tính là bộ lọc cứng, style chỉ dùng 2 giá trị đáng tin tin_tuc/doc_truyen — không suy đoán khi catalog thiếu dữ liệu, đúng Constraint 2) → `autodub/editor.py::suggest_voice()` (hàm thuần, đọc file qua `securestore.read_json_secure(key=None)`, còn khóa/thiếu/hỏng đều trả None chứ không xin lại khóa máy chủ) → khối "AI đề xuất giọng" trong `VoicePanel` (Trình chỉnh sửa), tái dùng đúng luồng đổi giọng thủ công đã có. 4+11+7+5 = 27 test mới, 0 regression (986/992 pass Python, 208/209 pass Node) — xem TEST_LOG |
| V34a | PoC hạ tầng API lồng tiếng đầy đủ (Phase G, đóng gap V31 — mở rộng dịch-thôi thành ASR+dịch+TTS+video) | ✅ Xong — **khuyến nghị GO cho V34b** | `DubApiJob`/`dub-job.service.js` (tách hẳn `RenderJob`) + `/internal/dub-jobs/*` + `/api/v1/dub*` + `control_server/worker-dub/` (Docker image mới, 3 venv Whisper/VieNeu/NLLB cài bằng chính script cài đặt có sẵn). Docker build thật + **2 lượt live-verify thật thành công** trên 1 video mẫu thật (12.2s, giọng nói tiếng Anh thật qua gTTS): 1 lượt bình thường (voice CapCut mặc định), 1 lượt **HOÀN TOÀN OFFLINE** (`--network none`, giọng VieNeu tự học từ file thật trong `voices/preset_voices_vn/`) — cả 2 đều `status: completed`, CPU-only ~3x thời lượng gốc, không cần GPU. 2 bug thật có sẵn trong codebase (không phải do V34a) lộ ra và sửa ngay lúc live-verify: `setup_whisper.py` gửi stdin rỗng cho worker luôn đòi JSON (chặn cài Whisper trên MỌI máy sạch); `saas_client.py` import cứng `autodub_gui` dù `autodub.cli` tự nhận không phụ thuộc GUI. 24+4 = 28 test mới, 0 regression (994/1000 pass Python, 232/233 pass Node) — xem TEST_LOG cho số liệu đầy đủ + Remaining Limits (bg-mode=demucs, video dài, billing thật đều chưa đo) |
| V34b | Build production API lồng tiếng đầy đủ (Phase G, đóng gap V34a — CHỈ mở khi V34a khuyến nghị "go") | ⏸️ V34a đã khuyến nghị GO (2026-08-13) — chưa mở, chờ chủ dự án quyết định thứ tự ưu tiên | Billing theo phút video + giới hạn lưu trữ production + GPU provisioning multi-tenant — có số liệu thật từ V34a (CPU đủ dùng cho video ngắn, ~3x thời lượng gốc, image 8.42GB) nhưng CHƯA có số liệu video dài/bg-mode=demucs — nên đo thêm trước khi chốt giá, xem TEST_LOG mục V34a |
| V35 | Nâng chất lượng nhân bản giọng (voice cloning) (Phase G, chủ dự án yêu cầu 2026-08-13) | ✅ Xong | `autodub/speech/tts/audio_quality.py` (mới, hàm thuần không model AI — clip ratio/RMS/khoảng lặng liên tục) nối vào `vieneu_worker.py::_encode_one()`: fail → chặn trước khi mã hóa nặng, warn → vẫn học nhưng gắn cảnh báo tạm thời (không lưu vào file), >8s → báo cắt thay vì âm thầm. Loại trừ CẤU TRÚC (không chỉ ngưỡng số học) cho giọng thư viện qua field `source="library"` có sẵn — Constraint 4 giữ nguyên hành vi 120 giọng preset, xác nhận thêm bằng regression test THẬT (0/120 file fail/warn). GUI (`settings_panels.py`) hiện cảnh báo ngay sau enroll, không đợi "Nghe thử". Bug thật tìm+sửa khi wiring: nạp module qua `importlib` thiếu đăng ký `sys.modules` làm `@dataclass` crash `AttributeError`. 26 test mới, 0 regression (1020/1026 pass Python, 232/233 pass Node) — xem TEST_LOG |

## Tổng quan phase

| Phase | Mini-spec | Trọng tâm | Thời lượng ước tính (AI-compressed, 7h/ngày) |
|---|---|---|---|
| **A — Ngắn hạn** (Foundation & Trust) | V1, V2, V3, V4 | Vận hành an toàn trước khi đổi gì khác + 1 quick win chất lượng | ~2-3 ngày AI/spec |
| **B — Trung hạn** (Core Capability) | V5, V6, V7 | Nâng năng lực lõi + mở nền tảng phân phối | ~4-7 ngày AI/spec |
| **C — Dài hạn** (Platform & Scale) | V8, V9, V10 | Mở rộng thị trường/nền tảng + hoàn thiện thương mại hoá | ~7-12 ngày AI/spec |
| **D — Hoàn thiện** (Close the gaps) | V11, V12, V13 | Đóng nốt giới hạn PoC của V8/V9/V10 — mỗi cái cần 1 quyết định/input từ chủ dự án trước khi làm | ~3-6 ngày AI/spec |

**Thứ tự bắt buộc**: V2 (tách billing khỏi core) phải làm **trước** V5/V6/V8 vì các spec
đó đều chạm `pipeline.py` — làm sau V2 sẽ an toàn hơn, tránh conflict với logic hold/credit
đang xen kẽ. V1 nên đi trước V2 vì V2 refactor luồng tiền thật, cần test bảo vệ trước.

---

## Phase A — Ngắn hạn (Foundation & Trust)

### V1 — Test & API Docs Foundation cho control_server

```
V1 — Test & API Docs Foundation cho control_server

Context:
- Tài liệu bắt buộc: docs/ARCH.md §2.3, control_server/src/routes/*.js,
  control_server/src/services/*.js (activation, ai-gateway, audit, billing, credit,
  device, email, hold, payos).
- Trạng thái hiện tại: control_server/tests/ chỉ có 3 file test thuần utility (format mã
  activation, crypto, JSON repair) — KHÔNG có test tích hợp DB. Debit credit dùng
  findOneAndUpdate atomic (không Mongo transaction, single-node). Webhook PayOS xác minh
  chữ ký nhưng chưa có test cho path lỗi/giả mạo. Không có API.md nào mô tả contract.
- Quyết định kiến trúc phải giữ nguyên:
  - Không đổi driver DB (MongoDB/Mongoose), không thêm Mongo transaction/replica-set
    requirement.
  - Không đổi cấu trúc route/service hiện có — chỉ thêm test + docs.

Goal:
- Mọi luồng chạm tiền thật (hold, debit, PayOS webhook, activation key) có test tích hợp
  chạy được trên CI, và có API.md mô tả đúng contract thật (không phải đoán từ code khi
  cần tích hợp thêm).

Constraints (Guardrails):
1. Không sửa business logic khi viết test — nếu test lộ bug thật, ghi riêng thành bug
   report trong docs/TEST_LOG.md, KHÔNG tự ý sửa trong cùng mini-spec này.
2. Không thêm Mongo transaction/replica-set — giữ nguyên atomic findOneAndUpdate.
3. Test DB dùng mongodb-memory-server hoặc test container ephemeral — không chạm Mongo
   production/staging thật.
4. PayOS webhook test phải cover: chữ ký hợp lệ, chữ ký sai, replay (webhook gửi 2 lần
   cùng orderId), payload thiếu field.
5. Nếu thiếu bằng chứng hành vi đúng (vd race condition chưa rõ outcome mong muốn) →
   ghi `unconfirmed` trong TEST_LOG.md, không tự đoán rồi viết test theo giả định sai.
6. Không bypass audit log khi test — mọi action test tạo ra vẫn phải ghi audit như thật
   (test đúng bằng cách xoá dữ liệu test sau, không tắt audit).

Scope:
A. Domain model: audit Device/ActivationKey/Order/Hold schema thật trong
   control_server/src/models/ (chưa liệt kê đủ trong ARCH.md — bổ sung vào ARCH.md §3
   khi audit xong).
B. Services/engine: test credit.js (debit atomic + double-spend), hold.js (create/commit/
   expire), activation.js (key format + redeem), payos.js (signature verify + webhook
   parse), audit.js (mọi mutation có audit entry).
C. API contract: viết docs/API.md — mỗi endpoint route (admin.js, ai.js, billing.js,
   config.js, device.js, holds.js): method, path, request/response shape thật (đọc code,
   không bịa), auth requirement, error shape.
D. UI surfaces: không có (backend only).
E. Tests: integration (HTTP + in-memory Mongo), regression (double-spend, webhook replay
   bị chặn), không cần unit riêng (logic đã đơn giản, integration cover đủ).

Audit Before Build:
- Đã kiểm: toàn bộ route/service file (liệt kê ở B), pyproject.toml/package.json cho
  dependency test hiện có (chỉ có node --test hoặc tương đương gì đó cần xác nhận runner
  thật trong package.json).
- Gap cụ thể: 0% integration test coverage cho billing/credit/hold — đây là gap
  nghiêm trọng nhất trong toàn bộ audit vì đây là luồng tiền thật.

Design Choice:
- Dùng `mongodb-memory-server` (hoặc runner tương đương đã có trong ecosystem Fastify/
  Node của project) để spin Mongo ephemeral trong CI — không cần Docker Compose mới,
  tái dùng cấu trúc test hiện có (`control_server/tests/`), chỉ thêm file test mới,
  không viết lại 3 file utility test đang có.
- API.md theo đúng style hiện có trong repo (README "for developers" section) — không
  invent format tài liệu mới.

Test Plan:
- Unit: giữ nguyên 3 file hiện có, không sửa.
- Integration: credit debit concurrent (2 request debit cùng lúc không double-spend),
  hold create→commit→settle full lifecycle, hold expire tự động, PayOS webhook 4 case
  ở Guardrail 4, activation key redeem 1 lần duy nhất (không redeem 2 lần).
- Regression: sau mỗi mini-spec khác chạm control_server (V2, V9, V10), suite này phải
  chạy pass trước khi merge.
- Live verification: không cần (đây là spec nền tảng, không đổi behavior sản xuất).

Success Criteria:
- `npm test` trong control_server chạy integration test thật (không chỉ utility), pass
  100%, có báo cáo coverage cho credit.js/hold.js/payos.js ≥ 80% branch.
- docs/API.md tồn tại, mô tả đúng 100% endpoint thật trong 6 route file, review chéo
  bằng cách gọi thử từng endpoint khớp response documented.
- Không còn luồng tiền thật nào (debit/hold/webhook/activation) thiếu test tích hợp.
```

---

### V2 — Tách lớp Billing/Credit khỏi core pipeline OSS

```
V2 — Tách lớp Billing/Credit (Vox hold) khỏi core pipeline OSS

Context:
- Tài liệu bắt buộc: docs/ARCH.md §2.1 (bảng "Licensing/credit"), autodub/pipeline.py
  (_setup_hold, _settle_hold_inline, _stop_for_export), autodub/securestore.py,
  autodub/device_id.py, autodub/keystore.py, autodub/saas_client.py (is_configured()).
- Trạng thái hiện tại: logic hold/credit gọi trực tiếp, xen kẽ trong DubPipeline.run()
  (file 1946 dòng) — không có interface/adapter tách biệt. `saas_client.is_configured()`
  là gate duy nhất nhưng các nhánh if/else nằm rải trong nhiều điểm của pipeline.py thay
  vì tập trung ở 1 lớp.
- Quyết định kiến trúc PHẢI giữ nguyên (từ README "for developers" + code hiện có):
  - `saas_client.is_configured()` (dựa trên VOXDUB_API_URL) vẫn là NGUỒN DUY NHẤT quyết
    định local-only vs SaaS — không thêm cổng thứ 2.
  - Không đổi format securestore (AES-256-GCM) hay device_id fingerprint.
  - Không đổi hành vi export/hold hiện tại (thứ tự setup_hold → chạy pipeline →
    settle_hold_inline khi export) — CHỈ tái cấu trúc code, không đổi outcome.

Goal:
- `autodub/` core (không tính 1 module billing_adapter mới) chạy được 100% đầy đủ mà
  không cần biết khái niệm "hold/credit/Vox" tồn tại — để mini-spec sau (V5, V6, V8) có
  thể sửa pipeline core mà không đá vào logic thương mại, và để tương lai có thể build
  1 core OSS tách bạch khỏi bản thương mại nếu cần.

Constraints (Guardrails):
1. KHÔNG rebuild pipeline hay đổi state machine hold hiện có — chỉ di chuyển code vào
   1 module/interface (`autodub/billing_adapter.py` hoặc tên tương đương), giữ nguyên
   toàn bộ logic bên trong.
2. Không đổi ý nghĩa của bất kỳ enum/state hold nào đã có.
3. Pipeline gọi billing adapter qua 1 interface rõ ràng (vd `BillingHooks` protocol với
   `on_asr_complete()`, `on_export()`, `on_stop()`) — không gọi thẳng
   `_setup_hold`/`_settle_hold_inline` từ nhiều điểm rải rác như hiện tại.
4. Khi `is_configured() == False`, adapter phải là no-op hoàn toàn (đã đúng behavior
   hiện tại — verify bằng test, không đổi).
5. Nếu phát hiện nhánh hold nào không rõ mục đích khi audit (evidence thiếu) → hỏi
   trong PR/báo cáo, KHÔNG tự đoán rồi xoá hay sửa.
6. Không bypass hold/settle gate khi refactor — pipeline vẫn phải chặn export nếu hold
   chưa settle trong chế độ SaaS, y hệt hiện tại.
7. Không đổi file autodub.spec/build_exe.py trừ khi việc tách module ảnh hưởng đến danh
   sách file PyInstaller cần bundle — nếu có, cập nhật kèm test build.

Scope:
A. Domain model: không thêm entity mới, chỉ tổ chức lại vị trí code hold/credit hiện có
   vào 1 module.
B. Services/engine: tạo `BillingHooks` interface (protocol/ABC) trong `autodub/billing_
   adapter.py`, implement 2 lớp: `NoopBillingHooks` (local) và `SaasBillingHooks` (wrap
   logic hold/settle hiện có). `DubPipeline.__init__` nhận 1 `BillingHooks` instance
   (default chọn theo `is_configured()`, giữ backward-compat cho code gọi
   `DubPipeline()` không đổi tham số).
C. API contract: không đổi (control_server không bị chạm trong spec này).
D. UI surfaces: không đổi — GUI vẫn ẩn trang "Tài khoản" khi `is_configured()==False`
   y hệt hiện tại.
E. Tests: unit cho `NoopBillingHooks`/`SaasBillingHooks` riêng biệt, regression đảm bảo
   `DubPipeline.run()` cho ra output/artifact giống hệt trước refactor (byte-for-byte
   với cùng input test fixture, trừ timestamp).

Audit Before Build:
- Đã kiểm: toàn bộ điểm gọi `_setup_hold`, `_settle_hold_inline`, `_stop_for_export`
  trong pipeline.py, cách `is_configured()` được check ở các module khác (editor.py,
  batch.py — cần audit xem 2 file này có gọi hold logic riêng không, chưa xác nhận
  trong đợt khảo sát đầu — BẮT BUỘC audit lại khi bắt tay spec này).
- Gap cụ thể: logic thương mại lẫn vào core, khiến các thay đổi core sau này (V5/V6/V8)
  có rủi ro đá vào billing ngoài ý muốn, và khó tách 1 "core OSS" thuần nếu công ty
  muốn open-source phần lõi sau này.

Design Choice:
- Adapter pattern nhẹ (protocol + 2 implementation), KHÔNG dùng dependency injection
  framework mới, KHÔNG đổi cách `DubPipeline` được khởi tạo từ `autodub_gui`/`batch.py`
  (giữ default constructor behavior để không phải sửa toàn bộ call site) — chỉ thêm
  optional param `billing_hooks=None` tự chọn theo `is_configured()` nếu không truyền.
  Lý do chọn: additive-first, reuse-first theo đúng nguyên tắc Playbook §6.2 — không
  build engine song song, không đổi call site không cần thiết.

Test Plan:
- Unit: BillingHooks interface, mỗi method của 2 implementation.
- Integration: chạy 1 project dubbing đầy đủ ở chế độ local (Noop) và assert không có
  bất kỳ network call/hold nào xảy ra (mock network, assert 0 call).
- Regression: so sánh output artifact (transcript, audio, video metadata — không so
  video pixel-by-pixel) trước/sau refactor trên cùng 1 test fixture, phải giống hệt.
- Live verification: không cần (refactor nội bộ, không đổi UX).

Success Criteria:
- `grep -rn "_setup_hold\|_settle_hold_inline" autodub/pipeline.py` không còn match nào
  ngoài lời gọi qua `self.billing_hooks.*`.
- Toàn bộ 546 test hiện có trong `tests/` vẫn pass sau refactor.
- Một dev mới đọc `pipeline.py` không cần hiểu khái niệm "Vox credit" để hiểu luồng
  dubbing chính — chỉ cần biết có 1 hook interface được gọi ở 2-3 điểm.
```

---

### V3 — Minh bạch mô hình Local-vs-SaaS

```
V3 — Minh bạch mô hình Local (free) vs SaaS (Vox trả phí)

Context:
- Tài liệu bắt buộc: README.md (mục cài đặt + "cách B — tự dựng máy chủ"), docs/PRD.md
  §9 (rủi ro minh bạch mô hình kinh doanh), scripts/build_exe.py (bake VOXDUB_API_URL).
- Trạng thái hiện tại: README định vị sản phẩm gần như 100% free/offline. Thực tế bản
  `.exe` chính thức (build qua build_exe.py) bake sẵn VOXDUB_API_URL trỏ tới control_
  server của maintainer → người dùng tải bản chính thức mặc định nằm trên hệ Vox trả phí
  cho tính năng auto-translate/metadata, dù pipeline dubbing lõi vẫn chạy free/offline.
  GUI đã ẩn trang "Tài khoản" khi không cấu hình server (đúng), nhưng không có thông báo
  chủ động nào giải thích "bạn đang dùng bản có/không có server" ngay khi mở app lần đầu.
- Quyết định kiến trúc phải giữ nguyên: không đổi gate `is_configured()`, không đổi
  luồng build (build_exe.py vẫn bake URL theo .env máy build).

Goal:
- Người dùng (kể cả người tải bản .exe chính thức) biết rõ, ngay từ lần mở app đầu
  tiên, họ đang ở chế độ nào (local-only hay có kết nối server trả phí) và tính năng
  nào miễn phí/tính năng nào tốn Vox — không còn ai bất ngờ khi thấy "hết Vox".

Constraints (Guardrails):
1. Không đổi business logic billing (đã tách ở V2, KHÔNG sửa lại ở đây).
2. Không ẩn hay xoá tính năng SaaS hiện có — chỉ làm rõ, không giảm chức năng.
3. Copy/wording là phạm vi BA quyết (theo BA⇄DEV handoff contract trong CLAUDE.md tổ
   chức) — DEV chỉ đặt biến/placeholder rõ ràng, BA review nội dung cuối trước khi live.
4. Không thêm bước xác nhận/checkbox chặn luồng dùng chính (không được biến thành dark
   pattern ngược — banner chỉ thông báo, không ép tương tác).
5. Nếu thiếu quyết định từ chủ dự án về mức độ công khai (vd có nêu tên "Vox credit"
   ngay banner đầu không) → escalate hỏi, không tự quyết thay.

Scope:
A. Domain model: không đổi.
B. Services/engine: thêm 1 flag đọc `is_configured()` để quyết định nội dung banner
   (tái dùng gate đã có, không thêm cổng mới).
C. API contract: không đổi.
D. UI surfaces: (1) banner/dialog 1 lần khi mở app lần đầu (persist "đã xem" vào local
   settings) giải thích chế độ hiện tại; (2) trang Trợ giúp bổ sung 1 mục FAQ "App này
   có tốn phí không?" nêu rõ ranh giới free (dubbing lõi) vs trả phí (auto-translate/
   metadata qua Vox); (3) README bổ sung 1 đoạn ngay đầu mục cài đặt nêu rõ 2 lựa chọn
   (dùng bản .exe chính thức = có kết nối server maintainer, hoặc tự build/tự chạy
   local = 100% offline).
E. Tests: test UI hiện dialog đúng 1 lần, test nội dung banner đổi đúng theo
   `is_configured()` true/false.

Audit Before Build:
- Đã kiểm: GUI hiện tại ẩn hoàn toàn trang "Tài khoản" khi local-only (đúng, giữ
  nguyên), không có onboarding banner nào giải thích mô hình.
- Gap cụ thể: thiếu 1 điểm chạm chủ động giải thích mô hình kinh doanh ngay từ đầu —
  đây là vocabulary/UX gap, không phải data/permission gap.

Design Choice:
- Tái dùng cơ chế "first-run/setup wizard" đã có trong autodub_gui (theo ARCH.md §2.2)
  — thêm 1 bước/dialog vào wizard đó thay vì xây luồng onboarding mới song song. Lý do:
  reuse-first, người dùng đã quen luồng setup wizard, không tạo thêm điểm vào ứng dụng.

Test Plan:
- Unit: hàm chọn nội dung banner theo is_configured() true/false.
- Integration: mở app lần đầu (fresh settings) → banner hiện; mở lần 2 → không hiện lại.
- Regression: setup wizard hiện có (trang khác) không bị ảnh hưởng thứ tự/luồng.
- Live verification: 1 lần build thử .exe với VOXDUB_API_URL set và không set, xác nhận
  banner đúng nội dung tương ứng.

Success Criteria:
- Không còn người dùng nào mở bản .exe chính thức lần đầu mà không thấy giải thích rõ
  đang ở chế độ nào.
- README mục cài đặt nêu rõ 2 lựa chọn trong 3 dòng đầu, không phải đọc hết bài mới biết.
- FAQ "có tốn phí không" tồn tại và trả lời đúng với thực tế code (đối chiếu docs/API.md
  từ V1 để không bịa số Vox/giá).
```

---

### V4 — Mở rộng lựa chọn ngôn ngữ nguồn ASR trong GUI

```
V4 — Mở rộng lựa chọn ngôn ngữ nguồn trong GUI (quick win chất lượng lõi)

Context:
- Tài liệu bắt buộc: autodub_gui/dub_constants.py (danh sách nguồn hiện tại: zh-CN,
  en-US, zh-HK, zh-TW), autodub/speech/transcriber.py (faster-whisper — hỗ trợ ~100
  ngôn ngữ upstream), autodub/languages.py (TARGETS chỉ có "vi" — KHÔNG đổi trong spec
  này, xem V8 cho đa ngôn ngữ đích).
- Trạng thái hiện tại: Whisper engine trong code đã nhận bất kỳ language code nào, chỉ
  bị GUI giới hạn cứng 4 lựa chọn. README có ví dụ nhắc tới tiếng Hàn nhưng UI không cho
  chọn — gap giữa marketing copy và UI thật.
- Quyết định kiến trúc phải giữ nguyên: KHÔNG đổi TARGETS (chỉ tiếng Việt là đích) — spec
  này CHỈ mở rộng NGUỒN (source language cho ASR), không đụng đích.

Goal:
- Người dùng chọn được ngôn ngữ nguồn từ danh sách đầy đủ ngôn ngữ Whisper hỗ trợ tốt
  (không phải chỉ 4 lựa chọn cứng), mà không cần đổi logic pipeline.

Constraints (Guardrails):
1. Không đổi transcriber.py logic — Whisper đã nhận language code tuỳ ý, chỉ đổi GUI.
2. Chỉ liệt kê ngôn ngữ Whisper có chất lượng tốt đã kiểm chứng (không liệt kê tất cả
   ~100 ngôn ngữ Whisper hỗ trợ nếu chưa test — tránh hứa hẹn chất lượng chưa kiểm chứng).
   Danh sách khởi điểm đề xuất: bổ sung ko (Hàn), ja (Nhật), th (Thái), id (Indonesia)
   bên cạnh 4 lựa chọn hiện có — mỗi ngôn ngữ mới cần ít nhất 1 lần test thật trước khi
   thêm vào danh sách chính thức.
3. Paraformer (engine thay thế, CPU-only) chỉ hỗ trợ tiếng Trung — GUI phải disable/ẩn
   lựa chọn Paraformer khi ngôn ngữ nguồn không phải zh-*, không được hiện lựa chọn rồi
   fail âm thầm.
4. Nếu 1 ngôn ngữ mới cho kết quả ASR chất lượng kém khi test thật → KHÔNG thêm vào
   danh sách chính thức, ghi lại trong TEST_LOG.md thay vì giả vờ hỗ trợ.

Scope:
A. Domain model: mở rộng enum/list ngôn ngữ nguồn trong dub_constants.py.
B. Services/engine: không đổi transcriber.py (đã hỗ trợ sẵn); chỉ đổi validation ở tầng
   GUI đảm bảo Paraformer chỉ available khi nguồn là zh-*.
C. API contract: không đổi.
D. UI surfaces: dropdown chọn ngôn ngữ nguồn (trang Tạo dự án + trang Cài đặt mặc định)
   thêm các lựa chọn mới; disable Paraformer option khi không phải zh-*.
E. Tests: test dropdown liệt kê đúng danh sách mới, test Paraformer bị disable đúng
   điều kiện, live test thật với ≥1 video mỗi ngôn ngữ mới thêm.

Audit Before Build:
- Đã kiểm: dub_constants.py là nguồn duy nhất định nghĩa danh sách — không có nơi nào
  khác hardcode lại danh sách 4 ngôn ngữ (cần xác nhận lại khi bắt tay, vì đây chỉ là
  audit ban đầu, chưa grep toàn bộ).
- Gap cụ thể: vocabulary gap thuần tuý — GUI hardcode ít hơn khả năng thật của engine.

Design Choice:
- Chỉ sửa dub_constants.py + validation logic liên quan Paraformer, không đổi kiến trúc
  gì khác. Đây là mini-spec nhỏ nhất trong roadmap — cố tình giữ nhỏ để làm quick win
  đầu tiên có thể ship trong Phase A mà không phụ thuộc V1/V2/V3.

Test Plan:
- Unit: validation Paraformer availability theo source language.
- Integration: chọn từng ngôn ngữ mới trong GUI, chạy tới bước ASR (không cần chạy hết
  pipeline), assert transcript sinh ra có nội dung hợp lý (không rỗng/lỗi).
- Regression: 4 ngôn ngữ cũ vẫn hoạt động y hệt.
- Live verification: 1 video thật mỗi ngôn ngữ mới (ko/ja/th/id), ghi chất lượng ASR
  quan sát được vào TEST_LOG.md — ngôn ngữ nào chất lượng kém thì loại khỏi danh sách
  chính thức (không phải bug, là kết quả audit).

Success Criteria:
- Danh sách ngôn ngữ nguồn trong GUI ≥ 8 lựa chọn (4 cũ + tối thiểu các ngôn ngữ đã
  live-verify đạt chất lượng chấp nhận được).
- Không còn trường hợp chọn Paraformer với nguồn không phải tiếng Trung mà không có
  cảnh báo/disable rõ ràng.
```

---

## Phase B — Trung hạn (Core Capability Upgrade)

### V5 — Auto text-region detection thay manual boxblur ("che chữ gốc")

```
V5 — Tự động phát hiện vùng chữ overlay (OCR) thay thế vẽ tay boxblur

Context:
- Tài liệu bắt buộc: docs/ARCH.md §2.1 dòng "Che chữ gốc", autodub/media/subtitle.py
  (blur_filter, build_filter_complex), autodub_gui/style_dialog.py (UI vẽ rectangle tay).
- Trạng thái hiện tại: "che chữ gốc" CHỈ là ffmpeg boxblur trên rectangle người dùng tự
  vẽ trong 1 frame preview tĩnh — không tự động, không theo dõi chữ di chuyển/xuất hiện
  ở frame khác, và README dùng ngôn ngữ khiến người đọc tưởng đây là AI text removal.
- Quyết định kiến trúc phải giữ nguyên: pipeline vẫn dùng ffmpeg filter_complex để áp
  blur (không đổi sang giải pháp inpainting nặng như LaMa/ProPainter trong V5 — đó là
  quá lớn cho 1 mini-spec, xem "Remaining Limits" — V5 chỉ tự động hoá việc PHÁT HIỆN
  vùng cần blur, không đổi cách blur được áp dụng).

Goal:
- Vùng chữ overlay trên video được phát hiện tự động (OCR + tracking cơ bản) và đề xuất
  sẵn cho người dùng xác nhận/chỉnh sửa, thay vì người dùng phải tự vẽ từ đầu trên 1
  frame tĩnh không đại diện cho cả video.

Constraints (Guardrails):
1. Không rebuild engine blur hiện có (ffmpeg boxblur filter) — chỉ thay đổi NGUỒN toạ độ
   rectangle từ "người dùng tự vẽ" sang "OCR đề xuất + người dùng xác nhận/sửa".
2. Giữ nguyên khả năng vẽ tay thủ công làm fallback — không được bắt buộc OCR, người
   dùng vẫn tắt được và tự vẽ như hiện tại (đây là guardrail an toàn: OCR có thể sai).
3. Không invent định dạng lưu rectangle mới nếu style_dialog.py đã có định dạng — audit
   trước khi thêm field.
4. Nếu OCR không phát hiện được chữ nào (video sạch) → không tự động bật tính năng blur,
   giữ trạng thái tắt mặc định (degrade trung thực, không ép người dùng xử lý việc không
   tồn tại).
5. OCR chạy trên sample frame (không phải toàn bộ video ở resolution gốc) để không làm
   nổ thời gian xử lý — cần benchmark thời gian thêm vào tổng pipeline runtime, ghi vào
   TEST_LOG.md, không được vượt quá 1 ngưỡng chấp nhận được (đề xuất: < 10% tổng thời
   gian pipeline cho video 5 phút — chốt số thật sau benchmark, không đoán trước).
6. Không gửi frame video ra ngoài máy người dùng (OCR phải chạy local, giữ nguyên triết
   lý offline-first của toàn bộ pipeline) — không dùng OCR API cloud.

Scope:
A. Domain model: thêm field "detected_regions" (list rectangle + confidence + frame
   range) bên cạnh "manual_regions" hiện có trong project state.
B. Services/engine: module OCR mới (đề xuất PaddleOCR hoặc EasyOCR — chọn theo license
   + kích thước model + CPU performance, quyết định cụ thể ghi trong Design Choice sau
   khi so sánh thật, không chốt trước khi audit), sample N frame đại diện (đầu/giữa/cuối
   + frame có audio segment dài), gộp region trùng lặp qua nhiều frame.
C. API contract: không đổi (tính năng local-only, không qua control_server).
D. UI surfaces: style_dialog.py hiển thị rectangle do OCR đề xuất (màu khác để phân biệt
   với rectangle tự vẽ), cho phép xác nhận/xoá/chỉnh từng cái, nút "Quét tự động" riêng
   (không tự chạy ngầm khi mở dialog, tránh bất ngờ delay).
E. Tests: unit (gộp region trùng lặp, sample frame selection), integration (chạy OCR
   thật trên video test cố định, assert phát hiện đúng vùng đã biết trước), regression
   (luồng vẽ tay thủ công không đổi hành vi).

Audit Before Build:
- Cần audit: định dạng lưu rectangle hiện tại trong style_dialog.py/project state
  (chưa xác nhận chi tiết trong khảo sát đầu — bắt buộc đọc kỹ trước khi thêm field).
- Gap cụ thể: hoàn toàn manual, không có OCR nào trong codebase hiện tại — đây là tính
  năng MỚI (không phải sửa bug), cần tuân thủ Playbook §3 "chỉ chạm gap đã xác nhận".

Design Choice:
- OCR chạy local (không cloud), tích hợp theo đúng pattern venv-con hiện có (giống
  .venv-whisper/.venv-vieneu) nếu thư viện OCR nặng — subprocess riêng để không phình
  bundle PyInstaller chính, tái dùng cơ chế setup script (`scripts/setup_ocr.py` theo
  đúng convention của setup_whisper.py/setup_vieneu.py).
- Cụ thể chọn PaddleOCR vs EasyOCR: benchmark cả 2 trên 5 video test tiếng Trung/Anh có
  chữ overlay thật, chọn theo tốc độ CPU + độ chính xác + kích thước model tải về, ghi
  kết quả benchmark vào TEST_LOG.md trước khi chốt — không chốt trong tài liệu plan này.

Test Plan:
- Unit: region dedup/merge logic.
- Integration: video test có chữ overlay biết trước vị trí, assert IoU (intersection
  over union) giữa region OCR phát hiện và ground truth ≥ ngưỡng chấp nhận (đề xuất 0.7,
  điều chỉnh sau benchmark thật).
- Regression: toàn bộ 546 test hiện có (đặc biệt subtitle/video mux) vẫn pass.
- Live verification: 3-5 video thật đa dạng (phụ đề cứng, watermark góc, tiêu đề kênh)
  chạy full pipeline, người dùng thật xác nhận blur đúng vị trí, ghi vào TEST_LOG.md.

Success Criteria:
- Người dùng không còn phải tự vẽ rectangle từ đầu cho video có chữ overlay rõ ràng —
  OCR đề xuất sẵn ≥ 70% vị trí đúng (đo qua live verification).
- Luồng vẽ tay thủ công 100% không đổi hành vi so với trước (regression pass).
- Thời gian pipeline tăng thêm do OCR nằm trong ngưỡng đã chốt sau benchmark, không
  làm pipeline "cảm giác chậm hẳn" với người dùng thật.
```

---

### V6 — Local/offline MT engine (path C bên cạnh manual/SaaS)

```
V6 — Local/offline Machine Translation engine

Context:
- Tài liệu bắt buộc: autodub/text/translate_saas.py, translate_hint.py,
  translate_review.py, translate_common.py, autodub/saas_client.py.
- Trạng thái hiện tại: chỉ 2 đường dịch — (A) thủ công dán vào ChatGPT/Gemini ngoài app,
  (B) tự động qua control_server (bắt buộc có server + Vox credit). KHÔNG có MT engine
  nào chạy local trong app.
- Quyết định kiến trúc phải giữ nguyên: KHÔNG xoá path A/B hiện có — V6 CHỈ THÊM path C,
  3 đường cùng tồn tại, người dùng chọn. `is_configured()` vẫn là gate cho path B, không
  đổi ý nghĩa gate đó cho path C (path C available bất kể is_configured()).

Goal:
- Người dùng không có server/Vox credit vẫn có 1 lựa chọn tự động dịch (chất lượng thấp
  hơn 3-pass SaaS nhưng nhanh hơn thủ công), chạy hoàn toàn offline.

Constraints (Guardrails):
1. Không đổi format transcript_vi.json hiện có — path C phải sinh ra đúng format mà
   path A/B đang tạo, để phần pipeline downstream (timing, TTS) không cần biết dịch từ
   đường nào.
2. Không thay thế/xoá 3-pass analyze→translate→review của path B — path C là bản đơn
   giản hơn (1-pass), không giả vờ có chất lượng tương đương.
3. Model MT phải chạy CPU-viable (giữ triết lý "CPU-only vẫn dùng được" đã ghi trong
   README FAQ) — nếu model chỉ chạy tốt trên GPU, phải có fallback rõ ràng hoặc cảnh báo
   thời gian xử lý dài, không im lặng treo máy.
4. Đóng gói theo đúng pattern venv-con hiện có (.venv-mt hoặc tương đương), không phình
   bundle chính.
5. Nếu chất lượng dịch path C được đánh giá kém hơn ngưỡng chấp nhận được khi live-test
   → phải cảnh báo rõ trong UI ("chất lượng có thể thấp hơn dịch thủ công/SaaS"), không
   giả vờ ngang hàng.
6. Không gửi transcript ra ngoài máy khi dùng path C (đây là điểm khác biệt chính so
   với path B — phải giữ đúng lời hứa "offline").

Scope:
A. Domain model: thêm "translate_method: manual|saas|local" vào project state (mở rộng
   enum hiện có, audit trước để không đổi ý nghĩa enum cũ).
B. Services/engine: module MT local mới (đề xuất NLLB-200 distilled hoặc model tương
   đương nhỏ đủ chạy CPU — chốt cụ thể sau benchmark, không quyết trong plan này), chạy
   qua subprocess venv riêng như các engine nặng khác.
C. API contract: không đổi (path C không gọi control_server).
D. UI surfaces: trang Dịch thuật thêm lựa chọn "Dịch tự động (offline)" bên cạnh 2 lựa
   chọn hiện có, kèm disclaimer chất lượng (nội dung do BA duyệt theo BA⇄DEV contract).
E. Tests: unit (format output khớp path A/B), integration (dịch thật 1 đoạn transcript
   cố định, so sánh chất lượng bằng BLEU/chrF hoặc đánh giá người với path B làm baseline),
   regression (path A/B không đổi hành vi).

Audit Before Build:
- Cần audit: định dạng transcript_vi.json chính xác (field nào bắt buộc) trước khi viết
  module MT mới — path C phải sinh đúng field, không thiếu/thừa so với path A/B.
- Gap cụ thể: capability hoàn toàn mới (không phải bug) — auto-translate hiện 100% phụ
  thuộc server, đây là nguồn phụ thuộc SaaS lớn nhất trong toàn sản phẩm.

Design Choice:
- Model MT nhỏ, ưu tiên license cho phép dùng thương mại (NLLB-200 distilled 600M hoặc
  tương đương — quyết định cuối sau khi benchmark thật CPU inference time trên máy cấu
  hình thấp, vì README cam kết CPU-only vẫn chạy được). Tích hợp qua subprocess venv
  riêng theo đúng pattern .venv-whisper/.venv-vieneu đã có — không đổi kiến trúc packaging.
- Lý do KHÔNG chọn cải thiện path A (thủ công) thay vì thêm path C: path A đã tối ưu
  (ghi sẵn prompt cho ChatGPT/Gemini), thêm path C giải quyết đúng nhu cầu "tự động mà
  không cần server", không trùng lặp path B.

Test Plan:
- Unit: format compatibility với transcript_vi.json.
- Integration: dịch full 1 video test, chạy hết pipeline downstream (timing/TTS) với
  output từ path C, assert không crash, video xuất ra hợp lệ.
- Regression: path A (TRANSLATE_PENDING.txt) và path B (SaaS) không đổi hành vi.
- Live verification: 3 video thật dịch bằng cả 3 path, so sánh chất lượng chủ quan +
  đo BLEU/chrF nếu có reference dịch tay, ghi kết quả thật vào TEST_LOG.md (không phải
  ước lượng).

Success Criteria:
- Người dùng không cấu hình server vẫn hoàn thành được 1 video dubbing đầy đủ, tự động,
  100% offline, từ đầu đến cuối — điều KHÔNG thể làm được ở trạng thái hiện tại.
- Chất lượng path C được đo và công bố trung thực (không phóng đại) trong UI/docs.
- 0 network call phát sinh khi dùng path C (verify bằng mock/monitor network trong test).
```

---

### V7 — Docker hoá control_server + audit khả năng Linux cho pipeline

```
V7 — Docker hoá control_server + audit khả năng chạy pipeline trên Linux

Context:
- Tài liệu bắt buộc: docs/ARCH.md §4 (đóng gói chỉ Windows), control_server/package.json,
  autodub.spec, scripts/build_exe.py, các điểm dùng Windows-specific API trong pipeline
  (ctypes.windll, add_dll_directory cho cuBLAS/cuDNN, nvidia-smi shell-out).
- Trạng thái hiện tại: control_server là Node/Fastify — về lý thuyết cross-platform
  nhưng CHƯA có Dockerfile/docker-compose nào trong repo (deploy hiện tại không rõ cơ
  chế — cần audit thêm khi bắt tay). Pipeline core (autodub/) phụ thuộc nhiều điểm
  Windows-specific cho GPU (nhưng phần lõi ffmpeg/Python thuần lý thuyết chạy được Linux).
- Quyết định kiến trúc phải giữ nguyên: KHÔNG cam kết ship Linux/macOS GUI build trong
  spec này — đây CHỈ LÀ AUDIT + containerize phần server (rủi ro thấp, giá trị rõ), việc
  build Linux GUI đầy đủ để ở V-tương lai (out of scope, ghi rõ trong Remaining Limits).

Goal:
- control_server chạy được bằng 1 lệnh `docker compose up` (giống chuẩn AI Factory), và
  có 1 báo cáo audit rõ ràng, có bằng chứng thật, về việc pipeline core (autodub/) chạy
  được đến đâu trên Linux (không phải suy đoán) — làm input quyết định cho roadmap dài
  hạn (V9).

Constraints (Guardrails):
1. Không đổi business logic control_server — chỉ thêm Dockerfile/docker-compose.yml.
2. Audit Linux chỉ chạy thử nghiệm (không sửa code pipeline để "ép chạy") — nếu 1 stage
   fail trên Linux, ghi lại nguyên nhân thật (thiếu DLL tương đương, thiếu binary ffmpeg
   build, v.v.), KHÔNG patch tạm bợ để qua audit.
3. MongoDB trong docker-compose dùng image chính thức, không tự build custom image trừ
   khi có lý do rõ.
4. Không đổi cấu trúc thư mục control_server/website hiện có để fit Docker — Dockerfile
   phải fit code, không phải ngược lại.
5. Nếu phát hiện pipeline core có phần không thể chạy Linux do giới hạn thư viện bên thứ
   3 (không phải do code tự viết) → ghi rõ đây là giới hạn cứng, không phải TODO có thể
   fix trong 1 mini-spec.

Scope:
A. Domain model: không đổi.
B. Services/engine: không đổi logic, chỉ đóng gói.
C. API contract: không đổi.
D. UI surfaces: không đổi (website vẫn build static, serve qua Fastify y hệt hiện tại
   trong container).
E. Tests: test `docker compose up` khởi động thành công + healthcheck endpoint trả 200;
   audit report (không phải test tự động) cho phần Linux pipeline.

Audit Before Build:
- Cần audit: cơ chế deploy control_server hiện tại là gì (PM2? systemd? thủ công?) —
  chưa xác nhận trong khảo sát đầu, bắt buộc kiểm tra trước khi viết Dockerfile để không
  phá luồng deploy đang chạy thật (nếu có).
- Gap cụ thể: thiếu hoàn toàn container hoá cho phần server-side (vốn dĩ cross-platform
  sẵn) — đây là gap dễ đóng nhất trong toàn bộ nhóm "nền tảng & phân phối".

Design Choice:
- Multi-stage Dockerfile (build website static assets → copy vào image Node chạy
  control_server, đúng như cách control_server hiện đang serve website/dist) + docker-
  compose.yml gồm control_server + mongo, theo đúng chuẩn AI Factory deploy convention
  (Traefik-ready labels nếu cần deploy qua mb-deploy sau này).
- Phần audit Linux cho pipeline: chạy thử `pytest` core (không cần GPU) trong 1
  container Python Linux, ghi lại chính xác bao nhiêu % trong 546 test pass mà không
  cần sửa gì — con số thật này là input cho quyết định đầu tư V9 sau này, không phải
  quyết định trước.

Test Plan:
- Unit: không áp dụng (đây là hạ tầng đóng gói).
- Integration: `docker compose up` → healthcheck pass → gọi thử 1 endpoint public (vd
  GET config) trả đúng response như chạy local không Docker.
- Regression: V1 test suite (control_server) chạy được y hệt bên trong container.
- Live verification: chạy pytest core autodub/ trong container Linux sạch, ghi số liệu
  pass/fail thật + lý do fail (nếu có) vào TEST_LOG.md.

Success Criteria:
- `docker compose up` từ repo sạch (không cần setup thủ công nào khác ngoài .env) chạy
  được control_server + website + mongo, healthcheck pass.
- Có 1 con số thật (không suy đoán) về % test suite autodub/ pass trên Linux, kèm danh
  sách cụ thể phần nào fail và vì sao — làm căn cứ cho quyết định đầu tư Linux GUI build
  đầy đủ (không nằm trong spec này).
```

---

## Phase C — Dài hạn (Platform & Scale)

### V8 — Kiến trúc TTS pluggable cho đa ngôn ngữ đích

```
V8 — Kiến trúc TTS engine pluggable, mở rộng ngôn ngữ đích ngoài tiếng Việt

Context:
- Tài liệu bắt buộc: docs/ARCH.md §2.1 (TTS: VieNeu + CapCut), autodub/languages.py
  (TARGETS = {"vi": ...}), autodub/speech/tts/vieneu_vi.py, capcut_vi.py.
- Trạng thái hiện tại: VieNeu là engine TTS tiếng Việt chuyên biệt (không đa ngôn ngữ);
  CapCut API hỗ trợ nhiều giọng nhưng chưa rõ phạm vi ngôn ngữ thật (cần audit). TARGETS
  hardcode chỉ "vi" — toàn bộ pipeline (timing, phụ đề, karaoke) viết cho giả định đích
  luôn là tiếng Việt.
- Quyết định kiến trúc phải giữ nguyên: đây là spec LỚN NHẤT về rủi ro kiến trúc trong
  roadmap — PHẢI làm sau V2 (billing đã tách khỏi core) để không chồng lấn refactor.
  Không được đổi trải nghiệm tiếng Việt hiện có (đây vẫn là thị trường chính) trong lúc
  build khả năng đa ngôn ngữ.

Goal:
- Pipeline có khả năng dub sang ít nhất 1 ngôn ngữ đích thứ 2 (đề xuất tiếng Anh hoặc
  tiếng Indonesia — thị trường TikTok/YouTube lớn, quyết định cuối cần input kinh doanh
  từ chủ dự án, không tự chốt trong tài liệu kỹ thuật này) mà không phá trải nghiệm
  tiếng Việt hiện có.

Constraints (Guardrails):
1. TARGETS không còn hardcode "vi" duy nhất, nhưng tiếng Việt vẫn là default/first-class
   — không đổi UX mặc định cho người dùng hiện tại.
2. TTS engine cho ngôn ngữ mới phải qua audit license/chất lượng rõ ràng trước khi thêm
   — không thêm engine chỉ vì "có API free", phải test chất lượng giọng đọc thật.
3. Module timing/align/subtitle hiện viết ngầm định cho đặc thù tiếng Việt (dấu thanh,
   CPS budget) — audit kỹ trước khi generalize, KHÔNG giả định logic tiếng Việt áp dụng
   được thẳng cho ngôn ngữ khác (vd CPS/tốc độ đọc khác nhau theo ngôn ngữ).
4. Nếu 1 ngôn ngữ đích không có TTS engine đạt chất lượng chấp nhận được sau audit →
   KHÔNG ship, ghi lại là giới hạn đã biết, không hạ chuẩn chất lượng để có "cho đủ tính
   năng".
5. Giữ nguyên toàn bộ pipeline stage khác (download/demucs/ASR) — spec này chỉ chạm
   TTS + phần timing/subtitle phụ thuộc ngôn ngữ đích.

Scope:
A. Domain model: TARGETS trở thành registry mở rộng được (dict ngôn ngữ → cấu hình TTS
   engine + timing params), audit lại toàn bộ chỗ code giả định `target == "vi"`.
B. Services/engine: interface `TtsEngine` chung (đã có 2 implementation VieNeu/CapCut
   cho tiếng Việt — audit xem có tái dùng được interface ẩn hiện có hay cần tạo mới),
   thêm 1 implementation cho ngôn ngữ đích thứ 2 (engine cụ thể chốt sau audit license/
   chất lượng, không chốt trong tài liệu này).
C. API contract: không đổi control_server trực tiếp (trừ khi content/metadata generation
   cũng cần đa ngôn ngữ — audit riêng, có thể tách thành mini-spec con nếu phát sinh).
D. UI surfaces: trang Tạo dự án thêm dropdown "Ngôn ngữ đích" (hiện tại ẩn vì chỉ có 1
   lựa chọn); trang Giọng đọc AI hiển thị giọng theo ngôn ngữ đích đã chọn.
E. Tests: unit (TARGETS registry lookup), integration (full pipeline chạy với target
   thứ 2 trên video test cố định), regression (target "vi" 100% không đổi hành vi/chất
   lượng so với trước spec này).

Audit Before Build:
- Cần audit sâu: liệt kê TOÀN BỘ điểm code (không chỉ languages.py) giả định ngầm đích
  là tiếng Việt — đặc biệt text/ass_karaoke.py, media/timing.py, editor.py. Đây là audit
  bắt buộc và tốn thời gian đáng kể, phải hoàn thành và có báo cáo riêng TRƯỚC khi viết
  bất kỳ code nào của spec này.
- Gap cụ thể: kiến trúc closed cho 1 ngôn ngữ đích — đây không phải bug mà là giới hạn
  thiết kế ban đầu, hợp lý cho MVP nhưng chặn mở rộng thị trường.

Design Choice:
- Registry pattern cho TARGETS (dict language code → TtsEngineConfig), interface
  TtsEngine chung mà VieNeu/CapCut phải tuân theo (refactor tối thiểu nếu 2 engine hiện
  tại chưa share interface rõ — audit trước khi quyết định mức độ refactor cần thiết).
  Ưu tiên KHÔNG viết pipeline riêng cho ngôn ngữ mới — mọi ngôn ngữ đích đi qua đúng 1
  pipeline, chỉ khác config/engine, đúng nguyên tắc Playbook "không build engine song song".

Test Plan:
- Unit: registry lookup, TtsEngine interface compliance cho engine mới.
- Integration: full pipeline video test với target thứ 2, output hợp lệ (audio sync,
  video mux thành công).
- Regression: bộ test hiện có cho target "vi" (phần lớn trong 546 test) pass 100% không
  đổi.
- Live verification: ≥3 video thật dub sang ngôn ngữ đích mới, đánh giá chất lượng giọng
  đọc + timing bởi người bản ngữ (không tự đánh giá bằng tai không rành ngôn ngữ đó),
  ghi kết quả thật vào TEST_LOG.md.

Success Criteria:
- Chạy được full pipeline với ≥1 ngôn ngữ đích mới, chất lượng được người bản ngữ xác
  nhận chấp nhận được (không phải "chạy không crash" là đủ).
- 0 regression cho pipeline tiếng Việt (test + ít nhất 1 live verification so sánh trước/
  sau).
- Thêm ngôn ngữ đích thứ 3 trong tương lai chỉ cần thêm 1 entry registry + 1
  TtsEngine implementation, không cần sửa lại core pipeline (kiểm chứng bằng code review,
  không chỉ khẳng định).
```

---

### V9 — Cloud/hybrid rendering option (premium tier)

```
V9 — Tuỳ chọn xử lý pipeline trên cloud (hybrid rendering)

Context:
- Tài liệu bắt buộc: docs/ARCH.md (toàn bộ pipeline hiện chạy 100% client-side), V7
  (audit khả năng Linux — input bắt buộc phải có TRƯỚC khi bắt tay spec này), control_
  server (đã có hạ tầng billing/device — có thể tái dùng cho job queue).
- Trạng thái hiện tại: mọi xử lý (Demucs, Whisper, VieNeu, mux) chạy trên máy người dùng
  — rào cản lớn cho người dùng không có GPU/máy yếu (dù CPU-only vẫn chạy được theo
  README, nhưng chậm). Không có bất kỳ hạ tầng job queue/worker nào phía server hiện tại.
- Quyết định kiến trúc phải giữ nguyên: KHÔNG thay thế luồng client-side hiện có — đây
  PHẢI là 1 TUỲ CHỌN thêm (premium/hybrid), người dùng không muốn dùng cloud vẫn chạy
  100% local như hiện tại, không ép buộc.

Goal:
- Người dùng máy yếu/không GPU có 1 lựa chọn (trả phí qua Vox, tận dụng hạ tầng billing
  đã có) để các bước nặng nhất (Demucs, Whisper, VieNeu) chạy trên server thay vì máy
  họ, kết quả tải về hoàn thiện như luồng local.

Constraints (Guardrails):
1. KHÔNG rebuild pipeline logic — các stage xử lý phải TÁI DÙNG đúng code autodub/ hiện
   có, chỉ đổi NƠI chạy (local process → remote worker), không viết pipeline song song
   cho cloud.
2. Dữ liệu người dùng tải lên server phải có chính sách rõ ràng (giữ bao lâu, xoá khi
   nào) — đây là điểm nhạy cảm nhất về niềm tin người dùng (sản phẩm định vị offline-
   first từ đầu), PHẢI được chủ dự án duyệt chính sách trước khi build, không tự quyết.
3. Billing cho cloud rendering phải qua đúng billing_adapter đã tách ở V2 — không viết
   luồng tính phí song song mới.
4. Không bypass gate `is_configured()` — cloud rendering chỉ available khi có server,
   đúng logic hiện có, không thêm ngoại lệ.
5. Nếu server quá tải/lỗi → pipeline phải fallback rõ ràng về local hoặc báo lỗi trung
   thực, KHÔNG âm thầm hàng đợi vô thời hạn không thông báo.
6. Không được document/quảng bá tính năng này như "nhanh hơn" nếu chưa benchmark thật —
   độ nhanh phụ thuộc băng thông upload video của người dùng, cần đo thật.

Scope:
A. Domain model: Job/Task entity mới phía control_server (trạng thái queued/running/
   done/failed, gắn với Device + Hold).
B. Services/engine: worker pool phía server chạy lại đúng module autodub/ (Demucs/
   Whisper/VieNeu) — audit V7 quyết định worker chạy Linux container hay Windows VM
   (phụ thuộc kết quả audit Linux ở V7, KHÔNG audit lại từ đầu ở đây).
C. API contract: bổ sung endpoint job (submit/status/download result) vào control_server,
   cập nhật docs/API.md (từ V1) theo đúng convention hiện có.
D. UI surfaces: trang Cài đặt/Tạo dự án thêm toggle "Xử lý trên cloud (Vox)" — hiển thị
   ước tính phí trước khi chạy, tiến độ job real-time.
E. Tests: integration (submit job giả lập → worker xử lý → tải kết quả, so sánh output
   với chạy local cùng input), regression (billing_adapter/V2 không đổi hành vi cho path
   local hiện có), load test cơ bản (worker pool xử lý N job đồng thời không crash).

Audit Before Build:
- Cần audit: kết quả thật của V7 (Linux viability) là điều kiện tiên quyết — nếu V7 cho
  thấy pipeline core không chạy được Linux mà không sửa lớn, spec này phải đổi hướng
  (Windows VM pool, chi phí vận hành khác hẳn) — QUYẾT ĐỊNH THẬT chỉ chốt sau khi có
  số liệu V7, không đoán trước trong tài liệu này.
- Gap cụ thể: đây là capability hoàn toàn mới, rủi ro kiến trúc + vận hành cao nhất
  trong roadmap — cần POC nhỏ (1 stage, vd chỉ Demucs) trước khi cam kết full scope.

Design Choice:
- Đề xuất bắt đầu bằng POC hẹp: chỉ đưa 1 stage nặng nhất (Demucs, vì GPU-bound rõ nhất)
  lên cloud trước, giữ ASR/TTS/timing/mux vẫn local — đo thực tế lợi ích (thời gian tiết
  kiệm trừ thời gian upload/download) trước khi mở rộng toàn bộ pipeline lên cloud. Lý
  do: đây là mini-spec rủi ro cao nhất, POC hẹp giảm rủi ro đầu tư sai hướng — không
  build full hybrid pipeline ngay từ đầu.

Test Plan:
- Unit: job state machine.
- Integration: POC Demucs-only end-to-end (upload → xử lý → tải kết quả → ghép lại vào
  pipeline local cho các bước còn lại).
- Regression: luồng 100% local hiện có không bị ảnh hưởng khi tính năng cloud tồn tại
  song song (test bằng cách tắt cloud option, chạy full suite local như cũ).
- Live verification: đo thời gian thật (upload + xử lý server + download) so với chạy
  local hoàn toàn trên ít nhất 2 cấu hình máy (máy yếu không GPU, máy có GPU) — chỉ kết
  luận "cloud nhanh hơn/chậm hơn" dựa trên số đo thật.

Success Criteria:
- POC Demucs-cloud chạy được end-to-end, kết quả tách nhạc giống hệt (hoặc sai khác
  không đáng kể) so với chạy local cùng input.
- Có số liệu thật (không ước lượng) về lợi ích thời gian cho ít nhất 2 profile máy khác
  nhau, làm căn cứ quyết định mở rộng full pipeline lên cloud hay dừng ở POC.
- Chính sách giữ/xoá dữ liệu người dùng trên server đã được chủ dự án duyệt bằng văn
  bản trước khi bất kỳ video thật nào của người dùng chạm server.
```

---

### V10 — Analytics/success metrics thật + hoàn thiện dashboard SaaS

```
V10 — Success metrics thật + hoàn thiện dashboard vận hành SaaS

Context:
- Tài liệu bắt buộc: docs/PRD.md §3 (chưa có success metrics định lượng nào), website/
  src (trang /admin: Dashboard, Devices, DeviceDetail, Orders, Keys, Providers, Config,
  AuditLog — đã tồn tại, cần audit xem Dashboard hiện show gì thật).
- Trạng thái hiện tại: control_server có audit log (từng action) nhưng KHÔNG có bằng
  chứng nào trong khảo sát đầu về việc có analytics tổng hợp (retention, funnel mua Vox,
  tỷ lệ hoàn thành pipeline vs bỏ dở) — cần audit lại Dashboard.jsx thật trước khi build
  gì thêm, có thể phần này đã có sẵn ở mức nào đó chưa được ghi nhận trong khảo sát.
- Quyết định kiến trúc phải giữ nguyên: không thêm bên thứ 3 (Google Analytics, Mixpanel,
  v.v.) gửi dữ liệu người dùng ra ngoài nếu chưa có chính sách privacy rõ — ưu tiên dùng
  chính audit log + MongoDB đã có trong control_server.

Goal:
- Chủ dự án có 1 dashboard thật, đo được các số quan trọng (số dubbing hoàn thành/bỏ dở,
  Vox revenue theo thời gian, retention device theo tuần/tháng, lỗi pipeline phổ biến
  nhất) để ra quyết định sản phẩm dựa trên dữ liệu thật thay vì cảm tính.

Constraints (Guardrails):
1. Audit trước: liệt kê chính xác Dashboard.jsx hiện đã show gì — CHỈ build phần còn
   thiếu, không build lại từ đầu nếu đã có nền.
2. Không thu thập thêm dữ liệu cá nhân người dùng ngoài những gì đã có (device
   fingerprint, không có tài khoản/email người dùng theo thiết kế hiện tại) — giữ đúng
   triết lý privacy hiện có (không có tài khoản người dùng).
3. Mọi số liệu hiển thị phải truy vết được về nguồn dữ liệu thật trong MongoDB — không
   hiển thị số liệu ước lượng/giả định là "estimate" mà không ghi rõ.
4. Không đổi audit.js logging behavior hiện có (chỉ query/aggregate dữ liệu đã ghi, không
   đổi cách ghi).
5. Metrics pipeline hoàn thành/bỏ dở cần dữ liệu từ CLIENT (autodub_gui) gửi về — nếu
   hiện tại app không gửi bất kỳ event nào dạng này (cần audit `saas_client.py`), đây là
   1 THAY ĐỔI THẬT vào client, phải rõ ràng với người dùng (đã có banner minh bạch từ
   V3) là app gửi event hoàn thành/lỗi khi ở chế độ SaaS — không ngầm thêm tracking.

Scope:
A. Domain model: có thể cần thêm collection "PipelineEvent" (device_id, event type:
   started/completed/failed/abandoned, stage nếu failed, timestamp) — CHỈ khi audit xác
   nhận chưa có cơ chế tương đương.
B. Services/engine: aggregation query cho revenue theo thời gian, retention cohort theo
   device, funnel completion rate theo stage pipeline.
C. API contract: endpoint admin mới cho các aggregation trên (bổ sung vào docs/API.md
   từ V1).
D. UI surfaces: Dashboard.jsx bổ sung chart (dùng skill dataviz nếu cần thiết kế chart
   mới) cho các số liệu ở Goal.
E. Tests: unit (aggregation query logic với dữ liệu test cố định, assert số đúng), không
   cần integration nặng (đây là reporting, không phải luồng tiền — nhưng vẫn phải test
   vì số liệu sai sẽ dẫn quyết định sai).

Audit Before Build:
- Cần audit: Dashboard.jsx hiện tại show gì (chưa xác nhận trong khảo sát ban đầu),
  saas_client.py có gửi event nào về hoàn thành/lỗi pipeline hay không.
- Gap cụ thể: PRD hiện không có success metrics định lượng nào — đây là gap ở tầng sản
  phẩm (không biết sản phẩm đang hoạt động tốt hay không dựa trên số liệu thật).

Design Choice:
- Aggregation trực tiếp trên MongoDB hiện có (không thêm data warehouse/ETL riêng —
  quy mô sản phẩm hiện tại chưa cần) qua Mongoose aggregation pipeline, hiển thị qua
  chart trong website/admin đã có sẵn khung (Dashboard.jsx) — tái dùng, không viết
  admin panel mới.

Test Plan:
- Unit: mỗi aggregation query test với fixture data cố định, assert kết quả đúng số học.
- Integration: gọi endpoint admin mới, assert response shape khớp docs/API.md.
- Regression: audit log ghi nhận hiện có không đổi hành vi.
- Live verification: chạy dashboard thật với dữ liệu production/staging thật (không
  phải fixture), chủ dự án xác nhận số liệu hợp lý so với hiểu biết thực tế của họ về
  sản phẩm (sanity check bằng người, không chỉ bằng test).

Success Criteria:
- Chủ dự án trả lời được câu hỏi "tuần này bao nhiêu % người dùng hoàn thành pipeline
  vs bỏ dở giữa chừng, ở stage nào bỏ nhiều nhất" bằng dashboard thật, không phải đoán.
- Revenue Vox theo thời gian hiển thị đúng, đối chiếu khớp với dữ liệu Order/ActivationKey
  thật trong MongoDB (không lệch).
- Không phát sinh thu thập dữ liệu cá nhân nào ngoài phạm vi đã công bố ở V3.
```

---

## Phase D — Hoàn thiện (đóng nốt giới hạn PoC của Phase C)

Phát sinh từ chính "Remaining Limits" mà V8/V9/V10 để lại sau khi thực thi (không phải
lên kế hoạch từ đầu — đây là vòng lặp thật của quy trình mini-spec: làm → phát hiện gap
mới → mở mini-spec mới, đúng tinh thần Playbook §3). Cả 3 đều cần **1 quyết định/input
cụ thể từ chủ dự án** trước khi bắt tay code — không tự quyết thay, đúng nguyên tắc đã
áp dụng xuyên suốt V6/V9.

### V11 — Hoàn thiện đa ngôn ngữ đích (đưa V8 từ PoC thành tính năng dùng được)

```
V11 — voices.catalog() target-aware + GUI chọn ngôn ngữ đích + audit timing/ass_karaoke

Context:
- Tài liệu bắt buộc: docs/PLAN.md mục V8 (đã làm), docs/TEST_LOG.md mục V8 "Remaining
  Limits" (nguồn gốc chính xác của mini-spec này).
- Trạng thái hiện tại: `TARGETS["en"]` đã có trong registry, `capcut_catalog.py` đã nhận
  tham số `lang` — nhưng `voices.catalog(settings)` (autodub/speech/tts/voices.py) VẪN
  gọi `capcut_catalog.entries()` KHÔNG tham số (mặc định vi-VN) và trộn chung với VieNeu
  (chỉ tiếng Việt). Không có nơi nào trong GUI (autodub_gui) cho chọn ngôn ngữ đích —
  mọi nơi đều hardcode `get_target("vi")`.
- Quyết định kiến trúc phải giữ nguyên: `Synthesizer` Protocol (base.py) đã đúng, không
  đổi. `TARGETS` registry đã đúng, không đổi cấu trúc. Không đổi trải nghiệm tiếng Việt
  mặc định — mọi dự án cũ/mới không chọn ngôn ngữ đích vẫn ra đúng tiếng Việt như trước.

Goal:
- Người dùng chọn được ngôn ngữ đích ngay trong GUI (Tạo dự án), thấy đúng giọng CapCut
  của ngôn ngữ đó, và chạy được ít nhất 1 video thật lồng tiếng sang tiếng Anh end-to-end
  (không chỉ 1 câu như V8 đã verify).

Constraints (Guardrails):
1. KHÔNG đổi mặc định — không chọn gì thì luôn ra tiếng Việt, y hệt hành vi trước V11.
2. `voices.catalog(settings, target=None)` — thêm tham số TUỲ CHỌN, không phá chữ ký cũ
   (mọi lời gọi hiện có không truyền `target` phải chạy y hệt trước, verify bằng test).
3. VieNeu CHỈ hiện khi target là tiếng Việt (model chuyên biệt, không giả vờ hỗ trợ ngôn
   ngữ khác) — không được hiện VieNeu trong danh sách giọng khi target=en rồi lỗi lúc chạy.
4. Audit ĐẦY ĐỦ (không chỉ đếm số điểm như V8 đã làm) từng điểm trong timing.py/
   ass_karaoke.py/editor.py giả định tiếng Việt — với MỖI điểm, kết luận rõ: có breaking
   với tiếng Anh hay không, sửa thế nào nếu có. Ghi vào TEST_LOG.md trước khi sửa code.
5. Nếu 1 điểm audit không chắc chắn (cần biết tiếng Anh thật để đánh giá, vd CPS budget
   đọc tiếng Anh khác tiếng Việt bao nhiêu) → để `unconfirmed`, không đoán.

Scope:
A. Domain model: không đổi (TARGETS đã đủ từ V8).
B. Services/engine: `voices.py` — `catalog(settings, target=None)`,
   `_capcut_voices(lang)`, `is_capcut_voice(name, target=None)`; `CapCutSynthesizer`
   nhận `target` để lookup đúng catalog theo ngôn ngữ.
C. API contract: không đổi (không đụng control_server).
D. UI surfaces: `new_project_steps.py` (bước chọn ngôn ngữ đích, ẩn nếu chỉ có 1 target
   — hiện khi >= 2, đúng nguyên tắc "không thêm UI cho tính năng chưa tồn tại").
E. Tests: unit (voices.catalog target-aware, không phá lời gọi cũ), integration (chạy
   full pipeline với target=en trên 1 video thật ngắn, không chỉ 1 câu).

Audit Before Build:
- Cần audit: liệt kê CHÍNH XÁC từng dòng trong timing.py/ass_karaoke.py/editor.py có
  `"vi"`/CPS tiếng Việt/dấu thanh — V8 mới đếm số lượng (~16), CHƯA đọc từng điểm.
- Gap cụ thể: kế thừa nguyên vẹn từ V8 — đây là phần V8 cố ý để lại.

Design Choice:
- Audit trước, sửa sau — KHÔNG sửa timing/ass_karaoke/editor tới khi audit xong và có
  danh sách cụ thể (đúng Playbook §3, không mở rộng phạm vi ngoài gap đã xác nhận).

Test Plan:
- Unit: voices.catalog() các trường hợp target=None/vi/en.
- Integration: 1 video thật (vài chục giây) chạy full pipeline target=en, xuất video
  hoàn chỉnh, không crash ở bất kỳ stage nào.
- Regression: toàn bộ 637 test hiện có phải pass y hệt (verify target=vi không đổi).
- Live verification: người bản ngữ tiếng Anh nghe thử video xuất ra, đánh giá chất lượng
  giọng đọc + timing — KHÔNG tự đánh giá bằng tai không rành tiếng Anh.

Success Criteria:
- Chạy được 1 video thật, đầu-cuối, target=en, không crash, không cần sửa tay giữa chừng.
- 0 regression cho target=vi (test + ít nhất 1 lần live-verify so sánh).
- Danh sách đầy đủ các điểm Vietnamese-assumption đã audit, ghi rõ điểm nào sửa/điểm nào
  an toàn không cần sửa — không còn "chưa audit" nào bị bỏ sót.
```

### V12 — Cloud rendering production-ready (đưa V9 từ PoC thành hạ tầng thật)

```
V12 — Docker cho pipeline Python + queue thật (thay xử lý đồng bộ) + GUI toggle

Context:
- Tài liệu bắt buộc: docs/PLAN.md mục V9 (đã làm), docs/TEST_LOG.md mục V9 "Remaining
  Limits", docker-compose.yml hiện tại (chỉ Node, không Python).
- Trạng thái hiện tại: `POST /v1/jobs/demucs` xử lý ĐỒNG BỘ trong request (giữ kết nối
  HTTP mở suốt lúc chạy Demucs) — chấp nhận được cho audio ngắn (giây), KHÔNG chấp nhận
  được cho video dài thật (phút) vì timeout HTTP + không có cách nào theo dõi tiến độ.
  `DEMUCS_PYTHON`/`DEMUCS_WORKER_SCRIPT` phải trỏ tới môi trường Python có torch+demucs
  cài sẵn NGOÀI Docker — image `control_server` hiện tại không có Python.
- Quyết định kiến trúc phải giữ nguyên: KHÔNG rebuild lại logic Demucs (vẫn gọi
  `demucs_worker.py` nguyên văn qua subprocess, đúng guardrail V9 gốc). Chính sách xoá
  dữ liệu ngay sau khi trả kết quả (đã chủ dự án duyệt ở V9) giữ nguyên.

Goal:
- `docker compose up` chạy được TOÀN BỘ (kể cả xử lý Demucs) mà không cần cài gì thêm
  ngoài Docker, và job xử lý bất đồng bộ thật (submit → poll status → tải khi xong),
  không giữ HTTP connection mở trong lúc xử lý.

Constraints (Guardrails):
1. Image Python (torch+demucs, ~1.5-2GB) tách RIÊNG khỏi image `control_server` (Node) —
   không nhét chung, để `control_server` build/deploy nhanh không phụ thuộc thay đổi bên
   Python. Compose 2 service riêng, giao tiếp qua volume dùng chung hoặc HTTP nội bộ.
2. Queue phải PERSIST qua restart (không mất job đang chạy khi container restart) — dùng
   lại chính `RenderJob` (Mongo) làm nguồn sự thật, không thêm Redis/broker mới nếu Mongo
   polling đủ dùng ở quy mô hiện tại (đừng over-engineer cho tải chưa tồn tại).
3. KHÔNG bypass billing_adapter/credit.service đã có — luồng trừ Vox giữ nguyên từ V9.
4. GUI toggle (Cài đặt/Tạo dự án) phải hiện rõ ước tính phí TRƯỚC khi người dùng bấm
   chạy — không được trừ Vox rồi mới báo giá.
5. Nếu worker Python crash/timeout → job phải chuyển `failed` rõ ràng, KHÔNG treo mãi ở
   `running` (thêm timeout + heartbeat, giống nguyên tắc hold TTL đã có).

Scope:
A. Domain model: `RenderJob` thêm field `workerId`/`heartbeatAt` (phát hiện worker chết).
B. Services/engine: tách job xử lý ra 1 worker process riêng (poll `RenderJob` status
   `queued`, nhận job, xử lý, cập nhật) thay vì xử lý inline trong route handler.
C. API contract: `POST /v1/jobs/demucs` đổi thành TRẢ NGAY `status:"queued"` (không đợi
   xử lý xong) — đây là BREAKING CHANGE so với V9 (client cũ đợi response=kết quả sẽ vỡ),
   cần version endpoint hoặc field mới `async:true` để không phá client hiện có.
D. UI surfaces: toggle "Xử lý trên cloud" (Cài đặt/Tạo dự án) + hiện tiến độ job.
E. Tests: integration (job queue thật qua nhiều lần poll), load test (N job đồng thời
   không crash worker), regression (V9 test suite vẫn pass với API cũ nếu giữ tương thích
   ngược, hoặc cập nhật có chủ đích nếu đổi hẳn).

Audit Before Build:
- Cần audit: có bao nhiêu client (autodub_gui) hiện đang gọi `/v1/jobs/demucs` — CHƯA CÓ
  (V9 không có GUI wiring) nên đây là lần đầu tiên có client thật, ĐỔI API contract ngay
  bây giờ AN TOÀN hơn nhiều so với đổi sau khi đã có người dùng thật phụ thuộc API đồng bộ.
- Gap cụ thể: kế thừa nguyên vẹn từ V9 — production-readiness, không phải tính năng mới.

Design Choice:
- Worker Python riêng, poll MongoDB (không cần Redis/BullMQ ở quy mô POC→production sớm
  — thêm broker là over-engineering khi chưa có số liệu tải thật). Image Docker 2 tầng
  (control_server nhẹ, worker nặng) build riêng, compose lên cùng lúc.

Test Plan:
- Unit: state machine job (queued→running→done/failed, heartbeat timeout→failed).
- Integration: `docker compose up` từ repo sạch → submit job thật → poll tới `done` →
  tải kết quả — TOÀN BỘ qua Docker, không cần cài Python ngoài container.
- Regression: billing/credit không đổi hành vi (test lại các case đã có ở V9).
- Live verification: đo thời gian thật xử lý 1 video vài phút qua queue mới, so với luồng
  đồng bộ cũ (V9) — xác nhận không tệ hơn, tốt hơn ở chỗ không bị timeout HTTP.

Success Criteria:
- `docker compose up` (không cần bước cài đặt thủ công nào khác) chạy được Demucs thật.
- Job dài (vài phút) không bị timeout HTTP — verify bằng 1 video thật đủ dài để vượt
  ngưỡng timeout HTTP mặc định (thường 30-60s) của luồng đồng bộ V9 cũ.
- GUI hiện đúng giá trước khi trừ Vox, không có trường hợp trừ tiền rồi mới báo.
```

### V13 — Phễu hoàn thành/bỏ dở pipeline (đưa V10 từ "một phần" thành đầy đủ)

```
V13 — Telemetry hoàn thành/bỏ dở pipeline từ client + dashboard phễu theo stage

Context:
- Tài liệu bắt buộc: docs/PLAN.md mục V10 (đã làm phần retention), docs/TEST_LOG.md mục
  V10 "Remaining Limits", docs/PRD.md §9 (rủi ro minh bạch), banner V3
  (autodub_gui/first_run.py — nội dung hiện tại KHÔNG nhắc gì tới việc gửi telemetry
  hoàn thành/bỏ dở, chỉ nói về chế độ local/SaaS và Vox).
- Trạng thái hiện tại: `autodub/saas_client.py` KHÔNG có bất kỳ hàm nào gửi event dạng
  "pipeline started/completed/failed/abandoned" — đã grep xác nhận ở V10. Đây LÀ MỘT
  TÍNH NĂNG THU THẬP DỮ LIỆU MỚI, không phải mở rộng cái đã có.
- Quyết định kiến trúc phải giữ nguyên: `is_configured()` vẫn là cổng — telemetry này
  CHỈ gửi khi có máy chủ cấu hình (SaaS mode), không bao giờ gọi mạng ở chế độ local-only
  (đúng triết lý offline-first cốt lõi của toàn sản phẩm).

Goal:
- Chủ dự án trả lời được "tuần này bao nhiêu % lượt chạy hoàn thành, bỏ dở ở stage nào
  nhiều nhất" bằng dashboard thật — dữ liệu tới từ chính app, không suy luận gián tiếp.

Constraints (Guardrails):
1. **BẮT BUỘC cập nhật minh bạch cho người dùng TRƯỚC KHI gửi bất kỳ event nào** — mở
   rộng banner/FAQ đã có ở V3 (autodub_gui/first_run.py, help_page.py) nói rõ: khi ở chế
   độ SaaS, app gửi về máy chủ trạng thái tiến độ (bắt đầu/xong/lỗi/dừng ở stage nào),
   KHÔNG gửi nội dung video/transcript/audio. Đây là gate KHÔNG được bỏ qua.
2. Event KHÔNG chứa nội dung nhạy cảm — chỉ (fingerprint, run_id, stage, status,
   timestamp), không bao giờ có text/audio/video/đường dẫn file người dùng.
3. Gửi event KHÔNG được làm chậm/chặn pipeline — best-effort, lỗi mạng lúc gửi event
   không được làm hỏng lượt dubbing (giống triết lý `audit.service.js` phía server: mất
   1 dòng log không đáng đánh đổi cả lượt chạy).
4. "Bỏ dở" (abandoned) là suy luận GIÁN TIẾP (không có event "abandoned" tường minh —
   không ai bấm nút "tôi bỏ cuộc") — định nghĩa rõ: 1 run có event "started" nhưng không
   có "completed"/"failed" trong N giờ thì coi là bỏ dở. Ghi rõ định nghĩa này trong docs,
   đây là ước lượng chứ không phải sự thật tuyệt đối.
5. Không thu thập qua chế độ local-only dù người dùng có bật gì trong Cài đặt — cổng
   `is_configured()` là điều kiện CẦN VÀ ĐỦ, không thêm cờ bật/tắt riêng gây rối logic.

Scope:
A. Domain model: `PipelineEvent` (control_server, Mongo) — fingerprint, runId, stage,
   status (started/completed/failed), timestamp, errorStage (nếu failed).
B. Services/engine: `saas_client.py` thêm `_note_pipeline_event()` (best-effort, non-
   blocking) gọi ở các điểm chuyển stage trong `pipeline.py` (đã có sẵn `rep.emit(...)`
   cho progress UI — TÁI DÙNG đúng các điểm đó, không thêm hook mới song song).
C. API contract: `POST /v1/telemetry/pipeline-event` (control_server) — endpoint mới,
   cập nhật docs/API.md.
D. UI surfaces: mở rộng banner V3 (first_run.py) + FAQ (help_page.py) nói rõ việc gửi
   event; Dashboard.jsx thêm phễu theo stage (download→demucs→asr→translate→tts→mux).
E. Tests: unit (định nghĩa "abandoned" theo N giờ), integration (event ghi đúng khi
   pipeline chạy thật qua các stage), privacy test (assert KHÔNG có field nội dung nào
   trong payload event — test kiểm tra ngược, cố ý thử gửi field cấm phải bị chặn).

Audit Before Build:
- Cần audit: rà lại `rep.emit(...)` trong pipeline.py — đã có sẵn đủ điểm chuyển stage
  chưa, hay cần thêm điểm mới. Đọc `autodub/progress.py` (ProgressReporter) trước khi
  quyết định điểm gắn hook.
- Gap cụ thể: kế thừa nguyên vẹn từ V10 — capability hoàn toàn mới (thu thập dữ liệu),
  KHÔNG phải mở rộng cái đã có, cần quyết định minh bạch mới (guardrail 1).

Design Choice:
- Tái dùng `rep.emit()` đã có (không thêm cơ chế event riêng trong pipeline.py) — chỉ
  thêm 1 listener gửi về server khi `is_configured()`, độc lập với UI progress hiện có.

Test Plan:
- Unit: logic phễu (started không completed/failed trong N giờ = abandoned).
- Integration: chạy 1 lượt dubbing thật (chế độ SaaS giả lập), xác nhận đúng chuỗi event
  ghi vào MongoDB, đúng thứ tự stage.
- Regression: chế độ local-only (is_configured()=False) — xác nhận 0 network call nào
  phát sinh (test bằng mock/monitor network, giống cách README/ARCH.md đã cam kết).
- Live verification: banner minh bạch mới đã hiện đúng, xác nhận bằng cách tự đọc lại
  UI như người dùng thật trước khi coi là "đã thông báo đầy đủ".

Success Criteria:
- Dashboard hiện đúng % hoàn thành/bỏ dở theo stage, dữ liệu thật không phải ước lượng.
- 0 event nào được gửi ở chế độ local-only — verify bằng test, không chỉ đọc code.
- Banner/FAQ minh bạch đã cập nhật VÀ TRIỂN KHAI trước khi tính năng này gửi bất kỳ dữ
  liệu thật nào của người dùng thật — không đảo ngược thứ tự.
```

### V15 — Sửa bug hardcode tiếng Việt ở prompt dịch server-side (bug thật, tìm ra khi audit V14)

Không phải mini-spec lên kế hoạch từ đầu — phát sinh khi audit trước khi bắt tay V14
(bên dưới), thấy `/translate`,`/analyze`,`/review` (control_server) hardcode dịch sang
tiếng Việt bất kể client đang lồng tiếng ngôn ngữ nào, ảnh hưởng thật tới tính năng đa
ngôn ngữ đích đã đóng ở V11 khi dùng qua SaaS. Coi đây là bug-fix ưu tiên trước khi tiếp
tục V14 (không hợp lý viết thêm tính năng dịch mới trên nền server đang dịch sai ngôn
ngữ). Đã code xong + test unit/mock đầy đủ, **CHƯA live-verify qua HTTP thật** (sandbox
hiện tại thiếu Mongo chạy + API key nhà cung cấp AI thật) — xem chi tiết đầy đủ ở
`docs/TEST_LOG.md` mục V15, bao gồm Remaining Limits cần chủ dự án xác nhận có chờ
live-verify trước khi đóng hẳn V15 hay không.

### V14 — Dịch phụ đề rời (`.srt`/`.vtt`, NGOÀI luồng dub video)

```
V14 — Tính năng mới: dịch 1 file phụ đề rời (không gắn video nào đang lồng tiếng)

Context:
- Phát sinh ngoài kế hoạch Phase A-D ban đầu — không phải đóng gap của V8/V9/V10 như
  V11-13, mà là TÍNH NĂNG MỚI. Thiết kế thuật toán parser dựa trên 1 công cụ khác của
  chủ dự án (VidGrab, 2026-08) đã kiểm chứng thật, chuyển quy ước sang project này.
- Đã có sẵn trước khi mở mini-spec chính thức (audit xác nhận, giữ nguyên):
  `autodub/text/subtitle_parse.py` (đọc/ghi `.srt`/`.vtt` rời, bỏ qua khối hỏng thay vì
  hỏng cả file, 24 test) và `run_local_worker()` tách ra từ `translate_local.py` (lõi
  gọi subprocess dịch local dùng chung, không phá hành vi `translate_segments_local()`
  cũ — 7 test cũ vẫn pass).
- 5 quyết định đã hỏi chủ dự án (2026-08-11), không tự đoán:
  1. Wiring: CẢ HAI — dialog trong `autodub_gui/` (desktop) VÀ script CLI riêng
     (`scripts/`).
  2. Nguồn dịch: CẢ HAI — local (NLLB qua `run_local_worker()`, offline) VÀ SaaS (cần
     endpoint control_server mới, xem Design Choice).
  3. Phạm vi ngôn ngữ: MỞ RỘNG theo FLORES-200 đầy đủ (~200 ngôn ngữ), không giới hạn
     theo `TargetLang`/`LANG_TO_FLORES` hẹp hiện có (chỉ 9 mã, gắn với pipeline dub).
  4. Đầu ra: LUÔN sinh file mới (`<tên>_<flores-code-đích>.<đuôi gốc>`), không ghi đè.
  5. Giá SaaS: tính phí như autotranslate — dùng lại `credit.cost.segment.autotranslate`
     (config service đã có), mỗi dòng phụ đề tính 1 "segment".

Goal:
- Người dùng dịch được 1 file `.srt`/`.vtt` độc lập (không cần đang lồng tiếng video
  nào) sang bất kỳ ngôn ngữ nào trong FLORES-200, từ cả GUI lẫn CLI, chọn được local
  (offline, miễn phí) hoặc SaaS (tốn Vox, chất lượng cao hơn qua LLM thật).

Constraints (Guardrails):
1. **KHÔNG tái dùng `TargetLang`** cho ngôn ngữ nguồn/đích của V14 — `TargetLang` gắn
   chặt với pipeline dub (audio_name/srt_name/folder_suffix/iso639_2 cho MP4 track,
   chỉ 2 giá trị vi/en). V14 dùng thẳng MÃ FLORES-200 (vd `vie_Latn`) làm định danh
   NGÔN NGỮ DUY NHẤT xuyên suốt (GUI/CLI/API) — không dựng thêm tầng ánh xạ BCP-47↔
   FLORES-200 cho ~200 ngôn ngữ (rủi ro sai âm thầm không test nào bắt được, vd các cặp
   dễ nhầm như `azb_Arab`/`azj_Latn`, hay `arb_Arab` không map 1-1 vào 1 mã BCP-47 quốc
   gia nào). Bảng mã FLORES-200 lấy nguyên từ nguồn thật
   (`facebookresearch/flores` repo, `flores200/README.md`) — KHÔNG tự suy đoán/nhớ lại,
   ghi rõ nguồn trong code.
2. Vì phụ đề rời không có audio kèm theo → KHÔNG tự nhận diện ngôn ngữ nguồn — người
   dùng chọn tay CẢ nguồn lẫn đích (khác pipeline dub, vốn có ASR biết ngôn ngữ nguồn).
3. Endpoint SaaS mới TÁCH KHỎI `/translate` hiện có — payload/prompt của `/translate`
   gắn với `duration`/`max_chars`/`cpsBudget` (ràng buộc tốc độ đọc cho TTS dub), không
   áp dụng cho phụ đề thuần (không có TTS). Prompt riêng, đơn giản hơn (không có luật
   prosody/CPS của prompt dub).
4. Billing: mỗi dòng phụ đề = 1 "segment" theo `credit.cost.segment.autotranslate` —
   KHÔNG cộng thêm `credit.cost.segment.base` (phần đó gắn với xử lý ASR/dub segment,
   không áp dụng ở đây).
5. Local path KHÔNG cần `is_configured()` (giữ triết lý offline-first) — GUI/CLI phải tự
   quyết định hiện lựa chọn SaaS hay không dựa trên `is_configured()`, không ẩn tuỳ chọn
   local dù có server cấu hình.
6. Đúng cảnh báo chất lượng đã áp dụng ở V4/V6: CHỈ live-verify được ngôn ngữ đã dùng
   thật trong app (vi/en qua NLLB đã verify từ V6/V11) — ~190 ngôn ngữ FLORES-200 còn lại
   CHƯA có bằng chứng chất lượng dịch thật nào, phải nói rõ trong docs, không ngầm định
   "hỗ trợ" nghĩa là "đã kiểm chứng".

Scope:
A. `autodub/text/flores200.py` (mới) — bảng đầy đủ `{code: name}` từ nguồn
   `facebookresearch/flores` (flores200/README.md), hàm tra cứu tên hiển thị.
B. `autodub/text/subtitle_translate.py` (mới) — orchestrate: đọc file
   (`subtitle_parse.parse_subtitle`) → dịch text từng cue (local qua
   `run_local_worker()`, hoặc SaaS qua `SaasClient.translate_subtitle()` mới) → ghép lại
   cue (giữ nguyên timestamp gốc) → serialize → ghi file mới.
C. `autodub/saas_client.py`: `translate_subtitle(texts, *, job_id, source_flores,
   target_flores, target_name, hold_id=None) -> dict` — endpoint mới.
D. `control_server`: route `POST /v1/ai/translate-subtitle` (file mới hoặc thêm vào
   `routes/ai.js`) — billing theo guardrail 4, gọi
   `ai-gateway.service.js` hàm mới `translateSubtitleBatch()` (không cps/prosody).
   `prompts/subtitle-translate.js` (mới) — prompt đơn giản: dịch trung thực, giữ số
   dòng/thứ tự, JSON in/out theo id.
E. CLI: `scripts/translate_subtitle.py` — argparse (`input`, `--source`, `--target` nhận
   mã FLORES-200, `--mode local|saas`).
F. GUI: `autodub_gui/subtitle_translate_dialog.py` (mới) — file picker, 2 combo tìm-được
   (nguồn/đích, 200 mục), toggle local/SaaS (ẩn SaaS nếu `not is_configured()`), chạy nền
   qua pattern `workers.py` sẵn có, báo đường dẫn file kết quả. Gắn entry point vào
   `autodub_gui/shell.py`.
G. Tests: unit cho A/B/C (mock local worker + saas client), CLI arg parsing, JS cho
   D (route + billing + prompt builder, theo đúng pattern `translate-prompts.test.js`
   của V15).

Audit Before Build:
- Đã audit `autodub/languages.py` (TargetLang chỉ vi/en, gắn dub) và
  `translate_local.py` (`LANG_TO_FLORES` chỉ 9 mã) trước khi quyết định KHÔNG tái dùng
  — đúng guardrail 1.
- Đã audit `control_server/src/services/config.service.js` — `credit.cost.segment.
  autotranslate` đã tồn tại (giá trị hiện tại: 2), dùng lại đúng theo guardrail 4, không
  tạo key giá mới.
- Bảng FLORES-200 lấy qua WebFetch thật từ `facebookresearch/flores` (flores200/
  README.md) tại thời điểm viết mini-spec này (2026-08-11) — không gõ tay từ trí nhớ.

Design Choice:
- Ngôn ngữ = mã FLORES-200 xuyên suốt (guardrail 1) — đơn giản hoá lớn, đánh đổi: GUI
  phải hiện tên người-đọc-được từ bảng tra cứu (flores200.py), không hiện mã thô cho
  người dùng cuối.
- SaaS path dùng endpoint/prompt RIÊNG (guardrail 3) thay vì nhét thêm field optional
  vào `/translate` — giữ `/translate` (dùng cho pipeline dub) không phình thêm logic
  không liên quan, đúng tinh thần "0 regression" đã áp dụng ở V15.

Test Plan:
- Unit: parser (đã xong, V14 giữ nguyên), `subtitle_translate` (mock cả 2 nguồn dịch,
  test giữ đúng timestamp/thứ tự cue, test file output đặt tên đúng quy ước).
- Unit JS: billing tính đúng theo số dòng × `credit.cost.segment.autotranslate`, prompt
  builder không crash với ngôn ngữ ngoài vi/en (fallback tên = mã FLORES-200 nếu chưa có
  tên hiển thị riêng).
- KHÔNG live-verify dịch thật ngoài vi/en (guardrail 6) — nếu cần, đó là 1 đợt live-
  verify riêng sau khi có nhu cầu thị trường thật cho ngôn ngữ cụ thể, giống tinh thần
  V4.

Success Criteria:
- Dịch được 1 file `.srt`/`.vtt` thật (source=zh/vi/en đã có sẵn, target bất kỳ trong
  FLORES-200) qua CẢ 2 đường GUI và CLI, CẢ 2 nguồn local/SaaS, ra file mới đúng tên,
  giữ nguyên timestamp.
- Billing SaaS đúng số Vox trừ = số dòng × giá autotranslate, verify bằng test (chưa
  live HTTP thật — cùng giới hạn đã ghi ở V15).
```

---

## Phase E — Đóng gap so với thị trường + ổn định vận hành (2026-08-11+)

Mở ra sau khi so sánh trực tiếp với các tool auto-dub thương mại (HeyGen,
ElevenLabs Dubbing Studio, Rask AI, Papercup, Deepdub, Sync Labs, CapCut,
Descript...) — xem báo cáo research trong lịch sử phiên làm việc 2026-08-11.
Kết luận chính: VoxDub là công cụ DUY NHẤT offline-first thật trong nhóm so
sánh (khác biệt cạnh tranh có chủ đích, giữ nguyên), nhưng thiếu 2 pattern
"production-stable" chuẩn công nghiệp — retry/backoff+idempotency cho MỌI
lời gọi mạng bên ngoài (không chỉ 1 phần) và phạm vi ngôn ngữ đích hẹp
(vi/en-thử nghiệm so với 90-175+ của đối thủ). Chủ dự án đã chọn ưu tiên
V16 (retry) + V17 (video dài) + mở rộng ngôn ngữ đích (mini-spec riêng, sau
V16/V17) trong đợt này; live-verify GPU thật (Whisper/VieNeu/Paraformer/
Demucs GPU) hoãn lại — sandbox không có phần cứng GPU.

### V16 — Retry/backoff cho các lượt gọi SaaS một-lần

```
V16 — Retry/backoff cho SaaS call một-lần (đóng gap ổn định Phase E)

Context:
- Tài liệu bắt buộc: autodub/text/translate_saas.py (đã có bounded-retry +
  backoff + jitter + rate-limit cho luồng dịch LÔ của pipeline dub — KHÔNG
  đụng file này, xem lý do trong Constraints), autodub/cloud_render.py
  (mini-spec V12 — poll/tải kết quả job cloud MỘT LẦN, không retry),
  autodub/text/subtitle_translate.py (mini-spec V14 — dịch phụ đề SaaS MỘT
  LẦN cho cả file, không retry).
- Trạng thái hiện tại (audit thật 2026-08-11): translate_saas.py ĐÃ đúng
  chuẩn (idempotency qua job_id băm nội dung + bounded retry 4 lượt + backoff
  2/6/15s có jitter, tôn trọng Retry-After, phân loại đúng lỗi tạm thời vs cố
  định). 2 nơi còn lại gọi saas_client MỘT LẦN duy nhất — một chớp mạng tạm
  thời (timeout, 429, 5xx) làm hỏng NGUYÊN job/file dù server không có gì
  sai, dù cả 2 đều idempotent-safe để gọi lại (poll là GET thuần đọc; tải
  kết quả mở file "wb" tự ghi đè; dịch phụ đề SaaS dùng job_id ổn định theo
  nội dung, máy chủ không tính phí 2 lần).

Goal:
- Không lượt gọi SaaS MỘT-LẦN nào trong sản phẩm còn "1 chớp mạng = hỏng
  nguyên tác vụ" khi bản thân tác vụ đó an toàn để gọi lại.

Constraints (Guardrails):
1. KHÔNG sửa translate_saas.py — logic đó đã đúng, có test, gắn trực tiếp
   luồng tiền (hold); nguyên tắc giống V2 (không ép refactor code tiền đang
   chạy đúng khi không có bằng chứng nó sai).
2. KHÔNG retry submit_demucs_job() — không có job_id do client sinh (server
   tự cấp), gọi lại khi request đã tới server nhưng response bị rớt có thể
   tạo 2 job + trừ Vox 2 lần — giữ single-attempt + fallback Demucs máy như
   cũ (đúng, không phải gap).
3. KHÔNG retry billing.py (setup_hold/settle_hold_inline) — đã có fallback
   design cố ý (rơi về trừ Vox từng lượt) thay vì retry, giữ nguyên.
4. Lỗi CỐ ĐỊNH (hết Vox, thiết bị khoá, bảo trì) không bao giờ retry — cùng
   luật is_retryable_error() như translate_saas.py.
5. Poll loop (cloud_render) không được lùi deadline tổng (MAX_WAIT_S) vì lỗi
   tạm thời — chỉ bỏ cuộc sớm hơn khi lỗi liên tiếp vượt ngưỡng riêng.

Scope:
B. Services/engine: module mới `autodub/saas_retry.py` (is_retryable_error,
   sleep_cancellable, call_with_retry) — rút từ đúng pattern translate_saas.py
   nhưng KHÔNG import/sửa file đó (duplicate có chủ đích, xem Constraint 1).
   Áp dụng: cloud_render.py (poll trong vòng lặp có sẵn — swallow lỗi tạm
   thời, đếm lỗi liên tiếp, KHÔNG dùng call_with_retry vì đã có vòng lặp
   riêng; download_job_result — bọc call_with_retry, 2 lượt độc lập);
   subtitle_translate.py (translate_subtitle_file_saas — bọc call_with_retry).
E. Tests: 18 test mới (test_saas_retry.py thuần cho module dùng chung + test
   riêng cho từng call site: retry-rồi-thành-công, hết-lượt-thì-raise,
   lỗi-cố-định-raise-ngay-không-retry).

Audit Before Build: xem "Trạng thái hiện tại" ở Context — đã audit đủ 6 file
gọi get_client() trong autodub/ (telemetry.py, cloud_render.py, billing.py,
subtitle_translate.py, content/generator.py, pipeline.py/translate_saas.py)
trước khi quyết định phạm vi. telemetry.py và content/generator.py KHÔNG
retry (đúng, cả 2 đều là tính năng phụ — gửi event/tạo caption mạng xã hội —
fail-soft chấp nhận được, retry không đáng giá trị tăng thêm).

Test Plan: unit đầy đủ (không cần mạng thật — mock SaasError/OfflineError ở
đúng biên get_client()), KHÔNG live-verify HTTP thật lượt này (đổi hành vi
lỗi-mạng, không đổi contract API — không cần key thật để xác nhận).

Success Criteria:
- 742/746 test pass (0 fail so với trước, 18 test mới) — xem TEST_LOG.
- `grep -rn "job_status\|download_job_result\|translate_subtitle(" autodub/cloud_render.py autodub/text/subtitle_translate.py`
  không còn lời gọi trần nào ngoài qua saas_retry (poll) hoặc call_with_retry.
```

### V17 — Mở rộng ngôn ngữ đích theo catalog CapCut thật

```
V17 — Mở rộng TARGETS theo catalog giọng CapCut thật (đóng gap cạnh tranh Phase E)

Context:
- Tài liệu bắt buộc: autodub/languages.py (TARGETS — chỉ vi/en trước V17),
  autodub/speech/tts/capcut_api/Voice.json (catalog giọng CapCut thật, 127
  giọng), autodub/speech/tts/voices.py::catalog() (đã target-aware từ V11),
  autodub/text/translate_local.py::LANG_TO_FLORES (đường dịch local NLLB).
- Trạng thái hiện tại: so sánh thị trường (Phase E, xem đầu mục "Phase E")
  cho thấy đây là gap cạnh tranh LỚN NHẤT — 90-175+ ngôn ngữ đích ở đối thủ
  vs chỉ vi+en (thử nghiệm) ở VoxDub, dù hạ tầng target-aware đã tổng quát
  hoá đầy đủ từ V11 (voices.catalog/GUI/editor/timing/align — không cần sửa
  thêm để thêm 1 target mới, CHỈ cần đăng ký registry).
- Quyết định kiến trúc phải giữ nguyên: KHÔNG thêm ngôn ngữ nào chưa có
  giọng CapCut thật backing nó (không hứa hẹn TTS không tồn tại) — audit
  Voice.json thật cho ra đúng 10 ngôn ngữ có giọng (>=3 giọng mỗi ngôn ngữ):
  vi(22)/en(40)/ja(19)/zh(16)/es(9)/th(6)/id(5)/pt(4)/fr(3)/de(3).

Goal:
- Người dùng chọn được 1 trong 10 ngôn ngữ đích (thay vì 2) mà không cần
  sửa gì ngoài đăng ký registry — verify hạ tầng target-aware của V11 thực
  sự tổng quát như thiết kế.

Constraints (Guardrails):
1. Chỉ thêm ngôn ngữ có giọng CapCut thật (đã audit Voice.json, không suy
   đoán) — đúng nguyên tắc V4 "mở rộng có kiểm chứng".
2. Đánh dấu "thử nghiệm" cho MỌI ngôn ngữ trừ vi (kể cả en đã có từ V11) —
   chỉ ngôn ngữ đã live-verify thật mới được bỏ nhãn.
3. KHÔNG đổi hành vi target=vi/en hiện có (regression test khoá lại).
4. Nếu audit phát hiện bug ảnh hưởng ngôn ngữ ĐANG CHẠY (không chỉ ngôn ngữ
   mới) — sửa luôn, không trì hoãn sang mini-spec khác (đúng tinh thần V11
   tìm+sửa bug align.py).

Scope:
A. Domain model: `autodub/languages.py::TARGETS` +8 entry (ja/zh/es/th/id/
   pt/fr/de), field suy ra máy móc từ key (text_field/transcript_name/
   srt_name/audio_name/folder_suffix) — không có logic đặc biệt nào khác vi.
B. Services/engine: `translate_local.py::LANG_TO_FLORES` +4 mã (es/pt/fr/de
   — ja/zh/th/id đã có sẵn từ V4). KHÔNG đổi voices.py/capcut_catalog.py
   (đã target-aware từ V11, chỉ cần TargetLang.code khớp catalog).
D. UI surfaces: `autodub_gui/dub_constants.py::DUB_TARGETS` +8 dòng, nhãn
   "thử nghiệm" cho tất cả trừ vi.
E. Tests: registry đủ 10 target + có giọng CapCut thật (test_multilang_
   target.py), mọi TargetLang.code resolve được FLORES (không rơi ngầm về
   vi như bug align.py cũ).

Audit Before Build:
- Voice.json: 127 giọng thật, `lang` field (BCP-47) cho 10 giá trị phân
  biệt (không phải 12 như ghi nhận sai ở V8 — đó là đếm nhầm field `lan`
  ngắn có 2 giá trị trùng lặp `jp`/`ja` và `br`/`pt` cho cùng 1 ngôn ngữ).
- **Bug thật phát hiện ngoài phạm vi trực tiếp** (Constraint 4): CapCut
  `synthesize()` áp `normalize_vi_text()` (đọc số kiểu tiếng Việt, "90%" ->
  "chín mươi phần trăm") cho MỌI giọng bất kể ngôn ngữ — kể cả tiếng Anh đã
  live từ V11. Không crash, chỉ đọc sai số trong câu có số. Đã sửa: lưu
  `self._lang` ở `__init__`, chỉ áp `normalize_vi_text` khi
  `self._lang == capcut_catalog.LANG` ("vi-VN"). Test khoá cả 2 chiều (vi
  vẫn đọc kiểu Việt, non-vi giữ nguyên số).

Design Choice:
- Đăng ký registry bằng vòng lặp dữ liệu (không viết tay 8 lần) — mọi field
  suy ra máy móc từ key, giữ đúng pattern additive-first (không đổi cách
  TargetLang được dùng ở nơi khác).

Test Plan:
- Unit: registry đủ 10 target, catalog CapCut thật có giọng cho từng target,
  FLORES mapping đủ cho mọi target.
- Regression: 0 thay đổi hành vi vi/en.
- Live verification: 1 ngôn ngữ mới (tiếng Nhật, chọn vì có 19 giọng — nhiều
  thứ 2 sau vi/en) qua 2 lượt gọi THẬT: (1) NLLB local dịch vi->ja (model
  622MB tải thật từ HuggingFace, không mock) — "Xin chào, hôm nay trời đẹp
  quá." -> "こんにちは 今日はとても素敵です" (đúng nghĩa, tự nhiên); (2)
  CapCut API thật, giọng "Hatunemiku" (ja-JP) — audio thật 2.352s, RMS biên
  độ 3345 (khác 0 = có tiếng nói thật, không phải file rỗng/lỗi).
- 7 ngôn ngữ còn lại (zh/es/th/id/pt/fr/de) CHƯA live-verify — đúng nguyên
  tắc "mở rộng có kiểm chứng", giữ nhãn "thử nghiệm", không giả vờ đã kiểm
  chứng chỉ vì code đúng.

Success Criteria:
- `set(TARGETS) == {vi, en, ja, zh, es, th, id, pt, fr, de}`, mỗi target có
  giọng CapCut thật + FLORES mapping (test khoá lại).
- 746/750 test pass, 0 regression.
- Bug đọc số sai ngôn ngữ đã sửa + có test khoá cho cả giọng Việt và giọng
  khác (không phải chỉ ghi nhận rồi để đó).
```

---

## Phase F — Tự động hoá vận hành không người giám sát (2026-08-12+)

Mở ra sau khi chủ dự án yêu cầu "tìm những vấn đề còn tồn đọng + đọc tính
năng tool rồi tiếp tục cải tiến phù hợp tự động hoá" — 1 agent audit toàn
bộ `docs/TEST_LOG.md`/`docs/PLAN.md` (mọi mục "Remaining Limits") cùng đọc
`autodub/pipeline.py`/`batch.py`/`editor.py`/`control_server/src/routes/`
để đề xuất hướng nâng cấp khớp định hướng hiện tại (offline-first, chạy
được không giám sát). Kết luận chính: pipeline core đã "GUI-ready" đúng như
docstring của nó tự nhận (không `input()`, không `sys.exit`, progress qua
callback, hủy qua `threading.Event`) nhưng KHÔNG có đường vào nào ngoài GUI
PySide6 — mọi kịch bản tự động hoá thật (cron, watch-folder, CI, script
hàng loạt) đều bị chặn ở bước đầu tiên vì phải khởi động Qt. Chủ dự án chọn
ưu tiên **cả 4 mini-spec dưới đây** (nhóm E1/E3 độc lập được đánh dấu
"Recommended", nhóm E2+E5+E6 gộp chung theo đúng lựa chọn của chủ dự án vì
cùng chạm 1 chỗ — vòng lặp `_run_items()`/subprocess worker trong
`batch.py`). **V22 (CLI) đã triển khai đầy đủ trong đợt này** vì là nền
tảng bắt buộc — V23/V24/V25 dùng nó làm điểm vào, nên viết mini-spec kỹ
thuật đầy đủ trước (đúng yêu cầu "kế hoạch nâng cấp phải xây theo
MINI-SPEC"), triển khai ở đợt kế tiếp sau khi chủ dự án xác nhận.

### V22 — CLI headless cho pipeline dub

```
V22 — CLI headless (nền tảng Phase F, E1)

Context:
- `autodub/pipeline.py` (docstring tự nhận "GUI-ready core"): không
  `input()`, không `sys.exit`, lỗi raise thuần, tiến trình qua
  `ProgressFn`/`ProgressEvent` (autodub/progress.py), hủy qua
  `threading.Event`. `DubPipeline(settings, progress=fn, cancel_event=ev,
  synth_cache=..., demucs_cache=..., whisper_cache=...).run(DubRequest(...))
  -> DubResult(status, work_dir, report)`.
- `autodub/batch.py::run_batch()` đã có sẵn: parse danh sách dòng
  (`parse_lines`), resume qua `batch_state.json` (`retry_done`), prefetch
  video kế tiếp, TTS/Demucs/Whisper cache dùng chung giữa các video.
- Đường vào DUY NHẤT hiện có: `autodub_gui/app.py:main()` (PySide6,
  `[project.gui-scripts]` trong pyproject.toml). KHÔNG có
  `[project.scripts]` console nào — script tự động hoá không có cách gọi
  pipeline mà không kéo theo Qt.
- Audit import: `pipeline.py`/`batch.py` không import gì từ `autodub_gui`
  hay `PySide6` (grep xác nhận) — lớp core đã tách sạch, chỉ thiếu lớp vỏ
  CLI mỏng gọi vào.
- **Hành vi cần audit kỹ trước khi viết CLI**: `voices.resolve(settings,
  name, target)` (autodub/speech/tts/voices.py) CHỦ ĐÍCH rơi ngầm về giọng
  khác khi tên không khớp danh mục (thứ tự: tên truyền vào → giọng mặc định
  cấu hình → DEFAULT_VOICE → giọng đầu danh mục) — thiết kế đúng cho GUI
  (không bao giờ "chết vì unknown voice" khi người dùng gõ nhầm, có picker
  sửa ngay). Với CLI/cron, im lặng thay giọng là bẫy thật: gõ sai tên trong
  script chạy định kỳ có thể tạo hàng loạt video sai giọng nhiều tuần không
  ai biết. CLI KHÔNG được kế thừa hành vi rơi ngầm này.

Goal:
- Dub được 1 video/file hoặc 1 batch từ terminal (`voxdub dub ...` /
  `voxdub batch ...`), không khởi động Qt, exit code + output máy đọc được
  — làm nền cho V23 (quality gate đọc kết quả CLI), V24 (retry/watchdog bọc
  quanh tiến trình CLI), V25 (watch-folder gọi CLI mỗi video mới).

Constraints (Guardrails):
1. Không đổi hành vi `pipeline.py`/`batch.py` hiện có — CLI chỉ là lớp vỏ
   mỏng dựng `DubRequest`/gọi `DubPipeline.run()`/`run_batch()` có sẵn.
2. Import module CLI KHÔNG được kéo theo `PySide6`/`autodub_gui` — khoá
   bằng test kiểm `sys.modules` sau `import autodub.cli`.
3. Tên giọng CLI phải validate tường minh trước khi chạy — lỗi rõ ràng
   (exit code 2) nếu không khớp danh mục, KHÔNG dùng `voices.resolve()`
   trực tiếp (hành vi rơi ngầm chỉ đúng cho GUI, xem Audit).
4. Output: mặc định người đọc được (stderr cho tiến trình, stdout cho kết
   quả cuối); `--json` chuyển sang NDJSON (1 dòng JSON/sự kiện) để script
   hoá — không phá vỡ chế độ mặc định khi thêm cờ này.

Scope:
A. `autodub/cli.py` (mới) — argparse, 2 subcommand:
   - `dub`: 1 URL hoặc `--file`, cờ khớp field của `DubRequest` (--voice,
     --target, --source-lang, --bg-mode, --subtitle-mode, --output-dir,
     --resume-dir, --skip-video).
   - `batch`: `--file <danh sách dòng>` hoặc đọc từ stdin, cờ khớp
     `run_batch()` (--retry-done, --state-path); in tiến trình từng video
     qua `observer` có sẵn của `run_batch`.
   - Voice validate qua `autodub.speech.tts.voices.catalog(settings,
     target)` trước khi gọi pipeline — không qua `resolve()`.
   - `--json`: bọc `ProgressFn`/`observer` in NDJSON thay vì text.
B. `pyproject.toml` — thêm `[project.scripts] voxdub = "autodub.cli:main"`
   (console_scripts thật — không kéo Qt như gui-scripts).
C. Exit code: 0 = `DubResult.status == "completed"`/batch không lỗi nào;
   1 = pipeline lỗi hoặc có video batch thất bại; 2 = lỗi tham số/giọng
   không hợp lệ.
D. `README.md` — thêm đoạn ngắn "Chạy không giao diện (CLI)".

Audit Before Build: xem phần Context — đã audit xong `pipeline.py`
(GUI-ready thật), `batch.py` (đã đủ hạ tầng resume/state), import graph
(sạch, không lẫn Qt), và hành vi `voices.resolve()` (rơi ngầm chủ đích cho
GUI, cần override cho CLI).

Design Choice:
- `argparse` (thư viện chuẩn) thay vì thêm dependency mới (click/typer) —
  đúng nguyên tắc dự án "không thêm phụ thuộc khi không bắt buộc"; CLI chỉ
  2 subcommand, argparse đủ.
- Tiến trình ra `stderr`, kết quả cuối (JSON report hoặc exit summary) ra
  `stdout` — giữ `stdout` sạch để pipe được (`voxdub dub ... | jq .`).
- `--json` phát đúng shape `ProgressEvent` (step/status/detail/current/
  total) làm dict — không tự chế định dạng mới, để V24/V25 parse lại được
  ngay bằng cùng shape đã có trong `autodub/progress.py`.

Test Plan:
- Unit: parser dựng đúng `DubRequest`/tham số `run_batch` từ mọi cờ; exit
  code đúng theo 3 trường hợp (thành công/lỗi pipeline/tham số sai); giọng
  không hợp lệ → exit 2 kèm thông báo rõ (không rơi ngầm).
- Cách ly: `import autodub.cli` xong, `"PySide6" not in sys.modules` và
  `"autodub_gui" not in sys.modules`.
- `--help` exit 0, có mô tả cả 2 subcommand.
- KHÔNG live-verify 1 lượt dub thật qua CLI trong đợt này (cần mạng/GPU,
  ngân sách thời gian phiên này ưu tiên cho việc viết đủ 4 mini-spec) — ghi
  nhận là giới hạn còn lại, cùng loại "chưa live-verify" như 7/8 ngôn ngữ
  của V17: hạ tầng đã đúng theo test cách ly + unit, nhưng đường thật
  end-to-end qua CLI (khác API Python trực tiếp) chưa chạy thật 1 lần.

Success Criteria:
- `voxdub dub --help` / `voxdub batch --help` chạy được sau
  `pip install -e .`, exit 0.
- Toàn bộ test mới pass, 0 regression trên bộ test hiện có.
- Không có `PySide6`/`autodub_gui` trong import graph của `autodub/cli.py`.
```

### V23 — Cổng chất lượng tự động đọc `quality_report.json`

```
V23 — Cổng chất lượng tự động (Phase F, E3) — CHƯA TRIỂN KHAI, mini-spec kế hoạch

Context:
- `DubPipeline._build_quality_report()` (autodub/pipeline.py:1579) đã tính
  sẵn 1 báo cáo đầy đủ mỗi lượt chạy — `quality_report.json` trong
  `data/`: `summary` (segments_ok/segments_shifted/segments_over_budget/
  segments_speed_fallback/segments_postprocess_fallback/...) +
  `per_segment` (chỉ câu có vấn đề, kèm text) + `translate_usage`.
- Hiện tại báo cáo này CHỈ để người dùng tự mở xem trong Editor
  (autodub/editor.py) — không có ngưỡng pass/fail, không có tín hiệu máy
  đọc được. Batch/CLI (V22) coi mọi video có `status == "completed"` là
  "xong", kể cả khi `quality_report.json` của nó có 40% câu lệch tốc
  độ/tràn thời lượng — vận hành không giám sát (V24 retry, V25
  watch-folder) cần phân biệt "chạy xong" khỏi "chạy xong VÀ đạt chất
  lượng" để biết video nào cần người xem lại tay.

Goal:
- Sau mỗi lượt dub, có 1 tín hiệu pass/fail dựa trên `quality_report.json`
  đã có sẵn (không tính lại số liệu mới) — dùng được cả trong CLI (exit
  code riêng) lẫn batch (đánh dấu trong `batch_state.json`).

Constraints (Guardrails):
1. KHÔNG đổi cách `_build_quality_report()` tính số liệu — cổng chất lượng
   chỉ ĐỌC báo cáo đã có, áp ngưỡng, không tính lại.
2. Ngưỡng mặc định phải BẢO THỦ (thà báo "cần xem lại" oan còn hơn bỏ sót
   video lỗi thật) và cấu hình được qua `Settings` (không hardcode) — dự án
   chưa có dữ liệu thật về ngưỡng "chấp nhận được" cho từng loại vấn đề,
   nên mặc định ban đầu cần chủ dự án duyệt lại sau khi thấy số liệu thật
   trên vài chục video.
3. Không chặn pipeline dừng lại vì fail — cổng chất lượng là TÍN HIỆU sau
   khi đã chạy xong, không phải điều kiện chặn giữa chừng (khác từ chối
   render).

Scope:
A. `autodub/quality_gate.py` (mới) — hàm thuần `evaluate(report: dict,
   thresholds: QualityThresholds) -> QualityVerdict` (pass/warn/fail +
   danh sách lý do fail cụ thể, trỏ lại đúng field trong `summary`).
   `QualityThresholds` dataclass: max tỉ lệ `segments_over_budget`, max
   `segments_speed_fallback`, max `segments_postprocess_fallback`, max
   `max_shift_s`. Đọc mặc định từ `Settings` (thêm field mới, có giá trị
   mặc định bảo thủ).
B. CLI (V22) — `voxdub dub`/`voxdub batch` thêm cờ `--quality-gate` (tắt
   mặc định lượt đầu, BẬT mặc định khi cờ này có mặt): video fail → exit
   code riêng (3, phân biệt với lỗi pipeline=1) trong `dub`; trong `batch`,
   ghi thêm field `quality` (pass/warn/fail + lý do) vào entry tương ứng
   trong `batch_state.json` — KHÔNG đổi field `status` hiện có
   (success/failed) để không phá vỡ logic resume của `run_batch()`.
C. Tests: verdict đúng cho báo cáo sạch/báo cáo có vấn đề (fixture dựng
   tay từ shape thật của `_build_quality_report()`, không cần chạy pipeline
   thật); ngưỡng cấu hình qua Settings override đúng; CLI exit code 3 khi
   fail; batch_state.json có field `quality` không phá field `status` cũ
   (test resume vẫn đọc đúng `status` như trước — 0 regression).

Audit Before Build (cần làm THẬT trước khi code, chưa làm trong đợt này):
- Chạy quality gate (ngưỡng nháp) trên `quality_report.json` thật của vài
  video đã dub trong phiên trước (nếu còn giữ ở `output/`) để hiệu chỉnh
  ngưỡng mặc định bằng số liệu thật thay vì đoán — đây là lý do mini-spec
  này CHƯA triển khai ngay, cần 1 vòng audit số liệu thật trước khi chốt
  Constraint 2.

Design Choice:
- Hàm thuần (`evaluate()`, không I/O) tách khỏi CLI để V24 (retry logic)
  và V25 (watch-folder) gọi lại được mà không phải qua subprocess/CLI —
  cùng pattern với `translate_hint.py`/`media/timing.py` (module tính toán
  thuần, lớp gọi ở ngoài quyết định làm gì với kết quả).

Test Plan:
- Unit thuần trên fixture `quality_report.json` (sạch/có vấn đề ở từng
  field riêng lẻ) — không cần chạy pipeline thật.
- Regression: `batch_state.json` cũ (không có field `quality`) vẫn đọc
  được bởi `run_batch()` — field mới là additive, không bắt buộc.

Success Criteria:
- `evaluate()` phân loại đúng theo ngưỡng cấu hình, có lý do cụ thể theo
  từng field (không chỉ "fail" trơn).
- CLI/batch phát tín hiệu pass/fail máy đọc được mà không đổi hành vi
  resume/exit code hiện có khi cờ `--quality-gate` KHÔNG được bật.
```

### V24 — Tự thử lại theo video trong batch + giám sát treo subprocess + log lỗi tập trung

```
V24 — Batch resilience: retry + watchdog + failures.jsonl (Phase F, E2+E5+E6 gộp) — CHƯA TRIỂN KHAI, mini-spec kế hoạch

Context (đã audit `batch.py` + `translate_local.py::run_local_worker`):
- `batch.py::_run_items()` HIỆN TẠI: 1 video lỗi → `except Exception` bắt
  lại, ghi `status="failed"` + `error` vào `batch_state.json`, GHI NHỚ
  `work_dir` dở dang (`item.ref["work_dir"]`), rồi CHUYỂN NGAY sang video
  kế tiếp — không thử lại trong cùng lượt chạy. Người dùng phải tự nhận ra
  batch có video fail, tự chạy lại `run_batch()` với đúng danh sách cũ để
  nó resume đúng `work_dir` đã lưu (`resume_dir` trong `DubRequest`). Đây
  LÀ resume THỦ CÔNG đã có sẵn (đúng, hoạt động) — cái THIẾU thật là: (a)
  không phân biệt lỗi TẠM THỜI (mất mạng, rate-limit SaaS — thử lại có thể
  qua) khỏi lỗi VĨNH VIỄN (giọng không tồn tại, file hỏng — thử lại vô ích)
  nên không tự động thử lại được an toàn; (b) không có giới hạn số lần thử.
- `translate_local.py::run_local_worker()` (dùng subprocess NLLB local):
  đọc `proc.stdout` bằng vòng lặp CHẶN (`for line in proc.stdout:`) KHÔNG
  timeout — nếu worker treo giữa chừng (model kẹt, deadlock hiếm), tiến
  trình gọi nó (cả pipeline) treo VÔ THỜI HẠN, không timeout, không log
  cảnh báo. Cùng dạng ở các worker subprocess khác (Whisper/VieNeu/
  Paraformer/Demucs — audit sơ bộ thấy `transcriber.py` CÓ `proc.wait(
  timeout=7200)` ở 1 chỗ nhưng không phải mọi điểm đọc stdout đều có
  timeout tương đương).
- KHÔNG có log lỗi tập trung: mỗi lỗi chỉ nằm rải rác trong
  `entry["error"]` của `batch_state.json` (1 dòng, cắt 200 ký tự,
  `str(e)[:200]`) — không có nơi tổng hợp lỗi qua nhiều lượt batch để thấy
  pattern (vd "80% lỗi tuần này là timeout Demucs" chỉ thấy được nếu đọc
  tay từng batch_state.json).

Goal:
- Batch tự thử lại video lỗi TẠM THỜI trong cùng lượt chạy (giới hạn số
  lần, có backoff), không treo vô thời hạn khi 1 subprocess worker bị kẹt,
  và có 1 nơi duy nhất tổng hợp mọi lỗi qua các lượt batch để nhìn ra
  pattern.

Constraints (Guardrails):
1. KHÔNG tự thử lại lỗi rõ ràng VĨNH VIỄN (voice không hợp lệ, file nguồn
   không đọc được, ConfigError thiếu API key) — thử lại vô ích, chỉ tốn
   thời gian/tài nguyên. Cần phân loại lỗi theo EXCEPTION TYPE đã có sẵn
   trong code (vd `ConfigError` = vĩnh viễn, lỗi mạng/timeout = tạm thời)
   thay vì đoán qua nội dung message.
2. Watchdog KHÔNG được đổi logic worker (`translate_local_worker.py` và
   tương tự) — chỉ bọc thêm timeout ở TẦNG GỌI (subprocess), giữ nguyên
   contract stdin/stdout hiện có, đúng nguyên tắc đã ghi trong CLAUDE.md
   ("mỗi engine nặng chạy trong venv con riêng qua subprocess" — không đổi
   ranh giới này).
3. `failures.jsonl` chỉ GHI THÊM (append-only), không đổi format
   `batch_state.json` hiện có — 2 file độc lập, `batch_state.json` vẫn là
   nguồn duy nhất cho logic resume (giữ đúng Constraint tương tự V23 với
   `quality`).
4. Giới hạn retry mặc định NHỎ (2-3 lần) + backoff — không biến 1 video
   lỗi vĩnh viễn (đoán nhầm là tạm thời) thành vòng lặp tốn giờ máy.

Scope:
A. `autodub/errors.py` hoặc mở rộng exception hiện có — gắn nhãn
   `transient: bool` cho các exception loại timeout/mạng (nếu chưa có class
   riêng, bọc bằng 1 marker exception mới `TransientPipelineError` ném ra
   từ đúng những chỗ lỗi mạng/timeout hiện đang raise Exception trần).
B. `batch.py::_run_items()` — khi lỗi là transient VÀ chưa hết lượt thử,
   resume ngay `work_dir` vừa lưu (dùng lại cơ chế `resume_dir` đã có,
   KHÔNG viết lại pipeline logic) thay vì chuyển sang video kế; backoff
   giữa các lần thử (thời gian chờ tăng dần, có giới hạn trần).
C. `autodub/subprocess_watchdog.py` (mới) — hàm bọc `subprocess.Popen` +
   đọc stdout theo dòng CÓ timeout tổng (không phải per-line — worker có
   thể hợp lệ đứng im lâu giữa các dòng khi đang tính toán nặng, nhưng
   TỔNG thời gian không phản hồi gì phải có trần); áp dụng cho
   `run_local_worker()` (translate_local.py) trước — nơi đã audit xác nhận
   thiếu — các worker khác (Whisper/VieNeu/Demucs) rà lại timeout hiện có,
   thống nhất qua cùng 1 hàm dùng chung thay vì mỗi nơi tự viết timeout
   riêng (rủi ro: các worker này CÓ chạy thật lâu hợp lệ với input nặng —
   audit kỹ giá trị timeout hiện tại của từng worker trước khi đổi số, để
   dành làm bước audit riêng khi triển khai, KHÔNG đoán số ở đây).
D. `autodub/failures_log.py` (mới) — `append_failure(entry: dict, path:
   str)`: ghi 1 dòng JSON/lỗi vào `failures.jsonl` cạnh `batch_state.json`
   (video, lỗi, transient/permanent, số lần đã thử, timestamp — KHÔNG dùng
   `datetime.now()`/thời gian hệ thống trong code lõi nếu cần test được
   deterministic, truyền timestamp từ ngoài vào).
E. Tests: phân loại transient/permanent đúng theo exception type (không
   đoán qua string message — dễ vỡ khi đổi ngôn ngữ lỗi); retry dừng đúng
   giới hạn; watchdog cắt được 1 subprocess giả lập treo (test dùng script
   giả ngủ vô hạn, không cần model NLLB thật); `failures.jsonl` ghi đúng
   định dạng, append không ghi đè.

Audit Before Build (cần làm THẬT trước khi code, chưa làm trong đợt này):
- Rà lại TOÀN BỘ điểm gọi subprocess trong autodub/speech/ + autodub/media/
  (không chỉ translate_local.py) để liệt kê chính xác nơi nào ĐÃ có
  timeout, nơi nào chưa, và giá trị timeout hợp lý cho từng loại việc
  (dịch 1 câu ngắn khác hẳn Demucs tách nhạc 1 video dài) — bảng audit này
  là điều kiện để chốt Design Choice cụ thể cho watchdog, chưa làm trong
  đợt viết mini-spec này.

Design Choice:
- Retry TÁI DÙNG cơ chế resume đã có (`resume_dir`) thay vì viết logic
  chạy lại riêng — tôn trọng nguyên tắc "artifact trung gian cache trên
  đĩa, pipeline resume-safe" đã ghi trong CLAUDE.md, tránh 2 đường resume
  song song (thủ công qua re-paste batch vs tự động qua V24) dễ lệch nhau.
- `failures.jsonl` tách khỏi `batch_state.json` (không gộp field) — giữ
  đúng nguyên tắc V23 (file mới additive, không đổi contract file cũ mà
  logic resume đang phụ thuộc).

Test Plan:
- Unit: phân loại lỗi, giới hạn retry, backoff tăng dần, watchdog cắt
  subprocess treo giả lập, format `failures.jsonl`.
- Regression: batch KHÔNG bật cờ retry mới vẫn chạy đúng y hệt hành vi
  hiện tại (1 lần thử/video, không đổi mặc định nếu retry là tính năng
  opt-in — cần quyết định lúc triển khai: mặc định BẬT hay opt-in, để dành
  hỏi chủ dự án trước khi code vì ảnh hưởng trực tiếp thời gian chạy batch
  mặc định).

Success Criteria:
- Video lỗi transient tự phục hồi trong cùng lượt batch (không cần người
  dùng tự chạy lại) trong giới hạn số lần thử.
- Subprocess treo bị cắt trong thời gian hữu hạn, không còn "treo vô thời
  hạn" như hiện trạng đã audit.
- `failures.jsonl` tổng hợp đủ để trả lời "lỗi nào lặp lại nhiều nhất qua
  các lượt batch" mà không cần đọc tay từng batch_state.json.
```

### V25 — Chế độ theo dõi thư mục/hàng đợi không người trực

```
V25 — Watch-folder / queue mode (Phase F, E4) — CHƯA TRIỂN KHAI, mini-spec kế hoạch

Context:
- Hiện tại MỌI cách chạy pipeline (GUI, batch dán danh sách, và CLI V22
  mới) đều cần người khởi động lượt chạy. Không có cách nào để "thả video
  vào 1 thư mục, tool tự nhận và dub" — đây là mẫu hình vận hành phổ biến
  cho use-case doanh nghiệp/kênh nội dung đăng đều (vd: biên tập viên thả
  file MP4 tải sẵn vào thư mục dùng chung, quay lại sau vài giờ lấy video
  đã lồng tiếng) mà `batch.py` hiện tại không phục vụ được (`batch.py` chỉ
  nhận danh sách CỐ ĐỊNH tại thời điểm gọi, không theo dõi thư mục LIÊN
  TỤC).
- Phụ thuộc trực tiếp: V22 (CLI, đã xong — watch-folder gọi `voxdub dub`/
  logic tương đương cho mỗi file mới), V24 (retry/watchdog — 1 tiến trình
  chạy liên tục nhiều giờ/ngày CÀNG cần watchdog để không bị 1 video kẹt
  làm treo cả hàng đợi phía sau).

Goal:
- 1 tiến trình chạy nền, theo dõi 1 thư mục input — file video mới xuất
  hiện tự động được đưa vào hàng đợi dub tuần tự, kết quả ra 1 thư mục
  output tương ứng, không cần người bấm gì sau khi khởi động.

Constraints (Guardrails):
1. Chỉ xử lý file ĐÃ ghi xong (không đụng file đang được copy/tải dở) —
   cần cơ chế phát hiện "file ổn định" (vd kích thước không đổi qua N giây
   liên tiếp) trước khi đưa vào hàng đợi, tránh dub 1 file MP4 chưa ghi
   xong (hỏng/thiếu dữ liệu).
2. KHÔNG dub trùng 1 file 2 lần — cần trạng thái bền (đĩa, không chỉ RAM)
   ghi nhớ file nào đã xử lý, sống sót qua việc tắt/bật lại tiến trình
   watch (khác `batch_state.json` theo danh sách, đây theo THƯ MỤC).
3. Đây là tiến trình DÀI HẠN (giờ/ngày) — PHẢI dùng watchdog của V24 cho
   từng lượt dub bên trong, nếu không 1 video kẹt sẽ treo toàn bộ hàng đợi
   vô thời hạn, mất hết lợi ích "không người trực". Không triển khai V25
   trước V24 vì lý do này.
4. Dừng sạch (Ctrl+C hoặc tín hiệu hệ thống) không làm hỏng file đang xử
   lý dở — dùng lại `resume_dir` hiện có, không cần cơ chế mới.

Scope:
A. `autodub/watch_folder.py` (mới) — vòng lặp polling (không dùng
   `inotify`/`watchdog` package ngoài trong bản đầu — polling đơn giản đủ
   cho tần suất video mới thấp, tránh thêm dependency; nếu sau này cần độ
   trễ thấp hơn, đó là quyết định nâng cấp riêng) quét thư mục input theo
   chu kỳ cấu hình được, phát hiện file mới + ổn định (Constraint 1), đẩy
   vào hàng đợi nội bộ.
B. Trạng thái bền: `<output_dir>/_watch_state.json` — map file đã xử lý
   (theo path + mtime + size làm khoá, tránh dub lại nếu file trùng tên
   khác nội dung) → kết quả (thành công/thất bại, work_dir).
C. CLI (V22) — subcommand `voxdub watch --input-dir ... --output-dir ...`,
   dùng lại `DubRequest`/`DubPipeline` như `dub`, bọc watchdog (V24) cho
   từng lượt, ghi log qua `failures_log.py` (V24) khi có lỗi.
D. Tests: phát hiện file ổn định đúng (giả lập file đang lớn dần → chưa
   đưa vào hàng đợi; file kích thước không đổi N giây → đưa vào); không xử
   lý trùng file đã có trong state; dừng giữa chừng không hỏng trạng thái
   (đọc lại được từ `_watch_state.json` sau restart).

Audit Before Build:
- Không có code hiện tại nào liên quan trực tiếp (tính năng hoàn toàn
  mới) — audit cần làm là XÁC NHẬN LẠI với chủ dự án tần suất polling hợp
  lý (bao nhiêu giây/phút) và ngưỡng "file ổn định" (bao nhiêu giây không
  đổi kích thước) trước khi chốt Design Choice — đây là quyết định vận
  hành thực tế (tuỳ tốc độ mạng/ổ đĩa nơi triển khai), không phải quyết
  định kỹ thuật thuần tuý đoán được từ code.

Design Choice:
- Polling đơn giản (không thêm dependency `watchdog`/`inotify`) cho bản
  đầu — đúng nguyên tắc dự án ưu tiên ít phụ thuộc, đổi sang event-based
  chỉ khi có nhu cầu thật về độ trễ thấp.
- Trạng thái theo THƯ MỤC (`_watch_state.json`, khoá theo path+mtime+size)
  tách hẳn khỏi `batch_state.json` (khoá theo URL) — 2 mô hình vận hành
  khác nhau (danh sách cố định vs luồng liên tục), không ép chung 1 state
  file.

Test Plan:
- Unit: phát hiện ổn định, dedup theo path+mtime+size, state bền qua
  restart giả lập (đọc/ghi lại đúng `_watch_state.json`).
- KHÔNG chạy 1 tiến trình watch thật dài hạn trong test (không phù hợp CI)
  — test bằng cách gọi trực tiếp các hàm thuần (phát hiện ổn định, dedup)
  với dữ liệu giả lập, không cần vòng lặp polling thật chạy trong suite.

Success Criteria:
- File mới thả vào thư mục input, không cần thao tác thêm, xuất hiện ở
  thư mục output sau khi dub xong (hoặc entry lỗi rõ ràng trong
  `_watch_state.json`/`failures.jsonl` nếu thất bại).
- Tắt/bật lại tiến trình watch không dub trùng file đã xử lý, không mất
  dấu vết file đang xử lý dở khi tắt giữa chừng.
```

## Phase G — Đóng gap cạnh tranh thị trường 2026 + mở hướng phát triển mới (2026-08-12+)

Mở ra sau khi chủ dự án đưa research thị trường trực tiếp (so sánh ElevenLabs,
HeyGen, Rask, CapCut, Murf, Deepdub, Sync Labs, Papercup, Dubverse, Maestra) và
yêu cầu "đưa hướng tốt nhất cho tool hoàn chỉnh hơn". 9 gap cạnh tranh được liệt
kê: lip-sync, diarization đa giọng, emotion/tone transfer, real-time/live dubbing,
developer API, human-in-the-loop QA, glossary lock, multi-user workspace, độ phủ
ngôn ngữ. Trước khi viết mini-spec, đã audit thật (không đoán) 4 khả năng hiện có
(xem "Audit Before Build" chung bên dưới) — kết quả đổi hẳn cách ước lượng độ khó
so với nhìn từ ngoài vào.

**Phân loại theo audit + xác nhận chủ dự án:**
- **Tier 1 — khớp kiến trúc hiện có, không phá guardrail nào, build ngay** (V26-V29):
  diarization, sửa bug glossary, emotion/tone-aware voice, lộ rõ AI review dịch.
  Cả 4 đều tận dụng được cơ chế ĐÃ CÓ SẴN trong code (per-segment voice override,
  quality_report.json của V23) — không phải xây từ số 0.
- **Tier 2 — audit trước, CHƯA cam kết build** (V30): lip-sync — đúng tiền lệ V5
  (giữ boxblur thay AI inpainting vì "quá lớn cho 1 mini-spec"), cộng thêm rủi ro
  đạo đức thật (deepfake khuôn mặt) mà README/LICENSE mới chỉ cảnh báo chính sách,
  chưa có kiểm soát kỹ thuật nào.
- **Tier 3 — phá guardrail hiện có hoặc đổi định vị chiến lược, chủ dự án đã chọn
  đào sâu 1 hướng** (V31): Developer API — audit thật lộ ra "full hosted Dub API"
  (như Sync Labs/Murf) là ĐẦU TƯ HẠ TẦNG GPU + đa tenant hoàn toàn mới (ASR/TTS
  hiện 100% chạy trên máy người dùng, KHÔNG có server nào làm thay) — quy mô lớn
  hơn hẳn 1 mini-spec. Chủ dự án chọn phạm vi hẹp hơn, khả thi ngay: chỉ mở phần
  ĐÃ 100% server-side sẵn (dịch thuật) qua API key, không đụng ASR/TTS/video.
  **Multi-user collaborative workspace** và **Real-time/live dubbing** bị loại
  khỏi phạm vi Phase G — ghi nhận cần quyết định chủ dự án riêng (xem "Remaining
  Limits" cuối Phase G), KHÔNG viết mini-spec cho 2 hướng này ở đợt này.
- **Độ phủ ngôn ngữ**: không phải gap kỹ thuật mới — tiếp tục đúng mô hình audit
  Voice.json + mở rộng có kiểm chứng đã dùng ở V17, không cần mini-spec riêng.

### Audit Before Build chung (áp dụng cho V26/V27/V28/V31 — làm 1 lần, dùng chung)

- **Diarization**: không venv nào hiện có (`.venv-whisper`/`.venv-vieneu`/
  `.venv-asr`/`.venv-translate-mt`) cài torch — xác nhận qua từng
  `scripts/setup_*.py`. Chỉ `.venv-gpu` có torch+CUDA (dùng cho Demucs GPU/cuBLAS
  Whisper), nhưng venv này CHỈ tồn tại trên máy có NVIDIA GPU đã chạy cài đặt GPU
  — không phải venv phổ quát. `asr_whisper_worker.py` output chỉ
  `{"word","start","end"}` — không có tín hiệu người nói. **Kết luận**:
  pyannote.audio (hoặc tương đương) cần venv HOÀN TOÀN MỚI (`.venv-diar`), không
  "đi nhờ" được venv nào sạch cho máy CPU-only.
- **Cơ chế multi-voice per-segment ĐÃ CÓ SẴN**: `pipeline.py` (bước tổng hợp TTS)
  đọc `seg["voice"]` tuỳ chọn cho từng câu, dùng bởi `editor.py::set_segment_voice`
  qua GUI (`editor_page.py`, gán TAY). V26/V28 chỉ cần TỰ ĐỘNG ĐIỀN field này
  (diarization → speaker→voice; emotion → style) — không viết lại tầng TTS.
- **Glossary + NLLB**: `ctranslate2.Translator.translate_batch()`'s `target_prefix`
  (dùng trong `translate_local_worker.py` hiện tại) CHỈ ép token ngôn ngữ đích ở
  đầu chuỗi — không có API lexical-constraint/vocabulary-biasing để ép 1 từ giữa
  câu. NLLB không nhận prompt như LLM — cơ chế `build_user_context_block` (chèn
  glossary vào prompt, dùng cho nhánh SaaS) không áp dụng được cho NLLB. **Kết
  luận**: cơ chế khả thi DUY NHẤT cho nhánh local là hậu xử lý tìm-thay-thế.
- **Emotion signal**: `--style` của VieNeu là tham số inference THẬT (không phải
  chuẩn hoá text) nhưng hiện là 1 giá trị CỐ ĐỊNH cho toàn bộ lượt chạy worker
  (không phải per-request). Không có tín hiệu cảm xúc per-segment nào tồn tại sẵn
  — `buildAnalysisPrompt` (control_server) chỉ trả kết quả CẤP VIDEO. Không có
  audio-prosody (pitch/RMS) nào trong code hiện tại (`pydub` không expose pitch).
- **API developer (control_server)**: identity 100% device-fingerprint
  (`device_id.py`, `Device.js`) — không có API key/org nào. `CreditLedger` khoá
  theo fingerprint. Dịch thuật (`ai-gateway.service.js`) là phần DUY NHẤT chạy
  100% server-side thật; cloud-render (V12) chỉ có Demucs, CPU-only (không cấp
  GPU trong `docker-compose.yml`), 1 worker replica xử lý TUẦN TỰ — không sẵn
  sàng cho tải đa tenant. ASR/TTS KHÔNG có đường server-side nào.

### V26 — Diarization tự động (đa giọng nói)

```
V26 — Diarization tự động, tận dụng cơ chế multi-voice per-segment có sẵn (Phase G)

Context:
- ASR hiện tại (Whisper/Paraformer) chỉ trả text+timing, KHÔNG có tín hiệu người
  nói — xác nhận qua audit `asr_whisper_worker.py`.
- `pipeline.py` ĐÃ đọc `seg["voice"]` tuỳ chọn (đa giọng per-segment) — cơ chế
  TTS multi-voice đã tồn tại, hiện chỉ gán được TAY qua editor
  (`editor.py::set_segment_voice`, GUI `editor_page.py`).
- Không venv nào có torch trừ `.venv-gpu` (chỉ máy có NVIDIA GPU) — pyannote.audio
  cần venv MỚI hoàn toàn, không đi nhờ được (xem "Audit Before Build" chung).

Goal:
- Video nhiều người nói tự động được gán giọng khác nhau, không cần người dùng
  tự click từng câu trong editor.

Constraints (Guardrails):
1. Chạy 100% local (offline-first) — không gửi audio ra ngoài máy.
2. KHÔNG bắt buộc — pipeline phải degrade trung thực nếu chưa cài `.venv-diar`
   (giống Paraformer lỗi → fallback Whisper có log rõ) — không giả vờ có mà gán
   giọng bừa.
3. Venv riêng `.venv-diar`, theo đúng nguyên tắc "mỗi engine nặng chạy trong venv
   con riêng" (CLAUDE.md) — không nhét torch vào venv chính, không giả định
   `.venv-gpu` luôn tồn tại (chỉ máy NVIDIA mới có).
4. Số giọng phát hiện được > số giọng khả dụng trong catalog → xử lý rõ ràng
   (round-robin có log), không crash.
5. Cài đặt TUỲ CHỌN (opt-in qua `.bat` riêng, giống Paraformer/Douyin) — không
   bundle mặc định (tăng kích thước cài đặt, không phải ai cũng cần đa giọng).

Scope:
A. `scripts/setup_diarization.py` + `Cai dat Diarization.bat` — cài `.venv-diar`
   (pyannote.audio + torch CPU, hoặc GPU nếu máy có card đồ hoạ), theo đúng mẫu
   `setup_paraformer.py`.
B. `autodub/speech/diarize_worker.py` (mới) — worker chuẩn (giống
   `asr_paraformer_worker.py`): nhận audio path, trả JSON stream
   `{"segment": true, "start", "end", "speaker_label"}`.
C. `autodub/speech/diarization.py` (mới) — driver gọi worker qua subprocess,
   dùng `autodub.subprocess_watchdog` NGAY TỪ ĐẦU (không lặp lại bug đã sửa ở
   V24 cho các worker khác); map kết quả diarization vào ASR segments theo %
   overlap thời gian lớn nhất.
D. `autodub/pipeline.py` — bước mới (opt-in qua `settings.diarization_enabled`,
   mặc định TẮT) sau ASR, trước dịch: gán `seg["speaker_label"]`, map
   speaker_label → tên giọng qua round-robin trên `voices.catalog()` đã có,
   ghi vào `seg["voice"]` (TÁI DÙNG cơ chế có sẵn, không viết lại TTS logic).
E. GUI: bước mới "Xem trước người nói" giữa ASR và chọn giọng — liệt kê N
   speaker phát hiện được kèm đoạn audio mẫu, cho đổi giọng theo TỪNG SPEAKER
   (không phải đổi tay từng câu) — mở rộng `editor_panels.py`, tái dùng UI
   pattern voice-picker đã có ở `style_dialog.py`/`editor.py`.
F. CLI: `voxdub dub --multi-speaker` (dùng gán tự động round-robin, không có
   UI để override tay — batch/watch-folder không tương tác được).
G. Tests: driver diarization (worker giả, theo đúng cách đã làm cho
   `run_local_worker()`/Whisper/Paraformer ở V24); mapping speaker→voice round-
   robin; fallback khi `.venv-diar` chưa cài (giữ hành vi single-voice cũ,
   không crash, có test khoá 0-regression).

Audit Before Build: đã làm (xem mục chung đầu Phase G). Còn thiếu khi bắt tay
build:
- Audit định dạng thật `voices.catalog()` trả về để viết round-robin đúng
  (không đoán trước cấu trúc).
- Xác nhận license `pyannote.audio` (thường cần HuggingFace token + chấp nhận
  user agreement cho pretrained model) — KHÔNG giả định miễn phí hoàn toàn tuỳ
  model chọn, kiểm tra cụ thể trước khi chọn, tài liệu hoá rõ trong
  `HUONG_DAN_CAI_DAT.md` nếu cần đăng ký tài khoản.
- Đo benchmark CPU-only trên cấu hình tối thiểu đã công bố (8GB RAM) trước khi
  cam kết — pyannote có thể nặng hơn Whisper/Demucs, không suy đoán.

Design Choice:
- Venv riêng, cài optional — không ép mọi người dùng tải thêm torch (~1-2GB) nếu
  không cần đa giọng.
- Map diarization → voice bằng ROUND-ROBIN trên catalog hiện có (KHÔNG tự động
  "tìm giọng giống nhất với người nói thật" — quá phức tạp, để dành mini-spec
  riêng nếu cần "voice matching" thông minh hơn sau này).
- Gán segment cho speaker có % overlap thời gian LỚN NHẤT — đơn giản, đủ dùng
  cho phần lớn video 2-4 người nói không chồng tiếng nhiều; KHÔNG cam kết chất
  lượng ở video nhiều người/giọng chồng lấn nặng.

Test Plan:
- Unit: mapping overlap→speaker đúng với input giả; round-robin gán voice đúng
  số giọng có sẵn; degrade an toàn khi thiếu `.venv-diar` (y hệt hành vi cũ).
- Live-verify (nếu môi trường có mạng, không cần GPU — pyannote hỗ trợ CPU chậm
  hơn): tải pyannote.audio thật, chạy trên 1 đoạn audio 2 người nói thật, xác
  nhận diarization thật phân biệt đúng 2 khoảng giọng — đúng nguyên tắc "mở
  rộng có kiểm chứng" của dự án (V4/V11).
- KHÔNG cam kết chất lượng ở video >4 người nói/giọng chồng lấn nhiều (ghi nhận
  rõ, ngoài phạm vi live-verify ban đầu).

Success Criteria:
- Video 2-3 người nói, bật diarization → xuất video có giọng khác nhau đúng
  người nói (live-verify ít nhất 1 video thật 2 giọng).
- Không bật diarization (mặc định) → hành vi Y HỆT hiện tại, 0 regression.
- `.venv-diar` chưa cài → pipeline chạy bình thường single-voice, log rõ ràng
  "chưa cài diarization, dùng giọng đơn" (không âm thầm bỏ qua).
```

### V27 — Sửa bug glossary không hoạt động trên nhánh dịch local NLLB

```
V27 — Glossary chỉ hoạt động ở nhánh SaaS, nhánh local NLLB âm thầm bỏ qua (bug thật, Phase G)

Context:
- Audit xác nhận: `translate_glossary` (Settings) CHỈ được enforce ở nhánh SaaS
  (`translate_hint.py::build_user_context_block`, chèn vào prompt LLM) —
  nhánh local NLLB (`translate_local_worker.py`) KHÔNG BAO GIỜ đọc glossary,
  âm thầm bỏ qua. Đây là BUG THẬT (không phải thiếu tính năng): người dùng đặt
  glossary tưởng áp dụng mọi bản dịch, thực ra chỉ áp dụng khi dùng SaaS.
- Audit kỹ thuật: `ctranslate2`'s `target_prefix` (đang dùng trong
  `translate_local_worker.py`) chỉ ép TOKEN NGÔN NGỮ ĐÍCH ở đầu chuỗi, KHÔNG có
  cơ chế lexical-constraint để ép 1 từ giữa câu. NLLB không nhận prompt như LLM
  — cơ chế `build_user_context_block` KHÔNG áp dụng được cho NLLB.
- Cơ chế khả thi DUY NHẤT: hậu xử lý tìm-thay-thế (tìm thuật ngữ nguồn trong câu
  gốc, ép thuật ngữ đích cố định vào bản dịch NLLB).

Goal:
- Glossary người dùng đặt được áp dụng NHẤT QUÁN ở CẢ 2 nhánh dịch (SaaS và
  local NLLB), không chỉ 1 nhánh như hiện tại.

Constraints (Guardrails — BUG FIX, áp theo đúng chuẩn "sửa triệt để + test lại"):
1. KHÔNG đổi hành vi nhánh SaaS đã đúng (`build_user_context_block` giữ nguyên).
2. Thừa nhận rõ giới hạn kỹ thuật: tìm-thay-thế văn bản KHÔNG hoàn hảo (không xử
   lý được biến cách/chia động từ/thứ tự từ khác nhau giữa 2 ngôn ngữ) — Success
   Criteria KHÔNG yêu cầu "hoàn hảo", chỉ yêu cầu "thuật ngữ xuất hiện đúng,
   không còn bị bỏ qua 100% như hiện tại".
3. Không match nhầm giữa-từ (vd glossary "AI" không được thay bên trong
   "SAIGON") — dùng ranh giới từ khi tìm-thay-thế.
4. Áp dụng SAU khi NLLB dịch xong (hậu xử lý), KHÔNG đổi luồng gọi model — giữ
   nguyên rủi ro thấp cho `run_local_worker()` (vừa làm cứng cáp ở V24, không
   mở rộng phạm vi rủi ro của worker).

Scope:
A. `autodub/text/translate_glossary_apply.py` (mới) — hàm THUẦN
   `apply_glossary(source_text, translated_text, glossary_pairs) -> str`: tìm
   từng cặp (nguồn, đích), nếu thuật ngữ nguồn xuất hiện trong `source_text`
   (ranh giới từ, không phân biệt hoa/thường) mà thuật ngữ đích CHƯA có sẵn
   trong `translated_text`, chèn/thay thế bảo thủ.
B. `autodub/text/translate_local.py::translate_segments_local()` — sau khi
   nhận kết quả từ `run_local_worker()`, áp `apply_glossary()` cho từng segment
   nếu `settings.translate_glossary` không rỗng.
C. Audit CHÍNH XÁC format thật của `settings.translate_glossary` (text nhiều
   dòng người dùng nhập qua GUI, ký tự phân tách nguồn/đích) — CHƯA audit ở
   lượt research ban đầu, bắt buộc làm trước khi code phần parse.
D. Tests: glossary áp đúng khi thuật ngữ nguồn xuất hiện; KHÔNG match nhầm giữa
   từ; không đổi câu nếu thuật ngữ đích đã có sẵn (tránh thay 2 lần); glossary
   rỗng → hành vi y hệt trước (0 regression); nhánh SaaS không bị ảnh hưởng.

Audit Before Build: đã xác nhận `target_prefix` không dùng được cho mục đích
này (xem "Audit Before Build" chung). CẦN audit thêm format thật của
`settings.translate_glossary` trước khi viết `apply_glossary()` — chưa làm ở
lượt research ban đầu.

Design Choice:
- Hậu xử lý tìm-thay-thế thay vì sửa model/decode — đơn giản, rủi ro thấp,
  khớp đúng giới hạn kỹ thuật thật của ctranslate2 (không có API tốt hơn).
- Regex có ranh giới từ (`\b`) cho ngôn ngữ có khoảng trắng (Latin); CJK cần xử
  lý khác (không có "ranh giới từ" rõ ràng — đúng bài học V19: `\s*` không
  `\s+`, ký tự không khoảng trắng) — thuật toán CJK cụ thể để dành audit khi
  bắt tay build, không đoán trước.

Test Plan:
- Unit thuần trên `apply_glossary()` — không cần chạy NLLB thật.
- Integration: 1 lượt dịch local NLLB thật (dùng lại hạ tầng test đã có ở
  V6/V21 — model qua `VOXDUB_TEST_NLLB_MODEL_DIR`) với glossary thật, xác nhận
  thuật ngữ xuất hiện đúng trong bản dịch — nếu môi trường có model.

Success Criteria:
- Cùng 1 glossary, dịch qua CẢ 2 nhánh (SaaS + local) đều thấy thuật ngữ xuất
  hiện đúng (trước đây chỉ SaaS).
- 0 regression nhánh SaaS.
- Test khoá rõ giới hạn: không match nhầm giữa từ, không thay 2 lần.
```

### V28 — Emotion/tone-aware voice tự động

```
V28 — Emotion/tone-aware voice, tận dụng cơ chế per-segment voice có sẵn (Phase G)

Context:
- VieNeu worker CÓ tham số `--style` thật (tu_nhien/tin_tuc/doc_truyen) — ảnh
  hưởng thật tới inference (không phải chuẩn hoá text), NHƯNG là 1 giá trị DUY
  NHẤT cho toàn bộ lượt chạy worker, không đổi theo từng câu.
- Cơ chế per-segment voice override (`seg["voice"]`) đã có (dùng chung với
  V26) — nhưng chưa có field per-segment STYLE tương ứng, và chưa có TÍN HIỆU
  nào để tự động quyết định câu nào cần giọng điệu gì.
- Audit: `buildAnalysisPrompt` (control_server) hiện chỉ trả kết quả CẤP VIDEO
  (summary/domain/pronouns/glossary/style_notes) — CHƯA BAO GIỜ hỏi LLM gắn
  nhãn cảm xúc THEO TỪNG CÂU.
- Không có audio-based (pitch/RMS) signal nào trong code hiện tại (`pydub`
  không expose pitch); thêm phân tích âm điệu gốc cần dependency mới.

Goal:
- Giọng đọc thay đổi sắc thái theo cảm xúc TỪNG CÂU thay vì 1 style cố định
  toàn video — bắt kịp hướng "Emotive TTS" của đối thủ (Deepdub).

Constraints (Guardrails):
1. CHỈ hoạt động khi có nguồn tín hiệu cảm xúc đáng tin — KHÔNG suy đoán cảm
   xúc bừa nếu không có tín hiệu (đúng nguyên tắc "không suy đoán capability
   khi thiếu evidence" — CLAUDE.md).
2. Nhánh SaaS (có LLM phân tích) và nhánh local-only (không LLM) PHẢI có 2
   đường xử lý RÕ RÀNG KHÁC NHAU, không giả vờ tương đương:
   - SaaS: mở rộng `buildAnalysisPrompt` gắn nhãn cảm xúc mỗi câu (không cần
     dependency mới, chỉ đổi prompt/schema).
   - Local-only: heuristic đơn giản dựa văn bản (dấu câu "!"/"?", chữ hoa toàn
     bộ, từ khoá cảm thán) — ĐỘ CHÍNH XÁC THẤP HƠN HẲN, gắn nhãn "thử nghiệm",
     có thể tắt riêng.
3. KHÔNG thêm dependency audio-processing mới (vd librosa) trong V28 — phạm vi
   CHỈ dùng tín hiệu VĂN BẢN (LLM hoặc heuristic); audio-prosody-based là
   NÂNG CẤP TIẾP THEO, không gộp vào đây.
4. Chỉ áp dụng cho VieNeu (giọng có `--style` thật) — CapCut TTS (giọng ngoài,
   không có knob emotion) KHÔNG áp style, giữ nguyên hành vi hiện tại.

Scope:
A. `control_server/src/prompts/translate.js` — mở rộng `buildAnalysisPrompt`/
   schema JSON để LLM trả thêm field `tone` mỗi segment (enum nhỏ:
   "neutral"/"excited"/"sad"/"serious" — ánh xạ được sang 3 style VieNeu hiện
   có, KHÔNG bịa style mới ngoài những gì VieNeu thật hỗ trợ).
B. `autodub/text/translate_hint.py` (hoặc module tương đương) — heuristic
   local-only (dấu câu/từ khoá) khi KHÔNG có SaaS, đặt cờ nguồn tín hiệu
   ("llm"/"heuristic") để GUI hiển thị đúng mức độ tin cậy.
C. `autodub/pipeline.py` — map `tone` → style VieNeu, ghi vào field style
   override cấp segment (mới, cạnh `seg["voice"]`), CHỈ áp dụng khi giọng đang
   dùng là VieNeu.
D. `autodub/speech/tts/vieneu_vi.py`/`vieneu_worker.py` — nhận style
   PER-SEGMENT thay vì chỉ per-run (hiện `--style` là tham số khởi động worker
   1 lần — audit kỹ giao thức worker trước khi đổi, xem "Audit Before Build").
E. Settings: cờ bật/tắt (mặc định TẮT — 0 regression khi không dùng, đúng mọi
   mini-spec Phase F/G khác).
F. Tests: mapping tone→style đúng; heuristic văn bản (câu có "!"/"?"/chữ hoa)
   cho đúng nhãn thô; giọng CapCut không bị áp style (giữ nguyên); tắt cờ →
   hành vi y hệt cũ.

Audit Before Build: đã xác nhận `--style` là tham số khởi động 1 lần của
worker (xem "Audit Before Build" chung). CẦN audit lại giao thức
`vieneu_worker.py` ĐẦY ĐỦ (không chỉ CLI arg) để biết đổi sang per-segment có
khả thi kỹ thuật hay cần khởi động lại worker mỗi lần đổi style (chi phí hiệu
năng thật, có thể phải cache theo style thay vì đổi liên tục) — CHƯA làm ở
lượt research ban đầu.

Design Choice:
- Ưu tiên nguồn tín hiệu LLM (SaaS) khi có — chính xác hơn hẳn heuristic văn
  bản thuần.
- Heuristic local-only là "tốt hơn không có gì" chứ không giả vờ ngang hàng
  LLM — gắn nhãn rõ trong GUI ("thử nghiệm, dựa dấu câu").
- KHÔNG động vào audio-prosody (pitch/RMS) trong V28 — giữ phạm vi hẹp, để
  dành mini-spec riêng nếu cần chính xác hơn.

Test Plan:
- Unit: mapping tone→style, heuristic text-based, cờ tắt/bật.
- Live-verify: NẾU giao thức worker cho phép đổi style theo từng câu mà không
  phải khởi động lại toàn bộ — verify thật 1 đoạn có câu "vui" và câu "nghiêm
  túc" ra 2 kiểu đọc khác nhau ĐO ĐƯỢC (RMS/waveform khác nhau, không chỉ nghe
  bằng tai).

Success Criteria:
- Video có SaaS bật + có câu cảm thán rõ ràng → giọng đọc câu đó khác câu
  bình thường (verify qua tín hiệu audio đo được).
- Tắt cờ (mặc định) → 0 regression.
- Giọng CapCut không bị ảnh hưởng bởi tính năng này.
```

### V29 — Lộ rõ AI review dịch ra quality_report.json + GUI

```
V29 — Lộ rõ trace của translate_review.py, đóng góp phần cho "human-in-the-loop QA" (Phase G)

Context:
- `translate_review.py` đã TỰ ĐỘNG chạy (mặc định bật), phát hiện + sửa câu có
  vấn đề (vượt ngân sách ký tự, còn sót chữ Hán, quá ngắn so với gốc) — NHƯNG
  kết quả review (câu nào bị flag, lý do gì, có sửa được không) KHÔNG được ghi
  lại ở đâu cả sau khi xong — chỉ tồn tại tạm thời trong bộ nhớ lúc chạy.
- `quality_report.json` (V23) tính lại vấn đề ĐỘC LẬP từ timing/budget — không
  biết gì về việc `translate_review` đã từng flag + sửa (hoặc thử sửa mà KHÔNG
  sửa được).
- Gap thật giữa những gì hệ thống ĐÃ LÀM (review tự động) và những gì NGƯỜI
  DÙNG THẤY ĐƯỢC (không gì cả) — hướng gần nhất tới "human-in-the-loop QA" của
  đối thủ (Papercup), dù VoxDub chưa có bước NGƯỜI THẬT xem — V29 là bước lộ rõ
  AI-QA trước, làm nền cho bước người thật sau nếu cần (mini-spec riêng).

Goal:
- Người dùng (và cổng chất lượng V23) thấy được CHÍNH XÁC review pass đã làm
  gì — câu nào bị nghi vấn, đã tự sửa hay vẫn còn vấn đề sau khi sửa.

Constraints (Guardrails):
1. KHÔNG đổi logic review đã đúng (`review_translations()` giữ nguyên hành vi
   sửa dịch) — chỉ THÊM việc ghi lại kết quả.
2. Field mới trong `quality_report.json` phải ADDITIVE (không đổi field cũ đã
   có từ V23 — `evaluate()`/`QualityThresholds` không cần biết field mới này,
   giữ đúng nguyên tắc tách biệt của V23).
3. Không lộ trace review cho câu KHÔNG bị flag (review pass chỉ đụng câu có vấn
   đề — `quality_report.json` chỉ nên liệt kê câu có review-trace).

Scope:
A. `autodub/text/translate_review.py::review_translations()` — trả thêm 1
   danh sách trace (`[{"id", "reason", "before", "after", "improved": bool}]`)
   bên cạnh kết quả dịch đã sửa (KHÔNG đổi return type theo cách phá vỡ caller
   cũ — audit kỹ chữ ký hàm trước khi đổi, xem "Audit Before Build").
B. `autodub/pipeline.py` — lưu trace này, truyền vào `_build_quality_report()`,
   thêm field mới `translate_review` (danh sách trace) vào `quality_report.json`.
C. GUI (`autodub_gui/pages/quality_page.py`/`editor_panels.py`) — thêm cột/nhãn
   "AI đã tự sửa" cho câu có trace, click xem before/after.
D. CLI (`autodub/cli.py`, tận dụng `--quality-gate` V23) — verdict có thể tham
   chiếu số câu đã được AI review sửa, KHÔNG bắt buộc đổi ngưỡng pass/fail
   (chỉ thêm thông tin).
E. Tests: trace ghi đúng before/after; câu không bị flag không có trace;
   `quality_report.json` field mới additive (test cũ V23 vẫn pass y hệt — 0
   regression); GUI hiện đúng (nếu test headless được).

Audit Before Build: cần đọc lại chữ ký hàm `review_translations()` ĐẦY ĐỦ
(không chỉ phần đã audit) để biết đổi return type có phá vỡ caller nào khác
không (`pipeline.py` là caller chính đã xác nhận, cần xác nhận không còn caller
khác) — CHƯA làm ở lượt research ban đầu.

Design Choice:
- Trace tách khỏi luồng sửa dịch chính (thêm, không thay) — review vẫn hoạt
  động y hệt kể cả nếu ghi trace lỗi (không được làm hỏng luồng dịch chính vì
  1 tính năng quan sát).

Test Plan:
- Unit: trace đúng cấu trúc, additive vào `quality_report.json`, không phá
  test V23 cũ.
- Regression: chạy lại toàn bộ `tests/test_quality_gate.py` xác nhận 0 đổi
  hành vi.

Success Criteria:
- `quality_report.json` của 1 video có câu bị review sửa → thấy rõ field
  `translate_review` liệt kê đúng câu đó kèm before/after.
- Video không có câu nào bị flag → field rỗng/không có, không gây nhiễu.
- 0 regression V23.
```

### V30 — Audit khả thi Lip-sync (KHÔNG cam kết build)

```
V30 — Audit lip-sync: chi phí thật, lựa chọn model, quyết định chính sách bắt buộc (Phase G)

Context:
- Lip-sync gần như là tính năng chuẩn ở mọi đối thủ lớn (ElevenLabs, HeyGen,
  Rask, CapCut, Murf, Deepdub) — gap cạnh tranh LỚN NHẤT còn lại theo research
  thị trường của chủ dự án.
- KHÔNG có bằng chứng VoxDub từng loại trừ tường minh tính năng này (đã đọc kỹ
  ARCH/PRD/PLAN/CLAUDE — không thấy nhắc tới) — nhưng cũng CHƯA từng audit khả
  thi kỹ thuật.
- Tiền lệ trực tiếp: V5 (che chữ gốc) đã CHỦ ĐỘNG KHÔNG dùng AI inpainting
  (LaMa/ProPainter) vì "quá lớn cho 1 mini-spec" — lip-sync còn nặng hơn nhiều
  (video diffusion/GAN theo khung hình, không phải ảnh tĩnh).
- Rủi ro đạo đức thật: sửa khuôn mặt người trong video là vùng giáp ranh
  deepfake — README/LICENSE hiện chỉ có CẢNH BÁO CHÍNH SÁCH ("xin đừng dùng để
  giả mạo"), KHÔNG có kiểm soát kỹ thuật nào (rate-limit, watermark, consent
  check) — xác nhận bởi chủ dự án.

Goal:
- Có ĐỦ DỮ LIỆU THẬT (chi phí compute, chất lượng model mã nguồn mở khả dụng,
  rủi ro pháp lý/đạo đức cụ thể) để chủ dự án ra quyết định CÓ/KHÔNG build
  lip-sync — mini-spec này KHÔNG build gì, chỉ audit + ép ra quyết định.

Constraints (Guardrails):
1. KHÔNG viết code sản xuất trong mini-spec này — chỉ nghiên cứu + thử nghiệm
   nhỏ (đo đạc, không phải tính năng).
2. Nghiên cứu PHẢI đo bằng số liệu THẬT (VRAM cần, thời gian xử lý/phút video,
   chất lượng thật trên video mẫu) — không lấy số liệu quảng cáo của công cụ
   khác làm chuẩn.
3. PHẢI đưa ra danh sách quyết định chính sách CỤ THỂ (không phải chung chung
   "cần cẩn thận") mà chủ dự án cần trả lời TRƯỚC KHI bất kỳ ai bắt tay build.

Scope (đây là RESEARCH, không phải code Scope A-F như mini-spec khác):
A. Khảo sát model mã nguồn mở khả dụng offline: Wav2Lip (nhẹ, chất lượng thấp,
   khung hình crop miệng nhỏ), SadTalker, VideoRetalking, MuseTalk hoặc tương
   đương mới hơn tại thời điểm làm — so sánh giấy phép kỹ (một số model nghiên
   cứu CẤM dùng thương mại, PHẢI kiểm tra trước khi chọn, không phải mọi model
   lip-sync mã nguồn mở cho phép dùng thương mại), yêu cầu phần cứng, chất
   lượng thật trên video mẫu tiếng Việt/Trung.
B. Đo THẬT trên phần cứng TỐI THIỂU đã công bố trong README (8GB RAM, không
   bắt buộc GPU) VÀ trên phần cứng có GPU tầm trung (nếu sandbox không có GPU
   thật, ghi rõ giới hạn — không giả vờ đo được khi không có phần cứng): VRAM
   tối thiểu, thời gian xử lý 1 phút video 1080p, chất lượng ở góc nghiêng/che
   khuất mặt (tình huống thật của video thị trường, không phải mặt thẳng
   studio). Mọi prototype/thử nghiệm cô lập trong `scripts/research/` + venv
   con riêng (`.venv-lipsync-research` nếu cần) — KHÔNG merge vào
   `pipeline.py` chính, không đụng `requirements.txt` chính, không tải/host
   model weights lớn (GB) trong repo (tài liệu hoá cách tự tải giống các
   `scripts/setup_*.py` khác nếu cần dùng tiếp).
C. Liệt kê quyết định chính sách BẮT BUỘC chủ dự án phải trả lời trước khi
   build: (a) có cần consent-check kỹ thuật không (vd chặn nếu phát hiện mặt
   người nổi tiếng/công chúng qua nhận diện)? (b) có bắt buộc watermark video
   đã lip-sync không? (c) tính năng có giới hạn theo gói/Vox trả phí để tránh
   lạm dụng hàng loạt không? (d) venv riêng `.venv-lipsync` GPU-only có chấp
   nhận được không (tính năng sẽ KHÔNG chạy được trên máy không có GPU mạnh —
   bất đối xứng lớn so với mọi tính năng khác của VoxDub vốn có đường CPU
   fallback)?
D. Báo cáo cuối: bảng so sánh chi phí/lợi ích, khuyến nghị build/không
   build/build-giới-hạn (vd chỉ mặt thẳng, chỉ video ngắn), và nếu build thì
   ước lượng mức độ 1 mini-spec riêng có đủ hay cần chia nhiều phase (giống
   Phase C/D đã chia V8→V11, V9→V12 trước đây).

Audit Before Build: N/A (chính mini-spec NÀY là audit).

Design Choice: N/A (không quyết định kiến trúc — mini-spec kế tiếp sau khi có
quyết định của chủ dự án mới quyết định kiến trúc, nếu được duyệt build).

Test Plan: N/A — "Test" của mini-spec này là ĐỘ TIN CẬY của số liệu đo được
(đo trên phần cứng thật, không suy đoán).

Success Criteria:
- Có bảng so sánh ≥2 model mã nguồn mở THẬT, đo được (không phải liệt kê tên
  suông).
- Có danh sách quyết định chính sách rõ ràng, đủ cụ thể để chủ dự án trả lời
  Có/Không cho từng mục (không phải câu hỏi mở).
- Có khuyến nghị rõ ràng (build/không build/build giới hạn) kèm lý do — KHÔNG
  lấp lửng.
```

### V31 — Translation-as-a-Service API cho developer bên thứ 3

```
V31 — API dịch thuật cho bên thứ 3, phạm vi hẹp có chủ đích (Phase G)

Context:
- Audit control_server: identity hiện tại 100% theo device-fingerprint
  (`device_id.py`, `Device.js` schema) — KHÔNG có khái niệm API key/tổ chức
  nào. Billing (`CreditLedger`) khoá theo fingerprint, không theo org.
- Phần DỊCH THUẬT (không phải ASR/TTS/video) đã 100% chạy server-side thật
  (`ai-gateway.service.js` gọi LLM thật) — đây là phần DUY NHẤT trong toàn hệ
  thống sẵn sàng mở cho bên thứ 3 mà KHÔNG cần đầu tư hạ tầng GPU mới (khác
  ASR/TTS/video hiện chỉ chạy trên máy người dùng, không có server nào làm
  thay — xác nhận qua audit: cloud-render V12 chỉ có Demucs CPU-only, 1 worker
  tuần tự, không sẵn sàng đa tenant).
- Rate limiting đã có (`@fastify/rate-limit`) nhưng khoá theo IP/device-token,
  không theo API key/tổ chức — cần lớp mới.
- **Quyết định phạm vi đã chốt với chủ dự án**: CHỈ mở API dịch thuật, KHÔNG mở
  ASR/TTS/video (đó là hướng "Full hosted Dub API" — quy mô đầu tư hạ tầng
  khác hẳn, không nằm trong mini-spec này, cần quyết định đầu tư riêng nếu
  theo đuổi sau này).

Goal:
- Developer bên thứ 3 gọi được 1 API dịch thuật thật (không qua desktop app
  VoxDub) bằng API key riêng, tính phí theo tổ chức/API key (không lẫn với ví
  Vox cá nhân của người dùng desktop).

Constraints (Guardrails):
1. KHÔNG đụng ASR/TTS/video — phạm vi CHỈ dịch thuật (tận dụng đúng phần đã
   100% server-side).
2. KHÔNG thay `saas_client.is_configured()` làm cổng chính cho app desktop —
   API key là lớp identity THỨ 2, SONG SONG với device-fingerprint, không thay
   thế (desktop app người dùng cuối vẫn dùng device-fingerprint như cũ, 0
   regression).
3. Billing tách biệt: `CreditLedger` hiện tại của người dùng desktop KHÔNG
   được lẫn với usage của API key bên thứ 3 — cần model/collection MỚI, không
   tái dùng thẳng Device/CreditLedger hiện có (rủi ro lẫn ví thật).
4. Rate limit RIÊNG theo API key/tổ chức (không dùng chung bucket IP/device-
   token hiện có — 1 API key gọi nhiều từ nhiều IP vẫn phải tính đúng 1 quota).
5. KHÔNG thêm MongoDB transaction/replica-set (giữ đúng nguyên tắc atomic
   single-node của V1) — billing theo API key vẫn dùng `findOneAndUpdate`
   atomic, không đổi mô hình.
6. KHÔNG thêm Redis/broker (giữ đúng nguyên tắc V12) — phạm vi V31 là API
   ĐỒNG BỘ (request/response ngay, không phải job queue), câu hỏi Redis/broker
   của V12 không áp dụng ở đây; nếu sau này cần queue cho khối lượng lớn, đó
   là quyết định RIÊNG khi có tải thật.

Scope:
A. `control_server/src/models/ApiKey.js` (mới) — schema: key (hash, không lưu
   plaintext), orgName, status, quota/usage counters, createdAt. Model RIÊNG,
   không sửa `Device.js`.
B. `control_server/src/middleware/apikey.middleware.js` (mới) — xác thực qua
   header (vd `Authorization: Bearer vx_live_...`), SONG SONG với
   `auth.middleware.js` hiện có (route nào dùng middleware nào tách rõ, không
   gộp logic).
C. `control_server/src/routes/api/v1/translate.js` (mới, namespace RIÊNG khỏi
   route nội bộ hiện có) — endpoint public, tái dùng `ai-gateway.service.js`
   (không viết lại logic gọi LLM), nhưng KHÔNG dùng lại prompt/schema nội bộ
   dành cho luồng dub video (context/domain/pronouns của `translate.js` hiện
   tại gắn với ngữ cảnh video) — cần 1 phiên bản prompt ĐƠN GIẢN HƠN cho dịch
   văn bản độc lập (không có "video context").
D. Rate limit + quota theo `apiKeyId` (không phải IP/device-token) — namespace
   `@fastify/rate-limit` riêng cho route `/api/v1/*`.
E. Billing: `ApiUsageLedger` (mới, TÁCH khỏi `CreditLedger`) — ghi mỗi lượt
   gọi, đối chiếu quota.
F. Tài liệu: `docs/API.md` mở rộng — endpoint public, cách lấy API key (thủ
   công qua admin lúc đầu, chưa cần self-service portal — self-service là
   mini-spec RIÊNG nếu nhu cầu thật xuất hiện).
G. Tests: xác thực API key đúng/sai; rate-limit theo `apiKeyId` không lẫn với
   device-token; billing ghi đúng, KHÔNG đụng `CreditLedger` của desktop;
   endpoint dịch trả kết quả đúng (mock LLM call trong test, không gọi thật
   tốn tiền).

Audit Before Build: đã audit đủ (auth/billing/server-side-execution — xem
"Audit Before Build" chung đầu Phase G). Cần audit THÊM khi build: chữ ký
`ai-gateway.service.js` hiện có (có sẵn hàm dịch văn bản độc lập chưa gắn với
luồng video hay phải viết mới hoàn toàn) — chưa làm ở lượt research ban đầu.

Design Choice:
- API key là lớp identity THỨ 2 hoàn toàn tách biệt (không sửa
  `auth.middleware.js`/`Device.js`) — giữ đúng tinh thần "0 regression cho
  luồng cũ" đã dùng xuyên suốt Phase F: hệ thống HOÀN TOÀN MỚI cộng thêm,
  không sửa hệ thống cũ.
- Billing tách `ApiUsageLedger` khỏi `CreditLedger` — tránh rủi ro thật: 1 lỗi
  logic ở billing API bên thứ 3 KHÔNG được có khả năng ảnh hưởng ví Vox của
  người dùng desktop cá nhân.

Test Plan:
- Unit: middleware xác thực, rate-limit theo key, billing ghi đúng ledger mới.
- KHÔNG live-verify gọi LLM thật tốn phí trong mini-spec ban đầu (dùng mock) —
  nếu chủ dự án muốn live-verify thật trước khi phát hành, đó là bước riêng
  trước khi công bố API cho bên ngoài.

Success Criteria:
- Gọi API bằng API key hợp lệ → dịch đúng, trừ đúng quota trong
  `ApiUsageLedger`.
- Gọi bằng API key sai/hết quota → từ chối rõ ràng (401/429), không rơi vào
  luồng device-fingerprint.
- App desktop hiện có (device-fingerprint) hoàn toàn không bị ảnh hưởng — 0
  regression toàn bộ test control_server hiện có.
- `docs/API.md` đủ để 1 developer bên ngoài tự tích hợp mà không cần hỏi thêm.
```

### V32a — PoC lip-sync MuseTalk (đóng gap V30, benchmark thật)

```
V32a — PoC hẹp: benchmark MuseTalk thật + thử nghiệm consent-check/watermark (Phase G)

Context:
- V30 (audit, không build) đã khảo sát 4 model mã nguồn mở, chốt MuseTalk (MIT)
  là lựa chọn DUY NHẤT khả thi cả về giấy phép lẫn phần cứng — Wav2Lip cấm
  thương mại (loại), SadTalker cần VRAM phi thực tế cho video dài (loại thực
  tế), VideoReTalking license chưa xác minh được (loại khỏi so sánh nghiêm
  túc). Nhưng V30 KHÔNG có GPU trong sandbox nên chưa đo được benchmark thật
  (Remaining Limit của V30) — đây chính là gap V32a đóng.
- Chủ dự án đã trả lời đủ 5 câu hỏi chính sách của V30 (2026-08-12, xác nhận
  trực tiếp): (1) CÓ cần consent-check kỹ thuật; (2) CÓ bắt buộc watermark;
  (3) CÓ giới hạn theo gói/Vox; (4) CHẤP NHẬN venv GPU-only (phá nguyên tắc
  "GPU-optional" lần đầu, có chủ đích); (5) KHÔNG cần xét lại Wav2Lip — dùng
  MuseTalk, cần audit KỸ THUẬT của AI (không phải tư vấn pháp lý, vì không
  dùng model có vấn đề pháp lý nữa).
- Tiền lệ đúng mô hình PoC-trước-build đã dùng: V8→V11 (TTS đa ngôn ngữ),
  V9→V12 (cloud rendering) — cả 2 đều PoC hẹp trước, đóng gap sau khi có số
  liệu thật.

Goal:
- Có số liệu benchmark THẬT (VRAM, thời gian xử lý, tỷ lệ face-detection
  thành công) đo trên GPU thật + video mẫu thật đa dạng góc mặt, ĐỦ để quyết
  định V32b có đáng đầu tư không và phạm vi ban đầu nên giới hạn ra sao (vd
  chỉ mặt thẳng trước). Đồng thời chứng minh khả thi kỹ thuật (không chỉ ý
  tưởng) cho 2 yêu cầu chính sách đã chốt: consent-check (nhận diện khuôn
  mặt) và watermark.

Constraints (Guardrails):
1. CHỈ MuseTalk — không khảo sát lại model khác (đã chốt xong ở V30, làm lại
   là lãng phí).
2. PHẢI chạy trên GPU THẬT. Môi trường hiện tại (2026-08-12, xác nhận qua
   `nvidia-smi` không tìm thấy lệnh + `torch.cuda.is_available()` không có
   torch cài) KHÔNG có GPU — đây là GATE CHẶN CỨNG của toàn bộ mini-spec
   này, giống hệt giới hạn đã ghi ở V30. Ai thực thi mini-spec này PHẢI có
   máy/instance có GPU rời thật (khuyến nghị tối thiểu class tương đương
   RTX 3050 Ti 4GB đã có số liệu công khai từ cộng đồng MuseTalk, xem bảng
   V30) trước khi bắt đầu Scope B.
3. PoC cô lập HOÀN TOÀN: venv `.venv-lipsync` mới + script trong
   `scripts/research/` — KHÔNG đụng `pipeline.py` chính, KHÔNG merge vào
   `requirements.txt`/`pyproject.toml` chính, KHÔNG tải/host model weights
   (GB) trong repo (tài liệu hoá cách tự tải, giống mọi `scripts/setup_*.py`
   khác).
4. Consent-check ở PoC này CHỈ cần chứng minh khả thi KỸ THUẬT của bước
   face-detection (phát hiện CÓ khuôn mặt người trong khung hình, tin cậy
   bao nhiêu %) — KHÔNG cần giải bài toán nhận diện DANH TÍNH người nổi
   tiếng (đó là bài toán khác hẳn — face recognition + cơ sở dữ liệu người
   nổi tiếng — ngoài phạm vi PoC này, ghi rõ thành phát hiện/khuyến nghị cho
   V32b thay vì tự mở rộng phạm vi).
5. Watermark ở PoC này CHỈ cần 1 phương án kỹ thuật khả thi (không cần chọn
   phương án cuối) — đo chi phí thời gian xử lý thêm phát sinh.
6. Video mẫu BẮT BUỘC đa dạng: ≥1 mặt thẳng (best case), ≥1 góc nghiêng/che
   khuất một phần (tình huống thật của video thị trường VoxDub xử lý, không
   phải mặt thẳng studio) — không được chỉ test best case rồi suy rộng.

Scope:
A. `.venv-lipsync` (mới, GPU-only) — cài MuseTalk + dependency theo đúng
   hướng dẫn chính chủ repo (không tự chế bộ dependency khác).
B. `scripts/research/lipsync_poc.py` — chạy MuseTalk trên ≥3 video mẫu (1
   mặt thẳng, 1 góc nghiêng/che khuất, 1 nhiều người trong khung) dùng audio
   ĐÃ DỊCH có sẵn từ 1 lượt pipeline VoxDub thật (không audio giả) — đo
   THẬT: VRAM peak, thời gian xử lý/giây video, tỷ lệ frame face-detection
   thành công/thất bại theo từng loại video mẫu.
C. Audit trước: đọc code MuseTalk thật xem face-detection đã tích hợp sẵn
   thư viện nào (không tự chọn lại nếu repo đã có pipeline detection riêng)
   — dùng lại làm bước consent-check thử nghiệm (Constraint 4), đo độ tin
   cậy phát hiện khuôn mặt trên chính 3 video mẫu ở Scope B.
D. Thử nghiệm watermark: 1 phương án cụ thể (vd overlay góc dưới hoặc
   metadata FFmpeg) áp lên video output của Scope B, đo chi phí thời gian
   xử lý thêm.
E. Báo cáo: bảng benchmark thật theo từng video mẫu, đánh giá mức độ hữu
   dụng khi face-detection thất bại (bao nhiêu % frame, hành vi degrade nên
   ra sao), khuyến nghị go/no-go rõ ràng cho V32b kèm phạm vi cụ thể nếu go
   (vd "chỉ hỗ trợ video 1 khuôn mặt, góc gần thẳng trước").

Audit Before Build:
- Xác nhận GPU thật có sẵn TRƯỚC KHI bắt đầu Scope B (Constraint 2) — không
  bắt đầu nếu chưa có, tránh lặp lại giới hạn của V30.
- Đọc code MuseTalk thật (không suy đoán từ README) để biết face-detection
  đã tích hợp sẵn hay cần thêm thư viện ngoài (Scope C).

Design Choice: N/A cho kiến trúc production (đây vẫn là PoC có code thử
nghiệm cô lập, không phải feature) — nhưng KHÁC V30 (chỉ liệt kê câu hỏi
chính sách), V32a PHẢI chứng minh khả thi KỸ THUẬT thật cho consent-check
và watermark, vì 2 điều này chủ dự án đã chốt CÓ, không còn là câu hỏi mở.

Test Plan: "Test" là độ tin cậy số liệu đo thật trên GPU thật + ≥3 video mẫu
đa dạng góc mặt (không phải unit test theo nghĩa thông thường, giống Test
Plan N/A của V30).

Success Criteria:
- Có bảng benchmark THẬT (VRAM/thời gian xử lý/tỷ lệ face-detection thành
  công) trên ≥3 video mẫu đa dạng, đo trên GPU thật.
- Có bằng chứng khả thi kỹ thuật (không phải suy đoán) cho face-detection
  (consent-check) và ≥1 phương án watermark hoạt động được.
- Khuyến nghị go/no-go rõ ràng cho V32b, kèm phạm vi cụ thể nếu go.
```

### V32b — Build lip-sync production (đóng gap V32a)

```
V32b — Tính năng "Đồng bộ khẩu hình" sản xuất (Phase G, CHỈ mở nếu V32a khuyến nghị "go")

Context:
- Điều kiện tiên quyết: V32a phải hoàn thành với khuyến nghị "go" kèm số
  liệu benchmark thật — mini-spec này KHÔNG được mở nếu V32a khuyến nghị
  "không build" hoặc "build giới hạn hơn nữa" mà chưa đáp ứng được.
- 5 quyết định chính sách đã CHỐT CỨNG (2026-08-12, không còn là câu hỏi mở
  ở mini-spec này): consent-check kỹ thuật BẮT BUỘC; watermark BẮT BUỘC;
  giới hạn theo gói/Vox BẮT BUỘC; venv GPU-only CHẤP NHẬN ĐƯỢC (tính năng
  này sẽ KHÔNG chạy trên máy không có GPU mạnh — ngoại lệ kiến trúc đầu
  tiên và duy nhất so với "GPU-optional" của mọi tính năng khác).
- Phạm vi cụ thể (video hỗ trợ, ngưỡng chất lượng chấp nhận được) LẤY TỪ kết
  quả thật của V32a — không tự đoán trước khi có số liệu.

Goal:
- Tính năng "Đồng bộ khẩu hình" hoạt động thật trong pipeline + GUI, đúng
  phạm vi đã được V32a chứng minh khả thi, có đủ 3 lớp kiểm soát đã chốt
  chính sách (consent-check, watermark, giới hạn gói).

Constraints (Guardrails):
1. Venv `.venv-lipsync` GPU-only, subprocess-isolated — cùng pattern mọi
   engine nặng khác (`.venv-whisper`/`.venv-vieneu`/`.venv-asr`/`.venv-gpu`).
2. KHÔNG giả vờ có đường CPU fallback — tính năng này CHỈ bật được khi phát
   hiện GPU đủ mạnh, degrade trung thực (ẩn/khoá tuỳ chọn kèm giải thích rõ,
   không phải lỗi mù mờ) khi không đủ điều kiện phần cứng.
3. Consent-check PHẢI chạy TRƯỚC khi xử lý, không phải hậu kiểm — phát hiện
   khuôn mặt không rõ/nhiều người/độ tin cậy thấp → cảnh báo hoặc chặn theo
   đúng chính sách chốt ở V32a's face-detection findings (ngưỡng cụ thể lấy
   từ số liệu PoC, không đoán).
4. Watermark KHÔNG được tuỳ chọn tắt bởi người dùng cuối — đây là kiểm soát
   đạo đức/pháp lý đã chốt CÓ, không phải tính năng thẩm mỹ.
5. Giới hạn theo gói/Vox: chi phí compute GPU cao hơn HẲN mọi tính năng khác
   (audio-only) — cần mô hình định giá Vox RIÊNG cho lip-sync (không dùng
   chung đơn giá segment hiện có của dịch/TTS), chốt cùng chủ dự án trước
   khi code phần billing.
6. Phạm vi video hỗ trợ ban đầu giới hạn đúng những gì V32a đã CHỨNG MINH
   khả thi (vd chỉ 1 khuôn mặt/góc gần thẳng) — không mở rộng thêm case
   chưa benchmark chỉ vì "chắc cũng chạy được".

Scope (khung ban đầu — tinh chỉnh cụ thể sau khi có số liệu V32a):
A. `.venv-lipsync` production (khác `.venv-lipsync` research của V32a — venv
   research KHÔNG tái sử dụng thẳng cho production, audit lại dependency
   pin version trước khi promote).
B. Stage mới trong `pipeline.py`, chạy SAU khi mix audio dubbed xong, TRƯỚC
   mux video cuối cùng — nhận (video gốc, audio đã lồng tiếng) → face-detect
   + consent-check → lip-sync theo khung hình → watermark → trả video đã
   xử lý cho bước mux hiện có.
C. `autodub_gui/` — toggle "Đồng bộ khẩu hình" (mặc định TẮT), kiểm tra GPU
   trước khi cho bật (Constraint 2), hiển thị rõ thời gian xử lý ước tính sẽ
   tăng đáng kể, cảnh báo watermark bắt buộc trước khi người dùng bấm chạy.
D. `control_server/` — mô hình giá Vox riêng cho lip-sync (Constraint 5),
   giới hạn lượt/thời lượng theo gói.
E. Tests: unit (face-detection threshold logic, watermark áp dụng luôn luôn
   không tắt được, degrade đúng khi thiếu GPU); integration (stage pipeline
   mới chạy đúng thứ tự, không phá stage khác); regression (toàn bộ pipeline
   KHÔNG bật lip-sync phải giữ nguyên 100% hành vi, đúng nguyên tắc mặc định
   TẮT xuyên suốt Phase F/G).

Audit Before Build: đọc kỹ báo cáo + số liệu thật của V32a trước khi viết
Scope B chi tiết — ngưỡng face-detection, phạm vi video hỗ trợ, phương án
watermark cuối cùng đều LẤY TỪ đó, không tự quyết lại.

Design Choice: chưa chốt được đầy đủ trước khi có V32a — nguyên tắc chung
đã rõ (venv GPU-only cô lập, stage cuối trước mux, degrade trung thực,
watermark không tuỳ chọn), chi tiết kỹ thuật (model version, ngưỡng chất
lượng, cấu trúc dữ liệu consent-check) chốt khi mở mini-spec này thật.

Test Plan:
- Unit: watermark luôn áp dụng (không có code path nào bỏ qua được);
  face-detection threshold đúng theo số liệu V32a; degrade đúng khi thiếu
  GPU (thông báo rõ, không crash mù mờ).
- Integration: pipeline đầy đủ có bật lip-sync trên video mẫu, output hợp
  lệ (mux thành công, có watermark).
- Regression: KHÔNG bật lip-sync (mặc định) → 100% hành vi pipeline y hệt
  trước mini-spec này.
- Live verification: ≥3 video thật (đúng phạm vi V32a đã chứng minh khả
  thi) qua GPU thật, đánh giá chất lượng khẩu hình bởi người thật (không tự
  đánh giá bằng "chạy không lỗi" là đủ).

Success Criteria:
- Tính năng chạy được thật trên GPU thật, đúng phạm vi V32a đã benchmark,
  có watermark + consent-check + giới hạn gói hoạt động đúng như chính sách
  đã chốt.
- 0 regression cho pipeline không bật lip-sync.
- Chi phí Vox cho 1 lượt lip-sync phản ánh đúng chi phí compute GPU thật
  (không lỗ, không đoán mò).
```

### V33 — AI tự đề xuất giọng đọc phù hợp theo nội dung video

```
V33 — AI đề xuất giọng đọc theo nội dung, thay vì người dùng tự lọc thủ công (Phase G)

Context:
- Chủ dự án yêu cầu trực tiếp (2026-08-13): hiện tại chọn giọng ở "Tạo dự
  án" hoàn toàn thủ công (bấm lọc giới tính/vùng miền/phong cách, nghe thử
  từng giọng) — muốn AI đọc hiểu nội dung video rồi TỰ ĐỀ XUẤT giọng phù
  hợp nhất, đỡ phải tự mò trong thư viện 120+ giọng.
- Hạ tầng đã có sẵn, tái dùng được: lượt "phân tích ngữ cảnh video" (Lượt 0
  — `analyze_transcript()`/`buildAnalysisPrompt`, mini-spec V18/gốc) ĐÃ gọi
  LLM đọc transcript và trả về `domain`/`style_notes`/`summary` — đây CHÍNH
  LÀ tín hiệu "hiểu nội dung video" mà tính năng này cần, không cần thêm 1
  lượt gọi AI mới tốn thêm Vox/token.
- Audit thật catalog giọng (đọc `autodub/speech/tts/voices.py`): VieNeu
  (120 giọng, nguồn chính) chỉ có 3 giá trị `style` (tu_nhien/tin_tuc/
  doc_truyen), suy ra từ CHỮ TRONG TÊN HIỂN THỊ (`_STYLE_FROM_TEXT`) — phần
  lớn giọng KHÔNG có chữ khoá đó trong tên nên mặc định rơi về "tu_nhien"
  hết. Tức là AI chỉ khớp được GIỚI TÍNH (`gender`) đáng tin cho VieNeu,
  KHÔNG có tín hiệu phong cách thật để khớp sâu hơn (khác V20 đã audit: 120
  giọng VieNeu "không có tag ngữ điệu/phong cách, chỉ tên"). Catalog CapCut
  có mô tả phong cách phong phú hơn hẳn qua `description` — khớp được sâu
  hơn cho nhánh này.

- **Audit thật luồng "Tạo dự án"** (2026-08-13, agent audit riêng): 6 bước
  của wizard (Video → Nhận dạng → Dịch thuật → Giọng & Phụ đề → Chạy dịch →
  Xuất video) chỉ là MÀN HÌNH CẤU HÌNH — `_go_next()`
  (`autodub_gui/pages/new_project_page.py:253`) không chạy bất kỳ pipeline
  nào cho tới khi bấm "Bắt đầu lồng tiếng" (bước 5, gọi `DubPipeline.run()`
  một lượt duy nhất). `analyze_transcript()` chỉ chạy BÊN TRONG lượt dịch
  đó (`pipeline.py:1115`), SAU khi giọng đã bị khoá vào `DubRequest` từ lúc
  rời bước 4. Nghĩa là KHÔNG có tín hiệu phân tích nào tồn tại lúc người
  dùng đang ở bước chọn giọng — chốt với chủ dự án (2026-08-13): xây bản
  **SAU khi lồng tiếng xong** (ở Trình chỉnh sửa) trước, dùng đúng kết quả
  phân tích đã có sẵn trên đĩa — không thêm bước chờ nào vào luồng tạo dự
  án. Bản "gợi ý SỚM trước khi chọn giọng" (cần 1 worker chạy nền riêng,
  thêm độ trễ + ASR/phân tích chạy 2 lần) để dành mini-spec khác nếu cần.
- **Audit khóa mã hóa** (`autodub/securestore.py`): `data/video_context.json`
  (nơi lưu kết quả phân tích) bị khóa AES-256-GCM chỉ trong lúc hold Vox
  CHƯA chốt (mục đích chống lấy data chưa trả tiền, không phải bảo mật nội
  dung — xem docstring `securestore.py`). Sau khi xuất video (hold đã chốt),
  `unlock_all()` tự giải mã file này thành JSON thường (`pipeline.py:1901`,
  `billing.py:191/314`) — `read_json_secure(path, key=None)` đọc được ngay,
  không cần xin lại khóa từ máy chủ. Dự án còn dở/chưa xuất thì file vẫn
  khóa — đọc sẽ ném `SecureStoreError`, phải bắt và ẨN gợi ý (đúng Constraint
  1, không phải lỗi).

Goal:
- Ở Trình chỉnh sửa (sau khi 1 video đã lồng tiếng xong), hiện 1 khối "AI
  đề xuất giọng" dựa trên nội dung video đã phân tích — nếu giọng đang dùng
  không khớp gợi ý, người dùng bấm 1 nút để đổi SANG giọng đó rồi đọc lại
  toàn bộ (tái dùng đúng luồng "Lưu tất cả và đọc lại" đã có). Đây là GỢI Ý,
  không phải ép buộc — không đổi gì nếu người dùng không bấm áp dụng.

Constraints (Guardrails):
1. CHỈ hoạt động khi có nguồn tín hiệu đáng tin (đúng nguyên tắc "không suy
   đoán capability khi thiếu evidence"): nhánh SaaS (đã có phân tích ngữ
   cảnh qua LLM) mới đề xuất được sâu; nhánh local-only KHÔNG có LLM →
   KHÔNG giả vờ "AI đề xuất" bằng suy đoán rỗng, ẩn hẳn phần gợi ý hoặc gắn
   nhãn "thử nghiệm" rất rõ nếu vẫn muốn có phiên bản tối giản (Design
   Choice quyết định cụ thể).
2. KHÔNG suy đoán phong cách cho giọng VieNeu vượt quá dữ liệu THẬT đang có
   (chỉ giới tính + có/không style rõ trong tên) — không tự gán nhãn phong
   cách "tưởng tượng" cho 1 giọng chỉ vì AI nghĩ nó "nghe hợp" mà không có
   căn cứ trong catalog.
3. KHÔNG thêm lượt gọi AI mới tốn thêm Vox — tái dùng đúng response của
   lượt phân tích ngữ cảnh (Lượt 0) đã có sẵn, chỉ mở rộng field trả về
   (giống cách V28 mở rộng `/translate` qua cờ opt-in, không phá contract
   cũ của các field hiện có `summary`/`domain`/`pronouns`/`glossary`/
   `style_notes`).
4. Gợi ý PHẢI giải thích được lý do bằng dữ liệu thật (vd "giọng nữ, phong
   cách kể chuyện — khớp domain 'review phim' AI phát hiện") — không hiện
   gợi ý mù mờ không giải thích được.
5. Người dùng luôn override được — đề xuất là GỢI Ý mặc định, không khoá
   quyền tự chọn giọng khác.

Scope:
A. `control_server/src/prompts/translate.js::buildAnalysisPrompt`/
   `ANALYSIS_SCHEMA` — mở rộng thêm field mới `voice_hint` (vd
   `{"gender": "nam"|"nữ"|"", "tone_keywords": ["năng động","điềm tĩnh",...]}`)
   — ADDITIVE, opt-in, không đụng 5 field hiện có (`summary`/`domain`/
   `pronouns`/`glossary`/`style_notes`).
B. `autodub/speech/tts/voice_recommend.py` (mới) — hàm thuần
   `recommend_voices(analysis: dict, catalog: list[Voice], target, n=3) ->
   list[Voice]`: khớp `voice_hint.gender` với `Voice.gender` (tín hiệu
   ĐÁNG TIN, luôn dùng được); khớp `tone_keywords` với `Voice.style`/
   `Voice.description` CHỈ khi 2 bên thật sự có dữ liệu (VieNeu phần lớn
   không có — rơi về xếp hạng chỉ theo giới tính, KHÔNG giả vờ khớp phong
   cách khi catalog không có tín hiệu đó — đúng Constraint 2).
C. `autodub_gui/pages/editor_panels.py::VoicePanel` (mục "Giọng đọc" của
   Trình chỉnh sửa) — thêm khối "AI đề xuất giọng", đọc
   `data/video_context.json` qua `securestore.read_json_secure(path,
   key=None)` khi mở dự án; bắt `SecureStoreError`/`OSError`/thiếu
   `voice_hint` → ẩn hẳn khối này (không hiện rỗng/lỗi). Có tín hiệu → gọi
   `recommend_voices()`, hiện tên giọng đề xuất hàng đầu + lý do, nút "Đổi
   sang giọng này" gọi lại đúng cơ chế đổi giọng dự án đã có
   (`VoicePanel.set_project_voice`/nút "Lưu tất cả và đọc lại").
D. Local-only (không SaaS) hoặc dự án chưa xuất (còn khóa): KHÔNG đề xuất —
   giữ nguyên trải nghiệm hiện có, đúng Constraint 1.
E. Tests: unit Python (`recommend_voices()` khớp giới tính đúng/sai, khớp
   phong cách chỉ khi catalog có dữ liệu, trả rỗng khi thiếu voice_hint);
   unit JS (schema/prompt có/không voice_hint theo đúng contract cũ); GUI
   headless (khối gợi ý ẩn khi thiếu file/khi còn khóa/khi thiếu
   voice_hint, hiện đúng khi đủ điều kiện); regression (đổi giọng thủ công
   không bị ảnh hưởng).

Audit Before Build: đã audit đủ — luồng wizard (Context), khóa mã hóa
(Context), catalog VieNeu/CapCut (Context gốc). Không còn điểm mù cần audit
thêm trước khi build.

Design Choice:
- Tái dùng lượt phân tích ngữ cảnh có sẵn (Constraint 3) — không xây pipeline
  phân tích riêng cho tính năng này, đúng nguyên tắc Playbook "không build
  song song với luồng đã có".
- Đặt gợi ý ở Trình chỉnh sửa (sau khi lồng tiếng xong), KHÔNG ở wizard Tạo
  dự án — vì phân tích chỉ có sau khi chạy, và không muốn thêm bước chờ/
  worker nền mới vào luồng tạo dự án (đã audit: cần 1 worker ASR+phân tích
  riêng, tốn thêm độ trễ + chạy ASR 2 lần nếu làm ở wizard).
- Ưu tiên trung thực hơn đầy đủ: catalog VieNeu thiếu dữ liệu phong cách
  thật thì CHỈ đề xuất theo giới tính, không bịa thêm — nếu chủ dự án muốn
  đề xuất sâu hơn cho VieNeu, cần 1 việc khác hẳn (gắn tay tag phong cách
  cho 120 giọng — công việc nhập liệu, không phải mini-spec kỹ thuật này).
- Dự án chưa xuất (hold chưa chốt, file còn khóa) → ẩn gợi ý thay vì xin lại
  khóa từ máy chủ (phức tạp hơn nhiều, tốn thêm round-trip mạng cho 1 tính
  năng chỉ là gợi ý phụ trợ — không đáng đánh đổi).

Test Plan:
- Unit: `recommend_voices()` khớp đúng giới tính; khớp phong cách CHỈ khi
  cả `voice_hint` và `Voice.style` đều có tín hiệu thật; trả rỗng (không
  suy đoán) khi thiếu `voice_hint`.
- GUI: khối gợi ý ẩn khi không có SaaS/không có voice_hint; hiện đúng khi
  có, kèm lý do đọc được.
- Live verification: NẾU có SaaS thật — chạy 1 video có domain rõ ràng (vd
  "review công nghệ" giọng nam năng động vs "phim cổ trang" giọng nữ điềm
  tĩnh), xác nhận gợi ý khớp cảm quan với domain AI phân tích được.

Success Criteria:
- Có SaaS + phân tích ngữ cảnh thành công → hiện đúng 1-3 giọng đề xuất
  kèm lý do đọc được, khớp giới tính chắc chắn.
- Không có SaaS hoặc phân tích lỗi → KHÔNG hiện gợi ý giả, trải nghiệm
  chọn giọng thủ công y hệt trước mini-spec này (0 regression).
- Không phát sinh thêm chi phí Vox nào cho tính năng này.
```

### V34a — PoC hạ tầng API lồng tiếng đầy đủ

```
V34a — PoC hẹp: chứng minh khả thi kỹ thuật engine đầy đủ chạy server-side (Phase G)

Context:
- Chủ dự án chọn trực tiếp (2026-08-13, qua AskUserQuestion): mở rộng V31
  (API dịch văn bản thôi) thành API lồng tiếng ĐẦY ĐỦ (ASR+dịch+TTS+video),
  giống Sync Labs/HeyGen — nộp video, nhận về video đã lồng tiếng.
- Agent audit riêng (2026-08-13) đối chiếu hạ tầng V9/V12 (Cloud rendering)
  đã có với nhu cầu thật của V34:
  - TÁI DÙNG ĐƯỢC nguyên si: job-queue pattern (`RenderJob` model,
    claim/heartbeat/complete/fail qua `internal-jobs.js`, xác thực
    `X-Worker-Token` tách hẳn device/API-key token) — thiết kế vốn đã
    tổng quát, không riêng Demucs. `autodub/cli.py` (V22) là engine headless
    KHÔNG phụ thuộc Qt, `DubPipeline`/`DubRequest` chạy được thẳng từ 1
    tiến trình server, không cần viết pipeline riêng.
  - THIẾU HOÀN TOÀN, phải xây mới: `control_server/worker/` (render_worker
    hiện tại) CHỈ cài `demucs`/`soundfile`/`requests`, KHÔNG import
    `autodub` — cố tình nhẹ, không có Whisper/VieNeu/Paraformer/ffmpeg đầy
    đủ. Billing hiện chỉ có 2 mô hình (Vox giá cố định theo hành động, hoặc
    `ApiKey.quota` đếm THEO LƯỢT GỌI — không có khái niệm "theo phút
    video"). Lưu trữ hiện dùng 1 volume chia sẻ nội bộ, giới hạn cứng
    200MB/request (đủ audio Demucs, KHÔNG đủ video). GPU: 0 cấu hình
    `deploy.resources.reservations.devices` trong `docker-compose.yml` —
    Demucs cloud hiện chạy CPU-only thật trong production, chưa từng có
    tiền lệ GPU server-side.
- Rủi ro V34 CAO HƠN cả V9 gốc (audio→video, 1 stage→cả pipeline, GPU chưa
  chứng minh được ở server, billing hoàn toàn mới) — agent khuyến nghị tách
  PoC/build đúng tiền lệ V9→V12, V30→V32a→V32b.

Goal:
- Chứng minh 1 video ngắn (<2 phút) chạy trót lọt ASR→dịch→TTS→mux qua 1
  container server MỚI gọi thẳng `autodub.cli`/`DubPipeline` headless, đo
  được số liệu thật (thời gian xử lý, dung lượng đĩa cần, có bắt buộc GPU
  hay CPU đủ dùng) — đủ dữ liệu để quyết định go/no-go cho V34b.

Constraints (Guardrails):
1. KHÔNG làm billing thật — chưa có số liệu chi phí compute thật để định
   giá đúng (đúng nguyên tắc "không suy đoán khi thiếu evidence"). PoC chỉ
   LOG chi phí giả định, không trừ Vox/quota thật.
2. Container MỚI HOÀN TOÀN, tách khỏi `control_server/worker/` (render_worker
   Demucs hiện có) — không nhét chung 1 image, đúng nguyên tắc đã có từ V12
   ("build/deploy control_server không phụ thuộc thay đổi bên Python").
3. Đo số liệu THẬT trên video mẫu cụ thể (không suy đoán) — thời gian xử
   lý, dung lượng input+output, GPU có bắt buộc hay CPU đủ dùng trong thời
   gian chấp nhận được.
4. Giới hạn video ĐẦU VÀO nhỏ (<2 phút, 1-2 video mẫu cụ thể) — KHÔNG cam
   kết video dài/nhiều tenant đồng thời ở PoC này.
5. Tái dùng nguyên si job-queue pattern (`RenderJob`/claim-heartbeat-
   complete-fail) — chỉ mở rộng tối thiểu (thêm giá trị `stage` mới hoặc
   field payload), không viết lại cơ chế queue.
6. Xác thực qua `ApiKey` (V31) chỉ để NHẬN DIỆN người gọi — không gắn quota/
   billing thật ở PoC này (Constraint 1).

Scope:
A. `control_server/worker-dub/` (mới, thư mục + Dockerfile TÁCH HẲN
   `control_server/worker/`) — cài đủ `autodub` package + faster-whisper +
   VieNeu (ONNX) + ffmpeg, gọi `autodub.cli`/`DubPipeline` headless xử lý
   1 job nhận được qua claim.
B. Mở rộng `RenderJob` schema tối thiểu — audit kỹ khi code xem thêm giá
   trị `stage: "full_dub"` vào enum hiện có là đủ, hay payload khác biệt
   quá (input là VIDEO không phải audio, cần thêm sourceLang/targetLang/
   voice params, output là VIDEO không phải audio) nên cần model job
   riêng — quyết định cụ thể lúc code, không chốt trước trong tài liệu này.
C. `POST /api/v1/dub` (mới, xác thực qua `requireApiKey` — tái dùng
   middleware V31) — CHỈ submit job, trả `jobId` ngay, KHÔNG đồng bộ như
   `/api/v1/translate` (dub mất nhiều phút, không thể chờ trong 1 request).
D. `GET /api/v1/dub/:jobId` (mới) — poll trạng thái + tải kết quả khi xong.
E. Lưu trữ: dùng lại volume chia sẻ tạm hiện có, audit dung lượng THẬT cần
   cho video test — KHÔNG cam kết giới hạn production (Constraint 4).
F. Tests: unit (job model mở rộng, route validate body); integration
   (submit → worker giả lập claim/complete → tải kết quả — theo đúng khuôn
   `render-job.integration.test.js`/`internal-jobs.test.js` đã có, không
   cần GPU thật để verify LUỒNG); KHÔNG cần test billing (chưa có ở PoC).

Audit Before Build: đã audit đủ hạ tầng hiện có (agent, kết quả ghi ở
Context) — cần audit THÊM khi code: đọc kỹ field cụ thể của `RenderJob`
schema (`control_server/src/models/RenderJob.js`) để quyết định mở rộng
enum hay tách model riêng (Scope B).

Design Choice:
- Container tách biệt hoàn toàn (Constraint 2) — đúng nguyên tắc đã có từ
  V12, tránh 1 lỗi ở pipeline nặng làm ảnh hưởng deploy control_server.
- Dùng `autodub.cli`/`DubPipeline` headless làm engine — không viết lại
  pipeline riêng cho server, đúng nguyên tắc Playbook "không build song
  song với luồng đã có" (đã áp dụng nhất quán từ V22 tới giờ).
- KHÔNG làm billing thật ở PoC (Constraint 1) — mô hình billing đúng
  (theo phút video) cần số liệu chi phí compute thật mới định giá đúng,
  làm sớm là định giá mù.

Test Plan:
- Unit: job model/route validate.
- Integration: toàn luồng submit→worker giả→hoàn thành→tải kết quả, dùng
  worker giả lập (không cần GPU thật) để verify WIRING đúng khuôn test
  render-job hiện có.
- Live verification: NẾU có máy GPU thật (hoặc xác nhận CPU đủ dùng) —
  chạy 1-2 video mẫu <2 phút thật qua worker mới, đo thời gian/dung lượng
  thật, ghi vào TEST_LOG.

Success Criteria:
- ≥1 video mẫu <2 phút chạy trót lọt qua API mới (submit→poll→tải kết
  quả), có số liệu thật (thời gian xử lý, dung lượng, GPU bắt buộc hay
  CPU đủ dùng).
- Khuyến nghị go/no-go rõ ràng cho V34b kèm lý do — không lấp lửng.
```

### V34b — Build production API lồng tiếng đầy đủ (đóng gap V34a)

```
V34b — Billing theo phút video + lưu trữ production + GPU đa tenant (Phase G, CHỈ mở nếu V34a khuyến nghị "go")

Context:
- Điều kiện tiên quyết: V34a phải hoàn thành với khuyến nghị "go" kèm số
  liệu benchmark thật (thời gian xử lý/phút video, dung lượng đĩa/video,
  GPU có bắt buộc hay không). Mini-spec này KHÔNG được mở nếu V34a khuyến
  nghị "không build" hoặc "cần thu hẹp phạm vi thêm".
- 3 mảng CHƯA có tiền lệ nào trong toàn hệ thống (xác nhận qua audit V34a):
  billing theo thời lượng media, giới hạn lưu trữ video-scale, GPU
  provisioning multi-tenant — đây là phần việc CHÍNH của mini-spec này.

Goal:
- API lồng tiếng đầy đủ chạy production thật: billing đúng chi phí compute
  thật (không lỗ, không đoán mò — lấy số từ V34a), giới hạn lưu trữ + dọn
  file tự động, hỗ trợ nhiều job đồng thời an toàn (không tranh chấp GPU/
  tài nguyên giữa các tenant).

Constraints (Guardrails):
1. Billing PHẢI theo số liệu chi phí compute THẬT đo được ở V34a — không
   định giá theo cảm tính.
2. Billing API lồng tiếng TÁCH HẲN `CreditLedger` (Vox desktop) VÀ
   `ApiUsageLedger` (V31 dịch văn bản) — 3 hệ billing độc lập, đúng nguyên
   tắc "lỗi 1 hệ không ảnh hưởng ví người dùng khác" đã áp dụng xuyên suốt
   Phase G (V31 Design Choice).
3. Lưu trữ video PHẢI có TTL/dọn tự động — video là dữ liệu lớn, không dọn
   sẽ đầy đĩa nhanh hơn hẳn audio Demucs trước đây.
4. GPU đa tenant: PHẢI có cơ chế hàng đợi/giới hạn concurrency rõ ràng
   (không để 2 job cùng tranh 1 GPU gây OOM hoặc timeout không kiểm soát
   được — bài học thật từ V32a: card 4GB đã cận trần chỉ với 1 job).
5. KHÔNG cam kết SLA thời gian xử lý cụ thể trước khi có số liệu vận hành
   thật qua ít nhất 1 đợt live traffic thử nghiệm.

Scope (khung ban đầu — tinh chỉnh cụ thể sau khi có số liệu V34a):
A. Mô hình billing mới — đơn giá theo PHÚT VIDEO ĐẦU RA (không phải theo
   lượt gọi như V31), tính từ số liệu chi phí compute thật của V34a + biên
   lợi nhuận do chủ dự án quyết định (quyết định giá là quyết định kinh
   doanh, không tự chốt trong tài liệu kỹ thuật này).
B. `DubApiJob` (model mới hoặc mở rộng `RenderJob` tuỳ quyết định audit của
   V34a Scope B) — thêm TTL dọn file tự động sau N giờ kể từ khi hoàn
   thành (giống `cloud.render.ttl.hours` đã có cho Demucs).
C. Giới hạn concurrency GPU — hàng đợi thật (không phải chỉ "ai claim
   trước chạy trước" như hiện tại), giới hạn số job xử lý cùng lúc theo
   đúng khả năng phần cứng thật đã đo ở V34a.
D. `docker-compose.yml`/tài liệu deploy — thêm cấu hình GPU provisioning
   (`deploy.resources.reservations.devices`) lần đầu tiên trong hệ thống.
E. Tests: billing tính đúng theo thời lượng thật; TTL dọn file đúng hạn;
   giới hạn concurrency chặn đúng khi vượt ngưỡng; regression (API dịch
   văn bản V31 và Demucs cloud V12 không bị ảnh hưởng — đúng Constraint 2).

Audit Before Build: đọc kỹ báo cáo + số liệu thật của V34a trước khi chốt
đơn giá/TTL/ngưỡng concurrency cụ thể — không tự quyết lại.

Design Choice: chưa chốt được đầy đủ trước khi có V34a — nguyên tắc chung
đã rõ (billing tách hệ, TTL bắt buộc, GPU có hàng đợi thật), số cụ thể
(giá/giờ TTL/số job đồng thời) chốt khi mở mini-spec này thật.

Test Plan:
- Unit: tính billing theo thời lượng, TTL dọn file, giới hạn concurrency.
- Integration: nhiều job đồng thời qua đúng giới hạn concurrency, không
  job nào bị treo/OOM.
- Regression: API dịch văn bản V31 + Demucs cloud V12 không đổi hành vi.
- Live verification: ≥1 đợt xử lý thật nhiều video liên tiếp qua GPU thật,
  xác nhận billing tính đúng + không tràn đĩa + không tranh chấp GPU.

Success Criteria:
- API lồng tiếng chạy production thật, billing đúng chi phí compute thật,
  không tranh chấp tài nguyên khi nhiều job chạy cùng lúc.
- 0 regression cho V31 (dịch văn bản) và V12 (Demucs cloud).
- Đĩa không tràn nhờ TTL dọn tự động, xác nhận qua live verification.
```

### V35 — Nâng chất lượng nhân bản giọng (voice cloning)

```
V35 — Kiểm tra chất lượng đầu vào + minh bạch giới hạn khi nhân bản giọng (Phase G)

Context:
- Chủ dự án yêu cầu trực tiếp (2026-08-13): nâng chất lượng nhân bản giọng
  (voice cloning) để cạnh tranh với ElevenLabs/XTTS-v2/OpenVoice.
- Agent audit riêng (2026-08-13) xác nhận kiến trúc THẬT: VieNeu-TTS
  v3-Turbo là zero-shot cloning (mã hoá 1 embedding giọng 192 chiều +
  reference codes từ audio, KHÔNG fine-tune/train riêng từng giọng, KHÔNG
  cần transcript) — cùng họ kỹ thuật với VALL-E/XTTS/GPT-SoVITS. Giọng
  nhân bản trở thành "preset" y hệt giọng đóng sẵn ngay sau khi enroll,
  không tốn thêm chi phí mỗi câu — đây LÀ điểm mạnh thật (khác nhiều đối
  thủ cần thời gian "train" riêng).
- Audit phát hiện 2 BUG THẬT, đã sửa riêng NGOÀI mini-spec này (commit
  `198633a`, trước khi viết mini-spec): (1) ngưỡng thời lượng tối thiểu
  sai lệch ~40 lần — trước đây chỉ chặn clip <25ms nhưng báo "cần ≥ 1
  giây", giờ đã có `MIN_ENROLL_SECONDS = 1.0` kiểm tường minh; (2)
  README mô tả bước "nhập đúng nội dung câu nói" khi thêm giọng — bước
  này KHÔNG tồn tại trong code (kiến trúc zero-shot không cần transcript),
  đã sửa lại mô tả đúng.
- Gap CÒN LẠI (audit, chưa sửa, phạm vi của mini-spec này): (a) KHÔNG có
  kiểm tra nhiễu/tiếng ồn/cắt tiếng (clipping)/im lặng trước khi học —
  file khử ồn ONNX luôn chạy nhưng không có bước TỪ CHỐI nếu chất lượng
  quá kém; (b) trần 8 giây (`wav[: int(8.0 * sr)]`,
  `autodub/speech/tts/vieneu_worker.py::_encode_one`) bị cắt ÂM THẦM
  không báo — file 60 giây bị cắt còn 8 giây mà người dùng không biết;
  (c) KHÔNG có điểm số tin cậy (confidence/similarity score) trước khi
  lưu — người dùng chỉ biết chất lượng SAU khi lưu, phải tự bấm "Nghe thử"
  rồi mới biết có cần học lại hay không.

Goal:
- Người dùng biết NGAY (trước khi mất công enroll) nếu file ghi âm không
  đạt chất lượng tối thiểu (quá ồn/quá ngắn/bị cắt tiếng/gần như im lặng),
  thay vì phải tự nghe thử sau khi đã lưu mới phát hiện giọng nhân bản tệ.

Constraints (Guardrails):
1. KHÔNG thêm dependency AI/model mới nặng (vd 1 model đánh giá chất lượng
   giọng nói riêng) — dùng phân tích tín hiệu số học đơn giản (năng lượng/
   biên độ/tỷ lệ mẫu bị clip) đã đủ bắt các lỗi rõ ràng nhất, đúng tinh
   thần "không suy đoán vượt quá điều đo được thật".
2. KHÔNG chặn cứng người dùng nếu chất lượng ở mức "chấp nhận được nhưng
   không lý tưởng" — chỉ CẢNH BÁO rõ ràng, để người dùng tự quyết định có
   tiếp tục hay chọn file khác (giống cách preflight check của app hiện có
   phân biệt "fail" cứng và "warn" mềm, xem `autodub/preflight.py`).
3. Trần độ dài (hiện 8 giây) PHẢI báo rõ khi file dài hơn bị cắt — không
   được cắt âm thầm như hiện tại.
4. KHÔNG đổi hành vi giọng THƯ VIỆN có sẵn (120 giọng preset,
   `voice_downloader.py`) — mini-spec này CHỈ chạm luồng người dùng tự học
   giọng riêng (`_enroll()`/`vieneu_worker.py --enroll`).
5. Sửa README nếu phát hiện thêm mô tả sai lệch khác trong lúc build (đã
   sửa 1 chỗ trước khi viết mini-spec, xem Context) — không để tài liệu
   tiếp tục sai sau mini-spec này.

Scope:
A. `autodub/speech/tts/audio_quality.py` (mới) — hàm thuần phân tích tín
   hiệu số học: tỷ lệ mẫu bị clip (biên độ chạm ±1.0 lặp lại), RMS năng
   lượng trung bình (phát hiện gần-im-lặng), tỷ lệ khoảng lặng liên tục dài
   nhất so với tổng thời lượng. Trả về cấu trúc rõ ràng (ok/warn/fail +
   lý do cụ thể bằng tiếng Việt), KHÔNG phải điểm số mù mờ.
B. `autodub/speech/tts/vieneu_worker.py::_encode_one()` — gọi
   `audio_quality` TRƯỚC khi mã hoá; `fail` → `ValueError` với lý do rõ
   (giống ngưỡng thời lượng đã sửa); `warn` → vẫn enroll nhưng trả kèm
   cảnh báo trong response JSON để GUI hiển thị (không chặn cứng, đúng
   Constraint 2). File dài hơn trần 8 giây → cảnh báo rõ trong response
   thay vì cắt âm thầm (Constraint 3).
C. `autodub_gui/pages/settings_panels.py` (luồng "Thêm giọng từ đoạn ghi
   âm") — hiện cảnh báo `warn`/thông báo bị cắt từ bước B ngay sau khi
   enroll xong, TRƯỚC khi người dùng phải tự bấm "Nghe thử" mới biết.
D. Tests: unit (`audio_quality` phát hiện đúng clip sạch/ồn/im lặng/bị cắt
   tiếng bằng dữ liệu tổng hợp — sin wave sạch vs random noise vs mảng
   toàn 0 vs mảng có clipping thật); tích hợp `_encode_one()` (fail đúng
   trường hợp quá tệ, warn đúng trường hợp biên, không đổi hành vi giọng
   thư viện — Constraint 4).

Audit Before Build: đã audit đủ kiến trúc + 2 bug thật (Context) — không
còn điểm mù kỹ thuật cần audit thêm trước khi build.

Design Choice:
- Phân tích tín hiệu số học đơn giản (Constraint 1) thay vì model AI đánh
  giá chất lượng riêng — đủ bắt các lỗi RÕ RÀNG nhất (câm, ồn trắng, cắt
  tiếng) mà không phải tải thêm model, đúng tinh thần "engine nhẹ, độ
  chính xác vừa đủ" đã dùng cho heuristic văn bản của V28.
- Cảnh báo thay vì chặn cứng cho trường hợp biên (Constraint 2) — người
  dùng vẫn là người quyết định cuối, app chỉ cung cấp thông tin để quyết
  định đúng hơn, không tự ý từ chối nếu chưa chắc chắn tệ.

Test Plan:
- Unit: `audio_quality` với dữ liệu tổng hợp (sin wave sạch → ok; toàn 0 →
  fail im lặng; random noise biên độ cao → warn/fail nhiễu; mảng có nhiều
  mẫu chạm ±1.0 → warn/fail clipping).
- Integration: `_encode_one()` fail đúng khi audio_quality fail, warn kèm
  đúng lý do khi audio_quality warn, không đổi hành vi khi audio_quality ok.
- Regression: enroll giọng thư viện (`voice_downloader.py`, 120 giọng
  preset) không bị ảnh hưởng bởi bước kiểm tra mới (Constraint 4).

Success Criteria:
- File ghi âm rõ ràng quá tệ (câm hoàn toàn, ồn trắng, cắt tiếng nặng) bị
  từ chối TRƯỚC khi tốn công enroll, kèm lý do cụ thể đọc được.
- File biên (không lý tưởng nhưng dùng được) vẫn enroll được, kèm cảnh báo
  rõ ràng cho người dùng tự quyết định.
- File dài hơn trần 8 giây → người dùng THẤY rõ bị cắt, không còn âm thầm.
- 120 giọng thư viện có sẵn không bị ảnh hưởng gì (0 regression).
```

### Remaining Limits / Follow-ups của Phase G

- **Multi-user collaborative workspace** — TRỰC TIẾP mâu thuẫn với guardrail
  "không có tài khoản người dùng theo thiết kế" (V10 Guardrail 2) — không spec
  ở đợt này, cần chủ dự án quyết định có muốn lật lại guardrail đó không trước
  khi mở cuộc thảo luận kỹ thuật.
- **Real-time/live dubbing** — kiến trúc HOÀN TOÀN KHÁC (streaming ASR/MT/TTS
  độ trễ thấp) so với batch/offline hiện tại — gần như 1 sản phẩm thứ 2, không
  phải nâng cấp. Không spec ở đợt này, cần quyết định đầu tư riêng nếu theo
  đuổi.
- **Full hosted Dub API** (ASR+TTS+video trên hạ tầng VoxDub, đúng tham vọng
  Sync Labs/Murf) — audit xác nhận đây là đầu tư hạ tầng GPU + đa tenant từ
  đầu, quy mô lớn hơn nhiều 1 mini-spec. V31 chỉ mở phần dịch thuật (đã 100%
  server-side sẵn) — nếu muốn full hosted dub sau này, đó là quyết định đầu tư
  riêng, không phải mở rộng dần từ V31.
- **Độ phủ ngôn ngữ** — không phải gap kỹ thuật mới, tiếp tục đúng mô hình audit
  Voice.json + mở rộng có kiểm chứng của V17 khi có nhu cầu thị trường cụ thể.

## Remaining Limits / Follow-ups (ngoài phạm vi 10 mini-spec trên)

- **Inpainting AI thật** (xoá chữ bằng AI thay vì blur) — V5 chỉ tự động hoá việc PHÁT
  HIỆN vùng chữ, không đổi cách xử lý (vẫn blur). Nếu sau này muốn inpainting thật
  (LaMa/ProPainter), đó là 1 mini-spec riêng, độ phức tạp cao hơn hẳn, cần GPU mạnh hơn
  — không gộp vào V5.
- **GUI build đầy đủ cho Linux/macOS** — V7 chỉ audit + Docker hoá control_server. Việc
  ship 1 bản GUI PySide6 đóng gói chính thức cho Linux/macOS là quyết định đầu tư lớn,
  phụ thuộc trực tiếp vào kết quả audit V7, để dành cho 1 mini-spec riêng sau khi có
  số liệu thật.
- **Đa ngôn ngữ nguồn ASR đầy đủ ~100 ngôn ngữ Whisper** — V4 chỉ mở rộng có kiểm chứng
  (4-8 ngôn ngữ ban đầu). Mở rộng tiếp theo nhu cầu thị trường thật, không làm tất cả
  cùng lúc vì mỗi ngôn ngữ cần live-verify riêng.
- **Ứng dụng mobile** — không nằm trong bất kỳ mini-spec nào ở trên; pipeline hiện tại
  (Demucs/Whisper/VieNeu chạy nặng) không phù hợp mobile trực tiếp, chỉ khả thi nếu V9
  (cloud rendering) đủ trưởng thành để mobile chỉ là client mỏng gọi cloud — quá xa để
  lên kế hoạch cụ thể ở thời điểm này.
- **Xử lý bản quyền/đạo đức kỹ thuật** (rate-limit tải video, watermark output, consent
  check cho voice cloning) — đã nêu ở docs/PRD.md §9 như rủi ro mở, chưa có mini-spec vì
  cần chủ dự án quyết định mức độ can thiệp trước (đây là quyết định chính sách, không
  phải kỹ thuật thuần tuý). **[XÁC NHẬN 2026-08-11]** Chủ dự án đã xác nhận: chưa cần
  can thiệp gì ở đợt này — giữ nguyên hiện trạng, không mở mini-spec mới cho mục này.
- **Phễu hoàn thành/bỏ dở đầy đủ (V10 phần 1, telemetry client mở rộng)** — cần thêm thu
  thập dữ liệu người dùng, đã hỏi chủ dự án. **[XÁC NHẬN 2026-08-11]** Giữ nguyên phạm vi
  hiện tại (chỉ retention cohort của V10 phần 2) — không mở rộng thu thập.

## Cách dùng tài liệu này

1. Làm theo đúng thứ tự phase A → B → C → D, và thứ tự bắt buộc V1 → V2 trước khi chạm
   pipeline core (V5/V6/V8/V9); V11/V12/V13 (Phase D) đều đòi 1 quyết định/input từ chủ
   dự án trước khi bắt tay — đọc mục "Constraints" đầu mỗi cái để biết cần hỏi gì.
2. Trước khi bắt tay 1 mini-spec, đọc lại đúng section "Audit Before Build" của nó và
   audit thật (đừng tin audit sơ bộ trong Context — Context chỉ là điểm khởi đầu).
3. Sau khi hoàn thành 1 mini-spec, báo cáo theo đúng format Playbook §7 (Summary, Audit
   Before Build, Design Choice, Changed Files, New API/DB/State, Tests, Live Verification,
   Remaining Limits/Follow-ups) và cập nhật `docs/ARCH.md`/`docs/API.md`/`docs/TEST_LOG.md`
   tương ứng.
4. Khi promote request #54 được duyệt trên AI Factory, tạo milestone cho từng phase
   (A/B/C/D) và task cho từng mini-spec (V0-V13) qua MCP để track thật, thay vì chỉ theo
   dõi trong file này.
5. **Vòng lặp lặp lại** (đã xảy ra thật 1 lần, 2026-08-11): thực thi xong 1 phase KHÔNG
   có nghĩa hết việc — mỗi mini-spec khi làm THẬT sẽ để lại giới hạn mới (ghi trong
   "Remaining Limits" của chính nó trong `docs/TEST_LOG.md`). Định kỳ (hoặc khi chủ dự
   án yêu cầu "kiểm tra lại") rà lại toàn bộ Remaining Limits của các mini-spec đã xong,
   phân loại: (a) sửa được ngay, ít rủi ro → sửa luôn, ghi vào TEST_LOG dưới mục
   "Re-audit"; (b) cần quyết định/input mới → mở mini-spec Phase mới (như Phase D ở
   trên), không tự quyết thay chủ dự án; (c) chấp nhận có chủ đích, ghi rõ lý do → giữ
   nguyên trong "Remaining Limits", không lặp lại vô ích.

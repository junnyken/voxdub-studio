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
| V5 | OCR thay boxblur | ⚠️ Một phần, live-verify mở rộng (08-11, Re-audit 08-17) | RapidOCR thật phát hiện đúng watermark trên video H.264 NÉN THẬT (không còn chỉ ảnh PIL) — verify bằng crop trực quan. Re-audit 08-17: thêm nền nhiễu thời gian thật + 3 case chưa test (tiếng Việt có dấu, watermark mờ dần thật, phụ đề cứng burn-in) — cả 3 phát hiện đúng; đo được OCR ~4s/lượt HẰNG SỐ (chỉ quét 3 frame, không phụ thuộc độ dài video); phát hiện 1 false-positive confidence thấp (0.793 vs ≥0.98 thật, chưa đủ dữ liệu để chốt ngưỡng lọc). 2 test mới thành pytest vĩnh viễn (chạy được trong CI vì ffmpeg đã có từ V38, OCR deps vẫn skip trong CI như trước). Còn thiếu: watermark/phụ đề THẬT từ TikTok/Douyin/YouTube thật (rủi ro bản quyền nội dung bên thứ 3, chưa thử) — cần chủ dự án tự cung cấp video thật — xem TEST_LOG |
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
| V32b | Build lip-sync production (Phase G, đóng gap V32a) | 🔶 Code + GUI xong, GIỚI HẠN đúng phạm vi V32a đã benchmark, CHƯA live-verify trên GPU thật | Chủ dự án chọn chấp nhận rủi ro tiền đề (V32a mới 1/3 mẫu, chưa go/no-go chính thức) đổi lấy phạm vi thu hẹp cứng: `lipsync_max_duration_s=12.0`/`lipsync_max_no_face_ratio=0.0` (đúng bằng mẫu benchmark thành công duy nhất). Worker `.venv-lipsync` chuyển thể TRỰC TIẾP từ harness đã live-verify (V32a), không viết lại logic MuseTalk. Consent-check chạy TRƯỚC inference (chặn cứng). Watermark 2 lớp (chữ đè + metadata) luôn áp, không tắt được. CLI `--lipsync` (dub+batch) + ô chọn GUI ở bước "Giọng đọc & phụ đề" (ẩn khi máy chưa đủ điều kiện, đúng pattern `cloud_render`) — Re-audit cùng phiên sau khi unlock môi trường test GUI (cài `ffmpeg`/`libegl1` + `QT_QPA_PLATFORM=offscreen`), verify thật qua smoke test toàn app (exit 0). **CHƯA làm**: billing Vox riêng (Constraint 5 gốc — cần chủ dự án chốt mô hình giá, quyết định kinh doanh), live-verify GPU thật trên đường code production (chỉ harness nghiên cứu đã live-verify — xem TEST_LOG), Editor re-export độc lập chưa nối lip-sync (có chủ đích, cần thiết kế cache riêng). 29 test mới (22 backend mock subprocess + 7 GUI), 0 regression (1123→1152 pass Python, baseline đã bao gồm cả suite GUI sau khi unlock môi trường) — xem TEST_LOG |
| V33 | AI tự đề xuất giọng đọc phù hợp theo nội dung video (Phase G, chủ dự án yêu cầu 2026-08-13) | ✅ Xong (bản "sau khi lồng tiếng xong", đúng chốt Design Choice) | Agent audit xác nhận luồng wizard "Tạo dự án" chỉ cấu hình, không có tín hiệu phân tích lúc chọn giọng — chốt xây bản đề xuất Ở TRÌNH CHỈNH SỬA (sau khi xuất, dùng `video_context.json` đã mở khóa). `voice_hint` additive trong `ANALYSIS_SCHEMA` (chỉ 3 style thật của VieNeu, khớp `VOICE_STYLE_VALUES`) → `autodub/speech/tts/voice_recommend.py::recommend_voices()` (giới tính là bộ lọc cứng, style chỉ dùng 2 giá trị đáng tin tin_tuc/doc_truyen — không suy đoán khi catalog thiếu dữ liệu, đúng Constraint 2) → `autodub/editor.py::suggest_voice()` (hàm thuần, đọc file qua `securestore.read_json_secure(key=None)`, còn khóa/thiếu/hỏng đều trả None chứ không xin lại khóa máy chủ) → khối "AI đề xuất giọng" trong `VoicePanel` (Trình chỉnh sửa), tái dùng đúng luồng đổi giọng thủ công đã có. 4+11+7+5 = 27 test mới, 0 regression (986/992 pass Python, 208/209 pass Node) — xem TEST_LOG |
| V34a | PoC hạ tầng API lồng tiếng đầy đủ (Phase G, đóng gap V31 — mở rộng dịch-thôi thành ASR+dịch+TTS+video) | ✅ Xong — **khuyến nghị GO cho V34b** | `DubApiJob`/`dub-job.service.js` (tách hẳn `RenderJob`) + `/internal/dub-jobs/*` + `/api/v1/dub*` + `control_server/worker-dub/` (Docker image mới, 3 venv Whisper/VieNeu/NLLB cài bằng chính script cài đặt có sẵn). Docker build thật + **2 lượt live-verify thật thành công** trên 1 video mẫu thật (12.2s, giọng nói tiếng Anh thật qua gTTS): 1 lượt bình thường (voice CapCut mặc định), 1 lượt **HOÀN TOÀN OFFLINE** (`--network none`, giọng VieNeu tự học từ file thật trong `voices/preset_voices_vn/`) — cả 2 đều `status: completed`, CPU-only ~3x thời lượng gốc, không cần GPU. 2 bug thật có sẵn trong codebase (không phải do V34a) lộ ra và sửa ngay lúc live-verify: `setup_whisper.py` gửi stdin rỗng cho worker luôn đòi JSON (chặn cài Whisper trên MỌI máy sạch); `saas_client.py` import cứng `autodub_gui` dù `autodub.cli` tự nhận không phụ thuộc GUI. 24+4 = 28 test mới, 0 regression (994/1000 pass Python, 232/233 pass Node) — xem TEST_LOG cho số liệu đầy đủ + Remaining Limits (bg-mode=demucs, video dài, billing thật đều chưa đo) |
| V34b | Build production API lồng tiếng đầy đủ (Phase G, đóng gap V34a) | ✅ Xong | Đo thêm 2 lượt thật (video dài + bg-mode=demucs) trước khi code — xác nhận ~1.6x/~2.6x tỉ lệ compute, CPU-only, sửa nhận định sai "cần GPU" của bản mini-spec gốc thành giới hạn CPU. `ApiKey.dubMinutesQuota/Used` (opt-in, tách hẳn quota V31) + `DubUsageLedger` (sống độc lập TTL sweeper) + billing tính SAU khi job xong theo `durationS` thật đo bởi ASR (không cần ffprobe ở Node). `bg-mode=demucs` giờ là tham số thật của API, `worker-dub` cài demucs vĩnh viễn. 2 bug thật tìm+sửa: admin thiếu route cấp quota cho key cũ (đã thêm `PATCH .../dub-quota`); `pip install demucs` kéo torch CUDA ~2.5GB thừa (đã sửa cài torch CPU-only). Live-verify cuối trên image production thật (9.72GB): cả 2 bg-mode chạy đúng, video hợp lệ. 249 test (233→249), 0 regression (248/249 Node, 1020/1026 Python) — xem TEST_LOG |
| V35 | Nâng chất lượng nhân bản giọng (voice cloning) (Phase G, chủ dự án yêu cầu 2026-08-13) | ✅ Xong | `autodub/speech/tts/audio_quality.py` (mới, hàm thuần không model AI — clip ratio/RMS/khoảng lặng liên tục) nối vào `vieneu_worker.py::_encode_one()`: fail → chặn trước khi mã hóa nặng, warn → vẫn học nhưng gắn cảnh báo tạm thời (không lưu vào file), >8s → báo cắt thay vì âm thầm. Loại trừ CẤU TRÚC (không chỉ ngưỡng số học) cho giọng thư viện qua field `source="library"` có sẵn — Constraint 4 giữ nguyên hành vi 120 giọng preset, xác nhận thêm bằng regression test THẬT (0/120 file fail/warn). GUI (`settings_panels.py`) hiện cảnh báo ngay sau enroll, không đợi "Nghe thử". Bug thật tìm+sửa khi wiring: nạp module qua `importlib` thiếu đăng ký `sys.modules` làm `@dataclass` crash `AttributeError`. 26 test mới, 0 regression (1020/1026 pass Python, 232/233 pass Node) — xem TEST_LOG |
| V36 | Nâng cấp gán giọng theo người nói — round-robin → theo pitch thật (Phase G, chủ dự án yêu cầu 2026-08-14) | ✅ Xong | `autodub/speech/diarization_voice_match.py` (mới, thuần numpy — autocorrelation ước lượng F0/pitch, KHÔNG model AI) + `voice_assign.py::assign_voices_by_gender()` nối vào `pipeline.py::_apply_diarization()`: người nói ước lượng được giới tính (145Hz/175Hz, có khoảng trống cố ý ở giữa cho vùng không chắc) nhận giọng cùng giới tính, người không chắc rơi về round-robin gốc (không đoán liều). Audit lúc code sửa 1 giả định sai trong chính mini-spec (wav không có sẵn như đã viết — thêm `load_wav_mono()` đọc file) + phát hiện bug thật trong test cũ (fixture `_FakeVoice` thiếu `gender`). 18 test mới, 0 regression (1038/1044 pass Python, 248/249 pass Node) — xem TEST_LOG |
| V37 | Nhạc nền + hiệu ứng âm thanh AI theo nội dung video (Phase G, chủ dự án yêu cầu 2026-08-14, làm SAU V36) | ✅ Xong | SaaS-proxy y hệt pattern dịch/phân tích có sẵn: `control_server` giữ key ElevenLabs thật (`ELEVENLABS_API_KEY`, gitignored), route mới `POST /v1/ai/sound-effect`+`/music` trả audio nhị phân qua header billing `X-Credit-Charged`/`X-Balance-After`. Python: `autodub/media/music_match.py` (mới) gọi qua `saas_client.py`, lưu `data/ai_music.wav` (dùng lại nguyên `editor.resolve_existing_background()` qua `bg_mode="ai_music"` mới — KHÔNG viết lại logic mixing/ducking) và `data/sfx_<name>.wav` (chèn bằng ffmpeg overlay điểm-thời-gian riêng, không qua `merge_segments`). Phát hiện điểm nhấn (`emphasis_points.py`, mới) dùng heuristic rẻ có sẵn (dấu câu !/?+khoảng lặng transcript) — **PySceneDetect (Scope B gốc) CHƯA làm, để dành** (xem Remaining Limits). GUI: khối "Nhạc nền & hiệu ứng âm thanh AI" gộp chung mục "Nhạc nền" của Editor — sinh → nghe thử bằng trình phát hệ thống → mới cho áp dụng (Constraint 5), không tự động chèn. Bug thật tìm+sửa khi wiring: `_save_audio_response()` quên gọi `_note_usage()` nên thanh Vox đầu app không tự cập nhật sau khi sinh nhạc/SFX (đã sửa). Live-verify THẬT với key ElevenLabs thật do chủ dự án cấp (2026-08-14): gọi Sound Effects thật, 17.180 byte MP3 trong 1.77s, convert WAV qua ffmpeg đúng 1.0s — chuỗi thật từ đầu tới cuối, không mock. Epidemic Sound Partner API vẫn là track kinh doanh riêng, chủ dự án tự theo dõi tiến độ đàm phán (ngoài phạm vi code). 67 test mới (58 Python, 9 Node), 0 regression (1096/1102 pass Python, 257/258 pass Node) — xem TEST_LOG |

| V38 | CI: cổng test tự động trước phát hành + sửa `UPDATE_REPO` sai (Phase G, phát hiện thật lúc build+deploy V37 2026-08-14) | ✅ Xong | Thêm `.github/workflows/test.yml` (pytest+node test, `ubuntu-latest`, mọi push/PR) tách riêng `release.yml`. Sửa `UPDATE_REPO`/`SUPPORT_URL` sai ở 4 chỗ (`.env.example` ×2, `config.py` field default + `env()` fallback, `README.md`) — sâu hơn phạm vi ban đầu tưởng. Lượt release đầu tiên trong lịch sử repo (`v3.0.0`) FAIL thật lúc build — audit lộ bug có sẵn từ trước (không liên quan V38): `_smoke_report()` bắt buộc `faster_whisper_importable=True` trong khi `autodub.spec` cố ý loại `faster_whisper`/`ctranslate2` khỏi bundle (ASR chạy qua `.venv-whisper` subprocess) — sửa bỏ khỏi tuple `required`. Verify `test.yml` thật lộ thêm 2 bug môi trường CI (thiếu `libEGL`+lib Qt hệ thống, thiếu `ffmpeg`) — cả 2 sửa xong, xác nhận qua chạy lại Actions thật, không suy đoán. Kết quả cuối: cả `test.yml` (`python-tests`+`node-tests`) và `release.yml` đều `success`, sinh ra bản release ĐẦU TIÊN thật có file tải (`VoxDub-Studio-v3.0.1-win64.zip`, 75.2MB, https://github.com/junnyken/voxdub-studio/releases/tag/v3.0.1) — trang Releases trước đó luôn trống. Follow-up 2026-08-15: `voice_downloader.py`'s `VOICES_RELEASE_URL` (404 ở cả 2 repo lúc audit V38) đã publish thật — release `voices-v1.0.0` trên `junnyken/voxdub-studio` kèm `preset_voices_vn.zip` (đóng gói từ 120 file `.wav` thật sẵn có trong repo), xác nhận `HTTP 200` + checksum khớp tuyệt đối, xem TEST_LOG. 0 regression (1096/1102 pass Python, 258/258 pass Node local + xác nhận lại trên CI thật) — xem TEST_LOG |

| V39 | Sửa race condition khiến ngữ cảnh câu trước bị bỏ trống khi dịch song song nhiều lô (Phase G, chủ dự án yêu cầu nâng độ tự nhiên bản dịch 2026-08-15) | ✅ Xong | Audit thật xác nhận 3/4 mảng chủ dự án nêu đã hoàn thiện (khớp thời gian, cảm xúc V28, nhạc nền V37) — chỉ mảng "độ tự nhiên" có bug thật. `translate_segments()` nộp tất cả lô vào `ThreadPoolExecutor` gần như đồng thời, `_prev_context()` tính ngay lúc dựng payload nên gần như luôn thấy bản dịch RỖNG của lô trước. Audit lúc code lộ bug SÂU HƠN: kể cả sửa đúng thời điểm, `_merge()` tạo dict MỚI thay vì mutate — segment gốc không bao giờ được cập nhật bản dịch (có test khoá `_merge()` không được đổi). Sửa: thêm `futures` điền dần + `_run_batch` đợi CÓ TRẦN (8s) lô liền trước qua `futures[i-1].result(timeout=...)`, rồi ghi ngược bản dịch vào đúng dict gốc trong `batch` (không đụng `_merge()`). Bug thứ 2 lộ ra lúc verify: fix làm lộ 1 test dùng chung list `SEGMENTS` mutable giữa nhiều hàm test — sửa cả code (`pop` tone cũ khi lượt này không có) lẫn test (copy segment, đúng convention có sẵn). 3 test mới (`test_translate_prev_context_race.py`), 0 regression (1101/1107 pass Python) — xem TEST_LOG |

| V40 | Sửa 3 bug thật từ audit sâu toàn pipeline (resume-safety + Demucs quality signal + orphaned subprocess) (Phase G, chủ dự án yêu cầu 2026-08-16) | ✅ Xong | Audit 2 agent song song (bug pipeline + khảo sát thị trường) tìm 4 bug thật, chủ dự án chọn sửa 3 (bỏ #4 LOW). **#1 HIGH** resume-safety: `_load_cached_transcript()` (mới, tách từ `_run_impl`) thêm marker `.asr_lang` — đổi "Ngôn ngữ gốc" rồi resume trước đây âm thầm dùng lại transcript SAI ngôn ngữ; `_ensure_render_mode()` (đã có từ trước, mở rộng) thêm dòng 2 lưu giọng đọc đã resolve vào marker `.render_mode` có sẵn — đổi giọng rồi resume trước đây để lại .wav CŨ lẫn với .wav MỚI trong cùng video. Cả 2 đều: marker không tồn tại (dự án tạo trước V40) → coi là khớp, không ép làm lại oan. **#2 MEDIUM** Demucs không có tín hiệu chất lượng: tái dùng NGUYÊN `audio_quality.analyze()` (RMS/khoảng-lặng, đã có từ V35 cho voice cloning) áp lên `vocals.wav` sau khi tách — CHỈ báo qua field mới `background_separation` trong `quality_report.json` (additive, theo đúng pattern `translate_review` của V29), KHÔNG chặn (video không lời thoại là hợp lệ). Đọc WAV bằng `wave` stdlib (không phải `soundfile`) — CI cố tình loại `soundfile` khỏi cài đặt test (V38) để tránh kéo torch. **#3 MEDIUM** tiến trình con mồ côi: `atexit.register(proc.kill)` cho Whisper subprocess (`transcriber.py`) và Demucs GPU worker (đổi `subprocess.run`→`Popen`+`communicate` để có handle đăng ký được, `vocal_separator.py`) — cùng pattern VieNeu worker đã dùng từ trước, đóng app giữa lúc ASR/Demucs chạy giờ có thêm lưới an toàn (không bảo vệ được kill -9/crash cứng). 18 test mới (`test_pipeline_resume_safety.py` mới + bổ sung `test_vocal_separator.py`/`test_transcriber_watchdog.py`), 0 regression (1118/1119 pass Python — 1 fail còn lại là flake phụ thuộc thứ tự test có sẵn từ TRƯỚC V40, xác nhận bằng cách chạy lại full suite trên `main` sạch, xem TEST_LOG) |

| V41 | Nâng chất lượng đọc hiểu nguồn Anh/Trung khi dịch sang tiếng Việt (Phase G, chủ dự án yêu cầu 2026-08-16) | ✅ Xong | Audit xác nhận: KHÔNG phải gap cấu trúc rộng (ranh giới câu Paraformer/Whisper đều dựa VAD tạm dừng âm thanh, không phải cấu trúc chữ — tiếng Trung không thua kém tiếng Anh ở điểm này); ý ngữ/thành ngữ tiếng Anh đã có rule map-theo-nghĩa tốt sẵn. 2 gap thật: **#1** `control_server/src/prompts/translate.js` đã có rule bỏ trợ từ tiếng Trung (啊/呢/嘛/吧) ở MỌI target trừ zh, nhưng KHÔNG có rule tương đương cho từ đệm tiếng Anh nói (um/uh/like/you know...) — thêm rule đối xứng vào 8/10 block (trừ zh giữ nguyên có chủ đích, trừ en vì target=nguồn=tiếng Anh không có nghĩa) + `_genericRules()` fallback. **#2** Model chấm câu CT-Transformer (Paraformer, tiếng Trung) tải lỗi lúc cài chỉ log stderr worker con (GUI không đọc) — degrade vĩnh viễn, không cảnh báo, vi phạm nguyên tắc "degrade trung thực" của CLAUDE.md. Worker (`asr_paraformer_worker.py`) thêm field `punctuation_available` vào message "done"; `paraformer_transcriber.py` đọc lại, cảnh báo rõ qua logger chính khi thiếu (mặc định `True` cho worker cũ chưa gửi field — 0 regression). 5 test mới Python (`test_paraformer_watchdog.py`) + 5 test mới Node (`translate-prompts.test.js`), 0 regression (Python 1120/1121 pass — 1 fail là flake có sẵn từ V40; Node 261/262 pass, 0 fail) |

| V42 | Audit kiến trúc batch song song không người canh (Phase G, chủ dự án yêu cầu 2026-08-16) | ✅ Xong (research + 1 fix nhỏ; KHÔNG build GPU-parallelism) | **Kết luận chính**: chạy song song thật 2 video (2 GPU stage cùng lúc) trên phần cứng thật của dự án (NVIDIA T1200 4GB VRAM, đã xác nhận qua V32a peak 96% cho 1 workload) là **ngõ cụt phần cứng**, không phải thiếu code — `GPU_LOCK`/`WhisperCache`/`DemucsCache` đã là cơ chế điều phối tài nguyên thật, có chủ đích, đúng đắn cho đúng giới hạn này (xem docstring `resources.py`). Batch/watch tuần tự (`batch.py::_run_items()`, `watch_folder.py`) là THIẾT KẾ ĐÚNG, không phải gap. Hướng scale thật cho content-automation: **`control_server/worker-dub`** (Docker, đã xây từ V34a/V34b, CPU-only nên không đụng trần VRAM, atomic job-claim đã verify N-replica-safe qua `docker compose --scale dub_worker=N`) — không cần code mới, chỉ cần quyết định cách đẩy job vào đó. **Bug thật tìm thêm lúc audit, đã sửa**: `pipeline.py` đặt tên work_dir theo GIÂY (`%Y%m%d%H%M%S`) — 2 lượt chạy MỚI (không phải resume) khởi động cùng giây trùng tên, `ensure_dir(exist_ok=True)` lặng lẽ tái dùng thư mục cũ như resume, 2 video đè file nhau; vô hại hiện tại (tuần tự thật) nhưng vá phòng hờ qua `_unique_new_folder_name()` (mới, static method, thêm hậu tố `-2`/`-3`... khi trùng). **Bug thật thứ 2 tìm được nhưng KHÔNG sửa** (đánh giá lại giữa chừng): cổng kiểm quota phút dub (`dub-job.service.js:73`, đọc-rồi-quyết) — phân tích sâu hơn xác nhận "atomic hóa" cái đọc này KHÔNG thực sự đóng được gap, vì `dubMinutesUsed` chỉ tăng SAU khi job hoàn tất (`chargeDubUsage()`), không có gì bị ghi đồng thời lúc submit để atomic bảo vệ — sửa đúng cần cơ chế RESERVATION/hold thật (như `hold.service.js` đã có cho Vox credit), là 1 mini-spec riêng, không phải "bug nhỏ". Giữ nguyên, ghi nhận là giới hạn chấp nhận được (billing thật vẫn đúng/atomic, chỉ có thể vượt nhẹ quota mềm). 3 test mới (`test_pipeline_workdir_collision.py`), 0 regression (1123/1124 pass Python — 1 fail là flake có sẵn từ V40) |
| V43 | Hold/reserve system cho quota phút dub (Phase G, chủ dự án yêu cầu 2026-08-17, đóng gap V42) | ✅ Xong | `ApiKey.dubMinutesReserved`/`DubApiJob.reservedMinutes` mới, giữ chỗ atomic lúc submit qua `$expr` (cùng kỹ thuật `balance:{$gte}` của `credit.service.js`) thay vì đọc-rồi-quyết cũ — đóng đúng gap V42 xác định. Không có ffprobe ở Node nên caller tự khai `estimatedMinutes` (tuỳ chọn, có mặc định+trần cấu hình). Release đúng chỗ ở `completeJob`/`failJob`/`sweepStaleRunning` + sweeper MỚI `sweepStaleQueued` (gap chưa từng tồn tại trước V43 — job kẹt `queued` quá TTL giờ phải giải phóng quota). 12 test mới kể cả tái hiện đúng race thật (5 submit đồng thời, quota vừa đủ 2 job) rồi xác nhận đã chặn đúng — 0 regression (265→277 pass Node) — xem TEST_LOG |
| V44 | Nhận file upload theo dòng thay vì nuốt vào RAM (Phase G, 2026-08-17) | ✅ Xong, live-verify prod | Đo thật RSS từ ngoài process: 1 upload 250 MB làm RSS tăng **485,3 MB → 34,6 MB**. Container prod chỉ 1 GB RAM + rate limit 5/phút = 2 upload đồng thời đủ OOM. Gộp cả `/v1/jobs/demucs` (cùng bug) và đảo thứ tự ghi-file/trừ-credit để upload hỏng không mất tiền. Verify prod: `UPLOAD_TOO_LARGE` (mã của mình, không phải của multipart) + ví giữ nguyên + uptime không reset |
| V45 | Kết quả job sống sót qua redeploy — GridFS (Phase G, 2026-08-17) | ✅ Xong, CHƯA verify đầu-cuối trên prod | File job chuyển vào GridFS (MongoDB managed là thứ DUY NHẤT bền vững qua redeploy), worker Python không phải sửa dòng nào. 2 bug thật lộ ra khi viết test: listener gắn sau `reply.send()` bắt hụt sự kiện → hoàn tiền nhầm cho khách đã nhận hàng; 2 request tải song song đua với dọn file → 500 thay vì 410. **Cần chủ dự án**: cấp API key để chạy kịch bản job-done → redeploy → tải lại **18-08 — LIVE-VERIFY XONG**: nộp job, chờ `done`, CỐ Ý không tải về, redeploy `voxdub-app` (container bị xoá), rồi tải — 339442 byte, MD5 TRÙNG byte-by-byte với bản trước. Trước V45 bước này sẽ trả `RESULT_LOST_REFUNDED`. |
| V46 | Đồng bộ docs cho lớp hosted dub (Phase G, 2026-08-17) | ✅ Xong | 3 commit ngày 17-08 ship mà không đụng docs nào — API.md thiếu `RESULT_LOST_REFUNDED`/`BAD_SOURCE_LANG`, ARCH.md không có một dòng nào về `worker-dub`/Vibe Host/"không có volume bền vững", TEST_LOG trống |
| V47 | Phát hành v3.1.0 (Phase G, 2026-08-17) | ✅ Xong, tải công khai được | 21 commit nằm trên `main` sau tag `v3.0.1` mà không ai tải được (`release.yml` chỉ build khi push tag). Bump `APP_VERSION` TRƯỚC khi tag là bắt buộc — `updates.py:58` so tag GitHub với hằng số đó. CI Windows sinh `VoxDub-Studio-v3.1.0-win64.zip` (75.2 MB), HTTP 200 |
| V48 | Sao lưu MongoDB không phụ thuộc nền tảng (Phase G, 2026-08-17) | ✅ Xong code, CHƯA có cron chạy thật | Backup hàng ngày trước đây là tính năng COOLIFY — rời nền tảng là mất trắng. `GET /v1/admin/backup` stream NDJSON+gzip bằng EJSON (JSON thường phá `ObjectId`/`Date`). **Vẫn là sao lưu KÉO**: chưa có máy ngoài đặt cron `backup-pull.sh` thì vẫn CHƯA có bản sao lưu nào **Bổ sung 18-08**: thêm `scripts/backup-pull.ps1` (bản PowerShell) — máy chủ dự án chạy Windows, không có `cron` lẫn `bash`, nên đặt bản `.sh` vào Task Scheduler là đặt một thứ không chạy được. Runbook mục 7b có nguyên câu lệnh `schtasks` + cách kiểm lại. **VẪN CHƯA có lịch nào chạy thật**: token admin local không khớp prod (test trả 401), đang chờ ADMIN_TOKEN thật. **18-08 — VERIFY ĐẦU-CUỐI THẬT**: xoay ADMIN_TOKEN mới + redeploy, kéo được bản sao lưu thật đầu tiên (75 dòng, 10 collection, có `creditledgers`+`apikeys`), giải nén và đếm bản ghi để kiểm chứ không chỉ nhìn dung lượng. **Vẫn CHƯA có lịch chạy** — `schtasks` phải đặt trên máy Windows của chủ dự án. |
| V49 | Trang `/thu-dub` thử API trên trình duyệt (Phase G, 2026-08-17) | ✅ Xong code, CHƯA click thử thật | Gọi đúng API đã có, XHR để có tiến trình upload, không lưu key vào localStorage, ngôn ngữ/giá đọc từ `cloudDub` trong `/v1/config/app`. **Cố ý KHÔNG làm chế độ dùng thử không cần key** — cho người lạ chạy ASR/TTS/mux miễn phí là quyết định chi phí + chống lạm dụng của chủ dự án. 8 test render mới (website lần đầu có hạ tầng test component) |
| V50 | Cloud render không im lặng nuốt tiền + giám sát kho (Phase G, 2026-08-17) | ✅ Xong, CẦN chủ dự án quyết | Audit lộ ra: `/v1/jobs/demucs` trừ 50 Vox lúc nộp, không sweeper nào đụng trạng thái `queued`, VÀ **không có worker render nào tồn tại** → bấm = mất tiền, job nằm im vĩnh viễn. `sweepStaleQueued` fail + hoàn Vox (chỉ khi CHƯA worker nào nhận). Thêm `GET /v1/admin/storage` (`orphanFiles`/`orphanChunks`). **Quyết định treo**: triển khai worker render hay tắt `cloud.render.enabled` |
| V51 | Đẩy batch lên `worker-dub` từ desktop (Phase G, 2026-08-17, đóng gap V42 để lại) | ✅ Xong code + 12 test, CHƯA chạy thật đầu-cuối | `voxdub cloud-batch --input <file\|thư mục> --output-dir …` — nộp từng video lên `/api/v1/dub`, chờ, tải kết quả. Resume-safe (chạy lại KHÔNG nộp lại video đã xong = không trả tiền lần hai); hết quota giữa chừng thì DỪNG nộp nhưng vẫn theo dõi nốt job đã nộp; "máy chủ mất kết quả (đã hoàn phí)" là trạng thái RIÊNG chứ không gộp vào `failed`; tải dở không để lại file mang tên thật. Test chạy trên máy chủ HTTP thật dựng tại chỗ, không mock `requests`. **Cần API key để verify thật** **18-08 — CHẠY THẬT XONG**: `cloud-batch` nộp→chờ→tải trọn vẹn trên prod, 41 giây cho video 24 giây, kết quả là bản lồng tiếng thật (MD5 audio khác gốc). Trừ đúng 1 phút, giữ chỗ nhả về 0. |
| V52 | Chạy đường ống cho `cloud-batch` — worker không nằm không (Phase G, 2026-08-17, đóng gap thông lượng V51 để lại) | ✅ Xong code + 16 test, CHƯA chạy thật | V51 chạy tuần tự nộp→chờ→tải→nộp, nên suốt lúc upload video sau thì worker máy chủ RẢNH — trong khi mục tiêu gốc của V42 chính là thông lượng. V52 giữ sẵn hàng đợi ngắn (`--queue-ahead`, mặc định 2): job N+1 đã đứng chờ trước khi kết quả job N tải xong. Hàng đợi cố ý NGẮN vì mỗi job chờ đã giữ chỗ quota (V43). Job xong trả lại quota → video từng bị 402 chặn được thử lại NGAY trong cùng lượt, không bỏ lửng **18-08**: chạy thật cùng lượt với V51 nhưng CHỈ 1 video nên đường ống `--queue-ahead` chưa bị ép — muốn kiểm thông lượng phải nộp nhiều video cùng lúc. **18-08 — ÉP THẬT XONG**: 4 video, `--queue-ahead 3` nộp sẵn 3 job trước khi job nào xong rồi nộp tiếp ngay khi có chỗ; 94 giây/4 video, máy chủ không nằm không. |
| V53 | Chế độ "xử lý trên máy chủ" trên trang Xử lý hàng loạt (Phase G, 2026-08-17) | ✅ Xong, CHƯA click thử thật | Ô chọn trên trang Batch, **ẩn hẳn khi chưa cấu hình** (đúng nếp `cloud_render` V12 + lip-sync V32b). Bật lên thì KHOÁ đúng những gì máy chủ không làm (phụ đề, chỉ-xuất-âm-thanh, giữ bộ giọng, mức giảm tiếng gốc) kèm ghi chú — để chúng bật mà vô tác dụng là hứa suông. Liên kết bị chặn kèm giải thích (máy chủ chỉ nhận file). 7 test GUI + smoke test toàn app |
| V54 | `cloud-batch` nhận cả liên kết, không chỉ file trên máy (Phase G, 2026-08-17) | ✅ Xong, CHƯA chạy thật | Liên kết được tải về máy trước (tái dùng `download_one` — yt-dlp + đường Douyin riêng) rồi mới đẩy lên; khoá trạng thái là CHÍNH liên kết nên tên file tải về đổi cũng không nộp trùng. Bản tải trung gian **xoá sau khi thành công, GIỮ khi hỏng** để lượt sau khỏi tải lại vài trăm MB. Gỡ luôn giới hạn "phải cùng thư mục" của V53. CLI thêm `--file` (danh sách, hỗ trợ cú pháp «link \| Tên giọng»). 6 test mới **18-08**: đường file trên máy đã chạy thật; đường LIÊN KẾT (yt-dlp/Douyin) vẫn chưa chạy thật. **18-08**: đường liên kết chạy thật qua yt-dlp Generic (URL mp4 trực tiếp) — CHƯA chứng minh extractor YouTube/TikTok/Douyin thật. |
| V55 | Huỷ job thật cho chế độ máy chủ (Phase G, 2026-08-17) | ✅ Xong code + 10 test, CHƯA live-verify prod | Đóng giới hạn V53/V54 tự ghi ra: nộp nhầm 20 video thì không có cách nào chặn. Điều kiện `apiKeyId` nằm TRONG câu update (nguyên tử) chứ không kiểm ở tầng route — huỷ job người khác nặng hơn hẳn xem trộm. 409 gộp 3 ca (không tồn tại / không phải của bạn / đã kết thúc) để không lộ jobId người khác có tồn tại. Job huỷ KHÔNG tính tiền mà không cần cơ chế hoàn: `completeJob` đòi `status:'running'` nên worker báo xong muộn bị từ chối. Worker đổi `subprocess.run`→`Popen` để giết được tiến trình con thật. **Giới hạn**: worker chỉ biết huỷ ở nhịp heartbeat (trễ vài giây là bình thường); cần API key + 1 job chạy thật mới verify được prod **18-08 — LIVE-VERIFY XONG, và lộ ra prod chạy code cũ 5 tiếng**: `cancel()` ban đầu trả "Không có endpoint này" vì nhánh `deploy/vays-control-server` tip 17-08 22:02 còn V55 landed 23:35 — nhánh deploy KHÔNG tự theo `main`. Sinh lại nhánh + redeploy rồi huỷ lúc job đã `running`: `cancelled`, quota giữ nguyên 8 phút (job huỷ không bị tính tiền). |
| V56 | Nghe thử 30 giây trước khi chạy cả video (Phase H, 2026-08-18) | ✅ Xong + 13 test, CHƯA chạy đầu-cuối trên Windows/GPU | Cắt bằng ffmpeg `-c copy -t N`, verify bằng ffprobe THẬT (video 12s → clip 5s); ffmpeg lỗi thì ném lỗi kèm lý do chứ không trả về video gốc. Nút ẩn khi «chạy tiếp dự án cũ» (nghe lại 30 giây đầu của dự án đã chạy là vô nghĩa). **Giới hạn**: vẫn tốn Vox nhưng CHƯA hiện số ước tính trước khi bấm; luôn là N giây ĐẦU, chưa chọn được đoạn giữa (video có intro dài thì đoạn đầu không đại diện); 30 giây là hằng số trong GUI |
| V57 | Hồ sơ nhân vật xuyên tập (Phase H, 2026-08-18) | ✅ Xong, CLI-first (GUI phải tới V60/V62 mới đủ dùng) | Bản khả thi của yêu cầu "đồng bộ nhân vật + giọng điệu": dub cả series thì nhân vật A giữ nguyên giọng A ở mọi tập. **Điểm chốt quyết định toàn bộ thiết kế**: nhãn diarization (`SPEAKER_00`…) KHÔNG ổn định giữa các file — cùng một người ở tập sau có thể mang nhãn khác, nên không khớp theo nhãn được. 3/4 mảnh ghép đã có sẵn (V26 tách người nói, V36 ước lượng F0 + gán giọng), V57 chỉ thêm đúng lớp ghi nhớ xuyên tập |
| V58 | Quy ước dịch của series đè cài đặt chung (Phase H, 2026-08-18) | ✅ Xong | Hồ sơ THẮNG cài đặt chung — chọn hồ sơ "Phim A" là đang nói "lần này tôi làm phim A". Nhưng chỉ đè bằng trường CÓ điền: chọn một hồ sơ mới lập mà mất sạch xưng hô đã cấu hình là kiểu mất mát âm thầm tệ nhất. Sửa TẠI CHỖ trên settings của lượt chạy, KHÔNG ghi xuống `.env` |
| V59 | Khớp nhân vật bằng speaker embedding (Phase H, 2026-08-18) | ✅ Chạy pyannote THẬT lần đầu (18-08) trên audio TỔNG HỢP — chưa có video thật | Thay khớp theo cao độ (dễ lẫn người cùng giới) bằng embedding cosine. **Đo được**: khác người khác giới 0.106–0.219; khác người CÙNG giới 0.651; **cùng người khác lời 0.783** → ngưỡng 0.72 đoán ở V59 nằm gần đúng điểm giữa, đứng vững, nhưng biên chỉ ~0.06 mỗi bên trên audio TTS SẠCH. **Rủi ro tầng hồ sơ không sửa nổi**: pyannote gộp 3 giọng nữ thành 1 người nói, cụm gộp khớp «A» ở 0.792 — cao hơn cả lượt khớp đúng — và qua luôn luật biên 0.05. Ngưỡng nào cũng vô dụng khi diarization đã gộp nhầm ở tầng dưới. Xem TEST_LOG mục V59 (18-08). |
| V60 | Hồ sơ nhân vật lên GUI (Phase H, 2026-08-18) | ✅ Xong, 2 bug thật do test bắt | Ô nhập chữ ở bước cuối wizard, chỉ hiện khi tách người nói đang bật (bày ra lúc tính năng đó tắt là hứa suông — nếp V53). Ô nhập chứ không phải danh sách chọn: gõ tên mới = tạo hồ sơ mới, gõ lại tên cũ = dùng tiếp. **Bug thật**: `_slug()` bản đầu vứt mọi ký tự ngoài ASCII nên «Phim Cổ Trang» và «Phim Có Trang» cùng ra `phim-c-trang` → hai series ghi đè hồ sơ của nhau, trộn lẫn nhân vật (với tên tiếng Việt đây là chuyện thường ngày, không phải ca hiếm) |
| V61 | Kiểm chứng hợp đồng pyannote + ngưỡng đo được (Phase H, 2026-08-18) | ✅ Xong, lộ 1 bug CÓ SẴN TỪ V26 | Không có HF token vẫn kiểm được hợp đồng API: tải MÃ NGUỒN thật về đọc (`pip download --no-deps --no-binary :all:`) cả 3.1.1 lẫn 4.0.7 — API hai bản khác hẳn nhau, và mã V26 gốc (`pipeline(audio)` rồi `.itertracks()`) **chết hoàn toàn trên 4.x**: bug có sẵn từ V26, chỉ là chưa ai chạy diarization trên máy cài mới nên chưa lộ. Giả định "embedding xếp theo `labels()`" của V59 xác nhận ĐÚNG bằng mã nguồn cả 2 bản, không phải theo tài liệu. Ngưỡng: khớp mập mờ (2 nhân vật cosine cách nhau <0.05) bị từ chối dù vượt ngưỡng, điểm số báo cáo được để người dùng tự hiệu chỉnh. **Giới hạn**: giờ có công cụ đo nhưng CHƯA có số liệu thật để chốt ngưỡng **V61b (18-08)**: dựng `.venv-diar` để chuẩn bị verify thì lộ tiếp một ca CÙNG LỚP mà V61 bỏ sót — bước NẠP model cũng đổi tên tham số (`use_auth_token` → `token`), truyền nhầm là `TypeError` bị `except Exception` biến thành "Không nạp được model", chỉ người dùng đi kiểm token/user agreement đang không hỏng. Đã sửa bằng dò chữ ký + 5 test, verify với pyannote 4.0.7 thật (hết TypeError, dừng đúng ở `GatedRepoError`). |
| V62 | Trang quản lý hồ sơ nhân vật (Phase H, 2026-08-18) | ✅ Xong + 12 test, CHƯA click thử trên Windows | Xem/đổi tên/đổi giọng/xoá nhân vật + sửa quy ước dịch của series. Cố ý KHÔNG cho tạo hồ sơ rỗng (hồ sơ sinh ra khi dub tập đầu). Cột "Nhận diện" nói rõ ai khớp bằng embedding (chính xác) và ai mới có cao độ (dễ lẫn) — người dùng biết chỗ nào đáng nghi thay vì tin mù. Cột số liệu hệ thống đo bị KHOÁ; tên trùng/rỗng bị chặn khi lưu (cả hai phá chính cơ chế khớp). **Bug tự soi ra**: đổi series khi đang sửa dở thì nạp đè luôn, mọi thứ vừa gõ biến mất không một lời nào. **Giới hạn**: chưa gộp được 2 nhân vật khi hệ thống tách nhầm một người thành hai |
| V63 | "Chạy như lần trước" — bỏ qua 6 bước wizard (Phase H, 2026-08-18) | ✅ Xong + 5 test | 90% đã có sẵn: nháp `draft_project.json` lưu toàn bộ lựa chọn và tự nạp lúc mở app, thứ thiếu chỉ là đường tắt tới nút chạy. Nút chỉ hiện ở bước 1, chỉ khi THẬT SỰ có nháp cũ, không hiện ở bước cuối (chỗ đó đã có "Bắt đầu lồng tiếng" — hai nút cùng nghĩa cạnh nhau chỉ làm người dùng phân vân). **Giới hạn**: dùng nháp gần nhất, chưa có "hồ sơ cấu hình" đặt tên (phim vs vlog) |
| V64 | Báo cáo chất lượng "5 câu đáng sửa nhất" (Phase H, 2026-08-18) | ✅ Xong + 15 test | Trang cũ liệt kê MỌI câu có vấn đề: video 300 câu ra 40 dòng, không trả lời được câu hỏi thật "sửa cái nào trước?". `autodub/quality_rank.py` (mới) là hàm thuần, tách hẳn khỏi GUI vì quy tắc xếp hạng đáng test kỹ và sẽ còn chỉnh. Thang điểm cố ý thô và GIẢI THÍCH ĐƯỢC: chồng tiếng > đọc nhanh (>1.3 nghe rõ méo) > dài quá chỗ trống. Thứ tự ổn định (cùng điểm → theo số câu) để mở 2 lần ra cùng kết quả. Câu sạch = 0 điểm và KHÔNG lọt vào danh sách. **Giới hạn**: mở Editor ở mức DỰ ÁN, chưa nhảy tới đúng câu (Editor chưa có API chọn câu theo id) |
| V65 | Ẩn hẳn "xử lý trên cloud" — đóng câu hỏi V50 để treo (Phase H, 2026-08-18, chủ dự án quyết) | ✅ Xong + 4 test, ĐÃ áp lên prod | Prod đang trả `cloudRenderEnabled: true` + giá 50 Vox trong khi KHÔNG có worker render nào — lỗi V50 mô tả đang sống thật, không phải nguy cơ lý thuyết. Tắt 3 lớp: cờ prod qua `PUT /v1/admin/config`, mặc định trong `config.service.js` (`true`→`false`, để dựng lại DB không hồi sinh), và GUI ẩn HẲN thay vì hiện ô xám "đang tạm tắt" — chữ "tạm" hứa một thứ sẽ quay lại mà nó thì không. Lớp chặn tiền vốn đã đúng chỗ (`submitDemucsJob` ném 409 trước khi trừ credit). Test khoá ca nguy hiểm nhất: nháp cũ còn tick mà máy chủ vừa tắt thì `values()` phải trả `False`. |
| V65b | Gợi ý số người nói cho pyannote — đóng lỗi gộp người nói (Phase H, 2026-08-18) | ✅ Xong + 15 test, verify thật với pyannote 4.0.7 | **KHÔNG** làm `min_speakers` = số nhân vật như đề xuất ban đầu: series 5 nhân vật mà tập này 2 người nói thì ép sàn 5 là buộc xé một người thành nhiều — đổi lỗi gộp lấy lỗi xé. Thay bằng: người dùng khai (`--speakers N`) → `num_speakers` (thắng mọi suy đoán), hồ sơ CHỈ cấp cận trên (`max_speakers` = số nhân vật + 2). Đo thật trên `tap2.wav` (4 người): không gợi ý → nhận 2, `--num-speakers 4` → nhận 3. Có tác dụng thật nhưng **pyannote không tuân thủ tuyệt đối** — xin 4 vẫn trả 3, đừng hứa khai đúng số là chắc tách đúng. |
| V66 | Gom bước rà soát vào MỘT lượt gọi (Phase H, 2026-08-18) | ✅ Xong + 7 test | Bản cũ gửi trọn system prompt của bước DỊCH (2.562 token) cho ĐÚNG MỘT câu, trong khi dịch chính câu đó tốn 84 — bước sửa đắt gấp ~31 lần bước nó đi sửa. System prompt riêng cho review (139 token) + lô 20 câu: **giảm 33 lần** token vào. Lô hỏng rơi về gọi từng câu CHỈ cho lô đó; câu bị bỏ sót thì giữ bản cũ chứ không gọi lại lẻ (gọi lại lẻ sẽ lặng lẽ kéo chi phí về mức cũ). |
| V67 | Cookie cho yt-dlp — đường lui cho video giới hạn (Phase H, 2026-08-18) | ✅ Xong + 8 test | Thử link Facebook thật của chủ dự án: reel CÔNG KHAI tải được KHÔNG cần cookie (6.2 MB, 20.166 giây) — dự đoán "sẽ gãy vì thiếu cookie" của tôi SAI. Nên cookie là đường lui, không phải cấu hình bắt buộc. `COOKIES_FILE`/`COOKIES_FROM_BROWSER`, nối vào CẢ HAI đường tải; file thắng trình duyệt, truyền tay thắng cấu hình chung. |
| V68 | Sửa tay hồ sơ nhân vật: gộp + học lại (Phase H, 2026-08-18) | ✅ Xong + 13 test | Hai lỗi NGƯỢC NHAU mà chỉnh ngưỡng không khỏi (đã thử, nới clustering hết cỡ vẫn sai). Gộp TRỘN embedding theo trọng số số tập chứ không xoá một bên. **Cố ý không có nút "tách thành 2"**: hồ sơ chỉ giữ MỘT vector mỗi nhân vật, không có dữ liệu để tách — tách thật phải chạy lại diarization trên audio. |
| — | Rà chéo sau V50 (2026-08-17) | ✅ Xong | 2 lỗi thật do V45 ⇄ V48 giẫm chân nhau: bản sao lưu nuốt byte video GridFS (600 KB video → dump 830 KB); upload đứt giữa chừng để lại chunk mồ côi VĨNH VIỄN (vô hình với mọi cách dọn theo tên). Bản test đầu của lỗi 2 PASS GIẢ — phải nhả nhiều chunk theo nhịp macrotask mới lộ ra 9 chunk nằm lại |

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
V34b — Billing theo phút video + lưu trữ production + giới hạn concurrency CPU (Phase G)

Context:
- V34a đã khuyến nghị GO (2026-08-13, xem docs/TEST_LOG.md) — điều kiện mở
  mini-spec này đã đạt.
- Chủ dự án yêu cầu trực tiếp (2026-08-14): làm tiếp V34b, nhưng "cần đo
  thêm video dài hơn trước khi chốt giá" — đúng gap V34a đã tự nêu. Đã đo
  THÊM 2 lượt live thật (2026-08-14, xem docs/TEST_LOG.md mục V34b) trước
  khi viết Scope cụ thể dưới đây:
  - Video 72.5s (17 câu, `--bg-mode none`): 118.0s xử lý → tỉ lệ **~1.63x**
    thời lượng gốc (RÕ RỆT thấp hơn tỉ lệ ~3x đo trên video 12.2s của
    V34a — chi phí nạp model là CỐ ĐỊNH, video càng dài càng pha loãng
    tốt, đúng dự đoán "chưa chắc tuyến tính" đã ghi trong Remaining Limits
    V34a).
  - Video 77.7s CÓ nhạc nền (12 câu, `--bg-mode demucs`): 204.8s xử lý →
    tỉ lệ **~2.64x** — Demucs cộng thêm ~1x thời lượng gốc so với
    `bg-mode none`. Cả 2 lượt đều CPU-only, không cần GPU (nhất quán với
    V34a: "GPU-optional" giữ nguyên đúng cho `bg-mode demucs` server-side,
    không chỉ desktop).
  - **Sửa nhận định GPU của mini-spec gốc**: Constraint 4 bản đầu viết
    "GPU đa tenant" — SAI với thực tế đã đo (2 lượt V34a + 2 lượt này, tất
    cả CPU-only). Sửa lại thành giới hạn concurrency CPU, không phải GPU
    (xem Constraint 4 mới bên dưới) — không suy đoán khi đã có bằng chứng
    ngược lại.

Goal:
- API lồng tiếng đầy đủ chạy production thật: billing đúng chi phí compute
  thật theo phút (không lỗ, không đoán mò), hỗ trợ `bg-mode=demucs` (tách
  nhạc nền) như 1 lựa chọn có giá riêng, giới hạn lưu trữ + dọn file tự
  động, nhiều job đồng thời an toàn qua nhiều worker (không tranh chấp CPU
  không kiểm soát).

Constraints (Guardrails):
1. Billing PHẢI theo số liệu chi phí compute THẬT đo được (V34a + đo thêm
   ở đây) — không định giá theo cảm tính.
2. Billing API lồng tiếng TÁCH HẲN `CreditLedger` (Vox desktop) VÀ
   `ApiUsageLedger` (V31 dịch văn bản) — 3 hệ billing độc lập, đúng nguyên
   tắc "lỗi 1 hệ không ảnh hưởng ví người dùng khác" đã áp dụng xuyên suốt
   Phase G (V31 Design Choice).
3. Lưu trữ video PHẢI có TTL/dọn tự động — ĐÃ CÓ từ V34a
   (`cloud.dub.ttl.hours`, sweeper đã nối vào `server.js`) — V34b chỉ cần
   XÁC NHẬN lại giá trị còn hợp lý với dung lượng video thật, không viết
   lại cơ chế.
4. **Giới hạn concurrency CPU** (sửa từ "GPU đa tenant" — xem Context: đã
   đo THẬT, không cần GPU) — mỗi worker chỉ xử lý ĐÚNG 1 job tại 1 thời
   điểm (đã đúng từ kiến trúc V34a: vòng lặp poll của `dub_worker.py` là
   TUẦN TỰ, `claimNextJob()` atomic không cho 2 worker nhận trùng job) —
   mở rộng công suất bằng cách chạy NHIỀU worker container (horizontal
   scale), mỗi container có giới hạn CPU rõ ràng (`deploy.resources.
   limits.cpus`) để nhiều container trên cùng máy chủ không tranh CPU vô
   kiểm soát.
5. KHÔNG cam kết SLA thời gian xử lý cụ thể trước khi có số liệu vận hành
   thật qua ít nhất 1 đợt live traffic thử nghiệm thật (khác PoC 1-2 video
   mẫu).
6. Đơn giá Vox/phút trong Scope A là **ĐỀ XUẤT BAN ĐẦU dựa trên số liệu
   compute thật**, KHÔNG PHẢI quyết định giá cuối cùng — chủ dự án là
   người chốt giá thật (quyết định kinh doanh, đúng Constraint 1 gốc).

Scope:
A. Mô hình billing mới — `ApiKey` thêm 2 field MỚI, TÁCH HẲN `quota`/
   `usageCount` hiện có của V31 (field đó đếm LƯỢT GỌI dịch văn bản, không
   liên quan): `dubMinutesQuota` (mặc định 0 — tính năng dub qua API là
   OPT-IN, admin phải cấp quota rõ ràng qua `/v1/admin`, không tự động mở
   cho mọi API key hiện có) và `dubMinutesUsed` (chạy, tăng atomic).
   `DubUsageLedger` (model MỚI, TÁCH HẲN `ApiUsageLedger`/`CreditLedger`)
   — 1 dòng bất biến mỗi job tính phí, SỐNG ĐỘC LẬP với vòng đời
   `DubApiJob` (job bị TTL sweeper xoá sau `cloud.dub.ttl.hours`, ledger
   thì KHÔNG — lịch sử billing phải còn lại).
   Tính phí SAU khi job hoàn thành (worker trả về `durationS` đo THẬT từ
   chính pipeline, không phải ước lượng client gửi lên) — quyết định khác
   khung "video đầu ra" ban đầu của mini-spec: `control_server` (Node,
   Alpine, không có ffmpeg/ffprobe) không thể tự đo thời lượng video lúc
   submit; đo thời lượng THẬT ở cuối (worker đã có sẵn số này trong
   `report.total_original_duration` của `autodub.cli`) vừa chính xác hơn
   "đầu ra" (không lệch vì tăng/giảm tốc từng câu) vừa không cần thêm phụ
   thuộc ffprobe vào control_server. Đơn giá ĐỀ XUẤT (tính từ tỉ lệ thật
   ở Context, làm tròn lên phút, CẦN CHỦ DỰ ÁN DUYỆT/CHỈNH):
   `credit.cost.cloud.dub.vox.per.minute` = 150 Vox/phút (`bg-mode=none`),
   `credit.cost.cloud.dub.vox.per.minute.demucs` = 250 Vox/phút
   (`bg-mode=demucs`, phản ánh ~1.6x lên ~2.6x compute thật đo được).
   Submit bị chặn (402) nếu `dubMinutesUsed >= dubMinutesQuota` — job ĐANG
   chạy khi cán mốc quota vẫn hoàn tất bình thường (post-paid nhẹ, không
   ngắt job giữa chừng vì lý do billing).
B. `bg-mode` là tham số THẬT của API (`POST /api/v1/dub?bgMode=none|demucs`,
   mặc định `none` — giữ hành vi/giá cũ nếu caller không đổi gì) — mở
   rộng `worker-dub/Dockerfile` cài thêm `demucs`+`soundfile` (đã live-
   verify thật ở Context, không phải suy đoán) VĨNH VIỄN vào image thay vì
   cài tạm lúc benchmark.
C. TTL: xác nhận `cloud.dub.ttl.hours` mặc định (2 giờ, đã có từ V34a) vẫn
   hợp lý — KHÔNG đổi cơ chế, chỉ audit lại có cần giảm xuống không (video
   nặng hơn audio Demucs nhiều).
D. Giới hạn CPU: thêm `deploy.resources.limits.cpus` cho service
   `dub_worker` trong `docker-compose.yml` + tài liệu hướng dẫn scale
   ngang (`docker compose up --scale dub_worker=N`) — KHÔNG cấu hình GPU
   (Constraint 4 đã sửa).
E. Tests: billing tính đúng theo `durationS` thật (làm tròn phút, đúng giá
   theo `bgMode`); quota chặn đúng khi hết (402), job đang chạy vẫn hoàn
   tất; `DubUsageLedger` sống sót qua TTL sweep của `DubApiJob`; regression
   (API dịch văn bản V31 + Demucs cloud V12 không đổi hành vi, đúng
   Constraint 2).

Audit Before Build: đã đo THẬT 2 lượt bổ sung (video dài hơn + bg-mode=
demucs) trước khi viết Scope cụ thể ở trên — xem Context + docs/TEST_LOG.md
mục V34b cho log đầy đủ.

Design Choice:
- Tính phí SAU (không phải giữ chỗ trước như luồng wizard desktop) — lý do
  kỹ thuật cụ thể ở Scope A (không có ffprobe trong control_server).
- Giới hạn concurrency bằng CPU + scale ngang (không phải GPU) — bằng
  chứng thật từ 4 lượt live-verify (2 của V34a + 2 ở đây), không suy đoán
  theo mini-spec gốc nữa.
- Đơn giá là đề xuất kỹ thuật có căn cứ, KHÔNG PHẢI quyết định cuối — đúng
  nguyên tắc "quyết định giá là quyết định kinh doanh" xuyên suốt Phase G.

Test Plan:
- Unit: tính Vox theo `durationS`+`bgMode` (làm tròn phút đúng); quota
  atomic (2 request đồng thời không vượt quota).
- Integration: job hoàn tất → ledger có đúng 1 dòng, `ApiKey.dubMinutesUsed`
  tăng đúng; hết quota → submit mới bị 402, job cũ vẫn chạy xong; TTL sweep
  xoá `DubApiJob` nhưng KHÔNG đụng `DubUsageLedger`.
- Regression: `/api/v1/translate` (V31) + `/v1/jobs/demucs` (V12) không
  đổi hành vi qua toàn bộ test suite hiện có.
- Live verification: đã có 2 lượt thật ở Context (không lặp lại — Docker
  build cho `bg-mode=demucs` mất ~2-3 phút tải torch+demucs lần đầu, đã
  xác nhận hoạt động đúng).

Success Criteria:
- Billing tính đúng theo phút thực tế đo được, tách hệ hoàn toàn khỏi Vox
  desktop và quota dịch văn bản V31.
- 0 regression cho V31 (dịch văn bản) và V12 (Demucs cloud).
- Đĩa không tràn nhờ TTL dọn tự động (đã có từ V34a, xác nhận lại).
- Concurrency an toàn qua nhiều worker (mỗi worker luôn đúng 1 job tại 1
  thời điểm, giới hạn CPU rõ ràng per-container).
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

### V36 — Nâng cấp gán giọng theo người nói (round-robin → theo đặc điểm giọng thật)

```
V36 — Gán giọng theo giới tính ước lượng từ pitch thay vì xoay vòng mù (Phase G)

Context:
- Chủ dự án hỏi trực tiếp (2026-08-14): tool có nhận diện được video có bao
  nhiêu người nói rồi chọn giọng phù hợp theo từng người, và giữ nhất quán
  xuyên suốt video không?
- Agent audit trả lời (2026-08-14, trích dẫn code thật):
  1. **Đếm/tách người nói**: CÓ thật — `autodub/speech/diarize_worker.py`
     chạy `pyannote.audio` (model `pyannote/speaker-diarization-3.1`,
     GATED trên HuggingFace, cần token) trong venv riêng `.venv-diar`
     (mini-spec V26). `autodub/speech/diarization.py::diarize()` trả về
     `[{"start", "end", "speaker"}, ...]`. **CHƯA từng live-verify trên
     audio nhiều người nói thật** — sandbox dev không có HF token/GPU để
     tải model gated (đã ghi nhận trong TEST_LOG mục V26 từ trước, không
     phải phát hiện mới).
  2. **Chọn giọng theo người nói**: ROUND-ROBIN THUẦN —
     `autodub/speech/tts/voice_assign.py::assign_voices_round_robin()`
     xoay vòng theo index qua `available_voice_names`, KHÔNG phân tích đặc
     điểm giọng nói thật của từng người (giới tính/tông giọng/tuổi) — đây
     là gap CHÍNH mini-spec này nhắm vào.
  3. **Nhất quán xuyên suốt video**: CÓ, đúng thiết kế —
     `pipeline.py::_apply_diarization()` (dòng 924-974) gọi
     `assign_voices_round_robin()` MỘT LẦN tạo `voice_map` cố định
     (speaker_label → tên giọng), rồi `apply_segment_voices()` áp dụng
     đồng loạt qua MỌI segment mang `speaker_label` đó — không có logic
     nào đổi giọng giữa chừng cho cùng 1 người.
  4. **UI**: `DIARIZATION_ENABLED` chỉ ở trang Cài đặt (mặc định tắt), cần
     cài thêm qua `scripts/setup_diarization.py` — không có trong wizard
     "Tạo dự án". Panel "Xem trước người nói" (`autodub_gui/ui/
     speaker_dialog.py` + `editor.py::list_speakers()`/`set_speaker_
     voice()`, dòng 234-314) cho người dùng ghi đè tay SAU khi dub xong.
  5. **Audit THÊM lúc chuẩn bị mini-spec này**: `_apply_diarization()`
     (dòng 458 của `pipeline.py::run()`) chạy TRƯỚC bước phân tích nội
     dung tạo `voice_hint` của V33 (`analyze_transcript()`, dòng ~1116-1117
     — thuộc bước dịch, chạy SAU diarization trong cùng 1 lượt `run()`).
     Nghĩa là `voice_hint` (giới tính/phong cách toàn video theo LLM)
     **CHƯA tồn tại** tại thời điểm gán giọng theo người nói cần chạy —
     không thể tái dùng `voice_recommend.recommend_voices()` với style
     ngay trong V36 mà không đổi thứ tự các bước trong pipeline (rủi ro
     cao hơn phạm vi mini-spec này nên KHÔNG làm ở đây — xem Scope B).

Goal:
- Gán giọng theo người nói dựa trên ĐẶC ĐIỂM THẬT đo được (giới tính ước
  lượng từ cao độ giọng nói/pitch của chính người đó) thay vì xoay vòng mù
  theo index — người nói nam có xu hướng được gán giọng nam, người nói nữ
  giọng nữ, thay vì ngẫu nhiên theo thứ tự phát hiện.

Constraints (Guardrails):
1. KHÔNG thêm model AI/dependency nặng để phân loại giọng nói (vd
   classifier giới tính giọng nói riêng, thường cần torch + model vài trăm
   MB) — dùng ước lượng cao độ cơ bản (F0) bằng autocorrelation thuần
   numpy, đúng tinh thần "engine nhẹ, đủ dùng" đã áp dụng cho
   `audio_quality.py` (V35).
2. Ước lượng giới tính từ pitch là HEURISTIC THÔ (ngưỡng tần số, không
   phải khoa học chính xác — có giọng nam trầm/nữ cao lệch ngưỡng thật) —
   khi kết quả KHÔNG rõ ràng (pitch nằm gần ngưỡng, hoặc không đo được đủ
   mẫu voiced) PHẢI rơi về round-robin cho người nói đó, KHÔNG đoán liều
   (đúng nguyên tắc "không suy đoán vượt quá điều đo được thật" xuyên suốt
   dự án).
3. KHÔNG đổi mặc định TẮT của diarization (V26 Guardrail gốc) — mini-spec
   này CHỈ đổi BƯỚC GÁN GIỌNG sau khi diarization đã chạy, không đổi có
   bật diarization hay không.
4. KHÔNG đổi luồng ghi đè tay của người dùng (`list_speakers()`/
   `set_speaker_voice()`, panel "Xem trước người nói") — gán tự động chỉ
   là GIÁ TRỊ KHỞI ĐẦU tốt hơn, người dùng vẫn luôn sửa được sau.
5. KHÔNG nối `voice_hint` (V33, phong cách toàn video) vào lần này — audit
   xác nhận thứ tự pipeline chưa cho phép (xem Context mục 5) — để dành
   mini-spec riêng nếu chủ dự án muốn sau khi đổi thứ tự các bước.
6. 0 regression khi diarization tắt (mặc định) hoặc khi ước lượng giới
   tính thất bại toàn bộ — hành vi round-robin thuần vẫn còn nguyên như
   lối thoát an toàn.

Scope:
A. `autodub/speech/diarization_voice_match.py` (mới) — hàm thuần
   `estimate_speaker_genders(wav, sr, diar_segments) -> dict[str, str]`:
   với mỗi `speaker_label`, cắt+ghép các đoạn audio thuộc người đó từ
   `wav` (đã có sẵn trong `_apply_diarization()`, không cần đọc file lại),
   ước lượng F0 trung vị bằng autocorrelation trên các khung "voiced"
   (năng lượng đủ lớn — tái dùng logic tương tự
   `audio_quality._longest_silence_ratio()` để bỏ khung lặng), phân loại
   "male"/"female" theo ngưỡng, trả `""` (rỗng — không đoán) nếu không đủ
   mẫu voiced hoặc pitch nằm trong vùng mù mờ gần ngưỡng.
B. `autodub/speech/tts/voice_assign.py` — hàm mới
   `assign_voices_by_gender(speaker_labels, genders, catalog, fallback_names)`:
   với mỗi speaker có giới tính ước lượng được, lọc `catalog` (danh mục
   `Voice` đầy đủ, không chỉ tên) theo giới tính CỨNG (tái dùng đúng quy
   tắc lọc của `voice_recommend.recommend_voices()` — giới tính LÀ bộ lọc
   cứng, không suy đoán phong cách vì chưa có `voice_hint`, xem Constraint
   5) rồi chọn 1 giọng (round-robin TRONG NHÓM giới tính đó nếu nhiều
   người nói cùng giới tính, để không phải ai cũng ra đúng 1 giọng); speaker
   không ước lượng được giới tính → rơi về `assign_voices_round_robin()`
   nguyên bản trên `fallback_names` (Constraint 2/6).
C. `autodub/pipeline.py::_apply_diarization()` — thay lời gọi
   `assign_voices_round_robin()` bằng luồng mới: ước lượng giới tính
   (Scope A) → gán theo giới tính (Scope B) → log rõ bao nhiêu người nói
   được gán theo giới tính ước lượng, bao nhiêu rơi về round-robin thuần
   (minh bạch, không giả vờ "tất cả đều thông minh").
D. Tests: unit `estimate_speaker_genders()` (giọng nói tổng hợp tần số cao/
   thấp rõ ràng → phân loại đúng; audio ngắn/lặng → trả rỗng, không đoán
   liều); unit `assign_voices_by_gender()` (lọc giới tính đúng, fallback
   round-robin đúng khi thiếu giới tính, không crash khi catalog thiếu 1
   giới tính hoàn toàn); integration `_apply_diarization()` (đúng luồng
   mới, KHÔNG đổi hành vi khi diarization tắt — regression 0).

Audit Before Build: đã audit thứ tự pipeline (Context mục 5) — xác nhận
`voice_hint` chưa sẵn sàng ở bước này, chốt Scope KHÔNG nối V33 (Constraint
5). Cần audit THÊM lúc code: cấu trúc `Voice` catalog thật
(`autodub/speech/tts/voices.py`) có field `gender` tin cậy đủ cho MỌI
giọng (kể cả giọng CapCut, không chỉ VieNeu) hay chỉ VieNeu mới có — quyết
định catalog nào Scope B lọc được.

Design Choice:
- Ước lượng pitch bằng autocorrelation thuần numpy (Constraint 1) — không
  kéo thêm model AI, nhất quán với `audio_quality.py` (V35) đã chứng minh
  cách tiếp cận "tín hiệu số học đơn giản, đủ dùng" hoạt động tốt cho lớp
  bài toán tương tự trong chính dự án này.
- KHÔNG nối `voice_hint`/V33 ở mini-spec này (Constraint 5) — đổi thứ tự
  gọi `analyze_transcript()` lên TRƯỚC `_apply_diarization()` là thay đổi
  kiến trúc lớn hơn hẳn phạm vi "gán giọng thông minh hơn", rủi ro ảnh
  hưởng luồng dịch/billing hiện có — để dành quyết định riêng.
- Rơi về round-robin khi không chắc (Constraint 2) — sai giới tính một
  giọng còn TỆ HƠN xoay vòng trung tính, nên thà thiếu thông minh còn hơn
  đoán sai có chủ đích.

Test Plan:
- Unit: `estimate_speaker_genders()` với sóng tổng hợp tần số cố định rõ
  ràng nam/nữ (ví dụ 100Hz vs 220Hz) → phân loại đúng; audio toàn khung
  lặng/quá ngắn → trả `""` cho speaker đó (không đoán).
- Unit: `assign_voices_by_gender()` — catalog đủ cả 2 giới tính → lọc
  đúng; catalog CHỈ có 1 giới tính → không crash, người nói giới tính kia
  vẫn được gán (không loại bỏ hoàn toàn, khác `recommend_voices()` được
  phép trả rỗng vì đó là GỢI Ý không bắt buộc — ở đây BẮT BUỘC phải gán
  được 1 giọng nào đó).
- Integration: `_apply_diarization()` — diarization tắt → không đổi gì
  (0 regression); bật + giới tính ước lượng được hết → không giọng nào
  trùng logic round-robin cũ một cách tình cờ (test có ý nghĩa); bật +
  không ước lượng được giới tính nào (audio giả toàn nhiễu) → HÀNH VI
  GIỐNG HỆT round-robin cũ (Constraint 6).
- Live verification: CHƯA thể chạy thật (cùng giới hạn model pyannote
  gated đã ghi nhận từ V26) — verify bằng dữ liệu tổng hợp + audio thật
  KHÔNG qua diarization (tự tạo danh sách speaker_label giả để test 2 hàm
  mới độc lập với việc diarization thật có chạy được hay không).

Success Criteria:
- Người nói có giọng nói rõ ràng nam/nữ (đo pitch tách biệt tốt) được gán
  đúng giới tính giọng đọc, thay vì ngẫu nhiên theo thứ tự phát hiện.
- Người nói không ước lượng được giới tính vẫn được gán 1 giọng hợp lệ
  (không crash, không bỏ sót) — rơi về round-robin đúng như trước.
- 0 regression khi diarization tắt (mặc định) hoặc khi chạy trên audio cũ
  đã test trước V36.
```

### V37 — Nhạc nền + hiệu ứng âm thanh AI theo nội dung video

```
V37 — PoC nhạc nền/SFX AI qua API bên thứ 3 có giấy phép thương mại rõ ràng (Phase G)

Context:
- Chủ dự án đề xuất (2026-08-14): kết nối API bên thứ 3 để lấy nhạc nền/
  hiệu ứng âm thanh phù hợp nội dung video, AI hỗ trợ chọn tự động, tiết
  kiệm thời gian dựng video thủ công, tận dụng AI cho tự động hoá.
- Agent khảo sát thị trường thật (2026-08-14, có trích nguồn) trước khi
  viết mini-spec — kết quả đầy đủ:
  - **Nhạc nền AI có giấy phép AN TOÀN cho SaaS trả phí**: ElevenLabs
    Music v2 (tự đăng ký được ngay, API đơn giản, cùng tài khoản với TTS/
    SFX đã tích hợp sẵn từ trước — VoxDub đã có dùng ElevenLabs SFX/TTS
    trong 1 số nhánh trước đó), Soundraw, Loudly. Epidemic Sound có Partner
    API "Connect" — điều khoản NÊU RÕ hỗ trợ "sublicensing cho end-user/
    onward distribution" (case study Shopee Video là 1 SaaS thật đã dùng
    kiểu này) — RẺ HƠN ở quy mô lớn và gộp cả nhạc+SFX 1 hợp đồng, nhưng
    cần đàm phán đối tác trước (không tự đăng ký được), track KINH DOANH
    riêng, không thuộc phạm vi code của mini-spec này.
  - **BẪY PHÁP LÝ tìm được, y hệt lớp lỗi cũ (NLLB-200/Wav2Lip)**: Meta
    MusicGen (tự host, miễn phí) là **CC-BY-NC-4.0 — CẤM dùng thương
    mại**, dùng sẽ lặp lại đúng lỗi NLLB đã gặp (mini-spec V6). Suno CHƯA
    có API chính thức (chỉ có API "chui" không được Suno công nhận — rủi
    ro pháp lý cho sản phẩm trả phí). Envato/AudioJungle: giấy phép chuẩn
    KHÔNG cho phép redistribute cho nhiều khách hàng trả phí (mô hình SaaS
    đa khách hàng) — không dùng được dù có vẻ rẻ.
  - **Hiệu ứng âm thanh**: ElevenLabs Sound Effects v2 (self-serve, giá rẻ
    ~$0.02/hiệu ứng, thương mại rõ ràng mọi gói trả phí) là lựa chọn nhanh
    nhất. Freesound có API thật nhưng giấy phép LẪN LỘN theo từng file
    (CC0/CC-BY/CC-BY-NC) — chỉ an toàn nếu LỌC CỨNG còn `license=CC0`.
  - **Đối thủ cùng ngành** (HeyGen — cũng là tool lồng tiếng AI) đã có API
    hiệu ứng âm thanh thật (`/v3/audio/sounds`, tìm bằng ngôn ngữ tự
    nhiên) — xác nhận tính năng này khả thi và có tiền lệ đúng lĩnh vực.
  - **Phát hiện "điểm nhấn" để đặt SFX**: KHÔNG cần model AI nặng mới cho
    PoC — timestamp/transcript ASR đã có sẵn (dấu câu, khoảng lặng giữa
    câu) cho tín hiệu rẻ; `PySceneDetect` (MIT license, pip install thuần,
    CPU-only, không cần GPU) cho phát hiện chuyển cảnh thật từ track hình
    ảnh — cả 2 khớp đúng tinh thần "engine nhẹ, đủ dùng" đã áp dụng cho
    `audio_quality.py` (V35)/ước lượng pitch (V36).
- Chủ dự án chốt (2026-08-14, qua AskUserQuestion): làm CẢ 2 track song
  song — PoC kỹ thuật với ElevenLabs ngay (mini-spec này), ĐỒNG THỜI bắt
  đầu liên hệ đàm phán đối tác Epidemic Sound (kinh doanh, ngoài phạm vi
  mini-spec kỹ thuật, chủ dự án tự theo dõi riêng).
- Ưu tiên: làm SAU V36 (thứ tự chủ dự án chỉ định).

Goal:
- 1 video mẫu dub xong có THÊM nhạc nền phù hợp tâm trạng nội dung + ít
  nhất 1 hiệu ứng âm thanh đặt đúng lúc (điểm nhấn thật, không phải chèn
  ngẫu nhiên), qua ElevenLabs Music/SFX API thật — người dùng xem trước
  được kết quả trước khi chốt, không tự động chèn vĩnh viễn không hỏi.

Constraints (Guardrails):
1. CHỈ dùng nguồn có giấy phép thương mại RÕ RÀNG cho SaaS trả phí đa
   khách hàng (verdict "SAFE" trong khảo sát) — CẤM MusicGen tự host,
   CẤM Envato/AudioJungle, CẤM Freesound trừ khi lọc cứng `license=CC0`,
   TRÁNH Suno tới khi có API chính thức. Vi phạm guardrail này là lặp lại
   đúng lỗi đã trả giá ở V6 (NLLB)/V30 (Wav2Lip).
2. Tính năng OPT-IN, KHÔNG bật mặc định cho mọi lượt dub — không phải mọi
   video (tin tức, hướng dẫn kỹ thuật) đều nên tự động có nhạc nền/SFX
   chèn thêm, và mỗi lượt gọi API tốn tiền thật (Vox + chi phí ElevenLabs
   credit).
3. KHÔNG suy đoán "điểm nhấn" bằng model AI phân tích cảm xúc/hành động
   nặng mới — dùng heuristic rẻ đã có (Context) cho PoC này, đúng nguyên
   tắc "không suy đoán vượt quá điều đo được thật" xuyên suốt dự án.
4. Billing: chi phí gọi ElevenLabs (credit thật) PHẢI phản ánh vào giá Vox
   tính năng này — không lỗ, cùng nguyên tắc "billing theo chi phí compute
   thật" đã áp dụng cho V34b (dù đây là chi phí API bên ngoài, không phải
   compute nội bộ, tinh thần vẫn giữ nguyên).
5. Người dùng LUÔN xem/nghe thử trước khi chốt (đúng nguyên tắc "người
   dùng là người quyết định cuối" đã áp dụng cho audio_quality warn ở
   V35) — không tự động ghép vĩnh viễn vào video xuất mà không cho duyệt.
6. Track Epidemic Sound là ĐÀM PHÁN KINH DOANH — mini-spec này KHÔNG viết
   code cho track đó, chỉ ghi nhận trạng thái tiến độ nếu chủ dự án cập
   nhật.

Scope:
A. `autodub/media/music_match.py` (mới) — gọi ElevenLabs Music API +
   Sound Effects API thật. Input: mô tả tâm trạng/nội dung (suy từ tiêu đề
   video đã có sẵn từ downloader + tóm tắt transcript — CHƯA dùng
   `voice_hint` của V33 vì lý do thứ tự pipeline y hệt đã audit ở V36,
   xem Constraint 3). Output: đường dẫn file nhạc/SFX đã tải về.
B. Phát hiện điểm nhấn nhẹ (mới, module riêng hoặc gộp vào A) — kết hợp
   dấu câu/khoảng lặng transcript (đã có timing) + `PySceneDetect` (thêm
   dependency mới, cần audit có xung đột `requirements.txt` không) → danh
   sách timestamp candidate cho SFX, xếp hạng đơn giản (KHÔNG suy đoán
   "quan trọng" — chỉ đưa danh sách candidate cho người dùng chọn ở GUI).
C. Tích hợp `autodub/pipeline.py` — bước MỚI, tuỳ chọn (`req.music_match`
   hoặc tương tự), đặt QUANH khu vực STEP 6 (dòng ~673, `_merge_audio_
   segments`)/`_resolve_background()` (dòng ~1319) đã có cho `bg_mode`.
   **Cần audit kỹ lúc code**: tương tác với `bg_mode=demucs` (giữ nhạc nền
   GỐC của video) — nhạc nền MỚI do AI chọn có xung đột/chồng lấn với
   nhạc nền gốc đã giữ lại không, hay 2 tính năng loại trừ lẫn nhau (PoC
   có thể giới hạn CHỈ áp dụng khi `bg_mode != demucs` để tránh chồng lấn,
   quyết định cụ thể lúc code).
D. Billing + config: `credit.cost.cloud.music_match` (Vox, phản ánh chi
   phí ElevenLabs credit thật + biên lợi nhuận — ĐỀ XUẤT, chủ dự án duyệt,
   cùng nguyên tắc Constraint 6 của V34b) — CHƯA quyết định model billing
   API-key-riêng hay dùng chung API key của VoxDub (server-side, giống
   cách control_server hiện quản lý AI provider key qua Admin, KHÔNG phải
   người dùng tự cung cấp key ElevenLabs).
E. GUI: nút "Gợi ý nhạc nền/hiệu ứng" (Editor, sau khi dub xong — cùng vị
   trí panel "AI đề xuất giọng" của V33) — hiện preview nghe thử, người
   dùng chọn áp dụng hay bỏ qua trước khi xuất video cuối.
F. Tests: unit (phát hiện điểm nhấn với transcript giả — dấu câu/khoảng
   lặng đúng vị trí kỳ vọng); integration (`music_match.py` MOCK response
   ElevenLabs — KHÔNG gọi API thật mỗi lần chạy test, tốn tiền thật);
   ≥1 lượt live-verify THẬT với API key ElevenLabs thật (chủ dự án cần
   cung cấp, giống cách cấp Gemini key cho control_server trước đây).

Audit Before Build:
- Cần API key ElevenLabs thật từ chủ dự án để live-verify (điều kiện tiên
  quyết, chưa có ở thời điểm viết mini-spec này).
- Cần audit thứ tự pipeline thật lúc code: tương tác `bg_mode=demucs` với
  nhạc nền mới (Scope C) — hiện CHƯA audit đủ, mini-spec chỉ nêu câu hỏi,
  không tự quyết trước.
- Cần audit `PySceneDetect` có xung đột dependency nào với
  `requirements.txt` hiện có không trước khi thêm.

Design Choice:
- ElevenLabs trước (self-serve, giấy phép rõ ràng, dùng được ngay) — Epidemic Sound
  để sau khi đàm phán xong (Design Choice nhất quán với pattern PoC-hẹp-
  trước-production đã dùng xuyên suốt dự án: V8→V11, V9→V12, V30→V32a/b,
  V34a→V34b).
- Server quản lý API key ElevenLabs (không bắt người dùng tự cấp key) —
  đúng mô hình SaaS hiện có (control_server quản lý AI provider key qua
  Admin, người dùng cuối không thấy/không cần biết key nào).
- Opt-in + preview bắt buộc (Constraint 2/5) — nhạc nền/SFX là lựa chọn
  thẩm mỹ chủ quan, khác các bước dịch/TTS là bắt buộc phải có kết quả.

Test Plan:
- Unit: phát hiện điểm nhấn từ transcript giả (dấu câu/khoảng lặng).
- Integration: `music_match.py` với response ElevenLabs giả lập (mock).
- Live verification: ≥1 video mẫu thật, API key ElevenLabs thật, nghe thử
  thật kết quả nhạc nền + SFX được chọn — GHI RÕ đánh giá chủ quan (nhạc
  có thật sự "phù hợp" hay không là đánh giá con người, không đo được tự
  động), không giả vờ có thước đo khách quan không tồn tại.

Success Criteria:
- ≥1 video mẫu thật có nhạc nền + SFX chèn đúng qua API thật, người dùng
  nghe thử được trước khi chốt.
- Billing tính đúng theo chi phí API thật + biên lợi nhuận đã duyệt.
- 0 regression cho luồng dub hiện có khi tính năng tắt (mặc định).
- Ghi nhận rõ giới hạn: PoC chỉ dùng ElevenLabs, track Epidemic Sound
  (kinh doanh) ghi trạng thái riêng, không chặn Success Criteria kỹ thuật.
```

### V38 — CI: cổng test tự động trước phát hành + sửa `UPDATE_REPO` sai

```
V38 — Vá lỗ hổng vận hành phát hiện thật lúc build+deploy release đầu tiên (Phase G)

Context:
- 2026-08-14, ngay sau khi build+publish bản release THẬT ĐẦU TIÊN
  (`v3.0.0`, `junnyken/voxdub-studio`) và deploy `control_server` lần đầu
  lên production, audit lộ 2 lỗ hổng vận hành thật (không phải suy đoán):
  1. `.github/workflows/` chỉ có `release.yml` (build khi push tag `v*`,
     chạy trên `windows-latest`) — KHÔNG có workflow nào chạy
     `pytest`/`node --test` tự động. 1096+ test Python và 258+ test Node
     đã tồn tại sẵn trong repo nhưng không có cơ chế nào bắt buộc chúng
     chạy trước khi 1 tag được đẩy lên và kích hoạt build release. Lượt
     release `v3.0.0` vừa rồi chỉ "an toàn" vì người vận hành (phiên làm
     việc này) tự chạy tay `pytest`/`npm test` trước khi push tag — đó là
     thói quen, không phải cơ chế của hệ thống.
  2. `.env.example:157` ghi `UPDATE_REPO=ttthanh2044/voxdub` — SAI, không
     khớp repo thật. Mặc định trong code (`autodub/config.py:251`) đã
     ĐÚNG là `junnyken/voxdub-studio` từ trước, nhưng `cai_dat.bat` copy y
     nguyên `.env.example` thành `.env` thật (đúng quy trình cài đặt
     README mục 1) — nên người dùng cài theo đúng hướng dẫn sẽ VÔ TÌNH ghi
     đè giá trị đúng bằng giá trị sai. Hệ quả: `autodub/updates.py` (kiểm
     tra bản mới qua GitHub Releases API) sẽ luôn hỏi nhầm repo, tính năng
     tự báo có bản cập nhật mới không bao giờ hoạt động cho ai cài theo
     hướng dẫn chính thức.
- Cả 2 đều là lỗi CƠ CHẾ/CẤU HÌNH thuần, không cần quyết định kinh
  doanh/hạ tầng nào — khác các mini-spec trước cần chủ dự án duyệt giá
  (V34b/V37) hay đàm phán đối tác (V37 Epidemic Sound).

Goal:
- Mọi commit đẩy lên `main` VÀ mọi tag `v*` đều tự động chạy đủ bộ test
  (Python + Node) — build release không còn phụ thuộc vào việc người vận
  hành có nhớ chạy tay hay không.
- `UPDATE_REPO` mặc định đúng xuyên suốt: code, `.env.example`, và (nếu
  có) giá trị nhúng lúc build `.exe` đều trỏ về `junnyken/voxdub-studio`.

Constraints (Guardrails):
1. Workflow test mới chạy trên `ubuntu-latest`, KHÔNG phải
   `windows-latest` — phần lớn test (pytest headless
   `QT_QPA_PLATFORM=offscreen`, `node --test` thuần) không phụ thuộc gì
   Windows-specific, chạy Linux runner rẻ hơn/nhanh hơn nhiều so với phút
   Actions Windows (giới hạn miễn phí GitHub tính phút Windows đắt gấp 2x
   Linux). `release.yml` (build .exe thật) vẫn giữ nguyên `windows-latest`
   — đó là bước RIÊNG, không gộp.
2. KHÔNG cần cài Whisper/VieNeu model nặng (~1-2GB) trong CI — audit trước
   khi build xem bộ test hiện có (1096+ Python) có bao nhiêu phần thật sự
   cần model tải về hay đã mock đủ (kỳ vọng: gần như toàn bộ đã mock, dựa
   trên pattern `fake_ffmpeg_ok`/mock `saas_client` xuyên suốt các mini-spec
   trước) — nếu có phần cần model thật, tách riêng hoặc đánh dấu skip
   trong CI (rõ ràng, không giả vờ đã test).
3. Sửa `UPDATE_REPO` là sửa VĂN BẢN VÍ DỤ (`.env.example`), KHÔNG đụng gì
   tới `autodub/config.py` (giá trị mặc định trong code đã đúng sẵn,
   không cần sửa) — tránh sửa nhầm chỗ đã đúng.
4. Không tự ý biến workflow test mới thành GATE CỨNG chặn merge (branch
   protection rule) — đó là quyết định vận hành nhóm (ai review/approve
   PR), CHỦ DỰ ÁN quyết định có bật branch protection hay chỉ để CI chạy
   báo đỏ/xanh tham khảo trước.

Scope:
A. `.github/workflows/test.yml` (mới) — 2 job song song: `python-tests`
   (setup Python 3.12, cài `requirements.txt` + deps test, chạy
   `pytest tests/ -q` với `QT_QPA_PLATFORM=offscreen`) và `node-tests`
   (setup Node 20, `cd control_server && npm ci && npm test`). Trigger:
   `push` (mọi nhánh) + `pull_request` vào `main`.
B. `.env.example:157` — sửa `UPDATE_REPO=junnyken/voxdub-studio` (khớp
   đúng mặc định code đã có).
C. Audit `scripts/build_exe.py`/`autodub_gui/_embedded.py` xem có nhúng
   cứng giá trị `UPDATE_REPO` nào khác lúc build `.exe` không (khác cơ chế
   `VOXDUB_API_URL` đã audit ở V34a) — nếu có, sửa luôn cho khớp.
D. Tests: workflow tự nó là bằng chứng — chạy thật qua GitHub Actions ít
   nhất 1 lần (push thử), xác nhận cả 2 job pass với đúng bộ test hiện có,
   không phải test giả/rỗng.

Audit Before Build:
- Cần đọc `scripts/build_exe.py` xác nhận `UPDATE_REPO` không bị nhúng
  cứng ở đâu khác ngoài `.env.example` (Scope C).
- Cần xác nhận bộ test Python hiện tại (1096+) chạy được trọn vẹn trên
  `ubuntu-latest` không cần model AI nặng tải về — audit nhanh bằng cách
  thử chạy `pytest tests/ -q` trên môi trường sạch (không có sẵn cache
  model) trước khi viết workflow thật.

Design Choice:
- Workflow test TÁCH RIÊNG khỏi `release.yml` (không nhúng bước test vào
  giữa quy trình build Windows) — độc lập, chạy nhanh trên mọi push (kể cả
  nhánh dev), không phải chỉ lúc chuẩn bị release. Đúng nguyên tắc "kiểm
  tra sớm, kiểm tra thường xuyên" hơn là chỉ kiểm tra ngay trước khi phát
  hành.

Test Plan:
- Chạy thử workflow qua 1 lượt push thật, xác nhận 2 job đều pass, thời
  gian chạy hợp lý (ước tính vài phút, không cần benchmark chính xác).
- Xác nhận `UPDATE_REPO` mới hoạt động đúng: `autodub/updates.py` gọi
  đúng repo, tìm thấy đúng release `v3.0.0` vừa publish.

Success Criteria:
- CI test chạy tự động, thấy được kết quả (pass/fail) ngay trên GitHub mà
  không cần ai chạy tay.
- `UPDATE_REPO` đúng ở mọi nơi, tính năng tự báo cập nhật hoạt động thật
  (không giả vờ) khi có release mới.
- 0 regression: `release.yml` vẫn hoạt động y nguyên như trước.
```

### V39 — Sửa race condition ngữ cảnh câu trước khi dịch song song nhiều lô

```
V39 — Nâng độ tự nhiên bản dịch: sửa cơ chế giữ mạch xưng hô/thuật ngữ giữa
các lô dịch song song, hiện gần như không hoạt động (Phase G)

Context:
- 2026-08-15, chủ dự án yêu cầu rà lại 4 mảng để "hoàn thiện việc xây dựng
  video": (1) độ tự nhiên bản dịch — ƯU TIÊN CAO NHẤT, (2) khớp thời gian
  đọc câu dài, (3) chất lượng giọng đọc AI/đồng bộ cảm xúc, (4) nhạc nền/SFX
  AI tự động (V37, vừa xong).
- Audit thật (đọc code, không suy đoán) cho cả 4 mảng:
  1. (2) Khớp thời gian: đã có `apply_soft_timing()` (dồn trễ vào khoảng
     lặng → nén nhẹ bất khả kháng → chấp nhận+báo cáo) + đòn bẩy toàn cục
     `video_speed`. Lời nhắc dịch (`control_server/src/prompts/translate.js`)
     ĐÃ gửi `max_chars` tính từ khung thời gian thật + yêu cầu model tự
     rút gọn ngay từ lượt dịch đầu, không đợi tới bước khớp thời gian mới
     xử lý. Đã khá đầy đủ, KHÔNG tìm thấy gap thật đáng kể.
  2. (3) Cảm xúc: mini-spec V28 đã wiring đúng — máy chủ phân loại tone
     từng câu (`neutral`/`excited`/`serious`) qua LLM khi bật
     `EMOTION_VOICE_ENABLED`, `pipeline.py::_apply_emotion_styles()` ưu
     tiên tín hiệu LLM hơn heuristic văn bản local, ánh xạ đúng sang 3
     style giọng VieNeu thật. Công tắc có trong Cài đặt (thẻ Giọng đọc).
     Đã hoạt động đúng, KHÔNG tìm thấy gap thật.
  3. (4) Nhạc nền/SFX AI: V37 vừa xong, live-verify thật, không lặp lại.
  4. (1) Độ tự nhiên bản dịch: prompt dịch (`control_server/src/prompts/
     translate.js::buildTranslateSystemPrompt()`) RẤT chi tiết — quy tắc
     riêng theo từng ngôn ngữ đích (trợ từ cuối câu tiếng Việt, kính ngữ
     tiếng Nhật, đại từ nhân xưng theo ngôn ngữ...), khối "CONSISTENCY"
     yêu cầu model tự giữ nhất quán tên riêng/thuật ngữ/xưng hô XUYÊN SUỐT
     transcript. **Tìm ra bug thật đúng vào yêu cầu "xuyên suốt transcript"
     này**: `autodub/text/translate_saas.py::translate_segments()` chia
     video thành nhiều lô (`translate_batch_size`, mặc định 40 câu) rồi
     nộp TẤT CẢ vào `ThreadPoolExecutor` gần như đồng thời
     (`[pool.submit(_run_batch, i, b) for i, b in enumerate(batches)]`,
     dòng ~294). Mỗi lô có gửi kèm `prev_context` (3 câu ngay trước lô,
     kèm bản dịch tiếng Việt NẾU ĐÃ CÓ — `_prev_context()`, dòng ~188) để
     giữ mạch — nhưng vì các lô chạy song song thật (mặc định
     `parallel_workers` > 1), lô sau hầu như LUÔN tính `_prev_context()`
     TRƯỚC KHI lô liền trước kịp nhận phản hồi mạng (độ trễ mạng thật quan
     sát được trong phiên này: vài giây/lô) — trường bản dịch tiếng Việt
     trong `prev_context` gần như luôn RỖNG cho MỌI lô từ lô thứ 2 trở đi.
     Cơ chế "đọc câu Việt đã dịch của lô trước để giữ mạch" gần như KHÔNG
     hoạt động đúng thiết kế — chỉ còn tác dụng thật cho video 1 lô (≤40
     câu). Video dài hơn (nhiều lô) mất đi lớp bảo vệ liền mạch NGAY TẠI
     ranh giới lô — đúng chỗ dễ lộ ra "câu trước câu sau lệch giọng văn"
     nhất.
  5. **Không phải mất hoàn toàn** — `context.pronouns`/`context.glossary`
     (từ `analyze_transcript()`, tính 1 lần/video, không đua tranh) vẫn
     gửi ĐẦY ĐỦ cho MỌI lô, đây là 2 lớp bảo vệ chính cho xưng hô/thuật
     ngữ CỐ ĐỊNH. `prev_context` cũng LUÔN gửi được câu GỐC (không phải
     bản dịch) của 3 câu trước — model vẫn đọc hiểu được mạch ý, chỉ thiếu
     đúng CÁCH DÙNG TỪ đã chọn ở câu ngay trước. Mức độ ảnh hưởng thật là
     "giảm độ mượt mạch văn ở ranh giới lô", không phải "dịch sai/lệch
     nghĩa".

Goal:
- Lô dịch thứ N (N ≥ 1, đánh số từ 0) khi xây `prev_context` phải ưu tiên
  đợi có kết quả THẬT của lô N-1 (bản dịch tiếng Việt thật, không phải
  rỗng) trong 1 khoảng chờ CÓ GIỚI HẠN — không đợi vô thời hạn (làm chậm cả
  lô nếu 1 lô bị treo/lỗi mạng), không phá vỡ tốc độ dịch song song cho
  video có NHIỀU lô CÁCH XA NHAU (lô N+3 không cần đợi lô N+2 nếu bản thân
  nó không phải lô liền sau).

Constraints (Guardrails):
1. KHÔNG chuyển toàn bộ về dịch tuần tự (workers=1) — mất hẳn lợi ích tốc
   độ dịch song song cho video dài (bằng chứng thật: `parallel_workers`
   mặc định >1, log thật trong phiên này cho thấy máy chạy `parallel 6`).
   Giải pháp phải giữ được phần lớn lợi ích song song.
2. Thời gian chờ lô liền trước PHẢI có trần cứng (vài giây, không phải vô
   hạn) — lô trước lỗi/bị retry (đã thấy thật trong phiên này: lỗi tạm
   thời phải thử lại tới 3 lần, mỗi lần backoff tăng dần) không được kéo
   lô sau treo theo.
3. Hết thời gian chờ mà lô trước vẫn chưa xong: lô sau PHẢI tự chạy tiếp
   với `prev_context` tốt nhất đang có (câu gốc, có thể thiếu bản dịch) —
   ĐÚNG hành vi graceful-degrade hiện có, không phải lỗi mới.
4. Không đổi format `prev_context`/prompt gửi lên máy chủ — chỉ đổi THỜI
   ĐIỂM lô sau tính `prev_context`, giữ nguyên toàn bộ hợp đồng API hiện
   có (0 thay đổi phía `control_server`).

Scope:
A. `autodub/text/translate_saas.py::translate_segments()` — đổi cách nộp
   batch vào `ThreadPoolExecutor`: giữ 1 danh sách `futures` được điền dần
   (không phải 1 list-comprehension nộp hết cùng lúc), để `_run_batch(i,
   batch)` với `i > 0` truy cập được `futures[i-1]` (lô liền trước, đã
   được nộp trước đó trong cùng vòng lặp — không có vấn đề thứ tự khởi tạo
   vì vòng lặp nộp batch chạy tuần tự trên luồng chính).
B. Trong `_run_batch`, TRƯỚC khi build payload: nếu `i > 0`, gọi
   `futures[i-1].result(timeout=<trần>)` — bọc `TimeoutError` (và mọi lỗi
   khác của lô trước — lô trước lỗi thật thì không có gì để đợi thêm) rồi
   BỎ QUA, tiếp tục với `prev_context` hiện có (dù rỗng bản dịch). Chỉ khi
   lô trước THẬT SỰ xong trong hạn mới đọc lại `_prev_context()` (lúc này
   `all_segments` đã được cập nhật bản dịch thật của lô trước).
C. Trần thời gian chờ: đề xuất ~8s (dựa quan sát thật độ trễ 1 lô dịch
   trong phiên này ~2-4s bình thường, có dư cho dao động) — ĐỀ XUẤT KỸ
   THUẬT, chủ dự án có thể điều chỉnh, không phải số cố định tuyệt đối.
D. Tests: mô phỏng 3 lô dịch với độ trễ giả lập khác nhau (lô 0 nhanh, lô
   1 chậm hơn ngưỡng trần) — xác nhận (a) lô 1 chờ được lô 0 khi lô 0 xong
   trong hạn (prev_context có bản dịch thật), (b) lô 2 KHÔNG chờ vô hạn
   khi lô 1 vượt trần (vẫn chạy tiếp, prev_context không có bản dịch của
   lô 1 nhưng vẫn có câu gốc), (c) 0 regression cho video 1 lô (hành vi y
   hệt trước — không có lô nào để chờ).

Audit Before Build:
- Đã audit đủ tại Context — không cần audit thêm trước khi code, hiểu rõ
  đúng vị trí (`translate_saas.py` dòng ~188 `_prev_context()`, ~294 nộp
  batch) và cơ chế race.

Design Choice:
- Chờ CÓ TRẦN thay vì (a) tuần tự hoàn toàn (mất tốc độ) hay (b) không sửa
  gì (giữ nguyên race, cơ chế prev_context gần như vô dụng cho video nhiều
  lô) — cân bằng giữa đúng mini-spec Goal và Constraint 1/2. Đây là quyết
  định kỹ thuật thuần (không phải giá/kinh doanh), không cần chủ dự án
  duyệt trước khi build, nhưng trần thời gian cụ thể (Scope C) có thể tinh
  chỉnh sau khi có số liệu thật từ nhiều video hơn.

Test Plan:
- Unit: giả lập futures với độ trễ kiểm soát được (không gọi mạng thật),
  xác nhận đúng 3 hành vi ở Scope D.
- Integration: chạy `translate_segments()` thật (mock `client.translate`)
  với video giả lập >40 câu (≥2 lô), xác nhận lô thứ 2 THẬT SỰ nhận được
  `prev_context` có bản dịch tiếng Việt của lô 1 khi lô 1 xong nhanh.

Success Criteria:
- Video nhiều lô: `prev_context` của lô N có bản dịch thật của lô N-1
  trong đa số trường hợp bình thường (lô trước không lỗi/không quá chậm).
- Video 1 lô: 0 regression, hành vi y hệt trước khi sửa.
- Không tăng đáng kể tổng thời gian dịch cho trường hợp bình thường (lô
  trước xong trong hạn thì gần như không có độ trễ thêm — thời gian chờ
  trùng với thời gian lô đó vốn đã cần để xong).
```

### V40 — Sửa 3 bug thật từ audit sâu toàn pipeline

```
V40 — Resume-safety (transcript/giọng đọc sai lệch khi resume) + tín hiệu
chất lượng Demucs + tiến trình con mồ côi (Phase G)

Context:
- 2026-08-16, chủ dự án yêu cầu audit lại toàn bộ tính năng tìm bug + tham
  khảo thị trường tool auto-dub/auto-video để định hướng nâng cấp. 2 agent
  chạy song song: (1) audit sâu code các mảng CHƯA soát trong V39 (ASR,
  Demucs, render, downloader, checkpoint/resume, SaaS credit, GUI lifecycle)
  — tìm 4 bug thật; (2) khảo sát thị trường (Rask/HeyGen/ElevenLabs/Vidnoz/
  Vrew/Opus Clip...) — xem mục "Định hướng thị trường" bên dưới.
- Chủ dự án chọn sửa 3/4 bug (bỏ #4 LOW — sai loại exception timeout hiếm
  gặp, không ảnh hưởng kết quả).
- Audit xác nhận phần còn lại (credit/billing, downloader, audio mixer, GUI
  cancel UX) đã vững, KHÔNG tìm thấy gap thật — không sửa gì thêm ở đó.

Goal:
1. Resume một dự án sau khi ĐỔI "Ngôn ngữ gốc" hoặc ĐỔI giọng đọc (job cũ
   dừng giữa chừng — hết Vox, lỗi mạng, cancel) không được âm thầm dùng lại
   cache của tham số CŨ.
2. Tách nhạc nền (Demucs) "chạy không lỗi" phải có tín hiệu SƠ BỘ về việc
   tách có sạch hay không, thay vì hoàn toàn im lặng.
3. Đóng app (đóng cửa sổ, force-quit) giữa lúc ASR/Demucs đang chạy phải có
   thêm 1 lưới an toàn dọn tiến trình con, giảm nguy cơ mồ côi.

Constraints (Guardrails):
1. Thư mục dự án tạo TRƯỚC V40 (không có marker mới) phải tiếp tục dùng lại
   cache như hành vi cũ — không được ép làm lại oan (nghe lại ASR/đọc lại
   TTS) chỉ vì thiếu 1 trường mới thêm.
2. Tín hiệu chất lượng Demucs CHỈ được báo, KHÔNG được chặn pipeline — video
   hoàn toàn không có lời thoại (nhạc phim, ASMR...) là hợp lệ, không phải
   lỗi tách; không có cách nào phân biệt chắc chắn 2 trường hợp mà không
   nghe thật.
3. Không thêm dependency mới cho code chạy trong tiến trình chính — CI đã
   cố tình loại `soundfile`/`demucs` khỏi cài đặt test (V38) để tránh kéo
   torch; đo chất lượng WAV phải dùng `wave` (stdlib) + `numpy` (đã có).
4. `atexit` chỉ là lưới an toàn BỔ SUNG cho lượt thoát tương đối êm (Qt app
   gọi `sys.exit`), không thay thế cơ chế cancel hiện có, không cam kết bảo
   vệ được `kill -9`/crash cứng — Windows không có parent-death-signal.

Scope:
A. `autodub/pipeline.py::_load_cached_transcript()` (mới, static method
   tách từ khối inline cũ trong `_run_impl` Step 3) — đọc + validate shape
   JSON (như cũ) + so `lang_code` với marker `.asr_lang` cạnh
   `transcript_original.json`. Marker ghi lại NGAY sau khi ASR thật chạy
   xong (không ghi khi dùng cache).
B. `autodub/pipeline.py::_ensure_render_mode()` (đã có từ V-render-mode cũ,
   mở rộng) — thêm tham số `target`/`voice`, resolve qua
   `voice_catalog.resolve()` (đúng tên thật dùng khi synth, tránh 2 alias
   cùng trỏ 1 giọng bị coi là "đổi"), ghi dòng 2 của marker `.render_mode`
   sẵn có (dòng 1 vẫn là `RENDER_MODE`). Marker CHỈ 1 dòng (từ trước V40)
   → `current_voice=None` → KHÔNG coi là đổi (Constraint 1).
C. `autodub/pipeline.py::_resolve_background()` — sau khi Demucs tách xong
   (nhánh local, không phải cloud — V12 cloud path ngoài phạm vi), đọc
   `vocals.wav` qua `wave` stdlib, chuẩn hoá mono float32, chạy
   `audio_quality.analyze()` (tái dùng nguyên, không viết ngưỡng mới) → lưu
   side-channel `self._last_vocals_quality`, đọc lại bởi
   `_build_quality_report()` → field mới `background_separation` (additive,
   cùng pattern `translate_review` của V29).
D. `autodub/speech/transcriber.py::_transcribe_whisper_subprocess()` +
   `autodub/media/vocal_separator.py::_run_demucs_gpu_worker()` —
   `atexit.register(proc.kill)` ngay sau `Popen`, `atexit.unregister(...)`
   trong `finally`/sau khi xong. Worker GPU đổi `subprocess.run()` →
   `Popen()` + `communicate(timeout=...)` thủ công để có handle `proc`
   đăng ký được (giữ nguyên hành vi timeout/kill khi hết hạn).
E. Tests: `tests/test_pipeline_resume_safety.py` (mới) cho A/B/C;
   `tests/test_vocal_separator.py`/`tests/test_transcriber_watchdog.py`
   (bổ sung) cho D — mock `atexit.register`/`unregister`, xác nhận gọi
   đúng cặp mà không cần chờ tiến trình thật chết.

Audit Before Build:
- Đã audit đủ qua 2 agent song song ở Context — đọc thật `pipeline.py`
  (Step 3/Step 5/`_resolve_background`), `vocal_separator.py`,
  `transcriber.py`, `vieneu_vi.py` (pattern atexit tham chiếu), xác nhận
  không có cơ chế tương đương nào đã tồn tại cho 3 bug này trước khi viết
  mini-spec.

Design Choice:
- Resume-safety: TÁI DÙNG đúng pattern marker file đã có sẵn cho
  render-mode (không phát minh cơ chế mới) — nhất quán với cách codebase đã
  giải quyết vấn đề y hệt (cache thuộc tính nào đó của lượt chạy trước) một
  lần trước đây.
- Demucs quality: CHỈ báo (field mới, không gate cứng) — khác V23's
  `quality_gate.py` (có thể BẶT gate chặn), vì không có ngưỡng nào phân
  biệt được "tách tệ" và "video không lời thoại" một cách đáng tin — quyết
  định kỹ thuật thuần, phù hợp Constraint 2.
- Orphaned subprocess: `atexit` (không phải process-group/job-object Windows
  API phức tạp hơn) — mức bảo vệ tương đương chính xác những gì VieNeu
  worker đã có, nhất quán toàn codebase, chi phí triển khai thấp; nâng lên
  job-object thật (bảo vệ được cả crash cứng) là nâng cấp riêng, không cần
  thiết cho mini-spec này.

Test Plan:
- Unit thuần (không cần subprocess/model thật): `_load_cached_transcript()`
  với transcript+marker giả (khớp/lệch ngôn ngữ/marker vắng/JSON hỏng);
  `_ensure_render_mode()` với danh mục giọng giả (`monkeypatch` catalog,
  tránh rơi về giọng mặc định làm 2 tên giả trùng nhau); `_build_quality_report()`
  field mới có mặt.
- Integration nhẹ: `_resolve_background()` với `separate_vocals` giả (viết
  WAV thật bằng pydub — im lặng vs. có âm) qua `monkeypatch`, xác nhận
  `_last_vocals_quality` đúng level.
- atexit: mock `atexit.register`/`unregister`, xác nhận gọi đúng 1 lần mỗi
  bên khi thành công (không rò rỉ đăng ký), và trên nhánh timeout (Demucs
  GPU worker) vẫn `proc.kill()`+`proc.wait()` như hành vi `subprocess.run()`
  cũ.

Success Criteria:
- Đổi "Ngôn ngữ gốc"/giọng đọc rồi resume: cache CŨ bị vô hiệu đúng, dự án
  tạo trước V40 không bị ép làm lại oan (0 regression).
- `quality_report.json` có field `background_separation` không rỗng khi
  `bg_mode="demucs"` chạy thật; rỗng (`{}`) khi không dùng Demucs.
- `atexit.register(proc.kill)` được gọi ngay sau khi tạo tiến trình ASR/
  Demucs-GPU, `unregister` khi hàm kết thúc bình thường — xác nhận qua
  test, không cần live-verify thật (không có cách an toàn mô phỏng force-
  quit thật trong CI).
- 0 regression toàn bộ suite hiện có.
```

### V41 — Nâng chất lượng đọc hiểu nguồn Anh/Trung

```
V41 — Rule bỏ từ đệm tiếng Anh (đối xứng rule bỏ trợ từ tiếng Trung đã có) +
cảnh báo khi thiếu model chấm câu Paraformer (Phase G)

Context:
- 2026-08-16, chủ dự án chọn "nâng chất lượng đọc hiểu nguồn Anh/Trung" làm
  1 trong 2 hướng ưu tiên (cùng batch xử lý song song — chưa làm, xem
  Remaining Limits). Khác V39 (sửa mạch xưng hô GIỮA CÁC LÔ trong CÙNG 1
  video) — đây là chất lượng HIỂU NGUỒN theo từng ngôn ngữ nguồn cụ thể.
- Audit thật (đọc code, không suy đoán) 5 câu hỏi:
  1. Prompt dịch (`translate.js`) có nhận biết ngôn ngữ NGUỒN không, hay
     hoàn toàn source-agnostic? → Source-agnostic gần như tuyệt đối
     (`sourceLang` chỉ xuất hiện 1 lần trong câu mở đầu prompt, không dùng
     lại). Đây LÀ nguyên nhân gốc của gap #1 bên dưới — nhưng bản thân việc
     source-agnostic không phải lỗi (LLM đa ngôn ngữ hiện đại không cần
     nhiều scaffolding "nguồn là X" cho ngữ pháp/thành ngữ thông thường).
  2. Ranh giới câu Paraformer (tiếng Trung) có kém hơn Whisper (tiếng Anh)
     không (lo ngại: tiếng Trung không có khoảng trắng/cấu trúc mệnh đề rõ
     như tiếng Anh)? → KHÔNG — cả 2 đều cắt câu theo silero-VAD (khoảng
     lặng ÂM THANH), không phải cấu trúc CHỮ. `asr_paraformer_worker.py`
     dòng ~115-122 và `transcriber.py` dòng ~420-421 dùng cùng kỹ thuật.
     Không phải gap thật.
  3. Thành ngữ/tiếng lóng tiếng Anh → đã có rule map-theo-nghĩa tốt sẵn
     (`translate.js` dòng 110: "Render slang/internet idioms as the
     EQUIVALENT English idiom for the same register"). Không phải gap.
  4. **Gap thật #1**: rule "bỏ trợ từ tiếng Trung 啊/呢/嘛/吧" đã có ở MỌI
     target trừ zh (dòng 94/125/156/218/249/280/311/342/373) — codebase đã
     tự nhận ra "tạp âm nguồn dịch thẳng ra target là lỗi thật" và sửa cho
     tiếng Trung, nhưng CHƯA làm tương tự cho từ đệm tiếng Anh nói (um, uh,
     like, you know...) — dù đây là tạp âm phổ biến NHẤT cho đúng nội dung
     "YouTube/TikTok creator style" mà chính prompt đang nhắm tới
     (`translate.js` dòng 64, "skip unnecessary filler" — nói MỤC TIÊU
     nhưng thiếu RULE cụ thể cho nguồn tiếng Anh).
  5. **Gap thật #2**: `scripts/setup_paraformer.py` dòng 128-136 tải model
     chấm câu CT-Transformer trong `try/except` — lỗi mạng/tải dở chỉ log
     `"!! không tải được model chấm câu ... bỏ qua"` rồi tiếp tục.
     `asr_paraformer_worker.py` dòng ~94 mỗi lượt chạy chỉ kiểm
     `os.path.isfile(punct_model)` — thiếu thì `punct=None` VĨNH VIỄN
     (script cài chỉ chạy 1 lần lúc setup, không có gì kích hoạt cài lại).
     Cảnh báo hiện tại (`asr_paraformer_worker.py` dòng 102) chỉ in ra
     stderr của tiến trình con — GUI/log chính KHÔNG đọc stream đó, người
     dùng không có cách nào biết transcript đang thiếu dấu câu. Vi phạm
     đúng nguyên tắc "degrade phải trung thực, không giả im lặng" đã ghi
     trong CLAUDE.md của project.

Goal:
1. Dịch nguồn tiếng Anh có từ đệm/tạp âm nói (um/uh/like/you know...) sang
   bất kỳ target nào (trừ chính target=en) không được dịch thẳng ra các từ
   này — đúng đối xứng với cách trợ từ tiếng Trung đã được xử lý.
2. Khi Paraformer chạy THIẾU model chấm câu, người dùng phải thấy cảnh báo
   rõ ràng ở nơi họ thực sự xem log (logger chính, không phải stderr của
   tiến trình con), giải thích ảnh hưởng + cách khắc phục.

Constraints (Guardrails):
1. KHÔNG đổi rule trợ từ tiếng Trung đã có (0 regression V18) — chỉ THÊM
   rule mới, không sửa/xóa rule cũ.
2. Rule mới KHÔNG áp cho target=zh (giữ nguyên hành vi V18: modal particles
   là ĐÚNG trong tiếng Trung nói) và KHÔNG áp cho target=en (target=nguồn
   cùng là tiếng Anh không có ý nghĩa thực tế trong use case dubbing).
3. Cảnh báo thiếu model chấm câu CHỈ báo, KHÔNG chặn pipeline (Paraformer
   vẫn chạy được không dấu câu, đây là hành vi degrade ĐÃ ĐÚNG từ trước —
   chỉ thiếu tín hiệu, không thiếu khả năng chạy).
4. KHÔNG thêm network retry vào worker subprocess (hot path mỗi lượt dịch)
   — rủi ro làm chậm/treo mọi video nếu mạng chập chờn; cảnh báo + hướng
   dẫn chạy lại script cài đặt thủ công là đủ, đúng mức độ rủi ro thấp nhất
   cho gap MEDIUM/hiếm gặp này.

Scope:
A. `control_server/src/prompts/translate.js` — thêm dòng rule "English
   Filler Words" cạnh rule "Chinese Particles" trong block `vi` (dòng 94,
   quan trọng nhất vì target=vi là ca thực tế chiếm đa số); mở rộng câu có
   sẵn "Drop discourse/modal particles..." ở các block ja/es/th/id/pt/fr/de
   để nêu thêm ví dụ từ đệm tiếng Anh; thêm dòng tương tự vào
   `_genericRules()` fallback. KHÔNG đụng block `zh`/`en`.
B. `autodub/speech/asr_paraformer_worker.py` — message `"done"` thêm field
   `punctuation_available: bool` (đã tính sẵn từ biến `punct is not None`
   có từ trước, không cần logic mới).
C. `autodub/speech/paraformer_transcriber.py::transcribe_paraformer()` —
   đọc field mới (mặc định `True` nếu worker cũ không gửi, tránh cảnh báo
   giả), `logger.warning(...)` rõ ràng khi `False`, kèm hướng dẫn chạy lại
   `scripts/setup_paraformer.py`.
D. Tests: `translate-prompts.test.js` (V41 — rule mới có mặt ở target
   không phải zh/en, vắng mặt ở zh/en, generic fallback cũng có);
   `test_paraformer_watchdog.py` (V41 — worker báo thiếu chấm câu → cảnh
   báo logger chính; worker báo có/không gửi field → không cảnh báo giả).

Audit Before Build:
- Đã audit đủ ở Context (đọc thật `translate.js` toàn bộ 756 dòng,
  `asr_paraformer_worker.py`, `setup_paraformer.py`, `transcriber.py`,
  `paraformer_transcriber.py`) trước khi viết mini-spec — không cần audit
  thêm.

Design Choice:
- Rule tiếng Anh: TÁI DÙNG đúng vị trí/pattern rule tiếng Trung đã có (mở
  rộng câu có sẵn thay vì viết khối riêng) — nhất quán, dễ maintain, không
  phát minh cấu trúc prompt mới.
- Cảnh báo chấm câu: chọn "chỉ báo qua logger chính" thay vì "tự động thử
  tải lại model trong worker" — đúng Constraint 4 (không thêm network call
  vào hot path), phù hợp mức độ nghiêm trọng thật (MEDIUM, hiếm gặp — chỉ
  ảnh hưởng khi cài đặt ban đầu bị gián đoạn mạng).

Test Plan:
- Node: `buildTranslateSystemPrompt()` cho từng target — rule mới có mặt
  (regex match cụm "um...uh...like...you know") ở target không phải zh/en,
  vắng mặt ở zh (đúng exception V18) và en (đúng exception mới).
- Python: worker giả (không mock Popen, đúng pattern có sẵn) gửi
  `punctuation_available: false`/`true`/vắng field — xác nhận cảnh báo
  logger đúng 1 trong 3 trường hợp, không cảnh báo giả 2 trường hợp còn
  lại.

Success Criteria:
- 8/10 target block (trừ zh/en) có rule bỏ từ đệm tiếng Anh, không đổi
  hành vi zh/en.
- Paraformer thiếu model chấm câu → dòng cảnh báo xuất hiện ở
  `autodub.paraformer` logger (nơi GUI/log chính đọc được), không chỉ ở
  stderr worker con.
- 0 regression toàn bộ 2 suite (Python `pytest tests/`, Node `npm test`).
```

### V44 — Nhận file upload theo dòng thay vì nuốt trọn vào RAM

```
V44 — Streaming upload cho 2 route nhận file (Phase G, phát hiện khi audit
hạ tầng sau khi chuyển sang Vibe Host 2026-08-17)

Context:
- docs/ARCH.md §2.3 (hosted dub API + worker-dub), docs/API.md mục /api/v1.
- Nền tảng thật: container `voxdub-app` 1 CPU / 1 GB RAM (Vibe Host), rate
  limit 5 request/phút/key trên cả 2 route nhận file.
- Quyết định kiến trúc phải giữ: Mongo là nguồn sự thật duy nhất; file job
  nằm trên đĩa cục bộ (nền tảng không có volume bền vững); mã lỗi và HTTP
  status của API công khai không được đổi.

Goal:
- Một upload đúng hạn mức không bao giờ hạ được máy chủ vì bộ nhớ.

Constraints (Guardrails):
1. Không nới `cloud.dub.max.upload.mb` / hạn mức 200 MB của demucs.
2. Không đổi hợp đồng API: vẫn multipart/form-data, vẫn NO_FILE/EMPTY_FILE
   đúng mã cũ, thêm đúng 1 mã mới UPLOAD_TOO_LARGE (413).
3. Hỏng giữa chừng KHÔNG được để lại file cụt, không giữ chỗ quota vĩnh
   viễn, không trừ tiền khách.
4. Không viết cơ chế streaming mới — tái dùng pattern đã chạy thật ở
   `POST /internal/dub-jobs/:id/output` (`pipeline()` + kiểm `truncated`).
5. Không đụng logic tính tiền/định giá; chỉ đổi THỨ TỰ khi thứ tự cũ thành
   bẫy mất tiền.

Scope:
A. Domain model: không đổi.
B. Services/engine: `utils/upload-stream.js` mới (dùng chung);
   `dub-job.service.js` + `render-job.service.js` nhận `fileStream`.
C. API contract: thêm `413 UPLOAD_TOO_LARGE` cho `POST /api/v1/dub` và
   `POST /v1/jobs/demucs`.
D. UI surfaces: không có (API thuần).
E. Tests: `tests/dub-upload-stream.test.js` + cập nhật 3 file test cũ sang
   chữ ký stream.

Audit Before Build:
- `api-v1.js:218` và `jobs.js:37` đều `await data.toBuffer()` rồi truyền
  Buffer xuống service — chặng khách → server là chỗ DUY NHẤT còn buffer,
  chặng worker ⇄ server đã stream từ 2026-08-17 (`ea49859`).
- Gap đo được (không suy đoán): 1 upload 250 MB đẩy RSS tiến trình tăng
  **485,3 MB** (toBuffer gom mảnh rồi `concat` nên đỉnh gấp đôi kích thước
  file). Trong container 1 GB, 2 upload đồng thời là OOM.
- Gap phụ phát hiện khi sửa: `submitDemucsJob` trừ credit TRƯỚC khi ghi
  file. Với buffer thì vô hại (route đã chặn file quá cỡ từ trước), nhưng
  chuyển sang stream thì lỗi 413 xảy ra SAU khi đã trừ → mất tiền khách.

Design Choice:
- 1 hàm dùng chung `writeUploadToDisk(stream, dest, {maxMb, makeError, label})`
  thay vì mỗi service tự viết: 2 route có cùng failure mode, khác nhau chỉ ở
  lớp lỗi domain (`DubJobError`/`RenderJobError`) nên truyền factory lỗi vào.
- Xử lý CẢ 2 hành vi quá-hạn-mức của `@fastify/multipart` (cắt ngang im lặng
  đặt cờ `truncated`, và ném `FST_REQ_FILE_TOO_LARGE`) vì cấu hình mặc định
  khác nhau giữa các phiên bản — không đoán, gom cả hai về 1 lỗi.
- `submitDemucsJob`: đảo thành ghi file → trừ credit → tạo job. Tiền luôn là
  bước sau cùng. Trừ hỏng thì xoá luôn thư mục job (file mồ côi không có
  document trỏ tới nên sweeper không bao giờ dọn được).

Test Plan:
- Unit/Integration: upload 3 MB đi qua HTTP thật → byte trên đĩa khớp CHÍNH
  XÁC; vượt hạn mức → 413 + không file cụt + không job; quota giữ chỗ được
  trả lại; file rỗng → 400 EMPTY_FILE; demucs vượt 200 MB → 413 + số dư Vox
  KHÔNG đổi.
- Regression: mã ngôn ngữ sai vẫn bị chặn trước khi đọc file (không phá
  V43/`93c6878`); toàn bộ suite `control_server`.
- Live verification: đo RSS thật của tiến trình server (đo TỪ NGOÀI qua
  /proc, không đo trong cùng process — lần đo đầu sai vì client fetch chung
  process làm RSS gộp cả bộ đệm phía gửi).

Success Criteria:
- 1 upload 250 MB làm RSS tăng < 50 MB (trước: 485 MB).
- Không có đường nào để lại file cụt hoặc trừ tiền cho upload hỏng.
- 0 regression trên suite control_server.
```

**Kết quả (2026-08-17)**: ✅ Xong. RSS đỉnh khi nhận 250 MB: **485,3 MB →
34,6 MB** (đo lại sau refactor: 36,5 MB) — đo ngoài process qua `/proc/<pid>/
VmRSS`, cùng file, cùng máy, chỉ khác code. 293 test control_server (292
pass, 1 skip, 0 fail). Xem `docs/TEST_LOG.md` mục V44.

### V48 — Sao lưu MongoDB không phụ thuộc nền tảng

```
V48 — Khôi phục khả năng sao lưu đã mất khi rời Coolify (Phase G, 2026-08-17)

Context:
- Mục "Remaining Limits/Follow-ups của Phase G" ở dưới ghi backup hàng ngày
  "ĐÃ XONG 2026-08-15" — nhưng đó là TÍNH NĂNG CỦA COOLIFY, không phải mã
  trong repo. Chuyển nền tảng là mất trắng.
- Nền tảng mới (Vibe Host): không volume bền vững, MCP không có tool sao
  lưu, `list_stacks` trả rỗng, dashboard chỉ bấm tay được.
- DB giữ ví/credit khách, đơn hàng, activation key, khoá nhà cung cấp AI
  (đã mã hoá). Đã mất sạch 1 lần thật trong ngày chuyển nền tảng.

Goal:
- Luôn lấy được một bản sao lưu KHÔI PHỤC ĐƯỢC, không phụ thuộc nền tảng
  đang chạy có hỗ trợ gì hay không.

Constraints (Guardrails):
1. Không dump ra đĩa trong container rồi coi là xong (nền tảng không có
   volume — đó là sao lưu giả vờ).
2. Không giữ cả DB trong RAM (đúng bài học vừa sửa ở V44).
3. Không đưa bí mật ngoài DB (APP_ENCRYPTION_KEY) vào bản dump.
4. Không thêm phụ thuộc dịch vụ ngoài (S3/credential mới) — đó là quyết
   định hạ tầng của chủ dự án, không phải hệ quả của mini-spec này.
5. Sao lưu KHÔNG khôi phục được thì tệ hơn không có → phải test vòng tròn
   xuất → xoá sạch → nhập lại, không chỉ test "endpoint trả về 200".

Scope:
A. Domain model: không đổi.
B. Services/engine: `backup.service.js` — `exportLines()`/`importLines()`.
C. API contract: `GET /v1/admin/backup` (X-Admin-Token, gzip NDJSON).
D. UI surfaces: không (2 script CLI: kéo định kỳ + khôi phục).
E. Tests: `tests/backup.test.js` — trọng tâm là vòng tròn khôi phục.

Design Choice:
- Stream Mongo → NDJSON → gzip → HTTP, không file tạm.
- EJSON thay JSON thường: giữ ObjectId/Date, nếu không thì khôi phục xong
  đứt hết quan hệ giữa collection — và chỉ phát hiện đúng lúc cần nhất.
- Nhập mặc định `upsert` (giữ bản ghi mới hơn bản sao lưu), `--wipe` mới xoá
  sạch: tình huống thường gặp là vá lại phần mất, không phải quay ngược hết.

Success Criteria:
- Xoá sạch DB rồi khôi phục từ bản dump ra đúng dữ liệu cũ, đúng kiểu.
- Không có admin token thì không lấy được một byte nào.
- Nhập lại nhiều lần không nhân đôi dữ liệu.
```

**Kết quả (2026-08-17)**: ✅ Xong phần mã. 5 test mới (vòng tròn xuất → xoá
sạch → nhập lại giữ nguyên số dư ví, `ObjectId`, `Date`). **Còn phụ thuộc 1
việc của chủ dự án**: phải đặt cron gọi `scripts/backup-pull.sh` trên một máy
NGOÀI (laptop/workspace/VPS) — không có máy đó thì vẫn không có bản sao lưu
nào, vì nền tảng không cho đặt lịch và container không giữ file. Xem
`docs/TEST_LOG.md` mục V48.

### V45 — Kết quả job sống sót qua redeploy

```
V45 — Chuyển file job từ đĩa container sang kho bền vững (Phase G, 2026-08-17)

Context:
- Sự cố đo được thật: job `done` → redeploy → file kết quả biến mất trong
  khi Mongo vẫn `done` và quota đã trừ. V44 (`refundLostResult`) mới chỉ
  hoàn tiền — khách vẫn KHÔNG có hàng và phải dub lại từ đầu.
- Vibe Host không có volume bền vững (xác nhận qua dashboard + MCP).
- Quyết định phải giữ: xoá file NGAY sau khi khách tải (chính sách V9);
  TTL `cloud.dub.ttl.hours`; worker Python không chạm DB.

Goal:
- Khách đã trả tiền luôn tải được kết quả trong TTL, kể cả khi máy chủ được
  dựng lại giữa chừng.

Constraints (Guardrails):
1. Không thêm dịch vụ ngoài/credential mới (S3 là quyết định chi phí của
   chủ dự án, không phải hệ quả của mini-spec này).
2. Không nạp cả video vào RAM (giữ nguyên nguyên tắc V44).
3. Không đổi hợp đồng API công khai và không đổi schema DubApiJob.
4. Giữ NGUYÊN lưới an toàn hoàn phí của V44 — kho mới không phải lý do bỏ
   đường phòng vệ cũ.
5. Worker không được biết chi tiết kho (vẫn chỉ HTTP + chuỗi khoá mờ).

Scope:
A. Domain model: không đổi field nào; `inputPath`/`outputPath` đổi ý NGHĨA
   từ đường dẫn đĩa sang khoá kho.
B. Services/engine: `job-storage.service.js` (GridFS), tách lõi
   `writeUploadStream` khỏi `upload-stream.js` để dùng chung cả đĩa lẫn kho.
C. API contract: không đổi.
D. UI surfaces: không có.
E. Tests: `dub-result-durability.test.js` (mô phỏng redeploy thật).

Design Choice:
- GridFS trên chính MongoDB managed — thứ DUY NHẤT trong hệ thống hiện tại
  thật sự sống qua redeploy, dùng được ngay, không thêm biến môi trường.
  Chia chunk 255KB, đọc/ghi theo dòng nên không phá nguyên tắc V44.
- Đánh đổi: DB phình vì chứa video. Chấp nhận vì file sống rất ngắn (xoá
  ngay sau khi giao + TTL 2h). Muốn đổi sang S3 sau này chỉ sửa đúng 1
  module.

Success Criteria:
- Đóng app + xoá sạch đĩa cục bộ + dựng lại trên cùng DB → kết quả vẫn tải
  được nguyên vẹn từng byte.
- Tải xong vẫn dọn file + đánh dấu đã giao, lượt gọi sau KHÔNG hoàn tiền.
- File mất thật (không phải do redeploy) vẫn rơi vào nhánh hoàn phí V44.
```

**Kết quả (2026-08-17)**: ✅ Xong. 3 test mới mô phỏng đúng lượt redeploy
(đóng app → xoá đĩa → dựng lại trên cùng DB) — kết quả tải về khớp từng byte.
**2 bug thật lộ ra khi viết test, đều đã sửa**: (1) listener `end`/`close`
gắn SAU `reply.send()` nên bắt hụt sự kiện với stream GridFS → file không bao
giờ được đánh dấu đã giao, lượt gọi sau sẽ hoàn tiền nhầm cho người đã nhận
đủ hàng; (2) 2 request tải song song chạy đua với việc dọn file → `500` thay
vì `410`, sửa bằng cách trả lời từ `deliveredAt` trước khi chạm kho. 301 test
(300 pass, 1 skip, 0 fail). Xem `docs/TEST_LOG.md` mục V45.

### V49 — Trang thử API lồng tiếng trên trình duyệt

```
V49 — Mặt tiền web cho hạ tầng dub đã có (Phase G, 2026-08-17)

Context:
- V34b dựng xong hạ tầng lồng tiếng chạy 100% trên máy chủ, nhưng cách DUY
  NHẤT chạm vào nó là gõ `curl` — trên thực tế chưa ai dùng.
- Audit thị trường 2026-08-16 chỉ ra điểm yếu lớn nhất KHÔNG phải chất
  lượng mà là ma sát dùng thử: đối thủ kéo-thả trên trình duyệt, VoxDub bắt
  tải .exe Windows.
- website/ đã có sẵn React+Vite, cùng origin với API (không CORS).

Goal:
- Người có API key thử được toàn bộ vòng lồng tiếng bằng chuột, không cần
  dòng lệnh và không cần cài gì.

Constraints (Guardrails):
1. KHÔNG thêm endpoint dub mới — chỉ dùng đúng API đã có.
2. KHÔNG có chế độ "dùng thử không cần key": cho người lạ chạy
   ASR/TTS/ghép video miễn phí là quyết định chi phí + chống lạm dụng của
   chủ dự án, không phải hệ quả kỹ thuật của mini-spec này.
3. Không lưu API key vào localStorage — key rò rỉ là tiền thật của người khác.
4. Không chép tay danh sách ngôn ngữ/giá sang frontend (sẽ trôi lệch) —
   phải đọc từ máy chủ.
5. Không đổi hành vi backend nào ngoài việc lộ thêm dữ liệu ĐỌC công khai.

Scope:
A. Domain model: không đổi.
B. Services/engine: không đổi.
C. API contract: `GET /v1/config/app` trả thêm khối `cloudDub` (bật/tắt, hạn
   mức MB, giá/phút, danh sách ngôn ngữ hợp lệ) — đọc từ chính
   `utils/dub-langs.js`.
D. UI surfaces: trang `/thu-dub` + mục trên thanh điều hướng và footer.
E. Tests: build + suite hiện có (không thêm test render — website chưa có
   hạ tầng test component).

Design Choice:
- Dán key thủ công thay vì đăng nhập: hệ thống KHÔNG có tài khoản người dùng
  (guardrail có sẵn từ V10) nên không có gì để đăng nhập vào.
- XHR thay `fetch` cho lượt upload: chỉ XHR báo được tiến trình tải lên, mà
  file vài trăm MB thì thanh tiến trình là khác biệt giữa "đang chạy" và
  "hình như treo".
- Giữ blob kết quả lại trong tab: máy chủ xoá file NGAY sau lượt tải đầu
  (chính sách V9), gọi lại sẽ ra 410 và trông như hỏng.

Success Criteria:
- Từ trình duyệt: dán key → thấy quota → chọn file → thấy tiến trình → tải
  được video kết quả, không gõ một dòng lệnh nào.
- Danh sách ngôn ngữ trên trang luôn khớp máy chủ (không có bản chép tay).
```

**Kết quả (2026-08-17)**: ✅ Xong phần mã, build sạch (website 31 test,
control_server 301 test, 0 fail). **CHƯA click thử trên trình duyệt thật** —
cần API key có quota (đòi `ADMIN_TOKEN` của chủ dự án). Điểm yếu "người lạ
không thử được nếu không có Windows" mới đóng được MỘT NỬA: có mặt tiền web
nhưng vẫn cần key. Nửa còn lại (dùng thử công khai) là quyết định kinh doanh,
xem Guardrail 2.

### V50 — Cloud render không được im lặng nuốt tiền + nhìn được dung lượng kho

```
V50 — Vá lỗ mất tiền của /v1/jobs/demucs + giám sát kho GridFS (Phase G,
2026-08-17, phát hiện khi rà "còn việc gì chưa làm" sau V49)

Context:
- `/v1/jobs/demucs` trừ Vox NGAY lúc nộp, chính sách ghi rõ "mất tiền cả khi
  job fail, không hoàn" (docs/API.md) — hợp lý khi job THẬT SỰ chạy.
- Nhưng: `sweepExpired` chỉ dọn `done`/`failed`, `sweepStaleRunning` chỉ lo
  `running`. KHÔNG AI đụng tới `queued`.
- Và: trên Vibe Host hiện chỉ có 2 service (`voxdub-app`, `voxdub-dub-worker`)
  — **không có worker render nào**, trong khi `cloud.render.enabled` = true và
  GUI vẫn hiện ô "Xử lý tách nhạc trên cloud".
- V45 đưa file job dub vào GridFS → video giờ nằm trong database, chưa có
  chỗ nào nhìn thấy dung lượng.

Goal:
- Khách không bao giờ mất Vox cho một việc chưa từng chạy, và dung lượng kho
  phải nhìn được trước khi nó thành sự cố.

Constraints (Guardrails):
1. GIỮ chính sách cũ: job đã được worker nhận rồi mới hỏng thì KHÔNG hoàn
   (đã tốn tài nguyên thật). Chỉ hoàn khi chưa có gì chạy.
2. Hoàn tiền phải idempotent — 2 lượt sweep chồng nhau không được cộng 2 lần.
3. Không tự ý bật/tắt tính năng trên prod (cần ADMIN_TOKEN + là quyết định
   của chủ dự án).
4. Không chuyển kho file của render sang GridFS trong đợt này — worker render
   đọc/ghi theo ĐƯỜNG DẪN FILE (thiết kế V12, chưa được chuyển sang HTTP như
   dub-worker), đổi kho mà không đổi transport là làm hỏng một service không
   test được.
5. Hạn mức upload không được tồn tại ở 2 nơi.

Scope:
A. Domain model: không đổi.
B. Services/engine: `renderJob.sweepStaleQueued()` (fail + hoàn Vox),
   `storage.stats()`.
C. API contract: `GET /v1/admin/storage`; 2 config mới
   (`cloud.render.queue.stale.minutes`, `storage.warn.mb`) + 1 config đưa
   hardcode vào (`cloud.render.max.upload.mb`).
D. UI surfaces: không.
E. Tests: 8 test hoàn phí + 5 test dung lượng + 8 test render trang /thu-dub.

Success Criteria:
- Job queued quá ngưỡng: chuyển failed VÀ số dư về đúng như trước khi nộp.
- Job đã chạy/đã xong: tuyệt đối không hoàn.
- Quét nhiều lần: đúng 1 dòng hoàn trong sổ cái.
- Admin nhìn được tổng dung lượng + số file MỒ CÔI (file không còn job trỏ tới).
```

**Kết quả (2026-08-17)**: ✅ Xong. 13 test backend mới (8 hoàn phí + 5 dung
lượng), 8 test render mới cho `/thu-dub`. Tổng: control_server **314 test
(313 pass, 1 skip, 0 fail)**, website **39 test** (từ 31).
**Cần chủ dự án quyết**: hiện KHÔNG có worker render nào chạy → nên (a) triển
khai 1 worker render, hoặc (b) tắt `cloud.render.enabled` để không ai bấm vào
một tính năng không thể chạy. V50 chỉ đảm bảo tiền được trả lại, không thay
được quyết định đó. Xem `docs/TEST_LOG.md` mục V50.

### V51 — Đẩy batch lên worker-dub từ desktop (đóng gap V42 để lại)

```
V51 — Mảnh nối giữa app desktop và hạ tầng xử lý trên máy chủ (Phase G,
2026-08-17)

Context:
- V42 kết luận: batch song song TRÊN MÁY là sai hướng (4GB VRAM đã chạm 96%
  với 1 workload — song song thật = CUDA OOM, không phải "chậm hơn"). Đường
  đúng để tăng thông lượng là `worker-dub` (CPU-only, N bản sao, đã verify
  atomic-safe ở V34a/V34b).
- V42 dừng ở đó và ghi lại nguyên văn: "Chưa thiết kế/xây cách app desktop
  hoặc quy trình vận hành đẩy batch job vào worker-dub để scale thật".
- Hạ tầng phía máy chủ nay đã đủ vững để dựa vào: V44 (không OOM vì upload),
  V45 (kết quả sống qua redeploy), V50 (không âm thầm nuốt tiền).

Goal:
- Chạy được cả loạt video qua hạ tầng máy chủ bằng MỘT lệnh, không tốn GPU
  máy nào và không phải gõ curl.

Constraints (Guardrails):
1. KHÔNG đụng `pipeline.py` hay luồng batch chạy máy — đây là đường thứ hai,
   song song, không thay thế.
2. KHÔNG trộn với `saas_client.py`: khác identity (API key vs token thiết
   bị), khác đơn vị tính tiền (phút vs Vox/segment), máy chủ cũng tách hẳn
   2 middleware.
3. Thiếu cấu hình thì BÁO THẲNG, tuyệt đối không âm thầm rơi về chạy máy —
   người dùng phải biết video của mình được xử lý ở đâu.
4. Chạy lại KHÔNG được nộp lại video đã xong (nộp lại = trả tiền lần hai).
5. Không bao giờ xoá/sửa file nguồn.
6. CLI không được kéo theo GUI/Qt (giữ nguyên cam kết của V22).

Scope:
A. Domain model: không có (client thuần).
B. Services/engine: `autodub/cloud_dub.py` (client HTTP + quota + tải có
   kiểm toàn vẹn), `autodub/cloud_batch.py` (vòng chạy + trạng thái + báo cáo).
C. API contract: không thêm endpoint nào — dùng đúng `/api/v1/*` đã có.
D. UI surfaces: CLI `voxdub cloud-batch` (GUI để sau, đúng thứ tự V22→V25).
E. Tests: 12 test trên máy chủ HTTP THẬT dựng tại chỗ.

Design Choice:
- Tuần tự ở phía client CÓ CHỦ ĐÍCH: máy chủ chặn 5 lượt nộp/phút/key và
  hiện chỉ 1 worker — bắn song song chỉ dời chỗ chờ và thêm rủi ro rối
  trạng thái. Chỗ đáng song song là SỐ BẢN SAO worker (quyết định hạ tầng).
- 3 trạng thái kết thúc chứ không 2: `success` / `failed` / **`refunded`**.
  Máy chủ mất kết quả rồi hoàn phí (V44/V45) KHÔNG phải video hỏng — gộp vào
  `failed` sẽ khiến người vận hành tưởng video lỗi và bỏ đi.
- Tải về ghi `.part` rồi `replace()`: máy chủ XOÁ kết quả ngay sau lượt tải
  đầu, nên một file dở mang đúng tên thật là mất hàng vĩnh viễn (lượt sau
  thấy "đã có" và bỏ qua).

Success Criteria:
- 1 lệnh chạy hết cả thư mục, kết quả về đủ, byte khớp.
- Ngắt giữa chừng rồi chạy lại: không nộp lại video đã xong.
- Hết quota: dừng nộp, báo rõ số video CHƯA chạy, không ăn 402 hàng loạt.
- Tải dở: không để lại file mang tên thật, cũng không để lại rác `.part`.
```

**Kết quả (2026-08-17)**: ✅ Xong code + 12 test (chạy trên máy chủ HTTP thật,
không mock `requests`). Baseline trước/sau: **936 → 948 pass**, đúng 12 test
mới, 0 regression. **Chưa chạy thật đầu-cuối** — cần API key có quota (đòi
`ADMIN_TOKEN` của chủ dự án). Xem `docs/TEST_LOG.md` mục V51.

### V52 — Đường ống cho cloud-batch (đóng gap thông lượng V51 để lại)

```
V52 — Worker máy chủ không được nằm không giữa 2 video (Phase G, 2026-08-17)

Context:
- V51 mở đường đẩy batch lên máy chủ, nhưng chạy THUẦN TUẦN TỰ: nộp → chờ
  xong → tải → mới nộp video kế tiếp.
- Hệ quả: suốt thời gian upload video N+1, worker trên máy chủ rảnh. Với
  file vài trăm MB qua đường truyền nhà, đó là phần lớn thời gian.
- Mà mục tiêu gốc của V42 chính là THÔNG LƯỢNG. V51 mới chỉ chuyển chỗ xử lý
  chứ chưa tăng thông lượng thật.
- V43 (giữ chỗ quota theo phút) là ràng buộc phải tôn trọng: mỗi job đứng
  chờ đã khoá trước một phần quota.

Goal:
- Worker máy chủ luôn có việc sẵn để làm ngay khi xong video trước.

Constraints (Guardrails):
1. KHÔNG chạy song song phía máy chủ — worker vẫn xử lý từng job một. Thứ
   được cắt bỏ là thời gian chết, không phải đổi mô hình xử lý.
2. Hàng đợi phải NGẮN và có trần: nộp trước vô hạn là tự khoá quota của
   chính mình cho những video có thể chẳng bao giờ tới lượt.
3. Hết quota giữa chừng KHÔNG được biến thành "bỏ luôn video còn lại" — job
   xong sẽ trả lại chỗ (V43), phải thử lại trong cùng lượt chạy.
4. Mọi bảo đảm của V51 giữ nguyên: resume-safe, 3 trạng thái kết thúc, tải
   dở không để lại file mang tên thật, không đụng file nguồn.
5. `--queue-ahead 1` phải cho lại đúng hành vi tuần tự cũ (đường lui).

Scope:
A/B. `run_cloud_batch` đổi từ vòng lặp thẳng sang bơm-và-rút hàng đợi.
C. Không đổi API máy chủ.
D. CLI thêm `--queue-ahead`.
E. Tests: 3 test mới cho đúng phần V52 thêm vào.

Design Choice:
- Đo bằng TRÌNH TỰ SỰ KIỆN chứ không bằng đồng hồ: test khẳng định "job2
  được nộp TRƯỚC khi job1 tải xong". Đo thời gian sẽ thành test chập chờn
  phụ thuộc máy chạy, còn thứ tự thì hoặc đúng hoặc sai.
- Video bị 402 chặn được trả lại hàng đợi (`next_index -= 1`) chứ không đánh
  dấu hỏng: nó chưa từng được thử thật sự, chỉ là chưa còn chỗ.

Success Criteria:
- Video N+1 đã nộp trước khi kết quả video N được tải về.
- Số job chờ đồng thời không bao giờ vượt `queue_ahead`.
- Quota được giải phóng thì video bị chặn phải chạy nốt trong cùng lượt.
```

**Kết quả (2026-08-17)**: ✅ Xong. 16 test (13 của V51 + 3 mới), baseline
**936 → 952 pass**, 0 regression. **Chưa chạy thật đầu-cuối** — cần API key.
Lưu ý khi chạy thật: lợi ích tỉ lệ với thời gian upload; mạng nhanh + video
nhỏ thì gần như không khác, mạng nhà + video vài trăm MB thì cắt được gần
trọn thời gian upload khỏi tổng thời gian chạy.

## Phase H — Trải nghiệm người dùng cuối (2026-08-18+, chủ dự án chọn sau khi xem app thật)

Chủ dự án xem lại app v3.0.1 đang chạy trên Windows và chọn 4 hướng, theo thứ
tự: (1) cập nhật bản mới → (2) nghe thử 30 giây → (3) hồ sơ nhân vật xuyên
tập → (4) extension làm mặt tiền. Hai hướng bị GẠT có lý do rõ: sinh video AI
từ kịch bản (sản phẩm khác, cần GPU farm, không có lợi thế cạnh tranh) và dub
thời gian thực trên trình duyệt (kiến trúc streaming, gần như sản phẩm thứ 2).

### V55 — Huỷ job thật cho chế độ máy chủ

*(Mục này ghi bổ sung ngày 2026-08-18 — mini-spec V55 ship ngày 17-08 mà chỉ
có mục trong `TEST_LOG.md`, bảng roadmap và phần spec đều bỏ sót. Nội dung
dưới đây tóm tắt từ TEST_LOG, không phải spec viết trước lúc build.)*

Xuất phát từ đúng giới hạn V53/V54 tự ghi ra: *"chưa có nút Dừng thật cho chế
độ máy chủ — job đã nộp vẫn chạy và vẫn bị tính tiền dù người dùng đóng app"*.
Ai lỡ nộp nhầm 20 video thì không có cách nào chặn.

Ba quyết định đáng nhớ:

1. Điều kiện `apiKeyId` nằm TRONG câu update chứ không kiểm ở tầng route —
   huỷ job của người khác nặng hơn hẳn xem trộm, nên phải đi cùng một lệnh
   nguyên tử chứ không dựa vào thứ tự if/else.
2. 409 gộp 3 ca (không tồn tại / không phải của bạn / đã kết thúc) — phân biệt
   sẽ để lộ jobId người khác có tồn tại hay không, chỉ cần dò là biết.
3. Không cần cơ chế hoàn tiền: `chargeDubUsage` chỉ chạy trong `completeJob`,
   mà `completeJob` đòi `status:'running'` — job đã `cancelled` thì worker báo
   xong muộn bị từ chối thẳng.

**Kết quả (2026-08-17)**: ✅ Xong code + 10 test (8 Node + 2 Python). **CHƯA
live-verify trên prod** — cần API key thật + một job đang chạy thật. Xem
`docs/TEST_LOG.md` mục V55.

### V56 — Nghe thử 30 giây trước khi chạy cả video

```
V56 — Dub thử một đoạn đầu để duyệt giọng/xưng hô (Phase H, 2026-08-18)

Context:
- Quy trình hiện tại: wizard 6 bước → chạy hết video 20 phút → mới phát hiện
  giọng không hợp hoặc xưng hô sai → làm lại từ đầu. Đây là vòng lặp lãng phí
  lớn nhất của người dùng, thấy rõ khi xem app thật.
- `pipeline.py:360` (`_resolve_video`) là điểm DUY NHẤT giải quyết nguồn video
  cho CẢ file local lẫn link (link đã tải xong ở bước này). Cắt clip ngay sau
  đó là tái dùng toàn bộ pipeline phía sau, không viết logic mới.
- `_unique_new_folder_name` (V42) đã lo chống trùng thư mục.

Goal:
- Nghe được kết quả lồng tiếng của 30 giây đầu trước khi cam kết chạy cả video.

Constraints (Guardrails):
1. KHÔNG viết pipeline riêng cho preview — cắt clip rồi chạy đúng pipeline cũ.
2. Thư mục preview phải PHÂN BIỆT ĐƯỢC với dự án thật, không bao giờ bị nhầm
   là bản cuối (người dùng đăng nhầm bản 30 giây lên kênh là hỏng thật).
3. KHÔNG đụng vào nhánh `resume_dir` — preview luôn là lượt chạy mới.
4. Tính phí trung thực: preview vẫn tốn Vox theo số câu trong đoạn đó, phải
   nói trước chứ không được ngầm hiểu là miễn phí.
5. Clip cắt hỏng (ffmpeg lỗi/video ngắn hơn N giây) phải báo rõ, KHÔNG âm thầm
   rơi về chạy full — người dùng đang cố tránh đúng chuyện đó.
6. Video ngắn hơn N giây thì preview = cả video, không phải lỗi.

Scope:
A. Domain model: `DubRequest.preview_seconds: int = 0`.
B. Services/engine: `autodub/preview.py` (cắt clip bằng ffmpeg, giữ nguyên
   codec khi có thể); chèn 1 bước vào `_run_impl` ngay sau `_resolve_video`.
C. API contract: không đổi (thuần desktop).
D. UI surfaces: CLI `--preview-seconds N`; GUI nút "Nghe thử 30 giây".
E. Tests: cắt đúng tham số, thư mục tách biệt, video ngắn, ffmpeg hỏng.

Design Choice:
- Cắt bằng `-t N` + `-c copy` (không mã hoá lại) → gần như tức thì kể cả với
  video 2 GB. `-c copy` cắt theo keyframe nên độ dài có thể lệch chút — chấp
  nhận được vì đây là bản nghe thử, không phải bản giao.
- Thư mục có hậu tố `-preview30s` NGAY TRONG TÊN: người dùng mở thư mục kết
  quả là biết ngay cái nào là thử, không phải đoán theo thời gian tạo.

Test Plan:
- Unit: dựng lệnh ffmpeg đúng; video ngắn hơn N vẫn chạy; ffmpeg lỗi → ném
  lỗi rõ chứ không trả về đường dẫn rác.
- Integration: `DubRequest(preview_seconds=30)` tạo thư mục có hậu tố và dùng
  clip làm nguồn; `preview_seconds=0` giữ NGUYÊN hành vi cũ (0 regression).
- Live: cắt thật bằng ffmpeg trên video thật, kiểm thời lượng bằng ffprobe.

Success Criteria:
- Chạy preview 30s trên video dài không tốn thời gian tải/tách nhạc cả video.
- Không có đường nào khiến bản preview bị nhầm là bản cuối.
- `preview_seconds=0` → mọi thứ y như trước.
```

### V57 — Hồ sơ nhân vật xuyên tập

```
V57 — Cùng một nhân vật giữ cùng một giọng qua nhiều tập (Phase H, 2026-08-18)

Context:
- Chủ dự án muốn "đồng bộ nhân vật + giọng điệu". Bản khả thi KHÔNG phải sinh
  video AI (sản phẩm khác, cần GPU farm) mà là: dub cả một series thì nhân
  vật A phải giữ NGUYÊN giọng A ở mọi tập. Hiện tập nào giọng nấy — xem 5 tập
  là thấy loạn.
- Mảnh ghép đã có, chỉ thiếu lớp ghi nhớ xuyên tập:
  * `diarization.py` tách người nói (V26)
  * `diarization_voice_match.estimate_speaker_genders()` ước lượng F0 từng
    người nói (V36) — F0 trung vị là ĐẶC TRƯNG SO SÁNH ĐƯỢC giữa các tập
  * `voice_assign.assign_voices_by_gender()` gán giọng (V36)
  * `Settings.translate_pronouns` / `translate_glossary` — xưng hô, thuật ngữ
- Điểm chốt kỹ thuật: nhãn diarization (`SPEAKER_00`…) KHÔNG ổn định giữa các
  file — tập 2 gọi cùng một người là `SPEAKER_01` là chuyện bình thường. Nên
  không thể khớp theo nhãn; phải khớp theo ĐẶC TRƯNG GIỌNG.

Goal:
- Dub tập tiếp theo của một series thì nhân vật cũ tự nhận lại đúng giọng cũ,
  và xưng hô/thuật ngữ của series được áp lại, không phải nhập lại từ đầu.

Constraints (Guardrails):
1. KHÔNG thêm model AI nhận dạng người nói. Dùng đúng F0 mà V36 đã tính —
   thêm model là đổi hẳn hạng mục chi phí/cài đặt.
2. Khớp SAI tệ hơn không khớp: ngoài ngưỡng tin cậy thì coi là nhân vật MỚI,
   không gán bừa (cùng tinh thần "vùng mù mờ thì không đoán" của V36).
3. Một nhân vật chỉ khớp với MỘT người nói trong cùng một tập (1-1).
4. Hồ sơ là dữ liệu của người dùng: sửa tay được, hỏng file không được làm
   sập lượt dub (degrade về hành vi V36 cũ).
5. Không có hồ sơ → hành vi y hệt hiện tại (0 regression).
6. Không tự động tạo/sửa hồ sơ khi người dùng không yêu cầu.

Scope:
A. Domain model: `Character` (tên, giọng, F0 trung vị, giới tính) +
   `CharacterProfile` (tên series, danh sách nhân vật, xưng hô, thuật ngữ,
   ngữ cảnh) lưu JSON.
B. Services/engine: `autodub/character_profile.py` — nạp/ghi, khớp người nói
   theo F0 (1-1, có ngưỡng), cập nhật sau mỗi tập.
   `diarization_voice_match.estimate_speaker_pitch()` (tách ra từ hàm đoán
   giới tính, KHÔNG tính F0 hai lần).
C. API contract: không đổi (thuần desktop).
D. UI surfaces: CLI `--character-profile <tên>`. GUI để đợt sau (đúng nếp
   CLI-first V22→V25).
E. Tests: khớp đúng/không khớp/1-1, hồ sơ hỏng, 0 regression khi không dùng.

Design Choice:
- **Khớp theo F0 trung vị** — đặc trưng DUY NHẤT đã có sẵn và so sánh được
  giữa các file. Thô, nhưng đúng tinh thần dự án: dùng tín hiệu số học đơn
  giản đủ dùng thay vì kéo thêm một model.
- **Ngưỡng + ghép tham lam theo khoảng cách tăng dần**, một-đối-một: cặp gần
  nhau nhất khớp trước, ai còn lại mà lệch quá ngưỡng thì thành nhân vật mới.
- **Ghi nhớ bằng trung bình động** thay vì đè giá trị mới: một tập thu âm tệ
  không được phép kéo lệch hồ sơ đã đúng qua nhiều tập.

Test Plan:
- Unit: khớp đúng người khi F0 gần; KHÔNG khớp khi lệch quá ngưỡng; 1-1 khi 2
  người nói cùng gần một nhân vật; nhân vật mới được thêm; trung bình động;
  hồ sơ hỏng/thiếu file → degrade chứ không nổ.
- Integration: `--character-profile` áp giọng cũ; không truyền → y hệt V36.
- Live: chưa (cần diarization thật trên nhiều tập của một series).

Success Criteria:
- Tập 2 của cùng một series: nhân vật cũ nhận lại đúng giọng đã dùng ở tập 1.
- Người nói lạ không bị gán nhầm vào nhân vật có sẵn.
- Không truyền hồ sơ → không có gì thay đổi so với hôm nay.
```

### V58–V60 — Hoàn thiện hồ sơ nhân vật (3 quyết định của chủ dự án)

```
V58 — Quy ước dịch của series đè cài đặt chung (Phase H, 2026-08-18)
V59 — Khớp nhân vật bằng speaker embedding thay F0
V60 — Hồ sơ nhân vật lên GUI

Context:
- V57 để lại đúng 3 giới hạn, chủ dự án chốt cả 3 trong một lượt:
  (1) xưng hô/thuật ngữ trong hồ sơ chưa áp → "hồ sơ đè cài đặt chung";
  (2) F0 là heuristic thô → "dùng speaker embedding, thêm model";
  (3) chưa có GUI → "làm trong GUI".
- Phát hiện quyết định V59: `diarize_worker.py` chạy pyannote
  `speaker-diarization-3.1`, mà pipeline đó **vốn đã tính embedding bên
  trong** để gom nhóm người nói — trước V59 nó bị vứt đi. Nên có embedding
  thật mà KHÔNG phải thêm model nào, không tốn thêm thời gian xử lý.

Goal:
- Nhân vật được nhận lại chính xác (không lẫn hai người cùng giới), quy ước
  của series tự áp, và người dùng cuối chạm được từ giao diện.

Constraints (Guardrails):
1. Hồ sơ đè cài đặt chung, NHƯNG chỉ với trường hồ sơ CÓ điền — trường trống
   không được xoá cài đặt của người dùng.
2. Sửa cấu hình TẠI CHỖ cho lượt chạy, KHÔNG ghi xuống `.env`.
3. Embedding và F0 là hai thang đo khác nhau — không trộn trong cùng một
   lượt xếp hạng.
4. Hồ sơ lập trước V59 (không có embedding) phải dùng tiếp được, không bắt
   làm lại.
5. pyannote bản cũ không hỗ trợ `return_embeddings` → degrade về F0, không
   chết.
6. Ô hồ sơ trên GUI chỉ hiện khi tách người nói đang bật (nếp V53).

Design Choice:
- **Embedding xét TRƯỚC và trọn vẹn, xong mới tới F0**: cosine 0.9 và lệch
  3Hz không so sánh được với nhau, gộp chung một bảng xếp hạng là sai.
- Ngưỡng cosine 0.72 — pyannote cho cùng người thường >0.8, người khác <0.5;
  0.72 nghiêng về phía thận trọng vì khớp sai tệ hơn không khớp.
- Embedding lưu dạng đã chuẩn hoá, cập nhật bằng trung bình động rồi chuẩn
  hoá lại (cùng lý do làm mượt F0).
- GUI dùng Ô NHẬP CHỮ chứ không phải danh sách chọn: gõ tên series mới là
  tạo hồ sơ mới, gõ lại tên cũ là dùng tiếp — không cần màn quản lý riêng.

Success Criteria:
- Hai người cùng giới chênh F0 dưới ngưỡng vẫn được tách đúng bằng embedding.
- Hồ sơ v1 (chưa có embedding) vẫn khớp được bằng F0.
- Chọn hồ sơ thì xưng hô của series thắng cài đặt chung, nhưng không xoá gì.
```

**Kết quả (2026-08-18)**: ✅ Cả 3. **2 bug thật tìm được**: (a) tên hồ sơ
tiếng Việt bị băm mất dấu nên «Phim Cổ Trang» và «Phim Có Trang» cùng ra một
file — hai series ghi đè hồ sơ của nhau; (b) `_apply_character_profile` đọc
`req` ngoài scope (đã nêu ở V57). 1230 test, 0 fail. Xem `docs/TEST_LOG.md`.

### V62–V64 — Ba việc chủ dự án chọn sau khi xem app thật

```
V62 — Trang quản lý hồ sơ nhân vật (Phase H, 2026-08-18)
V63 — "Chạy như lần trước": bỏ qua 6 bước wizard cho việc lặp hằng ngày
V64 — Báo cáo chất lượng chủ động: "5 câu đáng sửa nhất" + mở thẳng Editor

Context:
- V57–V61 dựng xong phần máy của hồ sơ nhân vật nhưng muốn đổi tên
  `SPEAKER_00` thành «Lý Tứ» vẫn phải mở file JSON bằng tay.
- Nháp (`draft_project.json`) ĐÃ lưu sẵn toàn bộ lựa chọn và tự nạp lúc mở
  app — thứ còn thiếu chỉ là đường tắt tới nút chạy.
- Trang Báo cáo chất lượng liệt kê MỌI câu có vấn đề: video 300 câu ra 40
  dòng, không trả lời được câu hỏi thật "sửa cái nào trước?".

Constraints (Guardrails):
1. V62 KHÔNG cho tạo hồ sơ rỗng — hồ sơ sinh ra khi dub tập đầu.
2. Cột số liệu hệ thống đo (số tập, cách nhận diện) phải KHOÁ, gõ tay vào chỉ
   tạo dữ liệu sai.
3. Tên nhân vật trùng/rỗng phải bị chặn khi lưu — chúng phá chính cơ chế khớp.
4. V63 chỉ hiện khi THẬT SỰ có lần chạy trước.
5. V64 không được đưa câu "không có gì để sửa" vào danh sách đáng sửa.
6. Quy tắc xếp hạng phải là hàm thuần, test được, không chôn trong code dựng
   bảng.

Design Choice:
- V62 hiện cột "Nhận diện" nói rõ nhân vật nào khớp bằng embedding (chính
  xác) và nhân vật nào chỉ có cao độ (dễ lẫn) — người dùng biết chỗ nào đáng
  nghi thay vì tin mù.
- V64 thang điểm CỐ Ý thô và giải thích được: chồng tiếng > đọc nhanh > dài
  quá chỗ trống, xếp theo mức khó chịu KHI XEM. Công thức tinh vi mà không ai
  kiểm chứng nổi thì tệ hơn.
- Thứ tự xếp hạng ổn định (cùng điểm → theo số câu): hai lần mở cùng một báo
  cáo phải ra cùng thứ tự, nếu không người dùng tưởng dữ liệu đang đổi.

Success Criteria:
- Đổi tên nhân vật trong GUI, tập sau vẫn nhận đúng người (embedding/số tập
  không mất).
- Chọn video xong bấm 1 nút là chạy với đúng cấu hình lần trước.
- Mở báo cáo là thấy ngay 5 câu nên sửa, bấm là vào thẳng Editor.
```

**Kết quả (2026-08-18)**: ✅ Cả 3. **1 bug tự soi ra và sửa**: đổi series khi
đang sửa dở làm mất trắng thay đổi, không một lời cảnh báo. 1265 test Python
(+32), 325 test Node, 0 fail. Xem `docs/TEST_LOG.md`.

### Định hướng thị trường (audit 2026-08-16, tham khảo cho roadmap Phase G/H)

- Khảo sát Rask AI/ElevenLabs Dubbing/HeyGen/Camb.ai/Dubverse/Vidnoz (auto-dub)
  + Vrew/Opus Clip/Klap/CapCut (auto-video rộng hơn) — không phải mini-spec,
  chỉ ghi lại để định hướng việc chọn mini-spec tiếp theo:
  - **Đã ngang/hơn đối thủ**: voice cloning (V35), tách+phối lại nhạc nền
    theo mood (Demucs, V37 — hiếm, hầu hết đối thủ chỉ duck nhạc gốc), editor
    review trước khi render.
  - **Lip-sync**: PoC V32a thành công 1/3 mẫu, 794s/10.7s video, sát trần
    VRAM 4GB — nhưng cả ngành (kể cả ElevenLabs, YouTube Aloud) cũng chưa
    hoàn thiện, KHÔNG phải chỗ VoxDub thua kém tương đối.
  - **Bài học Vrew** (đối chuẩn gần nhất — tool auto-dub 1 ngôn ngữ, 1.2M
    user): thắng bằng làm SÂU 1 ngôn ngữ, không phải breadth tính năng —
    đại từ xưng hô/ngữ vực tiếng Việt là lợi thế thật mà tool 100+ ngôn ngữ
    không tối ưu sâu nổi.
  - **2 gap thật chủ dự án chọn ưu tiên tiếp** (2026-08-16): (1) batch xử lý
    song song không người canh (hiện tuần tự do tranh chấp GPU — trần thông
    lượng thật nếu muốn scale content-automation); (2) nâng chất lượng đọc
    hiểu nguồn tiếng Anh/tiếng Trung để dịch tiếng Việt tự nhiên hơn (khác
    V39 — V39 sửa mạch xưng hô GIỮA CÁC LÔ cùng video, đây là chất lượng
    HIỂU NGUỒN theo từng ngôn ngữ nguồn cụ thể).

### Remaining Limits / Follow-ups của Phase G

- **[HẾT HIỆU LỰC TỪ 2026-08-17 — đọc cảnh báo trước khi tin mục này]**
  Toàn bộ đoạn dưới đây mô tả monitoring + backup **của Coolify**. Ngày
  2026-08-17 dự án chuyển sang Vibe Host nên **mất trắng cả hai**: không còn
  Sentinel, không còn backup hàng ngày. Đừng đọc lướt thấy "ĐÃ XONG" rồi tưởng
  dữ liệu vẫn được sao lưu. Thay thế: mini-spec **V48** (endpoint
  `GET /v1/admin/backup` + `scripts/backup-pull.sh`) — nhưng V48 là sao lưu
  KÉO, phải có một máy NGOÀI đặt cron gọi nó thì mới thật sự có bản sao lưu.
- **[ĐÃ XONG 2026-08-15, chỉ đúng trên Coolify] `control_server` production
  monitoring/backup cơ bản** — bật `health_check_enabled` đúng path `/health` (mặc định Coolify
  để tắt, trỏ `/`) — Coolify's Sentinel (đã bật sẵn cấp server) giờ có tín
  hiệu healthy/unhealthy chính xác. Backup MongoDB hàng ngày (3h sáng, lưu
  local trên server, giữ 14 bản/30 ngày) — live-verify thật bằng cách đổi
  lịch chạy thử mỗi 2 phút, xác nhận 2 lượt `status: success` với file thật
  trên đĩa, rồi đặt lại lịch thật. **Giới hạn còn lại có chủ đích**: backup
  chỉ lưu CÙNG server với database (bảo vệ khỏi lỗi DB/xoá nhầm, KHÔNG bảo
  vệ khỏi mất cả server) — nâng cấp lên backup ngoài (S3) cần credential
  bên ngoài, đây là quyết định hạ tầng/ngân sách của chủ dự án, chưa làm.
  Cảnh báo chủ động (Telegram/email khi server down) không tìm được endpoint
  API công khai của Coolify để cấu hình — có thể chỉ làm được qua UI, chưa
  xác nhận.
- **[ĐÃ XONG 2026-08-15] Runbook deploy `control_server`** —
  `control_server/docs/DEPLOY_RUNBOOK.md` (mới), ghi lại đầy đủ quy trình
  thật + mọi lỗi thật đã gặp lúc deploy lần đầu (token thiếu quyền
  `workflow`, domain/build_pack phải PATCH tách 2 lần, biến môi trường bị
  nhân đôi qua `envs/bulk`, DNS domain tuỳ chỉnh trỏ sai IP, thiếu seed nhà
  cung cấp AI dịch). Link từ `control_server/README.md`.
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
- **V37 — PySceneDetect (phát hiện điểm nhấn từ chuyển cảnh hình ảnh)** — Scope B
  gốc của mini-spec nêu cả transcript timing LẪN PySceneDetect; PoC chỉ làm phần
  transcript (dấu câu/khoảng lặng, đã đủ tín hiệu rẻ cho GUI chọn điểm chèn SFX).
  PySceneDetect để dành cho đợt sau nếu người dùng thấy danh sách điểm nhấn hiện
  tại còn thiếu (vd cắt cảnh không đi kèm câu thoại nhấn mạnh).
- **V37 — Epidemic Sound Partner API** — track kinh doanh (đàm phán đối tác), chủ
  dự án tự theo dõi tiến độ; mini-spec chỉ ghi nhận trạng thái, không có code.
- **V37 — Không phải bước tự động trong pipeline chính** — Scope C gốc đề xuất 1
  bước MỚI, tuỳ chọn trong `pipeline.py` (chạy cùng lượt dub); bản build thực tế
  là 1 hành động THỦ CÔNG ở Editor (sinh → nghe thử → áp dụng), nhất quán hơn với
  Constraint 5 (luôn cho nghe thử trước khi chốt) vì pipeline tự động khó chèn
  bước duyệt giữa chừng. Nếu sau này muốn tự động hoá gợi ý (không phải tự động
  áp dụng), đó là 1 mini-spec riêng.

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

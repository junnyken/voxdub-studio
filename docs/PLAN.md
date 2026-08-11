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

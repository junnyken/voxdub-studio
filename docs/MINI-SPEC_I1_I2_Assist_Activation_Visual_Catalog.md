# MINI-SPEC I1+I2 — Kích hoạt Assist & Từ điển Chỉ đạo Hình ảnh v1

- **Parent phase:** Phase I — Kịch bản thành chỉ đạo hình ảnh
- **Scope IDs:** I1 (Kích hoạt nền trợ lý AI `assist`) + I2 (Visual Direction Catalog v1)
- **Author:** Perplexity
- **Date:** 2026-09-22
- **Status:** Ready for audit and implementation after I0 + I0-FDE closure

---

## Context

### Tài liệu bắt buộc phải đọc trước khi sửa mã

- `FEATURES.md` (bản mới nhất sau khi I0/I0-FDE đóng)
- `MINI_SPEC_PLAYBOOK.md`
- `docs/ARCH.md`
- `docs/API.md`
- `docs/TEST_LOG.md`
- Schema/model/API hiện có cho nhà cung cấp AI, vai trò provider, ví Vox, hold/commit/refund, cache và thống kê trợ lý
- Các implementation hiện có của `explain_error`, `character_name`, `tighten_line`, `scene_script`
- Brand Profile (H1), Flow Blueprint (H2), Brand Script (H3), Storyboard/H4
- Trang quản trị cấu hình AI provider và UI hiện có cho các tác vụ trợ lý

### Trạng thái hiện tại đã xác nhận

1. Cổng gọi AI đã có bốn vai trò provider: `translate`, `content`, `assist`, `image`.
2. Các tác vụ trợ lý đã có contract/code/UI ở các mức khác nhau, gồm `explain_error`, `character_name`, `tighten_line`, `scene_script`, `music_suggest`, `scene_continuity` và các tác vụ khác.
3. `assist` đã được đăng ký như một vai trò trong hệ thống; phần còn thiếu là bản ghi nhà cung cấp thật kèm API key/model trên trang quản trị. Không được viết lại provider framework hoặc "đăng ký lại role `assist`".
4. Trong trạng thái trước I1, các tác vụ `assist` có thể rơi sang vai `translate`, chạy được nhưng đắt hơn khoảng 25 lần. Đây không phải cấu hình production chấp nhận được.
5. Cổng trợ lý đã có các lớp bảo vệ chi phí: danh sách tác vụ đóng, trần ký tự, hạn mức ngày theo máy và cache theo nội dung; gọi lại cùng input phải không trừ tiền lần hai.
6. Các prompt AI nằm ở máy chủ; app gửi tên tác vụ thay vì gửi system prompt. Đây là quyết định kiến trúc phải giữ nguyên.
7. `scene_script` hiện gợi ý câu dẫn và nhịp cho từng cảnh; đây là hook gần nhất cho Phase I nhưng chưa được phép tự biến thành `scene_director` hoặc tạo Visual Direction Sheet trong MINI-SPEC này.
8. H3 đã sinh kịch bản Brand có lời đọc, chữ trên hình và mô tả cần quay gì theo từng segment; H3 có các gate chống sao chép/cụm cấm. H4 đã dựng slideshow theo thời lượng TTS thật. H4d vẫn là cửa ảnh bị khóa cho tới khi calibration tuân thủ hoàn tất.
9. Hiện chưa có một catalog có kiểm soát, phiên bản hóa, map đúng khả năng H4 cho các chỉ đạo góc khung/bố cục/chuyển động/nhịp/chuyển cảnh/màu-ánh sáng.
10. H4 hiện là luồng ảnh tĩnh/slideshow. Vì vậy những từ như "camera movement", "zoom", "transition" chỉ được đưa vào catalog nếu có mapping thực tế sang ảnh tĩnh, Ken Burns, crop/scale, fade/cut hoặc hành vi H4 đã hỗ trợ. Không được mô tả/hứa hẹn chuyển động camera vật lý hay hiệu ứng video AI không tồn tại.
11. I0 + I0-FDE đã đóng: bản `.exe` đóng gói đã được kiểm qua clean-install, same-parent upgrade và dub thực qua artifact. I1+I2 không được làm suy yếu các release/packaging/deploy gate này.

### Quyết định kiến trúc phải giữ nguyên

- Không import/cài engine AI nặng vào tiến trình chính để làm I1 hoặc I2.
- Không cho client gửi system prompt tự do; prompt thuộc về server theo task allow-list.
- Không để UI tự suy ra giá hay tự trừ Vox; mọi giá/hold/commit/refund đi qua cổng server hiện có.
- Không dùng vai `translate` làm fallback im lặng cho `assist` trong production.
- Không tạo dashboard/provider framework mới nếu trang quản trị/provider registry hiện có đã đáp ứng.
- Không bật H4d, không cấu hình provider `image`, không sinh ảnh, không gọi tác vụ có phí mà không có xác nhận phù hợp.
- Không biến catalog thành lớp model/AI mới; I2 là dữ liệu có schema + mapping rõ ràng, chưa gọi AI để sinh visual direction.

---

## Goal

Đưa vai `assist` vào trạng thái chạy thật, đo được và tính phí trung thực; đồng thời tạo một Visual Direction Catalog v1 có kiểm soát, phiên bản hóa và chỉ chứa các chỉ dẫn hình ảnh mà H4 hiện có thể hiểu hoặc render một cách trung thực.

---

## Constraints (Guardrails)

1. **Audit trước build.** Không thêm provider record, đổi fallback, tạo catalog hoặc sửa UI trước khi audit contract/provider registry, cost pipeline, cache semantics, schema H3/H4 và mapping render hiện có.
2. **`assist` là cấu hình, không phải framework mới.** Nếu provider registry/admin UI đã có role `assist`, chỉ bổ sung cấu hình/provider record cần thiết; không tạo role/API/collection thứ hai trùng nghĩa.
3. **Không fallback im lặng sang `translate`.** Khi `assist` chưa có provider khả dụng hoặc provider lỗi, trả trạng thái/lỗi theo contract hiện có (dự kiến `503`), kèm hướng dẫn hành động; không tiêu giá `translate` mà UI vẫn gọi là trợ lý bình thường.
4. **Không hứa miễn phí sai.** `explain_error` là ngoại lệ miễn phí theo chính sách hiện có; mọi task khác phải hiển thị đúng giá trước xác nhận nếu flow hiện tại yêu cầu xác nhận. Không sửa tooltip/câu chữ độc lập với nguồn tính giá server.
5. **Tiền phải idempotent.** Cùng task + cùng payload chuẩn hóa + cùng ngữ cảnh cache phải trả cache hit hoặc cơ chế equivalent và không trừ thêm Vox. Không đánh đổi tính đúng tiền để chạy thử nhanh.
6. **Không đổi nghĩa task cũ.** `explain_error`, `character_name`, `tighten_line`, `scene_script` giữ nguyên objective/contract; I1 chỉ kích hoạt và kiểm chứng chúng. `scene_script` không được đổi thành `scene_director`.
7. **Catalog chỉ chứa khả năng thật.** Mỗi value của I2 phải có mapping có kiểm chứng sang H4 hiện tại hoặc trạng thái rõ `advisory_only` không được xuất hiện trong UI lựa chọn render. Không thêm drone shot, dolly zoom, rack focus, whip pan, 3D tracking, motion capture, camera handheld giả lập, hay video-AI effects.
8. **Không sao chép phong cách nguồn.** Catalog mô tả kỹ thuật/phổ quát (ví dụ "cận", "zoom vào chậm", "fade nhẹ"), không là thư viện style nhận diện, không lưu/copy bố cục, caption hay nhịp cụ thể của video tham khảo.
9. **Catalog phải là dữ liệu đóng và versioned.** Server/schema chỉ chấp nhận enum từ catalog version đã biết; client không được gửi enum tùy ý để lưu như hợp lệ.
10. **Không mở rộng H4d.** `image_prompt`, negative prompt, provider `image`, calibration, compliance của ảnh và sinh ảnh AI nằm ngoài MINI-SPEC này.
11. **Không tuyên bố chạy thật chỉ vì test xanh.** I1 yêu cầu lượt gọi provider thật; I2 yêu cầu review mapping thật với H4 fixture/pilot. Mọi thiếu provider, lỗi model, chi phí bất thường hoặc enum không render được phải báo `blocked`/`fail`.
12. **Giữ trace và redaction.** Log task/provider/model/token/giá/cache/hold/commit/refund cần đủ audit nhưng không lộ API key/token/bản ghi nhạy cảm.

---

## Scope

### A. Audit domain model và contract hiện có

#### I1 — Provider/assist/cost/cache

Audit tối thiểu các phần sau:

- Provider registry/schema: role, model, provider endpoint/protocol, enabled/disabled state, priority/fallback, key storage/redaction.
- Trang admin hiện có: thêm/sửa/xóa/test provider record, hiển thị role, giá, trạng thái lỗi.
- Task allow-list/schema: task nào thực sự đi qua `assist`, task nào miễn phí, task nào có giá.
- Cost pipeline: giá hiển thị trước, preflight, hold, completion commit, failure refund/release, reconciliation.
- Cache semantics: cache key, scope theo device/user/task/model/prompt version, TTL/invalidation, cache hit accounting.
- Error contract: phân biệt thiếu device token (`401`) với thiếu provider (`503`), provider upstream lỗi, timeout, quota, input invalid, insufficient Vox.
- Telemetry/analytics: token in/out, model/provider, cost, task, latency, error code, cache hit.
- Existing behavior when `assist` missing: xác minh có fallback `translate`, cách UI/cost hiện ra, và nơi cần thay đổi nhỏ nhất để cấm fallback im lặng.

#### I2 — H3/H4 render vocabulary/mapping

Audit tối thiểu:

- H3 script segment schema: ID, lời đọc, chữ trên hình, mô tả cảnh, narrative role/duration nếu có.
- H4 storyboard/project schema: image assignment, duration theo TTS thật, các tham số motion/crop/scale/transition đã có hoặc chưa có.
- Renderer/export: những transition/motion nào thật sự được hỗ trợ; action nào không có implementation.
- Existing visual/style settings, enum/config nào đã tồn tại để tái sử dụng thay vì tạo trùng.
- Validation pattern hiện có cho config/catalog JSON/schema version.
- Storage location phù hợp cho catalog: source-controlled JSON nếu v1 là dữ liệu sản phẩm tĩnh; DB/config chỉ nếu catalog hiện phải chỉnh runtime và hệ thống đã có pattern phù hợp.
- Localization/UI wording pattern cho nhãn tiếng Việt.

#### Gap classification bắt buộc

Ghi rõ từng gap đã xác nhận theo nhóm:

- Provider configuration gap
- Fallback/cost-truthfulness gap
- Cache/idempotency gap
- Provider error/observability gap
- Catalog vocabulary gap
- H4 render-mapping gap
- Schema validation/versioning gap
- UI wording/discovery gap

Không triển khai bất kỳ gap nào không được audit xác nhận.

---

### B. I1 — Kích hoạt provider `assist` và kiểm chứng task thật

#### B1. Provider configuration

Sử dụng trang quản trị/provider registry hiện có để tạo hoặc enable **một** provider record cho role `assist`.

Cấu hình phải có, theo schema hiện có:

- Role: `assist`
- Provider/protocol hợp lệ đã được hệ thống hỗ trợ
- Model ID hợp lệ
- API credential được lưu theo cơ chế hiện có, không log plaintext
- Pricing/usage mapping theo cơ chế thống kê/đối soát hiện có
- Timeout/retry/rate-limit theo defaults hiện có hoặc lý do audit cho một override tối thiểu
- Enabled state
- Fallback policy rõ ràng: ưu tiên provider `assist` hợp lệ; không rơi im lặng sang `translate`

Nếu hệ thống hỗ trợ provider test/health check, chạy nó và lưu evidence. Nếu không, task thật bên dưới là health check.

#### B2. Task matrix chạy thật

Chạy trên provider thật, với inputs kiểm soát và không nhạy cảm:

| Task | Mục tiêu kiểm chứng | Yêu cầu kết quả |
|---|---|---|
| `explain_error` | đường miễn phí + error-to-action UX | Kết quả hữu ích; không trừ Vox; chạy khi số dư thấp/hết theo contract hiện có |
| `character_name` | input transcript → gợi ý, không tự ghi hồ sơ | Có gợi ý; hồ sơ nhân vật không đổi nếu người dùng chưa tự lưu |
| `tighten_line` | rút gọn câu dịch, giữ nghĩa | Output ngắn hơn hoặc giải thích không thể rút; không phá format yêu cầu |
| `scene_script` | gợi ý câu dẫn/nhịp cảnh hiện có | Output đúng schema/contract hiện có; không tạo Visual Direction Sheet, không auto-write H3/H4 |

Chạy ít nhất 10 lượt tổng cộng, gồm:

- Mỗi task ít nhất 2 lượt;
- Ít nhất một cache hit có chủ đích cho task có phí;
- Ít nhất một ca lỗi provider mô phỏng/an toàn nếu hạ tầng cho phép;
- Ít nhất một ca thiếu provider trong staging/test config hoặc test integration, để xác minh `503` và không fallback `translate`.

#### B3. Cost, cache, failure invariant

Với từng lượt có phí, capture:

- task name;
- device/user scope đã redact;
- preflight displayed price;
- Vox balance trước/sau;
- hold created/reused;
- commit/refund/release outcome;
- provider/model selected;
- token/usage nếu provider trả về;
- cache key version/hash đã redact;
- cache hit/miss;
- response/error code;
- latency.

Invariants bắt buộc:

- Cache hit không tạo hold mới, không commit Vox lần hai.
- Provider missing trả `503` hoặc error domain tương đương đã documented, không phải `401`.
- Device token thiếu vẫn là `401`, không bị "sửa" để bỏ xác thực.
- Provider failure/timeout không commit tiền cho kết quả không thành công; hold phải được release/refund theo contract.
- Câu chữ UI/tooltip/receipt không mô tả task có phí là miễn phí.

#### B4. Minimal UI hardening

Chỉ sửa UI nếu audit xác nhận mismatch giữa hành vi thật và lời người dùng thấy. Phạm vi tối đa:

- Hiển thị giá/task status đúng từ server/preflight hiện có.
- Hiển thị cache/retry/failure message hành động được.
- Hiển thị thiếu provider như unavailable/service unavailable, không báo generic error.
- Không xây dashboard mới; dùng trang thống kê/admin/task UI hiện có.

---

### C. I2 — Visual Direction Catalog v1

#### C1. Catalog model

Tạo một catalog **source-controlled, versioned, schema-validated** trừ khi audit chứng minh dự án đã có storage/config runtime tương đương và phù hợp hơn.

V1 phải có mã version rõ ràng, ví dụ `catalog_version: 1`, và một cấu trúc tương đương:

```json
{
  "catalog_version": 1,
  "groups": [
    {
      "id": "shot",
      "label_vi": "Khung hình",
      "values": []
    }
  ]
}
```

Mỗi value tối thiểu có:

```json
{
  "id": "close_up",
  "label_vi": "Cận cảnh",
  "description_vi": "Tập trung vào gương mặt, chi tiết hoặc lợi ích chính.",
  "recommended_for": ["hook", "benefit", "detail"],
  "avoid_when": ["cần đọc nhiều chữ", "cần thấy nhiều đối tượng"],
  "prompt_hint_vi": "Cận cảnh rõ chủ thể, hậu cảnh gọn, chừa vùng đặt chữ.",
  "render_mode": "supported",
  "h4_mapping": {
    "implementation": "crop_scale",
    "parameters": {}
  }
}
```

Không lưu tên/video/creator/brand nguồn. Không lưu frame hoặc prompt copy từ video tham khảo.

#### C2. Sáu nhóm v1

Catalog v1 phải giới hạn số value để dễ kiểm chứng. Số lượng chính xác chỉ chốt sau audit H4, nhưng điểm xuất phát tối đa như sau:

| Group ID | Nhãn tiếng Việt | Chỉ được gồm |
|---|---|---|
| `shot` | Khung hình | Toàn cảnh, trung cảnh, cận cảnh, cực cận; chỉ khi H4 map được qua crop/fit/position hoặc advisory rõ ràng |
| `composition` | Bố cục | Chủ thể trung tâm, chừa vùng chữ trên/dưới, bố cục cân bằng, nhấn chi tiết sản phẩm; không chứa bố cục nhận diện của nguồn |
| `motion` | Chuyển động nhẹ | Tĩnh, zoom vào chậm, zoom ra chậm, pan nhẹ ngang/dọc **chỉ** nếu H4 renderer hỗ trợ Ken Burns/crop-scale tương ứng |
| `pacing` | Nhịp dựng | Giữ lâu, nhịp vừa, nhấn từ khóa, cắt gọn; phải map thành duration/timing policy tương thích D1, không tự ghi đè mốc audio thật |
| `transition` | Chuyển cảnh | Cắt thẳng, fade nhẹ, crossfade ngắn **chỉ** nếu exporter có implementation thật; nếu chưa có, catalog chỉ chứa `cut` hoặc value không được UI render lựa chọn |
| `lighting_color` | Màu sắc và ánh sáng | Sáng sạch, ấm gần gũi, trung tính, tối giản premium, tương phản rõ; là metadata/gợi ý selection ảnh, không tuyên bố renderer tự color-grade nếu chưa có chức năng đó |

#### C3. Truthful render states

Mỗi value phải dùng một trong các state sau:

- `supported`: H4 có mapping implementation thật, test được.
- `advisory_only`: chỉ dùng làm gợi ý người dùng chọn/gán ảnh; không được gửi như lệnh render và không được hiển thị như khả năng tự động.
- `unavailable`: không được xuất trong catalog runtime/UI v1; chỉ có thể tồn tại trong tài liệu backlog, không phải data ship.

Mặc định chỉ expose `supported` và (nếu UX mô tả rõ "gợi ý chọn ảnh") `advisory_only`. Catalog render control không được bao giờ map `advisory_only` thành effect thực thi.

#### C4. Mapping với H4 và D1

- `motion` chỉ map qua cơ chế ảnh tĩnh/crop/scale/Ken Burns đã audit xác nhận.
- `pacing` không được đổi duration đã được D1 tái dựng theo audio thật. Nó có thể gợi ý cách chọn hình/cắt cảnh nhưng không được ép TTS hoặc rút duration cuối.
- `transition` không được thêm thời lượng che mất audio hoặc gây cảnh cuối bị cắt. Nếu transition ảnh hưởng thời lượng, contract đo lại H4c-1/D1 phải tiếp tục pass.
- `lighting_color` và `composition` là metadata cho người dùng/H3/H4 sau này; v1 không thêm engine color grading/inpainting.

#### C5. Catalog delivery and read contract

Audit API/config pattern hiện có rồi chọn một đường duy nhất:

- **Ưu tiên:** catalog đóng gói trong app/server source, server trả version/values qua endpoint read-only hiện có hoặc một endpoint read-only tối thiểu theo style `API.md`.
- Nếu app desktop có config bundle đã versioning, có thể đọc từ bundle, nhưng server-side validation vẫn phải có trước khi future feature lưu selection.

I2 chưa tạo Visual Direction Sheet, chưa cần DB record per scene, và chưa cần write endpoint cho user selection. Chỉ cần catalog read/validation boundary đủ cho I3 sau này.

#### C6. Minimal discoverability surface

Không xây trang "Visual Direction" đầy đủ ở I2. Chỉ cần một trong hai cách, dựa vào UI pattern đã có:

- Developer/admin preview read-only; hoặc
- Một preview/read-only section nhỏ trên trang `scene_script` hiện có, ghi rõ "Danh mục định hướng hình ảnh — chưa tự áp dụng vào video".

Nếu audit thấy UI preview sẽ tạo hiểu nhầm vì chưa có I3/I4, không thêm UI; test/API/schema evidence đủ cho I2. Không được marketing catalog như tính năng render mới.

---

### D. API contract

#### I1

Không tạo API provider/task mới nếu endpoint hiện có đã làm được. Ghi rõ trong audit API nào được tái dùng.

Chỉ bổ sung/chỉnh contract nếu audit xác nhận thiếu một trong các điều kiện sau:

- Response phân biệt provider unavailable (`503`) với unauthorized (`401`).
- Response/receipt cần cost/cache metadata tối thiểu để UI nói thật.
- Admin provider test/status cần exposed state có redaction.

Mọi thay đổi phải theo style/validation/error envelope của `docs/API.md`.

#### I2

Chỉ thêm read contract tối thiểu nếu chưa có cơ chế config read phù hợp:

```text
GET /v1/visual-direction-catalog
```

Response tối thiểu:

```json
{
  "catalog_version": 1,
  "groups": ["..."],
  "values": ["..."],
  "generated_at": "optional, if existing contract supports it"
}
```

Rules:

- Read-only.
- Không chứa prompt/system prompt/provider secret.
- Không nhận enum user-defined.
- Không coi response này là permission mở H4d/image.

Nếu route mới được thêm, phải có device auth theo pattern hiện có nếu catalog không public. Không làm yếu xác thực để "dễ preview".

---

### E. UI surfaces

#### I1

- Reuse trang admin provider hiện có để cấu hình/enabled `assist`.
- Reuse task UI hiện có để kiểm chứng `explain_error`, `character_name`, `tighten_line`, `scene_script`.
- Sửa wording/trạng thái nhỏ nhất cần thiết để giá, unavailable, retry/cache nói đúng sự thật.
- `character_name` vẫn chỉ gợi ý; không tự ghi vào hồ sơ nhân vật.

#### I2

- Default: không cần UI người dùng cuối.
- Nếu audit chọn preview: chỉ read-only, viết rõ trạng thái catalog/gợi ý; không có nút "Áp dụng", "Sinh ảnh", "Render effect", hoặc "Xuất video" mới.
- Không thêm dashboard hay page riêng nếu preview không cần thiết.

---

### F. Tests

#### I1 test categories

- Unit: provider selection/fallback policy, task allow-list, error mapping, cache/idempotency, hold/commit/refund transitions, pricing wording source where applicable.
- Integration: HTTP + DB/provider registry thật/test double ở boundary hợp lý; provider missing vs unauthorized; admin provider config validation; task execution persistence/accounting.
- Regression: remove anti-fallback rule → test đỏ; cache hit charged twice → test đỏ; `character_name` auto-write → test đỏ; missing provider returning `401` → test đỏ.
- Live: ≥10 real provider calls, task matrix, cost/cache/error evidence.

#### I2 test categories

- Unit: catalog JSON/schema validation; unique IDs; known group/value validation; render-state validation; H4 mapping completeness for `supported`; no banned capability value; catalog version parsing.
- Integration: read contract/config delivery; auth policy; client parse; server-side validation boundary prepared for I3.
- Regression: unknown enum fails; `advisory_only` cannot be passed to renderer as executable mapping; `pacing` cannot overwrite D1 audio-derived duration; missing mapping makes `supported` invalid.
- Live: create a small representative storyboard fixture and demonstrate each `supported` mapping either renders/loads as intended or is removed/downgraded before completion.

---

## Audit Before Build

The implementation report must answer every item below before code changes.

### I1 audit checklist

- [ ] Provider registry/model and admin UI location for role `assist`.
- [ ] Current `assist` provider state and whether it currently falls back to `translate`.
- [ ] Exact endpoint(s) and server task dispatch for `explain_error`, `character_name`, `tighten_line`, `scene_script`.
- [ ] Price source, hold/commit/refund implementation, receipt/preflight UI path.
- [ ] Cache-key construction and cache hit charging behavior.
- [ ] Current 401/503/provider timeout/error contracts.
- [ ] Existing telemetry/token/cost fields and redaction behavior.
- [ ] Existing tests that protect money/task behavior.

### I2 audit checklist

- [ ] H3 segment and H4 storyboard schemas.
- [ ] Current renderer/export support for crop, scale, Ken Burns, fade, cut, transition, and timing.
- [ ] Existing enum/config/catalog validation pattern to reuse.
- [ ] Existing config/API delivery mechanism to reuse.
- [ ] Existing visual settings/labels that would duplicate catalog vocabulary.
- [ ] H4/D1/H4c-1 timing contract and where regression tests live.
- [ ] Exact list of v1 values that can be `supported`, `advisory_only`, or must remain out of runtime catalog.

### Required audit conclusion

The report must include a table:

| Need | Existing component | Status | Confirmed gap | Planned smallest change |
|---|---|---|---|---|
| Assist provider role | Audit result | reuse/add config | Audit result | Audit result |
| Cost/cache | Audit result | reuse/harden | Audit result | Audit result |
| Error contract | Audit result | reuse/harden | Audit result | Audit result |
| H4 visual mapping | Audit result | reuse/add catalog mapping | Audit result | Audit result |
| Catalog delivery | Audit result | reuse/new read-only route | Audit result | Audit result |

No implementation may begin until this table is filled with file/function/API evidence.

---

## Design Choice

I1+I2 are deliberately combined because the catalog is not useful as a future AI contract unless the `assist` path is first proven real, cost-correct and observable. But they remain two independent deliverables inside one implementation gate:

\[
\text{provider assist configured and verified}
\quad + \quad
\text{closed catalog with real H4 mappings}
\quad \rightarrow \quad
\text{safe input boundary for I3 scene\_director}
\]

### Chosen approach

1. **Configure, do not rebuild:** add/enable a provider record for existing role `assist`; retain the existing server-owned task prompt architecture, pricing, cache, accounting and admin patterns.
2. **Prove using existing tasks:** run `explain_error`, `character_name`, `tighten_line`, `scene_script` before inventing any visual-direction AI task.
3. **Source-controlled catalog v1:** introduce a narrow versioned catalog data file/schema with read-only delivery and strict enum validation, unless audit demonstrates an existing equivalent runtime-config pattern.
4. **Truthful mappings:** supported effects are only those H4 can actually render today; advisory guidance is visibly non-executable; unavailable effects are excluded.
5. **No scene persistence/UI editing yet:** I3/I4 own Visual Direction Sheet generation and editing. I2 creates only the vocabulary/mapping contract they will consume.

### Why this is preferred

- It prevents I3 from becoming another untested `assist` task with unknown cost/failure behavior.
- It prevents an LLM from inventing cinematic terms that the H4 renderer cannot implement.
- It preserves server control over prompts and spending.
- It avoids premature UI complexity before actual AI outputs exist.
- It protects D1 timing correctness by treating visual pacing as guidance, never as a replacement for audio-derived timings.

### Explicitly rejected approaches

- Creating a separate `scene_director` task in I1+I2: deferred to I3.
- Using `translate` as silent backup for assist: rejected due to cost and user-trust risk.
- Hard-coding visual options separately in GUI and server: rejected; catalog must be one versioned source of truth.
- Exposing unsupported cinema effects as selectable UI: rejected.
- Enabling H4d/image provider as part of catalog work: rejected.
- Storing source-video visual fingerprint/style for copying: rejected.

---

## Test Plan

### 1. I1 unit tests

1. A valid configured `assist` provider is selected for assist tasks.
2. Missing/disabled assist provider yields documented unavailable error (`503` or existing equivalent), never silent `translate` fallback.
3. Missing device token remains `401`.
4. Unknown task name is rejected before provider call.
5. `explain_error` costs 0 Vox according to server policy and receipt/telemetry.
6. A paid task cache hit does not create a second hold or second commit.
7. Failed/timeout provider calls release/refund hold according to current contract.
8. `character_name` response cannot write/update character profile automatically.
9. Task telemetry redacts credentials/secrets.
10. UI cost wording uses the authoritative price state, not a hard-coded "free" message.

### 2. I1 integration tests

1. Admin config validation accepts supported provider/model for `assist` and rejects invalid/incomplete record.
2. Each of four task endpoints executes with a controlled provider/test boundary and returns expected current contract.
3. Provider unavailable returns distinct server/service error and does not debit Vox.
4. Unauthorized device request returns 401 and does not reach provider.
5. Cache repeated identical paid request returns cached result and unchanged balance after first charge.
6. Simulated upstream failure leaves wallet/hold in correct terminal state.
7. Provider/model/token/usage cost telemetry is recorded without secrets.

### 3. I1 live verification

Perform at least 10 real calls after provider configuration:

| Required case | Minimum |
|---|---:|
| `explain_error` | 2 |
| `character_name` | 2 |
| `tighten_line` | 2 |
| `scene_script` | 2 |
| Deliberate identical paid request (cache hit) | 1 |
| Provider unavailable/error case, staging or safe test configuration | 1 |

For each call, record task, provider/model, result state, preflight cost, wallet delta, hold/commit/refund, cache hit/miss, latency and redacted request ID.

### 4. I2 unit tests

1. Catalog v1 validates against schema.
2. Catalog version is required and supported version is parsed deterministically.
3. Group IDs and value IDs are unique.
4. Every value has Vietnamese label/description, recommendation and avoid guidance.
5. Every `supported` value has a complete, existing H4 mapping.
6. Every `advisory_only` value has no executable renderer mapping.
7. Unknown group/value ID is rejected.
8. Banned/unsupported capabilities (for example `dolly_zoom`, `drone_shot`, `rack_focus`, `whip_pan`, `ai_video_generation`) cannot enter runtime catalog.
9. `pacing` mapping cannot overwrite the D1 audio-derived duration source.
10. Transition mapping cannot make final scene end before actual audio end.

### 5. I2 integration tests

1. Catalog delivery endpoint/config bundle returns the declared catalog version and full valid data.
2. Auth behavior follows existing app/API policy; no auth weakening is introduced.
3. Desktop/client parser displays/loads catalog without accepting unknown values.
4. For representative H4 project fixture, each `supported` motion/transition mapping passes the H4c-1/D1 timing checks or is demoted/removed.
5. Future-boundary validator rejects unknown/stale enum input when simulating I3 consumer request.

### 6. I2 live verification

1. Build a small representative H4 fixture with at least five scenes and real/safe TTS audio timing.
2. Exercise every `supported` motion/transition at least once across fixture variants, or document why value is removed/demoted.
3. Measure final audio/video duration and final-frame behavior using existing D1/H4c-1 tools.
4. Review output manually for misleading UI claims: a supported effect must visibly map to intended subtle slideshow behavior; advisory values must not claim automated rendering.

### 7. Regression proof

The implementation report must demonstrate red tests or equivalent mutation proof for these guardrails:

- Remove the no-translate-fallback policy → provider-missing test fails.
- Charge cache hit twice → wallet/cache test fails.
- Make `character_name` auto-save → profile invariant test fails.
- Mark unsupported cinematic action as `supported` without H4 mapping → catalog test fails.
- Let `pacing` replace D1 timing → timing regression test fails.
- Allow unknown enum → schema/boundary validation test fails.

---

## Success Criteria

I1+I2 close only when every condition below is met.

### I1 — Assist activation

1. A configured, enabled provider record for existing role `assist` is running through the existing provider framework.
2. At least 10 real calls across `explain_error`, `character_name`, `tighten_line`, and `scene_script` have evidence of useful response, correct provider/model selection, and redacted telemetry.
3. Paid tasks show truthful preflight price and correct hold/commit/refund behavior.
4. Repeating an identical paid request returns cache behavior without a second charge.
5. Missing assist provider is visibly unavailable/503 (or documented equivalent) and never silently consumes `translate` pricing.
6. Missing device authorization remains 401; no authentication rule is weakened.
7. `character_name` does not mutate character profile without an explicit user save.
8. Documentation/UI do not call paid tasks free; `explain_error` remains correctly free.

### I2 — Visual catalog v1

9. A versioned, schema-validated catalog v1 exists as one source of truth for the six defined groups.
10. Every runtime catalog value is either `supported` with a tested H4 mapping or clearly `advisory_only` and non-executable; unavailable cinematic effects are absent.
11. Catalog validation rejects unknown enum IDs, duplicate IDs, missing Vietnamese user descriptions, incomplete mappings and banned capabilities.
12. Supported mappings preserve D1/H4c-1 timing correctness, including final scene/audio behavior.
13. Catalog is deliverable/readable through the selected existing config/API pattern without exposing secrets or weakening auth.
14. No Visual Direction Sheet, per-scene persisted selection, `scene_director`, image generation, H4d activation, or user-facing rendering promise has been added prematurely.

### Joint readiness

15. `FEATURES.md`, `docs/API.md` if applicable, `docs/ARCH.md` if applicable, and `docs/TEST_LOG.md` distinguish what is configured/live from what is only catalog infrastructure.
16. Completion report includes audit evidence, changed files, test totals, live-call evidence, H4 fixture evidence, remaining limits, and a clear verdict: `ready for I3` or `blocked`.

---

## Out of Scope

- `scene_director` task/API and Visual Direction Sheet generation (I3).
- Scene-level Visual Direction storage, editing UI and brand presets (I4/I6).
- Mapping catalog into H4 production user workflow (I5).
- H4d image generation, image provider configuration, calibration, image compliance changes or automatic drawing.
- Video AI generation, optical flow, camera-motion recognition, depth/3D, tracking, or professional NLE timeline.
- New TTS/ASR/OCR engines and CPU optimization work.
- H3 price redesign; it remains data-gated by 10–20 actual H3 runs.
- New analytics dashboard; add fields to existing statistics only if audit confirms need.

---

## Documentation Updates

On completion, update existing documents truthfully:

- `FEATURES.md`
  - State that role `assist` is configured and which existing tasks have been live verified.
  - State Visual Direction Catalog v1 exists as controlled infrastructure; do not present it as scene generation/rendering feature.
- `docs/API.md`
  - Document any real provider availability/error contract change and catalog read endpoint if added.
- `docs/ARCH.md`
  - Document catalog source/delivery/validation boundary only if it changes architecture.
- `docs/TEST_LOG.md`
  - List exact live calls, cost/cache/hold outcomes, provider/model redacted evidence, catalog H4 mapping runs, bugs found and corrections.
- Existing admin/release documentation
  - Record how `assist` provider is configured without writing secrets into repository docs.

---

## Required Completion Report

The implementer must submit exactly this report structure:

1. **Summary**
   - What I1 and I2 delivered, provider state, catalog version, and final verdict.

2. **Audit Before Build**
   - Provider/task/cost/cache/error findings; H3/H4 mapping findings; completed "Need → existing component → gap → smallest change" table.

3. **Design Choice**
   - Provider configuration chosen; fallback behavior; catalog storage/delivery choice; supported vs advisory taxonomy; why no I3/I4/H4d work was included.

4. **Changed Files**
   - Server, admin/UI, catalog/schema, validation, tests, docs. State explicit `none` for each area untouched.

5. **API/DB/State Changes**
   - Reused endpoints/configuration or exact new read-only catalog route; provider record/schema changes; no invented parallel state.

6. **I1 Tests and Live Evidence**
   - Unit/integration totals; 10-call table with task, provider/model, cache, preflight, wallet/hold outcome, latency, result; 401/503/error test evidence; redaction evidence.

7. **I2 Tests and H4 Evidence**
   - Schema tests, catalog version, full supported/advisory list, mapping evidence, H4 timing/final-frame outputs, mutation/red-test proof.

8. **Documentation Updated**
   - Exact sections/files changed and wording that distinguishes live vs infrastructure.

9. **Remaining Limits / Follow-ups**
   - Genuine limits only; explicitly list I3 as next MINI-SPEC only if all success criteria passed.

10. **Verdict**
    - `ready for I3` only if all success criteria pass; otherwise `blocked` with exact condition and next required action.

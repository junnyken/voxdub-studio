# H3 — Viết lại kịch bản cho Brand từ Flow Blueprint, có guardrail chống sao chép

> **Trạng thái: ĐÃ TRIỂN KHAI 10/09/2026** — xem mục "Triển khai" ở cuối tệp.
>
> **Bản sửa 10/09/2026.** Bản gốc có một tiền đề sai ở mức chặn (giả định H2
> lưu evidence thô) và vài tên trường/API không khớp mã. Toàn bộ phần đã sửa
> được đánh dấu **[SỬA]** kèm lý do. Triết lý và các guardrail của bản gốc
> giữ nguyên — chúng đúng.

## Lưu ý thực thi bắt buộc

- Dự án: VoxDub Studio (desktop app + `control_server`). Không phải SocialHub,
  Ads Manager, hay website-only.
- H1, H2, H2a, H2b, H2c **đã push `main`, CI xanh, đã deploy prod** (kiểm
  10/09: 6 job CI xanh gồm cả lượt dub thật trên Windows; `/health` trả
  `{"ok":true,...}`).
- **[SỬA] CHƯA có `FlowBlueprint` THẬT nào tồn tại.** Chưa ai chạy H2
  end-to-end trên prod. Việc đầu tiên trước khi code H3 là **chạy một lượt H2
  thật** để có nguyên liệu cho live verification — nếu không, mục live
  verification của H3 sẽ bị làm cho có.

### Trạng thái đã xác nhận bằng cách ĐỌC MÃ (không giả định lại)

- Ownership theo **device identity/token**, không có account layer. `Device._id`
  là đơn vị danh tính duy nhất. H3 dùng đúng pattern này, không tạo cơ chế
  ownership thứ ba.
- **[SỬA] `BrandProfile` dùng camelCase** (`models/BrandProfile.js`):
  `ownerDeviceId`, `tenBrand` (required), `moTaSanPham`, `doiTuongKhach`,
  `toneGiong`, `usp`, `rangBuocKhongDuocNoi` (**`[String]`**, mặc định `[]`).
  Bản gốc viết snake_case — viết vậy Antigravity sẽ tạo trường mới thay vì
  dùng trường sẵn có.
- **[SỬA] `FlowBlueprint` cũng camelCase**: `sourceType`, `sourceReference`,
  `languageSourceDetected`, `analysisLanguage`, `evidenceSummary`,
  `samplingPolicyUsed`, `beats[]`, `userReviewNote`. Mỗi beat:
  `startS`, `endS`, `beatType` (enum đóng), `narrativeFunctionVi`,
  `pacingNoteVi`, `overlayPatternAbstractVi`, `spokenPatternAbstractVi`,
  `evidenceStatus`.
- **[SỬA] `evidenceStatus` là trường CỦA TỪNG BEAT**, không phải của Blueprint.
  Cấp Blueprint chỉ có `evidenceSummary` (mô tả *tình trạng* bằng chữ). Bản
  gốc viết "Blueprint có evidence_status = unavailable" — không có thứ đó.
- **[SỬA] H2b: `read_text_regions(bo_doc="may_chu")`**, không phải
  `bo_doc=gemini`. Tên model **cố ý không xuất hiện phía client** — model là
  cấu hình phía máy chủ; ghim tên model vào app là đúng thứ H2b tránh.
- Cổng trợ lý AI: khuôn closed-task, app gửi **tên task**, prompt nằm
  server-side, 4 lớp chặn chi phí (danh sách đóng → trần ký tự → hạn mức ngày
  → nhớ đệm theo nội dung).

### [SỬA] Tiền đề bị đảo: H2 KHÔNG lưu evidence thô

Bản gốc dựng toàn bộ originality check lên *"evidence nguồn (transcript + OCR
**đã lưu** ở H2)"*. Mã thật ngược lại: `routes/flow-blueprints.js` ghi rõ
*"KHÔNG lưu transcript/OCR thô — chỉ dùng TẠM để gọi mô hình rồi bỏ"*
(Constraint 2/Scope B của H2), và `models/FlowBlueprint.js` không có trường
nào chứa chúng.

**Đã xử lý bằng mini-spec H2c (xong 10/09)**: `FlowBlueprint` nay có trường
nội bộ `evidenceFingerprint` — **băm MỘT CHIỀU** của bằng chứng, dựng ngay lúc
tạo rồi bằng chứng thô vẫn bị bỏ như cũ. Xem
`docs/MINI-SPEC_H2c_Dau_Van_Tay_Bang_Chung.md`.

H3 dùng `services/dau-van-tay.service.js`:

```js
timTrungLap(vanBan, dvt) // -> { trung, cum, kieu, kiemDuoc }
```

- `cum` = cụm **trong văn bản MỚI** bị trùng.
- `kiemDuoc: false` = **CHƯA kiểm được**, khác hẳn `trung: false` (đã kiểm,
  không trùng). Dịch thành `unconfirmed`, tuyệt đối không phải `clear`.

**Hệ quả bắt buộc chấp nhận**: không giữ chữ nghĩa là **không trưng ra được
cụm gốc** bên nguồn. Mục Desktop UI đã sửa theo (xem phần E).

## Context

### Vì sao cần originality check riêng ở H3

Gate của H2 kiểm **Flow Blueprint** (mô tả trừu tượng) so với nguồn. H3 tạo
một văn bản HOÀN TOÀN MỚI (kịch bản cho brand khác). Rủi ro khác: model viết
lại có thể "quá trung thành" tới mức paraphrase sát nghĩa hoặc giữ nguyên cấu
trúc câu hook/CTA đặc trưng. H3 phải tự kiểm lại từ đầu, không được tin
"H2 đã sạch thì H3 chắc cũng sạch".

### Ba luật cứng (mirror khuôn đã chứng minh ở `packaging_check` C1)

1. **Mặc định**: học NHỊP/CẤU TRÚC từ Blueprint, tuân BrandProfile — không sao
   chép câu chữ nguồn.
2. **Kết quả kiểm đè lên ý định người dùng**: model "hứa" đã viết khác không
   có nghĩa nó thực sự khác — phải kiểm thật bằng so khớp văn bản.
3. **Không kiểm được thì coi như không dùng được.**

### Về phương pháp so khớp

Nguyên tắc "không dùng embedding/cosine" của dự án áp cho **so sánh ẢNH** (C1),
không cấm phép đo trùng lặp văn bản. H3 dùng n-gram (đã có sẵn, xem A.5),
nhưng giữ tinh thần: **luôn trả excerpt đọc được, không chỉ một con số**.

## Goal

Từ một `FlowBlueprint` + một `BrandProfile` (cùng device), sinh kịch bản mới
tiếng Việt — lời đọc theo beat, gợi ý caption, visual brief — đúng
tone/USP/ràng buộc brand, giữ nhịp kể chuyện của Blueprint, và **được xác
nhận không sao chép câu chữ nguồn** trước khi cho dùng tiếp sang H4.

## Constraints (Guardrails)

1. H3 chỉ nhận `flowBlueprintId` và `brandProfileId`; **không nhận prompt tự
   do từ client**.
2. H3 **không sinh ảnh, âm thanh, video**. Chỉ sinh văn bản.
3. Kịch bản PHẢI tuân `rangBuocKhongDuocNoi` — có bộ kiểm riêng chặn output
   chứa cụm/claim bị cấm.
4. **[SỬA]** Bắt buộc chạy originality check bằng `evidenceFingerprint` của
   Blueprint TRƯỚC khi cho `ready`. Không có đường nào trong UI/API bỏ qua.
5. Một beat `flagged` hoặc `violated` ⇒ **toàn bộ** BrandScript `blocked`.
   UI phải chỉ rõ ĐÚNG beat và ĐÚNG cụm gây chặn.
6. **[SỬA]** BrandScript ở `unconfirmed` khi **bất kỳ điều nào** sau đây đúng:
   - Blueprint **không có** `evidenceFingerprint` (bản ghi tạo trước 10/09 —
     không vá ngược được vì evidence gốc đã bỏ đi);
   - `timTrungLap` trả `kiemDuoc: false` (khác phiên bản thuật toán);
   - `evidenceFingerprint.dayTran === true` (vùng phủ không đầy đủ);
   - beat tương ứng của Blueprint có `evidenceStatus` ∈
     `unavailable | failed | no_text`.
7. Không tự điền `BrandProfile` thiếu trường bằng suy luận AI — thiếu trường
   bắt buộc (vd `usp` rỗng) thì **báo người dùng bổ sung**, không bịa USP.
8. BrandScript scope theo `ownerDeviceId` đúng pattern H1/H2.
9. Thêm task closed-list `brand_script_rewrite` vào cổng trợ lý AI hiện có,
   giá/limit/cache theo đúng pattern 4 lớp, **không tạo cổng gọi mô hình
   riêng**.
10. Mọi `catch` phải có log/lý do tại chỗ.
11. Tạo lại một beat ⇒ **chạy lại cả hai bộ kiểm cho TOÀN BỘ script** trước khi
    cho `ready` lại.
12. **[SỬA — mới]** Hai bộ kiểm là **thuần so khớp văn bản, KHÔNG gọi mô
    hình**. Nếu không ghi rõ, Constraint 11 sẽ vô tình thành hoá đơn AI nhân
    lên theo mỗi lần sửa beat.
13. **[SỬA — mới]** Ghi `originalityCheckVersion` = `PHIEN_BAN` của
    `dau-van-tay.service.js` lúc kiểm. Script `ready` bằng phiên bản CŨ hơn
    phiên bản hiện tại phải **hạ về `unconfirmed`** khi đọc lại, không giữ
    `ready` vĩnh viễn.
14. **[SỬA — mới]** Xoá dây chuyền: `BrandProfile`/`FlowBlueprint` đều có
    `DELETE`. Xoá một trong hai khi đã có BrandScript tham chiếu ⇒ phải quyết
    (chặn xoá, **hoặc** hạ script về `unconfirmed`). Không để tham chiếu treo
    im lặng.

## Scope

### A. Audit Before Build

**[SỬA] Năm mục dưới đây ĐÃ AUDIT XONG ngày 10/09** — không phải làm lại, chỉ
xác nhận nhanh nếu nghi mã đã đổi:

1. `FlowBlueprint`: xem phần "Trạng thái đã xác nhận" ở trên. Evidence thô
   **không** được lưu; dùng `evidenceFingerprint` (H2c).
2. `BrandProfile`: camelCase, `rangBuocKhongDuocNoi` là `[String]`.
3. Ownership: `ownerDeviceId` lấy TỪ token, **không nhận từ client**. Mã lỗi
   dùng chung `404` cho "không tồn tại" và "của thiết bị khác" — cố ý không
   tiết lộ. **[SỬA]** Bản gốc gợi ý phân biệt 403/404; style API hiện tại
   **không** phân biệt, giữ nguyên `404`.
4. Cổng trợ lý: `src/prompts/assist.js` (`TASKS`), giá ở
   `services/config.service.js`, nhớ đệm `cacheKey(task, input, images)`.
5. **Đã có sẵn công cụ so khớp, không cần thêm dependency**:
   - `dau-van-tay.service.js` — `timTrungLap()` cho originality (H3 dùng cái
     này);
   - `assist.js` — `coSaoChepNguyenVan()` cho gate H2, **chỉ trả
     `true/false`**. H3 cần excerpt ⇒ **mở rộng chính hàm/service sẵn có** để
     trả cụm khớp, **đừng viết bộ thứ hai**: hai bộ chặn song song sẽ trôi
     lệch nhau và lúc đó không ai biết bộ nào đang bảo vệ mình.
   - Phép chuẩn hoá dùng chung: `dau-van-tay.service.chuanHoaSoKhop`.

6. Nếu bất kỳ tiền đề nào ở trên sai so với mã, **DỪNG và báo gap**, không tự
   mở rộng phạm vi.

7. **[SỬA — mới] Ba chốt guardrail sẽ ĐỎ ngay khi thêm task mới.** Đây là
   thiết kế có chủ đích, **sửa cho đủ chứ đừng nới chốt**:
   - `tests/test_features_khop_ma.py` — `FEATURES.md` §3.5 phải có dòng giá;
   - `tests/assist-evals.test.js` — `evals/cases.js` phải có mẫu đo;
   - `tests/hold.test.js` — khoá giá mới phải thêm vào danh sách giá công khai.

### B. Domain model

Entity `BrandScript`, **camelCase** đúng pattern H1/H2:

- `_id`, `ownerDeviceId`, `flowBlueprintId`, `brandProfileId`
- `createdAt`, `updatedAt`
- `status`: `draft | checking | blocked | unconfirmed | ready | failed`
- `originalityCheckVersion` (Number — `PHIEN_BAN` lúc kiểm)
- `beats[]`, mỗi beat:
  - `beatType` (kế thừa Blueprint, enum đóng)
  - `voiceoverTextVi`, `captionSuggestionVi`, `visualBriefVi`
  - `originalityFlag`: `clear | flagged | unconfirmed`
  - **[SỬA]** `flaggedExcerpt` — **chỉ cụm trong kịch bản MỚI**. Không có
    trường cho cụm gốc: dấu vân tay là băm một chiều, không đọc ngược ra chữ.
  - `complianceFlag`: `clear | violated`
  - `complianceExcerpt` — cụm vi phạm **và** câu trong `rangBuocKhongDuocNoi`
    đã kích hoạt nó (cái này có đủ chữ vì ràng buộc do chính người dùng nhập).

### C. Service / Engine

1. **Sinh kịch bản**: task `brand_script_rewrite`. Prompt server-side nhận
   Blueprint (trừu tượng) + BrandProfile. Yêu cầu model: giữ nhịp/số
   beat/chức năng kể chuyện; viết nội dung mới hợp `moTaSanPham`,
   `doiTuongKhach`, `toneGiong`, `usp`; **tuyệt đối không paraphrase sát hoặc
   mượn cấu trúc câu đặc trưng** từ Blueprint; tự tránh `rangBuocKhongDuocNoi`
   ngay lúc sinh (lớp phòng đầu, **không thay thế** bước kiểm sau).
2. **Kiểm tuân thủ** (`complianceFlag`): so khớp từng beat với
   `rangBuocKhongDuocNoi`. Dùng `chuanHoaSoKhop` để chữ hoa/dấu câu không
   giúp lách. Ưu tiên so khớp trực tiếp, không cần AI.
3. **[SỬA] Kiểm nguyên gốc** (`originalityFlag`): với mỗi beat, gọi
   `timTrungLap(<văn bản beat>, blueprint.evidenceFingerprint)` trên **cả ba**
   trường sinh ra (`voiceoverTextVi`, `captionSuggestionVi`, `visualBriefVi`).
   Áp bảng trạng thái ở Constraint #6.
4. Bất kỳ beat nào `violated` hoặc `flagged` ⇒ `status = blocked`.
5. Bất kỳ beat nào không kiểm được ⇒ `unconfirmed` (trừ khi đã có beat
   `blocked` — `blocked` được ưu tiên).
6. Chỉ khi TẤT CẢ beat `clear` cả hai cờ ⇒ `ready`.

**[SỬA] Về ngưỡng.** Bản gốc yêu cầu đo ngưỡng trước khi chốt — vẫn đúng, và
đây là trạng thái thật: ngưỡng hiện tại (**cụm 6 từ**, kèm nhánh dòng ngắn
2–5 từ) **kế thừa từ gate H2**, và ba ca paraphrase trong test H2c là **viết
tay**, không phải do mô hình sinh. H3 **phải đo lại bằng kịch bản mô hình thật
sinh ra** (≥2–3 ca paraphrase hợp lệ + ≥1 ca chép sát) rồi mới chốt, ghi lý do
vào `docs/TEST_LOG.md`. Đổi ngưỡng ⇒ **tăng `PHIEN_BAN`** của
`dau-van-tay.service.js` (Constraint #13).

### D. API contract

Bám `docs/API.md` và ownership pattern H1/H2.

- `POST /v1/brand-scripts` — nhận `flowBlueprintId`, `brandProfileId`; **kiểm
  chéo ownership của CẢ HAI** tham chiếu, không chỉ record mới.
- `GET /v1/brand-scripts` — list theo device. **[SỬA]** Loại các trường nặng
  khỏi truy vấn list nếu có (đúng cách `flow-blueprints` làm với
  `evidenceFingerprint`).
- `GET /v1/brand-scripts/:id` — kèm đủ cờ + excerpt để UI hiển thị.
- `POST /v1/brand-scripts/:id/regenerate-beat` — tạo lại một beat, **chạy lại
  cả hai bộ kiểm cho TOÀN BỘ script** (Constraint #11).
- **Không có endpoint nào cho client set `status = ready`** — status chỉ do
  engine tính.
- **[SỬA]** Lỗi ownership trả `404` (dùng chung mã cho "không tồn tại" và
  "của thiết bị khác"), đúng style H1/H2.

### E. Desktop UI

- Chọn một `FlowBlueprint` + một `BrandProfile` → tạo `BrandScript`.
- Hiện tiến trình thật (sinh → kiểm tuân thủ → kiểm nguyên gốc), **không bịa
  phần trăm** nếu không có số thật.
- Hiện theo từng beat: lời đọc, caption, visual brief, và cờ
  `clear/flagged/violated/unconfirmed`.
- **[SỬA] Beat `flagged`**: hiện **đúng cụm trong kịch bản mới** bị chặn, tô
  đậm tại chỗ trong lời đọc để người dùng sửa được ngay. **KHÔNG hiện
  side-by-side với cụm gốc** — dấu vân tay là băm một chiều, không có chữ gốc
  để trưng. Câu giải thích phải nói thẳng điều đó, đừng để người dùng tưởng
  hệ thống đang giấu thông tin.
- Beat `violated`: hiện đúng cụm vi phạm **và** đúng câu trong
  `rangBuocKhongDuocNoi` đã kích hoạt nó (phần này có đủ chữ).
- **[SỬA] Beat `unconfirmed`**: nói rõ **vì sao** chưa kiểm được (Blueprint cũ
  không có dấu vân tay / vùng phủ chạm trần / bằng chứng nguồn không đủ) —
  bốn nguyên nhân ở Constraint #6 cần bốn câu khác nhau, không gộp thành một
  câu "chưa kiểm được".
- Nút **"Dùng kịch bản này"** (sang H4) CHỈ khả dụng khi `ready`. Không có nút
  "bỏ qua cảnh báo, dùng luôn".
- Nút "Tạo lại beat này" cho beat `flagged`/`violated`.

### F. Tests

**Unit**
- Compliance bắt đúng cụm bị cấm; **không** báo nhầm câu hợp lệ có từ gần
  giống (≥2 ca).
- Originality bắt fixture chép gần nguyên văn; **không** báo nhầm ≥3 ca
  paraphrase hợp lệ — **[SỬA]** ít nhất một ca phải là **output mô hình thật**,
  không phải câu viết tay.
- **[SỬA]** Bảng trạng thái: `blocked` > `unconfirmed` > `ready`; và **cả bốn
  nguyên nhân `unconfirmed`** ở Constraint #6 đều ra `unconfirmed`.
- **[SỬA]** Script `ready` với `originalityCheckVersion` cũ hơn `PHIEN_BAN`
  hiện tại ⇒ đọc lại phải thành `unconfirmed`.

**Integration**
- Device A không đọc/sửa/xoá BrandScript của Device B.
- `POST` bị chặn nếu `flowBlueprintId` **hoặc** `brandProfileId` không thuộc
  device đang gọi (kể cả khi ID tồn tại và thuộc device khác) — trả `404`.
- `regenerate-beat` kiểm lại toàn bộ: beat A cũ `clear`, beat B tạo lại và vô
  tình `flagged` ⇒ cả script `blocked`.
- **[SỬA]** Blueprint **không có** `evidenceFingerprint` ⇒ script `unconfirmed`,
  **không bao giờ** `ready`.

**Regression** (mỗi mục phải ĐỎ khi gỡ chốt)
- Gỡ originality check (ép luôn `clear`) → đỏ với fixture chép nguyên văn.
- Gỡ compliance check → đỏ với fixture chứa cụm cấm.
- Cho client set `status = ready` qua API → đỏ.
- Gỡ "regenerate phải kiểm lại toàn bộ" → đỏ.
- **[SỬA]** Coi `kiemDuoc: false` như `clear` → đỏ.

**Live verification (bắt buộc, không mock)**
- **[SỬA] Bước 0**: chạy **một lượt H2 thật** trên prod để có `FlowBlueprint`
  thật mang `evidenceFingerprint`. Hiện chưa có bản ghi nào.
- Sinh BrandScript thật, review tay: đúng tone/USP/brand, tiếng Việt tự nhiên,
  không beat nào trùng câu nguồn.
- Ca cố tình: đặt `rangBuocKhongDuocNoi` cấm từ "tốt nhất", xác nhận nếu model
  lỡ sinh ra thì hệ thống **bắt được và block đúng**, không lọt.
- Ca cố tình: ép model paraphrase rất sát để xác nhận gate bắt được, không chỉ
  pass mọi lượt.

## Design Choice

- Dùng phép đo trùng lặp văn bản (n-gram), **không** embedding/cosine — khác
  domain với nguyên tắc "không cosine cho ảnh" ở C1, nhưng giữ đúng tinh thần:
  luôn trả excerpt đọc được.
- Chặn ở **cấp toàn script**, không ẩn riêng beat lỗi — nhất quán với C3
  ("không lặng lẽ bỏ một phần khi có lỗi") và với chính gate H2.
- **[SỬA]** Đánh đổi cốt lõi đã chốt: **giữ lời hứa "máy chủ không tích trữ
  câu chữ nguyên văn của người khác"**, chấp nhận mất khả năng trưng cụm gốc.
  Đây là quyết định của chủ dự án ngày 10/09, không phải giới hạn kỹ thuật.

## Success Criteria

1. BrandScript đúng nhịp/beat theo Blueprint, đúng tone/USP theo BrandProfile.
2. Không đường nào (UI hay API) xuất được kịch bản khi còn beat `blocked`
   hoặc khi `unconfirmed`.
3. Mọi beat bị chặn đều hiện excerpt/lý do đọc được, không phải thông báo lỗi
   chung.
4. `rangBuocKhongDuocNoi` được kiểm thật, có test chứng minh bắt được vi phạm
   và không báo nhầm.
5. Device A không truy cập được dữ liệu của Device B qua bất kỳ đường nào.
6. `regenerate-beat` luôn kiểm lại toàn bộ script.
7. **[SỬA]** Ngưỡng originality được chốt bằng **output mô hình thật**, ghi lý
   do trong `TEST_LOG.md`; đổi ngưỡng thì tăng `PHIEN_BAN`.
8. **[SỬA]** Blueprint không có dấu vân tay không bao giờ cho ra `ready`.

## Remaining Limits / Follow-ups

- Out-of-scope H3: sinh ảnh/audio/video, storyboard timing theo giây — đó là H4.
- **[SỬA]** Không trưng được cụm gốc bên nguồn (hệ quả của H2c).
- **[SỬA]** Bản ghi `FlowBlueprint` tạo trước 10/09 vĩnh viễn không kiểm được
  — không vá ngược được vì evidence gốc đã bỏ đi.
- **[SỬA]** Gate chống sao chép của H2 vừa nhạy hơn hẳn với tiếng Việt (do
  H2b) và **chưa có dữ liệu thật nào** về tỉ lệ chặn oan. H3 chồng thêm một
  gate cùng họ lên trên đó ⇒ lấy dữ liệu vài lượt H2 thật trước khi chốt
  ngưỡng H3.
- Ngôn ngữ nguồn không phải Anh/Việt: H3 vẫn chạy nếu Blueprint hợp lệ, nhưng
  **không cam kết** chất lượng tương đương cho tới khi có dữ liệu đo riêng.
- H4 chỉ nên bắt đầu sau khi H3 chạy ổn trên vài BrandScript thật và ngưỡng đã
  hiệu chỉnh bằng dữ liệu thật, không phải ngay sau khi H3 "test xanh".


---

# Triển khai (10/09/2026)

## Changed Files

| Tệp | Vai trò |
|---|---|
| `control_server/src/models/BrandScript.js` | **mới** — entity, bốn `lyDoChuaKiem` tách bạch |
| `control_server/src/services/kiem-kich-ban.service.js` | **mới** — hai lớp kiểm + bảng ưu tiên trạng thái |
| `control_server/src/routes/brand-scripts.js` | **mới** — 5 endpoint |
| `control_server/src/prompts/assist.js` | tác vụ `brand_script_rewrite` + schema + parse |
| `control_server/src/services/config.service.js` | giá mặc định 12 Vox |
| `control_server/src/models/JobResult.js` | thêm `action: 'brand_script'` |
| `control_server/src/app.js` | đăng ký route |
| `autodub/saas_client.py` | 5 hàm client |
| `autodub_gui/workers.py` | `BrandScriptWorker` |
| `autodub_gui/pages/brand_script_page.py` | **mới** — trang Viết kịch bản |
| `autodub_gui/pages/flow_blueprint_page.py` | nút mở trang H3 + signal |
| `autodub_gui/app.py` | đăng ký trang (nhóm `hidden`) |

## Ba quyết định đáng ghi

**1. Trang H3 KHÔNG nằm trên thanh bên.** Thanh bên đã kín ở màn 1080p —
thêm mục thứ 21 làm test `test_sidebar_no_overlap` đỏ (tràn 45px, bắt người
dùng cuộn). Thay vì thu nhỏ toàn bộ thanh bên, đặt lối vào ở cuối trang «Phân
tích cấu trúc». Đây cũng **đúng luồng hơn**: chưa phân tích nhịp thì chưa viết
kịch bản được. Dùng nhóm `hidden` trong `PAGES` — khuôn đã có sẵn cho
`ROW_EDITOR_LAUNCHER`.

**2. `regenerate-beat` gửi NGỮ CẢNH viết lại.** Bản dựng đầu gọi mô hình với
đầu vào **y hệt** lượt trước ⇒ mô hình trả gần như y hệt ⇒ nút "viết lại"
trông như hỏng trong khi vẫn tính tiền mỗi lần bấm. Nay gửi kèm số đoạn đang
sửa, các đoạn đang giữ (để bản mới còn ăn khớp), và **lý do** phải làm lại
(cụm bị cấm nào / cụm trùng nào trong kịch bản mình) để nó tránh đúng chỗ đã
sai. Có test canh.

**3. Kiểm là thuần văn bản, không gọi mô hình** (Constraint 12) — có test đọc
thẳng mã nguồn để chặn ai đó nối cổng AI vào bộ kiểm sau này.

## Live Verification (bắt buộc, không mock)

Gọi **Gemini 3.8 Flash thật** bằng ĐÚNG system prompt + schema của máy chủ,
rồi cho ĐÚNG `kiemToanBo()` của máy chủ chấm trên chính output đó. Hồ sơ brand
thật (nồi chiên không dầu), bằng chứng nguồn tiếng Việt thật, 5 beat.

| Ca | Kết quả |
|---|---|
| Kịch bản bình thường | `ready` — **0 báo nhầm** trên 5 đoạn × 3 trường |
| Mô hình LỠ viết cụm bị cấm | bắt đúng «máy rửa bát» ⇒ **cả kịch bản** `blocked` |
| Ép mô hình bám sát nguồn | bắt đúng «link ở giỏ hàng nha mọi» ⇒ `blocked` |

Chất lượng kịch bản (đọc tay): đúng giọng "như bạn bè mách nhau", dùng đúng
USP (3 phút, chống dính, máy rửa bát), đúng đối tượng (mẹ bỉm), tiếng Việt tự
nhiên. ~4,4 giây và ~1.200 token mỗi lượt.

**Dữ liệu hiệu chỉnh ngưỡng** (thứ Success Criteria #7 đòi): ngưỡng 6 từ
KHÔNG báo nhầm trên văn bản mô hình thật. Hai ca suýt trùng đều là cụm cũng có
trong **USP của chính brand** ("lòng nồi chống dính nên…") — tức chúng là chữ
của người dùng, không phải chép từ nguồn, nên không báo là ĐÚNG. Ca chép thật
bị bắt là một câu CTA nguyên văn.

**Phát hiện kèm theo**: mô hình CHỈ sao chép khi bộ khung Blueprint chứa sẵn
câu nguồn. Gate của H2 đã chặn chuyện đó ở đầu vào, và gate H3 bắt lại ở đầu
ra — hai lớp bọc nhau đúng ý đồ, không phải một lớp thừa.

## Remaining Limits / Follow-ups

- **Chưa chạy end-to-end qua app thật trên prod.** Kiểm chứng ở trên gọi thẳng
  mô hình + engine, chưa đi qua HTTP/billing/giao diện thật. Vẫn cần một lượt
  H2 thật để có `FlowBlueprint` thật rồi chạy H3 từ app.
- **`regenerate-beat` tính tiền một lượt đầy đủ** dù chỉ lấy một đoạn: mô hình
  vẫn sinh cả kịch bản rồi ta bỏ phần thừa. Giao diện đã nói thẳng điều này.
  Rẻ hơn được nếu tách một prompt riêng chỉ viết một đoạn — chưa làm.
- **Giá 12 Vox là số khởi điểm**, đo thật mới có ~1.200 token/lượt cho kịch bản
  5 đoạn; kịch bản 40 đoạn sẽ tốn hơn nhiều mà giá vẫn phẳng.
- **H4 chưa làm** — nút "Dùng kịch bản này" hiện chỉ báo "sẽ có ở bản sau".
- Ngưỡng mới đo trên **một** brand và **một** nguồn. Cần thêm vài ca thật
  trước khi coi là đã hiệu chỉnh.

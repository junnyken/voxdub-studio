# MINI-SPEC I3 — `scene_director` & Bản chỉ đạo hình ảnh

- **Parent phase:** Phase I — Kịch bản thành chỉ đạo hình ảnh
- **Scope ID:** I3
- **Tác giả:** Claude (phiên làm việc 22/09/2026), viết SAU khi đọc mã thật của H3/H4/renderer/catalog
- **Ngày:** 2026-09-22
- **Trạng thái:** Chờ chủ dự án duyệt phạm vi trước khi code

---

## Context

### Vì sao spec này do người trong cuộc viết

Ba mini-spec trước (I0, I0-FDE, I1+I2) do bên ngoài viết và **cả ba đều có tiền đề đã cũ**: D3 "đang đỏ" thì đã sửa xong, danh sách đóng gói "cần suy ra" thì đã suy ra từ lâu, lời khuyên "bỏ skip ở bước publish" nếu làm theo sẽ mở lại đúng lỗ hổng vừa bịt. Mỗi lần đều mất một vòng audit mới phát hiện.

Spec này viết sau khi đã đọc `autodub/product_video.py`, `autodub/du_an_tu_kich_ban.py`, `autodub/storyboard.py`, `control_server/src/prompts/assist.js`, `control_server/src/models/BrandScript.js` và chính catalog v1 vừa ship. Mọi con số dưới đây **đo được**, không suy đoán.

### Trạng thái đã xác nhận, kèm bằng chứng

1. **I1 đã đóng.** Vai `assist` có nhà cung cấp thật (Perplexity `sonar`), 10 lượt gọi thật, mã thoát 0. Đường rơi im lặng sang `translate` đã bịt (`CHUA_CO_NOI_GOI_TRO_LY`, 503, không kèm `retryAfter`). Commit `891c433`.
2. **I2 đã đóng.** Catalog v1: 6 nhóm, 22 mục. Commit `867d1f2`.
3. **Chỉ 4/22 mục là `supported`** — và đây là dữ kiện quan trọng nhất của I3:

   | Nhóm | Số mục | `supported` |
   |---|---:|---|
   | `shot` | 4 | — |
   | `composition` | 5 | — |
   | `motion` | 1 | `tinh` |
   | `pacing` | 4 | — |
   | `transition` | 3 | `cat_thang`, `fade_nhe`, `crossfade_ngan` |
   | `lighting_color` | 5 | — |

   `motion.tinh` nghĩa là "đứng yên" — vốn đã là hành vi mặc định. Nên **thứ duy nhất thật sự có thể CHỌN** là ba kiểu chuyển cảnh.

4. **Luồng H4 chưa bao giờ truyền `kieu_chuyen`** (`du_an_tu_kich_ban.py:365`, D1 `:272-274`) — luôn mặc định «mờ chồng». Nối lựa chọn vào luồng là việc của **I5**, không phải I3.
5. **`dung_du_an()` đòi ảnh cho TỪNG đoạn**, thiếu một đoạn ⇒ `ThieuAnh`, và docstring ghi rõ *"không tự sinh thay người dùng"*. Tức trong luồng H4 hôm nay, **người dùng phải tự có ảnh**.
6. **`scene_script` phục vụ luồng KHÁC.** Nó chỉ được gọi từ `autodub/product_video.py:319` — luồng ảnh sản phẩm dòng C, không phải H3→H4. Lời nhắc của nó mở đầu bằng *"video ngắn ghép từ vài ảnh sản phẩm"*. Vậy `scene_director` **không phải đổi tên `scene_script`**, mà là anh em phục vụ dây chuyền khác.
7. **Schema đã có, không cần dựng lại**: đoạn H3 có `beatType` · `voiceoverTextVi` · `captionSuggestionVi` · `visualBriefVi` · `originalityFlag`. Đoạn H4 (`DoanStoryboard`) có `thu_tu` · `beat_type` · `loi_doc` · `caption` · `visual_brief` · `bat_dau_s` · `ket_thuc_s`.
8. **Thời lượng do D1 suy từ giọng đọc thật** (`_moc_that`), cảnh cuối kéo tới hết tệp tiếng. Bản vá 21/09 vừa sửa đúng lỗi "4 giây cuối đứng hình" ở chỗ này.

### Hệ quả thẳng thắn cho I3

Gộp (3) + (4) + (5): **bản chỉ đạo hình ảnh hôm nay chủ yếu là lời khuyên cho NGƯỜI đi chọn/chụp ảnh, không phải lệnh cho máy dựng.** Khoảng 18/22 mục là gợi ý; ba kiểu chuyển cảnh tuy dựng được nhưng luồng H4 chưa nhận.

Spec này **không giấu điều đó**. Nếu I3 được viết như thể nó sinh ra "chỉ đạo quay phim tự động", sản phẩm sẽ hứa thứ không làm được — đúng lớp lỗi #5 và #6 của dự án.

### Quyết định kiến trúc phải giữ nguyên

- Lời nhắc thuộc máy chủ; máy khách gửi **tên tác vụ**, không gửi system prompt.
- Giá/hold/commit/refund đi qua cổng máy chủ hiện có. Giao diện không tự suy giá.
- Không rơi im lặng sang vai khác (vừa bịt ở I1).
- Không import engine nặng vào tiến trình chính.
- Catalog v1 là **nguồn duy nhất** của vốn từ; không hard-code danh sách thứ hai ở nơi khác.
- Không đụng thời lượng D1 suy từ audio thật.

---

## Goal

Cho phép người dùng lấy được, từ một BrandScript `ready`, một **Bản chỉ đạo hình ảnh** theo từng đoạn — dùng đúng vốn từ của catalog v1, nói rõ mục nào là gợi ý chọn ảnh và mục nào máy dựng được — để họ biết **cần chuẩn bị ảnh như thế nào** trước khi vào H4.

Không render gì. Không sinh ảnh. Không đổi thời lượng.

---

## Constraints (Guardrails)

1. **Audit trước khi sửa.** Không thêm tác vụ, schema, cửa API hay UI trước khi đọc cách `assist` dispatch, cách BrandScript lưu, và cách giá/đệm hoạt động.
2. **Không đổi nghĩa `scene_script`.** Nó phục vụ luồng ảnh sản phẩm dòng C. `scene_director` là tác vụ RIÊNG cho luồng H3→H4.
3. **Mô hình chỉ được trả mã enum có trong catalog v1.** Máy chủ **phải soi lại** đầu ra; mã lạ ⇒ từ chối cả lượt, không "tự sửa cho gần đúng". Đây chính là ranh giới I2 dựng ra để I3 dùng.
4. **Không hứa render.** Mọi mục `advisory_only` phải hiện ra là **gợi ý cho người**, không được trình bày như hiệu ứng máy sẽ làm. Bản chỉ đạo phải tự nói ra tỉ lệ này.
5. **Không đụng thời lượng.** Bản chỉ đạo không mang tham số thời gian ở bất kỳ nhóm nào. `pacing` là gợi ý cách viết/chọn hình, không phải lệnh cắt.
6. **Không sao chép phong cách nguồn.** Không lưu/suy ra bố cục, caption hay nhịp cụ thể của video tham khảo. Chỉ dùng vốn từ kỹ thuật phổ quát của catalog.
7. **Tiền phải đúng và idempotent.** Giá lấy từ `credit.cost.assist.*` như mọi tác vụ khác; cùng kịch bản + cùng phiên bản catalog ⇒ đọc đệm, không trừ lần hai.
8. **Một lượt gọi cho cả kịch bản, không phải mỗi đoạn một lượt.** Kịch bản H3 có thể tới 40 đoạn; gọi từng đoạn là nhân giá lên 40 lần. Theo đúng cách H3 đã làm.
9. **Không mở H4d, không cấu hình vai `image`, không sinh ảnh.**
10. **Không nối vào luồng dựng.** Việc H4 đọc bản chỉ đạo để chọn `kieu_chuyen` là **I5**. I3 dừng ở chỗ tạo ra và hiển thị bản chỉ đạo.
11. **Không tuyên bố chạy thật chỉ vì test xanh.** Cần lượt gọi mô hình thật trên kịch bản thật.

---

## Scope

### A. Audit Before Build

Phải trả lời, kèm `file:dòng`:

1. `assist` dispatch: thêm một tác vụ mới cần chạm những chỗ nào (allow-list, giá, đệm, sổ dùng, `JobResult.action` enum, `evals/cases.js`, `tests/hold.test.js`, `FEATURES.md` dòng giá). Dự án đã ghi rõ ở `docs/BACKLOG_PHASE_H.md`: **thêm một tác vụ trợ lý là bốn chốt đỏ ngay** — liệt kê đủ bốn.
2. BrandScript lưu ở đâu, có chỗ nào gắn thêm dữ liệu theo đoạn mà không phá schema cũ không.
3. Đệm: khoá đệm dựng từ gì, có đủ để phân biệt hai kịch bản khác nhau và hai phiên bản catalog khác nhau không.
4. Cửa đọc catalog (`GET /v1/config/visual-direction-catalog`) và bộ soi (`visual-catalog.service.js`) — tái dùng thế nào để **không** dựng bộ soi thứ hai.
5. Giao diện: trang «Viết kịch bản» hiện có chỗ nào đặt được lối vào mà không phá thanh bên (đã KÍN ở 1080p — xem bài học H3).

### B. Tác vụ `scene_director`

**Đầu vào** (một lượt cho cả kịch bản):
- Danh sách đoạn: `beatType`, `voiceoverTextVi`, `visualBriefVi` (KHÔNG gửi `captionSuggestionVi` — caption là việc của H3, gửi thêm chỉ tốn token).
- Hồ sơ thương hiệu: tông giọng + điều không được nói.
- **Danh sách mã enum hợp lệ của catalog v1**, kèm nhãn tiếng Việt, để mô hình chọn trong đó thay vì tự nghĩ từ.

**Đầu ra**, mỗi đoạn:
- Tối đa **một mã mỗi nhóm** (6 nhóm ⇒ tối đa 6 mã/đoạn). Nhiều hơn là nhiễu, không phải chi tiết.
- Một câu **lý do ngắn** bằng tiếng Việt (≤ 25 chữ) — vì sao chọn vậy cho đoạn này.
- Được phép **bỏ trống** một nhóm nếu đoạn đó không cần.

**Máy chủ soi lại trước khi lưu:**
- Mã lạ / trùng nhóm / vượt trần ⇒ **từ chối cả lượt**, mã lỗi riêng, hoàn hold.
- Mã thuộc `advisory_only` ⇒ hợp lệ, nhưng đánh dấu rõ là gợi ý.
- Không mục nào được mang tham số thời gian.

**Giá**: một khoá `credit.cost.assist.scene_director` mới, giá khởi điểm do chủ dự án chốt. **Không** làm biến thể có ảnh ở v1 — giữ rẻ, và luồng H4 vốn chưa có ảnh lúc chạy bước này.

### C. Bản chỉ đạo hình ảnh (Visual Direction Sheet)

**Lưu**: gắn với BrandScript, có `catalog_version` đã dùng. Kịch bản đổi hoặc catalog lên đời ⇒ bản chỉ đạo cũ **được đánh dấu là cũ**, không tự xoá, không tự chạy lại (tốn tiền).

**Hiển thị** — đây là chỗ dễ nói sai nhất, phải đúng:
- Mỗi đoạn hiện các mã đã chọn kèm nhãn tiếng Việt + câu lý do.
- Mục `advisory_only` và mục `supported` **phải phân biệt được bằng mắt**, kèm câu giải thích khác nhau: *"gợi ý khi bạn chọn/chụp ảnh"* so với *"máy dựng được"*.
- Đầu bản phải có một câu nói thẳng tỉ lệ, đại ý: *"Phần lớn mục dưới đây là gợi ý để bạn chuẩn bị ảnh. Hiện chỉ có kiểu chuyển cảnh là thứ máy tự dựng được — và luồng Dựng video chưa đọc lựa chọn đó."*
- **Không** có nút «Áp dụng», «Render», «Sinh ảnh».

### D. API

Theo style `docs/API.md`. Ưu tiên tái dùng cửa `/v1/brand-scripts/:id/...` đã có thay vì dựng nhánh mới, nếu audit cho thấy hợp.

---

## Test Plan

### Unit
1. Mã enum lạ ⇒ từ chối cả lượt, không lưu một phần.
2. Hai mã cùng nhóm cho một đoạn ⇒ từ chối.
3. Số đoạn trả về khác số đoạn gửi đi ⇒ từ chối.
4. Mục mang tham số thời gian ⇒ từ chối.
5. `advisory_only` lưu được nhưng luôn kèm cờ gợi ý.
6. Khoá đệm phân biệt được: hai kịch bản khác nhau · cùng kịch bản nhưng catalog đổi phiên bản.
7. Bản chỉ đạo không bao giờ chứa văn bản lấy từ video tham khảo.
8. Kịch bản chưa `ready` ⇒ chặn trước khi gọi mô hình (không trừ tiền), cùng mẫu RS-3.

### Integration
9. Một lượt gọi cho cả kịch bản — không phải N lượt.
10. Gọi lại cùng kịch bản ⇒ đọc đệm, không trừ lần hai.
11. Thiếu vai `assist` ⇒ 503 `CHUA_CO_NOI_GOI_TRO_LY` (chốt I1 còn nguyên).
12. Bản chỉ đạo cũ không bị tự xoá khi kịch bản đổi.

### Chứng minh ĐỎ khi gỡ (bắt buộc)
- Bỏ phép soi enum ⇒ test mã lạ đỏ.
- Cho phép nhiều mã một nhóm ⇒ test trùng nhóm đỏ.
- Gộp `advisory_only` với `supported` ở tầng hiển thị ⇒ test phân biệt đỏ.
- Gọi từng đoạn thay vì một lượt ⇒ test số lượt đỏ.

### Live
Một lượt gọi mô hình **thật** trên một BrandScript `ready` thật. Ghi: số đoạn, mã đã chọn, token vào/ra, giá, độ trễ, và **soi tay** xem lý do mô hình đưa có nghĩa không — hay chỉ là chữ đẹp.

---

## Success Criteria

1. `scene_director` là tác vụ riêng trong allow-list, có giá riêng, lời nhắc ở máy chủ.
2. Một lượt gọi sinh bản chỉ đạo cho cả kịch bản; gọi lại ⇒ đệm, không trừ lần hai.
3. Máy chủ từ chối mọi đầu ra không khớp catalog v1; không có đường "tự sửa cho gần đúng".
4. Bản chỉ đạo lưu kèm `catalog_version`; kịch bản/catalog đổi ⇒ đánh dấu cũ, không tự chạy lại.
5. Giao diện phân biệt rõ **gợi ý cho người** với **máy dựng được**, và nói thẳng tỉ lệ. Không có nút hứa render.
6. Không đụng thời lượng D1; không mở H4d; không nối vào luồng dựng.
7. Bốn chốt "thêm tác vụ trợ lý" đều xanh (FEATURES dòng giá · `evals/cases.js` · `tests/hold.test.js` · `JobResult.action`).
8. Có ít nhất một lượt gọi mô hình thật, có bằng chứng, và có người soi tay chất lượng đầu ra.

---

## Out of Scope

- Nối bản chỉ đạo vào luồng H4 để chọn `kieu_chuyen` — **I5**.
- Sửa lựa chọn theo từng cảnh trên giao diện, preset theo thương hiệu — **I4/I6**.
- Sinh ảnh, vai `image`, H4d, calibration.
- Thêm mục mới vào catalog (vd ba kiểu chuyển cảnh còn lại) — việc riêng, v2 của I2.
- Đổi giá H3; vẫn chờ 10–20 lượt thật.
- Sửa câu chữ giá gõ tay trong giao diện — việc riêng đã ghi nhận.

---

## Quyết định của chủ dự án — đã chốt 22/09/2026

1. **Catalog v2 làm TRƯỚC I3.** Thêm ba kiểu chuyển cảnh còn lại (trượt trái, trượt lên, mở vòng — có thật trong `product_video.KIEU_CHUYEN`), nâng `supported` từ 4/22 lên **7/25**. I3 chỉ bắt đầu sau khi v2 đóng, để bản chỉ đạo có đủ thứ để chỉ đạo.

   Ba kiểu mới **phải được đo như v1 đã làm**: chạy ffmpeg thật trên fixture nhiều cảnh, chứng minh giữ đúng hợp đồng thời lượng D1/H4c-1 và **không để lại đuôi mất hình**. Thêm thẳng vào JSON mà không đo là làm hỏng chính điều khiến catalog đáng tin.

2. **Giá `scene_director`: 5 Vox (giá khởi điểm).** Đầu vào ngang `brand_script_rewrite` (đọc cả kịch bản + hồ sơ brand) nhưng đầu ra nhẹ hơn hẳn — vài mã enum + câu lý do ngắn, không phải viết trọn lời đọc. Nằm giữa `scene_script` (3) và `brand_script_rewrite` (12), lệch về phía thấp.

   Như mọi khoá `credit.cost.*`, giá này **đổi được lúc chạy** trên trang quản trị, không cần phát hành lại. Con số cuối chốt theo dữ liệu thật, cùng cách D2 đang chờ cho H3.

3. **Không đảo sang I5.** Câu hỏi "18/22 mục chỉ là gợi ý thì I3 có đáng làm không" được trả lời bằng quyết định (1): nâng số mục dựng được trước, rồi làm I3.

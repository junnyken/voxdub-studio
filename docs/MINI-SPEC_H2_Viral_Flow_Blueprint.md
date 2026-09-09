# MINI-SPEC H2 — Viral Flow Blueprint

**Ngày**: 08–09/09/2026 · **Trạng thái**: đã xong Scope A–E
**Phase**: H "Viral Flow Clone & Brand Rewrite" (xem `docs/PLAN.md`)
**Phụ thuộc**: H1 (Hồ sơ Brand) đã xong; H2a (OCR Read Layer) đã xong — H2
không mở được trước khi H2a đóng gap đọc nội dung chữ.

## 1. Mục tiêu và ranh giới

Phân tích **cấu trúc kể chuyện** của một video tham khảo: chia dòng thời gian
thành các *beat* và nói mỗi beat làm nhiệm vụ gì (mở đầu níu chân, nêu vấn đề,
đưa bằng chứng, cao trào, kêu gọi hành động…).

**KHÔNG thuộc H2**: đọc Hồ sơ Brand, viết lại kịch bản, sinh ảnh/giọng đọc,
dựng video. Đó là H3/H4, chưa làm. H2 chỉ mô tả cấu trúc của video nguồn.

## 2. Constraint quan trọng nhất — trừu tượng hoá, không sao chép

Output **không bao giờ** được chứa transcript/caption gốc nguyên văn. Đây
không phải lời dặn trong prompt mà là **chốt bằng mã**, vì prompt thì mô hình
lách được:

- `coSaoChepNguyenVan()` bắt chuỗi **6 từ liên tiếp** trùng giữa beat và bằng
  chứng nguồn (ngưỡng đủ dài để không bắt oan cụm trùng ngẫu nhiên).
- Caption ngắn 2 từ kiểu `STOP SCROLLING` không đủ 6 từ để bắt, nên có thêm
  nhánh so khớp cụm ngắn (`TOI_THIEU_TU_DE_KIEM_NGAN = 2`).
- Một beat chép nguyên văn **huỷ CẢ kết quả**, không chỉ lọc riêng beat đó —
  vì một lần sao chép lọt là hỏng cam kết của cả tính năng.

## 3. Kiến trúc — nặng ở máy người dùng, nhẹ ở máy chủ

| Việc | Chạy ở đâu |
|---|---|
| Tải video, tách tiếng, chép lời (ASR), đọc chữ trên hình (OCR) | **máy người dùng** |
| Phân tích cấu trúc (một lượt gọi mô hình) | máy chủ |
| Lưu kết quả | máy chủ (MongoDB) |

Máy chủ **không** nhận video, **không** có job nền, **không** xử lý nặng —
route chỉ nhận *bằng chứng đã trích*, gọi mô hình một lượt, rồi lưu.

`transcript`/`ocrEvidence` chỉ dùng **tạm** để gọi mô hình, **không lưu lại
thô** (Scope B). Entity không có field nào chứa bằng chứng thô, cố ý.

Lấy mẫu khung hình **thích ứng** (`moc_lay_mau_thich_ung`): 0–5 giây đầu và 5
giây cuối lấy mỗi 0,2 giây; đoạn giữa mỗi 0,5 giây. Lý do dày ở hai đầu: hook
và CTA là chỗ caption đổi nhanh nhất, mà H2a đã đo được caption 0,5 giây bị bộ
lấy mẫu thưa cũ bỏ lọt hoàn toàn (0/5 khung trúng).

> **Cập nhật H2b (09/09)**: bước đọc chữ nay có bộ đọc thay được. Có cấu hình
> máy chủ thì nội dung chữ được đọc lại bằng mô hình nhìn ảnh để **ra đúng dấu
> tiếng Việt** — RapidOCR tại máy không phát ra được dấu. Xem
> `docs/MINI-SPEC_H2b_Doc_Chu_Co_Dau.md`.

## 4. Dữ liệu

`FlowBlueprint` (`control_server/src/models/FlowBlueprint.js`), cách ly theo
`ownerDeviceId` — cùng quy ước H1, hệ thống không có khái niệm "tài khoản"
tách khỏi thiết bị.

Hai vocabulary **đóng** (đóng ở cả schema Mongo, JSON schema gửi mô hình, và
bước validate — một nguồn sự thật, ba nơi dùng):

- `beatType`: `hook, problem_context, tension, proof, demonstration, payoff,
  twist, objection, cta, transition, unknown`
- `evidenceStatus`: `no_text, unconfirmed, unavailable, failed, ok` — giữ đúng
  bốn trạng thái tách bạch của H2a, không trộn "chưa cài" với "không thấy chữ".

## 5. API

`/v1/flow-blueprints` — `GET /`, `GET /:id`, `POST /`, `DELETE /:id`. Chi tiết
khuôn dữ liệu và mã lỗi: `docs/API.md`.

`POST /` idempotent theo `jobId`. Giá lấy từ
`credit.cost.assist.viral_flow_blueprint` (mặc định 8 Vox), **trừ SAU KHI**
phân tích xong. Thiếu Vox (`402`) hoặc mô hình lỗi (`503`) đều **không tạo bản
ghi và không trừ tiền**.

**Khoảng trống đã biết, cố ý**: entity có `userReviewNote` (Scope E nhắc tới
việc cho người dùng ghi chú lên beat) nhưng bản đặc tả không liệt kê endpoint
sửa trường này, nên **chưa thêm** `PATCH`/`PUT` — không mở API ngoài phạm vi
đã chốt. Trang trong app hiện chỉ hiển thị, không có ô sửa ghi chú.

## 6. Giao diện

Trang **Phân tích cấu trúc video tham khảo**
(`autodub_gui/pages/flow_blueprint_page.py`, mục thứ 20 trên thanh bên).

## 7. Tests

- **Node 23**: `flow-blueprints-route.test.js` (11) — cách ly theo thiết bị
  bằng hai thiết bị THẬT (không giả lập), 404 đúng cho thiết bị lạ ở cả
  GET/DELETE, không lộ transcript/OCR thô ra response;
  `flow-blueprint-schema.test.js` (10) — vocabulary đóng khớp giữa schema và
  model, beat sai khoảng thời gian bị loại, kết quả rỗng → `null` chứ không
  phải "ready với 0 beat"; `ai-gateway-gemini-schema.test.js` (2).
- **Python**: `test_flow_blueprint.py`, `test_flow_blueprint_page.py`,
  `test_saas_client_flow_blueprint.py` — trích bằng chứng, gộp quan sát liên
  tiếp, guardrail bắt buộc dùng `read_text_regions()` (giữ nội dung chữ) chứ
  không phải `detect_text_regions()` (vứt nội dung chữ).

## 8. Remaining Limits / Follow-ups

- **H3** (viết lại kịch bản theo Hồ sơ Brand) và **H4** (dựng video) chưa làm;
  H3 cần cả H1 lẫn H2.
- Không có endpoint sửa `userReviewNote` (mục 5).
- Giá 8 Vox là **số khởi điểm**, chưa soi bằng chi phí token thật.
- Bộ chặn sao chép nguyên văn trở nên **nhạy hơn hẳn với tiếng Việt** sau khi
  H2b bật (bằng chứng OCR nay có dấu đầy đủ) — xem mục "Remaining Limits" của
  `docs/MINI-SPEC_H2b_Doc_Chu_Co_Dau.md`.

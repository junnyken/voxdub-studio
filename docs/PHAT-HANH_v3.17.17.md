# v3.17.17 — bản để chạy pilot H2→H3

> Bản `v3.17.16` (12/09) **không có** các bản vá dưới đây. Đừng dùng nó cho
> pilot: hai trong số đó đụng thẳng vào tiền của bạn.

## Phải đọc trước khi chạy pilot

### 1. E6 câu C.4 — đây là lý do bản này tồn tại

Lượt chạy 12/09 để lại một tệp chẩn đoán thiếu hai số đo, và nguyên nhân đã tìm
ra: **tệp worker OCR chạy thật là bản CŨ**, trong khi mã trong kho đã mới. Bản
`v3.17.16` bạn đang có **vẫn mang worker cũ đó**.

Từ bản này, worker tự khai đời của nó và phía app ghi lại nó đã chạy tệp nào.
Nên lượt chạy tới sẽ cho **một trong hai** kết quả, và cả hai đều dùng được:

- có `khoi_dong_s` + `quet_s` trong `data/ocr_chan_doan.json` ⇒ **trả lời được
  câu C.4**, mở đường cho việc cắt thời gian OCR (hiện chiếm 84% cả lượt);
- hoặc câu *"worker OCR đời 1 (bản cũ…) — tệp đang chạy: C:\\…"* ⇒ nói thẳng
  còn bản cũ nằm ở đâu để dọn.

**Việc bạn cần làm:** chạy xong một lượt H2, gửi lại tệp
`<thư mục dự án>/data/ocr_chan_doan.json`.

### 2. Hai lỗi ĐỤNG TIỀN đã sửa (RS-4, RS-5)

- **RS-4 — trừ tiền hai lần.** Nút «Viết kịch bản» bị mở lại giữa lúc đang
  chạy, bởi một lượt tải danh sách chạy nền về đích trước. Bấm thêm một cái là
  **12 Vox nữa**.
- **RS-5 — cổng sang H4 mở bằng phán quyết đã bị huỷ.** Sau lỗi «nguồn đã bị
  xoá», giao diện vẫn giữ bản sao `ready` cũ; bấm lại kịch bản đó từ lịch sử là
  đi tiếp sang H4 bằng đúng thứ máy chủ vừa nói là không kiểm được.

### 3. Chặn trước khi trừ tiền (RS-3, RS-18)

- Lượt phân tích cấu trúc **không có dấu vân tay bằng chứng** thì kịch bản viết
  ra sẽ **không bao giờ** được duyệt. Nay máy chủ chặn ngay ở cửa và nói rõ
  **chưa trừ Vox**, thay vì thu 12 Vox rồi trả về một kịch bản không dùng được.
- Hết hạn mức kiểm ảnh trong ngày thì **không vẽ** (ảnh chưa kiểm không được
  ghép vào video), thay vì vẽ xong mới phát hiện.

### 4. Dễ đọc hơn

- Cột **Trạng thái** ở trang phân tích nay là tiếng Việt (*Đang chờ / Đang chạy
  / Xong / Hỏng*), không còn `queued`/`ready`/`failed`.
- **Mất mạng không còn hiện ra như "chưa có gì".** Trước đây danh sách rỗng vì
  hỏng mạng trông y hệt danh sách rỗng thật — dễ khiến bạn đi tạo lại hồ sơ
  mình đang có.
- Đoạn kịch bản thiếu lời đọc: câu lỗi nói **đúng số đoạn**, không bắt bạn dò.
- Thư mục ảnh kết quả không còn sót tệp tạm `_anh_kiem_tam.jpg`.

## Chạy pilot thế nào

Runbook đầy đủ: `docs/PILOT_PHASE_H.md`. Tóm tắt bốn điều dễ quên nhất:

| Việc | Vì sao |
|---|---|
| **Hai** video, không phải một | Một video caption Việt cháy sẵn để kiểm đọc chữ CÓ DẤU; một video tiếng Anh có cấu trúc bán hàng rõ để chấm chất lượng phân tích nhịp |
| Ví còn **60–80 Vox** | H2 tốn 8, đọc chữ 8 mỗi lô 6 khung, H3 tốn 12 |
| Đã cài bộ OCR | Chưa cài thì bước đọc chữ báo *"chưa cài"*, không phải *"không có chữ"* |
| Mở **Nhật ký** lúc chạy | Dòng `Đọc chữ qua máy chủ: N khung → M đoạn → gửi K khung` là bằng chứng duy nhất chỉ có ở đó |

**Thứ duy nhất phải xác nhận bằng MẮT**: caption tiếng Việt hiện ra có **đúng
dấu** không (`Các bạn sẵn sàng`, không phải `Cuc ban san sang`). Mọi mục khác
script `scripts/bao_cao_pilot_phase_h.py` gom hộ.

**Cổng 50 Vox** vẫn còn: vượt ngưỡng thì app hỏi trước khi tiêu. Bấm «Bỏ qua»
vẫn chạy tiếp và vẫn ghi tệp chẩn đoán — **0 Vox**.

## Chưa có trong bản này

- Cổng trợ lý và sinh ảnh vẫn **tắt** ở máy chủ: cần thao tác quản trị (thêm
  nhà cung cấp cho vai `assist` và `image`), không phải việc lập trình.
- **RS-16** còn mở, cố ý: ảnh AI của H4d chưa đi qua đủ ba phép kiểm tuân thủ.
  Không ảnh hưởng pilot H2→H3, nhưng **phải đóng trước khi bật cửa sinh ảnh**.

# H2a — OCR Read Layer: gap chính xác (audit dừng H2 tại Scope A)

> **Kết luận (08/09/2026): H2 KHÔNG được triển khai tiếp.** Audit OCR theo
> đúng cổng chặn mà mini-spec H2 tự đặt ra ("nếu OCR chỉ trả vùng chữ, DỪNG
> H2 ở audit") — kết quả: **đúng vậy, OCR hiện tại chỉ trả vùng chữ (toạ độ
> + độ tin cậy + khung hình), không trả nội dung chữ đã đọc được.** Không
> có Flow Blueprint nào được build. Đây là báo cáo gap, không phải mini-spec
> đã hoàn thành.

## Câu hỏi audit (Scope A của H2)

Module OCR (`autodub/media/text_regions.py` — được gọi từ trang Phụ đề/tính
năng xoá chữ, `autodub_gui/style_dialog.py`) có trả về:
1. Text đã đọc được? → **KHÔNG.**
2. Timestamp/frame range? → **CÓ** (`anh` = chỉ số khung, `t_start`/`t_end`
   sau `gan_khoang_thoi_gian()`).
3. Confidence? → **CÓ** (`confidence`, giữ nguyên từ engine).

## Bằng chứng — đọc mã VÀ đo thật (không chỉ đoán từ code)

Đọc cả hai đường xử lý OCR trong dự án (subprocess `.venv-ocr` — đường
chính trên bản đóng gói, và in-process — đường dự phòng dev/test):

- `autodub/media/text_regions_worker.py:56-70` (đường chính, chạy trong
  `.venv-ocr`)
- `autodub/media/text_regions.py:190-202` (`_detect_in_process`, đường
  dự phòng)

Cả hai đều lặp `for box, text, confidence in result:` (đúng khuôn trả về
gốc của RapidOCR), dùng `text` **CHỈ để lọc dòng rỗng**
(`if not text.strip(): continue`) rồi **KHÔNG đưa `text` vào dict trả về**
— dict chỉ có `anh`, `x`, `y`, `w`, `h`, `confidence`. Đây không phải suy
đoán từ đọc mã — đã **đo thật** bằng RapidOCR thật trên máy:

```
Ảnh test: dựng bằng PIL, có chữ "SUBSCRIBE NOW FOR MORE" ở đáy khung hình.

Gọi THẲNG RapidOCR (không qua app):
  text= 'SUBSCRIBE NOW FOR MORE'  confidence= 0.9954  box= [[40,300],[173,300],[173,313],[40,313]]
  → Engine ĐỌC ĐƯỢC chữ, đầy đủ và đúng.

Gọi qua detect_text_regions() (đúng hàm app dùng thật ở style_dialog.py):
  {'x': 0.0469, 'y': 0.8306, 'w': 0.239, 'h': 0.0415, 'confidence': 0.995}
  → KHÔNG có khoá "text". Nội dung "SUBSCRIBE NOW FOR MORE" bị vứt đi ở
    tầng wrapper, dù engine gốc đã đọc đúng.
```

Quét toàn repo xác nhận `text_regions.py`/`text_regions_worker.py` là **nơi
DUY NHẤT** trong dự án gọi RapidOCR/bất kỳ engine OCR nào — không có đường
đọc caption nào khác đang tồn tại song song mà H2 có thể tái dùng.

## Gốc rễ — vì sao gap này tồn tại (không phải lỗi, là phạm vi cũ)

`text_regions.py` được build cho **mini-spec V5** (xem docstring đầu tệp:
"CHỈ thay đổi NGUỒN toạ độ rectangle... KHÔNG đổi cách áp dụng blur") — mục
tiêu gốc là tự động hoá việc **phát hiện VÙNG cần làm mờ/xoá**, không phải
đọc nội dung. Việc vứt `text` là cố ý và đúng cho mục tiêu V5, chỉ là mini-
spec H2 (2026-09-08) cần một khả năng KHÁC (đọc nội dung) mà module này
chưa từng có, chứ không hỏng so với mục đích ban đầu của nó.

## Việc cần làm để đóng gap (chưa làm, cần chốt trước khi H2 tiếp tục)

Engine (RapidOCR) **đã có sẵn khả năng đọc text** — không cần đổi engine
hay cài thêm gì. Việc cần làm là kỹ thuật vừa phải, không phải nghiên cứu
mới: thêm một hàm ĐỌC (song song với `detect_text_regions`, không sửa nó —
tránh phá hành vi blur đang chạy đúng) trả về
`[{"text", "confidence", "anh"/"t_start"/"t_end", "x","y","w","h"}, ...]`,
threading `text` qua cả hai đường (subprocess worker JSON + in-process).

Ba điểm CHƯA kiểm chứng, cần xác nhận trước khi tính đây là "OCR đọc được
caption" theo đúng nghĩa H2 cần:

1. **Ngôn ngữ**: `RapidOCR()` khởi tạo KHÔNG truyền tham số ngôn ngữ nào —
   dùng mặc định của thư viện (thường là Trung+Anh). Video tham khảo H2
   nhắm tới (đối thủ/KOL viral) có thể có caption tiếng Việt hoặc ngôn ngữ
   khác — CHƯA đo được độ chính xác đọc trên caption tiếng Việt thật.
2. **Caption động** (chữ chạy/xuất hiện dần theo hiệu ứng, phổ biến ở
   video ngắn viral): mẫu quét hiện tại là vài khung RẢI ĐỀU cả video (dùng
   cho blur, chấp nhận bỏ sót vì hậu quả nhẹ — làm mờ thiếu 1 đoạn). H2 cần
   ĐỘ PHỦ cao hơn nhiều để dựng blueprint đúng nhịp — số khung/giây cần
   quét lại chưa có số đo thật.
3. **Chất lượng đọc trên video nén/chữ nhỏ**: test hiện có
   (`test_real_encoded_video_detects_vietnamese_and_faded_watermark`) xác
   nhận PHÁT HIỆN VÙNG đúng trên video mã hoá thật, nhưng không kiểm ĐỘ
   CHÍNH XÁC của text đọc được (vì trước giờ không cần) — cần đo riêng.

## Không nằm trong phạm vi báo cáo này (đúng constraint H2 gốc)

Không tạo `FlowBlueprint`, không thêm API/UI nào, không đổi
`detect_text_regions()` hiện có (đang chạy đúng cho tính năng blur, không
được đụng vào khi chưa có yêu cầu). Không có test mới — đây là audit đọc +
đo, không phải mã sản phẩm.

## Khuyến nghị

Nếu muốn tiếp tục hướng "Viral Flow Clone", cần MỘT quyết định của chủ dự
án trước khi viết mini-spec kỹ thuật cho lớp đọc OCR mới: có chấp nhận chất
lượng đọc caption "chưa kiểm chứng cho tiếng Việt, mặc định RapidOCR" ở bản
đầu hay không, và mức độ phủ khung hình cần thêm (đổi từ "vài khung đại
diện" sang "quét dày" sẽ làm chậm hẳn bước phân tích — cần số đo thời gian
thật trước khi chốt). Sau khi có quyết định đó, H2a (đóng gap) có thể viết
thành mini-spec riêng, rồi H2 (Flow Blueprint) mới nối tiếp được.

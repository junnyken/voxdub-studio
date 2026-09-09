# H2a — OCR Read Layer: gap chính xác + đóng gap (audit dừng H2 tại Scope A)

> **Cập nhật (08/09/2026, cùng ngày): GAP ĐÃ ĐÓNG — H2a XONG.** Phần đầu
> tài liệu này (giữ nguyên bên dưới) là báo cáo audit: OCR hiện tại
> (`detect_text_regions()`, V5) chỉ trả vùng chữ, cố ý vứt nội dung. Theo
> đúng mini-spec H2a (spec hẹp, riêng) đã thêm `read_text_regions()` — lớp
> ĐỌC song song, không đổi hành vi `detect_text_regions()` cho caller cũ.
> **H2 (Flow Blueprint) vẫn CHƯA mở lại** — H2a chỉ đóng đúng gap OCR, chưa
> có quyết định nào về ngôn ngữ/mật độ lấy mẫu cho H2 dùng thật. Chi tiết
> triển khai, số đo live verification, và giới hạn còn lại ở mục "Triển
> khai H2a" cuối tài liệu này và `docs/TEST_LOG.md` mục "H2a — OCR Read
> Layer".

> **Kết luận audit gốc (08/09/2026): H2 KHÔNG được triển khai tiếp** (lúc
> viết audit này). OCR hiện tại chỉ trả vùng chữ (toạ độ + độ tin cậy +
> khung hình), không trả nội dung chữ đã đọc được. Không có Flow Blueprint
> nào được build. Đây là báo cáo gap ban đầu, phần dưới giữ nguyên làm bằng
> chứng audit — xem mục "Triển khai H2a" ở cuối cho phần đã đóng.

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

---

## Triển khai H2a (08/09/2026, cùng ngày với audit)

Chủ dự án gửi mini-spec hẹp ngay sau khi đọc báo cáo trên, chốt rõ: **chỉ
đóng gap OCR-read, không mở lại H2**. Đã build đúng phạm vi đó.

### Đo thêm trước khi build (Audit Before Build của chính H2a)

Ba việc mini-spec H2a yêu cầu đo trước khi code, cả ba đều đo bằng dữ liệu
thật (ảnh/video dựng bằng PIL/ffmpeg, gọi thẳng RapidOCR — không đoán):

1. **Caller của `detect_text_regions()`**: quét toàn repo — chỉ MỘT nơi gọi
   (`autodub_gui/style_dialog.py`), dùng đúng `{x,y,w,h,confidence[,t_start,
   t_end]}`. Xác nhận an toàn để thêm hàm mới song song mà không đụng caller
   này.
2. **Ngôn ngữ**: model bundled sẵn của gói `rapidocr-onnxruntime` là
   `ch_PP-OCRv4_rec_infer.onnx` (từ điển ký tự Trung + Latin cơ bản, KHÔNG
   có dấu thanh tiếng Việt). Đo thật bằng câu "Đăng ký kênh để không bỏ lỡ
   video mới!" (dựng ảnh, font DejaVu Sans có dấu đầy đủ): engine đọc ra
   **"Dang ky kenh de khong bo lo video moi!"** — MẤT TOÀN BỘ dấu thanh,
   nhưng confidence vẫn cao (0,951). Đo thêm trên video nén THẬT có sẵn
   trong repo (`tap01_clip.mp4`, phụ đề cứng song ngữ Anh-Việt): cùng hiện
   tượng, có chỗ còn sai cả ký tự gốc chứ không chỉ mất dấu (vd "Các bạn"
   đọc ra "Cuc ban"), confidence vẫn 0,90-0,997. **Kết luận: confidence
   KHÔNG phải tín hiệu cho lỗi mất-dấu-tiếng-Việt** — model đọc sai một
   cách tự tin. Đây là giới hạn của MODEL bundled sẵn, không phải lỗi code;
   không đổi/thêm model trong phạm vi H2a (Guardrail 2 — chưa chứng minh đủ
   để mở rộng, và RapidOCR pip package hiện chỉ bundle đúng một model nhận
   dạng).
3. **Mật độ lấy mẫu khung hình**: bộ lấy mẫu cũ (`style_dialog.py`,
   `_moc_lay_mau()`) rải 5-24 khung ĐỀU CẢ VIDEO, dựng cho watermark/phụ đề
   cháy nằm yên hàng chục giây. Đo thật: dựng video 3 giây, chữ "FLASH SALE"
   chỉ hiện từ giây 0,15 đến 0,65 (0,5 giây) — bộ lấy mẫu cũ (5 mốc:
   0,06/0,78/1,50/2,22/2,94) **bỏ lọt HOÀN TOÀN** (0/5 khung trúng). Lấy mẫu
   mỗi 0,2 giây bắt được (khung tại 0,2s/0,4s/0,6s đều đọc đúng "FLASH
   SALE", confidence 0,988). Đo thêm chi phí: ~1,23 giây/khung trên CPU
   (ảnh 640×360, đã warmup) — lấy mẫu dày cho video dài là chi phí thật,
   không tự áp đặt mật độ trong hàm, để bên gọi (H2 sau này) tự cân đối.

### Thiết kế

`autodub/media/text_regions.py` thêm (không sửa dòng nào của
`detect_text_regions()`/`merge_regions()`/`loc_theo_lap_lai()` hiện có):

- `read_text_regions(image_paths, settings=None, cancel_event=None,
  moc_thoi_gian=None) -> KetQuaDocChu` — hàm công khai mới.
- `QuanSatChu` (dataclass): `text, confidence, x, y, w, h, frame_index,
  timestamp_s, source, status`. MỖI khung hình một quan sát riêng — KHÔNG
  gộp qua nhiều khung (Scope A: `merge_regions()` gộp theo VỊ TRÍ, đúng cho
  làm mờ nhưng SAI cho nội dung — hai caption khác nhau cùng nằm đáy màn
  hình sẽ bị gộp nhầm nếu tái dùng hàm đó cho chữ).
- `KetQuaDocChu` (dataclass): `trang_thai` ("co_chu" | "no_text") +
  `quan_sat`. `"unavailable"`/`"failed"` KHÔNG phải giá trị của trường này
  — ném ngoại lệ (`ChuaCaiOcr` tái dùng nguyên; `DocChuThatBai` mới, khi
  MỌI khung hình đưa vào đều gọi OCR lỗi).
- `NGUONG_TIN_CAY_DOC = 0.70` — phân biệt `status="ok"`/`"unconfirmed"`
  mỗi quan sát. Chưa hiệu chỉnh rộng (xem giới hạn ở trên: không bắt được
  ca "tự tin nhưng sai" của tiếng Việt).
- `text_regions_worker.py` (script độc lập, chạy trong `.venv-ocr`): thêm
  cờ `--doc-chu` (mặc định TẮT) — bật lên mới có khoá `"text"` trong JSON
  trả về; JSON luôn có thêm `"anh_loi"` (số khung lỗi, caller cũ bỏ qua
  field lạ, không vỡ). `_detect_in_process`/`_detect_via_subprocess` cùng
  thêm tham số `doc_chu`/`thong_ke` theo kiểu keyword-only mặc định giữ
  hành vi cũ — lời gọi cũ trong `detect_text_regions()` không đổi một ký
  tự nào.

Không có UI mới (Scope B chỉ "tối thiểu nếu cần" — live verification làm
được bằng script, không cần màn hình review).

### Live Verification (bắt buộc theo Test Plan — cả 4 case, không mock)

Chạy qua ĐÚNG hàm `read_text_regions()` vừa build (không phải bản nháp gọi
RapidOCR tay):

1. **Ảnh tiếng Anh rõ**: "FLASH SALE" → `status="ok"`, confidence 0,988.
2. **Caption tiếng Việt**: xem mục "Ngôn ngữ" ở audit trên — đọc được,
   `status="ok"` (confidence cao), nhưng NỘI DUNG sai (mất dấu/sai ký tự).
   Không tự động phát hiện được ca này bằng ngưỡng confidence.
3. **Video nén thật, caption ngắn 0,5 giây trong 3 giây đầu**: lấy mẫu mỗi
   0,2 giây qua `read_text_regions()` → 3 quan sát tại t=0,2s/0,4s/0,6s,
   đều đọc đúng "FLASH SALE" — xác nhận đường ống ĐẦY ĐỦ (trích khung +
   đọc + gắn timestamp) hoạt động đúng khi mật độ đủ dày.
4. **Video nén thật, nền phức tạp/motion**: `tap01_clip.mp4` (clip có sẵn
   trong repo, dùng cho CI) — 2 khung tại t=1s/t=25s đọc ra đủ 7 dòng chữ
   song ngữ Anh-Việt, gắn đúng timestamp theo khung nguồn.

**Không đọc được chắc** (theo đúng yêu cầu "ghi tỷ lệ, không hứa đa ngôn
ngữ"): tiếng Anh rõ 100% chính xác trong mọi ca đã thử; tiếng Việt 100%
"đọc được" theo nghĩa có text + confidence cao, nhưng SAI ở mức ký tự
(mất dấu, đôi chỗ sai từ) trong TẤT CẢ câu tiếng Việt đã thử — không có
câu tiếng Việt nào ra đúng nguyên văn trong lượt đo này.

### Tests

12 test mới (`tests/test_read_text_regions.py`) + toàn bộ 69 test cũ của
OCR (`test_text_regions.py` và các tệp liên quan) chạy lại xanh nguyên,
không sửa gì. Hai hồi quy Guardrail 4 đã CHỨNG MINH đỏ trước khi phục hồi
(gỡ tạm code, chạy test thấy đỏ đúng chỗ, khôi phục lại xanh) — đúng kỷ
luật dự án, không chỉ tin lời tự nhận:
- Gộp `unavailable` thành `no_text` → đỏ (`test_chua_cai_ocr_nem_ChuaCaiOcr_khong_phai_no_text`).
- Vứt `text` dù đã bật `doc_chu=True` → đỏ (`test_doc_duoc_chu_giu_du_text_confidence_bbox_timestamp`).

### Remaining Limits

- **Tiếng Việt đọc được ở mức GIST, không chính xác ở mức KÝ TỰ** — cần
  quyết định của chủ dự án nếu H2 (sau này) cần độ chính xác cao hơn:
  đổi/thêm model nhận dạng có dấu tiếng Việt (ngoài phạm vi H2a).
  Confidence không phải tín hiệu để tự động phát hiện ca này.
- **Chưa chốt mật độ lấy mẫu cho H2 dùng thật** — `read_text_regions()`
  nhận `image_paths` bất kỳ, KHÔNG tự áp đặt mật độ. H2 (nếu mở lại) phải
  tự quyết định trade-off tốc độ/độ phủ (đo thật: ~1,23s/khung CPU) theo
  độ dài video thật cần phân tích.
- Không merge/dedupe caption lặp qua nhiều khung — cố ý, đúng Scope A
  ("chưa đủ bằng chứng, không bịa thuật toán gộp"). H2 sau này cần tự
  quyết định thuật toán gộp theo NỘI DUNG (không phải vị trí) nếu cần.
- H2 (Flow Blueprint) vẫn CHƯA mở lại — H2a chỉ đóng đúng gap kỹ thuật
  OCR, không phải quyết định "H2 sẵn sàng chạy".

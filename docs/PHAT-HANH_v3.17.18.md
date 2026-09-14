# v3.17.18 — bản sau pilot H2→H3

Bản `v3.17.17` bạn đang dùng **thiếu 5 đợt sửa**, trong đó có ba thứ chính
lượt pilot của bạn lôi ra.

## Ba thứ pilot tìm ra

### 1. H6 — kịch bản nay giữ đúng NHỊP của video tham khảo

**Trước:** nguồn 34 giây, kịch bản đọc hết **170 giây** — gấp **5 lần**. Cả
chuỗi H2 tốn 64 Vox để học nhịp của một Short, rồi H3 trả về một video gần 3
phút.

**Nguyên nhân:** thời lượng từng đoạn **không bao giờ tới được mô hình** — mã
lọc bỏ nó trước khi dựng lời nhắc, và lời nhắc cũng không nói gì về độ dài.

**Nay:** mỗi đoạn mang theo số giây và **ngân sách từ**, tính từ tốc độ đọc đo
thật của VieNeu:

```
Video tham khảo dài 34 giây — tổng lời đọc không quá 62 từ.
1. [hook]            | 4.0 giây — TỐI ĐA 7 từ
4. [transition]      | 2.0 giây — TỐI ĐA 4 từ
5. [demonstration]   | 8.0 giây — TỐI ĐA 15 từ
```

**Và cảnh báo nhịp chuyển lên trang «Viết kịch bản»** — trước đây nó chỉ hiện
ở trang «Dựng video», tức bạn biết SAU KHI đã tiêu 12 Vox và đi thêm một trang.

> ⚠️ Phần lời nhắc nằm ở **máy chủ** nên đã có hiệu lực từ trước bản này. Phần
> **cảnh báo tại H3** thì nằm trong app — cần bản này.

### 2. Nút đọc được chữ

Cột nút ở «Viết kịch bản» rộng 110px cho nhãn **«Viết lại đoạn»** → hiện ra
`: lại đi`. Cột ở «Dựng video» rộng 120px cho **hai** nút → cả hai **trắng
trơn**.

Không phải chuyện thẩm mỹ: «Viết lại đoạn» là đường thoát **duy nhất** khi
kịch bản bị chặn; và ở «Dựng video», một trong hai nút **tốn 33 Vox** còn nút
kia miễn phí — hai ô trắng cạnh nhau thì không đoán nổi cái nào.

Nay có test **đo bề rộng chữ thật của chính các nút** rồi so với cột, thay vì
áng chừng một con số.

### 3. Tệp chẩn đoán OCR không còn mất ở nhánh TRẢ TIỀN

Lượt bạn trả 56 Vox cho máy chủ đọc chữ **không ghi được** `ocr_chan_doan.json`
(`'<' not supported between instances of 'NoneType' and 'NoneType'`). Quan sát
do máy chủ đọc không có điểm tin cậy, mà bộ ghi lại đi so điểm.

Lỗi có từ v3.17.14 và **chỉ nổ ở nhánh trả tiền** — nhánh «Bỏ qua» vẫn ghi
được, nên cả hai tệp mang đi phân tích trước đây đều là của lượt «Bỏ qua» và
không ai thấy.

## Hai thứ mới

### H5 — dải điều hướng Phase H

```
Phân tích cấu trúc  →  Viết kịch bản  →  Dựng video
```

Hiện ở đầu **cả ba trang**. «Viết kịch bản» và «Dựng video» không nằm trên
thanh bên, nên trước đây đóng hoặc đổi trang là mất đường quay lại — đúng cảm
giác *"thiếu quy trình"* bạn báo.

Dải **chỉ là đường đi, không phải cổng**: mở được trang «Dựng video» không có
nghĩa dựng được video. Kịch bản `Bị chặn`/`Chưa kiểm được` vẫn không dựng
được, nhưng nay trang đó **nói rõ vì sao và phải làm gì** — bốn trạng thái,
bốn câu khác nhau, mỗi câu có đường xử lý.

### Xuất kịch bản ra tệp

Nút **«Xuất kịch bản…»** ghi kịch bản ra tệp chữ, kèm **cả cột kiểm tra từng
đoạn** (người cầm đi quay cần biết đoạn nào đang bị chặn, không thì quay xong
phải bỏ). Xuất được **kể cả khi bị chặn** — kịch bản chặn vẫn là thứ bạn vừa
trả 12 Vox để có.

## Sửa nhỏ khác

- Cột **Trạng thái** nói tiếng Việt; **mất mạng** không còn hiện ra như *"chưa
  có gì"*; câu lỗi thiếu lời đọc nói **đúng số đoạn**; hết sót tệp tạm
  `_anh_kiem_tam.jpg` trong thư mục ảnh.
- Kịch bản nay hiện thêm *"có chạm cụm ngắn «…»"* khi chạm từ vựng chủ đề của
  video nguồn — chạm nhưng **không** đủ để coi là chép.

## ⚠️ Giải nén vào thư mục TRỐNG

Lần trước bạn giải nén đè lên thư mục cũ và **tệp worker OCR cũ không bị ghi
đè** — nhật ký nói thẳng:

```
Worker OCR ĐỜI CŨ (1) — Tệp đang chạy:
...\v3.17.17-win64\_internal\autodub\media\text_regions_worker.py
```

Tôi đã tải chính tệp zip v3.17.17 từ GitHub về kiểm: bên trong là worker **đời
2**, đúng. Nên lỗi nằm ở lượt giải nén, không phải bản dựng. Đây gần như chắc
chắn cũng là nguyên nhân gốc của bí ẩn thiếu số đo hôm 12/09.

**Lần này giải nén vào một thư mục hoàn toàn mới.** Rồi chạy lại một lượt
«Phân tích cấu trúc», bấm **«Bỏ qua, không tốn Vox»** — tệp chẩn đoán vẫn được
ghi, **0 Vox**, và lần này nó sẽ có hai số đo `khoi_dong_s`/`quet_s` để trả
lời nốt câu hỏi thời gian OCR.

## Chưa có trong bản này

- **Sinh ảnh tự động** vẫn cần thao tác quản trị (nhà cung cấp vai `image` +
  máy của bạn trong danh sách hiệu chỉnh). «Dựng video» vẫn đòi bạn tự cấp đủ
  ảnh cho mọi đoạn — cố ý, nó không bịa hình.
- **RS-16** còn mở: ảnh AI chưa đi qua đủ ba phép kiểm tuân thủ. Không ảnh
  hưởng H2→H3, nhưng **phải đóng trước khi bật cửa sinh ảnh**.

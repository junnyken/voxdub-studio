# v3.17.19 — cổng tuân thủ ảnh AI, và nút đọc được chữ

Bản `v3.17.18` bạn đang dùng thiếu **hai** thứ đụng thẳng vào việc bạn đang
làm, cộng một lớp chặn phải có **trước** khi mở tính năng vẽ ảnh.

---

## 1. Nút trong bảng nay tự co theo phông máy bạn

**Trước:** ở trang «Viết kịch bản» nút «Viết lại đoạn» hiện ra `: lại đi`; ở
trang «Dựng video» hai nút cột «Ảnh» hiện ra `:họn ảnh..` và `/ẽ (33 Vox`.

Đây không phải chuyện thẩm mỹ. Ở H3, «Viết lại đoạn» là **đường đi tiếp duy
nhất** khi kịch bản bị chặn. Ở H4, một trong hai nút **tốn 33 Vox**, nút kia
miễn phí — hai ô cụt chữ cạnh nhau thì không đoán nổi cái nào tốn tiền.

**Nay:** bỏ hẳn bề rộng cố định, để Qt tự đo nút thật.

> Tôi đã sửa hụt **hai lần** trước khi hiểu: nới 110→160 rồi 120→240, và viết
> hẳn một phép đo để chứng minh là đủ. Phép đo ấy chạy trên máy Linux của tôi,
> nên nó chỉ chứng minh đủ **với phông của máy tôi**. Máy bạn phông khác, nút
> vẫn cụt. Mọi con số chốt cứng ở đây đều là con số sai của một máy nào đó.

## 2. Ảnh do AI vẽ nay phải qua cổng tuân thủ mới thành video được (RS-16)

Phần này **chưa ảnh hưởng bạn ngay**, vì tính năng vẽ ảnh còn khoá ở máy chủ.
Nó phải có **trước** khi mở khoá, nên nó nằm trong bản này.

**Khoảng hở đã bịt:** bước vẽ ảnh trả về đủ phán quyết kiểm duyệt (đã kiểm
chưa, đã đóng nhãn AI chưa, dấu băm của tệp), nhưng giao diện **chỉ giữ đường
dẫn ảnh rồi vứt hết phần còn lại**. Nên phép kiểm cuối cùng — thứ quyết định
một tấm ảnh có được vào video đem bán hay không — **không có gì để chạy**.

**Nay** phán quyết đi theo tấm ảnh tới tận bước ghép video, và bị **kiểm lại**
ở đó chứ không tin cờ đã lưu: giữa lúc vẽ và lúc dựng có thể là vài ngày, và
phép kiểm so lại **dấu băm của tệp** — ảnh bị sửa sau khi duyệt thì không còn
là tấm đã được duyệt nữa.

Nếu có ảnh chưa đạt, bạn sẽ thấy câu nói thẳng hai lối ra: **vẽ lại ảnh đó**,
hoặc **chọn ảnh bạn tự chụp cho đoạn ấy**. Ảnh bạn tự chụp không bị đòi kiểm.

## 3. Phần máy chủ (đã chạy sẵn, không cần bản mới)

- Sửa một chỗ rò rỉ: lượt tải lên đứt giữa chừng từng để lại mảnh dữ liệu
  chiếm chỗ **vĩnh viễn** trong cơ sở dữ liệu.
- Thêm một chốt tự động canh việc máy chủ có đang chạy đúng mã mới nhất không.
  Ngày 14/09 máy chủ đã chạy mã cũ **21 giờ** mà mọi đèn đều xanh.

---

## Tải gì

Tải **trọn bộ** bản `v3.17.19` như mọi lần.

> ⚠️ **Giải nén vào một thư mục RỖNG.** Giải đè lên thư mục cũ thì thư mục
> `_internal` **không được ghi đè**, và bạn sẽ chạy bản mới với ruột cũ — đúng
> chuyện đã xảy ra với bản `v3.17.18` và làm lượt đo C.4 thiếu số liệu.

## Việc còn chờ bạn

1. **Số đo C.4**: sau khi giải nén sạch, chạy lại H2 với «Bỏ qua, không tốn
   Vox» (0 Vox) rồi gửi tôi `output\flow_blueprint\data\ocr_chan_doan.json` —
   tệp đó phải có trường `worker_phien_ban`.
2. **Mở tính năng vẽ ảnh**: thêm vân tay máy vào danh sách hiệu chỉnh trên
   trang quản trị, rồi chạy 20–30 ảnh thật và **soi tay từng phán quyết**.
   Nay đã hết vướng vì cổng ở mục 2 đã xong.

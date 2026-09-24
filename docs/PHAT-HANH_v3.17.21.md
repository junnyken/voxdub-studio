# v3.17.21 — video dựng theo đúng chỉ đạo của trợ lý, và sửa tay được

Bản này chạm vào **luồng Kịch bản thương hiệu → Dựng video**. Nếu bạn chỉ
dùng VoxDub để lồng tiếng video thì đây là bản đẹp thêm. Nếu bạn dùng «Viết
kịch bản» + «Dựng video» thì đây là bản **đáng cập nhật**: từ nay bản chỉ đạo
hình ảnh bạn đã trả Vox để có **mới thật sự điều khiển video ra**.

---

## 1. «Dựng video» trước KHÔNG đọc bản chỉ đạo, nay đọc

**Trước:** bạn bấm «Chỉ đạo hình ảnh…», trợ lý chọn cho từng đoạn một kiểu
chuyển cảnh — đoạn hook cắt thẳng cho dứt khoát, đoạn thân mờ nhẹ cho êm — và
bạn đọc thấy nó trên màn hình. Rồi bấm «Dựng dự án», và video ra **mờ chồng
từ đầu đến cuối**. Không có thông báo nào; bản chỉ đạo chỉ là một tờ giấy đọc
cho vui.

**Nay:** mỗi mối nối dùng đúng kiểu của đoạn nó dẫn vào. Trang «Dựng video»
hiện một dòng nói rõ nó đang theo cái gì — *"Chuyển cảnh: theo bản chỉ đạo
hình ảnh (5 đoạn)"* hoặc *"Chuyển cảnh: Mờ chồng (chưa có bản chỉ đạo)"* —
nên bạn không phải đoán.

Sáu kiểu máy dựng được: cắt thẳng · mờ nhẹ · hoà ngắn · trượt trái · trượt
lên · mở vòng tròn. Các mục còn lại của bản chỉ đạo (khung hình, bố cục, ánh
sáng) **vẫn là lời khuyên cho người** khi bạn đi chọn hoặc chụp ảnh — máy
không tự làm được, và bản này không hứa khác đi.

## 2. Sửa tay được bản chỉ đạo

Trợ lý chọn sai một đoạn thì trước đây bạn **kẹt**: cách duy nhất là tạo lại
cả bản, tốn Vox, rồi hy vọng lần này nó chọn khác.

Nay trong hộp thoại «Chỉ đạo hình ảnh» mỗi đoạn có một ô chọn chuyển cảnh.
Đổi, bấm «Lưu chỉnh sửa», xong — **0 Vox**, vì không gọi mô hình. Lượt dựng
kế tiếp dùng đúng thứ bạn vừa sửa.

Chọn *«— không chỉ định —»* cũng được: đoạn đó sẽ rơi về nếp của thương hiệu
(mục 3) hoặc mờ chồng.

## 3. Nếp chỉ đạo theo thương hiệu

Hồ sơ Brand nay nhớ được một bộ chuyển cảnh ưa dùng. Nó làm hai việc, và cả
hai đều **không lấn quyền bạn**:

- đi vào lời nhắc của trợ lý dưới dạng *thói quen*, không phải lệnh — đoạn
  nào cần khác thì trợ lý vẫn chọn khác và nói lý do;
- làm **chỗ rơi** cho đoạn không có chỉ đạo, thay cho mờ chồng cứng.

Nó **không bao giờ đè** lên đoạn đã có chỉ đạo.

## 4. Sửa: video «Cắt thẳng» dài hơn thời lượng bạn đặt

**Đo thật:** 3 ảnh × 1,5 giây dựng ra **4,600 giây** thay vì 4,500. 3 ảnh ×
2,5 giây ra **7,600** thay vì 7,500.

Chỉ dính ở hai giá trị **1,5s** và **2,5s** của ô «Mỗi cảnh giữ» — mà **2,5s
là mặc định**, nên phần lớn video cắt thẳng đều lệch. Với 2,0 · 3,0 · 4,0 ·
6,0 giây thì trước nay vẫn đúng.

**Nguyên nhân:** ffmpeg giải mã ảnh ở 25 hình/giây nên chỉ cắt được theo mốc
0,04 giây. Thời lượng rơi đúng giữa hai mốc bị làm tròn **lên** ở mọi ảnh, và
phần dôi **cộng dồn**. Nay đã đặt đúng nhịp hình, cả bốn ca đo lại lệch
**0,000 giây**.

Luồng lồng tiếng thường **không bị** lỗi này: thời lượng ở đó lấy từ giọng
đọc thật nên là số lẻ, sai số triệt tiêu nhau (đo 3/5/8 cảnh: lệch ≤0,015s).

## 5. Sửa: trang quản trị nói ngược với chính nó

Bấm «Thử ngay» trên một nơi gọi mô hình, nó báo xanh *"Gọi được và đọc đúng
số trong ảnh"* — mà cái nhãn ngay cạnh vẫn ghi *"chưa chứng minh nhìn được
ảnh"*. Máy chủ đã ghi nhận đúng; chỉ là danh sách không tự đọc lại. Nay đọc
lại sau mỗi lượt thử.

## 6. Kịch bản: trợ lý được cho biết nhiều hơn

Ba thay đổi ở khâu viết kịch bản và chọn bố cục. **Phần lớn nằm ở máy chủ và
đã chạy từ 24/09** — bản `.exe` này chỉ đổi một chỗ nhỏ (mục 6.4).

**6.1 — Chọn bố cục theo NHỊP.** Trước đây bước chỉ đạo hình ảnh không biết
đoạn dài bao nhiêu, nên nó chọn chuyển cảnh như nhau cho đoạn 2 giây lẫn đoạn
8 giây — mà một cú chuyển mềm 0,3 giây ăn 15% của đoạn ngắn và gần như không
đáng kể ở đoạn dài. Nay nó biết thời lượng và nhịp của từng đoạn.

**6.2 — Trợ lý học được CÁCH NÓI của video tham khảo.** Bước phân tích cấu
trúc vốn đã trích bốn thứ cho mỗi đoạn, nhưng bước viết kịch bản chỉ nhận
được hai. Hai thứ bị bỏ chính là *khuôn chữ trên hình* và *khuôn câu nói* —
tức cách video gốc **truyền đạt**, không phải nội dung của nó. Nay cả bốn đều
tới nơi.

**6.3 — Một SÂN KHẤU dùng chung.** Trước đây mỗi đoạn tả hình độc lập, nên
đoạn 1 có thể là gian bếp và đoạn 5 là bàn làm việc, không gì chặn. Nay kịch
bản chốt sẵn một bối cảnh, một hướng sáng và một **quy ước khung người**
(ví dụ *"chỉ thấy bàn tay, không bao giờ thấy mặt"*) rồi mọi đoạn bám theo.

Hồ sơ Brand đặt được sân khấu riêng — đặt một lần, mọi kịch bản của thương
hiệu đó dùng lại. Đó là thứ làm nhiều video của cùng một thương hiệu nhìn như
một bộ.

> Quy ước khung người là quy ước **khung hình**, không phải mô tả người. Luật
> không tả khuôn mặt / ngoại hình / tuổi / tóc / trang phục **không đổi một
> chữ**.

**6.4 — Hộp thoại «Chỉ đạo hình ảnh» hiện thời lượng mỗi đoạn.** Đây là phần
duy nhất của mục 6 nằm trong bản `.exe`. Khi bạn tự sửa chuyển cảnh của một
đoạn, bạn cần biết đoạn ấy dài 2 giây hay 8 giây — trước đây bạn chọn mù đúng
như mô hình.

### Nói cho đúng mức: cái gì đã chứng minh, cái gì chưa

**Đã chứng minh:** thông tin tới được nơi cần tới, và không làm hỏng thứ đang
chạy — kịch bản 40 đoạn vẫn đủ đoạn, ngân sách từ vẫn giữ, bộ chặn sao chép
vẫn nguyên.

**CHƯA chứng minh:** kịch bản có **hay hơn** không. Phép đo so sánh trước/sau
(nhiều thương hiệu, nhiều video, chấm mù) **chưa chạy**. Ba mục trên cho mô
hình nhiều dữ kiện hơn để làm đúng — chúng chưa phải bằng chứng rằng nó đã
làm đúng hơn. Hai chuyện khác nhau, và bản ghi chú này không gộp lại.

---

## Cập nhật thế nào

Tải bản mới, giải nén **cạnh** thư mục cũ rồi chạy. Giọng đọc, model và cấu
hình của bản cũ được dùng lại — không phải cài lại gì.

Nếu bạn tự dựng máy chủ VoxDub riêng thì **cập nhật máy chủ trước**: bản này
gọi một cửa API mới (lưu chỉnh sửa bản chỉ đạo). App cũ chạy với máy chủ mới
thì không sao.

## Số đo của bản này

- `pytest` **3225 đạt**, 4 bỏ qua
- máy chủ **803 đạt**, 1 bỏ qua · website **76 đạt**
- cổng thời lượng chạy ffmpeg thật rồi đo lại bằng ffprobe trên **6 hình dạng
  trộn kiểu chuyển cảnh**, lệch tối đa **1 khung hình** (0,033 giây) và không
  tăng theo số cảnh

# v3.17.20 — cài được giọng VieNeu trở lại, và hình bám đúng giọng đọc

Nếu bạn **đang dùng `v3.17.19` và giọng VieNeu vẫn chạy**, bản này chỉ là bản
đẹp thêm. Nếu bạn **cài lại máy, đổi máy, hoặc đưa VoxDub cho người khác cài
mới** thì bản này là bản **bắt buộc**: trên `v3.17.19`, việc cài giọng VieNeu
**không còn cài nổi nữa**.

---

## 1. Cài giọng VieNeu trên máy mới: trước KHÔNG xong, nay xong

**Trước (trên `v3.17.19`):** đúp chuột «Cai dat giong VieNeu.bat», chờ vài
phút tải ~300 MB, rồi nó **hỏng ở bước cuối** — cửa sổ đen có dòng
`External data path escapes model directory`, và tệp đánh dấu cài xong
(`models\vieneu\installed_ok.json`) **không bao giờ được ghi**. Mở app lên,
app vẫn nói chưa cài giọng. Chạy lại cũng thế, vì lần tải hỏng đã để lại cache
sai trong máy.

**Vì sao tự nhiên hỏng, trong khi trước đó vẫn cài được:** kho model
HuggingFace **đổi chỗ đặt tệp** (chia thư mục `blobs` theo hai ký tự đầu). Từ
lúc đó, tệp model và tệp trọng số đi kèm nó trỏ về **hai thư mục thật khác
nhau**, nên onnxruntime chặn lại — đúng cơ chế an toàn của nó. Không phải máy
bạn hỏng, và cũng không phải bạn làm sai bước nào.

**Nay:** trình cài tải về **tệp thật** thay vì đường dẫn tắt, và trước khi tải
nó còn **dọn phần cache hỏng của lần trước** — nên bạn chỉ cần chạy lại trình
cài, **không phải xoá tay thư mục nào**.

> Cách tôi biết chắc bản mới sửa được: trong **cùng một lượt kiểm trên máy
> Windows sạch** (CI `35633769008`), trình cài của `v3.17.19` **hỏng**, còn
> trình cài của bản này **cài xong** — cùng máy, cùng mạng, cách nhau vài
> phút. Bản vá vốn viết cho máy chủ hôm 21/09, nhưng nó nằm đúng trong tệp mà
> **bạn** chạy khi đúp chuột, nên bạn được sửa theo.

**Ai KHÔNG bị ảnh hưởng:** người đã cài VieNeu xong từ trước. Bộ giọng đã cài
vẫn dùng được, và khi nâng cấp bạn **không phải tải lại 300 MB** (xem mục
«Nâng cấp thế nào» bên dưới).

## 2. Hình trong video dựng từ kịch bản nay chạy theo GIỌNG ĐỌC THẬT

Phần này chỉ đụng tới đường **dựng video từ kịch bản** (storyboard), không đụng
lồng tiếng video có sẵn.

**Trước:** hình đổi theo **thời lượng ước lượng** (tính từ số câu + số âm
tiết). Giọng đọc thật không bằng ước lượng — đo ở lượt chạy thử: phần hình
theo ước lượng dài **19,30 giây**, còn giọng đọc thật dài **20,31 giây**
(lệch ~5%). Vì các đoạn trong kịch bản **nối liền nhau, không có khoảng lặng
để dồn phần lệch**, sai số **cộng dồn**: càng về cuối video, hình càng chạy
trước lời.

**Nay:** mốc đổi hình lấy từ chính tệp giọng đọc đã dựng. Không tốn thêm Vox —
toàn bộ phần này chạy bằng ffmpeg trên máy bạn.

**Kèm một lỗi nữa đã sửa:** cảnh cuối trước đây tắt ngay ở chữ cuối cùng, nên
**khoảng 4 giây cuối video không có hình**. Nay hình giữ tới hết.

## 3. Thứ có trong bản này nhưng bạn không nhìn thấy khi dùng

`VoxDub.exe` nay có thêm một **lệnh chẩn đoán ẩn**, chỉ chạy khi gọi kèm cờ
riêng ở dòng lệnh — đúp chuột như thường ngày thì không bao giờ đi vào đó.

Nó tồn tại để máy dựng bản phát hành **chạy thử chính tệp `.exe` vừa đóng
gói**: cài mới trên thư mục trắng, cài bộ máy bằng đúng tệp `.bat` bạn sẽ đúp
chuột, lồng tiếng trọn một video ngắn, rồi soi lại tệp ra (có tiếng không, có
câm không, thời lượng có khớp không). Trước đây máy dựng chỉ chạy thử **mã
nguồn** — nên chuyện "bản `.exe` thiếu tệp nhưng mọi đèn đều xanh" đã xảy ra
thật nhiều lần. Từ bản này trở đi, một bản `.exe` không chạy nổi thì **không
được phát hành**.

## 4. Phần máy chủ (đã chạy sẵn, không cần bản mới)

- Dọn **mảnh dữ liệu mồ côi** định kỳ, chứ không chỉ đếm chúng: lượt tải lên
  đứt giữa chừng từng để lại mảnh chiếm chỗ vĩnh viễn.
- Trang thống kê đọc được quan hệ **số token ↔ số đoạn** của các lượt trợ giúp
  bằng AI.
- Cùng bản vá tải model ở mục 1, nhưng cho máy dựng worker lồng tiếng.

## 5. Có mã nhưng còn khoá — đừng chờ nó ở bản này

**Vẽ ảnh minh hoạ bằng AI (33 Vox/ảnh)** vẫn ở nấc **hiệu chỉnh**: máy chủ chỉ
mở cho những máy đã được thêm vân tay vào danh sách. Bấm vào, bạn sẽ nhận đúng
câu *"đang trong giai đoạn hiệu chỉnh, chưa mở cho máy này"* — đó là **chưa
mở**, không phải hỏng. Cổng tuân thủ ảnh AI (có từ `v3.17.19`) vẫn nguyên: ảnh
do AI vẽ phải qua kiểm mới vào được video.

## 6. Giới hạn đã biết (nói trước cho khỏi mất thời gian)

- **Trình cài VieNeu vẫn cần Python 3.10–3.12 cài sẵn trên máy** (Bước 2 của
  `HUONG_DAN_CAI_DAT.md`). Bản vá ở mục 1 chữa phần **tải model**, không tự
  cài Python hộ bạn.
- **Phần "đúp chuột rồi thấy gì" của các tệp `.bat` chưa ai kiểm tự động** —
  máy dựng chạy chúng không tương tác, nên lời văn/thao tác trong cửa sổ đen
  vẫn chỉ được kiểm bằng mắt.
- **Lượt chạy thử trước khi phát hành chỉ chứng minh MỘT đường chạy**: một
  video tiếng Anh 53,5 giây, bộ nghe `tiny`, không tách nhạc nền, không phụ
  đề. Nó nói rằng đường ống còn nguyên — **không** nói gì về chất lượng bản
  dịch, chất lượng giọng đọc, video tiếng Trung/Nhật, tách nhạc nền, khớp khẩu
  hình hay đường chạy GPU.

---

## Tải gì

Tải **trọn bộ** bản `v3.17.20` như mọi lần.

## Nâng cấp thế nào (đọc kỹ hai dòng này, tiết kiệm cho bạn 300 MB)

1. **Giải nén vào một thư mục RỖNG.** Giải đè lên thư mục cũ thì `_internal`
   **không được ghi đè**, và bạn sẽ chạy bản mới với ruột cũ — đúng chuyện đã
   xảy ra với `v3.17.18`.
2. **Đặt thư mục mới CẠNH thư mục cũ**, tức cùng một thư mục cha:

   ```
   D:\VoxDub\
       VoxDub Studio v3.17.19\     ← bản cũ, giữ nguyên, đừng xoá vội
       VoxDub Studio v3.17.20\     ← bản mới giải nén ra đây
   ```

   Đặt như vậy thì bản mới **tự tìm thấy và dùng lại** `.venv-*`, `models\`,
   `bin\` và cài đặt (`.env`) của bản cũ: **không phải cài lại bộ nghe, không
   phải tải lại giọng đọc**. Đặt ở một nhánh khác thì bản mới coi như máy
   trắng và bắt bạn cài lại từ đầu.

   Bản mới **không sửa, không xoá** gì trong thư mục bản cũ — nó chỉ dùng lại
   tại chỗ (và có thể **thêm** model mới vào kho dùng chung ở đó). Chạy ổn vài
   hôm rồi hãy xoá bản cũ.

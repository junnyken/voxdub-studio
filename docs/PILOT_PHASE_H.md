# Runbook pilot Phase H (H2 → H2b → H2c → H3)

Mục đích: chạy MỘT lượt thật xuyên suốt để đóng bốn cổng trước khi mở H4.
Chạy trên **máy Windows** có app — workspace Linux không chạy được app desktop.

## Trước khi bắt đầu

| Việc | Vì sao |
|---|---|
| App phải là bản dựng từ mã HIỆN TẠI | H2b/H3 nằm ở phía app; bản `.exe` cũ không có trang «Viết kịch bản» lẫn bộ đọc chữ máy chủ |
| `VOXDUB_API_URL` trỏ về prod | Không có máy chủ thì H2b lui về bộ đọc cục bộ (mất dấu) và H3 không chạy |
| Ví còn Vox | H2 tốn 8, H2b tốn 8 mỗi lô 6 khung, H3 tốn 12. Một pilot đủ hai ca gate ≈ 60-80 Vox |
| Đã cài bộ OCR | Chưa cài thì bước đọc chữ báo "chưa cài", không phải "không có chữ" |

## Chọn video — chỗ này quyết định pilot có đóng được cổng 2 không

Cổng 2 đòi *"H2b đọc đúng caption **có dấu** trên máy người dùng"*. **Video
caption tiếng Anh không đóng được cổng này** — không có dấu nào để đọc.

Nên chọn, theo thứ tự ưu tiên:

1. **Video bán hàng có phụ đề Việt cháy sẵn**, 30–60 giây, cấu trúc rõ
   (hook → vấn đề → bằng chứng → kết quả → kêu gọi). Đóng được **cả bốn cổng**
   trong một lượt.
2. **Hai video**: một tiếng Anh cấu trúc rõ (đánh giá chất lượng nhịp + H3),
   một có caption Việt (đóng cổng 2). Tốn gấp đôi nhưng tách bạch nguyên nhân
   khi có gì sai.
3. `tap01_clip.mp4` sẵn trong repo — phụ đề cháy song ngữ Anh–Việt, đóng được
   cổng 2, **nhưng** là video dạy tiếng Anh nên cấu trúc kể chuyện yếu; chỉ
   hợp để kiểm ĐƯỜNG CHẠY, không hợp để đánh giá chất lượng phân tích nhịp.

Tránh cho lượt đầu: chữ quá nhỏ, khung rung mạnh, caption ẩn (không cháy vào
hình). Pilot đầu kiểm đường chạy, không phải cố làm khó OCR.

## Bước 1 — chạy H2

1. Mở trang **Phân tích cấu trúc video tham khảo**, dán liên kết hoặc chọn tệp.
2. Theo dõi bốn bước thật: tải video → chép lời → đọc chữ → phân tích cấu trúc.
3. **Mở Nhật ký và chép lại dòng này** (bằng chứng số 6, chỉ có ở đây):
   ```
   Đọc chữ qua máy chủ: N khung lấy mẫu -> M đoạn chữ khác nhau ->
   gửi K khung (J khung đọc được kết quả)
   ```
   `N` là số khung sàng lọc miễn phí trên máy, `K` là số khung THẬT SỰ tốn
   Vox. Tỉ lệ `K/N` là phần tiết kiệm — thiết kế nhắm khoảng 1/3.
4. **Nhìn màn hình lúc chữ hiện ra**: caption tiếng Việt có ra ĐÚNG DẤU không
   (`Các bạn sẵn sàng` chứ không phải `Cuc ban san sang`). Đây là thứ **duy
   nhất** phải xác nhận bằng mắt — mọi mục khác script gom được.

Kiểm kết quả: hook có rơi vào 0–5 giây đầu không; có phân biệt được vấn đề /
bằng chứng / cao trào / kêu gọi hành động không; cột tình trạng bằng chứng có
giá trị rõ ràng chứ không phải trống.

## Bước 2 — chuẩn bị hồ sơ thương hiệu

Cần đủ **bốn trường bắt buộc**: mô tả sản phẩm, đối tượng khách, giọng điệu,
USP. Thiếu một trường là H3 chặn ở `400 HO_SO_BRAND_THIEU` và **không gọi mô
hình** (không tốn Vox) — cố ý, vì máy không được bịa USP hộ bạn.

Thêm ít nhất **một ràng buộc không được nói**, ví dụ `tốt nhất`.

## Bước 3 — chạy H3

Vào trang **Viết kịch bản** (nút ở cuối trang «Phân tích cấu trúc»), chọn nhịp
vừa tạo + hồ sơ brand, bấm **Viết kịch bản**.

Kiểm từng đoạn: lời đọc có đúng giọng/USP không; caption có phải nội dung mới
không; visual brief có đủ cụ thể để sau này chọn/dựng hình không.

## Bước 4 — hai ca gate CỐ TÌNH làm sai

Một lượt "mọi thứ xanh" không chứng minh được gate hoạt động.

| Ca | Thao tác | Kết quả bắt buộc |
|---|---|---|
| **Claim cấm** | Thêm vào hồ sơ brand một cụm mà kịch bản vừa rồi CÓ dùng (mở kịch bản ra, chọn một cụm bất kỳ trong lời đọc), rồi bấm **Viết lại đoạn** đó | Đoạn chuyển `violated`, chỉ đúng cụm + đúng câu ràng buộc, **cả kịch bản** thành `blocked`, nút "Dùng kịch bản này" **tắt** |
| **Sao chép sát** | Khó ép qua giao diện — mô hình thường tự tránh | Đã có test tự động chứng minh gate bắt fixture chép nguyên văn (xem dưới) |

Mẹo cho ca claim cấm: đừng đặt cụm cấm rồi mới sinh — mô hình sẽ tự né và bạn
không kích hoạt được gate. Sinh trước, rồi mới thêm cụm cấm lấy từ chính kịch
bản đó.

**Ca sao chép sát** đã được chứng minh bằng test không phụ thuộc may mắn của
mô hình, trong `control_server/tests/brand-scripts-route.test.js`:
`beat chép nguyên văn nguồn -> CẢ script blocked, chỉ rõ cụm`,
`regenerate-beat: beat mới bẩn -> CẢ script chuyển blocked`,
`Blueprint KHÔNG có dấu vân tay -> unconfirmed, không bao giờ ready`,
`HỒI QUY: không có đường nào cho client đặt status = ready`.
Coi "mô hình tự nhiên không copy trong một lần thử" là bằng chứng thì sai —
nên ca qua giao diện là bổ sung, không phải chỗ dựa.

## Bước 5 — gom bằng chứng

```
python3 scripts/bao_cao_pilot_phase_h.py --ra bao-cao-pilot.md
```

Script tự gom sáu trong bảy mục và **không in transcript/caption gốc** (đúng
cam kết H2c), cũng không in nội dung USP/mô tả sản phẩm (có thể nhạy cảm).

Mục nó **không tự kết luận được là cổng 2** — nó chỉ biết caption đọc ra là gì
nếu bằng chứng còn lưu, mà H2c cố ý không lưu. Phải nhìn màn hình lúc chạy,
xem bước 1 mục 4.

## Bốn cổng mở H4

1. H2 tạo được ít nhất một Flow Blueprint thật qua giao diện.
2. H2b đọc đúng caption **có dấu** trên máy người dùng — **xác nhận bằng mắt**.
3. H2c có dấu vân tay, và H3 dùng được nó (kịch bản KHÔNG rơi vào
   `unconfirmed` vì thiếu vân tay).
4. H3 có ít nhất một kịch bản `ready`, **và** ca claim cấm chặn được thật.

Thiếu bất kỳ cổng nào thì H4 chưa nên bắt đầu — không phải vì thủ tục, mà vì
H4 nối kịch bản vào dựng video: sai ở tầng dưới sẽ đi thẳng vào sản phẩm cuối
mà không còn chỗ nào chặn lại.

# Pilot Phase H — bảng chạy rút gọn (in ra, làm theo)

Bản đầy đủ: `docs/PILOT_PHASE_H.md`. Tệp này chỉ là thứ tự thao tác, để chạy
một lượt không phải đọc lại lý do.

**Mục tiêu**: đóng **bốn cổng** rồi mới mở H4. Ước tính 60–80 Vox, ~30 phút.

---

## Chuẩn bị (5 phút)

| Việc | Cách kiểm là xong |
|---|---|
| Cài bản **v3.17.0** | Mở app, góc dưới hiện `3.17.0`. Bản cũ hơn KHÔNG có trang «Viết kịch bản» |
| Có kết nối máy chủ | Cài đặt → thấy số dư Vox. Không thấy = chưa nối, H3 sẽ không chạy |
| Còn ≥ 100 Vox | H2 tốn 8, H2b 8/lô 6 khung, H3 12 |
| Đã cài bộ quét chữ | Chưa cài thì bước đọc chữ báo "chưa cài", **khác** với "không có chữ" |

**Hai video, không phải một:**

- **Video A — kiểm cổng 2**: video bán hàng có **caption tiếng Việt cháy sẵn
  vào hình**, ưu tiên caption hook ở giây 0–5. Không có dấu tiếng Việt trên
  hình thì **cổng 2 không đóng được**.
- **Video B — kiểm chất lượng nhịp**: video tiếng Anh có hook → vấn đề →
  bằng chứng → kết quả → kêu gọi rõ ràng.
- Bí quá: `tap01_clip.mp4` trong repo — **chỉ để kiểm đường chạy**, không
  dùng để kết luận chất lượng.

Tránh cho lượt đầu: chữ quá nhỏ, khung rung, caption ẩn (không cháy vào hình).

---

## Bước 1 — H2 trên **video A** ⟶ đóng **cổng 1 + cổng 2**

1. Trang **Phân tích cấu trúc video tham khảo** → dán link hoặc chọn tệp.
2. Xem chạy đủ bốn bước: tải → chép lời → **đọc chữ** → phân tích cấu trúc.
3. ⚠️ **NHÌN MÀN HÌNH lúc chữ hiện ra.** Caption phải ra `Các bạn sẵn sàng`,
   KHÔNG phải `Cuc ban san sang`.
   → Đây là thứ **duy nhất** không script nào kiểm hộ được, vì H2c cố ý không
   lưu caption gốc. Chụp màn hình lại làm bằng chứng.
4. Mở **Nhật ký**, chép nguyên dòng này:
   ```
   Đọc chữ qua máy chủ: N khung lấy mẫu -> M đoạn chữ khác nhau ->
   gửi K khung (J khung đọc được kết quả)
   ```
   `K/N` là phần tiết kiệm, thiết kế nhắm ~1/3.

**Cổng 1 đóng** khi có ít nhất một Flow Blueprint thật.
**Cổng 2 đóng** khi bạn nhìn thấy dấu tiếng Việt đúng.

---

## Bước 2 — kiểm dấu vân tay ⟶ đóng **cổng 3** (phần 1)

Trên máy vừa chạy pilot:

```
python3 scripts/bao_cao_pilot_phase_h.py
```

Mục 2 phải có: `soBam` > 0, `soDong` khớp số dòng bằng chứng, `dayTran` = không.

> **Không có dấu vân tay thì DỪNG.** H3 sẽ luôn ra `unconfirmed`, cổng 3 không
> đóng được, và chạy tiếp chỉ tốn Vox.

Lưu ý dễ hiểu sai: endpoint **danh sách** trả `soBam: null` là bình thường
("chưa nạp ở đây"); endpoint **chi tiết** mới có số thật. Thấy `0` ở danh
sách mới là lỗi.

---

## Bước 3 — hồ sơ brand

Điền đủ **bốn trường bắt buộc**: mô tả sản phẩm, đối tượng khách, giọng điệu,
USP. Thiếu một trường ⟶ H3 chặn `400 HO_SO_BRAND_THIEU` và **không gọi mô
hình** (không mất Vox).

Thêm ít nhất một ràng buộc không được nói, ví dụ `tốt nhất`.

---

## Bước 4 — H3 ⟶ đóng **cổng 3** (phần 2) + **cổng 4** (phần 1)

Trang **Viết kịch bản** (nút ở cuối trang «Phân tích cấu trúc») → chọn nhịp
vừa tạo + hồ sơ brand → **Viết kịch bản**.

Kiểm: lời đọc có đúng giọng/USP không; caption có phải nội dung mới không;
visual brief có đủ cụ thể để chọn/dựng hình không.

**Cổng 3 đóng** khi kịch bản KHÔNG rơi vào `unconfirmed`.
**Cổng 4 (phần 1) đóng** khi có ít nhất một kịch bản `ready`.

---

## Bước 5 — ca claim cấm ⟶ đóng **cổng 4** (phần 2)

⚠️ **Thứ tự này bắt buộc. Cấm TRƯỚC khi sinh là sai.**

1. Sinh kịch bản bình thường (đã làm ở bước 4).
2. Mở kịch bản, chọn **đúng một cụm THẬT SỰ xuất hiện** trong lời đọc.
3. Thêm cụm đó vào ràng buộc không được nói của hồ sơ brand.
4. Bấm **Viết lại đoạn** chứa cụm đó.
5. Phải thấy: đoạn thành `violated`, chỉ **đúng cụm đó** + đúng câu ràng
   buộc, **cả kịch bản** thành `blocked`, nút «Dùng kịch bản này» **tắt**.

Vì sao không cấm trước: mô hình tốt sẽ tự né ngay từ lời nhắc (đo thật 10/09
— nó viết "Đầu ngày mở mắt ra" thay vì cụm bị cấm). Gate không kích hoạt thì
bạn không phân biệt được (a) lớp phòng đầu chạy tốt hay (b) lớp chặn sau đã
hỏng nhưng bị che.

---

## Bước 6 — gom bằng chứng

```
python3 scripts/bao_cao_pilot_phase_h.py --ra bao-cao-pilot.md
```

Gom 6/7 mục, **không in** transcript/caption gốc (giữ cam kết H2c) và không
in USP/mô tả sản phẩm. Mục thứ 7 là cổng 2 — ảnh chụp màn hình của bạn ở
bước 1.

---

## Bảng đánh dấu

| Cổng | Nội dung | Xong? |
|---|---|---|
| 1 | H2 tạo được Flow Blueprint thật qua giao diện | ☐ |
| 2 | H2b đọc đúng caption **có dấu** — xác nhận bằng mắt | ☐ |
| 3 | H2c có vân tay **và** H3 dùng được nó (không `unconfirmed`) | ☐ |
| 4 | H3 có kịch bản `ready` **và** ca claim cấm chặn thật | ☐ |

Thiếu bất kỳ cổng nào thì **chưa nên dùng H4 để làm video thật** — H4 nối
kịch bản thẳng vào dựng video, sai ở tầng dưới sẽ đi vào sản phẩm cuối mà
không còn chỗ nào chặn lại.

---

## Nếu muốn thử luôn H4d (vẽ ảnh, 30 Vox/tấm)

Cửa `image.scene.stage` trên prod đang ở nấc **`calibration`** — chỉ mở cho
các máy nằm trong `image.scene.calibration.devices`. Máy bạn không có trong
danh sách thì nút «Vẽ» trả `409 IMAGE_STAGE_CALIBRATION`, **không mất Vox**.

H4d cũng cần một **nơi gọi mô hình sinh ảnh từ chữ**. Nếu bản khai hiện tại
là `custom_images` dựng cho C1 (có `{{image_data_uri}}`) thì nó **không dùng
được** cho ảnh minh hoạ — phải thêm bản khai thứ hai trỏ tới cửa sinh-từ-chữ.
Thông báo lỗi sẽ nói đúng câu đó thay vì để bạn đoán.

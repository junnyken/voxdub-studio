# Quy trình tạo video sản phẩm bằng VoxDub Studio

> Viết cho người **vận hành** VoxDub để làm video bán hàng — không cần biết code.
> Bản v3.17.22 · cập nhật 28/09/2026.

---

## Công cụ này làm gì, và KHÔNG làm gì

**Làm:** ghép **ảnh tĩnh** thành video dọc 9:16, mỗi đoạn một tấm ảnh giữ đúng
bằng thời gian đọc lời của đoạn đó, nối nhau bằng chuyển cảnh, kèm giọng đọc AI.

**KHÔNG làm:** không sinh video cho từng đoạn, không zoom/pan trên ảnh. Ảnh
đứng yên hoàn toàn. Nếu bạn cần cảnh quay có chuyển động thì phải tự quay rồi
dựng ở công cụ khác — VoxDub lo phần kịch bản, giọng đọc và ghép.

---

## Toàn cảnh

```
① Phân tích video tham khảo   →  học NHỊP kể chuyện        (~8 Vox+)
② Viết kịch bản cho thương hiệu →  7 đoạn có lời + chữ + mô tả hình  (~12 Vox)
③ Chuẩn bị ảnh                 →  1 ảnh mỗi đoạn            (0 hoặc 33 Vox/tấm)
④ Dựng dự án                   →  ghép thành video          (0 Vox)
⑤ Trình chỉnh sửa              →  nghe thử, sửa, xuất       (0 Vox)
```

---

## ① Phân tích video tham khảo

Mục đích **không** phải chép nội dung người khác, mà là đọc **vai trò kể
chuyện** của từng đoạn: đâu là mở hook, đâu là bằng chứng, đâu là cao trào.

1. Trang **Phân tích cấu trúc** → dán link video tham khảo → **Phân tích cấu trúc**.
2. Chờ. Xong thì nó hiện ở bảng **Đã phân tích trước đây** kèm số đoạn.

> ### ⚠️ Chọn video NGẮN — đây là bẫy tốn thời gian nhất
>
> Số khung hình phải đọc **tỉ lệ thẳng với độ dài video và chưa có trần**:
>
> | video dài | số khung | thời gian đọc chữ |
> |---|---|---|
> | 30 giây | 91 | 3–20 phút |
> | 1 phút | 151 | 5–35 phút |
> | 5 phút | **631** | 21 phút – **2,5 giờ** |
> | 10 phút | **1.231** | 41 phút – **4,8 giờ** |
>
> Dùng video **dưới 60 giây**. Video dài không cho nhịp tốt hơn — nhịp nằm ở
> cấu trúc, không ở độ dài. Lỡ chạy video dài thì bấm **Dừng** (dừng trong
> vòng một khung, phần chạy tại máy không tốn Vox).

**Phân tích lại một lần là đủ.** Kết quả lưu lại, dùng cho nhiều kịch bản sau.

---

## ② Viết kịch bản cho thương hiệu

1. Trang **Viết kịch bản** → chọn **Nhịp kể chuyện** (bản vừa phân tích) và
   **Thương hiệu**.
2. Bấm **Viết kịch bản** (~12 Vox). Viết lại một đoạn cũng tính một lượt.

Kết quả là bảng 7 đoạn: *Lời đọc · Chữ trên hình · Cần quay gì · Kiểm tra*.

**Đọc cột «Kiểm tra» trước tiên.** Máy chủ tự đối chiếu với video nguồn: đoạn
nào trùng câu chữ sẽ bị **chặn**, không có nút bỏ qua. Trạng thái phải là
**Dùng được** thì mới đi tiếp được.

**Rồi đọc bằng mắt người.** Máy kiểm được *không trùng, không cấm* — nó không
kiểm được *có thuyết phục không*. Cần soi:

- Hai đoạn có đang nói **cùng một ý** không? (thường gặp: hai đoạn cùng kể
  tính năng, thiếu đoạn nói giá hoặc lý do chọn mình thay vì đối thủ)
- Lời đọc có tự nhiên khi **đọc to** không?
- Đoạn kêu gọi hành động có nói rõ **làm gì tiếp** không?

Sửa bằng **Viết lại đoạn** ở đúng dòng đó.

### Chỉ đạo hình ảnh (tuỳ chọn)

Nút **Chỉ đạo hình ảnh…** cho trợ lý chọn kiểu chuyển cảnh cho từng đoạn —
hook cắt thẳng cho dứt khoát, thân mờ nhẹ cho êm. Sửa tay trong hộp thoại đó
**không tốn Vox**. Không dùng thì cả video dùng mờ chồng.

---

## ③ Chuẩn bị ảnh — bước quyết định chất lượng

Mỗi đoạn cần **một** ảnh. Hai đường:

### (a) Tự chụp/chọn — khuyên dùng, 0 Vox

Bấm **Chọn ảnh cho tất cả…**. Đọc cột «Cần quay gì» của từng đoạn rồi chụp
đúng thứ đó.

> **Vì sao nên tự chụp:** mô tả trong kịch bản gần như luôn là *ảnh sản phẩm
> thật của bạn* — giao diện quản lý, biểu đồ, logo, nút đăng ký. AI vẽ ra sẽ
> là giao diện **bịa**, trông giống phần mềm nhưng không phải phần mềm của
> bạn. Với video bán hàng thì đó là điểm trừ, không phải điểm cộng.

Ảnh nên **dọc 9:16** hoặc cắt được về 9:16.

### (b) Nhờ AI vẽ — 33 Vox/tấm

Bấm **Vẽ ảnh cho các đoạn còn thiếu…**. Hợp khi cần ảnh **minh hoạ khái
niệm** (ẩn dụ, nền trừu tượng), không hợp khi cần giao diện thật.

Báo *"Tính năng dựng ảnh đang trong giai đoạn hiệu chỉnh, chưa mở cho máy
này"* → xem **Phụ lục A**.

---

## ④ Dựng dự án — 0 Vox

Đủ ảnh thì nút **Dựng dự án** sáng. Bấm. Máy ghép ảnh + giọng đọc + chuyển
cảnh, **không tốn Vox** và **không gọi máy chủ**.

---

## ⑤ Trình chỉnh sửa

Dự án tự mở ở đây. Nghe thử từng đoạn, sửa lời đọc nếu giọng AI đọc sai,
rồi **xuất video**.

---

## Bảng chi phí

| Việc | Vox |
|---|---|
| Phân tích cấu trúc | 8 + 8 mỗi lô 6 khung có chữ |
| Viết kịch bản | ~12 mỗi lượt (viết lại 1 đoạn = 1 lượt) |
| Chỉ đạo hình ảnh — sửa tay | **0** |
| Vẽ ảnh | 33 mỗi tấm |
| Dựng dự án + xuất video | **0** |

Vox trừ **sau khi** chạy xong. Vượt ngưỡng thì có hộp thoại xin phép trước.

---

## Làm nhiều video cho cùng một thương hiệu

Đặt **sân khấu** trong **Hồ sơ brand** (mới từ v3.17.22): bối cảnh · đạo cụ +
ánh sáng · khung người. Mọi kịch bản sinh sau đó được nhắc **dùng lại đúng
sân khấu ấy**, nên các video của cùng brand trông như một loạt chứ không
phải ba thương hiệu khác nhau.

Khác với *nếp chỉ đạo hình ảnh* — nếp là gợi ý, sân khấu là yêu cầu dùng lại.

---

## Phụ lục A — mở tính năng vẽ ảnh

Tính năng có ba nấc, đặt ở trang admin → **Cấu hình**, khoá `image.scene.stage`:

| Nấc | Ai dùng được |
|---|---|
| (thiếu / gõ sai) | **không ai** — lỗi chính tả không được phép mở cửa |
| `calibration` | chỉ máy có vân tay trong `image.scene.calibration.devices` |
| `production` | **mọi máy** |

**Mở cho một máy (tạm):** lấy vân tay ở admin → **Thiết bị**, thêm vào
`image.scene.calibration.devices`, ngăn cách bằng dấu phẩy.

**Mở cho mọi máy (lâu dài):** chạy ~20 lượt vẽ ảnh ở nấc `calibration`, vào
admin → **Trợ lý** soi từng phán quyết tuân thủ (đồng ý / không đồng ý). Đủ
**20 lượt ĐÃ SOI** thì bấm được `production`.

> Máy chủ **từ chối** bấm `production` khi chưa đủ, và từ chối đúng: bấm nấc
> đó là mở cho mọi người bán trong khi chưa ai kiểm phán quyết tuân thủ đúng
> hay sai. *Số lượt đã chạy không thay được số lượt đã soi.*

---

## Phụ lục B — hỏng thì xem gì

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Phân tích chạy mãi | video quá dài — xem bảng ở ① |
| Kịch bản bị chặn | trùng câu chữ video nguồn; viết lại đoạn đó |
| Nút «Dựng dự án» mờ | còn đoạn chưa có ảnh |
| Đăng nhập lỗi, Vox không hiện | bản app cũ hơn v3.17.22 — địa chỉ máy chủ đã đổi 28/09 |
| Lồng tiếng máy chủ không chạy | hỏi quản trị kiểm `CONTROL_SERVER_URL` của worker |

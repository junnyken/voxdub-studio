# MINI-SPEC I8 — Đường nhập sân khấu thương hiệu

- **Họ:** I — đóng khoảng trống I7 §B2-b
- **Tác giả:** Claude (viết từ đo mã thật, 28/09/2026)
- **Trạng thái:** ĐÃ LÀM A→D 28/09/2026 — trừ tiêu chí 6 (bấm thật trên Windows)

---

## 0. Audit — đo được, không suy đoán

### (a) Triệu chứng

I7 §B2-b dựng "sân khấu quen của thương hiệu" để các video của cùng một brand
không đổi bối cảnh mỗi lần. Lời nhắc nói rất dứt khoát
([assist.js:695](../control_server/src/prompts/assist.js#L695)):

> `SÂN KHẤU của thương hiệu — DÙNG LẠI, đừng chốt sân khấu mới:`

Nhưng **không brand nào đang có sân khấu**, vì **không có chỗ nào để nhập**.

### (b) Hỏng IM LẶNG, không báo gì

[assist.js:951](../control_server/src/prompts/assist.js#L951):

```js
function dongSanKhauBrand(sk) {
  if (!sk) return ''
  const phan = [ /* boiCanh, daoCuAnhSang, quyUocKhungNguoi */ ].filter(Boolean)
  if (!phan.length) return ''
  return 'SÂN KHẤU của thương hiệu — DÙNG LẠI, đừng chốt sân khấu mới:\n' + …
}
```

Rỗng ⇒ trả `''` ⇒ **cả khối biến mất khỏi lời nhắc**. Không lỗi, không cảnh
báo, không dòng log. Từ ngoài nhìn vào, §B trông như đã chạy.

### (c) Phía MÁY CHỦ đã đủ và đúng — đừng đụng vào

Đã đo từng tầng:

| Tầng | Tệp | Trạng thái |
|---|---|---|
| Model | `models/BrandProfile.js:40-44` | 3 trường, `maxlength: 300` ✅ |
| Schema HTTP | `routes/brand-profiles.js` `bodySchema.properties.sanKhau` | khai đủ, `maxLength: 300` ✅ |
| Danh sách trắng | `TRUONG_CHO_PHEP` | có `sanKhau` ✅ |
| `PUT /:id` | chép theo `hasOwnProperty` | thiếu trường thì **GIỮ NGUYÊN**, không xoá ✅ |
| Lời nhắc | `assist.js:695`, `:1306-1309` | tiêu thụ đúng ✅ |

**Không có việc gì phải làm ở `control_server`.**

### (d) Khoảng trống nằm TRỌN ở phía client — ba chỗ

| # | Tệp | Thiếu gì |
|---|---|---|
| 1 | `autodub_gui/pages/brand_profile_page.py` — `BrandProfileFormDialog` | không có ô nhập nào cho sân khấu |
| 2 | cùng tệp — `fields()` | không trả `san_khau` |
| 3 | `autodub/saas_client.py:898`, `:916` | `create_brand_profile`/`update_brand_profile` không nhận và không gửi `sanKhau` |

### (e) Ba bẫy phải tránh

1. **ajv xoá im lặng.** `bodySchema` có `additionalProperties: false`, và
   `sanKhau` cũng có `additionalProperties: false` ở cấp lồng. Gõ sai tên một
   trường con (vd `boicanh`) thì ajv **xoá nó trước khi handler chạy** — máy
   chủ trả `200`, giao diện báo đã lưu, giá trị biến mất. Nên test phải
   **đọc lại** giá trị, không được dừng ở mã 200 (bài học đã ghi:
   *API trả 200 KHÔNG nghĩa là đã ghi*).
2. **Trần 300 ký tự ở CẢ HAI tầng** (schema HTTP + mongoose). Vượt trần thì
   máy chủ từ chối; giao diện phải chặn trước hoặc hiện lỗi đọc được, không
   được nuốt.
3. **`PUT` không xoá trường vắng mặt** — nên bản client CŨ (chưa có I8) sửa
   một brand sẽ *không* làm mất sân khấu đã đặt. Đây là tin tốt, nhưng phải
   giữ: đừng đổi `PUT` sang ghi đè cả cụm.

## 1. Đọc trước khi sửa

- `autodub_gui/pages/brand_profile_page.py` (toàn bộ `BrandProfileFormDialog`)
- `autodub/saas_client.py:886-945`
- `control_server/src/routes/brand-profiles.js` (`bodySchema`, `TRUONG_CHO_PHEP`, `PUT`)
- `control_server/src/prompts/assist.js:690-700`, `:951-961`
- `docs/MINI-SPEC_I7_Bo_Cuc_Theo_Nhip_Va_Dong_Nhat_Boi_Canh.md` §B2-b, §B4

## 2. Mục tiêu

Người dùng **đặt được** sân khấu cho một thương hiệu từ giao diện, và giá trị
đó **thật sự tới lời nhắc** — chứng minh bằng đọc lại, không bằng mã 200.

## 3. Rào chắn

1. **Không sửa `control_server`.** §0c cho thấy nó đã đúng. Sửa thêm ở đó là
   mở rộng phạm vi và tạo rủi ro mới cho một thứ đang chạy.
2. **Không sửa `scene_continuity`** — I7 §B4 đã chốt: nó *cố ý* không xét bối
   cảnh, và luật đó đúng cho việc của nó.
3. **Sân khấu là TUỲ CHỌN.** Brand không đặt vẫn phải chạy y như hôm nay
   (`dongSanKhauBrand` trả `''`). Đừng biến nó thành trường bắt buộc —
   `rangBuocKhongDuocNoi` bắt buộc là vì Constraint 2 của H1, sân khấu không
   có ràng buộc tương đương.
4. **Đừng đụng `TRUONG_CHO_PHEP` hay `bodySchema`.** Chúng đã có `sanKhau`.
5. **Chứng minh bằng đọc lại.** Test phải ghi rồi `GET` lại và so giá trị.
   Thêm một phép tiêm: gõ sai tên trường con ⇒ test phải ĐỎ (chứng minh nó
   thật sự bắt được cú xoá im lặng của ajv).

## 4. Phạm vi

### A. Ba ô nhập trong `BrandProfileFormDialog`

Đặt sau `usp`, trước khối ràng buộc. Dùng đúng hàm `truong()` có sẵn:

- **Bối cảnh** — nơi quay quen thuộc
- **Đạo cụ + ánh sáng**
- **Khung người** — quy ước đóng khung nhân vật

Nhãn phải nói rõ đây là **dùng lại giữa các video**, để phân biệt với *nếp chỉ
đạo* (I6) vốn chỉ là gợi ý. Mỗi ô nạp sẵn từ `p.get("sanKhau", {})`.

### B. `fields()` trả thêm `san_khau`

Luôn trả cụm 3 trường (chuỗi rỗng nếu người dùng bỏ trống) — cùng kiểu
"luôn có mặt" như `rang_buoc_khong_duoc_noi`, để phía sau không phải đoán
giữa "không đặt" và "đặt rỗng".

### C. `saas_client` nhận và gửi

`create_brand_profile` và `update_brand_profile` thêm tham số `san_khau`
(dict, mặc định `None`), đưa vào payload dưới khoá `sanKhau`. **Tên trường con
phải khớp chính xác** `boiCanh` / `daoCuAnhSang` / `quyUocKhungNguoi` (§0e-1).

### D. Chặn độ dài ở giao diện

Trần 300/ô, chặn tại chỗ nhập thay vì để máy chủ từ chối cả biểu mẫu.

## 5. Tiêu chí thành công

1. Đặt sân khấu trên giao diện → `GET` lại trả **đúng** ba giá trị.
2. Brand có sân khấu → lời nhắc **chứa** khối `SÂN KHẤU của thương hiệu`.
   Brand không đặt → lời nhắc **không đổi** so với hôm nay.
3. Sửa brand bằng client CŨ (không gửi `sanKhau`) → sân khấu **còn nguyên**.
4. Phép tiêm gõ sai tên trường con làm test ĐỎ.
5. `pytest` + `npm test` xanh.
6. Bấm thật trên Windows: đặt sân khấu cho **Mắt Bão**, sinh một kịch bản,
   xác nhận sân khấu xuất hiện trong bản chỉ đạo.

## 6. Ngoài phạm vi

- Sửa bất cứ thứ gì trong `control_server`.
- Giao diện web (brand quản lý ở app desktop, không ở web).
- Tự suy sân khấu bằng AI — I8 chỉ mở đường nhập tay.
- Chạy cổng A/B của I7 §6. I8 **gỡ chặn** cho nó, nhưng đo là việc riêng và
  tốn tiền gọi mô hình.

# v3.17.22 — đặt được «sân khấu» cho thương hiệu, và bản này BẮT BUỘC cập nhật

Bản này có **một** thay đổi bạn nhìn thấy, và **một** lý do kỹ thuật khiến nó
là bản bắt buộc.

> ## ⚠️ Vì sao phải cập nhật, kể cả khi bạn không dùng tính năng mới
>
> Máy chủ VoxDub đã **đổi địa chỉ** ngày 28/09. Địa chỉ cũ không còn trả lời.
>
> Địa chỉ máy chủ được **gắn sẵn vào file cài đặt** lúc chúng tôi dựng bản —
> nên **v3.17.21 và mọi bản cũ hơn sẽ không kết nối được nữa**. Triệu chứng
> bạn gặp: đăng nhập không được, số Vox không hiện, «Viết kịch bản» và «Chỉ
> đạo hình ảnh» báo lỗi mạng hoặc không phản hồi.
>
> Lồng tiếng chạy trên máy bạn thì **vẫn chạy bình thường** — phần đó không
> cần máy chủ. Chỉ các tính năng có gọi máy chủ mới đứng.
>
> Cài v3.17.22 là hết. Không phải gỡ bản cũ, không mất cấu hình.

---

## Sân khấu của thương hiệu

**Vấn đề:** bạn làm nhiều video cho cùng một thương hiệu. Mỗi lần trợ lý viết
kịch bản, nó lại tự chọn một bối cảnh khác — video này bàn gỗ, video sau quán
cà phê, video sau nữa phòng trắng. Xem rời từng cái thì đẹp; xem liền mạch
trên trang của bạn thì như ba thương hiệu khác nhau.

Bên trong, VoxDub **đã có sẵn** chỗ để giữ sân khấu cố định và đã biết nhắc
trợ lý *"dùng lại sân khấu của thương hiệu, đừng chốt sân khấu mới"*. Nhưng
**không có ô nào để bạn điền vào** — nên lời nhắc đó luôn rỗng và không bao
giờ tới nơi. Tính năng có, mà không ai chạm được.

**Nay:** mở **Hồ sơ brand** → sửa một thương hiệu, bạn thấy ba ô mới:

| Ô | Điền gì | Ví dụ |
|---|---|---|
| **Bối cảnh** | nơi quay quen thuộc | *bàn làm việc gỗ sáng, tường trắng* |
| **Đạo cụ + ánh sáng** | vật dụng và kiểu sáng cố định | *đèn dịu từ trái, laptop mở* |
| **Khung người** | cách đóng khung nhân vật | *nửa người, chính diện, ngang tầm mắt* |

Điền xong, mọi kịch bản sinh sau đó cho thương hiệu này đều được nhắc dùng lại
đúng sân khấu ấy.

**Ba điều nên biết:**

- **Không bắt buộc.** Để trống cả ba ô thì mọi thứ chạy y như trước — không có
  gì đổi, không có cảnh báo.
- **Khác với «nếp chỉ đạo hình ảnh»** (có từ v3.17.21). Nếp chỉ đạo là *gợi ý*
  — trợ lý vẫn được chọn khác khi một đoạn cần thế. Sân khấu là *yêu cầu dùng
  lại*, vì đổi bối cảnh giữa các video của cùng brand phá đúng cái đồng nhất
  bạn đang xây.
- **Tối đa 300 ký tự mỗi ô.** Gõ quá thì ô tự dừng lại — viết ngắn gọn, đây là
  lời nhắc cho trợ lý chứ không phải bản mô tả cảnh quay.

**Chưa làm:** VoxDub **không tự đoán** sân khấu từ video cũ của bạn. Bản này
chỉ mở đường để bạn tự điền. Và sân khấu hiện tác động vào phần **viết kịch
bản / chỉ đạo hình ảnh**; nó chưa tự chèn vào ảnh bạn tải lên.

---

## Cài đặt

Tải `VoxDub-Studio-v3.17.22-win64.zip` bên dưới, giải nén, chạy như thường lệ.
Cấu hình, giọng đã tải và dự án cũ giữ nguyên.

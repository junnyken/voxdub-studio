# Hướng dẫn đổi mô hình cho vai «trợ lý» (`assist`)

- **Cho ai**: chủ dự án / người quản trị máy chủ.
- **Vì sao có tệp này**: đo ngày 22/09/2026 cho thấy mô hình đang gán cho vai
  `assist` (`sonar`) **viết thiếu đoạn** ở kịch bản dài và **thỉnh thoảng
  không nhìn được ảnh**. Chi tiết số đo: `docs/TEST_LOG.md`, mục
  "Đo trước khi đổi mô hình vai `assist`".
- **Không có khoá API nào trong tệp này.** Khoá là việc của chủ dự án.

---

## 1. Vì sao phải đổi — ba con số

| Đo được (22/09/2026) | `sonar` (đang chạy) | `gemini-3.6-flash` (ứng viên) |
|---|---|---|
| H3 viết đủ số đoạn, kịch bản 20 đoạn | **2/3 lượt** | **3/3 lượt** |
| H3 viết đủ số đoạn, kịch bản 40 đoạn | **0/4 lượt** | **2/2 lượt** |
| Bốn tác vụ gửi ảnh | **3/4** (rớt phép thử nhìn ở `packaging_check`) | **4/4** |

Kịch bản thiếu đoạn bị máy chủ **huỷ cả lượt** (người dùng không mất Vox,
nhưng cũng không có kịch bản).

## 2. Điền gì vào đâu

Trang quản trị → **«Nơi gọi mô hình»** → sửa dòng có **Vai trò = `assist`**
(hoặc thêm dòng mới rồi tắt dòng cũ).

| Ô trên giao diện | Điền | Ghi chú |
|---|---|---|
| Tên định danh | `gemini-assist` (tuỳ ý, không dấu) | chỉ là tên để nhận ra |
| Nhãn hiển thị | `Gemini Flash (trợ lý)` | hiện trong bảng |
| **Vai trò** | **`assist`** | sai ô này là đổi nhầm vai khác |
| **Giao thức** | **`google`** | **KHÔNG phải `openai_compat`** — Gemini có API riêng |
| **Địa chỉ máy chủ** | `https://generativelanguage.googleapis.com/v1beta` | khác hẳn địa chỉ kiểu OpenAI |
| **Khoá API** | khoá Google AI Studio của chủ dự án | sửa dòng cũ mà để trống ô này thì **giữ nguyên khoá cũ** — đổi nhà cung cấp thì phải điền khoá mới |
| **Mô hình** | **`gemini-3.6-flash`** | xem bẫy ở mục 3 |
| Nhiệt độ | `0.3` | giữ mặc định |
| Token tối đa | `16384` | giữ mặc định; đã đo đầu ra thật 991–3.437 token |
| Thời gian chờ | `180000` trở lên | Gemini chậm hơn `sonar` (xem mục 5) |
| Ưu tiên | số nhỏ hơn dòng cũ | dòng ưu tiên nhỏ hơn được gọi trước |
| Bật | có | |

## 3. Ba cái bẫy đã gặp thật khi đo

1. **Tên mô hình KHÔNG có tiền tố.** Ô «Mô hình» đang gợi ý
   `google/gemini-2.5-flash` — kiểu viết của OpenRouter. Với Giao thức
   `google` thì máy chủ ghép địa chỉ thành
   `…/v1beta/models/<Mô hình>:generateContent`, nên điền
   `google/gemini-3.6-flash` sẽ ra `…/models/google/gemini-3.6-flash:…` và
   **404**. Điền đúng `gemini-3.6-flash`.
2. **`gemini-2.5-flash` đã bị khai tử cho khoá mới.** Đo được: HTTP 404 kèm
   câu *"no longer available to new users… use models/gemini-3.6-flash"*.
   Đừng điền bản 2.5.
3. **Vai `translate` của máy chủ hiện cũng đang là `gemini-2.5-flash`.** Nó có
   thể còn chạy nhờ ân hạn cho bản ghi cũ, nhưng **hãy bấm «Thử ngay» cho
   dòng vai `translate`** khi mở trang này — đó là đường dịch của toàn bộ
   pipeline lồng tiếng, hỏng thì mất nhiều hơn vai trợ lý rất nhiều.

## 4. Dấu hiệu đã đổi THÀNH CÔNG

Theo thứ tự, dừng lại ngay khi có cái nào không đúng:

1. **«Thử ngay»** ở chính dòng vừa sửa → phải trả `gọi được: có` **và
   `nhìn được ảnh: có`**. Riêng ô «nhìn được ảnh» là điều kiện bắt buộc của
   bước kiểm bao bì — thiếu nó thì `packaging_check` sẽ bị chặn.
2. **Trang «Cổng trợ lý»** → dải đỏ *"Đang chạy nhờ vai «dịch thuật»"* phải
   **không xuất hiện**. Nó chỉ hiện khi có lượt trợ lý chạy bằng vai
   `translate`; sau khi đổi đúng thì mọi lượt mới phải là vai `assist`.
3. **Chạy thật một lượt**: viết một kịch bản brand (H3) rồi mở bảng «Mô hình»
   ở trang «Cổng trợ lý» — cột mô hình phải là `gemini-3.6-flash`, không phải
   tên cũ.
4. **Một lượt có ảnh**: bấm kiểm bao bì một lần. Qua được nghĩa là phép thử
   nhìn ảnh đã chạy thật trên mô hình mới, không chỉ trên bài thử của
   «Thử ngay».

Nếu (1) trả `nhìn được ảnh: không` thì **dừng lại và giữ nguyên dòng cũ** —
bốn tác vụ có ảnh sẽ ngừng chạy.

## 5. Đánh đổi phải biết trước

- **Chậm hơn.** Đo cùng việc: `scene_director` 40 đoạn mất **36,1 giây** với
  Gemini so với **29,6 giây** với `sonar`; tác vụ ngắn 4,3–7,2 giây so với
  1,4–4,5 giây. Giao diện đều có nút Dừng và đường lui, nhưng người dùng sẽ
  thấy chậm hơn.
- **Số token tương đương** (chênh dưới ~15% ở kịch bản 20–40 đoạn), nên chênh
  lệch tiền chủ yếu nằm ở đơn giá mỗi nhà cung cấp — con số đó đọc ở trang
  thanh toán của chính họ, tệp này không đoán hộ.
- **Giá Vox không phải đổi**: đã đo lại `scene_director` ở 5/20/40 đoạn, tổng
  token với Gemini còn thấp hơn `sonar` ở cỡ 20 và 40. Mức 5 Vox giữ nguyên.
- **Không phải sửa dòng mã nào.** Đã rà: không tệp nào trong `control_server/src`,
  `control_server/evals`, `autodub/`, `autodub_gui/` nhắc tới `sonar` hay
  Perplexity. Lời nhắc và mẫu đo không ghim theo hành vi của một mô hình cụ thể.

## 6. Sau khi đổi xong, sửa tài liệu cho khớp

Hai chỗ đang ghi tên mô hình cũ, phải cập nhật để tài liệu không nói sai:

- `FEATURES.md` §4 — dòng *"Vai `assist` nay có nhà cung cấp (Perplexity `sonar`)"*.
- `docs/TEST_LOG.md` — mục I1 bước 2/3 ghi `sonar` như **bằng chứng lịch sử**;
  giữ nguyên (đó là thứ đã đo hôm ấy), chỉ thêm dòng nói đã đổi từ ngày nào.

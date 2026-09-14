# H5 — Dải điều hướng Phase H: Phân tích cấu trúc → Viết kịch bản → Dựng video

**Lập 14/09/2026.** Chủ dự án chạy pilot thật rồi báo: *"tôi thấy nó đang bị
thiếu quy trình… tôi không thấy biểu hiện gì làm tiếp theo"*.

> **Tên lát: H5, KHÔNG phải H4e.** Bản spec nhận được đặt tên `H4e`, nhưng
> `H4e` **đã có chủ** từ 10/09: đó là *"Giao diện storyboard / trang Dựng video
> từ kịch bản"* (commit `9a90cb1`), đang được `app.py:60`, `app.py:493`,
> `MINI-SPEC_H4_Storyboard_To_Video.md:148` và `MINI-SPEC_H4d` tham chiếu.
> Chủ dự án chốt đổi sang **H5** ngày 14/09.

---

## Audit trước khi code — và hai tiền đề SAI

### Bảy tiền đề đúng

| Kiểm | Kết quả |
|---|---|
| Ba trang có thật | `ROW_FLOW_BLUEPRINT=19` · `ROW_BRAND_SCRIPT=20` · `ROW_STORYBOARD=21` |
| Cơ chế chuyển trang | `switch_page(row)` + `_ensure_page(row)` — **dùng lại, không dựng router thứ hai** |
| **Giữ context** | ✅ `_ensure_page` **cache trang, không bao giờ huỷ** ⇒ `_hien_tai`/`_kich_ban`/`_anh` sống qua điều hướng. Ràng buộc 6 thoả được mà không phải thêm gì |
| Cổng H3→H4 | Ở **tầng hàm** (`dung_storyboard` ném `KichBanChuaDungDuoc`) ⇒ dải **không thể** bypass |
| Thiếu ảnh nêu đoạn nào | ✅ `ThieuAnh` đã liệt kê số đoạn |
| Test thanh bên | `tests/test_sidebar_no_overlap.py` (6 test, chốt 1080p) |
| `switch_page` có chốt riêng | `_blocked_by_unsaved` — hỏi trước khi rời trang còn việc dở |

### ❌ Tiền đề sai 1 — `H4e` đã có chủ

Xem khung trên. Đặt trùng tên tạo đúng va chạm mà backlog đã ghi sau sự cố
tiền tố `C<n>`.

> **Phát hiện phụ:** backlog ghi chốt `test_so_mini_spec_khong_trung` đã bắt
> được va chạm đó. **Test ấy KHÔNG tồn tại trong kho.** Bài học được ghi lại
> nhưng chốt chưa bao giờ được dựng — còn mở.

### ❌ Tiền đề sai 2 — component đã có sẵn

Spec viết *"Tạo component chung, ví dụ `PhaseHRibbon`"*. Nhưng
`autodub_gui/ui/stepper.py::Stepper` đã có: bấm được (`step_clicked`), ba trạng
thái `DONE/CURRENT/UPCOMING`, đang dùng ở **hai** chỗ. Tạo mới là dựng bản sao
thứ ba — trái chính Ràng buộc 2.

**Đã làm**: thêm `compact=True` + `tu_do_nhay=True` vào `Stepper`, rồi bọc
mỏng thành `PhaseHRibbon`. Hai chỗ dùng cũ **không truyền tham số mới nên
không đổi hành vi** — có test chốt (76px và luật nhảy cũ giữ nguyên).

### ⚠️ Một chỗ spec tự mâu thuẫn

Ràng buộc C nói *"ribbon chỉ đọc status đã có"*, nhưng bốn trạng thái H4 spec
liệt kê **chưa tồn tại tách bạch**: `blocked`/`unconfirmed`/`failed` đang gộp
làm một câu, `ready_missing_images` chỉ hiện **sau khi bấm Dựng**. Nên phần này
là **dựng mới một máy trạng thái hiển thị**, không phải chỉ đọc. Đã làm, và
đây là phần tốn công nhất — không phải phần vẽ dải.

---

## Đã dựng

### 1. `Stepper` — thêm chế độ, không đổi mặc định

`compact=True` (76px → 46px) và `tu_do_nhay=True`. Chế độ tự do nhảy là bắt
buộc: người dùng phải mở được H4 để **biết mình còn thiếu gì**, kể cả khi chưa
có kịch bản. Luật cũ (`max_reached + 1`) giữ nguyên cho trình hướng dẫn cài
đặt, nơi nhảy vượt bước đúng là vô nghĩa.

### 2. `ui/phase_h_ribbon.py` — dải dùng chung

Ba nhãn + một dòng nói **bước sau cần gì**. Bấm lại chính bước đang xem thì
không phát tín hiệu: dựng lại trang là vô ích, và ở H4 còn làm mất ảnh đang
gán dở.

### 3. Điều hướng đi qua `switch_page` sẵn có

`_noi_dai_phase_h(page)` nối dải của cả ba trang vào `switch_page`. **Cố ý
không tự đổi trang**: `switch_page` còn mang `_blocked_by_unsaved`, và một
đường chuyển trang thứ hai là bỏ qua chốt đó mà không ai nhận ra.

### 4. Bốn trạng thái H4 — bốn câu, mỗi câu có ĐƯỜNG XỬ LÝ

| Mã | Khi nào | Nói gì |
|---|---|---|
| `chua_chon` | chưa có kịch bản | quay lại «Viết kịch bản», bấm «Dùng kịch bản này» |
| `bi_chan` | `blocked` | quay lại, bấm «Viết lại đoạn» ở đoạn được đánh dấu |
| `chua_kiem` | `unconfirmed` | quay lại xem từng đoạn vì sao chưa kiểm được |
| `thieu_anh` | `ready` nhưng thiếu ảnh | **nêu đúng số đoạn thiếu**, không hứa tự sinh ảnh |

Gộp bốn ca thành một câu *"chưa dùng được"* chính là thứ khiến chủ dự án nhìn
màn hình rồi hỏi *"nên làm gì tiếp"* — có lý do mà không có đường đi.

**Không hứa H4d.** Cửa sinh ảnh đang TẮT ở máy chủ; hứa một thứ chưa bật là để
người dùng ngồi chờ một nút không bao giờ sáng. Có test cấm các cụm "tự sinh",
"tự vẽ", "AI sẽ".

---

## Đã kiểm

`tests/test_h5_dai_dieu_huong_phase_h.py` — **22 test**. Ba phép chứng minh
phủ định, mỗi cái gỡ **đúng một** chốt:

| Gỡ gì | Test đỏ |
|---|---|
| điều kiện `ready` trong `dung_storyboard` | `..._dai_KHONG_mo_cong_dung_video` (cả 3 trạng thái) |
| phần giải thích bốn ca | `..._moi_ca_H4_phai_co_cau_RIENG` + `..._DUNG_DOAN_NAO` |
| `_noi_dai_phase_h` ở một trang | `test_moi_trang_phase_h_deu_duoc_noi_dai` |

Kèm các chốt "đừng sửa quá tay": kịch bản `ready` + đủ ảnh **vẫn dựng được**;
hai trang dùng `Stepper` cũ **giữ nguyên 76px và luật nhảy cũ**; H3/H4 **vẫn
ẩn khỏi thanh bên**.

---

## Giới hạn còn lại

- **Chưa chạy trên desktop app thật.** Spec đòi mở ba trang trong app Windows
  rồi đi H2→H3→H4 và ngược lại. Tôi chạy được ở chế độ offscreen trên Linux,
  **không thay thế được** lượt đó. Chủ dự án cần xác nhận trên máy thật.
- Ngoài phạm vi (giữ nguyên theo spec): thêm H3/H4 vào thanh bên; H4d/provider
  `image`/`image.scene.stage`; D1 khớp giọng thật; RS-16.
- Chốt chống trùng số mini-spec vẫn **chưa có** — xem phần audit.

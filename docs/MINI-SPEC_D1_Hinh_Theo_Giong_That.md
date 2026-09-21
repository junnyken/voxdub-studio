# Mini-Spec D1 — Hình chạy theo GIỌNG ĐỌC THẬT, không theo ước lượng

**Ngày:** 15/09/2026. **Chi phí người dùng: 0 Vox** (thuần ffmpeg trên máy).

---

## 1. Khoảng hở

`dung_du_an()` dựng `storyboard_video.mp4` với thời lượng **ước lượng** từ
`uoc_luong_giay_doc()` (0,39 × số câu + 0,504 × số âm tiết). Sau đó người dùng
đọc bằng VieNeu trong Trình chỉnh sửa, và giọng thật **không bằng** ước lượng —
pilot H4 đo được **19,30 s so với 20,31 s**, lệch ~5%.

Hợp đồng H4c-1 chỉ bảo đảm video khớp **bản chữ**, nên không có gì sai theo
đúng chữ nghĩa. Nhưng thứ người xem gặp thì khác.

### Vì sao 5% không phải "trong ngưỡng nên bỏ qua"

Lệch ấy **cộng dồn theo đoạn**, không phải một sai số ở cuối. `apply_soft_timing`
dồn phần trễ vào khoảng lặng — mà kịch bản storyboard thì các đoạn **nối liền
nhau, không có khoảng lặng nào để dồn**. Nên mỗi đoạn đọc lâu hơn ước lượng sẽ
đẩy toàn bộ phần sau **trễ thêm**, trong khi hình vẫn đổi theo mốc ước lượng cũ.

Càng về cuối hình càng chạy trước lời. Đúng triệu chứng mà chú thích cổng thời
lượng trong `dung_du_an` đã mô tả cho một lỗi khác: *"hình đổi sớm dần, lệch hẳn
về cuối"*.

### Hướng sửa: đổi HÌNH, đừng ép GIỌNG

Engine hiện có `timing_max_atempo` (mặc định 1,1) — nó **nén giọng đọc** cho vừa
chỗ. Với video thường thì đúng: hình là thứ quay được, không co giãn tuỳ ý.

Với slideshow thì **ngược lại mới đúng**: ảnh tĩnh **không có nhịp riêng**, giữ
2,0 s hay 2,3 s đều không ai nhận ra. Ép giọng đọc nhanh lên để vừa một tấm ảnh
tĩnh là hy sinh đúng thứ người xem nghe được, để bảo toàn đúng thứ họ không để ý.

## 2. Việc may mắn đã có sẵn

`apply_soft_timing()` **đã tính sẵn timeline thật**: nó cập nhật `start`/`end`
của từng câu theo **vị trí đặt thật** sau khi đo clip. Nên D1 không phải tự đo
lại gì — chỉ cần dựng lại hình theo đúng mốc ấy.

Và bẫy `xfade` (chồng cảnh ăn mất `giay_chuyen` mỗi lần chuyển) đã được xử lý
sẵn trong `ghep_anh_nguoi_dung` + cổng đo lại của H4c-1. Dùng lại y nguyên.

## 3. Thiết kế

1. **`dung_du_an` ghi lại đường dẫn ảnh từng đoạn** vào `nguon_kich_ban.json`.
   Trước đây nó dựng video rồi **vứt danh sách ảnh đi**, nên về sau không còn
   gì để dựng lại.
2. **`dung_lai_video_theo_giong(work_dir, segments)`** — mốc lấy từ `start` của
   từng câu (đã là mốc thật sau bước đặt lại thời điểm):
   `giây[i] = start[i+1] − start[i]`, đoạn cuối lấy hết phần còn lại
   **của TỆP TIẾNG, không phải của câu cuối** — xem mục 7.
3. **Nối vào `editor.rebuild_output`**, sau bước đặt lại thời điểm và trước
   `merge_video`.

## 4. Chỗ nguy hiểm nhất: đây là đường xuất của MỌI dự án

`rebuild_output` là đường xuất chung — dự án lồng tiếng thường cũng đi qua đây.
Một bước "dựng lại video" chạy nhầm ở đó sẽ **thay video gốc của người ta** bằng
một slideshow. Nên mọi điều kiện dưới đây phải đúng thì mới động vào, sai một
cái là **bỏ qua im lặng, giữ nguyên hành vi cũ**:

| Điều kiện | Vì sao |
|---|---|
| Có `nguon_kich_ban.json` kèm `anh_moi_doan` | Chỉ dự án dựng từ kịch bản mới có |
| Số ảnh == số câu | Người dùng sửa kịch bản thêm/bớt câu ⇒ không còn ghép đúng |
| Mọi tệp ảnh còn tồn tại | Ảnh là tệp của người dùng, họ có thể đã xoá/đổi chỗ |
| Video đang ghép đúng là `storyboard_video.mp4` | Có `slowed_video.mp4` nghĩa là đã làm chậm — đừng chồng lên |
| Mọi khoảng `start[i+1] − start[i]` > 0 | Câu chồng nhau thì không lát kín được dòng thời gian |

Và **cổng thời lượng H4c-1 vẫn chạy trên video mới** — dựng lại mà lệch thì
hỏng to tiếng, không âm thầm ghi đè.

## 5. Chốt "đừng sửa quá tay"

Ước lượng **đã đúng sẵn** (mọi mốc lệch dưới `NGUONG_DANG_DUNG_LAI_S`) thì
**không dựng lại**. Dựng lại tốn hàng chục giây ffmpeg, và thay một tệp đang
đúng bằng một tệp cũng đúng là rủi ro không đổi lại được gì.

## 6. Cố ý KHÔNG làm

- **Không đụng `timing_max_atempo`.** Nó vẫn đúng cho dự án lồng tiếng thường.
- **Không tự đọc lại** bất cứ câu nào — D1 là 0 Vox.
- **Không đổi hợp đồng H4c-1.** Video vẫn phải khớp dòng thời gian, chỉ là dòng
  thời gian nay lấy từ giọng thật thay vì ước lượng.

---

## 7. Vá 21/09 — "phần còn lại" là của TỆP TIẾNG, không phải của câu cuối

Bản vá 15/09 (`5af86a3`) lấy `end` của câu cuối làm cuối dòng thời gian
(`cuối = end[-1]`, tổng cả video = `end[-1] − start[0]`). **Cuối câu cuối
không phải cuối dòng thời gian.**

Mọi cảnh khác dài tới `start` của câu KẾ, nên chúng ôm trọn khoảng lặng nằm
trong cảnh. Cảnh cuối không có câu kế để dựa vào, và `apply_soft_timing` thì
kéo `end` về đúng chỗ **tiếng nói tắt** — nên cảnh cuối chỉ còn đúng độ dài
clip giọng, còn bao nhiêu tiếng chạy sau đó thì mất hình.

Đo được (pilot `scripts/pilot_h4_cuc_bo.py`, 21/09):

| Thứ | Trước vá 21/09 | Sau |
|---|---|---|
| `storyboard_video.mp4` dựng lại | 16,33 s | 20,30 s |
| `data/audio_vi_full.wav` | 20,31 s | 20,31 s |
| Luồng video trong `dubbed_video.mp4` | 16,33 s | 20,30 s |
| Đuôi video **không có khung hình nào** | **3,98 s** | 0,01 s (dưới một khung) |

`merge_video` **không có `-shortest`**, nên tệp xuất ra luôn dài bằng TIẾNG:
hình ngắn hơn không bị cắt tiếng, nó để lại một cái đuôi đứng hình/đen. Ở
pilot, ảnh CTA tắt ngay khi đọc xong thay vì giữ tới hết — đúng thứ D1 sinh ra
để dọn, chỉ là ở cuối video thay vì giữa.

**Ba cảnh đầu vốn đã ĐÚNG** (đo bằng màu khung hình so với `silencedetect`:
cảnh đổi tại 0 / 6,44 / 13,88 khớp tiếng nói ở 0–3,03 / 6,56–9,81 /
14,0–16,21). Đây là lỗi ở ĐUÔI, không phải lệch nhịp — đừng đọc nhầm thành D1
hỏng cả gói.

**Sửa**: `_moc_that(segments, dai_tieng)` — cảnh cuối kéo tới
`max(end[-1], dai_tieng)`. `rebuild_output` **đo tệp tiếng vừa trộn xong**
(`wav_duration_s(merged_audio_path)`) rồi đưa sang, cố ý KHÔNG dùng lại biến
`total_duration`: con số đó là *ý định* lúc gọi trộn, thứ sắp ghép vào video là
*tệp*. `dai_tieng` chỉ được **kéo dài**, không bao giờ rút — một số đo hụt mà
rút hình lại thì cắt mất chữ cuối, hỏng nặng hơn hẳn cái đang sửa.

### Vì sao KHÔNG sửa ở đầu kia (cắt bớt tiếng)

`editor.rebuild_output:812` tính `total_duration = max(end) + 1.0` **trước**
bước đặt lại thời điểm, nên tệp tiếng dài theo ƯỚC LƯỢNG (19,31 + 1,0) trong
khi các câu đã lùi `end` về giọng thật — đó là nguồn của ~4 giây im lặng ở
cuối. Cắt nó đi là đổi hành vi **đường xuất của MỌI dự án**: với dự án lồng
tiếng video quay thật, tiếng BẮT BUỘC phủ hết video nguồn, rút ngắn là đổi
video thành đoạn cụt tiếng. Ngoài phạm vi D1 — ghi lại ở đây để ai đụng tới
`total_duration` sau này biết nó đang gánh hai vai.

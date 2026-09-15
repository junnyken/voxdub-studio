# VoxDub Studio — Trạng thái dự án, 15/09/2026

Tài liệu tự chứa, dùng làm ngữ cảnh lập kế hoạch đợt tiếp theo. Mọi con số
dưới đây đo tại 15/09/2026 ~06:40 UTC, không lấy từ trí nhớ.

---

## 1. Chốt nhanh

Phase H (thương hiệu → kịch bản → video) **đã chạy thông từ đầu tới cuối trong
một lượt pilot thật**. Toàn bộ 22 mục rà soát `RS-1…RS-22` và 7 mục `B1…B7` đã
đóng. Phát hiện lớn nhất của pilot — H3 viết kịch bản dài **gấp 5 lần** nhịp mà
H2 học được — đã đóng bằng H6 và **đo lại còn ≈1,0×**.

Vấn đề nghiêm trọng nhất hiện nay **không nằm ở tính năng mà ở đường ra
production**: một lượt deploy hỏng thì không bao giờ được thử lại, và commit kế
tiếp sẽ kết luận "không có gì để deploy". Prod tụt lại **21 giờ** trong khi CI
xanh toàn bộ. Xem §4.1 — đây là việc đáng ưu tiên số một.

---

## 2. Phiên bản và môi trường

| Thành phần | Trạng thái đo được |
|---|---|
| Kho mã `main` | `6baf2f2` — cây làm việc sạch, CI xanh |
| Bản phát hành Windows | **3.17.18** (RS-16 và bản vá nút **chưa** có trong bản này) |
| `voxdub-app` (prod) | ✅ `6baf2f2d46ca` — vừa đưa lên 15/09 06:35 UTC |
| `voxdub-dub-worker` (prod) | ⚠️ **đang tụt lại** — nhánh deploy ở `6baf2f2`, bản đang chạy sinh từ `bd62f3f` |
| Cổng Vibe Host | ✅ đã sống lại (hôm qua 404 toàn bộ) |
| pytest | 2.931 test (2.927 đạt, 4 bỏ qua) |
| `control_server` | 720 test (719 đạt, 1 bỏ qua) |
| `website` | 74 test / 8 tệp, đạt hết |

**Lệch quan trọng**: bản Windows người dùng đang cầm là 3.17.18, **chưa mang**
RS-16 (cổng tuân thủ ảnh AI) và bản vá nút bị cắt chữ. Hai thứ đó đã nằm trên
`main` nhưng **chưa dựng bản phát hành**.

---

## 3. Tính năng hiện có

### 3.1 Lõi lồng tiếng (đã ổn định từ trước Phase H)

Tải video (YouTube/TikTok/Douyin/Bilibili + tệp máy) → tách tiếng (Demucs) →
nhận dạng (Whisper / Paraformer) → dịch → đọc tiếng Việt (VieNeu ONNX) → ghép.
Mỗi engine nặng chạy trong venv con riêng qua tiến trình con. Mọi kết quả trung
gian ghi ra đĩa nên chạy lại được từ giữa chừng.

### 3.2 Phase H — dây chuyền làm video thương hiệu

| Bước | Việc | Chi phí | Trạng thái |
|---|---|---|---|
| **H1** | Hồ sơ thương hiệu (giọng điệu, điều không được nói) | 0 Vox | Chạy được |
| **H2** | Học "nhịp kể chuyện" từ một video tham khảo | 8 Vox | Chạy được, đã pilot thật |
| **H2a/b/c** | Đọc chữ trên hình (có dấu tiếng Việt) + dấu vân tay bằng chứng | 56 Vox (tuỳ chọn) | Chạy được |
| **H3** | Viết kịch bản riêng cho thương hiệu + 2 lớp chặn sao chép | 12 Vox | Chạy được, **H6 vừa siết nhịp** |
| **H4a–c** | Dựng dòng thời gian + ghép ảnh thành video theo đúng thời lượng từng đoạn | 0 Vox | Chạy được |
| **H4d** | Sinh ảnh minh hoạ bằng AI | 33 Vox | **Đang khoá ở máy chủ** (`image.scene.stage = off`) |
| **H5** | Dải điều hướng H2 → H3 → H4 | — | Chạy được |
| **H6** | Ngân sách từ theo thời lượng nguồn | — | Chạy được, đã đo |

### 3.3 Các lớp chặn đang hoạt động

- **Chặn sao chép nguyên văn** (H3): kịch bản trùng câu chữ video nguồn hoặc
  chạm cụm thương hiệu tự cấm thì bị chặn, không đi tiếp được sang H4.
- **Cổng thời lượng** (H4c-1): đo LẠI video vừa ghép, lệch quá ngưỡng thì hỏng.
- **Cổng tuân thủ ảnh AI** (RS-16, **mới 14/09**): ảnh do AI vẽ phải qua đủ ba
  phép kiểm — đã kiểm, đã đóng nhãn AI, và **băm tệp còn khớp** — mới được vào
  video. Đặt ở tầng dựng video chứ không ở nút bấm, nên không lối gọi nào đi
  vòng qua được.
- **Cổng deploy** (D3): prod chỉ nhận SHA đã qua đủ phép kiểm của chính nó, và
  dịch vụ phải **tự khai** SHA ở `/health` mới coi là lên thật.

---

## 4. Vấn đề còn lại

### 4.1 🔴 D5 (MỚI, chưa sửa) — deploy hỏng thì không bao giờ được thử lại

**Đây là vấn đề nghiêm trọng nhất hiện nay.**

Chuỗi đã xảy ra thật ngày 14/09:

1. `df980b2` (bản vá rò rỉ CSDL) qua hết phép kiểm, sinh nhánh deploy, gọi
   deploy → **cổng Vibe Host 404** (sự cố hạ tầng) → job đỏ. Prod giữ bản cũ.
2. `6baf2f2` (chỉ sửa tài liệu) chạy CI. Bước quyết định "có cần deploy không"
   so **nhánh deploy mới với nhánh deploy lần trước** — hai bản giống nhau, nên
   kết luận `app=0`, **bỏ qua deploy**, và job báo **thành công**.
3. Kết quả: bản vá nằm sẵn trên nhánh deploy, **CI xanh hoàn toàn**, prod chạy
   mã cũ **21 giờ** mà không có một tín hiệu đỏ nào.

**Gốc rễ**: phép so dùng *bản dựng lần trước* làm mốc, tức ngầm giả định lần
trước đã lên prod thật. Một lượt deploy hỏng phá vỡ giả định đó và không chốt
nào bắt được:

| Chốt đang có | Nó so cái gì | Vì sao không cứu được |
|---|---|---|
| `--sha-nhanh` | đầu nhánh deploy trên remote | chỉ chạy **khi có deploy** |
| `--sha-nguon` | SHA prod tự khai ở `/health` | chỉ chạy **khi có deploy** |
| `deploy-branch-drift` | nhánh deploy ↔ `main` | đúng, và vẫn đúng khi prod tụt lại |
| `app == 1` | bản dựng này ↔ bản dựng trước | mù với việc prod đang chạy gì |

**Không chốt nào so PROD với MAIN.** Đó là khoảng hở.

**Đã xử lý tạm**: 15/09 đã đưa `voxdub-app` lên `6baf2f2` bằng tay qua cổng
Vibe Host, và xác minh bằng chính `/health` (`commit = 6baf2f2d46ca`, uptime
reset). **Nhưng gốc rễ chưa sửa** — lần hạ tầng chập tiếp theo sẽ lặp lại y hệt.

**Hướng sửa đề xuất**: thêm một chốt so `/health.commit` của prod với `main`,
chạy **mỗi lượt CI** (không chỉ khi có deploy) và chạy định kỳ. Lệch thì hoặc
tự deploy lại, hoặc báo đỏ — nhưng phải **nhìn thấy**.

### 4.2 🔴 `voxdub-dub-worker` đang tụt lại, và không cách nào tự kiểm

Worker mang cả `du_an_tu_kich_ban.py` (RS-16) lẫn `doc_chu_may_chu.py` (RS-14)
nhưng bản đang chạy sinh từ `bd62f3f`, trong khi nhánh deploy đã ở `6baf2f2`.
Đúng cùng một cơ chế §4.1.

Tệ hơn: `/health` của worker trả chuỗi `"ok"` thuần, **không khai SHA**, nên
không ai kiểm được nó đang chạy gì — kể cả chốt `--sha-nguon` cũng phải bỏ
trống cho worker. Cần cho worker khai SHA giống app.

**Cần thao tác**: deploy lại worker (chưa làm — cần chủ dự án duyệt).

### 4.3 🟡 Rò rỉ chunk trong CSDL — đã vá phần chính, còn hai lỗ nhỏ

Upload đứt giữa chừng từng để lại "chunk mồ côi" chiếm chỗ vĩnh viễn trong
MongoDB. Nguyên nhân: driver gửi lệnh ghi bất đồng bộ và chỉ kiểm "đã huỷ chưa"
**trước khi gửi**, nên lệnh đã bay thì lượt dọn không tóm được.

Đã vá 14/09 (chờ mọi lệnh ghi hạ cánh xong rồi mới dọn) và **đã lên prod**.
Hai phần còn hở, đã ghi trong mã:

- Đường lùi (khi driver đổi) vẫn là **phỏng đoán theo thời gian** — chunk hạ
  cánh muộn hơn ~150 ms vẫn lọt.
- `stats().orphanChunks` mới **đếm** chunk mồ côi, **chưa ai dọn**. Cần một
  lượt quét định kỳ.

Ngoài ra bản vá dựa vào một trường **nội bộ** của driver `mongodb`; đã có test
đỏ thẳng nếu bản driver sau bỏ trường đó.

### 4.4 🟡 D1 — video khớp bản chữ, chưa khớp giọng đọc thật

Hợp đồng hiện tại chỉ bảo đảm video khớp **bản chữ**. Đo pilot: slideshow
19,30 s vs video cuối 20,31 s — giọng thật dài hơn ước lượng ~5%, nằm trong
±15% đã cam kết nên chưa hỏng. Muốn khớp thật thì phải lấy thời lượng sau khi
đọc xong rồi ghép lại.

### 4.5 🟡 D2 — định giá chưa theo chi phí thật

H3 tính **12 Vox phẳng theo số đoạn**, trong khi kịch bản 40 đoạn tốn hơn hẳn 5
đoạn. Máy chủ đã ghi đủ token vào/ra mỗi lượt. **Cần 10–20 lượt thật** rồi mới
viết được mini-spec định giá — chưa đủ dữ liệu, đừng sửa sớm.

### 4.6 🟡 D4 — siết khoá GitHub (chủ dự án đã hoãn)

Khoá cũ chưa thu hồi, hai remote còn nhúng khoá trong URL. **Đã hoãn có chủ
đích**, ghi lại để không bị quên.

### 4.7 ⚪ Một test Node đỏ chập chờn — đã vá, cần theo dõi

Đỏ khoảng 1/12 lượt CI, và **70 lượt chạy lại ở máy cục bộ không tái hiện nổi
lần nào** (cả khi rảnh lẫn khi ép tải). Đã vá bằng cách dựng phép tái hiện tất
định thay vì chờ may. Theo dõi vài lượt CI nữa mới nên coi là đóng hẳn.

---

## 5. Việc của con người, không phải việc lập trình

1. **Deploy lại `voxdub-dub-worker`** — cần duyệt (xem §4.2).
2. **Dựng bản Windows mới** mang RS-16 + bản vá nút. Cơ chế: đẩy thẻ `v*` là CI
   tự dựng và tạo bản phát hành.
3. **Thêm vân tay máy** vào `image.scene.calibration.devices` để mở H4d. Nay đã
   **hết vướng** vì RS-16 xong. Sau đó chạy 20–30 ảnh thật, soi tay từng phán
   quyết theo chốt ba nấc đã quy định.
4. **Cấu hình hai dòng nhà cung cấp** `assist` và `image` trên trang quản trị.

---

## 6. Số đo còn nợ

| Việc | Vì sao cần | Ai làm |
|---|---|---|
| Số liệu C.4 (worker OCR) | Xác nhận bản 3.17.18 giải nén sạch thì chạy worker đời mới. Phải giải nén vào thư mục **rỗng** — giải đè lên thư mục cũ **không** ghi đè `_internal` | Chủ dự án |
| H4d: 20–30 ảnh thật | Chốt ba nấc trước khi mở `image.scene.stage` | Chủ dự án, sau khi ra bản mới |
| 10–20 lượt H3 thật | Dữ liệu token cho D2 | Tích luỹ dần |

---

## 7. Đề xuất thứ tự cho đợt tới

1. **D5** — chốt so prod với main (§4.1). Đây là thứ duy nhất đang khiến một sự
   cố hạ tầng biến thành "prod tụt lại mà không ai biết".
2. **Worker khai SHA ở `/health`** + deploy lại worker (§4.2). Đi liền với D5 vì
   không có nó thì D5 không phủ được worker.
3. **Dựng bản Windows** mang RS-16, rồi mở H4d và chạy chốt ba nấc.
4. **Quét dọn chunk mồ côi định kỳ** (§4.3) — nhỏ, đóng nốt phần còn hở.
5. **D1** rồi **D2** — D2 phải chờ đủ dữ liệu thật.

---

## 8. Nguyên tắc dự án đang áp dụng (giữ nguyên cho đợt sau)

- **Rà soát trước khi dựng.** Tiền đề sai thì dừng và báo, đừng dựng tiếp.
- **Chứng minh test ĐỎ trước khi tin nó.** Gỡ từng chốt phải cho tập đỏ khác
  nhau; trùng nhau nghĩa là có chốt thừa.
- **Không trình bày suy luận như số đo.** Chạy lại nhiều lượt không tái hiện
  được thì phải nói thẳng là chưa chứng minh được, không lấy "hết đỏ" làm bằng
  chứng.
- **Chạy đủ bộ test, ở môi trường khó nhất có sẵn**, không chạy chọn lọc.
- **Đừng sửa quá tay** — mỗi lát đều kèm chốt "trường hợp bình thường phải im
  lặng".

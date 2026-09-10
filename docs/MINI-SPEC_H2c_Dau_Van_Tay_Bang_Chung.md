# MINI-SPEC H2c — Dấu vân tay bằng chứng (dọn đường cho H3)

**Ngày**: 10/09/2026 · **Trạng thái**: đã xong, chờ H3 dùng
**Sinh ra từ**: audit spec H3 phát hiện một tiền đề sai so với mã thật.

## 1. Vì sao có mini-spec này

Spec H3 (viết lại kịch bản cho brand) dựng toàn bộ bước kiểm nguyên gốc lên
giả định *"evidence nguồn (transcript + OCR **đã lưu** ở H2)"*. Đối chiếu mã
thật thì giả định đó **sai**:

- `models/FlowBlueprint.js` không có trường nào chứa transcript/OCR thô — chỉ
  có `evidenceSummary` (mô tả *tình trạng* bằng chữ) và `evidenceStatus`
  (enum, nằm trong từng beat).
- `routes/flow-blueprints.js` ghi thẳng: *"KHÔNG lưu transcript/OCR thô — chỉ
  dùng TẠM để gọi mô hình rồi bỏ"*, đúng Constraint 2/Scope B của H2.

Tức là H3 **không có gì để so sánh**. Đây đúng ca mà mục A.6 của chính spec
H3 yêu cầu: dừng và báo gap thay vì tự mở rộng phạm vi.

## 2. Ba đường và lý do chọn đường thứ ba

| Cách | Cái giá |
|---|---|
| a. H2 lưu evidence thô | Đảo ngược Scope B. Máy chủ trở thành kho câu chữ nguyên văn của video người khác — trong khi H3 chính là mảnh rủi ro pháp lý nhất Phase H |
| b. H3 tải lại video, trích lại lúc kiểm | Server không lưu video; `sourceReference` chỉ là URL hoặc **tên file**. `sourceType: "file"` gần như không tái tạo được; URL thì video có thể đã bị xoá |
| **c. Lưu dấu vân tay một chiều** | Giữ được lời hứa "không lưu câu chữ nguồn" và vẫn phát hiện trùng — **chủ dự án chọn 10/09** |

**Đánh đổi của (c), nói thẳng từ đầu**: không giữ chữ nghĩa là **không trưng
ra được cụm gốc** bên nguồn. H3 chỉ chỉ được đúng cụm trong kịch bản MỚI bị
chặn. Điều này **mâu thuẫn với mục Desktop UI của spec H3** (yêu cầu hiện
side-by-side cụm gốc) — phần đó của H3 phải sửa lại theo, không phải lỗi
triển khai.

Thứ người dùng cần để sửa vẫn còn nguyên: họ biết chính xác câu nào **trong
kịch bản của họ** bị chặn.

## 3. Thiết kế

`control_server/src/services/dau-van-tay.service.js`:

- `taoDauVanTay(cacDong)` — băm SHA-256 từng cụm từ, cắt còn 12 ký tự hex.
  - Cụm **6 từ** cho dòng dài — bằng đúng `NGUONG_TU_LIEN_TIEP` của gate H2.
    Hai bộ chặn lệch ngưỡng thì sẽ có ca H2 bắt mà H3 tha.
  - Dòng **2–5 từ** (caption/hook/CTA kiểu `STOP SCROLLING`) băm cả dòng kèm
    số từ; bên kiểm sinh mọi cửa sổ cùng độ dài — tương đương phép "chứa
    nguyên vẹn" của gate H2 ở mức TỪ.
  - Dòng **1 từ bị bỏ có chủ đích**: một từ đơn trùng nhau là chuyện bình
    thường của ngôn ngữ, không phải dấu hiệu sao chép.
- `timTrungLap(vanBan, dvt)` → `{trung, cum, kieu, kiemDuoc}`. `cum` là cụm
  trong **văn bản mới**.
- `locBangChungDaXacNhan(cacMuc)` — bỏ dòng OCR `status: "unconfirmed"`
  (chữ máy đọc mà chính nó không chắc; băm vào rồi H3 sẽ chặn kịch bản vì
  trùng với một câu **có thể vốn đã đọc sai**). Transcript không mang
  `status` nên luôn được giữ — đúng như client gửi lên.

**Muối riêng từng bản ghi**: cùng một nguồn tạo ra băm khác nhau ở hai bản
ghi, nên không dò chéo được bằng kho câu có sẵn từ bên ngoài.

**Chuẩn hoá gom về MỘT nguồn sự thật**: `chuanHoaSoKhop` chuyển từ
`prompts/assist.js` sang service này, `assist.js` nhập lại. Giữ hai bản song
song là bảo đảm chúng trôi lệch nhau sau vài lần sửa, và lúc đó không ai biết
bộ chặn nào mới là bộ đang bảo vệ mình.

### Ba trạng thái phải tách bạch

`kiemDuoc: false` (**chưa kiểm được**) KHÁC HẲN `trung: false` (**đã kiểm,
không trùng**). Không có dấu vân tay, hoặc dấu vân tay khác phiên bản thuật
toán ⇒ `kiemDuoc: false`. H3 phải dịch cái đó thành `unconfirmed`, không phải
`clear` — đúng luật "không kiểm được thì coi như không dùng được".

Chạm trần số băm thì **đánh dấu `dayTran`, không cắt âm thầm**: cắt mà không
nói ra là vùng phủ thủng, và một câu chép nguyên văn rơi đúng phần bị cắt sẽ
lọt qua trong im lặng.

## 4. Tính chất bảo mật — KHÔNG được nói quá

Băm có muối riêng bản ghi thì:

- **KHÔNG** đọc ngược ra văn bản ⇒ máy chủ không còn là kho copy-ready;
- **KHÔNG** dò được bằng kho câu có sẵn từ ngoài (muối chặn bảng tra sẵn).

**NHƯNG** người đã có CẢ cơ sở dữ liệu (nên có luôn muối) LẪN video gốc thì
vẫn xác nhận được "video này ứng với bản ghi kia". Đây là chống **tích trữ
nguyên văn**, không phải chống một kẻ tấn công có chủ đích. Đừng bán nó như
thứ thứ hai.

## 5. Số đo thật (đo trước, chốt trần sau)

Đo bằng văn bản đa dạng thật (từ vựng 3.000 từ, nguồn ngẫu nhiên thật —
lượt đo đầu dùng bộ sinh tự viết bị mất chính xác số học nên cho số thấp giả,
đã làm lại):

| Ca | Số băm | Dung lượng | Dựng | Kiểm 20 beat |
|---|---|---|---|---|
| Thường ngày (40 dòng × 18 từ) | 520 | 8 KB | 7 ms | 4 ms |
| Nhiều (150 × 18) | 1.950 | 29 KB | 16 ms | 6 ms |
| Kịch trần schema (800 × 25) | 16.000 | 234 KB | 72 ms | 37 ms |
| Cực đoan (800 × 80) | 20.000 (chạm trần) | 293 KB | 82 ms | 73 ms |

Trần chốt ở **20.000 băm** (~293 KB) từ số đo trên, không phải số đoán.

**Va chạm giả**: 12 ký tự hex = 48 bit. Với 20.000 băm lưu sẵn và 300 cụm đem
đi hỏi, kỳ vọng ≈ 20000×300/2^48 ≈ **2×10⁻⁸** — nhỏ hơn nhiều bậc so với mọi
nguồn sai khác trong chuỗi này.

**Bỏ khỏi truy vấn danh sách**: `GET /v1/flow-blueprints` thêm
`.select('-evidenceFingerprint')` — kéo hàng chục nghìn chuỗi băm về cho mỗi
lần mở trang là phí băng thông vô ích, mà `view()` không dùng tới.

## 6. Tests

**13 test đơn vị** (`tests/dau-van-tay.test.js`) — bắt câu chép gần nguyên
văn; bắt caption ngắn bị bê nguyên; **KHÔNG báo nhầm** với 3 câu diễn đạt lại
hợp lệ viết tay (báo nhầm thì người dùng học cách bỏ qua cảnh báo, hỏng cả bộ
chặn); dấu câu/chữ hoa không giúp lách; muối khác nhau giữa hai bản ghi nhưng
vẫn bắt được trong phạm vi từng bản ghi; **thiếu/khác phiên bản ⇒ "chưa kiểm
được", tuyệt đối không phải "sạch"**; không có bằng chứng ⇒ `null` chứ không
phải dấu vân tay rỗng; chạm trần thì đánh dấu; chuẩn hoá dùng chung với gate
H2.

Test quan trọng nhất: **dấu vân tay không chứa chữ nào của nguồn**. Test này
đỏ nghĩa là máy chủ đã quay lại thành kho câu chữ nguyên văn — mất đúng thứ
Scope B của H2 bảo vệ.

**2 test tầng route** (`tests/flow-blueprints-route.test.js`) — bản ghi thật
có lưu vân tay, **không lộ ra API**, và không còn nguyên văn trong cả bản
ghi; bằng chứng OCR chưa xác nhận không vào vân tay.

Toàn bộ Node: **595 passed, 0 fail** (từ 580).

## 7. Remaining Limits / Follow-ups

- **Chưa có lượt H2 THẬT nào chạy end-to-end trên prod**, nên chưa có
  `FlowBlueprint` thật nào mang dấu vân tay. Cần chạy một lượt thật trước khi
  H3 bắt đầu, nếu không mục live verification của H3 sẽ bị làm cho có.
- **Ngưỡng 6 từ là kế thừa từ gate H2, chưa hiệu chỉnh bằng output mô hình
  thật.** Ba ca paraphrase trong test là **viết tay**, không phải do mô hình
  sinh. H3 phải đo lại bằng kịch bản mô hình thật sinh ra rồi mới chốt, đúng
  nguyên tắc "đo trước, đặt ngưỡng sau".
- **Bản ghi FlowBlueprint tạo TRƯỚC 10/09 không có dấu vân tay** ⇒ H3 phải
  coi chúng là `unconfirmed`, không phải `clear`. Không có bước vá ngược vì
  evidence gốc đã bỏ đi từ lâu, không dựng lại được.
- Mục **Desktop UI của spec H3 phải sửa**: không hiện được side-by-side cụm
  gốc (mục 2 ở trên).
- Chưa xử lý: xoá FlowBlueprint sau khi H3 đã tạo BrandScript tham chiếu tới
  nó (H1/H2 đều có `DELETE`) — thuộc phạm vi H3, ghi lại ở đây để không quên.

# MINI-SPEC H2b — Đọc chữ overlay CÓ DẤU tiếng Việt

**Ngày**: 09/09/2026 · **Trạng thái**: đã xong, đã kiểm chứng thật
**Sinh ra từ**: khiếu nại thật của chủ dự án — *"tại sao nó lại dịch ra tiếng
Việt mà không có dấu, tôi cần nó phải có dấu"*.

## 1. Audit Before Build — đo trước, kết luận sau

### 1.1 Không phải lỗi đường DỊCH

Nghi can đầu tiên là bộ dịch. Loại trừ bằng cách đọc mã, không đoán:

- `autodub/text/translate_local_worker.py` dịch sang `vie_Latn` (NLLB) — đúng.
- Hàm `_canh_bao_neu_cau_dai_khong_dau` ở đó cảnh báo về **dấu KẾT CÂU**
  (chấm/hỏi/chấm than), không phải dấu thanh. Tên hàm dễ đọc nhầm.
- Chỗ bỏ dấu duy nhất trong toàn repo (`character_profile.py`, `unicodedata`
  NFD) chỉ dùng đặt **tên file**, không đụng nội dung hiển thị.

### 1.2 Nguyên nhân thật: giới hạn TỪ ĐIỂN của model OCR

Model nhận dạng bundled trong `rapidocr-onnxruntime` là
`ch_PP-OCRv4_rec_infer.onnx`. Đọc từ điển đầu ra của chính nó
(`onnxruntime` → `get_modelmeta().custom_metadata_map['character']`):

> **6.623 ký tự, trong đó CHỈ 2 ký tự** thuộc bộ tiếng Việt có dấu (`É`, `Ó`).

Các chữ `ă â đ ê ô ơ ư` và mọi chữ mang dấu thanh **không nằm trong từ điển**
⇒ model không thể phát ra chúng, dù ảnh nét tới đâu, dù chỉnh tham số gì.
Đây không phải lỗi cấu hình và không có tham số nào sửa được.

Tái hiện (ảnh dựng bằng PIL, font DejaVu có dấu đầy đủ):

| Nguồn | RapidOCR đọc ra | Tin cậy |
|---|---|---|
| `Đăng ký kênh để không bỏ lỡ video mới!` | `Dang ky kenh de khong l` / `bo lo video 1` / `moi` | 0,84–0,99 |

**Tin cậy KHÔNG phải tín hiệu cho lỗi này** — model đọc sai một cách tự tin.
Đây là lý do H2a (08/09) đã ghi nhận hiện tượng nhưng không tự chữa được.

### 1.3 Bẫy đã đo trước để không mất công — đổi model OCR KHÔNG cứu được

| Từ điển thay thế | Thiếu bao nhiêu ký tự Việt (trên 134) |
|---|---|
| `latin_dict.txt` (PaddleOCR) | **102** |
| `ppocrv5_latin_dict.txt` | **90** |
| `vi_dict.txt` | 66 (đủ chữ thường, thiếu toàn bộ chữ HOA có dấu) |

PaddlePaddle **không** phát hành model nhận dạng tiếng Việt chính thức nào
trên HuggingFace (đã tra API, chỉ có en/latin/korean/eslav/th/arabic/…).

### 1.4 Đo các ứng viên trên KHUNG HÌNH THẬT

Bộ đo: 4 khung cắt từ `tap01_clip.mp4` (video nén thật, phụ đề cháy song
ngữ). **Đáp án do người đọc bằng mắt**, không lấy từ engine nào. Thước đo:
% ký tự của đáp án tìm lại được trong output (công bằng với phụ đề nhiều
dòng và với output có lẫn chữ tiếng Anh).

| Cách đọc | Đọc đúng | Dấu tiếng Việt | Tốc độ | Nặng thêm |
|---|---|---|---|---|
| RapidOCR (đang dùng) | 78,5% | **không có chữ nào** | 1,03 s/khung | 0 |
| RapidOCR cắt vùng + Tesseract `vie` | 86,5% | có, còn nhiễu | 1,94 s/khung | 1,5 MB |
| VietOCR (torch) | **không đo được** | — | — | 1,5 GB |
| Gemini 3.8 Flash, gộp 4 khung/lượt | **100%** | đúng hết | 0,74 s/khung | 0 |
| Gemini 3.1 Flash **Lite**, gộp | **100%** | đúng hết | 0,79 s/khung | 0 |

Ghi chú từng dòng:

- Con số 78,5% của RapidOCR **cao một cách giả tạo** — nó khớp phần chữ tiếng
  Anh và phần xương phụ âm, còn dấu thì trắng trơn.
- Tesseract **phải cắt vùng chữ trước** (dùng box của RapidOCR, phóng 3×):
  đọc cả khung hình thì 64% sai, cắt vùng còn 33% sai. Tinh chỉnh thêm 10
  biến thể tiền xử lý (xám/nhị phân/đảo/làm nét, phóng 3× và 4×) chỉ nhích
  lên **87,6%** — chạm trần, không đủ để tranh với 100%.
- **VietOCR bị loại vì cái giá, không phải vì chất lượng**: venv 1,5 GB
  (PyTorch), trọng số 151,8 MB tải từ `vocr.vn` (tên miền cá nhân, không phải
  CDN) — đo thật **60 KB/s ⇒ ~42 phút**, hai lần chạy thử đều hết giờ nên
  KHÔNG có số đo chất lượng. Package còn không kèm config (cũng tải từ
  `vocr.vn`) và ghim `gdown==4.4.0` dùng `pkg_resources` đã bị gỡ khỏi Python
  3.12 ⇒ vỡ ngay lúc import nếu không cài thêm `setuptools<81`. Quá mong manh
  cho một bản `.exe` gửi người dùng cuối.
- Gộp nhiều khung vào MỘT lượt gọi nhanh gấp ~4 lần gọi lẻ.

**Chốt của chủ dự án**: dùng `gemini-3.8-flash`, tắt thinking.

## 2. Thiết kế

### 2.1 Guardrail — không đụng vào tính năng làm mờ chữ

Dự án có **hai** đường dùng OCR, nhu cầu khác hẳn nhau:

| Hàm | Cần gì | Quyết định |
|---|---|---|
| `detect_text_regions()` | chữ **nằm ở đâu** (để làm mờ) | RapidOCR làm tốt, offline — **KHÔNG đổi một dòng nào** |
| `read_text_regions()` | chữ **nói gì** (H2 Flow Blueprint) | chỗ RapidOCR bất lực — thêm bộ đọc thay được |

### 2.2 Bộ đọc thay được, không ghim cứng engine

`read_text_regions(..., bo_doc=...)` với `BO_DOC_CUC_BO` (mặc định, giữ
nguyên hành vi cũ) và `BO_DOC_MAY_CHU`. **Mặc định KHÔNG đổi** — đổi mặc định
là đổi hành vi mọi nơi gọi cũ và bắt đầu tiêu Vox mà không ai yêu cầu; có test
canh riêng chuyện này (`test_mac_dinh_van_la_bo_doc_cuc_bo`).

Bước **dò vùng** vẫn do RapidOCR chạy tại máy trong cả hai ca. Máy chủ chỉ
làm đúng việc đọc nội dung.

### 2.3 KHÔNG gửi mọi khung hình lên máy chủ

Đây là quyết định thiết kế quan trọng nhất, vì nó là tiền thật. Lấy mẫu thích
ứng của H2 cho video 60 giây ra **~152 khung**; gửi hết là ~175.000 token mỗi
lượt phân tích.

Cách gỡ: RapidOCR đọc mất dấu **nhưng vẫn phân biệt tốt "khung này khác khung
trước"** (phần phụ âm/chữ số vẫn đúng). Nên:

1. RapidOCR (miễn phí, tại máy) chia các khung thành từng **đoạn** liên tiếp
   cùng chữ;
2. chỉ gửi **một khung đại diện** mỗi đoạn, tối đa 6 khung/lượt gọi;
3. áp bản đọc đúng cho **cả đoạn**, giữ nguyên mốc thời gian từng khung.

Chỉ gộp khung **liền kề**: một caption hiện, biến mất, rồi hiện lại là hai lần
hiện KHÁC nhau trên dòng thời gian — gộp làm một là bịa ra khoảng liên tục
không có thật (cùng lý lẽ với `flow_blueprint.gop_quan_sat_lien_tiep`).

### 2.4 Khuôn output riêng, giữ bằng được ánh xạ ảnh↔chữ

Tác vụ dùng `outputSchema`/`parseResult` riêng (đường đã có sẵn từ H2), KHÔNG
dùng khuôn chung `{results:[{value,reason}]}` vì khuôn chung **lọc bỏ mục có
`value` rỗng** — mà "khung này không có chữ" là câu trả lời hợp lệ và thường
gặp. Lọc mất nó là lệch toàn bộ ánh xạ của mọi khung phía sau, **không có tín
hiệu nào để phát hiện**.

Chống lệch bằng hai lớp: schema ép mô hình gắn số thứ tự ảnh vào TỪNG mục
(không tin thứ tự mảng), và `parseDocChuResult` luôn trả đủ `soAnh` mục theo
đúng thứ tự 1..soAnh (ảnh mô hình bỏ sót → `dong: []`).

`parseResult` trả đúng khuôn `{results:[...]}` nên route `/v1/ai/assist` dùng
lại được **y nguyên, không sửa một dòng nào** (route đọc `result.results` như
một mảng đục). Có test chốt lại chuyện này.

### 2.5 Hỏng thì lui, không giết cả lượt phân tích

Chưa cấu hình máy chủ / mạng lỗi / hết Vox ⇒ **trả về nguyên bản đọc cục bộ**,
không ném. Chữ mất dấu vẫn dùng được cho việc phân tích cấu trúc; ném lỗi ở
đây là giết cả lượt phân tích chỉ vì phần làm-cho-tốt-hơn không chạy được.
Chỗ hỏng vẫn **lộ ra trong Nhật ký**, không nuốt im lặng.

### 2.6 Không bịa điểm tin cậy

Mô hình nhìn ảnh không chấm điểm tin cậy. `QuanSatChu.confidence` đổi thành
`float | None`, bộ đọc máy chủ điền `None`. Điền `1.0` cho đủ chỗ thì trông y
hệt một điểm đo thật và mọi thứ đọc trường này sau đó đều tin nhầm.

## 3. Changed Files

| Tệp | Thay đổi |
|---|---|
| `control_server/src/prompts/assist.js` | tác vụ `doc_chu_khung_hinh` + `docChuOutputSchema()` + `parseDocChuResult()` |
| `control_server/src/services/config.service.js` | giá mặc định `credit.cost.assist.doc_chu_khung_hinh` = 8 Vox/lượt (tối đa 6 khung) |
| `autodub/media/text_regions.py` | `BO_DOC_*`, tham số `bo_doc`/`client`, `confidence: float \| None` |
| `autodub/media/doc_chu_may_chu.py` | **mới** — chia đoạn, chọn khung đại diện, gọi máy chủ, áp kết quả |
| `autodub/flow_blueprint.py` | chọn bộ đọc máy chủ khi `saas_client.is_configured()` |

## 4. Tests

**Node (15 mới, `doc-chu-khung-hinh.test.js`)** — trọng tâm là ánh xạ
ảnh↔chữ: khung mô hình bỏ sót vẫn có mặt với `dong` rỗng; thứ tự lộn xộn được
xếp lại đúng; mô hình lặp số ảnh thì giữ mục đầu (không nhân đôi chữ); số ảnh
ngoài khoảng bị bỏ; "mọi khung không có chữ" là câu trả lời HỢP LỆ chứ không
phải lỗi; output sai khuôn → `null` để cổng trợ lý báo lỗi thay vì trả rỗng âm
thầm. Thêm test đọc thẳng trần `images.maxItems` trong `routes/ai.js` để
`soAnhToiDa` không bao giờ vượt trần schema route, và test canh prompt vẫn
còn hai câu bắt buộc (*giữ dấu tiếng Việt*, *KHÔNG dịch*) — ai sửa prompt mà
bỏ chúng đi thì bug gốc quay lại y nguyên.

**Python (17 mới, `tests/test_doc_chu_may_chu.py`)** — chia đoạn (liền kề,
đổi chữ, cùng chữ nhưng cách quãng, nhiều vùng chữ trong một khung); chỉ gửi
khung đại diện; chia lô đúng trần 6; áp kết quả cho cả đoạn và giữ nguyên mốc
thời gian; không bịa điểm tin cậy; máy chủ hỏng/chưa cấu hình thì giữ bản cục
bộ và **không** đánh dấu là đọc từ máy chủ; đoạn không có trả lời giữ bản cục
bộ riêng đoạn đó; mặc định vẫn là bộ đọc cục bộ.

Một test canh đúng **lỗi thật của bản dựng đầu**: bước sắp xếp cuối xếp theo
chữ cái nên phụ đề song ngữ bị đảo thứ tự đọc trên→dưới. Đã sửa, test giữ lại.

## 5. Live Verification (bắt buộc — không mock)

Chạy trên **video thật** (`tap01_clip.mp4`, 20 giây đầu), **lấy mẫu thật**
(`moc_lay_mau_thich_ung` → 71 khung), **RapidOCR thật**, và **Gemini 3.8
Flash thật** với ĐÚNG system prompt + schema của máy chủ:

| RapidOCR (trước) | Máy chủ (sau) |
|---|---|
| `Luyen nghe hoi thogi co ban` | `Luyện nghe hội thoại cơ bản` |
| `Chu de : At the restaurant` | `Chủ đề : At the restaurant` |
| `Cuc bgn san sang` | `Các bạn sẵn sàng` |
| `goi mon chua?` | `gọi món chưa?` |
| — | `Xin lỗi`, `Tôi có một câu hỏi` |

Phần tiết kiệm chạy đúng như thiết kế: **gửi 23/71 khung** (bỏ 68% số khung),
4 lượt gọi, 27.558 token, 77 giây.

## 6. Remaining Limits / Follow-ups

- **Chia đoạn bị vụn vì nhiễu OCR.** Cùng một caption, RapidOCR đọc ra ba bản
  khác nhau (`Cuc bgn san sang` / `Cuc ban sin sang` / `Cuc ban san sang`) nên
  bị tính là ba đoạn ⇒ gửi 23 khung thay vì ~15 lý tưởng. Chữa được bằng so
  khớp gần đúng thay vì so khớp chính xác, nhưng **cố ý chưa làm**: gộp nhầm
  hai caption THẬT SỰ khác nhau sẽ áp sai chữ cho cả một đoạn, mà cái giá phải
  trả hiện tại chỉ là ~35% chi phí. Cần đo trên nhiều video hơn trước khi chọn
  ngưỡng.
- **Giá 8 Vox/lượt là số khởi điểm**, đặt bằng `scene_script.co_anh` vì cùng
  cỡ 6 ảnh — **chưa soi bằng hoá đơn thật**. Đổi được ở trang quản trị.
- **Bộ chặn sao chép nguyên văn của H2 nay nhạy hơn hẳn với tiếng Việt.** Chú
  thích cũ ở `chuanHoaSoKhop` lập luận "OCR mất dấu nên câu tiếng Việt có dấu
  sẽ không trùng" — lập luận đó **không còn đúng** khi H2b bật, vì bằng chứng
  OCR giờ có dấu đầy đủ. Đây đúng ý đồ gốc của Guardrail 2/6/7 (bắt được
  chép nguyên văn tiếng Việt, trước đây LỌT), nhưng là **thay đổi hành vi
  thật**: một beat chép nguyên văn caption nay huỷ CẢ kết quả. Đã ghi cảnh
  báo ngay tại hàm đó. Cần theo dõi tỉ lệ bị chặn ở vài lượt H2 thật đầu tiên.
- **Chưa đo trên video dọc/chữ nhỏ/nền động** ngoài `tap01_clip.mp4`.
- **Bộ đọc offline có dấu vẫn còn chỗ trống.** Tesseract `vie` (1,5 MB, 87,6%)
  lắp vừa chỗ cắm này nếu sau có nhu cầu chạy không cần mạng/không tốn Vox —
  chưa làm vì chủ dự án đã chọn hướng máy chủ.
- **`gemini-2.5-flash` đã chết với khoá mới** (API trả 404 "no longer
  available to new users", khuyên chuyển `gemini-3.6-flash`). Không thuộc phạm
  vi H2b nhưng phát hiện dọc đường — cần rà lại cấu hình nhà cung cấp trên máy
  chủ thật.

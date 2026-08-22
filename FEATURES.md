# VoxDub Studio — Bản mô tả tính năng cho AI

> **Đọc file này để làm gì.** Đây là bản mô tả trung thực về một phần mềm
> đang chạy thật, viết cho một trợ lý AI cần hiểu hệ thống trước khi đề xuất
> nâng cấp. Nó ghi cả **thứ đang chạy được**, **thứ đã dựng nhưng chưa từng
> chạy thật**, và **thứ đang hỏng**. Ba loại đó khác nhau, và trộn lẫn chúng
> là cách nhanh nhất để đề xuất sai.
>
> Nếu bạn là AI đọc file này: đừng giả định thứ gì không có ở đây. Mục
> **§8 Những nhầm lẫn thường gặp** liệt kê các tiền đề sai mà những bản đề
> xuất trước đã mắc phải — đọc trước khi viết đề xuất.
>
> Cập nhật: 2026-08-22 · phiên bản ứng dụng `3.6.0`

---

## 1. Tóm tắt trong một đoạn

VoxDub Studio là **phần mềm máy tính (Windows) lồng tiếng video bằng AI**:
đưa vào một liên kết video hoặc một tệp, nhận ra bản video đã nói tiếng Việt
(hoặc 9 ngôn ngữ khác), giữ nguyên nhạc nền, có phụ đề, kèm tiêu đề/mô tả
cho mạng xã hội. Quanh lõi đó đã mọc thêm các công cụ tách rời: chép lời,
dịch phụ đề, quản lý giọng nhân vật xuyên tập, và mới nhất là dựng ảnh sản
phẩm có cổng kiểm tuân thủ sàn thương mại điện tử.

Có **hai chế độ chạy**, quyết định bởi việc người dùng đã kết nối tài khoản
hay chưa:

| | Chạy trên máy (local) | Có tài khoản (SaaS) |
|---|---|---|
| Chép lời, lồng tiếng, ghép video | ✅ miễn phí, cần cài engine | ✅ |
| Dịch bằng AI, tóm tắt, sinh ảnh, sinh nhạc | ❌ | ✅ tính bằng **Vox** |
| Tách nhạc nền | ✅ (cài Demucs) | ✅ (chạy trên máy chủ) |

**Vox** là đơn vị tính tiền nội bộ: 1 Vox = 10 VNĐ.

---

## 2. Kiến trúc — bốn phần rời nhau

| Phần | Công nghệ | Vai trò |
|---|---|---|
| `autodub/` | Python ≥3.10, ~55.000 dòng | Lõi xử lý: tải, tách tiếng, chép lời, dịch, tạo giọng, ghép video |
| `autodub_gui/` | PySide6 (Qt) | Giao diện máy tính, 17 trang |
| `control_server/` | Node 20, Fastify 5, MongoDB | Máy chủ: ví Vox, cổng gọi mô hình AI, thống kê, quản trị |
| `website/` | React 18, Vite, Tailwind | Trang bán hàng + trang quản trị |

**Một quy tắc kiến trúc quan trọng nhất, hay bị vi phạm nhất:** mọi engine AI
nặng (Whisper, Demucs, VieNeu, NLLB, diarization, lipsync) **không** nằm
trong bản `.exe`. Chúng sống trong các môi trường Python con
(`.venv-whisper`, `.venv-asr`, `.venv-vieneu`, `.venv-diar`…) và được gọi
qua tiến trình con. Nghĩa là:

> Bất kỳ dòng `import faster_whisper` (hay torch, demucs, PIL…) nào chạy
> trong tiến trình chính đều **không bao giờ chạy được ở bản phát hành**.
> Lỗi này đã lặp lại **bốn lần** trong lịch sử dự án.

Đóng gói bằng PyInstaller onedir, phát hành qua GitHub Actions trên
`windows-latest`. Test chạy trên `ubuntu-latest` — **nghĩa là mọi thứ chỉ
xảy ra trên Windows đều không được test tự động.**

---

## 3. Tính năng ĐANG CHẠY ĐƯỢC

### 3.1 Lồng tiếng video (luồng chính, 8 bước)

1. **Tải video** — YouTube, TikTok, Facebook, Douyin, Bilibili… qua `yt-dlp`;
   hoặc chọn tệp trên máy. Có xử lý riêng cho Douyin và cho link YouTube
   dính playlist.
2. **Tách âm thanh** khỏi video.
3. **Tách nhạc nền khỏi giọng nói** (Demucs) — chạy trên máy hoặc trên máy
   chủ (50 Vox/lượt). Nhờ bước này bản lồng tiếng vẫn còn nhạc gốc.
4. **Chép lời (ASR)** — Whisper (16 ngôn ngữ nguồn) hoặc Paraformer (tối ưu
   tiếng Trung).
5. **Dịch** — ba đường: gọi máy chủ (AI), dịch cục bộ offline (NLLB), hoặc
   dán bản dịch tay. Có ngữ cảnh dịch: chủ đề, xưng hô, thuật ngữ cố định,
   ghi chú giọng văn; và một lượt **soát lại bản dịch**.
6. **Tạo giọng đọc (TTS)** — hai nguồn: CapCut API (nhiều giọng, nhiều ngôn
   ngữ) và VieNeu (giọng Việt chạy offline trên máy). Có thư viện giọng, sao
   chép giọng (voice cloning), gợi ý giọng theo nhân vật.
7. **Khớp thời lượng** — câu dịch dài hơn câu gốc là chuyện thường; hệ thống
   co giãn mềm thời lượng, chỉnh tốc độ đọc, và có thể làm chậm cả video.
8. **Ghép video** — trộn giọng mới với nhạc nền, gắn phụ đề, xuất tệp; kèm
   tiêu đề/mô tả/hashtag cho mạng xã hội (20 Vox).

**Ngôn ngữ đích (10):** Việt, Anh, Nhật, Trung, Tây Ban Nha, Thái, Indonesia,
Bồ Đào Nha, Pháp, Đức.
**Ngôn ngữ nguồn nhận diện (16):** en, vi, zh, ko, ja, th, id + các biến thể
vùng.

### 3.2 Trình chỉnh sửa

Sửa từng câu phụ đề, nghe thử từng đoạn, đổi giọng cho từng nhân vật, xem
dạng sóng âm, chèn nhạc/hiệu ứng âm thanh, rồi xuất lại — không phải chạy
lại cả video.

### 3.3 Các công cụ tách rời (dùng độc lập, không cần dự án lồng tiếng)

| Công cụ | Việc nó làm |
|---|---|
| **Chép lời** | Liên kết/video/mp3 → văn bản + `.srt`/`.vtt`/`.json`, có mốc thời gian. Chọn nhiều tệp một lượt. |
| **Dịch phụ đề** | Dịch một tệp `.srt`/`.vtt` rời |
| **Tải xuống** | Chỉ tải video về, không lồng tiếng |
| **Xử lý hàng loạt** | Lồng tiếng nhiều video một lượt, có thử lại và ghi nhật ký hỏng |
| **Hồ sơ nhân vật** | Giữ cùng một giọng cho cùng một nhân vật qua nhiều tập phim |
| **Báo cáo chất lượng** | Thống kê độ tin cậy ASR, cảnh báo câu chồng tiếng, câu đọc quá nhanh |
| **Ảnh sản phẩm** | Dựng bối cảnh mới cho ảnh sản phẩm — xem §3.5 |

### 3.4 Cổng trợ lý AI (9 tác vụ)

Một cửa duy nhất cho mọi việc cần mô hình ngôn ngữ. **App gửi tên tác vụ,
không gửi câu lệnh** — toàn bộ câu chữ hướng dẫn mô hình nằm trên máy chủ,
nên sửa chúng hoặc đổi mô hình không cần phát hành lại bản `.exe`.

| Tác vụ | Việc | Giá |
|---|---|---|
| `music_suggest` | Gợi ý nhạc nền hợp video từ chính lời thoại | 2 Vox |
| `explain_error` | Dịch một dòng lỗi kỹ thuật thành việc người dùng làm được | **0 Vox**, chạy cả khi hết tiền |
| `video_summary` | Tóm tắt video trong 3 câu + từ khoá | 5 Vox |
| `character_name` | Đoán tên nhân vật từ lời thoại | 2 Vox |
| `series_glossary` | Rút thuật ngữ cố định cho cả bộ phim | 5 Vox |
| `tighten_line` | Rút gọn câu dịch cho vừa thời lượng | 2 Vox |
| `packaging_check` | Kiểm ảnh dựng có còn đúng sản phẩm không | 3 Vox |
| `scene_continuity` | Các cảnh trong video có nhìn liền mạch không (cảnh báo, không chặn) | 4 Vox |
| `scene_script` | Gợi ý câu dẫn và nhịp cho từng cảnh | 3 Vox |

Có **bốn lớp chặn chi phí**: danh sách tác vụ đóng (tên lạ bị chặn ở tầng
schema, trước cả xác thực) → trần ký tự → hạn mức ngày mỗi máy → nhớ đệm
theo nội dung (bấm lại cùng câu hỏi thì 0 đồng).

### 3.5 Ảnh sản phẩm + cổng tuân thủ (mới nhất, chưa mở)

Sinh ra từ một án phạt thật: tài khoản TikTok Shop của chủ dự án bị **hủy
quyền thương mại điện tử + trừ 1000 điểm** ngày 19/8/2026 vì "quảng bá sản
phẩm không nhất quán" — hình trong video không khớp sản phẩm đang bán.

Nên tính năng này **không phải "AI làm ảnh đẹp"**. Nó xoay quanh một câu hỏi:
*ảnh vừa dựng có còn là sản phẩm đang bán không?* Ba luật ép bằng mã:

1. Mặc định **giữ nguyên sản phẩm** — chỉ đổi bối cảnh quanh nó (6 bối cảnh
   dựng sẵn: bàn gỗ, bếp, nền studio, giỏ quà, ngoài trời, trên tay).
2. **Kết quả kiểm đè lên chế độ người dùng xin** — mô hình hứa giữ nguyên là
   một chuyện, nó có giữ hay không là chuyện khác.
3. **Không kiểm được thì coi như không dùng được** để bán.

Giám khảo là mô hình thị giác trả **lời văn** ("nhãn khác chữ so với bản
gốc"), **không phải điểm số** — cố ý, vì người bán đi khiếu nại cần lý do
đọc được. Có nhật ký tra soát ghi cạnh ảnh để dùng khi khiếu nại.

**Dựng video ngắn** từ chính những ảnh đã duyệt: kéo để sắp thứ tự cảnh, bỏ
tích ảnh không muốn đưa vào. Danh sách chỉ hiện ảnh đăng bán được — nhưng ảnh
đã chọn mà phán quyết bị lật giữa chừng thì **chặn cả lượt xuất kèm lý do**,
không lặng lẽ bỏ ảnh đó ra (xuất thiếu một cảnh mà không ai biết thì tệ hơn).
Video ra luôn mang nhãn "AI-generated" ở cảnh đầu, không có tuỳ chọn tắt.

### 3.6 Máy chủ và quản trị

- **Ví Vox**: nạp bằng mã kích hoạt hoặc thanh toán PayOS; có cơ chế *giữ
  tiền* (hold) để không tính tiền hai lần khi thử lại; có đối soát.
- **Cổng gọi mô hình đa nhà cung cấp** với 4 vai trò: `translate`, `content`,
  `assist`, `image` — mỗi vai trỏ vào một mô hình khác nhau, có dự phòng khi
  nhà cung cấp chính hỏng.
- **Trang quản trị**: quản lý thiết bị, khoá API, giá cả (đổi được lúc chạy,
  không cần deploy lại), thống kê chi phí theo từng việc/mô hình/mã lỗi,
  phễu hoàn thành, tỷ lệ quay lại theo tuần.
- **Chế độ dựng trên máy chủ**: đẩy cả lượt lồng tiếng lên máy chủ chạy
  (150 Vox/phút video, 250 nếu có tách nhạc nền).

### 3.7 Dòng lệnh (không cần giao diện)

`voxdub dub` · `batch` · `cloud` · `translate` · `watch` (theo dõi một thư
mục, có video mới thì tự xử lý).

---

## 4. Đã dựng xong nhưng CHƯA TỪNG CHẠY THẬT

Đây là mục quan trọng nhất cho ai định đề xuất nâng cấp. Những thứ dưới đây
**đã có mã, đã có test, đã lên máy chủ — nhưng chưa một lượt nào đi qua mô
hình thật.**

| Thứ | Vì sao chưa chạy |
|---|---|
| **Toàn bộ cổng trợ lý (7 tác vụ)** | Chưa ai tạo bản ghi nhà cung cấp cho vai `assist` trong trang quản trị. Hiện tự dùng chung vai `translate` — **chạy được nhưng đắt hơn khoảng 25 lần** |
| **Sinh ảnh sản phẩm** | Chưa có nhà cung cấp cho vai `image`. Không có vai dự phòng (cố ý — rơi về `translate` chỉ sinh ra chữ). Bốn giao thức: Google Gemini · OpenRouter Images · OpenAI/Grok Images · **tự khai** (nền tảng bất kỳ) — **DeepSeek không sinh được ảnh** |
| **Cổng kiểm tuân thủ** | Cùng lý do trên |
| **Trang Ảnh sản phẩm trong app** | Chưa nằm trong bản `.exe` nào đã phát hành |

**Đây là MỘT việc, không phải bốn**: thêm hai dòng nhà cung cấp trong trang
quản trị. Nó là thao tác của con người, không phải việc lập trình. Mọi đề
xuất "hãy nối nhà cung cấp thật" là đề xuất viết mã cho một lỗ hổng không tồn
tại.

Tính năng ảnh sản phẩm còn có **chốt ba nấc** (`image.scene.stage`), mặc định
**TẮT**: phải chuyển sang `calibration` (chỉ vài máy được phép), chạy 20–30
ảnh thật, soi tay từng phán quyết, rồi mới bấm `production`.

Ngoài ra: tác vụ `character_name` đã xong phía máy chủ nhưng **chưa nối vào
giao diện** — nó cần lời thoại theo từng người nói, mà trang Hồ sơ nhân vật
chỉ giữ tên/giọng, không giữ câu thoại.

---

## 5. Vấn đề đang tồn tại

### 5.1 Nghiêm trọng — ảnh hưởng người dùng thật

- **Nâng cấp là mất sạch engine đã cài.** `.venv-*` và `models/` nằm *trong*
  thư mục ứng dụng. Giải nén bản mới ra thư mục khác → app báo "chưa cài" dù
  người dùng đã cài (và mô hình nặng ~1,5 GB). Cách chữa hiện tại là chép tay
  hai thư mục đó sang. **Đây là thiết kế, chưa sửa.**
- **Không có máy Windows nào để kiểm thử.** Test chạy trên Linux; mọi bản
  phát hành đều do người dùng cuối phát hiện lỗi. Cả một chuỗi lỗi
  (V73–V87) đến từ ảnh chụp màn hình của người dùng, không phải từ test.

### 5.2 Đã biết, chưa sửa

- **Dịch cục bộ (NLLB) có thể bỏ sót câu** khi bản chép lời nhiễu — phát hiện
  thật, chưa sửa.
- **~190/204 mã ngôn ngữ FLORES chưa kiểm chứng chất lượng** — có chủ đích,
  giao diện có cảnh báo, nhưng đừng coi là "hỗ trợ 204 ngôn ngữ".
- **Trình chỉnh sửa chưa có nút Dừng** cho hai thao tác dài (làm mới phụ đề,
  ghép video).
- **Nhận diện vùng chữ (OCR)** vẫn gọi tiến trình con trần, hết giờ sau 60
  giây, không huỷ ngang được.
- **Chế độ dựng trên máy chủ chưa hiện tiến độ** — người dùng chỉ thấy một
  dòng "Đang chờ máy chủ xử lý…".
- Một lượt chạy test đầy đủ từng kết thúc bằng **core dump lúc dọn dẹp**
  (nghi Qt dọn luồng khi thoát). Chạy lại 4 lượt đều xanh. Chưa tái hiện
  được, ghi lại làm manh mối.

### 5.3 Chưa từng kiểm chứng

- Chưa chạy tải đồng thời nhiều lượt (`claimNextJob` đúng theo lý thuyết
  Mongo nhưng chưa chạy N tiến trình song song thật).
- Chưa có test cho các thành phần React — `npm run build` là mức xác minh
  duy nhất.
- Bản dựng Docker của tiến trình tách nhạc nền chưa build thành công trong
  môi trường phát triển (giới hạn mạng, không phải lỗi Dockerfile).

---

## 6. Bốn lớp lỗi đã lặp lại — đọc trước khi đề xuất

Dự án này có **bốn cơ chế lỗi đã tái diễn nhiều lần**. Đề xuất nào đụng vào
các vùng này phải tính tới chúng.

1. **`except Exception` không kèm log = lỗi sống nhiều tháng.** Trình cài đặt
   tự động chưa từng chạy được qua nhiều bản phát hành, vì một
   `AttributeError` bị nuốt im lặng. Cùng cơ chế đã gây ra 3 sự cố khác trong
   một tuần. Nay có luật: mọi `except` phải có dấu vết hoặc lý do viết ngay
   tại chỗ.
2. **Engine nặng import trong tiến trình chính** — xem §2. Bốn lần.
3. **Tệp worker không được đóng gói.** `asr_whisper_worker.py` chưa bao giờ
   nằm trong danh sách đóng gói → chép lời trong bản `.exe` **chưa từng chạy
   được lần nào**, sâu hơn cả hai lần chẩn đoán trước đó. Nay có test quét
   toàn bộ.
4. **Deploy báo thành công nhưng chạy mã cũ.** Máy chủ deploy từ *nhánh sinh
   tự động*, không phải `main`. Bẫy này sập hai lần, lần hai xảy ra dù tài
   liệu đã cảnh báo. Nay việc sinh nhánh nằm trong chính lệnh deploy, kèm bộ
   dò lệch và một job CI.

**Bài học chung của dự án:** tài liệu không sửa được lỗi con người — phải
biến quy tắc thành thứ máy tự kiểm. Nhưng **một bộ canh kêu nhầm sẽ bị tắt
trong tuần đầu**, nên đo tỷ lệ báo nhầm trước khi dựng bộ canh.

---

## 7. Những thứ CỐ Ý không làm

Đừng đề xuất lại những thứ này mà không có lý do mới:

| Không làm | Vì sao |
|---|---|
| Sinh video AI từ kịch bản | Sản phẩm khác hẳn, cần dàn GPU, không có lợi thế cạnh tranh |
| Lồng tiếng thời gian thực trên trình duyệt | Kiến trúc luồng, gần như là sản phẩm thứ hai |
| Bản macOS/Linux | Chưa có nhu cầu; toàn bộ người dùng dùng Windows |
| Dùng embedding/cosine để so ảnh | Phán quyết bằng **lời văn** là quyết định có chủ đích — người bán đi khiếu nại cần lý do đọc được, không cần con số |
| Cho người dùng bỏ qua kết quả kiểm tuân thủ | Đúng là thứ khiến tài khoản bị phạt |
| Lưu ảnh sản phẩm trên máy chủ | Trùng với nhật ký đã ghi trên máy người bán, nơi họ thật sự cần khi khiếu nại; và là quyết định về dữ liệu khách hàng |

---

## 8. Những nhầm lẫn thường gặp khi đề xuất cho hệ thống này

Các bản đề xuất trước đã mắc đúng những lỗi dưới đây. Kiểm lại trước khi viết:

1. **"Tái sử dụng embedding ảnh sẵn có"** — không có embedding ảnh nào, ở
   bất kỳ đâu trong dự án.
2. **"Hiệu chỉnh ngưỡng chấp nhận"** — không có ngưỡng nào. Phán quyết là
   nhãn văn bản. Thứ thật sự thay đổi khi hiệu chỉnh là **câu lệnh gửi mô
   hình**, và phiên bản của nó đã được ghi từng lượt.
3. **"Đăng ký vai `image`/`assist` vào hệ thống"** — đã đăng ký rồi. Thiếu là
   *bản ghi nhà cung cấp kèm khoá API*, một thao tác trong trang quản trị.
4. **"Sửa lỗi 401"** — `401` nghĩa là thiếu token thiết bị, đúng và phải giữ
   mãi. Thiếu nhà cung cấp trả `503`. Đặt "hết 401" làm tiêu chí thành công
   là mời người sau đi phá xác thực.
5. **Nhầm dự án.** Hai bản đề xuất gần đây ghi tiêu đề "SocialHub AutoPoster"
   trong khi nội dung là của VoxDub. Đây là hai phần mềm khác nhau.
6. **Đề xuất thêm bảng/cửa API/trang mới khi thứ tương đương đã có.** Ví dụ
   thống kê hiệu chỉnh đã có chỗ đứng trong bảng thống kê trợ lý sẵn có; dựng
   cửa thứ hai chỉ tạo thêm một chỗ phải nhớ mở.

---

## 9. Hướng nâng cấp còn để ngỏ

Xếp theo mức sẵn sàng, không phải theo mức hấp dẫn:

**Chặn ngay trước mắt (không phải việc lập trình):** cắm nhà cung cấp cho vai
`assist` và `image`, chạy 20–30 ảnh thật để hiệu chỉnh, rồi mở tính năng.
Cho tới lúc đó, mọi thứ trong §4 vẫn là mã chết.

**Việc kỹ thuật đã rõ hình:**
- Tách `.venv-*` và `models/` ra khỏi thư mục ứng dụng để nâng cấp không mất
  engine — sửa được lớp phiền toái lớn nhất của người dùng.
- Nối `character_name` vào giao diện (cần đổi cấu trúc hồ sơ nhân vật để giữ
  câu thoại theo người nói).
- Hiện tiến độ lượt chạy trên máy chủ.
- Nút Dừng cho hai thao tác còn thiếu trong Trình chỉnh sửa.

**Việc cần quyết định của con người trước:**
- Có thu thập thêm dữ liệu sử dụng không (đã hỏi, chủ dự án chọn giữ nguyên
  phạm vi hiện tại).
- Có kiểm soát việc sao chép giọng người thật không (rủi ro đã ghi nhận,
  chủ dự án xác nhận chưa can thiệp ở đợt này).

---

## 10. Tài liệu chi tiết hơn

| Tệp | Nội dung |
|---|---|
| `docs/PLAN.md` | Toàn bộ bản đặc tả từng đợt (~95 mini-spec, Phase A→H) |
| `docs/TEST_LOG.md` | Nhật ký từng đợt: đã kiểm gì, lỗi nào tự tìm ra, còn tồn gì |
| `docs/API.md` | Hợp đồng từng cửa API máy chủ |
| `docs/ARCH.md` | Kiến trúc lõi |
| `docs/PRD.md` | Yêu cầu sản phẩm và các rủi ro mở |

**Quy mô test hiện tại:** 1714 test Python (7 bỏ qua) + 471 test Node
(1 bỏ qua). Kỷ luật của dự án: mỗi luật quan trọng đều được **gỡ ra để chứng
minh test đỏ**, chứ không chỉ chạy cho xanh.

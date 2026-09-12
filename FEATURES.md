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
> Cập nhật: 2026-09-12 · phiên bản ứng dụng `3.17.16` · 2.823 test Python +
> 700 test Node + 74 test React

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
| `autodub/` | Python ≥3.10, ~28.000 dòng | Lõi xử lý: tải, tách tiếng, chép lời, dịch, tạo giọng, ghép video |
| `autodub_gui/` | PySide6 (Qt), ~30.000 dòng | Giao diện máy tính, **22 trang** |
| `control_server/` | Node 20, Fastify 5, MongoDB, ~12.000 dòng | Máy chủ: ví Vox, cổng gọi mô hình AI, thống kê, quản trị |
| `website/` | React 18, Vite, Tailwind, ~7.000 dòng | Trang bán hàng + trang quản trị |

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
xảy ra trên Windows đều không được test tự động** (trừ một lượt dub thật,
xem §5.1).

### Phần máy chủ triển khai thế nào (C57–C59, 03–04/09/2026)

`control_server` và tiến trình lồng tiếng phía máy chủ chạy trên Vibe Host,
**không deploy thẳng từ `main`** mà từ hai nhánh sinh tự động
(`deploy/vays-control-server`, `deploy/vays-dub-worker`) vì nền tảng chỉ nhận
thư mục con ở ngay gốc repo. Bẫy cố hữu: quên sinh lại nhánh thì nền tảng
dựng lại **mã cũ** và vẫn báo thành công — đã sập ba lần.

Nay chuỗi này chạy hết bằng máy, không còn bước tay nào:

1. Push `main` → CI **tự sinh lại cả hai nhánh** deploy từ đúng commit vừa
   push rồi force-push (`sinh-nhanh-deploy`).
2. Bộ dò so cây thư mục giữa `main` và nhánh deploy — chạy SAU bước sinh, và
   hỏi nhánh **trên remote** chứ không phải bản sao trên máy lập trình.
3. Chỉ khi test Python + Node + **lượt dub thật trên Windows** đều xanh, CI
   mới đưa lên prod — và **chỉ dịch vụ nào có thư mục build thật sự đổi**.
4. Deploy xong thì hỏi chính dịch vụ (`/health`): 200 chưa đủ, phải kèm
   `db: "đã kết nối"` — trước C59 đường này trả `ok: true` cả khi mất
   MongoDB, tức bộ kiểm sẽ ghi "đã lên" cho một bản không dùng được.

Một chi tiết đáng nhớ cho ai sửa phần này: **tác vụ deploy báo thành công
không có nghĩa là dịch vụ sống** — nền tảng chấm điểm bằng cổng mạng, còn thứ
người dùng gặp là câu trả lời của ứng dụng.

---

## 3. Tính năng ĐANG CHẠY ĐƯỢC

### 3.1 Lồng tiếng video (luồng chính, 8 bước)

1. **Tải video** — qua `yt-dlp`, hoặc chọn tệp trên máy. Có xử lý riêng cho
   link YouTube dính playlist (thiếu `noplaylist` từng làm hỏng MỌI lượt tải
   link dạng Mix) và cho chữ chia sẻ dán nguyên cả câu tiếng Trung (tự bóc
   lấy địa chỉ trong đó).

   **Nền tảng — nói thẳng mức độ chắc chắn:**

   | Nền tảng | Thực tế |
   |---|---|
   | YouTube, TikTok, Facebook | Chạy được, dùng thường xuyên |
   | **Douyin** | **Đã đóng mọi cửa ẩn danh** (C33): trang chia sẻ không còn địa chỉ video, `iteminfo` trả rỗng, `detail` trả 403. Chỉ còn đường **cookie của chính người dùng**; không có cookie thì báo hỏng thay vì thử vô ích. Đã đo tay nhiều đường, không phải suy đoán. |
   | **YouTube báo "không dùng được" GIẢ** | 08/09: chủ dự án báo hỏng thật với 2 video công khai. Nguyên nhân: YouTube mới bắt thêm bước giải mã (n-signature challenge) mà client mặc định của yt-dlp chưa xử lý được, báo lỗi CHUNG với ca video thật sự bị xoá — **đã sửa**: tự động thử lại bằng client Android (đo thật: tải được, nhưng giới hạn 360p) trước khi báo hỏng thật. |
   | Bilibili và các nền tảng Trung khác | **Chưa từng kiểm chứng** — máy chạy thử bị chặn ở tầng địa chỉ mạng (HTTP 412 ngay cả khi mở trang thường), nên không kết luận được gì. |
2. **Tách âm thanh** khỏi video.
3. **Tách nhạc nền khỏi giọng nói** (Demucs) — chạy trên máy hoặc trên máy
   chủ (50 Vox/lượt). Nhờ bước này bản lồng tiếng vẫn còn nhạc gốc.
4. **Chép lời (ASR)** — Whisper (16 ngôn ngữ nguồn) hoặc Paraformer (tối ưu
   tiếng Trung). Chọn «để ứng dụng tự nhận ra ngôn ngữ» thì mã ngôn ngữ máy
   nghe ra **đi tiếp vào mọi bước sau** (C44) — trước đó nó chỉ được ghi vào
   Nhật ký rồi vứt, nên bước dịch chạy với ngôn ngữ nguồn rỗng.
5. **Dịch** — ba đường: gọi máy chủ (AI), dịch cục bộ offline (NLLB), hoặc
   dán bản dịch tay. Có ngữ cảnh dịch: chủ đề, xưng hô, thuật ngữ cố định,
   ghi chú giọng văn; và một lượt **soát lại bản dịch**. Lời nhắc dịch có
   luật riêng cho **ngôn ngữ nguồn** (C44): chủ ngữ ẩn và đơn vị 万/亿 của
   tiếng Trung, «you» chung chung và cụm động từ của tiếng Anh, cộng phần
   chung nhắc rằng bản chép lời là của máy nên có nghe nhầm. Ngôn ngữ nguồn
   chưa có bộ riêng chỉ nhận phần chung.
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

**Ba thứ thêm gần đây, đều đụng tới tiền hoặc công sức người dùng:**

- **Chi phí hiện ra TRƯỚC khi chạy** (V97). Sau bước nghe-chép (chạy trên máy,
  miễn phí) app hỏi "video này tốn bao nhiêu Vox, ví còn bao nhiêu" rồi mới
  chạy tiếp. Trước đó số Vox chỉ hiện ở bảng tổng kết — tức là sau khi đã trừ.
  Chỉ hỏi ở luồng wizard; batch/dòng lệnh chạy thẳng.
- **Gộp mẩu vụn thành câu trước khi dịch** (V97). Máy chủ tính tiền theo số
  dòng; bộ nghe cắt theo khoảng lặng 500ms nên một câu có thể vỡ thành hàng
  chục mẩu một-hai chữ. Đo trên dữ liệu vụn mô phỏng: còn 18% số dòng. Hạn
  mức 7 giây/84 chữ để dòng gộp vẫn làm phụ đề đọc được; không gộp qua hai
  người nói. Tắt được bằng `GOP_CAU_TRUOC_KHI_DICH`.
- **Nâng cấp không mất gì đã cài** (V77/V81/V96). `.venv-*`, `models/`, `bin/`
  và `.env` đều nằm *trong* thư mục ứng dụng, nên bản mới về nguyên tắc là
  trắng trơn. App tự dò các thư mục **nằm cùng thư mục cha** và dùng lại:
  engine + model, FFmpeg, và cài đặt/khoá API/token (chép sang một lần lúc
  khởi động). Quy trình nâng cấp rút còn: giải nén cạnh bản cũ, mở lên.
  **Điều kiện:** phải cùng thư mục cha. Sang ổ đĩa khác thì vẫn phải chép tay
  hoặc trỏ đường dẫn trong Cài đặt.

- **Ba đường dịch, người dùng chọn thẳng** (D1). `TRANSLATE_MODE`:
  `server` (chất lượng AI, có phí dịch) · `offline` (NLLB trên máy, **không
  phí dịch nhưng KHÔNG miễn phí cả lượt** — giá nền 10 Vox/dòng vẫn tính,
  tiết kiệm ~17%) · `auto` (ưu tiên máy chủ, mất mạng thì rơi ngoại tuyến kèm
  báo rõ). Chọn `offline` thì **không giữ chỗ tiền dịch**, và chưa cài NLLB
  thì báo lỗi chứ không lặng lẽ quay về máy chủ. Trước D1 đường ngoại tuyến
  không thể chạm tới vì nó bị treo vào `is_configured()`.

- **Nhạc nền của bạn** (C42). Trình chỉnh sửa → Nhạc nền → *Chọn tệp nhạc của
  tôi…* nhận mp3/wav/m4a/aac/flac/ogg/opus/wma; app tự chuyển sang WAV 44.1kHz
  trong thư mục dự án, tự cắt hoặc đệm im lặng cho khớp độ dài video, và giảm
  nhỏ theo mức *Giảm tiếng gốc* khi có lời thoại. Chọn tệp là ô *Cách xử lý*
  tự chuyển sang «Nhạc nền của tôi».
  **Chưa có:** lớp âm thanh đặt tự do trên thanh thời gian (kéo thả nhiều đoạn
  vào các mốc khác nhau) — cố ý để đợt sau, vì phải dựng lại thanh thời gian.
  Cũng không có xoay/nghiêng/cắt khung hình: đây là công cụ lồng tiếng, không
  phải trình dựng phim.

### 3.2 Trình chỉnh sửa

Sửa từng câu phụ đề, nghe thử từng đoạn, đổi giọng cho từng nhân vật, xem
dạng sóng âm, chèn nhạc/hiệu ứng âm thanh, rồi xuất lại — không phải chạy
lại cả video.

### 3.3 Các công cụ tách rời (dùng độc lập, không cần dự án lồng tiếng)

| Công cụ | Việc nó làm |
|---|---|
| **Chép lời** | Liên kết/video/mp3 → văn bản + `.srt`/`.vtt`/`.json`, có mốc thời gian. Chọn nhiều tệp một lượt. Xem §3.4 — đây là phần được mài nhiều nhất gần đây. |
| **Dịch phụ đề** | Dịch một tệp `.srt`/`.vtt` rời |
| **Tải xuống** | Tải video (MP4) hoặc chỉ tải âm thanh (MP3) về, không lồng tiếng — chọn định dạng ngay trên trang |
| **Nhập video + phụ đề có sẵn** | Trang launcher Trình chỉnh sửa: (video, phụ đề đã tiếng Việt) → dự án chỉnh sửa được thẳng, không tốn Vox. Nút thứ hai (08/09): (video, phụ đề NƯỚC NGOÀI) → **tự dịch** (offline NLLB miễn phí hoặc SaaS tính phí) → dự án lồng tiếng luôn — gộp việc trước đây phải làm tay 2 bước (Dịch phụ đề rồi Nhập phụ đề) thành một |
| **Xử lý hàng loạt** | Lồng tiếng nhiều video một lượt, có thử lại và ghi nhật ký hỏng |
| **Hồ sơ nhân vật** | Giữ cùng một giọng cho cùng một nhân vật qua nhiều tập phim |
| **Báo cáo chất lượng** | Thống kê độ tin cậy ASR, cảnh báo câu chồng tiếng, câu đọc quá nhanh |
| **Ảnh sản phẩm** | Dựng bối cảnh mới cho ảnh sản phẩm — xem §3.6 |

### 3.4 Chép lời tệp dài — phần được mài nhiều nhất gần đây

Sinh ra từ một việc thật: một tệp giảng bài `.m4a` dài **3 giờ 43 phút**
(206 MB). Bốn thứ được thêm vì tệp đó, và tất cả đều chạy trên máy người dùng
nên **không tốn Vox**:

- **Tự chia tệp dài.** Quá `PHUT_TU_CAT` (45 phút) thì tự cắt thành nhiều
  đoạn, **cắt bám vào khoảng lặng** (dò trong ±90 giây quanh mốc) để không
  chặt ngang câu. Cắt bằng chép luồng (`-c copy`) nên gần như tức thì và
  không mất chất lượng. Mỗi đoạn mang mốc bắt đầu thật trong tên tệp, kết quả
  được **dời mốc thời gian về đúng vị trí trong tệp gốc** rồi ghép lại thành
  một bản duy nhất — người dùng không phải tự ghép.
- **Ghi kết quả dần** ra `<tên>.dang_chay.txt`, đẩy xuống đĩa theo từng câu.
  Dừng giữa chừng (tắt máy, lỗi) vẫn còn nguyên phần đã nghe.
- **Lọc câu bịa.** Whisper ở quãng im hay đọc ra câu mẫu kiểu "hãy đăng ký
  kênh". Hai lớp: gộp các câu **lặp lại liên tiếp** (≥3 lần giống hệt), và
  **bỏ câu nằm trọn trong vùng im lặng**. Gốc rễ đã sửa ở tầng dưới:
  `condition_on_previous_text=False` — chính tham số mặc định này đẩy mô hình
  vào vòng lặp tự nhắc lại.
- **Gộp câu cho tệp `.txt`.** Bộ nghe cắt theo khoảng lặng 500ms nên bản chép
  ra có thể toàn dòng một-hai chữ. Nút "Gộp câu cho .txt…" đọc lại tệp đã
  xuất và nối thành câu đọc được — **không đè lên tệp gốc**, ghi ra
  `..._da_gop.txt`. Đo trên tệp 8.123 dòng: xong dưới 1 giây, còn 18% số dòng.

**Chưa làm:** phân biệt người nói (diarization) trong công cụ chép lời độc
lập — chủ dự án chủ động bỏ qua ("chỉ cần ra được text là đủ").

### 3.5 Cổng trợ lý AI (12 tác vụ)

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
| `kiem_anh_minh_hoa` | Kiểm ảnh minh hoạ có lỡ vẽ ra sản phẩm/nhãn/chữ không (mini-spec H4d) — câu hỏi NGƯỢC với `packaging_check`, vì ở đây không có ảnh sản phẩm thật làm neo | 3 Vox |
| `scene_continuity` | Các cảnh trong video có nhìn liền mạch không (cảnh báo, không chặn) | 4 Vox |
| `scene_script` | Gợi ý câu dẫn và nhịp cho từng cảnh | 3 Vox (**8 Vox** nếu kèm xem ảnh) |
| `viral_flow_blueprint` | Phân tích cấu trúc video tham khảo (mini-spec H2) — chỉ gọi qua `/v1/flow-blueprints`, không qua `/v1/ai/assist` chung, vì cần lưu lại thành Flow Blueprint | 8 Vox (giá khởi điểm, chưa chốt bằng số liệu chi phí thật) |
| `doc_chu_khung_hinh` | Đọc chữ hiện trên khung hình video, **giữ đúng dấu tiếng Việt** (mini-spec H2b) — bộ đọc chữ chạy trên máy không phát ra được dấu | 8 Vox mỗi lượt (tối đa 6 khung/lượt, app tự gộp trước khi gửi) |
| `brand_script_rewrite` | Viết lại kịch bản cho thương hiệu từ nhịp kể chuyện của video tham khảo (mini-spec H3) — chỉ gọi qua `/v1/brand-scripts` vì kết quả phải qua hai lớp kiểm rồi mới lưu | 12 Vox (giá khởi điểm) |

Có **bốn lớp chặn chi phí**: danh sách tác vụ đóng (tên lạ bị chặn ở tầng
schema, trước cả xác thực) → trần ký tự → hạn mức ngày mỗi máy → nhớ đệm
theo nội dung (bấm lại cùng câu hỏi thì 0 đồng).

### 3.6 Ảnh sản phẩm + cổng tuân thủ (mới nhất, chưa mở)

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

### 3.7 Máy chủ và quản trị

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

### 3.8 Dòng lệnh (không cần giao diện)

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
| **Trang Ảnh sản phẩm trong app** | Đã có trong bản phát hành (mục «Ảnh sản phẩm» ở thanh bên, từ v3.6.0, commit C1 21/08), nhưng chốt `image.scene.stage` mặc định TẮT nên bấm vào chưa chạy được gì |

**Đây là MỘT việc, không phải bốn**: thêm hai dòng nhà cung cấp trong trang
quản trị. Nó là thao tác của con người, không phải việc lập trình. Mọi đề
xuất "hãy nối nhà cung cấp thật" là đề xuất viết mã cho một lỗ hổng không tồn
tại.

Tính năng ảnh sản phẩm còn có **chốt ba nấc** (`image.scene.stage`), mặc định
**TẮT**: phải chuyển sang `calibration` (chỉ vài máy được phép), chạy 20–30
ảnh thật, soi tay từng phán quyết, rồi mới bấm `production`.

Ngoài ra: tác vụ `character_name` **đã nối vào giao diện** (hộp thoại "Xem
trước người nói" trong Trình chỉnh sửa — nút "Gợi ý tên gọi" đọc thẳng câu
thoại của người nói đó từ transcript đang mở, không cần đổi cấu trúc hồ sơ
nhân vật). Cố ý **không tự ghi** tên gợi ý vào hồ sơ nhân vật — người dùng
phải tự gõ, vì tên sai tự ghi sẽ áp cho mọi tập sau (có test chặn cứng:
`tests/test_tro_ly_giai_doan_2.py::test_khong_tu_ghi_ten_vao_ho_so`). Việc
này vẫn nằm trong nhóm "chưa chạy thật" chỉ vì **chưa có nhà cung cấp cho vai
`assist`** (xem bảng trên) — mã đã xong, đang chờ đúng thao tác quản trị đó.

---

## 5. Vấn đề đang tồn tại

### 5.1 Nghiêm trọng — ảnh hưởng người dùng thật

- **Không có máy Windows nào để kiểm thử tay.** Test chạy trên Linux; cả một
  chuỗi lỗi (V73–V87, và tiếp tục ở C61–C64) đến từ ảnh chụp màn hình của
  người dùng, không phải từ test.

  **Đỡ hơn nhiều từ 28/08 (C45) và 04/09 (C55)**: mỗi push vào `main`, CI chạy
  MỘT lượt dub THẬT trên runner Windows; và trước mỗi lần phát hành, lượt đó
  đi **tới tận video xuất ra** — đóng vai người dùng dịch tay, đọc giọng bằng
  VieNeu, ghép video, rồi soi chính tệp ra: có luồng tiếng không, **có CÂM
  không** (đo `mean_volume`), thời lượng có khớp nguồn không. Hỏng thì không
  phát hành. Bằng chứng lượt v3.16.3: *23 câu · tiếng aac · −15,9 dB · 54,6s
  (nguồn 53,5s)*.

  Còn lại chưa tự động: lượt chạy đó dùng **mã nguồn**, không phải bản `.exe`
  đã đóng gói (bản `.exe` chỉ có smoke test khởi động + kiểm tệp worker có
  trong gói). Và không có gì kiểm được **chất lượng** — chỉ kiểm đường chạy.

### 5.2 Đã biết, chưa sửa

- ~~Dịch cục bộ (NLLB) có thể lẫn/bịa nội dung khi câu 2 trong 1 segment bị
  model "dừng sớm"~~ — **đã sửa thật (C69).** C67 phát hiện lại đúng bug V11
  và thử hai cách LỌC (đo sau khi dịch) — cả hai đều không phân biệt được ca
  lỗi với bản dịch đúng. C69 đổi hướng sang SỬA TRƯỚC khi model kịp dừng
  sớm: ép `min_decoding_length` (tham số có sẵn của ctranslate2) theo đúng
  độ dài từng câu nguồn — đo thật bằng model NLLB thật, hết dấu vết bug V11,
  0 hồi quy trên mọi ca đã thử, đổi lại translation chậm hơn ~10% (đo thật,
  do gọi riêng từng câu thay vì gộp — `min_decoding_length` là số dùng
  chung cho cả lượt gọi của ctranslate2, gộp câu thì không đặt riêng được).
  Còn tồn: ca "segment không có dấu kết câu" (ASR mất dấu câu) — cảnh báo ra
  log (giữ từ C67) nhưng chưa có sửa tự động, vì không tách được ranh giới
  câu một cách đáng tin khi nguồn không có dấu. Xem `docs/TEST_LOG.md` C67+C69.
- ~~"Nghe chép thiếu câu" — chủ dự án báo, CHƯA tái hiện được~~ — **TÁI HIỆN
  ĐƯỢC THẬT và ĐÃ SỬA (G1→G3, 08/09).** Clip ngắn (30s/53s) không lộ ra gì —
  nhưng video hoạt hình cảnh hành động (nhạc nền + hiệu ứng dồn dập) làm lộ:
  Silero VAD (bộ lọc trước khi nghe, `threshold=0.5` mặc định) coi cả một
  đoạn 38 giây là "không có tiếng nói", dù âm lượng không khác gì đoạn nghe
  bình thường (không phải do quá to). Sửa hai lớp: (1) hạ `threshold` xuống
  0.3 ở cả 3 nơi dùng chung model VAD (Whisper 2 đường + Paraformer), không
  hồi quy trên video nói liên tục; (2) tự động dò khoảng cách bất thường
  giữa 2 câu liên tiếp rồi nghe lại đúng đoạn đó tắt hẳn VAD. Verify bằng
  `transcribe()` production thật trên đúng video đã lỗi: **toàn bộ khoảng
  trống 38 giây được lấp đầy**, khớp (vài chỗ còn nhiều hơn) chuẩn đối
  chứng nghe không lọc VAD. Công cụ đo: `scripts/so_sanh_nghe.py` (chạy
  trên máy, không tốn Vox) — từ C65 nhận thẳng tệp video. Chi tiết:
  `docs/TEST_LOG.md` mục G1/G3, `docs/MINI-SPEC_G3_VAD_Bo_Sot_Doan_On.md`.
- **~190/204 mã ngôn ngữ FLORES chưa kiểm chứng chất lượng** — có chủ đích,
  giao diện có cảnh báo, nhưng đừng coi là "hỗ trợ 204 ngôn ngữ".
- **Nhận diện vùng chữ (OCR)** nay dừng ngang được, hết giờ tính theo số
  khung, và lấy mẫu rải đều cả video (C49). Có lựa chọn **xoá chữ**
  (`delogo`, C51): đo trên khung hình thật, làm mờ lệch 52,66/255 so với nền
  gốc — gần bằng để nguyên chữ — còn xoá chỉ lệch 3,58.

  **Vùng rộng trên nền nhiều chi tiết vẫn bị kéo nhoè** — đã xảy ra thật
  05/09: bộ quét đề xuất ~15 vùng trên một cảnh phố đêm (biển hiệu neon, cả
  mặt diễn viên), bật xoá chữ rồi xuất ra thì nguyên mảng người bị nhoè, xấu
  hơn chữ gốc. Ba việc đã sửa sau đó: **lọc chữ chỉ TRÔI QUA một khung** và
  giữ chữ NẰM LÌ (C63 — watermark/phụ đề cháy nằm yên một chỗ nên khung nào
  cũng thấy; biển hiệu trôi theo máy quay); **cảnh báo khi vùng quá rộng mà
  đang bật xoá chữ** (cảnh báo, không tự đổi sang làm mờ); **bấm chuột phải
  để xoá riêng một vùng** (C64 — trước đó chỉ có "Xoá vùng cuối"/"Xoá tất
  cả", muốn bỏ vài vùng ở giữa thì phải xoá sạch rồi vẽ lại).

  Inpainting học sâu thì vẫn chưa (cần model vài trăm MB + xử lý từng khung).

  **`detect_text_regions()` (dùng cho làm mờ/xoá) chỉ trả VÙNG, không trả
  nội dung chữ** — cố ý, đúng mục tiêu gốc V5, không phải lỗi. Từ 08/09 có
  thêm **`read_text_regions()`** (mini-spec H2a) — lớp ĐỌC song song, giữ
  lại `text` + `confidence` + `timestamp` mỗi khung hình, KHÔNG đổi hành vi
  hàm cũ. **Chưa nối vào bất kỳ trang/tính năng nào** — đây là hạ tầng cho
  mini-spec H2 ("Flow Blueprint", đang tạm dừng) đọc sau này, chưa có giao
  diện người dùng nào gọi tới hàm này.

  Hai giới hạn đã ĐO THẬT (không suy đoán), phải biết trước khi dùng lớp
  đọc này cho việc gì: (1) **tiếng Việt bị đọc MẤT DẤU THANH** (model
  nhận dạng bundled sẵn — `ch_PP-OCRv4` — không có ký tự tiếng Việt trong
  từ điển), và **confidence vẫn báo cao (0,90-0,99) dù đọc sai** — không
  có tín hiệu tự động nào bắt được lỗi này; (2) **caption ngắn (dưới 1
  giây) cần lấy mẫu khung hình DÀY hơn hẳn** mức dùng cho làm mờ (đo thật:
  caption 0,5 giây bị bộ lấy mẫu thưa của tính năng làm mờ bỏ lọt hoàn
  toàn 0/5 khung; lấy mẫu mỗi 0,2 giây mới bắt được) — chi phí ~1,23
  giây/khung trên CPU, mật độ dày cho video dài là chi phí thật. Chi tiết
  đầy đủ: `docs/MINI-SPEC_H2a_OCR_Read_Layer_Gap.md`.
- **Che chữ trên video DÀI chưa ai chạy thật.** C50 quét dày hơn theo thời
  lượng (tới 24 khung), nhưng mọi bằng chứng hiện có là test và tính tay —
  chưa có lượt nào trên phim ~40 phút. Lấy mẫu ~2 phút/khung vẫn **có thể
  lọt** chữ chỉ hiện 30 giây.
- ~~Chế độ dựng trên máy chủ chưa hiện tiến độ~~ — **đã sửa (C68/V12).** Gốc
  rễ thật không chỉ là "thiếu UI": `Narrator` (khung Nhật ký) không có
  template cho step "separate" nên dòng tiến độ **không hề lên Nhật ký**,
  người dùng chỉ thấy dòng tĩnh "Đang tách giọng nói khỏi nhạc nền" rồi im
  lặng tới khi xong (có thể 30 phút). Nay hiện **số giây đã chờ thật** (server
  không trả % thật — 1 job Demucs không chia nhỏ được, nên không bịa ra một
  con số hoàn thành).
- Một lượt chạy test đầy đủ **thỉnh thoảng kết thúc bằng core dump lúc dọn
  dẹp** (nghi Qt dọn luồng khi thoát). Đã gặp lần hai ngày 28/08; cả hai lần
  đều xảy ra SAU khi test chạy xong, chạy lại ngay là xanh. Chưa tái hiện
  được theo ý muốn.

### 5.3 Chưa từng kiểm chứng

- Chưa chạy tải đồng thời nhiều lượt (`claimNextJob` đúng theo lý thuyết
  Mongo nhưng chưa chạy N tiến trình song song thật).
- ~~Chưa có test cho các thành phần React~~ — **sai từ 17/08 (V50)**: đã có
  Vitest + React Testing Library. C70 (07/09) viết thêm 35 test theo rủi ro
  TIỀN/BẢO MẬT (`api/client.js`, phiên đăng nhập admin, state machine
  Checkout, form cấu hình nhà cung cấp AI) — nay **74 test/8 tệp**
  (`npm test` trong `website/`). Tìm ra 1 bug thật khi viết: phiên admin bị
  đăng xuất oan lúc mất mạng tạm thời (đã sửa, xem `docs/TEST_LOG.md` C70).
- Bản dựng Docker của tiến trình tách nhạc nền chưa build thành công trong
  môi trường phát triển (giới hạn mạng, không phải lỗi Dockerfile).

---

## 6. Sáu lớp lỗi đã lặp lại — đọc trước khi đề xuất

Dự án này có **sáu cơ chế lỗi đã tái diễn nhiều lần**. Đề xuất nào đụng vào
các vùng này phải tính tới chúng.

1. **`except Exception` không kèm log = lỗi sống nhiều tháng.** Trình cài đặt
   tự động chưa từng chạy được qua nhiều bản phát hành, vì một
   `AttributeError` bị nuốt im lặng. Cùng cơ chế đã gây ra 3 sự cố khác trong
   một tuần. Nay có luật: mọi `except` phải có dấu vết hoặc lý do viết ngay
   tại chỗ.
2. **Engine nặng import trong tiến trình chính** — xem §2. Bốn lần.
3. **Tệp cần thiết không được đóng gói.** (Đã tái diễn 26/8/2026 ở một
   danh sách khác: `build_exe.py` gõ tay 6 tên script cài đặt, trong khi app
   bảo người dùng chạy 11 tên — nên dịch ngoại tuyến, phân biệt người nói,
   lipsync, OCR và ghi danh giọng **chưa bao giờ cài được từ bản tải nào**.
   Nay danh sách được suy ra từ thư mục, có test canh.)
   Lần đầu: `asr_whisper_worker.py` chưa bao giờ
   nằm trong danh sách đóng gói → chép lời trong bản `.exe` **chưa từng chạy
   được lần nào**, sâu hơn cả hai lần chẩn đoán trước đó. Nay có test quét
   toàn bộ.
4. **Deploy báo thành công nhưng chạy mã cũ.** Máy chủ deploy từ *nhánh sinh
   tự động*, không phải `main`. Bẫy này sập hai lần, lần hai xảy ra dù tài
   liệu đã cảnh báo. Nay việc sinh nhánh nằm trong chính lệnh deploy, kèm bộ
   dò lệch và một job CI.

5. **Câu chữ nói về TIỀN đi lệch khỏi mã.** Nút "Gợi ý từ nội dung video"
   ghi *"chạy ngay trên máy, không tốn Vox"* — đúng ở V88 (đo bằng luật), SAI
   từ V89 khi đường hỏi máy chủ (**2 Vox/lượt**) được thêm vào. Truy ngược thì
   thấy **mô tả đầu tệp `music_suggest.py` cũng sai y hệt**: người viết giao
   diện đọc mô tả ấy, tin nó, chép sang tooltip. Hứa miễn phí rồi trừ tiền là
   kiểu sai tệ nhất về câu chữ — người dùng không có cách nào biết mình vừa
   mất tiền cho tới khi nhìn ví. Nay có bộ canh cấp lớp: tệp nào gọi
   `get_client()` (tiêu được Vox) mà mô tả có hứa miễn phí thì **phải nói luôn
   giá của đường tốn tiền**; miễn trừ phải kèm lý do viết ra, và có test canh
   chính danh sách miễn trừ đó.

6. **Máy BIẾT chuyện gì xảy ra nhưng nói ra một câu người dùng không dùng
   được.** Lớp lỗi này lặp ba lần trong hai ngày (05–07/09):
   - Chưa cài bộ quét chữ → trả `[]` → giao diện báo *"Không phát hiện chữ
     overlay nào trong video này"*. Người dùng kết luận video mình sạch chữ
     rồi đi tiếp (C56).
   - Chưa cài bộ dịch ngoại tuyến → `FileNotFoundError` không ai bọc → *"Dừng
     lại vì một lỗi ngoài dự tính"* (C61).
   - Lời khuyên khi TikTok chặn bảo đi bật mượn cookie; làm theo thì gặp *"không
     chép được kho cookie"* (Windows khoá tệp khi trình duyệt đang chạy); tắt
     cookie đi thì quay lại lời khuyên cũ — **một vòng lặp kín do chính ứng
     dụng dựng ra** (C62).

   Ba cách chữa thành luật: (a) tài nguyên tuỳ chọn phải có chốt "đã cài
   chưa" TRƯỚC khi gọi, và ném lỗi RIÊNG chứ không để lỗi hệ điều hành rơi ra
   giao diện; (b) rỗng chỉ được có MỘT nghĩa — "đã kiểm, không có gì" — không
   được trộn với "không kiểm được"; (c) trước khi viết *"làm A đi"*, phải tự
   đi hết đường A: điều kiện ngầm của A là phần BẮT BUỘC của lời khuyên.
   Nay có test canh tên ô/nút nhắc trong lời khuyên phải THẬT SỰ tồn tại
   trong giao diện.

**Bài học chung của dự án:** tài liệu không sửa được lỗi con người — phải
biến quy tắc thành thứ máy tự kiểm. Nhưng **một bộ canh kêu nhầm sẽ bị tắt
trong tuần đầu**, nên đo tỷ lệ báo nhầm trước khi dựng bộ canh.

**Và một bài học riêng cho AI đọc file này:** năm trong sáu lớp lỗi trên đều
lộ ra từ **một lượt chạy thật của người dùng**, không phải từ 2.356 test. Test
canh được cái mình đã nghĩ tới; lượt chạy thật canh phần còn lại.

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
7. **"App đã đọc được caption/chữ overlay trên hình, dùng ngay để..."** —
   CÓ hàm đọc được (`read_text_regions()`, mini-spec H2a, `text_regions.py`)
   nhưng **CHƯA nối vào bất kỳ trang/tính năng nào** — không có UI, không
   có tác vụ nào gọi tới nó. Và đừng hứa chính xác cho tiếng Việt: đo thật
   xác nhận model đọc MẤT DẤU THANH (đôi khi sai cả ký tự gốc) trong MỌI
   câu tiếng Việt đã thử, dù confidence báo cao — xem
   `docs/MINI-SPEC_H2a_OCR_Read_Layer_Gap.md`.

---

## 9. Hướng nâng cấp còn để ngỏ

Xếp theo mức sẵn sàng, không phải theo mức hấp dẫn:

**Chặn ngay trước mắt (không phải việc lập trình):** cắm nhà cung cấp cho vai
`assist` và `image`, chạy 20–30 ảnh thật để hiệu chỉnh, rồi mở tính năng.
Cho tới lúc đó, mọi thứ trong §4 vẫn là mã chết.

**Việc kỹ thuật đã rõ hình:**
- Hiện tiến độ lượt chạy trên máy chủ.

**Sáng kiến mới bắt đầu (08/09) — Viral Flow Clone & Brand Rewrite.** Mục
tiêu cuối: học nhịp/cấu trúc từ video đối thủ/KOL viral (KHÔNG sao chép câu
chữ) rồi viết lại kịch bản theo hồ sơ brand riêng của từng khách hàng, dựng
thành video hoàn chỉnh (nối vào pipeline ảnh sản phẩm C3 đã có). Bốn mini-spec:
- **H1 — Hồ sơ Brand: ĐÃ XONG, CHẠY THẬT.** Trang **Hồ sơ Brand** (thanh bên)
  — tạo/sửa/xoá nhiều hồ sơ (tên, sản phẩm, tone, đối tượng, USP, ràng buộc
  không được nói) cho MỘT thiết bị. Server `/v1/brand-profiles` (xem
  docs/API.md), cách ly theo thiết bị — có test chéo thiết bị thật (không
  chỉ giả lập). **Chưa có tác vụ nào ĐỌC hồ sơ này** — H3 (viết kịch bản) là
  nơi tiêu thụ dữ liệu, chưa làm.
- **H2a — OCR Read Layer: ĐÃ XONG.** Audit trước khi mở H2 phát hiện OCR cũ
  (`detect_text_regions()`) chỉ biết VÙNG chữ, không đọc được NỘI DUNG — đóng
  gap bằng `read_text_regions()` mới (song song, không đổi hợp đồng hàm cũ).
  Đo thật: RapidOCR đọc tiếng Việt MẤT DẤU THANH dù confidence vẫn cao
  (0,90-0,99) — xem docs/MINI-SPEC_H2a_OCR_Read_Layer_Gap.md.
- **H2 — Viral Flow Blueprint: ĐÃ XONG, CHẠY THẬT.** Trang **Phân tích cấu
  trúc video tham khảo** (thanh bên) — trích bằng chứng ASR+OCR TRÊN MÁY
  NGƯỜI DÙNG (tải video → chép lời → đọc caption, lấy mẫu OCR thích ứng dày
  hơn hẳn bộ lấy mẫu cũ ở 0-5s/5s cuối), gửi lên máy chủ để mô hình phân
  tích VAI TRÒ KỂ CHUYỆN từng đoạn (hook/nêu vấn đề/bằng chứng/cao trào/kêu
  gọi hành động…) rồi lưu lại. Server `/v1/flow-blueprints` (xem docs/API.md),
  cách ly theo thiết bị. **Chặn sao chép nguyên văn bằng mã** (N-gram 6 từ +
  so khớp cụm ngắn cho caption 1-2 từ kiểu "STOP SCROLLING") — một beat chép
  nguyên văn huỷ CẢ kết quả, không chỉ lọc riêng beat đó. Output KHÔNG BAO
  GIỜ chứa transcript/caption gốc, chỉ mô tả trừu tượng.
- **H2b — Đọc chữ CÓ DẤU tiếng Việt: ĐÃ XONG, KIỂM CHỨNG THẬT.** Bộ đọc chữ
  chạy trên máy không phát ra được dấu tiếng Việt (giới hạn từ điển của model:
  6.623 ký tự mà chỉ 2 ký tự có dấu) nên caption ra `Dang ky kenh de khong bo
  lo`. Nay có **bộ đọc thay được**: có máy chủ thì đọc lại bằng mô hình nhìn
  ảnh, ra đúng `Đăng ký kênh để không bỏ lỡ`. Chỉ gửi **một khung đại diện cho
  mỗi đoạn chữ khác nhau** (đo thật: 23/71 khung), không gửi cả video. Chưa
  cấu hình máy chủ thì vẫn chạy, chỉ là chữ mất dấu. Tính năng làm mờ chữ
  KHÔNG đổi gì.
- **H2c — Dấu vân tay bằng chứng: ĐÃ XONG.** H3 cần so kịch bản mới với câu
  chữ video gốc, nhưng H2 cố ý không lưu câu chữ đó. Cách gỡ: lưu **băm một
  chiều** — phát hiện trùng được, mà máy chủ vẫn không giữ nguyên văn. Đổi
  lại: chỉ chỉ ra được cụm trong kịch bản MỚI, không trưng ra được cụm gốc.
- **H3 — Viết kịch bản cho thương hiệu: ĐÃ XONG.** Trang **Viết kịch bản**
  (thanh bên): chọn một lượt phân tích cấu trúc + một hồ sơ thương hiệu →
  máy chủ viết kịch bản mới (lời đọc, chữ trên hình, mô tả cần quay gì cho
  từng đoạn), rồi chạy **hai lớp kiểm** trước khi cho dùng: có chứa cụm bạn
  đã cấm không, và có trùng câu chữ video nguồn không. Một đoạn bẩn là **chặn
  cả kịch bản**, và nút "Dùng kịch bản này" chỉ sáng khi sạch — không có nút
  bỏ qua cảnh báo. Đoạn bị chặn hiện đúng cụm gây chặn để biết sửa ở đâu.
  Viết lại một đoạn thì kiểm lại TOÀN BỘ, không tạo trạng thái nửa vá.
- **H4 — Dựng video từ kịch bản: ĐÃ XONG phần không tốn Vox.** Trang **Dựng
  video** (mở từ nút «Dùng kịch bản này» ở trang Viết kịch bản): gán ảnh cho
  từng đoạn, mỗi đoạn giữ hình **đúng bằng thời gian đọc lời của nó** (tốc độ
  đọc đo thật bằng chính engine VieNeu), rồi dựng thành **dự án mở được trong
  Trình chỉnh sửa** — từ đó nghe thử, sửa lời, đọc lại, xuất video đều dùng
  máy móc có sẵn. Ghép và dựng **không tốn Vox**.
- **H4d — Nhờ vẽ ảnh minh hoạ cho đoạn còn thiếu (30 Vox/ảnh).** Đoạn nào chưa
  có ảnh thì hiện luôn **gợi ý hình** của kịch bản và cho bấm «Vẽ». Công cụ
  **không bao giờ tự vẽ**: luôn hỏi trước, kèm tổng tiền và đúng những gợi ý
  sắp được vẽ. Ảnh vẽ ra là ảnh **minh hoạ** — cố ý không vẽ hộp, chai, nhãn
  hay chữ nào, vì sản phẩm bịa trong video bán hàng là thứ khiến tài khoản bị
  phạt; ảnh nào lỡ có thì bị **loại, không ghép vào video**. Người trong các
  ảnh sẽ **khác nhau giữa các đoạn** — công cụ không giữ được cùng một nhân
  vật, và nói điều đó ra trước khi bạn trả tiền. Cửa này mặc định **tắt** ở
  máy chủ; bật nó là một quyết định về tuân thủ, không phải một cờ cấu hình.

**Đã giải quyết, đừng đề xuất lại:** tách `.venv-*`/`models/` ra khỏi thư mục
ứng dụng — không cần nữa, vì app đã tự dò bản cũ nằm cùng thư mục cha (§3.1).
Xem trước chi phí và gộp câu trước khi tính tiền cũng đã làm (V97);
ba đường dịch đã làm (D1). Nối `character_name` vào giao diện cũng đã làm —
xem §4. Nút Dừng cho "Lưu tất cả và đọc lại" và "Xuất video"/"Ghi lại phụ đề"
trong Trình chỉnh sửa cũng đã thêm (C66) — cờ huỷ ở tầng worker có từ C49,
chỉ thiếu nút bấm tại chỗ.

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
| `docs/KE-HOACH-KIEM-C50-C52.md` | Hai việc còn tồn chỉ máy chủ dự án trả lời được: che chữ trên phim dài, và "nghe chép thiếu câu" — kèm cách đo, **không tốn Vox** |
| `docs/MINI-SPEC_H1_Ho_So_Brand_Multi_Tenant.md` | Hồ sơ Brand — nền tảng multi-tenant cho sáng kiến "Viral Flow Clone & Brand Rewrite", đã xong Scope A-D |
| `docs/MINI-SPEC_H2a_OCR_Read_Layer_Gap.md` | Audit OCR dừng H2 (Flow Blueprint) + đóng gap: `read_text_regions()` mới, đọc được nội dung chữ nhưng tiếng Việt còn mất dấu |
| `docs/MINI-SPEC_H2_Viral_Flow_Blueprint.md` | Viral Flow Blueprint — phân tích cấu trúc video tham khảo (abstraction-first, chặn sao chép nguyên văn bằng mã), đã xong Scope A-E |
| `docs/MINI-SPEC_H2b_Doc_Chu_Co_Dau.md` | Đọc chữ overlay CÓ DẤU tiếng Việt — vì sao OCR trên máy không thể ra dấu, đo 5 hướng chữa, và bộ đọc thay được |
| `docs/MINI-SPEC_H2c_Dau_Van_Tay_Bang_Chung.md` | Dấu vân tay một chiều của bằng chứng — cho H3 kiểm sao chép mà máy chủ vẫn không giữ câu chữ nguyên văn |
| `docs/MINI-SPEC_H3_Brand_Script_Rewrite.md` | Viết kịch bản cho thương hiệu — hai lớp kiểm (tuân thủ + nguyên gốc), chặn ở cấp toàn kịch bản |
| `docs/MINI-SPEC_H4_Storyboard_To_Video.md` | Từ kịch bản brand thành dự án video — storyboard, ghép ảnh theo thời lượng riêng, và vì sao không đồng bộ được nhân vật |
| `docs/MINI-SPEC_H4d_Sinh_Anh_Minh_Hoa.md` | Sinh ảnh minh hoạ từ chữ — vì sao cửa ảnh cũ không làm được, và luật tuân thủ thay thế khi không có ảnh sản phẩm làm neo |
| `docs/MINI-SPEC_H4c1_Timing_Contract.md` | Hợp đồng thời lượng lớp dựng hình — audit vì sao video ngắn hơn transcript, và cổng đo lại sau khi dựng |
| `docs/BACKLOG_PHASE_H.md` | Mọi phát hiện Phase H còn mở, có trạng thái thật: đã sửa / đã tự kiểm chứng / chưa kiểm chứng |
| `docs/PILOT_PHASE_H.md` | Runbook chạy thử xuyên suốt H2→H3 trên máy thật + bốn cổng phải đóng trước khi mở H4 |

**Quy mô test tại thời điểm cập nhật tệp này:** 2.449 test Python (4 bỏ qua —
chỉ có nghĩa trên Windows) + 542 test Node (1 bỏ qua, 0 hỏng) + 74 test React (0 hỏng).
Con số này tăng gần như mỗi đợt — dùng nó để hình dung quy mô, đừng dùng làm
mốc đối chiếu.

⚠️ **Một cái bẫy khi tự đếm:** máy chạy test thiếu thư viện hệ thống của Qt
thì một loạt tệp test giao diện bị bỏ qua **ngay ở tầng nạp module** —
`pytest` báo xanh với con số thấp hơn mà không kêu một tiếng. Có lần báo
"1790 đạt" trong khi số thật là 1954. Thấy tổng số tụt thì nghi môi trường
trước khi nghi mã. Kỷ luật của dự án: mỗi luật quan trọng đều được **gỡ ra để chứng
minh test đỏ**, chứ không chỉ chạy cho xanh.

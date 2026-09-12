# Backlog Phase H — mọi thứ còn mở, có trạng thái thật

**Lập 11/09/2026.** Trước tệp này, các phát hiện từ đợt rà soát chỉ nằm trong
hội thoại — không nơi nào theo dõi được. Chủ dự án hỏi đúng câu:
*"các vấn đề trên bạn đã lên kế hoạch khắc phục chưa"*. Câu trả lời thật lúc
đó là **chưa**, nên có tệp này.

## Cách đọc

| Nhãn | Nghĩa |
|---|---|
| ✅ | Đã sửa, có test, đã chứng minh đỏ trước khi tin |
| 🔴 | Còn mở, **tôi đã tự kiểm chứng** là có thật |
| 🟡 | Còn mở, agent báo, **CHƯA kiểm chứng độc lập** — phải kiểm trước khi sửa |

🟡 không có nghĩa là sai; nó có nghĩa là **chưa ai đo**. Sửa một thứ chưa đo
là cách nhanh nhất để sửa nhầm.

---

## Đã sửa (11/09)

| Mã | Việc | Commit |
|---|---|---|
| ✅ | `201 Created` bị coi là lỗi — chặn toàn bộ Phase H | `ff4dfbd` |
| ✅ | Câu báo lỗi đổ cho mạng cho mọi nguyên nhân | `ff4dfbd` |
| ✅ | `evidenceStatus` chưa từng được ghi ⇒ mọi đoạn `ok` | `ad2b1ac` |
| ✅ | Gate chống sao chép: H2 bắt, H3 tha | `ad2b1ac` |
| ✅ | Kịch bản ≥30 đoạn: H3 không chạy được, viết-lại đốt tiền | `ad2b1ac` |
| ✅ | Ràng buộc một từ bắt oan ("nhất định", "thống nhất") | `ad2b1ac` |
| ✅ | Hai chỗ hiện sai giá (30 vs 33 Vox; 8 vs ~32 Vox) | `ad2b1ac` |
| ✅ | `PUT /brand-profiles/:id` đổi được chủ sở hữu | `ad2b1ac` |
| ✅ | H2b dùng PIL mà bản đóng gói loại PIL ⇒ mất dấu tiếng Việt | `ad2b1ac` |
| ✅ | H4c-1 video ngắn hơn transcript, hình lệch dần | `38e1d02` |
| ✅ | H4c-2 xuất ra video câm không cảnh báo | `a950fbc` |
| ✅ | H4d-0 mẻ vẽ ảnh hỏng thì giao diện im lặng | `5392a05` |
| ✅ | Dự án H4c bị chặn ở bước Xuất vì thiếu dấu `.render_mode` | `21f423b` |
| ✅ | Lỗi engine nghe giết cả lượt H2 (lẽ ra phải hạ cấp) | đang commit |

---

## 🔴 Còn mở — đã tự kiểm chứng

### ✅ B1. ĐÃ SỬA 11/09 — TDZ `ReferenceError` ⇒ 500 VĨNH VIỄN — `routes/ai.js:838`

`result.results[0]` dùng ở dòng 838 trong khi `let result` mãi dòng 898. Chỉ
nổ khi `task === 'packaging_check'` **và** trúng nhớ đệm theo nội dung: lần
đầu thành công ghi đệm, lần sau cùng bộ ảnh đó ⇒ object literal dựng ra ném
**đồng bộ**, `.catch()` không bắt được ⇒ **500 vĩnh viễn cho bộ ảnh đó**.

`doc_chu_khung_hinh` (H2b) thoát nạn chỉ nhờ ternary ngắn mạch.

**Mức**: cao — hỏng vĩnh viễn, không tự khỏi. **Ước**: nhỏ (dời khai báo).

### ✅ B2. ĐÃ SỬA 11/09 — `429` nuốt mã và câu của máy chủ — `saas_client.py:274`

Nhánh 429 vứt cả `code` lẫn `message`, thay bằng *"Máy chủ đang bận… Chờ một
chút rồi thử lại."* Nên `DAILY_LIMIT` (máy chủ nói *"Hôm nay đã dùng hết N
lượt… Thử lại vào ngày mai"*) tới người dùng thành "chờ một chút" ⇒ họ bấm
lại cả buổi.

Cùng lớp với lỗi `201` vừa sửa: **hợp đồng máy chủ bị máy khách viết đè.**

**Mức**: cao — sai hướng hoàn toàn. **Ước**: nhỏ.

### ✅ B3. ĐÃ SỬA 11/09 — `is_running()` bỏ sót `_bp_worker` — `storyboard_page.py:436`

`shutdown()` có `_bp_worker` nhưng `is_running()` thì không, mà `app.py` chỉ
gọi `shutdown()` cho trang nào `is_running()` trả True. Chính `app.py` ghi:
*"huỷ QThread đang chạy lúc teardown sẽ làm Qt crash cứng (0xC0000409)"*.

**Mức**: trung bình — sập app lúc đóng, hiếm. **Ước**: rất nhỏ.

**Đã sửa**: thêm `_bp_worker` vào `is_running()`; `shutdown()` nay XIN DỪNG
trước rồi mới chờ, vì mẻ vẽ có thể còn chín tấm mà chờ suông 3 giây là bỏ đi
trong lúc luồng vẫn chạy. Test: `tests/test_b3_b4_b5_ton_dong.py`.

### ✅ B4. ĐÃ SỬA 11/09 — Mẻ vẽ ảnh không có nút Dừng — `workers.py`

`SinhAnhMinhHoaWorker` không có `cancel_event` (khác `TranscribeWorker`). Mỗi
ảnh tới 120s vẽ + 90s kiểm; mẻ 5 ảnh có thể chạy 15 phút, `shutdown()` chỉ
chờ 3 giây.

**Mức**: trung bình. **Ước**: nhỏ.

### ✅ B5. ĐÃ SỬA 11/09 — Thư mục ra đóng cứng `~/VoxDub` — `storyboard_page.py:323,413`

`self._settings_provider` nhận vào rồi **không dùng ở đâu cả**. Trang C1 (ảnh sản phẩm) cùng
loại thì tôn trọng `settings.output_dir`. Người dùng đặt `D:\Videos` thì dự
án vẫn nằm ở `C:\Users\…\VoxDub` và **không hiện ở trang Dự án**.

**Mức**: trung bình. **Ước**: nhỏ.

**Đã sửa**: thêm `_goc_ra()` đọc `settings.output_dir`, hai chỗ gọi đổi theo;
đọc cài đặt hỏng thì lùi về `~/VoxDub` chứ không chặn việc. Có test chốt CHỖ
GỌI (không còn `expanduser` trong hai hàm đó), không chỉ chốt thân hàm.

### ✅ B7. ĐÃ SỬA 11/09 — gọi `"ffmpeg"` trần, không qua `duong_dan_ffmpeg()`

Tìm ra khi soi kết quả live của RS-20. `product_video._lenh_ghep()` và
`product_scene._chay_ffmpeg()` gọi thẳng `"ffmpeg"` — tức dựa vào PATH.

Trong GUI thì **không sao**: app nối `bin/` vào PATH lúc khởi động. Nhưng
docstring của chính `ffmpeg_deps.duong_dan_ffmpeg()` đã ghi: *"bản đóng gói
đã nối `bin` vào PATH lúc khởi động, nhưng **CLI và test thì không**."*

⇒ Máy KHÔNG có ffmpeg hệ thống (đúng máy chủ dự án — preflight cho thấy nó
dùng bản trong `bin/`), chạy bất cứ thứ gì ngoài GUI mà đụng `product_video`
sẽ hỏng với một lỗi "không tìm thấy tệp" trần, thay vì câu nói rõ của dự án.

Chạm thật: `scripts/pilot_h4_cuc_bo.py` đi qua đúng đường này.

**Mức**: trung bình — GUI không ảnh hưởng, chỉ CLI/script. **Ước**: nhỏ.

**Đo lại khi sửa**: không phải 2 chỗ mà **30 chỗ** trong `autodub/` gọi
`"ffmpeg"`/`"ffprobe"` trần (`media/video.py`, `media/audio.py`, `editor.py`,
`preview.py`, `speech/transcriber.py`…). Nên chữa ở MỘT chỗ thay vì 30: thêm
`ffmpeg_deps.vao_duong_ffmpeg()` vá `PATH` một lần, gọi từ `cli.main()` và
`scripts/pilot_h4_cuc_bo.py`. `app.py` đổi sang dùng chung hàm này thay cho
bản sao riêng của nó — hai bản sao của cùng phép vá thì sửa một bên là hai
đường đi lệch nhau mà không ai thấy.

Sửa 30 chỗ gọi là 30 cơ hội bỏ sót, và chỗ thứ 31 thêm vào tháng sau lại hỏng
y như cũ. Test: `tests/test_b7_ffmpeg_ngoai_gui.py` (7), trong đó có một test
chốt `shutil.which` thật sự tìm ra — thêm chữ vào biến môi trường mà `which`
vẫn không thấy thì chưa chữa gì.

### ✅ B6. ĐÃ SỬA 11/09 — `UsageLog.create` không bọc `.catch` ở nhánh THÀNH CÔNG — `ai.js:1375`

`Promise.all([remember(...), UsageLog.create({...})])`. `remember()` đã được
làm cho không bao giờ ném (sự cố 22/8), `UsageLog.create` thì chưa — trong
khi nhánh LỖI ngay trên lại có `.catch()`. MongoDB trục trặc giữa `charge` và
ghi sổ ⇒ app nhận 500, ảnh mất, **30 Vox đã trừ**. `/product-scene` cùng dạng.

**Mức**: cao (đụng tiền), xác suất thấp. **Ước**: rất nhỏ.

---

## Đã sửa 12/09 — lượt chạy thật thứ hai của chủ dự án

Nguồn: `youtube.com/shorts/9iB1Io8InXg`, ~34 giây, tiếng Việt. Lỗi cp1252 đã
hết (OCR chạy xong 65 khung), nhưng hỏng ở bước cuối với *"Không phân tích
được lúc này. Thử lại sau."* Bốn lỗi tìm ra, ba trong số đó CHE LẤP nhau.

### ✅ E1. Máy chủ ném đi nguyên nhân, thay mọi thứ bằng một câu 503

`routes/flow-blueprints.js` bắt mọi lỗi không phải 400 rồi trả
`AI_UNAVAILABLE`. `AiError` đã mang sẵn `code` và câu riêng — ném đi rồi đoán
lại là tự bịt mắt mình. Ba ca cần ba cách chữa khác nhau (đợi mạng / đổi
video / báo lỗi) mà nói cùng một câu.

**Đã sửa**: lỗi có `code` + `statusCode` đi thẳng lên máy khách; chỉ lỗi trần
(socket rơi) mới còn là 503. Luôn ghi nhật ký đầy đủ trước.

> **Lỗi tôi tự tạo khi sửa:** bản đầu ép mọi mã ≥500 về 502 và làm mất
> `retryAfter`. Nhưng `callWithFallback` ném `PROVIDER_UNAVAILABLE` với
> `statusCode` **503** khi hết nhà cung cấp — tức ca hay gặp nhất trong thực
> tế bị đổi thành "lỗi phía máy khách" và mất luôn lời khuyên thử lại. Ba
> test đầu không chạm tới vì đều dùng lỗi tự dựng; phải viết thêm test cho
> ĐƯỜNG THẬT mới thấy.

### ✅ E2. Bộ chặn sao chép huỷ cả kết quả vì một từ ghép hai chữ

**Đây là nguyên nhân gốc.** OCR đọc được `hóa đơn` — đúng chủ đề video. Luật
"dòng bằng chứng ngắn (≥2 chữ) thì kiểm CHỨA NGUYÊN VẸN" biến nó thành lệnh
huỷ toàn bộ, trong khi mô hình bị buộc mô tả một video tiếng Việt về hoá đơn,
bằng tiếng Việt, mà không được viết chữ "hóa đơn". Việc đó không làm được.

**ĐO trước khi chọn ngưỡng** (kỷ luật "đo trước khi đặt tolerance"):

| ngưỡng | bỏ sót ca chép thật | chặn oan từ thông thường |
|---|---|---|
| 2 (cũ) | 0/4 | 3/3 |
| 3 | 1/4 | 1/3 |
| 4 | 2/4 | 1/3 |
| 5 | 3/4 | 0/3 |

**Không ngưỡng nào sạch** — số chữ không phân biệt được khẩu hiệu bị chép với
từ vựng thông thường, vì `STOP SCROLLING` và `hóa đơn` đều hai chữ.

**Đã sửa**: tách hai câu hỏi vốn bị gộp. "Có chạm bằng chứng không" giữ
nguyên độ nhạy (ngưỡng 2, không đổi); "chạm thì có đáng HUỶ không" dùng ngưỡng
4 chữ. Dòng 2–3 chữ thành CẢNH BÁO gắn vào kết quả — không mất ca phát hiện
nào, cũng không giết lượt chạy. Một chốt cũ (`flow-blueprint-schema.test.js`,
ca `STOP SCROLLING`) đổi từ "huỷ" sang "cảnh báo", có ghi rõ lý do tại chỗ.

### ✅ E3. Giá hiện ra lệch 3,7 lần, và không có chỗ nào hỏi

Màn hình hứa "khoảng 32 Vox". Thực tế 65 khung ÷ 6 = 11 lô × 8 = **88 Vox**,
tiêu hết rồi mới hỏng ở bước cuối. Giá phụ thuộc **lượng chữ trên hình**,
không phải số giây — video ngắn kín caption tốn hơn video dài không chữ.

**Đã sửa**: câu báo giá nói đúng đại lượng (30–100 Vox, tuỳ lượng chữ); nhật
ký ghi số Vox dự tính TRƯỚC lô đầu tiên; thêm cổng xin phép khi vượt 50 Vox,
đặt ở TẦNG HÀM (`doc_lai_bang_may_chu`) để CLI/script cũng được chặn. Hộp
thoại dựng ở luồng giao diện qua tín hiệu — Qt cấm dựng widget từ luồng nền.

### ✅ E4. Nhật ký máy chủ bị lượt poll làm ngập — không chẩn đoán được

Lỗi xảy ra 09:56 UTC; tới 10:01 nhật ký chạy chỉ còn **82 dòng**, toàn bộ là
`POST /internal/dub-jobs/claim` (worker hỏi 3 giây một lượt, 2 dòng mỗi
lượt ≈ 40 dòng/phút). Dòng `flow_blueprint analysis failed` mang nguyên nhân
thật đã bị đẩy ra ngoài. **Mọi thứ ghi ở mức `info` có tuổi thọ dưới hai
phút** — E1 sửa xong cũng vô ích nếu dòng log không sống nổi tới lúc đọc.

**Đã sửa**: dạng HÀM của `disableRequestLogging` (`logController` +
`LogController`), bỏ qua `/internal/*/claim` và `/health`.

> **Hai lỗi tôi tự tạo khi sửa, tự bắt khi chạy thật — ghi lại để khỏi lặp:**
>
> 1. Bản đầu tự viết hook `onRequest`/`onResponse` và **làm mất dòng ghi ở
>    mức `error`** — đúng thứ quý nhất. Chữa một lỗi chẩn đoán bằng một lỗi
>    chẩn đoán nặng hơn. Dạng hàm giữ nguyên đường ghi của Fastify.
> 2. `disableRequestLogging` ở mức trên cùng đã **deprecated** (FSTDEP023),
>    bỏ ở Fastify 6 — chỉ thấy khi chạy thật, không test nào bắt.
>
> Cả hai chỉ lộ ra khi chạy mã thật và ĐỌC đầu ra, không phải khi test xanh.

---

## Đã sửa 12/09 (đợt 2) — lượt chạy thật thứ ba

Cổng 50 Vox chạy đúng (chủ dự án thấy hộp thoại, đồng ý, mất 88 Vox), nhưng
bước cuối vẫn huỷ: *đoạn 5 lặp lại cụm "tự động gửi dữ liệu"*.

### ✅ E5. Ngưỡng chống sao chép đo sai ĐẠI LƯỢNG

`tự động gửi dữ liệu` là **chức năng của phần mềm trong video**. Mô tả "vai
trò kể chuyện" của đoạn đó mà không được gọi tên việc phần mềm tự động gửi
dữ liệu thì không mô tả được gì — cùng lớp với `hóa đơn` (11/09).

**Nguyên nhân sâu hơn con số**: `tự động gửi dữ liệu lên` là **ba từ** tiếng
Việt nhưng **sáu âm tiết**, nên rơi vào luật n-gram. `NGUONG_TU_LIEN_TIEP = 6`
hiệu chỉnh trên ví dụ tiếng Anh ("Stop wasting money on this" = 5 tiếng = 5
từ). Tiếng Việt tách theo âm tiết, nên **cùng con số 6 lại chặt gấp đôi** —
không ai chọn điều đó, nó là hệ quả không ai để ý của việc đếm "từ" bằng
khoảng trắng.

**Đo, không đoán** — 15 ca (7 phải huỷ, 8 không được huỷ), sau khi sửa phép
đo để tính đoạn liên tiếp DÀI NHẤT thay vì cứng `n`:

| tiêu chí huỷ | sai |
|---|---|
| luật cũ (cụm ≥ 4 tiếng) | 5/15 |
| phủ ≥ 25% | 3/15 |
| phủ ≥ 30% / 35% / 40% | 1/15 |
| **phủ ≥ 45%** | **0/15** ← điểm duy nhất sạch |
| phủ ≥ 50% | 1/15 |
| phủ ≥ 60% | 3/15 |

45% sạch nhưng nằm ĐÚNG TRÊN RANH: ca phải-qua phủ 40%, ca phải-huỷ phủ 45%.
**Một điểm duy nhất đúng nghĩa là phép đo vẫn chưa tách được hai lớp**, không
phải là đã tìm ra ngưỡng.

**Quyết định của chủ dự án**: đi theo đúng mẫu **H3** — lớp gác thứ SẼ ĐĂNG.
H3 không huỷ gì cả: nó gắn `originalityFlag='flagged'` cho đúng đoạn rồi mời
viết lại đoạn đó (`brand-scripts.js:445`). H2 chỉ sinh bản phân tích NỘI BỘ mà
lại chặt hơn hẳn lớp gác quan trọng hơn nó — **đó mới là chỗ sai, không phải
con số**. Ngưỡng huỷ nay 70% (beat bị phủ hơn hai phần ba), cách ca phải-qua
cao nhất 30 điểm. Độ nhạy phát hiện KHÔNG đổi — có tệp test riêng chốt việc
đó, vì hạ ngưỡng mà bỏ luôn phát hiện thì bảng kết quả trông y hệt nhau.

### 🟡 E6. Thời gian — 84% nằm ở OCR CỤC BỘ, không phải mạng
**ĐÃ ĐO trên dữ liệu thật (12/09). D5 đã dựng: 88 → 48 Vox. D1 BỊ BÁC BỎ.
Phần THỜI GIAN vẫn chưa cắt được — thiếu số đo C.4.**
Mini-spec: `docs/MINI-SPEC_E6_Bot_Khung_OCR.md`.

Đo từ nhật ký chủ dự án (12/09, 12:37–12:41):

    12:37:44 → 12:40:57   OCR tại máy, 104 khung   3 phút 13 giây   (84%)
    12:40:57 → 12:41:35   gửi máy chủ, 11 lô            38 giây     (16%)

**Tôi đã đoán sai một lần ở đây rồi sửa**: thoạt nhìn "65 đoạn chữ khác nhau
cho video 34 giây" trông như lỗi gộp đoạn (`_khoa_doan` so chuỗi chính xác
trên chữ RapidOCR vốn nhiễu). Kiểm lại thì **65 là thật**: video là sketch có
phụ đề chạy theo lời, lấy mẫu 5 khung/giây ở đầu-cuối và 2 khung/giây ở giữa
(`moc_lay_mau_thich_ung` → 99 mốc), nên gần như mỗi khung bắt được một trạng
thái phụ đề khác.

**Đòn bẩy thật**: phụ đề cháy vào hình **lặp lại đúng thứ ASR đã cho**. Giá
trị riêng của OCR với H2 là mẫu overlay (chữ lớn, thẻ CTA), không phải phụ
đề. Bỏ đoạn OCR nào đã được transcript phủ ở cùng mốc sẽ cắt phần lớn cả tiền
lẫn thời gian — nhưng phải ĐO trước.

**Giai đoạn 0 đã dựng (v3.17.14) — chỉ đo, 0 Vox, không đổi hành vi:**

- Ghi `<work_dir>/data/ocr_chan_doan.json` từ
  `flow_blueprint.trich_bang_chung` — tầng duy nhất có đủ cả bằng chứng OCR
  lẫn transcript. Chạy kể cả khi người dùng bấm «Bỏ qua» ở cổng 50 Vox, nên
  lấy số đo không mất đồng nào.
- `text_regions_worker.py` đo **riêng** `khoi_dong_s` (nạp mô hình RapidOCR,
  chi phí CỐ ĐỊNH) và `quet_s` (co theo số khung). Hai phần phản ứng NGƯỢC
  nhau khi cắt khung; gộp làm một con số là không trả lời được câu quyết
  định "cắt khung có nhanh lên không". Đo ở tiến trình cha KHÔNG tách được
  vì đường chính là subprocess.
- `scripts/do_chan_doan_ocr.py` đọc tệp đó ra bốn câu trả lời kèm kết luận
  có điều kiện — không có nó thì "đo" lại thành nhìn JSON rồi ước lượng.
  Script tự bỏ dấu tiếng Việt trước khi so, vì RapidOCR trả `met moi` còn
  transcript trả `Mệt mỏi`; thiếu bước đó là mọi đoạn đều "không trùng" và
  kết luận ngược hẳn sự thật.

**Đã sửa một khẳng định sai trong chính spec**: bản đầu nói cần hai video dài
khác nhau mới tách được khởi động khỏi phần quét. Không cần — đo hai mốc
ngay trong worker là đủ trong một lượt.

**Kết quả đo (12/09, chủ dự án gửi `ocr_chan_doan.json` — 36,2 giây, 104 mốc,
65 đoạn):**

| | |
|---|---|
| D1 — đoạn OCR trùng lời đọc | **10/65 = 15%**, tiết kiệm đúng **8 Vox** |

**D1 bị bác bỏ.** Phần lớn chữ trên hình là ảnh chụp màn hình phần mềm MISA
(có khung tới 64 vùng chữ), không phải phụ đề lặp lời.

**Tôi kết luận sai HAI LẦN trước khi có dữ liệu.** Đoán "65 đoạn là lỗi gộp",
rồi tự bác bỏ — *"65 là thật, phụ đề chạy theo lời"*. Dữ liệu cho thấy lần
đoán ĐẦU mới đúng:

```
'supersale d onn& am am'  khung 7
'supersale d onn&amam'    khung 8   cùng caption, lệch 2 ký tự
'supersale d onn&am am'   khung 9
```

**D5 (đòn bẩy thật) — gộp khung liền nhau khi chữ GẦN GIỐNG:**

    giống >= 75%: 65 -> 31 đoạn = 48 Vox
    giống >= 80%: 65 -> 33 đoạn = 48 Vox   <- chọn (giữa cao nguyên)
    giống >= 85%: 65 -> 34 đoạn = 48 Vox
    giống >= 90%: 65 -> 40 đoạn = 56 Vox

Soi tay cả 17 nhóm gộp ở mức 80%: không nhóm nào gộp nhầm. Chạy lại bằng mã
đã cài trên đúng tệp đó: **65 → 35 đoạn, 88 → 48 Vox (giảm 46%)**.

Đại diện mỗi đoạn nay là khung ĐỌC RÕ NHẤT, không phải khung đầu — ca thật
`surersale` (0,944) rồi `supersale` (0,989): gửi khung đầu là trả tiền để máy
chủ đọc lại một khung vốn đã đọc sai.

**CÒN MỞ — C.4 chưa trả lời được.** Tệp thật không có `khoi_dong_s`/`quet_s`
dù mã đã có trong v3.17.14; chưa rõ vì sao. Đã thêm tổng đo ở tiến trình cha
làm mức chặn trên + cảnh báo trong Nhật ký để lượt sau lần ra. **D5 cắt TIỀN
nhưng KHÔNG cắt thời gian** — OCR cục bộ vẫn quét đủ 104 khung (~3 phút).
Đòn bẩy thời gian là D3, mà D3 cần đúng con số đang thiếu.

---

## Đã sửa 12/09 (đợt 3) — nhánh "Bỏ qua" tôi vừa thêm tự làm hỏng chính nó

Chủ dự án làm ĐÚNG hướng dẫn của tôi: bấm «Bỏ qua, không tốn Vox», chờ thêm
ba phút, rồi nhận `Dừng lại: must NOT have more than 400 items`.

### ✅ E7. Máy khách không giữ trần bằng chứng — nhánh RẺ là nhánh duy nhất hỏng

Cổng 50 Vox tôi thêm ở v3.17.13 tạo ra một nhánh mới, và tôi **không chạy thử
nhánh từ chối tới cùng**:

| | Chữ OCR | Gộp | Số mẩu |
|---|---|---|---|
| Đồng ý đọc | máy chủ trả SẠCH, một dòng mỗi khung | tốt | 65 ✓ |
| **Bỏ qua** | RapidOCR thô, mỗi khung vài vùng, lệch nhau vài ký tự | gần như không gộp được | **>400** ✗ |

`gop_quan_sat_lien_tiep` so `text` NGUYÊN VĂN, mà OCR tiếng Việt nhiễu nên
hai khung liền nhau ra chữ khác nhau. Máy chủ khai `maxItems: 400` và từ
chối — sau khi người dùng đã chờ bốn phút.

**Đã sửa**: `gioi_han_bang_chung()` ở máy khách, trần khớp máy chủ (có test
chốt hai bên không lệch). Cắt thì **rải đều dòng thời gian**, không cắt đuôi
— lấy 400 mẩu đầu rồi bỏ phần sau là mất sạch bằng chứng nửa cuối video, và
mô hình sẽ kết luận nhịp video đúng như thế. Cắt bao nhiêu, từ bao nhiêu,
ghi vào `samplingPolicyUsed` (ràng buộc E.1 của mini-spec E6).

### ✅ E8. `setErrorHandler` KHÔNG BAO GIỜ chạy — toàn bộ API nói tiếng Anh

Đào tiếp thì lỗi rộng hơn hẳn một route. `src/app.js` CÓ bộ xử lý trả
*"Dữ liệu gửi lên không hợp lệ."* — nhưng nó nằm ở dòng **191**, sau tất cả
`await app.register(routes)` ở 141–168.

Fastify chốt bộ xử lý lỗi cho một route **ngay lúc route được đăng ký**. Mỗi
`await app.register(...)` đăng ký xong route trước khi chạy tiếp, nên mọi
route đã chốt bộ mặc định. Đo thật:

```
POST /v1/device/register  -> "body/fingerprint must NOT have fewer than 64 characters"
POST /v1/flow-blueprints  -> "body must have required property 'sourceType'"
```

**Mọi** lỗi kiểm dữ liệu trong cả API đều trả chuỗi ajv tiếng Anh, và mất
luôn trường `details`. 695 test cũ không bắt được vì chúng chỉ kiểm
`statusCode`, không ai đọc `message`.

**Đã sửa**: chuyển `setErrorHandler` lên TRƯỚC mọi `app.register(routes)`.
Test mới đọc `message` và cấm mọi chuỗi `must NOT`/`must be`/`must have` lọt
ra người dùng, trên hai route khác nhau để chốt đây là lỗi thứ tự đăng ký
chứ không phải lỗi của một route.

> **Bài học lặp lại lần thứ hai trong ngày**: thêm một nhánh mới (cổng 50
> Vox) mà không chạy thử nhánh đó tới cùng. Lần trước là `download_job_result`
> sau khi sửa 2xx. Test xanh không thay thế được một lượt chạy thật trên
> nhánh vừa thêm.

---

## 🟡 Còn mở — agent báo, CHƯA kiểm chứng

> Mã `RS-<n>` = phát hiện của đợt **rà soát**, KHÔNG phải số mini-spec. Tiền
> tố riêng là cố ý: bản đầu dùng `C<n>` và đụng ngay không gian số mini-spec
> đã có của dự án (C1, C2, C6, C17… đều là mini-spec thật) — chốt
> `test_so_mini_spec_khong_trung` bắt được.

Phải **đo trước khi sửa**. Xếp theo mức nghiêm trọng agent gán.

| Mã | Việc | Tệp |
|---|---|---|
| RS-1 | Sửa ràng buộc brand KHÔNG hạ `ready` ⇒ kịch bản chứa cụm mới cấm vẫn `ready` vĩnh viễn | `brand-scripts.js:86` |
| RS-2 | Xoá blueprint/brand chỉ bị phát hiện ở `regenerate`, không ở `GET`/`list` | `brand-scripts.js` |
| RS-3 | Trừ 12 Vox cho blueprint **không đời nào** ra `ready` (thiếu vân tay) | `brand-scripts.js:176` |
| RS-4 | GUI bật lại nút giữa lúc chạy ⇒ trừ tiền hai lần | `brand_script_page.py:289` |
| RS-5 | Sau `409`, GUI giữ trạng thái cũ và mở lại được cổng H4 | `brand_script_page.py:303` |
| RS-6 | Nhánh `409` hạ `blocked` xuống `unconfirmed` — mất phán quyết đã có | `brand-scripts.js:326` |
| RS-7 | `rangBuocKhongDuocNoi` không có `maxItems` | `brand-profiles.js` |
| ~~RS-8~~ | ✅ **ĐÃ SỬA 11/09** — đường dẫn dựng bằng `os.path` | `bao_cao_pilot_phase_h.py` |
| ~~RS-9~~ | ✅ **ĐÃ SỬA 11/09** — hỏi máy chủ trước khi kết luận | `bao_cao_pilot_phase_h.py` |
| RS-10 | Danh sách rỗng vì mất mạng trông y hệt "chưa có gì" | `saas_client.py:848,906` |
| RS-11 | Lỗi kiểm dữ liệu về tới người dùng chỉ còn câu trống không (`details` bị bỏ) | `app.js:153` |
| RS-12 | Bộ chặn sao chép huỷ kết quả nhưng báo "thử lại sau" | `flow-blueprints.js:210` |
| RS-13 | `UsageLog.create(...).catch(()=>{})` ⇒ trần ngày tắt hẳn mà không ai biết | `flow-blueprints.js:261` |
| RS-14 | `doc_chu_may_chu` dựng `SaasClient()` mới thay vì `get_client()` ⇒ đăng ký lại thiết bị mỗi lượt | `doc_chu_may_chu.py:140` |
| RS-15 | Cột "Trạng thái" hiện tiếng Anh (`ready`/`queued`/`failed`) | `flow_blueprint_page.py:368` |
| RS-16 | Ảnh AI của H4d đi qua cửa mà H4b cấm; `bam` bị vứt ⇒ mất phép kiểm C6 | `storyboard_page.py:335` |
| RS-17 | Đoạn không có lời đọc ⇒ `ValueError` không nói đoạn nào | `product_video.py:348` |
| RS-18 | Hết hạn mức **trợ lý** ⇒ vẽ xong mà ảnh nào cũng bị loại (hai trần tách rời) | `ai.js` |
| RS-19 | `_anh_kiem_tam.jpg` để lại trong thư mục ảnh kết quả | `story_image.py:141` |
| ~~RS-20~~ | ✅ **ĐÃ SỬA 11/09** — app TỰ KIỂM: thêm mục «Đóng nhãn chữ lên hình» vào bộ kiểm hệ thống, chạy thật bộ lọc chứ không chỉ hỏi danh sách | `preflight.py` |
| RS-21 | `/story-image` khai `preHandler: requireDevice` trong khi plugin đã có hook ⇒ xác thực hai lần | `ai.js:1267` |
| RS-22 | Ảnh minh hoạ dùng chung khoá giá với ảnh sản phẩm | `ai.js:1288` |

---

## Lát chưa làm, đã biết trước

### D1. Khớp video với GIỌNG ĐỌC THẬT (không chỉ transcript)

Pilot H4 cục bộ đo được: slideshow **19,30s**, video cuối **20,31s** — giọng
thật dài hơn ước lượng **~5%**. Nằm trong ±15% đã ghi ở H4a, và `merge_video`
nới video theo tiếng nên không cụt.

Nhưng hợp đồng H4c-1 chỉ bảo đảm video khớp **transcript**. Muốn khớp giọng
thật thì phải **lấy thời lượng TTS sau khi đọc xong rồi ghép lại** — mỗi đoạn
giữ hình đúng bằng câu nói của nó.

**Chưa làm.** Cần một lát riêng (tạm gọi H4c-3), 0 Vox, sau khi pilot H2→H3
xong.

### D2. Định giá lại theo số liệu thật

Giá 12 Vox của H3 là **phẳng theo số đoạn** trong khi kịch bản 40 đoạn tốn
hơn hẳn 5 đoạn. Máy chủ đã ghi đủ token vào/ra mỗi lượt. Cần **10–20 lượt
thật** rồi mới viết mini-spec định giá. Chủ dự án đã dặn: *"Đừng sửa pricing
trước pilot nếu chưa có token data."*

### D3. Chốt deploy bị webhook đi vòng qua

`sinh-nhanh-deploy` force-push nhánh deploy ở giây thứ 12, webhook Vibe Host
dựng ngay; `trien-khai-prod` (nhánh có ba chốt "chỉ deploy sau khi test
xanh") mãi phút thứ 4 mới chạy. Prod nhận mã **trước khi** test xong.

Ngày 10/09 vô hại vì test đều xanh, nhưng thiết kế đang không bảo vệ được
điều nó tuyên bố. **Đáng một mini-spec riêng, không nên vá vội.**

### D4. Bảo mật vận hành — ⏸ CHỦ DỰ ÁN HOÃN LẠI (11/09)

- Thu hồi token GitHub cũ `…CjoKKY`.
- Hai remote còn nhúng token dạng chữ thường trong URL.

**Đừng tự làm.** Chủ dự án đã quyết hoãn: còn nhiều việc khác đang chạy dở, và
thu hồi token giữa chừng thì chặn luôn đường push/deploy của những việc đó.
Chờ họ báo mới làm — đây là quyết định của họ, không phải mục bị bỏ quên.

---

## Thứ tự đề xuất

1. ~~**B1, B2, B6**~~ ✅ **xong 11/09** — cùng đợt với RS-8, RS-9.
2. **Pilot H2→H3** của chủ dự án. ← **đang ở đây**. Mọi thứ dưới đây nên đợi
   số liệu thật.
3. **RS-1–RS-6** — nhóm H3, đều đụng trạng thái `ready` và tiền. Kiểm chứng từng
   cái trước khi sửa.
5. ~~**B3, B4, B5**~~ ✅ **xong 11/09** — cùng đợt với B7 và lỗi cp1252.
   Còn **RS-15–RS-22** — nhóm trải nghiệm và dọn dẹp.
6. **D1** rồi mới tới **H4d calibration** (sinh ảnh có tính tiền thật).

> **RS-20 ĐÃ XÁC MINH TRÊN WINDOWS THẬT — 11/09/2026 14:33.**
>
> Chủ dự án chạy v3.17.10 trên máy Windows của họ, kết quả:
>
>     [OK] Đóng nhãn chữ lên hình: Dựng được chữ lên khung hình.
>          Đã kiểm lúc 11/09/2026 14:33 bằng:
>          C:\Users\…\VoxDub-Studio-v3.17.10-win64\bin\ffmpeg.EXE
>
> Ba điều con số này chứng minh, và một điều nó KHÔNG chứng minh:
>
> 1. `drawtext` chạy được với bản ffmpeg **đi kèm app** — rủi ro thiếu
>    fontconfig không hiện thực hoá trên bản người dùng đang dùng.
> 2. Bản được kiểm đúng là bản **app sẽ dùng lúc chạy thật**: app nối
>    `bin/` vào PATH lúc khởi động (`app.py:1051`), nên `shutil.which()` của
>    preflight và lệnh `"ffmpeg"` trần lúc ghép video cùng trỏ về một tệp.
> 3. Phần chẩn đoán (đường dẫn + mốc thời gian) làm được đúng việc của nó:
>    không có nó thì "đã kiểm, đạt" không nói được là kiểm bản NÀO.
>
> **Không chứng minh**: máy có sẵn một bản ffmpeg khác trên PATH hệ thống sẽ
> ra sao — PATH hệ thống đứng SAU `bin/` nên ca đó chưa được đo.

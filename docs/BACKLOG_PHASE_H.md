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

### B3. `is_running()` bỏ sót `_bp_worker` — `storyboard_page.py:436`

`shutdown()` có `_bp_worker` nhưng `is_running()` thì không, mà `app.py` chỉ
gọi `shutdown()` cho trang nào `is_running()` trả True. Chính `app.py` ghi:
*"huỷ QThread đang chạy lúc teardown sẽ làm Qt crash cứng (0xC0000409)"*.

**Mức**: trung bình — sập app lúc đóng, hiếm. **Ước**: rất nhỏ.

### B4. Mẻ vẽ ảnh không có nút Dừng — `workers.py`

`SinhAnhMinhHoaWorker` không có `cancel_event` (khác `TranscribeWorker`). Mỗi
ảnh tới 120s vẽ + 90s kiểm; mẻ 5 ảnh có thể chạy 15 phút, `shutdown()` chỉ
chờ 3 giây.

**Mức**: trung bình. **Ước**: nhỏ.

### B5. Thư mục ra đóng cứng `~/VoxDub` — `storyboard_page.py:323,413`

`self._settings_provider` nhận vào rồi **không dùng ở đâu cả**. Trang C1 cùng
loại thì tôn trọng `settings.output_dir`. Người dùng đặt `D:\Videos` thì dự
án vẫn nằm ở `C:\Users\…\VoxDub` và **không hiện ở trang Dự án**.

**Mức**: trung bình. **Ước**: nhỏ.

### ✅ B6. ĐÃ SỬA 11/09 — `UsageLog.create` không bọc `.catch` ở nhánh THÀNH CÔNG — `ai.js:1375`

`Promise.all([remember(...), UsageLog.create({...})])`. `remember()` đã được
làm cho không bao giờ ném (sự cố 22/8), `UsageLog.create` thì chưa — trong
khi nhánh LỖI ngay trên lại có `.catch()`. MongoDB trục trặc giữa `charge` và
ghi sổ ⇒ app nhận 500, ảnh mất, **30 Vox đã trừ**. `/product-scene` cùng dạng.

**Mức**: cao (đụng tiền), xác suất thấp. **Ước**: rất nhỏ.

---

## 🟡 Còn mở — agent báo, CHƯA kiểm chứng

Phải **đo trước khi sửa**. Xếp theo mức nghiêm trọng agent gán.

| Mã | Việc | Tệp |
|---|---|---|
| C1 | Sửa ràng buộc brand KHÔNG hạ `ready` ⇒ kịch bản chứa cụm mới cấm vẫn `ready` vĩnh viễn | `brand-scripts.js:86` |
| C2 | Xoá blueprint/brand chỉ bị phát hiện ở `regenerate`, không ở `GET`/`list` | `brand-scripts.js` |
| C3 | Trừ 12 Vox cho blueprint **không đời nào** ra `ready` (thiếu vân tay) | `brand-scripts.js:176` |
| C4 | GUI bật lại nút giữa lúc chạy ⇒ trừ tiền hai lần | `brand_script_page.py:289` |
| C5 | Sau `409`, GUI giữ trạng thái cũ và mở lại được cổng H4 | `brand_script_page.py:303` |
| C6 | Nhánh `409` hạ `blocked` xuống `unconfirmed` — mất phán quyết đã có | `brand-scripts.js:326` |
| C7 | `rangBuocKhongDuocNoi` không có `maxItems` | `brand-profiles.js` |
| ~~C8~~ | ✅ **ĐÃ SỬA 11/09** — đường dẫn dựng bằng `os.path` | `bao_cao_pilot_phase_h.py` |
| ~~C9~~ | ✅ **ĐÃ SỬA 11/09** — hỏi máy chủ trước khi kết luận | `bao_cao_pilot_phase_h.py` |
| C10 | Danh sách rỗng vì mất mạng trông y hệt "chưa có gì" | `saas_client.py:848,906` |
| C11 | Lỗi kiểm dữ liệu về tới người dùng chỉ còn câu trống không (`details` bị bỏ) | `app.js:153` |
| C12 | Bộ chặn sao chép huỷ kết quả nhưng báo "thử lại sau" | `flow-blueprints.js:210` |
| C13 | `UsageLog.create(...).catch(()=>{})` ⇒ trần ngày tắt hẳn mà không ai biết | `flow-blueprints.js:261` |
| C14 | `doc_chu_may_chu` dựng `SaasClient()` mới thay vì `get_client()` ⇒ đăng ký lại thiết bị mỗi lượt | `doc_chu_may_chu.py:140` |
| C15 | Cột "Trạng thái" hiện tiếng Anh (`ready`/`queued`/`failed`) | `flow_blueprint_page.py:368` |
| C16 | Ảnh AI của H4d đi qua cửa mà H4b cấm; `bam` bị vứt ⇒ mất phép kiểm C6 | `storyboard_page.py:335` |
| C17 | Đoạn không có lời đọc ⇒ `ValueError` không nói đoạn nào | `product_video.py:348` |
| C18 | Hết hạn mức **trợ lý** ⇒ vẽ xong mà ảnh nào cũng bị loại (hai trần tách rời) | `ai.js` |
| C19 | `_anh_kiem_tam.jpg` để lại trong thư mục ảnh kết quả | `story_image.py:141` |
| C20 | `drawtext` không truyền `fontfile` — **phải thử trên Windows đóng gói** | `product_video.py:408` |
| C21 | `/story-image` khai `preHandler: requireDevice` trong khi plugin đã có hook ⇒ xác thực hai lần | `ai.js:1267` |
| C22 | Ảnh minh hoạ dùng chung khoá giá với ảnh sản phẩm | `ai.js:1288` |

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

### D4. Bảo mật vận hành

- Thu hồi token GitHub cũ `…CjoKKY`.
- Hai remote còn nhúng token dạng chữ thường trong URL.

---

## Thứ tự đề xuất

1. ~~**B1, B2, B6**~~ ✅ **xong 11/09** — cùng đợt với C8, C9.
2. **Pilot H2→H3** của chủ dự án. ← **đang ở đây**. Mọi thứ dưới đây nên đợi
   số liệu thật.
3. **C1–C6** — nhóm H3, đều đụng trạng thái `ready` và tiền. Kiểm chứng từng
   cái trước khi sửa.
5. **B3, B4, B5, C15–C22** — nhóm trải nghiệm và dọn dẹp.
6. **D1** rồi mới tới **H4d calibration** (sinh ảnh có tính tiền thật).

> **C20 chỉ kiểm được trên máy Windows đóng gói.** Ở workspace Linux lệnh
> chạy rc=0 vì ffmpeg có fontconfig; bản ffmpeg của người dùng thiếu
> fontconfig thì cả lượt ghép hỏng. Đây là mục **phải nhờ chủ dự án thử**.

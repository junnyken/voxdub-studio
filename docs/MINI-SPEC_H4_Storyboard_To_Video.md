# MINI-SPEC H4 — Từ kịch bản brand thành dự án video

**Ngày soạn**: 10/09/2026 · **Trạng thái**: H4a xong, H4b–H4d chờ duyệt
**Phụ thuộc**: H1, H2, H2a, H2b, H2c, H3 — đã lên production.

> Spec này do **đọc mã hiện tại** mà viết, không viết từ trí nhớ về hệ thống.
> Lý do: spec H3 trước đó có một tiền đề sai ở mức chặn (giả định H2 lưu
> evidence) và phải mất nguyên mini-spec H2c để gỡ. Xem mục A.

## A. Hai tiền đề đã sai, đã sửa

**1. `ProductSceneVideoJob` không tồn tại — và đã cố ý không làm.** Dòng mô
tả H4 trong spec H3 ("nối BrandScript vào ProductSceneVideoJob") mô tả một hệ
thống khác. `docs/ARCH.md` §4 có hẳn một mục cho chuyện này: ngày 21/8/2026
**ba bản đề bài liên tiếp** đều giả định luồng ảnh sản phẩm có thực thể phía
máy chủ (`image_id`, `ProductSceneVideoJob`, `/video-job/{id}/export`), không
cái nào tồn tại, và mục đó kết bằng *"Tài liệu không nói ra thì lần thứ tư sẽ
lặp lại"*. Đây là lần thứ tư.

**Ranh giới thật**: máy chủ chỉ có cửa gọi **lẻ, không trạng thái** (vẽ ảnh,
chấm bao bì, gợi ý câu dẫn). Chọn ảnh, sắp thứ tự, ghép ffmpeg đều chạy trên
máy người dùng. ⇒ **H4 không cần endpoint máy chủ mới nào.**

**2. Trình chỉnh sửa cần VIDEO NGUỒN, không chỉ cần segment.**
`editor.load_work_dir()` đòi ba thứ: thư mục dự án chưa bị `securestore` khoá,
tệp segment đã dịch ở `data/<transcript_name>`, và một video nguồn trong thư
mục. H4 chưa có video nguồn nào — nên nó phải **tự dựng** một bản trình chiếu
ảnh trước, rồi mới giao cho Trình chỉnh sửa.

Đây hoá ra là điều tốt: dựng đúng khuôn dự án thì **toàn bộ máy móc nghe thử /
sửa từng câu / đọc lại / ghép xuất đã có sẵn**, H4 không phải làm lại gì.

## B. Hai quyết định của chủ dự án (10/09)

| Câu hỏi | Đã chọn |
|---|---|
| Ảnh lấy từ đâu | **Hỗn hợp** — có sẵn thì dùng, thiếu mới sinh |
| H4 xuất ra gì | **Dự án mở trong Trình chỉnh sửa**, không phải mp4 bấm-một-nút |

**Hệ quả bắt buộc của "hỗn hợp"**: đường sinh ảnh dùng
`POST /v1/ai/product-scene` — **30 Vox mỗi ảnh**, và cửa đó mặc định `off`
(`image.scene.stage`). Bật nó là **quyết định về tuân thủ**, không phải một cờ
cấu hình: C1/C2 sinh ra vì người bán bị TikTok Shop phạt do ảnh dựng lệch bao
bì. Mọi ảnh SINH RA phải qua `packaging_check` trước khi vào video; ảnh người
dùng tự chọn thì không cần (đó là ảnh của họ).

## B2. Nhân vật: hệ thống KHÔNG đồng bộ được người giữa các cảnh

Câu hỏi của chủ dự án 10/09, và câu trả lời là **không** — hệ thống chưa từng
được dựng để làm việc đó.

Máy sinh ảnh của dự án neo tính nhất quán vào **ảnh sản phẩm thật**:
`prompts/product_scene.js` ra lệnh *"TUYỆT ĐỐI giữ nguyên sản phẩm trong ảnh
gốc… Chỉ thay đổi: bối cảnh xung quanh, mặt bàn/nền, ánh sáng, bóng đổ và góc
máy."* Nhân vật thì **không có ảnh gốc nào để neo**. Sáu bối cảnh dựng sẵn
cũng nói lên điều đó — bối cảnh "người" duy nhất là `tay_cam`: *một bàn tay*,
không có mặt.

Bộ kiểm liền mạch `scene_continuity` cũng không cứu được: nó chỉ xét *cỡ sản
phẩm trong khung, góc máy, tông màu, hướng ánh sáng*, và ghi rõ KHÔNG xét bao
bì (việc của `packaging_check`). Nó **không có khái niệm nhân vật**.

**Chuyện này đã suýt thành thật.** Lượt chạy H3 thật ngày 10/09 sinh ra
visual brief *"cắt nhanh sang cảnh một người mẹ bỉm vừa bế con nhỏ vừa loay
hoay lật chảo"* và *"Khuôn mặt mẹ bỉm lộ rõ vẻ mệt mỏi"*. Sinh ảnh theo đúng
những mô tả đó sẽ ra **bốn người phụ nữ khác nhau đóng cùng một vai**, và
không bộ kiểm nào trong hệ thống bắt được.

### Đã chốt: hướng 1 mặc định, hướng 2 cho ai muốn có người

| Hướng | Cách làm | Trạng thái |
|---|---|---|
| **1 — tránh nhân vật** (mặc định) | `visual_brief` tả bằng **sản phẩm, bàn tay, bối cảnh**; cần người thì chỉ nói VAI TRÒ + HÀNH ĐỘNG, cấm chi tiết nhận dạng | **đã làm** — sửa prompt, `PROMPT_VERSION` 1→2 |
| **2 — người dùng tự đưa ảnh người thật** | Hợp với hướng "hỗn hợp": họ tự quay/chụp, hệ thống chỉ ghép. Nhất quán tuyệt đối vì là người thật | H4c/H4e lo phần gán ảnh |
| 3 — neo nhân vật bằng ảnh tham chiếu | Cần mô hình identity-preserving + một bộ kiểm "còn đúng người không" kiểu `packaging_check` + đo thật | **không làm** — là mini-spec riêng |

Lợi ích kèm theo của hướng 1: ảnh AI có mặt người còn vướng chuyện chân
dung/đồng ý hình ảnh mà `docs/PRD.md` §9 đã ghi là rủi ro mở.

**Kiểm chứng thật sau khi sửa prompt** (cùng brand, cùng bộ khung, Gemini 3.8
thật): **0/5 đoạn** còn tả nhận dạng người. Ví dụ đoạn hook đổi từ *"Khuôn mặt
mẹ bỉm lộ rõ vẻ mệt mỏi"* thành *"một tay người mẹ vừa cầm bình sữa vừa với
tay tắt bếp ga đang xèo xèo chảo mỡ"* — vai trò + hành động, không nhận dạng.

## C. Guardrails

1. **Chỉ kịch bản `ready`.** Đã cài ở H4a — `dung_storyboard()` ném lỗi, ở
   tầng thấp nhất chứ không phải chỉ tắt nút trên giao diện.
2. **Không có đường nào xuất video từ kịch bản `blocked`/`unconfirmed`.**
3. **Ảnh SINH RA mà chưa qua `packaging_check` thì không được vào video.**
   Ảnh người dùng tự chọn không áp luật này.
4. **Không tự ý sinh ảnh.** Thiếu ảnh cho một đoạn thì HỎI người dùng, kèm
   giá. Tự bấm hộ là tiêu tiền của người ta mà không xin phép.
5. **Luôn cho nghe thử trước khi chốt** — Constraint 5 của dự án. Đây chính
   là lý do chọn đầu ra "dự án", không phải mp4.
6. Mọi `except` phải có log/lý do tại chỗ.
7. **Không dựng thực thể job phía máy chủ** (mục A.1).

## D. Phạm vi, chia lát theo mức đốt tiền

### H4a — Storyboard ✅ ĐÃ XONG (10/09)

`autodub/storyboard.py`. Phép tính thuần, **0 Vox, không gọi mô hình**.
Tốc độ đọc **đo bằng chính VieNeu** (giây ≈ 0,39 + 0,504 × âm tiết), kiểm
chéo trên câu chưa từng đo: lệch trung bình 3,3%. Trả về KHOẢNG vì giọng
chênh nhau 1,21 lần. Cảnh báo khi kịch bản lệch nhịp video nguồn ≥1,5 lần.
23 test.

### H4b — Ghép ảnh theo thời lượng riêng (0 Vox)

`product_video.dung_video()` hiện chia **đều** thời lượng cho mọi ảnh. Cần
nhận thời lượng riêng từng ảnh từ storyboard.

- Đổi `_lenh_ghep()` nhận `list[float]` thay vì một `giay_moi_anh`.
- Giữ nguyên `kiem_lai_truoc_khi_xuat()` — nó vẫn là chỗ cuối cùng nói "không".
- Không đụng đường gọi cũ (ảnh sản phẩm C-series vẫn chia đều được).

**Không phụ thuộc pilot** — thuần ffmpeg, không tiền, không mô hình.

### H4c — Dựng dự án cho Trình chỉnh sửa (0 Vox)

Từ storyboard + danh sách ảnh, dựng một thư mục dự án đúng khuôn
`editor.load_work_dir()`:

- video nguồn = bản trình chiếu ảnh (H4b), **chưa có tiếng**;
- `data/<transcript_name>` = một segment mỗi đoạn: `id`, `start`/`end` lấy từ
  storyboard, trường lời đọc = `voiceoverTextVi`, `sub_vi` =
  `captionSuggestionVi`;
- `securestore` KHÔNG khoá (dự án này không đi qua wizard trả phí).

Xong bước này là người dùng bấm mở Trình chỉnh sửa và **mọi thứ có sẵn tự
chạy**: nghe thử từng câu, sửa lời, đọc lại bằng VieNeu (0 Vox, chạy máy),
đổi giọng, xuất video.

**Không phụ thuộc pilot.**

### H4d — Sinh ảnh cho đoạn còn thiếu (30 Vox/ảnh) ⚠ CHỜ PILOT

- Đoạn nào chưa có ảnh thì hiện `visualBriefVi` làm gợi ý và **hỏi** người
  dùng có muốn sinh không, kèm giá cụ thể.
- Ảnh sinh ra bắt buộc qua `packaging_check` (Guardrail 3).
- Cửa `image.scene.stage` phải được bật — quyết định tuân thủ riêng.

**Phụ thuộc pilot H2→H3**: đây là chỗ tiền bị đốt cho mỗi asset và cũng là
chỗ rủi ro pháp lý thành hình. Nếu H3 chặn nhầm hoặc bỏ lọt mà chưa ai chạy
thật lần nào, bước này nhân cái sai lên thành sản phẩm hoàn chỉnh.

### H4e — Giao diện storyboard ⚠ CHỜ H4b/H4c

Hiện dòng thời gian theo đoạn, cho gán ảnh, hiện khoảng thời gian ước lượng
(**khoảng**, không phải một con số), và cảnh báo lệch nhịp. Nút "Mở trong
Trình chỉnh sửa" chỉ sáng khi mọi đoạn đã có ảnh.

Thanh bên đã kín (20 mục) — dùng nhóm `hidden` + lối vào từ trang «Viết kịch
bản», đúng cách H3 đang làm.

## E. Tests

**Đơn vị**: thời lượng riêng từng ảnh vào đúng lệnh ffmpeg; tổng thời lượng
video khớp tổng storyboard; dự án dựng ra `load_work_dir()` đọc được; segment
có đủ `id`/`start`/`end`/lời đọc/phụ đề.

**Hồi quy** (mỗi mục phải ĐỎ khi gỡ chốt):
- Dựng dự án từ kịch bản `blocked` → phải đỏ.
- Ảnh sinh ra chưa qua `packaging_check` mà vào được video → phải đỏ.
- Tự sinh ảnh không hỏi người dùng → phải đỏ.
- `dung_video()` quay lại chia đều thời lượng → phải đỏ.

**Live verification**: dựng một dự án thật từ kịch bản `ready` thật, mở được
trong Trình chỉnh sửa, nghe thử ra tiếng, xuất được video. Không mock.

## F. Success Criteria

1. Kịch bản `ready` → dự án mở được trong Trình chỉnh sửa, có tiếng, có phụ đề.
2. Mỗi đoạn giữ hình đúng thời lượng lời đọc của nó (±15%, đúng khoảng đã đo).
3. Không đường nào (giao diện hay hàm) dựng được video từ kịch bản chưa `ready`.
4. Không ảnh sinh ra nào vào video mà chưa qua kiểm bao bì.
5. Không lượt sinh ảnh nào chạy mà người dùng chưa bấm đồng ý, có thấy giá.

## G. Remaining Limits / Follow-ups

- **Ước lượng thời gian là ƯỚC LƯỢNG.** Sau khi TTS chạy thật, thời lượng
  thật nên thay thế ước lượng và storyboard phải tính lại — nếu không, hình
  và tiếng lệch dần về cuối video. Chưa làm.
- Chưa có nhạc nền, chưa có chuyển cảnh theo nhịp beat (`KIEU_CHUYEN` hiện có
  sẵn vài kiểu nhưng chọn theo tay).
- Giọng đọc chọn thế nào cho từng đoạn (một giọng cả video, hay đổi theo vai)
  — chưa quyết.
- **Pilot H2→H3 vẫn chưa chạy.** H4b/H4c không phụ thuộc, H4d thì có.

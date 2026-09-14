# VoxDub Studio — Trạng thái dự án tới 14/09/2026

> **File này dùng để làm gì.** Dán vào một chatbot/AI khác để nó hiểu dự án
> đang ở đâu trước khi đề xuất nâng cấp. Nó ghi **ba loại thứ khác nhau** và
> cố ý không trộn chúng:
>
> | Nhãn | Nghĩa |
> |---|---|
> | ✅ **XONG, CHẠY THẬT** | Có mã, có test, **và** đã đi qua một lượt chạy thật trên máy người dùng |
> | 🟨 **XONG, CHƯA CHẠY THẬT** | Có mã, có test, chưa lượt nào đi qua mô hình/máy thật |
> | 🔴 **CÒN MỞ** | Chưa làm, hoặc đã đo mà chưa sửa |
> | 🟡 **CHƯA AI ĐO** | Agent/rà soát báo có vấn đề, **chưa kiểm chứng độc lập** |
>
> 🟡 không có nghĩa là sai — nghĩa là **chưa ai đo**. Sửa một thứ chưa đo là
> cách nhanh nhất để sửa nhầm.
>
> Nguồn của file: `docs/BACKLOG_PHASE_H.md`, `FEATURES.md`, `docs/TEST_LOG.md`,
> các `docs/MINI-SPEC_*.md`, và trạng thái git đọc trực tiếp ngày 14/09/2026.

---

## 0. Ảnh chụp nhanh

| | |
|---|---|
| Phiên bản ứng dụng | `3.17.16` (đồng bộ ở `autodub_gui/app.py`, `control_server/package.json`, `website/package.json`) |
| Commit `main` | `5f27e61` — *feat(v3.17.16): E6 đo trên dữ liệu THẬT — 88 → 48 Vox* |
| Đồng bộ remote | ✅ GitHub `main` = `5f27e61` (đã có từ 12/09) · GitLab `origin` đã đẩy kịp 14/09 (`4e152ec..5f27e61`) |
| Cây làm việc | Sạch (không có thay đổi chưa commit) |
| Nhánh deploy | `deploy/vays-control-server` = `1769096`, `deploy/vays-dub-worker` = `4816eba` — CI sinh lại lúc 12/09 14:42 (+0700), **13 giây sau** commit `main` |
| **Prod đang chạy** | ✅ `voxdub-app` trả `/health` = `{"ok":true,"version":"3.17.16","db":"đã kết nối"}` — kiểm 14/09 |
| Quy mô mã | `autodub/` ~28k dòng · `autodub_gui/` ~30k dòng (22 trang) · `control_server/` ~12k dòng · `website/` ~7k dòng |
| Tệp test | 246 tệp pytest + 68 tệp test Node + 8 tệp test React |

**Số lượng test — ĐO THẬT 14/09** (trước đó `FEATURES.md` tự mâu thuẫn: đầu
tệp ghi *2.823 Python + 700 Node*, §10 ghi *2.449 + 542* — không con số nào
đúng, đã sửa cả hai):

| | Đạt | Bỏ qua | Hỏng |
|---|---|---|---|
| Python (`pytest`) | **2.851** | 4 | 0 |
| Node (`npm test`) | **713** | 1 | 0 |
| React (`website`) | 74 | 0 | 0 |

4 test Python bỏ qua chỉ có nghĩa trên Windows. Con số này tăng gần như mỗi
đợt — dùng để hình dung quy mô, đừng dùng làm mốc đối chiếu.

---

## 1. ✅ Đồng bộ & triển khai — ĐÃ XÁC MINH 14/09, không còn chặn

> **Sửa một khẳng định sai của chính bản nháp trước.** Bản đầu của file này viết
> *"7 commit chưa push ⇒ prod vẫn chạy mã trước v3.17.12"*. **Sai.** Bản nháp đó
> chỉ so với remote `origin` (GitLab) mà không so với `github` — trong khi CI và
> deploy đều chạy từ **GitHub**. Giữ lại đoạn này vì đó đúng là bẫy hai-remote mà
> dự án đang mang (xem D4).

Trạng thái thật, đo ngày 14/09:

| Kiểm | Kết quả |
|---|---|
| GitHub `main` | `5f27e61` — đủ cả 7 commit, có từ 12/09 |
| GitLab `origin` (mirror) | tụt 7 commit → **đã đẩy 14/09** (`4e152ec..5f27e61`) |
| CI sinh lại nhánh deploy | ✅ `1769096` / `4816eba`, lúc 12/09 14:42:29 (+0700) |
| Nhánh deploy mang mã nào | ✅ `control_server/package.json` = `3.17.16`; `setErrorHandler` ở dòng 154, **trước** mọi `app.register(routes)` (dòng 173+) — tức bản vá E8 có trong mã đã deploy |
| Vibe Host | `voxdub-app` deploy 12/09 **14:48**, `voxdub-dub-worker` **14:53** — đều sau commit `main` 14:42 |
| `/health` prod | `{"ok":true,"version":"3.17.16","db":"đã kết nối","uptimeS":153726}` (~42,7 giờ ⇒ khớp mốc 12/09 14:48) |

**Kiểm chứng E8 bằng hành vi thật, không chỉ bằng chuỗi phiên bản** — gọi thẳng
prod với dữ liệu sai:

```
POST /v1/device/register  {"fingerprint":"qua-ngan"}
→ {"code":"VALIDATION_ERROR",
   "message":"Dữ liệu gửi lên không hợp lệ.",
   "details":["/fingerprint must NOT have fewer than 64 characters"]}

POST /v1/flow-blueprints  {}
→ {"code":"VALIDATION_ERROR",
   "message":"Dữ liệu gửi lên không hợp lệ.",
   "details":["body must have required property 'jobId'"]}
```

Trước v3.17.15, `message` chính là chuỗi ajv tiếng Anh và **không có** `details`.
Nay câu tiếng Việt ra tới người dùng, phần kỹ thuật lui về `details`. ⇒ **E1, E2,
E4, E8 đã live trên prod từ 12/09.**

> **Bài học của chính lượt này**: so `main` với *một* remote rồi kết luận về prod
> là đúng loại lỗi §4.4 — tự viết đè hợp đồng của hệ thống thay vì hỏi nó. Câu
> trả lời đáng tin duy nhất là `/health` + một lượt gọi thật, và cả hai đều rẻ.

## 2. Đã đi tới đâu — theo giai đoạn

### 2.1 Lõi sản phẩm (Phase A→G) — ✅ chạy thật

- Lồng tiếng video 8 bước (tải → tách nhạc → chép lời → dịch → tạo giọng →
  ghép), Trình chỉnh sửa, các công cụ tách rời (chép lời, dịch phụ đề, quản lý
  giọng nhân vật xuyên tập), CLI.
- Hai chế độ: chạy trên máy (miễn phí) vs có tài khoản (SaaS, tính **Vox**,
  1 Vox = 10 VNĐ). Cổng duy nhất phân biệt: `saas_client.is_configured()`.
- **G1→G3 (08/09)**: "nghe chép thiếu câu" đã **tái hiện được và sửa thật** —
  Silero VAD `threshold=0.5` coi cả đoạn 38 giây là im lặng; hạ xuống 0.3 ở cả
  3 nơi + tự dò khoảng trống bất thường rồi nghe lại tắt VAD. Verify bằng
  `transcribe()` production trên đúng video đã lỗi.
- **C69**: NLLB dừng sớm/bịa câu — sửa bằng `min_decoding_length` theo độ dài
  câu nguồn (đổi lại chậm hơn ~10%).
- **C45/C55**: mỗi push `main`, CI chạy **một lượt dub THẬT trên runner
  Windows**, trước mỗi lần phát hành đi tới tận video xuất ra và soi tệp (có
  tiếng không, có câm không, thời lượng khớp nguồn không).

### 2.2 Phase H — "Viral Flow Clone & Brand Rewrite" (bắt đầu 08/09)

Mục tiêu: học **nhịp/cấu trúc** video viral (KHÔNG chép câu chữ) → viết lại
kịch bản theo hồ sơ brand → dựng thành video.

| Mã | Việc | Trạng thái |
|---|---|---|
| H1 | Hồ sơ Brand (multi-tenant theo thiết bị) | ✅ **XONG, CHẠY THẬT** |
| H2a | Lớp ĐỌC nội dung chữ OCR (`read_text_regions()`) | ✅ XONG |
| H2 | Viral Flow Blueprint — phân tích vai trò kể chuyện từng đoạn | ✅ **XONG, CHẠY THẬT** |
| H2b | Đọc chữ overlay **có dấu** tiếng Việt qua máy chủ | ✅ **XONG, KIỂM CHỨNG THẬT** |
| H2c | Dấu vân tay một chiều của bằng chứng (cho H3 kiểm trùng) | ✅ XONG |
| H3 | Viết kịch bản cho thương hiệu + 2 lớp guardrail | ✅ XONG (chưa qua pilot đủ) |
| H4/H4a-c | Storyboard → dự án mở được trong Trình chỉnh sửa, 0 Vox | ✅ XONG (pilot cục bộ đã chạy thật) |
| H4d | Sinh ảnh minh hoạ 30 Vox/ảnh | 🟨 **XONG mã, CHƯA CHẠY THẬT** — cửa `image` chưa có nhà cung cấp |

**Giới hạn đã ĐO, phải biết trước khi đề xuất gì đụng OCR:**
- RapidOCR bundled (`ch_PP-OCRv4`) **đọc tiếng Việt mất dấu**, mà confidence
  vẫn báo 0,90–0,99 ⇒ **không có tín hiệu tự động nào bắt được lỗi này**.
- Caption dưới 1 giây cần lấy mẫu dày hơn hẳn mức dùng cho làm mờ; chi phí
  ~1,23 giây/khung trên CPU.

### 2.3 Ba lượt chạy thật của chủ dự án (11–12/09) và thứ chúng lôi ra

Mỗi lượt chạy thật tìm ra lỗi mà **toàn bộ test xanh không bắt được**:

| Lượt | Triệu chứng người dùng thấy | Nguyên nhân thật |
|---|---|---|
| 10/09 | *"Lỗi máy chủ (HTTP 201)"* | `201 Created` bị coi là lỗi — chặn toàn bộ Phase H |
| 11/09 | Phân tích sập giữa chừng | Lỗi `cp1252` khi đọc đầu ra tiến trình con (chỉ xảy ra trên Windows) |
| 12/09 #1 | *"Không phân tích được lúc này"* | E2: OCR đọc ra `hóa đơn` (đúng chủ đề video) ⇒ luật chống-chép huỷ sạch kết quả |
| 12/09 #2 | Mất **88 Vox** trong khi màn hình hứa *"khoảng 32 Vox"* | E3: giá phụ thuộc **lượng chữ trên hình**, không phải số giây |
| 12/09 #3 | Bấm «Bỏ qua, không tốn Vox» rồi vẫn `must NOT have more than 400 items` | E7: nhánh RẺ vừa thêm là nhánh duy nhất chưa ai chạy thử tới cùng |

Đã sửa hết ở v3.17.13–3.17.16 (**nhưng xem mục 1 — chưa push**), kèm:
- Cổng xin phép khi vượt **50 Vox**, đặt ở tầng hàm nên CLI/script cũng bị chặn.
- Câu báo giá nói đúng đại lượng (30–100 Vox tuỳ lượng chữ).
- `gioi_han_bang_chung()` phía máy khách, trần khớp máy chủ, **cắt rải đều
  dòng thời gian** chứ không cắt đuôi.

### 2.4 E6 — cắt chi phí OCR: cắt được TIỀN, **chưa** cắt được THỜI GIAN

Đo trên dữ liệu thật của chủ dự án (12/09, 104 mốc, 65 đoạn, 36,2 giây):

```
12:37:44 → 12:40:57   OCR tại máy, 104 khung   3 phút 13 giây   (84%)
12:40:57 → 12:41:35   gửi máy chủ, 11 lô            38 giây     (16%)
```

- **D1 (bỏ đoạn OCR trùng lời đọc) — BỊ BÁC BỎ**: chỉ 10/65 = 15% trùng, tiết
  kiệm đúng 8 Vox. Phần lớn chữ trên hình là ảnh chụp phần mềm, không phải phụ
  đề lặp lời.
- **D5 (gộp khung liền nhau khi chữ GẦN GIỐNG, ngưỡng 80%) — ĐÃ DỰNG**:
  65 → 35 đoạn, **88 → 48 Vox (giảm 46%)**. Soi tay cả 17 nhóm gộp: không nhóm
  nào gộp nhầm. Đại diện mỗi đoạn là khung **đọc rõ nhất**, không phải khung đầu.
- 🔴 **C.4 CÒN MỞ**: tệp đo thật **không có** `khoi_dong_s`/`quet_s` dù mã đã
  có từ v3.17.14 — chưa rõ vì sao. Không tách được "nạp mô hình" (chi phí cố
  định) khỏi "quét khung" (co theo số khung) ⇒ **không trả lời được câu quyết
  định: cắt khung có nhanh lên không**. D3 (giảm mật độ lấy mẫu) là đòn bẩy duy
  nhất chạm tới thời gian, và nó chờ đúng con số này.

---

## 3. 🔴 Còn gì chưa làm

### 3.1 Việc của con người, không phải việc lập trình (chặn nhiều tính năng nhất)

| Việc | Đang chặn cái gì |
|---|---|
| Tạo bản ghi **nhà cung cấp cho vai `assist`** trong trang quản trị | Toàn bộ cổng trợ lý (7 tác vụ) — hiện dùng chung vai `translate`, **đắt hơn ~25 lần** |
| Tạo bản ghi **nhà cung cấp cho vai `image`** | Sinh ảnh sản phẩm · cổng kiểm tuân thủ · trang «Ảnh sản phẩm» · **H4d** |
| Chuyển chốt `image.scene.stage` TẮT → `calibration`, chạy 20–30 ảnh thật, soi tay từng phán quyết, rồi mới `production` | Mở tính năng ảnh |

> Mọi đề xuất kiểu *"hãy viết mã để nối nhà cung cấp thật"* là đề xuất viết mã
> cho một lỗ hổng **không tồn tại**. Đây là hai dòng cấu hình trong trang quản trị.

### 3.2 Pilot H2→H3 — **đang ở đây trong thứ tự ưu tiên**

Runbook: `docs/PILOT_PHASE_H.md`. Cần **hai video** (một có caption Việt cháy
sẵn để kiểm H2b đọc đúng dấu; một tiếng Anh có cấu trúc bán hàng rõ để đánh
giá chất lượng phân tích nhịp). Chạy trên **máy Windows** — workspace Linux
không chạy được app desktop. Chi phí ước tính: 60–80 Vox cho một pilot đủ hai
ca gate.

Bốn cổng phải đóng trước khi mở H4. Mọi việc ở mục 3.3 nên **đợi số liệu của
pilot này**.

### 3.3 ✅ RS-1 → RS-22 — ĐÃ XỬ LÝ 14/09, còn đúng 1 mục mở

22 mục rà soát, kết cục thật sau khi **kiểm chứng độc lập từng cái**:

| Kết cục | Số mục | Mã |
|---|---|---|
| Đã sửa (trước 14/09) | 3 | RS-8, RS-9, RS-20 |
| **Đã sửa 14/09** | **17** | RS-1…RS-7, RS-10, RS-13, RS-14, RS-15, RS-17, RS-18, RS-19, RS-21, RS-22 |
| Hoá ra đã xong từ trước | 2 | RS-11 (do E8), RS-12 (do E1) |
| **Còn mở, cố ý** | **1** | **RS-16** |

**Hai mô tả trong backlog là SAI, đã sửa lại tại chỗ:**

- **RS-13** ghi *"trần ngày tắt hẳn mà không ai biết"* — **không đúng**.
  `ghiSoDung()` đã tự bắt lỗi và ghi nhật ký, nên `.catch(()=>{})` bên ngoài
  không bao giờ chạy. Trần ngày không hề tắt. Phần thật nhỏ hơn nhiều (mã
  chết gây hiểu lầm + không truyền `request.log`).
- **RS-14** ghi *"đăng ký lại thiết bị mỗi lượt"* — **không đúng**. Token nằm
  trong kho khoá hệ điều hành nên bản máy khách mới vẫn đọc ra token cũ. Phần
  thật: phiên HTTP thừa + không chịu ảnh hưởng `reset_client()`.

> Đây đúng là lý do backlog phân biệt 🔴 (tự kiểm chứng) với 🟡 (chưa ai đo).
> Sửa theo lời mô tả của một mục 🟡 là cách nhanh nhất để "chữa" một lỗi không
> tồn tại rồi ghi vào nhật ký rằng đã chữa.

**🔴 RS-16 — mục duy nhất còn mở, và là mục CỐ Ý chưa sửa.**

`storyboard_page._ve_anh_xong()` chỉ giữ ĐƯỜNG DẪN ảnh, vứt `phan_quyet`,
`da_kiem`, `da_dong_nhan`, `bam`. `DungDuAnWorker` nhận một danh sách chuỗi,
nên `kiem_lai_truoc_khi_xuat()` **không thể chạy** — vi phạm đúng một cảnh
báo đã viết sẵn trong mã từ trước khi H4d tồn tại.

Sửa đúng nghĩa là mang phán quyết + băm xuyên qua lớp dựng dự án tới bước
Xuất, tức đổi hợp đồng của `DungDuAnWorker` và của tệp dự án — **một lát
thiết kế, không phải một bản vá**. Vá vội một cổng TUÂN THỦ là cách tệ nhất
để đóng nó.

**Rủi ro thực tế hiện bằng 0**: `image.scene.stage` mặc định `off`, chưa máy
nào sinh được ảnh minh hoạ AI. Nhưng cổng này **phải đóng trước** khi chốt đó
chuyển sang `calibration` — xem mục 3.1.

### 3.4 🔴 Lát đã biết trước, chưa làm

| Mã | Việc | Chặn bởi |
|---|---|---|
| D1 | Khớp video với **giọng đọc thật** (hiện chỉ bảo đảm khớp transcript; đo thật lệch ~5%) | Cần lát riêng H4c-3, 0 Vox, **sau** pilot H2→H3 |
| D2 | Định giá lại theo số liệu thật (H3 đang tính **phẳng** 12 Vox bất kể 5 hay 40 đoạn) | Cần **10–20 lượt thật**. Chủ dự án đã dặn: *"Đừng sửa pricing trước pilot nếu chưa có token data"* |
| D3 | Chốt deploy bị webhook đi vòng qua — `sinh-nhanh-deploy` force-push ở giây 12, webhook dựng ngay; `trien-khai-prod` (có 3 chốt "chỉ deploy sau khi test xanh") mãi phút 4 mới chạy ⇒ **prod nhận mã trước khi test xong** | Đáng một mini-spec riêng, không nên vá vội |
| D4 | Bảo mật vận hành: thu hồi token GitHub cũ `…CjoKKY`; 2 remote còn nhúng token trong URL | ⏸ **CHỦ DỰ ÁN ĐÃ HOÃN (11/09)** — thu hồi giữa chừng sẽ chặn đường push/deploy của việc đang chạy dở. **Đừng tự làm** |

### 3.5 🔴 Chưa từng kiểm chứng

- Che chữ trên video **DÀI** (~40 phút) chưa ai chạy thật — lấy mẫu ~2
  phút/khung **có thể lọt** chữ chỉ hiện 30 giây. Kế hoạch đo: `docs/KE-HOACH-KIEM-C50-C52.md`.
- Chưa chạy **tải đồng thời** nhiều lượt (`claimNextJob` đúng theo lý thuyết
  Mongo nhưng chưa chạy N tiến trình song song thật).
- ~190/204 mã ngôn ngữ FLORES chưa kiểm chất lượng — **đừng nói "hỗ trợ 204 ngôn ngữ"**.
- Bản `.exe` đóng gói chỉ có smoke test khởi động; lượt dub thật của CI chạy từ
  **mã nguồn**, không phải từ gói. Và **không có gì kiểm chất lượng** — chỉ kiểm đường chạy.
- Một lượt test đầy đủ **thỉnh thoảng core dump lúc dọn dẹp** (nghi Qt dọn
  luồng khi thoát); chạy lại ngay là xanh, chưa tái hiện được theo ý muốn.

### 3.6 Cần con người quyết định

- Có thu thập thêm dữ liệu sử dụng không (đã hỏi — chủ dự án chọn giữ nguyên phạm vi).
- Có kiểm soát việc sao chép giọng người thật không (rủi ro đã ghi nhận, chủ dự
  án xác nhận chưa can thiệp ở đợt này).

---

## 4. Bảy bẫy đã lặp lại — đọc trước khi đề xuất bất cứ điều gì

1. **Import engine nặng trong tiến trình chính.** Mọi `import faster_whisper`
   / torch / demucs / PIL chạy ở tiến trình chính **không bao giờ chạy được ở
   bản phát hành** — chúng sống trong `.venv-*` riêng, gọi qua tiến trình con.
   Lỗi này đã lặp **bốn lần**.
2. **Test xanh không thay thế được một lượt chạy thật.** Cả 5 lỗi nghiêm trọng
   nhất tháng 9 đều đến từ ảnh chụp màn hình của chủ dự án, không từ test.
3. **Thêm một nhánh mới mà không chạy thử nhánh đó tới cùng** — lặp hai lần
   trong một ngày (12/09): `download_job_result` sau khi sửa 2xx, rồi cổng 50
   Vox ⇒ nhánh «Bỏ qua» (nhánh RẺ) là nhánh duy nhất hỏng.
4. **Máy khách viết đè hợp đồng máy chủ** — `201` bị coi là lỗi; `429` nuốt cả
   `code` lẫn `message`; `AiError` có `code` riêng bị ném đi rồi đoán lại.
5. **Đo trước khi đặt ngưỡng — và một điểm sạch duy nhất nghĩa là phép đo còn
   sai.** E5: ngưỡng 45% sạch 0/15 nhưng nằm đúng trên ranh ⇒ đó là dấu hiệu
   phép đo chưa tách được hai lớp, không phải đã tìm ra ngưỡng.
6. **Đếm "từ" bằng khoảng trắng.** `NGUONG_TU_LIEN_TIEP = 6` hiệu chỉnh trên
   tiếng Anh; tiếng Việt tách theo âm tiết nên **cùng con số lại chặt gấp đôi**.
7. **Chữa một lỗi chẩn đoán bằng một lỗi chẩn đoán nặng hơn.** Bản sửa E4 đầu
   tiên tự viết hook và **làm mất dòng ghi mức `error`** — đúng thứ quý nhất.

Thêm: máy thiếu thư viện hệ thống Qt thì hàng loạt tệp test giao diện bị bỏ qua
**ngay ở tầng nạp module** — `pytest` báo xanh với con số thấp hơn mà không kêu
một tiếng (từng báo "1790 đạt" trong khi số thật là 1954). **Thấy tổng số tụt
thì nghi môi trường trước khi nghi mã.**

---

## 5. Thứ tự đề xuất cho bước tiếp theo

1. ~~**Push + CI + kiểm `/health`.**~~ ✅ **XONG 14/09** — xem §1. Prod chạy
   `3.17.16`, E8 xác minh bằng lượt gọi thật; GitLab mirror đã đuổi kịp.
2. **Chạy pilot H2→H3** theo `docs/PILOT_PHASE_H.md` (hai video, máy Windows,
   60–80 Vox). Đây là cổng chặn: mọi việc dưới đây nên đợi số liệu của nó.
3. ~~**Lần ra C.4**~~ ✅ **XONG 14/09** — nguyên nhân: **worker chạy thật là bản
   CŨ**, chứng minh từ chính tệp chẩn đoán. Đã bịt chỗ im lặng (worker khai
   đời, cha ghi đường dẫn). **Vẫn chưa có SỐ ĐO** — cần một lượt chạy trên bản
   mới, rồi D3 mới quyết được.
4. ~~**RS-1 → RS-22**~~ ✅ **XONG 14/09** trừ **RS-16** (xem 3.3) — RS-16 phải
   đóng TRƯỚC khi bật `image.scene.stage` sang `calibration`.
6. **D1** (khớp giọng thật), rồi mới tới **hiệu chỉnh H4d** (sinh ảnh có tính
   tiền thật) — và H4d còn chờ thao tác quản trị ở mục 3.1.
7. **D2** (định giá lại) sau khi có 10–20 lượt thật.
8. **D3** (chốt deploy) — mini-spec riêng.

---

## 6. Tài liệu để đọc sâu hơn

| Tệp | Nội dung |
|---|---|
| `FEATURES.md` | Bản mô tả tính năng viết riêng cho AI đọc — có §4 "đã dựng nhưng chưa chạy thật" và §8 "những nhầm lẫn thường gặp khi đề xuất" |
| `docs/BACKLOG_PHASE_H.md` | Mọi phát hiện Phase H còn mở, có trạng thái thật (đã sửa / đã tự kiểm chứng / chưa ai đo) |
| `docs/PILOT_PHASE_H.md` | Runbook pilot H2→H3 + bốn cổng phải đóng trước khi mở H4 |
| `docs/MINI-SPEC_E6_Bot_Khung_OCR.md` | Bảng đòn bẩy D1–D5 và ngưỡng, kèm chỗ C.4 còn trống |
| `docs/TEST_LOG.md` | Nhật ký từng đợt: đã kiểm gì, lỗi nào tự tìm ra, còn tồn gì |
| `docs/API.md` · `docs/ARCH.md` · `docs/PRD.md` | Hợp đồng API · kiến trúc · yêu cầu sản phẩm |
| `docs/PLAN.md` | Toàn bộ ~95 mini-spec, Phase A→H |

---

*Lập 14/09/2026 bởi trieunt. Trạng thái git và phiên bản đọc trực tiếp từ repo
trong ngày; số lượng test **chưa chạy lại trong phiên này** — xem cảnh báo ở §0.*

# MINI-SPEC H4d — Sinh ảnh minh hoạ cho đoạn còn thiếu

**Ngày soạn**: 10/09/2026 · **Trạng thái**: đang dựng
**Phụ thuộc**: H4a–H4c, H4e (đã lên `main`), C1/C2 (cửa ảnh), V89 (cổng trợ lý)

> Spec này viết SAU khi đọc mã, không viết từ trí nhớ. Xem mục A — dòng mô tả
> H4d trong spec H4 mô tả một hệ thống không tồn tại, đây là **lần thứ năm**
> mắc đúng lớp sai lầm mà `docs/ARCH.md` §4 đã đếm.

## A. Tiền đề sai trong spec H4

Spec H4 mục D viết: *"Đoạn nào chưa có ảnh thì hiện `visualBriefVi` làm gợi ý
và hỏi người dùng có muốn sinh không"*. Điều đó ngụ ý có một đường **sinh ảnh
từ chữ**. Không có.

Đường sinh ảnh duy nhất của dự án là `POST /v1/ai/product-scene`, và nó:

| Ràng buộc | Vị trí |
|---|---|
| `required: ['jobId', 'scene', 'image']` — bắt buộc **ảnh sản phẩm thật** | `routes/ai.js` |
| `scene` phải thuộc **enum 6 bối cảnh dựng sẵn** | `routes/ai.js` |
| Câu lệnh luôn là *"dựng lại **ảnh sản phẩm này** {bối cảnh}"* | `prompts/product_scene.js` |
| `note` (≤300 ký tự) chỉ được nối thêm ở cuối, không thay câu lệnh chính | `prompts/product_scene.js` |

Và cả **bốn** giao thức vận chuyển đều bắt buộc ảnh vào — `google` nhét
`inlineData`, `openrouter_images` nhét `input_references`, `custom_images`
điền `image_data_uri`/`image_base64`/`image_mime` vào mẫu, còn `openai_images`
gọi thẳng `/images/**edits**` với ghi chú tại chỗ: *"Dùng SỬA ẢNH, không phải
sinh ảnh mới: `/images/generations` không nhận ảnh vào, nên sản phẩm sẽ do mô
hình bịa ra hoàn toàn."*

⇒ `visualBriefVi` **không có cửa nào để vào**. H4d như spec mô tả không dựng
được bằng cách sửa cờ; nó cần một đường vận chuyển mới.

## B. Quyết định của chủ dự án (10/09)

Đã hỏi, kèm nguyên văn ba lựa chọn và hệ quả của từng cái.

| Câu hỏi | Đã chọn |
|---|---|
| Dùng cửa C1 sẵn có (ảnh sản phẩm + 6 nền) hay thêm đường sinh ảnh tự do | **Thêm đường sinh ảnh tự do** |
| Bật cửa `image.scene.stage` tới nấc nào | **Giữ `off`** — dựng mã, test cục bộ, không tiêu Vox thật |

Nghĩa là lát này **không chạy live**. Ai bật cửa sau đó là một quyết định
riêng, có mục riêng ở phần G.

## C. Bề mặt tuân thủ MỚI, và luật thay thế

`packaging_check` so ảnh mới với **ảnh gốc** để trả lời *"còn là sản phẩm thật
không"*. Ảnh minh hoạ **không có ảnh gốc** — nên bước kiểm đó không kiểm được
gì. Guardrail 3 của H4 (*"ảnh sinh ra phải qua `packaging_check`"*) không áp
được nguyên văn, và bỏ trống nó thì H4d thành lỗ hổng chứ không phải tính năng.

**Vì sao ảnh minh hoạ vẫn nguy hiểm**, dù không đụng bao bì thật: nó nằm trong
**cùng một video bán hàng**, cạnh sản phẩm thật. Mô hình vẽ ra một hộp, chai
hay gói có nhãn — dù nhãn bịa — thì người xem lẫn máy quét thị giác của TikTok
đều thấy "sản phẩm" trong video quảng bá. Đó đúng là *quảng bá sản phẩm không
nhất quán*, cùng một điều khoản đã đẻ ra C1.

**Luật thay thế**: ảnh minh hoạ **KHÔNG được chứa sản phẩm có nhãn, bao bì có
thương hiệu, logo, hay chữ đọc được**. Cấm trong câu lệnh, và kiểm lại sau khi
sinh — vì câu lệnh một mình không đủ (bài học «Đo trước khi tin prompt»: chỉ
1/3 luật viết trong prompt thật sự có tác dụng).

## D. Guardrails

1. **Ảnh minh hoạ không được chứa sản phẩm/nhãn/logo/chữ đọc được.** Cấm
   trong prompt **và** kiểm lại bằng tác vụ chữ sau khi sinh. Trượt kiểm thì
   ảnh **không được vào video** — không phải chỉ dán nhãn rồi cho qua.
2. **Mọi ảnh sinh ra phải đóng nhãn "AI-generated"** nhìn thấy được. Đóng hụt
   thì ảnh chỉ để xem, không ghép.
3. **Không tự sinh.** Giữ nguyên Guardrail 4 của H4: hỏi, kèm giá cụ thể.
4. **Dùng CHUNG cửa `image.scene.stage`.** Không mở cửa thứ hai lỏng hơn cho
   cùng một loại rủi ro.
5. **Dùng CHUNG trần ngày `image.daily.limit`.** Đếm gộp cả hai loại ảnh —
   tách trần là mở đường lách trần.
6. **Nói trước rằng người trong ảnh sẽ KHÁC nhau giữa các đoạn** (mục B2 của
   H4: hệ thống không có khái niệm nhân vật). Để người dùng tự phát hiện sau
   khi đã trả tiền là cách tệ nhất để họ biết điều đó.
7. Mọi `except` có log/lý do tại chỗ.

## E. Phạm vi, chia lát

### H4d-1 — Máy chủ: đường sinh ảnh từ chữ

- `prompts/story_image.js` — câu lệnh, kèm phần cấm của Guardrail 1.
- `image-transport.service.js`: thêm `dungYeuCauTuChu({provider, prompt})`.
  `openai_images` chuyển sang `/images/generations`; `google` bỏ phần
  `inlineData`; `openrouter_images` bỏ `input_references`; `custom_images`
  chỉ điền `prompt` — mẫu nào đòi `{{image_*}}` thì **từ chối tại chỗ**, chứ
  không gửi đi một thân yêu cầu thiếu biến.
- `ai-gateway.service.js`: `generateStoryImage({ brief, chiDinh })`.
- Tác vụ chữ `kiem_anh_minh_hoa` trong `prompts/assist.js` — nhận 1 ảnh, trả
  `{ value: 'DAT' | 'CO_SAN_PHAM', reason }`.
- `POST /v1/ai/story-image` — cùng cửa C2, cùng trần ngày, cùng `precheck`,
  `action: 'story_image'` (thêm vào enum `JobResult`/`UsageLog`).

### H4d-2 — Máy khách: gọi, kiểm, đóng nhãn

`autodub/story_image.py` — `sinh_anh_minh_hoa(brief, thu_muc_ra, khach=None)`
đi đúng ba bước **sinh → kiểm → đóng nhãn**, cùng khuôn `KetQua` của C1 để
nhật ký tra soát đọc được bằng một bộ mắt.

### H4d-3 — Giao diện

Nút **«Sinh ảnh cho đoạn này»** trên trang Dựng video, hộp xác nhận kèm giá và
câu cảnh báo của Guardrail 6. Test `test_trang_KHONG_co_duong_sinh_anh` của
H4e **sẽ đỏ — đúng như nó tự dự báo** — và được viết lại thành *"không sinh
được nếu chưa xác nhận có thấy giá"*.

## F. Tests

**Máy chủ**: mẫu `custom_images` đòi biến ảnh thì bị từ chối, không gửi đi;
`openai_images` đi `/images/generations` chứ không phải `/edits`; cửa `off`
chặn trước cả `replay`; trần ngày đếm gộp `product_scene` + `story_image`;
ảnh trượt `kiem_anh_minh_hoa` không được trả về là dùng được.

**Máy khách**: kiểm hỏng ⇒ ảnh không dùng được (nghiêng về an toàn như C1);
đóng nhãn hụt ⇒ không dùng được; đường sinh KHÔNG chạy khi chưa xác nhận.

**Không mock `gateway`** ở chỗ đang kiểm chính bộ chuẩn hoá — bài học H3.

## G. Remaining Limits

- **Chưa chạy thật lần nào.** Cửa `image.scene.stage` vẫn `off` theo quyết
  định ở mục B. Mọi con số chất lượng ảnh trong tài liệu này sẽ là con số
  **chưa đo** cho tới khi có người bật cửa và chạy.
- **Pilot H2→H3 vẫn chưa chạy.** Spec H4 đặt H4d sau pilot vì đây là chỗ tiền
  bị đốt cho mỗi asset. Chủ dự án chọn làm trước; giữ cửa đóng là thứ bù lại.
- Người trong các ảnh sẽ khác nhau giữa các đoạn — giới hạn kiến trúc (H4 §B2),
  không sửa được ở lát này. Đã nói ra trong hộp thoại trước khi trừ tiền.
- **Khung 9:16 chỉ là lời dặn trong câu lệnh**, không phải tham số kích thước.
  `openai_images` có tham số `size` riêng mà đường này không đặt — mô hình nghe
  lời dặn tới đâu thì chưa đo được, vì cửa còn đóng. Ảnh ra lệch tỉ lệ thì
  `product_video` vẫn ghép được, chỉ là có viền.
- **Không có bước kiểm liên tục giữa các ảnh minh hoạ.** `scene_continuity`
  xét cỡ sản phẩm trong khung — ảnh minh hoạ không có sản phẩm nên nó không
  nói được gì. Mỗi ảnh vẫn là một lượt gọi độc lập, tông màu và ánh sáng có
  thể trôi mỗi ảnh một kiểu. Đây là chuyện xem có mượt hay không, không phải
  chuyện bị sàn phạt, nên để lại chứ không chặn.
- **Một bản khai `custom_images` chỉ phục vụ được một trong hai đường.** Cần
  cả dựng bối cảnh lẫn vẽ minh hoạ thì phải thêm hai bản khai. Đã nói rõ trong
  thông báo lỗi thay vì để người cấu hình đoán.

## H. Đã dựng những gì (10/09)

| Lát | Tệp chính | Test |
|---|---|---|
| H4d-1 máy chủ | `prompts/story_image.js`, `dungYeuCauTuChu()`, `generateStoryImage()`, tác vụ `kiem_anh_minh_hoa`, `POST /v1/ai/story-image` | `tests/story-image.test.js` (14) |
| H4d-2 máy khách | `autodub/story_image.py`, `saas_client.story_image()` | `tests/test_story_image.py` (16) |
| H4d-3 giao diện | `storyboard_page` — nút vẽ theo dòng + hàng loạt, hộp xác nhận có giá | `tests/test_storyboard_page.py` (+9) |

Vòng thử nơi gọi mô hình tách thành `_sinhAnhQuaCacNoi()` dùng chung cho cả
hai đường; chốt "chặn trước khi gọi mạng" nay xét hàm dùng chung **và** bắt
buộc cả hai đường đi qua nó — chặt hơn bản cũ, vốn không cấm được một đường
thứ hai vòng qua chốt.

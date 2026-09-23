# MINI-SPEC I4 + I6 — Sửa tay Bản chỉ đạo & Preset theo thương hiệu

- **Phase cha:** Phase I — Kịch bản thành chỉ đạo hình ảnh
- **Phụ thuộc:** I2 (catalog v2), I3 (sinh bản chỉ đạo), I5 (bản chỉ đạo điều khiển đầu ra thật)
- **Tác giả:** Claude (viết từ đọc mã thật)
- **Ngày:** 2026-09-23
- **Trạng thái (23/09/2026):** **ĐẠT** — trừ một lượt bấm tay trên Windows.
  Cửa ghi + cờ `suaTay` + giao diện sửa (I4); preset brand + gợi ý cho mô
  hình + chỗ rơi cho đoạn bỏ trống (I6).

---

## 0. Vì sao BÂY GIỜ mới làm được, và vì sao bây giờ PHẢI làm

Cửa ghi trên máy chủ đang **cố ý đóng**, và lý do được ghi ngay tại chỗ
(`control_server/src/routes/config.js`):

> *"Vì sao KHÔNG có cửa ghi: I2 chỉ dựng vốn từ. Lưu lựa chọn theo từng cảnh
> là việc của I3/I4 — **mở cửa ghi bây giờ là mời dữ liệu vào trước khi có ai
> đọc nó**."*

Điều kiện đó **vừa hết hiệu lực hôm nay**: I5 làm bản chỉ đạo điều khiển đầu
ra thật. Và chính I5 mở ra một lỗ mới — mô hình chọn sai một đoạn thì người
dùng **không có đường sửa**, chỉ còn cách tạo lại cả bản (tốn Vox) rồi hy
vọng lần này nó chọn khác. I4 vá đúng lỗ đó.

I6 (preset theo thương hiệu) là lớp trên: sửa tay một lần rồi lưu thành nếp
của brand, để lần sau không phải sửa lại từ đầu.

## 1. Đọc trước khi sửa

- `MINI_SPEC_PLAYBOOK.md`
- `docs/MINI-SPEC_I3_...md` (§Ngoài phạm vi ghi rõ I4/I6), `docs/MINI-SPEC_I5_...md`
- `control_server/src/services/visual-direction.service.js` — `kiemBanChiDao`, `trangThaiBan`, `bamKichBan`
- `control_server/src/services/visual-catalog.service.js` — `kiemChon`, `cachDungCua`
- `control_server/src/models/BrandScript.js` — `banChiDaoSchema`, `doanChiDaoSchema`
- `control_server/src/models/BrandProfile.js`
- `control_server/src/routes/brand-scripts.js` — `xemChiDao`, hai cửa `visual-direction`
- `autodub_gui/pages/brand_script_page.py` — nơi bản chỉ đạo đang hiện ra
- `autodub/chi_dao_hinh_anh.py` — bên tiêu thụ (I5)

## 2. Mục tiêu

**I4:** người dùng sửa được lựa chọn chỉ đạo của **từng đoạn**, lưu lại, và
lượt dựng kế tiếp dùng đúng thứ đã sửa — **không tốn Vox**, vì không gọi mô
hình.

**I6:** lưu một bộ lựa chọn ưa dùng theo **hồ sơ brand**, áp được cho cả bản
chỉ đạo bằng một thao tác, và làm mặc định cho đoạn bỏ trống thay vì
«Mờ chồng» cứng.

## 3. Rào chắn (Guardrails)

1. **Không tin đầu vào.** Cửa ghi soi lại bằng `visual-catalog.service`
   y như đường sinh tự động. Mã lạ / nhóm lạ / hai mã cùng nhóm / trường lạ
   / khoá mang nghĩa thời gian ⇒ **từ chối cả lượt**, không "sửa cho gần
   đúng". Đây là luật I3 đã đặt, không được nới ở cửa mới.
2. **Không gọi mô hình, không trừ Vox.** Sửa tay là thao tác dữ liệu. Một
   đồng bị trừ ở đây là lỗi.
3. **Không đổi `scriptHash`.** Sửa chỉ đạo KHÔNG phải sửa kịch bản. Giữ
   nguyên hash để `trangThaiBan` tiếp tục nói đúng "còn khớp hay đã cũ".
4. **Phân biệt được máy chọn và người sửa.** Mỗi lựa chọn mang cờ `suaTay`.
   Không có nó thì lần sinh lại sau sẽ im lặng đè mất công sửa của người
   dùng mà không ai cảnh báo.
5. **Không tự áp preset lên bản đã có.** I6 chỉ áp khi người dùng bấm, hoặc
   cho đoạn ĐỂ TRỐNG. Tự đè lên lựa chọn đã có là quyết thay người dùng.
6. **Preset cũng đi qua cùng bộ soi.** Không có đường tắt cho dữ liệu "của
   mình".
7. **Không mở rộng sang nhóm máy không dựng được.** Sửa được mọi nhóm (chúng
   vẫn là chỉ dẫn cho người), nhưng giao diện phải nói rõ nhóm nào máy dựng
   được — cờ `laGoiY` đã có sẵn.

## 4. Phạm vi — I4

### A. Cửa ghi

`PUT /v1/brand-scripts/:id/visual-direction`

- Thân: `{ doan: [{ thuTu, chon: [{ nhom, ma }] }] }` — chỉ phần người dùng
  sửa được. `nhan`, `laGoiY`, `dung` do máy chủ tính, **không nhận từ client**.
- Chưa có bản chỉ đạo ⇒ `404 CHUA_CO_CHI_DAO`. Sửa tay không thay thế được
  lượt sinh đầu tiên.
- Số đoạn phải khớp bản đang lưu ⇒ lệch là `400`.
- Soi xong mới ghi; hỏng thì không đụng gì tới bản cũ.
- Trả về **đúng hình dạng `xemChiDao`** để app không cần hai đường đọc.

### B. Cờ `suaTay`

Thêm vào `maChiDaoSchema`. Đặt `true` cho lựa chọn đi qua cửa ghi, `false`
cho lựa chọn do mô hình sinh. `xemChiDao` trả kèm.

### C. Giao diện

Ở hộp thoại bản chỉ đạo (trang «Viết kịch bản»): mỗi đoạn một ô chọn kiểu
chuyển cảnh, lấy danh sách **từ catalog của máy chủ** (đã có cửa đọc
`GET /v1/config/visual-direction-catalog`), không gõ tay danh sách vào app.
Nút «Lưu chỉnh sửa». Đoạn đã sửa tay hiện dấu phân biệt.

## 5. Phạm vi — I6

### A. Lưu preset

Thêm `visualPreset: { catalogVersion, chon: [{ nhom, ma }] }` vào
`BrandProfile`. Cửa ghi đi cùng cửa sửa hồ sơ brand đã có, soi bằng cùng bộ
soi catalog.

### B. Áp preset

- Nút «Áp preset cho cả bản» ở hộp thoại chỉ đạo — người dùng bấm, không tự động.
- **Đoạn bỏ trống**: I5 hiện rơi về `mo_chong` cứng. Sau I6, rơi về preset
  của brand nếu có, và **câu giải thích phải nói rõ đang dùng preset** chứ
  không im lặng đổi hành vi.

### C. Gợi ý cho mô hình

`scene_director` (I3) nhận thêm preset trong phần đầu lời nhắc, dạng "thương
hiệu này ưa dùng…". Là **gợi ý**, không phải ràng buộc — mô hình vẫn được
chọn khác nếu đoạn đó cần, vì ép cứng thì preset thành ra vô hiệu hoá cả
việc chỉ đạo.

## 6. Tiêu chí thành công

1. Sửa kiểu chuyển cảnh của một đoạn → lưu → mở lại thấy đúng thứ đã sửa.
2. Lượt dựng kế tiếp (I5) dùng đúng thứ đã sửa — chốt bằng test nối đường,
   không chỉ test cửa API.
3. Mã lạ / số đoạn lệch / trường lạ ⇒ từ chối, **bản cũ không suy suyển**.
4. Không lượt gọi mô hình nào, không Vox nào bị trừ — chốt bằng test.
5. `scriptHash` sau khi sửa **bằng đúng** trước khi sửa.
6. Preset áp được cho cả bản bằng một thao tác; đoạn bỏ trống rơi về preset
   và **nói ra**.
7. Sinh lại bản chỉ đạo khi đang có sửa tay ⇒ **cảnh báo trước**, không im
   lặng đè.
8. `pytest` + `npm test` xanh; mỗi test mới chứng minh ĐỎ bằng phép tiêm lỗi.

## 7. Ngoài phạm vi

Sửa các nhóm không phải `transition` ở mức "máy làm theo" (chúng vẫn chỉ là
chỉ dẫn cho người); preset dùng chung giữa nhiều brand; lịch sử phiên bản
bản chỉ đạo; sinh lại chỉ một đoạn.


---

## 8. Chốt phát sinh khi làm

### (a) Fastify GỠ BỎ trường lạ, không từ chối

`additionalProperties: false` + `removeAdditional` mặc định của Fastify
nghĩa là client gửi kèm `laGoiY: false` hay `dung: {...}` thì chúng bị **gỡ
im lặng**, và lượt ghi vẫn trả 200. Tính chất an toàn vẫn giữ (thứ LƯU LẠI do
catalog tính), nhưng test phải soi **kết quả** chứ không soi mã trạng thái —
soi mã trạng thái là chốt vào cơ chế, và bản sau đổi sang từ chối hẳn sẽ làm
test đỏ oan.

### (b) Một test của tôi xanh GIẢ, và phép tiêm lỗi lôi nó ra

`I4: sửa tay KHÔNG đổi scriptHash` ban đầu không chốt mã trạng thái của lượt
PUT. Khi tiêm lỗi "đổi scriptHash" mà test vẫn xanh, truy ra hai chuyện:

1. lượt PUT đang trả **400**, nên chẳng có gì được ghi và hash không đổi —
   test xanh vì **không có gì xảy ra**;
2. lý do 400 là dữ liệu test dùng `tan` — đó là **giá trị tham số dựng**
   (`KIEU_CHUYEN` của Python), không phải **mã catalog**. Mã đúng là
   `crossfade_ngan`.

Hai lớp cùng một bài học: một lượt ghi không chốt mã trạng thái thì mọi
assertion sau nó đều có thể xanh vì trống rỗng.

### (c) Hộp thoại mặc định vẫn CHỈ ĐỌC

`_sua_duoc()` đòi đủ ba thứ: danh sách mã từ máy chủ, chỗ lưu, và bản còn
khớp kịch bản. Nhờ vậy test canh cũ (`nhãn nút == ["Đóng"]`) vẫn xanh nguyên
mà không phải nới — chế độ sửa là thứ phải **bật lên**, không phải mặc định.

### (d) KHÔNG báo «Đã lưu» trước khi biết kết quả

Lượt ghi chạy ở luồng nền. Hộp thoại chỉ viết "Đang lưu…" rồi chờ
`bao_ket_qua()` từ trang. Bản đầu tôi viết "Đã lưu" ngay sau lời gọi — đúng
lớp lỗi "báo thành công khi chưa ghi" mà dự án đã dính nhiều lần.

# MINI-SPEC I5 — «Dựng video» đọc Bản chỉ đạo hình ảnh

- **Phase cha:** Phase I — Kịch bản thành chỉ đạo hình ảnh
- **Phụ thuộc:** I2 (catalog v2), I3 (`scene_director` + `visual-direction.service`)
- **Tác giả:** Claude (viết từ đọc mã thật, không từ tài liệu)
- **Ngày:** 2026-09-23
- **Trạng thái:** ĐANG LÀM — chủ dự án chốt **Hướng A** (riêng từng mối
  nối) ngày 23/09/2026. Gộp thêm lỗi nhãn «Thử ngay» không làm mới danh
  sách nhà cung cấp (xem §10).

---

## 0. Một ngã rẽ phải chốt TRƯỚC khi viết dòng mã nào

Bản chỉ đạo cho **một kiểu chuyển cảnh mỗi đoạn**. Khâu ghép hình hiện nhận
**một kiểu cho cả video**. Hai hướng, và chúng khác nhau về rủi ro chứ không
phải về công sức:

**Hướng A — chuyển cảnh riêng từng mối nối.** Trung thành với bản chỉ đạo.
Về cấu trúc là làm được: `_lenh_ghep` đã dựng một `xfade` cho mỗi mối nối,
chỉ cần đổi `ten_ffmpeg` theo `i`. **Nhưng nó động vào đúng phép tính thời
lượng đã từng hỏng và đã phải đo lại để sửa** (H4c-1, 11/09: ba ảnh ra 5,40s
thay vì 6,00s). Xem §3 để biết hai chỗ vỡ.

**Hướng B — một kiểu cho cả video, chọn theo đa số trong bản chỉ đạo.**
Không động vào phép tính thời lượng. Nhưng bỏ đi phần lớn giá trị của bản
chỉ đạo: mô hình chọn `cat_thang` cho hook và `fade_nhe` cho phần thân là có
chủ ý, gộp thành một kiểu là xoá mất chủ ý đó.

**ĐÃ CHỐT: Hướng A, kèm cổng đo bắt buộc ở §6.** Lý do: hướng B làm tính năng
trông như đã nối trong khi thực chất vẫn đoán hộ người dùng — đúng loại "hỏng
im lặng" mà I3 đã cố tránh khi từ chối "sửa cho gần đúng". Rủi ro của A là
rủi ro **đo được**, và §6 buộc phải đo.

---

## 1. Đọc trước khi sửa

- `MINI_SPEC_PLAYBOOK.md`
- `docs/MINI-SPEC_I3_Scene_Director_Visual_Direction_Sheet.md`
- `autodub/product_video.py` — `KIEU_CHUYEN`, `_lenh_ghep`, `ghep_anh_nguoi_dung`
- `autodub_gui/pages/product_scene_page.py` — nơi người dùng chọn chuyển cảnh
- `autodub_gui/pages/brand_script_page.py` — nơi bản chỉ đạo đang được hiển thị
- `autodub/saas_client.py` — `doc_chi_dao_hinh_anh()`
- `control_server/src/services/visual-catalog.service.js` — `CACH_DUNG`
- `control_server/src/data/visual-direction-catalog.json` — `h4_mapping`
- `docs/TEST_LOG.md` mục H4c-1 (phép đo thời lượng) và I2/I3

## 2. Hiện trạng đã kiểm (không phải suy đoán)

| Thứ | Trạng thái |
|---|---|
| Đường lấy bản chỉ đạo về app | **ĐÃ CÓ** — `saas_client.doc_chi_dao_hinh_anh()`, cửa `GET /brand-scripts/:id/visual-direction` |
| Bảng ánh xạ mã → tham số dựng | **ĐÃ CÓ** trong catalog: `h4_mapping.implementation` + `.parameters` |
| Số mã máy dựng được | **7** — `motion.tinh` (`{}`) + 6 mã `transition` |
| App hiển thị bản chỉ đạo | **ĐÃ CÓ** — nút «Chỉ đạo hình ảnh…» ở trang Kịch bản thương hiệu |
| Trang dựng video đọc bản chỉ đạo | **CHƯA** — `product_scene_page.py` không nhắc tới `chi_dao` ở bất kỳ đâu |

**Khe hở thật sự là hai đầu không gặp nhau.** Bản chỉ đạo sinh ra ở trang
*Kịch bản thương hiệu*; video dựng ở trang *Ảnh sản phẩm*. Không có đường nào
nối hai trang. Đây KHÔNG phải thiếu dữ liệu hay thiếu bảng ánh xạ — cả hai đã
có — mà là thiếu chỗ nối.

Ánh xạ đầy đủ, đọc thẳng từ catalog v2:

| Mã catalog | `kieu_chuyen` | ffmpeg |
|---|---|---|
| `transition.cat_thang` | `khong` | *(concat, không xfade)* |
| `transition.fade_nhe` | `mo_chong` | `fade` |
| `transition.crossfade_ngan` | `tan` | `dissolve` |
| `transition.truot_trai` | `truot_trai` | `slideleft` |
| `transition.truot_len` | `truot_len` | `slideup` |
| `transition.mo_vong` | `mo_vong` | `circleopen` |
| `motion.tinh` | *(không tham số)* | — |

## 3. Hai chỗ vỡ nếu trộn kiểu (Hướng A)

**(a) `cat_thang` không đi đường `xfade`.** Hiện `khong` rẽ sang `concat` cho
**cả chuỗi**. Chú thích tại chỗ nói rõ `xfade` với `duration=0` **không tương
đương** — nó vẫn ăn mất một khoảng của cảnh sau. Nên một mối nối `cat_thang`
nằm giữa chuỗi xfade cần cách xử lý riêng, không được lười dùng `duration=0`.

**(b) Phép bù thời lượng giả định mọi mối nối đều ăn `giay_chuyen`.**

```python
dai_vao = [g + giay_chuyen for g in giay[:-1]] + [giay[-1]]
```

Trộn kiểu thì mối `cat_thang` ăn **0** giây, các mối khác ăn `giay_chuyen`.
Bù đều cho tất cả ⇒ **thừa** đúng `giay_chuyen` cho mỗi mối cắt thẳng, và sai
lệch **cộng dồn** — đúng hình dạng lỗi H4c-1. Phép bù phải thành **theo từng
mối**, và mốc `offset` phải tính lại từ chuỗi bù mới.

## 4. Mục tiêu

Để người dùng dựng video sản phẩm **theo đúng chuyển cảnh mà bản chỉ đạo đã
chọn cho từng đoạn**, thay vì tự đoán một kiểu áp cho cả video — mà không làm
lệch dòng thời lượng đã đo đúng ở H4c-1.

## 5. Rào chắn (Guardrails)

1. **Không dựng bảng ánh xạ thứ hai.** Catalog là nguồn duy nhất. App đọc
   `h4_mapping.parameters`, không hardcode bảng mã→`kieu_chuyen` trong Python.
2. **Mã lạ thì NÉM LỖI, không rơi về mặc định.** Giữ đúng luật đang có ở
   `_lenh_ghep`. Người dùng nhận một kiểu khác kiểu đã chọn là hỏng im lặng.
3. **Không đoán hộ khi số lượng lệch.** Bản chỉ đạo N đoạn, video M ảnh —
   N ≠ M là chuyện thường (người dùng tự chọn ảnh). Xem §7.
4. **Không đụng thời lượng từ bản chỉ đạo.** Catalog đã cấm mọi khoá mang
   nghĩa thời gian; luật đó giữ nguyên ở đây. Thời lượng chỉ có một nguồn:
   giọng đọc thật (D1).
5. **Không bỏ quyền chọn tay.** Bản chỉ đạo là **đề xuất**; người dùng phải
   ghi đè được, và phải thấy rõ mình đang dùng cái nào.
6. **Không mở rộng sang `shot`/`composition`/`lighting_color`.** Chúng là
   `advisory_only` — máy không dựng được. I5 chỉ nối nhóm `transition`
   (và `motion.tinh`, vốn không có tham số).
7. **Không đổi hợp đồng hiện có của `ghep_anh_nguoi_dung`.** Tham số
   `kieu_chuyen: str` phải tiếp tục chạy y nguyên cho mọi chỗ gọi cũ.

## 6. Cổng đo BẮT BUỘC — không có số đo thì không tính là xong

Phép bù thời lượng đã hỏng một lần và chỉ lộ ra khi đo bằng ffprobe. Nên:

- Dựng thật bằng ffmpeg, **đo lại bằng ffprobe**, trên **ít nhất 6 hình dạng
  trộn kiểu**, bắt buộc có: toàn `cat_thang`; toàn `fade_nhe`; xen kẽ
  cắt/mờ; `cat_thang` ở **mối đầu**; `cat_thang` ở **mối cuối**; ba kiểu
  khác nhau liền nhau.
- Tiêu chí: lệch tối đa **1 khung @30fps (0,0333s)** so với tổng thời lượng
  yêu cầu, và **không tăng theo số ảnh** — đúng ngưỡng H4c-1 đã chốt.
- Số đo ghi vào `docs/TEST_LOG.md`. Test xanh mà không có số đo ffprobe thì
  **chưa đóng được cổng này**: bộ test hiện đọc *lệnh* ffmpeg, mà lệnh đúng
  hình dạng vẫn có thể ra sai thời lượng.

## 7. Số lượng lệch — luật phải rõ

| Trường hợp | Xử lý |
|---|---|
| M ảnh = N đoạn | Ánh xạ 1-1 theo thứ tự |
| M < N | Dùng N đoạn **đầu**, nói rõ trên giao diện là đã bỏ phần đuôi |
| M > N | Các ảnh thừa dùng kiểu của đoạn **cuối**, nói rõ trên giao diện |
| Không có bản chỉ đạo | Giữ nguyên hành vi cũ — ô chọn tay, mặc định `mo_chong` |
| Bản chỉ đạo lệch kịch bản (`scriptHash` khác) | **Từ chối dùng**, bảo người dùng tạo lại — I3 đã băm sẵn cho đúng việc này |

Ba dòng giữa **phải hiện ra chữ cho người dùng đọc**, không được im lặng.

## 8. Tiêu chí thành công

1. Trang «Ảnh sản phẩm» lấy được bản chỉ đạo của kịch bản đang mở và hiện ra
   kiểu chuyển cảnh mỗi đoạn, kèm câu lý do của mô hình.
2. Bấm dựng ⇒ video ra **đúng chuyển cảnh từng mối** như bản chỉ đạo.
3. Người dùng ghi đè được bằng tay, và thấy rõ đang dùng cái nào.
4. Sáu hình dạng ở §6 đo bằng ffprobe đạt ngưỡng 1 khung, số đo trong
   `TEST_LOG`.
5. Mã lạ / bản chỉ đạo lệch kịch bản ⇒ báo lỗi đọc được, không dựng bừa.
6. Mọi chỗ gọi `ghep_anh_nguoi_dung` cũ chạy y nguyên.
7. `pytest` + `npm test` xanh, và mỗi test mới **đã được chứng minh ĐỎ** khi
   gỡ phần sửa tương ứng.

## 9. Ngoài phạm vi

Sinh ảnh theo `shot`/`composition`/`lighting_color`; hiệu ứng mới; đổi
`GIAY_CHUYEN_CANH` mặc định; đưa bản chỉ đạo vào luồng lồng tiếng thường
(I5 chỉ nói về video sản phẩm).


---

## 10. Gộp thêm: nhãn «Thử ngay» không làm mới danh sách

**Lỗi đã kiểm 23/09/2026.** Bấm «Thử ngay» trên trang *Nơi gọi mô hình* hiện
câu xanh "Gọi được và đọc đúng số trong ảnh — nhìn được ảnh", nhưng nhãn bên
cạnh vẫn là "chưa chứng minh nhìn được ảnh".

Không phải lỗi ghi. `ai-gateway.service.js` `thuNgay()` đã
`$set: { visionOkAt: new Date() }` khi đạt. Lỗi ở giao diện:
`TestNowButton({ id })` trong `website/src/pages/admin/Providers.jsx` chỉ giữ
kết quả trong state riêng, **không báo cho danh sách cha nạp lại**; nhãn đọc
`p.visionOkAt` từ danh sách cũ nên đứng yên tới khi tải lại trang.

**Sửa:** truyền `onDone` để nút báo ngược lên, danh sách nạp lại sau mỗi lượt
thử. Cần một test chặn hồi quy — nút đổi trạng thái lưu trữ mà không làm mới
chỗ hiển thị trạng thái đó là cái bẫy đọc-sai kinh điển.

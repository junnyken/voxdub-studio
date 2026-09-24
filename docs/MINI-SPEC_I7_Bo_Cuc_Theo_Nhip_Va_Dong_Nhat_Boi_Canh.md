# MINI-SPEC I7 — Bố cục theo nhịp & đồng nhất bối cảnh

- **Phase cha:** Phase I — Kịch bản thành chỉ đạo hình ảnh
- **Phụ thuộc:** H2 (Flow Blueprint), H3 (viết kịch bản), I2 (catalog), I3 (chỉ đạo hình ảnh), I5 (dựng theo bản chỉ đạo)
- **Tác giả:** Claude (viết từ đo mã thật, 24/09/2026)
- **Trạng thái:** CHƯA bắt đầu — spec chờ duyệt
- **Ưu tiên chủ dự án chốt:** (A) bố cục theo nhịp trước · (B) đồng nhất bối cảnh/nhân vật

---

## 0. Audit — những gì ĐO ĐƯỢC, không phải suy đoán

### (a) Chặng chỉ đạo hình ảnh mù hoàn toàn về nhịp

`visual-direction.service.dungInput()` gửi cho `scene_director` **đúng ba
trường mỗi đoạn**:

```js
beats: (kichBan?.beats || []).map((b) => ({
  beatType:    b?.beatType || 'unknown',
  loiDoc:      b?.voiceoverTextVi || '',
  visualBrief: b?.visualBriefVi || '',
}))
```

**Không có thời lượng. Không có nhịp.** Nên khi mô hình chọn khung hình và
chuyển cảnh, nó không phân biệt được đoạn 2 giây với đoạn 8 giây — hai thứ
cần bố cục khác hẳn nhau. Một cú «mở vòng tròn» 0,3 giây trên đoạn 2 giây ăn
mất 15% đoạn; trên đoạn 8 giây thì không đáng kể.

### (b) Không một chữ nào về đồng nhất giữa các đoạn

Rà lời nhắc `brand_script_rewrite` với 8 cụm khoá (`đồng nhất`, `nhất quán`,
`cùng một`, `giữ nguyên`, `xuyên suốt`, `liền mạch`, `các đoạn khác`,
`lặp lại`): **không khớp cụm nào**. Mỗi `visual_brief` được viết độc lập, nên
đoạn 1 có thể là gian bếp sáng và đoạn 5 là bàn làm việc, không gì chặn.

### (c) Bộ kiểm liền mạch đang có CỐ Ý không xét bối cảnh

`scene_continuity` (`assist.js`) ghi thẳng trong lời nhắc:

> *"KHÔNG xét bối cảnh khác nhau — các cảnh CỐ Ý khác bối cảnh."*

Và `product_video.kiem_lien_tuc()` là **lớp cảnh báo, không chặn** — hỏng thì
trả `da_kiem=False` và cho đi tiếp. Nó xét cỡ sản phẩm, góc máy, tông màu,
hướng sáng — **trên ảnh ĐÃ DỰNG**, tức sau khi tiền đã tiêu.

Nói cách khác: đồng nhất hiện được **kiểm sau**, không được **thiết kế vào**.

### (d) Ngân sách lời nhắc — số đo thật

| | 5 đoạn | 10 | 20 | 30 | 40 |
|---|---|---|---|---|---|
| `brand_script_rewrite` | 1.626 | 2.799 | 5.146 | **5.846** | 4.042 |
| `scene_director` | 2.471 | 3.279 | **4.895** | 4.024 | 4.810 |

Trần cả hai là **6.000**. H3 ở 30 đoạn chỉ còn **154 ký tự trống** — thêm gì
vào đó là vỡ. I3 còn **1.100–2.700** — đủ chỗ.

*(Số không tăng đều vì bậc ngân sách cắt bớt mô tả khi chạm trần — cơ chế
`NGAN_SACH_BEAT`. Đã đo: **không bao giờ mất đoạn nào** ở mọi cỡ 5→40.)*

### (e) Mâu thuẫn phải giải, không được lờ

Chủ dự án muốn **"nhân vật đồng nhất"**. Nhưng lời nhắc H3 **cấm**:

> *"KHÔNG mô tả khuôn mặt, ngoại hình, tuổi tác, kiểu tóc hay trang phục của
> người nào. Cần có người trong khung thì chỉ nói VAI TRÒ và HÀNH ĐỘNG."*

Đây là luật riêng tư, **không được nới**. Xem §3 guardrail 4 để biết cách
spec này giải mà không đụng vào nó.

---

## 1. Đọc trước khi sửa

- `MINI_SPEC_PLAYBOOK.md`
- `docs/MINI-SPEC_I3_...md`, `docs/MINI-SPEC_I5_...md`, `docs/MINI-SPEC_H2_...md`
- `control_server/src/prompts/assist.js` — `brand_script_rewrite`, `scene_director`, `scene_continuity`, `NGAN_SACH_BEAT`, `TRAN_LOI_NHAC`, `dungDongDoanChiDao`
- `control_server/src/services/visual-direction.service.js` — `dungInput`
- `control_server/src/models/BrandScript.js` — `beats`, `banChiDaoSchema`
- `autodub/product_video.py` — `kiem_lien_tuc`, `KIEU_CHUYEN`
- `autodub/chi_dao_hinh_anh.py` — bên tiêu thụ (I5)
- `docs/TEST_LOG.md` mục I3, I5, H4c-1

## 2. Mục tiêu

**(A)** Chặng chỉ đạo hình ảnh **biết đoạn dài bao nhiêu và nhịp thế nào**,
để chọn khung hình và chuyển cảnh hợp với đoạn đó thay vì chọn mù.

**(B)** Kịch bản sinh ra có **một sân khấu nhất quán**: cùng bối cảnh, cùng
đạo cụ, cùng hướng sáng, cùng quy ước khung người — thay vì mỗi đoạn một nơi.

## 3. Rào chắn (Guardrails)

1. **Không nới luật riêng tư.** Lệnh cấm tả khuôn mặt/ngoại hình/tuổi/tóc/
   trang phục giữ nguyên từng chữ. §5 giải bài toán đồng nhất **mà không
   chạm vào nó**.
2. **Không vỡ trần lời nhắc.** H3 ở 30 đoạn còn 154 ký tự — mọi thứ thêm vào
   H3 phải có bậc ngân sách riêng và **thứ tự hy sinh ghi rõ**. Chốt cũ giữ
   nguyên: thà mất phần mô tả còn hơn mất một đoạn.
3. **Không đưa thời lượng thành thứ mô hình ĐẶT.** Mô hình chỉ ĐỌC thời
   lượng để chọn bố cục. Catalog đã cấm mọi khoá mang nghĩa thời gian
   (`THAM_SO_CAM`) và luật đó giữ nguyên: thời lượng chỉ có một nguồn là
   giọng đọc thật (D1).
4. **Không biến cảnh báo thành cổng chặn.** `kiem_lien_tuc` đang là lớp cảnh
   báo và phải giữ vậy — người bán quyết giữ hay dựng lại, không phải máy.
5. **Không dựng bảng ánh xạ thứ hai.** Catalog vẫn là nguồn duy nhất (rào
   chắn 1 của I5).
6. **Đo A/B trước khi tin.** Đây là thay đổi **chất lượng đầu ra** của tính
   năng đang chạy. Không có số đo hai chiều thì không đóng được — xem §6.
7. **Không mở rộng sang sinh ảnh.** I7 chỉ nói về LỜI (kịch bản) và MÃ CHỈ
   ĐẠO. Việc vẽ ảnh vẫn là chuyện của H4d.

---

## 4. Phạm vi A — bố cục theo nhịp *(ưu tiên)*

### A1. Gửi thời lượng và nhịp xuống `scene_director`

`dungInput()` thêm cho mỗi đoạn:

- `giay` — thời lượng đoạn (số, một chữ số thập phân)
- `nhip` — `pacingNoteVi` của beat Blueprint **tương ứng**, cắt ~120 ký tự

`giay` lấy từ đâu: kịch bản brand chưa lưu thời lượng đoạn, nên phải lần
theo Blueprint gốc (`flowBlueprintId` → `beats[i].startS/endS`). **Audit bắt
buộc trước khi code:** xác nhận số đoạn của kịch bản luôn bằng số beat của
Blueprint (H3 đòi đúng số đoạn — kiểm lại chứ đừng tin).

Blueprint đã mất/đã xoá ⇒ **bỏ trống, không đoán**. Mô hình vẫn chạy như
hôm nay.

### A2. Dạy mô hình dùng con số đó

Thêm vào `system` của `scene_director` — nói bằng NGƯỠNG, không bằng lời
khuyên mơ hồ:

- đoạn **ngắn** (≲2,5 giây): chuyển cảnh ăn thời gian là ăn vào phần đáng
  kể của đoạn ⇒ nghiêng về `cat_thang`
- đoạn **dài** (≳5 giây): có chỗ cho chuyển mềm và khung hình rộng hơn
- `nhip` nói "cắt nhanh" ⇒ đừng chọn chuyển cảnh mềm kéo dài

Con số ngưỡng phải **đo rồi chốt** (§6), không gõ đại.

### A3. Nói ra cho người dùng

Hộp thoại chỉ đạo hiện thêm thời lượng mỗi đoạn. Người dùng sửa tay (I4) cần
thấy đoạn này dài bao nhiêu mới chọn đúng được — nay họ cũng đang chọn mù.

## 5. Phạm vi B — đồng nhất bối cảnh & nhân vật

### B1. Cách giải mà KHÔNG đụng luật riêng tư

Đồng nhất **không đòi** phải tả nhận dạng. Thay vào đó chốt ba thứ ở mức cả
kịch bản, gọi là **"sân khấu"**:

| Thành phần | Ví dụ | Có chạm luật riêng tư? |
|---|---|---|
| **Bối cảnh** | "gian bếp nhỏ, mặt bàn gỗ sáng" | không |
| **Đạo cụ + ánh sáng** | "ánh sáng cửa sổ từ bên trái, có rổ rau" | không |
| **Quy ước khung người** | "chỉ thấy bàn tay, không bao giờ thấy mặt" | **không** — đây là quy ước KHUNG HÌNH, không phải mô tả người |

Thứ tạo cảm giác "cùng một người" trong video ngắn thực tế là **quy ước
khung hình nhất quán**, không phải mô tả ngoại hình. Đó là chỗ spec này đi
vào, và nó nằm hoàn toàn ngoài luật cấm.

### B2. Sân khấu sinh ra ở đâu

Hai hướng, phải chọn — **đo rồi chốt, đừng chọn theo cảm tính**:

**B2-a. Mô hình tự chốt sân khấu trong cùng lượt H3.** Thêm vào schema đầu
ra một khối `san_khau { boi_canh, dao_cu_anh_sang, quy_uoc_khung_nguoi }`,
sinh TRƯỚC danh sách đoạn, và lời nhắc buộc mọi `visual_brief` bám theo.
*Lợi:* không thêm lượt gọi, không thêm Vox. *Hại:* thêm chữ vào đầu ra của
một lời nhắc đã chạm trần ở 30 đoạn.

**B2-b. Lấy từ hồ sơ thương hiệu.** Thêm trường `sanKhau` vào `BrandProfile`
(giống `visualPreset` của I6), người dùng đặt một lần dùng mãi.
*Lợi:* nhất quán giữa **nhiều kịch bản**, không chỉ trong một kịch bản; 0 Vox.
*Hại:* thêm việc cho người dùng.

**Đề xuất: làm cả hai, B2-b làm mặc định của B2-a.** Có hồ sơ thì dùng nếp
của brand; chưa có thì mô hình tự chốt cho kịch bản đó. Đúng khuôn I6 đã
dựng (nếp là **chỗ rơi**, không phải lệnh).

### B3. Ràng buộc mọi đoạn bám sân khấu

Lời nhắc H3 thêm luật — đặt ở `system`, không tốn ngân sách `user`:

> Mọi `visual_brief` phải xảy ra trong CÙNG bối cảnh đã chốt, dưới CÙNG hướng
> sáng, và theo CÙNG quy ước khung người. Đổi góc máy và cỡ khung thì được;
> đổi NƠI CHỐN thì không, trừ khi vai trò của đoạn đòi hỏi rõ ràng.

### B4. Nói ra khi lệch

`scene_continuity` hiện **cố ý** không xét bối cảnh, và luật đó **đúng cho
ngữ cảnh cũ** (ảnh sản phẩm dựng nhiều bối cảnh là cố ý). Nhưng khi kịch bản
có sân khấu đã chốt thì "khác bối cảnh" trở thành tín hiệu đáng nói.

**Không sửa `scene_continuity`.** Thay vào đó truyền sân khấu đã chốt qua
trường `note` sẵn có của nó, và để lời nhắc xét thêm một câu *khi và chỉ khi*
`note` có sân khấu. Giữ nguyên hành vi cũ cho mọi chỗ gọi không truyền.

Vẫn là **cảnh báo**, không chặn (guardrail 4).

---

## 6. Cổng đo BẮT BUỘC

Đây là thay đổi chất lượng đầu ra. "Thêm dữ liệu thì tốt hơn" là **giả
thuyết**, không phải sự thật — dự án này đã nhiều lần đo ra điều ngược lại.

**Bộ mẫu:** ít nhất **3 hồ sơ thương hiệu khác nhau** × **2 video tham khảo**
(một nhịp nhanh nhiều chữ, một nhịp chậm ít chữ) = 6 lượt, chạy **trước và
sau**, tổng 12 lượt gọi thật.

**Tiêu chí đọc được, chấm trước khi biết lượt nào là lượt nào:**

| Đo gì | Cách đếm |
|---|---|
| Bố cục theo nhịp | tỉ lệ đoạn ≲2,5 giây được gán `cat_thang` — trước/sau |
| | tỉ lệ đoạn ≳5 giây được gán chuyển mềm |
| Đồng nhất bối cảnh | đếm số NƠI CHỐN khác nhau trong các `visual_brief` của một kịch bản |
| Đồng nhất khung người | số quy ước khung người khác nhau xuất hiện |
| Không hỏng thứ đang tốt | số đoạn trả về đúng · ngân sách từ không vượt · bộ chặn sao chép không đỏ thêm |
| Giá | token đầu vào/đầu ra trước/sau — I7 KHÔNG được làm tăng giá quá 15% |

Số đo ghi vào `docs/TEST_LOG.md`. **Không đạt tiêu chí cuối thì lùi lại**,
không "để đó rồi tính".

## 7. Tiêu chí thành công

1. `scene_director` nhận được thời lượng và nhịp mỗi đoạn; Blueprint mất thì
   bỏ trống chứ không đoán.
2. Đo được: đoạn ngắn nghiêng về cắt thẳng rõ rệt hơn bản trước.
3. Kịch bản sinh ra có sân khấu chốt sẵn, và mọi `visual_brief` bám theo.
4. Hồ sơ brand đặt được sân khấu; chưa đặt thì mô hình tự chốt.
5. Luật riêng tư **không đổi một chữ** — có test canh.
6. Ngân sách lời nhắc: ở 40 đoạn vẫn **không mất đoạn nào**.
7. Giá không tăng quá 15%.
8. `pytest` + `npm test` xanh; mỗi test mới chứng minh ĐỎ bằng phép tiêm lỗi.

## 8. Ngoài phạm vi

- Nối `overlay_pattern_abstract_vi` + `spoken_pattern_abstract_vi` vào H3 —
  **lỗ hổng riêng, đã đo, đáng một mini-spec khác.** Hai trường này hiện được
  H2 sinh ra (bắt buộc, tốn token), lưu vào CSDL, trả qua API, và **không ai
  đọc**: grep toàn bộ máy chủ + app ra đúng **một** chỗ dùng mỗi trường, là
  bước lưu. Chúng nói *đối thủ TRUYỀN ĐẠT thế nào* — đúng thứ H3 cần để viết
  hay hơn. Không gộp vào I7 vì H3 đã chạm trần ngân sách và trộn hai thay đổi
  chất lượng vào một lượt đo là không biết cái nào có tác dụng.
- Sinh ảnh theo sân khấu (H4d).
- Đồng nhất giữa các kịch bản KHÁC nhau của cùng brand (B2-b mở đường, nhưng
  đo và chốt là việc sau).

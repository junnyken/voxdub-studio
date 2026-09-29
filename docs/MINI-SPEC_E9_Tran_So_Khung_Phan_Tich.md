# MINI-SPEC E9 — Trần số khung cho phân tích cấu trúc

- **Họ:** E — chi phí & độ ổn định của đường phân tích
- **Tác giả:** Claude (viết từ đo mã thật, 28/09/2026)
- **Trạng thái:** XONG 29/09/2026 — §5 đo chốt `SO_KHUNG_TOI_DA = 250`, §4A-D đã code

---

## 0. Audit — đo được, không suy đoán

### (a) Triệu chứng

Chủ dự án chạy «Phân tích cấu trúc» trên một video YouTube thường, **562 giây
vẫn chưa xong**, còn ở bước *"Đang đọc chữ trên hình"*. Không có gì hỏng —
nó thật sự còn phải đọc rất nhiều khung.

### (b) Số khung KHÔNG có trần

`moc_lay_mau_thich_ung(dai_giay)` rải mốc: 5 giây đầu và 5 giây cuối mỗi
**0,2s**, đoạn giữa mỗi **0,5s**. Không có bước nào kẹp tổng số. Tính bằng
chính hàm đó:

| video dài | số khung | OCR cục bộ 2–14 giây/khung |
|---|---|---|
| 30 giây | 91 | 3–21 phút |
| 47 giây | 125 | 4–29 phút |
| 1 phút | 151 | 5–35 phút |
| 2 phút | 271 | 9 phút – 1,1 giờ |
| 5 phút | **631** | 21 phút – **2,5 giờ** |
| 10 phút | **1.231** | 41 phút – **4,8 giờ** |

### (c) Trần ĐÃ CÓ ở đầu ra — chỉ thiếu ở đầu vào

Đây là chỗ then chốt, và nó biến E9 từ "thêm tính năng" thành "đóng một nửa
còn thiếu":

| Chiều | Trần | Ở đâu |
|---|---|---|
| **Ra** (mẩu gửi lên máy chủ) | **400**, rải đều | `SO_BANG_CHUNG_TOI_DA`, khớp `maxItems` của `routes/flow-blueprints.js` |
| **Vào** (khung đem đi OCR) | **không có** | `moc_lay_mau_thich_ung` |

Repo đã tự ghi bài học này ở chỗ khác (E7, trần bằng chứng H2):

> *"trần phải đặt ở **CẢ HAI** chiều của một mảng"*

E9 chỉ là áp đúng câu đó cho đường còn lại. Và `gioi_han_bang_chung` đã có
sẵn khuôn mẫu đúng để bắt chước: **giữ N mẩu, RẢI ĐỀU dòng thời gian, không
cắt đuôi** — cắt đuôi là mất sạch phần cuối video, nơi có lời kêu gọi hành động.

### (d) Sản phẩm đã BIẾT nó ngoài tầm, chỉ chưa hành động

`GIAY_KHUYEN_NGHI_TOI_DA = 90.0` — H2-MVP chỉ cam kết độ phủ đầy đủ cho video
**≤ 90 giây**. `ta_chinh_sach_lay_mau` đã nói ra điều đó với mô hình:

> *"video {n}s, dài hơn mức H2-MVP cam kết độ phủ đầy đủ 90s — đoạn giữa có
> thể bỏ sót caption chớp nhanh"*

Tức dài hơn 90 giây thì **đã chấp nhận bỏ sót**. Nhưng vẫn đi đọc đủ 1.231
khung. Trả giá đầy đủ cho một lời hứa đã rút lại.

### (e) BẪY KHỚP NỐI — thưa đoạn giữa mà quên chỗ này là PHẢN TÁC DỤNG

```python
#: Hai quan sát cùng chữ nhưng cách xa hơn mức này thì coi là HAI LẦN XUẤT
#: HIỆN riêng … gấp đôi bước lấy mẫu thưa nhất (0,5s)
KHOANG_CACH_TOI_DA_DE_GOP_GIAY = 1.0
```

`gop_quan_sat_lien_tiep` chỉ gộp hai quan sát cùng chữ khi chúng cách nhau
**≤ 1,0 giây**. Con số 1,0 được chọn = gấp đôi bước thưa nhất hiện tại (0,5s).

Thưa đoạn giữa xuống 2s/khung mà giữ nguyên 1,0 thì **không quan sát liên
tiếp nào còn gộp được nữa** — một dòng chữ đứng yên 10 giây sẽ thành 5 mẩu
rời thay vì 1. Số mẩu **tăng**, đụng trần 400 sớm hơn, và `gioi_han_bang_chung`
lại phải vứt bớt. Đọc ít khung hơn nhưng bằng chứng **tệ hơn**.

Nên bước lấy mẫu và khoảng cách gộp là **một cặp**, phải đổi cùng nhau.

---

## 1. Đọc trước khi sửa

- `autodub/flow_blueprint.py`: `moc_lay_mau_thich_ung`, `ta_chinh_sach_lay_mau`,
  `gop_quan_sat_lien_tiep`, `gioi_han_bang_chung`, các hằng dòng 26–91
- `control_server/src/routes/flow-blueprints.js` (`maxItems: 400`)
- `docs/MINI-SPEC_H2_Viral_Flow_Blueprint.md` Scope A #4, #5
- `tests/test_e7_tran_bang_chung.py`

## 2. Mục tiêu

Thời gian phân tích **có trần**, không phình theo độ dài video — mà **không
làm xấu** bằng chứng cho video ngắn (nơi sản phẩm cam kết độ phủ đầy đủ).

## 3. Rào chắn

1. **Video ≤ 90 giây KHÔNG được đổi một mốc nào.** Đó là vùng H2-MVP cam kết
   độ phủ đầy đủ. Trần chỉ được cắn vào phần vượt ngoài cam kết.
2. **Giữ dày ở 5 giây đầu và 5 giây cuối.** Hook và kêu gọi hành động nằm ở
   đó; thưa hai đầu là hỏng đúng thứ tính năng này sinh ra để đọc.
3. **Rải đều, KHÔNG cắt đuôi** — theo đúng `gioi_han_bang_chung` đã làm.
4. **Đổi bước lấy mẫu thì nên đổi `KHOANG_CACH_TOI_DA_DE_GOP_GIAY` theo**
   (§0e), để hằng số giữ đúng ý nghĩa đã ghi trong chú thích.

   > **Hạ từ «bắt buộc» xuống «nên» sau khi đo 28/09.** Tôi từng khẳng định
   > bỏ qua việc này làm một dòng chữ 10 giây tách thành 7 mẩu. Số đó đúng
   > trong mô phỏng cô lập nhưng **sai trên đường chạy thật**: bỏ-khung-trùng
   > (I7) đã loại các khung giống nhau TRƯỚC bước gộp, nên cả ba cấu hình đo
   > được đều có số mẩu = số quan sát thô — **bước gộp không gộp được gì**.
   > Xem `docs/TEST_LOG.md` mục «E9 §5 (tiếp)».
5. **`samplingPolicyUsed` phải nói ra mật độ THẬT.** Mô hình dùng chuỗi đó để
   biết tin phần OCR đến đâu. Thưa đi mà vẫn khai như cũ là để mô hình tin
   quá mức vào bằng chứng mỏng — tệ hơn cả việc thưa.
6. **Không đụng trần 400 ở đầu ra**, không đụng `maxItems` của máy chủ.

## 4. Phạm vi

### A. Trần số khung, thưa dần ở ĐOẠN GIỮA

Thêm `SO_KHUNG_TOI_DA`. Hai đầu giữ nguyên 0,2s (52 khung cố định). Ngân sách
còn lại chia đều cho đoạn giữa; video càng dài thì bước giữa càng thưa, nhưng
tổng luôn ≤ trần.

**Đã chốt bằng đo (xem `docs/TEST_LOG.md` mục E9 §5): `SO_KHUNG_TOI_DA = 250`.**
Cận dưới 211 do rào chắn 1; 250 cho biên. Trần 400 gần như không cắn.

### B. Khoảng cách gộp đi theo bước giữa

`KHOANG_CACH_TOI_DA_DE_GOP_GIAY` không còn là hằng: nó phải là **gấp đôi bước
thưa nhất THẬT SỰ dùng** cho lượt đó. Giữ nguyên ý nghĩa cũ, chỉ thôi ghim
cứng vào con số 0,5s.

### C. Nói thật trong `samplingPolicyUsed`

Khi trần cắn, chuỗi phải ghi rõ bước giữa thật là bao nhiêu và tổng bao nhiêu
khung — thay vì tiếp tục khai "giữa mỗi 0,5s".

### D. Nói cho người dùng biết TRƯỚC khi chạy

Trang «Phân tích cấu trúc» hiện ước tính khi video vượt 90 giây: bao nhiêu
khung, và khuyên dùng video ngắn hơn. Người dùng hiện chỉ biết sau khi đã
chờ 10 phút.

## 5. Chốt con số bằng đo — làm TRƯỚC khi code

Đừng chọn trần bằng cảm giác. Chạy **cùng một video ~3 phút** hai lần:

1. bản hiện tại (không trần)
2. bản có trần, thử vài giá trị

Rồi so **thứ thật sự quan trọng**, không phải số khung:

- số đoạn blueprint sinh ra, và **vai trò** từng đoạn có khớp nhau không
- số mẩu `ocrEvidence` sau khi gộp (trần 400 có bị đụng không)
- thời gian chạy

> **Sửa 28/09 sau khi đo lặp.** Tiêu chí "cùng số đoạn và cùng vai trò"
> **không đạt được với bất kỳ thay đổi nào**, kể cả thay đổi rỗng: chạy 10
> lượt trên **một đầu vào duy nhất** cho ra từ **7 đến 10 đoạn**. Mô hình
> không tất định, nên so một lượt với một lượt là đo nhiễu.
>
> Tiêu chí đúng: **khung xương giữ nguyên** — `hook` → `problem_context` →
> `tension` → … → `cta`, ba vị trí đầu và đoạn kết. Qua 15 lượt của cả ba
> cấu hình, phần đó luôn đúng. Và phải đo **nhiều lượt**, không một lượt.

## 6. Tiêu chí thành công

1. Video 10 phút: số khung ≤ trần; thời gian phân tích **có chặn trên**.
2. Video ≤ 90 giây: mốc lấy mẫu **giống hệt** trước khi sửa, từng con số.
3. `samplingPolicyUsed` ghi đúng bước giữa thật và tổng số khung.
4. Không lượt nào còn đụng trần 400 ở đầu ra vì cớ "không gộp được" (§0e).
5. Có **bằng chứng đo** ở §5 trong `docs/TEST_LOG.md`, kèm con số đã chọn và
   lý do.
6. `pytest` xanh, gồm phép tiêm lỗi chứng minh trần thật sự cắn.

**Tiêu chí 5 ĐÃ ĐẠT** (28/09, sau khi chạy lặp 15 lượt): khung xương giữ
nguyên ở mọi lượt của mọi cấu hình — `hook` → `problem_context` → `tension`
→ … → `cta`.

> Bản ghi đầu của tôi nói trần "bỏ một đoạn nhiễu dựng trên caption chớp
> 0,4 giây". **Sai** — chạy lặp cho thấy đoạn đó là một lượt dao động, không
> phải hiệu ứng hệ thống. Khác biệt giữa có trần và không trần **không phân
> biệt được** với dao động của chính mô hình. Xem `docs/TEST_LOG.md` mục
> «E9 §5 (lần 3)».

## 7. Ngoài phạm vi

- Đổi trần 400 ở đầu ra, hay `maxItems` của máy chủ.
- Bỏ OCR cục bộ để gửi thẳng mọi khung cho mô hình nhìn ảnh — đã tính: video
  5 phút ≈ **840 Vox**, 10 phút ≈ **1.640 Vox**, tức trả tiền để đọc hàng
  trăm khung trùng nhau. Đặt trần rẻ hơn nhiều và không đổi kiến trúc.
- Chặn video dài. Sản phẩm cố ý **không chặn**, chỉ nói rõ giới hạn — E9 giữ
  nguyên lựa chọn đó.

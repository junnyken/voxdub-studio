# H6 — H3 phải giữ đúng NHỊP mà H2 học được

**Lập 14/09/2026**, từ lượt chạy pilot thật của chủ dự án.

## Vấn đề, nói bằng số

Trang «Dựng video» tự báo:

> `Kịch bản đọc hết khoảng 170 giây, dài gấp 5.0 lần video tham khảo (34 giây)`
> `— nhịp kể chuyện học được sẽ không còn giống nữa.`

Đây là **mục tiêu của cả sáng kiến Phase H bị hụt**. Chuỗi H2 tốn 8 Vox phân
tích + 56 Vox đọc chữ để học **NHỊP** của một video 34 giây. H3 trả về một
kịch bản đọc **170 giây**. Cùng 7 đoạn, cùng vai trò kể chuyện — nhưng một
Short 34 giây và một video gần 3 phút không phải cùng một định dạng.

## Nguyên nhân — một dòng, tìm trong mã

`brand-scripts.js::dungInput` lọc bỏ `startS`/`endS`:

```js
beats: (blueprint.beats || []).map((b) => ({
  beatType, narrativeFunctionVi, pacingNoteVi,     // <- chỉ ba trường
}))
```

Và lời nhắc hệ thống của `brand_script_rewrite` **không có một chữ nào về độ
dài**. Nên mô hình **không có cách nào biết** nguồn dài 34 giây; nó viết theo
độ dài mặc định của văn quảng cáo. Ra gấp 5 là đương nhiên, **không phải rủi
ro ngẫu nhiên**.

**Vì sao tới pilot mới lộ:** bộ dò nằm ở `storyboard.dung_storyboard` — tận
H4, sau khi đã tiêu 12 Vox — và chỉ **cảnh báo**, không chặn. Trước lượt này
chưa ai đi tới H4 với một kịch bản thật.

## Đã dựng

### 1. Thời lượng đi tới được mô hình

`dungInput` gửi thêm `giay = endS - startS` cho từng đoạn.

### 2. Ngân sách TỪ, tính từ tốc độ đọc ĐO THẬT

`autodub/storyboard.py` có hai hằng số đo trên 4 giọng VieNeu, kiểm chéo trên
câu chưa từng dùng để khớp (sai lệch tuyệt đối trung bình **3,3%**):

```
giây = 0,39 × số_câu + 0,504 × số_âm_tiết
```

Đảo lại thành ngân sách: `số_từ ≈ (giây − 0,39) / 0,504`, sàn 4 từ (đoạn
chuyển cảnh 2 giây ra số âm, mà một đoạn không thể rỗng).

Với video 34 giây / 7 đoạn của pilot, lời nhắc nay mang:

```
Video tham khảo dài 34 giây. TOÀN BỘ kịch bản phải đọc hết trong khoảng
chừng ấy — tổng lời đọc không quá 62 từ.
1. [hook]            | 4.0 giây — TỐI ĐA 7 từ  | vai trò: …
2. [problem_context] | 6.0 giây — TỐI ĐA 11 từ | vai trò: …
4. [transition]      | 2.0 giây — TỐI ĐA 4 từ  | vai trò: …
5. [demonstration]   | 8.0 giây — TỐI ĐA 15 từ | vai trò: …
```

Kiểm vòng tròn: 62 từ × 0,504 + 7 câu × 0,39 = **33,9 giây** ≈ đúng 34.

**Ngân sách đặt NGAY SAU số thứ tự**, trước phần mô tả — khối mô tả có thể bị
cắt bớt khi hết ngân sách prompt (vòng `NGAN_SACH_BEAT`), con số này thì không
được phép mất.

### 3. Lời nhắc nói rõ đây là ràng buộc CỨNG

Nói *"nên ngắn gọn"* thì mô hình coi là gợi ý — pilot đã cho thấy nó viết gấp
5 lần khi không bị ràng buộc. Nên lời nhắc nói thẳng: **ngân sách là ràng buộc
cứng**, và **thà bỏ bớt ý còn hơn viết tràn**. Không nói cách xử khi hết ngân
sách thì mô hình sẽ nhồi cho đủ ý rồi tràn.

Ngân sách chỉ tính cho `loi_doc`. `caption` ngắn hơn nữa; `visual_brief` không
bị giới hạn vì nó không được đọc thành tiếng.

### 4. Cảnh báo nhịp chuyển lên H3

Trước H6 dòng cảnh báo chỉ có ở H4 — tức người dùng biết **sau khi** đã tiêu
12 Vox và đi thêm một trang. Nay trang «Viết kịch bản» tự tính ngay sau khi
nhận kết quả, **dùng lại `uoc_luong_giay_doc`** của `autodub.storyboard` chứ
không tự tính lại.

## Nợ kỹ thuật đã nhận, và cách trả

Hai hằng số tốc độ đọc nay có **bản sao** trong `assist.js` (hàm ước lượng ở
Python, lời nhắc dựng ở Node). Bản sao là nợ.

Lãi được trả bằng `tests/test_h6_ngan_sach_tu.py`: đọc hằng số **từ chính tệp
JS** rồi so với Python. Đổi một bên mà quên bên kia thì đỏ ngay, không trôi âm
thầm. Kèm phép kiểm **vòng tròn**: lấy ngân sách của công thức JS, đưa lại qua
hàm ước lượng THẬT của Python, phải ra xấp xỉ số giây ban đầu (±0,6s) — so hai
hằng số chỉ chứng minh chúng bằng nhau, không chứng minh dùng đúng cách.

## Đã kiểm

`tests/test_h6_ngan_sach_tu.py` — **9 test**. Gỡ từng chốt thì đỏ đúng chốt đó:

| Gỡ gì | Test đỏ |
|---|---|
| trường `giay` khỏi `dungInput` | `..._thoi_luong_phai_di_qua_dungInput` |
| cho hằng số JS lệch Python | `..._KHONG_duoc_lech_giua_python_va_node` |
| cảnh báo nhịp ở H3 | `..._canh_bao_NGAY_o_H3` |

Kèm chốt *đừng sửa quá tay*: kịch bản **vừa nhịp phải IM LẶNG** (cảnh báo kêu
cả lúc đúng thì người ta tắt nó khỏi mắt), và **không có blueprint thì không
kết luận gì**.

> **Một lỗi tôi tự tạo khi làm H6, tự bắt khi chạy thử**: nhãn cảnh báo được
> `setVisible(False)` nhưng **không xoá chữ**, nên kịch bản sau sẽ hiện lại
> nguyên cảnh báo của kịch bản trước. Có test riêng chốt việc đó.

Node: **717 đạt / 0 hỏng**.

## CÒN THIẾU — chưa đo trên mô hình thật

Tất cả những gì ở trên chứng minh **lời nhắc mang đúng con số**. Nó **chưa
chứng minh mô hình tuân theo**. Đó là hai chuyện khác nhau, và chỉ một lượt
chạy thật mới trả lời được.

**Mốc đối chứng đã có sẵn**, do chính pilot tạo ra:

| | Trước H6 |
|---|---|
| Video nguồn | 34 giây |
| Kịch bản H3 | **170 giây** |
| Tỉ lệ | **5,0×** |

Lượt đo sau H6: **cùng video, cùng brand**, viết lại (12 Vox), rồi đọc dòng
cảnh báo ngay tại H3. Đạt nghĩa là tỉ lệ **dưới 1,5×**. Không đạt thì ngân
sách chưa đủ cứng và phải siết tiếp — nhưng lúc đó đã có hai điểm đo để so,
thay vì một.

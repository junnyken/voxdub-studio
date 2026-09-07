# Kế hoạch kiểm C50 và C52 trên phim dài — không tốn Vox

> Hai việc còn tồn duy nhất mà **chỉ máy của chủ dự án mới trả lời được**.
> Tài liệu này viết để làm theo từng bước, không cần đọc mã.
>
> **Điểm quan trọng nhất: cả hai đều KHÔNG tốn Vox.** Quét chữ và nghe chép
> đều chạy trên máy. Không cần lồng tiếng cả phim (một phim 40 phút tốn
> khoảng 4.500–8.000 Vox — gần hết ví).

---

## Vì sao hai việc này chưa xong

| | Đã có gì | Thiếu gì |
|---|---|---|
| **C50** — che chữ trên video dài | Quét dày hơn theo thời lượng (5→24 khung), gán khoảng thời gian cho từng vùng, lọc chữ trôi qua (C63) | Mọi bằng chứng là test và tính tay. **Chưa lượt nào trên phim ~40 phút.** |
| **C52** — nghe chép thiếu câu | Đo trên clip 53 giây: 13 câu ở cả bản sạch lẫn bản trộn nhạc, cùng 107 từ. Lượt 30 giây ngày 05/09: đúng 5/5 câu | **Chưa tái hiện được.** Cả hai lượt đều là video NGẮN — mà chủ dự án báo lỗi trên phim dài |

Chưa tái hiện được **không có nghĩa là không có lỗi**. Nó có nghĩa là tôi
đang thiếu đúng một lượt chạy trên đúng loại vật liệu.

---

## Chuẩn bị (một lần)

Cần **tệp phim nằm trên máy** (không phải liên kết) — vì cả hai phép đo đều
đọc thẳng tệp. Phim ~40 phút, loại có chữ cháy sẵn: watermark góc màn hình
và/hoặc phụ đề Trung ở đáy.

---

## Phép đo 1 — C50: che chữ trên phim dài

**Tốn: 0 Vox. Mất: vài phút quét.**

1. Tạo dự án mới → bước 1 chọn **"Tải tệp lên"** → trỏ vào tệp phim.
2. Đi tới bước **"Giọng & Phụ đề"** → mở khung **"Phụ đề & che chữ"**.
3. Bấm **"Quét chữ tự động"** rồi chờ. Phim 40 phút sẽ quét khoảng **20–24
   khung** (cứ ~2 phút một khung), lâu hơn clip ngắn nhiều.
4. **Dừng lại ở đây — đừng bấm chạy lồng tiếng.** Thoát ra cũng được; thứ cần
   đo đã hiện xong trên màn hình.

### Chụp lại giúp tôi

- Câu thông báo màu xanh sau khi quét, **nguyên văn**. Nó có ba con số tôi
  cần: quét bao nhiêu khung · đề xuất bao nhiêu vùng · trong đó bao nhiêu vùng
  *"chỉ che đúng đoạn có chữ"*. Nếu có dòng *"Đã bỏ N vùng chỉ thấy ở một
  khung"* thì đó là C63 đang chạy.
- Ảnh khung hình kèm các vùng được đề xuất.

### Ba câu hỏi lượt này trả lời

1. **Watermark có được đề xuất che không?** Nó nằm lì cả phim nên đúng ra phải
   được giữ lại sau bộ lọc C63.
2. **Có bỏ sót chữ chỉ hiện một đoạn ngắn không?** Lấy mẫu ~2 phút/khung vẫn
   có thể lọt chữ chỉ hiện 30 giây — đây là giới hạn tôi đã ghi trước, cần số
   liệu thật để biết nó tệ tới đâu.
3. **Có còn đề xuất bừa không** (biển hiệu, mặt người)? Đây là thứ C63 sinh ra
   để chặn.

Muốn xem chất lượng xoá chữ thì: xoá hết vùng thừa (**bấm chuột phải vào vùng
để xoá riêng vùng đó** — có từ bản sau v3.16.3; bản hiện tại dùng nút "Xoá
vùng cuối"/"Xoá tất cả"), giữ đúng vùng watermark, rồi bấm **"Nghe thử 30
giây"**. Lượt đó tốn vài chục Vox chứ không phải cả phim.

---

## Phép đo 2 — C52: nghe chép có thiếu câu không

**Tốn: 0 Vox.** Chạy trên máy, không gọi máy chủ.

### Cách A — nhanh, dùng ngay trong app

1. Mở trang **Chép lời** → **"Chọn file…"** → trỏ vào tệp phim.
2. Ngôn ngữ đang nói: **Tiếng Trung**. Xuất ra: **Chỉ phụ đề (.srt)**.
3. Bấm **"Bắt đầu chép lời"**, chờ xong.
4. Mở tệp `.srt` ra, xem **số câu cuối cùng**, rồi tua vài đoạn trong phim để
   đối chiếu: có đoạn nào nhân vật nói mà phụ đề trống không.

Ghi lại: **số câu app ghi được** và **đoạn phút thứ mấy bị thiếu** (chỉ cần
một hai mốc thời gian là đủ cho tôi truy).

### Cách B — đo bằng công cụ, khi cách A thấy nghi

Công cụ nghe lại cùng một tệp bằng nhiều cách khác nhau rồi so số câu/số từ:
nhạc nền có nuốt lời không, bộ lọc im lặng có cắt nhầm không, model to hơn có
nghe ra nhiều hơn không.

Mở PowerShell trong thư mục app rồi chạy:

```
py scripts\so_sanh_nghe.py --video "D:\phim\tap01.mp4" --model small ^
   --python .venv-whisper\Scripts\python.exe
```

Nó in ra bảng dạng:

```
bản trộn (app đang nghe) · lọc im lặng BẬT     13 câu ·  107 từ ·   42.0s có tiếng
bản trộn (app đang nghe) · lọc im lặng TẮT     13 câu ·  107 từ ·   40.8s có tiếng
```

**Cách đọc:** nhìn cột **số TỪ** trước, không phải số câu — hai lượt cắt câu
khác nhau vẫn có thể cùng nội dung. Số từ chênh nhau nhiều mới là mất lời
thật. Chụp cả bảng gửi tôi.

> Phim 40 phút chạy `--model small` khá lâu (vài chục phút, tuỳ máy). Muốn
> nhanh thì cắt lấy ~5 phút quanh đoạn nghi thiếu bằng nút **"Cắt tệp dài…"**
> trên trang Chép lời, rồi đo trên đoạn đó.

---

## Sau khi có số liệu

| Kết quả | Tôi sẽ làm gì |
|---|---|
| Số từ chênh nhiều giữa các cách nghe | Đã khoanh được nguyên nhân (nhạc nền / bộ lọc im lặng / model) — sửa đúng chỗ đó |
| Số từ gần bằng nhau nhưng phim vẫn thiếu đoạn | Không phải bước nghe — nghi bước cắt tệp dài hoặc gộp câu; tôi truy tiếp theo mốc thời gian bạn ghi |
| Quét chữ bỏ sót chữ chỉ hiện ngắn | Tăng mật độ lấy mẫu quanh vùng nghi, hoặc cho chọn tay số khung quét |
| Quét chữ vẫn đề xuất bừa | Ngưỡng lọc C63 chưa đủ — siết thêm theo độ tin cậy OCR |

**Nếu cả hai phép đo đều sạch:** tôi sẽ ghi rõ trong `FEATURES.md` rằng C50 và
C52 đã được kiểm trên phim dài và không tái hiện được, kèm số liệu — thay vì
để chúng nằm mãi trong mục "chưa từng chạy thật".

---

## Điều tôi sẽ KHÔNG làm

Không "sửa đại" chuyện thiếu câu khi chưa tái hiện được. Sửa một lỗi không đo
được nghĩa là không biết mình đã sửa gì, và lần sau nó quay lại thì cũng không
biết vì sao.

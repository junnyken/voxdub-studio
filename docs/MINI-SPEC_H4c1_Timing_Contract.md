# MINI-SPEC H4c-1 — Hợp đồng thời lượng của lớp dựng hình

**Ngày**: 11/09/2026 · **Trạng thái**: đã dựng, 0 Vox
**Phụ thuộc**: H4a (storyboard), H4b (ghép theo thời lượng riêng), H4c (dựng dự án)

> Chủ dự án chốt: *"Chưa nên tự đặt tolerance cho đến khi biết sai lệch phát
> sinh từ đâu."* Spec này vì thế bắt đầu bằng **audit đo được**, và con số
> ngưỡng ở mục D là hệ quả của phép đo chứ không phải một lựa chọn.

## A. Triệu chứng

Ba ảnh `[2,0; 1,0; 3,0]` giây, chuyển cảnh 0,3 giây:

| | |
|---|---|
| Dòng thời gian trong `data/transcript_vi.json` | kết thúc ở **6,00 giây** |
| Video `storyboard_video.mp4` dựng thật ra | **5,40 giây** |

## B. Audit nguyên nhân gốc

Bốn giả thuyết được nêu, **ba cái sai**:

| Giả thuyết | Phán quyết | Bằng chứng |
|---|---|---|
| Chuyển cảnh bị trừ hai lần | ✗ sai | Công thức mốc cũ `sum(giay[:i]) − D×i` nhất quán nội bộ |
| ffmpeg concat rounding / timebase | ✗ sai | Sai lệch đúng bằng `D×(n−1)`, không phải phần lẻ |
| Mất thời lượng ảnh cuối | ✗ sai | Ảnh cuối vào đủ; thiếu hụt tỉ lệ với **số lần chuyển** |
| **Chồng lấn chuyển cảnh không được bù** | ✓ **ĐÚNG** | xem dưới |

**Cơ chế**: `xfade` **chồng** hai cảnh lên nhau. Cảnh sau bắt đầu tại `offset`
và phát chồng lên cảnh trước `duration` giây, nên mỗi lần chuyển **ăn mất
đúng `giay_chuyen` giây** của dòng thời gian. Tổng ra:

```
thời lượng video = Σ giay − giay_chuyen × (n − 1)
```

Điều tệ hơn con số thiếu hụt: **sai lệch cộng dồn**. Đoạn thứ *i* bắt đầu
sớm hơn lời đọc của nó `giay_chuyen × i` giây — người dùng nghe thử thấy
"hơi lệch" ở giữa rồi lệch hẳn ở cuối, và không có gì chỉ ra nguyên nhân.

**Đo thật** (ffmpeg 6.1, công thức cũ):

| Kịch bản | Mong muốn | Thực tế | Thiếu |
|---|---|---|---|
| 3 ảnh `[2; 1; 3]` | 6,00s | 5,40s | 0,60s = 0,3×2 |
| 5 ảnh × 1,0s | 5,00s | 3,80s | 1,20s = 0,3×4 |
| 2 ảnh × 4,0s | 8,00s | 7,70s | 0,30s = 0,3×1 |
| 1 ảnh | 3,00s | 3,00s | 0 (không có chuyển cảnh) |

## C. Bản vá

Bù đúng phần bị ăn, và đặt mốc chuyển cảnh vào **ranh giới thật** của đoạn:

```
dài ảnh đưa vào:  L[i] = giay[i] + giay_chuyen   (mọi ảnh TRỪ ảnh cuối)
                  L[n-1] = giay[n-1]
mốc chuyển cảnh:  offset[i] = Σ giay[:i]          (không trừ gì)
```

Ảnh cuối không cộng thêm vì không có lần chuyển nào sau nó. Mốc là tổng thời
lượng các đoạn trước — tức chuyển cảnh bắt đầu **đúng lúc lời đọc của đoạn
mới bắt đầu**.

## D. Ngưỡng — hệ quả của phép đo, không phải lựa chọn

Sau khi bù, dựng thật trên **8 hình dạng** (2→9 ảnh; 0,34→11,9 giây mỗi ảnh;
tổng 0,68→35,2 giây):

| Kịch bản | Lệch |
|---|---|
| `[0,5; 2,0; 0,5]` | 1,00 khung |
| `[0,4; 0,4; 0,4]` | 0,00 khung |
| `[1,7; 2,3; 0,9; 4,1]` | 1,00 khung |
| `[0,34; 0,34]` | 0,60 khung |
| `[10,0; 0,5]` | 1,00 khung |
| 6 ảnh × 2,5s | 1,00 khung |
| 7 ảnh, tổng 30s | 1,00 khung |
| 9 ảnh × 0,7s | 1,00 khung |

**Lệch tối đa: đúng 1 khung @30fps = 0,0333s — và KHÔNG tăng theo số ảnh hay
độ dài video.** Đó là lượng tử hoá khung hình, tức sàn của thứ 30fps làm
được.

⇒ Ngưỡng là **hằng số** `2/30 s`, không nhân theo độ dài. Lấy 2 khung để chừa
chỗ cho máy khác/bản ffmpeg khác; vẫn nhỏ hơn 9 lần sai lệch cũ của một video
chỉ 3 đoạn.

## E. Cổng cứng

`dung_du_an()` **đo lại video vừa dựng** bằng ffprobe rồi đối chiếu với tổng
dòng thời gian. Quá ngưỡng ⇒ ném `VideoLechThoiLuong`, **không dựng tiếp
transcript**.

Hai ca đều là CHẶN, cố ý:

| Ca | Xử lý |
|---|---|
| Lệch quá ngưỡng | Ném, kèm cả hai con số và số giây lệch |
| **Không đo được** thời lượng | Ném — "không đo được" KHÁC "đo xong thấy ổn" |

Ca thứ hai quan trọng ngang ca thứ nhất: bỏ qua phép đối chiếu khi ffprobe
hỏng thì lỗi quay lại y như cũ mà không ai biết.

## F. Vì sao lỗi này trốn được lâu

Toàn bộ test H4c tiêm một hàm ghép giả ghi 9 byte `b"video gia"` làm "video".
`test_TRINH_CHINH_SUA_MO_DUOC_du_an_vua_dung` chỉ chứng minh
`load_work_dir()` chấp nhận **tên tệp** — không chứng minh có video thật, dài
đúng bao nhiêu, hay có tiếng.

`tests/test_h4c1_thoi_luong.py` (12 test) đóng lỗ đó: 5 test chạy **ffmpeg
thật** trên ảnh PNG thật, và một test đi **trọn đường người dùng** — không
tiêm hàm ghép, không tiêm phép đo.

Chốt quan trọng nhất không phải "độ dài đúng" mà là
`test_LECH_KHONG_tang_theo_so_doan`: bù một phần thì test độ dài đơn lẻ vẫn
qua trong khi sai lệch cộng dồn còn nguyên.

**Đã chứng minh đỏ**: khôi phục công thức cũ ⇒ **6/12 test đỏ**.

## G. Còn lại — KHÔNG thuộc lát này

- **H4c-2 Editor Export Readiness**: dự án dựng xong mở trong Trình chỉnh sửa
  rồi bấm Xuất ngay ⇒ **video câm**, không cảnh báo. Lát riêng.
- **H4d-0 Batch Failure Observability**: `me.hong` không có nơi nào đọc ⇒ mẻ
  vẽ ảnh hỏng cả mẻ thì giao diện im lặng. Lát riêng, phải xong **trước** khi
  gọi cửa sinh ảnh có tính tiền.
- Thời lượng vẫn lấy từ **ước lượng** tốc độ đọc (H4a), chưa phải TTS thật.
  Hợp đồng ở đây bảo đảm video khớp **transcript**; khớp **giọng đọc thật**
  là việc của bước sau khi TTS chạy.

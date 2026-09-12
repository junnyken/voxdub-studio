# MINI-SPEC E6 — Cắt tiền và thời gian của bước đọc chữ

**Ngày**: 12/09/2026 · **Trạng thái**: ĐÃ ĐO trên dữ liệu thật (12/09) — D5 đã dựng, D1 bị bác bỏ
**Phụ thuộc**: H2 (Flow Blueprint), H2b (đọc chữ qua máy chủ)

> Kỷ luật của dự án: *"Chưa nên tự đặt tolerance cho đến khi biết sai lệch
> phát sinh từ đâu."* Spec này vì thế **bắt đầu bằng một giai đoạn chỉ đo,
> không sửa gì**. Mọi ngưỡng ở mục D là ô trống cho tới khi có số.
>
> Lý do phải nhấn mạnh: hai lượt hỏng trước (`hóa đơn` 11/09, `tự động gửi
> dữ liệu` 12/09) đều vì một ngưỡng được chọn bằng suy luận hợp lý thay vì
> bằng phép đo. Ở đây cám dỗ còn lớn hơn — "bỏ khung nào phụ đề trùng lời
> đọc" nghe hiển nhiên đúng, và đó chính là dấu hiệu nguy hiểm.

## A. Triệu chứng — đo từ nhật ký chủ dự án (12/09, 12:37–12:41)

Nguồn: `youtube.com/shorts/9iB1Io8InXg`, 33,6 giây, tiếng Việt.

| Bước | Thời gian | Phần |
|---|---|---|
| OCR **tại máy**, 104 khung | 3 phút 13 giây | **84%** |
| Gửi máy chủ đọc lại, 11 lô | 38 giây | 16% |
| | **3 phút 51 giây** | |

Tiền: 65 khung ÷ 6 = 11 lô × 8 Vox = **88 Vox**, chỉ cho bước đọc chữ.

Một lượt đánh giá gần bốn phút và 88 Vox là quá đắt để lặp lại nhiều lần —
mà lặp nhiều lần đúng là việc chủ dự án cần làm để đánh giá H2.

## B. Audit — một giả thuyết đã bị bác bỏ

| Giả thuyết | Phán quyết | Bằng chứng |
|---|---|---|
| `_khoa_doan` so chuỗi chính xác trên chữ RapidOCR nhiễu → mỗi khung thành một đoạn riêng | ✗ **sai** | xem dưới |
| Phụ đề cháy vào hình lặp lại thứ ASR đã có | chưa kiểm | giai đoạn 0 |

**Vì sao giả thuyết gộp-đoạn sai.** Thoạt nhìn "65 đoạn chữ khác nhau cho
video 34 giây" trông như lỗi khử trùng lặp. Nhưng `moc_lay_mau_thich_ung(33.6)`
trả **99 mốc**: 5 khung/giây ở 5 giây đầu và 5 giây cuối, 2 khung/giây ở
giữa. Video này là sketch có **phụ đề chạy theo lời** — phụ đề đổi mỗi
~0,5 giây, tức gần đúng bằng bước lấy mẫu ở đoạn giữa. 65 trạng thái khác
nhau là **có thật**, không phải lỗi.

Ghi lại đây vì tôi đã báo nhầm nó là lỗi một lần trước khi kiểm.

## C. Giai đoạn 0 — CHỈ ĐO, không sửa gì (làm trước)

**Chi phí với người dùng: 0 Vox.** Chỗ ghi nằm ở
`flow_blueprint.trich_bang_chung`, ngay sau `read_text_regions` — tầng duy
nhất có ĐỦ cả bằng chứng OCR lẫn transcript, mà câu hỏi C.1 cần cả hai.
`read_text_regions` trả về bình thường kể cả khi người dùng bấm **"Bỏ qua,
không tốn Vox"** ở cổng 50 Vox, nên dữ liệu đo vẫn đủ mà không mất đồng nào.

Ghi ra `<work_dir>/data/ocr_chan_doan.json`:

```json
{
  "video": { "dai_giay": 33.6, "so_moc_lay_mau": 99 },
  "thoi_gian": { "ocr_cuc_bo_s": 193.0, "duong": "subprocess",
                 "so_khung": 99, "khoi_dong_s": 21.4, "quet_s": 171.6 },
  "doan": [
    { "khung": [12, 13], "bat_dau_s": 2.4, "ket_thuc_s": 2.6,
      "chu_cuc_bo": "met moi that su khong a",
      "so_vung": 1, "tin_cay_nho_nhat": 0.83 }
  ],
  "transcript": [ { "bat_dau_s": 4.5, "ket_thuc_s": 5.9, "chu": "..." } ]
}
```

Đủ để trả lời **bốn câu hỏi**, mỗi câu là một quyết định thiết kế:

1. **Bao nhiêu phần đoạn OCR trùng lời đọc ở cùng mốc thời gian?**
   → quyết định đòn bẩy chính có thật hay không.
2. **Phần không trùng nằm ở đâu?** Nếu chúng dồn vào 5 giây đầu/cuối thì đó
   đúng là overlay/CTA — thứ H2 cần — và luật lọc phải chừa chúng ra.
3. **Nếu bỏ các đoạn trùng, còn bao nhiêu lô?** → số Vox tiết kiệm được thật.
4. **OCR cục bộ 3 phút 13 giây phân bổ thế nào?** Khởi động engine là chi
   phí CỐ ĐỊNH — cắt khung không làm nó nhỏ đi. Phần quét thì co theo tỉ lệ.

> Câu 4 quan trọng riêng: cả mục D dưới đây ngầm giả định thời gian tỉ lệ với
> số khung. Chưa đo mà đã tin thì có thể bỏ công cắt khung để rồi vẫn chờ
> ba phút.
>
> **Bản đầu của spec này nói cần hai video dài khác nhau mới tách được hai
> phần đó. Không cần** — `text_regions_worker.py` nay đo riêng `khoi_dong_s`
> và `quet_s` ngay trong một lượt: một mốc trước `RapidOCR()`, một mốc trước
> vòng quét. Đo ở tiến trình cha thì không tách được, vì đường CHÍNH là
> subprocess và từ ngoài chỉ thấy một con số gộp.

## C-BIS. SỐ ĐO THẬT (12/09) — và hai kết luận sai của tôi

Chủ dự án chạy một lượt, bấm «Bỏ qua», gửi `ocr_chan_doan.json`. Nguồn 36,2
giây, 104 mốc lấy mẫu, 65 đoạn.

### D1 BỊ BÁC BỎ bằng số đo

| | |
|---|---|
| Đoạn OCR trùng lời đọc (≥60% tiếng chung, cùng mốc) | **10/65 = 15%** |
| Bỏ hết phần trùng | 11 lô → 10 lô, **tiết kiệm 8 Vox** |

Giả thuyết chính của tôi — *"phụ đề cháy vào hình lặp lại đúng thứ ASR đã
cho"* — sai. Phần lớn chữ trên hình là **ảnh chụp màn hình phần mềm MISA**
(có khung tới 64 vùng chữ: bảng hoá đơn, menu, thông báo), không phải phụ đề.

### Tôi đã kết luận sai HAI LẦN trước khi có dữ liệu

1. Đoán "65 đoạn là lỗi gộp đoạn" → 2. tự bác bỏ: *"65 là thật, video có phụ
đề chạy theo lời"*. Dữ liệu cho thấy **lần đoán đầu mới đúng**:

```
'supersale d onn& am am'   khung 7
'supersale d onn&amam'     khung 8    cùng caption, lệch 2 ký tự
'supersale d onn&am am'    khung 9
'supersale d onn&amam'     khung 10
```

`_khoa_doan` so chuỗi NGUYÊN VĂN, nên bốn khung này thành bốn đoạn riêng và
bốn khung được gửi đi thay vì một.

### D5 (mới) — gộp khi chữ GẦN GIỐNG. Đây mới là đòn bẩy.

    giống >= 75%: 65 -> 31 đoạn = 6 lô = 48 Vox
    giống >= 80%: 65 -> 33 đoạn = 6 lô = 48 Vox   <- chọn
    giống >= 85%: 65 -> 34 đoạn = 6 lô = 48 Vox
    giống >= 90%: 65 -> 40 đoạn = 7 lô = 56 Vox
    giống >= 95%: 65 -> 47 đoạn = 8 lô = 64 Vox

75–85% là một CAO NGUYÊN (đều 48 Vox) → lấy 80% ở giữa. Soi tay cả 17 nhóm
gộp được ở mức đó: **không nhóm nào gộp nhầm hai caption khác nhau**.

Chạy lại bằng mã đã cài, trên đúng tệp đó: **65 → 35 đoạn, 88 → 48 Vox
(giảm 46%)**.

Kèm theo: đại diện của mỗi đoạn nay là khung **đọc rõ nhất**, không phải
khung đầu — ca thật `surersale` (0,944) rồi `supersale` (0,989), gửi khung
đầu là trả tiền để máy chủ đọc lại một khung vốn đã đọc sai.

### C.4 vẫn CHƯA trả lời được — thời gian không giảm

Tệp thật **không có** `khoi_dong_s`/`quet_s` dù mã đã có trong v3.17.14.
Chưa rõ vì sao. Đã thêm tổng đo ở tiến trình cha làm mức chặn trên và một
dòng cảnh báo nói thẳng là chưa tách được — tuyệt đối không suy hai phần ra
từ con số gộp.

**Vì vậy: D5 cắt TIỀN (88→48 Vox) nhưng KHÔNG cắt thời gian.** OCR cục bộ
vẫn quét đủ 104 khung. Muốn nhanh hơn thì phải qua D3, mà D3 cần đúng con số
C.4 đang thiếu.

## D. Các đòn bẩy — ngưỡng để TRỐNG tới khi có số đo

| # | Đòn bẩy | Cắt được | Rủi ro | Ngưỡng |
|---|---|---|---|---|
| D1 | Bỏ đoạn OCR đã được transcript phủ ở cùng mốc thời gian | tiền + phần gửi mạng | mất caption vừa trùng lời vừa là overlay có ý nghĩa | *(chờ C.1)* |
| D2 | Trần số khung gửi máy chủ, rải đều dòng thời gian | tiền | mất bằng chứng ở video nhiều chữ — đúng loại video H2 cần đọc kỹ | *(chờ C.3)* |
| D3 | Giảm mật độ lấy mẫu ở đoạn giữa | thời gian **và** tiền — *chỉ khi C.4 cho thấy phần quét lớn hơn phần khởi động* | bỏ sót caption chớp nhanh ở giữa | *(chờ C.4)* |
| D4 | Bỏ qua OCR khi transcript đã dày | cả hai | video không lời nhưng nhiều chữ sẽ mất hết bằng chứng | *(chờ C.1)* |

| D5 | **Gộp khung liền nhau khi chữ GẦN GIỐNG** | tiền: 88 → 48 Vox | gộp nhầm hai caption ⇒ mất hẳn một cái | **80%** ✅ đã dựng |

~~**D1 là ứng viên chính**~~ — **bị bác bỏ**, chỉ 15% trùng, tiết kiệm 8 Vox.
Xem mục C-BIS. Đòn bẩy thật là **D5**.

D3 (giảm mật độ lấy mẫu) là đòn bẩy duy nhất chạm tới THỜI GIAN, nhưng nó
phụ thuộc C.4 — con số hiện chưa lấy được.

## E. Ràng buộc — không được vi phạm

1. **Không tự bỏ bằng chứng mà không nói.** Bỏ bao nhiêu đoạn, vì lý do gì,
   phải vào `samplingPolicyUsed` — trường này đi thẳng vào lời nhắc và là
   thứ cho mô hình biết độ tin cậy của phần OCR. Bỏ im lặng là để mô hình
   nói chắc nịch trên nền bằng chứng đã bị cắt.
2. **Không đổi hành vi mặc định trước khi đo.** Giai đoạn 0 chỉ thêm tệp
   chẩn đoán.
3. **Giữ cổng 50 Vox.** Nó vừa chạy đúng trên máy chủ dự án (12/09) và là
   thứ duy nhất hiện chặn được một lượt đắt ngoài dự tính.
4. **Tệp chẩn đoán không được chứa gì dẫn về video gốc** ngoài thứ đã có
   trong `work_dir` — cùng ràng buộc với Constraint 2 của H2.

## F. Cách kiểm

- Giai đoạn 0: chạy thật một lượt trên đúng nguồn 12/09, bấm **"Bỏ qua"**,
  lấy tệp `ocr_chan_doan.json`. Không tốn Vox.
- Sau khi có luật: chạy lại **cùng nguồn đó**, so ba số — số lô, tổng thời
  gian, và số beat trong kết quả. Beat ít đi nghĩa là đã cắt mất bằng chứng
  thật, không phải tiết kiệm.
- Chốt hồi quy: một video **không lời, nhiều chữ** phải vẫn ra đủ bằng chứng
  OCR sau khi áp D1 — đây là ca mà "bỏ đoạn trùng transcript" dễ bỏ sạch.

## G. Thứ tự

1. Giai đoạn 0 (đo) — nhỏ, 0 Vox, không đổi hành vi.
2. Đọc số → chọn đòn bẩy → điền ngưỡng vào mục D.
3. Dựng, kèm test hồi quy ở mục F.

Không nhảy sang bước 3.

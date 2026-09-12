# MINI-SPEC E6 — Cắt tiền và thời gian của bước đọc chữ

**Ngày**: 12/09/2026 · **Trạng thái**: giai đoạn 0 ĐÃ dựng (v3.17.14) — chờ số đo thật
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

## D. Các đòn bẩy — ngưỡng để TRỐNG tới khi có số đo

| # | Đòn bẩy | Cắt được | Rủi ro | Ngưỡng |
|---|---|---|---|---|
| D1 | Bỏ đoạn OCR đã được transcript phủ ở cùng mốc thời gian | tiền + phần gửi mạng | mất caption vừa trùng lời vừa là overlay có ý nghĩa | *(chờ C.1)* |
| D2 | Trần số khung gửi máy chủ, rải đều dòng thời gian | tiền | mất bằng chứng ở video nhiều chữ — đúng loại video H2 cần đọc kỹ | *(chờ C.3)* |
| D3 | Giảm mật độ lấy mẫu ở đoạn giữa | thời gian **và** tiền — *chỉ khi C.4 cho thấy phần quét lớn hơn phần khởi động* | bỏ sót caption chớp nhanh ở giữa | *(chờ C.4)* |
| D4 | Bỏ qua OCR khi transcript đã dày | cả hai | video không lời nhưng nhiều chữ sẽ mất hết bằng chứng | *(chờ C.1)* |

**D1 là ứng viên chính**, nhưng chỉ khi C.1 cho thấy tỉ lệ trùng cao *và*
C.2 cho thấy overlay tách bạch được khỏi phụ đề. Nếu C.2 cho thấy chúng lẫn
vào nhau thì D1 phải bỏ, và D2/D3 lên thay.

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

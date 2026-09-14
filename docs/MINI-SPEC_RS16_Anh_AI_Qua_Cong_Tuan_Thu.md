# Mini-Spec RS-16 — Ảnh do AI vẽ phải qua cổng tuân thủ trước khi thành video

**Ngày:** 14/09/2026
**Trạng thái:** đã làm, 12 test, hai phép chứng minh phủ định đều đỏ đúng chốt.
**Phạm vi:** `autodub/du_an_tu_kich_ban.py`, `autodub_gui/pages/storyboard_page.py`,
`autodub_gui/workers.py`. **Không** đụng máy chủ, **không** đụng `image.scene.stage`,
**không** đụng C1/H4d vốn đã đúng.

---

## 1. Khoảng hở, nói bằng đường đi của dữ liệu

H4d vẽ ảnh xong trả về một bản ghi đầy đủ: `phan_quyet`, `ly_do`, `da_kiem`,
`da_dong_nhan`, `bam`. Trang H4 chỉ lấy **một trường**:

```python
self._anh[i] = ket.duong_dan      # ← còn lại vứt hết
```

`DungDuAnWorker` vì thế nhận một danh sách **chuỗi**. Mà
`product_video.kiem_lai_truoc_khi_xuat()` cần một `AnhNguon` có đủ bốn trường kia.
Không có chúng thì **hàm ấy không có gì để chạy** — cổng tồn tại, được viết đúng,
và không bao giờ được gọi.

Đây không phải suy đoán: `product_video.dung_video_tu_anh_nguoi_dung` đã có sẵn
cảnh báo trong docstring **từ trước khi H4d ra đời**:

> ⚠ Khi H4d thêm đường sinh ảnh AI: ảnh sinh ra KHÔNG được đi qua hàm này.
> Chúng phải qua `dung_video()` với đủ ba phép kiểm.

H4d lên rồi, cảnh báo thì vẫn nằm đó.

**Vì sao chưa nổ trên thực tế:** `image.scene.stage` mặc định `off` ở máy chủ nên
chưa máy nào sinh được ảnh minh hoạ. Cổng phải đóng **trước** khi chốt đó chuyển
sang `calibration`, không phải sau.

## 2. Chốt đặt ở đâu, và vì sao không đặt ở giao diện

Chốt nằm trong `dung_du_an()` — **hàm duy nhất tạo ra tệp video từ kịch bản**, tức
chỗ cuối cùng còn nói được "không". Cổng đặt ở nút bấm thì mọi lối gọi khác (test,
script, bản sau, một trang GUI thứ hai) đều đi vòng qua được mà không ai biết.

Và **kiểm lại tại chỗ dựng**, không tin cờ đã lưu: giữa lúc vẽ xong và lúc dựng có
thể là vài ngày. `kiem_lai_truoc_khi_xuat` so lại **băm** của tệp, nên tệp bị sửa
sau khi kiểm thì nội dung không còn là tấm đã được duyệt nữa.

```python
if anh_ai:
    kq = kiem_lai_truoc_khi_xuat([...])
    if not kq.cho_phep:
        raise AnhAiChuaDat("Có ảnh do AI vẽ chưa dùng để bán được — " + chi_tiet)
```

`AnhAiChuaDat` là lỗi **riêng**, không gộp vào `ThieuAnh`: ở đây ảnh CÓ, kịch bản
SẠCH, chỉ tấm ảnh là không được phép đi vào một video đem bán. Câu báo nói thẳng
hai lối ra — vẽ lại, hoặc tự chụp ảnh cho đoạn ấy.

## 3. Cái bẫy từ vựng, và hướng an toàn

Hai mini-spec dùng hai bộ chữ cho **cùng một ý**:

| Nơi | Trường | Giá trị "dùng được" |
|---|---|---|
| H4d `story_image.kiem_anh` | `phan_quyet` | `"DAT"` |
| C1 `product_video.AnhNguon` | `ket_luan` | `"SAFE"` |

Ánh xạ phải **viết ra**, không để ngầm: dịch ẩu theo một chiều thì chặn sạch mọi
ảnh, theo chiều kia thì mở toang cổng — và **cả hai đều im lặng**.

```python
_PHAN_QUYET_SANG_KET_LUAN = {"DAT": "SAFE"}
```

Phán quyết lạ **giữ nguyên chuỗi gốc** nên không khớp `"SAFE"` và bị chặn. Đó là
hướng an toàn có chủ đích: một mã lạ nghĩa là bản H4d mới thêm trạng thái mà cổng
này chưa biết, và "chưa biết" phải là "không cho qua".

## 4. Giao diện: giữ bản ghi, và XOÁ nó đúng lúc

`storyboard_page` nay giữ `self._anh_ai: dict[int, dict]` song song với `self._anh`.

Phần khó không phải là giữ, mà là **xoá**: người dùng vẽ ảnh AI cho đoạn 3 rồi đổi
ý chọn ảnh mình chụp cho chính đoạn đó. Bản ghi AI cũ mà còn nằm lại thì phán quyết
của **tấm ảnh đã bị thay** sẽ được đem đi kiểm — băm không khớp, chặn oan; hoặc tệ
hơn, nếu băm tình cờ khớp thì một tấm ảnh người dùng bị gán nhãn AI. Nên `.pop(i, None)`
nằm ở **cả hai** đường chọn ảnh (`_chon_mot`, `_chon_nhieu`), và toàn bộ dict reset
trong `dat_kich_ban`. Có một test đọc mã nguồn để bảo đảm cả hai đường đều xoá.

## 5. Bằng chứng

`tests/test_rs16_anh_ai_qua_cong_tuan_thu.py` — **12 test**:

**Chặn (5):** ảnh chưa kiểm; ảnh bị phán `CO_SAN_PHAM` bịa; ảnh chưa đóng nhãn
AI-generated; **tệp bị sửa sau khi kiểm** (băm lệch); phán quyết lạ thì chặn chứ
không cho qua.

**Cho qua (3):** ảnh `DAT` đủ ba phép kiểm; ảnh người dùng tự chọn không bị đòi
kiểm ảnh AI; **trộn** ảnh AI và ảnh người dùng trong cùng một kịch bản.

**Nối dây (4):** ánh xạ `DAT`→`SAFE` được khai báo tường minh; trang H4 giữ phán
quyết khi vẽ và xoá khi người dùng thay ảnh; mã nguồn xoá bản ghi ở **cả hai**
đường chọn ảnh; worker truyền phán quyết xuống tầng dựng.

### Chứng minh phủ định (bắt buộc — test xanh không tự chứng minh mình có tác dụng)

| Gỡ gì | Kết quả |
|---|---|
| `if anh_ai:` → `if False:` (bỏ cổng) | **5 đỏ** — cả bốn ca chặn + ca phán quyết lạ |
| `_PHAN_QUYET_SANG_KET_LUAN = {}` (bỏ ánh xạ) | **5 đỏ** — gồm cả hai ca *cho qua* và ca khai báo ánh xạ |

Hai lần gỡ cho hai tập đỏ **khác nhau**, đúng như thiết kế: cổng giữ chiều chặn,
ánh xạ giữ chiều cho qua. Nếu gỡ một trong hai mà tập đỏ giống nhau thì một trong
hai là thừa.

### Một bẫy trong chính bộ test, đã sửa

Ba test "phải xanh" lúc đầu đỏ với `VideoLechThoiLuong` — không phải cổng RS-16
chặn, mà `do_thoi_luong` giả của tôi trả 10,0s trong khi dòng thời gian là 8,84s,
nên **cổng H4c-1** nổ trước. Sửa bằng cách tính tổng thật qua `dung_storyboard()`.
Ghi lại vì nó là ví dụ đúng kiểu: test đỏ vì **đồ giả sai**, không phải vì mã sai.

## 6. Cố ý KHÔNG làm

- **Không** bật `image.scene.stage`. Đó là thao tác của chủ dự án trên admin.
- **Không** thêm vân tay máy vào `image.scene.calibration.devices` — việc ấy làm
  **sau** khi lát này lên bản phát hành, không phải trước.
- **Không** đụng `kiem_lai_truoc_khi_xuat`, `AnhNguon`, hay `story_image.kiem_anh`.
  Chúng đã đúng; khoảng hở nằm ở đoạn dây nối, và chỉ sửa đoạn dây nối.
- **Không** để `dung_du_an` tự vẽ lại ảnh bị chặn. Cổng tuân thủ mà tự chữa thì
  không còn là cổng.

## 7. Thứ tự việc sau lát này

1. Lát này lên bản phát hành.
2. Chủ dự án thêm vân tay máy vào `image.scene.calibration.devices`.
3. Chạy 20–30 ảnh thật, **soi tay từng phán quyết**, theo chốt ba nấc đã quy định.
4. Chỉ khi ba nấc đó đạt mới bàn tới chuyện chuyển `stage` khỏi `calibration`.

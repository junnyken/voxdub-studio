# Mini-Spec D5 — Không chốt nào so PROD với MAIN

**Ngày:** 15/09/2026. **Trạng thái:** rà soát xong, bắt đầu dựng.

---

## 1. Khoảng hở, bằng chứng chứ không phải suy đoán

Chuỗi đã xảy ra thật 14/09:

1. `df980b2` (bản vá rò rỉ CSDL) qua hết phép kiểm → sinh nhánh deploy →
   gọi cổng Vibe Host → **404** (sự cố hạ tầng) → job đỏ. Prod giữ bản cũ.
2. `6baf2f2` (chỉ sửa tài liệu) chạy CI. Bước quyết định "có cần deploy không"
   so nhánh deploy **mới** với nhánh deploy **lần trước** — hai bản giống nhau
   ⇒ `app=0` ⇒ **bỏ qua deploy** ⇒ job báo **thành công**.
3. Prod chạy mã cũ **21 giờ**, CI xanh toàn bộ, không một tín hiệu đỏ nào.

Đo được tại 15/09 06:32 UTC trước khi sửa tay: `/health` trả
`commit = 3a8f6809c800`, `uptimeS = 77237` (≈21,4 giờ) — prod **không hề khởi
động lại** sau lượt `6baf2f2` lúc 10:42 UTC ngày 14/09, dù job `trien-khai-prod`
của lượt ấy báo `success`.

### Gốc rễ, đọc từ chính workflow

```bash
truoc_app=$(git rev-parse origin/deploy/vays-control-server)   # ← BẢN DỰNG LẦN TRƯỚC
...
if ! git diff --quiet "$truoc_app" "$sau_app" -- webapp/ ...; then app=1; fi
```

`truoc_app` là **thứ ta đã dựng lần trước**, không phải **thứ prod đang chạy**.
Phép so ngầm giả định lần trước đã lên prod thật. Một lượt deploy hỏng phá vỡ
giả định đó, và không chốt nào bắt được:

| Chốt đang có | So cái gì | Vì sao không cứu được |
|---|---|---|
| `--sha-nhanh` | đầu nhánh deploy trên remote | chỉ chạy **khi có deploy** |
| `--sha-nguon` | SHA prod tự khai ở `/health` | chỉ chạy **khi có deploy** |
| `deploy-branch-drift` | nhánh deploy ↔ `main` | đúng, và vẫn đúng khi prod tụt lại |
| `app == 1` | bản dựng này ↔ bản dựng trước | mù với việc prod đang chạy gì |

D3 đã dựng được hai chốt tốt — nhưng cả hai nằm **bên trong** lượt deploy. Deploy
không chạy thì chốt cũng không chạy. Đó đúng là chỗ hở.

## 2. Bất biến D5 phải giữ

> Prod đúng nhịp ⟺ **mã nguồn sinh ra ảnh prod đang chạy** giống hệt mã nguồn
> mà `main` bảo phải chạy.

Chú ý cách phát biểu: **không** phải `prod.commit == main HEAD`. Một commit chỉ
sửa tài liệu KHÔNG deploy lại — đó là chính sách cố ý (C58 chốt 2), nên prod
đứng ở commit mã gần nhất là **đúng**. So SHA trực tiếp sẽ đỏ ở mọi commit tài
liệu, tức biến chốt thành bộ canh kêu nhầm — và backlog dự án đã ghi: *bộ canh
hay kêu nhầm thì người ta tắt nó đi, còn tệ hơn không có*.

Nên phép so phải là **theo nội dung nguồn**, không theo SHA.

## 3. Thiết kế

### 3.1 So nguồn, và chống danh sách nguồn mục nát

`webapp/` và `dub-worker/` là bản chép thuần từ vài thư mục nguồn (đọc từ
`scripts/gen_*.sh`):

| Dịch vụ | Nguồn |
|---|---|
| `voxdub-app` | `control_server/`, `website/`, + chính script sinh |
| `voxdub-dub-worker` | `autodub/`, `control_server/worker-dub/`, vài `scripts/*.py`, + chính script sinh |

Danh sách nguồn chép tay là thứ sẽ mục nát: ai thêm một dòng `cp` vào script
sinh mà quên cập nhật danh sách thì D5 **im lặng bỏ sót**. Nên kèm một chốt
**tĩnh**: đọc chính script sinh, bóc mọi đường dẫn nó chép, và bắt buộc mọi
đường dẫn ấy phải nằm trong danh sách. Thêm `cp` mà quên khai ⇒ test đỏ.

### 3.2 Đặt ở đâu

Job mới `kiem-prod-theo-main`, `needs: [trien-khai-prod]`, `if: always()`.

**Sau** lượt deploy, không phải trước — chạy trước thì mọi commit mã đều đỏ oan
vì prod chưa kịp lên. Sau đó thì ba ca đều đúng:

| Tình huống | Kết quả mong muốn |
|---|---|
| Deploy vừa xong | prod khớp ⇒ **xanh** |
| Deploy hỏng | prod tụt lại ⇒ **ĐỎ** ← tín hiệu đang thiếu |
| Deploy bị bỏ qua (`app=0`) | prod đã khớp sẵn ⇒ xanh; **còn tụt lại ⇒ ĐỎ** ← đúng ca 14/09 |

### 3.3 Không kết luận được ≠ đã đúng

Prod không trả lời (mạng chập, cổng hỏng) thì D5 **không được** báo xanh. Nhưng
cũng không nên đỏ ngay vì một cú chập mạng — đó lại là kêu nhầm. Chọn: thử lại
vài lượt, hết lượt vẫn không hỏi được thì **cảnh báo to** và thoát 0, kèm ghi rõ
trong nhật ký là *chưa xác minh được*, không phải *đã đúng*.

Đây là đánh đổi có ý thức, ghi ra để lần sau ai đọc còn biết nó là lựa chọn chứ
không phải sơ suất.

## 4. Worker phải tự khai SHA

`/health` của worker trả chuỗi `"ok"` thuần. Hậu quả: chốt `--sha-nguon` phải bỏ
trống cho worker (workflow đã ghi chú đúng chuyện này), và D5 cũng không phủ nổi
worker. Đây là lý do việc này đi liền D5 chứ không tách ra.

Sửa: `_HealthHandler` trả JSON `{"ok": true, "commit": "<12 ký tự>"}`, đọc từ
`dub-worker/SOURCE_SHA` — **cùng đúng cách** `control_server/src/version.js` đang
làm, không bịa cách mới. Không có tệp (chạy từ mã nguồn, chạy test) là chuyện
bình thường ⇒ `commit` vắng mặt, im lặng.

Kiểm chéo đã làm trước khi sửa: `_phu_thuoc_hong()` parse JSON và chỉ soi trường
`db`; worker không có trường đó ⇒ trả `None` ⇒ **không** biến thành lượt deploy
đỏ. `_sha_lech()` sẽ bắt đầu chạy được cho worker.

## 5. Cố ý KHÔNG làm

- **Không tự deploy lại khi phát hiện lệch.** D5 là chốt *phát hiện*. Chốt tự
  chữa thì lần sau hỏng thật sẽ tự che mất. Làm cho nó **nhìn thấy** trước đã.
- **Không đổi khoá, cổng, webhook, branch protection.**
- **Không đụng chính sách "chỉ deploy dịch vụ có thư mục build đổi"** (C58 chốt
  2) — nó đúng, và tiết kiệm ~11 phút dựng worker mỗi lượt.
- **Không thêm lịch chạy định kỳ** trong lát này. Lát này bảo đảm *lượt push kế
  tiếp* phát hiện ra; muốn phát hiện khi nhiều ngày không ai push thì cần một
  lượt chạy theo giờ — ghi lại làm việc sau, đừng gộp.

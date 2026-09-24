# MINI-SPEC D6 — Nhánh deploy chỉ mang thứ cần dựng

- **Họ:** D — toàn vẹn đường deploy (tiếp D3, D5)
- **Tác giả:** Claude (viết từ đo mã thật, 24/09/2026)
- **Trạng thái:** ĐÃ LÀM 24/09/2026 — trừ mục D (xem §7)

---

## 0. Audit — đo được, không suy đoán

### (a) Triệu chứng

Gọi `redeploy_project` cho **cả hai** dịch vụ đều bị chặn:

```
ENV_REQUIRED: Cần bạn cấp 15 biến môi trường trước khi triển khai lại:
WHISPER_BEAM_SIZE, VIENEU_MAX_WORKERS, PARALLEL_WORKERS, TRANSLATE_DOMAIN,
TRANSLATE_CONTEXT, TRANSLATE_PRONOUNS, TRANSLATE_GLOSSARY,
TRANSLATE_STYLE_NOTES, SUBTITLE_COLOR, SUBTITLE_OUTLINE_COLOR,
SUBTITLE_BOX_COLOR, KARAOKE_HIGHLIGHT_COLOR, DISPLAY_NAME, VOXDUB_API_URL,
VOXDUB_API_KEY
```

Cả 15 biến là biến của **app desktop**. Máy chủ web đọc **0/15** (rà
`process.env.<TÊN>` khắp `control_server/src` + Dockerfile + compose: không
khớp cái nào, và không có chỗ nào tra `process.env[...]` động).

### (b) Nguyên nhân gốc — đã đo, không phải suy đoán

Repo có **ba** tệp `.env.example`:

| Tệp | Số biến | Có biến nào bị đòi? |
|---|---|---|
| `.env.example` (gốc repo) | 65 | **cả 15** |
| `control_server/.env.example` | 22 | 0 |
| `website/.env.example` | 1 | 0 |

Nền tảng đọc tệp ở **gốc nhánh**, không đọc tệp trong build context — nếu nó
đọc build context (`webapp/control_server/.env.example`) thì đã đòi 22 biến
của máy chủ, chứ không đòi 15 biến desktop.

Và nó không đòi cả 65 biến. Nó lọc. Dấu hiệu lọc đo được chính xác:

| Dạng khai trong `.env.example` | Số biến | Bị đòi? |
|---|---|---|
| `VAR=` (rỗng hẳn) | **11** | có |
| `VAR=#FFFFFF` (giá trị mở đầu bằng `#`) | **4** | có |
| còn lại (`WHISPER_MODEL=auto`, `VOICE_SPEED=1.0`…) | 50 | không |

**11 + 4 = đúng 15**, và trong 65 biến **không biến nào khác** có một trong
hai tính chất trên. Nghĩa là bộ quét của nền tảng coi `#` là mở chú thích, nên
`SUBTITLE_COLOR=#FFFFFF` với nó là **rỗng** — rồi nó đòi mọi biến rỗng.

> **App KHÔNG bị lỗi này.** Đã đo: `python-dotenv` (thứ `autodub/config.py:408`
> dùng) trả đúng `'#FFFFFF'`, và `set -a; . .env` trong bash cũng trả đúng
> `#FFFFFF`. Lỗi chỉ nằm ở bộ đọc của nền tảng. Không cần sửa `.env.example`
> vì app — nếu sửa thì chỉ để né bộ quét, và đó là lý do yếu.

**Tại sao tệp gốc lại có mặt trên nhánh deploy:** nhánh sinh bằng **worktree
từ `main`**, nên nó mang **cả repo**. Script chỉ *thêm* một thư mục gốc mới
chứa bản chép đã chọn lọc:

| Nhánh | Thư mục build | Phần còn lại của nhánh |
|---|---|---|
| `deploy/vays-control-server` | `webapp/` | cả repo — **trơ với lượt build** |
| `deploy/vays-dub-worker` | `dub-worker/` | cả repo — **trơ với lượt build** |

Lý do có thư mục gốc mới đã ghi trong script: *"VAYS build theo model 1 subdir
= build context, và subdir chỉ nhận THƯ MỤC CON Ở NGAY GỐC REPO"*. Hệ quả
ngoài ý muốn: `.env.example` của app desktop đi theo lên gốc nhánh deploy.

### (b2) Nền tảng có HAI cơ chế — chỉ MỘT cái chặn

Đo từ nhật ký dựng 24/09 (lượt `ecd8c59`, sau khi đã gỡ tệp):

| Cơ chế | Nguồn | Hành vi | Số biến |
|---|---|---|---|
| `ENV_REQUIRED` | `.env.example` ở **gốc nhánh** | **CHẶN** deploy | 15 |
| `[Env] Phát hiện … CHƯA khai báo` | quét **mã nguồn** | chỉ *"cân nhắc thêm"* | 20 |

Hai danh sách gần như rời nhau (`ADMIN_TOKEN`, `DEMUCS_*`, `HF_TOKEN`,
`CORS_ORIGIN`… ở danh sách 20; chỉ `DISPLAY_NAME` trùng). **Đừng cấp 20 biến
kia** — nó là lời khuyên, không phải cổng, và lượt dựng 24/09 chạy qua nó bình
thường. Ghi ở đây vì đọc vội rất dễ tưởng đây là `ENV_REQUIRED` quay lại.

### (c) Vì sao KHÔNG cấp bừa 15 biến cho xong

Đã cấp cho `voxdub-app` — được, vì máy chủ web không đọc biến nào trong 15.
Với `voxdub-dub-worker` thì **không**, và đây là chỗ phải nói rõ:

- **5 biến `TRANSLATE_*`** đi thẳng vào lời nhắc dịch.
  `autodub/text/translate_hint.py:276-277`:
  `if domain: lines.append(f"- **Video topic/domain**: {domain}")`, đọc từ env
  qua `autodub/config.py:524`. Worker chạy `autodub.cli dub` **không truyền
  cấu hình dịch**, nên nó lấy từ env. Bất kỳ giá trị nào khác rỗng đều thêm
  một dòng **bịa** vào mọi lượt dịch.
- **`VOXDUB_API_URL`** khác rỗng làm `saas_client.is_configured()` thành
  `true` (`autodub/saas_client.py:114-116`: `return bool(resolve_api_url())`)
  — **lật worker sang chế độ SaaS**. `CLAUDE.md` của dự án ghi đây là **cổng
  duy nhất** phân biệt hai chế độ.
- Cổng **từ chối cả chuỗi rỗng lẫn một dấu cách** (`ENV_VALUE_REQUIRED`), nên
  không có giá trị nào vừa qua cổng vừa rỗng-về-nghĩa.

Cấp bừa = đổi hành vi một dịch vụ đang chạy, đổi lấy việc một cổng thôi kêu.

### (d) Hệ quả đang chịu

`kiem-prod-theo-main` **đỏ vĩnh viễn** vì worker tụt 4 tệp dưới `autodub/`.
Cổng nói ĐÚNG — ảnh worker thật sự chứa bản cũ. Nhưng một cổng đỏ liên tục sẽ
thành cổng không ai đọc, và đó chính là cách prod từng tụt **19 tệp** suốt từ
22/09 mà không ai hay.

### (e) Đã kiểm: dọn gốc nhánh KHÔNG phá chốt nào

| Chốt | So cái gì | Bị ảnh hưởng? |
|---|---|---|
| `kiem_nhanh_deploy.py` (drift) | chỉ các cặp `main:<đường> ↔ nhánh:webapp/…` và `dub-worker/…` | **không** |
| `kiem_prod_theo_main.py` (D5) | hai SHA của `main`, qua `NGUON[...]` | **không** |
| `test_d3_deploy_integrity.py` | cặp commit trên `main` | **không** |

Không chốt nào đọc phần repo ở gốc nhánh deploy.

---

## 1. Đọc trước khi sửa

- `scripts/gen_vays_control_server_branch.sh`, `scripts/gen_vays_dub_worker_branch.sh`
- `scripts/kiem_nhanh_deploy.py`, `scripts/kiem_prod_theo_main.py`
- `tests/test_d3_deploy_integrity.py`, `tests/test_d5_prod_theo_main.py`
- `control_server/worker-dub/Dockerfile`, `control_server/Dockerfile`
- `docs/TEST_LOG.md` mục D3, D5, C57, C58, V90

## 2. Mục tiêu

Nhánh deploy **chỉ mang thứ lượt build cần**, để phép quét cấu hình của nền
tảng không còn đòi biến của một ứng dụng khác — và để hai dịch vụ deploy lại
được mà không phải đặt một giá trị bịa nào.

## 3. Rào chắn

1. **Không đổi nội dung thư mục build.** `webapp/` và `dub-worker/` phải
   giống hệt trước và sau. Đây là thứ đi vào ảnh Docker; đụng vào nó là đổi
   phạm vi từ "dọn nhánh" sang "đổi bản dựng".
2. **Không nới chốt nào.** D3, D5, drift giữ nguyên hành vi. Nếu một chốt đỏ
   sau thay đổi này thì đó là tín hiệu thật, không phải phiền toái cần tắt.
3. **Không sửa cổng cho nó thôi kêu.** `kiem-prod-theo-main` đang nói đúng:
   ảnh worker CHỨA bản cũ. Cách làm nó xanh là **deploy worker**, không phải
   dạy nó bỏ qua khác biệt có thật. *(Tôi từng đề xuất hướng ngược lại và đã
   rút — ghi ở đây để bản sau đừng đề xuất lại.)*
4. **Không sửa `.env.example` trên `main` để né bộ quét.** Đóng ngoặc 4 giá
   trị màu sẽ giấu 4/15 biến khỏi bộ quét, nhưng app vốn đọc đúng rồi (§0b),
   nên đó là sửa tệp thật để chiều một bộ đọc sai — và vẫn còn 11 biến.
5. **Chứng minh bằng một lượt deploy THẬT.** Nhánh sinh ra đúng hình dạng
   không phải bằng chứng nền tảng chịu nhận. Chốt duy nhất tính được là
   `redeploy_project` chạy xong và `/health` khai đúng SHA.
6. **Không đụng `main`.** Mọi thứ diễn ra trong nhánh sinh tự động.

## 4. Phạm vi

### A. Chọn mức dọn — chốt trước khi code

**A1 — tối thiểu: gỡ `.env.example` ở gốc nhánh.** Một dòng `rm` trong mỗi
script sinh. *Lợi:* nhỏ nhất, dễ lùi, và theo §0b là **đủ** để gỡ cả 15 biến.
*Hại:* chữa đúng triệu chứng đã biết; mai mốt thêm tệp cấu hình mẫu khác ở gốc
là lặp lại.

**A2 — triệt để: nhánh CHỈ có thư mục build.** Xoá toàn bộ phần còn lại.
*Lợi:* phép quét không còn gì ngoài build context để hiểu nhầm; nhánh deploy
thành đúng nghĩa "thứ đem đi dựng". *Hại:* thay đổi lớn hơn; và **lưu ý**
build context có `webapp/control_server/.env.example` với 22 biến — theo §0b
nền tảng không đọc tệp đó, nhưng A2 làm nó thành tệp `.env.example` *duy nhất*
còn lại, nên phải đo lại chứ đừng cho là đương nhiên vẫn im.

**Đề xuất: A1 trước.** §0b cho thấy A1 đủ, và A1 giữ nguyên mọi thứ khác nên
nếu sai thì biết ngay là sai ở đâu. A2 chỉ nên mở nếu A1 chạy rồi mà vẫn muốn
dọn.

### B. Kiểm giả thuyết TRƯỚC khi sửa script

Đừng sửa script rồi mới biết. Dựng một nhánh thử tay, gỡ `.env.example` ở gốc,
push, rồi gọi `redeploy_project` cho **`voxdub-dub-worker`** (dịch vụ còn kẹt).
Ba kết quả, ba kết luận:

| Cổng trả về | Nghĩa |
|---|---|
| chạy được | §0b đúng — làm A1 |
| vẫn đòi 15 biến | nền tảng không đọc tệp gốc; §0b sai, tìm lại, **đừng** sửa script |
| đòi 22 biến của `control_server` | nó đọc cả build context — A1 chưa đủ, cần bàn lại |

### C. Sau khi script sửa

- Chạy lại cả hai script sinh, `git diff` thư mục build **phải rỗng** (rào
  chắn 1).
- `scripts/kiem_nhanh_deploy.py` xanh.
- Deploy **cả hai** dịch vụ, `/health` khai đúng SHA của `main`.
- `kiem-prod-theo-main` **xanh** — đây là thứ chứng minh cả chuỗi, vì nó hỏi
  chính dịch vụ đang chạy.

### D. Gỡ 7 biến đã cấp tạm cho worker

`VIENEU_MAX_WORKERS`, `PARALLEL_WORKERS`, `WHISPER_BEAM_SIZE` và 4 biến màu
đã được cấp 24/09 để thử. Giá trị của chúng **trùng đúng thứ mã tự tính hoặc
mặc định**, nên không đổi hành vi hôm nay — nhưng `VIENEU_MAX_WORKERS` nay bị
**ghim**, tức container được cấp thêm RAM/CPU về sau sẽ vẫn chạy 1 tiến
trình. Gỡ sau khi D6 xong để trả lại phép tự tính.

## 5. Tiêu chí thành công

1. `redeploy_project` chạy được cho **cả hai** dịch vụ, **không** phải cấp
   biến nào của app desktop.
2. Thư mục build không đổi một byte.
3. `kiem-prod-theo-main` xanh trên một lượt CI thật.
4. D3, D5, drift không chốt nào bị nới.
5. 7 biến tạm đã gỡ; worker trở lại tự tính số tiến trình.
6. `pytest` + `npm test` xanh.

## 6. Ngoài phạm vi

- Đổi cách nền tảng quét cấu hình (không nằm trong tay dự án).
- Sửa `.env.example` trên `main` (rào chắn 4).
- Bật CI chạy **định kỳ** — chỉ nên làm SAU khi `kiem-prod-theo-main` xanh
  ổn định, nếu không mỗi ngày một lượt đỏ và cổng lại thành thứ không ai đọc.
- Đổi nội dung ảnh Docker của hai dịch vụ.

---

## 7. Kết quả thật (24/09/2026)

| Tiêu chí §5 | Kết quả |
|---|---|
| 1. Deploy được, không cấp biến desktop | ✅ worker · app: **chưa chứng minh được**, xem (b) |
| 2. Thư mục build không đổi một byte | ✅ `dub-worker` cây `d447d11` trước = sau · `webapp` 240/241 blob giống hệt, tệp lệch duy nhất là `SOURCE_SHA` (đúng thiết kế) |
| 3. `kiem-prod-theo-main` xanh | ✅ mã thoát 0, cả hai «ĐÚNG NHỊP» ở `d9afde6b918e` |
| 4. Không nới chốt nào | ✅ `kiem_nhanh_deploy.py` mã thoát 0; D5 vẫn bắt đúng lúc còn lệch, rồi tự xanh khi deploy xong |
| 5. Gỡ 7 biến tạm | ❌ **không làm được qua MCP** — xem (a) |
| 6. `pytest` + `npm test` xanh | ✅ 3.241 / 848 / 79, và CI xanh toàn bộ trừ D5 (D5 đỏ lúc đó vì prod chưa deploy — nay đã xanh) |

**Bằng chứng chính:** worker kẹt từ 21/09 nay deploy được mà không cấp biến
nào. `/health` đi `9b5b8ea2a98e` → `dfe66e6b8a0b` → `d9afde6b918e`, version
62 → 63 → 64. App: v110 → v111, cùng SHA `d9afde6b918e`. D5 trước đó báo
worker tụt **4 tệp** dưới `autodub/`; sau lượt deploy đầu còn 1 tệp (chính
script sinh), sau lượt deploy thứ hai **hết hẳn**.

CI đã sinh lại cả hai nhánh bằng script đã sửa — `.env.example` ở gốc:
**0/0**. Nên bản vá là vĩnh viễn, không phải nhánh thử tay.

**Một cổng CI khác đang báo xanh mà không làm gì:** `trien-khai-prod` ghi
`::warning::Chưa cấu hình secret VIBEHOST_TOKEN — BỎ QUA bước đưa lên prod`
rồi thoát 0. Tức CI **chưa bao giờ** tự deploy; mọi lượt tới giờ đều là tay.
Đây là mục C58 còn treo, không thuộc D6, nhưng ghi ở đây vì nó làm người đọc
bảng job tưởng prod đã tự lên.

### Hai việc CHƯA xong

**(a) Gỡ biến rác — cần làm tay trên giao diện.** Cổng VAYS chỉ có `set_env`,
**không có lệnh xoá**, và `set_env` bắt buộc `value` tối thiểu 1 ký tự nên
đến "để trống" cũng không được. Cần xoá:

- `voxdub-dub-worker` — 7 biến: `SUBTITLE_COLOR`, `SUBTITLE_OUTLINE_COLOR`,
  `SUBTITLE_BOX_COLOR`, `KARAOKE_HIGHLIGHT_COLOR`, `VIENEU_MAX_WORKERS`,
  `PARALLEL_WORKERS`, `WHISPER_BEAM_SIZE`.
- `voxdub-app` — 15 biến rác (id `cmudv…`), gồm cả 5 biến `TRANSLATE_*`,
  `VOXDUB_API_URL`, `VOXDUB_API_KEY`, `DISPLAY_NAME`.

`VIENEU_MAX_WORKERS` đang bị **ghim**: container được cấp thêm RAM/CPU về sau
vẫn sẽ chạy 1 tiến trình.

**(b) Tiêu chí 1 cho `voxdub-app` chưa chứng minh được.** App hiện đã có đủ
15 biến nên cổng `ENV_REQUIRED` không kêu — nhưng đó là vì biến đã được cấp,
không phải vì tệp đã gỡ. Chỉ chứng minh được sau khi xoá 15 biến ở (a). Cơ
chế và hình dạng nhánh giống hệt worker, nhưng **giống hệt không phải là đo**.

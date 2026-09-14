# D3 — Deploy Integrity: AUDIT (14/09/2026)

> **Trạng thái: DỪNG Ở BƯỚC AUDIT, CHƯA SỬA MÃ.**
>
> Mini-spec yêu cầu *"Nếu một tiền đề sai, dừng báo cáo, không sửa theo spec."*
> **Một tiền đề sai.** Nhưng mục tiêu của D3 vẫn còn một lỗ hổng **có thật, đã
> đo được** — chỉ là qua một cơ chế khác hẳn cơ chế spec mô tả. Bản vá cho hai
> cơ chế đó gần giống nhau, nhưng **lý do và tác dụng phụ khác nhau**, nên phải
> chốt lại hướng trước khi viết một dòng mã nào.

---

## 1. Luồng thật, từ push tới prod

Đo trên lượt chạy THẬT `84ac00d` (14/09), lấy từ GitHub Actions API và
Vibe Host, không suy đoán:

```
03:16:35Z  push main (84ac00d) → workflow run 34802054885 bắt đầu
03:16:39Z  sinh-nhanh-deploy   BẮT ĐẦU   (KHÔNG có `needs:` — chạy song song với test)
03:16:46Z    └─ force-push deploy/vays-control-server   ← 11 giây sau khi push
03:16:48Z    └─ force-push deploy/vays-dub-worker
03:16:52Z  sinh-nhanh-deploy   XONG
03:16:55Z  deploy-branch-drift bắt đầu (needs: sinh-nhanh-deploy)
03:17:23Z  node-tests          XONG ✅
03:19:20Z  chay-that-windows   XONG ✅
03:20:45Z  python-tests        XONG ✅   ← CỔNG CUỐI CÙNG
03:20:48Z  trien-khai-prod     BẮT ĐẦU  (needs: cả bốn job trên)
03:20:52Z    └─ gọi redeploy_project voxdub-app  (tác vụ cmu0oe7q6008x…)
03:22:28Z    └─ voxdub-app LÊN — /health trả uptimeS=14, db "đã kết nối"
03:22:28Z    └─ gọi redeploy_project voxdub-dub-worker (tác vụ cmu0og9d000az…)
03:29:00Z    └─ voxdub-dub-worker LÊN — /health 200
03:29:03Z  run KẾT THÚC ✅
```

Vibe Host xác nhận đúng hai lượt deploy, khớp từng phút:
`voxdub-app` 10:22 (+0700) v88→**89**; `voxdub-dub-worker` 10:28 v50→**51**.

**Cửa sổ phơi nhiễm: 3 phút 59 giây** — từ lúc nhánh deploy mang mã mới
(03:16:46) tới lúc cổng test cuối cùng xanh (03:20:45).

### Ai deploy từ đâu

| | |
|---|---|
| `voxdub-app` | `github.com/junnyken/voxdub-studio`, nhánh **`deploy/vays-control-server`** |
| `voxdub-dub-worker` | cùng repo, nhánh **`deploy/vays-dub-worker`** |

Nhánh deploy sinh bởi `scripts/gen_vays_*_branch.sh`:
`git worktree add -B <nhánh> <tmp> $GOC` rồi commit đè + `git push --force`.
CI truyền `GOC=${{ github.sha }}`, nên **cha của commit deploy CHÍNH LÀ SHA
nguồn** — đã kiểm: `deploy/vays-control-server^` = `84ac00d` = `main~1`.

---

## 2. ❌ TIỀN ĐỀ SAI: webhook KHÔNG deploy khi force-push

Spec nói: *"Webhook của platform có thể thấy force-push đó và bắt build/deploy
ngay"* và *"`trien-khai-prod` … có thể chạy quá muộn nếu webhook đã tự khởi
động deployment"*.

**Không quan sát được điều đó. Hai thí nghiệm tự nhiên, ngược chiều nhau:**

**(a) Force-push mà KHÔNG deploy — 14/09.** Commit `d5d6495` (chỉ sửa tài
liệu) push lúc 03:23:47Z. `sinh-nhanh-deploy` force-push lại **cả hai** nhánh
lúc ~03:24:04Z (có run `7796ed5d` trên `deploy/vays-dub-worker` chứng minh đầu
nhánh đã đổi). `trien-khai-prod` bỏ qua bước deploy vì `webapp/` và
`dub-worker/` không đổi.

> Kết quả: **prod KHÔNG deploy**. Tới 03:31Z (hơn 7 phút sau) hai dịch vụ vẫn
> đứng ở 10:22/v89 và 10:28/v51. Nếu có webhook theo push, đây là chỗ nó phải
> nổ — và nó không nổ.

**(b) Mọi lượt deploy đều khớp `trien-khai-prod`, không khớp force-push.**
Log của chính job đó in ra `jobId` Vibe Host và câu `/health`; giờ deploy của
Vibe Host trùng khít. Và số phiên bản chỉ **+1** mỗi dịch vụ — nếu webhook
cũng deploy thì phải là +2.

**⚠ GIỚI HẠN CỦA KẾT LUẬN NÀY.** "Không thấy nổ trong 2 lượt" **không bằng**
"không thể nổ". `get_project` của Vibe Host **không trả về** trường nào về
auto-deploy/webhook, nên tôi không đọc được cấu hình đó, chỉ đọc được hành vi.
**Cần chủ dự án xác nhận trong giao diện Vibe Host**: hai dự án có bật
auto-deploy-on-push cho nhánh git nguồn không?

- Nếu **KHÔNG** (khớp quan sát) → hướng sửa là mục 4 dưới đây.
- Nếu **CÓ** → tiền đề của spec đúng, mức nghiêm trọng cao hơn hẳn, và cách
  sửa vẫn là mục 4 nhưng thành **khẩn**.

---

## 3. ✅ LỖ HỔNG CÓ THẬT — khác cơ chế, cùng hậu quả

### 3.1 Nhánh deploy mang mã ĐỎ, và ở lại đó vô thời hạn

`sinh-nhanh-deploy` **không có `needs:`** nên nó force-push bất kể test.
Bằng chứng lịch sử, không phải giả định:

| Lượt chạy | SHA | Test | `sinh-nhanh-deploy` | `trien-khai-prod` |
|---|---|---|---|---|
| 34584418242 (11/09) | `4e7c19f` | **python-tests ĐỎ** 09:33:04 | ✅ force-push **09:29:14** | bỏ qua |
| 34198840549 (08/09) | `4049d13` | **node-tests ĐỎ** 07:21:05 | ✅ force-push **07:20:44** | bỏ qua |

Cổng tự động làm đúng việc: `trien-khai-prod` bị bỏ qua. **Nhưng nhánh deploy
— thứ mà Vibe Host coi là nguồn sự thật của production — đã mang mã trượt
test, và nằm đó cho tới lần push xanh kế tiếp.**

`main` có **58 lượt đỏ** trong lịch sử. Mỗi lượt là một quãng thời gian mà
nhánh deploy trỏ vào mã chưa qua được test của chính nó.

Bất cứ thứ gì deploy theo **đầu nhánh** trong quãng đó sẽ đưa mã đỏ lên prod,
**không có tín hiệu nào**:
- bấm redeploy trong giao diện Vibe Host;
- `mb-deploy`, hoặc gọi `redeploy_project` qua MCP từ workspace (tôi làm được
  việc đó ngay trong phiên này);
- khởi động lại / rollback nếu nền tảng kéo lại đầu nhánh;
- và auto-deploy, nếu nó được bật sau này.

**Đây mới là lỗ hổng thật, và nó thoả đúng mục tiêu D3 đang muốn chặn** —
chỉ khác là đường vào không phải webhook mà là **mọi đường deploy thủ công**.

### 3.2 `trien-khai-prod` deploy "đầu nhánh lúc này", KHÔNG phải SHA đã pass

`trien_khai_vibehost.py` gọi `redeploy_project {projectId}`. **Không có tham
số SHA.** Nền tảng dựng từ đầu nhánh *tại thời điểm gọi*.

Hậu quả cụ thể, đo được trong chính lượt 14/09: khoảng hở giữa
`python-tests` xanh (03:20:45) và lệnh deploy (03:20:52) là 7 giây; giữa lệnh
deploy và lúc app lên là 96 giây. Một lượt push khác rơi vào quãng đó sẽ sinh
lại nhánh deploy, và **lượt chạy của SHA cũ sẽ deploy mã của SHA mới rồi báo
thành công cho SHA cũ**.

Và sau khi deploy, không có gì khẳng định **SHA nào đang chạy**: `/health` trả
`version` là chuỗi `3.17.16` lấy từ `package.json`, không đổi giữa các commit.
Tức Success Criterion 2 ("trace được về chính source SHA đã pass") **hiện
không đáp ứng được**, kể cả khi mọi thứ chạy đúng.

### 3.3 Branch protection không phải chốt

Lượt push của chính phiên này in ra:

```
remote: Bypassed rule violations for refs/heads/main:
remote: - 2 of 2 required status checks are expected.
```

`main` **có** đặt required status checks, nhưng khoá đang dùng **được phép
vượt**. Nên chốt duy nhất còn hiệu lực là chốt bên trong CI — đúng như spec
nhận định.

### 3.4 Những thứ KIỂM RỒI, thấy đã ĐÚNG — đừng sửa lại

- **`trien-khai-prod` gate đầy đủ**: `needs: [sinh-nhanh-deploy, python-tests,
  node-tests, chay-that-windows]`. Đã chứng minh bằng 2 lượt đỏ → bị bỏ qua.
- **Health verification đã đạt yêu cầu 7 của spec**: `_phu_thuoc_hong()` trong
  `trien_khai_vibehost.py` (mini-spec C59) **đã** từ chối 200-giả khi
  `db` khác `"đã kết nối"`/`"không dùng"`. Không cần dựng mới, chỉ cần test
  hồi quy.
- **Truy vết SHA nguồn đã có sẵn, dạng ngầm**: cha của commit nhánh deploy
  chính là SHA nguồn. Chỉ thiếu việc ghi nó ra dạng đọc được và **đối chiếu**.
- **Chỉ deploy dịch vụ có thư mục build đổi**: đã có, hoạt động đúng (lượt
  `d5d6495` bỏ qua cả hai).

---

## 4. Hướng sửa đề xuất — CHỜ CHỐT, chưa làm

**Chọn A: chỉ sinh/force-push nhánh deploy SAU khi mọi cổng bắt buộc xanh.**

Thêm `needs: [python-tests, node-tests, chay-that-windows]` vào
`sinh-nhanh-deploy`. Hệ quả: trên lượt đỏ, nhánh deploy **đứng nguyên ở lần
xanh gần nhất** — nên mọi đường deploy thủ công, và cả auto-deploy nếu có,
đều chỉ lấy được mã đã pass. Đóng được cả 3.1 lẫn tiền đề webhook (nếu nó
đúng), bằng một thay đổi.

**Vì sao không chọn B (release artifact / attestation).** B đòi nền tảng
deploy theo một SHA/artifact chỉ định. `redeploy_project` của Vibe Host
**không nhận tham số SHA** — đã đọc toàn bộ danh sách công cụ MCP. Nên B phải
dựng một đường phát hành song song (registry ảnh, hoặc nhánh release riêng +
đổi cấu hình nguồn của cả hai dự án). Đó là dựng hệ thống deploy thứ hai, trái
ràng buộc "reuse pipeline hiện có, không dựng parallel deployment system", và
đổi cấu hình prod là thao tác của chủ dự án.

**Ba tác dụng phụ của A phải xử lý, không được bỏ qua:**

1. **`deploy-branch-drift` sẽ luôn đỏ trên lượt đỏ.** Nó `needs:
   [sinh-nhanh-deploy]` + `always()`, và so cây thư mục main↔deploy. Hoãn việc
   sinh nhánh nghĩa là trên lượt đỏ nó sẽ thấy "lệch" — mà lệch lúc đó là
   **đúng và mong muốn**. Phải cho nó phân biệt "lệch vì quên sinh" với "lệch
   vì cố ý giữ lại bản xanh", nếu không ta tạo ra một bộ canh kêu nhầm — và
   backlog của chính dự án đã ghi: bộ canh hay kêu nhầm thì người ta tắt nó
   đi, còn tệ hơn không có.
2. **Nhánh deploy chậm hơn main ~4 phút.** Chấp nhận được, và đó chính là cái
   giá của việc không để mã chưa kiểm nằm ở nguồn sự thật của prod.
3. **Không đóng được 3.2 (đua SHA).** Cần thêm: ghi SHA nguồn vào commit nhánh
   deploy dạng đọc được, và trước khi gọi `redeploy_project` thì **đối chiếu**
   đầu nhánh remote đúng bằng SHA vừa sinh; lệch thì dừng, không deploy.

---

## 5. Cần chủ dự án trả lời trước khi tôi viết mã

1. **Vibe Host có bật auto-deploy-on-push cho hai dự án không?** Tôi đọc được
   hành vi (không nổ trong 2 lượt) nhưng không đọc được cấu hình. Câu trả lời
   đổi mức nghiêm trọng, không đổi hướng sửa.
2. **Đồng ý hướng A không?** Đánh đổi: nhánh deploy chậm hơn main ~4 phút, và
   trên lượt đỏ nó cố ý đứng lại ở bản xanh gần nhất.
3. **`/health` được thêm trường SHA nguồn không?** Đây là thay đổi nhỏ trong
   `control_server` (một trường đọc từ biến môi trường lúc build). Không có nó
   thì Success Criterion 2 chỉ đạt được ở mức "suy ra từ nhánh", không phải
   "hỏi chính dịch vụ". Spec cấm đụng app ngoài CI/deploy tối thiểu — nên tôi
   hỏi thay vì tự làm.

**Không đụng trong D3** (theo đúng spec): D4 token, H4d/provider/
`image.scene.stage`, pricing, Brand Profile, OCR, UI.

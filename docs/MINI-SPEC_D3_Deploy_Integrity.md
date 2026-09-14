# D3 — Deploy Integrity (14/09/2026)

> Audit và **tiền đề đã bị bác bỏ** nằm ở
> `docs/MINI-SPEC_D3_Deploy_Integrity_AUDIT.md`. Tệp này là phần thi công.

## Vấn đề, nói bằng số đo

Lượt chạy thật `84ac00d` (14/09), lấy từ GitHub Actions API:

```
03:16:39  sinh-nhanh-deploy BẮT ĐẦU   ← không có `needs:`
03:16:46    force-push deploy/vays-control-server
03:20:45  python-tests XONG ✅         ← cổng cuối cùng
```

**Hở 3 phút 59 giây.** Và trên lượt ĐỎ thì khoảng hở không đóng lại:

| Lượt | Test | `sinh-nhanh-deploy` | `trien-khai-prod` |
|---|---|---|---|
| 34584418242 (11/09) | python-tests **ĐỎ** 09:33:04 | force-push **09:29:14** | bỏ qua ✅ |
| 34198840549 (08/09) | node-tests **ĐỎ** 07:21:05 | force-push **07:20:44** | bỏ qua ✅ |

Cổng tự động làm đúng. Nhưng **nhánh deploy là nguồn sự thật của production**,
và nó mang mã trượt test rồi nằm lại đó tới lần push xanh kế tiếp. `main` có
**58 lượt đỏ** trong lịch sử. Trong mỗi quãng đó, bấm redeploy trên giao diện
Vibe Host / chạy `mb-deploy` / gọi `redeploy_project` qua MCP đều đưa mã đỏ lên
prod, **không tín hiệu nào**.

> Tiền đề của bản spec — *webhook nền tảng deploy ngay khi force-push* —
> **không quan sát được**; xem mục 2 của tệp audit. Lỗ hổng thật là mọi đường
> deploy **thủ công**, và nó không cần webhook nào để xảy ra.

## Hướng chọn: A — gate việc SINH nhánh deploy

Chủ dự án chốt A ngày 14/09. Loại B (release artifact/attestation) vì
`redeploy_project` của Vibe Host **không nhận tham số SHA**, nên B buộc phải
dựng một đường phát hành song song — trái ràng buộc "không dựng parallel
deployment system".

## Ba chốt đã dựng

### 1. Nhánh deploy chỉ sinh SAU khi mọi cổng xanh

```yaml
sinh-nhanh-deploy:
  needs: [python-tests, node-tests, chay-that-windows]
```

Test đỏ ⇒ nhánh deploy **đứng nguyên ở bản xanh gần nhất**. Giá phải trả: nhánh
deploy chậm hơn `main` ~4 phút.

**Tác dụng phụ đã xử lý — `deploy-branch-drift` không được kêu nhầm.** Job đó
`always()` + `needs: [sinh-nhanh-deploy]`; từ D3, trên lượt đỏ job sinh nhánh
bị *bỏ qua* nên nhánh deploy CỐ Ý lệch. Bước kiểm nay đọc
`needs.sinh-nhanh-deploy.result`: khác `success` thì in `::notice::` nói rõ đây
là cổng đang làm đúng việc rồi `exit 0`. Không có phần này thì ta vừa dựng một
chốt an toàn vừa dựng một bộ canh kêu nhầm — mà backlog dự án đã ghi: bộ canh
hay kêu nhầm thì người ta tắt nó đi, còn tệ hơn không có.

### 2. Ghim SHA — chống đua giữa hai lượt push

`redeploy_project` **không nhận SHA**: nền tảng dựng "đầu nhánh lúc gọi". Đo
thật trên lượt `84ac00d`: từ lúc cổng cuối xanh tới lúc gọi deploy là 7 giây,
từ lệnh deploy tới lúc dịch vụ lên là 96 giây. Một lượt push khác rơi vào quãng
đó sẽ sinh lại nhánh, và lượt chạy của SHA **cũ** sẽ đẩy mã của SHA **mới** lên
prod rồi ghi "thành công" cho SHA cũ.

- `sinh-nhanh-deploy` xuất `sha_app` / `sha_worker`.
- `trien_khai_vibehost.py --nhanh-deploy --sha-nhanh` hỏi **`git ls-remote`**
  (remote, không phải bản sao trên máy — bản sao là thứ ta vừa tự ghi ra) và
  **từ chối deploy** nếu lệch.
- Đối chiếu chạy **trước** lượt gọi đầu tiên; kiểm sau khi deploy thì mã sai đã
  nằm trên prod rồi.
- Khai `--nhanh-deploy` mà thiếu `--sha-nhanh` ⇒ **thoát mã 2**. Khai một nửa là
  cái bẫy tệ nhất: lệnh chạy trót lọt, báo xanh, mà chốt chưa từng chạy.

### 3. Dịch vụ TỰ KHAI đang chạy SHA nào

`/health` trả `version` lấy từ `package.json` nên **không đổi giữa các commit**
— đo thật 14/09: prod trả `3.17.16` cả trước lẫn sau một lượt deploy. Nên
Success Criterion 2 trước D3 **không đáp ứng được kể cả khi mọi thứ chạy đúng**.

- `gen_vays_*_branch.sh` ghi SHA nguồn vào **hai** chỗ: trailer `Source-SHA:`
  trong commit (đọc bằng `git log`) và tệp `SOURCE_SHA` trong thư mục build
  (đi **vào ảnh Docker**).
- `control_server/src/version.js` giữ nguyên thứ tự ưu tiên cũ
  (`APP_COMMIT` → `SOURCE_COMMIT`) rồi mới đọc tệp. Không có tệp là chuyện bình
  thường (chạy từ mã nguồn, chạy test) ⇒ im lặng; có tệp mà đọc không được thì
  **cảnh báo**, không nuốt.
- `trien_khai_vibehost.py --sha-nguon` đối chiếu trường `commit` của `/health`.
  **SHA lệch ở lượt đầu = "chưa lên"**, không phải hỏng ngay: container cũ còn
  trả lời trong lúc bản mới chưa thay xong. Hết lượt mà vẫn lệch mới là hỏng —
  và lúc đó câu báo nói rõ đang chạy cái gì.
- **Không khai `commit` ⇒ CHƯA XÁC MINH ĐƯỢC, không phải "đã đúng".**
- `.gitignore` chặn `control_server/SOURCE_SHA` lọt lên `main`: một tệp cũ ở đó
  khiến `/health` khai một commit khác hẳn thứ đang chạy — tệ hơn không khai gì,
  vì nó trông như bằng chứng.

**Worker cố ý KHÔNG có chốt 3**: `/health` của nó trả chuỗi `"ok"` thuần, không
khai được gì. Bịa một phép kiểm không chạy được ở đó còn tệ hơn không kiểm.
Chốt 1 và 2 vẫn áp dụng đủ cho worker.

## Đã kiểm

`tests/test_d3_deploy_integrity.py` — **24 test**. Ba phép chứng minh phủ định
của mini-spec, mỗi cái gỡ **đúng một** chốt:

| Gỡ gì | Test đỏ |
|---|---|
| dòng `needs:` của `sinh-nhanh-deploy` | `test_sinh_nhanh_deploy_phu_thuoc_MOI_cong_bat_buoc` |
| — (SHA nhánh lệch) | `test_BANG_CHUNG_PHU_DINH_2_dau_nhanh_LECH_thi_CHAN` |
| phép kiểm CSDL trong `_phu_thuoc_hong` | `test_BANG_CHUNG_PHU_DINH_3_…` |

Gỡ TOÀN BỘ bản vá D3: **21/24 đỏ**.

> **Một test của chính đợt này lúc đầu đỏ vì LÝ DO SAI.** Bản đầu của phép
> chứng minh phủ định #3 truyền kèm `sha_nguon=`, nên gỡ D3 ra nó đỏ vì
> `TypeError` chứ không phải vì phép kiểm CSDL bị mất. Một test đỏ nhầm lý do
> không chứng minh gì. Đã bỏ tham số đó để nó chỉ đỏ khi đúng chốt nó nói bị gỡ.

Chạy thật hai script sinh nhánh với một remote tạm (không đụng GitHub):
trailer `Source-SHA` đúng, tệp `SOURCE_SHA` nằm đúng trong thư mục build, và
cha của commit deploy đúng bằng SHA nguồn.

Hồi quy: Node **713 đạt / 0 hỏng**; nhóm deploy 54 đạt.

## Giới hạn còn lại

1. **Chưa xác nhận được cấu hình auto-deploy của Vibe Host.** `get_project`
   không trả trường nào về việc đó. Quan sát hai lượt cho thấy nó không nổ khi
   force-push, nhưng "không thấy nổ" ≠ "không thể nổ". *Nếu* nó đang bật thì
   chốt 1 vẫn đóng đúng lỗ đó — đây là giới hạn về **hiểu biết**, không phải về
   bản vá.
2. **Branch protection vẫn bypass được.** Lượt push nào cũng in *"Bypassed rule
   violations — 2 of 2 required status checks"*. Chốt duy nhất còn hiệu lực là
   chốt bên trong CI. Gỡ được điều này là thao tác của chủ dự án trên GitHub
   (đổi rule hoặc đổi khoá), **không** làm trong D3 vì đụng D4.
3. **Worker không tự khai SHA** — xem trên.
4. **Deploy thủ công vẫn deploy được bất cứ lúc nào.** D3 bảo đảm *thứ nằm trên
   nhánh deploy* luôn là mã đã pass; nó không ngăn người ta bấm redeploy. Sau
   D3 thì bấm nhầm lúc cũng chỉ dựng lại đúng bản xanh gần nhất — đó chính là
   điều muốn có.

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

## Kiểm chứng LIVE — hai lượt CI thật

### Lượt 1 — `128bcd9` (run 34804079842): cổng D3 nổ lần đầu

```
03:57:26  python-tests        FAILURE
03:57:27  sinh-nhanh-deploy   SKIPPED   ← cổng D3
03:57:27  trien-khai-prod     skipped
03:57:37  deploy-branch-drift success   ← KHÔNG kêu nhầm
```

**Trước D3, `sinh-nhanh-deploy` đã force-push từ ~03:52:55** — tức nguồn sự
thật của prod sẽ mang đúng mã vừa trượt test. Đây là bằng chứng live cho cả
chốt 1 lẫn phần chống-kêu-nhầm.

Lượt đó đỏ vì một chốt SẴN CÓ của dự án bắt mã mới của tôi:
`subprocess.run(..., encoding="utf-8")` trong `doi_chieu_dau_nhanh` thiếu
`errors="replace"` (`tests/test_subprocess_encoding.py`) — đúng lớp lỗi cp1252
ngày 11/09. Lỗi quy trình của tôi: chạy test **chọn lọc** rồi đẩy thay vì chạy
đủ bộ; chốt bắt được, nhưng bắt ở CI thì tốn một lượt đỏ trên `main`.

### Lượt 2 — `8f17a70` (run 34804806017): thứ tự đúng, prod khai đúng SHA

```
04:06:42  node-tests          success
04:08:42  chay-that-windows   success
04:10:03  python-tests        success   ← cổng cuối cùng
04:10:06  sinh-nhanh-deploy   BẮT ĐẦU   ← SAU cổng cuối, không còn trước
04:10:15  sinh-nhanh-deploy   success
04:12:05  trien-khai-prod     success
```

Nhánh deploy sinh **sau** cổng cuối cùng 3 giây, thay vì **trước** nó 4 phút.

Prod, hỏi trực tiếp:

```
GET https://voxdub-app.cmc-1.vibenode.matbao.ai/health
{"ok":true,"version":"3.17.16","commit":"8f17a706f1eb","db":"đã kết nối","uptimeS":314}
```

`git log -1 --format=%b github/deploy/vays-control-server` →
`Source-SHA: 8f17a706f1ebece618c47ad1588c9afe9f0e1bdb`.

**`commit` = đúng SHA `main` mà test của chính nó vừa xanh.** Success Criterion
2 nay đạt bằng cách **hỏi dịch vụ**, không phải suy ra từ nhánh.

### Lượt 2 cũng lộ ra lỗi thứ hai của tôi — và cách chặn nó tái diễn

`deploy-branch-drift` đỏ với đúng câu:

```
control_server/ ⇄ webapp/control_server/: 1 tệp thừa (vd SOURCE_SHA)
```

Tệp `SOURCE_SHA` phải nằm TRONG `webapp/control_server/` (chỗ duy nhất
`COPY control_server/ ./` mang được vào ảnh), nên nó rơi đúng vào vùng bộ dò so
sánh — mà `main` không có nó. Bộ dò làm đúng việc; thứ sai là danh sách bỏ qua
chưa theo kịp thứ script sinh ra. Đã thêm `"SOURCE_SHA"` vào `BO_QUA`.

**24 test D3 đều xanh mà vẫn lọt** — vì không test nào chạy *script sinh nhánh*
và *bộ dò* CÙNG NHAU. Test cũ `test_anh_xa_phu_het_thu_ma_script_sinh_nhanh_chep`
cũng không bắt được: nó đọc các lệnh `cp -r`, còn `SOURCE_SHA` thì `printf` ra.

Đã thêm `test_DAU_CUOI_sinh_nhanh_that_thi_bo_do_phai_noi_KHONG_LECH`: sinh
nhánh THẬT vào một remote tạm rồi bắt chính bộ dò chấm. Bỏ `SOURCE_SHA` khỏi
`BO_QUA` ⇒ test đỏ. Test tự trả nhánh deploy cục bộ về nguyên trạng — một bộ
test làm bẩn repo của người chạy nó là một bộ test người ta sẽ tắt.

> **Bản đầu của chính test đầu-cuối đó cũng sai**, và cách nó sai đáng ghi
> lại: nó gọi `kiem_mot_nhanh()`, mà hàm này CỐ Ý ưu tiên nhánh trên REMOTE
> (C57b) — ở máy dev remote là bản cũ, nên test đỏ vì ref cũ chứ không vì thứ
> đang kiểm (báo `src/version.js` khác nội dung). Đã đổi sang so trực tiếp
> bằng `_liet_ke` trên nhánh vừa sinh.

### Lượt cuối — `bd62f3f` (run 34807643557): XANH TOÀN BỘ

```
04:54:00  node-tests          success
04:55:21  chay-that-windows   success
04:57:16  python-tests        success   ← cổng cuối cùng
04:57:19  sinh-nhanh-deploy   BẮT ĐẦU   ← SAU cổng cuối đúng 3 giây
04:57:30  sinh-nhanh-deploy   success
04:57:33  deploy-branch-drift success   ← không kêu nhầm
04:57:33  trien-khai-prod     BẮT ĐẦU
04:59:59  trien-khai-prod     success   ← gồm cả đối chiếu đầu nhánh + SHA ở /health
```

Trước D3 con số tương ứng là **force-push trước cổng cuối 3 phút 59 giây**.
Nay là **sau nó 3 giây**.

Prod, hỏi trực tiếp ngay sau lượt chạy:

```
{"ok":true,"version":"3.17.16","commit":"bd62f3f5e93d","db":"đã kết nối","uptimeS":66}
```

`git log -1 --format=%b github/deploy/vays-control-server` →
`Source-SHA: bd62f3f5e93d80b1f5a9c91bfe9630021bf92ae3`

Ba con số khớp nhau: SHA `main` đã pass test = `Source-SHA` trên nhánh deploy =
`commit` mà dịch vụ đang chạy tự khai.

### Ba lượt đỏ trên đường tới đây — đều là LỖI QUY TRÌNH của tôi, cùng một lỗi

| Lượt | Đỏ vì | Lẽ ra bắt được ở đâu |
|---|---|---|
| 34804079842 | `subprocess.run(encoding=)` thiếu `errors="replace"` | chạy ĐỦ BỘ pytest tại máy (chốt `test_subprocess_encoding.py` đã có sẵn) |
| 34805967418 | `fatal: empty ident name` | chạy với `GIT_CONFIG_GLOBAL=/dev/null` |
| 34806866247 | `shallow update not allowed` | chạy trong một bản sao NÔNG |

Cùng một sai sót ba lần: **dựng một test chạy THẬT rồi kiểm nó ở môi trường DỄ
HƠN chỗ nó sẽ chạy.** Máy tôi có git config, có repo đầy đủ, và tôi chạy test
chọn lọc. Runner thì không có gì trong ba thứ đó.

Cách chữa đã áp dụng: chạy lượt cuối bằng
`GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null` trên ĐỦ BỘ, **và**
chạy riêng nhóm D3 bên trong một bản sao nông thật. Hai điều kiện đó cộng lại
mới xấp xỉ được runner.

> Đáng ghi: cả ba lượt đỏ đó đồng thời là **bằng chứng live cho chính cổng
> D3** — mỗi lượt đều cho `sinh-nhanh-deploy` SKIPPED và nhánh deploy đứng
> nguyên ở bản xanh gần nhất. Trước D3, cả ba đã force-push mã đỏ lên nguồn sự
> thật của prod.

### Lỗi thứ tư — tôi tự gây ra, và nó chỉ lộ ra trên PROD

Sau khi lượt xanh chốt xong, một commit **chỉ sửa tài liệu** vẫn làm prod deploy
lại. Đo trên Vibe Host trong cùng ngày:

| | trước D3 | sau vài commit tài liệu |
|---|---|---|
| `voxdub-app` | v89 | **v92** |
| `voxdub-dub-worker` | v51 | **v54** |

**Nguyên nhân:** `SOURCE_SHA` mang SHA nguồn nên nó đổi ở **mọi** commit — mà
nó lại nằm **trong** thư mục build. Nên phép so *"thư mục build có đổi không"*
(`git diff --quiet "$truoc_app" "$sau_app" -- webapp/`) luôn thấy khác, và
chính sách **"chỉ deploy dịch vụ có thư mục build thay đổi"** (có từ C57, và là
một yêu cầu của chính mini-spec này) bị vô hiệu. Riêng worker tốn ~11 phút dựng
lại mỗi lượt, đổi lại không có gì.

**Sửa:** loại đúng tệp đó khỏi phép so bằng pathspec —
`-- webapp/ ':(exclude)webapp/control_server/SOURCE_SHA'` và tương tự cho
worker.

**Không mất truy vết:** prod giữ ảnh cũ thì `/health` khai đúng SHA đã dựng ra
ảnh đó. Khai SHA `main` mới nhất trong khi *không* dựng lại mới là nói dối —
nên "`commit` ở `/health` cũ hơn `main`" là trạng thái ĐÚNG, không phải drift.

**Vì sao 26 test trước đó không bắt:** không test nào chạy *hai lượt sinh nhánh
từ hai commit khác nhau* rồi hỏi đúng câu lệnh CI dùng để quyết định deploy.
Đã thêm `test_DAU_CUOI_hai_commit_chi_khac_TAI_LIEU_thi_thu_muc_build_KHONG_doi`
— nó tự mang cả hai chiều: khẳng định trước rằng **không** loại trừ thì phép so
CÓ thấy khác (tiền đề), rồi khẳng định **có** loại trừ thì không.

> Bốn lỗi, cùng một hình dạng: tôi kiểm ở tầng dễ hơn tầng thứ sẽ chạy. Ba lỗi
> đầu là môi trường test; lỗi này là **hệ quả trên hệ thống thật mà không test
> nào mô phỏng**. Thứ bắt được nó là đi đọc số phiên bản trên Vibe Host sau khi
> đã tuyên bố xong — chứ không phải một bảng test xanh.

**Chứng minh bản vá trên hệ thống thật** — run 34809207038 (`7db0acf`, chỉ
sửa workflow/test/docs):

```
05:23:09  python-tests        success
05:23:11  sinh-nhanh-deploy   success   (sau cổng cuối 2 giây)
05:23:24  trien-khai-prod     success   — chạy 6 GIÂY
     · Đưa voxdub-app lên prod         skipped
     · Đưa voxdub-dub-worker lên prod  skipped
```

Phiên bản trên Vibe Host đứng nguyên **v92 / v54**. Trước bản vá, đúng lượt này
sẽ dựng lại cả hai dịch vụ (worker ~11 phút) để nhận về một ảnh giống hệt.

Sau đó `/health` khai `commit: e13a89c80df7` trong khi `main` ở `7db0acf` — và
đó là **trạng thái đúng**: prod đang chạy ảnh dựng từ `e13a89c`, vì `7db0acf`
không đổi gì trong thư mục build.

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

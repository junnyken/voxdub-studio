# Runbook triển khai `control_server` lên Coolify

Ghi lại đúng quy trình đã chạy thật (2026-08-14/15, lần deploy production đầu
tiên của repo này) — kể cả những chỗ vấp thật, để lần sau (đổi server, tăng
tài nguyên, khôi phục sau sự cố, dựng lại từ đầu) không phải dò lại từ đầu.
Không phải hướng dẫn lý thuyết — mọi bước dưới đây đã chạy qua Coolify API
thật và xác nhận kết quả thật.

**Không dùng `mb-deploy` CLI cho service này** — nó tự động hoá đúng
trường hợp "1 app = 1 Dockerfile ở gốc repo", nhưng `control_server` nằm
trong monorepo (Dockerfile cần cả `website/` làm build context, xem
Bước 2) nên phải cấu hình tay qua API Coolify (`https://ops.matbao.ai`).

---

## 0. Việc cần chuẩn bị trước

- Token Coolify (đọc từ `$TOKENS_DIR/coolify-token`, hoặc hỏi admin hạ tầng).
- 1 API key Google Gemini thật (AI Studio, dạng `AIzaSy...`) — **bắt buộc**,
  không có thì tính năng dịch tự động luôn báo lỗi (xem Bước 6, đây là lỗi
  thật đã gặp và mất nhiều thời gian truy mới ra).
- 1 API key ElevenLabs thật (nếu muốn bật tính năng nhạc nền/SFX AI, V37).

## 1. Tạo app Coolify (build_pack `dockerfile`, KHÔNG phải `dockercompose`)

Dù repo có `docker-compose.yml` ở gốc, **không dùng build_pack tự động phát
hiện** — Coolify sẽ chọn `dockercompose` (vì thấy file đó) và cần cấu hình
domain kiểu `docker_compose_domains` mà `mb-deploy` không hỗ trợ. Tạo app
xong thì PATCH lại build_pack:

```bash
# 1a. Tạo app (build_pack ban đầu không quan trọng, sẽ sửa ngay)
curl -X POST "$COOLIFY_URL/api/v1/applications/private-deploy-key" \
  -H "Authorization: Bearer $COOLIFY_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "<ten-app>", "project_uuid": "<uuid>", "environment_name": "production",
    "server_uuid": "<uuid>", "private_key_uuid": "<uuid>",
    "git_repository": "git@github.com:junnyken/voxdub-studio.git",
    "git_branch": "main", "build_pack": "dockerfile", "ports_exposes": "3001"
  }'

# 1b. PATCH build_pack + domain TÁCH RIÊNG 2 lần — gộp chung 1 lần PATCH sẽ
#     lỗi "domains field cannot be used for dockercompose applications" vì
#     Coolify validate domains theo build_pack CŨ trước khi áp build_pack mới
#     trong cùng request (bug/quirk thật đã gặp).
curl -X PATCH ".../applications/<uuid>" -d '{"build_pack": "dockerfile"}'
curl -X PATCH ".../applications/<uuid>" -d '{
  "dockerfile_location": "/control_server/Dockerfile",
  "base_directory": "/",
  "ports_exposes": "3001",
  "domains": "https://<domain-mong-muon>"
}'
```

**`base_directory` PHẢI để `/` (gốc repo), không phải `control_server`** —
`control_server/Dockerfile` có `COPY website/...` (multi-stage build kèm
frontend), cần cả `website/` làm build context. Đặt `base_directory=control_server`
sẽ làm build fail vì thiếu `website/`.

## 2. Domain — ưu tiên domain tự sinh nếu domain tuỳ chỉnh có vấn đề DNS

Domain tuỳ chỉnh dạng `<project>.<team>.<dev-domain>` (theo quy ước
`mb-deploy`) có thể bị **DNS trỏ sai IP** kể cả khi Coolify đã cấu hình đúng
— đã gặp thật với `voidmax.mk.b.matbao.ai` (trỏ nhầm sang IP khác, không
phải IP server Coolify thật). Cách kiểm tra nhanh: `getent hosts <domain>`
so với IP server thật (`.destination.server.ip` hoặc field tương đương từ
`GET /applications/<uuid>`).

Nếu DNS sai và không có quyền sửa ngay: **dùng domain tự sinh của Coolify**
(`<app-uuid>.<dev-domain>`, vd `zhttjocbofa47t1afq3pslzw.dev.matbao.ai`) —
domain này LUÔN trỏ đúng vì được set trong `domains` field, không phụ thuộc
DNS zone ngoài. Đổi `domains` về giá trị này (PATCH như Bước 1b) rồi **phải
deploy lại** (Bước 5) — label Traefik chỉ cập nhật khi container mới được
tạo, đổi qua API không tự áp dụng cho container đang chạy.

## 3. MongoDB riêng

```bash
curl -X POST "$COOLIFY_URL/api/v1/databases/mongodb" -d '{
  "project_uuid": "<uuid>", "environment_name": "production",
  "server_uuid": "<uuid>", "name": "<ten>-mongo", "instant_deploy": true
}'
```

Lấy connection string thật từ `GET /databases/<uuid>` → field `internal_db_url`.

## 4. Biến môi trường — TỪNG BIẾN MỘT, không dùng `envs/bulk`

`PATCH .../envs/bulk` (kể cả `POST`) **tự nhân đôi bản ghi** mỗi lần gọi —
bug thật của Coolify, gặp lặp lại 3 lần trong buổi deploy này dù đã đổi
cách gọi. Cách chắc ăn: gọi **`POST /applications/<uuid>/envs` từng biến
một** (không phải `/bulk`), và **luôn set `is_buildtime: false`** — mặc
định Coolify để biến "available at buildtime", khiến `NODE_ENV=production`
lọt vào build stage `website-build` của Dockerfile, làm `npm ci` bỏ qua
`devDependencies` (trong đó có `vite`) → build fail với `vite: not found`.

Biến bắt buộc: `NODE_ENV`, `HOST=0.0.0.0`, `PORT=3001`, `TRUST_PROXY=1`,
`PUBLIC_URL`, `MONGODB_URI`, `JWT_SECRET`/`ADMIN_TOKEN`/`APP_ENCRYPTION_KEY`
(sinh bằng `openssl rand -hex 32`), `ELEVENLABS_API_KEY` (nếu dùng V37).

```bash
curl -X POST ".../applications/<uuid>/envs" -d '{
  "key": "<TEN_BIEN>", "value": "<gia-tri>",
  "is_buildtime": false, "is_runtime": true
}'
```

## 5. Deploy + health check

```bash
curl -X POST "$COOLIFY_URL/api/v1/deploy" -d '{"uuid": "<app-uuid>"}'
```

Sau khi `status: running:healthy`, **bật health check đúng path** (mặc
định Coolify để `health_check_enabled: false`, path `/`) — app có sẵn
route `/health` thật:

```bash
curl -X PATCH ".../applications/<uuid>" -d '{
  "health_check_enabled": true, "health_check_path": "/health",
  "health_check_interval": 30, "health_check_retries": 3
}'
# rồi deploy lại — cấu hình health check cũng chỉ áp dụng khi container mới tạo
```

Kiểm tra thật (không tin log Coolify): `curl -k https://<domain>/health` →
phải ra `{"ok":true,"version":"...",...}`.

## 6. **BẮT BUỘC**: seed nhà cung cấp AI dịch — dễ quên nhất, gây lỗi khó truy nhất

Database MongoDB mới **không tự có nhà cung cấp AI dịch nào** —
`GET /v1/admin/providers` trả `data: []`. Thiếu bước này thì MỌI lượt dịch
tự động sẽ thất bại 100% (không phải ngẫu nhiên), nhưng client chỉ thấy
thông báo chung chung **"Dịch vụ dịch tạm thời không phản hồi"** vì
`control_server/src/routes/ai.js` nuốt lỗi thật trước khi trả về client —
phải gọi thẳng `/v1/admin/providers` mới thấy nguyên nhân. Đây là lỗi thật
đã tốn nhiều thời gian truy trong buổi deploy này.

```bash
curl -X POST ".../v1/admin/providers" -H "x-admin-token: $ADMIN_TOKEN" -d '{
  "name": "gemini-direct", "label": "Google Gemini (trực tiếp)",
  "role": "translate", "type": "google",
  "apiKey": "<AIzaSy...>", "model": "gemini-2.5-flash",
  "priority": 100, "enabled": true
}'
```

Xác nhận thật bằng 1 lượt dịch thử (không chỉ tin config đã lưu) — xem
`docs/TEST_LOG.md` mục "Thiết lập hạ tầng... nhà cung cấp AI dịch" cho ví
dụ Python gọi trực tiếp `translate_segments()`.

**Cấu hình này nằm trong MongoDB, không nằm trong `.env`/code nào cả** —
dựng lại database từ đầu (kể cả cùng app Coolify) sẽ mất, phải làm lại
đúng bước này.

## 7. Backup MongoDB

> **[HẾT HIỆU LỰC TỪ 2026-08-17 — đọc trước khi tin mục này]** Toàn bộ mục 7
> mô tả backup **của Coolify**. Ngày 17-08 dự án chuyển sang Vibe Host, nên
> lịch backup này **không còn tồn tại và không có lượt nào chạy nữa**. Giữ lại
> vì runbook còn dùng khi dựng lại trên Coolify. Cách sao lưu ĐANG dùng nằm ở
> mục 7b ngay dưới.


```bash
curl -X POST ".../databases/<mongo-uuid>/backups" -d '{"frequency": "0 3 * * *"}'
# response mặc định save_s3=true dù CHƯA có S3 storage nào — PHẢI tắt đi,
# không thì lượt backup thật sẽ lỗi vì không có nơi tải lên:
curl -X PATCH ".../databases/<mongo-uuid>/backups/<backup-uuid>" -d '{
  "save_s3": false,
  "database_backup_retention_amount_locally": 14,
  "database_backup_retention_days_locally": 30
}'
```

Đây là backup **lưu trên cùng server** với database — bảo vệ khỏi lỗi
database/xoá nhầm, KHÔNG bảo vệ khỏi mất cả server. Muốn thêm lớp bảo vệ
đó cần đăng ký S3 storage (`POST /s3-storages`, cần credential ngoài,
chưa làm — xem `docs/PLAN.md` Remaining Limits).

Không có endpoint API "chạy backup ngay" — muốn kiểm tra thật, đổi tạm
`frequency` thành `*/2 * * * *`, đợi 1 lượt chạy (`GET .../backups` xem
field `executions`), rồi đặt lại lịch thật.

## 7b. Sao lưu thật sau khi rời Coolify — lịch đặt trên máy NGOÀI

Vibe Host không có ổ đĩa bền vững: bản dump ghi trong container bay theo lần
redeploy kế tiếp. Nên sao lưu là kiểu **KÉO** — một máy bên ngoài gọi
`GET /v1/admin/backup` rồi giữ file. Không có máy ngoài đặt lịch thì **không
có bản sao lưu nào cả**, kể cả khi endpoint hoạt động hoàn hảo.

Hai script, cùng ràng buộc, khác vỏ:

| Máy | Script | Đặt lịch bằng |
|---|---|---|
| Windows | `scripts/backup-pull.ps1` | Task Scheduler |
| Linux/macOS | `scripts/backup-pull.sh` | `cron` |

Cả hai đều: kiểm HTTP 200, **giải nén thật** để chắc file không hỏng, từ chối
bản dump rỗng, chỉ đổi tên `.part` → tên chính thức khi đã qua hết, và xoay
vòng giữ N bản mới nhất. File `.gz` hỏng nằm trong thư mục sao lưu là kiểu
hỏng tệ nhất — chỉ phát hiện đúng lúc cần khôi phục.

### Windows (máy chủ dự án)

```powershell
# 1. Cất token vào biến môi trường của user (không nhét vào dòng lệnh của
#    Task Scheduler — chỗ đó ai mở Task Scheduler cũng đọc được).
setx VOXDUB_ADMIN_TOKEN "<ADMIN_TOKEN của máy chủ>"

# 2. Chạy TAY một lần trước khi đặt lịch. Đặt lịch cho một thứ chưa từng chạy
#    thành công = lên lịch cho một thất bại im lặng.
cd C:\voxdub\control_server
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup-pull.ps1 C:\voxdub-backups 14

# 3. Đặt lịch 3h sáng hằng ngày. Để NGUYÊN một dòng — dấu `^` xuống dòng là
#    của cmd.exe, dán vào PowerShell sẽ hỏng.
schtasks /Create /SC DAILY /ST 03:00 /TN "VoxDub backup" /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\voxdub\control_server\scripts\backup-pull.ps1 C:\voxdub-backups 14"
```

Máy tắt lúc 3h sáng thì lượt đó **mất luôn**, không chạy bù. Muốn chạy bù khi
máy bật lại, thêm `/RI` hoặc bật "Run task as soon as possible after a
scheduled start is missed" trong Task Scheduler UI.

### Linux/macOS

```bash
0 3 * * * VOXDUB_ADMIN_TOKEN=... /đường/dẫn/backup-pull.sh ~/voxdub-backups 14
```

### Kiểm lại — bắt buộc, không phải tuỳ chọn

Sao lưu không ai kiểm là sao lưu giả vờ. Mỗi vài tuần mở thư mục đích xem file
mới nhất có đúng ngày hôm qua không, và dung lượng không đột ngột tụt.

### Khôi phục

```bash
node scripts/restore-backup.js <file.ndjson.gz>          # upsert: giữ bản ghi mới hơn
node scripts/restore-backup.js <file.ndjson.gz> --wipe   # xoá sạch rồi nhập: quay ngược thời gian
```

Kết nối bằng `MONGODB_URI` giống máy chủ nên chạy được từ bất kỳ đâu thấy được
database.

## 8. Publish GitHub Release cho app desktop (không liên quan `control_server`
   nhưng chung 1 repo, dễ nhầm)

Token GitHub cần quyền **`workflow`** để push được thay đổi trong
`.github/workflows/` — token loại "Fine-grained" cần bật riêng mục
**"Workflows: Read and write"** (khác `.env`, không tự động theo quyền
"Contents"). Thiếu quyền này, `git push` báo lỗi rõ ràng
`refusing to allow a Personal Access Token to create or update workflow`.

Tag `v*` mới kích hoạt `.github/workflows/release.yml` — không tự chạy
khi chỉ push `main`.

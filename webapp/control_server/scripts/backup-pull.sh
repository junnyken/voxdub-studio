#!/usr/bin/env bash
# Kéo một bản sao lưu đầy đủ về máy đang chạy script này (mini-spec V48).
#
# Vì sao chạy TỪ NGOÀI chứ không phải cron trong container: nền tảng đang
# dùng (Vibe Host) không có ổ đĩa bền vững — bản dump ghi trong container sẽ
# bay theo lần redeploy kế tiếp, tức là sao lưu giả vờ. Máy chạy script này
# (laptop, workspace, hay 1 VPS bất kỳ) mới là nơi bản sao thật sự sống.
#
#   VOXDUB_ADMIN_TOKEN=... ./backup-pull.sh [thư-mục-đích] [số-bản-giữ-lại]
#
# Đặt vào crontab của máy đó để có sao lưu hàng ngày, ví dụ 3h sáng:
#   0 3 * * * VOXDUB_ADMIN_TOKEN=... /đường/dẫn/backup-pull.sh ~/voxdub-backups 14
set -euo pipefail

BASE_URL="${VOXDUB_BASE_URL:-https://voxdub-app.cmc-1.vibenode.matbao.ai}"
DEST_DIR="${1:-./backups}"
KEEP="${2:-14}"

if [ -z "${VOXDUB_ADMIN_TOKEN:-}" ]; then
  echo "Thiếu VOXDUB_ADMIN_TOKEN (biến môi trường ADMIN_TOKEN của máy chủ)." >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
TMP="$DEST_DIR/.voxdub-backup-$STAMP.part"
OUT="$DEST_DIR/voxdub-backup-$STAMP.ndjson.gz"

HTTP_CODE=$(curl -sS -w '%{http_code}' -o "$TMP" \
  -H "X-Admin-Token: $VOXDUB_ADMIN_TOKEN" \
  "$BASE_URL/v1/admin/backup")

if [ "$HTTP_CODE" != "200" ]; then
  echo "Sao lưu THẤT BẠI (HTTP $HTTP_CODE): $(head -c 300 "$TMP")" >&2
  rm -f "$TMP"
  exit 1
fi

# Kiểm tra thật sự giải nén được TRƯỚC khi đặt tên chính thức — file .gz hỏng
# mà vẫn nằm trong thư mục sao lưu là kiểu hỏng tệ nhất: chỉ phát hiện đúng
# lúc cần khôi phục.
if ! gzip -t "$TMP" 2>/dev/null; then
  echo "File tải về không phải gzip hợp lệ, bỏ." >&2
  rm -f "$TMP"
  exit 1
fi

LINES=$(gzip -dc "$TMP" | wc -l)
if [ "$LINES" -lt 1 ]; then
  echo "Bản sao lưu rỗng, bỏ." >&2
  rm -f "$TMP"
  exit 1
fi

mv "$TMP" "$OUT"
echo "OK: $OUT ($(du -h "$OUT" | cut -f1), $LINES dòng)"

# Xoay vòng: giữ lại $KEEP bản mới nhất.
ls -1t "$DEST_DIR"/voxdub-backup-*.ndjson.gz 2>/dev/null | tail -n "+$((KEEP + 1))" | while read -r old; do
  rm -f "$old"
  echo "đã xoá bản cũ: $old"
done

#!/usr/bin/env bash
# Sinh nhánh deploy TỰ ĐỘNG `deploy/vays-control-server` cho VAYS
# (vibehost.matbao.ai) — cùng ràng buộc đã xác nhận thật với
# gen_vays_dub_worker_branch.sh: VAYS build theo model "1 subdir = build
# context" và subdir chỉ nhận thư mục con Ở NGAY GỐC repo. `control_server/
# Dockerfile` build đa giai đoạn cần copy CẢ `website/` (build React) LẪN
# `control_server/` từ gốc repo (context "." trong docker-compose.yml) —
# không thể trỏ subdir=control_server thẳng vì website/ sẽ nằm ngoài build
# context.
#
# Script này dựng 1 thư mục GỐC MỚI `webapp/` (ngang hàng control_server/,
# website/, dub-worker) chứa bản sao control_server/ + website/ + Dockerfile
# (COPY paths bên trong Dockerfile giữ nguyên vì context mới `webapp/` vẫn
# chứa 2 thư mục con cùng tên) — TRÊN MỘT NHÁNH RIÊNG (không đụng main).
# KHÔNG sửa tay các file được sinh ra — sửa control_server/ hoặc website/
# hoặc control_server/Dockerfile trên main rồi chạy lại script này.
#
# Chạy lại + force-push mỗi khi control_server/ hoặc website/ đổi, trước
# khi redeploy trên VAYS.
#
# Dùng: scripts/gen_vays_control_server_branch.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="deploy/vays-control-server"
# C57 — CI tự chạy script này sau mỗi lần push `main`, nên hai thứ dưới đây
# nhận biến môi trường: `REMOTE` (trên CI là `origin`, ở máy là `github`) và
# `GOC` (commit gốc để sinh; CI truyền thẳng SHA vì checkout có thể ở trạng
# thái HEAD rời). Mặc định giữ NGUYÊN như cũ để lệnh gõ tay không đổi.
REMOTE="${REMOTE:-github}"
GOC_SINH="${GOC:-main}"
WORKTREE_DIR="$(mktemp -d)"
# D3 — GHIM SHA NGUỒN vào chính nhánh deploy.
#
# Trước D3, commit sinh ra chỉ có câu "regenerate ..." và không nơi nào nói nó
# dựng từ commit nào của `main`. Truy vết vẫn có nhưng ở dạng NGẦM (cha của
# commit deploy chính là SHA nguồn) — ngầm thì đọc được lúc bình tĩnh, không
# đọc được lúc đang dò một sự cố.
#
# Hai chỗ ghi, cố ý:
#   - trailer `Source-SHA:` trong commit  → đọc bằng `git log`, không cần
#     dựng lại gì;
#   - tệp trong thư mục build            → đi VÀO ảnh Docker, nên chính dịch
#     vụ đang chạy khai được nó ở `/health` (xem control_server/src/version.js).
#     Không có tệp này thì "prod đang chạy SHA nào" chỉ suy ra được từ nhánh,
#     tức vẫn là suy luận chứ không phải hỏi.
SHA_NGUON="$(git rev-parse "$GOC_SINH")"


cleanup() {
  git worktree remove "$WORKTREE_DIR" --force >/dev/null 2>&1 || true
  rm -rf "$WORKTREE_DIR"
}
trap cleanup EXIT

git worktree add -B "$BRANCH" "$WORKTREE_DIR" "$GOC_SINH" >/dev/null

cd "$WORKTREE_DIR"

# D6 — GỠ `.env.example` CỦA APP DESKTOP KHỎI GỐC NHÁNH.
#
# Nhánh này là worktree từ `main` nên nó mang CẢ repo, kể cả `.env.example` ở
# gốc — tệp của app desktop, không liên quan gì tới thứ được dựng ở đây.
#
# Bộ quét cấu hình của nền tảng đọc tệp Ở GỐC NHÁNH (không đọc build context)
# rồi CHẶN mọi lượt deploy bằng `ENV_REQUIRED`, đòi cấp 15 biến. Đo 24/09:
# nó đòi đúng những biến mà nó đọc ra rỗng — 11 biến khai `VAR=` cộng 4 biến
# màu khai `VAR=#FFFFFF` (bộ đọc của nó coi `#` là mở chú thích). 11+4=15, và
# trong 65 biến của tệp không biến nào khác có hai tính chất đó.
#
# KHÔNG sửa `.env.example` trên `main` để né: đã đo `python-dotenv` (thứ
# autodub/config.py dùng) và `set -a; . .env` đều trả đúng `#FFFFFF`, nên tệp
# trên main không hỏng — chỉ bộ đọc của nền tảng hiểu khác.
#
# Cấp bừa 15 biến cho worker là KHÔNG được: 5 biến `TRANSLATE_*` chèn thẳng
# một dòng bịa vào mọi lời nhắc dịch, còn `VOXDUB_API_URL` khác rỗng lật
# worker sang chế độ SaaS (cổng duy nhất phân biệt hai chế độ).
#
# Chỉ gỡ tệp Ở GỐC. `control_server/.env.example` và `website/.env.example`
# giữ nguyên — đo 24/09 xác nhận nền tảng không đọc chúng (nếu có thì nó đã
# đòi 22 biến của control_server chứ không đòi 15 biến desktop).
rm -f .env.example

TARGET="webapp"

rm -rf "$TARGET"
mkdir -p "$TARGET"
cp -r control_server "$TARGET/control_server"
cp -r website "$TARGET/website"
cp control_server/Dockerfile "$TARGET/Dockerfile"

# package.json CHỈ để VAYS auto-detect nhận diện đây là app Node (cùng lý
# do requirements.txt của nhánh dub-worker — có Dockerfile thôi KHÔNG đủ).
# Dockerfile vẫn tự npm ci trực tiếp trong control_server/ như cũ, KHÔNG
# dùng file này để cài đặt thật.
cp control_server/package.json "$TARGET/package.json"

# Tệp thường (không phải dotfile) và nằm TRONG `control_server/` để lệnh
# `COPY control_server/ ./` của Dockerfile mang nó vào ảnh. Dotfile dễ bị bỏ
# sót bởi một `.dockerignore` thêm vào sau này mà không ai nghĩ tới.
printf '%s\n' "$SHA_NGUON" > "$TARGET/control_server/SOURCE_SHA"

{
  echo "# ============================================================="
  echo "# FILE SINH TỰ ĐỘNG cho nhánh $BRANCH — KHÔNG sửa tay."
  echo "# Nguồn thật: control_server/Dockerfile trên main +"
  echo "# scripts/gen_vays_control_server_branch.sh. Sửa ở đó rồi chạy lại script."
  echo "# Thư mục này (webapp/, GỐC repo) chỉ tồn tại trên nhánh $BRANCH —"
  echo "# VAYS subdir chỉ nhận thư mục con Ở NGAY GỐC repo, không nhận"
  echo "# đường dẫn lồng như control_server/Dockerfile với build context"
  echo "# ngoài subdir (xác nhận thật lúc deploy dub-worker 2026-08-17)."
  echo "# ============================================================="
  echo
  cat "$TARGET/Dockerfile"
} > "$TARGET/Dockerfile.tmp"
mv "$TARGET/Dockerfile.tmp" "$TARGET/Dockerfile"

git add -A
if git diff --cached --quiet; then
  echo "Không có gì thay đổi so với lần sinh trước — bỏ qua commit."
else
  git commit -q -m "chore(deploy): regenerate self-contained webapp for VAYS" \
    -m "Source-SHA: $SHA_NGUON"
fi

git push --force "$REMOTE" "HEAD:$BRANCH"

echo "Đã push nhánh $BRANCH lên $REMOTE."

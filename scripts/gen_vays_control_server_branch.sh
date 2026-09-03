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

cleanup() {
  git worktree remove "$WORKTREE_DIR" --force >/dev/null 2>&1 || true
  rm -rf "$WORKTREE_DIR"
}
trap cleanup EXIT

git worktree add -B "$BRANCH" "$WORKTREE_DIR" "$GOC_SINH" >/dev/null

cd "$WORKTREE_DIR"

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
  git commit -q -m "chore(deploy): regenerate self-contained webapp for VAYS"
fi

git push --force "$REMOTE" "HEAD:$BRANCH"

echo "Đã push nhánh $BRANCH lên $REMOTE."

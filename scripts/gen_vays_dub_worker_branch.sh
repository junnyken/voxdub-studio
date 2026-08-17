#!/usr/bin/env bash
# Sinh nhánh deploy TỰ ĐỘNG `deploy/vays-dub-worker` cho VAYS (vibehost.matbao.ai).
#
# VAYS build theo model "1 subdir = build context" — không thấy được thư mục
# anh em (xem docs/TEST_LOG.md mục "Ghi nhận: thử deploy lên VAYS"). Script
# này copy autodub/ + 3 script cài đặt vào trong control_server/worker-dub/
# TRÊN MỘT NHÁNH RIÊNG (không đụng main) để subdir đó tự chứa đủ code build
# độc lập. KHÔNG sửa tay các file được sinh ra — sửa autodub/ trên main rồi
# chạy lại script này.
#
# Chạy lại + force-push mỗi khi autodub/ hoặc 3 script setup đổi, trước khi
# redeploy trên VAYS.
#
# Dùng: scripts/gen_vays_dub_worker_branch.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="deploy/vays-dub-worker"
REMOTE="github"
WORKTREE_DIR="$(mktemp -d)"

cleanup() {
  git worktree remove "$WORKTREE_DIR" --force >/dev/null 2>&1 || true
  rm -rf "$WORKTREE_DIR"
}
trap cleanup EXIT

git worktree add -B "$BRANCH" "$WORKTREE_DIR" main >/dev/null

cd "$WORKTREE_DIR"

TARGET="control_server/worker-dub"
rm -rf "$TARGET/autodub" "$TARGET/scripts"
mkdir -p "$TARGET/scripts"
cp -r autodub "$TARGET/autodub"
cp scripts/setup_whisper.py scripts/setup_vieneu.py scripts/setup_translate_local.py "$TARGET/scripts/"

# dub_worker.py giờ nằm ngay trong build context (không còn prefix control_server/worker-dub/)
sed -i 's#^COPY control_server/worker-dub/dub_worker\.py /app/dub_worker\.py#COPY dub_worker.py /app/dub_worker.py#' "$TARGET/Dockerfile"

{
  echo "# ============================================================="
  echo "# FILE SINH TỰ ĐỘNG cho nhánh $BRANCH — KHÔNG sửa tay."
  echo "# Nguồn thật: control_server/worker-dub/Dockerfile trên main +"
  echo "# scripts/gen_vays_dub_worker_branch.sh. Sửa ở đó rồi chạy lại script."
  echo "# Build context ở nhánh này = chính thư mục control_server/worker-dub/"
  echo "# (đã copy sẵn autodub/ + scripts/ vào trong), KHÔNG phải gốc repo."
  echo "# ============================================================="
  echo
  cat "$TARGET/Dockerfile"
} > "$TARGET/Dockerfile.tmp"
mv "$TARGET/Dockerfile.tmp" "$TARGET/Dockerfile"

git add -A
if git diff --cached --quiet; then
  echo "Không có gì thay đổi so với lần sinh trước — bỏ qua commit."
else
  git commit -q -m "chore(deploy): regenerate self-contained worker-dub for VAYS"
fi

git push --force "$REMOTE" "HEAD:$BRANCH"

echo "Đã push nhánh $BRANCH lên $REMOTE."

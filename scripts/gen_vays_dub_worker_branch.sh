#!/usr/bin/env bash
# Sinh nhánh deploy TỰ ĐỘNG `deploy/vays-dub-worker` cho VAYS (vibehost.matbao.ai).
#
# VAYS build theo model "1 subdir = build context", VÀ (xác nhận thật lúc
# deploy 2026-08-17) subdir chỉ nhận THƯ MỤC CON Ở NGAY GỐC REPO — không nhận
# đường dẫn lồng 2 cấp như `control_server/worker-dub` dù bên trong có đủ
# Dockerfile (Source Validation báo "chọn 1 trong: control_server, website").
# Script này dựng 1 thư mục GỐC MỚI `dub-worker/` (ngang hàng control_server/,
# website/) chứa Dockerfile + dub_worker.py + autodub/ + 3 script cài đặt —
# TRÊN MỘT NHÁNH RIÊNG (không đụng main). KHÔNG sửa tay các file được sinh
# ra — sửa autodub/ hoặc control_server/worker-dub/Dockerfile trên main rồi
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

SRC="control_server/worker-dub"
TARGET="dub-worker"

rm -rf "$TARGET"
mkdir -p "$TARGET/scripts"
cp -r autodub "$TARGET/autodub"
cp scripts/setup_whisper.py scripts/setup_vieneu.py scripts/setup_translate_local.py "$TARGET/scripts/"
cp "$SRC/dub_worker.py" "$TARGET/dub_worker.py"

# dub_worker.py giờ nằm ngay trong build context (không còn prefix control_server/worker-dub/)
sed 's#^COPY control_server/worker-dub/dub_worker\.py /app/dub_worker\.py#COPY dub_worker.py /app/dub_worker.py#' \
  "$SRC/Dockerfile" > "$TARGET/Dockerfile"

# requirements.txt CHỈ để VAYS auto-detect nhận diện đây là app Python (xác
# nhận thật lúc deploy 2026-08-17: có Dockerfile thôi KHÔNG đủ, detector đòi
# requirements.txt/package.json làm tín hiệu) — Dockerfile vẫn tự pip install
# trực tiếp như cũ, KHÔNG dùng file này, giữ nguyên logic cài đặt đã test.
cat > "$TARGET/requirements.txt" <<'EOF'
# Chỉ để nền tảng VAYS auto-detect app Python — KHÔNG dùng để cài đặt thật.
# Dockerfile tự pip install trực tiếp (xem control_server/worker-dub/Dockerfile
# trên main). Danh sách dưới đây PHẢI khớp các gói trong Dockerfile đó.
torch>=2.0.0,<3.0
pydub>=0.25.1,<2.0
numpy>=1.24,<3.0
python-dotenv>=1.0.1,<2.0
requests>=2.31.0,<3.0
cryptography>=42.0.0
demucs>=4.0.0,<5.0
soundfile>=0.13.0,<0.14
EOF

{
  echo "# ============================================================="
  echo "# FILE SINH TỰ ĐỘNG cho nhánh $BRANCH — KHÔNG sửa tay."
  echo "# Nguồn thật: control_server/worker-dub/Dockerfile trên main +"
  echo "# scripts/gen_vays_dub_worker_branch.sh. Sửa ở đó rồi chạy lại script."
  echo "# Thư mục này (dub-worker/, GỐC repo) chỉ tồn tại trên nhánh"
  echo "# $BRANCH — VAYS subdir chỉ nhận thư mục con Ở NGAY GỐC repo, không"
  echo "# nhận đường dẫn lồng như control_server/worker-dub (xác nhận thật"
  echo "# lúc deploy 2026-08-17)."
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

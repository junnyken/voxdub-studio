#!/usr/bin/env bash
# Một lệnh duy nhất để đưa mã lên VAYS — mini-spec V90.
#
# Vì sao: `voxdub-app` và `voxdub-dub-worker` deploy từ NHÁNH SINH TỰ ĐỘNG,
# không phải `main`. Quên chạy script sinh nhánh thì VAYS build lại mã CŨ và
# báo thành công — bẫy đã sập hai lần (18-08, 19-08), lần hai xảy ra dù
# runbook đã có hẳn một mục cảnh báo.
#
# Nên bước sinh nhánh KHÔNG còn là việc phải nhớ: nó nằm trong chính lệnh
# deploy. Chạy xong lệnh này thì nhánh deploy chắc chắn khớp `main`.
#
# Dùng:
#   scripts/deploy_vays.sh              # sinh lại cả hai nhánh rồi kiểm
#   scripts/deploy_vays.sh app          # chỉ control_server + website
#   scripts/deploy_vays.sh worker       # chỉ dub-worker
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MUC_TIEU="${1:-all}"

nhanh_hien_tai="$(git rev-parse --abbrev-ref HEAD)"
if [ "$nhanh_hien_tai" != "main" ]; then
  echo "!! Đang ở nhánh '$nhanh_hien_tai', không phải main."
  echo "   Nhánh deploy sinh TỪ main — chạy ở nhánh khác là đẩy nhầm mã."
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "!! Còn thay đổi chưa commit. Nhánh deploy sinh từ commit đã có trên"
  echo "   main, nên phần chưa commit sẽ KHÔNG lên máy chủ — commit trước đã."
  exit 1
fi

if [ "$MUC_TIEU" = "all" ] || [ "$MUC_TIEU" = "app" ]; then
  echo "== Sinh lại nhánh cho voxdub-app =="
  scripts/gen_vays_control_server_branch.sh
fi
if [ "$MUC_TIEU" = "all" ] || [ "$MUC_TIEU" = "worker" ]; then
  echo "== Sinh lại nhánh cho voxdub-dub-worker =="
  scripts/gen_vays_dub_worker_branch.sh
fi

echo
echo "== Kiểm lại: nhánh deploy đã khớp main chưa =="
git fetch github 'refs/heads/deploy/*:refs/remotes/github/deploy/*' -q || true
python3 scripts/kiem_nhanh_deploy.py

echo
echo "Xong phần mã. Giờ mới bấm redeploy trên VAYS."
echo "Sau khi deploy xong, kiểm bằng:"
echo "    python3 scripts/kiem_deploy_song.py https://voxdub-app.cmc-1.vibenode.matbao.ai"

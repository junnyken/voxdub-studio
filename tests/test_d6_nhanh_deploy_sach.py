"""D6 — nhánh deploy KHÔNG được mang `.env.example` của app desktop.

Vì sao tệp đó có mặt: nhánh deploy là worktree từ `main` nên nó mang CẢ repo,
kể cả tệp cấu hình mẫu của app desktop — thứ không liên quan gì tới cái được
dựng. Bộ quét cấu hình của nền tảng đọc tệp Ở GỐC NHÁNH rồi chặn mọi lượt
deploy bằng `ENV_REQUIRED`, đòi 15 biến mà Dockerfile không bao giờ đọc.

Test này CHẠY THẬT script sinh trong một repo tạm rồi soi nhánh nó đẩy ra,
chứ không so chuỗi trong mã script: so chuỗi thì đổi cách viết là test mù,
mà thứ cần canh là KẾT QUẢ trên nhánh.
"""
import os
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")

# 15 biến bị nền tảng đòi = 11 biến khai rỗng + 4 biến màu khai `=#RRGGBB`
# (bộ đọc của nền tảng coi `#` là mở chú thích nên cũng ra rỗng).
ENV_MAU = (
    "WHISPER_BEAM_SIZE=\n"
    "VOXDUB_API_URL=\n"
    "SUBTITLE_COLOR=#FFFFFF\n"
    "WHISPER_MODEL=auto\n"
)


def _chay(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", **kw)


def _repo_gia(goc, ten_script):
    """Repo tối thiểu đủ cho script sinh chạy, + một bare repo làm remote."""
    nguon = os.path.join(goc, "nguon")
    bare = os.path.join(goc, "remote.git")
    os.makedirs(nguon)
    _chay(["git", "init", "-q", "-b", "main", "."], nguon)
    _chay(["git", "config", "user.email", "t@t.t"], nguon)
    _chay(["git", "config", "user.name", "t"], nguon)
    _chay(["git", "init", "-q", "--bare", bare], goc)

    def ghi(duong, noi_dung):
        p = os.path.join(nguon, duong)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(noi_dung)

    # Tệp gây ra cả sự cố.
    ghi(".env.example", ENV_MAU)
    # Hai tệp KHÔNG được đụng tới — nền tảng không đọc chúng.
    ghi("control_server/.env.example", "MONGODB_URI=\n")
    ghi("website/.env.example", "VITE_API=\n")

    # Đủ thứ mỗi script cần chép.
    ghi("autodub/__init__.py", "")
    for s in ("setup_whisper.py", "setup_vieneu.py",
              "setup_translate_local.py", "_python_ho_tro.py"):
        ghi(f"scripts/{s}", "# stub\n")
    ghi("control_server/worker-dub/dub_worker.py", "# stub\n")
    ghi("control_server/worker-dub/Dockerfile",
        "FROM python:3.12\n"
        "COPY control_server/worker-dub/dub_worker.py /app/dub_worker.py\n")
    ghi("control_server/Dockerfile", "FROM node:22\n")
    ghi("control_server/package.json", '{"name":"cs"}\n')
    ghi("website/index.html", "<html></html>\n")

    # Script THẬT, chép nguyên văn — nó tự định vị REPO_ROOT theo chỗ nó nằm.
    with open(os.path.join(SCRIPTS, ten_script), encoding="utf-8") as f:
        ghi(f"scripts/{ten_script}", f.read())

    _chay(["git", "add", "-A"], nguon)
    _chay(["git", "commit", "-qm", "goc"], nguon)
    return nguon, bare


def _sinh(nguon, bare, ten_script):
    moi = dict(os.environ, REMOTE=bare, GOC="main")
    _chay(["bash", f"scripts/{ten_script}"], nguon, env=moi)


def _tep_tren_nhanh(bare, nhanh):
    ra = _chay(["git", "ls-tree", "-r", "--name-only", nhanh], bare)
    return set(ra.stdout.split())


CA_HAI = [
    ("gen_vays_dub_worker_branch.sh", "deploy/vays-dub-worker", "dub-worker"),
    ("gen_vays_control_server_branch.sh", "deploy/vays-control-server", "webapp"),
]


@pytest.mark.parametrize("ten,nhanh,build", CA_HAI)
def test_nhanh_deploy_KHONG_mang_env_example_o_goc(tmp_path, ten, nhanh, build):
    nguon, bare = _repo_gia(str(tmp_path), ten)
    _sinh(nguon, bare, ten)
    tep = _tep_tren_nhanh(bare, nhanh)

    assert ".env.example" not in tep, (
        f"{ten}: nhánh {nhanh} vẫn mang .env.example của app desktop ở gốc ⇒ "
        "nền tảng sẽ chặn deploy bằng ENV_REQUIRED, đòi 15 biến mà Dockerfile "
        "không đọc")
    assert any(t.startswith(build + "/") for t in tep), \
        f"{ten}: không sinh ra thư mục build {build}/"


@pytest.mark.parametrize("ten,nhanh,build", CA_HAI)
def test_chi_go_tep_O_GOC_hai_tep_kia_giu_nguyen(tmp_path, ten, nhanh, build):
    """Gỡ rộng tay hơn là đổi thứ đi vào ảnh — ngoài phạm vi D6."""
    nguon, bare = _repo_gia(str(tmp_path), ten)
    _sinh(nguon, bare, ten)
    tep = _tep_tren_nhanh(bare, nhanh)

    assert "control_server/.env.example" in tep
    assert "website/.env.example" in tep


def test_BANG_CHUNG_PHU_DINH_bo_buoc_don_thi_test_phai_DO(tmp_path):
    """Tiêm lỗi: gỡ đúng dòng dọn khỏi script ⇒ phép kiểm trên phải bắt được.

    Không có bước này thì test trên có thể đang xanh vì một lý do khác (vd
    script chưa bao giờ chép tệp đó vào) chứ không phải vì nó dọn thật.
    """
    ten = "gen_vays_dub_worker_branch.sh"
    nguon, bare = _repo_gia(str(tmp_path), ten)

    p = os.path.join(nguon, "scripts", ten)
    with open(p, encoding="utf-8") as f:
        ma = f.read()
    assert "\nrm -f .env.example\n" in ma, "mốc tiêm lỗi không còn — sửa test"
    with open(p, "w", encoding="utf-8") as f:
        f.write(ma.replace("\nrm -f .env.example\n", "\n"))
    _chay(["git", "commit", "-aqm", "tiem loi"], nguon)

    _sinh(nguon, bare, ten)
    assert ".env.example" in _tep_tren_nhanh(bare, "deploy/vays-dub-worker"), (
        "bỏ bước dọn mà nhánh vẫn sạch ⇒ test không đo cái nó tưởng đang đo")

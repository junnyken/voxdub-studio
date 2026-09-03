"""V90 — chốt chặn cho bẫy "nhánh deploy không theo main".

Bẫy đã sập hai lần (18-08, 19-08). Lần hai xảy ra **dù runbook đã có hẳn một
mục cảnh báo** — bằng chứng rằng tài liệu không sửa được lỗi con người.

Bộ dò `kiem_nhanh_deploy.py` chỉ có ích khi ánh xạ đường dẫn của nó khớp đúng
thứ script sinh nhánh chép sang. Ánh xạ lệch thì hoặc bỏ sót (vô dụng), hoặc
kêu nhầm — mà bộ kiểm hay kêu nhầm thì người ta tắt đi, còn tệ hơn không có.
Bản đầu của chính bộ dò đã kêu nhầm 99 tệp cho worker vì đúng lỗi này.

Nên ở đây **canh chính bộ canh**: đọc script sinh nhánh, rút ra thứ nó chép,
rồi bắt ánh xạ phải phủ hết.
"""
from __future__ import annotations

import importlib.util
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _nap_bo_do():
    spec = importlib.util.spec_from_file_location(
        "kiem_nhanh_deploy", os.path.join(REPO, "scripts", "kiem_nhanh_deploy.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bo_do = _nap_bo_do()


def _doc(ten: str) -> str:
    return open(os.path.join(REPO, "scripts", ten), encoding="utf-8").read()


def test_co_du_ba_cong_cu():
    """Ba việc khác nhau: dò lệch, deploy đúng cách, kiểm sau khi deploy."""
    for ten in ("kiem_nhanh_deploy.py", "deploy_vays.sh", "kiem_deploy_song.py"):
        assert os.path.isfile(os.path.join(REPO, "scripts", ten)), ten


@pytest.mark.parametrize("nhanh", [
    "deploy/vays-control-server", "deploy/vays-dub-worker"])
def test_moi_nhanh_deploy_deu_duoc_theo_doi(nhanh):
    assert nhanh in bo_do.NHANH, f"{nhanh} không nằm trong bộ dò"


def test_anh_xa_phu_het_thu_ma_script_sinh_nhanh_chep():
    """Đọc `cp -r <thư mục>` trong hai script sinh nhánh rồi đối chiếu.

    Thêm một thư mục vào script sinh nhánh mà quên khai ở bộ dò thì thư mục
    đó âm thầm không được canh — đúng kiểu lỗ hổng đã tạo ra bẫy này.
    """
    theo_doi = {nguon for cap in bo_do.NHANH.values() for nguon, _ in cap}
    theo_doi |= {nguon.split("/")[0]
                 for cap in bo_do.TEP_LE.values() for nguon, _ in cap}

    bo_qua = {"$TARGET", "$SRC"}
    for ten in ("gen_vays_control_server_branch.sh", "gen_vays_dub_worker_branch.sh"):
        for thu_muc in re.findall(r'^\s*cp -r (\S+) ', _doc(ten), re.M):
            if thu_muc in bo_qua or thu_muc.startswith("$"):
                continue
            assert thu_muc in theo_doi, (
                f"{ten} chép '{thu_muc}/' nhưng bộ dò không canh thư mục đó")


def test_script_deploy_chan_chay_o_nhanh_khac():
    """Nhánh deploy sinh TỪ main — chạy ở nhánh khác là đẩy nhầm mã lên."""
    src = _doc("deploy_vays.sh")
    assert "abbrev-ref HEAD" in src and "main" in src


def test_script_deploy_chan_khi_con_thay_doi_chua_commit():
    """Nhánh deploy sinh từ commit đã có trên main; phần chưa commit sẽ không
    lên máy chủ — im lặng bỏ qua là đúng kiểu hỏng âm thầm."""
    src = _doc("deploy_vays.sh")
    assert "git diff --quiet" in src


def test_script_deploy_tu_sinh_nhanh_roi_tu_kiem():
    """Bước dễ quên nhất phải nằm TRONG lệnh deploy, không phải trong đầu."""
    src = _doc("deploy_vays.sh")
    assert "gen_vays_control_server_branch.sh" in src
    assert "gen_vays_dub_worker_branch.sh" in src
    assert "kiem_nhanh_deploy.py" in src


def test_kiem_song_luon_co_moc_doi_chung():
    """Chỉ thử cửa mới thì 404 dễ bị hiểu nhầm là route đăng ký sai. Phải có
    cửa CŨ làm đối chứng — đó mới là thứ phân biệt được hai ca."""
    src = _doc("kiem_deploy_song.py")
    assert "CU = [" in src and "MOI = [" in src
    assert "/v1/ai/translate" in src, "thiếu mốc đối chứng"
    assert "/v1/ai/assist" in src, "thiếu cửa mới"


def test_ci_chay_bo_do_tren_main():
    wf = open(os.path.join(REPO, ".github", "workflows", "test.yml"),
              encoding="utf-8").read()
    assert "kiem_nhanh_deploy.py" in wf, "CI chưa chạy bộ dò"
    assert "fetch-depth: 0" in wf, "thiếu lịch sử thì không so được cây thư mục"


def test_runbook_van_giu_canh_bao():
    """Tự động hoá không thay cho tài liệu — nó chỉ bù chỗ tài liệu bất lực."""
    rb = open(os.path.join(REPO, "control_server", "docs", "DEPLOY_RUNBOOK.md"),
              encoding="utf-8").read()
    assert "deploy/vays-control-server" in rb
    assert "deploy_vays.sh" in rb, "runbook phải chỉ sang lệnh làm đúng"


def test_script_chep_sang_nhanh_deploy_khong_thieu_phu_thuoc():
    """Chép một script mà quên module nó import là Docker build chết.

    Đã sập thật 20-08: `setup_whisper.py` import `_python_ho_tro` (thêm ở
    V80) nhưng script sinh nhánh worker chỉ chép ba tệp setup_*, nên build
    dừng ngay dòng import. Bộ dò V90 không bắt được vì nó so thứ ĐÃ khai,
    còn đây là phụ thuộc MỚI chưa ai khai.

    Test này đọc từng script được chép, tìm import module cục bộ, rồi bắt
    module đó cũng phải nằm trong danh sách chép.
    """
    # Hai nơi cùng liệt kê TAY danh sách tệp, thiếu ở nơi nào cũng chết:
    #   - script sinh nhánh (`cp ... "$TARGET/scripts/"`)
    #   - Dockerfile của worker (`COPY scripts/... /app/scripts/`)
    # Lượt deploy 20-08 sửa được nơi thứ nhất mà vẫn chết vì nơi thứ hai.
    nguon = {
        "gen_vays_dub_worker_branch.sh": _doc("gen_vays_dub_worker_branch.sh"),
        "control_server/worker-dub/Dockerfile": open(
            os.path.join(REPO, "control_server", "worker-dub", "Dockerfile"),
            encoding="utf-8").read(),
    }
    for ten_nguon, noi_dung in nguon.items():
        duoc_chep = set(re.findall(r'scripts/([\w.]+\.py)', noi_dung))
        assert duoc_chep, f"không đọc được danh sách tệp trong {ten_nguon}"
        _kiem_phu_thuoc(duoc_chep, ten_nguon)


def _kiem_phu_thuoc(duoc_chep: set[str], ten_nguon: str) -> None:

    thieu = []
    for ten in sorted(duoc_chep):
        duong = os.path.join(REPO, "scripts", ten)
        if not os.path.isfile(duong):
            continue
        src = open(duong, encoding="utf-8").read()
        for mod in re.findall(r'^\s*(?:from|import)\s+(_\w+)', src, re.M):
            if f"{mod}.py" not in duoc_chep:
                thieu.append(f"{ten} import {mod} nhưng {mod}.py không có "
                             f"trong {ten_nguon}")
    assert not thieu, "; ".join(thieu)


# ------------------------------------------- C57: máy tự sinh, đừng nhờ người ---

def _workflow() -> str:
    return open(os.path.join(REPO, ".github", "workflows", "test.yml"),
                encoding="utf-8").read()


def test_ci_tu_sinh_lai_nhanh_deploy():
    """Bước sinh lại nhánh phải do MÁY làm, không dựa vào trí nhớ con người.

    V90 đã kết luận tài liệu không sửa được lỗi này; C54 cho bộ kiểm chạy trên
    nhánh deploy nhưng lượt chạy của `main` vẫn đỏ tới khi có người nhớ chạy
    script. Chừng nào còn một bước tay thì còn ngày quên.
    """
    wf = _workflow()
    assert "sinh-nhanh-deploy:" in wf, "thiếu job sinh lại nhánh deploy"
    assert "gen_vays_control_server_branch.sh" in wf and \
           "gen_vays_dub_worker_branch.sh" in wf, \
        "job sinh nhánh phải chạy CẢ HAI script — thiếu một là nhánh kia tụt lại"
    assert "contents: write" in wf, "job sinh nhánh không có quyền push"


def test_kiem_drift_chay_SAU_khi_sinh_lai():
    """Chấm trước khi sinh thì luôn chấm phải trạng thái chưa sinh — đúng cái
    race đã làm lượt chạy của `main` đỏ ngày 03-09."""
    wf = _workflow()
    khoi = wf.split("deploy-branch-drift:", 1)[1]
    assert "needs: [sinh-nhanh-deploy]" in khoi.split("steps:", 1)[0], \
        "job kiểm drift phải phụ thuộc job sinh nhánh"


def test_script_sinh_nhanh_nhan_remote_va_goc_tu_moi_truong():
    """CI push về `origin` và sinh từ SHA vừa push; máy dev push về `github` và
    sinh từ `main`. Ghim cứng một trong hai là bên kia không dùng được."""
    for ten in ("gen_vays_control_server_branch.sh", "gen_vays_dub_worker_branch.sh"):
        ma = _doc(ten)
        assert 'REMOTE="${REMOTE:-github}"' in ma, f"{ten}: REMOTE bị ghim cứng"
        assert 'GOC_SINH="${GOC:-main}"' in ma, f"{ten}: gốc sinh bị ghim cứng"
        assert '"$GOC_SINH"' in ma, f"{ten}: khai biến gốc nhưng không dùng"


# ------------------- C57b: hỏi nhánh REMOTE, không phải bản sao trên máy ---

def test_bo_do_hoi_nhanh_TREN_REMOTE_truoc():
    """Thứ nền tảng hosting build là nhánh TRÊN REMOTE.

    Bản trước ưu tiên nhánh local. Từ khi CI tự sinh lại nhánh (C57), nhánh
    local trên máy dev cũ ngay lập tức ⇒ bộ dò kêu nhầm dù nội dung giống hệt
    (gặp thật 03-09: cùng md5 mà vẫn báo lệch). Bộ kiểm hay kêu nhầm thì bị tắt
    đi — còn tệ hơn không có (V90).

    Chiều ngược lại nguy hơn: local vô tình khớp `main` mà remote đang cũ thì
    bộ dò báo OK trong khi deploy build mã cũ — đúng bẫy V90 sinh ra để chặn.
    """
    ma = _doc_script_do()
    i_xa = ma.index('f"github/{nhanh}"')
    i_local = ma.index("else nhanh")
    assert i_xa < i_local, (
        "bộ dò vẫn ưu tiên nhánh local — phải hỏi nhánh trên remote trước")


def _doc_script_do() -> str:
    return open(os.path.join(REPO, "scripts", "kiem_nhanh_deploy.py"),
                encoding="utf-8").read()


def test_bo_do_van_chay_duoc_khi_chua_fetch_remote():
    """Máy chưa `git fetch` thì rơi về nhánh local, và phải NÓI RA nếu không
    có nhánh nào — im lặng trả 'khớp' là kiểu hỏng tệ nhất của một bộ dò."""
    ma = _doc_script_do()
    assert "không tìm thấy nhánh" in ma

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

"""C58 — bộ kích deploy tự động phải NÓI THẬT về kết quả.

Tự động hoá việc bấm nút là chuyện dễ. Cái khó là đừng biến nó thành một lệnh
gọi bắn-rồi-quên — đúng lớp lỗi C54 vừa dọn ở worker: CI xanh, prod chết, và
không ai biết cho tới khi có người tình cờ mở ra xem.

Nên bộ test này canh đúng những chỗ dễ nói dối:
* tác vụ deploy "thành công" mà dịch vụ không trả lời ⇒ vẫn phải là HỎNG;
* hỏng vì lỗi hạ tầng chập thì thử lại, nhưng hỏng vì mã sai thì ĐỪNG;
* hết giờ chờ phải nói "tôi không biết", không được đoán bừa là xong.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def bo_kich():
    duong_dan = os.path.join(GOC, "scripts", "trien_khai_vibehost.py")
    spec = importlib.util.spec_from_file_location("trien_khai_c58", duong_dan)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _gia_cong(bo_kich, monkeypatch, ket_qua: list, ghi: list | None = None):
    """Thay lời gọi mạng bằng một danh sách câu trả lời dựng sẵn."""
    hang_doi = list(ket_qua)

    def gia(ten, tham_so, **kw):
        if ghi is not None:
            ghi.append(ten)
        return hang_doi.pop(0)

    monkeypatch.setattr(bo_kich, "goi_cong", gia)


# --------------------------------------------- không được nói dối ---

def test_deploy_xong_ma_dich_vu_cam_thi_van_la_HONG(bo_kich, monkeypatch):
    """Nền tảng chấm điểm bằng cổng mạng; thứ người dùng gặp là câu trả lời của
    ứng dụng. Hai thứ đó lệch nhau là chuyện có thật."""
    _gia_cong(bo_kich, monkeypatch, [
        {"jobId": "j1"},
        {"job": {"state": "succeeded"}},
    ])
    monkeypatch.setattr(bo_kich, "kiem_suc_khoe",
                        lambda *a, **k: (_ for _ in ()).throw(
                            bo_kich.DeployHong("không trả 200")))
    with pytest.raises(bo_kich.DeployHong):
        bo_kich.trien_khai("id", "app", "https://x/health",
                           cong="c", token="t", ngu=lambda _s: None)


def test_suc_khoe_bo_cuoc_co_gioi_han_va_noi_ro(bo_kich):
    lan = []

    def mo_hong(url, timeout=0):
        lan.append(url)
        raise OSError("connection refused")

    with pytest.raises(bo_kich.DeployHong) as e:
        bo_kich.kiem_suc_khoe("https://x/health", so_lan=3, nhip_s=0,
                              ngu=lambda _s: None, mo=mo_hong)
    assert len(lan) == 3
    assert "đừng coi là đã lên" in str(e.value)


def test_suc_khoe_len_muon_van_tinh_la_dat(bo_kich):
    class _Resp:
        status = 200
        def read(self): return b'{"ok":true}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    lan = []

    def mo(url, timeout=0):
        lan.append(url)
        if len(lan) < 3:
            raise OSError("chưa lên")
        return _Resp()

    ra = bo_kich.kiem_suc_khoe("https://x/health", so_lan=5, nhip_s=0,
                               ngu=lambda _s: None, mo=mo)
    assert "ok" in ra and len(lan) == 3


# ------------------------------------------------ thử lại đúng ca ---

def test_thu_lai_khi_ha_tang_chap(bo_kich, monkeypatch):
    """Đã gặp thật 03-09: 'fetch failed (đã thử 6/6)', chạy lại thì xong."""
    ghi = []
    _gia_cong(bo_kich, monkeypatch, [
        {"jobId": "j1"},
        {"job": {"state": "failed", "error": "fetch failed (đã thử 6/6)"}},
        {"jobId": "j2"},
        {"job": {"state": "succeeded"}},
    ], ghi)
    monkeypatch.setattr(bo_kich, "kiem_suc_khoe", lambda *a, **k: "ok")
    bao_cao = bo_kich.trien_khai("id", "app", "https://x/health",
                                 cong="c", token="t", ngu=lambda _s: None)
    assert ghi.count("redeploy_project") == 2
    assert any("thử lại" in d for d in bao_cao)


def test_KHONG_thu_lai_khi_build_hong_vi_ma_sai(bo_kich, monkeypatch):
    """Thử lại một lượt build hỏng vì mã sai chỉ tốn thêm 11 phút để nhận đúng
    cùng một câu trả lời."""
    ghi = []
    _gia_cong(bo_kich, monkeypatch, [
        {"jobId": "j1"},
        {"job": {"state": "failed", "error": "npm ERR! build failed"}},
    ], ghi)
    with pytest.raises(bo_kich.DeployHong):
        bo_kich.trien_khai("id", "app", "https://x/health",
                           cong="c", token="t", ngu=lambda _s: None)
    assert ghi.count("redeploy_project") == 1


def test_phan_loai_loi_dang_thu_lai(bo_kich):
    assert bo_kich.dang_thu_lai_duoc("retry 4/6: fetch failed")
    assert bo_kich.dang_thu_lai_duoc("connect ETIMEDOUT 10.0.0.1:27017")
    assert not bo_kich.dang_thu_lai_duoc("npm ERR! code ELIFECYCLE")
    assert not bo_kich.dang_thu_lai_duoc("")


# ------------------------------------------- hết giờ ≠ đã thành công ---

def test_het_gio_thi_noi_KHONG_BIET_chu_khong_doan(bo_kich, monkeypatch):
    dong_ho = iter([0.0, 0.0, 9999.0, 9999.0, 9999.0])
    _gia_cong(bo_kich, monkeypatch, [
        {"job": {"state": "running", "progress": 27}},
        {"job": {"state": "running", "progress": 27}},
    ])
    with pytest.raises(bo_kich.DeployHong) as e:
        bo_kich.cho_xong("j1", cong="c", token="t", tran_s=10,
                         ngu=lambda _s: None, dong_ho=lambda: next(dong_ho))
    assert "KHÔNG kết luận được" in str(e.value)


def test_thieu_token_thi_dung_ngay_chu_khong_chay_tiep(bo_kich, monkeypatch):
    monkeypatch.delenv("VIBEHOST_TOKEN", raising=False)
    monkeypatch.setattr("sys.argv", ["x", "--du-an", "a", "--ten", "b",
                                     "--suc-khoe", "https://x"])
    assert bo_kich.main() == 2


# --------------------------------------- cắm vào quy trình phát hành ---

def test_workflow_chi_deploy_sau_khi_test_xanh():
    """Deploy tự động mà không đợi test là đổi một lớp rủi ro này lấy một lớp
    rủi ro khác — prod nhận thẳng mã chưa ai kiểm."""
    wf = open(os.path.join(GOC, ".github", "workflows", "test.yml"),
              encoding="utf-8").read()
    assert "trien-khai-prod:" in wf, "chưa cắm bước deploy vào CI"
    khoi = wf.split("trien-khai-prod:", 1)[1].split("steps:", 1)[0]
    for phai_co in ("python-tests", "node-tests", "chay-that-windows",
                    "sinh-nhanh-deploy"):
        assert phai_co in khoi, (
            f"bước deploy không đợi {phai_co} — prod có thể nhận mã chưa kiểm")


def test_workflow_chi_deploy_dich_vu_co_thay_doi():
    """Mỗi lượt dựng worker mất ~11 phút và kéo cả torch. Deploy lại cả hai
    dịch vụ cho một commit chỉ sửa tài liệu là đốt thời gian vô ích."""
    wf = open(os.path.join(GOC, ".github", "workflows", "test.yml"),
              encoding="utf-8").read()
    assert "dub-worker/" in wf and "webapp/" in wf, (
        "workflow phải so từng thư mục build để biết dịch vụ nào cần deploy")

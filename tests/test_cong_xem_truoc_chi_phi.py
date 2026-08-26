"""V97 phần 2 — cho xem giá TRƯỚC khi tiêu Vox.

Trước mini-spec này, số Vox chỉ hiện ở bảng tổng kết — tức là sau khi máy chủ
đã dịch và đã trừ tiền. Route `/v1/device/estimate` và hàm `SaasClient.estimate`
đã có sẵn từ lâu nhưng **không nơi nào gọi**. Với video dài, chênh lệch giữa
"biết trước" và "biết sau" là hàng trăm nghìn đồng.

Bộ test giữ bốn quyết định thiết kế, mỗi cái đều có thể lặng lẽ mất đi:

1. Hỏi giá phải nằm TRƯỚC `setup_hold` (giữ chỗ rồi mới hỏi thì hỏi làm gì).
2. Chỉ luồng wizard mới dừng — batch/dòng lệnh không có ai ngồi đó để bấm.
3. Đã duyệt rồi thì không hỏi lại.
4. Hỏi giá trượt thì KHÔNG chặn, nhưng phải để lại cảnh báo.
"""
from __future__ import annotations

import ast
import logging

import pytest

from autodub.billing import HoldBillingAdapter
from autodub.config import Settings
from autodub.progress import ProgressReporter
from autodub.saas_client import OfflineError
from tests import doc_ma


class _MayChu:
    def __init__(self, **tra):
        self.tra = tra
        self.so_lan = 0

    def estimate(self, sentences, *, auto_translate=False, metadata=False):
        self.so_lan += 1
        self.da_hoi = {"sentences": sentences, "auto_translate": auto_translate}
        return self.tra


@pytest.fixture
def adapter():
    return HoldBillingAdapter(Settings(), ProgressReporter())


@pytest.fixture
def co_may_chu(monkeypatch):
    def _dung(client):
        monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
        monkeypatch.setattr("autodub.saas_client.get_client", lambda: client)
        return client
    return _dung


def _segments(n=100):
    return [{"id": i, "start": i, "end": i + 1, "text": "câu"} for i in range(n)]


def test_dung_lai_va_tra_ve_gia(adapter, co_may_chu, tmp_path):
    co_may_chu(_MayChu(estimated=1200, balance=5000, sufficient=True,
                       creditEnabled=True))
    ra = adapter.cong_xem_truoc(_segments(100), str(tmp_path), 300.0,
                                khong_can_dich=False, da_duyet=False)
    assert ra is not None and ra.status == "cost_pending"
    assert ra.report["estimated"] == 1200
    assert ra.report["balance"] == 5000
    assert ra.report["sentences"] == 100


def test_da_duyet_thi_khong_hoi_lai(adapter, co_may_chu, tmp_path):
    may = co_may_chu(_MayChu(estimated=1200, balance=5000, creditEnabled=True))
    ra = adapter.cong_xem_truoc(_segments(), str(tmp_path), 300.0,
                                khong_can_dich=False, da_duyet=True)
    assert ra is None
    assert may.so_lan == 0, "đã duyệt rồi mà vẫn gọi máy chủ hỏi giá"


def test_chay_thuan_tren_may_thi_khong_hoi(adapter, monkeypatch, tmp_path):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    assert adapter.cong_xem_truoc(_segments(), str(tmp_path), 300.0,
                                  khong_can_dich=False, da_duyet=False) is None


def test_may_chu_tat_tinh_tien_thi_khong_hoi(adapter, co_may_chu, tmp_path):
    co_may_chu(_MayChu(estimated=0, balance=0, creditEnabled=False))
    assert adapter.cong_xem_truoc(_segments(), str(tmp_path), 300.0,
                                  khong_can_dich=False, da_duyet=False) is None


def test_hoi_gia_truot_thi_chay_tiep_nhung_co_canh_bao(
        adapter, monkeypatch, tmp_path, caplog):
    """Cổng thông tin, không phải cổng an toàn: `setup_hold` ngay sau đó vẫn
    tự chặn khi thiếu Vox. Nhưng trượt mà im lặng thì đúng bằng không có."""
    class _Hong:
        def estimate(self, *a, **k):
            raise OfflineError("mất mạng")
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: _Hong())
    with caplog.at_level(logging.WARNING):
        ra = adapter.cong_xem_truoc(_segments(), str(tmp_path), 300.0,
                                    khong_can_dich=False, da_duyet=False)
    assert ra is None
    assert any("hỏi được giá" in r.message for r in caplog.records), \
        "hỏi giá trượt mà không để lại dấu vết nào"


def test_cung_ngon_ngu_thi_khong_tinh_tien_dich(adapter, co_may_chu, tmp_path):
    """Nguồn trùng đích thì không có bước dịch nào chạy (C23) — giá hỏi ra
    cũng phải phản ánh đúng thế."""
    may = co_may_chu(_MayChu(estimated=1000, balance=5000, creditEnabled=True))
    adapter.cong_xem_truoc(_segments(), str(tmp_path), 300.0,
                           khong_can_dich=True, da_duyet=False)
    assert may.da_hoi["auto_translate"] is False


# --- Vị trí trong pipeline: đọc mã, vì chạy thật cần ASR + mạng ----------

def _than_run_impl() -> str:
    nguon = open("autodub/pipeline.py", encoding="utf-8").read()
    for nut in ast.walk(ast.parse(nguon)):
        if isinstance(nut, ast.FunctionDef) and nut.name == "_run_impl":
            return ast.get_source_segment(nguon, nut) or ""
    raise AssertionError("pipeline.py không còn _run_impl")


def test_hoi_gia_dung_truoc_khi_giu_cho():
    """Giữ chỗ xong mới hỏi thì tiền đã bị khoá — hỏi để làm gì nữa."""
    than = _than_run_impl()
    assert "cong_xem_truoc" in than, "pipeline không hề hỏi giá"
    assert than.index("cong_xem_truoc") < than.index("_setup_hold("), \
        "hỏi giá đứng SAU khi giữ chỗ Vox"


def test_chi_hoi_o_luong_wizard():
    """Batch và dòng lệnh không có ai ngồi trước màn hình để bấm — dừng lại ở
    đó là treo cả mẻ. Kiểm bằng AST: lời gọi phải nằm TRONG khối
    `if req.defer_export`, chứ không chỉ tình cờ đứng gần chữ đó."""
    nguon = open("autodub/pipeline.py", encoding="utf-8").read()
    cay = ast.parse(nguon)

    def trong_khoi_defer(nut) -> bool:
        for con in ast.walk(nut):
            if not isinstance(con, ast.If):
                continue
            if "defer_export" not in ast.dump(con.test):
                continue
            for x in ast.walk(ast.Module(body=con.body, type_ignores=[])):
                if (isinstance(x, ast.Call)
                        and getattr(x.func, "attr", "") == "cong_xem_truoc"):
                    return True
        return False

    assert trong_khoi_defer(cay), \
        "cổng hỏi giá không nằm trong khối `if req.defer_export`"


def test_gop_cau_dung_truoc_khi_tinh_tien():
    """Gộp sau khi chốt giá thì chẳng tiết kiệm được đồng nào."""
    than = _than_run_impl()
    assert "gop_de_dich" in than, "pipeline không gộp câu"
    assert than.index("gop_de_dich") < than.index("_setup_hold("), \
        "gộp câu đứng SAU khi giữ chỗ — tiền vẫn tính theo mẩu vụn"
    assert than.index("gop_de_dich") < than.index("cong_xem_truoc"), \
        "báo giá trước khi gộp — con số hiện cho người dùng là giá của mẩu vụn"
    assert than.index("gop_de_dich") < than.index("annotate_slots(segments)"), \
        "gộp sau khi chia khung thời gian — khung tính trên mẩu cũ, sai hết"


def test_bam_chay_tiep_phai_doi_luong_cu_dong():
    """`finished_ok` bắn từ TRONG thân worker — QThread lúc đó vẫn đang chạy.
    Gọi `_launch` ngay thì nó thấy "đang có video chạy dở" và từ chối: người
    dùng bấm Chạy tiếp mà không có gì xảy ra."""
    nguon = open("autodub_gui/pages/new_project_page.py", encoding="utf-8").read()
    for nut in ast.walk(ast.parse(nguon)):
        if (isinstance(nut, ast.FunctionDef)
                and nut.name == "_chay_tiep_sau_khi_duyet_gia"):
            than = ast.get_source_segment(nguon, nut) or ""
            break
    else:
        raise AssertionError("không còn hàm _chay_tiep_sau_khi_duyet_gia")
    assert "isRunning()" in than, "không kiểm luồng cũ còn chạy hay không"
    assert "finished.connect" in than, "không đợi luồng cũ đóng rồi mới chạy"


def test_giao_dien_co_nhanh_xu_ly_cost_pending():
    nguon = open("autodub_gui/pages/new_project_page.py", encoding="utf-8").read()
    assert '"cost_pending"' in nguon, "giao diện không xử lý trạng thái mới"
    assert "chi_phi_da_duyet = True" in nguon, \
        "bấm chạy tiếp mà không mang theo dấu đã duyệt — sẽ hỏi lại vô tận"


def test_tat_hoi_duyet_thi_chay_thang():
    """Người dùng chạy nhiều video liên tiếp tắt được cổng hỏi (D1e)."""
    than = _than_run_impl()
    assert "hoi_truoc_khi_tieu_vox" in than, \
        "không có đường tắt cổng hỏi — người làm hàng loạt phải bấm mỗi lượt"
    i = than.index("hoi_truoc_khi_tieu_vox")
    assert than.index("cong_xem_truoc") > i, \
        "cờ tắt phải được xét TRƯỚC khi gọi hỏi giá"


def test_chi_ghi_khong_hoi_lai_khi_nguoi_dung_dong_y():
    """Tích ô rồi bấm Hủy là đổi ý về video NÀY, không phải cho phép tiêu
    tiền mọi video sau."""
    nguon = open("autodub_gui/pages/new_project_page.py", encoding="utf-8").read()
    assert "if dong_y and khong_hoi_lai:" in nguon, (
        "ghi cờ mà không xét người dùng có bấm đồng ý hay không")
    assert 'write_env({"HOI_TRUOC_KHI_TIEU_VOX": "false"})' in nguon

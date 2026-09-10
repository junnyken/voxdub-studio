"""Script gom bằng chứng pilot Phase H.

Hai thứ phải giữ:
  1. **Không rò transcript/caption gốc** ra báo cáo — báo cáo mà phá cam kết
     của H2c thì chính nó trở thành bản sao copy-ready mà H2c né.
  2. **Không kết luận ĐẠT khi thiếu bằng chứng.** Một báo cáo tô hồng còn tệ
     hơn không có báo cáo: nó là cái cớ để mở H4 sớm.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_DUONG = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "bao_cao_pilot_phase_h.py"
_spec = importlib.util.spec_from_file_location("bao_cao_pilot", _DUONG)
bcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bcp)

CAU_NGUON = "Sáng nào mình cũng dậy sớm hơn nửa tiếng để chuẩn bị bữa sáng"


class _ClientGia:
    def __init__(self, *, blueprints=None, bp=None, brands=None, scripts=None):
        self._blueprints = blueprints if blueprints is not None else [{"id": "bp1"}]
        self._bp = bp if bp is not None else _bp_day_du()
        self._brands = brands if brands is not None else [_brand()]
        self._scripts = scripts if scripts is not None else []

    def list_flow_blueprints(self): return self._blueprints
    def get_flow_blueprint(self, _id): return self._bp
    def list_brand_profiles(self): return self._brands
    def list_brand_scripts(self): return self._scripts


def _bp_day_du(**kw):
    goc = {
        "id": "bp1", "sourceType": "url", "sourceReference": "https://x/v",
        "status": "ready", "languageSourceDetected": "en",
        "samplingPolicyUsed": "0-5s mỗi 0.2s",
        "evidenceSummary": "ASR: 6 câu. OCR: 4 quan sát từ 71 khung lấy mẫu.",
        "beats": [{"startS": 0, "endS": 3, "beatType": "hook",
                   "narrativeFunctionVi": "Mở đầu", "evidenceStatus": "ok"}],
        "evidenceFingerprint": {"v": 1, "soBam": 520, "soDong": 40,
                                "soDongBoQua": 2, "dayTran": False},
    }
    goc.update(kw)
    return goc


def _brand(**kw):
    goc = {"tenBrand": "Bếp Nhà Vui", "moTaSanPham": "Nồi chiên",
           "doiTuongKhach": "Mẹ bỉm", "toneGiong": "Gần gũi",
           "usp": "Nóng trong 3 phút", "rangBuocKhongDuocNoi": ["tốt nhất"]}
    goc.update(kw)
    return goc


def _script(status, beats):
    return {"id": "s1", "status": status, "originalityCheckVersion": 1,
            "createdAt": "2026-09-10T00:00:00Z", "beats": beats}


def _beat(**kw):
    goc = {"beatType": "hook", "originalityFlag": "clear", "complianceFlag": "clear",
           "flaggedExcerpt": "", "complianceExcerpt": "", "lyDoChuaKiem": ""}
    goc.update(kw)
    return goc


def test_khong_ro_transcript_goc_ra_bao_cao():
    # Dấu vân tay chỉ có metadata, nhưng nếu ai đó sau này nhét evidence thô
    # vào API thì báo cáo cũng không được in nó ra.
    bp = _bp_day_du(transcript=[{"text": CAU_NGUON}],
                    ocrEvidence=[{"text": "MUA NGAY KẺO HẾT"}])
    ra = bcp.dung_bao_cao(_ClientGia(bp=bp))
    assert CAU_NGUON not in ra
    assert "MUA NGAY KẺO HẾT" not in ra


def test_khong_in_noi_dung_usp_va_mo_ta_san_pham():
    ra = bcp.dung_bao_cao(_ClientGia(
        brands=[_brand(usp="BÍ MẬT KINH DOANH", moTaSanPham="CÔNG THỨC RIÊNG")]))
    assert "BÍ MẬT KINH DOANH" not in ra
    assert "CÔNG THỨC RIÊNG" not in ra
    assert "Bếp Nhà Vui" in ra          # tên brand thì hiện, để biết dùng hồ sơ nào


def test_chua_co_blueprint_thi_noi_thang_la_khong_ket_luan_duoc():
    ra = bcp.dung_bao_cao(_ClientGia(blueprints=[]))
    assert "CHƯA CÓ FLOW BLUEPRINT NÀO" in ra
    assert "không kết luận được" in ra


def test_thieu_dau_van_tay_thi_bao_cong_3_chua_dat():
    ra = bcp.dung_bao_cao(_ClientGia(bp=_bp_day_du(evidenceFingerprint=None)))
    assert "KHÔNG CÓ DẤU VÂN TAY" in ra
    assert "unconfirmed" in ra


def test_hồ_so_brand_thieu_truong_thi_danh_dau_THIEU():
    ra = bcp.dung_bao_cao(_ClientGia(brands=[_brand(usp="")]))
    assert "**THIẾU**" in ra


def test_cong_4_chi_DAT_khi_co_CA_ready_lan_blocked():
    # Chỉ có `ready` là chưa đủ: chưa chứng minh được gate chặn thật.
    chi_sach = _ClientGia(scripts=[_script("ready", [_beat()])])
    ra = bcp.dung_bao_cao(chi_sach)
    assert "**CHƯA CÓ** — chưa kích hoạt được gate nào" in ra

    du_ca_hai = _ClientGia(scripts=[
        _script("ready", [_beat()]),
        _script("blocked", [_beat(complianceFlag="violated", complianceExcerpt="tốt nhất")]),
    ])
    ra2 = bcp.dung_bao_cao(du_ca_hai)
    assert "**CHƯA CÓ** — chưa kích hoạt được gate nào" not in ra2
    assert "tốt nhất" in ra2, "phải chỉ ra cụm gây chặn"


def test_dem_dung_hai_loai_ly_do_bi_chan():
    ra = bcp.dung_bao_cao(_ClientGia(scripts=[_script("blocked", [
        _beat(complianceFlag="violated", complianceExcerpt="tốt nhất"),
        _beat(originalityFlag="flagged", flaggedExcerpt="link ở giỏ hàng"),
        _beat(),
    ])]))
    assert "cụm brand tự cấm**: 1" in ra
    assert "trùng câu chữ nguồn**: 1" in ra


def test_cong_2_khong_tu_ket_luan_dat():
    # H2b (chữ có dấu) không quan sát được từ API vì H2c cố ý không lưu chữ.
    # Script tự nhận "ĐẠT" ở đây là bịa bằng chứng.
    ra = bcp.dung_bao_cao(_ClientGia())
    dong_cong_2 = [d for d in ra.splitlines() if "H2b đọc đúng caption" in d]
    assert dong_cong_2, "phải có dòng cổng 2"
    assert "ĐẠT" not in dong_cong_2[0]
    assert "phải xem tay" in dong_cong_2[0]


def test_chay_duoc_voi_du_lieu_day_du():
    ra = bcp.dung_bao_cao(_ClientGia(scripts=[_script("ready", [_beat()])]))
    for muc in ("1. Flow Blueprint", "2. Dấu vân tay", "3. Hồ sơ thương hiệu",
                "4. Kịch bản đã sinh", "5. Hai ca gate", "6. Số liệu chạy thật",
                "7. Bốn cổng mở H4"):
        assert muc in ra, f"thiếu mục: {muc}"

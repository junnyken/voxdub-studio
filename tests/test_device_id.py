"""Mã thiết bị phải ỔN ĐỊNH — mỗi lần đổi là một ví mới.

Lỗ thật, đo được ngày 22/8/2026: trên workspace Linux, `uuid.getnode()` không
tìm được MAC nào nên Python bịa một số ngẫu nhiên MỚI mỗi tiến trình. Hậu quả
đọc thẳng trong cơ sở dữ liệu máy chủ: **25 thiết bị từ đúng một máy**, vài
cái mang 500 Vox dùng thử. Vừa là lỗ cấp phát tiền, vừa làm danh sách máy
hiệu chỉnh không dùng được (thêm vân tay hôm nay, mai chạy lại đã là máy
khác).
"""
from __future__ import annotations

import os

import pytest

from autodub import device_id as di

#: Bit multicast bật = số Python tự bịa. Tắt = MAC thật của card mạng.
NODE_NGAU_NHIEN = 0x010000000000 | 0xD1D93EC90490
NODE_MAC_THAT = 0x00D1D93EC904


@pytest.fixture(autouse=True)
def _tep_rieng(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "TEP_MA_DU_PHONG", str(tmp_path / "ma_may"))
    monkeypatch.setattr(di, "_cached_fingerprint", None)
    yield


def test_co_mac_that_thi_dung_mac(monkeypatch):
    """Máy thường không cần tới tệp — đừng đẻ ra tệp khi không cần."""
    monkeypatch.setattr(di.uuid, "getnode", lambda: NODE_MAC_THAT)
    assert di._machine_guid() == f"mac-{NODE_MAC_THAT:012x}"
    assert not os.path.exists(di.TEP_MA_DU_PHONG)


def test_khong_co_mac_thi_KHONG_dung_so_ngau_nhien(monkeypatch):
    monkeypatch.setattr(di.uuid, "getnode", lambda: NODE_NGAU_NHIEN)
    ma = di._machine_guid()
    assert f"{NODE_NGAU_NHIEN:012x}" not in ma, (
        "dùng thẳng số Python bịa ra là mỗi lần chạy một máy mới")


def test_hai_luot_chay_ra_cung_mot_ma(monkeypatch):
    """Đây là chính cái đã hỏng: ba tiến trình, ba vân tay khác nhau."""
    monkeypatch.setattr(di.uuid, "getnode", lambda: NODE_NGAU_NHIEN)
    lan1 = di._machine_guid()
    # Tiến trình sau: cùng tệp, `uuid.uuid4()` cho số khác hẳn nếu bị gọi lại.
    lan2 = di._machine_guid()
    assert lan1 == lan2


def test_ma_da_co_tren_dia_thi_dung_lai_nguyen_van(monkeypatch):
    with open(di.TEP_MA_DU_PHONG, "w", encoding="utf-8") as f:
        f.write("rand-machuadoi\n")
    monkeypatch.setattr(di.uuid, "getnode", lambda: NODE_NGAU_NHIEN)
    assert di._machine_guid() == "rand-machuadoi"


def test_khong_ghi_duoc_tep_thi_KEU_LEN_chu_khong_im(monkeypatch, caplog):
    """Im lặng ở đây, người dùng thấy là 'tự dưng mất tiền'."""
    monkeypatch.setattr(di.uuid, "getnode", lambda: NODE_NGAU_NHIEN)
    monkeypatch.setattr(di, "TEP_MA_DU_PHONG",
                        os.path.join("/khong-co-thu-muc-nay", "ma"))
    with caplog.at_level("WARNING"):
        ma = di._machine_guid()
    assert ma.startswith("rand-"), "vẫn phải chạy được, chỉ là không bền"
    assert any("máy mới" in r.message for r in caplog.records)


def test_van_tay_on_dinh_qua_nhieu_luot(monkeypatch):
    monkeypatch.setattr(di.uuid, "getnode", lambda: NODE_NGAU_NHIEN)
    lan1 = di.get_fingerprint()
    monkeypatch.setattr(di, "_cached_fingerprint", None)  # như tiến trình mới
    assert di.get_fingerprint() == lan1
    assert len(lan1) == 64

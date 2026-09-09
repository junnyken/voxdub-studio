"""Máy khách hồ sơ brand — mini-spec H1 (docs/PLAN.md, Phase H).

Bốn hàm mỏng trên `SaasClient`, chỉ canh đúng hình dạng lời gọi (method,
đường dẫn, payload) xuống `_request` — hợp đồng HTTP thật đã canh ở phía
`control_server` (`brand-profiles-route.test.js`, 13 test).
"""
from __future__ import annotations

from autodub.saas_client import SaasClient, SaasError


def _client() -> SaasClient:
    return SaasClient(base_url="http://test.local")


def test_list_tra_ve_danh_sach(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_request",
                        lambda method, path, **k: {"data": [{"id": "1"}]})
    assert c.list_brand_profiles() == [{"id": "1"}]


def test_list_loi_mang_thi_tra_rong_khong_nem_loi(monkeypatch):
    """Thiếu danh sách chỉ chặn trang này, không được chặn cả việc khác
    đang chạy — cùng nguyên tắc đã áp dụng cho image_providers()."""
    c = _client()

    def gia_lap(method, path, **k):
        raise SaasError("mất mạng")

    monkeypatch.setattr(c, "_request", gia_lap)
    assert c.list_brand_profiles() == []


def test_create_gui_dung_method_duong_dan_va_rang_buoc_bat_buoc_co_mat(monkeypatch):
    c = _client()
    ghi_nhan = {}

    def gia_lap(method, path, *, json_body=None, timeout=None):
        ghi_nhan["method"] = method
        ghi_nhan["path"] = path
        ghi_nhan["body"] = json_body
        return {"id": "abc", **json_body}

    monkeypatch.setattr(c, "_request", gia_lap)
    c.create_brand_profile("Trà sữa Bình Minh", usp="giao nhanh")

    assert ghi_nhan["method"] == "POST"
    assert ghi_nhan["path"] == "/v1/brand-profiles/"
    assert ghi_nhan["body"]["tenBrand"] == "Trà sữa Bình Minh"
    assert ghi_nhan["body"]["usp"] == "giao nhanh"
    # Constraint 2 của H1: trường này phải LUÔN có mặt (mảng, có thể rỗng)
    # kể cả khi người gọi không truyền gì — không được lặng lẽ vắng mặt.
    assert ghi_nhan["body"]["rangBuocKhongDuocNoi"] == []


def test_update_goi_dung_id_va_ca_5_truong(monkeypatch):
    c = _client()
    ghi_nhan = {}

    def gia_lap(method, path, *, json_body=None, timeout=None):
        ghi_nhan["method"] = method
        ghi_nhan["path"] = path
        return json_body

    monkeypatch.setattr(c, "_request", gia_lap)
    c.update_brand_profile("xyz", ten_brand="Tên mới",
                           rang_buoc_khong_duoc_noi=["không hứa y tế"])

    assert ghi_nhan["method"] == "PUT"
    assert ghi_nhan["path"] == "/v1/brand-profiles/xyz"


def test_delete_goi_dung_id(monkeypatch):
    c = _client()
    ghi_nhan = {}
    monkeypatch.setattr(c, "_request",
                        lambda method, path, **k: ghi_nhan.update(
                            method=method, path=path))
    c.delete_brand_profile("xyz")
    assert ghi_nhan == {"method": "DELETE", "path": "/v1/brand-profiles/xyz"}

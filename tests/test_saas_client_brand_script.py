"""Máy khách BrandScript — mini-spec H3.

Cùng khuôn `test_saas_client_flow_blueprint.py` (H2): chỉ canh hình dạng lời
gọi xuống `_request`. Hợp đồng HTTP thật đã canh ở phía `control_server`
(`brand-scripts-route.test.js`).
"""
from __future__ import annotations

from autodub.saas_client import SaasClient, SaasError


def _client() -> SaasClient:
    return SaasClient(base_url="http://test.local")


def test_list_tra_ve_danh_sach(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_request",
                        lambda method, path, **k: {"data": [{"id": "1"}]})
    assert c.list_brand_scripts() == [{"id": "1"}]


def test_list_loi_mang_thi_tra_rong_khong_nem_loi(monkeypatch):
    # Thiếu danh sách chỉ chặn trang này, không được chặn việc khác đang chạy.
    c = _client()

    def gia_lap(method, path, **k):
        raise SaasError("mất mạng")

    monkeypatch.setattr(c, "_request", gia_lap)
    assert c.list_brand_scripts() == []


def test_get_va_delete_goi_dung_duong_dan(monkeypatch):
    c = _client()
    ghi = []
    monkeypatch.setattr(c, "_request",
                        lambda method, path, **k: ghi.append((method, path)) or {})
    c.get_brand_script("abc")
    c.delete_brand_script("abc")
    assert ghi == [("GET", "/v1/brand-scripts/abc"),
                   ("DELETE", "/v1/brand-scripts/abc")]


def test_create_gui_dung_hai_tham_chieu(monkeypatch):
    c = _client()
    ghi = {}

    def gia_lap(method, path, *, json_body=None, **k):
        ghi.update(method=method, path=path, body=json_body)
        return {"id": "s1", "status": "ready"}

    monkeypatch.setattr(c, "_request", gia_lap)
    monkeypatch.setattr(c, "_note_usage", lambda data: None)
    ket = c.create_brand_script("bp1", "br1", job_id="job-12345678")

    assert ghi["method"] == "POST"
    assert ghi["path"] == "/v1/brand-scripts/"
    assert ghi["body"] == {
        "jobId": "job-12345678",
        "flowBlueprintId": "bp1",
        "brandProfileId": "br1",
    }
    assert ket["status"] == "ready"


def test_create_khong_gui_holdId_khi_khong_co(monkeypatch):
    # Gửi `holdId: None` lên là schema máy chủ chặn ngay — lỗi khó hiểu cho
    # một chuyện đơn giản là "lượt này không có hold".
    c = _client()
    ghi = {}
    monkeypatch.setattr(c, "_request",
                        lambda method, path, *, json_body=None, **k: ghi.update(body=json_body) or {})
    monkeypatch.setattr(c, "_note_usage", lambda data: None)
    c.create_brand_script("bp1", "br1", job_id="job-12345678")
    assert "holdId" not in ghi["body"]

    c.create_brand_script("bp1", "br1", job_id="job-12345678", hold_id="hold-1234")
    assert ghi["body"]["holdId"] == "hold-1234"


def test_regenerate_gui_dung_chi_so_doan(monkeypatch):
    c = _client()
    ghi = {}

    def gia_lap(method, path, *, json_body=None, **k):
        ghi.update(method=method, path=path, body=json_body)
        return {"id": "s1", "status": "blocked"}

    monkeypatch.setattr(c, "_request", gia_lap)
    monkeypatch.setattr(c, "_note_usage", lambda data: None)
    c.regenerate_brand_script_beat("s1", 2, job_id="job-12345678")

    assert ghi["path"] == "/v1/brand-scripts/s1/regenerate-beat"
    assert ghi["body"]["beatIndex"] == 2
    assert isinstance(ghi["body"]["beatIndex"], int)


def test_khong_co_ham_nao_dat_duoc_trang_thai():
    # Guardrail H3: trạng thái CHỈ do máy chủ tính. Một hàm client kiểu
    # `set_status`/`mark_ready` là đủ để vô hiệu hoá toàn bộ lớp kiểm.
    ten_ham = [t for t in dir(SaasClient) if "brand_script" in t]
    assert "set_brand_script_status" not in ten_ham
    for t in ten_ham:
        assert "ready" not in t.lower(), f"hàm đáng ngờ: {t}"
        assert "status" not in t.lower(), f"hàm đáng ngờ: {t}"

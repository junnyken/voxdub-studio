"""Máy khách Flow Blueprint — mini-spec H2 (docs/PLAN.md, Phase H).

Bốn hàm mỏng trên `SaasClient`, cùng khuôn với `test_saas_client_brand_profile.py`
(H1) — chỉ canh đúng hình dạng lời gọi (method, đường dẫn, payload) xuống
`_request`, hợp đồng HTTP thật đã canh ở phía `control_server`
(`flow-blueprints-route.test.js`).
"""
from __future__ import annotations

from autodub.flow_blueprint import BangChungFlowBlueprint
from autodub.saas_client import SaasClient, SaasError


def _client() -> SaasClient:
    return SaasClient(base_url="http://test.local")


def test_list_tra_ve_danh_sach(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "_request",
                        lambda method, path, **k: {"data": [{"id": "1"}]})
    assert c.list_flow_blueprints() == [{"id": "1"}]


def test_list_loi_mang_thi_tra_rong_khong_nem_loi(monkeypatch):
    c = _client()

    def gia_lap(method, path, **k):
        raise SaasError("mất mạng")

    monkeypatch.setattr(c, "_request", gia_lap)
    assert c.list_flow_blueprints() == []


def test_get_goi_dung_id(monkeypatch):
    c = _client()
    ghi_nhan = {}

    def gia_lap(method, path, **k):
        ghi_nhan["method"] = method
        ghi_nhan["path"] = path
        return {"id": "xyz"}

    monkeypatch.setattr(c, "_request", gia_lap)
    data = c.get_flow_blueprint("xyz")
    assert ghi_nhan == {"method": "GET", "path": "/v1/flow-blueprints/xyz"}
    assert data == {"id": "xyz"}


def test_delete_goi_dung_id(monkeypatch):
    c = _client()
    ghi_nhan = {}
    monkeypatch.setattr(c, "_request",
                        lambda method, path, **k: ghi_nhan.update(
                            method=method, path=path))
    c.delete_flow_blueprint("xyz")
    assert ghi_nhan == {"method": "DELETE", "path": "/v1/flow-blueprints/xyz"}


def test_create_gui_dung_duong_dan_va_khong_gui_title(monkeypatch):
    """``title`` là thuộc tính của `BangChungFlowBlueprint` (hiển thị cục
    bộ) nhưng KHÔNG có field tương ứng ở entity server (models/
    FlowBlueprint.js) — payload gửi lên không được có khoá này."""
    c = _client()
    ghi_nhan = {}

    def gia_lap(method, path, *, json_body=None, timeout=None):
        ghi_nhan["method"] = method
        ghi_nhan["path"] = path
        ghi_nhan["body"] = json_body
        return {"id": "abc", "creditCharged": 8, "balanceAfter": 92}

    monkeypatch.setattr(c, "_request", gia_lap)

    bang_chung = BangChungFlowBlueprint(
        source_type="file", source_reference="/tmp/video.mp4",
        title="Video demo", language_source_detected="en",
        sampling_policy_used="0-5s mỗi 0.2s...",
        evidence_summary="ASR: 1 câu. OCR: 1 quan sát.",
        transcript=[{"start_s": 0.0, "end_s": 2.5, "text": "Stop wasting money."}],
        ocr_evidence=[{"start_s": 0.2, "end_s": 1.0, "text": "FLASHSALE", "status": "ok"}],
    )

    data = c.create_flow_blueprint(bang_chung, job_id="job123")

    assert ghi_nhan["method"] == "POST"
    assert ghi_nhan["path"] == "/v1/flow-blueprints/"
    body = ghi_nhan["body"]
    assert "title" not in body
    assert body["jobId"] == "job123"
    assert body["sourceType"] == "file"
    assert body["sourceReference"] == "/tmp/video.mp4"
    assert body["languageSourceDetected"] == "en"
    assert body["transcript"] == bang_chung.transcript
    assert body["ocrEvidence"] == bang_chung.ocr_evidence
    assert "holdId" not in body
    assert data["creditCharged"] == 8


def test_create_gui_hold_id_khi_co(monkeypatch):
    c = _client()
    ghi_nhan = {}

    def gia_lap(method, path, *, json_body=None, timeout=None):
        ghi_nhan["body"] = json_body
        return {"id": "abc", "creditCharged": 0, "balanceAfter": 100}

    monkeypatch.setattr(c, "_request", gia_lap)
    bang_chung = BangChungFlowBlueprint(source_type="url", source_reference="https://x")
    c.create_flow_blueprint(bang_chung, job_id="job123", hold_id="hold1")
    assert ghi_nhan["body"]["holdId"] == "hold1"


def test_create_cap_nhat_so_du_qua_note_usage(monkeypatch):
    """Cùng lượt như `translate`/`product_scene` — phải gọi `_note_usage`
    để thanh Vox đầu app cập nhật, không chỉ trả dữ liệu suông."""
    c = _client()
    monkeypatch.setattr(c, "_request", lambda *a, **k: {
        "id": "abc", "creditCharged": 8, "balanceAfter": 42})
    bang_chung = BangChungFlowBlueprint(source_type="url", source_reference="https://x")
    c.create_flow_blueprint(bang_chung, job_id="job123")
    assert c.device.get("balance") == 42

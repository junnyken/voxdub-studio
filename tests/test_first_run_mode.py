"""Mini-spec V3 (docs/PLAN.md) — màn chào lần đầu phải nói ĐÚNG chế độ hiện
tại (local-only vs có máy chủ), không được báo "đã sẵn sàng — chạy qua máy
chủ" khi không hề có máy chủ nào cấu hình (bug thật tìm thấy khi audit V3,
xem docs/TEST_LOG.md)."""
from __future__ import annotations

from autodub_gui.first_run import mode_banner_text, translate_mode_check
from autodub.config import Settings


def test_translate_check_not_ready_when_no_server(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    name, description, command, probe = translate_mode_check()
    assert probe(Settings()) is False
    assert "dịch tay" in description.lower() or "dịch TAY" in description


def test_translate_check_ready_when_server_configured_and_enabled(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    name, description, command, probe = translate_mode_check()
    settings = Settings()
    settings.translate_enabled = True
    assert probe(settings) is True


def test_translate_check_not_ready_when_configured_but_disabled_in_settings(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    name, description, command, probe = translate_mode_check()
    settings = Settings()
    settings.translate_enabled = False
    assert probe(settings) is False


def test_mode_banner_reflects_local_only(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    text = mode_banner_text()
    assert "local" in text.lower() or "trên máy" in text
    assert "không tốn phí" in text


def test_mode_banner_reflects_server_configured(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    text = mode_banner_text()
    assert "máy chủ" in text
    assert "Vox" in text


def test_mode_banner_discloses_telemetry_when_server_configured(monkeypatch):
    """Guardrail 1 của mini-spec V13 (docs/PLAN.md) — banner PHẢI nói rõ
    việc gửi trạng thái tiến trình TRƯỚC KHI tính năng gửi bất kỳ event
    nào. Đây là gate KHÔNG được bỏ qua — test này khoá lại nội dung thật,
    không chỉ tin code đã sửa đúng."""
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    text = mode_banner_text()
    assert "trạng thái" in text.lower() and "tiến trình" in text.lower()
    assert "không bao giờ gửi nội dung" in text.lower() or \
        "không bao giờ gửi" in text.lower()


def test_mode_banner_local_only_explicitly_states_nothing_sent(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    text = mode_banner_text()
    assert "không gửi" in text.lower()

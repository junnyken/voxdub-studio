"""V65 — máy chủ tắt xử lý trên cloud thì ô chọn phải ẩn HẲN.

Audit V50 phát hiện không có worker render nào tồn tại. Bản cũ vẫn hiện ô chọn
bị khoá kèm chữ "Máy chủ đang tạm tắt xử lý trên cloud" — hứa một tính năng sẽ
quay lại, mà nó thì không.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages.new_project_steps import RecognizeStep  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_an_han_khi_may_chu_tat():
    step = RecognizeStep()
    step.set_cloud_render_info(True, enabled_on_server=False, cost_vox=50)

    assert step.cloud_render.isHidden(), "máy chủ tắt thì phải ẩn, không phải khoá"
    assert step._cloud_price.isHidden(), "dòng giá cũng phải biến mất theo"


def test_van_hien_khi_may_chu_bat():
    step = RecognizeStep()
    step.set_cloud_render_info(True, enabled_on_server=True, cost_vox=50)

    assert not step.cloud_render.isHidden()
    assert step.cloud_render.isEnabled(), "hiện thì phải bấm được"
    assert "50" in step._cloud_price.text(), "phải nói rõ giá trước khi bấm"


def test_an_roi_thi_luot_chay_khong_gui_cloud_du_o_van_con_tick():
    """Ca nguy hiểm nhất: nháp cũ đã tick, máy chủ vừa tắt tính năng.

    Ẩn mà giá trị vẫn lọt ra thì khách bị trừ tiền cho một job không ai xử lý —
    đúng thứ V50 phát hiện.
    """
    step = RecognizeStep()
    step.set_cloud_render_info(True, enabled_on_server=True, cost_vox=50)
    step.cloud_render.setChecked(True)
    assert step.values()["cloud_render"] is True

    step.set_cloud_render_info(True, enabled_on_server=False, cost_vox=50)
    assert step.values()["cloud_render"] is False, "ẩn rồi thì không được gửi nữa"


def test_nap_lai_nhap_cu_khong_bat_lai_duoc_khi_da_an():
    step = RecognizeStep()
    step.set_cloud_render_info(True, enabled_on_server=False, cost_vox=50)
    step.load({"cloud_render": True})

    assert step.values()["cloud_render"] is False

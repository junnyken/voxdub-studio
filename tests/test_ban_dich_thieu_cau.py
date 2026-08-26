"""Bản dịch thiếu câu phải DỪNG, không được lặng lẽ xuất video thiếu nội dung.

Lỗi thật, chủ dự án báo sau lượt chạy đầu (26/08/2026): *"thật chất nó rất
nhiều câu nhưng bạn lại dịch rất ít nên nó bị thiếu"*.

Cơ chế: `_load_translation()` so số câu của bản dịch với bản gốc, thấy lệch
thì ghi MỘT dòng cảnh báo rồi **dùng luôn tệp thiếu**. Cảnh báo trôi trong
nhật ký, video xuất ra mất hẳn phần lời thoại không có bản dịch, và không có
gì chặn lại.

Hay gặp nhất ở đường dịch tay: người dùng nhờ một AI khác dịch, mô hình đó tự
gộp dòng cho gọn nên trả về ít câu hơn hẳn.
"""
from __future__ import annotations

import json

import pytest

from autodub.config import Settings
from autodub.languages import get_target
from autodub.pipeline import DubPipeline


def _goc(n: int) -> list[dict]:
    return [{"id": i, "start": float(i), "end": i + 0.9, "duration": 0.9,
             "text": f"line {i}"} for i in range(n)]


def _ghi(tmp_path, segs) -> str:
    p = tmp_path / "transcript_dub.json"
    p.write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")
    return str(p)


@pytest.fixture
def pipeline():
    return DubPipeline(Settings())


def _dich(segs, field):
    ra = []
    for s in segs:
        x = dict(s)
        x[field] = "bản dịch"
        ra.append(x)
    return ra


def test_thieu_cau_thi_dung_han(pipeline, tmp_path):
    target = get_target("vi")
    goc = _goc(100)
    duong = _ghi(tmp_path, _dich(goc[:40], target.text_field))
    with pytest.raises(ValueError) as e:
        pipeline._load_translation(duong, goc, target)
    loi = str(e.value)
    assert "40" in loi and "100" in loi, "không nói rõ thiếu bao nhiêu"
    assert "thiếu 60" in loi


def test_loi_noi_ro_phai_lam_gi(pipeline, tmp_path):
    """Báo lỗi mà không nói cách chữa thì người dùng vẫn kẹt."""
    target = get_target("vi")
    goc = _goc(10)
    duong = _ghi(tmp_path, _dich(goc[:3], target.text_field))
    with pytest.raises(ValueError) as e:
        pipeline._load_translation(duong, goc, target)
    loi = str(e.value)
    assert "bổ sung" in loi and "xoá tệp" in loi
    assert "gộp dòng" in loi, "không nhắc nguyên nhân hay gặp nhất"


def test_du_cau_thi_chay_binh_thuong(pipeline, tmp_path):
    target = get_target("vi")
    goc = _goc(20)
    duong = _ghi(tmp_path, _dich(goc, target.text_field))
    ra = pipeline._load_translation(duong, goc, target)
    assert len(ra) == 20


def test_thua_cau_van_chay_chi_canh_bao(pipeline, tmp_path, caplog):
    """Tách một câu dài thành hai là sửa tay hợp lệ — không được chặn."""
    import logging

    target = get_target("vi")
    goc = _goc(5)
    them = dict(goc[-1])
    them["id"] = 99
    with caplog.at_level(logging.WARNING):
        ra = pipeline._load_translation(
            _ghi(tmp_path, _dich(goc + [them], target.text_field)), goc, target)
    assert len(ra) == 6

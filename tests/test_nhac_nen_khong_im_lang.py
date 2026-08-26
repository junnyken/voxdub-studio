"""Chọn nhạc nền mà không có nhạc thì phải NÓI, không được im lặng.

Lỗi thật, chủ dự án báo sau lượt chạy đầu (26/08/2026): *"nó không chọn nhạc
nên khi nó xuất ra video thì chỉ có lời thoại chứ không có nhạc nền gì hết"*.

Họ chọn "Nhạc nền AI (ElevenLabs)" ở bước 2. Nhưng nhạc AI được SINH Ở TRÌNH
CHỈNH SỬA, tức chỉ có sau khi đã chạy xong một lượt — nên ở lượt đầu tệp
`data/ai_music.wav` chưa tồn tại. Và `_resolve_background()` chỉ xử lý
`demucs` với `duck`; mọi giá trị khác rơi thẳng xuống nhánh cuối, ghi nhật ký
"STEP 2.5 skipped: --bg-mode=none" — một câu SAI, vì người dùng không hề chọn
"none". Video ra trống nhạc, không một lời cảnh báo nào bằng tiếng Việt.
"""
from __future__ import annotations

import ast
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def than_resolve() -> str:
    nguon = open(os.path.join(REPO, "autodub", "pipeline.py"),
                 encoding="utf-8").read()
    for nut in ast.walk(ast.parse(nguon)):
        if isinstance(nut, ast.FunctionDef) and nut.name == "_resolve_background":
            return ast.get_source_segment(nguon, nut) or ""
    raise AssertionError("pipeline.py không còn _resolve_background")


def test_nhac_ai_duoc_xu_ly_rieng(than_resolve):
    assert '"ai_music"' in than_resolve, (
        "chế độ nhạc AI không được xử lý — rơi vào nhánh 'không có nhạc' và "
        "nhật ký ghi sai tên chế độ")


def test_chua_co_nhac_ai_thi_bao_ro_bang_tieng_viet(than_resolve):
    i = than_resolve.index('"ai_music"')
    sau = than_resolve[i:]
    assert "logger.warning" in sau, "thiếu nhạc AI mà không cảnh báo gì"
    assert "Trình chỉnh sửa" in sau, (
        "không chỉ cho người dùng biết sinh nhạc AI ở đâu")
    assert "nhạc nền" in sau.lower()


def test_da_co_nhac_ai_thi_dung_lai(than_resolve):
    """Chạy lại sau khi đã sinh nhạc thì phải dùng, không bỏ phí."""
    assert "ai_music.wav" in than_resolve
    assert "os.path.exists(ai_music)" in than_resolve


def test_che_do_la_khong_bi_coi_nhu_none_trong_im_lang(than_resolve):
    """Nhật ký ghi 'bg-mode=none' khi người dùng chọn thứ khác là nói dối."""
    assert 'bg_mode != "none"' in than_resolve, (
        "chế độ lạ vẫn bị âm thầm coi như 'none'")


def test_nhan_giao_dien_noi_ro_phai_sinh_truoc():
    nguon = open(os.path.join(REPO, "autodub_gui", "dub_constants.py"),
                 encoding="utf-8").read()
    i = nguon.index('"ai_music"')
    dong = nguon[nguon.rindex("(", 0, i):i]
    assert "Trình chỉnh sửa" in dong, (
        "nhãn hứa nhạc AI mà không nói phải sinh trước — lượt đầu chắc chắn "
        "không có nhạc")

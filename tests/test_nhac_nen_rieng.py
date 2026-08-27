"""Nhạc nền do người dùng tự chọn (C42).

Chủ dự án nhìn thanh thời gian rồi hỏi (27/08/2026): *"ở đây tôi muốn kéo
thêm âm thanh này kia vô được không"*. Lúc đó câu trả lời là KHÔNG — ba nguồn
nhạc nền duy nhất là giữ nhạc gốc (Demucs), giảm nhỏ tiếng gốc, và nhạc AI.
Muốn ghép nhạc của mình thì phải xuất video rồi làm ở phần mềm khác.

Học từ ElevenLabs Dubbing Studio (có «Upload Audio» cho track nhạc/nền không
có tiếng nói), nhưng KHÔNG bê nguyên cách làm: dựng hẳn lớp âm thanh đặt tự
do trên thanh thời gian là việc lớn hơn nhiều. Bước trộn nhạc nền của VoxDub
vốn đã nhận một tệp bất kỳ rồi tự đệm/cắt cho khớp độ dài — nên chỉ cần
chuyển tệp người dùng thành WAV chuẩn trong thư mục dự án và thêm một chế độ
trỏ vào đó.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import wave

import pytest

from autodub.media.nhac_nen_rieng import (DUOI_NHAN, LoiNhacNen, dat_nhac_nen,
                                          duong_nhac_nen, xoa_nhac_nen)

can_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg")


@pytest.fixture
def nhac(tmp_path):
    duong = tmp_path / "nhac.mp3"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
         "sine=frequency=220:duration=4", "-c:a", "libmp3lame", str(duong), "-y"],
        check=True)
    return str(duong)


@can_ffmpeg
def test_dat_va_tra_ve_wav_chuan(tmp_path, nhac):
    """Chuyển sang WAV chứ không dùng thẳng tệp gốc: bước trộn chạy lại mỗi
    lần xuất, và tệp gốc có thể bị xoá/đổi chỗ giữa hai lần."""
    duan = str(tmp_path / "duan")
    ra = dat_nhac_nen(duan, nhac)
    assert os.path.isfile(ra) and ra.endswith(".wav")
    with wave.open(ra) as f:
        assert f.getframerate() == 44100, "không khớp đường nhạc nền chất lượng cao"
        assert f.getnchannels() == 2
        assert f.getnframes() > 0


@can_ffmpeg
def test_tra_lai_duong_dan_da_dat(tmp_path, nhac):
    duan = str(tmp_path / "duan")
    assert duong_nhac_nen(duan) == ""
    dat_nhac_nen(duan, nhac)
    assert duong_nhac_nen(duan).endswith("nhac_nen_rieng.wav")


@can_ffmpeg
def test_chon_tep_khac_thi_de_len(tmp_path, nhac):
    """Chọn tệp khác nghĩa là đổi ý — không để lại hai bản gây khó hiểu."""
    duan = str(tmp_path / "duan")
    dat_nhac_nen(duan, nhac)
    khac = tmp_path / "khac.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=880:duration=1", str(khac), "-y"], check=True)
    dat_nhac_nen(duan, str(khac))
    with wave.open(duong_nhac_nen(duan)) as f:
        assert f.getnframes() / f.getframerate() < 2, "vẫn là tệp cũ"


def test_tep_khong_ton_tai_bao_ro(tmp_path):
    with pytest.raises(LoiNhacNen, match="Không thấy tệp"):
        dat_nhac_nen(str(tmp_path / "duan"), str(tmp_path / "khong-co.mp3"))


def test_duoi_la_bao_ro_ten_duoc_nhan(tmp_path):
    """Câu lỗi phải nói ra đuôi nào dùng được, không để người dùng đoán."""
    xau = tmp_path / "x.txt"
    xau.write_text("x", encoding="utf-8")
    with pytest.raises(LoiNhacNen) as e:
        dat_nhac_nen(str(tmp_path / "duan"), str(xau))
    assert ".mp3" in str(e.value) and ".wav" in str(e.value)


@can_ffmpeg
def test_xoa_duoc(tmp_path, nhac):
    duan = str(tmp_path / "duan")
    assert xoa_nhac_nen(duan) is False, "chưa có gì mà báo đã xoá"
    dat_nhac_nen(duan, nhac)
    assert xoa_nhac_nen(duan) is True
    assert duong_nhac_nen(duan) == ""


# --- Nối vào hai đường xuất video ---------------------------------------

def _than(tep: str, ten_ham: str) -> str:
    import ast

    nguon = open(tep, encoding="utf-8").read()
    for nut in ast.walk(ast.parse(nguon)):
        if isinstance(nut, ast.FunctionDef) and nut.name == ten_ham:
            return ast.get_source_segment(nguon, nut) or ""
    raise AssertionError(f"{tep} không còn {ten_ham}")


def test_luot_chay_dau_hieu_che_do_moi():
    than = _than("autodub/pipeline.py", "_resolve_background")
    assert '"tep_rieng"' in than, "lượt chạy đầu không hiểu chế độ nhạc riêng"
    i = than.index('"tep_rieng"')
    assert "logger.warning" in than[i:i + 1200], (
        "chọn chế độ mà chưa có tệp thì im lặng — đúng lỗi nhạc AI đã mắc")


def test_xuat_lai_tu_trinh_chinh_sua_cung_hieu():
    than = _than("autodub/editor.py", "resolve_existing_background")
    assert '"tep_rieng"' in than, (
        "xuất lại từ Trình chỉnh sửa không hiểu chế độ này — nhạc biến mất ở "
        "lần xuất thứ hai")


def test_giao_dien_co_lua_chon_va_nut():
    consts = open("autodub_gui/dub_constants.py", encoding="utf-8").read()
    assert '"tep_rieng"' in consts, "không có lựa chọn trong ô Cách xử lý"
    panel = open("autodub_gui/pages/editor_panels.py", encoding="utf-8").read()
    assert "chon_nhac_requested" in panel
    trang = open("autodub_gui/pages/editor_page.py", encoding="utf-8").read()
    assert "chon_nhac_requested.connect" in trang, "nút không nối vào việc gì"


def test_nut_khong_nam_trong_panel_can_may_chu():
    """`MusicSfxPanel` bị ẩn hoàn toàn khi chưa cấu hình máy chủ (nhạc AI cần
    máy chủ). Chọn tệp trên máy thì không cần gì — đặt nhầm chỗ là người chạy
    ngoại tuyến không bao giờ thấy nút."""
    panel = open("autodub_gui/pages/editor_panels.py", encoding="utf-8").read()
    i_bg = panel.index("class BackgroundPanel")
    i_music = panel.index("class MusicSfxPanel")
    i_nut = panel.index("chon_nhac_requested")
    assert i_bg < i_nut < i_music, (
        "nút chọn tệp nhạc nằm ngoài BackgroundPanel")

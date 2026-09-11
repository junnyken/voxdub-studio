"""Hợp đồng thời lượng của video dựng từ storyboard — mini-spec H4c-1.

Lỗi thật, đo bằng ffmpeg ngày 11/09/2026: ba ảnh [2,0; 1,0; 3,0] với chuyển
cảnh 0,3 giây dựng ra video **5,40 giây** trong khi transcript ghi dòng thời
gian kết thúc ở **6,00 giây**.

**Nguyên nhân gốc** — không phải rounding, không phải trừ hai lần, không phải
mất ảnh cuối: `xfade` CHỒNG hai cảnh lên nhau nên mỗi lần chuyển ăn mất đúng
`giay_chuyen` giây, và **không có gì bù lại**. Thiếu hụt bằng
`giay_chuyen × (n-1)`, nhưng tệ hơn con số đó: nó **cộng dồn**, nên đoạn thứ
i đổi hình sớm `giay_chuyen × i` giây so với lời đọc của nó. Người dùng nghe
thử thấy "hơi lệch" ở giữa rồi lệch hẳn ở cuối.

Vì sao phải có tệp test riêng: toàn bộ H4c trước đây tiêm một hàm ghép giả
ghi 9 byte `b"video gia"` làm "video", nên **chưa lượt test nào chạy ffmpeg
thật**. Một dự án mở được trong Trình chỉnh sửa không chứng minh được nó có
video dài đúng bao nhiêu.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from autodub.du_an_tu_kich_ban import (
    LECH_THOI_LUONG_TOI_DA_S, VideoLechThoiLuong, dung_du_an,
)
from autodub.product_video import _lenh_ghep

co_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="cần ffmpeg + ffprobe thật")


def _anh_that(thu_muc, so: int) -> list[str]:
    """Ảnh PNG THẬT do ffmpeg vẽ — không phải tệp giả vài byte."""
    ra = []
    for i in range(so):
        p = str(thu_muc / f"anh{i}.png")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"color=c=0x{(i * 37) % 256:02x}3050:s=320x180:d=1",
             "-frames:v", "1", p], check=True, capture_output=True)
        ra.append(p)
    return ra


def _do(duong: str) -> float:
    ra = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", duong], capture_output=True, text=True, check=True)
    return float(ra.stdout.strip())


# ------------------------------------------- hợp đồng thời lượng THẬT ------

@co_ffmpeg
@pytest.mark.parametrize("giay", [
    [2.0, 1.0, 3.0],          # ca gốc của lỗi
    [1.0, 1.0, 1.0, 1.0, 1.0],
    [4.0, 4.0],
    [3.0],                     # một ảnh: không có chuyển cảnh nào
    [8.4, 5.2, 11.9, 3.1, 6.6],
])
def test_video_dung_ra_dai_DUNG_bang_tong_thoi_luong(tmp_path, giay):
    anh = _anh_that(tmp_path, len(giay))
    ra = str(tmp_path / "ra.mp4")
    p = subprocess.run(_lenh_ghep(anh, ra, giay, 0.3), capture_output=True,
                       text=True)
    assert p.returncode == 0, p.stderr[-400:]
    lech = abs(_do(ra) - sum(giay))
    assert lech <= LECH_THOI_LUONG_TOI_DA_S, (
        f"video dài {_do(ra):.2f}s, dòng thời gian {sum(giay):.2f}s — "
        f"lệch {lech:.3f}s, hình sẽ trôi dần so với tiếng")


@co_ffmpeg
def test_LECH_KHONG_tang_theo_so_doan(tmp_path):
    """Chốt quan trọng nhất: sai lệch phải là hằng số, không cộng dồn.

    Lỗi cũ lệch `0,3 × (n-1)` nên video càng nhiều đoạn càng sai. Nếu bản vá
    chỉ bù một phần thì test độ dài đơn lẻ vẫn qua mà vấn đề thật còn nguyên.
    """
    lech_theo_n = {}
    for n in (2, 5, 9):
        giay = [1.5] * n
        anh = _anh_that(tmp_path, n)
        ra = str(tmp_path / f"ra{n}.mp4")
        subprocess.run(_lenh_ghep(anh, ra, giay, 0.3), check=True,
                       capture_output=True)
        lech_theo_n[n] = abs(_do(ra) - sum(giay))

    assert max(lech_theo_n.values()) <= LECH_THOI_LUONG_TOI_DA_S, lech_theo_n
    # 9 đoạn không được lệch hơn 2 đoạn quá một khung hình.
    assert lech_theo_n[9] - lech_theo_n[2] <= 1 / 30 + 1e-6, (
        f"sai lệch còn cộng dồn theo số đoạn: {lech_theo_n}")


@co_ffmpeg
def test_cat_thang_cung_phai_dung_thoi_luong(tmp_path):
    giay = [2.0, 1.0, 3.0]
    anh = _anh_that(tmp_path, 3)
    ra = str(tmp_path / "ra.mp4")
    subprocess.run(_lenh_ghep(anh, ra, giay, 0.3, "khong"), check=True,
                   capture_output=True)
    assert abs(_do(ra) - sum(giay)) <= LECH_THOI_LUONG_TOI_DA_S


# ------------------------------------------------------- cổng cứng --------

def _kich_ban(so_doan: int = 3) -> dict:
    return {
        "id": "s1", "status": "ready",
        "beats": [{
            "beatType": "hook",
            "voiceoverTextVi": f"Câu số {i} nói vừa đủ dài để đo thời lượng.",
            "captionSuggestionVi": f"Chữ {i}",
            "visualBriefVi": "Cận cảnh",
        } for i in range(so_doan)],
    }


def test_video_lech_qua_nguong_thi_NEM_LOI_khong_dung_tiep(tmp_path):
    """Dựng tiếp một dự án lệch nghĩa là đặt mọi bước sau lên dòng thời gian
    sai — và người dùng chỉ phát hiện ở bước nghe thử."""
    anh = [str(tmp_path / f"a{i}.png") for i in range(3)]
    for a in anh:
        open(a, "wb").write(b"x")

    def _ghep_gia(duong_anh, duong_ra, **kw):
        open(duong_ra, "wb").write(b"video gia")

    with pytest.raises(VideoLechThoiLuong, match="lệch"):
        dung_du_an(_kich_ban(), anh, str(tmp_path / "duan"),
                   ghep_video=_ghep_gia,
                   # Video ngắn hơn 1,2 giây — đúng kiểu sai lệch của lỗi cũ.
                   do_thoi_luong=lambda _p: 1.0)


def test_khong_do_duoc_thoi_luong_cung_la_CHAN(tmp_path):
    """Không đo được KHÁC "đo xong thấy ổn". Bỏ qua phép đối chiếu thì lỗi
    quay lại y như cũ mà không ai biết."""
    anh = [str(tmp_path / f"a{i}.png") for i in range(3)]
    for a in anh:
        open(a, "wb").write(b"x")

    with pytest.raises(VideoLechThoiLuong, match="Không đọc được"):
        dung_du_an(_kich_ban(), anh, str(tmp_path / "duan"),
                   ghep_video=lambda p, r, **k: open(r, "wb").write(b"x"),
                   do_thoi_luong=lambda _p: None)


def test_dung_thoi_luong_thi_di_tiep_binh_thuong(tmp_path):
    anh = [str(tmp_path / f"a{i}.png") for i in range(3)]
    for a in anh:
        open(a, "wb").write(b"x")
    work = str(tmp_path / "duan")

    board_giay = {}

    def _ghep_gia(duong_anh, duong_ra, *, giay_moi_anh, **kw):
        board_giay["tong"] = sum(giay_moi_anh)
        open(duong_ra, "wb").write(b"video gia")

    ket = dung_du_an(_kich_ban(), anh, work, ghep_video=_ghep_gia,
                     do_thoi_luong=lambda _p: board_giay["tong"])
    assert os.path.isfile(ket.duong_transcript)


def test_nguong_lech_la_con_so_DO_DUOC_khong_phai_chon_bua():
    """2 khung ở 30fps. Đo thật cho lệch tối đa 1 khung và không tăng theo số
    ảnh, nên ngưỡng là hằng số chứ không nhân theo độ dài video."""
    assert LECH_THOI_LUONG_TOI_DA_S == pytest.approx(2 / 30)
    # Phải nhỏ hơn hẳn sai lệch CŨ của một video chỉ 3 đoạn (0,3 × 2 = 0,6s).
    assert LECH_THOI_LUONG_TOI_DA_S < 0.6 / 5


# --------------------------------------------- đường đi THẬT, đầu tới cuối -

@co_ffmpeg
def test_dung_du_an_bang_ffmpeg_THAT_va_do_lai(tmp_path):
    """Không tiêm hàm ghép giả, không tiêm phép đo: chạy y như người dùng.

    Đây là lượt duy nhất trong bộ test đi qua ffmpeg thật của H4c — chỗ mà
    lỗi thời lượng đã trốn suốt vì mọi test khác đều ghi 9 byte làm "video".
    """
    anh = _anh_that(tmp_path, 3)
    work = str(tmp_path / "duan")
    ket = dung_du_an(_kich_ban(3), anh, work)

    assert os.path.isfile(ket.duong_video)
    tong = sum(d.giay for d in ket.storyboard.doan)
    assert abs(_do(ket.duong_video) - tong) <= LECH_THOI_LUONG_TOI_DA_S

    # Và video phải mở được thật, không phải một tệp rỗng đúng tên.
    assert os.path.getsize(ket.duong_video) > 10_000

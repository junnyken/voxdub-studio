"""C55 — cổng kiểm trước phát hành phải đi tới TẬN video xuất ra.

Chặng 1 (C45) dừng ở bước dịch. Nghĩa là hai thứ chính LÀ sản phẩm — giọng đọc
và video ghép xong — chưa từng được chạy thử trước khi phát hành. Một bản có
thể ship với VieNeu hỏng hoặc video ra CÂM mà cổng kiểm, smoke test và mọi mã
thoát đều xanh.

Ca đáng sợ nhất là video câm: ffmpeg ghép một luồng tiếng toàn số 0 vẫn trả mã
thoát 0, mọi bước đều báo "done", chỉ người dùng mở ra nghe mới biết.

Nên ở đây **canh chính bộ canh** (đúng bài học V90): dựng thật hai video —
một câm, một có tiếng — rồi bắt bộ đo phân biệt được. Bộ đo không phân biệt
được thì chặng 2 chỉ là trang trí.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

can_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="cần ffmpeg/ffprobe để dựng video thử")


@pytest.fixture(scope="module")
def cong():
    duong_dan = os.path.join(GOC, "scripts", "kiem_chay_that.py")
    spec = importlib.util.spec_from_file_location("kiem_chay_that_c55", duong_dan)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dung_video(dich: str, co_tieng: bool) -> str:
    """Video 2 giây: `co_tieng=False` cho luồng tiếng IM LẶNG (không phải
    thiếu luồng — đó là ca khác, dễ bắt hơn nhiều)."""
    am = "sine=frequency=440:sample_rate=44100" if co_tieng else "anullsrc=r=44100:cl=mono"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10",
         "-f", "lavfi", "-i", am,
         "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", dich],
        check=True, capture_output=True, timeout=120)
    return dich


# ------------------------------------------------- đo mức âm ---

@can_ffmpeg
def test_video_cam_bi_bat(cong, tmp_path):
    v = _dung_video(str(tmp_path / "cam.mp4"), co_tieng=False)
    muc = cong._muc_am_trung_binh(cong.Path(v))
    assert muc is not None, "không đo được mức âm — bộ đo vô dụng"
    assert muc <= -70, f"video CÂM mà đo ra {muc} dB — ngưỡng không bắt được"


@can_ffmpeg
def test_video_co_tieng_khong_bi_bao_nham(cong, tmp_path):
    """Bộ canh hay kêu nhầm thì người ta tắt đi — còn tệ hơn không có (V90)."""
    v = _dung_video(str(tmp_path / "co_tieng.mp4"), co_tieng=True)
    muc = cong._muc_am_trung_binh(cong.Path(v))
    assert muc is not None and muc > -70, f"video CÓ tiếng mà đo ra {muc} dB"


@can_ffmpeg
def test_do_duoc_thoi_luong(cong, tmp_path):
    v = _dung_video(str(tmp_path / "hai_giay.mp4"), co_tieng=True)
    assert 1.5 <= cong._thoi_luong(cong.Path(v)) <= 2.5


def test_khong_do_duoc_thi_noi_khong_do_duoc(cong, tmp_path):
    """Tệp không phải video: phải trả None để nơi gọi báo hỏng, KHÔNG được trả
    một con số trông như đã đo."""
    rac = tmp_path / "rac.mp4"
    rac.write_text("đây không phải video", encoding="utf-8")
    assert cong._muc_am_trung_binh(cong.Path(str(rac))) is None
    assert cong._thoi_luong(cong.Path(str(rac))) == 0.0


# --------------------------------------- hợp đồng bản dịch tay ---

def test_ban_dich_tay_giu_nguyen_moc_thoi_gian(cong, tmp_path):
    """`pipeline._load_translation` từ chối bản dịch thiếu start/end/duration —
    và nó từ chối SAU khi TTS đã chạy tốn công. Bộ canh phải ghi đúng hợp đồng
    ngay từ đầu, không thì chặng 2 hỏng vì chính nó chứ không phải vì sản phẩm.
    """
    work = tmp_path / "duan"
    (work / "data").mkdir(parents=True)
    cau = [{"id": 1, "start": 0.0, "end": 1.5, "duration": 1.5, "text": "hello"},
           {"id": 2, "start": 1.5, "end": 3.0, "duration": 1.5, "text": "world"}]

    dich = cong._viet_ban_dich_tay(work, cau)

    import json
    ra = json.loads(dich.read_text(encoding="utf-8"))
    assert len(ra) == 2
    for s in ra:
        for truong in ("start", "end", "duration"):
            assert isinstance(s.get(truong), (int, float)), f"mất {truong}"
        assert s.get("text_vi", "").strip(), "thiếu text_vi"


def test_cau_dich_tay_la_tieng_viet_that(cong):
    """VieNeu đọc tiếng Việt. Nhét chuỗi rác vào là đang kiểm một ca không ai
    gặp, và giọng đọc hỏng thật vẫn có thể lọt."""
    assert cong.CAU_DICH_TAY, "không có câu mẫu nào"
    for c in cong.CAU_DICH_TAY:
        assert len(c) > 20
        assert any(k in c.lower() for k in "ăâêôơưđáàảãạ"), (
            f"câu mẫu {c!r} không có dấu tiếng Việt")


# -------------------------------------------- cổng phải được dùng ---

def test_release_workflow_co_chay_chang_hai():
    """Viết ra một cổng kiểm mà không cắm vào quy trình phát hành thì nó chỉ là
    một tệp nằm im — đúng lớp lỗi 'công cụ có mà không ai chạy' của V90."""
    wf = open(os.path.join(GOC, ".github", "workflows", "release.yml"),
              encoding="utf-8").read()
    assert "--den-cuoi" in wf, (
        "release.yml chưa chạy chặng 2 — giọng đọc và video xuất ra vẫn "
        "không được kiểm trước khi phát hành")
    assert "setup_vieneu.py" in wf, (
        "release.yml chạy --den-cuoi nhưng không cài VieNeu — chặng 2 sẽ hỏng "
        "vì thiếu engine, không phải vì sản phẩm hỏng")


# --------------------------------------- nhánh HỎNG phải bị bắt ---

def test_khong_ra_video_thi_chan_phat_hanh(cong, tmp_path, monkeypatch):
    """Lượt chạy tiếp không xuất được video = KHÔNG phát hành. Trước C55 ca này
    không ai bắt: chặng 1 xong là cổng kiểm xanh."""
    work = tmp_path / "duan"
    (work / "data").mkdir(parents=True)
    (work / "data" / "transcript_original.json").write_text(
        '[{"id":1,"start":0.0,"end":1.0,"duration":1.0,"text":"hi"}]',
        encoding="utf-8")

    class _KetQuaGia:
        returncode, stdout, stderr = 1, "", "TTS chết giữa chừng"

    monkeypatch.setattr(cong, "_chay_tiep", lambda *a, **k: _KetQuaGia())
    with pytest.raises(cong.Hong, match="Không có dubbed_video.mp4"):
        cong._kiem_chang_hai(cong.Path("x.mp4"), work, "python3", 60)


@can_ffmpeg
def test_video_ra_cam_thi_chan_phat_hanh(cong, tmp_path, monkeypatch):
    """Ca đắt nhất: video ra ĐỦ mọi thứ, mã thoát 0, chỉ mỗi việc là câm."""
    work = tmp_path / "duan"
    (work / "data").mkdir(parents=True)
    (work / "data" / "transcript_original.json").write_text(
        '[{"id":1,"start":0.0,"end":1.0,"duration":1.0,"text":"hi"}]',
        encoding="utf-8")
    _dung_video(str(work / "dubbed_video.mp4"), co_tieng=False)

    class _KetQuaGia:
        returncode, stdout, stderr = 0, "done", ""

    monkeypatch.setattr(cong, "_chay_tiep", lambda *a, **k: _KetQuaGia())
    with pytest.raises(cong.Hong, match="CÂM"):
        cong._kiem_chang_hai(cong.Path(str(work / "dubbed_video.mp4")), work,
                             "python3", 60)

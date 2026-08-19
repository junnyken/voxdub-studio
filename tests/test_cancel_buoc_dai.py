"""V79 — nút Dừng cắt ngang được cả các bước DÀI NHẤT của lượt chạy.

Sau V76 (canh chữ karaoke), rà tiếp thì thấy `rep.check_cancelled()` chỉ nằm
GIỮA các bước: bấm Dừng lúc đang tách nhạc nền (Demucs, 10+ phút), đang xuất
video (ffmpeg re-encode), đang dịch máy hay đang đồng bộ khẩu hình thì máy vẫn
cày tới khi bước đó tự xong.

Cái bẫy riêng của nhóm này (khác V76): giết tiến trình con làm bước đó "hỏng"
theo đủ kiểu, mà mỗi bước lại có sẵn một đường DỰ PHÒNG âm thầm — Demucs hỏng
thì video ra KHÔNG CÓ NHẠC NỀN, dịch máy hỏng thì rơi sang "dịch tay". Nên cú
bấm Dừng phải trông ra cú bấm Dừng ở mọi tầng.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time

import pytest

from autodub.cancel_guard import bat_dau_canh, giet_khi_dung, kiem_dung
from autodub.progress import PipelineCancelled


_POPEN_THAT = subprocess.Popen


def _tien_trinh_lau(giay=30):
    # Giữ tham chiếu THẬT: test bên dưới monkeypatch subprocess.Popen, gọi
    # lại qua tên đã bị patch là tự đệ quy vô hạn.
    return _POPEN_THAT([sys.executable, "-c", f"import time;time.sleep({giay})"])


# -- 1. Bộ canh dùng chung ---------------------------------------------------

def test_giet_tien_trinh_khi_bam_dung():
    proc = _tien_trinh_lau()
    huy = threading.Event()
    threading.Timer(0.5, huy.set).start()

    t0 = time.monotonic()
    with pytest.raises(PipelineCancelled):
        with giet_khi_dung(proc, huy):
            proc.communicate(timeout=30)
    assert time.monotonic() - t0 < 10, "phải chết ngay, không đợi hết 30s"
    assert proc.poll() is not None, "tiến trình con phải bị giết"


def test_loi_sau_khi_bam_dung_duoc_doi_thanh_da_dung():
    """Giết tiến trình thường làm nơi gọi ném RuntimeError/JSONDecodeError...
    Để nguyên là tầng trên tưởng bước này HỎNG rồi chạy đường dự phòng."""
    proc = _tien_trinh_lau(1)
    huy = threading.Event()
    huy.set()

    with pytest.raises(PipelineCancelled):
        with giet_khi_dung(proc, huy):
            raise RuntimeError("worker chết bất thường")


def test_khong_co_co_dung_thi_hoan_toan_trong_suot():
    """Mọi lời gọi cũ (Trình chỉnh sửa, CLI) phải giữ nguyên hành vi."""
    with pytest.raises(RuntimeError, match="lỗi thật"):
        with giet_khi_dung(_tien_trinh_lau(1), None):
            raise RuntimeError("lỗi thật")


def test_luong_canh_tu_tat_khi_tien_trinh_xong():
    """Thân hàm dài có nhiều đường thoát — không thể trông chờ nơi gọi nhớ
    tắt luồng canh."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    truoc = threading.active_count()
    bat_dau_canh(proc, threading.Event())
    time.sleep(1.0)
    assert threading.active_count() <= truoc, "luồng canh còn sống sau khi xong"


def test_kiem_dung_chi_nem_khi_da_bam():
    kiem_dung(None)
    kiem_dung(threading.Event())
    huy = threading.Event()
    huy.set()
    with pytest.raises(PipelineCancelled):
        kiem_dung(huy)


# -- 2. Tách nhạc nền: Dừng KHÔNG được biến thành "mất nhạc nền" -------------

def test_dung_luc_tach_nhac_nen_khong_thanh_video_mat_nhac(tmp_path,
                                                           monkeypatch):
    from autodub.media import vocal_separator

    wav = tmp_path / "original_audio.wav"
    import wave
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * 1600)

    huy = threading.Event()
    huy.set()

    def _worker_bi_giet(*a, **k):
        raise RuntimeError("worker bị giết giữa chừng")

    monkeypatch.setattr(vocal_separator, "_run_demucs_gpu_worker",
                        _worker_bi_giet)

    with pytest.raises(PipelineCancelled):
        vocal_separator.separate_vocals(str(wav), str(tmp_path),
                                        cancel_event=huy)


def test_cache_demucs_cung_nhan_co_dung(tmp_path, monkeypatch):
    """Đường mẻ nhiều video dùng worker thường trú — cũng phải dừng được."""
    from autodub.media import vocal_separator

    nhan = {}

    class _Cache:
        def separate(self, *a, cancel_event=None, **k):
            nhan["co"] = cancel_event
            return False

    wav = tmp_path / "a.wav"
    import wave
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * 1600)

    huy = threading.Event()
    monkeypatch.setattr(vocal_separator, "_run_demucs_gpu_worker",
                        lambda *a, **k: False)
    monkeypatch.setattr(vocal_separator, "_run_demucs",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("bỏ qua")))
    vocal_separator.separate_vocals(str(wav), str(tmp_path),
                                    demucs_cache=_Cache(), cancel_event=huy)
    assert nhan["co"] is huy


# -- 3. Xuất video: bước lâu nhất của cả lượt --------------------------------

def test_dung_luc_xuat_video_giet_ffmpeg(tmp_path, monkeypatch):
    from autodub.media import video

    procs = []

    def _popen_gia(cmd, **k):
        p = _tien_trinh_lau(30)
        procs.append(p)
        return p

    monkeypatch.setattr(video.subprocess, "Popen", _popen_gia)
    monkeypatch.setattr(video, "probe_duration_s", lambda p: 10.0)
    (tmp_path / "v.mp4").write_bytes(b"x")
    (tmp_path / "a.wav").write_bytes(b"x")

    huy = threading.Event()
    threading.Timer(0.5, huy.set).start()
    t0 = time.monotonic()
    with pytest.raises(PipelineCancelled):
        video.merge_video(str(tmp_path / "v.mp4"), str(tmp_path / "a.wav"),
                          str(tmp_path / "out.mp4"), cancel_event=huy)
    assert time.monotonic() - t0 < 10
    assert procs and procs[0].poll() is not None


def test_khong_co_co_dung_thi_xuat_video_chay_duong_cu(tmp_path, monkeypatch):
    """Bước quan trọng nhất — không đổi cách chạy khi không ai bấm Dừng."""
    from autodub.media import video

    goi = {}

    def _run_gia(cmd, **k):
        goi["chay"] = True
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(video.subprocess, "run", _run_gia)
    monkeypatch.setattr(video.subprocess, "Popen",
                        lambda *a, **k: pytest.fail("đừng đổi sang Popen"))
    monkeypatch.setattr(video, "probe_duration_s", lambda p: 10.0)
    (tmp_path / "v.mp4").write_bytes(b"x")
    (tmp_path / "a.wav").write_bytes(b"x")
    video.merge_video(str(tmp_path / "v.mp4"), str(tmp_path / "a.wav"),
                      str(tmp_path / "out.mp4"))
    assert goi["chay"]


# -- 4. Dây nối từ pipeline ---------------------------------------------------

def test_pipeline_truyen_co_dung_xuong_cac_buoc_dai():
    """Đứt dây ở pipeline thì mọi thứ trên kia thành vô nghĩa."""
    src = open("autodub/pipeline.py", encoding="utf-8").read()
    for dau_hieu in ("sep = separate_vocals(", "return translate_segments_local(",
                     "            merge_video(", "output_video = lipsync_module.run("):
        i = src.find(dau_hieu)
        assert i > 0, dau_hieu
        assert "cancel_event=self._cancel_event" in src[i:i + 700], (
            f"{dau_hieu} chưa nhận cờ Dừng")

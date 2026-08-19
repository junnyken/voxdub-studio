"""V76 — nút Dừng phải dừng được cả lúc đang canh chữ karaoke.

Canh chữ là bước LÂU NHẤT của việc ghi phụ đề (nghe lại từng clip giọng đọc,
video 200 câu là hàng phút) nhưng lại là bước duy nhất trên đường đó không
nhìn cờ Dừng: `SubtitleWorker.cancel()` chỉ có tác dụng SAU khi
`build_karaoke_ass` chạy xong, còn pipeline thì `rep.check_cancelled()` giữa
hai bước — không cắt ngang được bước đang chạy.

Hai cái bẫy đã biết, khoá lại ở đây:
- V72: kiểm cờ ở đầu vòng rồi chờ dài trong `readline()` = không bao giờ chạy
  tới chỗ kiểm. Phải GIẾT tiến trình con.
- V74: `except Exception` nuốt mất ngoại lệ huỷ rồi CHẠY LẠI đường khác. Trên
  đường này có tận BA tầng `except Exception` (align, ass_karaoke, subtitles).
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from autodub.config import Settings
from autodub.progress import PipelineCancelled
from autodub.speech import align as align_mod


@pytest.fixture()
def st(tmp_path):
    s = Settings()
    s.whisper_venv_python = str(tmp_path / "khong-co" / "python.exe")
    s.whisper_model_dir = str(tmp_path / "models")
    return s


def _todo(tmp_path, n=2):
    out = []
    for i in range(1, n + 1):
        wav = tmp_path / f"seg{i}.wav"
        wav.write_bytes(b"RIFF")
        out.append(({"id": i, "start": float(i), "text_vi": "xin chào"},
                    str(wav), 2.0, f"k{i}"))
    return out


# -- 1. Tiến trình con: bấm Dừng là dừng NGAY, không chờ hết mẻ --------------

def test_dung_giua_chung_thi_khong_cho_het_me(st, tmp_path, monkeypatch):
    """Đo THẬT: worker giả nghe 2 giây/clip, mẻ 30 clip (≈60s). Bấm Dừng sau
    ~1s thì phải thoát trong vài giây, không phải sau một phút."""
    import sys as _sys

    lib = tmp_path / "fakelib"
    lib.mkdir()
    (lib / "faster_whisper.py").write_text(
        "import time\n"
        "class _W:\n"
        "    def __init__(s, w, a, b): s.word, s.start, s.end = w, a, b\n"
        "class _Seg:\n"
        "    def __init__(s, ws): s.words = ws\n"
        "class WhisperModel:\n"
        "    def __init__(s, *a, **k): pass\n"
        "    def transcribe(s, wav, **k):\n"
        "        time.sleep(2)\n"
        "        return [_Seg([_W('x', 0.0, 0.5)])], None\n",
        encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(lib))

    py = tmp_path / "venv" / "python.exe"
    py.parent.mkdir(parents=True, exist_ok=True)
    md = tmp_path / "models"
    md.mkdir(exist_ok=True)
    (md / "installed_ok.json").write_text("{}")
    st.whisper_venv_python = _sys.executable
    st.whisper_model_dir = str(md)

    huy = threading.Event()
    threading.Timer(1.0, huy.set).start()

    t0 = time.monotonic()
    with pytest.raises(PipelineCancelled):
        align_mod._asr_words_subprocess(_todo(tmp_path, n=30), "vi", st,
                                        cancel_event=huy)
    tre = time.monotonic() - t0
    # Mẻ này chạy hết cần ~60s (30 clip × 2s, 1 luồng mỗi 2 giây). Nới rộng
    # ngưỡng cho máy CI chậm, nhưng vẫn cách xa "chạy hết mẻ".
    assert tre < 20, f"Dừng mất {tre:.1f}s — nghĩa là vẫn ngồi chờ hết mẻ"


def test_dung_luc_dang_nap_model_van_bao_dung_dung_ly_do(st, tmp_path,
                                                          monkeypatch):
    """Ca đo được, suýt lọt: giết tiến trình lúc CHƯA có dòng nào ra thì
    `readline` trả "" → nếu không kiểm cờ, nó báo "không phản hồi ready" và
    tầng trên hiểu là HỎNG (bản mã nguồn chạy lại toàn bộ in-process, bản
    .exe ghi phụ đề chia đều rồi đi tiếp). Đo: 1,0s so với 20,1s khi không có
    luồng canh — nhưng lý do báo ra mới là thứ test này khoá."""
    import sys as _sys

    lib = tmp_path / "fakelib_nap_lau"
    lib.mkdir()
    (lib / "faster_whisper.py").write_text(
        "import time\n"
        "class WhisperModel:\n"
        "    def __init__(s, *a, **k): time.sleep(30)\n",
        encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(lib))
    md = tmp_path / "models"
    md.mkdir(exist_ok=True)
    (md / "installed_ok.json").write_text("{}")
    st.whisper_venv_python = _sys.executable
    st.whisper_model_dir = str(md)

    huy = threading.Event()
    threading.Timer(1.0, huy.set).start()

    t0 = time.monotonic()
    with pytest.raises(PipelineCancelled):
        align_mod._asr_words_subprocess(_todo(tmp_path, n=3), "vi", st,
                                        cancel_event=huy)
    assert time.monotonic() - t0 < 15, "phải cắt ngang lúc đang nạp model"


def test_bam_dung_truoc_khi_bat_dau_cung_dung(st, tmp_path, monkeypatch):
    """Cờ đã set từ trước: không được chạy tiếp rồi mới nhớ ra."""
    monkeypatch.setattr(align_mod, "_load_align_model",
                        lambda: (MagicMock(), "cpu", 1))
    monkeypatch.setattr(align_mod, "_asr_words",
                        lambda *a, **k: pytest.fail("đã bấm Dừng rồi"))
    huy = threading.Event()
    huy.set()

    with pytest.raises(PipelineCancelled):
        align_mod._asr_words_in_process(_todo(tmp_path), "vi", cancel_event=huy)


# -- 2. Ba tầng `except Exception` không được nuốt cú bấm Dừng ---------------

def test_align_khong_nuot_roi_chay_lai_in_process(st, tmp_path, monkeypatch):
    """Đúng lỗi V74: nuốt ngoại lệ huỷ rồi chạy lại toàn bộ ở đường khác."""
    py = tmp_path / "venv" / "python.exe"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("")
    md = tmp_path / "models"
    md.mkdir(exist_ok=True)
    (md / "installed_ok.json").write_text("{}")
    st.whisper_venv_python = str(py)
    st.whisper_model_dir = str(md)

    def _huy(*a, **k):
        raise PipelineCancelled("Đã dừng theo yêu cầu.")

    monkeypatch.setattr(align_mod, "_asr_words_subprocess", _huy)
    monkeypatch.setattr(align_mod, "_asr_words_in_process",
                        lambda *a, **k: pytest.fail("Dừng rồi còn chạy lại"))

    with pytest.raises(PipelineCancelled):
        align_mod._asr_words_for_clips(_todo(tmp_path), "vi", st,
                                       cancel_event=threading.Event())


def test_karaoke_khong_bien_cu_bam_dung_thanh_chia_deu(tmp_path, monkeypatch):
    """`resolve_word_times` bọc `except Exception` — nuốt ở đó là video vẫn
    chạy tới cùng với phụ đề sai nhịp, người dùng tưởng Dừng hỏng."""
    from autodub.text import ass_karaoke

    def _huy(*a, **k):
        raise PipelineCancelled("Đã dừng theo yêu cầu.")

    monkeypatch.setattr("autodub.speech.align.align_segments", _huy)
    monkeypatch.setattr("autodub.media.audio.wav_duration_s", lambda p: 2.0)

    with pytest.raises(PipelineCancelled):
        ass_karaoke.resolve_word_times(
            [{"id": 1, "text_vi": "xin chào", "start": 0.0, "end": 2.0}],
            str(tmp_path), "text_vi", cancel_event=threading.Event())


def test_refresh_subtitles_khong_nuot_cu_bam_dung(tmp_path, monkeypatch):
    """Tầng thứ ba: `refresh_subtitles` cũng có `except Exception` riêng."""
    from autodub.languages import get_target
    from autodub.text import subtitles

    def _huy(*a, **k):
        raise PipelineCancelled("Đã dừng theo yêu cầu.")

    monkeypatch.setattr("autodub.text.ass_karaoke.build_karaoke_ass", _huy)
    segs = [{"id": 1, "text_vi": "xin chào", "start": 0.0, "end": 2.0,
             "duration": 2.0}]

    with pytest.raises(PipelineCancelled):
        subtitles.refresh_subtitles(
            segs, str(tmp_path), get_target("vi"),
            {"display": "karaoke"}, merge_dir=str(tmp_path),
            for_burn=True, cancel_event=threading.Event())


# -- 3. Dây nối từ chỗ bấm nút tới chỗ nghe ---------------------------------

def test_co_dung_di_tu_subtitles_toi_align(tmp_path, monkeypatch):
    """Khoá cả đường dây: refresh_subtitles → build_karaoke_ass →
    resolve_word_times → align_segments. Đứt một mắt là nút Dừng vô nghĩa."""
    from autodub.languages import get_target
    from autodub.text import subtitles

    nhan = {}

    def _bat(segments, merge_dir, text_field, **kw):
        nhan["cancel_event"] = kw.get("cancel_event")
        return {}

    monkeypatch.setattr("autodub.speech.align.align_segments", _bat)
    monkeypatch.setattr("autodub.media.audio.wav_duration_s", lambda p: 2.0)
    ev = threading.Event()
    segs = [{"id": 1, "text_vi": "xin chào", "start": 0.0, "end": 2.0,
             "duration": 2.0}]

    subtitles.refresh_subtitles(segs, str(tmp_path), get_target("vi"),
                                {"display": "karaoke"},
                                merge_dir=str(tmp_path), for_burn=True,
                                cancel_event=ev)
    assert nhan["cancel_event"] is ev


def test_pipeline_giu_co_dung_de_truyen_xuong():
    """`rep.check_cancelled()` chỉ chạy GIỮA hai bước — bước dài phải nhận
    thẳng cờ, nên pipeline phải giữ lại nó."""
    from autodub.pipeline import DubPipeline

    ev = threading.Event()
    assert DubPipeline(Settings(), cancel_event=ev)._cancel_event is ev

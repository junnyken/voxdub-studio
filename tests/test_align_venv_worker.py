"""V75 — canh chữ karaoke phải chạy trong `.venv-whisper`, không im lặng nữa.

Lỗi thật (tìm ra khi rà lại V74, chưa ai báo vì nó KHÔNG kêu): `align.py`
import `faster_whisper` ngay trong tiến trình chính. `autodub.spec` cố ý
không đóng gói thư viện đó, mà chỗ gọi lại bọc `try/except` — nên ở bản
`.exe` mọi lượt canh chữ đều hỏng và phụ đề âm thầm rơi về "chia đều theo
thời lượng câu". Đúng lớp lỗi của V38/V74, chỉ khác là nó không đẻ ra thông
báo nào để người dùng nghi ngờ.

Bộ test này khoá lại: (1) có venv thì đi tiến trình con, (2) bản đóng gói
thiếu venv thì NÓI RA cách cài chứ không im, (3) bản mã nguồn vẫn chạy
in-process như cũ, và (4) giao thức JSON hai đầu khớp nhau thật — chạy
`align_whisper_worker.py` bằng một `faster_whisper` giả.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import textwrap

import pytest

from autodub.config import Settings
from autodub.speech import align as align_mod


@pytest.fixture()
def st(tmp_path):
    """Settings trỏ vào thư mục ứng dụng rỗng — chưa cài venv nào."""
    s = Settings()
    s.whisper_venv_python = str(tmp_path / "khong-co" / "python.exe")
    s.whisper_model_dir = str(tmp_path / "models")
    return s


def _cai_venv(st, tmp_path, python_that=None):
    """Giả lập máy ĐÃ cài Whisper đúng cách."""
    py = python_that or str(tmp_path / "venv" / "python.exe")
    if python_that is None:
        os.makedirs(os.path.dirname(py), exist_ok=True)
        open(py, "w").close()
    md = tmp_path / "models"
    md.mkdir(exist_ok=True)
    (md / "installed_ok.json").write_text("{}")
    st.whisper_venv_python = py
    st.whisper_model_dir = str(md)


def _todo(tmp_path, n=2):
    """Danh sách việc đúng dạng align_segments dựng ra: (seg, wav, dur, key)."""
    out = []
    for i in range(1, n + 1):
        wav = tmp_path / f"seg{i}.wav"
        wav.write_bytes(b"RIFF....WAVEfmt ")
        out.append(({"id": i, "start": float(i), "text_vi": "xin chào"},
                    str(wav), 2.0, f"k{i}"))
    return out


# -- 1. Chọn đường: venv > in-process, bản đóng gói không có in-process ------

def test_co_venv_thi_di_tien_trinh_con(st, tmp_path, monkeypatch):
    _cai_venv(st, tmp_path)
    goi = {}
    monkeypatch.setattr(align_mod, "_asr_words_subprocess",
                        lambda todo, lang, s: goi.setdefault("sub", lang) or {})
    monkeypatch.setattr(align_mod, "_load_align_model",
                        lambda: pytest.fail("bản có venv KHÔNG được nạp "
                                            "model trong tiến trình chính"))

    align_mod._asr_words_for_clips(_todo(tmp_path), "vi", st)
    assert goi["sub"] == "vi"


def test_ban_dong_goi_thieu_venv_thi_NOI_RA_cach_cai(st, tmp_path, monkeypatch,
                                                     caplog):
    """Lỗi gốc của V75: chỗ này trước đây im lặng, phụ đề lệch mà không ai biết."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(align_mod, "_load_align_model",
                        lambda: pytest.fail("bản .exe không có đường này"))

    with caplog.at_level(logging.WARNING, logger="autodub.align"):
        ket_qua = align_mod._asr_words_for_clips(_todo(tmp_path), "vi", st)

    assert ket_qua is None, "không canh được thì phải trả None, không phải {}"
    loi = " ".join(r.getMessage() for r in caplog.records)
    assert "Không canh được phụ đề: chưa cài bộ nghe" in loi
    assert "Cai dat Whisper ASR.bat" in loi, "phải chỉ đúng tệp cần bấm"


def test_ban_ma_nguon_thieu_venv_van_chay_in_process(st, tmp_path, monkeypatch):
    """Máy dev không có venv — đường in-process vẫn hợp lệ, không được chặn."""
    monkeypatch.setattr(align_mod, "_asr_words_subprocess",
                        lambda *a, **k: pytest.fail("không có venv thì đừng "
                                                    "gọi tiến trình con"))
    monkeypatch.setattr(align_mod, "_asr_words_in_process",
                        lambda todo, lang: {1: [("xin", 0.0, 0.5)]})

    assert align_mod._asr_words_for_clips(_todo(tmp_path), "vi", st) \
        == {1: [("xin", 0.0, 0.5)]}


def test_ma_nguon_venv_hong_thi_lui_ve_in_process(st, tmp_path, monkeypatch):
    _cai_venv(st, tmp_path)

    def _no(*a, **k):
        raise RuntimeError("worker chết")

    monkeypatch.setattr(align_mod, "_asr_words_subprocess", _no)
    monkeypatch.setattr(align_mod, "_asr_words_in_process",
                        lambda todo, lang: {2: [("chào", 0.1, 0.4)]})

    assert align_mod._asr_words_for_clips(_todo(tmp_path), "vi", st) \
        == {2: [("chào", 0.1, 0.4)]}


def test_dong_goi_venv_hong_thi_KHONG_lui_ve_in_process(st, tmp_path,
                                                        monkeypatch, caplog):
    """Bản .exe rơi về in-process chỉ đổi lỗi thật thành `No module named 'av'`
    — đúng cái bẫy đã mắc ở V74."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    _cai_venv(st, tmp_path)

    def _no(*a, **k):
        raise RuntimeError("worker chết")

    monkeypatch.setattr(align_mod, "_asr_words_subprocess", _no)
    monkeypatch.setattr(align_mod, "_asr_words_in_process",
                        lambda *a: pytest.fail("bản .exe không có đường này"))

    with caplog.at_level(logging.WARNING, logger="autodub.align"):
        assert align_mod._asr_words_for_clips(_todo(tmp_path), "vi", st) is None
    assert "worker chết" in " ".join(r.getMessage() for r in caplog.records)


def test_khong_co_settings_van_tu_doc_cau_hinh(tmp_path, monkeypatch):
    """Caller cũ gọi align_segments không kèm settings — vẫn phải biết venv
    nằm đâu, nếu không bản đóng gói lại rơi vào đúng lỗi V75."""
    thay = {}
    monkeypatch.setattr(align_mod, "seg_wav_path",
                        lambda d, sid: str(tmp_path / "seg1.wav"))
    (tmp_path / "seg1.wav").write_bytes(b"RIFF")
    monkeypatch.setattr("autodub.media.audio.wav_duration_s", lambda p: 2.0)
    monkeypatch.setattr(align_mod, "_asr_words_for_clips",
                        lambda todo, lang, s: thay.setdefault("settings", s)
                        and None)

    align_mod.align_segments([{"id": 1, "text_vi": "xin chào", "start": 0.0,
                               "end": 2.0}], str(tmp_path), "text_vi")
    assert isinstance(thay["settings"], Settings)


# -- 2. Kết quả tiến trình con phải khớp vào mốc chữ cuối cùng ---------------

def test_mocs_tu_tien_trinh_con_di_thang_vao_ket_qua(st, tmp_path, monkeypatch):
    _cai_venv(st, tmp_path)
    wav = tmp_path / "seg7.wav"
    wav.write_bytes(b"RIFF")
    monkeypatch.setattr(align_mod, "seg_wav_path", lambda d, sid: str(wav))
    monkeypatch.setattr("autodub.media.audio.wav_duration_s", lambda p: 2.0)
    monkeypatch.setattr(
        align_mod, "_asr_words_subprocess",
        lambda todo, lang, s: {7: [("xin", 0.0, 0.5), ("chào", 0.6, 1.2)]})

    out = align_mod.align_segments(
        [{"id": 7, "text_vi": "xin chào", "start": 10.0, "end": 12.0}],
        str(tmp_path), "text_vi", settings=st)

    # Mốc tuyệt đối = mốc trong clip + start của câu.
    assert out[7] == [("xin", 10.0, 10.5), ("chào", 10.6, 11.2)]


# -- 3. Giao thức hai đầu: chạy worker THẬT bằng faster_whisper giả ----------

@pytest.fixture()
def fake_fw(tmp_path):
    """Một `faster_whisper` giả để chạy worker mà không cần model 150 MB."""
    lib = tmp_path / "fakelib"
    lib.mkdir()
    (lib / "faster_whisper.py").write_text(textwrap.dedent('''
        import os

        class _W:
            def __init__(self, word, start, end):
                self.word, self.start, self.end = word, start, end

        class _Seg:
            def __init__(self, words):
                self.words = words

        class WhisperModel:
            def __init__(self, *a, **k):
                pass

            def transcribe(self, wav, **kw):
                ten = os.path.basename(wav)
                if "hong" in ten:
                    raise RuntimeError("clip này nghe không ra")
                # Trả đúng tên clip làm chữ để test truy được clip nào ra clip nào.
                return [_Seg([_W(" " + ten + " ", 0.25, 0.75),
                              _W("  ", 0.8, 0.9)])], None
    '''), encoding="utf-8")
    return str(lib)


def test_worker_that_chay_duoc_va_khop_giao_thuc(st, tmp_path, monkeypatch,
                                                 fake_fw):
    """Chạy align_whisper_worker.py bằng python thật + thư viện giả.

    Đây là phép kiểm duy nhất chứng minh hai đầu giao thức khớp nhau — mọi
    test mock ở trên vẫn xanh kể cả khi worker viết sai JSON.
    """
    _cai_venv(st, tmp_path, python_that=sys.executable)
    monkeypatch.setenv("PYTHONPATH", fake_fw)

    todo = _todo(tmp_path, n=2)
    got = align_mod._asr_words_subprocess(todo, "vi", st)

    assert set(got) == {1, 2}
    # Chữ rỗng bị loại, chữ có nội dung giữ nguyên mốc tương đối trong clip.
    assert got[1] == [("seg1.wav", 0.25, 0.75)]
    assert got[2] == [("seg2.wav", 0.25, 0.75)]


def test_mot_clip_hong_khong_giet_ca_me(st, tmp_path, monkeypatch, fake_fw):
    _cai_venv(st, tmp_path, python_that=sys.executable)
    monkeypatch.setenv("PYTHONPATH", fake_fw)

    todo = _todo(tmp_path, n=1)
    hong = tmp_path / "seg-hong.wav"
    hong.write_bytes(b"RIFF")
    todo.append(({"id": 9, "start": 9.0}, str(hong), 2.0, "k9"))

    got = align_mod._asr_words_subprocess(todo, "vi", st)
    assert set(got) == {1}, "clip hỏng chỉ mất câu đó, mẻ vẫn phải xong"


def test_worker_thieu_faster_whisper_thi_bao_loi_ro(st, tmp_path, monkeypatch):
    """venv cài dở — phải raise nói rõ, không trả về {} lặng lẽ.

    Chặn bằng một `faster_whisper` STUB tự ném ImportError chứ không phải
    PYTHONPATH rỗng: `requirements.txt` có faster-whisper thật, nên trên máy
    CI (và mọi máy dev đã cài đủ) worker vẫn import được và test rỗng kia
    PASS GIẢ — đúng lỗi đã làm CI đỏ ở lần chạy đầu của V75.
    """
    _cai_venv(st, tmp_path, python_that=sys.executable)
    chan = tmp_path / "venv-cai-do"
    chan.mkdir()
    # PYTHONPATH đứng trước site-packages nên stub này luôn thắng, bất kể máy
    # chạy test có faster-whisper hay không.
    (chan / "faster_whisper.py").write_text(
        'raise ImportError("giả lập venv cài dở")', encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(chan))
    monkeypatch.setattr(align_mod, "_ALIGN_READY_TIMEOUT_S", 120)

    with pytest.raises(RuntimeError, match="faster-whisper chưa cài"):
        align_mod._asr_words_subprocess(_todo(tmp_path, n=1), "vi", st)


def test_worker_bundled_trong_spec():
    """Quên dòng datas là bản .exe không có tệp worker — hỏng y như cũ."""
    spec = open("autodub.spec", encoding="utf-8").read()
    assert "align_whisper_worker.py" in spec


# -- 4. Lời cho khung Nhật ký ----------------------------------------------

def test_nhat_ky_hien_duoc_loi_khuyen_cai_bo_nghe():
    """`log_text.notice_for` là allowlist: không có dòng riêng thì thông báo
    này bị lọc mất vì chứa chữ "Whisper" (xem _TECH_RE) — bài học V73."""
    from autodub_gui.log_text import notice_for

    msg = ('Không canh được phụ đề: chưa cài bộ nghe Whisper trong thư mục '
           'ứng dụng này — đúp chuột "Cai dat Whisper ASR.bat" rồi chạy lại '
           'thì chữ mới nhảy đúng nhịp giọng đọc')
    line = notice_for(msg, logging.WARNING)
    assert line is not None, "thông báo phải tới được người dùng"
    assert "Cai dat Whisper ASR.bat" in line[0]


def test_worker_khong_import_gi_tu_autodub():
    """Worker chạy trong .venv-whisper — ở đó không có package autodub."""
    src = open("autodub/speech/align_whisper_worker.py", encoding="utf-8").read()
    assert "import autodub" not in src and "from autodub" not in src


def test_in_process_tu_chan_o_ban_dong_goi(tmp_path, monkeypatch):
    """Lưới an toàn: người viết code sau này gọi thẳng vào đường in-process
    thì phải nổ với lý do THẬT, không phải `No module named 'av'` (V38/V74)."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(align_mod, "_load_align_model",
                        lambda: pytest.fail("không được nạp tới đây"))

    with pytest.raises(RuntimeError, match="\\.venv-whisper"):
        align_mod._asr_words_in_process(_todo(tmp_path, n=1), "vi")

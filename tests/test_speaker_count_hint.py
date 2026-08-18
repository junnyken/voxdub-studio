"""V65b — gợi ý số người nói xuống pyannote.

Đo thật ngày 18-08: 3 giọng nữ trong cùng một file bị GỘP thành một người nói,
và tầng hồ sơ nhân vật không sửa nổi vì nó chỉ nhìn thấy một người (xem
TEST_LOG mục V59 18-08).
"""
from __future__ import annotations

import sys
import textwrap


from autodub.speech.diarize_worker import _speaker_hint


# --------------------------------------------------------------- hàm thuần
def test_khong_biet_gi_thi_khong_goi_y():
    assert _speaker_hint(0, 0, 0) == {}, "để trống thì pyannote tự đoán như trước"


def test_biet_chac_thi_dung_num_speakers():
    assert _speaker_hint(3, 0, 0) == {"num_speakers": 3}


def test_biet_chac_de_len_khoang():
    """Đưa cả ba mà lệch nhau thì pyannote không chiều được cả hai.

    Con số người dùng gõ tay đáng tin hơn con số suy ra từ hồ sơ.
    """
    assert _speaker_hint(3, 5, 9) == {"num_speakers": 3}


def test_chi_tran_hoac_chi_san():
    assert _speaker_hint(0, 0, 7) == {"max_speakers": 7}
    assert _speaker_hint(0, 2, 0) == {"min_speakers": 2}
    assert _speaker_hint(0, 2, 7) == {"min_speakers": 2, "max_speakers": 7}


def test_tran_thap_hon_san_thi_bo_TRAN_chu_khong_bo_san():
    """Thà tách hơi nhiều người còn hơn gộp nhầm hai người vào một giọng.

    Gộp thì người xem nghe hai nhân vật cùng một giọng — hỏng ngay trên màn
    hình. Tách dư thì hồ sơ nhân vật ở tập sau vẫn khớp lại được.
    """
    assert _speaker_hint(0, 5, 2) == {"min_speakers": 5}


def test_so_am_coi_nhu_khong_biet():
    assert _speaker_hint(-1, -3, -2) == {}


# ------------------------------------------------- truyền xuống dòng lệnh
def _fake_worker(tmp_path, body: str) -> str:
    path = tmp_path / "worker.py"
    path.write_text("import json\n" + textwrap.dedent(body), encoding="utf-8")
    return str(path)


def _settings(monkeypatch, worker_path):
    from autodub.config import Settings
    settings = Settings()
    monkeypatch.setattr(settings, "diarization_venv_python_path", lambda: sys.executable)
    monkeypatch.setattr(settings, "diarization_model_dir_path", lambda: "/tmp/fake-model")
    monkeypatch.setattr("autodub.speech.diarization._WORKER_SCRIPT", worker_path)
    return settings


# KHÔNG thụt lề: `_fake_worker` gọi `textwrap.dedent` trên cả chuỗi đã ghép
# thêm dòng `ARGV_OUT = ...` không thụt, nên tiền tố chung là rỗng và dedent
# không gỡ được gì.
DUMP_ARGV = """
import sys
print(json.dumps({"segment": True, "start": 0.0, "end": 1.0,
                  "speaker": "SPEAKER_00"}), flush=True)
print(json.dumps({"done": True, "num_speakers": 1}), flush=True)
with open(ARGV_OUT, "w", encoding="utf-8") as f:
    json.dump(sys.argv[1:], f)
"""


def _run_diarize(monkeypatch, tmp_path, **kwargs):
    from autodub.speech.diarization import diarize
    argv_out = tmp_path / "argv.json"
    worker = _fake_worker(tmp_path,
                          f"ARGV_OUT = {str(argv_out)!r}\n" + DUMP_ARGV)
    settings = _settings(monkeypatch, worker)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\0")
    diarize(str(audio), settings, **kwargs)
    import json as _json
    return _json.loads(argv_out.read_text(encoding="utf-8"))


def test_khong_truyen_gi_thi_dong_lenh_sach(monkeypatch, tmp_path):
    argv = _run_diarize(monkeypatch, tmp_path)
    assert "--num-speakers" not in argv
    assert "--min-speakers" not in argv
    assert "--max-speakers" not in argv


def test_truyen_dung_con_so_xuong_worker(monkeypatch, tmp_path):
    argv = _run_diarize(monkeypatch, tmp_path, num_speakers=4, max_speakers=9)
    assert argv[argv.index("--num-speakers") + 1] == "4"
    assert argv[argv.index("--max-speakers") + 1] == "9"


def test_so_0_khong_lot_vao_dong_lenh(monkeypatch, tmp_path):
    """`0` nghĩa là KHÔNG BIẾT, không phải "không có ai nói"."""
    argv = _run_diarize(monkeypatch, tmp_path, num_speakers=0, min_speakers=0)
    assert "--num-speakers" not in argv


# ------------------------------------------------------ trần từ hồ sơ nhân vật
def _pipeline():
    from autodub.pipeline import DubPipeline
    from autodub.config import Settings
    return DubPipeline(Settings())


def test_khong_co_ho_so_thi_khong_co_tran(tmp_path, monkeypatch):
    p = _pipeline()
    monkeypatch.setattr(p, "_profiles_dir", lambda s: str(tmp_path))
    assert p._profile_speaker_ceiling("", None) == 0


def test_tran_bang_so_nhan_vat_cong_hai(tmp_path, monkeypatch):
    """Cộng 2 chỗ cho nhân vật mới xuất hiện lần đầu ở tập này."""
    from autodub.character_profile import CharacterProfile
    hs = CharacterProfile.load(str(tmp_path), "Phim A")
    hs.remember({"S0": "Lý Tứ", "S1": "Vương Ngũ", "S2": "Triệu Lục"},
                {"S0": 120.0, "S1": 200.0, "S2": 210.0},
                {"S0": "v1", "S1": "v2", "S2": "v3"})
    hs.save(str(tmp_path))

    p = _pipeline()
    monkeypatch.setattr(p, "_profiles_dir", lambda s: str(tmp_path))
    assert p._profile_speaker_ceiling("Phim A", None) == 5


def test_ho_so_hong_khong_lam_chet_luot_dub(tmp_path, monkeypatch):
    p = _pipeline()

    def no_ra(_settings):
        raise OSError("ổ đĩa hỏng")

    monkeypatch.setattr(p, "_profiles_dir", no_ra)
    assert p._profile_speaker_ceiling("Phim A", None) == 0, \
        "đọc hồ sơ lỗi thì để pyannote tự quyết, không được ném lên"


def test_ho_so_rong_khong_sinh_tran_bang_2(tmp_path, monkeypatch):
    """Hồ sơ mới lập chưa có nhân vật nào — trần 2 sẽ ép gộp, tệ hơn không có."""
    from autodub.character_profile import CharacterProfile
    CharacterProfile.load(str(tmp_path), "Phim Rỗng").save(str(tmp_path))
    p = _pipeline()
    monkeypatch.setattr(p, "_profiles_dir", lambda s: str(tmp_path))
    assert p._profile_speaker_ceiling("Phim Rỗng", None) == 0


# ------------------------------------------------------------------ CLI
def test_cli_speakers_dat_vao_settings(monkeypatch):
    from autodub import cli
    parser = cli.build_parser()
    args = parser.parse_args(["dub", "https://youtu.be/x", "--multi-speaker",
                              "--speakers", "4"])
    assert args.speakers == 4


def test_cli_mac_dinh_khong_khai_so_nguoi(monkeypatch):
    from autodub import cli
    parser = cli.build_parser()
    args = parser.parse_args(["dub", "https://youtu.be/x"])
    assert args.speakers == 0

"""Đóng gói `models/` rồi kéo về máy khác — đúng và AN TOÀN (mini-spec C47).

Chủ dự án hỏi: cài xong máy phình lên 17,8 GB, có đưa phần đó lên hosting rồi
kéo về được không. Phần venv thì KHÔNG (gắn đường dẫn tuyệt đối của máy đã tạo
ra nó), nhưng `models/` thì được — nó là tệp dữ liệu thuần.

Bộ canh này giữ ba thứ dễ hỏng nhất của một cơ chế tải tệp vài trăm MB:
mã băm phải được kiểm THẬT, model dở dang không được để lại trên đĩa, và gói
tải từ mạng về không được ghi ra ngoài thư mục đích.
"""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parents[1]
DONG_GOI = GOC / "scripts" / "dong_goi_models.py"
TAI = GOC / "scripts" / "tai_models.py"


def _chay(kich_ban: Path, *tham_so: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(kich_ban), *tham_so],
                          capture_output=True, text=True, timeout=300,
                          errors="replace")


@pytest.fixture()
def may_a(tmp_path: Path) -> Path:
    """Một 'máy' đã cài sẵn hai model thường + một model có ràng buộc."""
    # Dữ liệu NGẪU NHIÊN, không nén được: model thật cũng vậy, và bài test cắt
    # phần chỉ có nghĩa khi gói sau khi nén vẫn vượt trần.
    import os as _os
    for ten, noi_dung in (("whisper", _os.urandom(3 * 1024 * 1024)),
                          ("vieneu", b"y" * 3000),
                          ("diarization", b"z" * 1000)):
        d = tmp_path / "appA" / "models" / ten
        d.mkdir(parents=True)
        (d / "model.bin").write_bytes(noi_dung)
        (d / "installed_ok.json").write_text("{}", encoding="utf-8")
    return tmp_path / "appA"


def test_dong_goi_bo_qua_model_co_rang_buoc_quyen(may_a, tmp_path):
    ra = tmp_path / "goi"
    kq = _chay(DONG_GOI, "--thu-muc", str(may_a), "--ra", str(ra))
    assert kq.returncode == 0, kq.stderr
    ke = json.loads((ra / "models.json").read_text(encoding="utf-8"))
    ten = {m["ten"] for m in ke["models"]}
    assert ten == {"whisper", "vieneu"}, (
        "pyannote là gated model — mỗi người phải tự đồng ý điều khoản và "
        "dùng token riêng; đóng gói sẵn là đi vòng qua đúng cái cổng đó")
    assert "BỎ QUA diarization" in kq.stdout
    assert "--gom-ca-model-gioi-han" in kq.stdout, "phải chỉ ra lối đi tiếp"


def test_co_co_de_dong_goi_ca_model_gioi_han(may_a, tmp_path):
    ra = tmp_path / "goi"
    kq = _chay(DONG_GOI, "--thu-muc", str(may_a), "--ra", str(ra),
               "--gom-ca-model-gioi-han")
    assert kq.returncode == 0
    ke = json.loads((ra / "models.json").read_text(encoding="utf-8"))
    assert "diarization" in {m["ten"] for m in ke["models"]}


def test_ban_ke_ghi_du_ma_bam_va_dung_luong(may_a, tmp_path):
    ra = tmp_path / "goi"
    _chay(DONG_GOI, "--thu-muc", str(may_a), "--ra", str(ra))
    for m in json.loads((ra / "models.json").read_text(encoding="utf-8"))["models"]:
        assert len(m["sha256"]) == 64
        assert m["bytes"] == (ra / m["tep"]).stat().st_size


def test_keo_ve_may_khac_ra_dung_noi_dung(may_a, tmp_path):
    ra, may_b = tmp_path / "goi", tmp_path / "appB"
    _chay(DONG_GOI, "--thu-muc", str(may_a), "--ra", str(ra))
    kq = _chay(TAI, "--tu", str(ra / "models.json"), "--thu-muc", str(may_b))
    assert kq.returncode == 0, kq.stderr
    goc = (may_a / "models" / "whisper" / "model.bin").read_bytes()
    assert (may_b / "models" / "whisper" / "model.bin").read_bytes() == goc
    assert (may_b / "models" / "vieneu" / "installed_ok.json").is_file()


def test_da_co_san_thi_KHONG_de_len(may_a, tmp_path):
    ra, may_b = tmp_path / "goi", tmp_path / "appB"
    _chay(DONG_GOI, "--thu-muc", str(may_a), "--ra", str(ra))
    d = may_b / "models" / "whisper"
    d.mkdir(parents=True)
    (d / "model.bin").write_bytes(b"cua toi")
    _chay(TAI, "--tu", str(ra / "models.json"), "--thu-muc", str(may_b))
    assert (d / "model.bin").read_bytes() == b"cua toi", "đã đè mất bản của máy"


def test_tep_hong_thi_BAO_HONG_va_khong_de_lai_model_do_dang(may_a, tmp_path):
    """Tải hỏng mà vẫn giải nén thì lỗi lộ ra tận lúc đang lồng tiếng dở."""
    ra, may_b = tmp_path / "goi", tmp_path / "appB"
    _chay(DONG_GOI, "--thu-muc", str(may_a), "--ra", str(ra))
    goi = ra / "models-whisper.zip"
    d = bytearray(goi.read_bytes())
    d[len(d) // 2] ^= 0xFF
    goi.write_bytes(bytes(d))

    kq = _chay(TAI, "--tu", str(ra / "models.json"), "--thu-muc", str(may_b),
               "--chi", "whisper")
    assert kq.returncode == 1
    assert "MÃ BĂM KHÔNG KHỚP" in kq.stderr
    assert not (may_b / "models" / "whisper").exists(), (
        "để lại model dở dang thì app tưởng đã cài xong")


def test_goi_co_duong_dan_thoat_ra_ngoai_thi_bi_chan(may_a, tmp_path):
    """Tệp tải từ mạng về thì không được tin (zip slip)."""
    ra, may_b = tmp_path / "goi", tmp_path / "appB"
    _chay(DONG_GOI, "--thu-muc", str(may_a), "--ra", str(ra))
    goi = ra / "models-whisper.zip"
    with zipfile.ZipFile(goi, "a") as z:
        z.writestr("../../thoat_ra.txt", "x")
    ke_path = ra / "models.json"
    ke = json.loads(ke_path.read_text(encoding="utf-8"))
    import hashlib
    for m in ke["models"]:
        if m["ten"] == "whisper":
            m["sha256"] = hashlib.sha256(goi.read_bytes()).hexdigest()
            m["bytes"] = goi.stat().st_size
    ke_path.write_text(json.dumps(ke), encoding="utf-8")

    kq = _chay(TAI, "--tu", str(ke_path), "--thu-muc", str(may_b),
               "--chi", "whisper")
    assert kq.returncode != 0
    assert not (tmp_path / "thoat_ra.txt").exists()
    assert not (may_b / "thoat_ra.txt").exists()


def test_khong_co_models_thi_bao_ro(tmp_path):
    kq = _chay(DONG_GOI, "--thu-muc", str(tmp_path), "--ra", str(tmp_path / "x"))
    assert kq.returncode == 2
    assert "Không thấy" in kq.stderr


# ---------------- gói lớn phải cắt phần, vì mọi chỗ chứa đều có trần ----------------

def test_goi_lon_duoc_cat_phan_va_ghep_lai_dung_tung_byte(may_a, tmp_path):
    """Model Whisper large-v3 cỡ 3 GB, GitHub Release chặn 2 GB mỗi tệp."""
    ra, may_b = tmp_path / "goi", tmp_path / "appB"
    kq = _chay(DONG_GOI, "--thu-muc", str(may_a), "--ra", str(ra),
               "--cat-phan-mb", "1")   # ép cắt với dữ liệu bé của test
    assert kq.returncode == 0, kq.stderr
    ke = json.loads((ra / "models.json").read_text(encoding="utf-8"))
    lon = next(m for m in ke["models"] if m["ten"] == "whisper")
    assert lon.get("phan"), "gói vượt trần mà không được cắt"
    assert not (ra / lon["tep"]).exists(), (
        "còn để lại bản nguyên bên cạnh các phần — vừa tốn chỗ vừa dễ đưa "
        "nhầm tệp lên máy chủ")
    for ph in lon["phan"]:
        assert (ra / ph["tep"]).is_file() and len(ph["sha256"]) == 64

    assert _chay(TAI, "--tu", str(ra / "models.json"),
                 "--thu-muc", str(may_b)).returncode == 0
    goc = (may_a / "models" / "whisper" / "model.bin").read_bytes()
    assert (may_b / "models" / "whisper" / "model.bin").read_bytes() == goc


def test_mot_phan_hong_thi_bao_dung_phan_do(may_a, tmp_path):
    ra, may_b = tmp_path / "goi", tmp_path / "appB"
    _chay(DONG_GOI, "--thu-muc", str(may_a), "--ra", str(ra), "--cat-phan-mb", "1")
    ke = json.loads((ra / "models.json").read_text(encoding="utf-8"))
    lon = next(m for m in ke["models"] if m["ten"] == "whisper")
    hong = ra / lon["phan"][1]["tep"]          # phá ĐÚNG phần giữa
    d = bytearray(hong.read_bytes())
    d[0] ^= 0xFF
    hong.write_bytes(bytes(d))

    kq = _chay(TAI, "--tu", str(ra / "models.json"), "--thu-muc", str(may_b),
               "--chi", "whisper")
    assert kq.returncode == 1
    assert "phần 2" in kq.stderr, f"không chỉ ra phần nào hỏng: {kq.stderr}"
    assert not (may_b / "models" / "whisper").exists()

"""I0-FDE — bộ lái cổng kiểm bản đóng gói (`scripts/kiem_goi_phat_hanh.py`).

Bộ lái chạy trên CI: giải nén gói ứng viên vào hộp cát, cài bộ máy theo đúng
đường người dùng, chạy `VoxDub.exe`, rồi soi tệp ra. Những phép kiểm dưới đây
khoá đúng các ca mà nếu hỏng thì cổng sẽ **xanh giả**:

* chạy nhầm mã nguồn thay vì gói (cách "sửa cho nhanh" cám dỗ nhất);
* lượt chạy mượn tệp của cây mã nguồn / ngoài hộp cát;
* hộp cát "cài mới" thật ra có bản cũ nằm cạnh;
* tệp ra tồn tại nhưng CÂM hoặc lệch thời lượng;
* bản mới sửa/xoá tệp của bản cũ mà không ai thấy.

Chạy được trên Linux: mọi lượt gọi `.exe`/ffprobe đều bị thay bằng bản giả —
phần chạy thật là việc của runner Windows (xem docs/TEST_LOG.md).
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import kiem_goi_phat_hanh as bo_lai  # noqa: E402

from autodub.bang_chung import manifest_thu_muc, so_sanh_manifest  # noqa: E402


# ----------------------------------------------------------- chốt đường chạy --

def test_khong_cho_chay_thu_gi_khac_ngoai_exe(tmp_path):
    """Đổi sang `python …` cho tiện phải ĐỎ — đó là cả lý do có cổng này."""
    gia = tmp_path / "python.exe"
    gia.write_text("")
    with pytest.raises(bo_lai.Hong, match="VoxDub.exe"):
        bo_lai.chay_exe(gia, [], tmp_path / "bc", 5)


def test_khong_cho_chay_ban_dung_trong_cay_ma_nguon():
    trong_repo = bo_lai.GOC_REPO / "dist" / "VoxDub" / "VoxDub.exe"
    with pytest.raises(bo_lai.Hong, match="cây mã nguồn"):
        bo_lai.chay_exe(trong_repo, [], bo_lai.GOC_REPO / "bc", 5)


def test_exe_thieu_thi_noi_that(tmp_path):
    with pytest.raises(bo_lai.Hong, match="thiếu tệp chạy"):
        bo_lai.chay_exe(tmp_path / "VoxDub.exe", [], tmp_path / "bc", 5)


def test_ma_thoat_khac_0_thi_noi_dung_giai_doan():
    class _Kq:
        returncode = 3
    with pytest.raises(bo_lai.Hong, match="asr"):
        bo_lai._doi_ma(_Kq(), {"giai_doan_hong": "asr", "loi": "thiếu venv"},
                       "chặng 1")


# ------------------------------------------------------- soi đường đã dùng --

def _ghi_worker_log(thu_muc: Path, cac_duong: list[str]) -> Path:
    thu_muc.mkdir(parents=True, exist_ok=True)
    with open(thu_muc / "worker-launches.jsonl", "w", encoding="utf-8") as f:
        for d in cac_duong:
            f.write(json.dumps({"chuong_trinh": d, "tham_so": [],
                                "cwd": d}) + "\n")
    return thu_muc


def test_duong_tu_cay_ma_nguon_la_hong(tmp_path):
    """Ca xanh-giả nguy hiểm nhất: gói thiếu tệp, nhưng mượn được của repo."""
    bc = _ghi_worker_log(tmp_path / "bc", [
        str(tmp_path / "hop" / ".venv-vieneu" / "python.exe"),
        str(bo_lai.GOC_REPO / "autodub" / "speech" / "tts" /
            "vieneu_worker.py"),
    ])
    with pytest.raises(bo_lai.Hong, match="cây mã nguồn"):
        bo_lai.kiem_duong_chay(bc, {}, [str(tmp_path / "hop")], "")


def test_duong_ngoai_hop_cat_la_hong(tmp_path):
    bc = _ghi_worker_log(tmp_path / "bc",
                         [str(tmp_path / "noi-khac" / "python.exe")])
    with pytest.raises(bo_lai.Hong, match="NGOÀI hộp cát"):
        bo_lai.kiem_duong_chay(bc, {}, [str(tmp_path / "hop")], "")


def test_ffmpeg_cua_may_la_ngoai_le_da_khai(tmp_path):
    """Gói cố ý KHÔNG kèm ffmpeg (HUONG_DAN_CAI_DAT.md Bước 1) — phải tha."""
    ffmpeg = tmp_path / "choco" / "bin" / "ffmpeg.exe"
    ffmpeg.parent.mkdir(parents=True)
    ffmpeg.write_text("")
    bc = _ghi_worker_log(tmp_path / "bc", [str(ffmpeg)])
    dong = bo_lai.kiem_duong_chay(bc, {}, [str(tmp_path / "hop")],
                                  str(ffmpeg))
    assert dong and "trong hộp cát" in dong[0]


def test_bo_may_da_chon_cung_bi_soi(tmp_path):
    """Không chỉ tiến trình con: bộ máy mà app CHỌN cũng phải trong hộp cát."""
    bc = _ghi_worker_log(tmp_path / "bc", [])
    ket = {"bo_may": {"vieneu": {"python": str(tmp_path / "ban-cu-la" /
                                               "python.exe"),
                                 "thu_muc_model": "", "san_sang": True}}}
    with pytest.raises(bo_lai.Hong, match="NGOÀI hộp cát"):
        bo_lai.kiem_duong_chay(bc, ket, [str(tmp_path / "hop")], "")


# ------------------------------------------------------------- hộp cát sạch --

def test_hop_cat_con_ban_cu_canh_ben_la_hong(tmp_path, monkeypatch):
    cha = tmp_path / "cha"
    cai = cha / "VoxDub Studio"
    cai.mkdir(parents=True)
    (cha / "VoxDub-Studio-v3.17.18").mkdir()
    with pytest.raises(bo_lai.Hong, match="cạnh bên"):
        bo_lai.kiem_hop_cat_sach(cai)


def test_hop_cat_sach_thi_qua(tmp_path):
    cai = tmp_path / "cha" / "VoxDub Studio"
    cai.mkdir(parents=True)
    dong = bo_lai.kiem_hop_cat_sach(cai)
    assert any("không có bản cài nào cạnh bên" in d for d in dong)


def test_hop_cat_nam_trong_repo_la_hong(tmp_path, monkeypatch):
    monkeypatch.setattr(bo_lai, "GOC_REPO", tmp_path)
    cai = tmp_path / "dist" / "VoxDub"
    cai.mkdir(parents=True)
    with pytest.raises(bo_lai.Hong, match="cây mã nguồn"):
        bo_lai.kiem_hop_cat_sach(cai)


# ------------------------------------------------------------------ giải nén --

def _zip_gia(duong: Path, tien_to: str = "") -> Path:
    with zipfile.ZipFile(duong, "w") as zf:
        zf.writestr(f"{tien_to}VoxDub.exe", "MZ")
        zf.writestr(f"{tien_to}scripts/setup_vieneu.py", "#")
    return duong


@pytest.mark.parametrize("tien_to", ["", "VoxDub Studio/"])
def test_nhan_ca_hai_dang_zip(tmp_path, tien_to):
    """Hai dạng zip cùng tồn tại thật; đoán sai gốc là kiểm một thư mục rỗng."""
    z = _zip_gia(tmp_path / "goi.zip", tien_to)
    cai = bo_lai.giai_nen(z, tmp_path / "ra")
    assert (cai / "VoxDub.exe").is_file()


def test_zip_khong_co_exe_la_hong(tmp_path):
    z = tmp_path / "rong.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("doc.txt", "x")
    with pytest.raises(bo_lai.Hong, match="KHÔNG có VoxDub.exe"):
        bo_lai.giai_nen(z, tmp_path / "ra")


# ------------------------------------------------------------- cài bộ máy ---

def test_thieu_tep_bat_trong_goi_thi_noi_ten_tep(tmp_path):
    """V80 tái bản: tệp thiếu khỏi gói phải ĐỎ kèm TÊN, không im lặng."""
    cai = tmp_path / "VoxDub Studio"
    cai.mkdir()
    with pytest.raises(bo_lai.Hong, match="Cai dat Whisper ASR.bat"):
        bo_lai.cai_bo_may(cai, "bat", 5)


def test_thieu_script_setup_trong_goi_thi_noi_ten_tep(tmp_path):
    cai = tmp_path / "VoxDub Studio"
    (cai / "scripts").mkdir(parents=True)
    with pytest.raises(bo_lai.Hong, match="setup_whisper.py"):
        bo_lai.cai_bo_may(cai, "script", 5)


def test_da_cai_roi_thi_khong_cai_lai(tmp_path):
    cai = tmp_path / "VoxDub Studio"
    for _ten, _bat, _script, venv, dau in bo_lai.BO_MAY_CAN:
        (cai / dau).parent.mkdir(parents=True, exist_ok=True)
        (cai / dau).write_text("{}")
        (cai / venv).mkdir(parents=True, exist_ok=True)
    dong = bo_lai.cai_bo_may(cai, "bat", 5)
    assert all("đã có sẵn" in d for d in dong)


# --------------------------------------------------------------- soi tệp ra --

def _thay_bo_do(monkeypatch, tieng="aac", muc=-16.3, giay_ra=54.0,
                giay_nguon=53.5):
    monkeypatch.setattr(bo_lai, "_ffprobe", lambda *a: tieng)
    monkeypatch.setattr(bo_lai, "_muc_am_trung_binh", lambda p: muc)
    monkeypatch.setattr(bo_lai, "_thoi_luong",
                        lambda p: giay_nguon if "clip" in str(p) else giay_ra)


def _tep_ra(tmp_path) -> tuple:
    nguon = tmp_path / "clip.mp4"
    nguon.write_bytes(b"0" * 10)
    ra = tmp_path / "dubbed_video.mp4"
    ra.write_bytes(b"1" * 4096)
    (tmp_path / "bc").mkdir()
    return nguon, ra, tmp_path / "bc"


def test_tep_ra_dat_thi_ghi_du_bang_chung(tmp_path, monkeypatch):
    _thay_bo_do(monkeypatch)
    nguon, ra, bc = _tep_ra(tmp_path)
    do = bo_lai.soi_video_ra(nguon, ra, bc)
    assert do["codec_tieng"] == "aac" and do["sha256"]
    assert json.loads((bc / "output-probe.json").read_text("utf-8"))["byte"]
    assert (bc / "output-video.sha256").read_text("utf-8").strip().endswith(
        "dubbed_video.mp4")


def test_khong_co_tep_ra_la_hong(tmp_path, monkeypatch):
    _thay_bo_do(monkeypatch)
    nguon, ra, bc = _tep_ra(tmp_path)
    ra.unlink()
    with pytest.raises(bo_lai.Hong, match="KHÔNG xuất được video"):
        bo_lai.soi_video_ra(nguon, ra, bc)


def test_khong_co_luong_tieng_la_hong(tmp_path, monkeypatch):
    _thay_bo_do(monkeypatch, tieng="")
    nguon, ra, bc = _tep_ra(tmp_path)
    with pytest.raises(bo_lai.Hong, match="KHÔNG có luồng tiếng"):
        bo_lai.soi_video_ra(nguon, ra, bc)


def test_tieng_cam_la_hong(tmp_path, monkeypatch):
    """Tệp ra "bình thường" nhưng CÂM — mã thoát nào cũng 0, chỉ số này bắt."""
    _thay_bo_do(monkeypatch, muc=-91.0)
    nguon, ra, bc = _tep_ra(tmp_path)
    with pytest.raises(bo_lai.Hong, match="CÂM"):
        bo_lai.soi_video_ra(nguon, ra, bc)


def test_khong_do_duoc_muc_am_la_hong(tmp_path, monkeypatch):
    _thay_bo_do(monkeypatch, muc=None)
    nguon, ra, bc = _tep_ra(tmp_path)
    with pytest.raises(bo_lai.Hong, match="Không đo được mức âm"):
        bo_lai.soi_video_ra(nguon, ra, bc)


def test_thoi_luong_lech_qua_nhieu_la_hong(tmp_path, monkeypatch):
    _thay_bo_do(monkeypatch, giay_ra=10.0)
    nguon, ra, bc = _tep_ra(tmp_path)
    with pytest.raises(bo_lai.Hong, match="Thời lượng lệch"):
        bo_lai.soi_video_ra(nguon, ra, bc)


def test_dung_lai_dung_nguong_cua_cong_kiem_ma_nguon():
    """Hai định nghĩa 'câm' khác nhau thì sớm muộn chúng nói ngược nhau."""
    import kiem_chay_that

    for ten in ("_ffprobe", "_muc_am_trung_binh", "_thoi_luong",
                "_viet_ban_dich_tay"):
        assert getattr(bo_lai, ten) is getattr(kiem_chay_that, ten)


# ------------------------------------------------- giữ nguyên vẹn bản cũ ---

def _ban_cu_gia(goc: Path) -> Path:
    (goc / "models" / "vieneu").mkdir(parents=True)
    (goc / "models" / "vieneu" / "installed_ok.json").write_text("{}")
    (goc / ".env").write_text("VOXDUB_TOKEN=gia\n")
    (goc / "data").mkdir()
    (goc / "data" / "app.dll").write_text("nhi phan")
    return goc


def test_bat_duoc_tep_bi_sua_va_bi_xoa(tmp_path):
    cu = _ban_cu_gia(tmp_path / "VoxDub-previous")
    truoc = manifest_thu_muc(str(cu))
    (cu / ".env").write_text("VOXDUB_TOKEN=bi-ghi-de\n")
    (cu / "data" / "app.dll").unlink()
    khac = so_sanh_manifest(truoc, manifest_thu_muc(str(cu)))
    assert khac["sua_doi"] == [".env"]
    assert khac["bi_xoa"] == ["data/app.dll"]
    assert khac["nguyen_ven"] is False


def test_them_tep_moi_khong_bi_tinh_la_pha_hoai(tmp_path):
    cu = _ban_cu_gia(tmp_path / "VoxDub-previous")
    truoc = manifest_thu_muc(str(cu))
    (cu / "logs").mkdir()
    (cu / "logs" / "voxdub.log").write_text("dòng mới")
    khac = so_sanh_manifest(truoc, manifest_thu_muc(str(cu)))
    assert khac["nguyen_ven"] is True and khac["them_moi"]


def test_thu_muc_nang_chi_dem_tep_va_byte(tmp_path):
    """`.venv-*`/`models/` có hàng chục nghìn tệp — băm hết là hàng phút CI."""
    cu = tmp_path / "VoxDub-previous"
    (cu / ".venv-vieneu" / "Lib").mkdir(parents=True)
    (cu / ".venv-vieneu" / "Lib" / "a.py").write_text("x")
    m = manifest_thu_muc(str(cu))
    assert m["thu_muc_nang"][".venv-vieneu"]["so_tep"] == 1
    assert not any(k.startswith(".venv-vieneu") for k in m["tep"])

    (cu / ".venv-vieneu" / "Lib" / "a.py").unlink()
    khac = so_sanh_manifest(m, manifest_thu_muc(str(cu)))
    assert khac["thu_muc_nang_doi"] == [".venv-vieneu"]
    assert khac["nguyen_ven"] is False

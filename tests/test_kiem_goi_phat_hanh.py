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


def test_thu_muc_nang_ghi_ten_va_kich_thuoc_khong_bam(tmp_path):
    """`.venv-*` đo thật 20.388 tệp — băm hết là hàng phút CI mỗi lần chụp.

    Nhưng chỉ đếm tệp/byte thì người đọc bằng chứng chỉ biết "có thứ gì đó
    đổi" rồi tắc. Nên: tên + kích thước từng tệp, không băm.
    """
    cu = tmp_path / "VoxDub-previous"
    (cu / ".venv-vieneu" / "Lib").mkdir(parents=True)
    (cu / ".venv-vieneu" / "Lib" / "a.py").write_text("xin chao")
    (cu / "models" / "vieneu").mkdir(parents=True)
    (cu / "models" / "vieneu" / "m.onnx").write_bytes(b"0" * 100)

    m = manifest_thu_muc(str(cu))
    venv = m["thu_muc_nang"][".venv-vieneu"]
    assert venv["so_tep"] == 1 and venv["tong_byte"] == 8
    assert venv["tep"] == {".venv-vieneu/Lib/a.py": 8}
    assert m["thu_muc_nang"]["models"]["tep"] == {"models/vieneu/m.onnx": 100}
    assert not any(k.startswith((".venv-vieneu", "models")) for k in m["tep"]), (
        "thư mục nặng KHÔNG được băm"
    )


# ------------------ THÊM thì được, MẤT và ĐỔI thì không (chính sách I0-E) --
#
# Run 35621763885 đỏ oan ở đúng chỗ này: `models/` của bản cũ đi từ 39 tệp lên
# 51 tệp (+231.946.522 byte) trong khi `.venv-vieneu` (20.388 tệp) và
# `.venv-whisper` (4.557 tệp) không đổi một byte. Đó là hành vi ĐÚNG của thiết
# kế "dùng lại tại chỗ, không chép": sau nâng cấp, models/ của bản cũ CHÍNH LÀ
# kho model dùng chung, thiếu model thì tải về đúng đó. Chốt cũ bắt mọi thay
# đổi số byte là vi phạm — quá thô, và nó chặn đúng cái mà I0-E đang canh.

#: Kích thước 12 tệp model mới, cộng lại đúng bằng số đo thật của lượt chạy.
_THEM_THAT = [19_328_876] * 11 + [231_946_522 - 19_328_876 * 11]


def _kho_model_39_tep() -> dict:
    tep = {f"models/vieneu/tep_{i:02d}.onnx": 133_284_800 + i
           for i in range(39)}
    return {"goc": "X", "tep": {},
            "thu_muc_nang": {"models": {
                "so_tep": len(tep), "tong_byte": sum(tep.values()),
                "tep": tep}}}


def test_them_tep_vao_kho_model_dung_chung_la_HOP_LE():
    """Chiều 1: đúng số đo của run 35621763885 — 39 → 51 tệp, phải XANH."""
    truoc = _kho_model_39_tep()
    sau = json.loads(json.dumps(truoc))
    moi = {f"models/whisper/them_{i:02d}.bin": byte
           for i, byte in enumerate(_THEM_THAT)}
    sau["thu_muc_nang"]["models"]["tep"].update(moi)
    sau["thu_muc_nang"]["models"]["so_tep"] = 51
    sau["thu_muc_nang"]["models"]["tong_byte"] += 231_946_522

    khac = so_sanh_manifest(truoc, sau)
    assert khac["nguyen_ven"] is True, (
        "cấm THÊM là buộc mỗi lần nâng cấp phải nhân đôi 5,4 GB model — đi "
        "ngược đúng lời hứa mà I0-E đang canh")
    assert khac["nang_bi_mat"] == [] and khac["nang_doi_kich_thuoc"] == []
    assert len(khac["them_moi_trong_thu_muc_nang"]) == 12
    assert khac["them_moi_trong_thu_muc_nang"][0].startswith("models/whisper/")
    assert (sau["thu_muc_nang"]["models"]["tong_byte"]
            - truoc["thu_muc_nang"]["models"]["tong_byte"]) == 231_946_522


def test_xoa_tep_cu_trong_thu_muc_nang_la_VI_PHAM():
    """Chiều 2a: mất tệp của bản cũ = đúng thứ I0-E cấm."""
    truoc = _kho_model_39_tep()
    sau = json.loads(json.dumps(truoc))
    mat = sau["thu_muc_nang"]["models"]["tep"].pop("models/vieneu/tep_07.onnx")
    sau["thu_muc_nang"]["models"]["so_tep"] -= 1
    sau["thu_muc_nang"]["models"]["tong_byte"] -= mat

    khac = so_sanh_manifest(truoc, sau)
    assert khac["nguyen_ven"] is False
    assert khac["nang_bi_mat"] == ["models/vieneu/tep_07.onnx"]


def test_doi_kich_thuoc_tep_cu_la_VI_PHAM():
    """Chiều 2b: ghi đè tệp cũ — kể cả khi tổng byte TĂNG lên."""
    truoc = _kho_model_39_tep()
    sau = json.loads(json.dumps(truoc))
    sau["thu_muc_nang"]["models"]["tep"]["models/vieneu/tep_07.onnx"] += 999
    sau["thu_muc_nang"]["models"]["tong_byte"] += 999

    khac = so_sanh_manifest(truoc, sau)
    assert khac["nguyen_ven"] is False
    assert khac["nang_doi_kich_thuoc"] == [
        "models/vieneu/tep_07.onnx (133284807 → 133285806 byte)"]


def test_ca_thu_muc_nang_bien_mat_la_VI_PHAM():
    truoc = _kho_model_39_tep()
    sau = {"goc": "X", "tep": {}, "thu_muc_nang": {}}
    khac = so_sanh_manifest(truoc, sau)
    assert khac["nguyen_ven"] is False
    assert khac["nang_bi_mat"] == ["models/** (cả thư mục biến mất)"]


def test_thieu_danh_sach_thi_chi_ket_luan_duoc_ve_MAT():
    """Ảnh chụp không có danh sách tệp: phải nói ra là mình đang mù."""
    truoc = {"thu_muc_nang": {"models": {"so_tep": 39, "tong_byte": 1000}}}
    tang = {"thu_muc_nang": {"models": {"so_tep": 51, "tong_byte": 2000}}}
    giam = {"thu_muc_nang": {"models": {"so_tep": 30, "tong_byte": 900}}}

    khac = so_sanh_manifest(truoc, tang)
    assert khac["nguyen_ven"] is True
    assert khac["thu_muc_nang_khong_so_duoc"] == ["models"]

    khac = so_sanh_manifest(truoc, giam)
    assert khac["nguyen_ven"] is False
    assert khac["nang_bi_mat"] == ["models/** (số tệp hoặc byte GIẢM)"]


def test_thu_muc_nang_khong_doi_thi_nguyen_ven(tmp_path):
    """`.venv-*` không đổi một byte (đúng như đo thật) → xanh."""
    cu = tmp_path / "VoxDub-previous"
    (cu / ".venv-whisper" / "Scripts").mkdir(parents=True)
    (cu / ".venv-whisper" / "Scripts" / "python.exe").write_bytes(b"MZ")
    m = manifest_thu_muc(str(cu))
    khac = so_sanh_manifest(m, manifest_thu_muc(str(cu)))
    assert khac["nguyen_ven"] is True
    assert khac["them_moi_trong_thu_muc_nang"] == []



# ------------------------------------------------- ĐƯỜNG DẪN QUA RANH GIỚI --
#
# Lỗi thật, run CI 35614850573 (lượt chạy Windows ĐẦU TIÊN của cổng này):
# workflow gọi `--bang-chung packaged-dub-evidence` (tương đối). Bộ lái đứng ở
# gốc repo nên tự ghi đúng chỗ, nhưng nó CHUYỂN nguyên chuỗi đó cho
# `VoxDub.exe`, mà exe được chạy với `cwd` = thư mục cài trong hộp cát. Exe
# chạy đúng, báo thiếu bộ máy đúng, trả đúng mã 5 — và ghi `result.json` vào
# trong hộp cát rồi biến mất cùng runner. Bộ lái đọc phải thư mục rỗng và kết
# luận NGƯỢC HẲN: "bản đóng gói KHÔNG báo thiếu".
#
# Không bộ test nào trước đó chạm tới được: test đơn vị gọi `chay()` trong
# CÙNG tiến trình với đường dẫn tuyệt đối của `tmp_path`, còn lượt chạy thử
# với exe GIẢ trên Linux cũng được gọi bằng `--bang-chung` tuyệt đối. Seam
# hỏng nằm đúng ở chỗ hai tiến trình có hai thư mục làm việc khác nhau.

def _exe_gia(thu_muc: Path) -> Path:
    """`VoxDub.exe` giả: ghi result.json vào abspath(--bang-chung) của CHÍNH nó."""
    thu_muc.mkdir(parents=True, exist_ok=True)
    exe = thu_muc / "VoxDub.exe"
    exe.write_text(
        "#!/usr/bin/env bash\n"
        'BC=""\n'
        'while [ $# -gt 0 ]; do case "$1" in --bang-chung) BC="$2"; shift 2;;'
        ' *) shift;; esac; done\n'
        '[ -n "$BC" ] || exit 9\n'
        'mkdir -p "$BC"\n'
        'printf \'{"ket_qua":"hong","giai_doan_hong":"bo_may_thieu",'
        '"bo_may_thieu":["vieneu"],"cwd":"%s"}\\n\' "$PWD" > "$BC/result.json"\n'
        "exit 5\n", encoding="utf-8")
    exe.chmod(0o755)
    return exe


@pytest.mark.skipif(os.name == "nt", reason="exe giả viết bằng bash")
def test_duong_dan_tuyet_doi_thi_doc_lai_duoc_ket_qua(tmp_path):
    """Bằng chứng chỉ đọc lại được khi bộ lái đưa đường dẫn TUYỆT ĐỐI."""
    exe = _exe_gia(tmp_path / "VoxDub Studio")
    bc = tmp_path / "bang-chung"
    kq, ket = bo_lai.chay_exe(exe, ["--tu-kiem-goi", "--chi-do-dac",
                                    "--bang-chung", str(bc)], bc, 60)
    assert kq.returncode == 5
    assert ket["giai_doan_hong"] == "bo_may_thieu"
    # exe chạy ở thư mục cài, KHÔNG phải thư mục của bộ lái — chính chỗ này
    # là thứ làm đường dẫn tương đối rơi vào hố.
    assert Path(ket["cwd"]).resolve() == exe.parent.resolve()


@pytest.mark.skipif(os.name == "nt", reason="exe giả viết bằng bash")
def test_duong_dan_tuong_doi_bi_chan_truoc_khi_chay(tmp_path, monkeypatch):
    """Ca đã làm CI đỏ: đưa đường tương đối qua ranh giới hai thư mục làm việc."""
    exe = _exe_gia(tmp_path / "VoxDub Studio")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(bo_lai.Hong, match="TƯƠNG ĐỐI"):
        bo_lai.chay_exe(exe, ["--tu-kiem-goi", "--chi-do-dac",
                              "--bang-chung", "bang-chung/sach"],
                        tmp_path / "bang-chung" / "sach", 60)


def test_thu_muc_bang_chung_phai_tuyet_doi(tmp_path, monkeypatch):
    exe = tmp_path / "VoxDub.exe"
    exe.write_text("")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(bo_lai.Hong, match="tuyệt đối"):
        bo_lai.chay_exe(exe, [], Path("bc-tuong-doi"), 5)


def test_chuan_hoa_duong_dan_ngay_tai_cua_vao(tmp_path, monkeypatch):
    """Chuẩn hoá một cửa, thay vì nhớ gọi abspath ở tám chỗ gọi."""
    monkeypatch.chdir(tmp_path)

    class _Args:
        bang_chung = "packaged-dub-evidence"
        goc_thu = "hop"
        video = "clip.mp4"
        zip = "goi.zip"

    a = _Args()
    bo_lai.chuan_hoa_duong_dan(a)
    for ten in ("bang_chung", "goc_thu", "video", "zip"):
        gia_tri = getattr(a, ten)
        assert os.path.isabs(gia_tri), ten
        assert gia_tri.startswith(str(tmp_path.resolve()))


# ---------------------------------------- hai ca hỏng phải nói KHÁC nhau ---

class _KqGia:
    def __init__(self, ma):
        self.returncode = ma


def test_mat_bang_chung_va_san_pham_sai_la_hai_cau_khac_nhau(tmp_path):
    """Câu lỗi đúng một nửa chỉ người đọc đi chẩn sai chỗ — đúng chuyện đã xảy ra."""
    with pytest.raises(bo_lai.Hong, match="KHÔNG ghi result.json"):
        bo_lai.kiem_bao_thieu_bo_may(_KqGia(5), {}, tmp_path)

    with pytest.raises(bo_lai.Hong, match="KHÔNG báo thiếu"):
        bo_lai.kiem_bao_thieu_bo_may(_KqGia(0), {"giai_doan_hong": None},
                                     tmp_path)

    bo_lai.kiem_bao_thieu_bo_may(_KqGia(5),
                                 {"giai_doan_hong": "bo_may_thieu"}, tmp_path)


def test_main_that_su_goi_chuan_hoa(tmp_path, monkeypatch, capsys):
    """Có hàm chuẩn hoá mà quên GỌI thì y như không có."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", [
        "kiem_goi_phat_hanh.py", "--che-do", "sach",
        "--zip", "khong-co-that.zip", "--goc-thu", "hop",
        "--bang-chung", "bang-chung"])
    assert bo_lai.main() == 2
    loi = capsys.readouterr().err
    assert str(tmp_path.resolve()) in loi, (
        "câu lỗi phải in đường dẫn TUYỆT ĐỐI — nó là bằng chứng rằng bộ lái "
        f"đã chuẩn hoá trước khi dùng: {loi!r}")


# ---------------------------------------- BỘ DÒ KÊU NHẦM (run 35618355094) --
#
# Lượt chạy Windows THỨ HAI: bản đóng gói dub xong thật (aac, −18,5 dB, 54,4s
# so với nguồn 53,5s, 42 tiến trình con, không một đường nào dưới gốc repo) —
# nhưng cổng vẫn đỏ vì bộ dò kêu nhầm HAI lớp:
#
#   1. coi mọi chuỗi có dấu ":" là đường dẫn → `-b:v`, `-c:v`,
#      `color=black:s=256x256:d=0.1` bị kể là tệp;
#   2. tính "mượn cây mã nguồn" = "ngoài vùng cho phép", nên ba chuỗi đó bị
#      gán nhãn nặng nhất mà bộ canh có.
#
# Với một bộ canh, kêu nhầm tệ hơn bỏ sót: bỏ sót thì mất một lần phát hiện,
# kêu nhầm thì mất CẢ CÁI CHỐT (FEATURES.md §6, bài học D5 ở 1a21d34). Nên
# phải khoá CẢ HAI CHIỀU.

#: Nguyên văn từ `duong-da-dung.json` của run 35618355094.
CO_FFMPEG_THAT = ["-b:v", "-c:v", "color=black:s=256x256:d=0.1", "-hide_banner",
                  "volumedetect", "format=yuv420p", "-f", "null"]


def _ghi_lan_chay(thu_muc: Path, chuong_trinh: str, tham_so: list,
                  cwd: str) -> Path:
    thu_muc.mkdir(parents=True, exist_ok=True)
    with open(thu_muc / "worker-launches.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"chuong_trinh": chuong_trinh,
                            "tham_so": tham_so, "cwd": cwd}) + "\n")
    return thu_muc


def test_co_va_bo_loc_ffmpeg_KHONG_bi_ke_la_duong_dan(tmp_path, monkeypatch):
    """Chiều 1: thứ không phải đường dẫn thì không được kêu."""
    hop = tmp_path / "hop"
    # Đứng ở gốc repo lúc soi — đúng cảnh của bộ lái trên CI, và đúng cơ chế
    # đã biến `-b:v` thành "tệp trong cây mã nguồn".
    monkeypatch.chdir(bo_lai.GOC_REPO)
    bc = _ghi_lan_chay(tmp_path / "bc", str(hop / "ffmpeg.exe"),
                       CO_FFMPEG_THAT, str(hop))
    dong = bo_lai.kiem_duong_chay(bc, {}, [str(hop)], "")
    assert dong and "trong hộp cát" in dong[0]
    soi = json.loads((bc / "duong-da-dung.json").read_text(encoding="utf-8"))
    assert soi["ngoai_vung"] == [] and soi["tu_cay_ma_nguon"] == []
    for co in CO_FFMPEG_THAT:
        assert co not in soi["tat_ca"], f"{co!r} không phải đường dẫn"
        assert co in soi["khong_phai_duong_dan"], (
            "thứ bị bộ lọc bỏ qua phải liệt kê ra được — bộ lọc không ai "
            "kiểm được thì chính nó là chỗ giấu lỗi")


@pytest.mark.parametrize("chuoi", CO_FFMPEG_THAT)
def test_tung_co_ffmpeg_khong_phai_duong_dan(chuoi):
    assert bo_lai.la_duong_dan(chuoi) is False


@pytest.mark.parametrize("chuoi", [
    r"D:\a\_temp\hop\VoxDub Studio\.venv-whisper\Scripts\python.exe",
    "/usr/bin/ffmpeg", r"..\..\autodub\speech\asr_whisper_worker.py",
    "autodub/speech/vieneu_worker.py", "C:/Windows/system32/cmd.exe",
])
def test_duong_dan_that_van_duoc_nhan(chuoi):
    assert bo_lai.la_duong_dan(chuoi) is True


def test_duong_TUYET_DOI_trong_cay_ma_nguon_van_do(tmp_path):
    """Chiều 2: ca thật vẫn phải đỏ — mượn tệp của repo."""
    hop = tmp_path / "hop"
    that = bo_lai.GOC_REPO / "autodub" / "speech" / "asr_whisper_worker.py"
    bc = _ghi_lan_chay(tmp_path / "bc", str(hop / "python.exe"),
                       [str(that)], str(hop))
    with pytest.raises(bo_lai.Hong, match="cây mã nguồn"):
        bo_lai.kiem_duong_chay(bc, {}, [str(hop)], "")


def test_duong_TUONG_DOI_leo_ra_cay_ma_nguon_van_do(tmp_path):
    """Ca khó: đường tương đối, giải theo cwd của lượt gọi thì rơi vào repo."""
    cwd = str(bo_lai.GOC_REPO / "dist" / "VoxDub")
    bc = _ghi_lan_chay(tmp_path / "bc", "python.exe",
                       [r"..\..\autodub\speech\asr_whisper_worker.py"
                        if os.sep == "\\"
                        else "../../autodub/speech/asr_whisper_worker.py"],
                       cwd)
    with pytest.raises(bo_lai.Hong, match="cây mã nguồn"):
        bo_lai.kiem_duong_chay(bc, {}, [str(tmp_path / "hop")], "")


def test_ngoai_hop_cat_KHAC_muon_ma_nguon(tmp_path):
    """Hai khái niệm phải tách: ngoài vùng ≠ mượn cây mã nguồn."""
    hop = tmp_path / "hop"
    la = tmp_path / "noi-khac" / "python.exe"
    bc = _ghi_lan_chay(tmp_path / "bc", str(la), [], str(hop))
    with pytest.raises(bo_lai.Hong, match="NGOÀI hộp cát"):
        bo_lai.kiem_duong_chay(bc, {}, [str(hop)], "")
    soi = json.loads((bc / "duong-da-dung.json").read_text(encoding="utf-8"))
    assert soi["ngoai_vung"] == [str(la)]
    assert soi["tu_cay_ma_nguon"] == [], (
        "gán nhãn 'mượn mã nguồn' cho một đường chỉ vì nó ngoài vùng là làm "
        "hỏng chính cái nhãn đó")
    assert soi["goc_repo"] == str(bo_lai.GOC_REPO)


def test_duong_tuong_doi_trong_hop_cat_khong_bi_keu(tmp_path, monkeypatch):
    """Chuỗi lọt lưới lọc được giải theo cwd của lượt gọi → vẫn trong hộp cát."""
    monkeypatch.chdir(bo_lai.GOC_REPO)
    hop = tmp_path / "hop"
    bc = _ghi_lan_chay(tmp_path / "bc", str(hop / "ffmpeg.exe"),
                       ["scale=trunc(iw/2)*2", "data/seg_00001.wav"], str(hop))
    dong = bo_lai.kiem_duong_chay(bc, {}, [str(hop)], "")
    assert dong and "trong hộp cát" in dong[0]


def test_bo_may_da_chon_van_bi_soi_sau_ban_va(tmp_path):
    """Bản vá không được làm mất độ nhạy với bộ máy app đã chọn."""
    hop = tmp_path / "hop"
    bc = _ghi_lan_chay(tmp_path / "bc", str(hop / "ffmpeg.exe"), [], str(hop))
    ket = {"bo_may": {"vieneu": {
        "python": str(tmp_path / "ban-cu-la" / "python.exe"),
        "thu_muc_model": "", "san_sang": True}}}
    with pytest.raises(bo_lai.Hong, match="NGOÀI hộp cát"):
        bo_lai.kiem_duong_chay(bc, ket, [str(hop)], "")


# ------------------------------------------ NÂNG CẤP LIÊN PHIÊN BẢN (I0-E) --
#
# Giới hạn (2) của mục TEST_LOG I0-FDE(e): "bản cũ" được dựng từ CHÍNH gói ứng
# viên. Lượt đó chứng minh được CƠ CHẾ dùng lại bộ máy, nhưng người dùng thật
# không bao giờ nâng cấp từ chính bản họ đang cài — họ nâng từ bản phát hành
# trước đó. Những phép kiểm dưới đây khoá đúng các cách mà bản vá này có thể
# tụt về tình trạng cũ mà vẫn xanh:
#
#   * trỏ nhầm cả hai bên vào cùng một gói (xanh, không kiểm gì);
#   * bước tải hỏng mà cổng lặng lẽ rơi về gói ứng viên (xanh giả);
#   * chép sha256 của GitHub API vào bằng chứng thay vì tự băm lại;
#   * tải thiếu byte mà vẫn dựng "bản cũ" từ tệp cụt.


class _ArgsGia:
    """Bộ tham số tối thiểu cho các hàm của bộ lái (thay cho argparse)."""

    def __init__(self, zip_moi, zip_cu="", nguon="", sha="abc123"):
        self.zip = str(zip_moi)
        self.zip_ban_cu = str(zip_cu)
        self.nguon_ban_cu = str(nguon)
        self.sha = sha
        self.cai_dat = "script"
        self.timeout = 5
        self.goc_thu = ""


def _hai_goi_khac_nhau(tmp_path) -> tuple:
    """Hai gói phát hành KHÁC nội dung — hình dạng thật của ca liên phiên bản."""
    cu = tmp_path / "VoxDub-Studio-v3.17.19-win64.zip"
    moi = tmp_path / "VoxDub-Studio-main-win64.zip"
    with zipfile.ZipFile(cu, "w") as zf:
        zf.writestr("VoxDub.exe", "MZ bản cũ")
        zf.writestr("scripts/setup_vieneu.py", "# bản cũ")
        zf.writestr("chi-co-o-ban-cu.txt", "x")
    with zipfile.ZipFile(moi, "w") as zf:
        zf.writestr("VoxDub.exe", "MZ bản MỚI khác hẳn")
        zf.writestr("scripts/setup_vieneu.py", "# bản cũ")
        zf.writestr("chi-co-o-ban-moi.txt", "y")
    return cu, moi


def test_khong_co_co_thi_ban_cu_van_la_goi_ung_vien(tmp_path):
    """Đường đang XANH không được đụng tới: không có cờ = y như trước."""
    _cu, moi = _hai_goi_khac_nhau(tmp_path)
    assert bo_lai._zip_ban_cu(_ArgsGia(moi)) == Path(moi)


def test_co_co_thi_ban_cu_la_goi_phat_hanh_that(tmp_path):
    cu, moi = _hai_goi_khac_nhau(tmp_path)
    assert bo_lai._zip_ban_cu(_ArgsGia(moi, cu)) == Path(cu)


def test_mat_goi_ban_cu_la_BI_CHAN_chu_khong_roi_ve_goi_ung_vien(tmp_path):
    """Bước tải hỏng thì phải DỪNG — rơi về gói ứng viên là xanh mà rỗng."""
    _cu, moi = _hai_goi_khac_nhau(tmp_path)
    args = _ArgsGia(moi, tmp_path / "khong-co-that.zip")
    with pytest.raises(bo_lai.BiChan, match="xanh mà KHÔNG kiểm"):
        bo_lai._zip_ban_cu(args)


def test_bang_chung_nguon_goc_du_truong_va_sha256_la_TU_BAM(tmp_path):
    """Sáu tháng sau vẫn phải trả lời được: bản 'cũ' này từ đâu ra."""
    import hashlib

    cu, moi = _hai_goi_khac_nhau(tmp_path)
    nguon = tmp_path / "nguon.json"
    nguon.write_text(json.dumps({
        "tag": "v3.17.19", "ten_asset": cu.name,
        "url_release": "https://github.com/junnyken/voxdub-studio/releases/"
                       "tag/v3.17.19",
        "url_asset": "https://api.github.com/repos/junnyken/voxdub-studio/"
                     "releases/assets/565214095",
        "byte": cu.stat().st_size, "tai_luc": "2026-09-22T00:00:00+00:00",
    }, ensure_ascii=False), encoding="utf-8")
    bc = tmp_path / "bc"

    dong = bo_lai.ghi_nguon_ban_cu(_ArgsGia(moi, cu, nguon), bc, cu)

    ho_so = json.loads((bc / "previous-artifact.json").read_text("utf-8"))
    assert ho_so["che_do_ban_cu"] == "gói phát hành riêng"
    assert ho_so["ten_tep"] == cu.name
    assert ho_so["byte"] == cu.stat().st_size
    # sha256 phải là số TỰ BĂM từ tệp trên đĩa — tính lại độc lập ở đây.
    assert ho_so["sha256"] == hashlib.sha256(cu.read_bytes()).hexdigest()
    assert ho_so["tu_bam_luc"] and ho_so["nguon_khai_bao"]["tag"] == "v3.17.19"
    assert "releases/tag/v3.17.19" in ho_so["nguon_khai_bao"]["url_release"]
    # và phải chứng minh được HAI GÓI KHÁC NHAU THẬT, không chỉ khác tên tệp.
    khac = ho_so["khac_goi_ung_vien"]
    assert khac["so_tep_khac_noi_dung"] == 1        # VoxDub.exe
    assert khac["so_tep_chi_co_o_ban_cu"] == 1
    assert khac["so_tep_chi_co_o_ban_moi"] == 1
    assert any("GÓI PHÁT HÀNH THẬT" in d for d in dong)


def test_hai_ben_cung_mot_goi_la_HONG(tmp_path):
    """Trỏ nhầm cả hai bên vào một gói: xanh mà không kiểm gì — phải ĐỎ."""
    _cu, moi = _hai_goi_khac_nhau(tmp_path)
    ban_sao = tmp_path / "ban-sao.zip"
    ban_sao.write_bytes(moi.read_bytes())
    with pytest.raises(bo_lai.Hong, match="TRÙNG KHÍT"):
        bo_lai.ghi_nguon_ban_cu(_ArgsGia(moi, ban_sao), tmp_path / "bc",
                                ban_sao)


def test_khac_ten_nhung_trung_noi_dung_tung_tep_la_HONG(tmp_path):
    """Đổi tên một gói không làm nên phép kiểm nâng cấp."""
    moi = tmp_path / "moi.zip"
    cu = tmp_path / "VoxDub-Studio-v3.17.19-win64.zip"
    for duong, ghi_chu in ((moi, "a"), (cu, "b")):
        with zipfile.ZipFile(duong, "w") as zf:
            zf.writestr("VoxDub.exe", "MZ")
        # khác byte ở vỏ zip (chú thích), giống hệt từng tệp bên trong
        with zipfile.ZipFile(duong, "a") as zf:
            zf.comment = ghi_chu.encode()
    with pytest.raises(bo_lai.Hong, match="trùng nội dung|KHÔNG tệp nào"):
        bo_lai.ghi_nguon_ban_cu(_ArgsGia(moi, cu), tmp_path / "bc", cu)


def test_tai_thieu_byte_la_HONG(tmp_path):
    """Ca hỏng im lặng của curl: tệp cụt vẫn mang đúng tên."""
    cu, moi = _hai_goi_khac_nhau(tmp_path)
    nguon = tmp_path / "nguon.json"
    nguon.write_text(json.dumps({"tag": "v3.17.19",
                                 "byte": cu.stat().st_size + 4096}),
                     encoding="utf-8")
    with pytest.raises(bo_lai.Hong, match="tải thiếu|Tải thiếu"):
        bo_lai.ghi_nguon_ban_cu(_ArgsGia(moi, cu, nguon), tmp_path / "bc", cu)


def test_sha256_lech_so_nguon_khai_la_HONG(tmp_path):
    """Tệp trên đĩa không phải tệp bước tải tưởng mình lấy."""
    cu, moi = _hai_goi_khac_nhau(tmp_path)
    nguon = tmp_path / "nguon.json"
    nguon.write_text(json.dumps({"tag": "v3.17.19", "sha256": "0" * 64}),
                     encoding="utf-8")
    with pytest.raises(bo_lai.Hong, match="SHA-256 tự tính"):
        bo_lai.ghi_nguon_ban_cu(_ArgsGia(moi, cu, nguon), tmp_path / "bc", cu)


def test_bang_chung_van_duoc_ghi_tren_duong_HONG(tmp_path):
    """Bằng chứng của lượt ĐỎ là thứ đáng giá nhất — đừng để nó rỗng."""
    _cu, moi = _hai_goi_khac_nhau(tmp_path)
    ban_sao = tmp_path / "ban-sao.zip"
    ban_sao.write_bytes(moi.read_bytes())
    bc = tmp_path / "bc"
    with pytest.raises(bo_lai.Hong):
        bo_lai.ghi_nguon_ban_cu(_ArgsGia(moi, ban_sao), bc, ban_sao)
    ho_so = json.loads((bc / "previous-artifact.json").read_text("utf-8"))
    assert ho_so["ket_luan"] == "hai gói trùng khít"
    assert ho_so["sha256"]


def test_cung_goi_thi_bang_chung_phai_TU_KHAI_gioi_han(tmp_path):
    """Không có cờ thì vẫn chạy — nhưng không được im lặng như đã kiểm đủ."""
    _cu, moi = _hai_goi_khac_nhau(tmp_path)
    bc = tmp_path / "bc"
    dong = bo_lai.ghi_nguon_ban_cu(_ArgsGia(moi), bc, Path(moi))
    ho_so = json.loads((bc / "previous-artifact.json").read_text("utf-8"))
    assert ho_so["che_do_ban_cu"] == "cùng gói ứng viên"
    assert "KHÔNG chứng minh nâng cấp liên phiên bản" in ho_so["ket_luan"]
    assert any("chỉ chứng minh cơ chế" in d for d in dong)
    assert "cùng gói ứng viên" in bo_lai._mo_ta_ban_cu(ho_so)


class _Dung(Exception):
    """Chốt dừng: đã đi qua đúng chỗ cần đo thì không chạy tiếp nữa."""


def test_che_do_nang_cap_noi_dung_goi_vao_dung_ben(tmp_path, monkeypatch):
    """Bản CŨ từ gói phát hành cũ, bản MỚI từ gói ứng viên — không hoán đổi.

    Đây là phép kiểm giữ cho bản vá không tự lặng lẽ quay về: đổi một trong
    hai lượt gọi về `zip_goc` là test này đỏ ngay, trong khi mọi phép kiểm
    khác vẫn xanh (đúng cách mà giới hạn (2) đã sống sót qua bốn lượt CI).
    """
    cu, moi = _hai_goi_khac_nhau(tmp_path)
    goi_vao = {}

    def _dung_ban_cu_gia(nguon_zip, thu_muc, args):
        goi_vao["ban_cu"] = Path(nguon_zip)
        thu_muc.mkdir(parents=True, exist_ok=True)
        return thu_muc

    def _giai_nen_gia(tep_zip, dich):
        goi_vao["ban_moi"] = Path(tep_zip)
        dich.mkdir(parents=True, exist_ok=True)
        return dich

    monkeypatch.setattr(bo_lai, "_dung_ban_cu", _dung_ban_cu_gia)
    monkeypatch.setattr(bo_lai, "giai_nen", _giai_nen_gia)
    monkeypatch.setattr(bo_lai, "manifest_thu_muc",
                        lambda *a, **k: (_ for _ in ()).throw(_Dung()))

    args = _ArgsGia(moi, cu)
    args.goc_thu = str(tmp_path / "hop")
    with pytest.raises(_Dung):
        bo_lai.che_do_nang_cap(args, tmp_path / "bc")

    assert goi_vao["ban_cu"] == Path(cu), "bản cũ phải dựng từ gói phát hành cũ"
    assert goi_vao["ban_moi"] == Path(moi), "bản mới phải là gói ứng viên"
    assert (tmp_path / "bc" / "previous-artifact.json").is_file(), (
        "nguồn gốc phải ghi TRƯỚC khi dựng — dựng mất vài phút, hỏng giữa "
        "chừng mà chưa ghi thì không ai biết đã tải phải tệp nào")


def test_ca_am_cung_dung_goi_phat_hanh_cu(tmp_path, monkeypatch):
    """Ba ca âm không cần biến thể riêng: chúng thừa hưởng chính bản cũ đó."""
    cu, moi = _hai_goi_khac_nhau(tmp_path)
    goi_vao = {}

    def _dung_ban_cu_gia(nguon_zip, thu_muc, args):
        goi_vao["ban_cu"] = Path(nguon_zip)
        thu_muc.mkdir(parents=True, exist_ok=True)
        return thu_muc

    monkeypatch.setattr(bo_lai, "_dung_ban_cu", _dung_ban_cu_gia)
    monkeypatch.setattr(bo_lai, "giai_nen",
                        lambda z, d: (d.mkdir(parents=True, exist_ok=True), d)[1])
    monkeypatch.setattr(bo_lai, "chay_exe",
                        lambda *a, **k: (_ for _ in ()).throw(_Dung()))

    args = _ArgsGia(moi, cu)
    args.goc_thu = str(tmp_path / "hop")
    with pytest.raises(_Dung):
        bo_lai.che_do_am_tinh(args, tmp_path / "bc")
    assert goi_vao["ban_cu"] == Path(cu)


def test_cau_loi_cua_trinh_cai_noi_ro_dang_cai_cho_BAN_NAO(tmp_path):
    """Từ nay một lượt chạy cài trình cài của HAI bản — đỏ phải chỉ đúng bản."""
    cai = tmp_path / "VoxDub-previous"
    cai.mkdir()
    with pytest.raises(bo_lai.Hong, match="BẢN CŨ dựng từ"):
        bo_lai.cai_bo_may(cai, "bat", 5,
                          nhan="BẢN CŨ dựng từ VoxDub-Studio-v3.17.19-win64.zip")

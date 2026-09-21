"""I0-FDE — lệnh chẩn đoán của BẢN ĐÓNG GÓI (`VoxDub.exe --tu-kiem-goi`).

Vì sao cần lệnh này (đã soi trước khi viết, xem docstring
`autodub_gui/tu_kiem_goi.py`): bản `.exe` **không có dòng lệnh nào** —
`app.main()` không đọc `sys.argv`, `autodub/cli.py` không được nhập ở đâu
trong `autodub_gui/` nên PyInstaller không gói nó, và không có máy chủ nội
bộ nào để điều khiển. Cửa duy nhất là `AUTODUB_SMOKE=1`, chỉ chứng minh app
KHỞI ĐỘNG được.

Bộ test này khoá những thứ mà nếu hỏng thì cổng kiểm sẽ xanh GIẢ:

* lệnh không được kéo Qt/engine nặng vào tiến trình;
* lệnh phải TỰ khoá ngoại tuyến (không thì mỗi lượt kiểm tiêu một suất Vox
  thật — đã xảy ra ngày 22/8/2026);
* thiếu tham số/thiếu bộ máy/lượt chạy không tới đích đều phải ra mã thoát
  KHÁC 0 và nói đúng giai đoạn hỏng;
* tệp bằng chứng không được mang theo token.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from autodub_gui import tu_kiem_goi as tk

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _giu_moi_truong(monkeypatch, tmp_path):
    """`chay()` cố ý ghi vào `os.environ` — không để nó rỉ sang test khác."""
    for k in ("AUTODUB_SMOKE", "TRANSLATE_MODE", "TRANSLATE_LOCAL_ENABLED",
              "TRANSLATE_ANALYSIS"):
        monkeypatch.delenv(k, raising=False)
    # Mọi lượt chạy neo vào thư mục tạm: `init_file_logging()` và phép dò bản
    # cài cũ đều đi qua `app_root()`, trỏ vào repo là bẩn cây mã nguồn.
    goc = tmp_path / "VoxDub-ung-vien"
    goc.mkdir()
    for ten in ("autodub.utils.app_root", "autodub.config.app_root",
                "autodub.venv_discovery.app_root"):
        monkeypatch.setattr(ten, lambda g=str(goc): g)
    from autodub import venv_discovery

    venv_discovery.quen_cache()
    yield goc
    venv_discovery.quen_cache()


class _KetQuaGia:
    def __init__(self, status, work_dir, report=None):
        self.status, self.work_dir = status, work_dir
        self.report = report or {}


def _duong_ong_gia(monkeypatch, *, status="completed", buoc=(), loi=None,
                   work_dir=""):
    """Thay `DubPipeline` bằng bản giả — test này kiểm LỚP VỎ, không kiểm dub."""
    class Gia:
        def __init__(self, settings, progress=None, **kw):
            self.progress = progress

        def run(self, req):
            from autodub.progress import ProgressEvent

            for ten_buoc, trang_thai in buoc:
                self.progress(ProgressEvent(step=ten_buoc,
                                            status=trang_thai))
            if loi:
                raise loi
            return _KetQuaGia(status, work_dir)

    monkeypatch.setattr("autodub.pipeline.DubPipeline", Gia)
    return Gia


# --------------------------------------------------------------- ranh giới --

def test_nhap_lenh_tu_kiem_khong_keo_qt_vao():
    """Lệnh chạy không giao diện — kéo PySide6 vào là sai kiến trúc."""
    kq = subprocess.run(
        [sys.executable, "-c",
         "import autodub_gui.tu_kiem_goi, sys; "
         "assert 'PySide6' not in sys.modules, sorted(sys.modules); "
         "assert 'autodub_gui.app' not in sys.modules; "
         "print('OK')"],
        cwd=REPO, capture_output=True, text=True, timeout=60)
    assert kq.returncode == 0, kq.stdout + kq.stderr
    assert "OK" in kq.stdout


def test_dau_vao_khong_co_co_thi_chay_duong_cu():
    """Không có `--tu-kiem-goi` thì đây vẫn là app bình thường."""
    assert tk.co_yeu_cau_tu_kiem([]) is False
    assert tk.co_yeu_cau_tu_kiem(["--gi-do"]) is False
    assert tk.co_yeu_cau_tu_kiem(["--tu-kiem-goi", "--chi-do-dac"]) is True


def test_khoa_ngoai_tuyen_chan_duoc_dia_chi_nhung_trong_exe(monkeypatch):
    """Khoá phải THẬT SỰ chặn — đây là chốt giữ tiền Vox của lượt kiểm."""
    import autodub_gui._embedded as emb
    from autodub import saas_client

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(emb, "VOXDUB_API_URL", "https://may-chu-that.example")
    assert saas_client.resolve_api_url() == "https://may-chu-that.example"

    tk.khoa_ngoai_tuyen()
    assert saas_client.resolve_api_url() == "", (
        "bỏ khoá ngoại tuyến là mỗi lượt kiểm đăng ký một thiết bị thật và "
        "tiêu một suất Vox (bug 22/8/2026)")
    assert os.environ["TRANSLATE_MODE"] == "manual"


# ------------------------------------------------------------- tham số sai --

@pytest.mark.parametrize("argv, vi_sao", [
    (["--tu-kiem-goi"], "thiếu --bang-chung"),
    (["--tu-kiem-goi", "--bang-chung", "BC"], "thiếu --video"),
    (["--tu-kiem-goi", "--bang-chung", "BC", "--video", "KHONG_CO.mp4"],
     "video không tồn tại"),
])
def test_thieu_tham_so_thi_tu_choi(argv, vi_sao, tmp_path):
    argv = [x.replace("BC", str(tmp_path / "bc")) for x in argv]
    with pytest.raises(tk.LoiThamSo):
        tk.phan_tich(argv)
    assert tk.chay(argv) == tk.MA_THAM_SO, vi_sao


def test_co_video_nhung_khong_co_cho_ghi_ket_qua(tmp_path):
    mau = tmp_path / "clip.mp4"
    mau.write_bytes(b"0")
    with pytest.raises(tk.LoiThamSo):
        tk.phan_tich(["--tu-kiem-goi", "--bang-chung", str(tmp_path / "bc"),
                      "--video", str(mau)])


def test_tham_so_sai_van_ghi_lai_bang_chung(tmp_path):
    bc = tmp_path / "bc"
    assert tk.chay(["--tu-kiem-goi", "--bang-chung", str(bc),
                    "--video", "KHONG_CO.mp4"]) == tk.MA_THAM_SO
    ket = json.loads((bc / "result.json").read_text(encoding="utf-8"))
    assert ket["giai_doan_hong"] == "startup"
    assert "tham số" in ket["loi"]


# --------------------------------------------------------------- đo đạc ----

def test_chi_do_dac_khong_chay_dub(tmp_path, monkeypatch):
    def _no(*a, **k):
        raise AssertionError("chế độ đo đạc KHÔNG được chạm vào đường ống dub")

    monkeypatch.setattr("autodub.pipeline.DubPipeline", _no)
    bc = tmp_path / "bc"
    assert tk.chay(["--tu-kiem-goi", "--chi-do-dac",
                    "--bang-chung", str(bc)]) == tk.MA_DAT
    ket = json.loads((bc / "result.json").read_text(encoding="utf-8"))
    assert ket["ket_qua"] == "dat"
    assert ket["ung_dung"]["ngoai_tuyen"] is True
    assert set(ket["bo_may"]) >= {"vieneu", "whisper", "paraformer", "ffmpeg"}


def test_thieu_bo_may_co_ma_thoat_rieng(tmp_path):
    """Thư mục cài mới chưa cài gì phải nói ĐÚNG là thiếu cái gì."""
    bc = tmp_path / "bc"
    ma = tk.chay(["--tu-kiem-goi", "--chi-do-dac", "--doi-bo-may",
                  "vieneu,whisper", "--bang-chung", str(bc)])
    assert ma == tk.MA_THIEU_BO_MAY
    ket = json.loads((bc / "result.json").read_text(encoding="utf-8"))
    assert ket["giai_doan_hong"] == "bo_may_thieu"
    assert sorted(ket["bo_may_thieu"]) == ["vieneu", "whisper"]


def test_do_dac_khong_nhan_vo_ban_cai_do_dang(tmp_path, monkeypatch,
                                              _giu_moi_truong):
    """Bản cũ chỉ có dấu `installed_ok` mà không có venv = KHÔNG dùng lại được."""
    goc = _giu_moi_truong
    cu = goc.parent / "VoxDub-cu"
    (cu / "models" / "vieneu").mkdir(parents=True)
    (cu / "models" / "vieneu" / "installed_ok.json").write_text("{}")

    from autodub.config import Settings

    do = tk.do_dac_bo_may(Settings())
    assert do["vieneu"]["san_sang"] is False, (
        "một bản cài dở dang bị tính là dùng lại được thì người dùng nâng cấp "
        "sẽ gặp lỗi giữa chừng thay vì câu 'chưa cài'")


# ------------------------------------------------------- lượt dub qua vỏ ---

def _argv_dub(tmp_path, them=()):
    mau = tmp_path / "clip.mp4"
    mau.write_bytes(b"0")
    return ["--tu-kiem-goi", "--video", str(mau),
            "--thu-muc-ra", str(tmp_path / "ra"),
            "--bang-chung", str(tmp_path / "bc"), *them]


def test_chang_mot_dung_o_dich_tay_la_dat(tmp_path, monkeypatch):
    _duong_ong_gia(monkeypatch, status="translate_pending",
                   buoc=[("asr", "done"), ("translate", "done")],
                   work_dir=str(tmp_path / "work"))
    assert tk.chay(_argv_dub(tmp_path)) == tk.MA_DAT
    ket = json.loads((tmp_path / "bc" / "result.json").read_text("utf-8"))
    assert ket["trang_thai_pipeline"] == "translate_pending"
    assert ket["yeu_cau"]["skip_video"] is True


def test_chang_hai_khong_duoc_nhan_translate_pending(tmp_path, monkeypatch):
    """Chạy tiếp mà vẫn 'chờ dịch' nghĩa là CHƯA xuất video — không được xanh."""
    work = tmp_path / "work"
    work.mkdir()
    mau = tmp_path / "clip.mp4"
    mau.write_bytes(b"0")
    _duong_ong_gia(monkeypatch, status="translate_pending",
                   buoc=[("translate", "done")], work_dir=str(work))
    ma = tk.chay(["--tu-kiem-goi", "--video", str(mau),
                  "--resume-dir", str(work),
                  "--bang-chung", str(tmp_path / "bc")])
    assert ma == tk.MA_KHONG_TOI_DICH
    ket = json.loads((tmp_path / "bc" / "result.json").read_text("utf-8"))
    assert ket["trang_thai_mong_doi"] == ["completed"]
    assert ket["giai_doan_hong"] == "translation_fixture"


def test_trang_thai_la_khong_toi_dich(tmp_path, monkeypatch):
    _duong_ong_gia(monkeypatch, status="credit_blocked",
                   buoc=[("asr", "done"), ("tts", "error")],
                   work_dir=str(tmp_path / "work"))
    assert tk.chay(_argv_dub(tmp_path)) == tk.MA_KHONG_TOI_DICH
    ket = json.loads((tmp_path / "bc" / "result.json").read_text("utf-8"))
    assert ket["giai_doan_hong"] == "tts"


@pytest.mark.parametrize("buoc, giai_doan", [
    ([("acquire", "start")], "input"),
    ([("asr", "start")], "asr"),
    ([("translate", "start")], "translation_fixture"),
    ([("tts", "start")], "tts"),
    ([("merge_video", "start")], "merge"),
])
def test_loi_giua_chung_ghi_dung_giai_doan(tmp_path, monkeypatch, buoc,
                                           giai_doan):
    _duong_ong_gia(monkeypatch, buoc=buoc,
                   loi=RuntimeError("Thư mục này chưa cài bộ nghe Whisper."))
    assert tk.chay(_argv_dub(tmp_path)) == tk.MA_NGOAI_DU_TINH
    ket = json.loads((tmp_path / "bc" / "result.json").read_text("utf-8"))
    assert ket["giai_doan_hong"] == giai_doan
    assert "chưa cài bộ nghe" in ket["loi"], (
        "câu lỗi phải đi nguyên vào bằng chứng — đó là thứ nói cho người "
        "chẩn lỗi biết phải làm gì")


def test_bang_chung_khong_mang_theo_token(tmp_path, monkeypatch):
    _duong_ong_gia(monkeypatch,
                   loi=RuntimeError("gọi hỏng, VOXDUB_TOKEN=sieu_bi_mat_123"))
    assert tk.chay(_argv_dub(tmp_path)) == tk.MA_NGOAI_DU_TINH
    noi_dung = (tmp_path / "bc" / "result.json").read_text("utf-8")
    assert "sieu_bi_mat_123" not in noi_dung
    assert "(đã che)" in noi_dung


def test_ghi_lai_moi_tien_trinh_con(tmp_path, monkeypatch):
    """Không có nhật ký này thì không chứng minh được engine chạy qua tiến
    trình con NẰM TRONG gói — đúng chỗ mà bản đóng gói hay mượn nhầm."""
    jsonl = tmp_path / "worker-launches.jsonl"
    goc = subprocess.Popen.__init__
    try:
        da_ghi = tk._ghi_nhat_ky_tien_trinh_con(str(jsonl))
        subprocess.run([sys.executable, "-c", "pass",
                        "--api-key", "khoa_that_123"],
                       capture_output=True, timeout=60)
    finally:
        subprocess.Popen.__init__ = goc
    assert len(da_ghi) == 1
    dong = json.loads(jsonl.read_text(encoding="utf-8").splitlines()[0])
    assert dong["chuong_trinh"] == sys.executable
    assert "khoa_that_123" not in jsonl.read_text(encoding="utf-8")


def test_vo_goi_khong_dung_duong_ong_thu_hai():
    """Route B là lớp vỏ, KHÔNG phải đường ống dub thứ hai.

    Khoá bằng mã nguồn: tệp phải gọi `DubPipeline(...).run(...)` và không
    được tự gọi engine (Whisper/VieNeu/ffmpeg) theo đường riêng.
    """
    nguon = open(tk.__file__, encoding="utf-8").read()
    assert "DubPipeline" in nguon and "duong_ong.run(yeu_cau)" in nguon
    for cam in ("faster_whisper", "vieneu_worker", "subprocess.run([",
                "transcribe(", "synthesize("):
        assert cam not in nguon, (
            f"{cam!r} trong lệnh chẩn đoán nghĩa là đang dựng đường dub thứ "
            "hai — nó sẽ xanh trong khi sản phẩm hỏng")


# ------------------------------- MỌI đường thoát phải để lại bằng chứng ----
#
# Run CI 35614850573: lệnh này chạy đúng, báo thiếu bộ máy đúng, trả đúng mã 5
# — nhưng bộ lái đọc phải một thư mục RỖNG nên kết luận ngược hẳn. Gốc nằm ở
# bộ lái (đưa đường dẫn tương đối qua ranh giới hai thư mục làm việc), nhưng
# bài học thì thuộc về cả hai phía: một trạng thái kết thúc không có bằng
# chứng là một trạng thái không ai đọc lại được.

def test_moi_duong_thoat_deu_de_lai_result_json(tmp_path, monkeypatch):
    """Lưới an toàn: nhánh bên trong quên ghi thì vỏ ngoài vẫn ghi."""
    monkeypatch.setattr(tk, "_chay_mot_luot", lambda argv: 7)
    bc = tmp_path / "bc"
    assert tk.chay(["--tu-kiem-goi", "--bang-chung", str(bc)]) == 7
    ket = json.loads((bc / "result.json").read_text(encoding="utf-8"))
    assert ket["giai_doan_hong"] == "unexpected"
    assert ket["ma_thoat"] == 7
    assert ket["bang_chung"] == str(bc)


def test_ket_qua_noi_ro_no_hieu_bang_chung_nam_o_dau(tmp_path, capsys):
    """Đường dẫn lệch thì phải có chỗ mà nhìn, thay vì một thư mục rỗng."""
    bc = tmp_path / "bc"
    assert tk.chay(["--tu-kiem-goi", "--chi-do-dac",
                    "--bang-chung", str(bc)]) == tk.MA_DAT
    ket = json.loads((bc / "result.json").read_text(encoding="utf-8"))
    assert ket["ung_dung"]["bang_chung"] == str(bc)
    assert ket["ung_dung"]["cwd_ban_dau"] == os.getcwd()
    assert str(bc) in capsys.readouterr().out


def test_duong_dan_tuong_doi_hieu_theo_cwd_cua_CHINH_no(tmp_path, monkeypatch):
    """Ghi lại đúng ngữ nghĩa đã gây ra sự cố, để lần sau không ai đoán lại."""
    monkeypatch.chdir(tmp_path)
    assert tk.chay(["--tu-kiem-goi", "--chi-do-dac",
                    "--bang-chung", "bc-tuong-doi"]) == tk.MA_DAT
    assert (tmp_path / "bc-tuong-doi" / "result.json").is_file(), (
        "đường dẫn tương đối được hiểu theo thư mục làm việc của TIẾN TRÌNH "
        "NÀY — nên người gọi ở thư mục khác phải đưa đường tuyệt đối")


def test_luong_ra_khoa_utf8_khong_vo_chu(tmp_path):
    """`app.stderr.log` của run thật bị vỡ chữ vì cp1252 — khoá lại ở đây."""
    kq = subprocess.run(
        [sys.executable, "-c",
         "import autodub_gui.tu_kiem_goi as tk, sys;"
         "tk._bang_ma_utf8();"
         "print('giọng đọc tiếng Việt');"
         "print(sys.stdout.encoding)"],
        cwd=REPO, capture_output=True, timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"})
    ra = kq.stdout.decode("utf-8", errors="replace")
    assert "giọng đọc tiếng Việt" in ra, ra
    assert "utf-8" in ra.lower()

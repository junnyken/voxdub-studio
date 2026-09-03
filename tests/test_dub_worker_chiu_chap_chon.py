"""C54 — worker dub phải sống được qua lúc mạng chập chờn.

Worker và control_server chạy trên HAI project hosting tách nhau, nên mọi lệnh
gọi đi vòng ra tên miền công cộng. Ngày 31-08 mất phân giải tên miền khoảng một
tiếng: worker vẫn nện 3 giây/lần (mỗi lượt ôm timeout 15s) và xả đúng một dòng
lỗi lặp kín cả cửa sổ log.

Nhưng thứ ĐẮT NHẤT không phải log rác: `/complete` là lệnh gọi bắn-rồi-quên.
Mạng chập đúng lúc đó thì một job đã dub xong (hàng chục phút CPU, khách đã bị
giữ tiền) rơi vào im lặng — mà log vẫn in "Job … xong" như thường.

Bộ test này canh ba thứ: giãn nhịp khi mất kết nối, gộp log mà KHÔNG im lặng,
và không bao giờ báo "xong" khi báo cáo chưa tới nơi.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def worker():
    duong_dan = os.path.join(GOC, "control_server", "worker-dub", "dub_worker.py")
    spec = importlib.util.spec_from_file_location("dub_worker_c54", duong_dan)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dub_worker_c54"] = mod
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------- giãn nhịp ---

def test_khong_co_loi_thi_giu_nhip_thuong(worker):
    assert worker._nhip_cho(0) == worker.POLL_INTERVAL_S


def test_loi_lien_tiep_thi_gian_nhip_gap_doi(worker):
    assert worker._nhip_cho(1) > worker._nhip_cho(0)
    assert worker._nhip_cho(2) > worker._nhip_cho(1)


def test_gian_nhip_co_tran(worker):
    """Một tiếng mất DNS không được biến thành nhịp chờ hàng giờ — nối lại
    được thì phải nhận việc trong vòng một phút."""
    assert worker._nhip_cho(50) == worker.POLL_BACKOFF_MAX_S
    assert worker.POLL_BACKOFF_MAX_S <= 300


# --------------------------------------------------------- gộp log lỗi ---

def test_lan_hong_dau_tien_in_ngay(worker):
    dem = worker._SoMatKetNoi(now=lambda: 0.0)
    assert "mất DNS" in dem.ghi_loi("mất DNS")


def test_hong_lap_lai_thi_thua_dan_chu_khong_im(worker):
    dong_ho = [0.0]
    dem = worker._SoMatKetNoi(now=lambda: dong_ho[0])
    in_ra = []
    for i in range(40):
        dong_ho[0] = float(i)
        dong = dem.ghi_loi("mất DNS")
        if dong:
            in_ra.append(dong)
    # Thưa dần: 40 lần hỏng không được thành 40 dòng, nhưng cũng KHÔNG được
    # tụt về 1 dòng rồi im bặt — đọc log phải thấy nó vẫn đang hỏng.
    assert 2 <= len(in_ra) <= 8, in_ra
    assert any("lần trong" in d for d in in_ra), in_ra


def test_noi_lai_duoc_thi_noi_ra(worker):
    dong_ho = [0.0]
    dem = worker._SoMatKetNoi(now=lambda: dong_ho[0])
    dem.ghi_loi("mất DNS")
    dong_ho[0] = 120.0
    dong = dem.ghi_thanh_cong()
    assert dong and "nối lại" in dong.lower(), dong
    assert dem.lien_tiep == 0


def test_dang_binh_thuong_thi_khong_in_gi_them(worker):
    dem = worker._SoMatKetNoi(now=lambda: 0.0)
    assert dem.ghi_thanh_cong() is None


# ------------------------------------------------- claim phân biệt hai ca ---

def test_claim_phan_biet_khong_co_viec_va_khong_goi_duoc(worker, monkeypatch):
    monkeypatch.setattr(worker, "_post_chi_tiet", lambda p, d: ({"job": None}, None))
    assert worker.claim_next_job() == (None, None)

    monkeypatch.setattr(worker, "_post_chi_tiet", lambda p, d: (None, "mất DNS"))
    job, loi = worker.claim_next_job()
    assert job is None and loi == "mất DNS"


# ------------------------------------------ báo kết quả cuối job: thử lại ---

def test_bao_ket_thuc_thu_lai_khi_mang_hong(worker, monkeypatch):
    lan = []

    def gia_post(path, payload):
        lan.append(path)
        if len(lan) < 3:
            return None, "mất DNS"
        return {"ok": True}, None

    monkeypatch.setattr(worker, "_post_chi_tiet", gia_post)
    monkeypatch.setattr(worker.time, "sleep", lambda _s: None)
    assert worker._bao_ket_thuc("/x/complete", {}, "Báo XONG") is True
    assert len(lan) == 3


def test_bao_ket_thuc_khong_thu_lai_khi_may_chu_tra_loi_ro_rang(worker, monkeypatch):
    """Máy chủ trả lời (kể cả 'job không còn của bạn') là câu trả lời, không
    phải sự cố đường truyền — nện thêm 5 lần chỉ tốn thời gian."""
    lan = []

    def gia_post(path, payload):
        lan.append(path)
        return {"ok": False}, None

    monkeypatch.setattr(worker, "_post_chi_tiet", gia_post)
    monkeypatch.setattr(worker.time, "sleep", lambda _s: None)
    worker._bao_ket_thuc("/x/complete", {}, "Báo XONG")
    assert len(lan) == 1


def test_bao_ket_thuc_bo_cuoc_co_gioi_han(worker, monkeypatch):
    lan = []
    monkeypatch.setattr(worker, "_post_chi_tiet",
                        lambda p, d: (lan.append(p), (None, "mất DNS"))[1])
    monkeypatch.setattr(worker.time, "sleep", lambda _s: None)
    assert worker._bao_ket_thuc("/x/complete", {}, "Báo XONG") is False
    assert len(lan) == worker.BAO_KET_THUC_SO_LAN


def test_dang_tat_may_van_co_bao_cho_xong(worker, monkeypatch):
    """SIGTERM tới giữa lúc báo kết quả: job đã chạy xong rồi, đây là thứ đáng
    cố nhất trong cả vòng đời job — không được bỏ ngang như tải file."""
    lan = []

    def gia_post(path, payload):
        lan.append(path)
        return (None, "mất DNS") if len(lan) < 2 else ({"ok": True}, None)

    monkeypatch.setattr(worker, "_post_chi_tiet", gia_post)
    monkeypatch.setattr(worker.time, "sleep", lambda _s: None)
    worker._shutdown.set()
    try:
        assert worker._bao_ket_thuc("/x/complete", {}, "Báo XONG") is True
    finally:
        worker._shutdown.clear()


# --------------------------------------- không được nói dối trong log ---

def _job_chay_xong(worker, monkeypatch, bao_duoc: bool) -> list:
    goi = []
    monkeypatch.setattr(worker, "_heartbeat_loop", lambda *a, **k: None)
    monkeypatch.setattr(worker, "run_dub", lambda job, lost=None: {
        "ok": True, "video_path": "/tmp/x.mp4",
        "metrics": {"processingMs": 1234},
    })
    monkeypatch.setattr(worker, "upload_output", lambda *a: "/srv/out.mp4")
    monkeypatch.setattr(worker, "_bao_ket_thuc",
                        lambda path, payload, mo_ta: (goi.append((path, payload)),
                                                      bao_duoc)[1])
    worker.process_job({"jobId": "j1", "sourceLang": "en", "targetLang": "vi"})
    return goi


def test_bao_duoc_thi_in_xong(worker, monkeypatch, capsys):
    goi = _job_chay_xong(worker, monkeypatch, bao_duoc=True)
    ra = capsys.readouterr().out
    assert "Job j1 xong" in ra
    assert "MẤT BÁO CÁO" not in ra
    # Đúng endpoint, đúng đường dẫn kết quả server trả về — không phải
    # video_path tạm trên đĩa worker.
    assert goi and goi[0][0] == "/internal/dub-jobs/j1/complete", goi
    assert goi[0][1]["outputPath"] == "/srv/out.mp4"


def test_khong_bao_duoc_thi_KHONG_duoc_in_xong(worker, monkeypatch, capsys):
    _job_chay_xong(worker, monkeypatch, bao_duoc=False)
    ra = capsys.readouterr().out
    assert "MẤT BÁO CÁO" in ra
    assert "Job j1 xong" not in ra, "log nói dối: báo cáo chưa tới nơi mà đã in xong"


# ------------------------------------------------ tải/đẩy file: thử lại ---

def test_day_ket_qua_thu_lai_khi_mat_mang(worker, monkeypatch):
    lan = []

    def gia_day(job_id, video_path):
        lan.append(job_id)
        return (None, True) if len(lan) < 3 else ("/srv/out.mp4", False)

    monkeypatch.setattr(worker, "_day_ket_qua_mot_lan", gia_day)
    monkeypatch.setattr(worker._shutdown, "wait", lambda _s: False)
    assert worker.upload_output("j1", "/tmp/x.mp4") == "/srv/out.mp4"
    assert len(lan) == 3


def test_day_ket_qua_khong_thu_lai_khi_may_chu_tu_choi(worker, monkeypatch):
    lan = []
    monkeypatch.setattr(worker, "_day_ket_qua_mot_lan",
                        lambda j, v: (lan.append(j), (None, False))[1])
    monkeypatch.setattr(worker._shutdown, "wait", lambda _s: False)
    assert worker.upload_output("j1", "/tmp/x.mp4") is None
    assert len(lan) == 1


def test_tai_input_thu_lai_co_gioi_han(worker, monkeypatch):
    lan = []
    monkeypatch.setattr(worker, "_tai_input_mot_lan",
                        lambda j, d: (lan.append(j), (False, True))[1])
    monkeypatch.setattr(worker._shutdown, "wait", lambda _s: False)
    assert worker.download_input("j1", "/tmp/x.mp4") is False
    assert len(lan) == worker.TRUYEN_FILE_SO_LAN

"""V89 — cổng trợ lý: app gọi tác vụ có tên, và LUÔN có đường lui.

Nguyên tắc phải giữ, khoá lại ở đây:

1. App gửi TÊN tác vụ, không gửi prompt — prompt nằm ở máy chủ nên sửa câu
   chữ không cần phát hành lại bản .exe.
2. Mọi kết quả kèm lý do; thiếu lý do thì bỏ, không hiện nửa vời.
3. Máy chủ hỏng / chưa cấu hình / hết Vox → rơi về tầng luật chạy trên máy.
   Tầng luật không bị thay thế: nó là thứ duy nhất chạy khi không mạng.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app

from autodub.media import music_suggest
from autodub.media.music_suggest import GoiYNhac


def _segs(n=4):
    cau = ("Hôm nay mình hướng dẫn các bạn nấu món phở bò thật ngon tại nhà. "
           "Nguyên liệu gồm xương bò, quế, hồi, gừng nướng và hành tím. ")
    return [{"text_vi": cau, "start": i * 5.0, "end": (i + 1) * 5.0,
             "duration": 5.0} for i in range(n)]


class _KhachGia:
    """Máy chủ giả — ghi lại đúng thứ app gửi lên."""

    def __init__(self, tra_ve=None, no=None):
        self.tra_ve = tra_ve if tra_ve is not None else []
        self.no = no
        self.da_goi = []

    def assist(self, task, input_data, *, job_id, hold_id=None, timeout=45.0):
        self.da_goi.append((task, input_data, job_id))
        if self.no:
            raise self.no
        return self.tra_ve


def _cam_may_chu(monkeypatch, khach, configured=True):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: configured)
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: khach)
    monkeypatch.setattr("autodub.saas_client.new_job_id", lambda: "job-test-1234")


# -- 1. Đường qua máy chủ ----------------------------------------------------

def test_co_tai_khoan_thi_hoi_may_chu(monkeypatch):
    khach = _KhachGia([{"value": "nhạc mộc, guitar nhẹ", "reason": "video nấu ăn"}])
    _cam_may_chu(monkeypatch, khach)

    ra, nguon = music_suggest.goi_y_nhac_thong_minh(_segs(), "text_vi", "Nấu phở")

    assert nguon == "may_chu"
    assert ra == [GoiYNhac("nhạc mộc, guitar nhẹ", "video nấu ăn")]


def test_gui_ten_tac_vu_chu_khong_gui_prompt(monkeypatch):
    """Đây là thứ giữ cho chi phí đoán được và cho phép sửa prompt trên máy
    chủ mà không phát hành lại app."""
    khach = _KhachGia([{"value": "a", "reason": "b"}])
    _cam_may_chu(monkeypatch, khach)

    music_suggest.goi_y_nhac_thong_minh(_segs(), "text_vi")

    task, input_data, _job = khach.da_goi[0]
    assert task == "music_suggest"
    assert set(input_data) <= {"transcript", "videoTitle"}
    xau = " ".join(str(v).lower() for v in input_data.values())
    for cam in ("bạn là", "hãy trả về", "json", "system", "prompt"):
        assert cam not in xau, f"lộ chỉ dẫn mô hình phía app: {cam!r}"


def test_cat_loi_thoai_truoc_khi_gui(monkeypatch):
    """Đừng đẩy vài trăm KB qua mạng chỉ để bên kia vứt đi."""
    khach = _KhachGia([{"value": "a", "reason": "b"}])
    _cam_may_chu(monkeypatch, khach)
    dai = [{"text_vi": "câu dài " * 5000, "start": 0, "end": 60, "duration": 60}] * 3

    music_suggest.goi_y_nhac_thong_minh(dai, "text_vi")

    _task, input_data, _job = khach.da_goi[0]
    assert len(input_data["transcript"]) <= music_suggest._TRAN_CHU


# -- 2. Đường lui: tầng luật không bao giờ bị bỏ ------------------------------

def test_chua_co_tai_khoan_thi_do_tren_may(monkeypatch):
    khach = _KhachGia()
    _cam_may_chu(monkeypatch, khach, configured=False)

    ra, nguon = music_suggest.goi_y_nhac_thong_minh(_segs(), "text_vi")

    assert nguon == "luat" and ra
    assert not khach.da_goi, "chạy thuần trên máy thì tuyệt đối không gọi ra ngoài"


@pytest.mark.parametrize("no", [
    RuntimeError("mất mạng"),
    TimeoutError("máy chủ chậm"),
    Exception("hết Vox"),
])
def test_may_chu_hong_thi_roi_ve_luat(monkeypatch, no):
    _cam_may_chu(monkeypatch, _KhachGia(no=no))

    ra, nguon = music_suggest.goi_y_nhac_thong_minh(_segs(), "text_vi")

    assert nguon == "luat"
    assert ra, "hỏng máy chủ mà mất luôn gợi ý thì tính năng thành vô dụng"


def test_may_chu_tra_rong_cung_roi_ve_luat(monkeypatch):
    _cam_may_chu(monkeypatch, _KhachGia([]))
    ra, nguon = music_suggest.goi_y_nhac_thong_minh(_segs(), "text_vi")
    assert nguon == "luat" and ra


def test_bo_ket_qua_thieu_ly_do(monkeypatch):
    """Gợi ý không có lý do thì người dùng không kiểm chứng được — thà rơi
    về tầng luật, nơi lý do luôn là con số đo được."""
    _cam_may_chu(monkeypatch, _KhachGia([{"value": "nhạc vui", "reason": ""}]))

    ra, nguon = music_suggest.goi_y_nhac_thong_minh(_segs(), "text_vi")

    assert nguon == "luat"


def test_loi_thoai_qua_ngan_thi_khong_ton_vox(monkeypatch):
    khach = _KhachGia([{"value": "a", "reason": "b"}])
    _cam_may_chu(monkeypatch, khach)

    music_suggest.goi_y_nhac_thong_minh(
        [{"text_vi": "chào", "start": 0, "end": 1, "duration": 1}], "text_vi")

    assert not khach.da_goi, "vài chữ thì hỏi mô hình cũng vô nghĩa"


# -- 3. Hàm gọi API của app --------------------------------------------------

def test_client_gui_dung_duong_dan_va_doc_ket_qua(monkeypatch):
    from autodub.saas_client import SaasClient

    khach = SaasClient.__new__(SaasClient)
    da_gui = {}

    def _fake_request(method, path, *, json_body=None, timeout=None, **kw):
        da_gui.update(method=method, path=path, body=json_body, timeout=timeout)
        return {"results": [{"value": "x", "reason": "y"}], "creditCharged": 2}

    khach._request = _fake_request
    khach._note_usage = lambda data: None

    ra = khach.assist("music_suggest", {"transcript": "abc"}, job_id="j-123456789")

    assert da_gui["method"] == "POST"
    assert da_gui["path"] == "/v1/ai/assist"
    assert da_gui["body"]["task"] == "music_suggest"
    assert da_gui["body"]["jobId"] == "j-123456789"
    assert ra == [{"value": "x", "reason": "y"}]


def test_client_khong_no_khi_may_chu_tra_sai_khuon(monkeypatch):
    from autodub.saas_client import SaasClient

    khach = SaasClient.__new__(SaasClient)
    khach._request = lambda *a, **k: {"results": "không phải mảng"}
    khach._note_usage = lambda data: None

    assert khach.assist("music_suggest", {}, job_id="j-123456789") == []


# -- 4. Giao diện ------------------------------------------------------------

def test_worker_khong_bao_gio_nem_ra_ngoai(qapp, monkeypatch):
    """Gợi ý hỏng không được giết Trình chỉnh sửa."""
    from autodub_gui.workers import MusicSuggestWorker

    def _no(*a, **k):
        raise RuntimeError("hỏng bất ngờ")

    monkeypatch.setattr("autodub.media.music_suggest.goi_y_nhac_thong_minh", _no)
    nhan = []
    w = MusicSuggestWorker(_segs(), "text_vi")
    w.finished_ok.connect(lambda ra, nguon: nhan.append((ra, nguon)))
    w.run()
    assert nhan == [([], "luat")]


def test_giai_thich_loi_im_lang_khi_chua_co_tai_khoan(qapp, monkeypatch):
    """Người đang bực vì lỗi không cần thêm một thông báo "không giải thích
    được lỗi"."""
    from autodub_gui.workers import ExplainErrorWorker

    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    nhan = []
    w = ExplainErrorWorker("[WinError 2] file not found")
    w.finished_ok.connect(lambda a, b: nhan.append((a, b)))
    w.run()
    assert nhan == []


def test_nguoi_dung_biet_goi_y_den_tu_dau(qapp):
    """Hai đường cho chất lượng khác nhau — người dùng có quyền biết mình
    đang xem cái nào."""
    from autodub_gui.pages.editor_panels import MusicSfxPanel

    panel = MusicSfxPanel()
    panel.show_music_suggestions([GoiYNhac("nhạc nhẹ", "vì A")], nguon="may_chu")
    assert "trợ lý" in panel.music_status.text()
    panel.show_music_suggestions([GoiYNhac("nhạc nhẹ", "vì A")], nguon="luat")
    assert "trên máy" in panel.music_status.text()

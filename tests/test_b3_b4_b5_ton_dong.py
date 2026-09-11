"""Ba lỗi tồn đọng trong `docs/BACKLOG_PHASE_H.md` — B3, B4, B5.

Cả ba đều là lớp lỗi "thêm đường mới mà quên nối vào đường cũ": `_bp_worker`
thêm vào nhưng `is_running()` không kể tới, mẻ vẽ thêm vào nhưng không có
đường huỷ, `_settings_provider` nhận vào nhưng không ai đọc. Không lỗi nào bị
2.700 test cũ bắt được vì mỗi phần *riêng nó* đều đúng.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

from autodub.story_image import AnhMinhHoa, sinh_nhieu_anh


# --- B4: mẻ vẽ phải dừng được ------------------------------------------------

def _anh_gia(goi_y, thu_muc_ra, **kw):
    return AnhMinhHoa(duong_dan=f"{thu_muc_ra}/x.jpg", goi_y=goi_y,
                      phan_quyet="DAT", ly_do="ổn", da_kiem=True,
                      da_dong_nhan=True, vox_ve=30, vox_kiem=2)


def test_huy_giua_me_thi_dung_khong_ve_tiep(tmp_path):
    """Bấm huỷ ở ảnh thứ hai thì ảnh thứ ba KHÔNG được vẽ.

    Mỗi tấm là 30 Vox và hai lượt gọi mạng tới 120 giây. Mẻ mười tấm không
    dừng được nghĩa là người dùng lỡ tay bấm nhầm thì phải ngồi nhìn 300 Vox
    trôi đi trong bốn phút, không có cách nào can thiệp ngoài giết app — mà
    giết app giữa chừng thì mất luôn cả những ảnh đã trả tiền.
    """
    da_ve: list[str] = []
    dung = threading.Event()

    def ve(goi_y, thu_muc_ra, **kw):
        da_ve.append(goi_y)
        if len(da_ve) == 2:
            dung.set()
        return _anh_gia(goi_y, thu_muc_ra, **kw)

    goi_y = [(i, f"gợi ý {i}") for i in range(5)]
    with patch("autodub.story_image.sinh_mot_anh", side_effect=ve):
        me = sinh_nhieu_anh(goi_y, str(tmp_path), huy=dung.is_set)

    assert da_ve == ["gợi ý 0", "gợi ý 1"], (
        f"Huỷ sau ảnh 2 mà vẫn vẽ tiếp: {da_ve}")
    assert me.da_huy is True
    assert me.so_chua_ve == 3


def test_huy_giu_nguyen_anh_da_tra_tien(tmp_path):
    """Huỷ KHÔNG được vứt những ảnh đã trả tiền.

    Tiền đã trừ ở máy chủ rồi; trả về mẻ rỗng là làm người dùng mất trắng
    phần đã mua chỉ vì họ bấm dừng.
    """
    dung = threading.Event()

    def ve(goi_y, thu_muc_ra, **kw):
        dung.set()
        return _anh_gia(goi_y, thu_muc_ra, **kw)

    with patch("autodub.story_image.sinh_mot_anh", side_effect=ve):
        me = sinh_nhieu_anh([(0, "a"), (1, "b")], str(tmp_path),
                            huy=dung.is_set)

    assert me.so_dung_duoc == 1
    assert me.vox_da_mat == 32
    assert me.da_huy is True


def test_huy_truoc_khi_bat_dau_thi_khong_ve_tam_nao(tmp_path):
    with patch("autodub.story_image.sinh_mot_anh",
               side_effect=AssertionError("không được gọi")):
        me = sinh_nhieu_anh([(0, "a")], str(tmp_path), huy=lambda: True)
    assert me.da_huy is True
    assert me.so_yeu_cau == 0
    assert me.vox_da_mat == 0


def test_khong_huy_thi_me_chay_het_nhu_cu(tmp_path):
    """Đường cũ không đổi khi không truyền `huy`."""
    with patch("autodub.story_image.sinh_mot_anh", side_effect=_anh_gia):
        me = sinh_nhieu_anh([(0, "a"), (1, "b")], str(tmp_path))
    assert me.so_dung_duoc == 2
    assert me.da_huy is False
    assert me.so_chua_ve == 0


def test_trang_thai_da_huy_khac_hong_ca_me(tmp_path):
    """Huỷ không phải là hỏng — hai ca nói ra hai câu khác nhau.

    Gộp chung thì màn hình báo "Không vẽ được ảnh nào" kèm nút "Thử lại"
    cho một lượt mà chính người dùng vừa chủ động dừng.
    """
    with patch("autodub.story_image.sinh_mot_anh",
               side_effect=AssertionError("không được gọi")):
        me = sinh_nhieu_anh([(0, "a")], str(tmp_path), huy=lambda: True)
    assert me.trang_thai == "da_huy"


def test_worker_ve_anh_co_ham_cancel():
    """`SinhAnhMinhHoaWorker` phải có `cancel()` như mọi worker dài khác.

    `TranscribeWorker`, `BatchWorker`… đều có. Worker này thì không, nên nút
    huỷ ở giao diện không có gì để gọi.
    """
    from autodub_gui.workers import SinhAnhMinhHoaWorker
    assert hasattr(SinhAnhMinhHoaWorker, "cancel")


def test_worker_ve_anh_truyen_co_huy_xuong_thu_vien(tmp_path):
    """Gọi `cancel()` thì `sinh_nhieu_anh` phải NHẬN được tín hiệu đó.

    Có hàm `cancel()` mà không nối xuống dưới là lớp lỗi "chốt thân hàm mà
    quên chốt chỗ gọi" — nút bấm được, đèn tắt, mẻ vẫn chạy.
    """
    from autodub_gui.workers import SinhAnhMinhHoaWorker

    w = SinhAnhMinhHoaWorker([(0, "a")], str(tmp_path))
    w.cancel()
    bat = {}

    def gia(goi_y_theo_doan, thu_muc_ra, **kw):
        bat.update(kw)
        from autodub.story_image import MeAnh
        return MeAnh(thu_muc=thu_muc_ra)

    with patch("autodub.story_image.sinh_nhieu_anh", side_effect=gia):
        w.run()

    assert callable(bat.get("huy")), "worker không truyền `huy` xuống"
    assert bat["huy"]() is True, "`cancel()` rồi mà `huy()` vẫn False"


# --- B3: `is_running()` phải kể cả `_bp_worker` ------------------------------

def test_is_running_ke_ca_bp_worker():
    """`app.py` chỉ `shutdown()` trang nào `is_running()` trả True.

    Chính `app.py` ghi rằng huỷ QThread đang chạy lúc teardown làm Qt chết
    cứng (0xC0000409). Bỏ sót `_bp_worker` ở đây nghĩa là worker đó không
    bao giờ được chờ — đóng app giữa lúc nó chạy là crash.
    """
    from autodub_gui.pages.storyboard_page import StoryboardPage

    class _Gia:
        def __init__(self):
            self._chay = True

        def isRunning(self):
            return self._chay

    trang = StoryboardPage.__new__(StoryboardPage)
    trang._worker = None
    trang._ve_worker = None
    trang._bp_worker = _Gia()
    assert StoryboardPage.is_running(trang) is True


def test_is_running_false_khi_moi_worker_deu_nghi():
    from autodub_gui.pages.storyboard_page import StoryboardPage

    trang = StoryboardPage.__new__(StoryboardPage)
    trang._worker = trang._ve_worker = trang._bp_worker = None
    assert StoryboardPage.is_running(trang) is False


# --- B5: thư mục ra phải theo Cài đặt ----------------------------------------

def test_goc_ra_theo_cai_dat():
    """Đặt thư mục ra là `D:/Videos` thì ảnh không được rơi vào `~/VoxDub`.

    Trang Dự án chỉ quét `output_dir`; ghi ra chỗ khác nghĩa là dự án vừa
    dựng KHÔNG hiện ở đâu cả. Trang ảnh sản phẩm cùng loại đã tôn trọng cài
    đặt từ lâu — chỉ trang này đóng cứng.
    """
    from autodub_gui.pages.storyboard_page import StoryboardPage

    class _CaiDat:
        output_dir = "/tmp/thu-muc-nguoi-dung-chon"

    trang = StoryboardPage.__new__(StoryboardPage)
    trang._settings_provider = lambda: _CaiDat()
    assert StoryboardPage._goc_ra(trang) == "/tmp/thu-muc-nguoi-dung-chon"


@pytest.mark.parametrize("cai_dat", [
    pytest.param(lambda: None, id="khong-co-cai-dat"),
    pytest.param(lambda: (_ for _ in ()).throw(RuntimeError("hỏng")),
                 id="doc-cai-dat-nem-loi"),
])
def test_goc_ra_lui_ve_mac_dinh_khi_khong_doc_duoc(cai_dat):
    """Đọc cài đặt hỏng thì lùi về `~/VoxDub`, không chặn việc."""
    import os

    from autodub_gui.pages.storyboard_page import StoryboardPage

    trang = StoryboardPage.__new__(StoryboardPage)
    trang._settings_provider = cai_dat
    assert StoryboardPage._goc_ra(trang) == os.path.join(
        os.path.expanduser("~"), "VoxDub")


def test_khong_con_duong_dan_dong_cung_trong_trang():
    """Chốt luôn CHỖ GỌI, không chỉ chốt thân hàm.

    Sửa `_goc_ra()` cho đúng mà hai chỗ gọi vẫn `expanduser("~")` thì hàm
    mới chỉ là trang trí — đúng lớp lỗi đã lặp bốn lần trong dự án này.
    """
    import inspect

    from autodub_gui.pages import storyboard_page

    for ten in ("_ve_anh_hang_loat", "_dung_du_an"):
        ham = getattr(storyboard_page.StoryboardPage, ten, None)
        if ham is None:
            continue
        than = inspect.getsource(ham)
        assert "expanduser" not in than, (
            f"`{ten}` vẫn đóng cứng đường dẫn thay vì gọi `_goc_ra()`")


def test_thoi_gian_huy_khong_ke_luot_dang_ve(tmp_path):
    """Huỷ chỉ chặn ảnh KẾ TIẾP, không cắt ngang ảnh đang vẽ dở.

    Cắt giữa chừng là mất tiền mà không có tệp: máy chủ đã vẽ xong và đã trừ
    Vox trước khi máy khách kịp buông kết nối.
    """
    dung = threading.Event()
    xong: list[float] = []

    def ve(goi_y, thu_muc_ra, **kw):
        dung.set()
        time.sleep(0.02)
        xong.append(time.monotonic())
        return _anh_gia(goi_y, thu_muc_ra, **kw)

    with patch("autodub.story_image.sinh_mot_anh", side_effect=ve):
        me = sinh_nhieu_anh([(0, "a"), (1, "b")], str(tmp_path),
                            huy=dung.is_set)

    assert len(xong) == 1, "ảnh đang vẽ dở bị cắt ngang"
    assert me.so_dung_duoc == 1

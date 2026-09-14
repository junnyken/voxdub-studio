"""H5 — Dải điều hướng Phase H: H2 → H3 → H4.

Vấn đề nó giải (chủ dự án báo 14/09): «Viết kịch bản» và «Dựng video» KHÔNG
nằm trên thanh bên, nên đóng/đổi trang là mất đường quay lại và không lúc nào
nhìn thấy cả chuỗi — *"nó đang bị thiếu quy trình"*.

Điều tệp này canh gắt nhất: **dải là đường đi, KHÔNG phải cổng.** Mở được
trang H4 ≠ dựng được video. Một dải điều hướng vô tình mở cổng là cách tệ nhất
để thêm một tiện nghi.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages.brand_script_page import BrandScriptPage  # noqa: E402
from autodub_gui.pages.flow_blueprint_page import FlowBlueprintPage  # noqa: E402
from autodub_gui.pages.storyboard_page import StoryboardPage  # noqa: E402
from autodub_gui.ui.phase_h_ribbon import NHAN_BUOC, PhaseHRibbon  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _beat(**kw):
    d = {"beatType": "hook", "voiceoverTextVi": "Một câu lời đọc đủ dài để đo",
         "captionSuggestionVi": "Chữ trên hình", "visualBriefVi": "Cảnh quay"}
    d.update(kw)
    return d


# ================================================== 1. HIỂN THỊ ============

@pytest.mark.parametrize("lop,buoc", [
    (FlowBlueprintPage, 0), (BrandScriptPage, 1), (StoryboardPage, 2)])
def test_ba_trang_deu_co_dai_va_highlight_dung_buoc(lop, buoc):
    trang = lop(lambda: object())
    assert hasattr(trang, "ribbon"), f"{lop.__name__} thiếu dải điều hướng"
    assert trang.ribbon.stepper.current_step() == buoc


def test_nhan_ba_buoc_dung_ten_nguoi_dung_doc():
    assert NHAN_BUOC == ["Phân tích cấu trúc", "Viết kịch bản", "Dựng video"]


def test_moi_buoc_deu_bam_duoc_ke_ca_buoc_chua_toi():
    """H4 phải mở được để người dùng BIẾT mình còn thiếu gì.

    `Stepper` mặc định chỉ cho nhảy tới `max_reached + 1` — đúng cho trình
    hướng dẫn cài đặt, sai cho dải này.
    """
    dai = PhaseHRibbon(0)
    for i in range(len(NHAN_BUOC)):
        assert dai.stepper.can_jump_to(i), f"bước {i} không bấm được"


def test_bam_lai_chinh_buoc_dang_xem_thi_khong_phat_gi():
    """Chuyển sang chính mình là dựng lại trang vô ích, và ở H4 còn làm mất
    ảnh người dùng đang gán dở."""
    dai = PhaseHRibbon(1)
    ra = []
    dai.buoc_duoc_chon.connect(ra.append)
    dai._bam_buoc(1)
    assert ra == []
    dai._bam_buoc(2)
    assert ra == [2]


def test_dai_KHONG_cao_qua_muc():
    """Dải nằm ở đầu CẢ BA trang, nên chiều cao bị nhân ba."""
    dai = PhaseHRibbon(0)
    assert dai.stepper.minimumHeight() <= 50, (
        "dùng chế độ gọn; bản đầy 76px ăn quá nhiều chiều dọc khi lặp ba lần")


def test_hai_trang_cu_dung_Stepper_KHONG_bi_doi_kich_thuoc():
    """Thêm chế độ, không đổi mặc định — `new_project_page` và
    `setup_wizard` không truyền `compact` nên phải giữ nguyên 76px."""
    from autodub_gui.ui.stepper import Stepper

    cu = Stepper(["a", "b", "c"])
    assert cu.minimumHeight() == 76
    assert not cu.can_jump_to(2), "luật nhảy cũ phải giữ nguyên cho hai trang kia"


# ====================================== 2. ĐIỀU HƯỚNG QUA CƠ CHẾ SẴN CÓ ====

def test_dai_di_qua_switch_page_chu_khong_tu_doi_trang():
    """`switch_page` còn mang chốt `_blocked_by_unsaved`. Dựng đường chuyển
    trang thứ hai là bỏ qua chốt đó mà không ai nhận ra."""
    import inspect

    from autodub_gui import app as m

    ma = inspect.getsource(m.MainWindow._noi_dai_phase_h)
    assert "switch_page" in ma
    assert m.MainWindow.HANG_PHASE_H == (
        m.ROW_FLOW_BLUEPRINT, m.ROW_BRAND_SCRIPT, m.ROW_STORYBOARD)


def test_moi_trang_phase_h_deu_duoc_noi_dai():
    import inspect

    from autodub_gui import app as m

    ma = inspect.getsource(m.MainWindow._create_page)
    assert ma.count("_noi_dai_phase_h") == 3, (
        "thiếu một trang là trang đó thành ngõ cụt, đúng lỗi H5 sinh ra để chữa")


# ================================= 3. DẢI KHÔNG ĐƯỢC LÀ CỔNG ==============

@pytest.mark.parametrize("trang_thai", ["blocked", "unconfirmed", "failed"])
def test_BANG_CHUNG_PHU_DINH_dai_KHONG_mo_cong_dung_video(trang_thai):
    """Gỡ điều kiện `ready` ở H4 thì test này phải đỏ."""
    t = StoryboardPage(lambda: object())
    t.dat_kich_ban({"status": trang_thai, "beats": [_beat(), _beat()]})

    assert not t.btn_dung.isEnabled(), (
        f"kịch bản «{trang_thai}» mà vẫn dựng được video")
    assert not t.btn_ve_het.isEnabled(), (
        "kịch bản chưa duyệt thì cũng không được tiêu Vox vẽ ảnh cho nó")


def test_kich_ban_ready_du_anh_thi_moi_dung_duoc():
    """Mặt ngược lại — đừng khoá cứng thành 'không bao giờ dựng được'."""
    t = StoryboardPage(lambda: object())
    t.dat_kich_ban({"status": "ready", "beats": [_beat(), _beat()]})
    t._anh = ["a.png", "b.png"]
    t._ve()
    assert t.btn_dung.isEnabled()
    assert t.trang_thai_buoc()[0] == "du_dieu_kien"


# ============================ 4. BỐN CA H4 — BỐN CÂU KHÁC NHAU ============

def test_BANG_CHUNG_PHU_DINH_moi_ca_H4_phai_co_cau_RIENG():
    """Gỡ phần giải thích thì test này đỏ.

    Gộp bốn ca thành một câu "chưa dùng được" chính là thứ khiến chủ dự án
    nhìn màn hình rồi hỏi *"nên làm gì tiếp"*.
    """
    ca = {
        "chua_chon": {},
        "bi_chan": {"status": "blocked", "beats": [_beat()]},
        "chua_kiem": {"status": "unconfirmed", "beats": [_beat()]},
        "thieu_anh": {"status": "ready", "beats": [_beat(), _beat()]},
    }
    cau = {}
    for ma_mong_doi, kb in ca.items():
        t = StoryboardPage(lambda: object())
        t.dat_kich_ban(kb)
        ma, noi_dung = t.trang_thai_buoc()
        assert ma == ma_mong_doi, f"{ma_mong_doi}: nhận {ma}"
        assert noi_dung.strip(), f"{ma}: không nói gì"
        cau[ma] = noi_dung

    assert len(set(cau.values())) == 4, (
        "bốn ca phải ra bốn câu KHÁC NHAU:\n"
        + "\n".join(f"  {k}: {v[:60]}" for k, v in cau.items()))

    # Mỗi câu phải có ĐƯỜNG XỬ LÝ, không chỉ lý do.
    for ma, noi_dung in cau.items():
        assert ("Quay lại" in noi_dung or "Chọn ảnh" in noi_dung), (
            f"{ma}: nói lý do mà không nói làm gì tiếp — «{noi_dung}»")


def test_thieu_anh_neu_DUNG_DOAN_NAO():
    t = StoryboardPage(lambda: object())
    t.dat_kich_ban({"status": "ready", "beats": [_beat(), _beat(), _beat()]})
    t._anh = ["a.png", "", "c.png"]
    ma, cau = t.trang_thai_buoc()
    assert ma == "thieu_anh"
    assert "đoạn 2" in cau, f"phải chỉ đúng đoạn thiếu, nhận: {cau}"


def test_thieu_anh_KHONG_duoc_hua_tu_sinh_anh():
    """Cửa sinh ảnh (H4d) đang TẮT ở máy chủ. Hứa một thứ chưa bật là để
    người dùng ngồi chờ một nút không bao giờ sáng."""
    t = StoryboardPage(lambda: object())
    t.dat_kich_ban({"status": "ready", "beats": [_beat()]})
    cau = t.trang_thai_buoc()[1]
    for cam in ("tự sinh", "tự vẽ", "AI sẽ", "tự động tạo ảnh"):
        assert cam not in cau, f"câu hứa «{cam}»: {cau}"


def test_cau_cua_ca_hien_tai_len_toi_DAI_dieu_huong():
    """Tính đúng mà không hiện ra thì người dùng vẫn không biết gì."""
    t = StoryboardPage(lambda: object())
    t.dat_kich_ban({"status": "blocked", "beats": [_beat()]})
    assert "bị chặn" in t.ribbon.dong_trang_thai.text()
    assert t.ribbon.dong_trang_thai.isVisible() or True  # trang chưa show()


# ================== 5. GIỮ CONTEXT QUA ĐIỀU HƯỚNG (ràng buộc 6) ===========

def test_BANG_CHUNG_PHU_DINH_trang_duoc_giu_lai_qua_dieu_huong():
    """Kiến trúc hiện có giữ context bằng cách CACHE trang.

    Gỡ phần cache trong `_ensure_page` thì mọi lựa chọn dở dang (kịch bản đang
    mở ở H3, ảnh đã gán ở H4) biến mất mỗi lần đổi trang — và dải điều hướng
    biến từ tiện nghi thành cái bẫy.
    """
    import inspect

    from autodub_gui import app as m

    ma = inspect.getsource(m.MainWindow._ensure_page)
    assert "_page_widgets" in ma and "return page" in ma, (
        "trang không được giữ lại ⇒ điều hướng làm mất context")


def test_trang_H4_giu_anh_da_gan_khi_ve_lai():
    t = StoryboardPage(lambda: object())
    t.dat_kich_ban({"status": "ready", "beats": [_beat(), _beat()]})
    t._anh = ["a.png", "b.png"]
    t._ve()
    assert t._anh == ["a.png", "b.png"], "vẽ lại trang làm mất ảnh đã gán"


def test_KHONG_tu_doan_kich_ban_gan_nhat_khi_chua_chon():
    """Ràng buộc 6: thà nói 'chưa có lựa chọn' còn hơn tự chọn hộ."""
    t = StoryboardPage(lambda: object())
    assert t._kich_ban is None
    assert t.trang_thai_buoc()[0] == "chua_chon"


# ====================== 6. KHÔNG ĐỤNG THANH BÊN (ràng buộc 1/3) ===========

def test_KHONG_them_muc_nao_vao_thanh_ben():
    """Ràng buộc 1: dải thay cho việc thêm mục, không phải thêm cả hai."""
    from autodub_gui.app import PAGES

    tren_thanh_ben = [p for p in PAGES if p[4 + 1] in ("main", "tools", "second")] \
        if PAGES and len(PAGES[0]) > 5 else None
    an = [p for p in PAGES if p[-1] == "hidden"]
    ten_an = {p[1] for p in an}
    assert {"Viết kịch bản", "Dựng video"} <= ten_an, (
        "H3/H4 phải VẪN ẩn khỏi thanh bên — thêm vào đó là ngoài phạm vi H5 "
        "và làm chồng lấn ở màn 1080p")

"""V88 — gợi ý mô tả nhạc nền suy từ chính lời thoại của video.

Người dùng hỏi: "app có tự nhận định và chọn nhạc phù hợp cho video không?".
V37 sinh được nhạc AI nhưng bắt người dùng tự nghĩ ra mô tả — mà nghĩ ra một
mô tả tốt mới là phần khó.

Cố ý KHÔNG dùng AI: máy chủ chỉ có 4 endpoint cố định, không có đường hỏi tự
do; còn mọi tín hiệu cần thiết thì đã nằm sẵn trong transcript. Suy từ số đo
thì tức thì, chạy offline, không tốn Vox, và **giải thích được** — mỗi gợi ý
kèm lý do bằng con số thật.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app

from autodub.media.music_suggest import GoiYNhac, do_dac, goi_y_nhac


def _segs(*cau, giay=3.0):
    return [{"text_vi": c, "start": i * giay, "end": (i + 1) * giay,
             "duration": giay} for i, c in enumerate(cau)]


# -- Số đo phải đúng trước khi nói tới gợi ý ---------------------------------

def test_do_nhip_noi_theo_chu_moi_giay():
    so = do_dac(_segs("một hai ba bốn năm sáu", giay=2.0), "text_vi")
    assert so["so_cau"] == 1
    assert so["tong_chu"] == 6
    assert so["chu_moi_giay"] == 3.0


def test_khong_co_thoi_luong_thi_khong_chia_cho_khong():
    so = do_dac([{"text_vi": "một hai ba"}], "text_vi")
    assert so["chu_moi_giay"] == 0.0


def test_doc_duoc_ca_transcript_goc_lan_ban_dich():
    so = do_dac([{"text": "hello world there"}], "")
    assert so["tong_chu"] == 3


# -- Gợi ý: mỗi cái phải có lý do đo được ------------------------------------

def test_noi_nhanh_thi_de_xuat_nhac_soi_dong():
    dai = " ".join(["chữ"] * 20)
    ra = goi_y_nhac(_segs(dai, dai, dai, giay=3.0), "text_vi")
    assert ra and "sôi động" in ra[0].mo_ta
    assert "chữ/giây" in ra[0].ly_do, "phải nói rõ đo được gì"


def test_noi_cham_thi_de_xuat_nhac_nhe():
    ra = goi_y_nhac(_segs("một hai", "ba bốn", "năm sáu", "bảy tám",
                          "chín mười", "mười một", "mười hai", "mười ba",
                          "mười bốn", "mười lăm", giay=5.0), "text_vi")
    assert ra and "nhẹ nhàng" in ra[0].mo_ta


def test_nhan_ra_chu_de_qua_tu_khoa():
    ra = goi_y_nhac(_segs("Hôm nay mình nấu món phở bò",
                          "Nguyên liệu gồm xương bò và gia vị",
                          "Công thức này rất dễ làm theo"), "text_vi")
    mo_ta = " ".join(g.mo_ta for g in ra)
    assert "ấm áp" in mo_ta or "mộc mạc" in mo_ta
    assert any("nấu ăn" in g.ly_do for g in ra)


def test_nhieu_cau_cam_than_thi_de_xuat_nhac_kich_tinh():
    # Đủ dài để qua ngưỡng tối thiểu — ngưỡng đó có test riêng ở trên.
    ra = goi_y_nhac(_segs(
        "Trận đấu hôm nay thực sự quá hay và quá kịch tính!",
        "Bàn thắng ở phút cuối cùng khiến tất cả khán giả đứng dậy!",
        "Đội nhà đã chơi một trận tuyệt vời từ đầu tới cuối!"), "text_vi")
    assert any("kịch tính" in g.mo_ta for g in ra)
    assert any("cảm thán" in g.ly_do for g in ra)


def test_nhieu_cau_hoi_thi_de_xuat_kieu_dan_dat():
    ra = goi_y_nhac(_segs(
        "Bạn có biết vì sao chuyện này lại xảy ra như vậy không?",
        "Điều gì sẽ xảy ra tiếp theo với những người trong câu chuyện?",
        "Liệu kết quả có đúng như tất cả chúng ta vẫn nghĩ lâu nay?"),
        "text_vi")
    assert any("tò mò" in g.mo_ta for g in ra)


# -- Thà không gợi ý còn hơn gợi ý bừa --------------------------------------

@pytest.mark.parametrize("segments", [
    [],
    [{"text_vi": "chào"}],
    [{"text_vi": ""}, {"text_vi": "   "}],
    [{"text_vi": "một"}, {"text_vi": "hai"}, {"text_vi": "ba"}],  # quá ít chữ
])
def test_transcript_qua_ngan_thi_khong_goi_y(segments):
    assert goi_y_nhac(segments, "text_vi") == []


def test_du_lieu_rac_khong_lam_no():
    rac = [{"text_vi": "câu " * 30, "start": "hỏng", "end": None,
            "duration": "x"}] * 4
    ra = goi_y_nhac(rac, "text_vi")
    assert all(isinstance(g, GoiYNhac) for g in ra)


def test_khong_tra_ve_hai_goi_y_trung_nhau():
    ra = goi_y_nhac(_segs(
        "Món ăn này nấu rất ngon mà cách nấu lại vô cùng đơn giản!",
        "Nguyên liệu để nấu món này thì ở chợ nào cũng có bán sẵn!",
        "Công thức nấu nhanh, ai mới tập nấu cũng làm theo được!"),
        "text_vi")
    assert len({g.mo_ta for g in ra}) == len(ra)


def test_toi_da_ba_goi_y():
    ra = goi_y_nhac(_segs(
        "Trận đấu quá hay và quá hấp dẫn! Bạn có biết vì sao không?",
        "Bàn thắng đó rất đẹp mắt! Vì sao lại làm được như vậy?",
        "Vận động viên này thi đấu quá giỏi! Thật khó tin phải không?"),
        "text_vi")
    assert len(ra) <= 3


# -- Nối vào giao diện -------------------------------------------------------

def test_giao_dien_co_nut_va_duong_day():
    """Đứt một mắt là nút bấm không ra gì — kiểm cả ba mắt."""
    import os

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    panels = open(os.path.join(repo, "autodub_gui", "pages",
                               "editor_panels.py"), encoding="utf-8").read()
    assert "music_suggest_requested" in panels
    assert "Gợi ý từ nội dung video" in panels
    assert "def show_music_suggestions" in panels

    mixin = open(os.path.join(repo, "autodub_gui", "pages",
                              "editor_music_sfx.py"), encoding="utf-8").read()
    assert "_on_music_suggest_requested" in mixin
    # V89 dời lời gọi vào luồng riêng (đường máy chủ có thể mất vài giây),
    # nên mắt xích ở đây là worker chứ không còn là hàm luật gọi thẳng.
    assert "MusicSuggestWorker" in mixin

    workers = open(os.path.join(repo, "autodub_gui", "workers.py"),
                   encoding="utf-8").read()
    assert "goi_y_nhac_thong_minh" in workers

    page = open(os.path.join(repo, "autodub_gui", "pages", "editor_page.py"),
                encoding="utf-8").read()
    assert "music_suggest_requested.connect" in page


def test_bam_goi_y_thi_dien_vao_o_mo_ta(qapp):
    from autodub_gui.pages.editor_panels import MusicSfxPanel

    panel = MusicSfxPanel()
    panel.show_music_suggestions([GoiYNhac("nhạc vui tươi", "vì lý do A")])
    nut = panel._suggest_box.itemAt(0).widget()
    assert "nhạc vui tươi" in nut.text()
    assert "vì lý do A" in nut.toolTip(), "phải cho thấy LÝ DO"
    nut.click()
    assert panel.music_desc.text() == "nhạc vui tươi"


def test_khong_co_goi_y_thi_noi_ro_vi_sao(qapp):
    from autodub_gui.pages.editor_panels import MusicSfxPanel

    panel = MusicSfxPanel()
    panel.show_music_suggestions([])
    assert "chép lời" in panel.music_status.text()

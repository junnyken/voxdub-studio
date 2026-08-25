"""C30 — dán nguyên đoạn chia sẻ của Douyin/TikTok vào ô liên kết.

Chủ dự án dán đúng thứ nút Chia sẻ của Douyin sinh ra:

    9.76 y@t.rE 11/09 :5pm LJV:/ 今天晚餐吃照烧肥牛乌冬面 🍜 📍西瓜奶冻碗~
    还有甜辣脆皮鸡… #美食vlog https://v.douyin.com/9Rrk-r-GziU/ 复制此链接,
    打开Dou音搜索,直接观看视频!

App nhận NGUYÊN cụm đó làm địa chỉ →
`ERROR: [generic] '9.76 y@t.rE 11/09…'`. Người dùng không có cách nào đoán ra
là phải tự cắt lấy liên kết.
"""
from __future__ import annotations

import pytest

from autodub.media.downloader import normalize_url
from autodub.transcribe_tool import is_url
from autodub.utils import tach_lien_ket

DOAN_DOUYIN = (
    "9.76 y@t.rE 11/09 :5pm LJV:/ 今天晚餐吃照烧肥牛乌冬面 🍜 📍西瓜奶冻碗~ "
    "还有甜辣脆皮鸡，是清爽夏天的感觉！ #美食vlog #吃货日常 #伊利臻浓特浓牛奶 "
    "https://v.douyin.com/9Rrk-r-GziU/ 复制此链接，打开Dou音搜索，直接观看视频！")


def test_tach_dung_lien_ket_khoi_doan_chia_se_douyin():
    assert tach_lien_ket(DOAN_DOUYIN) == "https://v.douyin.com/9Rrk-r-GziU/"


def test_dau_cau_TIENG_TRUNG_ngay_sau_lien_ket_khong_dinh_vao():
    """Cắt tới khoảng trắng là chưa đủ — Douyin dán 「，」ngay sau liên kết."""
    assert tach_lien_ket("xem nè https://v.douyin.com/abc/，复制此链接") \
        == "https://v.douyin.com/abc/"


@pytest.mark.parametrize("duoi", [".", ",", "!", "?", ")", "]"])
def test_dau_cau_dinh_duoi_khong_thuoc_dia_chi(duoi):
    assert tach_lien_ket(f"link đây https://youtu.be/abc{duoi}") \
        == "https://youtu.be/abc"


def test_lien_ket_sach_thi_giu_nguyen():
    for u in ("https://youtu.be/abc123",
              "http://a.vn/x?y=1&z=2"):
        assert tach_lien_ket(u) == u


def test_lay_lien_ket_DAU_TIEN_khi_co_nhieu():
    assert tach_lien_ket("a https://mot.vn/1 b https://hai.vn/2") \
        == "https://mot.vn/1"


def test_DUONG_DAN_TEP_khong_bi_bien_thanh_rong():
    """Biến đường dẫn tệp thành chuỗi rỗng là làm hỏng một đường đang chạy tốt."""
    for p in ("C:/Users/trieunt/Downloads/Học luật ads 1.m4a",
              "/home/a/b.mp4", "phim.mp4"):
        assert tach_lien_ket(p) == p


def test_dia_chi_thieu_luoc_do_van_giu_nguyen():
    """`normalize_url` mới là chỗ thêm https:// — đừng cắt mất ở đây."""
    assert tach_lien_ket("www.youtube.com/watch?v=xyz") \
        == "www.youtube.com/watch?v=xyz"


def test_chuoi_rong_khong_no():
    assert tach_lien_ket("") == ""
    assert tach_lien_ket(None) == ""


# -- Đã nối vào đường chạy thật chưa ----------------------------------------

def test_doan_chia_se_duoc_coi_la_LIEN_KET_khong_phai_tep():
    """Không tách thì nó bị định tuyến sang nhánh «tìm tệp trên máy» rồi báo
    "không tìm thấy file" — đúng kỹ thuật, vô nghĩa với người dùng."""
    assert is_url(DOAN_DOUYIN) is True


def test_duong_tai_nhan_dung_dia_chi():
    assert normalize_url(DOAN_DOUYIN) == "https://v.douyin.com/9Rrk-r-GziU/"


def test_tach_TRUOC_moi_phep_kiem_khac_trong_normalize_url():
    """Mọi phép kiểm bên dưới (`urlparse`, `netloc`) đều trượt nếu chuỗi còn
    dính chữ."""
    from tests.doc_ma import goi_truoc

    assert goi_truoc(normalize_url, "tach_lien_ket", "urlparse")


def test_van_viet_lai_duoc_lien_ket_douyin_dang_modal():
    """Bản vá không được làm hỏng phép viết lại sẵn có."""
    assert normalize_url("Xem đi https://www.douyin.com/discover?modal_id=7123") \
        == "https://www.douyin.com/video/7123"


# -- Tách phải xảy ra TRƯỚC phép hỏi Douyin (mini-spec C31) -----------------
#
# C30 tách bên trong `normalize_url`, nhưng `is_douyin_url` được hỏi TRƯỚC đó.
# Dán nguyên đoạn chia sẻ thì câu hỏi "đây có phải Douyin không" nhận cả cụm
# chữ và trả lời KHÔNG → đường tải Douyin riêng (dựng ra vì bộ tải Douyin của
# yt-dlp hỏng sẵn ở thượng nguồn) bị bỏ qua, rơi xuống yt-dlp rồi chết với
# "Fresh cookies are needed". Người dùng thật đã gặp đúng dòng đó.

def test_ca_doan_chia_se_KHONG_duoc_nhan_ra_la_douyin():
    """Đây là lý do phải tách trước — ghi lại để không ai 'tối ưu' bỏ đi."""
    from autodub.media.douyin import is_douyin_url

    assert is_douyin_url(DOAN_DOUYIN) is False
    assert is_douyin_url(tach_lien_ket(DOAN_DOUYIN)) is True


def test_download_video_tach_TRUOC_khi_hoi_douyin():
    from tests.doc_ma import goi_truoc

    from autodub.media.downloader import download_video

    assert goi_truoc(download_video, "tach_lien_ket", "is_douyin_url"), \
        "đường tải Douyin riêng sẽ bị bỏ qua khi dán đoạn chia sẻ"


def test_moi_cho_hoi_douyin_deu_tach_truoc():
    """Có HAI hàm tải cùng mẫu này — sửa một chỗ là còn sót chỗ kia."""
    import ast
    import io as _io

    nguon = _io.open("autodub/media/downloader.py", encoding="utf-8").read()
    cay = ast.parse(nguon)
    from tests.doc_ma import cac_luot_goi

    ham_hoi_douyin = []
    for node in ast.walk(cay):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ten_goi = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
            if any(getattr(g.func, "id", "") == "is_douyin_url" for g in ten_goi):
                ham_hoi_douyin.append(node)

    assert len(ham_hoi_douyin) >= 2, "mẫu này vốn có ở hai chỗ"
    for node in ham_hoi_douyin:
        goi = []
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                ten = getattr(n.func, "id", "") or getattr(n.func, "attr", "")
                if ten in ("tach_lien_ket", "is_douyin_url"):
                    goi.append((n.lineno, ten))
        goi.sort()
        thu_tu = [t for _l, t in goi]
        assert thu_tu[0] == "tach_lien_ket", \
            f"{node.name}(): hỏi Douyin trước khi tách liên kết"


def test_loi_doi_cookie_co_loi_soan_san():
    """Dòng gốc của yt-dlp không gợi ý gì làm được trong app."""
    from autodub_gui.dub_constants import friendly_error

    soan = friendly_error(
        "ERROR: [Douyin] 7650489705510783333: Fresh cookies "
        "(not necessarily logged in) are needed")
    assert soan is not None
    tieu_de, cach_chua = soan
    assert "cookie" in tieu_de.lower()
    assert "Douyin.bat" in cach_chua, "phải chỉ đúng tệp cài có thật trong app"

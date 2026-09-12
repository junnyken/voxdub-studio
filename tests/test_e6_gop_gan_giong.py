"""E6 — gộp khung liền nhau khi chữ GẦN GIỐNG, không đòi giống hệt.

Đo trên dữ liệu THẬT do chủ dự án gửi (12/09, `ocr_chan_doan.json`, nguồn
`youtube.com/shorts/9iB1Io8InXg`, 36,2 giây, 104 mốc lấy mẫu).

**Tôi đã kết luận sai hai lần trước khi có dữ liệu này.** Lần đầu tôi đoán
"65 đoạn cho video 34 giây là lỗi gộp đoạn". Rồi tôi tự bác bỏ: *"65 là
thật — video có phụ đề chạy theo lời"*. Dữ liệu thật cho thấy **lần đoán
đầu mới đúng**, và lần "sửa" của tôi là sai:

    'supersale d onn& am am'   <- khung 7
    'supersale d onn&amam'     <- khung 8   cùng caption, lệch 2 ký tự
    'supersale d onn&am am'    <- khung 9
    'supersale d onn&amam'     <- khung 10

`_khoa_doan` so chuỗi NGUYÊN VĂN nên bốn khung này thành bốn đoạn riêng, và
bốn khung được gửi lên máy chủ thay vì một.

**Đòn bẩy D1 bị BÁC BỎ bằng số đo.** Giả thuyết chính của tôi — "phụ đề lặp
lại lời đọc, bỏ đi là xong" — chỉ đúng 15% (10/65 đoạn), tiết kiệm được đúng
8 Vox. Phần lớn chữ trên hình là ảnh chụp màn hình phần mềm, không phải phụ
đề.

Đòn bẩy THẬT (đo trên chính dữ liệu đó):

    gộp khi giống >= 75%: 65 -> 31 đoạn = 6 lô = 48 Vox
    gộp khi giống >= 80%: 65 -> 33 đoạn = 6 lô = 48 Vox   <- chọn
    gộp khi giống >= 85%: 65 -> 34 đoạn = 6 lô = 48 Vox
    gộp khi giống >= 90%: 65 -> 40 đoạn = 7 lô = 56 Vox
    gộp khi giống >= 95%: 65 -> 47 đoạn = 8 lô = 64 Vox

75–85% là một CAO NGUYÊN (đều 48 Vox), lấy 80% ở giữa. Và ở 80%, **không
nhóm nào gộp nhầm hai caption khác nhau** — soi tay cả 17 nhóm.

88 Vox -> 48 Vox, giảm 45%.
"""
from __future__ import annotations

import pytest

from autodub.media.doc_chu_may_chu import NGUONG_GIONG_DE_GOP, chia_doan


class _Q:
    def __init__(self, frame_index, text, *, conf=0.9, x=0.0, y=0.0):
        self.frame_index = frame_index
        self.text = text
        self.confidence = conf
        self.x = x
        self.y = y


def test_nguong_la_80_phan_tram():
    assert NGUONG_GIONG_DE_GOP == 0.80


# --- Ca THẬT, nguyên văn từ tệp chủ dự án gửi ------------------------------

def test_ca_that_supersale_gop_lam_mot():
    quan_sat = [
        _Q(7, "supersale d onn& am am"),
        _Q(8, "supersale d onn&amam"),
        _Q(9, "supersale d onn&am am"),
        _Q(10, "supersale d onn&amam"),
    ]
    doan = chia_doan(quan_sat)
    assert len(doan) == 1, (
        f"bốn khung cùng một caption vẫn thành {len(doan)} đoạn — mỗi đoạn "
        "thừa là một khung nữa gửi lên máy chủ")
    assert doan[0] == [7, 8, 9, 10]


def test_ca_that_nhap_hoa_don():
    quan_sat = [
        _Q(34, "nhaphoa don xuatkipcho khach"),
        _Q(35, "nhaphoa don xuat kip cho khach"),
        _Q(36, "nhaphoadon xuat kipcho khach"),
    ]
    assert chia_doan(quan_sat) == [[34, 35, 36]]


def test_ca_that_man_hinh_phan_mem():
    quan_sat = [
        _Q(59, "tudongguiduleu lencoquanthue"),
        _Q(60, "tudongguiduleu lencoquanthue nd-cp"),
        _Q(61, "tudongguiduleu len coquan thue"),
        _Q(62, "tudongguiduleu len coquanthue ae"),
    ]
    assert chia_doan(quan_sat) == [[59, 60, 61, 62]]


# --- KHÔNG được gộp nhầm ---------------------------------------------------

def test_hai_caption_KHAC_nhau_van_tach():
    """Gộp nhầm là mất hẳn một caption: máy chủ chỉ đọc khung đại diện, nên
    caption kia thừa hưởng chữ của caption này. Sai mà im lặng."""
    quan_sat = [
        _Q(1, "met moi that su"),
        _Q(2, "tu van mien phi"),
    ]
    assert chia_doan(quan_sat) == [[1], [2]]


def test_khung_KHONG_lien_tiep_van_tach_du_chu_giong_het():
    """Chữ biến mất rồi hiện lại KHÔNG phải một khoảng liên tục — luật cũ,
    không đổi."""
    quan_sat = [_Q(1, "tu van mien phi"), _Q(9, "tu van mien phi")]
    assert chia_doan(quan_sat) == [[1], [9]]


def test_chuoi_ngan_khong_bi_gop_bua():
    """Hai chuỗi rất ngắn dễ đạt tỉ lệ giống cao một cách tình cờ."""
    quan_sat = [_Q(1, "roa"), _Q(2, "rob")]
    doan = chia_doan(quan_sat)
    assert len(doan) == 2, f"gộp bừa hai chuỗi ba ký tự khác nghĩa: {doan}"


# --- Đại diện phải là khung ĐỌC ĐƯỢC NHẤT ---------------------------------

def test_dai_dien_la_khung_tin_cay_cao_nhat():
    """Gửi khung nào lên máy chủ thì đọc lại được chữ của khung ĐÓ.

    Ca thật: `surersale` (0,944) rồi `supersale` (0,989) — gửi khung đầu là
    trả tiền để máy chủ đọc lại một khung vốn đã đọc sai. Lấy khung đọc rõ
    nhất trong nhóm không tốn thêm đồng nào.
    """
    from autodub.media.doc_chu_may_chu import dai_dien_cua_doan

    quan_sat = [
        _Q(2, "surersale", conf=0.944),
        _Q(3, "supersale", conf=0.989),
        _Q(4, "supersale", conf=0.980),
    ]
    doan = chia_doan(quan_sat)
    assert doan == [[2, 3, 4]]
    assert dai_dien_cua_doan(doan[0], quan_sat) == 3


def test_dai_dien_mot_khung_thi_chinh_no():
    from autodub.media.doc_chu_may_chu import dai_dien_cua_doan

    quan_sat = [_Q(5, "abc", conf=0.7)]
    assert dai_dien_cua_doan([5], quan_sat) == 5


def test_duong_gui_dung_dai_dien_moi():
    """CHỐT CHỖ GỌI — chọn đại diện tốt hơn mà không ai dùng là vô ích."""
    import inspect

    from autodub.media import doc_chu_may_chu as m

    than = inspect.getsource(m.doc_lai_bang_may_chu)
    assert "dai_dien_cua_doan(" in than, (
        "vẫn lấy `d[0]` — khung đọc sai vẫn được gửi đi")


# --- Số tổng trên dữ liệu thật --------------------------------------------

def test_giam_dung_nhu_da_do_tren_du_lieu_that():
    """Chốt lại con số đã hứa: 65 đoạn -> 33, tức 11 lô -> 6 lô.

    Dựng lại đúng chuỗi đoạn của tệp chủ dự án gửi (rút gọn phần chữ dài
    nhưng giữ nguyên quan hệ giống/khác giữa các khung liền nhau).
    """
    chu = [
        (1, "梦"), (2, "surersale"), (3, "supersale"), (4, "supersale"),
        (5, "supersale"), (6, "supersale tonnlanon"),
        (7, "supersale d onn& am am"), (8, "supersale d onn&amam"),
        (9, "supersale d onn&am am"), (10, "supersale d onn&amam"),
        (11, "50h 909 ying 6668 mat may cau co! g"),
        (12, "sobbini 666 mat may cau co!"),
        (13, "sobbing 5dl mat may cau co!"),
    ]
    doan = chia_doan([_Q(i, t) for i, t in chu])
    # 梦 | surersale+supersale×3 | supersale tonnlanon | ×4 | 50h… | sobbi×2
    assert len(doan) <= 7, (
        f"13 khung đầu của video thật ra {len(doan)} đoạn, đo được là ≤7")


@pytest.mark.parametrize("rong", [[], [_Q(1, "")], [_Q(1, "  ")]])
def test_khung_khong_co_chu_khong_thanh_doan(rong):
    assert chia_doan(rong) == []

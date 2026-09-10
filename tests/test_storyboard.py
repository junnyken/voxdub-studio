"""Storyboard — mini-spec H4a.

Trọng tâm là **cổng của H4**: kịch bản chưa `ready` thì không dựng được dòng
thời gian, và cổng đó phải nằm ở tầng thấp nhất chứ không phải chỉ ở nút bấm.
Một kịch bản `blocked` đi tiếp thành video là đúng thứ cả H3 dựng ra để chặn.

Phần còn lại canh chuyện ước lượng thời gian đọc không được giả vờ chính xác
hơn thực tế đo được.
"""
from __future__ import annotations

import pytest

from autodub import storyboard as sb


def _beat(loi="Câu lời đọc bình thường thôi", **kw):
    goc = {"beatType": "hook", "voiceoverTextVi": loi,
           "captionSuggestionVi": "Chữ trên hình", "visualBriefVi": "Cận cảnh"}
    goc.update(kw)
    return goc


def _kich_ban(status="ready", beats=None):
    return {"status": status, "beats": beats if beats is not None else [_beat()]}


# ------------------------------------------------------- cổng của H4 -------

@pytest.mark.parametrize("trang_thai", ["blocked", "unconfirmed", "draft",
                                        "checking", "failed", ""])
def test_kich_ban_chua_ready_thi_KHONG_dung_duoc(trang_thai):
    with pytest.raises(sb.KichBanChuaDungDuoc) as e:
        sb.dung_storyboard(_kich_ban(status=trang_thai))
    # Câu báo phải nói rõ trạng thái, không phải "có lỗi, thử lại".
    assert trang_thai in str(e.value) or "không rõ" in str(e.value)


def test_chi_ready_moi_dung_duoc():
    ra = sb.dung_storyboard(_kich_ban())
    assert len(ra.doan) == 1


def test_kich_ban_ready_nhung_rong_cung_bi_chan():
    with pytest.raises(sb.KichBanChuaDungDuoc):
        sb.dung_storyboard(_kich_ban(beats=[]))


# --------------------------------------------------- đếm âm tiết / câu -----

def test_dem_am_tiet_bo_dau_cau():
    assert sb.dem_am_tiet("Thử đi.") == 2
    assert sb.dem_am_tiet("Xong, rồi!") == 2
    assert sb.dem_am_tiet("") == 0
    assert sb.dem_am_tiet(None) == 0


def test_dem_cau():
    assert sb.dem_cau("Một câu thôi.") == 1
    assert sb.dem_cau("Câu một. Câu hai! Câu ba?") == 3
    # Không có dấu kết câu vẫn là một câu, không phải không câu nào.
    assert sb.dem_cau("không có dấu chấm") == 1
    assert sb.dem_cau("   ") == 0


# ------------------------------------------------ ước lượng thời gian ------

def test_uoc_luong_khop_so_do_that():
    # Số liệu đo thật 10/09 bằng VieNeu (4 giọng × 4 câu). Sai lệch cho phép
    # 10% — chính giọng đọc đã chênh nhau 1,21 lần nên đòi khít hơn là tự
    # lừa mình.
    for am_tiet, do_duoc in ((2, 1.44), (11, 5.88), (15, 7.88), (21, 11.04)):
        text = " ".join(["từ"] * am_tiet) + "."
        ul = sb.uoc_luong_giay_doc(text)
        assert abs(ul.giay - do_duoc) / do_duoc < 0.10, (
            f"{am_tiet} âm tiết: ước {ul.giay:.2f}s nhưng đo được {do_duoc}s")


def test_uoc_luong_tra_ve_KHOANG_khong_phai_mot_con_so():
    # Giọng nhanh nhất và chậm nhất chênh 1,21 lần. Đưa một con số lẻ tới hai
    # chữ số thập phân là giả vờ chính xác, và người dùng sẽ dựng hình khít
    # theo nó rồi lệch tiếng.
    ul = sb.uoc_luong_giay_doc("Một câu dài vừa phải để đo cho ra khoảng")
    assert ul.giay_min < ul.giay < ul.giay_max
    assert ul.giay_max / ul.giay_min > 1.2, "khoảng phải phủ được chênh lệch giọng"


def test_cau_ngan_ton_nhieu_hon_moi_am_tiet_dung_nhu_do_duoc():
    # Phụ trội đầu/cuối là có thật: câu 2 âm tiết đo được 0,72 giây mỗi âm
    # tiết, câu 21 âm tiết chỉ 0,53. Mô hình tuyến tính thuần (không phụ
    # trội) sẽ cho hai con số bằng nhau — tức là sai.
    ngan = sb.uoc_luong_giay_doc("Thử đi.")
    dai = sb.uoc_luong_giay_doc(" ".join(["từ"] * 21) + ".")
    assert ngan.giay / 2 > dai.giay / 21 * 1.2


def test_loi_doc_rong_thi_khong_giay_nao():
    assert sb.uoc_luong_giay_doc("").giay == 0.0


# ------------------------------------------------------ dòng thời gian -----

def test_cac_doan_noi_tiep_nhau_khong_ho_khong_chong():
    ra = sb.dung_storyboard(_kich_ban(beats=[
        _beat("Đoạn một ngắn thôi."),
        _beat("Đoạn hai dài hơn một chút cho khác nhau."),
        _beat("Đoạn ba."),
    ]))
    assert ra.doan[0].bat_dau_s == 0.0
    for truoc, sau in zip(ra.doan, ra.doan[1:]):
        assert abs(sau.bat_dau_s - truoc.ket_thuc_s) < 0.02, "dòng thời gian bị hở"
    assert abs(ra.tong_giay - ra.doan[-1].ket_thuc_s) < 0.02


def test_doan_dai_ngan_khac_nhau_thi_giay_khac_nhau():
    # Đây là lý do storyboard tồn tại: `dung_video()` hiện chia đều thời
    # lượng cho mọi ảnh, nên đoạn hook ngắn và đoạn bằng chứng dài bị giữ
    # hình bằng nhau.
    ra = sb.dung_storyboard(_kich_ban(beats=[
        _beat("Thử đi."),
        _beat("Cả nhà bốn người có bữa sáng nóng hổi, còn mẹ thì thảnh thơi "
              "pha ly cà phê uống trọn vẹn."),
    ]))
    assert ra.doan[1].giay > ra.doan[0].giay * 3


def test_doan_khong_co_loi_doc_thi_canh_bao():
    ra = sb.dung_storyboard(_kich_ban(beats=[_beat(""), _beat("Có lời")]))
    assert any("im lặng" in c for c in ra.canh_bao)


# ----------------------------------------------------- so nhịp với nguồn ---

def _blueprint(dai_giay):
    return {"beats": [{"startS": 0, "endS": dai_giay}]}


def test_kich_ban_dai_gap_ruoi_nguon_thi_canh_bao():
    # Cả điểm của H2 là học NHỊP video tham khảo. Viết ra kịch bản dài gấp
    # đôi thì nhịp học được không còn nghĩa gì — phải nói ngay, không để
    # người dùng phát hiện sau khi đã dựng xong video.
    dai = _beat(" ".join(["từ"] * 60) + ".")
    ra = sb.dung_storyboard(_kich_ban(beats=[dai]), _blueprint(10))
    assert any("dài gấp" in c for c in ra.canh_bao)


def test_kich_ban_ngan_hon_han_nguon_cung_canh_bao():
    ra = sb.dung_storyboard(_kich_ban(beats=[_beat("Thử đi.")]), _blueprint(60))
    assert any("ngắn hơn" in c for c in ra.canh_bao)


def test_dai_xap_xi_nguon_thi_KHONG_canh_bao():
    # Báo nhầm ở đây thì người dùng học cách bỏ qua cảnh báo.
    ra = sb.dung_storyboard(_kich_ban(beats=[_beat(" ".join(["từ"] * 20) + ".")]),
                            _blueprint(10.5))
    assert not any("gấp" in c or "ngắn hơn" in c for c in ra.canh_bao)


def test_khong_co_blueprint_thi_khong_so_nhip():
    ra = sb.dung_storyboard(_kich_ban())
    assert ra.nguon_giay == 0.0
    assert not any("gấp" in c for c in ra.canh_bao)


# --------------------------------------------------------- ranh giới -------

def test_storyboard_KHONG_goi_mo_hinh_va_KHONG_dung_mang():
    # H4a là phép tính thuần, chạy trên máy người dùng. Nối cổng AI hay HTTP
    # vào đây là biến một bước chỉnh-cho-vừa-ý thành một bước tính tiền.
    import inspect
    ma = inspect.getsource(sb)
    for cam in ("saas_client", "requests", "urllib", "gateway", "http"):
        assert cam not in ma, f"storyboard không được phụ thuộc: {cam}"


def test_uoc_luong_dung_tren_cau_CHUA_TUNG_do():
    """Kiểm chéo — số đo thật 10/09 trên 5 câu KHÔNG nằm trong bộ dùng để
    khớp hằng số (mỗi câu đo trung bình 3 giọng).

    Không có phép kiểm này thì hai hằng số chỉ chứng minh được chúng khớp
    với chính dữ liệu đã sinh ra chúng — vòng tròn.
    """
    do_thuc_te = [
        ("Bạn đã bao giờ đứng trước tủ lạnh đầy đồ mà vẫn không biết nấu gì chưa?", 8.32),
        ("Chỉ cần cắm điện, chọn chế độ, rồi đi làm việc khác.", 6.51),
        ("Đây rồi.", 1.49),
        ("Sau hai tuần dùng thử, chị Lan ở Gò Vấp nói bữa sáng nhà chị giờ "
         "nhanh hơn hẳn, mà con vẫn ăn hết suất.", 12.91),
        ("Hộp đựng tháo rời được nên rửa cũng nhàn.", 4.96),
    ]
    lech = []
    for cau, do_duoc in do_thuc_te:
        ul = sb.uoc_luong_giay_doc(cau)
        lech.append(abs(ul.giay - do_duoc) / do_duoc)
        assert ul.giay_min <= do_duoc <= ul.giay_max, (
            f"số đo thật {do_duoc}s rơi NGOÀI khoảng "
            f"[{ul.giay_min:.2f}, {ul.giay_max:.2f}] — khoảng đang quá hẹp")
    tb = sum(lech) / len(lech)
    assert tb < 0.06, f"sai lệch trung bình {tb*100:.1f}% (đo được 3,3%)"

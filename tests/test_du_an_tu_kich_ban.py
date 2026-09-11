"""Dựng dự án từ kịch bản brand — mini-spec H4c.

Phép kiểm quan trọng nhất: **`editor.load_work_dir()` mở được thật**. Kiểm
kiểu "có tệp transcript" thì xanh cả khi Trình chỉnh sửa từ chối mở vì thiếu
video nguồn — đúng cái bẫy làm H4c trở nên vô dụng mà test vẫn báo ổn.
"""
from __future__ import annotations

import json
import os

import pytest

from autodub import du_an_tu_kich_ban as da
from autodub.storyboard import KichBanChuaDungDuoc


def _beat(loi, caption="Chữ trên hình", **kw):
    goc = {"beatType": "hook", "voiceoverTextVi": loi,
           "captionSuggestionVi": caption, "visualBriefVi": "Cận cảnh sản phẩm"}
    goc.update(kw)
    return goc


def _kich_ban(status="ready", beats=None):
    return {
        "id": "s1", "flowBlueprintId": "bp1", "brandProfileId": "br1",
        "originalityCheckVersion": 1, "status": status,
        "beats": beats or [
            _beat("Sáng nào cũng vội, bếp thì ngổn ngang."),
            _beat("Cắm điện, ba phút là nóng, thả đồ vào bấm nút là xong.",
                  beatType="proof"),
        ],
    }


@pytest.fixture()
def anh(tmp_path):
    """Hai tệp ảnh THẬT trên đĩa — hàm ghép có kiểm tệp còn tồn tại."""
    from PIL import Image
    ds = []
    for i in range(2):
        p = tmp_path / f"anh{i}.png"
        Image.new("RGB", (64, 64), "white").save(p)
        ds.append(str(p))
    return ds


class _GhepGia:
    """Thay ffmpeg — test không cần dựng video thật, chỉ cần đúng tham số."""

    def __init__(self):
        self.lan_goi = []

    def __call__(self, duong_anh, duong_ra, *, giay_moi_anh, giay_chuyen=0.3):
        self.lan_goi.append({"anh": list(duong_anh), "ra": duong_ra,
                             "giay": list(giay_moi_anh), "chuyen": giay_chuyen})
        with open(duong_ra, "wb") as f:
            f.write(b"video gia")
        return duong_ra

    def do_thoi_luong(self, _duong_video):
        """Phép đo khớp với hàm ghép giả này.

        Cổng thời lượng của H4c-1 ĐO video thật bằng ffprobe; tệp 9 byte ở
        trên thì không đo được. Giả hàm ghép thì phải giả luôn phép đo, và
        khai rõ ra như vậy là cố ý: nó nhắc rằng những lượt test dưới đây
        KHÔNG chứng minh được gì về thời lượng thật — việc đó là của
        `tests/test_h4c1_thoi_luong.py`, nơi chạy ffmpeg thật.
        """
        return sum(self.lan_goi[-1]["giay"]) if self.lan_goi else None


# ------------------------------------------------------------- cổng H4 ----

def test_kich_ban_chua_ready_thi_khong_dung_duoc_du_an(tmp_path, anh):
    # Cổng nằm ở `dung_storyboard()`; H4c không kiểm lại (một chỗ chặn là đủ,
    # hai chỗ thì có ngày lệch nhau) — nhưng phải chắc nó CÓ chặn tới đây.
    with pytest.raises(KichBanChuaDungDuoc):
        da.dung_du_an(_kich_ban(status="blocked"), anh,
                      str(tmp_path / "duan"), ghep_video=(g := _GhepGia()), do_thoi_luong=g.do_thoi_luong)


def test_khong_tao_thu_muc_nao_khi_bi_chan(tmp_path, anh):
    duan = tmp_path / "duan"
    with pytest.raises(KichBanChuaDungDuoc):
        da.dung_du_an(_kich_ban(status="unconfirmed"), anh, str(duan),
                      ghep_video=(g := _GhepGia()), do_thoi_luong=g.do_thoi_luong)
    assert not duan.exists(), "bị chặn mà vẫn để lại thư mục dở dang"


# --------------------------------------------------------- thiếu ảnh -----

def test_thieu_anh_thi_bao_ro_DOAN_NAO(tmp_path, anh):
    with pytest.raises(da.ThieuAnh, match="đoạn 2"):
        da.dung_du_an(_kich_ban(), anh[:1], str(tmp_path / "duan"),
                      ghep_video=(g := _GhepGia()), do_thoi_luong=g.do_thoi_luong)


def test_anh_rong_cung_tinh_la_thieu(tmp_path, anh):
    with pytest.raises(da.ThieuAnh, match="đoạn 1"):
        da.dung_du_an(_kich_ban(), ["", anh[1]], str(tmp_path / "duan"),
                      ghep_video=(g := _GhepGia()), do_thoi_luong=g.do_thoi_luong)


def test_KHONG_tu_sinh_anh_thay_nguoi_dung(tmp_path, anh):
    # Guardrail 4 của H4: sinh ảnh tốn 30 Vox mỗi tấm; tự bấm hộ là tiêu tiền
    # của người ta mà không xin phép. Thiếu ảnh phải DỪNG, không "tự lo".
    import inspect
    ma = inspect.getsource(da)
    for cam in ("product-scene", "product_scene", "dung_boi_canh"):
        assert cam not in ma, f"H4c không được tự gọi đường sinh ảnh: {cam}"


# ------------------------------------------- Trình chỉnh sửa mở được ------

def test_TRINH_CHINH_SUA_MO_DUOC_du_an_vua_dung(tmp_path, anh):
    # Đây là phép kiểm thật sự của H4c. Kiểm "có tệp transcript" thì xanh cả
    # khi Trình chỉnh sửa từ chối mở vì thiếu video nguồn.
    from autodub import editor

    duan = str(tmp_path / "duan")
    ket = da.dung_du_an(_kich_ban(), anh, duan, ghep_video=(g := _GhepGia()), do_thoi_luong=g.do_thoi_luong)

    state = editor.load_work_dir(duan)
    assert len(state.segments) == 2
    assert state.video_path == ket.duong_video, "phải tìm ra video nguồn"
    assert state.segments[0]["text_vi"].startswith("Sáng nào cũng vội")


def test_ten_video_khong_dinh_tien_to_bi_BO_QUA(tmp_path, anh):
    # `_find_source_video()` cố ý bỏ qua `dubbed_`/`retimed_`/`slowed_` vì
    # chúng là sản phẩm phái sinh. Đặt tên trúng một trong ba là dự án không
    # mở được, với một lỗi chẳng liên quan gì tới nguyên nhân thật.
    for cam in ("dubbed_video", "retimed_video", "slowed_video"):
        assert not da.TEN_VIDEO_NGUON.startswith(cam)


def test_segment_dung_khuon_trinh_chinh_sua_doc(tmp_path, anh):
    duan = str(tmp_path / "duan")
    ket = da.dung_du_an(_kich_ban(), anh, duan, ghep_video=(g := _GhepGia()), do_thoi_luong=g.do_thoi_luong)
    with open(ket.duong_transcript, encoding="utf-8") as f:
        segs = json.load(f)

    assert [s["id"] for s in segs] == [1, 2], "id phải bắt đầu từ 1, liên tục"
    for s in segs:
        for truong in ("id", "start", "end", "text", "text_vi", "sub_vi"):
            assert truong in s, f"segment thiếu trường {truong}"
        assert s["end"] > s["start"]
    assert segs[1]["start"] == pytest.approx(segs[0]["end"]), "dòng thời gian hở"


def test_loi_doc_va_chu_tren_hinh_la_HAI_thu_khac_nhau(tmp_path, anh):
    # Lời đọc là câu nói đầy đủ (đưa cho TTS), caption là chữ ngắn hiện trên
    # hình. Gộp làm một thì hoặc phụ đề dài lê thê hoặc giọng đọc cụt lủn.
    kb = _kich_ban(beats=[_beat("Một câu lời đọc đầy đủ và dài hơn hẳn.",
                                caption="Ngắn thôi")])
    duan = str(tmp_path / "duan")
    ket = da.dung_du_an(kb, anh[:1], duan, ghep_video=(g := _GhepGia()), do_thoi_luong=g.do_thoi_luong)
    with open(ket.duong_transcript, encoding="utf-8") as f:
        seg = json.load(f)[0]
    assert seg["text_vi"] != seg["sub_vi"]
    assert seg["sub_vi"] == "Ngắn thôi"


def test_caption_rong_thi_phu_de_lay_luon_loi_doc(tmp_path, anh):
    kb = _kich_ban(beats=[_beat("Câu lời đọc.", caption="")])
    ket = da.dung_du_an(kb, anh[:1], str(tmp_path / "duan"),
                        ghep_video=(g := _GhepGia()), do_thoi_luong=g.do_thoi_luong)
    with open(ket.duong_transcript, encoding="utf-8") as f:
        seg = json.load(f)[0]
    assert seg["sub_vi"] == "Câu lời đọc.", "để trống phụ đề là mất chữ trên hình"


# ----------------------------------------------- thời lượng riêng đoạn ----

def test_moi_doan_ghep_dung_thoi_luong_cua_no(tmp_path, anh):
    ghep = _GhepGia()
    kb = _kich_ban(beats=[_beat("Thử đi."),
                          _beat("Cả nhà bốn người có bữa sáng nóng hổi, còn mẹ "
                                "thì thảnh thơi pha ly cà phê uống trọn vẹn.")])
    ket = da.dung_du_an(kb, anh, str(tmp_path / "duan"), ghep_video=ghep, do_thoi_luong=ghep.do_thoi_luong)

    giay = ghep.lan_goi[0]["giay"]
    assert len(giay) == 2
    assert giay[1] > giay[0] * 3, "đoạn dài phải giữ hình lâu hơn hẳn"
    assert giay == [d.giay for d in ket.storyboard.doan]


# --------------------------------------------------------- truy nguồn -----

def test_ghi_lai_NGUON_GOC_de_du_an_khong_thanh_hop_den(tmp_path, anh):
    duan = str(tmp_path / "duan")
    ghep = _GhepGia()
    da.dung_du_an(_kich_ban(), anh, duan, ghep_video=ghep,
                  do_thoi_luong=ghep.do_thoi_luong)
    with open(os.path.join(duan, "data", da.TEN_NGUON_GOC), encoding="utf-8") as f:
        nguon = json.load(f)
    assert nguon["brand_script_id"] == "s1"
    assert nguon["flow_blueprint_id"] == "bp1"
    assert nguon["brand_profile_id"] == "br1"
    assert nguon["originality_check_version"] == 1
    assert nguon["so_doan"] == 2


def test_canh_bao_lech_nhip_duoc_giu_lai_trong_nguon_goc(tmp_path, anh):
    # Cảnh báo chỉ hiện lúc dựng rồi mất thì người mở dự án sau không biết.
    kb = _kich_ban(beats=[_beat(" ".join(["từ"] * 60) + "."), _beat("Ngắn.")])
    duan = str(tmp_path / "duan")
    ghep = _GhepGia()
    da.dung_du_an(kb, anh, duan, blueprint={"beats": [{"startS": 0, "endS": 8}]},
                  ghep_video=ghep, do_thoi_luong=ghep.do_thoi_luong)
    with open(os.path.join(duan, "data", da.TEN_NGUON_GOC), encoding="utf-8") as f:
        nguon = json.load(f)
    assert any("dài gấp" in c for c in nguon["canh_bao"])


# ------------------------------------------------------ ranh giới C1 ------

def test_KHONG_di_qua_cong_kiem_anh_AI_cua_C1(tmp_path, anh, monkeypatch):
    """`dung_video()` bắt mọi ảnh phải đã kiểm bao bì VÀ đã đóng nhãn
    AI-generated LÊN ẢNH. Ảnh người dùng tự chụp không phải ảnh AI — điền các
    cờ đó cho nó chỉ để qua cổng là BỊA trạng thái tuân thủ.

    Kiểm HÀNH VI chứ không quét chuỗi ký tự: quét chuỗi sẽ bắt luôn câu chú
    thích giải thích vì sao không dùng, tức test đỏ vì đọc nhầm chính lời
    giải thích của mình.
    """
    from autodub import product_video as pv

    def _cam(*a, **k):
        raise AssertionError("H4c gọi cổng ảnh AI của C1 — sai đường")

    da_goi = []
    monkeypatch.setattr(pv, "dung_video", _cam)
    # Phép đo cũng phải giả: hàm ghép đã bị thay bằng một hàm ghi tệp RỖNG,
    # nên cổng thời lượng thật sẽ không đo được gì. Test này kiểm ĐƯỜNG ĐI
    # chứ không kiểm thời lượng — trả đúng tổng mà bên gọi yêu cầu.
    monkeypatch.setattr(
        pv, "ghep_anh_nguoi_dung",
        lambda *a, **k: (da_goi.append(k["giay_moi_anh"]),
                         open(a[1], "wb").close())[1])
    da.dung_du_an(_kich_ban(), anh, str(tmp_path / "duan"),
                  do_thoi_luong=lambda _p: sum(da_goi[-1]))
    assert da_goi, "phải ghép qua đường ảnh người dùng"


def test_ham_ghep_anh_nguoi_dung_van_dong_nhan_AI_len_VIDEO():
    # Kịch bản do mô hình viết và giọng đọc là giọng tổng hợp ⇒ video này
    # đúng là nội dung chỉnh sửa bằng AI đáng kể. Nhãn phải còn.
    from autodub import product_video as pv
    lenh = pv._lenh_ghep(["a.png", "b.png"], "ra.mp4", [2.0, 3.0], 0.3)
    i = lenh.index("-filter_complex")
    assert pv.NHAN_VIDEO in lenh[i + 1]


def test_ghep_anh_nguoi_dung_chan_khi_tep_khong_con(tmp_path):
    from autodub import product_video as pv
    with pytest.raises(ValueError, match="Không còn tệp ảnh"):
        pv.ghep_anh_nguoi_dung([str(tmp_path / "khong_co.png")],
                               str(tmp_path / "ra.mp4"), giay_moi_anh=[2.0])

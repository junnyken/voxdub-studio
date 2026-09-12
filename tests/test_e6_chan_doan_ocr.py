"""E6 giai đoạn 0 — ghi bằng chứng OCR ra đĩa để ĐO ĐƯỢC.

Bước đọc chữ tốn 3 phút 51 giây và 88 Vox cho một video 34 giây (đo từ nhật
ký chủ dự án 12/09). Có bốn đòn bẩy để cắt, nhưng **không đòn bẩy nào chọn
được nếu không có dữ liệu thật** — và dữ liệu đó hiện chỉ tồn tại trong bộ
nhớ rồi biến mất cùng lượt chạy.

Giai đoạn này KHÔNG đổi hành vi: chỉ ghi thêm một tệp chẩn đoán. Chi phí với
người dùng là **0 Vox** — chỗ ghi nằm ở `flow_blueprint.trich_bang_chung`,
ngay sau `read_text_regions`, mà hàm đó trả về bình thường kể cả khi người
dùng bấm "Bỏ qua" ở cổng xin phép 50 Vox.

Xem `docs/MINI-SPEC_E6_Bot_Khung_OCR.md`.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from autodub.media import doc_chu_may_chu as m


class _QuanSat:
    """Đủ thuộc tính mà `_khoa_doan`/`chia_doan` dùng."""

    def __init__(self, frame_index, text, *, x=0.0, y=0.0, conf=0.9, ts=None):
        self.frame_index = frame_index
        self.text = text
        self.x = x
        self.y = y
        self.confidence = conf
        self.timestamp_s = ts if ts is not None else frame_index * 0.5
        self.status = "ok" if conf >= 0.6 else "unconfirmed"


@pytest.fixture
def quan_sat():
    return [
        _QuanSat(0, "met moi that su"),
        _QuanSat(1, "met moi that su"),
        _QuanSat(2, "nhap hoa don"),
        _QuanSat(4, "MUA NGAY", conf=0.95),
    ]


def _doc(tmp_path):
    tep = tmp_path / "data" / "ocr_chan_doan.json"
    assert tep.exists(), f"không ghi ra {tep}"
    return json.loads(tep.read_text(encoding="utf-8"))


def test_ghi_tep_chan_doan_ra_work_dir(tmp_path, quan_sat):
    m.ghi_chan_doan_ocr(str(tmp_path), quan_sat, transcript=[], giay_ocr=193.0,
                        dai_giay=33.6, so_moc=99)
    d = _doc(tmp_path)
    assert d["video"]["dai_giay"] == 33.6
    assert d["video"]["so_moc_lay_mau"] == 99
    assert d["thoi_gian"]["ocr_cuc_bo_s"] == 193.0


def test_moi_doan_co_du_thu_de_tra_loi_bon_cau_hoi(tmp_path, quan_sat):
    """Thiếu một trường là phải chạy lại lượt bốn phút để lấy nó."""
    m.ghi_chan_doan_ocr(str(tmp_path), quan_sat, transcript=[], giay_ocr=1.0,
                        dai_giay=10.0, so_moc=20)
    doan = _doc(tmp_path)["doan"]
    assert doan, "không ghi đoạn nào"
    for d in doan:
        for khoa in ("khung", "bat_dau_s", "ket_thuc_s", "chu_cuc_bo",
                     "so_vung", "tin_cay_nho_nhat"):
            assert khoa in d, f"đoạn thiếu `{khoa}` — xem mục C của mini-spec"


def test_gop_dung_khung_lien_tiep_cung_chu(tmp_path, quan_sat):
    m.ghi_chan_doan_ocr(str(tmp_path), quan_sat, transcript=[], giay_ocr=1.0,
                        dai_giay=10.0, so_moc=20)
    doan = _doc(tmp_path)["doan"]
    assert [d["khung"] for d in doan] == [[0, 1], [2], [4]], (
        "phải khớp đúng `chia_doan` — tệp chẩn đoán mà khác thứ thật thì đo "
        "xong vẫn không kết luận được gì")


def test_ghi_ca_transcript_de_so_khop_thoi_gian(tmp_path, quan_sat):
    """Câu hỏi C.1 là 'bao nhiêu đoạn OCR trùng lời đọc' — cần cả hai phía."""
    tr = [{"start_s": 0.0, "end_s": 1.0, "text": "Mệt mỏi thật sự"}]
    m.ghi_chan_doan_ocr(str(tmp_path), quan_sat, transcript=tr, giay_ocr=1.0,
                        dai_giay=10.0, so_moc=20)
    d = _doc(tmp_path)
    assert len(d["transcript"]) == 1
    assert d["transcript"][0]["chu"] == "Mệt mỏi thật sự"
    assert d["transcript"][0]["bat_dau_s"] == 0.0


def test_ghi_hong_KHONG_chan_luot_chay(tmp_path, quan_sat, caplog):
    """Chẩn đoán là thứ phụ. Không ghi được thì phải chạy tiếp.

    Đây là lớp lỗi tệ: thêm một tính năng đo đạc rồi chính nó giết lượt chạy
    của người dùng.
    """
    import logging

    # `json.dumps`, không phải `json.dump`: bản cài dựng chuỗi XONG rồi mới
    # mở tệp, vì `open(p, "w")` cắt trắng tệp cũ ngay cả khi phần dựng dữ
    # liệu ném lỗi sau đó.
    with patch("json.dumps", side_effect=OSError("đĩa đầy")):
        with caplog.at_level(logging.WARNING):
            m.ghi_chan_doan_ocr(str(tmp_path), quan_sat, transcript=[],
                                giay_ocr=1.0, dai_giay=10.0, so_moc=20)
    assert "chẩn đoán" in caplog.text.lower() or "chan doan" in caplog.text.lower()


def test_khong_ghi_gi_dan_ve_video_goc(tmp_path, quan_sat):
    """Ràng buộc E.4 — cùng luật với Constraint 2 của H2."""
    m.ghi_chan_doan_ocr(str(tmp_path), quan_sat, transcript=[], giay_ocr=1.0,
                        dai_giay=10.0, so_moc=20)
    tho = (tmp_path / "data" / "ocr_chan_doan.json").read_text(encoding="utf-8")
    for cam in ("youtube.com", "sourceReference", "http://", "https://"):
        assert cam not in tho, f"tệp chẩn đoán chứa `{cam}`"


def test_duoc_goi_tu_duong_THAT():
    """CHỐT CHỖ GỌI — hàm đúng mà không ai gọi thì không có dữ liệu nào cả.

    Chỗ gọi nằm ở `flow_blueprint.trich_bang_chung`, KHÔNG phải trong
    `doc_chu_may_chu`: đó là tầng duy nhất có đủ cả bằng chứng OCR lẫn
    transcript, mà câu hỏi chính của mini-spec cần cả hai. Bản đầu của test
    này chốt nhầm tầng dưới và đỏ vì `transcript` không tồn tại ở đó.
    """
    import inspect

    from autodub import flow_blueprint as fb

    than = inspect.getsource(fb.trich_bang_chung)
    assert "ghi_chan_doan_ocr(" in than, (
        "`trich_bang_chung` không gọi hàm ghi chẩn đoán")
    assert "transcript=transcript" in than, (
        "gọi mà không đưa transcript vào — mất nửa dữ liệu cần để đo")


def test_ghi_ca_khi_nguoi_dung_bo_qua_cong_vox(tmp_path, monkeypatch):
    """0 Vox: bấm «Bỏ qua» vẫn phải có đủ dữ liệu đo.

    Cả điểm của giai đoạn 0 là lấy số đo mà không tốn đồng nào. `xin_phep`
    trả False thì `doc_lai_bang_may_chu` trả về bản đọc cục bộ và
    `read_text_regions` vẫn trả bình thường — nên chỗ ghi (nằm SAU nó) vẫn
    chạy. Test này chốt đúng chuỗi đó.
    """
    from autodub.media import doc_chu_may_chu as mm

    quan_sat = [_QuanSat(i, "chu") for i in range(65)]

    class _Khach:
        def assist(self, *a, **kw):
            raise AssertionError("từ chối rồi mà vẫn gọi mạng")

    monkeypatch.setattr(mm, "chia_doan", lambda _q: [[i] for i in range(65)])
    with patch.object(mm, "_anh_gui_di", return_value={"data": "x"}):
        ra = mm.doc_lai_bang_may_chu(
            quan_sat, [str(tmp_path / f"{i}.jpg") for i in range(65)],
            client=_Khach(), xin_phep=lambda v, k: False)

    # Bản đọc cục bộ trả về nguyên vẹn -> tầng trên vẫn có `quan_sat` để ghi.
    assert ra == quan_sat
    mm.ghi_chan_doan_ocr(str(tmp_path), ra, transcript=[], giay_ocr=1.0,
                         dai_giay=10.0, so_moc=20)
    assert len(_doc(tmp_path)["doan"]) == 65


# --- Tách khởi động engine khỏi phần quét từng khung ----------------------

def test_ghi_tach_khoi_dong_va_quet(tmp_path, quan_sat):
    """Hai phần phản ứng NGƯỢC nhau khi giảm số khung.

    Khởi động engine là chi phí cố định — cắt khung không làm nó nhỏ đi. Phần
    quét thì co theo tỉ lệ. Gộp làm một con số là không trả lời được câu
    quyết định của cả mini-spec: "cắt bớt khung có làm nhanh lên không".
    """
    m.ghi_chan_doan_ocr(
        str(tmp_path), quan_sat, transcript=[], giay_ocr=193.0,
        dai_giay=33.6, so_moc=99,
        thoi_gian_ocr={"duong": "subprocess", "so_khung": 99,
                       "khoi_dong_s": 21.4, "quet_s": 171.6})
    t = _doc(tmp_path)["thoi_gian"]
    assert t["khoi_dong_s"] == 21.4
    assert t["quet_s"] == 171.6
    assert t["so_khung"] == 99


def test_khong_co_so_do_thi_de_TRONG_chu_khong_doan(tmp_path, quan_sat):
    """Worker cũ không trả hai khoá đó thì tuyệt đối không bịa ra.

    Một con số đoán ở đây dẫn thẳng tới một quyết định thiết kế sai — đúng
    lớp lỗi mà cả mini-spec E6 sinh ra để tránh.
    """
    m.ghi_chan_doan_ocr(str(tmp_path), quan_sat, transcript=[], giay_ocr=193.0,
                        dai_giay=33.6, so_moc=99)
    t = _doc(tmp_path)["thoi_gian"]
    assert "khoi_dong_s" not in t
    assert "quet_s" not in t


def test_ket_qua_doc_chu_mang_theo_thoi_gian():
    from autodub.media.text_regions import KetQuaDocChu

    assert "thoi_gian" in KetQuaDocChu.__dataclass_fields__, (
        "`read_text_regions` không mang số đo về thì tầng trên không có gì "
        "để ghi")


def test_worker_ocr_bao_cao_hai_moc_thoi_gian():
    """CHỐT CHỖ ĐO: đường chính là subprocess, không đo được từ ngoài."""
    import pathlib

    tho = pathlib.Path("autodub/media/text_regions_worker.py").read_text(
        encoding="utf-8")
    assert '"khoi_dong_s"' in tho and '"quet_s"' in tho, (
        "worker không báo cáo thời gian — đường subprocess là đường CHÍNH, "
        "đo ở tiến trình cha chỉ ra một con số gộp")


def test_flow_blueprint_truyen_so_do_xuong():
    import inspect

    from autodub import flow_blueprint as fb

    than = inspect.getsource(fb.trich_bang_chung)
    assert "thoi_gian_ocr=" in than, (
        "đo được rồi nhưng không đưa vào tệp chẩn đoán")


# --- Script đọc kết quả ----------------------------------------------------

def test_script_doc_chay_duoc_va_noi_dung_ket_luan(tmp_path, capsys):
    """Script phải NÓI RA kết luận, không chỉ in số.

    Không có nó thì "đo" lại thành đọc JSON bằng mắt rồi ước lượng.
    """
    import importlib.util
    import pathlib

    m.ghi_chan_doan_ocr(
        str(tmp_path),
        [_QuanSat(i, "met moi that su", ts=i * 0.5) for i in range(12)],
        transcript=[{"start_s": 0.0, "end_s": 10.0, "text": "Mệt mỏi thật sự"}],
        giay_ocr=50.0, dai_giay=10.0, so_moc=12,
        thoi_gian_ocr={"so_khung": 12, "khoi_dong_s": 40.0, "quet_s": 10.0})

    duong = pathlib.Path("scripts/do_chan_doan_ocr.py").resolve()
    spec = importlib.util.spec_from_file_location("do_cd", duong)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ma = mod.main(str(tmp_path / "data" / "ocr_chan_doan.json"))

    ra = capsys.readouterr().out
    assert ma == 0
    assert "C.1" in ra and "C.3" in ra and "C.4" in ra
    assert "KHỞI ĐỘNG chiếm phần lớn" in ra, (
        "khởi động 40s / quét 10s mà không nói ra là cắt khung vô ích thì "
        f"script chưa làm đúng việc của nó.\n{ra}")


def test_script_bo_dau_de_so_duoc_hai_phia():
    """RapidOCR trả `met moi`, transcript trả `Mệt mỏi` — không bỏ dấu thì
    mọi đoạn đều 'không trùng' và kết luận ngược hẳn sự thật."""
    import importlib.util
    import pathlib

    duong = pathlib.Path("scripts/do_chan_doan_ocr.py").resolve()
    spec = importlib.util.spec_from_file_location("do_cd2", duong)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.bo_dau("Mệt mỏi thật sự") == "met moi that su"
    assert mod.bo_dau("hóa đơn") == "hoa don"
    assert mod.bo_dau("Đặt hàng") == "dat hang", "`đ` không tách được bằng NFD"

"""E7 — máy khách phải tự giữ trần bằng chứng, không để máy chủ từ chối.

Lượt chạy thật 12/09 (v3.17.14): người dùng bấm «Bỏ qua, không tốn Vox» đúng
như hướng dẫn, chờ thêm ba phút, rồi nhận:

    Dừng lại: must NOT have more than 400 items

Đây là lỗi do chính đường "Bỏ qua" sinh ra — tôi thêm cổng 50 Vox nhưng
không chạy thử nhánh TỪ CHỐI tới cùng:

- Đồng ý đọc → máy chủ trả chữ SẠCH, một dòng mỗi khung → gộp tốt → 65 mục.
- Bỏ qua     → giữ bản RapidOCR thô: mỗi khung vài vùng chữ, mỗi vùng lệch
  nhau vài ký tự vì OCR tiếng Việt nhiễu. `gop_quan_sat_lien_tiep` so
  `text` NGUYÊN VĂN nên gần như không gộp được gì → vượt 400.

Tức nhánh rẻ tiền là nhánh DUY NHẤT hỏng. Người dùng làm đúng lời khuyên của
tôi thì mất bốn phút và không được gì.

Hai thứ phải sửa, và sửa cả hai:
  1. Máy khách KHÔNG được gửi quá trần — nó biết trần đó.
  2. Cắt bớt thì phải NÓI RA trong `samplingPolicyUsed`, vì trường đó đi
     thẳng vào lời nhắc và là thứ cho mô hình biết độ tin cậy của phần OCR.
     Cắt im lặng là để mô hình nói chắc nịch trên nền bằng chứng đã bị xén.
"""
from __future__ import annotations

import pytest

from autodub.flow_blueprint import SO_BANG_CHUNG_TOI_DA, gioi_han_bang_chung


def _bc(n: int, *, dai_giay: float = 34.0) -> list[dict]:
    """`n` mẩu bằng chứng rải đều dòng thời gian."""
    buoc = dai_giay / max(n, 1)
    return [{"text": f"chu {i}", "status": "ok",
             "start_s": round(i * buoc, 3),
             "end_s": round(i * buoc + 0.2, 3)} for i in range(n)]


def test_tran_khop_may_chu():
    """Đổi một bên mà quên bên kia là lỗi quay lại y hệt."""
    import pathlib
    import re

    tho = pathlib.Path("control_server/src/routes/flow-blueprints.js").read_text(
        encoding="utf-8")
    so = {int(m) for m in re.findall(r"maxItems:\s*(\d+)", tho)}
    assert SO_BANG_CHUNG_TOI_DA in so, (
        f"máy khách giữ trần {SO_BANG_CHUNG_TOI_DA}, máy chủ khai {sorted(so)}")


def test_duoi_tran_thi_khong_dong_gi(caplog):
    goc = _bc(120)
    ra, ghi_chu = gioi_han_bang_chung(goc, ten="OCR")
    assert ra == goc
    assert ghi_chu == ""


def test_dung_bang_tran_cung_khong_dong_gi():
    goc = _bc(SO_BANG_CHUNG_TOI_DA)
    ra, ghi_chu = gioi_han_bang_chung(goc, ten="OCR")
    assert len(ra) == SO_BANG_CHUNG_TOI_DA
    assert ghi_chu == ""


def test_vuot_tran_thi_cat_ve_dung_tran():
    ra, _ = gioi_han_bang_chung(_bc(900), ten="OCR")
    assert len(ra) == SO_BANG_CHUNG_TOI_DA


def test_cat_xong_van_phu_HET_dong_thoi_gian():
    """Cắt 500 mẩu đầu rồi bỏ phần sau là mất sạch bằng chứng nửa cuối video.

    Đó là ca tệ hơn cả việc không có bằng chứng: mô hình thấy chữ dày đặc ở
    đầu và im lặng ở cuối, rồi kết luận nhịp video như thế thật.
    """
    ra, _ = gioi_han_bang_chung(_bc(900, dai_giay=34.0), ten="OCR")
    dau = min(o["start_s"] for o in ra)
    cuoi = max(o["end_s"] for o in ra)
    assert dau <= 1.0, f"mất phần đầu (bắt đầu ở {dau}s)"
    assert cuoi >= 33.0, f"mất phần cuối (kết thúc ở {cuoi}s)"

    # Rải đều: nửa đầu và nửa cuối phải xấp xỉ nhau.
    nua = sum(1 for o in ra if o["start_s"] < 17.0)
    assert 0.4 <= nua / len(ra) <= 0.6, (
        f"lệch về một phía: {nua}/{len(ra)} mẩu nằm ở nửa đầu")


def test_giu_dung_thu_tu_thoi_gian():
    ra, _ = gioi_han_bang_chung(_bc(900), ten="OCR")
    moc = [o["start_s"] for o in ra]
    assert moc == sorted(moc)


def test_cat_thi_PHAI_noi_ra_va_noi_con_so_that():
    _, ghi_chu = gioi_han_bang_chung(_bc(900), ten="OCR")
    assert ghi_chu, "cắt im lặng là giấu việc bằng chứng đã bị xén"
    assert "900" in ghi_chu and str(SO_BANG_CHUNG_TOI_DA) in ghi_chu, (
        f"phải nói cắt từ bao nhiêu xuống bao nhiêu: {ghi_chu!r}")
    assert "OCR" in ghi_chu


@pytest.mark.parametrize("n", [0, 1])
def test_rong_hoac_mot_mau_khong_vo(n):
    ra, ghi_chu = gioi_han_bang_chung(_bc(n), ten="OCR")
    assert len(ra) == n
    assert ghi_chu == ""


def test_trich_bang_chung_co_ap_tran():
    """CHỐT CHỖ GỌI — hàm đúng mà không ai gọi thì máy chủ vẫn từ chối."""
    import inspect

    from autodub import flow_blueprint as fb

    than = inspect.getsource(fb.trich_bang_chung)
    assert "gioi_han_bang_chung(" in than, (
        "`trich_bang_chung` không áp trần — lỗi 400 items quay lại nguyên vẹn")


def test_ghi_chu_cat_di_vao_sampling_policy():
    """Ràng buộc E.1 của mini-spec E6: bỏ bằng chứng thì phải nói ra ở đúng
    chỗ mô hình đọc được."""
    import inspect

    from autodub import flow_blueprint as fb

    than = inspect.getsource(fb.trich_bang_chung)
    assert "chinh_sach" in than and "gioi_han_bang_chung" in than
    vi_cat = than.index("gioi_han_bang_chung(")
    vi_dung = than.rindex("sampling_policy_used=")
    assert vi_cat < vi_dung, (
        "áp trần SAU khi đã chốt `samplingPolicyUsed` thì ghi chú không vào "
        "được lời nhắc")

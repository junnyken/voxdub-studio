"""Việc tách giọng người nói phải HIỆN RA, không chỉ nằm trong nhật ký.

Chủ dự án chạy thật rồi hỏi (27/08/2026): *"trong video của tôi chỉ có đúng
2 giọng đọc, hình như nó không có chỗ nhận định được"*.

Kiểm mã thì đúng: trình hướng dẫn sáu bước KHÔNG có một chữ nào về người nói
(ô số người nói nằm tận trong Cài đặt), và việc tách giọng chỉ ghi
`logger.info` chứ không hiện thành bước nào trên danh sách tiến trình. Người
dùng đi hết sáu bước, thấy đúng một ô «Giọng đọc», rồi kết luận app không làm
được video nhiều người.

Tính năng CÓ, chỉ là không ai nhìn thấy nó. Đây là lỗi trình bày, nhưng hậu
quả y hệt như không có tính năng.
"""
from __future__ import annotations

import ast
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(ten: str) -> str:
    return open(os.path.join(REPO, ten), encoding="utf-8").read()


# --- Bước hiện trên tiến trình -----------------------------------------

def test_co_buoc_tach_giong_trong_danh_sach():
    from autodub.progress import STEPS

    assert "diarize" in STEPS, "không có bước nào cho việc tách giọng"
    assert STEPS.index("diarize") > STEPS.index("asr"), (
        "tách giọng chạy SAU khi nghe-chép — đặt trước là sai thứ tự thật")
    assert STEPS.index("diarize") < STEPS.index("translate")


def test_buoc_do_co_nhan_tieng_viet():
    from autodub_gui.widgets import STEP_LABELS

    assert STEP_LABELS.get("diarize"), "bước mới không có nhãn hiển thị"
    assert "người nói" in STEP_LABELS["diarize"].lower()


@pytest.mark.parametrize("truong_hop,ky_vong", [
    ("đang tắt trong Cài đặt", "tắt tính năng"),
    ("chưa cài bộ tách giọng", "chưa cài engine"),
    ("người nói", "chạy xong, báo số người"),
])
def test_moi_ket_cuc_deu_bao_len_giao_dien(truong_hop, ky_vong):
    """Ba kết cục: tắt · chưa cài · chạy xong. Kết cục nào im lặng thì người
    dùng vẫn không biết vì sao chỉ có một giọng."""
    nguon = _doc("autodub/pipeline.py")
    for nut in ast.walk(ast.parse(nguon)):
        if isinstance(nut, ast.FunctionDef) and nut.name == "_apply_diarization":
            than = ast.get_source_segment(nguon, nut) or ""
            break
    else:
        raise AssertionError("không còn _apply_diarization")
    assert truong_hop in than, f"không báo trường hợp: {ky_vong}"


def test_nhanh_loi_cung_hien_ra():
    """Lỗi thiếu DLL torchcodec (26/08) chỉ nằm trong nhật ký — người dùng
    chạy xong thấy một giọng mà không biết vì sao."""
    nguon = _doc("autodub/pipeline.py")
    i = nguon.index("except DiarizationError")
    assert 'rep.emit("diarize", "error"' in nguon[i:i + 500]


def test_so_nguoi_noi_bao_len_chu_khong_chi_ghi_nhat_ky():
    nguon = _doc("autodub/pipeline.py")
    i = nguon.index("gendered = sum(")
    khoi = nguon[i:i + 700]
    assert 'rep.emit("diarize", "done"' in khoi
    assert "người nói" in khoi


# --- Ô trong trình hướng dẫn -------------------------------------------

def test_buoc_giong_doc_co_o_so_nguoi_noi():
    src = _doc("autodub_gui/pages/new_project_steps.py")
    assert "Số người nói trong video" in src, (
        "trình hướng dẫn vẫn không có chỗ nào nói về người nói")
    assert "speaker_count" in src, "ô đó không trả giá trị ra ngoài"


def test_gia_tri_do_di_vao_luot_chay():
    """Có ô mà không nối thì bấm cũng như không — đúng lỗi `close_requested`
    đã mắc ở Trình chỉnh sửa."""
    trang = _doc("autodub_gui/pages/new_project_page.py")
    assert 'changes["speaker_count"]' in trang, (
        "số người nói khai ở bước 4 không đi vào lượt chạy")
    assert '"SPEAKER_COUNT"' in trang, "không ghi lại để lần sau khỏi khai lại"


def test_cau_mo_ta_noi_dung_ba_trang_thai():
    """Chưa cài · đã cài nhưng tắt · đang bật — ba câu khác nhau."""
    from autodub_gui.pages.new_project_steps import _nhan_trang_thai_tach_giong

    chua_cai = _nhan_trang_thai_tach_giong(True, False)
    dang_tat = _nhan_trang_thai_tach_giong(False, True)
    dang_bat = _nhan_trang_thai_tach_giong(True, True)
    assert len({chua_cai, dang_tat, dang_bat}) == 3, "ba trạng thái nói giống nhau"
    assert "Chưa cài" in chua_cai and ".bat" in chua_cai, (
        "không chỉ cách cài")
    assert "TẮT" in dang_tat and "Cài đặt" in dang_tat, "không chỉ chỗ bật"
    assert "mỗi người một giọng" in dang_bat


def test_pipeline_van_uu_tien_so_nguoi_dung_khai():
    """Số người dùng khai THẮNG suy đoán của máy — họ xem video rồi."""
    nguon = _doc("autodub/pipeline.py")
    assert "so_nguoi_khai" in nguon
    i = nguon.index("so_nguoi_khai =")
    assert "num_speakers=so_nguoi_khai" in nguon[i:i + 900]

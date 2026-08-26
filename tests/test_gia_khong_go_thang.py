"""Giá Vox không được gõ thẳng vào câu chữ giao diện.

Lỗi thật, chủ dự án phát hiện bằng ảnh chụp (26/08/2026): sau khi thêm đường
dịch ngoại tuyến, BỐN chỗ trong giao diện vẫn nói "12 Vox mỗi câu" cho lượt
dịch tự động — đúng khi máy chủ là đường duy nhất, sai khi người dùng chọn
ngoại tuyến (lúc đó không có phần cộng thêm, còn 10). Cùng lúc, bước 3 hiện
nhãn "Dịch bằng: VoxDub Cloud" viết chết, trong khi lượt chạy dùng NLLB trên
máy.

Đây là lớp lỗi #5 của dự án (FEATURES.md §6). Sửa bốn chuỗi rồi hy vọng lần
sau ai đó nhớ sửa cả bốn là cách chữa đã hỏng một lần. Nên luật ở đây: câu
chữ hỏi `autodub_gui.gia`, không tự gõ số.

Ngoại lệ CÓ CHỦ Ý: câu nói về những khoản KHÔNG đổi theo đường dịch (gói
tiêu đề + mô tả, giá dựng trên máy chủ) vẫn được nêu số, vì chúng không phải
thứ đã gây ra lỗi này.
"""
from __future__ import annotations

import ast
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Các mẫu "gõ giá thẳng" nói về giá MỖI CÂU — thứ thay đổi theo đường dịch.
MAU_GIA_MOI_CAU = re.compile(r"\d+\s*Vox\s*(?:mỗi câu|/câu|mỗi dòng|/dòng)")

#: Tệp được phép nêu số vì lý do viết ra.
MIEN_TRU = {
    "autodub_gui/gia.py":
        "đây chính là chỗ định nghĩa giá mặc định, phải có số",
    "autodub_gui/pages/batch_page.py":
        "chỉ là chú thích trong mã giải thích cách ước lượng số Vox cho hàng "
        "chờ, không phải câu chữ hiện ra cho người dùng",
}


def _tep_giao_dien():
    for thu, _d, tep in os.walk(os.path.join(REPO, "autodub_gui")):
        if "__pycache__" in thu:
            continue
        for f in sorted(tep):
            if f.endswith(".py"):
                duong = os.path.join(thu, f)
                yield (os.path.relpath(duong, REPO).replace(os.sep, "/"),
                       open(duong, encoding="utf-8").read())


def test_khong_go_gia_moi_cau_thang_vao_cau_chu():
    vi_pham = []
    for ten, src in _tep_giao_dien():
        if ten in MIEN_TRU:
            continue
        for dong in src.splitlines():
            # Chỉ soi CHUỖI hiện ra, bỏ qua chú thích giải thích.
            if dong.lstrip().startswith("#"):
                continue
            if MAU_GIA_MOI_CAU.search(dong):
                vi_pham.append(f"{ten}: {dong.strip()[:90]}")
    assert not vi_pham, (
        "giá mỗi câu bị gõ thẳng vào câu chữ — nó đổi theo đường dịch, phải "
        f"hỏi autodub_gui.gia: {vi_pham}")


def test_mien_tru_kem_ly_do():
    for ten, ly_do in MIEN_TRU.items():
        assert os.path.isfile(os.path.join(REPO, ten)), ten
        assert len(ly_do) > 40, f"lý do miễn trừ quá sơ sài: {ten}"


def test_bang_gia_lay_tu_may_chu_khi_co():
    """Máy chủ đổi được bảng giá lúc chạy — app phải hiện theo, không cần
    phát hành lại."""
    src = open(os.path.join(REPO, "autodub_gui", "gia.py"), encoding="utf-8").read()
    assert "segmentAutoTranslate" in src and "pricing" in src


def test_khong_goi_mang_khi_dung_nhan():
    """Hàm này chạy trên luồng giao diện lúc dựng nhãn — một lượt gọi mạng ở
    đó là một lần app đứng hình."""
    src = open(os.path.join(REPO, "autodub_gui", "gia.py"), encoding="utf-8").read()
    for nut in ast.walk(ast.parse(src)):
        if isinstance(nut, ast.FunctionDef) and nut.name == "bang_gia":
            than = ast.get_source_segment(src, nut) or ""
            break
    else:
        raise AssertionError("không còn hàm bang_gia")
    assert "app_config(" not in than, "gọi app_config() là có thể chạm mạng"
    assert "_config" in than, "không đọc bản đã nhớ đệm"


def test_ngoai_tuyen_khong_cong_phi_dich():
    from autodub.config import Settings
    from autodub_gui import gia

    st = Settings()
    nen, them, _ = gia.GIA_MAC_DINH
    for che_do, mong_doi in (("server", nen + them), ("auto", nen + them),
                             ("offline", nen)):
        st.translate_mode = che_do
        assert gia.moi_cau(st, True) == mong_doi, che_do
    st.translate_mode = "server"
    assert gia.moi_cau(st, False) == nen, "dịch tay không được tính phí dịch"


def test_nhan_duong_dich_o_buoc_3_khong_viet_chet():
    """Nhãn "Dịch bằng" từng là QLabel("VoxDub Cloud") cố định — người dùng
    chọn ngoại tuyến ở trang Dịch thuật rồi sang bước 3 vẫn thấy VoxDub
    Cloud, không biết tin cái nào."""
    src = open(os.path.join(REPO, "autodub_gui", "pages", "new_project_steps.py"),
               encoding="utf-8").read()
    assert 'QLabel("VoxDub Cloud")' not in src, "nhãn đường dịch lại viết chết"
    assert "NHAN_DUONG_DICH" in src and "set_translate_mode" in src
    trang = open(os.path.join(REPO, "autodub_gui", "pages", "new_project_page.py"),
                 encoding="utf-8").read()
    assert "set_translate_mode(" in trang, "trang không hề cập nhật nhãn đó"

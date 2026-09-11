"""Hai mini-spec khác nhau không được mang cùng một số.

Chuyện thật, 26/8/2026: hai commit ngày 25/8 mang nhãn `V91`/`V92`, trùng hai
mini-spec đã có từ 20/8. Không hỏng gì lúc chạy — nhưng sổ là thứ để tra lại,
mà tra `V92` ra hai việc khác hẳn nhau thì sổ mất tác dụng đúng lúc cần nhất.
Đã đánh số lại thành `V96`/`V97`.

Chốt này chỉ xét **tiêu đề dạng chuẩn** `## <số> — <tên>`. Các mục ghi tiếp
của cùng một mini-spec (`## V89 giai đoạn 2`, `## V89 lên production`) cố ý
không theo dạng đó nên không bị tính là trùng — đó là ghi tiếp, không phải
đánh số nhầm.
"""
from __future__ import annotations

import collections
import os
import re

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SO = os.path.join(GOC, "docs", "TEST_LOG.md")

#: Trùng CÓ LÝ DO, đã soi tay. Thêm vào đây phải kèm lý do đọc được — danh
#: sách miễn trừ không có lý do thì chỉ là cách tắt chốt cho êm chuyện.
TRUNG_DUOC_PHEP = {
    "V48": "cùng một việc (sao lưu MongoDB) verify lại hôm sau, không phải "
           "hai mini-spec khác nhau",
}


def _tieu_de_chuan() -> list[tuple[str, str]]:
    ra = []
    with open(SO, encoding="utf-8") as f:
        for dong in f:
            m = re.match(r"## ([VC]\d+) — (.+)", dong)
            if m:
                ra.append((m.group(1), m.group(2).strip()))
    return ra


def test_doc_duoc_so():
    assert len(_tieu_de_chuan()) > 100, "đọc hụt tiêu đề — biểu thức khớp sai?"


def test_khong_co_so_nao_bi_dung_hai_lan():
    dem = collections.Counter(so for so, _ten in _tieu_de_chuan())
    trung = {so: n for so, n in dem.items()
             if n > 1 and so not in TRUNG_DUOC_PHEP}
    assert not trung, (
        "hai mini-spec khác nhau mang cùng số: "
        + ", ".join(f"{so} ({n} mục)" for so, n in sorted(trung.items()))
        + " — đổi số mục ra sau, và ghi chú lại vì commit cũ vẫn mang nhãn cũ")


def test_hai_so_da_sua_khong_quay_lai():
    """Ca cụ thể đã sửa — giữ để không ai vô tình đặt lại."""
    dem = collections.Counter(so for so, _ten in _tieu_de_chuan())
    assert dem["V91"] == 1, "V91 lại có hai mục"
    assert dem["V92"] == 1, "V92 lại có hai mục"
    assert dem["V96"] == 1 and dem["V97"] == 1, "thiếu mục đã đánh số lại"


def test_moi_muc_mien_tru_deu_co_ly_do():
    for so, ly_do in TRUNG_DUOC_PHEP.items():
        assert len(ly_do) > 20, f"{so} miễn trừ mà không nói lý do"


# ---------------------------------------------------------------------------
# Toàn vẹn THAM CHIẾU khi đổi không gian mã — bài học 11/09/2026.
#
# Chốt "không số nào dùng hai lần" ở trên bắt được lúc tôi đặt mã `C20` cho
# một phát hiện rà soát, trong khi `C` là không gian số mini-spec đã có của
# dự án. Nhưng nó KHÔNG bắt được lỗi tiếp theo: phép thay hàng loạt
# `C<n>` → `RS-<n>` đổi nhầm cả một chỗ đang nhắc **mini-spec C1 thật**
# thành `RS-1`.
#
# Bài học: đổi không gian mã cần HAI chốt khác nhau —
#   1. duy nhất (đã có ở trên);
#   2. **tham chiếu còn trỏ đúng chỗ** (dưới đây).
#
# Chỉ có chốt thứ nhất thì migration vẫn phá được tài liệu trong im lặng.

BACKLOG = os.path.join(GOC, "docs", "BACKLOG_PHASE_H.md")


def _so_mini_spec_co_that() -> set[str]:
    """Mọi số mini-spec THẬT.

    Rộng hơn `_tieu_de_chuan()` có chủ đích: hàm kia chỉ nhận dạng chuẩn
    `## <số> — <tên>` để đếm TRÙNG, còn ở đây câu hỏi là "số này có tồn tại
    không". Tiêu đề thật có thể mang chú thích (`## C2 (rút gọn) — …`), và
    một số mini-spec chỉ được nhắc trong mã chứ chưa có mục sổ riêng.

    Bản đầu của hàm này chỉ đọc dạng chuẩn ⇒ báo nhầm `C2` là không tồn tại.
    """
    ra: set[str] = set()
    with open(SO, encoding="utf-8") as f:
        for dong in f:
            m = re.match(r"## ([VC]\d+)\b", dong)
            if m:
                ra.add(m.group(1))
    # Mini-spec được nhắc trong mã/tài liệu cũng là mini-spec có thật.
    for goc, _, tep in os.walk(GOC):
        if any(x in goc for x in ("node_modules", ".git", ".venv")):
            continue
        for ten in tep:
            if not ten.endswith((".py", ".js", ".md")):
                continue
            try:
                noi = open(os.path.join(goc, ten), encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            ra.update(re.findall(r"mini-spec ([VC]\d+)\b", noi))
    return ra


def test_backlog_KHONG_dung_lai_khong_gian_so_mini_spec():
    """Mã phát hiện rà soát phải mang tiền tố riêng `RS-`.

    Dùng `C<n>` cho một finding tạo ra hai nghĩa cho cùng một mã trong tài
    liệu, sổ test và roadmap — tra `C20` ra hai việc khác hẳn nhau.
    """
    if not os.path.exists(BACKLOG):
        return
    with open(BACKLOG, encoding="utf-8") as f:
        noi_dung = f.read()

    # Mã phát hiện là ô đầu của một hàng bảng: `| C20 | ...`
    ma_finding = set(re.findall(r"^\|\s*~?~?([VC]\d+)~?~?\s*\|", noi_dung,
                                flags=re.M))
    assert not ma_finding, (
        f"backlog dùng mã {sorted(ma_finding)} — trùng không gian số "
        "mini-spec. Phát hiện rà soát phải mang tiền tố `RS-`.")


def test_moi_tham_chieu_mini_spec_trong_backlog_van_TRO_DUNG_CHO():
    """Nhắc `C1`, `C6`… trong backlog phải là mini-spec CÓ THẬT.

    Đây là chốt mà migration `C<n>` → `RS-<n>` cần: nó bắt cả hai hướng hỏng
    — đổi nhầm một tham chiếu thật thành `RS-`, hoặc để sót một mã finding
    chưa đổi.
    """
    if not os.path.exists(BACKLOG):
        return
    with open(BACKLOG, encoding="utf-8") as f:
        noi_dung = f.read()

    that = _so_mini_spec_co_that()
    # Bỏ qua phần trong dấu nháy ngược (tên tệp, đoạn mã) và các hàng bảng.
    sach = re.sub(r"`[^`]*`", " ", noi_dung)
    ma = set(re.findall(r"\b([VC]\d+)\b", sach))
    khong_co = sorted(m for m in ma if m not in that)
    assert not khong_co, (
        f"backlog nhắc {khong_co} nhưng TEST_LOG không có mini-spec nào mang "
        "số đó — hoặc đây là mã finding chưa đổi sang `RS-`, hoặc là một "
        "tham chiếu bị phép thay hàng loạt làm hỏng")


#: Những từ mà trong tài liệu này LUÔN đứng trước một mini-spec, không bao giờ
#: đứng trước một mã phát hiện. Dùng để bắt ca phép-thay-hàng-loạt đổi nhầm
#: một tham chiếu mini-spec thành mã `RS-`.
TU_DAN_MINI_SPEC = ("Trang", "trang", "mini-spec", "phép kiểm", "bài học",
                    "Guardrail của", "cổng của")


def test_RS_khong_bi_dung_o_cho_von_la_mot_mini_spec():
    """Bắt ca phép thay hàng loạt làm hỏng tham chiếu — nửa KHÓ của bài học.

    Chốt `..._van_TRO_DUNG_CHO` phía trên chỉ kiểm được các mã `C<n>` CÒN
    LẠI có trỏ đúng không. Nó **không** bắt được ca ngược: một `C1` thật bị
    đổi thành `RS-1`, vì sau khi đổi thì không còn `C<n>` nào để soi, và
    `RS-1` lại đúng là một mã phát hiện có thật trong bảng.

    Đây là phép đo THEO NGỮ CẢNH, và nó là **phỏng đoán có chủ đích**: nó bắt
    được đúng ca đã xảy ra ("Trang RS-1…", "mất phép kiểm RS-6"), nhưng không
    bắt được mọi cách làm hỏng tham chiếu. Toàn vẹn tham chiếu nói chung vẫn
    cần người đọc lại — test này thu hẹp chỗ phải soi, không thay thế việc đó.
    """
    if not os.path.exists(BACKLOG):
        return
    with open(BACKLOG, encoding="utf-8") as f:
        noi_dung = f.read()

    xau = []
    for tu in TU_DAN_MINI_SPEC:
        for m in re.finditer(rf"{re.escape(tu)}\s+(RS-\d+)", noi_dung):
            xau.append(f"«{tu} {m.group(1)}»")
    assert not xau, (
        f"{', '.join(xau)} — `RS-<n>` là mã PHÁT HIỆN, không phải mini-spec. "
        "Nhiều khả năng một phép thay hàng loạt đã đổi nhầm tham chiếu thật.")

"""Đọc Bản chỉ đạo hình ảnh, suy ra tham số dựng — mini-spec I5.

Bản chỉ đạo do máy chủ sinh (`scene_director`, I3) và đã được soi với từ điển
ở đó. Tệp này KHÔNG soi lại và KHÔNG giữ bảng mã→tham số nào: máy chủ trả sẵn
`chon[].dung.parameters` tính từ chính catalog, nên chép một bảng thứ hai vào
đây là dựng ra nguồn sự thật thứ hai để có ngày trôi lệch — đúng lớp lỗi mà
`tests/test_i2_catalog_khop_renderer.py` sinh ra để chặn.

**Đoạn ↔ mối nối.** Bản chỉ đạo cho một kiểu chuyển cảnh mỗi ĐOẠN, còn mối
nối nằm GIỮA hai ảnh — n ảnh chỉ có n-1 mối. Quy ước ở đây:

    kiểu của đoạn i = kiểu đi VÀO đoạn i

nên mối nối thứ j (nối ảnh j và ảnh j+1) lấy kiểu của **đoạn j+1**, và kiểu
của đoạn ĐẦU không dùng được — không có gì đứng trước nó để chuyển sang.

Vì sao chọn chiều này chứ không phải chiều ngược lại: `mo_vong` ánh xạ sang
`circleopen` của ffmpeg — vòng tròn MỞ RA để lộ cảnh kế, tức hiệu ứng giới
thiệu một cảnh. Đoạn chọn `mo_vong` nghĩa là "đoạn này hiện ra bằng vòng
tròn mở", tức kiểu đi vào nó. Hai chiều đều đọc xuôi với `fade_nhe`, chỉ
`mo_vong` phân biệt được — nên nó là căn cứ.
"""
from __future__ import annotations

#: Nhóm duy nhất khâu ghép hình thực thi được (catalog I2 §C2).
NHOM_CHUYEN_CANH = "transition"

#: Dùng khi một đoạn không chọn kiểu nào — cố ý TRÙNG mặc định cũ của
#: `ghep_anh_nguoi_dung`, để "không có chỉ đạo" cho ra đúng thứ người dùng
#: vẫn nhận trước I5, chứ không phải một kiểu mới lạ.
KIEU_MAC_DINH = "mo_chong"


class ChiDaoDaCu(Exception):
    """Bản chỉ đạo không còn khớp kịch bản (hoặc catalog) hiện tại.

    Ném chứ không lặng lẽ dùng tiếp: bản chỉ đạo cũ nói về một kịch bản khác,
    nên áp nó vào kịch bản mới là gán chuyển cảnh cho nhầm đoạn — hỏng im
    lặng, và người dùng không có cách nào nhận ra.
    """


def _kieu_cua_doan(doan: dict) -> str | None:
    """Mã `kieu_chuyen` mà đoạn này chỉ định, hoặc None nếu đoạn bỏ trống."""
    for chon in (doan.get("chon") or []):
        if chon.get("nhom") != NHOM_CHUYEN_CANH:
            continue
        thamso = ((chon.get("dung") or {}).get("parameters") or {})
        kieu = thamso.get("kieu_chuyen")
        if kieu:
            return str(kieu)
        # Có chọn mã chuyển cảnh nhưng máy chủ KHÔNG kèm cách dựng ⇒ mã đó là
        # gợi ý cho người, máy không làm được. Coi như đoạn bỏ trống.
        return None
    return None


def kieu_chuyen_theo_moi_noi(ban: dict | None, so_anh: int):
    """Suy ra kiểu chuyển cảnh cho TỪNG mối nối, kèm lời giải thích.

    Trả về ``(kieus, ghi_chu)``:

    * ``kieus`` — danh sách dài đúng ``so_anh - 1``, truyền thẳng được cho
      ``ghep_anh_nguoi_dung(kieu_chuyen=...)``. ``None`` khi không có bản chỉ
      đạo dùng được: bên gọi giữ nguyên hành vi cũ (ô chọn tay).
    * ``ghi_chu`` — những câu PHẢI hiện cho người dùng đọc. Mọi chỗ máy tự
      quyết (đoạn bỏ trống, số ảnh lệch số đoạn) đều phải có một câu ở đây;
      im lặng tự quyết là thứ mini-spec này cấm.

    Ném :class:`ChiDaoDaCu` khi bản chỉ đạo đã lệch kịch bản/catalog.
    """
    ghi_chu: list[str] = []
    if not ban:
        return None, ghi_chu
    if ban.get("laCu"):
        vi_sao = []
        if ban.get("kichBanDaDoi"):
            vi_sao.append("kịch bản đã sửa sau khi tạo bản chỉ đạo")
        if ban.get("catalogDaDoi"):
            vi_sao.append("từ điển chỉ đạo đã lên phiên bản mới")
        raise ChiDaoDaCu(
            "Bản chỉ đạo hình ảnh không còn khớp — "
            + ("; ".join(vi_sao) or "đã cũ")
            + ". Tạo lại bản chỉ đạo rồi dựng.")

    doan = sorted((ban.get("doan") or []), key=lambda d: d.get("thuTu") or 0)
    if not doan:
        return None, ghi_chu
    so_moi = max(so_anh - 1, 0)
    if so_moi == 0:
        return [], ghi_chu

    # Mối nối thứ j lấy kiểu của đoạn j+1 (xem docstring của module). Ảnh
    # nhiều hơn đoạn thì phần dư dùng kiểu của đoạn CUỐI — nói ra, không giấu.
    kieus: list[str] = []
    doan_trong: list[int] = []
    for j in range(so_moi):
        chi_so = min(j + 1, len(doan) - 1)
        kieu = _kieu_cua_doan(doan[chi_so])
        if kieu is None:
            kieu = KIEU_MAC_DINH
            doan_trong.append(doan[chi_so].get("thuTu") or chi_so + 1)
        kieus.append(kieu)

    if so_anh > len(doan):
        ghi_chu.append(
            f"Bạn chọn {so_anh} ảnh nhưng kịch bản chỉ có {len(doan)} đoạn — "
            f"{so_anh - len(doan)} ảnh cuối dùng chuyển cảnh của đoạn cuối.")
    elif so_anh < len(doan):
        ghi_chu.append(
            f"Bạn chọn {so_anh} ảnh nhưng kịch bản có {len(doan)} đoạn — "
            f"chỉ dùng chỉ đạo của {so_anh} đoạn đầu.")
    if doan_trong:
        ds = ", ".join(str(x) for x in sorted(set(doan_trong)))
        ghi_chu.append(
            f"Đoạn {ds} không có chỉ đạo chuyển cảnh — dùng «Mờ chồng».")
    return kieus, ghi_chu

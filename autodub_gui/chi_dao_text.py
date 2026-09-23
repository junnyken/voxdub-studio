"""Câu chữ của bản chỉ đạo hình ảnh — MINI-SPEC I3.

Tách khỏi giao diện vì đây là phần **dễ nói sai nhất** của I3, và phần dễ nói
sai nhất thì phải test được mà không cần dựng cửa sổ.

Sự thật phải nói ra, không được làm mờ đi: trong từ điển chỉ đạo hình ảnh
hiện nay, **phần lớn mục là gợi ý cho NGƯỜI đi chọn/chụp ảnh**, chỉ nhóm
chuyển cảnh (và "giữ hình tĩnh") là thứ máy dựng được. Từ I5, luồng «Dựng
video» ĐÃ đọc nhóm chuyển cảnh và dựng theo đúng nó; 18/25 mục còn lại vẫn
chỉ là lời khuyên cho người, và đó mới là phần cần nói cho rõ.

Trình bày một bản chỉ đạo như thể máy sắp tự làm tất cả là đúng hai lớp lỗi
đã lặp lại nhiều lần trong dự án: hứa thứ không làm được (#5), và nói ra câu
người dùng không dùng được (#6).
"""
from __future__ import annotations

from autodub_gui.status_text import STATUS_OK, STATUS_WARN

#: Nhãn đứng TRƯỚC mỗi mục. Phân biệt bằng CHỮ, không chỉ bằng màu: màu không
#: đọc được bằng test, không đọc được khi in ra giấy, và không đọc được với
#: người mù màu.
NHAN_GOI_Y = f"{STATUS_WARN} Gợi ý cho bạn"
NHAN_MAY_DUNG = f"{STATUS_OK} Máy dựng được"


def nhan_muc(muc: dict) -> str:
    """Một mã đã chọn, ở dạng đọc được: nhãn loại + tên tiếng Việt + mã."""
    ten = str(muc.get("nhan") or muc.get("ma") or "")
    ma = str(muc.get("ma") or "")
    dau = NHAN_GOI_Y if muc.get("laGoiY", True) else NHAN_MAY_DUNG
    return f"{dau}: {ten} ({ma})" if ma and ma != ten else f"{dau}: {ten}"


def mo_ta_loai(muc: dict) -> str:
    """Câu giải thích khác nhau cho hai loại — không dùng chung một câu."""
    if muc.get("laGoiY", True):
        return "gợi ý khi bạn chọn hoặc chụp ảnh; máy không tự làm được"
    return "khâu ghép hình dựng được thật"


def cau_ty_le(ban: dict) -> str:
    """Câu mở đầu, nói THẲNG tỉ lệ. Đây là câu bắt buộc của mini-spec I3."""
    goi_y = int(ban.get("soGoiY") or 0)
    may = int(ban.get("soMayDungDuoc") or 0)
    tong = goi_y + may
    if tong == 0:
        return ("Bản chỉ đạo này chưa chọn mục nào. Không có gì để chuẩn bị "
                "và cũng không có gì máy tự làm.")
    return (
        f"{goi_y}/{tong} mục dưới đây là GỢI Ý để bạn chuẩn bị ảnh — máy không "
        f"tự làm được. {may}/{tong} mục là thứ khâu ghép hình dựng được, và "
        "ngay cả chúng thì trang «Dựng video» hiện CHƯA đọc tới. Bản chỉ đạo "
        "không tự áp vào video của bạn.")


def cau_trang_thai(ban: dict) -> str:
    """Bản này còn khớp kịch bản/từ điển hiện tại không.

    Nói rõ PHẢI LÀM GÌ, và nói rõ việc chạy lại là **tốn tiền** — máy chủ cố
    ý không tự chạy lại, nên câu ở đây không được úp mở chuyện đó.
    """
    if not ban.get("laCu"):
        return ""
    ly_do = []
    if ban.get("kichBanDaDoi"):
        ly_do.append("kịch bản đã đổi lời kể từ lúc lấy chỉ đạo")
    if ban.get("catalogDaDoi"):
        ly_do.append(
            "từ điển chỉ đạo đã lên phiên bản "
            f"{ban.get('catalogVersionHienTai')}")
    return (f"{STATUS_WARN} Bản này đã cũ — " + "; ".join(ly_do)
            + ". Nội dung cũ vẫn đọc được; muốn bản mới thì bấm lấy lại "
              "(tính thêm một lượt).")


def dong_cho_doan(doan: dict) -> list[str]:
    """Các dòng chữ của MỘT đoạn — dùng cho cả giao diện lẫn test."""
    dong = [nhan_muc(c) for c in (doan.get("chon") or [])]
    if not dong:
        dong.append(f"{STATUS_WARN} Không chọn mục nào cho đoạn này")
    ly_do = str(doan.get("lyDo") or "").strip()
    if ly_do:
        dong.append(f"Vì sao: {ly_do}")
    return dong

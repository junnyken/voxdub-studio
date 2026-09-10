"""Ảnh minh hoạ cho một đoạn kịch bản — mini-spec H4d.

Kịch bản brand (H3) cho mỗi đoạn một `visualBriefVi`. Module này biến gợi ý
đó thành một tấm ảnh dùng được, đi đúng ba bước như C1:

    sinh  →  kiểm  →  đóng nhãn

Không có đường tắt nào bỏ bước kiểm, và bước kiểm ở đây hỏi câu **ngược** với
C1. Ở C1 có ảnh sản phẩm thật làm neo nên câu hỏi là *"còn là sản phẩm đó
không"*. Ở đây không có neo nào — mô hình vẽ từ chữ — nên câu hỏi phải là
*"có LỠ vẽ ra một sản phẩm không"*. Lý do: ảnh này sẽ nằm trong cùng một video
bán hàng, cạnh sản phẩm thật; một cái hộp có nhãn do mô hình bịa ra vẫn là
"sản phẩm" trong mắt máy quét của sàn.

Một chỗ **chặt hơn C1**: ở đó `dung_duoc_de_ban` không đòi đã đóng nhãn, còn
ở đây `dung_duoc` đòi. Ảnh C1 là ảnh sản phẩm thật của người bán, đóng nhãn
hụt thì nó vẫn là ảnh thật; ảnh này thì 100% do máy vẽ, không nhãn là không
có gì phân biệt nó với một khung hình quay thật.
"""
from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass, field

from autodub.product_scene import (
    _KHONG_THU_LAI, bam_tep, dong_nhan_chu, thu_nho_de_gui,
)

logger = logging.getLogger(__name__)

#: Nhãn đóng lên ảnh. Không dấu — bộ chữ mặc định của ffmpeg trên máy người
#: dùng không chắc có dấu tiếng Việt, và một dòng nhãn vỡ chữ còn khó hiểu
#: hơn không có nhãn.
NHAN = "AI-generated — anh minh hoa"

#: Tên tệp nhật ký tra soát, nằm cạnh ảnh.
NHAT_KY = "nhat_ky_anh_minh_hoa.json"


@dataclass
class AnhMinhHoa:
    """Một ảnh minh hoạ đã sinh, kèm phán quyết tuân thủ."""

    duong_dan: str
    goi_y: str
    phan_quyet: str          # DAT | CO_SAN_PHAM
    ly_do: str               # bằng lời, không phải điểm số
    da_kiem: bool            # False = chưa kiểm được, phải coi như trượt
    #: Đoạn nào của kịch bản. Kết quả phải TỰ MANG số đoạn: bên gọi ghép lại
    #: theo thứ tự trong danh sách thì một đoạn hỏng giữa mẻ đẩy lệch toàn bộ
    #: phần sau, và ảnh đi lên nhầm đoạn mà không có triệu chứng nào.
    chi_so: int = -1
    vox: int = 0
    bam: str = ""
    da_dong_nhan: bool = False

    @property
    def dung_duoc(self) -> bool:
        """Ảnh này có được ghép vào video không."""
        return self.phan_quyet == "DAT" and self.da_kiem and self.da_dong_nhan


@dataclass
class MeAnh:
    """Một lượt sinh nhiều ảnh minh hoạ."""

    thu_muc: str
    ket_qua: list[AnhMinhHoa] = field(default_factory=list)
    #: (chỉ số đoạn, lý do) cho từng đoạn KHÔNG sinh được.
    hong: list[tuple[int, str]] = field(default_factory=list)

    @property
    def so_dung_duoc(self) -> int:
        return sum(1 for k in self.ket_qua if k.dung_duoc)


def kiem_anh(khach, anh: dict, *, goi_y: str = "") -> tuple[str, str, bool]:
    """Hỏi máy chủ: ảnh này có lỡ vẽ ra sản phẩm nào không?

    Trả ``(phan_quyet, ly_do, da_kiem)``. Hỏng thì trả ``CO_SAN_PHAM`` —
    nghiêng về phía an toàn, y như `product_scene.kiem_tuan_thu`: đoán sai
    theo hướng an toàn chỉ mất một tấm ảnh, đoán sai hướng kia là người bán
    mất tài khoản.
    """
    from autodub.saas_client import new_job_id

    try:
        ket = khach.assist(
            "kiem_anh_minh_hoa", {"note": goi_y[:400]},
            images=[anh], job_id=new_job_id(), timeout=90.0)
    except Exception as e:  # noqa: BLE001 — mọi lỗi đều nghiêng về an toàn
        # Kèm NGUYÊN VĂN nguyên nhân: "chưa kiểm được" một mình không cho
        # người dùng biết nên đợi mạng, đổi gợi ý, hay báo lỗi.
        logger.warning(f"Không kiểm được ảnh minh hoạ ({str(e)[:120]}) — "
                       "đánh dấu là không dùng được cho chắc")
        return ("CO_SAN_PHAM",
                f"chưa kiểm được ({str(e)[:80]}) — đánh dấu an toàn", False)

    if not ket:
        return "CO_SAN_PHAM", "máy chủ không trả kết quả kiểm", False
    dau = ket[0]
    gia_tri = str(dau.get("value", "")).strip().upper()
    ly_do = str(dau.get("reason", "")).strip() or "không rõ"
    if gia_tri not in ("DAT", "CO_SAN_PHAM"):
        return "CO_SAN_PHAM", f"kết quả kiểm lạ ({gia_tri[:20]})", False
    return gia_tri, ly_do, True


def sinh_mot_anh(goi_y: str, thu_muc_ra: str, *, ten_tep: str = "",
                 noi_goi: str = "", khach=None) -> AnhMinhHoa:
    """Sinh MỘT ảnh minh hoạ, kiểm, rồi đóng nhãn.

    Ném lỗi nếu không sinh được ảnh — bên gọi quyết định dừng cả mẻ hay đi
    tiếp. Sinh được rồi thì luôn trả về một `AnhMinhHoa`, kể cả khi nó trượt
    kiểm: người dùng đã trả tiền cho tấm ảnh đó, họ có quyền nhìn thấy nó và
    biết vì sao nó không dùng được.
    """
    from autodub.saas_client import get_client, is_configured, new_job_id

    if not is_configured():
        raise RuntimeError(
            "Tính năng này cần tài khoản VoxDub — mở Cài đặt để kết nối.")
    khach = khach or get_client()
    os.makedirs(thu_muc_ra, exist_ok=True)

    tra_ve = khach.story_image(goi_y, job_id=new_job_id(), provider=noi_goi)
    anh_moi = tra_ve.get("image") or {}
    if not anh_moi.get("data"):
        raise RuntimeError("Máy chủ nhận lượt gọi nhưng không trả về ảnh")

    ra_path = os.path.join(thu_muc_ra, ten_tep or f"{new_job_id()[:12]}.jpg")
    with open(ra_path, "wb") as f:
        f.write(base64.b64decode(anh_moi["data"]))

    # Gửi bản THU NHỎ đi kiểm, không phải ảnh mô hình vừa trả về: ảnh gốc quá
    # nặng nên lượt kiểm bị chặn ở tầng vận chuyển (bài học C7). Phán quyết
    # vẫn đúng vì bước này nhìn có hộp/nhãn/chữ hay không, không soi điểm ảnh.
    try:
        anh_de_kiem = thu_nho_de_gui(ra_path, thu_muc_ra, "_anh_kiem_tam.jpg")
    except (OSError, ValueError) as e:
        logger.warning(f"Không chuẩn bị được ảnh để kiểm ({e})")
        anh_de_kiem = anh_moi

    phan_quyet, ly_do, da_kiem = kiem_anh(khach, anh_de_kiem, goi_y=goi_y)
    da_dong_nhan = dong_nhan_chu(ra_path, NHAN)

    return AnhMinhHoa(
        duong_dan=ra_path, goi_y=goi_y, phan_quyet=phan_quyet, ly_do=ly_do,
        da_kiem=da_kiem, vox=int(tra_ve.get("creditCharged") or 0),
        # Băm SAU khi đóng nhãn: tệp trên đĩa lúc này mới là tệp cuối cùng,
        # và đó mới là thứ cần khớp lúc ghép video (mini-spec C6).
        bam=bam_tep(ra_path), da_dong_nhan=da_dong_nhan)


def sinh_nhieu_anh(goi_y_theo_doan: list[tuple[int, str]], thu_muc_ra: str, *,
                   noi_goi: str = "", khach=None, tien_do=None) -> MeAnh:
    """Sinh ảnh cho nhiều đoạn. ``goi_y_theo_doan`` = [(chỉ số đoạn, gợi ý)].

    Một đoạn hỏng không giết cả mẻ — trừ những lý do mà thử tiếp cũng ra đúng
    câu trả lời đó: cửa đang tắt, hoặc máy này chưa nằm trong danh sách chạy
    thử. Thử thêm năm lượt nữa chỉ tốn thời gian của người dùng để nhận về
    cùng một câu (bài học C15).
    """
    me = MeAnh(thu_muc=thu_muc_ra)
    for thu_tu, (chi_so, goi_y) in enumerate(goi_y_theo_doan):
        if tien_do:
            tien_do(thu_tu, len(goi_y_theo_doan))
        try:
            ket = sinh_mot_anh(
                goi_y, thu_muc_ra, ten_tep=f"doan_{chi_so + 1:02d}.jpg",
                noi_goi=noi_goi, khach=khach)
            ket.chi_so = chi_so
            me.ket_qua.append(ket)
        except Exception as e:  # noqa: BLE001 — một đoạn hỏng không giết cả mẻ
            if getattr(e, "code", "") in _KHONG_THU_LAI:
                raise
            logger.warning(f"Không vẽ được ảnh cho đoạn {chi_so + 1} "
                           f"({str(e)[:120]})")
            me.hong.append((chi_so, str(e)[:200]))
    return me

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

#: Mã lỗi mà THỬ LẠI cũng ra đúng câu trả lời đó — khác `_KHONG_THU_LAI` ở
#: chỗ: những mã kia dừng CẢ MẺ, còn những mã này chỉ nói với người dùng
#: "đừng bấm lại nút thử lại cho đoạn này". Bảo họ thử lại một thứ không thể
#: khác đi là làm mất thời gian và có khi mất tiền.
_KHONG_THU_LAI_ME = frozenset({
    "IMAGE_STAGE_OFF", "IMAGE_STAGE_CALIBRATION",  # cửa đóng
    "INSUFFICIENT_CREDIT",                          # hết Vox
    "DAILY_LIMIT", "DAILY_LIMIT_CONCEPT",           # hết hạn mức ngày
    "NO_PROVIDER", "PROVIDER_MISCONFIGURED",        # chưa cấu hình nơi gọi
    "KHONG_THAY_NOI_GOI",
})


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
    #: Vox của lượt VẼ và lượt KIỂM, tách riêng. Mỗi ảnh là HAI lượt tính
    #: tiền; gộp làm một thì lúc lượt kiểm hỏng không nói được người dùng vừa
    #: mất bao nhiêu và vì việc gì.
    vox_ve: int = 0
    vox_kiem: int = 0
    bam: str = ""
    da_dong_nhan: bool = False

    @property
    def vox(self) -> int:
        """Tổng Vox thật sự đã mất cho tấm ảnh này."""
        return self.vox_ve + self.vox_kiem

    @property
    def dung_duoc(self) -> bool:
        """Ảnh này có được ghép vào video không."""
        return self.phan_quyet == "DAT" and self.da_kiem and self.da_dong_nhan

    @property
    def vi_sao_khong_dung_duoc(self) -> str:
        """Nói ĐÚNG chuyện gì hỏng — ba nguyên nhân cần ba cách chữa khác nhau."""
        if self.dung_duoc:
            return ""
        if not self.da_kiem:
            return f"chưa kiểm được ({self.ly_do})"
        if self.phan_quyet != "DAT":
            return f"ảnh có sản phẩm hoặc chữ đọc được ({self.ly_do})"
        return "không đóng được nhãn AI-generated lên ảnh"


@dataclass
class DoanHong:
    """Một đoạn KHÔNG vẽ được — mini-spec H4d-0.

    Không đủ nếu chỉ giữ lý do: người dùng cần biết **có mất tiền không** và
    **thử lại có ích không**. Hai câu hỏi đó quyết định việc họ bấm tiếp.
    """

    chi_so: int
    ly_do: str
    #: Vox đã mất cho đoạn này dù không có ảnh nào tới nơi.
    vox: int = 0
    #: Thử lại có cơ hội khác kết quả không. Cửa đang tắt hay chưa nối tài
    #: khoản thì thử lại bao nhiêu lần cũng ra đúng câu trả lời đó.
    thu_lai_duoc: bool = True


@dataclass
class MeAnh:
    """Một lượt sinh nhiều ảnh minh hoạ, kèm đủ thứ để giao diện nói ra được.

    Trước H4d-0, `hong` được ghi nhưng **không nơi nào đọc** — mẻ hỏng cả mẻ
    thì màn hình im lặng hoàn toàn: không hộp thoại, không toast, chỉ còn
    dòng "Còn N đoạn chưa có ảnh" y như lúc chưa bấm. Người dùng bấm nút,
    chờ, rồi không được biết chuyện gì đã xảy ra hay đã mất bao nhiêu.
    """

    thu_muc: str
    ket_qua: list[AnhMinhHoa] = field(default_factory=list)
    hong: list[DoanHong] = field(default_factory=list)
    #: Người dùng chủ động dừng mẻ. KHÁC với hỏng: không có gì để "thử lại",
    #: và không có lỗi nào để báo — nói nhầm thành hỏng là đổ cho phần mềm
    #: một chuyện chính họ vừa quyết.
    da_huy: bool = False
    #: Số đoạn còn lại lúc dừng — để nói "đã dừng, còn N đoạn chưa vẽ" chứ
    #: không phải một câu chung chung.
    so_chua_ve: int = 0

    @property
    def so_dung_duoc(self) -> int:
        return sum(1 for k in self.ket_qua if k.dung_duoc)

    @property
    def so_yeu_cau(self) -> int:
        return len(self.ket_qua) + len(self.hong)

    @property
    def vox_da_mat(self) -> int:
        """Tổng Vox thật sự đã trừ trong cả mẻ, kể cả cho ảnh bỏ đi."""
        return sum(k.vox for k in self.ket_qua) + sum(h.vox for h in self.hong)

    @property
    def vox_mat_khong_duoc_gi(self) -> int:
        """Phần tiền đã trả mà không nhận được ảnh dùng được.

        Đây là con số người dùng cần thấy nhất, và cũng là con số dễ bị giấu
        nhất: nó nằm rải giữa ảnh trượt kiểm và đoạn vẽ hỏng.
        """
        return (sum(k.vox for k in self.ket_qua if not k.dung_duoc)
                + sum(h.vox for h in self.hong))

    @property
    def trang_thai(self) -> str:
        """`xong` | `da_huy` | `hong_mot_phan` | `hong_ca_me`.

        Bốn ca, bốn cách nói. `da_huy` đứng TRƯỚC mọi ca hỏng: dừng giữa
        chừng thì phần chưa vẽ không phải là phần "hỏng".
        """
        if self.da_huy:
            return "da_huy"
        if not self.so_yeu_cau:
            return "xong"
        if self.so_dung_duoc == self.so_yeu_cau:
            return "xong"
        if self.so_dung_duoc == 0:
            return "hong_ca_me"
        return "hong_mot_phan"

    @property
    def thu_lai_duoc(self) -> bool:
        """Có đoạn nào thử lại còn có ích không.

        Ảnh trượt kiểm thì vẽ lại CÓ THỂ ra khác (mô hình không tất định),
        nhưng đoạn hỏng vì cửa đóng thì không.
        """
        if self.da_huy:
            # Còn đoạn chưa vẽ thì "vẽ tiếp" là việc có nghĩa.
            return self.so_chua_ve > 0
        return (any(h.thu_lai_duoc for h in self.hong)
                or any(not k.dung_duoc for k in self.ket_qua))


def kiem_anh(khach, anh: dict, *, goi_y: str = "") -> tuple[str, str, bool, int]:
    """Hỏi máy chủ: ảnh này có lỡ vẽ ra sản phẩm nào không?

    Trả ``(phan_quyet, ly_do, da_kiem, vox)``. ``vox`` là tiền THẬT của lượt
    kiểm, đọc từ trả lời của máy chủ chứ không đoán bằng hằng số ở máy khách —
    đoán là đúng lớp lỗi "giá hiện ra khác giá bị trừ". Hỏng thì trả
    ``CO_SAN_PHAM`` —
    nghiêng về phía an toàn, y như `product_scene.kiem_tuan_thu`: đoán sai
    theo hướng an toàn chỉ mất một tấm ảnh, đoán sai hướng kia là người bán
    mất tài khoản.
    """
    from autodub.saas_client import new_job_id

    try:
        # `assist_day_du` chứ không phải `assist`: cần cả `creditCharged`.
        goi = khach.assist_day_du(
            "kiem_anh_minh_hoa", {"note": goi_y[:400]},
            images=[anh], job_id=new_job_id(), timeout=90.0)
    except Exception as e:  # noqa: BLE001 — mọi lỗi đều nghiêng về an toàn
        # Kèm NGUYÊN VĂN nguyên nhân: "chưa kiểm được" một mình không cho
        # người dùng biết nên đợi mạng, đổi gợi ý, hay báo lỗi.
        logger.warning(f"Không kiểm được ảnh minh hoạ ({str(e)[:120]}) — "
                       "đánh dấu là không dùng được cho chắc")
        return ("CO_SAN_PHAM",
                f"chưa kiểm được ({str(e)[:80]}) — đánh dấu an toàn", False, 0)

    vox = int((goi or {}).get("creditCharged") or 0)
    ket = (goi or {}).get("results")
    ket = ket if isinstance(ket, list) else []
    if not ket:
        return "CO_SAN_PHAM", "máy chủ không trả kết quả kiểm", False, vox
    dau = ket[0]
    gia_tri = str(dau.get("value", "")).strip().upper()
    ly_do = str(dau.get("reason", "")).strip() or "không rõ"
    if gia_tri not in ("DAT", "CO_SAN_PHAM"):
        return "CO_SAN_PHAM", f"kết quả kiểm lạ ({gia_tri[:20]})", False, vox
    return gia_tri, ly_do, True, vox


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

    phan_quyet, ly_do, da_kiem, vox_kiem = kiem_anh(khach, anh_de_kiem,
                                                    goi_y=goi_y)
    da_dong_nhan = dong_nhan_chu(ra_path, NHAN)

    return AnhMinhHoa(
        duong_dan=ra_path, goi_y=goi_y, phan_quyet=phan_quyet, ly_do=ly_do,
        da_kiem=da_kiem, vox_ve=int(tra_ve.get("creditCharged") or 0),
        vox_kiem=vox_kiem,
        # Băm SAU khi đóng nhãn: tệp trên đĩa lúc này mới là tệp cuối cùng,
        # và đó mới là thứ cần khớp lúc ghép video (mini-spec C6).
        bam=bam_tep(ra_path), da_dong_nhan=da_dong_nhan)


def sinh_nhieu_anh(goi_y_theo_doan: list[tuple[int, str]], thu_muc_ra: str, *,
                   noi_goi: str = "", khach=None, tien_do=None,
                   huy=None) -> MeAnh:
    """Sinh ảnh cho nhiều đoạn. ``goi_y_theo_doan`` = [(chỉ số đoạn, gợi ý)].

    Một đoạn hỏng không giết cả mẻ — trừ những lý do mà thử tiếp cũng ra đúng
    câu trả lời đó: cửa đang tắt, hoặc máy này chưa nằm trong danh sách chạy
    thử. Thử thêm năm lượt nữa chỉ tốn thời gian của người dùng để nhận về
    cùng một câu (bài học C15).

    ``huy`` là hàm không tham số trả ``True`` khi người dùng bấm dừng. Nó được
    hỏi **giữa hai ảnh**, không bao giờ cắt ngang một ảnh đang vẽ dở: máy chủ
    trừ Vox ngay sau khi vẽ xong, nên buông kết nối giữa chừng là mất tiền mà
    không nhận được tệp. Mẻ mười tấm là 330 Vox và bốn phút chờ — không có
    đường dừng thì lỡ tay bấm nhầm chỉ còn cách giết app, mà giết app thì mất
    luôn những ảnh đã trả tiền.
    """
    me = MeAnh(thu_muc=thu_muc_ra)
    for thu_tu, (chi_so, goi_y) in enumerate(goi_y_theo_doan):
        if huy is not None and huy():
            me.da_huy = True
            me.so_chua_ve = len(goi_y_theo_doan) - thu_tu
            logger.info(f"Người dùng dừng mẻ vẽ — còn {me.so_chua_ve} đoạn "
                        f"chưa vẽ, đã tiêu {me.vox_da_mat} Vox")
            break
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
            me.hong.append(DoanHong(
                chi_so=chi_so, ly_do=str(e)[:200],
                # Máy chủ chỉ trừ tiền SAU khi đã vẽ xong (`charge()` đứng sau
                # `gateway.generateStoryImage` ở route `/story-image`), nên
                # ném ở đây nghĩa là chưa mất Vox nào cho đoạn này.
                vox=0,
                thu_lai_duoc=getattr(e, "code", "") not in _KHONG_THU_LAI_ME))
    return me

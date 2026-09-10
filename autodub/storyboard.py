"""Storyboard — dựng dòng thời gian cho một kịch bản brand (mini-spec H4a).

Nhận một `BrandScript` **đã ở trạng thái `ready`** (H3) và tính ra mỗi đoạn
chiếm bao nhiêu giây, để bước sau còn biết mỗi cảnh phải giữ hình bao lâu.

**Vì sao cần**: `product_video.dung_video()` hiện ghép ảnh với thời lượng
ĐỒNG ĐỀU cho mọi ảnh. Kịch bản thì mỗi đoạn dài ngắn khác nhau — đoạn hook
hai câu ngắn và đoạn bằng chứng bốn câu dài mà giữ hình bằng nhau thì hoặc
hụt tiếng hoặc thừa hình.

**Chạy hoàn toàn trên máy người dùng, không tốn Vox, không gọi mô hình.**
Đây là phép tính thuần, và đó là chủ đích: bước dựng dòng thời gian mà phải
trả tiền thì người dùng sẽ ngại chỉnh lại cho vừa ý.

**Ranh giới đã chốt** (docs/ARCH.md §4 — đọc trước khi mở rộng): máy chủ
KHÔNG có thực thể job ghép video, KHÔNG có `image_id`, KHÔNG lưu ảnh. Chọn
ảnh, sắp thứ tự, ghép bằng ffmpeg đều ở máy người dùng. Ba bản đề bài trong
ngày 21/8/2026 đã giả định ngược lại và cả ba đều sai; tài liệu ghi lại chính
là để lần sau không lặp.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Đo THẬT bằng chính engine sẽ đọc (VieNeu ONNX, 4 giọng dựng sẵn × 4 câu
#: kiểu kịch bản quảng cáo, 10/09/2026). Khớp tuyến tính trên số liệu đo:
#: giây ≈ 0,39 + 0,504 × số âm tiết. Kiểm lại trên chính dữ liệu đó: dự đoán
#: 1,40 / 5,93 / 7,95 / 10,97 so với đo được 1,44 / 5,88 / 7,88 / 11,04.
#:
#: Phần phụ trội cố định là có thật, không phải sai số: câu 2 âm tiết mất
#: 1,44 giây (0,72 giây mỗi âm tiết) trong khi câu 21 âm tiết chỉ mất 0,53 —
#: khoảng lặng đầu/cuối mỗi lượt đọc không co lại theo độ dài câu.
#:
#: **Kiểm chéo trên câu CHƯA từng dùng để khớp** (5 câu × 3 giọng, 10/09):
#: sai lệch tuyệt đối trung bình **3,3%**, và cả 5 câu đều rơi trong khoảng
#: ước lượng. Không có bước này thì hai hằng số trên chỉ chứng minh được
#: chúng khớp với chính dữ liệu đã dùng để tính ra chúng.
GIAY_MOI_AM_TIET = 0.504
PHU_TROI_MOI_CAU_GIAY = 0.39

#: Giọng đọc nhanh nhất và chậm nhất chênh nhau 1,21 lần (0,473 - 0,575 giây
#: mỗi âm tiết, đo trên 4 giọng dựng sẵn). Nên ước lượng phải trả về một
#: KHOẢNG — đưa ra một con số lẻ tới hai chữ số thập phân là giả vờ chính xác
#: hơn thực tế, và người dùng sẽ dựng video theo con số đó rồi lệch tiếng.
BIEN_DO_GIONG = 0.15

#: Ngưỡng cảnh báo khi kịch bản mới dài/ngắn hơn hẳn video tham khảo. Cả
#: điểm của H2 là học NHỊP của video nguồn; học xong mà viết ra kịch bản dài
#: gấp đôi thì nhịp đó không còn ý nghĩa gì. 1,5 lần là mức bắt đầu đáng nói,
#: không phải mức chặn — người dùng có thể cố ý làm video dài hơn.
TI_LE_LECH_DANG_NOI = 1.5

_DAU_CAU = re.compile(r"[.,!?;:…–—\"'“”‘’()\[\]]+")
_KET_CAU = re.compile(r"[.!?…]+")


class KichBanChuaDungDuoc(RuntimeError):
    """Kịch bản chưa ở trạng thái `ready` thì KHÔNG dựng storyboard.

    Đây là cổng của H4, và nó phải nằm ở tầng thấp nhất tạo ra storyboard —
    không phải chỉ ở nút bấm trên giao diện. Một kịch bản `blocked` (có đoạn
    trùng câu chữ nguồn hoặc chứa cụm brand tự cấm) hay `unconfirmed` (chưa
    đối chiếu được) mà đi tiếp thành video là đúng thứ cả H3 dựng ra để chặn.
    """


def dem_am_tiet(text: str) -> int:
    """Đếm âm tiết tiếng Việt.

    Tiếng Việt viết rời từng âm tiết nên đếm cụm cách nhau bởi khoảng trắng
    là đủ — không cần từ điển. Bỏ dấu câu trước khi đếm để "xong." và "xong"
    ra cùng một số.
    """
    return len([t for t in _DAU_CAU.sub(" ", str(text or "")).split() if t])


def dem_cau(text: str) -> int:
    """Đếm câu — mỗi câu chịu một lần phụ trội đầu/cuối khi đọc."""
    s = str(text or "").strip()
    if not s:
        return 0
    return max(1, len([p for p in _KET_CAU.split(s) if p.strip()]))


@dataclass
class UocLuongGiay:
    """Ước lượng thời gian đọc, kèm KHOẢNG chứ không chỉ một con số."""

    giay: float
    giay_min: float
    giay_max: float

    def to_dict(self) -> dict:
        return {"giay": round(self.giay, 2),
                "giay_min": round(self.giay_min, 2),
                "giay_max": round(self.giay_max, 2)}


def uoc_luong_giay_doc(text: str) -> UocLuongGiay:
    """Ước lượng thời gian đọc một đoạn lời.

    Trả về KHOẢNG vì giọng đọc khác nhau chênh tới 1,21 lần (đo thật). Bên
    gọi nào cần một con số thì dùng `.giay`, nhưng giao diện phải hiện khoảng
    — nếu không người dùng sẽ dựng hình khít theo con số rồi lệch tiếng.
    """
    am_tiet = dem_am_tiet(text)
    if not am_tiet:
        return UocLuongGiay(0.0, 0.0, 0.0)
    giay = PHU_TROI_MOI_CAU_GIAY * dem_cau(text) + GIAY_MOI_AM_TIET * am_tiet
    return UocLuongGiay(giay, giay * (1 - BIEN_DO_GIONG), giay * (1 + BIEN_DO_GIONG))


@dataclass
class DoanStoryboard:
    """Một đoạn trên dòng thời gian."""

    thu_tu: int
    beat_type: str
    loi_doc: str
    caption: str
    visual_brief: str
    bat_dau_s: float
    ket_thuc_s: float
    uoc_luong: UocLuongGiay

    @property
    def giay(self) -> float:
        return self.ket_thuc_s - self.bat_dau_s


@dataclass
class Storyboard:
    """Dòng thời gian đầy đủ + những chỗ đáng nói cho người dùng."""

    doan: list[DoanStoryboard] = field(default_factory=list)
    tong_giay: float = 0.0
    tong_giay_min: float = 0.0
    tong_giay_max: float = 0.0
    #: Thời lượng của video tham khảo, nếu bên gọi đưa Blueprint vào.
    nguon_giay: float = 0.0
    canh_bao: list[str] = field(default_factory=list)


def _giay_cua_blueprint(blueprint: dict | None) -> float:
    """Video tham khảo dài bao nhiêu, suy từ mốc cuối của các beat."""
    if not blueprint:
        return 0.0
    cuoi = [float(b.get("endS") or 0) for b in (blueprint.get("beats") or [])]
    return max(cuoi) if cuoi else 0.0


def dung_storyboard(kich_ban: dict, blueprint: dict | None = None) -> Storyboard:
    """Dựng dòng thời gian từ một kịch bản brand ĐÃ `ready`.

    ``blueprint`` (tuỳ chọn): Flow Blueprint gốc — dùng để so nhịp. Cả điểm
    của H2 là học NHỊP của video tham khảo, nên kịch bản viết ra dài gấp rưỡi
    nguồn là chuyện đáng nói ngay tại đây, chứ không phải để người dùng phát
    hiện sau khi đã dựng xong video.

    Ném :class:`KichBanChuaDungDuoc` khi kịch bản chưa `ready`.
    """
    trang_thai = str(kich_ban.get("status") or "")
    if trang_thai != "ready":
        raise KichBanChuaDungDuoc(
            f"Kịch bản đang ở trạng thái «{trang_thai or 'không rõ'}», chưa "
            "dùng được. Chỉ kịch bản đã qua cả hai lớp kiểm mới dựng được "
            "video.")

    beats = kich_ban.get("beats") or []
    if not beats:
        raise KichBanChuaDungDuoc("Kịch bản không có đoạn nào.")

    sb = Storyboard()
    moc = 0.0
    tong_min = 0.0
    tong_max = 0.0
    for i, b in enumerate(beats):
        loi = str(b.get("voiceoverTextVi") or "")
        ul = uoc_luong_giay_doc(loi)
        sb.doan.append(DoanStoryboard(
            thu_tu=i + 1,
            beat_type=str(b.get("beatType") or "unknown"),
            loi_doc=loi,
            caption=str(b.get("captionSuggestionVi") or ""),
            visual_brief=str(b.get("visualBriefVi") or ""),
            bat_dau_s=round(moc, 2),
            ket_thuc_s=round(moc + ul.giay, 2),
            uoc_luong=ul,
        ))
        moc += ul.giay
        tong_min += ul.giay_min
        tong_max += ul.giay_max

        if not loi.strip():
            sb.canh_bao.append(
                f"Đoạn {i + 1} không có lời đọc — cảnh này sẽ im lặng.")

    sb.tong_giay = round(moc, 2)
    sb.tong_giay_min = round(tong_min, 2)
    sb.tong_giay_max = round(tong_max, 2)
    sb.nguon_giay = round(_giay_cua_blueprint(blueprint), 2)

    if sb.nguon_giay > 0 and sb.tong_giay > 0:
        ti_le = sb.tong_giay / sb.nguon_giay
        if ti_le >= TI_LE_LECH_DANG_NOI:
            sb.canh_bao.append(
                f"Kịch bản đọc hết khoảng {sb.tong_giay:.0f} giây, dài gấp "
                f"{ti_le:.1f} lần video tham khảo ({sb.nguon_giay:.0f} giây) "
                "— nhịp kể chuyện học được sẽ không còn giống nữa.")
        elif ti_le <= 1 / TI_LE_LECH_DANG_NOI:
            sb.canh_bao.append(
                f"Kịch bản chỉ đọc hết khoảng {sb.tong_giay:.0f} giây, ngắn "
                f"hơn nhiều video tham khảo ({sb.nguon_giay:.0f} giây) — có "
                "thể bị hụt so với nhịp đã học.")
    return sb

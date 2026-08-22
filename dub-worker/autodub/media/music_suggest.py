"""Gợi ý mô tả nhạc nền suy từ CHÍNH lời thoại của video (mini-spec V88).

Người dùng hỏi: "app có tự nhận định và chọn nhạc phù hợp cho video không?".
V37 sinh được nhạc AI nhưng bắt người dùng tự nghĩ ra mô tả ("nhạc vui tươi,
tempo nhanh") — mà nghĩ ra một mô tả tốt chính là phần khó.

Cách làm ở đây CỐ Ý không dùng AI:

- Máy chủ chỉ có 4 endpoint cố định (dịch, viết bài, nhạc, hiệu ứng); không có
  đường hỏi tự do nào. Thêm endpoint mới là việc của phía server, không làm
  trong bản này.
- Mọi tín hiệu cần thiết ĐÃ nằm sẵn trong transcript: nhịp nói, độ dài câu,
  dấu chấm hỏi/chấm than, từ khoá chủ đề. Suy từ số đo thì tức thì, chạy
  offline, không tốn Vox, và **giải thích được**.

Mỗi gợi ý luôn kèm LÝ DO bằng con số thật ("nói nhanh 4,2 chữ/giây"), để người
dùng tự đánh giá thay vì tin một cái nhãn từ trên trời rơi xuống. Đây cũng là
nguyên tắc của `emphasis_points.py` (V37): đưa ứng viên, không tự quyết.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: Nhóm chủ đề → (từ khoá, mô tả nhạc, tên nhóm để giải thích).
#: Từ khoá để cả tiếng Việt lẫn tiếng Anh vì transcript có thể là bản gốc.
_CHU_DE = (
    ("hài hước", ("cười", "hài", "vui", "buồn cười", "troll", "funny",
                  "laugh", "joke", "lol"),
     "nhạc nền vui nhộn, tiết tấu nảy, âm sắc sáng"),
    ("nấu ăn", ("nấu", "món", "công thức", "nguyên liệu", "gia vị", "recipe",
                "cook", "kitchen", "ingredient"),
     "nhạc nền ấm áp, mộc mạc, guitar nhẹ và tiết tấu thong thả"),
    ("du lịch", ("du lịch", "chuyến đi", "khám phá", "biển", "núi", "travel",
                 "trip", "journey", "explore"),
     "nhạc nền phóng khoáng, âm hưởng rộng mở, tiết tấu vừa"),
    ("công nghệ", ("máy tính", "phần mềm", "ứng dụng", "cài đặt", "công nghệ",
                   "ai", "software", "app", "tech", "device"),
     "nhạc nền điện tử tối giản, nhịp đều, không lấn tiếng nói"),
    ("thể thao", ("trận", "thi đấu", "bàn thắng", "vận động", "gym", "match",
                  "score", "workout", "training"),
     "nhạc nền mạnh mẽ, trống dồn, năng lượng cao"),
    ("kể chuyện", ("câu chuyện", "ngày xưa", "kể", "cuộc đời", "kỷ niệm",
                   "story", "once", "remember"),
     "nhạc nền tự sự, piano nhẹ, tiết tấu chậm"),
    ("tin tức", ("tin tức", "thông tin", "báo cáo", "sự kiện", "news",
                 "report", "announce"),
     "nhạc nền trung tính, nhịp đều, âm lượng nền thấp"),
)

#: Ngưỡng nhịp nói (chữ/giây) — đo trên chính transcript, không phải cảm tính.
_NOI_NHANH = 3.6
_NOI_CHAM = 2.2


@dataclass(frozen=True)
class GoiYNhac:
    """Một mô tả nhạc kèm lý do đo được."""

    mo_ta: str
    ly_do: str


def _chu(text: str) -> int:
    return len([t for t in re.split(r"\s+", text.strip()) if t])


def do_dac(segments: list[dict], text_field: str = "") -> dict:
    """Số đo thô của lời thoại — tách riêng để test được từng con số."""
    tong_chu = 0
    tong_giay = 0.0
    hoi = 0
    than = 0
    chu_hoa_lien = 0
    van_ban: list[str] = []
    for seg in segments or []:
        text = ""
        for khoa in (text_field, "text_vi", "text"):
            if khoa and str(seg.get(khoa, "")).strip():
                text = str(seg[khoa]).strip()
                break
        if not text:
            continue
        van_ban.append(text)
        tong_chu += _chu(text)
        try:
            keo_dai = float(seg.get("duration") or
                            (float(seg.get("end", 0)) - float(seg.get("start", 0))))
        except (TypeError, ValueError):
            keo_dai = 0.0
        if keo_dai > 0:
            tong_giay += keo_dai
        hoi += text.count("?")
        than += text.count("!")
        if re.search(r"\b[A-ZÀ-Ỹ]{3,}\b", text):
            chu_hoa_lien += 1

    so_cau = len(van_ban)
    return {
        "so_cau": so_cau,
        "tong_chu": tong_chu,
        "tong_giay": round(tong_giay, 2),
        "chu_moi_giay": round(tong_chu / tong_giay, 2) if tong_giay > 0 else 0.0,
        "ty_le_hoi": round(hoi / so_cau, 3) if so_cau else 0.0,
        "ty_le_than": round(than / so_cau, 3) if so_cau else 0.0,
        "ty_le_hoa": round(chu_hoa_lien / so_cau, 3) if so_cau else 0.0,
        "noi_dung": " ".join(van_ban).lower(),
    }


def _chu_de(noi_dung: str) -> tuple[str, str, int] | None:
    """Nhóm chủ đề khớp nhiều từ khoá nhất, kèm số lần khớp."""
    tot_nhat = None
    for ten, tu_khoa, mo_ta in _CHU_DE:
        dem = sum(len(re.findall(rf"\b{re.escape(t)}\b", noi_dung))
                  for t in tu_khoa)
        if dem and (tot_nhat is None or dem > tot_nhat[2]):
            tot_nhat = (ten, mo_ta, dem)
    return tot_nhat


def goi_y_nhac(segments: list[dict], text_field: str = "",
               toi_da: int = 3) -> list[GoiYNhac]:
    """2–3 mô tả nhạc nền hợp với video này, mỗi cái kèm lý do đo được.

    Danh sách rỗng khi transcript quá ngắn để nói được điều gì — thà không
    gợi ý còn hơn gợi ý bừa (cùng nguyên tắc "không bịa" của cả dự án).
    """
    so = do_dac(segments, text_field)
    if so["so_cau"] < 3 or so["tong_chu"] < 20:
        return []

    ra: list[GoiYNhac] = []

    # 1) Nhịp nói — tín hiệu chắc chắn nhất, luôn có nếu đo được thời lượng.
    cps = so["chu_moi_giay"]
    if cps >= _NOI_NHANH:
        ra.append(GoiYNhac(
            "nhạc nền sôi động, tiết tấu nhanh, năng lượng cao",
            f"lời thoại dày ({cps} chữ/giây) — nhạc chậm sẽ bị lời lấn"))
    elif cps and cps <= _NOI_CHAM:
        ra.append(GoiYNhac(
            "nhạc nền nhẹ nhàng, tiết tấu chậm, nhiều khoảng trống",
            f"nói thong thả ({cps} chữ/giây) — nhạc dồn dập sẽ chỏi"))
    elif cps:
        ra.append(GoiYNhac(
            "nhạc nền vừa phải, tiết tấu đều, âm lượng nền thấp",
            f"nhịp nói trung bình ({cps} chữ/giây)"))

    # 2) Chủ đề theo từ khoá.
    chu_de = _chu_de(so["noi_dung"])
    if chu_de:
        ten, mo_ta, dem = chu_de
        ra.append(GoiYNhac(mo_ta,
                           f"lời thoại nhắc tới chủ đề {ten} ({dem} lần)"))

    # 3) Cảm xúc: nhiều câu cảm thán / chữ hoa liền → nhấn mạnh.
    if so["ty_le_than"] >= 0.15 or so["ty_le_hoa"] >= 0.15:
        ra.append(GoiYNhac(
            "nhạc nền kịch tính, có cao trào, trống nhấn ở điểm mạnh",
            f"{int(so['ty_le_than'] * 100)}% số câu là câu cảm thán"))
    elif so["ty_le_hoi"] >= 0.2:
        ra.append(GoiYNhac(
            "nhạc nền tò mò, lửng lơ, không quá vui cũng không quá buồn",
            f"{int(so['ty_le_hoi'] * 100)}% số câu là câu hỏi — kiểu dẫn dắt"))

    # Bỏ trùng mô tả, giữ nguyên thứ tự (tín hiệu chắc chắn nhất lên trước).
    da_co: set[str] = set()
    loc: list[GoiYNhac] = []
    for g in ra:
        if g.mo_ta in da_co:
            continue
        da_co.add(g.mo_ta)
        loc.append(g)
    return loc[:toi_da]


# --------------------------------------------- đường qua máy chủ (V89) -- #

#: Trần ký tự gửi lên — máy chủ cũng cắt, nhưng cắt sớm ở đây thì không phải
#: đẩy vài trăm KB lời thoại qua mạng chỉ để bên kia vứt đi.
_TRAN_CHU = 4000


def _loi_thoai(segments: list[dict], text_field: str = "") -> str:
    return do_dac(segments, text_field)["noi_dung"][:_TRAN_CHU]


def goi_y_nhac_thong_minh(segments: list[dict], text_field: str = "",
                          video_title: str = "") -> tuple[list[GoiYNhac], str]:
    """Gợi ý tốt nhất có thể trong hoàn cảnh hiện tại.

    Trả ``(danh sách, nguồn)`` với ``nguồn`` là ``"may_chu"`` hoặc ``"luat"``
    — nơi gọi cần biết để nói đúng cho người dùng, chứ không phải để trang trí.

    Có tài khoản thì hỏi máy chủ (hiểu nội dung thật); hỏng hoặc chưa cấu hình
    thì rơi về luật đo trên máy. Đường luật KHÔNG bị thay thế: nó là thứ duy
    nhất chạy được khi không mạng, không tài khoản, và tốn 0 Vox.
    """
    from autodub.utils import setup_logging

    log = setup_logging("autodub.music_suggest")
    theo_luat = goi_y_nhac(segments, text_field)

    try:
        from autodub.saas_client import is_configured
        if not is_configured():
            return theo_luat, "luat"
    except Exception:  # rơi về tầng luật, giao diện nói rõ nguồn gợi ý
        return theo_luat, "luat"

    noi_dung = _loi_thoai(segments, text_field)
    if len(noi_dung) < 60:
        # Quá ít lời thoại để hỏi cho ra hồn — đừng tốn Vox của người dùng.
        return theo_luat, "luat"

    try:
        from autodub.saas_client import get_client, new_job_id

        ket = get_client().assist(
            "music_suggest",
            {"transcript": noi_dung, "videoTitle": (video_title or "")[:200]},
            job_id=new_job_id())
    except Exception as e:  # noqa: BLE001 — mọi lỗi đều rơi về đường luật
        log.info(f"Trợ lý chưa gợi ý được ({str(e)[:120]}) — dùng cách đo "
                 "trên máy")
        return theo_luat, "luat"

    tu_may_chu = [GoiYNhac(str(r.get("value", "")).strip(),
                           str(r.get("reason", "")).strip())
                  for r in ket
                  if str(r.get("value", "")).strip()
                  and str(r.get("reason", "")).strip()]
    if not tu_may_chu:
        return theo_luat, "luat"
    return tu_may_chu, "may_chu"

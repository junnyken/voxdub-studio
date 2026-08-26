"""Nhập một video + tệp phụ đề TIẾNG VIỆT SẴN thành dự án chỉnh sửa được.

Vì sao có tệp này (yêu cầu người dùng thật, 26/8/2026): *"tôi muốn lấy giọng
đọc .srt cho ra tiếng Việt ghép vào trong chỉnh sửa được không"* và *"ở chỗ
chỉnh sửa tôi có thể lấy video từ file… hay chỉ chỉnh sửa được video làm trên
tool này"*.

Câu trả lời lúc đó là chưa — Trình chỉnh sửa chỉ mở được thư mục dự án do
chính app tạo, và không có đường nào từ `.srt` sang giọng đọc. Nhưng mọi mảnh
đều đã có sẵn: đọc phụ đề, sinh giọng từng câu, ghép tiếng theo mốc, xuất
video. Thiếu đúng **một mảnh nối**: biến (video, phụ đề) thành thư mục dự án
đúng khuôn.

Đây là bản cho phụ đề **đã là tiếng Việt**. Không dịch, không gọi máy chủ, nên
không tốn Vox — giọng đọc offline VieNeu lo phần còn lại. Phụ đề tiếng nước
ngoài là chặng sau.

Ba chỗ chắc chắn vướng, xử ngay tại đây chứ không để bộ đọc gánh:

1. **Phụ đề hay cắt câu làm đôi** cho vừa dòng. Đọc thẳng từng dòng thì giọng
   ngắt cụt giữa câu — nên gộp lại bằng `gop_cau` (mini-spec C27) trước.
2. **Mốc chồng nhau**, hay gặp ở phụ đề tải từ mạng.
3. **Dòng rỗng / mốc lùi** — bỏ, nhưng phải ĐẾM và nói ra, không im lặng.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime

from autodub.languages import get_target
from autodub.utils import ensure_dir, setup_logging
from autodub.workdir import data_path

logger = setup_logging("autodub.nhap_phu_de")

#: Đuôi tệp video nhận vào — cùng danh sách với chỗ khác trong app.
DUOI_VIDEO = (".mp4", ".mov", ".mkv", ".avi", ".webm")


@dataclass
class KetQuaNhap:
    """Kết quả một lượt nhập."""

    thu_muc: str
    so_cau: int
    #: Những chỗ đã tự nắn hoặc bỏ — người dùng có quyền biết.
    canh_bao: list[str] = field(default_factory=list)


class LoiNhap(Exception):
    """Không nhập được, kèm câu nói rõ vì sao."""


def _giay(ts: str) -> float:
    from autodub.text.subtitle_parse import timestamp_to_seconds

    return float(timestamp_to_seconds(ts))


def cue_thanh_cau(cues) -> tuple[list[dict], list[str]]:
    """Đổi các dòng phụ đề thành câu thoại, kèm danh sách chỗ đã nắn."""
    canh_bao: list[str] = []
    tho: list[dict] = []
    bo_rong = 0
    bo_moc_hong = 0

    for c in cues:
        chu = " ".join(str(c.text or "").split())
        if not chu:
            bo_rong += 1
            continue
        try:
            dau, cuoi = _giay(c.start), _giay(c.end)
        except (ValueError, TypeError):
            bo_moc_hong += 1
            continue
        if cuoi <= dau:
            bo_moc_hong += 1
            continue
        tho.append({"start": dau, "end": cuoi, "text": chu})

    if bo_rong:
        canh_bao.append(f"Bỏ {bo_rong} dòng phụ đề không có chữ.")
    if bo_moc_hong:
        canh_bao.append(f"Bỏ {bo_moc_hong} dòng có mốc thời gian không hợp lệ.")

    tho.sort(key=lambda s: s["start"])

    # Mốc chồng nhau: kéo mốc kết thúc của dòng trước về sát dòng sau. Giữ
    # nguyên thì hai câu đọc chồng lên nhau lúc ghép tiếng.
    chong = 0
    for i in range(len(tho) - 1):
        if tho[i]["end"] > tho[i + 1]["start"]:
            tho[i]["end"] = tho[i + 1]["start"]
            chong += 1
    if chong:
        canh_bao.append(
            f"Nắn lại {chong} chỗ mốc thời gian chồng nhau — giữ nguyên thì "
            "hai câu sẽ đọc đè lên nhau.")

    return tho, canh_bao


def dung_cau_thoai(cues, *, gop: bool = True) -> tuple[list[dict], list[str]]:
    """Danh sách câu thoại hoàn chỉnh cho `transcript_<đích>.json`."""
    tho, canh_bao = cue_thanh_cau(cues)
    if not tho:
        raise LoiNhap(
            "Tệp phụ đề không có dòng nào dùng được. Kiểm tra lại tệp — cần "
            "định dạng .srt hoặc .vtt có mốc thời gian.")

    if gop:
        from autodub.transcribe_tool import gop_cau

        truoc = len(tho)
        tho = gop_cau(tho)
        if len(tho) < truoc:
            canh_bao.append(
                f"Gộp {truoc} dòng phụ đề thành {len(tho)} câu đọc được — "
                "phụ đề hay cắt câu làm đôi cho vừa dòng, đọc thẳng từng "
                "dòng thì giọng ngắt cụt giữa câu.")

    ra: list[dict] = []
    for i, s in enumerate(tho, 1):
        dau, cuoi = float(s["start"]), float(s["end"])
        chu = str(s["text"]).strip()
        ra.append({
            "id": i,
            "start": dau,
            "end": cuoi,
            "duration": round(cuoi - dau, 3),
            # Phụ đề đã là tiếng Việt: nó vừa là bản gốc vừa là bản đích.
            # Giữ cả hai trường để Trình chỉnh sửa hiện được cột đối chiếu.
            "text": chu,
            "text_vi": chu,
        })
    return ra, canh_bao


def nhap_du_an(video_path: str, phu_de_path: str, thu_muc_goc: str, *,
               target_key: str = "vi", gop: bool = True) -> KetQuaNhap:
    """Dựng thư mục dự án từ một video và một tệp phụ đề tiếng Việt.

    KHÔNG chép video — chỉ ghi nhớ đường dẫn trong `source_video.json`, đúng
    cách pipeline vẫn làm với tệp nằm ngoài thư mục dự án. Chép một tệp 2 GB
    chỉ để mở ra sửa là việc vô ích.
    """
    if not os.path.isfile(video_path):
        raise LoiNhap(f"Không thấy tệp video: {video_path}")
    if not video_path.lower().endswith(DUOI_VIDEO):
        raise LoiNhap(
            "Tệp video phải có đuôi " + ", ".join(DUOI_VIDEO) + ".")
    if not os.path.isfile(phu_de_path):
        raise LoiNhap(f"Không thấy tệp phụ đề: {phu_de_path}")

    from autodub.text.subtitle_parse import SubtitleParseError, parse_subtitle

    try:
        with open(phu_de_path, encoding="utf-8-sig") as f:
            noi_dung = f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise LoiNhap(f"Không đọc được tệp phụ đề: {e}") from e
    # `parse_subtitle` nhận ĐỊNH DẠNG ("srt"/"vtt"), không nhận đường dẫn —
    # suy ra từ đuôi tệp tại đây.
    dinh_dang = os.path.splitext(phu_de_path)[1].lower().lstrip(".")
    if dinh_dang not in ("srt", "vtt"):
        raise LoiNhap(
            f"Chỉ nhận tệp phụ đề .srt hoặc .vtt (tệp bạn chọn có đuôi "
            f"«.{dinh_dang}»).")
    try:
        cues, bo_qua = parse_subtitle(noi_dung, dinh_dang)
    except SubtitleParseError as e:
        raise LoiNhap(f"Tệp phụ đề không đọc được: {e}") from e

    cau, canh_bao = dung_cau_thoai(cues, gop=gop)
    if bo_qua:
        # `parse_subtitle` tự bỏ những khối sai khuôn. Im lặng thì người dùng
        # tưởng phụ đề của mình vào đủ.
        canh_bao.insert(0, f"Bỏ qua {bo_qua} khối phụ đề sai khuôn trong tệp.")

    target = get_target(target_key)
    ten = datetime.now().strftime("%Y%m%d%H%M%S") + target.folder_suffix
    thu_muc = ensure_dir(os.path.join(thu_muc_goc, ten))

    with open(data_path(thu_muc, target.transcript_name, create_dir=True),
              "w", encoding="utf-8") as f:
        json.dump(cau, f, ensure_ascii=False, indent=2)

    with open(data_path(thu_muc, "source_video.json"), "w",
              encoding="utf-8") as f:
        json.dump({"file_path": os.path.abspath(video_path)}, f,
                  ensure_ascii=False, indent=2)

    logger.info("Đã nhập %d câu từ «%s» vào %s",
                len(cau), os.path.basename(phu_de_path), thu_muc)
    return KetQuaNhap(thu_muc=thu_muc, so_cau=len(cau), canh_bao=canh_bao)

"""Cắt một tệp âm thanh/video dài thành nhiều đoạn đều nhau (mini-spec C25).

Vì sao có tệp này: người dùng có một tệp `.m4a` dài **3 giờ 43 phút** và
không có phần mềm cắt nào trên máy. Nhưng ffmpeg thì app đã cần sẵn cho mọi
việc khác — nên "phải cài thêm phần mềm" là một câu trả lời sai.

Hai điều quyết định cách làm:

* **Chép lại luồng, KHÔNG mã hoá lại** (`-c copy`). Mã hoá lại một tệp 3 giờ
  mất hàng chục phút và làm giảm chất lượng âm thanh — trong khi việc cần làm
  chỉ là cắt. Chép luồng thì gần như tức thì và không mất một chút chất lượng
  nào.
* **Tên tệp mang MỐC BẮT ĐẦU**. Sau khi cắt, mốc thời gian trong mỗi bản chép
  lời chạy lại từ 0. Không nói ra thì người đọc tưởng câu ở phút 5 của phần 3
  là phút 5 của cả buổi. Tên `phan_03_tu_01-00-00` là chỗ duy nhất giữ được
  thông tin đó mà không phải sửa đường chép lời.
"""
from __future__ import annotations

import os
import re
import subprocess

from autodub.ffmpeg_deps import bao_dam_co_ffmpeg, duong_dan_ffmpeg
from autodub.utils import setup_logging

logger = setup_logging("autodub.media.cat_tep")

#: Độ dài mỗi đoạn mặc định. 30 phút là khoảng cân bằng: đủ ngắn để chạy lại
#: một đoạn hỏng không đau, đủ dài để không vụn thành hàng chục tệp.
PHUT_MAC_DINH = 30

_PHUT_TOI_THIEU = 1
_PHUT_TOI_DA = 120


def _mmss_ten(giay: int) -> str:
    """Mốc thời gian dùng trong TÊN TỆP — dấu hai chấm không đặt tên được."""
    phut, gy = divmod(int(giay), 60)
    gio, phut = divmod(phut, 60)
    return f"{gio:02d}-{phut:02d}-{gy:02d}"


def do_dai_giay(duong_dan: str) -> float:
    """Độ dài tệp, tính bằng giây. Trả 0.0 nếu không đọc được."""
    ffprobe = duong_dan_ffmpeg().replace("ffmpeg", "ffprobe")
    try:
        chay = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", duong_dan],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Không đọc được độ dài «{duong_dan}» ({e})")
        return 0.0
    try:
        return float((chay.stdout or "").strip())
    except ValueError:
        return 0.0


def cat_deu(duong_dan: str, thu_muc_ra: str = "", *,
            phut: int = PHUT_MAC_DINH, timeout: float = 1800.0) -> list[str]:
    """Cắt tệp thành các đoạn dài `phut` phút. Trả về danh sách đường dẫn.

    Tệp ngắn hơn một đoạn thì **trả về chính nó** — cắt một tệp 10 phút thành
    "một đoạn 10 phút" chỉ tạo thêm một bản sao vô ích.
    """
    if not os.path.isfile(duong_dan):
        raise FileNotFoundError(f"Không thấy tệp: {duong_dan}")
    if not _PHUT_TOI_THIEU <= phut <= _PHUT_TOI_DA:
        raise ValueError(
            f"Độ dài mỗi đoạn phải từ {_PHUT_TOI_THIEU} đến {_PHUT_TOI_DA} phút.")
    bao_dam_co_ffmpeg()

    tong = do_dai_giay(duong_dan)
    if tong and tong <= phut * 60:
        logger.info("Tệp ngắn hơn một đoạn — không cần cắt.")
        return [duong_dan]

    goc, duoi = os.path.splitext(os.path.basename(duong_dan))
    thu_muc_ra = thu_muc_ra or os.path.join(
        os.path.dirname(os.path.abspath(duong_dan)), f"{goc}_cat")
    os.makedirs(thu_muc_ra, exist_ok=True)

    # `%03d` là số thứ tự do ffmpeg điền; mốc bắt đầu điền sau, khi đổi tên —
    # ffmpeg không có chỗ điền "giây bắt đầu của đoạn này".
    mau = os.path.join(thu_muc_ra, f"{goc}_phan_%03d{duoi}")
    lenh = [
        duong_dan_ffmpeg(), "-y", "-i", duong_dan,
        "-f", "segment", "-segment_time", str(phut * 60),
        # Chép luồng: nhanh và không mất chất lượng. Mã hoá lại một tệp 3 giờ
        # mất hàng chục phút để đổi lấy một tệp xấu hơn.
        "-c", "copy",
        # Mỗi đoạn bắt đầu lại từ 0 — thiếu cờ này thì đoạn 2 mang mốc của
        # phút thứ 30 và nhiều trình phát tưởng tệp hỏng.
        "-reset_timestamps", "1",
        mau,
    ]
    try:
        chay = subprocess.run(lenh, capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"Không chạy được ffmpeg để cắt tệp: {e}") from e
    if chay.returncode != 0:
        duoi_loi = (chay.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError("Cắt tệp hỏng: " + " | ".join(duoi_loi))

    phan = sorted(
        os.path.join(thu_muc_ra, t) for t in os.listdir(thu_muc_ra)
        if re.fullmatch(rf"{re.escape(goc)}_phan_\d+{re.escape(duoi)}", t))
    if not phan:
        raise RuntimeError("ffmpeg chạy xong nhưng không có đoạn nào được tạo.")

    # Đổi tên để mang MỐC BẮT ĐẦU — xem docstring đầu tệp.
    ra: list[str] = []
    for i, cu in enumerate(phan):
        moc = _mmss_ten(i * phut * 60)
        moi = os.path.join(thu_muc_ra, f"{goc}_phan_{i + 1:02d}_tu_{moc}{duoi}")
        try:
            os.replace(cu, moi)
        except OSError as e:
            logger.warning(f"Không đổi được tên «{cu}» ({e})")
            moi = cu
        ra.append(moi)
    logger.info(f"Đã cắt thành {len(ra)} đoạn ở «{thu_muc_ra}».")
    return ra

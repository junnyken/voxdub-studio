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
            phut: int = PHUT_MAC_DINH, theo_khoang_lang: bool = True,
            timeout: float = 1800.0) -> list[str]:
    """Cắt tệp thành các đoạn khoảng `phut` phút. Trả về danh sách đường dẫn.

    `theo_khoang_lang=True` (mặc định) dò các quãng im rồi **nắn mốc cắt về
    quãng im gần nhất** trong khoảng ±90 giây. Cắt đều tăm tắp thì mỗi ranh
    giới rơi vào giữa một câu — với tệp 3 giờ 43 cắt 8 đoạn là 7 câu bị chia
    đôi, và một câu bị chia đôi là một câu SAI ở cả hai bản chép lời.

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
    # Mốc cắt: nắn về khoảng lặng nếu dò được, còn không thì cắt đều.
    moc_cat: list[float] = []
    if theo_khoang_lang:
        moc_cat = chon_moc_cat(tong or 0.0, phut,
                               tim_khoang_lang(duong_dan, timeout=timeout))
    if moc_cat:
        cat_theo = ["-segment_times",
                    ",".join(f"{g:.3f}" for g in moc_cat)]
    else:
        cat_theo = ["-segment_time", str(phut * 60)]

    mau = os.path.join(thu_muc_ra, f"{goc}_phan_%03d{duoi}")
    lenh = [
        duong_dan_ffmpeg(), "-y", "-i", duong_dan,
        "-f", "segment", *cat_theo,
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
    # Mốc bắt đầu THẬT của từng đoạn. Suy ra từ `số thứ tự × độ dài đoạn` là
    # sai ngay khi mốc đã được nắn về khoảng lặng.
    bat_dau = [0.0] + list(moc_cat) if moc_cat else \
        [i * phut * 60 for i in range(len(phan))]

    ra: list[str] = []
    for i, cu in enumerate(phan):
        moc = _mmss_ten(bat_dau[i] if i < len(bat_dau) else i * phut * 60)
        moi = os.path.join(thu_muc_ra, f"{goc}_phan_{i + 1:02d}_tu_{moc}{duoi}")
        try:
            os.replace(cu, moi)
        except OSError as e:
            logger.warning(f"Không đổi được tên «{cu}» ({e})")
            moi = cu
        ra.append(moi)
    logger.info(f"Đã cắt thành {len(ra)} đoạn ở «{thu_muc_ra}».")
    return ra

#: Tìm khoảng lặng trong khoảng ± bao nhiêu giây quanh mốc cắt mong muốn.
#: 90 giây: đủ rộng để gần như luôn có một quãng nghỉ, đủ hẹp để các đoạn
#: không lệch nhau quá nhiều về độ dài.
_SAI_SO_GIAY = 90

#: Ngưỡng coi là "im". -30 dB bắt được quãng nghỉ giữa câu của người giảng
#: bài trong phòng có tiếng ồn nền nhẹ; im tuyệt đối thì gần như không có.
_NGUONG_DB = -30
_IM_TOI_THIEU_S = 0.6


def tim_vung_lang(duong_dan: str, timeout: float = 1800.0
                  ) -> list[tuple[float, float]]:
    """Các VÙNG im, trả về (bắt đầu, kết thúc) tính bằng giây.

    Khác `tim_khoang_lang` (chỉ trả điểm giữa để cắt tệp): ở đây cần cả khoảng
    để trả lời câu hỏi "câu này có nằm trong chỗ im không" — dùng để phát hiện
    câu do mô hình BỊA ra (mini-spec C29).
    """
    import re as _re

    lenh = [duong_dan_ffmpeg(), "-i", duong_dan, "-af",
            f"silencedetect=noise={_NGUONG_DB}dB:d={_IM_TOI_THIEU_S}",
            "-f", "null", "-"]
    try:
        chay = subprocess.run(lenh, capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Không dò được vùng im ({e})")
        return []

    vung: list[tuple[float, float]] = []
    dau = None
    for dong in (chay.stderr or "").splitlines():
        m = _re.search(r"silence_start:\s*(-?[\d.]+)", dong)
        if m:
            dau = float(m.group(1))
            continue
        m = _re.search(r"silence_end:\s*(-?[\d.]+)", dong)
        if m and dau is not None:
            vung.append((dau, float(m.group(1))))
            dau = None
    return vung


def tim_khoang_lang(duong_dan: str, timeout: float = 1800.0) -> list[float]:
    """Các mốc (giây) mà âm thanh im — dùng làm chỗ cắt.

    Trả về giữa mỗi quãng im: cắt ngay lúc bắt đầu im thì chữ cuối câu trước
    dễ bị hụt đuôi, cắt lúc hết im thì chữ đầu câu sau dễ mất.
    """
    lenh = [duong_dan_ffmpeg(), "-i", duong_dan, "-af",
            f"silencedetect=noise={_NGUONG_DB}dB:d={_IM_TOI_THIEU_S}",
            "-f", "null", "-"]
    try:
        chay = subprocess.run(lenh, capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Không dò được khoảng lặng ({e})")
        return []

    moc: list[float] = []
    bat_dau = None
    for dong in (chay.stderr or "").splitlines():
        m = re.search(r"silence_start:\s*(-?[\d.]+)", dong)
        if m:
            bat_dau = float(m.group(1))
            continue
        m = re.search(r"silence_end:\s*(-?[\d.]+)", dong)
        if m and bat_dau is not None:
            ket = float(m.group(1))
            moc.append(round((bat_dau + ket) / 2, 3))
            bat_dau = None
    return moc


def chon_moc_cat(tong_giay: float, phut: int,
                 khoang_lang: list[float]) -> list[float]:
    """Chọn các mốc cắt: bám mốc đều, nhưng NẮN về khoảng lặng gần nhất.

    Không có khoảng lặng nào đủ gần thì giữ nguyên mốc đều — thà cắt giữa câu
    còn hơn để một đoạn dài gấp đôi các đoạn khác.
    """
    buoc = phut * 60
    ra: list[float] = []
    moc = buoc
    while moc < tong_giay - 1:
        gan = [g for g in khoang_lang if abs(g - moc) <= _SAI_SO_GIAY
               and g > (ra[-1] if ra else 0) + 5]
        ra.append(min(gan, key=lambda g: abs(g - moc)) if gan else float(moc))
        moc += buoc
    return ra

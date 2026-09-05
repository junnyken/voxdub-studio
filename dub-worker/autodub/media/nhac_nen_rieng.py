"""Nhạc nền do người dùng tự chọn (mini-spec C42).

Trước đây chỉ có ba nguồn nhạc nền: giữ nhạc gốc (Demucs), giảm nhỏ tiếng gốc,
hoặc nhạc do AI sinh. Không có đường nào đưa **tệp nhạc của chính người dùng**
vào — họ phải xuất video rồi ghép nhạc ở phần mềm khác.

Chủ dự án hỏi thẳng khi nhìn thanh thời gian (27/08/2026): *"ở đây tôi muốn
kéo thêm âm thanh này kia vô được không"*. Câu trả lời lúc đó là không.

Cách làm bám đúng lối đã có: KHÔNG dựng lớp âm thanh mới trên thanh thời gian
(việc đó lớn hơn nhiều, để sau). Bước trộn nhạc nền đã nhận một tệp bất kỳ rồi
tự đệm/cắt cho khớp độ dài video — nên chỉ cần chuyển tệp người dùng chọn
thành WAV chuẩn trong thư mục dự án, và thêm một chế độ nhạc nền trỏ vào đó.

Chuyển sang WAV chứ không dùng thẳng tệp gốc: mp3/m4a/flac đều nhận được đầu
vào, nhưng bước trộn chạy lại nhiều lần (mỗi lần xuất video), giải mã lại mỗi
lượt là phí; và tệp gốc có thể bị người dùng xoá hoặc đổi chỗ giữa hai lần
xuất, lúc đó dự án mất nhạc mà không rõ vì sao.
"""
from __future__ import annotations

import os
import subprocess

from autodub.utils import setup_logging
from autodub.workdir import data_path

logger = setup_logging("autodub.nhac_nen_rieng")

#: Tên cố định trong thư mục dự án — cùng lối với `no_vocals.wav`,
#: `ai_music.wav`: chế độ nhạc nền tra theo TÊN, không giữ đường dẫn ngoài.
TEN_TEP = "nhac_nen_rieng.wav"

#: Đuôi tệp nhận vào. Danh sách đóng để câu báo lỗi nói được tên cụ thể thay
#: vì để ffmpeg trả về một dòng khó hiểu.
DUOI_NHAN = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma")


class LoiNhacNen(Exception):
    """Không dùng được tệp người dùng chọn — kèm lý do đọc được."""


def duong_nhac_nen(work_dir: str) -> str:
    """Đường dẫn nhạc nền riêng của dự án, hoặc "" nếu chưa đặt."""
    duong = data_path(work_dir, TEN_TEP)
    return duong if os.path.isfile(duong) else ""


def dat_nhac_nen(work_dir: str, nguon: str, *, timeout: int = 300) -> str:
    """Chuyển tệp người dùng chọn thành nhạc nền của dự án. Trả về đường dẫn.

    Ghi đè bản cũ nếu có — người dùng chọn tệp khác nghĩa là đổi ý.
    """
    if not nguon or not os.path.isfile(nguon):
        raise LoiNhacNen(f"Không thấy tệp: {nguon}")
    duoi = os.path.splitext(nguon)[1].lower()
    if duoi not in DUOI_NHAN:
        raise LoiNhacNen(
            f"Chưa nhận tệp «{duoi}». Dùng một trong: "
            + ", ".join(DUOI_NHAN) + ".")

    ra = data_path(work_dir, TEN_TEP, create_dir=True)
    tam = ra + ".tmp.wav"
    lenh = ["ffmpeg", "-y", "-i", nguon,
            # 44.1 kHz stereo — khớp đường nhạc nền chất lượng cao của bộ trộn.
            "-ar", "44100", "-ac", "2", "-acodec", "pcm_s16le", tam]
    try:
        ket = subprocess.run(lenh, capture_output=True, text=True,
                             timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise LoiNhacNen(f"Không đọc được tệp nhạc: {e}") from e
    if ket.returncode != 0 or not os.path.isfile(tam):
        # Lấy dòng cuối của ffmpeg — dòng đó nói lý do thật.
        vet = (ket.stderr or "").strip().splitlines()
        raise LoiNhacNen(
            "Không chuyển được tệp nhạc sang dạng dùng được"
            + (f": {vet[-1]}" if vet else "."))

    # Đổi tên ở bước cuối: hỏng giữa chừng thì bản cũ còn nguyên, không để
    # dự án rơi vào trạng thái có tệp nhạc rỗng.
    os.replace(tam, ra)
    logger.info("Đã đặt nhạc nền riêng cho dự án: %s → %s",
                os.path.basename(nguon), ra)
    return ra


def xoa_nhac_nen(work_dir: str) -> bool:
    """Bỏ nhạc nền riêng. Trả về True nếu có tệp để xoá."""
    duong = duong_nhac_nen(work_dir)
    if not duong:
        return False
    try:
        os.remove(duong)
    except OSError as e:
        logger.warning("Không xoá được nhạc nền riêng (%s)", e)
        return False
    return True

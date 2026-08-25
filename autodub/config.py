"""Cấu hình ứng dụng — đọc từ biến môi trường / tệp ``.env``.

An toàn với giao diện: nạp module này (hay gọi ``Settings.load()``) không bao
giờ làm thoát tiến trình. API Key chỉ được kiểm tra vào lúc một bước thật
sự cần tới, qua :meth:`Settings.require`, và lỗi thiếu cấu hình là
:class:`ConfigError` để giao diện bắt và hiển thị tử tế.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from autodub.utils import app_root


class ConfigError(Exception):
    """Ném ra khi một mục cấu hình bắt buộc còn trống ngay lúc cần dùng."""


def _auto_vieneu_workers() -> int:
    """Số tiến trình giọng đọc mặc định — theo RAM trống và số nhân CPU.

    Mỗi tiến trình VieNeu chiếm ~1.5 GB RAM. Máy 8 GB mà chạy 3 tiến trình
    (4.5 GB) cộng Demucs + giao diện là tràn bộ nhớ, hệ điều hành swap và
    MỌI THỨ chậm đi — 3 luồng lúc đó còn chậm hơn 1 luồng. VIENEU_MAX_WORKERS
    trong .env khai báo tường minh luôn thắng giá trị tự tính này.
    """
    from autodub.sysinfo import available_ram_gb

    cores = os.cpu_count() or 4
    by_cpu = max(1, cores // 2)

    avail = available_ram_gb()
    # ~1.5 GB/tiến trình, chừa ~3 GB cho giao diện + Demucs + hệ điều hành.
    # Công thức này giữ nguyên số luồng của máy 6-10 GB như trước, nhưng máy
    # khỏe (24-32 GB, nhiều nhân) không còn bị kẹp ở 3 nữa — TTS là bước lâu
    # nhất nên trần thấp làm mất phần lớn hiệu năng sẵn có.
    if avail is None:          # không đọc được RAM — giữ mặc định an toàn
        by_ram = 3
    else:
        by_ram = max(1, int((avail - 3.0) // 1.5))

    workers = max(1, min(_VIENEU_WORKER_CEILING, by_ram, by_cpu))
    if workers < _VIENEU_WORKER_CEILING:
        _log_governor_once(workers, avail, cores)
    return workers


#: Trần cho số tiến trình giọng đọc tự tính. Trên mức này lợi ích giảm nhanh
#: (tranh nhân CPU giữa các tiến trình ONNX) mà RAM vẫn tăng tuyến tính.
_VIENEU_WORKER_CEILING = 6


_governor_logged = False


def _log_governor_once(workers: int, avail: float | None, cores: int) -> None:
    """Báo MỘT lần mỗi phiên khi tự hạ số luồng giọng đọc (tránh spam log
    vì Settings.load() được giao diện gọi lại mỗi lần lưu cài đặt)."""
    global _governor_logged
    if _governor_logged:
        return
    _governor_logged = True
    from autodub.utils import setup_logging

    ram_txt = f"{avail:.1f} GB RAM trống" if avail is not None else "RAM không rõ"
    setup_logging("autodub.config").info(
        f"Máy này ({ram_txt}, {cores} nhân) — chạy {workers} luồng giọng đọc "
        f"để không tràn bộ nhớ. Đặt VIENEU_MAX_WORKERS trong .env nếu muốn khác."
    )




def _one_of(value: str, allowed: tuple[str, ...], default: str) -> str:
    """Chuẩn hóa một mục kiểu danh sách, sai chính tả thì lấy giá trị mặc định.

    Gõ nhầm trong .env không được phép làm sập giao diện, nên hàm này dễ tính.
    """
    v = value.strip().lower()
    return v if v in allowed else default


# Mức chất lượng — MỘT nút vặn (QUALITY_PRESET) đặt sẵn giá trị mặc định cho
# các mục chi tiết bên dưới. Biến môi trường khai báo tường minh luôn thắng.
_PRESETS: dict[str, dict[str, str]] = {
    # Nhanh: ưu tiên tốc độ, chấp nhận chất lượng thấp hơn.
    "fast": {
        "whisper_model": "medium",
        "hq_background": "false",
        "translate_analysis": "false",
        "translate_review": "false",
        "karaoke_alignment": "false",
    },
    # Cân bằng (mặc định): mọi cải tiến chất lượng chính, chi phí vừa phải.
    "balanced": {
        "whisper_model": "auto",
        "hq_background": "true",
        "translate_analysis": "true",
        "translate_review": "true",
        "karaoke_alignment": "true",
    },
    # Chất lượng cao: chấp nhận chậm — ASR lớn, đủ mọi lượt kiểm tra.
    "quality": {
        "whisper_model": "auto",
        "hq_background": "true",
        "translate_analysis": "true",
        "translate_review": "true",
        "karaoke_alignment": "true",
    },
}

@dataclass
class Settings:
    # Mức chất lượng: một nút vặn đặt mặc định hợp lý cho các mục chi tiết
    # ("fast" | "balanced" | "quality"). Biến môi trường riêng vẫn ghi đè.
    quality_preset: str = "balanced"

    # --- Nghe và chép lời (ASR) -------------------------------------------
    # Whisper chạy trên máy, miễn phí. Model lớn hơn = đúng hơn nhưng chậm hơn.
    # "auto" = large-v3 khi có CUDA, medium khi chỉ có CPU.
    whisper_model: str = "auto"
    # Bộ nhận dạng: "whisper" (mặc định, mọi ngôn ngữ) | "paraformer" (chuyên
    # tiếng Trung, chạy CPU/ONNX trong .venv-asr — cài bằng
    # scripts/setup_paraformer.py; tự quay về Whisper khi chưa cài).
    asr_engine: str = "whisper"
    asr_venv_python: str = ""       # mặc định: <app>/.venv-asr/Scripts/python.exe
    paraformer_model_dir: str = ""  # mặc định: <app>/models/paraformer-zh

    # mini-spec V26 (docs/PLAN.md, Phase G) — diarization đa giọng nói, TUỲ
    # CHỌN (mặc định TẮT, cài qua scripts/setup_diarization.py giống
    # Paraformer) — venv riêng .venv-diar (pyannote.audio + torch), không
    # đóng gói mặc định.
    # mini-spec V67 — cookie cho yt-dlp. Video giới hạn (Facebook riêng tư,
    # YouTube tuổi/thành viên, TikTok vài vùng) đòi đăng nhập; không có cookie
    # thì yt-dlp chỉ báo lỗi chung chung và người dùng không biết đường xử lý.
    #
    # Đo 18-08: reel Facebook CÔNG KHAI tải được mà KHÔNG cần cookie — nên đây
    # là đường lui khi gặp lỗi, không phải thứ bắt buộc cấu hình trước.
    #
    # `cookies_file`: file Netscape cookies.txt xuất từ extension trình duyệt.
    # `cookies_from_browser`: tên trình duyệt để yt-dlp tự đọc (chrome, edge,
    # firefox...). Điền cả hai thì FILE thắng — đường tường minh thắng đường
    # tự đoán, và người vừa xuất file ra là người đang cố sửa một lỗi cụ thể.
    cookies_file: str = ""
    cookies_from_browser: str = ""

    diarization_enabled: bool = False
    diarization_venv_python: str = ""  # mặc định: <app>/.venv-diar/Scripts/python.exe
    diarization_model_dir: str = ""    # mặc định: <app>/models/diarization
    # mini-spec V65b — số người nói NGƯỜI DÙNG khai cho video này. `0` = không
    # biết, pyannote tự đoán y như trước. Đo thật 18-08: 3 giọng nữ trong cùng
    # một file bị GỘP thành một người nói, và tầng hồ sơ nhân vật không sửa
    # nổi vì nó chỉ nhìn thấy một người. Người dùng thì biết chắc video của
    # mình có mấy người — đây là thông tin rẻ nhất và đáng tin nhất.
    speaker_count: int = 0

    # mini-spec V32b (docs/PLAN.md, Phase G) — "Đồng bộ khẩu hình" (MuseTalk),
    # NGOẠI LỆ KIẾN TRÚC ĐẦU TIÊN so với "GPU-optional" của mọi tính năng khác
    # (chốt chính sách 2026-08-12) — venv riêng .venv-lipsync (GPU-only, cài
    # qua scripts/setup_lipsync.py), mặc định TẮT, không đóng gói mặc định.
    # Bật/tắt là lựa chọn TỪNG VIDEO (DubRequest.lipsync), không phải cấu
    # hình toàn app — đúng cách subtitle_mode/blur_regions đã làm, không
    # phải kiểu diarization_enabled (bật 1 lần áp cho mọi video sau đó).
    # Phạm vi hiện tại CHỈ đúng những gì V32a đã benchmark thật (1 khuôn mặt,
    # video ngắn) — xem docs/TEST_LOG.md mục V32a/V32b trước khi nới rộng.
    lipsync_venv_python: str = ""      # mặc định: <app>/.venv-lipsync/Scripts/python.exe
    lipsync_model_dir: str = ""        # mặc định: <app>/models/lipsync
    # Ngưỡng cấu hình CHỦ ĐÍCH BẢO THỦ (đúng nguyên tắc quality_gate_*): mẫu
    # DUY NHẤT đã benchmark thành công thật (V32a) dài 10.7s, VRAM đỉnh 96%
    # trên card 4GB — KHÔNG có số liệu cho video dài hơn, nên trần mặc định
    # chỉ nhỉnh hơn chút, không đoán xa. Chủ dự án tự nới sau khi tự benchmark
    # thêm trên phần cứng của mình.
    lipsync_max_duration_s: float = 12.0
    # Consent-check (Constraint 3 của V32b): tỷ lệ frame KHÔNG phát hiện được
    # khuôn mặt phải bằng 0 mới cho qua — mẫu THÀNH CÔNG duy nhất đã có
    # (V32a) đạt đúng 0% (268/268 frame); CHƯA có số liệu về khuôn mặt góc
    # nghiêng/nhiều người nên không nới ngưỡng này lên trên 0.
    lipsync_max_no_face_ratio: float = 0.0

    # mini-spec V28 (docs/PLAN.md, Phase G) — giọng đọc tự đổi giọng điệu
    # theo cảm xúc từng câu (chỉ áp cho VieNeu, xem Constraint 4). Mặc định
    # TẮT. Đường tín hiệu THẬT ở đợt này CHỈ có heuristic văn bản local
    # (autodub/text/tone_heuristic.py) — đường LLM/SaaS (buildAnalysisPrompt
    # per-segment) CHƯA nối, xem "Remaining Limits" mục V28 trong
    # docs/TEST_LOG.md.
    emotion_voice_enabled: bool = False
    asr_num_threads: int = 4
    # Beam size của Whisper (1–10). 5 là mặc định của thư viện — giữ nguyên
    # chất lượng. Máy CPU yếu có thể hạ (vd 1) để nhanh gấp 2–3 lần, đổi lại
    # kém chính xác hơn một chút — đây là lựa chọn CHỦ ĐỘNG, không tự hạ.
    whisper_beam_size: int = 5
    # Whisper chạy trong venv riêng (.venv-whisper) khi đã cài
    # scripts/setup_whisper.py — faster-whisper + ctranslate2 không cần bundle
    # trong exe, giảm ~112 MB. Khi venv chưa có, app tự dùng faster-whisper
    # đã cài trong môi trường hiện tại (dev) hoặc báo lỗi nếu thiếu (exe).
    whisper_venv_python: str = ""   # mặc định: <app>/.venv-whisper/Scripts/python.exe
    whisper_model_dir: str = ""     # mặc định: <app>/models/whisper (cache HuggingFace)

    # --- Giọng đọc tiếng Việt (VieNeu — bộ giọng DUY NHẤT) -----------------
    # Chạy trong venv riêng (.venv-vieneu) qua tiến trình con — cài một lần
    # bằng scripts/setup_vieneu.py. Chạy CPU/ONNX nên không tốn VRAM và không
    # tranh card đồ họa với Whisper/Demucs.
    vieneu_venv_python: str = ""   # mặc định: <app>/.venv-vieneu/Scripts/python.exe
    vieneu_model_dir: str = ""     # mặc định: <app>/models/vieneu
    #: Tên giọng mặc định cho dự án mới (xem autodub.speech.tts.voices).
    vieneu_voice: str = ""
    vieneu_style: str = "tu_nhien"   # "tu_nhien" | "tin_tuc" | "doc_truyen"
    # Số tiến trình con chạy song song (~1.5 GB RAM mỗi cái). Chạy trên CPU
    # nên tăng số luồng là nhanh lên gần như tuyến tính, tới khi hết nhân.
    vieneu_max_workers: int = 3

    # Hiệu năng: số luồng cho các bước nặng (gửi việc cho bộ giọng, nhóm
    # ffmpeg atempo, dịch qua mạng). Tự tính theo CPU lúc nạp cấu hình;
    # PARALLEL_WORKERS trong .env là lối thoát hiểm cho người biết việc.
    parallel_workers: int = 4

    # HAI nút vặn thời lượng — không tự căn, không cắt, không nén từng câu.
    # Giọng luôn đọc ở voice_speed; video luôn chạy ở video_speed. Tiếng Việt
    # dài hơn tiếng Trung khoảng 20% nên VIDEO_SPEED≈0.82 cho bản lồng tiếng
    # đủ chỗ thở. Còn chồng tiếng thì hạ video_speed (hoặc tăng voice_speed)
    # rồi chạy lại — giọng đọc đã có sẵn nên chạy lại rất nhanh.
    video_speed: float = 1.0    # 1.0 = giữ nguyên; 0.82 = video dài thêm 22%
    voice_speed: float = 1.0    # áp cố định cho mọi câu (0.5–2.0)

    # Ngân sách dịch (số ký tự trên mỗi giây khung thời gian). Số nhỏ hơn ép
    # bản dịch ngắn lại nên ít tràn hơn.
    translate_cps_budget: float = 12.5

    # --- Chất lượng âm thanh ----------------------------------------------
    # Nhạc nền chất lượng cao: rút thêm original_audio_hq.wav 44.1 kHz stereo
    # riêng cho Demucs + bản trộn cuối (bản 16 kHz mono chỉ dành cho ASR).
    hq_background: bool = True
    # Chuẩn hóa âm lượng + fade từng câu (EBU R128 loudnorm, highpass 80 Hz,
    # fade 15 ms). Tắt = giữ nguyên bản thô từ bộ giọng.
    voice_postprocess: bool = True
    voice_target_lufs: float = -16.0
    # Nhạc nền tự nhỏ đi khi có giọng và hồi lại ở khoảng lặng. 0 = tắt.
    bg_duck_voice_db: float = -7.0
    # Chống chồng tiếng "mềm": câu dài hơn khung thì DỒN TRỄ các câu sau vào
    # khoảng lặng kế tiếp (có trần tổng), tuyệt đối không đổi tốc độ đọc từng
    # câu. Chỉ khi kịch trần mới nén nhẹ và đều, với trần thấp.
    soft_timing_fit: bool = True
    timing_max_drift_s: float = 1.5     # trần dồn trễ tích lũy
    timing_min_gap_s: float = 0.12      # khoảng thở tối thiểu giữa hai câu
    timing_max_atempo: float = 1.1      # trần nén bất khả kháng (mỗi câu)

    # mini-spec V23 (docs/PLAN.md, Phase F) — cổng chất lượng tự động đọc
    # quality_report.json (đã có sẵn từ trước, không tính lại số liệu).
    # Ngưỡng mặc định CHỦ ĐÍCH bảo thủ (thà báo "cần xem lại" oan còn hơn bỏ
    # sót video lỗi thật) vì dự án CHƯA có dữ liệu thật để hiệu chỉnh trên
    # quy mô lớn — xem "Remaining Limits" mục V23 trong docs/TEST_LOG.md.
    quality_gate_max_over_budget_ratio: float = 0.15
    quality_gate_max_speed_fallback_ratio: float = 0.10
    quality_gate_max_postprocess_fallback_ratio: float = 0.10
    # Thấp hơn timing_max_drift_s (trần cứng của timing engine) có chủ đích:
    # 1 câu áp sát trần đã là dấu hiệu video này bị nén nhiều, đáng xem lại,
    # dù timing engine không coi đó là lỗi (vẫn nằm trong trần cho phép).
    quality_gate_max_shift_s: float = 1.0

    # --- Ngữ cảnh dịch do người dùng cung cấp (đều không bắt buộc) ---------
    translate_domain: str = ""       # chủ đề, vd "review công nghệ"
    translate_context: str = ""      # mô tả tự do (nhiều dòng)
    translate_pronouns: str = ""     # quy ước xưng hô, vd "mình – các bạn"
    translate_glossary: str = ""     # thuật ngữ cố định, mỗi dòng "gốc = dịch"
    translate_style_notes: str = ""  # yêu cầu thêm về giọng văn
    # Tiêu đề video gốc — KHÔNG nạp từ .env: pipeline tự bơm mỗi lượt chạy
    # (đọc data/video_meta.json do downloader ghi) vào bản sao Settings để
    # prompt dịch/phân tích biết video nói về gì ngay từ tiêu đề.
    translate_video_title: str = ""

    # --- Dịch hai lượt ----------------------------------------------------
    # Lượt 0 "hiểu video": trước khi dịch, gửi toàn bộ lời thoại gốc để rút ra
    # tóm tắt + nhân vật/xưng hô + thuật ngữ, rồi tự bơm vào ngữ cảnh dịch
    # (mục người dùng điền tay luôn được ưu tiên hơn).
    translate_analysis: bool = True
    # Lượt rà soát: sau khi dịch, soát các câu nghi vấn (vượt ngân sách nhiều,
    # còn ký tự CJK, quá ngắn so với câu gốc) rồi dịch lại đúng các câu đó.
    translate_review: bool = True

    # --- Chung ------------------------------------------------------------
    default_source_lang: str = "zh-CN"
    audio_sample_rate: int = 16000
    output_dir: str = "./output"
    vietnamese_output_dir: str = ""
    # Tự dọn tệp trung gian ngay khi xuất video xong. Tắt mặc định vì dọn
    # rồi thì không sửa từng câu hay xuất lại dự án đó được nữa.
    auto_clean_intermediates: bool = False

    # --- Cập nhật và hỗ trợ -----------------------------------------------
    # Kho GitHub chứa bản phát hành (dạng "chủ/kho") — dùng để báo bản mới.
    update_repo: str = "junnyken/voxdub-studio"
    # Đường dẫn biểu mẫu nhận báo lỗi và góp ý từ người dùng.
    support_url: str = "https://github.com/junnyken/voxdub-studio/issues"

    # Liên kết video mặc định (dùng khi giao diện/chạy hàng loạt không đưa nguồn)
    video_url: str = ""

    # --- Nội dung đăng bài ------------------------------------------------
    # Tạo tiêu đề/mô tả/hashtag sau mỗi lần lồng tiếng (máy chủ viết).
    # Tắt = bỏ hẳn bước này (và không tốn Vox).
    generate_metadata: bool = True

    # --- Dịch tự động -----------------------------------------------------
    # Mô hình, lời nhắc và API key đều nằm trên máy chủ VoxDub — app chỉ gửi
    # câu thoại và ngữ cảnh. Hai nút vặn dưới đây là thứ duy nhất còn lại ở
    # phía máy khách vì chúng quyết định cách CHIA VIỆC, không phải cách dịch.
    translate_enabled: bool = True
    # Số câu mỗi lượt gửi lên máy chủ (trần cứng phía máy chủ là 120).
    translate_batch_size: int = 40
    # Mini-spec V6 (docs/PLAN.md) — đường dịch thứ 3: KHÔNG cần máy chủ, chạy
    # local/offline (ctranslate2 + NLLB-200-distilled, CPU). Chỉ dùng khi
    # KHÔNG có máy chủ nào cấu hình (is_configured()==False) — có máy chủ
    # thì đường B (chất lượng cao hơn, 3-pass) luôn được ưu tiên trước,
    # path C không thay thế nó.
    # Mặc định BẬT theo quyết định chủ dự án (2026-08-10, xem docs/TEST_LOG.md
    # mục V6): model NLLB-200 có giấy phép CC-BY-NC-4.0, dự án hiện CHƯA
    # thương mại hoá tính năng này nên chấp nhận được — cần xem lại quyết
    # định này nếu sau này tính phí trực tiếp cho bản dịch. Chất lượng thấp
    # hơn dịch tay/SaaS, đặc biệt câu ngắn — xem cảnh báo trong GUI trang
    # Dịch thuật (do BA duyệt câu chữ cuối cùng, theo BA⇄DEV convention).
    translate_local_enabled: bool = True

    # Gộp mẩu vụn thành câu TRƯỚC bước dịch (mini-spec V97). Bộ nghe cắt theo
    # khoảng lặng 500ms nên một câu liền mạch có thể vỡ thành hàng chục mẩu
    # một-hai chữ; máy chủ tính tiền theo SỐ DÒNG nên mỗi mẩu là một lần trả
    # tiền. BẬT mặc định: gộp vừa rẻ hơn vừa cho giọng đọc liền mạch hơn,
    # người dùng nào muốn giữ đúng từng mẩu của bộ nghe thì tắt đi.
    gop_cau_truoc_khi_dich: bool = True

    # Mini-spec V9 → V12 (docs/PLAN.md) — tách nhạc nền (Demucs) trên cloud
    # thay vì trên máy. Chỉ có nghĩa ở chế độ SaaS (is_configured()==True,
    # xem autodub.cloud_render.is_available) — TẮT mặc định, khác
    # translate_local_enabled: đây là tính năng TỐN VOX mỗi lượt, không nên
    # tự bật cho người dùng chưa chọn.
    cloud_render_enabled: bool = False

    # --- Phụ đề -----------------------------------------------------------
    # Kiểu mặc định: "none" | "soft" (tệp rời) | "burn" (ghi thẳng vào hình)
    subtitle_mode: str = "none"
    #: Bộ kiểu chữ dựng sẵn (xem autodub.media.subtitle.PRESETS).
    subtitle_preset: str = "clean"
    subtitle_position: str = "bottom"   # "bottom" | "middle" | "top"
    subtitle_font: str = "Arial"
    subtitle_font_size: int = 22
    subtitle_margin_v: int = 40         # khoảng cách tới mép (điểm ảnh ASS)
    subtitle_outline: int = 2           # độ dày viền chữ
    subtitle_shadow: int = 0            # độ đổ bóng
    subtitle_bold: bool = True
    subtitle_color: str = "#FFFFFF"
    subtitle_outline_color: str = "#000000"
    # Nền sau chữ: "none" (chỉ viền) | "box" (khối nền đặc kiểu CapCut)
    subtitle_box: str = "none"
    subtitle_box_color: str = "#000000"
    subtitle_box_opacity: int = 60      # 0–100, chỉ có nghĩa khi box = "box"
    # Số CHỮ mỗi hàng do người dùng chốt. 0 = tự xuống dòng theo bề rộng chuẩn.
    subtitle_line_words: int = 0
    subtitle_max_lines: int = 2
    subtitle_all_caps: bool = False

    # --- Phụ đề theo cụm chữ (nhảy theo giọng đọc, chỉ chế độ ghi vào hình) -
    # "sentence" (cả câu) | "karaoke" (cụm chữ .ass)
    subtitle_display: str = "sentence"
    karaoke_words_per_cue: int = 3      # 1-5 chữ mỗi cụm
    karaoke_effect: str = "pop"         # "pop" | "fade" | "karaoke" | "none"
    karaoke_highlight_color: str = "#FFD54A"
    # Khớp mốc chữ THẬT bằng Whisper nghe lại giọng đọc (~30-60s/video).
    # Tắt = ước lượng theo âm tiết (nhanh, kém chính xác hơn một chút).
    karaoke_alignment: bool = True

    # ------------------------------------------------------------------ #

    @classmethod
    def load(cls, env_file: str | None = None, override: bool = False) -> "Settings":
        """Dựng Settings từ môi trường (sau khi nạp ``.env``).

        ``override=True`` đọc lại .env đè lên biến môi trường đã đặt — giao
        diện dùng để nạp nóng cài đặt ngay sau khi lưu tệp.
        """
        if env_file:
            load_dotenv(env_file, override=override)
        else:
            # Luôn là tệp .env nằm cạnh ứng dụng (thư mục chứa exe khi đã
            # đóng gói) — không phụ thuộc thư mục người dùng đang đứng.
            tep = os.path.join(app_root(), ".env")
            if not os.path.isfile(tep):
                # Bản mới giải nén cạnh bản cũ: mượn cài đặt của bản cũ thay
                # vì bắt khai báo lại khoá API và token từ đầu (V96).
                from autodub.venv_discovery import tim_env_cu

                tep = tim_env_cu() or tep
            load_dotenv(tep, override=override)

        def env(key: str, default: str = "", *aliases: str) -> str:
            for k in (key, *aliases):
                value = os.environ.get(k)
                if value is not None:
                    return value
            return default

        def env_int(key: str, default: str) -> int:
            try:
                return int(float(env(key, default)))
            except ValueError:
                return int(float(default))

        def env_float(key: str, default: str) -> float:
            try:
                return float(env(key, default))
            except ValueError:
                return float(default)

        def env_dir(key: str, default: str) -> str:
            """Mục thư mục; đường dẫn tương đối neo vào thư mục ứng dụng."""
            value = env(key, default).strip()
            if value and not os.path.isabs(value):
                value = os.path.normpath(os.path.join(app_root(), value))
            return value

        def env_multiline(key: str) -> str:
            """Mục nhiều dòng, lưu trên một dòng .env với ký tự \\n."""
            return env(key).replace("\\n", "\n").strip()

        def env_bool(key: str, default: str) -> bool:
            return env(key, default).strip().lower() in ("1", "true", "yes")

        # Mức chất lượng: nền mặc định cho các mục chi tiết. Biến môi trường
        # tường minh vẫn thắng (env() đọc chúng trước khi dùng tới preset).
        preset = _one_of(env("QUALITY_PRESET", "balanced"),
                         ("fast", "balanced", "quality"), "balanced")
        _p = _PRESETS[preset]

        # Tự tính số luồng theo CPU: một nửa số nhân logic, kẹp trong 2–8.
        auto_workers = str(min(8, max(2, (os.cpu_count() or 4) // 2)))

        return cls(
            quality_preset=preset,
            whisper_model=env("WHISPER_MODEL", _p["whisper_model"]),
            asr_engine=_one_of(env("ASR_ENGINE", "whisper"),
                               ("whisper", "paraformer"), "whisper"),
            asr_venv_python=env("ASR_VENV_PYTHON"),
            paraformer_model_dir=env("PARAFORMER_MODEL_DIR"),
            cookies_file=env("COOKIES_FILE", ""),
            cookies_from_browser=env("COOKIES_FROM_BROWSER", ""),
            diarization_enabled=env_bool("DIARIZATION_ENABLED", "false"),
            speaker_count=env_int("SPEAKER_COUNT", "0"),
            diarization_venv_python=env("DIARIZATION_VENV_PYTHON"),
            diarization_model_dir=env("DIARIZATION_MODEL_DIR"),
            lipsync_venv_python=env("LIPSYNC_VENV_PYTHON"),
            lipsync_model_dir=env("LIPSYNC_MODEL_DIR"),
            lipsync_max_duration_s=env_float("LIPSYNC_MAX_DURATION_S", "12.0"),
            lipsync_max_no_face_ratio=env_float("LIPSYNC_MAX_NO_FACE_RATIO", "0.0"),
            emotion_voice_enabled=env_bool("EMOTION_VOICE_ENABLED", "false"),
            asr_num_threads=max(1, min(16, env_int("ASR_NUM_THREADS", "4"))),
            whisper_beam_size=max(1, min(10, env_int("WHISPER_BEAM_SIZE", "5"))),
            vieneu_venv_python=env("VIENEU_VENV_PYTHON"),
            vieneu_model_dir=env("VIENEU_MODEL_DIR"),
            vieneu_voice=env("VIENEU_VOICE", "").strip(),
            vieneu_style=_one_of(env("VIENEU_STYLE", "tu_nhien"),
                                 ("tu_nhien", "tin_tuc", "doc_truyen"),
                                 "tu_nhien"),
            # Người dùng đặt tay thì tôn trọng; chưa đặt thì tự tính theo
            # RAM trống + số nhân (xem _auto_vieneu_workers).
            vieneu_max_workers=max(1, min(8, env_int(
                "VIENEU_MAX_WORKERS",
                "3" if env("VIENEU_MAX_WORKERS")
                else str(_auto_vieneu_workers())))),
            parallel_workers=max(1, min(16, env_int("PARALLEL_WORKERS",
                                                    auto_workers))),
            video_speed=min(1.0, max(0.5, env_float("VIDEO_SPEED", "1.0"))),
            voice_speed=min(2.0, max(0.5, env_float("VOICE_SPEED", "1.0"))),
            translate_cps_budget=env_float("TRANSLATE_CPS_BUDGET", "12.5"),
            hq_background=env_bool("HQ_BACKGROUND", _p["hq_background"]),
            voice_postprocess=env_bool("VOICE_POSTPROCESS", "true"),
            voice_target_lufs=env_float("VOICE_TARGET_LUFS", "-16.0"),
            bg_duck_voice_db=min(0.0, max(-24.0,
                env_float("BG_DUCK_VOICE_DB", "-7.0"))),
            soft_timing_fit=env_bool("SOFT_TIMING_FIT", "true"),
            timing_max_drift_s=min(5.0, max(0.0,
                env_float("TIMING_MAX_DRIFT_S", "1.5"))),
            timing_min_gap_s=min(1.0, max(0.0,
                env_float("TIMING_MIN_GAP_S", "0.12"))),
            timing_max_atempo=min(1.3, max(1.0,
                env_float("TIMING_MAX_ATEMPO", "1.1"))),
            quality_gate_max_over_budget_ratio=min(1.0, max(0.0,
                env_float("QUALITY_GATE_MAX_OVER_BUDGET_RATIO", "0.15"))),
            quality_gate_max_speed_fallback_ratio=min(1.0, max(0.0,
                env_float("QUALITY_GATE_MAX_SPEED_FALLBACK_RATIO", "0.10"))),
            quality_gate_max_postprocess_fallback_ratio=min(1.0, max(0.0,
                env_float("QUALITY_GATE_MAX_POSTPROCESS_FALLBACK_RATIO", "0.10"))),
            quality_gate_max_shift_s=min(5.0, max(0.0,
                env_float("QUALITY_GATE_MAX_SHIFT_S", "1.0"))),
            translate_analysis=env_bool("TRANSLATE_ANALYSIS",
                                        _p["translate_analysis"]),
            translate_review=env_bool("TRANSLATE_REVIEW",
                                      _p["translate_review"]),
            translate_domain=env("TRANSLATE_DOMAIN").strip(),
            translate_context=env_multiline("TRANSLATE_CONTEXT"),
            translate_pronouns=env("TRANSLATE_PRONOUNS").strip(),
            translate_glossary=env_multiline("TRANSLATE_GLOSSARY"),
            translate_style_notes=env_multiline("TRANSLATE_STYLE_NOTES"),
            default_source_lang=env("DEFAULT_SOURCE_LANG", "zh-CN"),
            audio_sample_rate=env_int("AUDIO_SAMPLE_RATE", "16000"),
            output_dir=env_dir("OUTPUT_DIR", "./output"),
            vietnamese_output_dir=env_dir("VIETNAMESE_OUTPUT_DIR", ""),
            auto_clean_intermediates=env_bool("AUTO_CLEAN_INTERMEDIATES",
                                              "false"),
            update_repo=env("UPDATE_REPO",
                            "junnyken/voxdub-studio").strip(),
            support_url=env("SUPPORT_URL",
                            "https://github.com/junnyken/voxdub-studio/issues").strip(),
            video_url=env("VIDEO_URL"),
            generate_metadata=env("GENERATE_METADATA", "true").strip().lower()
                              not in ("0", "false", "no"),
            translate_enabled=env("TRANSLATE_ENABLED", "true").strip().lower()
                              not in ("0", "false", "no"),
            translate_batch_size=max(1, min(100,
                env_int("TRANSLATE_BATCH_SIZE", "40"))),
            translate_local_enabled=env("TRANSLATE_LOCAL_ENABLED", "false")
                                    .strip().lower() not in ("0", "false", "no"),
            gop_cau_truoc_khi_dich=env("GOP_CAU_TRUOC_KHI_DICH", "true")
                                    .strip().lower() not in ("0", "false", "no"),
            cloud_render_enabled=env("CLOUD_RENDER_ENABLED", "false")
                                 .strip().lower() not in ("0", "false", "no"),
            subtitle_mode=_one_of(env("SUBTITLE_MODE", "none"),
                                  ("none", "soft", "burn"), "none"),
            subtitle_preset=env("SUBTITLE_PRESET", "clean").strip() or "clean",
            subtitle_position=_one_of(env("SUBTITLE_POSITION", "bottom"),
                                      ("bottom", "middle", "top"), "bottom"),
            subtitle_font=env("SUBTITLE_FONT", "Arial"),
            subtitle_font_size=env_int("SUBTITLE_FONT_SIZE", "22"),
            subtitle_margin_v=env_int("SUBTITLE_MARGIN_V", "40"),
            subtitle_outline=env_int("SUBTITLE_OUTLINE", "2"),
            subtitle_shadow=max(0, min(8, env_int("SUBTITLE_SHADOW", "0"))),
            subtitle_bold=env_bool("SUBTITLE_BOLD", "true"),
            subtitle_color=env("SUBTITLE_COLOR", "#FFFFFF"),
            subtitle_outline_color=env("SUBTITLE_OUTLINE_COLOR", "#000000"),
            subtitle_box=_one_of(env("SUBTITLE_BOX", "none"),
                                 ("none", "box"), "none"),
            subtitle_box_color=env("SUBTITLE_BOX_COLOR", "#000000"),
            subtitle_box_opacity=max(0, min(100,
                env_int("SUBTITLE_BOX_OPACITY", "60"))),
            subtitle_line_words=max(0, min(12,
                env_int("SUBTITLE_LINE_WORDS", "0"))),
            subtitle_max_lines=max(1, min(4,
                env_int("SUBTITLE_MAX_LINES", "2"))),
            subtitle_all_caps=env_bool("SUBTITLE_ALL_CAPS", "false"),
            subtitle_display=_one_of(env("SUBTITLE_DISPLAY", "sentence"),
                                     ("sentence", "karaoke"), "sentence"),
            karaoke_words_per_cue=max(1, min(5,
                env_int("KARAOKE_WORDS_PER_CUE", "3"))),
            karaoke_effect=_one_of(env("KARAOKE_EFFECT", "pop"),
                                   ("pop", "fade", "karaoke", "none"), "pop"),
            karaoke_highlight_color=env("KARAOKE_HIGHLIGHT_COLOR",
                                        "#FFD54A").strip() or "#FFD54A",
            karaoke_alignment=env_bool("KARAOKE_ALIGNMENT",
                                       _p["karaoke_alignment"]),
        )

    # --- Kiểm tra cấu hình -------------------------------------------------

    def require(self, *fields: str) -> None:
        """Ném ConfigError nếu một trong các mục được nêu còn trống."""
        missing = [f for f in fields if not getattr(self, f)]
        if missing:
            env_names = ", ".join(f.upper() for f in missing)
            raise ConfigError(
                f"Thiếu cấu hình bắt buộc: {env_names}. "
                f"Điền vào trang Cài đặt (hoặc tệp .env) rồi chạy lại."
            )

    # --- Phụ đề ------------------------------------------------------------

    def subtitle_style(self) -> dict:
        """Kiểu phụ đề truyền cho ffmpeg/libass.

        Đây là "đường ống" DUY NHẤT đưa lựa chọn phụ đề từ Cài đặt qua
        pipeline tới trình chỉnh sửa (render_opts.json).
        """
        return {
            "preset": self.subtitle_preset,
            "position": self.subtitle_position,
            "font": self.subtitle_font,
            "font_size": self.subtitle_font_size,
            "margin_v": self.subtitle_margin_v,
            "outline": self.subtitle_outline,
            "shadow": self.subtitle_shadow,
            "bold": self.subtitle_bold,
            "color": self.subtitle_color,
            "outline_color": self.subtitle_outline_color,
            "box": self.subtitle_box,
            "box_color": self.subtitle_box_color,
            "box_opacity": self.subtitle_box_opacity,
            "line_words": self.subtitle_line_words,
            "max_lines": self.subtitle_max_lines,
            "all_caps": self.subtitle_all_caps,
            "display": self.subtitle_display,
            "words_per_cue": self.karaoke_words_per_cue,
            "effect": self.karaoke_effect,
            "highlight_color": self.karaoke_highlight_color,
        }

    # --- Đường dẫn của các bộ chạy riêng ------------------------------------

    def _ban_cu(self, ten_venv: str, ten_model: str, lay_model: bool) -> str:
        """Đường dẫn lấy từ bản cài CŨ cạnh bên, hoặc "" nếu không có.

        Mini-spec V77: venv và models nằm trong thư mục ứng dụng nên nâng cấp
        (giải nén bản mới ra thư mục khác) là mất sạch. Xem
        autodub/venv_discovery.py.
        """
        from autodub.venv_discovery import tim_ban_cai_cu

        found = tim_ban_cai_cu(ten_venv, ten_model)
        if not found:
            return ""
        return found[1] if lay_model else found[0]

    def asr_venv_python_path(self) -> str:
        """Trình thông dịch Python của venv dành riêng cho Paraformer."""
        if self.asr_venv_python:
            return self.asr_venv_python
        exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        mac_dinh = os.path.join(app_root(), ".venv-asr", *exe.split("/"))
        if os.path.isfile(mac_dinh):
            return mac_dinh
        return self._ban_cu(".venv-asr", "paraformer-zh", False) or mac_dinh

    def paraformer_model_dir_path(self) -> str:
        """Thư mục chứa model Paraformer + silero-VAD (+ chấm câu)."""
        if self.paraformer_model_dir:
            return self.paraformer_model_dir
        mac_dinh = os.path.join(app_root(), "models", "paraformer-zh")
        if os.path.isfile(os.path.join(mac_dinh, "installed_ok.json")):
            return mac_dinh
        return self._ban_cu(".venv-asr", "paraformer-zh", True) or mac_dinh

    def paraformer_configured(self) -> bool:
        """venv ASR và dấu hiệu cài đặt xong đều có mặt hay chưa."""
        return (os.path.isfile(self.asr_venv_python_path())
                and os.path.isfile(os.path.join(self.paraformer_model_dir_path(),
                                                "installed_ok.json")))

    def diarization_venv_python_path(self) -> str:
        """Trình thông dịch Python của venv dành riêng cho diarization."""
        if self.diarization_venv_python:
            return self.diarization_venv_python
        exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        return os.path.join(app_root(), ".venv-diar", *exe.split("/"))

    def diarization_model_dir_path(self) -> str:
        """Thư mục cache model diarization (pyannote pipeline)."""
        if self.diarization_model_dir:
            return self.diarization_model_dir
        return os.path.join(app_root(), "models", "diarization")

    def diarization_configured(self) -> bool:
        """venv diarization và dấu hiệu cài đặt xong đều có mặt hay chưa —
        pipeline dùng cờ này để degrade trung thực khi chưa cài (V26
        Constraint 2), không phải chỉ dựa vào `diarization_enabled`."""
        return (os.path.isfile(self.diarization_venv_python_path())
                and os.path.isfile(os.path.join(self.diarization_model_dir_path(),
                                                "installed_ok.json")))

    def lipsync_venv_python_path(self) -> str:
        """Trình thông dịch Python của venv dành riêng cho lip-sync (MuseTalk)."""
        if self.lipsync_venv_python:
            return self.lipsync_venv_python
        exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        return os.path.join(app_root(), ".venv-lipsync", *exe.split("/"))

    def lipsync_repo_dir_path(self) -> str:
        """Mã nguồn MuseTalk đã vendor (xem scripts/setup_lipsync.py)."""
        return os.path.join(app_root(), "vendor", "musetalk")

    def lipsync_model_dir_path(self) -> str:
        """Thư mục cache model MuseTalk (weights ~5-6GB)."""
        if self.lipsync_model_dir:
            return self.lipsync_model_dir
        return os.path.join(app_root(), "models", "lipsync")

    def lipsync_configured(self) -> bool:
        """venv + mã nguồn + weights lip-sync đều có mặt hay chưa — pipeline
        dùng cờ này để degrade trung thực (V32b Constraint 2), không chỉ dựa
        vào DubRequest.lipsync."""
        return (os.path.isfile(self.lipsync_venv_python_path())
                and os.path.isdir(os.path.join(self.lipsync_repo_dir_path(), "musetalk"))
                and os.path.isfile(os.path.join(self.lipsync_model_dir_path(),
                                                "installed_ok.json")))

    def lipsync_gpu_available(self) -> bool:
        """GPU NVIDIA thật có mặt hay chưa (V32b Constraint 1 — tính năng
        CHỈ bật được khi phát hiện GPU, không có đường CPU fallback). Kiểm
        NHẸ (chỉ `nvidia-smi` có mặt) — không đo VRAM cụ thể ở đây, việc đó
        thuộc về script cài đặt (xem scripts/setup_lipsync.py)."""
        import shutil as _shutil
        return _shutil.which("nvidia-smi") is not None

    def whisper_venv_python_path(self) -> str:
        """Trình thông dịch Python của venv dành riêng cho Whisper."""
        if self.whisper_venv_python:
            return self.whisper_venv_python
        exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        mac_dinh = os.path.join(app_root(), ".venv-whisper", *exe.split("/"))
        if os.path.isfile(mac_dinh):
            return mac_dinh
        return self._ban_cu(".venv-whisper", "whisper", False) or mac_dinh

    def whisper_model_dir_path(self) -> str:
        """Thư mục cache model Whisper (HuggingFace)."""
        if self.whisper_model_dir:
            return self.whisper_model_dir
        mac_dinh = os.path.join(app_root(), "models", "whisper")
        if os.path.isfile(os.path.join(mac_dinh, "installed_ok.json")):
            return mac_dinh
        return self._ban_cu(".venv-whisper", "whisper", True) or mac_dinh

    def whisper_venv_configured(self) -> bool:
        """venv Whisper đã cài và có marker hay chưa."""
        return (os.path.isfile(self.whisper_venv_python_path())
                and os.path.isfile(os.path.join(self.whisper_model_dir_path(),
                                                "installed_ok.json")))

    def vieneu_venv_python_path(self) -> str:
        """Trình thông dịch Python của venv dành riêng cho VieNeu."""
        if self.vieneu_venv_python:
            return self.vieneu_venv_python
        exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        mac_dinh = os.path.join(app_root(), ".venv-vieneu", *exe.split("/"))
        if os.path.isfile(mac_dinh):
            return mac_dinh
        return self._ban_cu(".venv-vieneu", "vieneu", False) or mac_dinh

    def vieneu_model_dir_path(self) -> str:
        """Thư mục chứa các tệp model VieNeu đã tải về."""
        if self.vieneu_model_dir:
            return self.vieneu_model_dir
        mac_dinh = os.path.join(app_root(), "models", "vieneu")
        if os.path.isfile(os.path.join(mac_dinh, "installed_ok.json")):
            return mac_dinh
        return self._ban_cu(".venv-vieneu", "vieneu", True) or mac_dinh

    def vieneu_custom_voices_path(self) -> str:
        """Tệp JSON chứa giọng người dùng tự thêm.

        Nằm trong models/vieneu cạnh ứng dụng (không nằm trong gói mã) nên
        cập nhật ứng dụng không làm mất giọng đã học.
        """
        return os.path.join(self.vieneu_model_dir_path(), "custom_voices.json")

    def vieneu_configured(self) -> bool:
        """venv VieNeu và dấu hiệu cài đặt xong đều có mặt hay chưa."""
        return (os.path.isfile(self.vieneu_venv_python_path())
                and os.path.isfile(os.path.join(self.vieneu_model_dir_path(),
                                                "installed_ok.json")))

    def translate_local_venv_python_path(self) -> str:
        """Trình thông dịch Python của venv dành riêng cho dịch local (V6)."""
        exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        return os.path.join(app_root(), ".venv-mt", *exe.split("/"))

    def translate_local_model_dir_path(self) -> str:
        """Thư mục chứa model dịch local (NLLB-200 distilled, ctranslate2)."""
        return os.path.join(app_root(), "models", "translate-local")

    def translate_local_configured(self) -> bool:
        """venv dịch local và dấu hiệu cài đặt xong đều có mặt hay chưa."""
        return (os.path.isfile(self.translate_local_venv_python_path())
                and os.path.isfile(os.path.join(
                    self.translate_local_model_dir_path(), "installed_ok.json")))

    def ocr_venv_python_path(self) -> str:
        """Trình thông dịch Python của venv dành riêng cho quét chữ tự động (V5)."""
        exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        return os.path.join(app_root(), ".venv-ocr", *exe.split("/"))

    def ocr_configured(self) -> bool:
        """venv OCR đã cài và có marker hay chưa (RapidOCR tự mang sẵn model
        nhỏ trong gói pip — không cần bước tải model riêng như Whisper/VieNeu)."""
        return os.path.isfile(self.ocr_venv_python_path())

    def vi_output_dir(self) -> str:
        """Thư mục kết quả: VIETNAMESE_OUTPUT_DIR hoặc OUTPUT_DIR/VN."""
        if self.vietnamese_output_dir:
            return self.vietnamese_output_dir
        return os.path.join(self.output_dir, "VN")

    def resolved_whisper_model(self, cuda_available: bool) -> str:
        """Tên model Whisper thật khi chọn "auto" (large-v3 GPU / medium CPU).

        large-v3 int8 cần khoảng 3 GB VRAM — vẫn vừa card 6 GB vì ASR chạy
        một mình trên card (Demucs xong, giọng đọc chạy CPU). Trên CPU thì
        large-v3 chậm gấp nhiều lần medium nên "auto" chỉ nâng khi có CUDA.
        """
        if self.whisper_model.strip().lower() != "auto":
            return self.whisper_model
        return "large-v3" if cuda_available else "medium"

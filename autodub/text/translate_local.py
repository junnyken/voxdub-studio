"""Dịch local/offline (mini-spec V6, xem docs/PLAN.md) — path C bên cạnh
dịch tay (path A) và dịch qua máy chủ (path B, xem translate_saas.py).

Chỉ dùng khi KHÔNG có máy chủ nào cấu hình (``saas_client.is_configured()``
== False — pipeline.py giữ nguyên gate đó làm cổng duy nhất) VÀ người dùng
đã bật ``settings.translate_local_enabled`` VÀ đã tải model
(``scripts/setup_translate_local.py``). Chạy 100% trên máy, không gọi mạng.

Chất lượng THẤP HƠN dịch tay (ChatGPT/Gemini) hoặc dịch qua máy chủ (3-pass
analyze→translate→review) — đây là bản dịch 1-pass, không có ngữ cảnh video.
Không giả vờ ngang hàng — GUI phải hiện rõ cảnh báo (xem
autodub_gui, trang Dịch thuật).

Giấy phép: model NLLB-200-distilled-600M là CC-BY-NC-4.0 (Meta) — CHỈ dùng
cho tính năng miễn phí của ứng dụng, không bán riêng bản dịch từ engine này.
"""
from __future__ import annotations

import json
import subprocess
from collections import deque

from autodub.languages import TargetLang
from autodub.progress import ProgressReporter
from autodub.text.translate_hint import ensure_terminal_punct
from autodub.utils import bundled_file, setup_logging

logger = setup_logging("autodub.translate_local")

# BCP-47 (dùng trong app) -> FLORES-200 (dùng bởi NLLB). Chỉ gồm đúng các
# ngôn ngữ nguồn đã có trong autodub_gui/dub_constants.py (V4) + đích "vi".
LANG_TO_FLORES = {
    "zh-CN": "zho_Hans",
    "zh-TW": "zho_Hant",
    "zh-HK": "yue_Hant",   # Hồng Kông nói/viết phổ biến — Quảng Đông
    "en-US": "eng_Latn",
    "ko-KR": "kor_Hang",
    "ja-JP": "jpn_Jpan",
    "th-TH": "tha_Thai",
    "id-ID": "ind_Latn",
    "vi-VN": "vie_Latn",
}


class LocalTranslateError(Exception):
    """Dịch local hỏng (worker crash, model thiếu, ngôn ngữ không hỗ trợ)."""


def flores_code(bcp47: str) -> str | None:
    """FLORES-200 code cho 1 mã BCP-47, hoặc None nếu chưa map (chưa hỗ trợ)."""
    return LANG_TO_FLORES.get(bcp47)


def is_available(settings, source_lang: str) -> bool:
    """Đủ điều kiện dùng path C cho lượt này chưa (đã cài + ngôn ngữ hỗ trợ)."""
    return (bool(settings.translate_local_configured())
            and flores_code(source_lang) is not None)


def translate_segments_local(
    segments: list[dict], target: TargetLang, source_lang: str, settings,
    reporter: ProgressReporter | None = None,
) -> list[dict]:
    """Dịch toàn bộ câu bằng model local (NLLB, subprocess trong .venv-mt).

    Trả về bản sao ``segments`` kèm ``target.text_field``, cùng dạng dữ liệu
    với translate_saas.translate_segments() để pipeline.py không cần biết
    bản dịch đến từ đâu (xem điểm gọi trong DubPipeline._auto_translate()).
    """
    if not segments:
        raise LocalTranslateError("Không có câu nào để dịch")

    src = flores_code(source_lang)
    tgt = flores_code(target.code) or flores_code("vi-VN")
    if not src:
        raise LocalTranslateError(
            f"Dịch local chưa hỗ trợ ngôn ngữ nguồn '{source_lang}'")

    worker_script = bundled_file("autodub", "text", "translate_local_worker.py")
    cmd = [
        settings.translate_local_venv_python_path(),
        worker_script,
        "--model-dir", settings.translate_local_model_dir_path(),
        "--src-lang", src,
        "--tgt-lang", tgt,
    ]
    logger.info(f"Đang dịch {len(segments)} câu bằng model local (offline)...")
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
    )

    stderr_tail: deque[str] = deque(maxlen=30)
    import threading

    def _drain() -> None:
        try:
            for line in proc.stderr:
                line = line.rstrip()
                if line:
                    stderr_tail.append(line)
        except (ValueError, OSError):
            pass

    threading.Thread(target=_drain, daemon=True).start()

    ready_line = proc.stdout.readline().strip()
    try:
        ready = json.loads(ready_line)
    except (json.JSONDecodeError, ValueError):
        proc.kill()
        raise LocalTranslateError(
            f"Worker dịch local không phản hồi: {ready_line!r}\n"
            + "\n".join(stderr_tail))
    if not ready.get("ready"):
        proc.kill()
        raise LocalTranslateError(
            f"Worker dịch local báo lỗi: {ready}\n" + "\n".join(stderr_tail))

    payload = {"segments": [{"id": s.get("id"), "text": s.get("text", "")}
                            for s in segments]}
    proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    proc.stdin.close()

    by_id: dict = {}
    done = False
    for line in proc.stdout:
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("error"):
            proc.wait(timeout=5)
            raise LocalTranslateError(f"Worker dịch local: {msg['error']}")
        if msg.get("seg"):
            by_id[msg.get("id")] = str(msg.get("text", ""))
            if reporter is not None:
                reporter.emit("translate", "progress",
                              current=len(by_id), total=len(segments))
        elif msg.get("done"):
            done = True
            break

    proc.wait(timeout=30)
    if not done:
        raise LocalTranslateError(
            "Worker dịch local kết thúc bất thường\n" + "\n".join(stderr_tail))

    merged = []
    for seg in segments:
        text = by_id.get(seg.get("id"), "")
        merged.append({**seg, target.text_field: ensure_terminal_punct(text)})
    logger.info(f"Dịch local xong: {len(merged)} câu")
    return merged

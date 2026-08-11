"""Vox hold/credit — lớp giữ chỗ trả phí của một lượt dubbing (SaaS, tuỳ chọn).

Được tách ra từ ``pipeline.py`` (mini-spec V2, xem ``docs/PLAN.md``) — DI CHUYỂN
NGUYÊN VĂN logic, không đổi hành vi. ``DubPipeline`` giữ nguyên các phương thức
riêng ``_setup_hold``/``_stop_for_export``/``_settle_hold_inline``/
``_money_note_for_manual`` như cũ, chỉ còn là 1 dòng gọi sang
:class:`HoldBillingAdapter` — mọi call site khác trong ``run()`` không đổi.

Cố ý KHÔNG đụng tới ``HOLD``/``USAGE`` (global state trong
``autodub.text.translate_common``, đọc trực tiếp ở nhiều module khác ngoài
pipeline.py: translate_saas.py, translate_review.py, translate_hint.py,
content/generator.py) — đó là ambient state có chủ đích của thiết kế gốc, tách
nó ra là một thay đổi kiến trúc lớn hơn nhiều, cần môi trường regression-test
đầy đủ (ffmpeg+GPU+control_server thật) mà mini-spec V2 hiện tại không có.
``saas_client.is_configured()`` vẫn là cổng duy nhất, không thêm cổng thứ hai.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from autodub.progress import ProgressReporter
from autodub.utils import setup_logging
from autodub.workdir import data_path

if TYPE_CHECKING:
    from autodub.config import Settings
    from autodub.languages import TargetLang
    from autodub.pipeline import DubResult

logger = setup_logging("autodub.billing")


class HoldBillingAdapter:
    """Toàn bộ vòng đời hold Vox của MỘT lượt ``DubPipeline.run()``.

    Sở hữu bởi ``DubPipeline`` (1 instance mỗi lần ``run()``, giống các cache
    khác của pipeline) — thay cho việc lưu ``self._hold_estimate`` trực tiếp
    trên ``DubPipeline``.
    """

    def __init__(self, settings: "Settings", reporter: ProgressReporter) -> None:
        self.settings = settings
        self.reporter = reporter
        self.hold_estimate = 0

    # ------------------------------------------------------------------ #
    # Di chuyển nguyên văn từ DubPipeline._setup_hold (pipeline.py, mini-spec
    # V2) — comment/logic giữ nguyên 100%, chỉ đổi self.settings/self.reporter
    # cho khớp adapter và self._unlock_after_commit -> self.unlock_after_commit.
    def setup_hold(
        self, segments: list[dict], target: "TargetLang", work_dir: str,
        video_duration_s: float,
    ) -> "DubResult | None":
        """Giữ chỗ Vox cho lượt chạy — gọi ngay sau ASR, mọi luồng.

        Giá là công thức đóng trên số câu thoại ASR vừa tách được, nên chốt
        được ngay tại đây và không đổi nữa. Ví bị trừ đủ tại bước này; chốt
        hold (bấm Xuất video ở wizard, tự động ở batch/legacy) chỉ mở khóa,
        không hoàn cũng không truy thu.

        Dịch tay (tắt dịch tự động) VẪN giữ chỗ: người dùng trả giá nền cho
        cả lượt xử lý — nghe-chép, tách nhạc, lồng tiếng, ghép video — chỉ
        không trả phần cộng thêm của dịch tự động.

        Trả về ``DubResult(status="credit_blocked")`` khi thiếu Vox (chặn
        TRƯỚC khi máy chạy tiếp), hoặc ``None`` để pipeline chạy tiếp:

        - Hold tạo/nhận lại thành công → ``HOLD`` mang hold_id + khóa mã hóa,
          file trung gian mã hóa trên đĩa cho tới lúc xuất video.
        - Máy chủ tắt hold / hold đã chốt / không kết nối được → rơi về luồng
          cũ (trừ Vox theo từng lượt, không mã hóa) kèm cảnh báo.
        """
        from autodub.pipeline import DubResult
        from autodub.saas_client import (
            InsufficientCreditError, OfflineError, SaasError, get_client,
            is_configured)
        from autodub.text.translate_common import HOLD
        from autodub.text.translate_saas import run_id_for

        HOLD.clear()
        if not is_configured():
            # Chạy thuần trên máy — không có ví Vox nào để giữ chỗ.
            return None
        auto = bool(self.settings.translate_enabled)
        meta = bool(getattr(self.settings, "generate_metadata", True))
        run_id = run_id_for(segments, target)
        mins, secs = divmod(int(video_duration_s), 60)
        try:
            data = get_client().create_hold(
                run_id, len(segments), video_duration_s,
                auto_translate=auto, metadata=meta)
        except InsufficientCreditError as e:
            self.reporter.emit("translate", "error", detail="Không đủ Vox")
            logger.warning(
                f"Không đủ Vox cho video này: cần giữ chỗ {e.required:,} Vox "
                f"(ví còn {e.balance:,}). Nạp thêm rồi chạy lại — phần đã "
                "nghe-chép được dùng lại, không mất công.")
            return DubResult(status="credit_blocked", work_dir=work_dir,
                             report={"balance": e.balance,
                                     "required": e.required,
                                     "sentences": len(segments),
                                     "duration_s": video_duration_s})
        except SaasError as e:
            if getattr(e, "code", "") == "HOLD_FINISHED":
                # Hold đã tự chốt sau 48h — giá đã trả đủ từ lúc giữ chỗ.
                # Lấy lại khóa (get_hold vẫn trả khi committed) và giải mã
                # file cũ để lượt chạy này dùng tiếp phần đã trả tiền.
                logger.warning("Lượt trả phí trước đã tự chốt (quá 48 giờ) — "
                               "dùng lại phần đã dịch, không tính phí lần "
                               "hai; chạy tiếp kiểu thường")
                self.unlock_after_commit(work_dir, run_id)
                return None
            if getattr(e, "code", "") == "HOLD_DISABLED":
                logger.warning(f"Không giữ chỗ Vox được ({e}) — chuyển sang "
                               "trừ Vox theo từng lượt như cũ")
                return None
            logger.warning(f"Giữ chỗ Vox lỗi ({e}) — trừ theo từng lượt như cũ")
            return None
        except OfflineError as e:
            # Chưa vào tới bước dịch nên chưa cần fail-closed — bước dịch sẽ
            # tự báo nếu lúc đó vẫn mất mạng.
            logger.warning(f"Không kết nối được máy chủ ({e}) — "
                           "trừ Vox theo từng lượt như cũ")
            return None

        hold = data.get("hold") or {}
        key = str(hold.get("encKeyHex") or "")
        if not key:
            logger.warning("Máy chủ không trả khóa mã hóa — trừ Vox theo "
                           "từng lượt như cũ")
            return None
        HOLD.set(run_id, key)

        est = int(hold.get("estimatedVox") or 0)
        self.hold_estimate = est
        balance = int(data.get("balance") or 0)
        dur_txt = f"{mins} phút {secs} giây" if mins else f"{secs} giây"
        if data.get("created"):
            logger.info(
                f"Video này tốn {est:,} Vox ({len(segments)} câu thoại, "
                f"{dur_txt}) — ví còn {balance:,} Vox. Giá đã chốt, chạy lại "
                "hay dịch nhiều lượt cũng không tính thêm.")
        else:
            logger.info(
                f"Dùng lại lượt đã trả phí của lần chạy trước ({est:,} Vox) "
                "— không tính phí lần hai.")
        return None

    # Di chuyển nguyên văn từ DubPipeline._money_note_for_manual.
    def money_note_for_manual(self) -> str:
        """Dòng trấn an về Vox để ghi vào hướng dẫn dịch tay.

        Lượt chạy KHÔNG chốt hold ở đây: giá đã chốt và ví đã trừ đủ từ lúc
        giữ chỗ, nên phần dịch tay không phát sinh thêm đồng nào. Giữ hold
        nguyên còn cần cho lúc chạy lại — cùng ``run_id`` nhận lại đúng hold
        cũ kèm khóa, mở được ``video_context.json`` và sổ tạm đã mã hóa,
        không bị tính phí lần hai.
        """
        from autodub.text.translate_common import HOLD

        if not HOLD.active:
            return ""
        est = int(getattr(self, "hold_estimate", 0) or 0)
        if not est:
            return ("Phần dịch tay dưới đây không tốn thêm Vox — giá của "
                    "video này đã chốt từ đầu.")
        return (f"Video này đã tính {est:,} Vox từ đầu và giá không đổi nữa. "
                "Phần bạn dịch tay dưới đây không tốn thêm đồng nào, chạy "
                "lại cũng không bị tính lần hai.")

    # Di chuyển nguyên văn từ DubPipeline._unlock_after_commit (staticmethod).
    @staticmethod
    def unlock_after_commit(work_dir: str, hold_id: str) -> None:
        """Giải mã file trung gian của một hold ĐÃ chốt (tự chốt sau 48h).

        Vox đã trừ rồi nên dữ liệu thuộc về người dùng — lấy lại khóa qua
        ``get_hold`` (vẫn trả khi committed) và mở khóa toàn bộ. Lỗi ở đây
        không chặn pipeline: file mã hóa sẽ bị coi là hỏng và làm lại
        (máy chủ trả kết quả cache theo job_id, không tính phí lần hai).
        """
        from autodub import securestore

        if not securestore.is_locked(work_dir):
            return
        try:
            from autodub.saas_client import get_client
            hold = get_client().get_hold(hold_id).get("hold") or {}
            key = str(hold.get("encKeyHex") or "")
            if key:
                done = securestore.unlock_all(work_dir, key)
                if done:
                    logger.info(f"Đã mở khóa {len(done)} file trung gian "
                                "của lần chạy trước")
        except Exception as e:  # noqa: BLE001 — mở khóa hỏng thì làm lại
            logger.warning(f"Không mở khóa được file lần chạy trước ({e}) — "
                           "phần đó sẽ được làm lại, không tính phí lần hai")

    # Di chuyển nguyên văn từ DubPipeline._stop_for_export.
    def stop_for_export(self, state: dict, work_dir: str) -> "DubResult":
        """Dừng ở ranh giới Xuất video (luồng wizard, hold còn active).

        Thành quả trả phí (bản dịch đã mã hóa từ trước, audio ghép, trạng
        thái xuất) nằm trên đĩa dưới dạng mã hóa AES-256-GCM; khóa chỉ có
        máy chủ giữ bản gốc. Bấm Xuất video → commit hold → nhận khóa →
        giải mã → :meth:`DubPipeline._export_phase`.
        """
        from autodub import securestore
        from autodub.editor import load_render_opts, save_render_opts
        from autodub.pipeline import DubResult
        from autodub.speech.tts import voices as voice_catalog
        from autodub.text.translate_common import HOLD, USAGE

        hold_id, key = HOLD.hold_id, HOLD.key

        # Ghim giọng + tùy chọn render để thẻ dự án hiện đúng thông tin
        # (Trình chỉnh sửa vẫn khóa cho tới khi xuất).
        render_opts = load_render_opts(work_dir)
        render_opts["voice"] = voice_catalog.resolve(self.settings,
                                                     state.get("voice"))
        render_opts.setdefault("subtitle_mode", state.get("subtitle_mode"))
        render_opts.setdefault("blur_regions", state.get("blur_regions"))
        render_opts.setdefault("subtitle_style", state.get("subtitle_style"))
        save_render_opts(work_dir, render_opts)

        # Audio ghép + trạng thái xuất: mã hóa rồi ghi vào marker.
        merged = state["merged_audio_path"]
        securestore.encrypt_file(merged, key)
        securestore.add_locked_file(work_dir, hold_id, merged)

        state_path = data_path(work_dir, "export_state.json")
        securestore.write_json_secure(state, state_path, key)
        securestore.add_locked_file(work_dir, hold_id, state_path)

        # video_context.json đã mã hóa từ bước phân tích — thêm vào marker
        # để lúc commit được mở khóa cùng lượt.
        ctx = data_path(work_dir, "video_context.json")
        if os.path.exists(ctx) and securestore.is_encrypted(ctx):
            securestore.add_locked_file(work_dir, hold_id, ctx)

        segments = state["segments"]
        duration_s = max(float(s.get("end", 0) or 0) for s in segments)
        usage = USAGE.snapshot()
        # Tổng Vox của video (``estimatedVox``) cho thẻ tổng kết — lấy trượt
        # cũng không sao, GUI vẫn hiện được số liệu cục bộ.
        hold_detail = None
        try:
            from autodub.saas_client import get_client
            hold_detail = (get_client().get_hold(hold_id) or {}).get("hold")
        except Exception:  # noqa: BLE001 — mạng chập chờn thì bỏ qua
            pass
        total = int((hold_detail or {}).get("estimatedVox") or usage["vox"] or 0)
        mins, secs = divmod(int(duration_s), 60)
        dur_txt = f"{mins} phút {secs} giây" if mins else f"{secs} giây"
        logger.info("=" * 60)
        logger.info(
            f"Đã lồng tiếng xong ({len(segments)} câu, {dur_txt}) — video này "
            f"tốn {total:,} Vox. Bấm Xuất video để nhận video hoàn chỉnh.")
        return DubResult(status="export_pending", work_dir=work_dir,
                         report={
                             "hold_id": hold_id,
                             "sentences": len(segments),
                             "duration_s": round(duration_s, 1),
                             "usage": usage,
                             "hold": hold_detail,
                         })

    # Di chuyển nguyên văn từ DubPipeline._settle_hold_inline.
    def settle_hold_inline(self, work_dir: str) -> None:
        """Chốt hold ngay trước phase xuất (luồng batch/legacy).

        Không có nút Xuất video ở luồng này nên chốt tại đây: commit là
        trung tính về tiền (giá đã trừ đủ lúc giữ chỗ), chỉ để mở khóa các
        file trung gian đã mã hóa và đóng hold thay vì chờ sweeper 48 giờ.
        ``HOLD`` được GIỮ NGUYÊN — bước tạo nội dung đăng bài trong phase
        xuất còn trỏ vào hold này (server nhận hold committed cho đúng một
        lượt generate_post); nơi gọi chịu trách nhiệm ``HOLD.clear()`` sau.

        Lỗi mạng ở đây KHÔNG làm hỏng lượt chạy — khóa còn trong RAM nên
        file trung gian vẫn mở được; hold sẽ tự chốt sau TTL, không tính
        thêm Vox.
        """
        from autodub import securestore
        from autodub.text.translate_common import HOLD, USAGE

        hold_id, key = HOLD.hold_id, HOLD.key
        if not hold_id:
            return
        try:
            from autodub.saas_client import get_client
            data = get_client().commit_hold(hold_id)
            charged = int(data.get("chargedVox") or 0)
            balance = int(data.get("balance") or 0)
            # Thẻ tổng kết/nhật ký hiện đúng tổng Vox của video này.
            USAGE.reset()
            USAGE.add(charged, balance)
            logger.info(f"Video này tốn {charged:,} Vox — ví còn "
                        f"{balance:,} Vox")
        except Exception as e:  # noqa: BLE001 — video sắp xuất xong, không chặn
            logger.warning(f"Chưa chốt được lượt trả phí ({e}) — video vẫn "
                           "hoàn chỉnh; lượt này sẽ tự chốt sau, không tính "
                           "thêm Vox")
        # Mở khóa bằng khóa còn trong RAM — kể cả khi commit lỗi mạng, người
        # dùng đã trả đủ tiền nên dữ liệu thuộc về họ. video_context.json
        # được mã hóa ngay lúc phân tích (ngoài marker) nên mở riêng.
        if not key:
            return
        try:
            if securestore.is_locked(work_dir):
                done = securestore.unlock_all(work_dir, key)
                if done:
                    logger.info(f"Đã mở khóa {len(done)} file dữ liệu "
                                "của dự án")
            ctx = data_path(work_dir, "video_context.json")
            if os.path.exists(ctx) and securestore.is_encrypted(ctx):
                securestore.decrypt_file(ctx, key)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Không mở khóa được file trung gian ({e}) — "
                           "chạy lại video sẽ tự mở, không tính phí "
                           "lần hai")

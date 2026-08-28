# CLAUDE.md — VoxDub Studio (voidmix)

Đây là project **VoxDub Studio**: ứng dụng desktop Windows lồng tiếng Việt tự động cho
video nước ngoài (YouTube/TikTok/Douyin/Bilibili + file local), chạy pipeline AI offline
trên máy người dùng, kèm lớp SaaS tuỳ chọn (`control_server` + `website`) cho dịch tự
động và hệ thống tín dụng "Vox".

Xem `docs/ARCH.md` cho kiến trúc chi tiết, `docs/PRD.md` cho scope sản phẩm,
`docs/PLAN.md` cho roadmap nâng cấp hiện tại (mini-spec theo `MINI_SPEC_PLAYBOOK.md`).

## Stack

- **autodub/** — Python ≥3.10, thư viện thuần (không phụ thuộc GUI). yt-dlp, faster-whisper,
  sherpa-onnx (Paraformer), Demucs, VieNeu (ONNX TTS), Playwright (Douyin), ffmpeg (subprocess).
- **autodub_gui/** — PySide6 desktop app, entry `autodub-gui` (`app.py:main()`).
- **control_server/** — Node 20, Fastify 5, Mongoose 8 (MongoDB). Serve `website/dist`
  cùng process.
- **website/** — React 18, Vite 5, Tailwind, Zustand, react-router.
- **Đóng gói**: PyInstaller onedir (`autodub.spec`) + `.bat` script cài đặt/chạy. **Chỉ
  Windows** hiện tại.
- **Test**: pytest cho `autodub/` + `autodub_gui/` (2224 test); `control_server` chạy
  `npm test` (527 test, một `mongod` dùng chung qua `tests/chay.js`); `website` chưa có
  test.
- **Máy mới / workspace vừa reset**: chạy `bash scripts/cai_moi_truong_test.sh` trước.
  Thiếu `libGL`/`ffmpeg` thì `pytest` nôn ra hàng chục lỗi import rời rạc trông y như
  lỗi mã — nay `tests/conftest.py` chặn sớm và in đúng câu lệnh chữa.

> Lưu ý stack lệch chuẩn AI Factory (Next.js/FastAPI/Postgres/Docker Compose) — đã gate
> qua `request_tech_exception`, xem `.vibe/audit.json` cho trạng thái duyệt.

## Nguyên tắc thiết kế đã có trong code (giữ nguyên khi sửa)

- Mỗi engine nặng (Whisper, VieNeu, Paraformer, Demucs GPU) chạy trong **venv con riêng**
  (`.venv-whisper`, `.venv-vieneu`, `.venv-asr`, `.venv-gpu`) qua subprocess, để giữ
  bundle PyInstaller nhẹ và tránh xung đột dependency.
- Mọi artifact trung gian cache trên đĩa dưới `output/VN/<timestamp>_vi/data/` — pipeline
  resume-safe, script cài đặt idempotent.
- `saas_client.is_configured()` (tức `VOXDUB_API_URL` có set hay không) là **cổng duy
  nhất** phân biệt chế độ local-only vs SaaS — không rải điều kiện tương đương ở chỗ khác.
- `tokens.py` là nguồn màu QSS duy nhất cho GUI — không hardcode màu ở nơi khác.
- Không suy đoán capability platform khi thiếu evidence — pipeline phải degrade trung
  thực (vd Paraformer lỗi → fallback Whisub có log rõ, không giả im lặng).

## Identity

Khi cần email/owner/author cho bất kỳ artifact nào (commit, report, task), đọc từ env
theo quy ước org-wide trong `~/.claude/CLAUDE.md` — **không** hardcode hay đoán từ context.

## Việc cần làm khi nhận task trong project này

1. Đọc `docs/PLAN.md` để biết mini-spec nào đang active và guardrails của nó.
2. Đọc guardrails của mini-spec trước khi code — không mở rộng phạm vi ngoài gap đã
   xác nhận trong mini-spec đó.
3. Sau khi code xong: chạy `pytest` liên quan (`autodub/`) hoặc `npm test` (`control_server`),
   cập nhật `docs/TEST_LOG.md`/`docs/ARCH.md`/`docs/API.md` nếu có thay đổi contract.

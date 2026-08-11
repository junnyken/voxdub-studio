# PRD — VoxDub Studio (voidmix)

Status: **Draft** (sinh từ audit code hiện có 2026-08-10 — cần chủ dự án review & approve
trước khi coi là chốt, theo quy trình `/start audit`)

## 1. Bối cảnh & vấn đề

Video nước ngoài (đặc biệt tiếng Trung — TikTok/Douyin/Bilibili) không có bản lồng tiếng
Việt chất lượng, người xem phải đọc phụ đề hoặc dựa vào lồng tiếng thủ công tốn kém
(editor, diễn viên lồng tiếng, thời gian). VoxDub Studio giải quyết bằng pipeline AI
tự động: tải video → tách nhạc nền → nghe-chép → dịch → đọc bằng giọng Việt (TTS) → khớp
thời gian → xuất video hoàn chỉnh, chạy ngay trên máy người dùng.

## 2. Người dùng mục tiêu

- **Content creator / editor cá nhân**: cần lồng tiếng nhanh video nước ngoài để đăng lại
  (re-upload) trên kênh Việt, không có ngân sách thuê dịch/lồng tiếng.
- **Nhóm nhỏ/agency sản xuất nội dung**: xử lý batch nhiều video, cần voice library và
  chỉnh sửa từng câu (editor) để đảm bảo chất lượng trước khi xuất bản.
- **Vận hành nội bộ (chủ dự án)**: qua `control_server`/`website`, bán Vox credit cho
  tính năng auto-translate + metadata generation.

## 3. Mục tiêu & success metrics

- Sản phẩm hiện tại (v2.1.0): pipeline dubbing end-to-end chạy được offline, chất lượng
  đủ dùng thật (đã có 546 test, engineering polish rõ — không phải MVP thô).
- Chưa có success metrics định lượng nào được ghi nhận trong code/README (không có
  analytics/telemetry usage nào ngoài audit log phía `control_server`). Đây là gap cần
  mini-spec riêng nếu muốn đo lường thật (xem `docs/PLAN.md`).

## 4. User journeys chính (đã implement)

1. **Lồng tiếng 1 video**: dán link/chọn file → chọn giọng đọc → chọn preset chất lượng
   → chạy → nhận video đã lồng tiếng (nhạc nền gốc giữ nguyên) + phụ đề + editor để tinh
   chỉnh từng câu.
2. **Dịch thủ công**: pipeline dừng ở bước ASR, ghi `TRANSLATE_PENDING.txt` với prompt
   sẵn để người dùng tự dịch bằng ChatGPT/Gemini, dán lại `transcript_vi.json` để tiếp tục.
3. **Dịch tự động (SaaS)**: nếu cấu hình `VOXDUB_API_URL`, pipeline tự gọi
   `control_server` (3-pass analyze→translate→review) — tốn Vox credit.
4. **Batch nhiều video**: nhập danh sách URL (có thể chỉ định giọng riêng từng dòng) →
   xử lý tuần tự với prefetch, resume an toàn khi crash.
5. **Mua Vox credit**: qua `website` (PayOS) → nhận activation key → dán vào app → Vox
   balance tăng → dùng cho auto-translate/metadata.

## 5. Entities chính

- **Project** (local): 1 lần chạy dubbing, lưu tại `output/VN/<timestamp>_vi/`, có
  `data/` chứa mọi artifact trung gian.
- **Device** (server): định danh bằng machine fingerprint SHA-256, không có tài khoản
  người dùng.
- **ActivationKey / Order / Vox balance** (server): hệ tín dụng trả trước.
- **Voice** (local + server catalog): giọng VieNeu (bundled/cloned) hoặc CapCut.

## 6. Phạm vi hiện tại (đã có, không phải làm lại)

Xem `docs/ARCH.md` §2 cho danh sách đầy đủ giai đoạn pipeline đã implement (download,
tách nhạc, ASR đa engine, dịch 2 đường, TTS 2 engine, timing, phụ đề, mux, editor, batch).
Toàn bộ đã DONE, không có stub/TODO tồn đọng trong code.

## 7. Gap đã xác nhận qua audit (input cho roadmap nâng cấp)

Chi tiết đầy đủ + ưu tiên nằm ở `docs/PLAN.md`. Tóm tắt các nhóm gap:

- **Chất lượng lõi**: "che chữ gốc" chỉ là boxblur thủ công (không phải OCR/inpainting
  tự động); ngôn ngữ nguồn giới hạn 4 lựa chọn dù Whisper hỗ trợ ~100; không có ngôn ngữ
  đích nào khác ngoài tiếng Việt; auto-translate không có đường local/offline.
- **Nền tảng & phân phối**: chỉ đóng gói Windows, không Linux/macOS/Docker cho pipeline.
- **Thương mại hoá**: README không làm rõ bản `.exe` chính thức mặc định chạy trên hệ
  Vox trả phí; logic hold/credit xen trong `pipeline.py` core, chưa tách lớp OSS/SaaS.
- **Nền tảng kỹ thuật & vận hành**: `control_server` thiếu test tích hợp DB, `website`
  không có test nào; thiếu docs chuẩn (đã bắt đầu khắc phục qua đợt audit này); dependency
  thừa (`google-genai` không còn dùng).

## 8. Ngoài phạm vi (out of scope, tường minh)

- Không đổi ngôn ngữ lập trình lõi (Python cho pipeline, Node cho server) — chỉ nâng
  cấp trong nền tảng hiện có.
- Không cam kết đưa vào chuẩn stack Next.js/FastAPI/Postgres của AI Factory (đã gate
  tech exception cho stack hiện tại — xem `.vibe/audit.json`).

## 9. Rủi ro / câu hỏi mở

- **Bản quyền/đạo đức**: pipeline tải video từ nền tảng thứ 3 (yt-dlp, Douyin scraping)
  và nhân bản giọng nói (voice cloning) — README đã có cảnh báo nhưng chưa có kiểm soát
  kỹ thuật (vd rate-limit, watermark, consent check). Cần quyết định mức độ can thiệp.
- **Minh bạch mô hình kinh doanh**: cần chủ dự án quyết định có công bố rõ ràng bản
  `.exe` chính thức chạy trên hệ trả phí hay giữ nguyên hiện trạng.
- **Ưu tiên nền tảng**: mở rộng Linux/macOS có đáng đầu tư so với việc đào sâu chất
  lượng Windows hiện tại? (Roadmap trong `docs/PLAN.md` đặt đây là phase dài hạn, chưa
  chốt.)

## 10. Roadmap

Xem `docs/PLAN.md` — toàn bộ được cấu trúc theo `MINI_SPEC_PLAYBOOK.md`, chia phase
ngắn hạn/trung hạn/dài hạn, mỗi mini-spec đủ chi tiết để bắt tay code ngay.

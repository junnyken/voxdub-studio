# H1 — Hồ sơ Brand (nền tảng multi-tenant cho Phase H mới)

> **Trạng thái (08/09/2026): XONG — Scope A/B/C/D đều chạy thật.** Entity
> `BrandProfile` + API `/v1/brand-profiles` (cách ly theo thiết bị, có test
> chéo thiết bị thật) + trang **Hồ sơ Brand** trong `autodub_gui`. Hai phát
> hiện đổi cách đọc spec khi audit: (1) không có model "Account" nào trong
> dự án — "tài khoản VoxDub" của spec CHÍNH LÀ `Device` (xem docs/ARCH.md
> §3); (2) UI thuộc **desktop app**, không phải `website/` (đó là trang bán
> hàng + quản trị, không phải cổng khách hàng tự quản lý dữ liệu). Chi tiết
> đầy đủ, số liệu test, và bằng chứng hồi quy đỏ/xanh ở `docs/TEST_LOG.md`
> mục "H1 — Hồ sơ Brand, nền tảng multi-tenant Phase H".
>
> **Chưa có tác vụ nào ĐỌC hồ sơ này** — đây chỉ là nền tảng lưu trữ. H2
> (trích flow từ video đối thủ), H3 (viết lại kịch bản, cần cả H1 và H2),
> H4 (dựng video, gắn hồ sơ vào `ProductSceneVideoJob`) đều CHƯA làm.

## Context

Sáng kiến mới "Viral Flow Clone & Brand Rewrite" (Phase H mới — tên trùng
với "Phase H — Trải nghiệm người dùng cuối" đã có sẵn trong `docs/PLAN.md`
là trùng hợp đặt tên, không phải cùng một chuỗi công việc; theo đúng tiền lệ
các luồng mini-spec chữ cái độc lập đã dùng trong dự án này, vd G1-G3).

Bốn quyết định đã chốt với chủ dự án trước khi viết spec:

1. Output cuối là **VIDEO HOÀN CHỈNH**, nối vào pipeline ảnh sản phẩm/dựng
   video ngắn đã có (C3) — không chỉ trả về văn bản kịch bản.
2. Tính năng bán cho **NHIỀU khách VoxDub khác nhau** — mỗi khách có
   brand/sản phẩm riêng, không phải cấu hình cứng cho một brand duy nhất.
3. Nguồn học flow là video **ĐỐI THỦ/KOL VIRAL** trên mạng (không chỉ video
   của chính người dùng) — học NHỊP/CẤU TRÚC, không sao chép câu chữ; ranh
   giới này phải RÕ trong sản phẩm, không chỉ là lời khuyên trong tài liệu.
4. Bắt buộc đọc được caption/chữ overlay trên hình (tái dùng module OCR
   C49-C64) — mức phân tích hiệu ứng hình ảnh/chuyển cảnh CHƯA xác nhận
   cần, để ngoài phạm vi bản đầu.

Trạng thái hạ tầng đã xác nhận THẬT (không phải giả định của spec gốc — xem
mục Audit Before Build trong TEST_LOG.md để biết chỗ nào spec gốc đoán đúng,
chỗ nào cần sửa lại):

- Không có khái niệm "brand"/"khách hàng cuối của khách hàng" nào trong dự
  án trước H1 — Vox/thiết bị hiện tại đều gắn với MỘT thiết bị VoxDub, và
  **thiết bị chính là đơn vị danh tính duy nhất** (không có model Account).
- Cổng trợ lý AI 9 tác vụ đã có khuôn "app gửi tên tác vụ, câu lệnh nằm máy
  chủ" — H1 không đổi khuôn này, chỉ chuẩn bị DỮ LIỆU để H3 đọc.
- `ProductSceneVideoJob` (C3) đã có khái niệm chọn ảnh SAFE để ghép video —
  chưa có khái niệm "brand" gắn với ảnh/sản phẩm (vẫn chưa có sau H1 — đó
  là phạm vi H4).

## Goal

Một nơi lưu trữ hồ sơ brand (tên, sản phẩm, tone giọng, đối tượng khách,
USP, ràng buộc không được nói) mà MỘT thiết bị VoxDub có thể tạo NHIỀU hồ
sơ khác nhau — để H3/H4 biết "viết cho ai" mà không cần người dùng gõ tay
lại mỗi lần.

## Constraints (Guardrails)

1. Một thiết bị có thể có NHIỀU hồ sơ brand — không giới hạn cứng 1
   brand/thiết bị.
2. Hồ sơ brand KHÔNG được chia sẻ/nhìn thấy giữa các thiết bị khác nhau —
   dữ liệu riêng tư, lưu trên máy chủ (khác quyết định "không lưu ảnh sản
   phẩm trên máy chủ" của C1) vì cần dùng lại nhiều lượt/nhiều lần, nhưng
   phải cách ly đúng theo thiết bị.
3. Không tự động điền hồ sơ brand từ dữ liệu suy luận — người dùng phải tự
   nhập hoặc xác nhận, đúng nguyên tắc đã áp dụng cho `character_name`.
4. Hồ sơ brand phải có trường ghi rõ RÀNG BUỘC KHÔNG ĐƯỢC NÓI — bắt buộc
   CÓ MẶT (mảng, có thể rỗng) khi tạo/sửa, không bắt buộc CÓ NỘI DUNG. H3
   sẽ đọc trường này để chặn khi viết lại kịch bản.
5. Không xây hồ sơ brand thành một trang quản lý phức tạp kiểu CRM — chỉ đủ
   trường cho H3/H4 đọc được.
6. Không đổi cấu trúc `ProductSceneVideoJob`/ảnh sản phẩm hiện có trong H1 —
   gắn hồ sơ brand vào job video là phạm vi H4.

## Scope (đã build đúng theo mục này — xem TEST_LOG.md cho chi tiết mã)

- **A. Domain model**: `BrandProfile` — `ownerDeviceId`, `tenBrand`,
  `moTaSanPham`, `doiTuongKhach`, `toneGiong`, `usp`,
  `rangBuocKhongDuocNoi`. 1 thiết bị → N `BrandProfile`.
- **B. Service**: CRUD cơ bản; `rangBuocKhongDuocNoi` bắt buộc có mặt khi
  tạo/sửa (ép ở tầng schema Fastify, không chỉ UI).
- **C. API**: `GET/POST /v1/brand-profiles`, `PUT/DELETE /v1/brand-profiles/:id`
  — `ownerDeviceId` LUÔN lấy từ token, không nhận từ client. Chi tiết đầy
  đủ ở `docs/API.md`.
- **D. UI**: trang **Hồ sơ Brand** trong `autodub_gui` (desktop app, không
  phải `website/`) — danh sách + form tạo/sửa, không có dashboard riêng.

## Design Choice

- `toneGiong` là văn bản tự do (không phải enum đóng) — chưa đủ dữ liệu
  thật về các tone phổ biến; văn bản tự do linh hoạt hơn cho H3 đọc bằng AI.
- Không tự suy luận trường nào từ video mẫu — giữ nguyên nguyên tắc "người
  dùng tự nhập/xác nhận dữ liệu quan trọng".

## Test Plan / Live Verification (đã chạy thật — xem TEST_LOG.md)

Unit + integration (API thật, `app.inject()`, hai thiết bị thật qua
`deviceService.registerDevice`) + regression (gỡ điều kiện sở hữu → xác
nhận đỏ đúng 3 test cách ly, rồi khôi phục). Không cần "live verification"
kiểu 2 tài khoản test thật ngoài bộ test tự động — hệ thống này không có
khái niệm tài khoản/đăng nhập để tạo thủ công, phép thử integration bằng
2 device token thật (không mock) đã đóng vai trò tương đương.

## Success Criteria — đã đạt cả bốn

- Một thiết bị tạo được nhiều hồ sơ brand, mỗi hồ sơ độc lập. ✅
- Không có đường nào (UI hay API) để một thiết bị đọc/sửa/xoá hồ sơ của
  thiết bị khác. ✅ (có test hồi quy chứng minh)
- Hồ sơ có đủ trường để H3 đọc được. ✅
- Không có trường nào bị tự động điền bởi hệ thống. ✅

## Remaining Limits / Follow-ups

- Out-of-scope H1: gắn hồ sơ brand vào `ProductSceneVideoJob` hoặc bất kỳ
  tác vụ AI nào — phạm vi H3/H4, chưa làm.
- H2 không phụ thuộc H1 — có thể build song song. Chỉ H3 cần CẢ H1 VÀ H2.
- **Giới hạn thật phát sinh khi build (không có trong spec gốc)**: hồ sơ
  brand gắn với THIẾT BỊ, không phải một đăng nhập di động được — cài lại
  app hoặc đổi máy sẽ mất quyền truy cập hồ sơ cũ (cùng giới hạn Vox đã có
  từ trước, không phải giới hạn mới riêng cho H1, nhưng đáng nói rõ vì
  spec gốc dùng chữ "tài khoản" có thể gây hiểu lầm là có đăng nhập di
  động được).

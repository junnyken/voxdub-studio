# G2 — PoC: ASR có thật sự mất nội dung khi nhiều người nói chồng tiếng? (bản sẵn sàng chạy)

## Lưu ý thực thi trước tiên (đọc trước khi bắt đầu)

- Đây là spec **PoC/benchmark**, không phải spec build production. Mục tiêu
  là có **số liệu thật** để quyết định có đáng đầu tư sửa hay không — không
  phải viết tính năng "tách giọng chồng tiếng" ngay.
- **KHÔNG bắt đầu Scope B/C nếu chưa có GPU thật.** Model tách giọng nói
  (speech separation) và pyannote diarization thật đều cần GPU để chạy đủ
  nhanh trên video dài — sandbox phát triển hiện tại (Linux, không GPU rời)
  **không đủ điều kiện chạy PoC này**, giống hệt giới hạn đã gặp ở V30/V32a
  (lipsync). Xác nhận bằng `nvidia-smi` + `torch.cuda.is_available()` TRƯỚC
  khi cài bất kỳ thứ gì.
- Nếu chưa có tài khoản HuggingFace + đã "Agree and access" model
  `pyannote/speaker-diarization-3.1`, việc ĐẦU TIÊN của Scope A là làm việc
  đó và lấy `HF_TOKEN` thật — không tự chế giả lập kết quả diarization.
- Không tự tải thêm video mẫu ngoài phạm vi G1 nếu chưa cần — 3 video G1 đã
  có (kèm bản chép JSON) đủ làm bộ mẫu ban đầu, tái dùng để đỡ tốn công
  chuẩn bị dữ liệu (đúng gợi ý "G3 có thể tái dùng dữ liệu G1" trong chính
  spec G1).

## Context

Dự án: VoxDub Studio, v3.16.5+. Đọc trước: `docs/TEST_LOG.md` mục "G1 —
Điều tra nghe chép thiếu câu" và mục tiếp theo "G1 tiếp — thử biến nhiều
người nói chồng tiếng" (08/09/2026), `docs/PLAN.md` mini-spec V26 (dòng
~2060-2170, diarization) và V32a (dòng ~2512-2612, tiền lệ PoC-trước-build).

**Trạng thái đã xác nhận từ G1, không giả định lại:**

- Chủ dự án báo lỗi thật "thiếu câu". 5 lượt thử có kiểm soát (30s, 53s,
  16 phút, 22 phút, 8,9 phút phim nhiều người nói) — **KHÔNG lượt nào xác
  nhận được mất nội dung thật** khi kiểm tay đối chiếu 2 bản chép đầy đủ.
  Mọi khác biệt đều là "cắt câu khác nhau" (VAD/nhạc nền), không phải "mất
  câu".
- Video có chồng tiếng nhiều nhất đã thử (phim, 4-5 người, chen lời nhanh)
  cho chênh SỐ TỪ cao hơn ~6-18 lần so với video phỏng vấn êm (1,3% vs
  0,07-0,2%) — **xu hướng đúng hướng giả thuyết nhưng CHƯA đủ mạnh để kết
  luận có bug**. 2/2 mẫu kiểm tay thủ công vẫn là "cắt khác", không "mất".
- Giới hạn kiến trúc ASR một-kênh trước chồng tiếng thật sự (2 giọng cùng
  lúc, không phải chen lời cách nhau vài trăm ms) là hạn chế **đã biết rộng
  rãi trong ngành**, độc lập với 5 lượt thử trên — nhưng 5 video đã thử có
  thể chưa chạm đúng mức độ chồng tiếng nặng đó.
- Hạ tầng liên quan đã có: diarization (`autodub/speech/diarization.py`,
  pyannote `speaker-diarization-3.1`) chạy **SAU** ASR, chỉ gán giọng TTS —
  **không dùng để cải thiện ASR**. pyannote có tín hiệu overlap sẵn
  (`speaker_diarization` output) nhưng bị `assign_speakers()` vứt bỏ (chỉ
  lấy 1 nhãn/segment theo % overlap lớn nhất). Demucs (tách nhạc nền) không
  giải quyết được bài toán tách NHIỀU GIỌNG NGƯỜI — khác bài toán hoàn
  toàn, cần model khác (speech separation, vd SepFormer/Conv-TasNet), hiện
  **chưa có bất kỳ dây nối nào trong repo**.
- Diarization (V26) **chưa từng chạy thật với model pyannote thật** ở bất
  kỳ đâu theo tài liệu (sandbox không có `HF_TOKEN`, model gated trên HF
  Hub) — đây là điều kiện tiên quyết phải làm trước khi dùng diarization
  làm nền cho bất kỳ giải pháp overlap nào.

## Goal

Có số liệu benchmark THẬT trả lời hai câu hỏi, đủ để quyết định có mở
mini-spec build production (G3?) hay không:

1. Trên video có chồng tiếng NẶNG thật sự (không chỉ chen lời nhanh), ASR
   hiện tại (Whisper) có thật sự mất nội dung đáng kể không — đo bằng số
   liệu, không suy đoán?
2. Nếu có mất: chèn một bước tách giọng nói (speech separation) TRƯỚC ASR
   có cải thiện được không, cải thiện bao nhiêu, và chi phí (thời gian xử
   lý, VRAM) có chấp nhận được cho một tính năng opt-in không?

## Constraints (Guardrails)

1. **PHẢI chạy trên GPU THẬT** cho Scope B/C — gate chặn cứng, xem Lưu ý
   thực thi.
2. Không tự chọn model tách giọng nói mà không audit trước (Scope A) — có
   thể có lựa chọn giấy phép/phần cứng phù hợp hơn giả định ban đầu
   (SepFormer/Conv-TasNet chỉ là gợi ý, không phải quyết định cuối).
3. PoC cô lập hoàn toàn, đúng khuôn V32a: venv mới (`.venv-speech-sep`?) +
   script trong `scripts/research/` — KHÔNG đụng `pipeline.py` chính, KHÔNG
   merge vào requirements chính, KHÔNG host model weights trong repo.
4. Trước khi benchmark tách giọng, PHẢI **live-verify diarization pyannote
   thật lần đầu tiên** (chưa ai làm — xem Context) trên chính video PoC, vì
   cần dùng tín hiệu overlap của nó để biết ĐOẠN NÀO cần tách, tránh chạy
   model nặng cho toàn bộ video.
5. Cần tối thiểu 1 video chồng tiếng NẶNG THẬT SỰ (hai người nói cùng lúc
   kéo dài ≥1-2 giây, không phải chen lời) — nếu 3 video G1 hiện có chưa đủ
   nặng (khả năng cao, xem Context), phải tìm/hỏi thêm TRƯỚC khi kết luận
   PoC, không benchmark trên video chưa đủ điều kiện rồi kết luận nhầm
   "không cải thiện được gì".
6. Không cam kết production ở đợt này — Success Criteria chỉ đòi khuyến
   nghị go/no-go kèm số liệu, giống V32a.
7. Ghi lại MỌI lượt đo vào `docs/TEST_LOG.md`, kể cả lượt không cải thiện
   gì hoặc benchmark thất bại.

## Scope

**A. Audit trước khi chọn model (không benchmark ngay)**
- Khảo sát 2-3 model speech-separation mã nguồn mở (giấy phép + yêu cầu
  phần cứng công khai) — tối thiểu SepFormer (SpeechBrain), Conv-TasNet;
  audit giấy phép TRƯỚC (bài học V30: license loại được nhiều lựa chọn
  ngay từ đầu, đỡ benchmark uổng công).
- Đọc code diarization hiện có (`autodub/speech/diarize_worker.py`) để biết
  chính xác cách lấy `speaker_diarization` (bản CÓ overlap, hiện bị vứt) —
  tái dùng, không viết lại từ đầu.

**B. Live-verify diarization pyannote thật (lần đầu tiên, điều kiện tiên
quyết — Constraint 4)**
- `scripts/setup_diarization.py --hf-token ...` trên máy có GPU thật.
- Chạy trên 1-2 video G1 đã có (16 phút hoặc phim 8,9 phút) — xác nhận
  pyannote thật chạy được, đo thời gian xử lý thật (đối chiếu
  `_DIARIZE_TIMEOUT_S = 1800` hiện là ước lượng chưa kiểm chứng).
- Trích xuất `speaker_diarization` (bản CÓ overlap) — liệt kê các đoạn
  overlap thật tìm được trên video phim 8,9 phút, đối chiếu bằng tai/mắt
  (xem lại đúng đoạn đó trong video) xem có đúng là chồng tiếng không.

**C. Benchmark tách giọng + ASR lại (chỉ sau khi B xong và tìm được ≥1
video có overlap thật đủ nặng — Constraint 5)**
- Với mỗi đoạn overlap tìm được ở B: cắt đoạn đó ra, chạy qua model tách
  giọng nói đã chọn ở A, được N track giọng riêng.
- Chạy Whisper (`small`, cùng cấu hình G1) trên: (a) đoạn gốc chưa tách,
  (b) từng track đã tách riêng. So số từ + kiểm tay nội dung.
- Đo: VRAM peak, thời gian xử lý/giây audio của bước tách.

**D. Báo cáo + khuyến nghị**
- Bảng: đoạn overlap nào, tách có ra thêm nội dung không (số từ trước/sau),
  chi phí xử lý.
- Khuyến nghị go/no-go rõ ràng cho việc build production (G3), kèm phạm vi
  cụ thể nếu go (vd "chỉ áp dụng khi diarization phát hiện overlap >X giây
  liên tục, bỏ qua chen lời ngắn").

**E. Không có API contract mới. Không có UI surfaces mới** (PoC nghiên
cứu, giống V32a).

## Audit Before Build

- Xác nhận GPU thật có sẵn TRƯỚC Scope B (Constraint 1).
- Đọc lại 3 file JSON bản chép đã có từ G1
  (`docs/TEST_LOG.md` trỏ tới, hoặc chạy lại `so_sanh_nghe.py --ra` nếu bản
  cũ không còn) để xác nhận lại bằng mắt: video phim 8,9 phút có đoạn nào
  THẬT SỰ hai giọng chồng ≥1 giây không, hay toàn bộ chỉ là chen lời nhanh
  (khả năng cao theo phân tích ở Context) — quyết định luôn cần thêm video
  mẫu mới hay không TRƯỚC khi bắt đầu Scope B.

## Design Choice

Theo đúng tiền lệ V30→V32a (lipsync): PoC hẹp, benchmark thật trước, không
thiết kế kiến trúc production ở đợt này. Điểm khác V32a: ở đây có SẴN một
phần hạ tầng (diarization, dù chưa live-verify) nên PoC không bắt đầu từ
số 0 — B tận dụng lại, không xây diarization mới.

## Test Plan

"Test" là độ tin cậy số liệu đo thật (giống V32a, không phải unit test):
1. B xong: diarization pyannote thật chạy được, có log thời gian + overlap
   tìm được.
2. C xong (nếu tìm được video đủ điều kiện): bảng số từ trước/sau tách,
   trên ≥1 đoạn overlap thật.
3. Nếu Audit Before Build kết luận 3 video G1 KHÔNG có overlap đủ nặng:
   DỪNG ở đây, ghi rõ vào TEST_LOG, hỏi chủ dự án video mẫu mới trước khi
   làm tiếp Scope B/C (đúng guardrail G1 "không tự chọn video mà không
   biết đặc điểm khớp báo cáo").

## Success Criteria

- Kết luận rõ một trong ba: (a) có overlap thật + tách giúp lấy lại nội
  dung đáng kể → khuyến nghị go cho G3 kèm phạm vi; (b) có overlap thật
  nhưng tách không cải thiện đáng kể (model không đủ tốt, hoặc ASR vốn đã
  nghe được nhờ ngữ cảnh) → khuyến nghị no-go, ghi rõ lý do; (c) không tìm
  được video overlap đủ nặng để test → dừng, hỏi chủ dự án, không kết luận
  go/no-go từ dữ liệu không đủ điều kiện.
- `docs/TEST_LOG.md` đủ chi tiết để người khác đọc lại không cần hỏi lại
  từ đầu.

## Remaining Limits / Follow-ups

- Out-of-scope G2: build production tách giọng nói tích hợp vào
  `pipeline.py` — đó là G3, chỉ mở sau kết luận (a).
- Nếu kết luận (b) hoặc (c): không tạo G3, quay lại theo dõi báo cáo lỗi
  thật từ người dùng thay vì đầu tư tiếp vào giả thuyết chưa đủ bằng chứng.
- G2 phá giả định "mọi engine core đều CPU-optional" của dự án (giống
  MuseTalk lipsync) — nếu đi tới G3, đây là quyết định kiến trúc cần chủ
  dự án xác nhận rõ (chấp nhận tính năng GPU-only, opt-in), không tự quyết.

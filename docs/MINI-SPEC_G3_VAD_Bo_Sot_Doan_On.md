# G3 — VAD bỏ sót cả đoạn khi âm thanh ồn (xác nhận + sửa) (bản sẵn sàng chạy)

> **Trạng thái (08/09/2026): ĐÓNG — Scope A+B+C đều xong, verify bằng
> `transcribe()` production thật.** Hạ `threshold` VAD 0.5→0.3 (Scope B) +
> cơ chế tự vá khoảng trống bất thường (Scope C, nghe lại tắt hẳn VAD).
> Verify trên đúng video Sing 2: toàn bộ khoảng trống 38 giây đã mất trước
> đây nay được lấp đầy, khớp (và vài chỗ nhiều hơn) chuẩn đối chứng VAD-tắt-
> hoàn-toàn của G1. Chi tiết đầy đủ ở `docs/TEST_LOG.md` mục "G3 Scope C
> thực hiện xong — ĐÓNG NỐT".

## Lưu ý thực thi trước tiên (đọc trước khi bắt đầu)

- Đây là spec **xác nhận nguyên nhân rồi sửa**, khác G1/G2 (thuần điều
  tra) — vì lần này đã có bằng chứng MẤT NỘI DUNG THẬT, không phải suy
  đoán. Nhưng vẫn phải xác nhận đúng cơ chế TRƯỚC khi đổi tham số, không
  đổi rồi hy vọng.
- **Không cần GPU, không cần model mới** — khác hẳn G2. Toàn bộ thực hiện
  được bằng CPU + faster-whisper đã có sẵn, nghĩa là làm được ngay, kể cả
  trong sandbox không GPU.
- **Đổi MỘT tham số VAD mỗi lần** (đúng phương pháp G1) — không đổi nhiều
  tham số cùng lúc rồi không biết cái nào có tác dụng.
- Video mẫu tái dùng từ G1 (đã có sẵn, không cần tải lại): *Sing 2* (khoảng
  mất 53,8s-91,5s — trọng tâm), *Kung Fu Panda*, và 2 video phỏng vấn êm
  (16 phút, 22 phút) — **BẮT BUỘC chạy lại cả 4 video sau khi đổi bất kỳ
  tham số nào**, không chỉ chạy video lỗi — mục đích là sửa mà KHÔNG làm
  hỏng 4 video đang chạy tốt (thêm hallucination giả trong đoạn nhạc/im
  lặng, đúng lớp lỗi "Lọc câu bịa" đã từng gặp — xem FEATURES.md §3.4).

## Context

Dự án: VoxDub Studio, v3.16.5+. Đọc trước: `docs/TEST_LOG.md` mục "G1 tiếp
— TÁI HIỆN ĐƯỢC THẬT" (08/09/2026), và `docs/MINI-SPEC_G2_POC_ASR_Chong_Tieng.md`
(hướng đã cân nhắc nhưng KHÔNG còn ưu tiên số 1 sau phát hiện này).

**Bằng chứng đã có, không giả định lại:**

- Video *Sing 2* (cảnh cả nhóm chạy trốn, nhạc nền + hiệu ứng dồn dập):
  bản ASR thật của app (VAD bật, `min_silence_duration_ms=500`, ngưỡng mặc
  định `threshold=0.5`) có khoảng TRỐNG HOÀN TOÀN 53,8s→91,5s (~38 giây),
  mất sạch 6 câu. Cùng đoạn đó chạy KHÔNG lọc VAD thì nghe được đầy đủ.
- Âm lượng đoạn mất (`ffmpeg volumedetect`): mean −24,1dB, gần giống hệt
  đoạn nghe bình thường (−22,7dB) — **không phải do quá to**.
- Cấu hình VAD sản xuất thật, xác nhận đúng 2 nơi dùng chung tham số:
  `autodub/speech/transcriber.py:633-634` (whisper trong-tiến-trình) và
  `autodub/speech/asr_whisper_worker.py:277-278` (worker con) — cả hai
  cùng `vad_filter=True, vad_parameters={"min_silence_duration_ms": 500}`.
  Đây là cấu hình từ commit NỀN TẢNG đầu tiên của dự án (`git log -S`),
  không có lý do lịch sử cụ thể (không phải sửa cho một bug trước đó) —
  chỉ là giá trị mặc định hợp lý ban đầu, **không có ràng buộc phải giữ
  nguyên**.
- `faster_whisper.vad.VadOptions` có các tham số tinh chỉnh được (đọc trực
  tiếp signature, không suy đoán từ tài liệu cũ):
  `threshold=0.5, neg_threshold=None, min_speech_duration_ms=0,
  max_speech_duration_s=inf, min_silence_duration_ms=2000, speech_pad_ms=400`.
  App hiện chỉ ghi đè MỘT tham số (`min_silence_duration_ms=500`), mọi
  tham số khác dùng mặc định — bao gồm `threshold=0.5`, tham số nghi ngờ
  chính (ngưỡng xác suất "đây là giọng nói" của model Silero VAD).
- `align_whisper_worker.py:172` và `align.py:116` có `vad_filter=False` —
  nhưng đó là bước CANH LẠI PHỤ ĐỀ trên audio ĐÃ BIẾT có lời (comment "clip
  đã là lời nói thuần"), khác ngữ cảnh với bước NGHE ban đầu đang lỗi —
  không phải bằng chứng "cứ tắt VAD là xong", vì bước nghe ban đầu cần VAD
  để không nghe cả những đoạn thật sự im lặng dài (tiết kiệm thời gian xử
  lý, tránh Whisper tự bịa câu trong im lặng — xem C-series lọc câu bịa).

## Goal

1. Xác nhận CƠ CHẾ: có đúng là `threshold=0.5` mặc định quá cao khiến VAD
   coi đoạn 53,8-91,5s của Sing 2 là "không phải giọng nói" không? Đo bằng
   cách gọi thẳng Silero VAD lấy xác suất speech theo từng khung, không chỉ
   suy đoán từ kết quả cuối.
2. Tìm MỘT thay đổi (tham số VAD, hoặc cơ chế vá thêm) phục hồi được đoạn
   mất ở Sing 2, mà KHÔNG làm hỏng 4 video mẫu đang chạy tốt (không thêm
   câu bịa trong đoạn nhạc/im lặng thật).

## Constraints (Guardrails)

1. Đổi MỘT biến mỗi lần (Lưu ý thực thi).
2. Sau mỗi thay đổi, PHẢI chạy lại đủ 4 video mẫu G1 (không chỉ Sing 2) —
   Success Criteria đòi cả "sửa được" LẪN "không hỏng cái đang tốt".
3. Không đổi `min_silence_duration_ms` xa khỏi giá trị hiện tại (500ms) mà
   không lý do — tham số nghi ngờ chính là `threshold`, không phải tham số
   này (đã có sẵn từ trước, hoạt động ổn cho mọi video khác).
4. Nếu tinh chỉnh tham số KHÔNG đủ (vẫn mất nội dung ở ngưỡng thử hợp lý,
   vd threshold 0.5→0.2 mà vẫn mất, hoặc threshold thấp làm video êm bắt
   đầu bịa câu trong nhạc) — chuyển sang phương án B (Scope C): cơ chế phát
   hiện KHOẢNG TRỐNG bất thường sau VAD rồi tự động nghe lại đúng khoảng đó
   KHÔNG lọc VAD, thay vì đổi tham số toàn cục.
5. Test bằng số liệu (so_sanh_nghe.py hoặc gọi thẳng VAD lấy xác suất),
   không kết luận bằng nghe tay chủ quan — đúng nguyên tắc G1.
6. Ghi lại MỌI lượt thử vào `docs/TEST_LOG.md`, kể cả lượt không có tác
   dụng.
7. Nếu sửa được: PHẢI có test hồi quy (`tests/`) khoá lại đúng ca Sing 2
   (dùng đoạn audio ngắn trích từ 51-92s, không cần tải cả video vào repo
   — xem cách `tests/test_translate_local.py` xử lý dữ liệu cần model
   thật cho tham khảo phong cách, dù ở đây không cần model nặng).

## Scope

**A. Chẩn đoán trực tiếp (không đổi gì, chỉ đo)**
- Gọi thẳng `faster_whisper.vad.get_speech_timestamps` (hoặc tương đương
  nội bộ faster-whisper) trên đoạn audio 45-95s của Sing 2 với
  `threshold=0.5` mặc định — xác nhận VAD thật sự trả về KHÔNG có đoạn
  speech nào trong khoảng 53,8-91,5s (khác với suy đoán gián tiếp qua kết
  quả ASR cuối).
- Lặp lại với `threshold` giảm dần (0.5 → 0.35 → 0.2) — tìm ngưỡng mà VAD
  bắt đầu nhận ra đoạn đó CÓ giọng nói. Ghi lại xác suất speech thật VAD
  tính ra cho đoạn này (nếu lấy được) để biết nó "suýt qua ngưỡng" hay
  "sai rất xa".

**B. Nếu A tìm được ngưỡng `threshold` hợp lý phục hồi được Sing 2**
- Áp ngưỡng đó, chạy lại ĐỦ 4 video mẫu G1 bằng `so_sanh_nghe.py` (thêm
  tuỳ chọn `--vad-threshold` vào script nếu cần, hoặc sửa tạm để test).
- Nếu không video nào hỏng (không sinh câu bịa mới trong đoạn nhạc/im lặng
  của 2 video phỏng vấn) → đây là phương án được chọn, đưa vào
  `transcriber.py`/`asr_whisper_worker.py`.

**C. Nếu B thất bại (đổi threshold không đủ, hoặc gây hồi quy) — phương án
"vá khoảng trống"**
- Sau khi VAD chạy xong (theo cấu hình HIỆN TẠI, không đổi), kiểm tra
  khoảng cách giữa 2 segment liên tiếp: nếu khoảng trống > ngưỡng (đề xuất
  ban đầu 15-20 giây — cần AUDIT xem video dài nhất trong bộ test có đoạn
  im lặng THẬT tự nhiên nào dài hơn ngưỡng này không, tránh chọn nhầm
  ngưỡng gây false-positive nghe lại đoạn im lặng thật vô ích) VÀ video còn
  nội dung ở đó (không phải cuối video) → tự động chạy lại ĐÚNG đoạn đó
  KHÔNG lọc VAD (`vad_filter=False`), chèn kết quả (nếu có) vào đúng vị
  trí thời gian.
- Đây là thay đổi CÓ CODE thật vào `transcriber.py`/`asr_whisper_worker.py`
  — không phải PoC nghiên cứu như G2, vì bằng chứng đã đủ mạnh.

**D. Không có API contract mới. Không có UI surfaces mới** ở đợt này (cả
B lẫn C đều là thay đổi bên trong bước nghe, không lộ ra ngoài).

**E. Ghi nhận**: mỗi lượt thử (A/B/C) ghi vào `docs/TEST_LOG.md` — tham số
dùng, kết quả trên Sing 2, kết quả trên 3 video còn lại.

## Audit Before Build

- Đã có: cấu hình VAD sản xuất thật (2 nơi, cùng tham số), bằng chứng mất
  nội dung thật, âm lượng loại trừ được nghi ngờ "quá to" (xem Context).
- Cần làm trước Scope B: audit xem 4 video mẫu hiện có (đặc biệt 2 video
  phỏng vấn 16'/22') có đoạn NHẠC hay IM LẶNG THẬT nào có thể bị hiểu nhầm
  thành "giọng nói" nếu hạ `threshold` quá thấp — nếu có, đây là ranh giới
  trên cho thử nghiệm ở Scope A/B.

## Design Choice

Ưu tiên phương án B (đổi 1 tham số) vì đơn giản, rẻ, dễ hiểu, dễ bảo trì —
chỉ chuyển sang C (phức tạp hơn: logic phát hiện khoảng trống + lượt nghe
lại thứ hai) nếu B không đủ hoặc gây hồi quy. Đây là thứ tự ưu tiên đúng
tinh thần dự án: giải pháp đơn giản trước, phức tạp sau khi có bằng chứng
đơn giản không đủ (không tự động nhảy thẳng vào C vì "nghe an toàn hơn" mà
chưa thử B).

## Test Plan

1. Scope A: đo xác suất speech thật của VAD trên đoạn 45-95s Sing 2 ở
   nhiều `threshold` — ghi bảng threshold → có/không phát hiện speech.
2. Scope B (nếu tìm được threshold phù hợp): chạy `so_sanh_nghe.py` (hoặc
   biến thể có tham số VAD chỉnh được) trên cả 4 video mẫu, so sánh trước/
   sau đổi tham số — bảng số từ + kiểm tay đoạn nghi ngờ mới nếu số liệu
   đổi bất thường.
3. Nếu đi Scope C: viết `tests/test_vad_khoang_trong.py` — dựng audio giả
   lập có 1 đoạn giọng nói ngắn được bao bởi 2 khoảng im lặng dài hơn
   ngưỡng, xác nhận cơ chế phát hiện khoảng trống kích hoạt đúng lúc, và 1
   test âm tính (khoảng trống NGẮN hơn ngưỡng thì KHÔNG kích hoạt, tránh
   nghe lại vô ích tốn thời gian).

## Success Criteria

- Xác nhận rõ CƠ CHẾ (Scope A) bằng số liệu VAD thật, không suy đoán.
- Sing 2 (đoạn 53,8-91,5s) phục hồi được nội dung (dù không cần khớp 100%
  với bản VAD tắt — chỉ cần KHÔNG còn trống hoàn toàn).
- 3 video mẫu còn lại (Kung Fu Panda, phỏng vấn 16', 22') KHÔNG xuất hiện
  câu bịa mới hoặc thoái hoá chất lượng sau khi áp thay đổi.
- Có test hồi quy khoá lại thay đổi (Constraint 7).
- `docs/TEST_LOG.md` đủ chi tiết để người khác đọc lại không cần hỏi lại
  từ đầu.

## Remaining Limits / Follow-ups

- Không giải quyết lại bài toán "chồng tiếng nhiều người nói" — đó vẫn là
  phạm vi G2 (PoC riêng, còn treo, cần GPU). G3 chỉ giải quyết đúng cơ chế
  "VAD bỏ sót đoạn ồn", một nguyên nhân KHÁC được phát hiện trong lúc tìm
  bằng chứng cho giả thuyết chồng tiếng.
- Nếu cả B lẫn C đều không đủ (hiếm, nhưng có thể xảy ra): quay lại xem
  xét G2 (speech-separation) như phương án cuối, vì lúc đó mới thật sự cần
  tách nguồn âm thanh thay vì chỉ chỉnh cách VAD quyết định "đoạn nào có
  lời".

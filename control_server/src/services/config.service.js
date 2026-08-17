'use strict'

/**
 * Cấu hình lúc chạy — đọc AppConfig với cache TTL, có giá trị mặc định.
 *
 * Mọi nơi trong server đọc config qua đây chứ không truy vấn AppConfig trực
 * tiếp: mỗi request AI cần 3-4 khóa, không cache thì mỗi lượt dịch thêm vài
 * chục truy vấn vô ích. TTL 60 giây đủ để admin đổi giá trị mà không phải
 * restart, và đủ ngắn để không ai phải chờ lâu.
 */
const AppConfig = require('../models/AppConfig')

const TTL_MS = 60_000

/** Giá trị mặc định — nguồn sự thật khi DB chưa có khóa đó. */
const DEFAULTS = {
  'credit.enabled': true,
  'credit.vox.to.vnd': 10,
  // Số Vox tặng lần đầu mỗi thiết bị (0 = tắt hoàn toàn). Giá tính theo
  // segment (10 Vox/segment) nên quà phải đủ một video thật để dùng thử.
  'trial.vox': 2000,
  // Chống farm trial: tặng ngay `trial.upfront.vox`, phần còn lại
  // (trial.vox − upfront) chờ thiết bị sống đủ `trial.defer.hours` giờ mới
  // cấp nốt. upfront >= trial.vox nghĩa là tắt cơ chế chờ (tặng hết một lần).
  'trial.upfront.vox': 500,
  'trial.defer.hours': 24,
  // Trần thiết bị MỚI đăng ký từ cùng một IP trong 24 giờ (0 = không giới
  // hạn). Vượt trần: máy vẫn đăng ký được nhưng KHÔNG được tặng trial —
  // người thật sau NAT không bị chặn làm việc, còn farm thì hết mồi.
  'register.max.new.per.ip.day': 3,
  // ĐƠN GIÁ (Vox) — tính theo SEGMENT, không theo lượt gọi AI.
  //
  // Một video = số segment sau ASR × đơn giá. Giá chốt ngay sau ASR và không
  // đổi nữa: người dùng thấy đúng một con số, không phải bảng chi tiết theo
  // từng bước xử lý. Các lượt AI bên trong (phân tích, dịch, rà soát) là
  // chuyện nội bộ của server — vẫn ghi vào CreditHold.usage để đối soát và
  // theo dõi biên lợi nhuận, nhưng KHÔNG quyết định số tiền.
  //
  //   không bật dịch tự động → base                        = 10 Vox/segment
  //   bật dịch tự động       → base + autotranslate        = 12 Vox/segment
  //   bật tạo tiêu đề+mô tả  → cộng thêm metadata trọn gói  = +20 Vox/video
  'credit.cost.segment.base': 10,
  'credit.cost.segment.autotranslate': 2,
  'credit.cost.metadata': 20,
  // GIÁ NỘI BỘ — để ghi `CreditHold.usage` (đối soát biên lợi nhuận) và làm
  // giá dự phòng chống lạm dụng khi một lượt AI được gọi lẻ KHÔNG kèm hold.
  // Trong luồng bình thường (có hold) các số này không bao giờ trừ vào ví
  // người dùng và không lộ ra API public.
  'internal.cost.translate.per_sentence': 1,
  'internal.cost.analyze': 2,
  'internal.cost.review.per_sentence': 1,
  'internal.cost.generate_post': 5,
  // Giữ chỗ Vox (luồng wizard: hold sau ASR → commit lúc xuất video).
  'hold.enabled': true,
  'hold.ttl.hours': 48,
  'hold.sweep.interval.minutes': 30,
  // Rà soát chỉ chạm ~15% số câu — buffer cộng vào ước tính lúc hold.
  'hold.review.ratio': 0.15,
  'maintenance.mode': false,
  'maintenance.message': '',
  'min.app.version': '3.0.0',
  'force.update.version': '',
  // Trần cứng chống lạm dụng — app KHÔNG đổi được.
  'ai.max.segments.per.request': 120,
  'ai.max.chars.per.segment': 800,
  'ai.max.retries': 2,
  // Mua credit.
  'order.min.vnd': 10000,
  'order.max.vnd': 20000000,
  'order.expire.minutes': 60,
  // Mini-spec V9 (docs/PLAN.md) — POC hẹp: xử lý Demucs trên cloud, phí
  // trọn gói mỗi lượt (không theo thời lượng — đơn giản hoá cho POC, xem
  // lại nếu mở rộng ra ngoài phạm vi thử nghiệm).
  'cloud.render.enabled': true,
  'credit.cost.cloud.demucs': 50,
  // Chính sách dữ liệu đã chủ dự án duyệt (2026-08-11): xoá ngay sau khi
  // trả kết quả; TTL dưới đây chỉ là lưới an toàn dự phòng.
  'cloud.render.ttl.hours': 2,
  // Mini-spec V12 — worker Python poll heartbeat mỗi 30s (render_worker.py);
  // 5 phút không thấy nhịp coi là worker chết, sweeper chuyển job `failed`
  // (guardrail 5) thay vì treo mãi ở `running`.
  'cloud.render.heartbeat.stale.minutes': 5,
  'cloud.render.sweep.interval.minutes': 2,
  // Mini-spec V34a (docs/PLAN.md, Phase G) — PoC hạ tầng API lồng tiếng đầy
  // đủ. Constraint 1: KHÔNG billing thật ở PoC này — con số dưới đây CHỈ để
  // LOG chi phí giả định (audit.log), không bao giờ trừ Vox/quota thật.
  'cloud.dub.enabled': true,
  'cloud.dub.estimate.vox.per.request': 500,
  'cloud.dub.max.upload.mb': 300,
  // Dub xử lý lâu hơn Demucs nhiều (ASR+dịch+TTS+mux, không chỉ 1 stage) —
  // ngưỡng heartbeat-chết PHẢI rộng hơn hẳn cloud.render (5 phút) để không
  // báo nhầm worker chết giữa lúc TTS/mux vẫn đang chạy bình thường.
  'cloud.dub.heartbeat.stale.minutes': 15,
  'cloud.dub.sweep.interval.minutes': 2,
  'cloud.dub.ttl.hours': 2,
  // Mini-spec V34b (docs/PLAN.md) — billing THẬT theo phút video, tính từ
  // tỉ lệ compute thật đo được (xem docs/TEST_LOG.md mục V34b): ~1.63x
  // thời lượng gốc cho bg-mode=none, ~2.64x cho bg-mode=demucs. 2 giá dưới
  // đây là ĐỀ XUẤT KỸ THUẬT có căn cứ — KHÔNG PHẢI giá cuối cùng, chủ dự
  // án cần duyệt/chỉnh qua trang Admin trước khi tính là giá chính thức
  // (quyết định giá là quyết định kinh doanh, đúng nguyên tắc xuyên suốt
  // Phase G — xem Constraint 6 của V34b).
  'credit.cost.cloud.dub.vox.per.minute': 150,
  'credit.cost.cloud.dub.vox.per.minute.demucs': 250,
  // Mini-spec V43 (docs/PLAN.md) — giữ chỗ quota phút dub lúc submit (đóng
  // gap race condition V42 phát hiện). KHÔNG có ffprobe ở Node (Constraint
  // 3 của V34a) nên không biết thời lượng thật trước khi worker chạy —
  // caller CÓ THỂ tự khai `estimatedMinutes` (họ thường biết file của
  // chính họ dài bao lâu); không khai thì dùng mặc định dưới đây. Đây là
  // NGƯỠNG GIỮ CHỖ để chặn submit tràn lan, KHÔNG phải số tiền cuối — số
  // tiền cuối luôn tính lại THẬT theo durationS worker đo được
  // (`chargeDubUsage`), không đổi.
  'cloud.dub.reservation.default.minutes': 5,
  'cloud.dub.reservation.max.minutes': 240,
  // Mini-spec V37 (docs/PLAN.md) — nhạc nền/hiệu ứng âm thanh AI qua
  // ElevenLabs (Sound Effects v2 + Music v2). Bật/tắt qua
  // `cloud.music_match.enabled` — mặc định TẮT (Constraint 2 của V37: tính
  // năng OPT-IN, không phải mọi video đều nên tự động có thêm nhạc/SFX).
  // 2 giá dưới đây là ĐỀ XUẤT KỸ THUẬT thô dựa trên giá công bố của
  // ElevenLabs (SFX ~$0.02/hiệu ứng, Music theo credit-pool subscription —
  // CHƯA đo được chi phí credit thật/lượt gọi) — KHÔNG PHẢI giá cuối cùng,
  // chủ dự án cần duyệt/chỉnh qua Admin (Constraint 6 của V37, cùng
  // nguyên tắc Constraint 6 của V34b).
  'cloud.music_match.enabled': false,
  'credit.cost.cloud.sound_effect': 100,
  'credit.cost.cloud.music': 500,
  // Chuẩn giá: 1 Vox = 10đ (1.000 Vox = 10.000đ). Bonus tăng dần theo gói.
  'credit.packages': [
    { id: 'mini', label: 'Khởi đầu', vnd: 10000, vox: 1000, bonus: 0, popular: false },
    { id: 'starter', label: 'Cơ bản', vnd: 50000, vox: 5000, bonus: 250, popular: false },
    { id: 'standard', label: 'Phổ thông', vnd: 100000, vox: 10000, bonus: 1000, popular: true },
    { id: 'pro', label: 'Chuyên nghiệp', vnd: 300000, vox: 30000, bonus: 4500, popular: false },
    { id: 'studio', label: 'Studio', vnd: 1000000, vox: 100000, bonus: 20000, popular: false },
  ],
}

const cache = new Map()   // key -> { value, expiresAt }

async function get(key) {
  const now = Date.now()
  const hit = cache.get(key)
  if (hit && hit.expiresAt > now) return hit.value

  let value = DEFAULTS[key]
  try {
    const doc = await AppConfig.findOne({ key }).lean()
    if (doc && doc.value !== undefined && doc.value !== null) value = doc.value
  } catch {
    // DB chớp nháy không được phép làm sập request — dùng mặc định.
  }
  cache.set(key, { value, expiresAt: now + TTL_MS })
  return value
}

async function getMany(keys) {
  const out = {}
  await Promise.all(keys.map(async (k) => { out[k] = await get(k) }))
  return out
}

async function set(key, value) {
  await AppConfig.findOneAndUpdate(
    { key },
    { $set: { value } },
    { upsert: true, new: true },
  )
  cache.delete(key)
  return value
}

/** Xóa cache — gọi sau khi admin sửa hàng loạt. */
function invalidate(key) {
  if (key) cache.delete(key)
  else cache.clear()
}

/** Toàn bộ khóa đã biết, kèm giá trị hiệu dụng (cho trang admin). */
async function all() {
  const docs = await AppConfig.find({}).lean()
  const byKey = new Map(docs.map((d) => [d.key, d]))
  const keys = new Set([...Object.keys(DEFAULTS), ...byKey.keys()])
  return [...keys].sort().map((key) => {
    const doc = byKey.get(key)
    return {
      key,
      value: doc && doc.value !== undefined && doc.value !== null
        ? doc.value : DEFAULTS[key],
      isDefault: !doc,
      default: DEFAULTS[key],
      description: doc ? doc.description : '',
      updatedAt: doc ? doc.updatedAt : null,
    }
  })
}

module.exports = { get, getMany, set, invalidate, all, DEFAULTS }

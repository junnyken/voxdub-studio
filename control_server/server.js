'use strict'

/**
 * Điểm khởi động server VoxDub.
 *
 * Kiểm tra biến môi trường bắt buộc NGAY khi khởi động chứ không đợi request
 * đầu tiên: thiếu APP_ENCRYPTION_KEY mà chạy được thì mọi lượt gọi AI sẽ hỏng
 * lúc 3 giờ sáng thay vì hỏng ngay lúc deploy.
 */
require('dotenv').config()

const { build } = require('./src/app')

const REQUIRED = ['MONGODB_URI', 'JWT_SECRET', 'APP_ENCRYPTION_KEY']

function checkEnv() {
  const missing = REQUIRED.filter((k) => !(process.env[k] || '').trim())
  if (missing.length) {
    console.error(`[voxdub] Thiếu biến môi trường bắt buộc: ${missing.join(', ')}`)
    console.error('[voxdub] Xem control_server/.env.example')
    process.exit(1)
  }
  if ((process.env.APP_ENCRYPTION_KEY || '').trim().length !== 64) {
    console.error('[voxdub] APP_ENCRYPTION_KEY phải là 64 ký tự hex (openssl rand -hex 32)')
    process.exit(1)
  }
  if (!(process.env.ADMIN_TOKEN || '').trim()) {
    console.warn('[voxdub] CẢNH BÁO: chưa đặt ADMIN_TOKEN — /v1/admin/* sẽ trả 503.')
  }
  if (!(process.env.WORKER_INTERNAL_TOKEN || '').trim()) {
    console.warn('[voxdub] CẢNH BÁO: chưa đặt WORKER_INTERNAL_TOKEN — cloud '
      + 'rendering (mini-spec V12) không hoạt động, /internal/jobs/* sẽ trả 503.')
  }
}

async function main() {
  checkEnv()
  const app = await build()

  const port = Number(process.env.PORT) || 3001
  const host = process.env.HOST || '127.0.0.1'
  await app.listen({ port, host })

  // Sweeper hold quá hạn: bỏ ngang không xuất video thì sau TTL server tự
  // chốt (Vox đã tiêu là đã tiêu). Lỗi một vòng quét không được làm sập app.
  const holds = require('./src/services/hold.service')
  const config = require('./src/services/config.service')
  const sweepMinutes = Number(await config.get('hold.sweep.interval.minutes')) || 30
  const sweepTimer = setInterval(async () => {
    try {
      const done = await holds.expireSweep(app.log)
      if (done > 0) app.log.info({ done }, 'đã tự chốt hold quá hạn')
    } catch (err) {
      app.log.warn({ err }, 'vòng quét hold thất bại')
    }
  }, sweepMinutes * 60 * 1000)
  sweepTimer.unref()

  // Đối soát ví ↔ sổ cái mỗi ngày: chỉ đọc và báo (audit log + log server),
  // không tự sửa. Lệch tiền phải có người nhìn vào trước khi đụng ví.
  const credit = require('./src/services/credit.service')
  const reconcileTimer = setInterval(async () => {
    try {
      const { checked, mismatches } = await credit.reconcile()
      if (mismatches.length) {
        app.log.error({ mismatches }, `ĐỐI SOÁT: ${mismatches.length}/${checked} thiết bị lệch ví — xem audit log`)
      } else {
        app.log.info({ checked }, 'đối soát ví–sổ cái: khớp toàn bộ')
      }
    } catch (err) {
      app.log.warn({ err }, 'vòng đối soát thất bại')
    }
  }, 24 * 60 * 60 * 1000)
  reconcileTimer.unref()

  // Sweeper cloud rendering (mini-spec V9 xoá TTL đã có sẵn từ đầu nhưng
  // CHƯA từng được nối vào scheduler nào — job hết hạn nằm lại vô thời hạn
  // cho tới khi phát hiện lúc audit V12; nối luôn cả sweeper heartbeat mới
  // của V12 (worker chết giữa chừng → job không treo mãi ở "running").
  const renderJobService = require('./src/services/render-job.service')
  const renderSweepMinutes = Number(
    await config.get('cloud.render.sweep.interval.minutes')) || 2
  const renderSweepTimer = setInterval(async () => {
    try {
      const [expired, staleFailed] = await Promise.all([
        renderJobService.sweepExpired(app.log),
        renderJobService.sweepStaleRunning(app.log),
      ])
      if (expired > 0) app.log.info({ expired }, 'đã dọn render job hết hạn TTL')
      if (staleFailed > 0) {
        app.log.warn({ staleFailed }, 'đã chuyển failed render job kẹt ở running (worker mất kết nối)')
      }
    } catch (err) {
      app.log.warn({ err }, 'vòng quét render job thất bại')
    }
  }, renderSweepMinutes * 60 * 1000)
  renderSweepTimer.unref()

  // Sweeper API lồng tiếng đầy đủ (mini-spec V34a) — cùng lý do/cơ chế của
  // render sweeper phía trên, tách timer riêng vì ngưỡng heartbeat-chết
  // khác hẳn (dub xử lý lâu hơn Demucs nhiều — xem cloud.dub.heartbeat.
  // stale.minutes trong config.service.js).
  const dubJobService = require('./src/services/dub-job.service')
  const dubSweepMinutes = Number(
    await config.get('cloud.dub.sweep.interval.minutes')) || 2
  const dubSweepTimer = setInterval(async () => {
    try {
      const [expired, staleFailed] = await Promise.all([
        dubJobService.sweepExpired(app.log),
        dubJobService.sweepStaleRunning(app.log),
      ])
      if (expired > 0) app.log.info({ expired }, 'đã dọn dub job hết hạn TTL')
      if (staleFailed > 0) {
        app.log.warn({ staleFailed }, 'đã chuyển failed dub job kẹt ở running (worker mất kết nối)')
      }
    } catch (err) {
      app.log.warn({ err }, 'vòng quét dub job thất bại')
    }
  }, dubSweepMinutes * 60 * 1000)
  dubSweepTimer.unref()

  // Tắt êm: ngừng nhận request mới, cho request đang chạy kịp xong.
  for (const sig of ['SIGINT', 'SIGTERM']) {
    process.on(sig, async () => {
      app.log.info(`Nhận ${sig} — đang tắt...`)
      await app.close()
      process.exit(0)
    })
  }
}

main().catch((err) => {
  console.error('[voxdub] Không khởi động được:', err)
  process.exit(1)
})

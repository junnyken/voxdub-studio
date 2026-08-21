'use strict'

/**
 * `/v1/config` — app gọi lúc khởi động.
 *
 * Trả về đúng những gì app cần biết để quyết định có chạy được không: bảo
 * trì, phiên bản tối thiểu, credit đang bật hay tắt, và đơn giá theo segment
 * (để app hiện tổng "video này tốn ~2.400 Vox" trước khi bấm chạy).
 *
 * Chỉ có ba con số giá, và đó là chủ ý: giá theo segment cộng gói tiêu đề+mô
 * tả là toàn bộ những gì người dùng cần biết. Chi phí từng lượt AI bên trong
 * là chuyện nội bộ của server, không lộ ra API public.
 *
 * KHÔNG cần token: app phải đọc được thông báo bảo trì kể cả khi chưa đăng
 * ký thiết bị.
 */
const config = require('../services/config.service')
const { SOURCE_LANGS, TARGET_LANGS } = require('../utils/dub-langs')

module.exports = async function configRoutes(fastify) {
  fastify.get('/app', {
    config: { rateLimit: { max: 60, timeWindow: '1 minute' } },
  }, async () => {
    const cfg = await config.getMany([
      'credit.enabled', 'maintenance.mode', 'maintenance.message',
      'min.app.version', 'force.update.version',
      'credit.cost.segment.base', 'credit.cost.segment.autotranslate',
      'credit.cost.metadata',
      'ai.max.segments.per.request',
      // Mini-spec V12 (docs/PLAN.md) — GUI cần biết TRƯỚC khi người dùng
      // bấm "Xử lý trên cloud": có bật không, và giá bao nhiêu Vox
      // (guardrail 4 — hiện đúng giá trước khi trừ Vox, không được trừ
      // tiền rồi mới báo).
      'cloud.render.enabled', 'credit.cost.cloud.demucs',
      // Mini-spec V49 — trang thử API trên web cần biết ngôn ngữ nào hợp lệ
      // và giá mỗi phút TRƯỚC khi gửi file. Lấy từ nguồn duy nhất
      // `utils/dub-langs.js` thay vì để trang web tự chép danh sách (bản chép
      // tay sẽ trôi lệch, đúng thứ `tests/dub-langs.test.js` sinh ra để chặn).
      'cloud.dub.enabled', 'cloud.dub.max.upload.mb',
      'credit.cost.cloud.dub.vox.per.minute',
      'credit.cost.cloud.dub.vox.per.minute.demucs',
      // Mini-spec C6 — app cần biết nấc hiện tại TRƯỚC khi hiện chế độ dựng
      // video: khâu ghép video chỉ mở ở nấc chạy thật, tức là chỉ sau khi
      // phán quyết kiểm bao bì đã được soi tay và duyệt.
      'image.scene.stage',
    ])
    return {
      creditEnabled: cfg['credit.enabled'],
      imageSceneStage: cfg['image.scene.stage'],
      maintenanceMode: cfg['maintenance.mode'],
      maintenanceMessage: cfg['maintenance.message'],
      minAppVersion: cfg['min.app.version'],
      forceUpdateVersion: cfg['force.update.version'],
      maxSegmentsPerRequest: cfg['ai.max.segments.per.request'],
      pricing: {
        segmentBase: cfg['credit.cost.segment.base'],
        segmentAutoTranslate: cfg['credit.cost.segment.autotranslate'],
        metadata: cfg['credit.cost.metadata'],
        cloudRenderDemucs: cfg['credit.cost.cloud.demucs'],
      },
      cloudRenderEnabled: cfg['cloud.render.enabled'],
      cloudDub: {
        enabled: cfg['cloud.dub.enabled'],
        maxUploadMb: cfg['cloud.dub.max.upload.mb'],
        voxPerMinute: cfg['credit.cost.cloud.dub.vox.per.minute'],
        voxPerMinuteDemucs: cfg['credit.cost.cloud.dub.vox.per.minute.demucs'],
        sourceLangs: SOURCE_LANGS,
        targetLangs: TARGET_LANGS,
      },
      webUrl: (process.env.PUBLIC_URL || 'http://localhost:3001').replace(/\/+$/, ''),
      serverVersion: '3.0.0',
    }
  })
}

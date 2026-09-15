'use strict'

/**
 * Integration test: vòng đời hold Vox chạm MongoDB thật (in-memory).
 * Bổ sung cho hold.test.js (chỉ test phần thuần) theo mini-spec V1
 * (docs/PLAN.md) — không mock hold.service/credit.service.
 *
 * Chạy:  node --test tests/hold.integration.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const Device = require('../src/models/Device')
const CreditHold = require('../src/models/CreditHold')
const holds = require('../src/services/hold.service')
const credit = require('../src/services/credit.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(clearDb)

async function makeDevice(fingerprint, balance = 1000) {
  return Device.create({ fingerprint, balance, status: 'active' })
}

test('vòng đời đầy đủ: tạo hold → trừ ví ngay → accrue usage → commit → không hoàn/không truy thu', async () => {
  const fp = '1'.repeat(64)
  await makeDevice(fp, 1000)

  const { hold, balance, created } = await holds.createHold({
    fingerprint: fp, holdId: 'run-full-cycle', sentences: 20,
    autoTranslate: true, metadata: true,
  })
  assert.equal(created, true)
  assert.equal(hold.estimatedVox, 20 * 12 + 20)   // 260
  assert.equal(balance, 1000 - 260)

  // Tích lũy usage nội bộ (chi phí AI) — KHÔNG được đổi số tiền người dùng trả.
  await holds.accrue({
    holdId: 'run-full-cycle', fingerprint: fp, jobId: 'job-1',
    action: 'translate', vox: 15, sentences: 20,
  })
  const mid = await holds.getHold(fp, 'run-full-cycle')
  assert.equal(mid.usedVox, 15)
  assert.equal(mid.status, 'active')

  const committed = await holds.commitHold({ fingerprint: fp, holdId: 'run-full-cycle' })
  assert.equal(committed.chargedVox, 260, 'giá chốt từ lúc tạo hold, không đổi theo usedVox')
  assert.equal(committed.usedVox, 15)
  assert.equal(await credit.getBalance(fp), 1000 - 260, 'commit không hoàn cũng không truy thu')
})

test('commit là idempotent: gọi lại trả cùng kết quả, không trừ ví lần hai', async () => {
  const fp = '2'.repeat(64)
  await makeDevice(fp, 1000)
  await holds.createHold({ fingerprint: fp, holdId: 'run-idem', sentences: 10 })

  const first = await holds.commitHold({ fingerprint: fp, holdId: 'run-idem' })
  const second = await holds.commitHold({ fingerprint: fp, holdId: 'run-idem' })

  assert.equal(first.replayed, false)
  assert.equal(second.replayed, true)
  assert.equal(second.encKeyHex, first.encKeyHex, 'key giải mã phải giữ nguyên qua các lần gọi lại')
  assert.equal(await credit.getBalance(fp), 1000 - first.chargedVox)
})

test('tạo hold hai lần cùng holdId (resume sau crash) trả về đúng hold cũ, không trừ ví lần hai', async () => {
  const fp = '3'.repeat(64)
  await makeDevice(fp, 1000)

  const a = await holds.createHold({ fingerprint: fp, holdId: 'run-resume', sentences: 10 })
  const b = await holds.createHold({ fingerprint: fp, holdId: 'run-resume', sentences: 10 })

  assert.equal(a.created, true)
  assert.equal(b.created, false)
  assert.equal(a.hold.encKeyHex, b.hold.encKeyHex)
  assert.equal(await credit.getBalance(fp), 1000 - a.hold.estimatedVox, 'không bị trừ hai lần')
})

test('hold thuộc thiết bị khác thì bị từ chối', async () => {
  const fpA = '4'.repeat(64)
  const fpB = '5'.repeat(64)
  await makeDevice(fpA, 1000)
  await makeDevice(fpB, 1000)
  await holds.createHold({ fingerprint: fpA, holdId: 'run-cross-device', sentences: 5 })

  await assert.rejects(
    () => holds.createHold({ fingerprint: fpB, holdId: 'run-cross-device', sentences: 5 }),
    (err) => err.code === 'HOLD_FORBIDDEN',
  )
})

test('không đủ Vox thì createHold từ chối, ví không bị trừ', async () => {
  const fp = '6'.repeat(64)
  await makeDevice(fp, 5)

  await assert.rejects(
    () => holds.createHold({ fingerprint: fp, holdId: 'run-poor', sentences: 100 }),
    (err) => err.code === 'INSUFFICIENT_CREDIT',
  )
  assert.equal(await credit.getBalance(fp), 5)
})

test('expireSweep: hold active quá hạn tự động commit, hold chưa hết hạn thì không đụng', async () => {
  const fp = '7'.repeat(64)
  await makeDevice(fp, 1000)
  await holds.createHold({ fingerprint: fp, holdId: 'run-fresh', sentences: 5 })

  // Giả lập một hold đã hết hạn bằng cách ghi thẳng expiresAt trong quá khứ
  // (bỏ qua createHold để không phải chờ TTL thật).
  await holds.createHold({ fingerprint: fp, holdId: 'run-expired', sentences: 5 })
  await CreditHold.updateOne(
    { holdId: 'run-expired' },
    { $set: { expiresAt: new Date(Date.now() - 1000) } },
  )

  const swept = await holds.expireSweep()
  assert.equal(swept, 1, 'chỉ đúng một hold (đã hết hạn) được tự động chốt')

  const fresh = await CreditHold.findOne({ holdId: 'run-fresh' }).lean()
  const expired = await CreditHold.findOne({ holdId: 'run-expired' }).lean()
  assert.equal(fresh.status, 'active', 'hold chưa hết hạn không bị đụng vào')
  assert.equal(expired.status, 'committed')
  assert.equal(expired.autoCommitted, true)
})

test('canAbsorb + accrue nhất quán: hold autoTranslate=false không hấp thụ lượt translate', async () => {
  const fp = '8'.repeat(64)
  await makeDevice(fp, 1000)
  await holds.createHold({
    fingerprint: fp, holdId: 'run-no-autotranslate', sentences: 10, autoTranslate: false,
  })

  const hold = await holds.getHold(fp, 'run-no-autotranslate')
  assert.equal(holds.canAbsorb(hold, 'translate', 'job-x'), false)

  const result = await holds.accrue({
    holdId: 'run-no-autotranslate', fingerprint: fp, jobId: 'job-x',
    action: 'translate', vox: 5,
  })
  assert.equal(result, null, 'accrue nguyên tử phải khớp đúng điều kiện canAbsorb (JS thuần)')
})

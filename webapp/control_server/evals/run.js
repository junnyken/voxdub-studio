'use strict'

/**
 * Chạy bộ đo cổng trợ lý (mini-spec V89).
 *
 *   node evals/run.js                 # đo KHÔ: kiểm prompt, trần, khuôn
 *   node evals/run.js --live          # gọi mô hình thật rồi chấm kết quả
 *
 * Chế độ thật đọc cấu hình từ biến môi trường, KHÔNG đụng cơ sở dữ liệu —
 * để chạy được trên máy nhà phát triển mà không cần dựng Mongo:
 *
 *   ASSIST_EVAL_BASE_URL   ví dụ https://api.openai.com/v1
 *   ASSIST_EVAL_KEY        khoá API
 *   ASSIST_EVAL_MODEL      tên mô hình
 *   ASSIST_EVAL_TYPE       "google" cho Gemini, để trống cho loại OpenAI
 *
 * Vì sao cần: mô hình hỏng KHÔNG kêu lên — nó vẫn trả lời, chỉ là trả lời kém
 * đi. Không có bảng điểm thì đổi mô hình xong không ai biết chất lượng tụt.
 */
const assert = require('node:assert')

const { CASES } = require('./cases')
const assist = require('../src/prompts/assist')

const NGUONG = 0.85   // tỷ lệ phép kiểm phải đạt thì mới coi là còn dùng được

function inBang(dong) {
  const w = [28, 34, 8, 9]
  console.log(dong.map((c, i) => String(c).padEnd(w[i])).join(''))
}

/** Đo khô: những thứ sai là sai ngay, không cần gọi mô hình. */
function doKho() {
  let loi = 0
  for (const ten of assist.TASK_NAMES) {
    const t = assist.getTask(ten)
    const mau = CASES.filter((c) => c.task === ten)
    const van_de = []
    if (!mau.length) van_de.push('chưa có mẫu đo')
    for (const c of mau) {
      const user = t.buildUser(c.input)
      if (!user || user.length < 10) van_de.push(`${c.ten}: dữ liệu gửi lên rỗng`)
      if (user.length > t.maxInput + 500) {
        van_de.push(`${c.ten}: ${user.length} ký tự > trần ${t.maxInput}`)
      }
      if (!c.kiem.length) van_de.push(`${c.ten}: mẫu không có phép kiểm nào`)
    }
    // Mẫu cần ảnh thật thì lượt đo khô KHÔNG nói được gì về chất lượng —
    // ghi rõ ngay trên dòng đó. Để trơ chữ "đạt" là mời người đọc hiểu nhầm
    // thành "tác vụ này chạy tốt", đúng thứ cờ `canAnh` sinh ra để tránh.
    const canAnh = mau.some((c) => c.canAnh)
    inBang([ten, van_de.length ? van_de[0] : 'ổn', mau.length,
      van_de.length ? 'HỎNG' : (canAnh ? 'cấu hình ổn (cần ảnh thật)' : 'đạt')])
    loi += van_de.length ? 1 : 0
  }
  return loi
}

async function goiThat(task, input) {
  const spec = assist.getTask(task)
  const base = process.env.ASSIST_EVAL_BASE_URL
  const key = process.env.ASSIST_EVAL_KEY
  const model = process.env.ASSIST_EVAL_MODEL
  assert.ok(base && key && model,
    'Thiếu ASSIST_EVAL_BASE_URL / ASSIST_EVAL_KEY / ASSIST_EVAL_MODEL')

  const axios = require('axios')
  const schema = assist.resultsSchema(spec.maxResults)
  const la_google = process.env.ASSIST_EVAL_TYPE === 'google'

  if (la_google) {
    const url = `${base.replace(/\/$/, '')}/models/${model}:generateContent?key=${key}`
    const { data } = await axios.post(url, {
      systemInstruction: { parts: [{ text: spec.system }] },
      contents: [{ role: 'user', parts: [{ text: spec.buildUser(input) }] }],
      generationConfig: { responseMimeType: 'application/json' },
    }, { timeout: 60000 })
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text || '{}'
    return JSON.parse(text).results || []
  }

  const { data } = await axios.post(`${base.replace(/\/$/, '')}/chat/completions`, {
    model,
    messages: [
      { role: 'system', content: spec.system },
      { role: 'user', content: spec.buildUser(input) },
    ],
    response_format: {
      type: 'json_schema',
      json_schema: { name: 'ket_qua', schema, strict: false },
    },
  }, { headers: { Authorization: `Bearer ${key}` }, timeout: 60000 })
  const text = data.choices?.[0]?.message?.content || '{}'
  return JSON.parse(text).results || []
}

async function doThat() {
  let dat = 0
  let tong = 0
  const hong = []
  for (const c of CASES) {
    if (c.canAnh) {
      // Không im lặng bỏ qua: in ra để người chạy biết phần nào CHƯA được đo.
      inBang([c.task, c.ten.slice(0, 32), '-', 'bỏ qua (cần ảnh thật)'])
      continue
    }
    let ket = []
    try {
      ket = await goiThat(c.task, c.input)
    } catch (err) {
      hong.push(`${c.task}/${c.ten}: gọi hỏng — ${String(err.message).slice(0, 80)}`)
      inBang([c.task, c.ten.slice(0, 32), '-', 'HỎNG'])
      continue
    }
    if (!ket.length) {
      hong.push(`${c.task}/${c.ten}: không có kết quả`)
      inBang([c.task, c.ten.slice(0, 32), 0, 'HỎNG'])
      continue
    }
    let dat_mau = 0
    let tong_mau = 0
    for (const [ten_kiem, kiem] of c.kiem) {
      for (let i = 0; i < ket.length; i += 1) {
        tong_mau += 1
        const r = { value: String(ket[i].value || ''), reason: String(ket[i].reason || '') }
        if (kiem(r, c, i)) dat_mau += 1
        else hong.push(`${c.task}/${c.ten}: «${r.value.slice(0, 40)}» trượt "${ten_kiem}"`)
      }
    }
    dat += dat_mau
    tong += tong_mau
    inBang([c.task, c.ten.slice(0, 32), `${dat_mau}/${tong_mau}`,
      dat_mau === tong_mau ? 'đạt' : 'lệch'])
  }
  const ty_le = tong ? dat / tong : 0
  console.log(`\nĐiểm: ${dat}/${tong} = ${(ty_le * 100).toFixed(0)}% `
    + `(ngưỡng ${NGUONG * 100}%)`)
  if (hong.length) {
    console.log('\nChi tiết trượt:')
    for (const d of hong.slice(0, 25)) console.log(`  - ${d}`)
  }
  return ty_le >= NGUONG ? 0 : 1
}

async function main() {
  const live = process.argv.includes('--live')
  console.log(live ? 'ĐO THẬT (gọi mô hình)\n' : 'ĐO KHÔ (không gọi mô hình)\n')
  inBang(live ? ['Tác vụ', 'Mẫu', 'Điểm', 'Kết quả']
    : ['Tác vụ', 'Vấn đề', 'Số mẫu', 'Kết quả'])
  console.log('-'.repeat(79))
  const ma = live ? await doThat() : (doKho() ? 1 : 0)
  if (!live) {
    console.log('\nĐo khô chỉ chặn lỗi cấu hình. Đổi mô hình hay sửa prompt thì '
      + 'PHẢI chạy --live rồi so với lần trước.')
  }
  process.exit(ma)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})

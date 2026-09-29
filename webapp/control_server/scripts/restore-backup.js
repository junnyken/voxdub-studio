#!/usr/bin/env node
'use strict'

/**
 * Khôi phục dữ liệu từ một bản sao lưu do `GET /v1/admin/backup` sinh ra
 * (mini-spec V48).
 *
 *   node scripts/restore-backup.js <file.ndjson.gz> [--wipe]
 *
 * Mặc định chạy chế độ `upsert`: ghi đè bản ghi trùng `_id`, GIỮ NGUYÊN bản
 * ghi mới tạo sau lúc sao lưu. `--wipe` xoá sạch từng collection có trong
 * bản dump trước khi nhập — dùng khi thật sự muốn quay ngược thời gian.
 *
 * Kết nối bằng `MONGODB_URI` như chính máy chủ, nên chạy được từ bất kỳ đâu
 * thấy được database (kể cả bên trong container qua terminal của nền tảng).
 */
const fs = require('node:fs')
const zlib = require('node:zlib')
const readline = require('node:readline')
const mongoose = require('mongoose')

const backup = require('../src/services/backup.service')

async function main() {
  const [file, ...flags] = process.argv.slice(2)
  if (!file) {
    console.error('Dùng: node scripts/restore-backup.js <file.ndjson.gz> [--wipe]')
    process.exit(1)
  }
  if (!fs.existsSync(file)) {
    console.error(`Không thấy file: ${file}`)
    process.exit(1)
  }

  const mode = flags.includes('--wipe') ? 'wipe' : 'upsert'
  const uri = process.env.MONGODB_URI
  if (!uri) {
    console.error('Thiếu MONGODB_URI.')
    process.exit(1)
  }

  await mongoose.connect(uri)
  console.log(`Đã kết nối ${mongoose.connection.db.databaseName}, chế độ: ${mode}`)

  const input = file.endsWith('.gz')
    ? fs.createReadStream(file).pipe(zlib.createGunzip())
    : fs.createReadStream(file)

  const stats = await backup.importLines(
    readline.createInterface({ input, crlfDelay: Infinity }), { mode },
  )

  if (stats.meta) {
    console.log(`Bản sao lưu tạo lúc: ${stats.meta.createdAt} (DB "${stats.meta.database}")`)
  }
  for (const [name, n] of Object.entries(stats.counts).sort()) {
    console.log(`  ${name}: ${n}`)
  }
  console.log(`Tổng: ${stats.total} bản ghi.`)

  await mongoose.connection.close()
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})

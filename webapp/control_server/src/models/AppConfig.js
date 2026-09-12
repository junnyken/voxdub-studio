'use strict'

/**
 * Cấu hình runtime dạng key/value (cache TTL 60s ở config.service.js).
 * Dựng lại từ config.service.js — xem ghi chú Device.js.
 */
const mongoose = require('mongoose')

const appConfigSchema = new mongoose.Schema({
  key: { type: String, required: true, unique: true },
  value: { type: mongoose.Schema.Types.Mixed },
  description: { type: String, default: '' },
}, { timestamps: true })

module.exports = mongoose.models.AppConfig || mongoose.model('AppConfig', appConfigSchema)

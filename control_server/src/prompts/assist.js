'use strict'

/**
 * Danh mục tác vụ của cổng trợ lý (mini-spec V89).
 *
 * Đây là DANH SÁCH ĐÓNG — app chỉ gửi TÊN tác vụ, không bao giờ gửi prompt.
 * Nhờ vậy chi phí đoán được, và sửa câu chữ hướng dẫn mô hình không cần phát
 * hành lại bản .exe.
 *
 * Mỗi tác vụ tự khai:
 *   - `costKey`     khoá giá trong cấu hình (đổi giá lúc chạy, không sửa mã)
 *   - `maxInput`    trần ký tự đầu vào — CẮT trước khi gọi, không trả tiền rồi
 *                   mới biết là quá dài
 *   - `maxResults`  số kết quả tối đa
 *   - `system`      vai trò của mô hình
 *   - `buildUser`   dựng phần dữ liệu từ input của app
 *
 * Mọi tác vụ trả về cùng một khuôn `{ results: [{ value, reason }] }`. Trường
 * `reason` là BẮT BUỘC: giao diện đã hiện lý do cho từng gợi ý (xem
 * `music_suggest.py` phía app), và người dùng cần biết vì sao máy đề xuất như
 * vậy thay vì tin một cái nhãn. Ép trong schema thì mô hình không bỏ qua được.
 */

/** Khuôn kết quả dùng chung — mọi tác vụ đều theo đúng khuôn này. */
function resultsSchema(maxResults) {
  return {
    type: 'object',
    required: ['results'],
    properties: {
      results: {
        type: 'array',
        minItems: 1,
        maxItems: maxResults,
        items: {
          type: 'object',
          required: ['value', 'reason'],
          properties: {
            value: { type: 'string' },
            reason: { type: 'string' },
          },
        },
      },
    },
  }
}

function cat(text, max) {
  const s = String(text == null ? '' : text).trim()
  return s.length > max ? `${s.slice(0, max)}…` : s
}

const TASKS = {
  /**
   * Gợi ý mô tả nhạc nền từ lời thoại.
   *
   * App đã có bản suy bằng luật (đếm chữ + dò từ khoá) chạy offline; tác vụ
   * này là bản nâng cấp khi người dùng có tài khoản. Vì vậy prompt phải đòi
   * MÔ TẢ ĐỂ ĐƯA THẲNG CHO MÁY SINH NHẠC, không phải lời bình luận.
   */
  music_suggest: {
    costKey: 'credit.cost.assist.music_suggest',
    maxInput: 4000,
    maxResults: 3,
    system: [
      'Bạn chọn nhạc nền cho video lồng tiếng Việt.',
      'Người dùng sẽ đưa mô tả của bạn thẳng cho một máy sinh nhạc, nên mỗi',
      'mô tả phải là một câu tả ÂM NHẠC: thể loại, nhạc cụ, tiết tấu, tâm',
      'trạng. Không nhắc tên bài hát hay nghệ sĩ có thật (máy sinh nhạc không',
      'dùng được, và dễ đụng bản quyền). Không mô tả hình ảnh video.',
      'Nhạc chỉ làm nền cho giọng đọc: tránh đề xuất thứ có giai điệu lấn át.',
      'Viết tiếng Việt, mỗi mô tả tối đa 20 chữ.',
      'Phần lý do: nói ngắn gọn dựa vào nội dung lời thoại, tối đa 15 chữ.',
    ].join(' '),
    buildUser: (input) => {
      const loi = cat(input.transcript, 4000)
      const tieu_de = cat(input.videoTitle, 200)
      return [
        tieu_de ? `Tiêu đề video: ${tieu_de}` : '',
        'Lời thoại (đã chép từ chính video này):',
        loi,
      ].filter(Boolean).join('\n')
    },
  },

  /**
   * Giải thích một dòng lỗi kỹ thuật thành việc người dùng làm được.
   *
   * Giá 0 Vox và chạy cả khi hết Vox — người đang gặp lỗi mà còn bị chặn vì
   * hết tiền thì đó là lúc tệ nhất để thu phí. Bù lại có hạn mức ngày riêng.
   */
  explain_error: {
    costKey: 'credit.cost.assist.explain_error',
    maxInput: 2000,
    maxResults: 1,
    system: [
      'Bạn giải thích lỗi của phần mềm lồng tiếng VoxDub Studio cho người',
      'dùng KHÔNG rành kỹ thuật, bằng tiếng Việt.',
      'Trường value: nói người dùng cần LÀM GÌ, tối đa 45 chữ, câu mệnh lệnh',
      'cụ thể. Trường reason: nói CHUYỆN GÌ đã xảy ra, tối đa 25 chữ.',
      'Không dùng từ kỹ thuật (traceback, exception, module, PATH, venv...),',
      'không nhắc tên tệp mã nguồn, không bảo người dùng đi báo lỗi trên',
      'GitHub. Nếu lỗi cho thấy thiếu một chương trình phụ trợ thì nói rõ tên',
      'chương trình đó theo cách người dùng nhận ra.',
      'Không chắc thì nói thẳng là chưa rõ nguyên nhân và đề xuất chạy lại,',
      'TUYỆT ĐỐI không bịa ra cách sửa nghe có vẻ hợp lý.',
    ].join(' '),
    buildUser: (input) => [
      `Bối cảnh: người dùng đang ở bước "${cat(input.step, 100) || 'không rõ'}".`,
      'Dòng lỗi phần mềm ghi lại:',
      cat(input.message, 2000),
    ].join('\n'),
  },
}

/** Tên tác vụ hợp lệ — dùng cho schema của route và cho test. */
const TASK_NAMES = Object.keys(TASKS)

function getTask(name) {
  return Object.prototype.hasOwnProperty.call(TASKS, name) ? TASKS[name] : null
}

module.exports = { TASKS, TASK_NAMES, getTask, resultsSchema, cat }

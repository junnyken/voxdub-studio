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

  /**
   * Tóm tắt video thành vài câu + từ khoá.
   *
   * Dùng cho người vừa chép lời xong và cần biết video nói gì mà không phải
   * đọc hết. Từ khoá phải LẤY TỪ lời thoại, không tự nghĩ ra — đây là chỗ mô
   * hình hay bịa nhất.
   */
  video_summary: {
    costKey: 'credit.cost.assist.video_summary',
    maxInput: 8000,
    maxResults: 4,
    system: [
      'Bạn tóm tắt nội dung video dựa trên lời thoại đã chép, bằng tiếng Việt.',
      'Trả về đúng 4 mục theo thứ tự: mục 1 là bản tóm tắt tối đa 3 câu',
      '(value = tóm tắt, reason = "tóm tắt"); ba mục còn lại mỗi mục là MỘT',
      'từ khoá (value = từ khoá, reason = câu trong lời thoại chứa nó).',
      'Từ khoá phải xuất hiện trong lời thoại — không tự nghĩ thêm.',
      'Lời thoại do máy chép nên có thể sai chính tả; tóm ý, đừng trích y',
      'nguyên chỗ nghe nhầm. Không bịa chi tiết không có trong lời thoại.',
    ].join(' '),
    buildUser: (input) => [
      cat(input.videoTitle, 200) ? `Tiêu đề: ${cat(input.videoTitle, 200)}` : '',
      'Lời thoại:',
      cat(input.transcript, 8000),
    ].filter(Boolean).join('\n'),
  },

  /**
   * Đặt tên cho nhân vật dựa trên chính lời họ nói.
   *
   * Người dùng đang phải tự nghĩ tên cho từng người nói mà bước tách giọng
   * tìm ra ("Người nói 1", "Người nói 2"). Tên gợi ý phải NGẮN để còn hiện
   * vừa trong bảng hồ sơ.
   */
  character_name: {
    costKey: 'credit.cost.assist.character_name',
    maxInput: 3000,
    maxResults: 3,
    system: [
      'Bạn đặt tên gọi cho một nhân vật trong video, dựa trên chính lời người',
      'đó nói. Tên phải NGẮN (tối đa 3 chữ), tiếng Việt, dễ nhớ, và nói lên',
      'vai trò hoặc đặc điểm nhận ra được — ví dụ "Người dẫn", "Ông chủ quán".',
      'Nếu trong lời thoại có tên riêng của chính người đó thì ưu tiên dùng.',
      'Không đặt tên xúc phạm, không đoán giới tính khi lời thoại không cho',
      'biết. Phần reason: nói dựa vào đâu, tối đa 12 chữ.',
    ].join(' '),
    buildUser: (input) => [
      `Nhân vật này nói ${Number(input.lineCount) || 0} câu trong video.`,
      'Một số câu của họ:',
      cat(input.lines, 3000),
    ].join('\n'),
  },

  /**
   * Dựng quy ước dịch cho cả series: xưng hô + thuật ngữ cố định.
   *
   * Đây là thứ người dùng đang gõ tay từng dòng ở trang Hồ sơ nhân vật, và
   * là thứ quyết định các tập sau có dịch nhất quán hay không.
   */
  series_glossary: {
    costKey: 'credit.cost.assist.series_glossary',
    maxInput: 8000,
    maxResults: 5,
    system: [
      'Bạn dựng quy ước dịch cho một series video sắp lồng tiếng Việt.',
      'Mục 1: cách xưng hô giữa các nhân vật (value = "tôi – anh" chẳng hạn,',
      'reason = dựa vào đâu). Các mục sau: mỗi mục một thuật ngữ cần dịch cố',
      'định, value viết đúng dạng "gốc = dịch", reason nói vì sao cần cố định.',
      'Chỉ lấy thuật ngữ CÓ trong lời thoại và thật sự lặp lại — thuật ngữ',
      'dịch mỗi lúc một kiểu mới là thứ làm người xem khó theo.',
      'Không đưa từ thông thường ai cũng dịch giống nhau.',
    ].join(' '),
    buildUser: (input) => [
      cat(input.seriesName, 200) ? `Series: ${cat(input.seriesName, 200)}` : '',
      'Lời thoại gốc:',
      cat(input.transcript, 8000),
    ].filter(Boolean).join('\n'),
  },

  /**
   * Viết ngắn lại một câu dịch quá dài so với chỗ trống.
   *
   * Câu dài buộc giọng đọc phải tăng tốc cho kịp, nghe méo — đây là lỗi chất
   * lượng đứng đầu bảng xếp hạng "đáng sửa trước" (mini-spec V64).
   */
  tighten_line: {
    costKey: 'credit.cost.assist.tighten_line',
    maxInput: 1200,
    maxResults: 2,
    system: [
      'Bạn rút gọn một câu thoại tiếng Việt để đọc kịp trong thời lượng cho',
      'phép, giữ NGUYÊN ý và giữ nguyên mọi con số, tên riêng, đơn vị.',
      'Mỗi phương án phải NGẮN HƠN câu gốc rõ rệt, đọc lên vẫn tự nhiên như',
      'lời nói, không viết tắt, không bỏ dấu câu cần thiết.',
      'Phần reason: nói đã lược bỏ gì, tối đa 12 chữ.',
      'Nếu câu gốc đã ngắn gọn hết mức thì nói thẳng trong reason là không',
      'rút thêm được, và trả lại chính câu đó.',
    ].join(' '),
    buildUser: (input) => [
      `Câu gốc (đọc mất ${Number(input.needSeconds) || 0} giây):`,
      cat(input.line, 1200),
      `Chỗ trống chỉ có ${Number(input.roomSeconds) || 0} giây.`,
      `Cần ngắn hơn khoảng ${Number(input.trimPercent) || 20}%.`,
    ].join('\n'),
  },
}

/** Tên tác vụ hợp lệ — dùng cho schema của route và cho test. */
const TASK_NAMES = Object.keys(TASKS)

function getTask(name) {
  return Object.prototype.hasOwnProperty.call(TASKS, name) ? TASKS[name] : null
}

module.exports = { TASKS, TASK_NAMES, getTask, resultsSchema, cat }

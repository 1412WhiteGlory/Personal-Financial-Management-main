/**
 * helpers/testApp.js
 * ------------------------------------------------------------------
 * Tạo một ứng dụng Express tối giản (minimal) dùng riêng cho việc test.
 *
 * TẠI SAO KHÔNG IMPORT server.js TRỰC TIẾP?
 *   server.js khi được require() sẽ lập tức:
 *     - Khởi động các WebSocket stream (kết nối realtime tới thị trường tài chính)
 *     - Chạy các cron job (tác vụ định kỳ)
 *     - Kết nối Redis listener
 *   Những side-effect này làm ô nhiễm môi trường test, gây khó kiểm soát và
 *   làm chậm quá trình test. Vì vậy chúng ta xây dựng một app Express "sạch"
 *   chỉ mount đúng route module cần test.
 *
 * CÁCH DÙNG (trong mỗi file test):
 *   const buildApp = require('./helpers/testApp');
 *   // Tạo app với router authRoutes mount ở path '/api/v1/auth'
 *   const app = buildApp(authRoutes, '/api/v1/auth');
 *   // Gửi HTTP request tới app trong test (không cần server đang lắng nghe)
 *   const response = await request(app).post('/api/v1/auth/login').send({...});
 * ------------------------------------------------------------------
 */

const express = require('express');

/**
 * buildApp - Xây dựng một Express app tối giản để test một router cụ thể.
 *
 * Thay vì khởi động toàn bộ server (với tất cả side-effect),
 * hàm này chỉ tạo một app Express đơn giản với:
 *   1. JSON body parser (để đọc req.body)
 *   2. Router cần test được mount tại prefix chỉ định
 *
 * supertest sẽ gửi HTTP request trực tiếp vào app này mà không cần
 * server thật phải đang lắng nghe trên bất kỳ port nào.
 *
 * @param {express.Router} router   - Router module cần test (ví dụ: authRoutes)
 * @param {string}         prefix   - URL prefix để mount router (ví dụ: '/api/v1/auth')
 * @returns {express.Application}   - Express app có thể dùng với supertest
 */
function buildApp(router, prefix) {
    const app = express();

    // Middleware: parse JSON body trong tất cả request (cần thiết để req.body hoạt động)
    app.use(express.json());

    // Mount router dưới prefix được chỉ định.
    // Ví dụ: buildApp(authRoutes, '/api/v1/auth') → POST /api/v1/auth/login sẽ hoạt động
    app.use(prefix, router);

    return app;
}

module.exports = buildApp;

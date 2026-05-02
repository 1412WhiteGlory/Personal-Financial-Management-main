/**
 * tests/helpers/jestSetupEnv.js
 * ──────────────────────────────────────────────────────────────────
 * Nạp các biến môi trường từ file .env.test TRƯỚC KHI Jest chạy bất kỳ
 * test file nào. Nhờ đó các module import process.env.JWT_SECRET, v.v.
 * sẽ thấy giá trị hợp lệ ngay từ đầu.
 *
 * TẠI SAO CẦN FILE NÀY?
 *   - File .env thật (ở thư mục backend/) chứa thông tin kết nối tới
 *     database thật, Redis thật, email thật, v.v.
 *   - Khi chạy test, chúng ta KHÔNG muốn kết nối tới bất kỳ dịch vụ thật nào.
 *   - File .env.test chứa các giá trị "giả" (stub) an toàn để test:
 *       MONGO_URI     → không dùng (mongodb-memory-server override)
 *       JWT_SECRET    → chuỗi bất kỳ để sign/verify JWT trong test
 *       EMAIL_USER    → giả (nodemailer được mock)
 *       REDIS_URL     → giả (Redis được mock)
 *       DATABASE_URL  → giả (PostgreSQL được mock)
 *
 * CÁCH HOẠT ĐỘNG:
 *   jest.config.js khai báo: setupFiles: ['<rootDir>/tests/helpers/jestSetupEnv.js']
 *   → Jest tự động chạy file này trong mỗi worker thread TRƯỚC khi
 *     import bất kỳ test module nào, đảm bảo process.env đã có đầy đủ
 *     giá trị cho mọi require() tiếp theo.
 * ──────────────────────────────────────────────────────────────────
 */

const path   = require('path');
const dotenv = require('dotenv');

// Nạp file .env.test (nằm trong thư mục tests/) vào process.env.
// path.resolve đảm bảo đường dẫn luôn đúng bất kể thư mục làm việc hiện tại.
// Dùng .env.test thay vì .env để tránh vô tình dùng credential thật khi test.
dotenv.config({ path: path.resolve(__dirname, '../.env.test') });

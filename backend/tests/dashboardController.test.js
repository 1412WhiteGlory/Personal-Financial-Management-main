/**
 * dashboardController.test.js
 * ==================================================================
 * Test cases TC-DASH-001  →  TC-DASH-004
 *
 * Controller đang được test : backend/controllers/dashboardController.js
 *
 * CÁC KHÁI NIỆM NGHIỆP VỤ ĐƯỢC KIỂM TRA:
 *   • MongoDB aggregation ($sum) để tính totalIncome / totalExpenses
 *   • Bộ lọc ngày 30 ngày gần nhất (TC-DASH-003) — kiểm tra BVA boundary
 *   • Sắp xếp recentTransactions theo thứ tự giảm dần (mới nhất trước) (TC-DASH-004)
 *
 * KIẾN TRÚC TEST (không cần container nào đang chạy):
 *  - mongodb-memory-server: cô lập hoàn toàn với DB thật.
 *  - ROLLBACK: setupMongoMemory.js xóa tất cả collections trước MỖI test.
 *  - authMiddleware bị mock để inject FAKE_USER_ID vào mọi request.
 * ==================================================================
 */

// ── Kết nối MongoDB in-memory ──────────────────────────────────────
require('./helpers/setupMongoMemory');

const request          = require('supertest');
const mongoose         = require('mongoose');
const buildApp         = require('./helpers/testApp');
const dashboardRoutes  = require('../routes/dashboardRoutes');
const Income           = require('../models/Income');   // Seed và CheckDB
const Expense          = require('../models/Expense');  // Seed và CheckDB

// ── Tạo Express app tối giản chỉ mount dashboardRoutes ────────────
const app = buildApp(dashboardRoutes, '/api/v1/dashboard');

// ── Tạo userId giả cố định cho toàn bộ suite ─────────────────────
const FAKE_USER_ID = new mongoose.Types.ObjectId();

// ── Mock authMiddleware: inject userId từ global variable ──────────
// TẠI SAO DÙNG global.__DASHBOARD_USER_ID__?
//   jest.mock() là hoist (chạy trước code thường), nên trong factory function
//   của mock ta không thể trực tiếp truy cập biến FAKE_USER_ID được khai báo
//   sau đó. Giải pháp: dùng global variable làm cầu nối.
jest.mock('../middleware/authMiddleware', () => ({
    protect: (req, _res, next) => {
        // Đọc userId từ global (được set trong beforeAll bên dưới)
        req.user = { id: global.__DASHBOARD_USER_ID__ };
        next();
    },
}));

// Set global userId sau khi mongoose đã sẵn sàng (beforeAll của setupMongoMemory chạy trước)
beforeAll(() => {
    // Tạo ObjectId string và lưu vào global để mock có thể truy cập
    global.__DASHBOARD_USER_ID__ = new mongoose.Types.ObjectId().toString();
});

// ──────────────────────────────────────────────────────────────────
// Seed helpers: chèn dữ liệu mẫu trực tiếp vào DB in-memory
// Tham số daysAgo: record cách đây bao nhiêu ngày (dùng cho test boundary 30 ngày)
// ──────────────────────────────────────────────────────────────────

/**
 * seedIncome – Tạo một Income record với amount và ngày tính từ hiện tại.
 * @param {number} amount   - Số tiền thu nhập (VND)
 * @param {number} daysAgo  - Record được tạo cách đây bao nhiêu ngày (mặc định 5)
 */
async function seedIncome({ amount, daysAgo = 5 }) {
    const date = new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000);
    return Income.create({
        userId: global.__DASHBOARD_USER_ID__,
        source: 'TestSource',
        amount,
        date,
    });
}

/**
 * seedExpense – Tạo một Expense record với amount và ngày tính từ hiện tại.
 * @param {number} amount   - Số tiền chi phí (VND)
 * @param {number} daysAgo  - Record được tạo cách đây bao nhiêu ngày (mặc định 5)
 */
async function seedExpense({ amount, daysAgo = 5 }) {
    const date = new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000);
    return Expense.create({
        userId  : global.__DASHBOARD_USER_ID__,
        category: 'TestCategory',
        amount,
        date,
    });
}


// ══════════════════════════════════════════════════════════════════
// dashboardController → getDashboardData()
// Kiểm tra chức năng: Lấy dữ liệu tổng quan tài chính của user
// Endpoint: GET /api/v1/dashboard
// ══════════════════════════════════════════════════════════════════
describe('dashboardController → getDashboardData()', () => {

    // TC-DASH-001 ─────────────────────────────────────────────────
    // Kiểm tra công thức: totalBalance = totalIncome - totalExpenses
    it('TC-DASH-001: should return correct totalBalance = totalIncome - totalExpenses', async () => {
        // Seed: 10 triệu thu nhập, 3 triệu chi phí → số dư = 7 triệu
        await seedIncome({ amount: 10_000_000 });
        await seedExpense({ amount:  3_000_000 });

        const response = await request(app).get('/api/v1/dashboard');

        expect(response.status).toBe(200);
        expect(response.body.totalIncome).toBe(10_000_000);
        expect(response.body.totalExpenses).toBe(3_000_000);
        // Xác nhận công thức tính số dư đúng
        expect(response.body.totalBalance).toBe(7_000_000); // 10M - 3M = 7M
    });

    // TC-DASH-002 ─────────────────────────────────────────────────
    // EP Edge case: database rỗng → tất cả giá trị phải là 0 (không crash)
    it('TC-DASH-002: should return all-zero fields when no transactions exist (empty database)', async () => {
        // setupMongoMemory đã xóa sạch DB trước test → không cần seed
        const response = await request(app).get('/api/v1/dashboard');

        expect(response.status).toBe(200);
        // Tất cả giá trị tổng hợp phải là 0, không phải null/undefined
        expect(response.body.totalBalance).toBe(0);
        expect(response.body.totalIncome).toBe(0);
        expect(response.body.totalExpenses).toBe(0);
        expect(response.body.last30DaysIncome.total).toBe(0);
        expect(response.body.last30DaysExpenses.total).toBe(0);
    });

    // TC-DASH-003 ─────────────────────────────────────────────────
    // BVA (Boundary Value Analysis): kiểm tra ngưỡng 30 ngày chính xác
    // Record 29 ngày trước: TRONG window → được tính vào last30DaysIncome
    // Record 31 ngày trước: NGOÀI window → chỉ tính vào totalIncome, không phải last30Days
    it('TC-DASH-003: should count only income records from the last 30 days (BVA date boundary)', async () => {
        // Seed trong window: 29 ngày trước = 1 ngày trước ngưỡng 30 ngày → HỢP LỆ
        await seedIncome({ amount: 5_000_000, daysAgo: 29 });

        // Seed ngoài window: 31 ngày trước = 1 ngày sau ngưỡng 30 ngày → KHÔNG ĐẾM
        await seedIncome({ amount: 9_000_000, daysAgo: 31 });

        const response = await request(app).get('/api/v1/dashboard');

        expect(response.status).toBe(200);

        // last30DaysIncome chỉ tính record 29 ngày trước (5 triệu)
        expect(response.body.last30DaysIncome.total).toBe(5_000_000);
        expect(response.body.last30DaysIncome.transactions.length).toBe(1); // chỉ 1 giao dịch

        // totalIncome tính TẤT CẢ (cả 2 records = 14 triệu)
        expect(response.body.totalIncome).toBe(14_000_000); // 5M + 9M
    });

    // TC-DASH-004 ─────────────────────────────────────────────────
    // Kiểm tra recentTransactions: tối đa 20 records, sắp xếp mới nhất trước
    it('TC-DASH-004: recentTransactions must have ≤ 20 entries and be sorted newest-first', async () => {
        // Seed 15 income + 15 expense = 30 records tổng cộng.
        // Controller lấy top 10 income + top 10 expense → merged array ≤ 20.
        // Dùng daysAgo = i để tạo records với ngày khác nhau:
        //   i=0 → hôm nay (mới nhất), i=14 → 14 ngày trước (cũ nhất)
        for (let i = 0; i < 15; i++) {
            await seedIncome({ amount: 1_000, daysAgo: i });
            await seedExpense({ amount: 1_000, daysAgo: i });
        }

        const response = await request(app).get('/api/v1/dashboard');

        expect(response.status).toBe(200);

        const transactions = response.body.recentTransactions;

        // Ràng buộc số lượng: không quá 20 (10 income + 10 expense)
        expect(transactions.length).toBeLessThanOrEqual(20);
        expect(transactions.length).toBeGreaterThan(0); // phải có ít nhất 1

        // Xác nhận thứ tự giảm dần (mới nhất trước):
        // Duyệt qua từng cặp liên tiếp, ngày sau phải <= ngày trước
        for (let i = 0; i < transactions.length - 1; i++) {
            const currentDate = new Date(transactions[i].date).getTime();
            const nextDate    = new Date(transactions[i + 1].date).getTime();
            expect(currentDate).toBeGreaterThanOrEqual(nextDate);
        }
    });
});

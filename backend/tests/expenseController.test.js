/**
 * expenseController.test.js
 * ==================================================================
 * Test cases TC-EXP-001  →  TC-EXP-009
 *
 * Controller đang được test : backend/controllers/expenseController.js
 *
 * KIẾN TRÚC TEST (không cần container nào đang chạy):
 *  - mongodb-memory-server: cô lập hoàn toàn với DB thật.
 *  - ROLLBACK: setupMongoMemory.js xóa tất cả collections trước MỖI test.
 *  - authMiddleware bị jest-mock để inject req.user có thể kiểm soát.
 *    → Test có thể giả lập "người dùng A" hay "người dùng B" đang đăng nhập
 *      để kiểm tra logic phân quyền (chỉ owner mới được sửa/xóa record của mình).
 *  - CheckDB: sau các thao tác ghi, test truy vấn trực tiếp vào Expense model
 *    để xác nhận trạng thái DB đúng như mong đợi.
 * ==================================================================
 */

// ── Kết nối MongoDB in-memory (rollback tự động giữa các test) ─────
require('./helpers/setupMongoMemory');

const request       = require('supertest');
const mongoose      = require('mongoose');
const buildApp      = require('./helpers/testApp');
const expenseRoutes = require('../routes/expenseRoutes');
const Expense       = require('../models/Expense'); // Model dùng để CheckDB

// ── Tạo Express app tối giản chỉ mount expenseRoutes ──────────────
const app = buildApp(expenseRoutes, '/api/v1/expense');

// ── Tạo 2 userId giả cố định để kiểm tra phân quyền ownership ────
// FAKE_USER_ID    = user đang đăng nhập (authenticated user)
// ANOTHER_USER_ID = user khác (để test trường hợp cố sửa record của người khác)
const FAKE_USER_ID    = new mongoose.Types.ObjectId().toString();
const ANOTHER_USER_ID = new mongoose.Types.ObjectId().toString();

// ── Mock authMiddleware với userId có thể thay đổi được ────────────
// TẠI SAO MOCK authMiddleware?
//   authMiddleware.protect() thật sự kiểm tra JWT token trong Authorization header.
//   Trong test, chúng ta không muốn phải tạo token thật cho từng request.
//   Mock này bypass xác thực và inject thẳng userId vào req.user,
//   cho phép từng test tự chọn mình đang "đăng nhập" bằng user nào.
//
// __setUserId() là phương thức bổ sung để test có thể chuyển đổi
// giữa các userId (ví dụ: chuyển sang ANOTHER_USER_ID để test 403 Forbidden).
jest.mock('../middleware/authMiddleware', () => {
    let currentUserId = null; // userId hiện tại sẽ được inject vào req.user

    const mockProtect = (req, _res, next) => {
        req.user = { id: currentUserId }; // giả lập user đang đăng nhập
        next(); // bỏ qua xác thực, tiếp tục sang controller
    };

    // Phương thức helper để test thay đổi "ai đang đăng nhập"
    mockProtect.__setUserId = (id) => { currentUserId = id; };
    return { protect: mockProtect };
});

const { protect: mockProtect } = require('../middleware/authMiddleware');

// ── Trước MỖI test: đặt lại user đang đăng nhập về FAKE_USER_ID ───
// Đảm bảo mặc định là "người dùng hợp lệ đang đăng nhập".
// Các test cần giả lập user khác sẽ tự gọi mockProtect.__setUserId(ANOTHER_USER_ID).
beforeEach(() => {
    mockProtect.__setUserId(FAKE_USER_ID);
});

// ──────────────────────────────────────────────────────────────────
// Helper: tạo trực tiếp một Expense record vào DB in-memory
// Dùng để chuẩn bị dữ liệu nền cho các test cần record đã tồn tại sẵn
// (ví dụ: test update/delete cần record để update/delete)
// ──────────────────────────────────────────────────────────────────
async function seedExpenseRecord({
    userId   = FAKE_USER_ID, // mặc định thuộc về FAKE_USER_ID
    category = 'Food',
    amount   = 150_000,
    date     = new Date('2024-01-15'),
    icon     = '🍔',
} = {}) {
    // Tạo record trực tiếp trong DB (không qua API) để nhanh hơn
    return Expense.create({ userId, category, amount, date, icon });
}


// ══════════════════════════════════════════════════════════════════
// expenseController → addExpense()
// Kiểm tra chức năng: Thêm chi phí mới
// ══════════════════════════════════════════════════════════════════
describe('expenseController → addExpense()', () => {

    // TC-EXP-001 ──────────────────────────────────────────────────
    // Kịch bản happy path: thêm chi phí với đầy đủ thông tin hợp lệ
    it('TC-EXP-001: should save and return a new expense with all valid fields (HTTP 200)', async () => {
        const payload = {
            icon     : '🍔',
            category : 'Food',
            amount   : 150_000,
            date     : '2024-01-15',
        };

        // Gửi POST /api/v1/expense/add với dữ liệu chi phí
        const response = await request(app)
            .post('/api/v1/expense/add')
            .send(payload);

        expect(response.status).toBe(200);
        // Response phải trả về record vừa tạo với đúng category và amount
        expect(response.body.category).toBe(payload.category);
        expect(response.body.amount).toBe(payload.amount);

        // ── CheckDB: xác nhận record đã được ghi vào MongoDB ──────
        // Truy vấn trực tiếp bằng _id trong response để kiểm tra
        const savedRecord = await Expense.findById(response.body._id);
        expect(savedRecord).not.toBeNull();                     // phải tồn tại
        expect(savedRecord.category).toBe(payload.category);   // category đúng
        expect(savedRecord.amount).toBe(payload.amount);        // amount đúng
    });

    // TC-EXP-002 ──────────────────────────────────────────────────
    // Kịch bản lỗi: thiếu trường category bắt buộc
    it('TC-EXP-002: should return HTTP 400 when the category field is missing', async () => {
        // EP (Equivalence Partitioning) Invalid class: thiếu required field
        const response = await request(app)
            .post('/api/v1/expense/add')
            .send({ amount: 150_000, date: '2024-01-15' }); // không có category

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/required/i);

        // ── CheckDB: không có record nào được tạo ─────────────────
        expect(await Expense.countDocuments()).toBe(0);
    });

    // TC-EXP-003 ──────────────────────────────────────────────────
    // Kịch bản lỗi: thiếu trường amount bắt buộc
    it('TC-EXP-003: should return HTTP 400 when the amount field is missing', async () => {
        const response = await request(app)
            .post('/api/v1/expense/add')
            .send({ category: 'Food', date: '2024-01-15' }); // không có amount

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/required/i);

        // Xác nhận không có gì được lưu vào DB
        expect(await Expense.countDocuments()).toBe(0);
    });

    // TC-EXP-004 ──────────────────────────────────────────────────
    // BVA (Boundary Value Analysis): amount = 1 là giá trị dương tối thiểu
    it('TC-EXP-004: should accept amount = 1 (minimum positive boundary) and save successfully (BVA)', async () => {
        // BVA lower boundary: 1 là số dương nhỏ nhất hợp lệ
        const response = await request(app)
            .post('/api/v1/expense/add')
            .send({ category: 'Misc', amount: 1, date: '2024-01-15' });

        expect(response.status).toBe(200);
        expect(response.body.amount).toBe(1);

        // ── CheckDB: amount = 1 phải được lưu đúng ────────────────
        const savedRecord = await Expense.findById(response.body._id);
        expect(savedRecord.amount).toBe(1);
    });
});


// ══════════════════════════════════════════════════════════════════
// expenseController → getAllExpense()
// Kiểm tra chức năng: Lấy danh sách tất cả chi phí của user đang đăng nhập,
// được sắp xếp theo ngày giảm dần (mới nhất trước)
// ══════════════════════════════════════════════════════════════════
describe('expenseController → getAllExpense()', () => {

    it('TC-EXP helper: getAllExpense returns expenses sorted by date desc for the authenticated user', async () => {
        // Seed 2 records với ngày khác nhau
        await seedExpenseRecord({ category: 'Old',    date: new Date('2024-01-01') });
        await seedExpenseRecord({ category: 'Recent', date: new Date('2024-06-01') });

        const response = await request(app).get('/api/v1/expense/get');

        expect(response.status).toBe(200);
        expect(response.body.length).toBe(2);
        // Record mới nhất (Recent - tháng 6) phải xuất hiện đầu tiên
        expect(response.body[0].category).toBe('Recent');
    });
});


// ══════════════════════════════════════════════════════════════════
// expenseController → updateExpense()
// Kiểm tra chức năng: Cập nhật thông tin chi phí
// Bao gồm kiểm tra phân quyền: chỉ owner mới được sửa record của mình
// ══════════════════════════════════════════════════════════════════
describe('expenseController → updateExpense()', () => {

    // TC-EXP-005 ──────────────────────────────────────────────────
    // Kịch bản happy path: user sửa record của chính mình
    it('TC-EXP-005: should update an expense the authenticated user owns and return HTTP 200', async () => {
        // Seed record thuộc về FAKE_USER_ID (user đang đăng nhập)
        const ownedRecord = await seedExpenseRecord({
            userId   : FAKE_USER_ID,
            category : 'Food',
            amount   : 150_000,
        });

        const updatedPayload = {
            category : 'Transport',
            amount   : 50_000,
            date     : '2024-02-01',
        };

        // Gửi PUT request để update record của mình
        const response = await request(app)
            .put(`/api/v1/expense/${ownedRecord._id}`)
            .send(updatedPayload);

        expect(response.status).toBe(200);
        // Response phải trả về dữ liệu đã cập nhật
        expect(response.body.category).toBe('Transport');
        expect(response.body.amount).toBe(50_000);

        // ── CheckDB: xác nhận thay đổi đã được lưu vào DB ────────
        const refreshedRecord = await Expense.findById(ownedRecord._id);
        expect(refreshedRecord.category).toBe('Transport');
        expect(refreshedRecord.amount).toBe(50_000);
    });

    // TC-EXP-006 ──────────────────────────────────────────────────
    // Decision Table: user cố sửa record của NGƯỜI KHÁC → phải bị từ chối
    it('TC-EXP-006: should return HTTP 403 when trying to update another user\'s expense (Decision Table)', async () => {
        // Seed record thuộc về ANOTHER_USER_ID (không phải user đang đăng nhập)
        const otherUsersRecord = await seedExpenseRecord({ userId: ANOTHER_USER_ID });

        // FAKE_USER_ID đang đăng nhập (set bởi beforeEach) cố sửa record của ANOTHER_USER_ID
        const response = await request(app)
            .put(`/api/v1/expense/${otherUsersRecord._id}`)
            .send({ category: 'Hack', amount: 999, date: '2024-02-01' });

        expect(response.status).toBe(403); // Forbidden
        expect(response.body.message).toMatch(/not authorized/i);

        // ── CheckDB: record gốc phải KHÔNG bị thay đổi ────────────
        const unchangedRecord = await Expense.findById(otherUsersRecord._id);
        expect(unchangedRecord.category).toBe('Food'); // giá trị seed mặc định
    });

    // TC-EXP-007 ──────────────────────────────────────────────────
    // Kịch bản lỗi: record cần update không tồn tại
    it('TC-EXP-007: should return HTTP 404 when the expense record does not exist', async () => {
        // Tạo một ObjectId hợp lệ nhưng không có record tương ứng trong DB
        const nonExistentId = new mongoose.Types.ObjectId();

        const response = await request(app)
            .put(`/api/v1/expense/${nonExistentId}`)
            .send({ category: 'X', amount: 100, date: '2024-02-01' });

        expect(response.status).toBe(404); // Not Found
        expect(response.body.message).toMatch(/not found/i);
    });
});


// ══════════════════════════════════════════════════════════════════
// expenseController → deleteExpense()
// Kiểm tra chức năng: Xóa chi phí
// ══════════════════════════════════════════════════════════════════
describe('expenseController → deleteExpense()', () => {

    // TC-EXP-008 ──────────────────────────────────────────────────
    // Kịch bản happy path: xóa record tồn tại thành công
    it('TC-EXP-008: should delete an existing expense record and return HTTP 200', async () => {
        // Seed một record để có thứ mà xóa
        const existingRecord = await seedExpenseRecord();

        // Gửi DELETE request với _id của record
        const response = await request(app)
            .delete(`/api/v1/expense/${existingRecord._id}`);

        expect(response.status).toBe(200);
        expect(response.body.message).toMatch(/deleted/i);

        // ── CheckDB: record phải không còn tồn tại trong DB ───────
        const deletedRecord = await Expense.findById(existingRecord._id);
        expect(deletedRecord).toBeNull(); // findById trả về null nếu không tìm thấy
    });
});


// ══════════════════════════════════════════════════════════════════
// expenseController → getUniqueCategories()
// Kiểm tra chức năng: Lấy danh sách các category duy nhất (không trùng lặp)
// Dùng để populate dropdown chọn category khi lọc chi phí
// ══════════════════════════════════════════════════════════════════
describe('expenseController → getUniqueCategories()', () => {

    // TC-EXP-009 ──────────────────────────────────────────────────
    // Kiểm tra: kết quả phải loại bỏ trùng lặp và sắp xếp theo alphabet
    it('TC-EXP-009: should return distinct, non-null categories sorted alphabetically', async () => {
        // Seed 3 records: 2 cùng category 'Food' → phải bị deduplicate
        await seedExpenseRecord({ category: 'Food' });
        await seedExpenseRecord({ category: 'Transport' });
        await seedExpenseRecord({ category: 'Food' }); // trùng lặp, phải bị loại bỏ

        const response = await request(app).get('/api/v1/expense/categories');

        expect(response.status).toBe(200);
        // Kết quả: ['Food', 'Transport'] (đã deduplicate và sort A→Z)
        expect(response.body).toEqual(['Food', 'Transport']);
    });
});

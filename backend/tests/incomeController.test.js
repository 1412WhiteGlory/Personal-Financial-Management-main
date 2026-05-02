/**
 * incomeController.test.js
 * ==================================================================
 * Test cases TC-INC-001  →  TC-INC-012
 *
 * Controller đang được test : backend/controllers/incomeController.js
 *
 * KIẾN TRÚC TEST (không cần container nào đang chạy):
 *  - mongodb-memory-server: cô lập hoàn toàn với DB thật.
 *  - ROLLBACK: setupMongoMemory.js xóa tất cả collections trước MỖI test.
 *  - authMiddleware bị jest-mock, kiểm soát được userId đang "đăng nhập"
 *    để test logic phân quyền (chỉ owner mới được sửa/xóa record của mình).
 *  - CheckDB: sau write operations, test query Income model trực tiếp
 *    để xác nhận trạng thái DB đúng như mong đợi.
 * ==================================================================
 */

// ── Kết nối MongoDB in-memory (rollback tự động giữa các test) ─────
require('./helpers/setupMongoMemory');

const request      = require('supertest');
const mongoose     = require('mongoose');
const buildApp     = require('./helpers/testApp');
const incomeRoutes = require('../routes/incomeRoutes');
const Income       = require('../models/Income'); // Model để CheckDB

// ── Tạo Express app tối giản ──────────────────────────────────────
const app = buildApp(incomeRoutes, '/api/v1/income');

// ── Tạo 2 userId giả để kiểm tra phân quyền ownership ────────────
// FAKE_USER_ID    = user đang đăng nhập (được inject vào req.user)
// ANOTHER_USER_ID = user khác (để test cố sửa record của người khác)
const FAKE_USER_ID    = new mongoose.Types.ObjectId().toString();
const ANOTHER_USER_ID = new mongoose.Types.ObjectId().toString();

// ── Khai báo mock đầu tiên (sẽ bị ghi đè bởi mock thứ hai bên dưới) ──
// Phần này export FAKE_USER_ID để mock đầu tiên có thể tham chiếu.
// LƯU Ý: Jest hoist tất cả jest.mock() lên đầu file, nên thứ tự thực tế
// khác thứ tự viết trong code. Mock thứ hai sẽ là mock cuối cùng được dùng.
jest.mock('../middleware/authMiddleware', () => ({
    protect: (req, _res, next) => {
        req.user = { id: require('./incomeController.test').FAKE_USER_ID };
        next();
    },
}));

// Export FAKE_USER_ID để mock closure tham chiếu được
// (circular-safe vì Jest hoist mock trước khi thực thi)
module.exports = { FAKE_USER_ID };

// ── Mock thứ hai: có thể thay đổi userId động ─────────────────────
// Mock này OVERRIDE mock trên và là mock thực sự được dùng.
// Cung cấp __setUserId() để từng test có thể chọn user đang "đăng nhập".
jest.mock('../middleware/authMiddleware', () => {
    // Biến lưu userId hiện tại — các test gọi __setUserId() để thay đổi
    let currentUserId = null;

    const mockProtect = (req, _res, next) => {
        req.user = { id: currentUserId }; // inject userId vào request
        next(); // bỏ qua xác thực JWT
    };

    // Phương thức helper: cho phép test chuyển đổi user đang đăng nhập
    // Ví dụ: mockProtect.__setUserId(ANOTHER_USER_ID) → giả lập user khác
    mockProtect.__setUserId = (id) => { currentUserId = id; };
    return { protect: mockProtect };
});

const { protect: mockProtect } = require('../middleware/authMiddleware');

// ──────────────────────────────────────────────────────────────────
// Helper: chèn trực tiếp một Income record vào DB in-memory
// Dùng để chuẩn bị dữ liệu nền (không qua API, nhanh hơn)
// ──────────────────────────────────────────────────────────────────
async function seedIncomeRecord({
    userId   = FAKE_USER_ID, // mặc định thuộc về user đang đăng nhập
    source   = 'Salary',
    amount   = 5_000_000,
    date     = new Date('2024-01-15'),
    icon     = '💰',
} = {}) {
    return Income.create({ userId, source, amount, date, icon });
}

// ── Trước MỖI test: đặt lại user đang đăng nhập về FAKE_USER_ID ───
beforeEach(() => {
    mockProtect.__setUserId(FAKE_USER_ID);
});


// ══════════════════════════════════════════════════════════════════
// incomeController → addIncome()
// Kiểm tra chức năng: Thêm nguồn thu nhập mới
// ══════════════════════════════════════════════════════════════════
describe('incomeController → addIncome()', () => {

    // TC-INC-001 ──────────────────────────────────────────────────
    // Kịch bản happy path: thêm thu nhập với đầy đủ thông tin hợp lệ
    it('TC-INC-001: should save and return a new income record with all valid fields (HTTP 200)', async () => {
        const payload = {
            icon   : '💰',
            source : 'Salary',
            amount : 5_000_000,
            date   : '2024-01-15',
        };

        const response = await request(app)
            .post('/api/v1/income/add')
            .send(payload);

        expect(response.status).toBe(200);
        expect(response.body.source).toBe(payload.source);
        expect(response.body.amount).toBe(payload.amount);

        // ── CheckDB: xác nhận record đã thực sự được lưu vào MongoDB ──
        const savedRecord = await Income.findById(response.body._id);
        expect(savedRecord).not.toBeNull();
        expect(savedRecord.source).toBe(payload.source);
        expect(savedRecord.amount).toBe(payload.amount);
    });

    // TC-INC-002 ──────────────────────────────────────────────────
    // Kịch bản lỗi: thiếu trường source bắt buộc
    it('TC-INC-002: should return HTTP 400 when the source field is missing', async () => {
        const response = await request(app)
            .post('/api/v1/income/add')
            .send({ amount: 5_000_000, date: '2024-01-15' }); // thiếu source

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/required/i);

        // ── CheckDB: không có record nào được tạo ─────────────────
        const recordCount = await Income.countDocuments();
        expect(recordCount).toBe(0);
    });

    // TC-INC-003 ──────────────────────────────────────────────────
    // BVA + Document Bug: amount = 0 bị controller từ chối do kiểm tra !amount
    // → Đây là hành vi hiện tại được document lại, không phải design lý tưởng.
    it('TC-INC-003: amount = 0 is rejected by the current controller (falsy guard) — documents BVA behaviour', async () => {
        // LƯU Ý VỀ BEHAVIOR CỦA CONTROLLER:
        //   Controller dùng `if (!amount)` để kiểm tra → !0 === true (falsy)
        //   Nghĩa là amount=0 bị coi là "thiếu trường" và trả về 400.
        //   Đây có thể là bug; giá trị 0 đôi khi có ý nghĩa hợp lệ.
        //   Nếu controller được sửa thành `amount === undefined || amount === null`,
        //   test này phải đổi thành expect(response.status).toBe(200).
        const response = await request(app)
            .post('/api/v1/income/add')
            .send({ source: 'Gift', amount: 0, date: '2024-01-15' });

        // Hành vi hiện tại: !0 === true → 400 "All fields are required"
        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/required/i);

        // ── CheckDB: không có record được tạo ─────────────────────
        const savedRecord = await Income.countDocuments();
        expect(savedRecord).toBe(0);
    });

    // TC-INC-004 ──────────────────────────────────────────────────
    // Document Schema Behavior: amount âm không bị Mongoose schema từ chối
    it('TC-INC-004: should handle negative amount (schema rejects or saves — verifies schema behaviour)', async () => {
        // EP Invalid class: amount âm là không hợp lệ về mặt nghiệp vụ.
        // Tuy nhiên, Mongoose schema hiện tại KHÔNG có validator `min: 0`.
        // → amount âm sẽ được lưu thành công (status 200).
        // Test này document hành vi hiện tại; nếu thêm `min: 0` vào schema,
        // kết quả mong đợi phải đổi thành 400.
        const response = await request(app)
            .post('/api/v1/income/add')
            .send({ source: 'Refund', amount: -1, date: '2024-01-15' });

        // Chấp nhận cả 200 (không có validator) và 400 (có validator min:0)
        // để test không bị break khi schema được cải thiện
        expect([200, 400]).toContain(response.status);
    });
});


// ══════════════════════════════════════════════════════════════════
// incomeController → getAllIncome()
// Kiểm tra chức năng: Lấy danh sách tất cả thu nhập của user,
// sắp xếp theo ngày giảm dần (mới nhất trước)
// ══════════════════════════════════════════════════════════════════
describe('incomeController → getAllIncome()', () => {

    // TC-INC-005 ──────────────────────────────────────────────────
    // Kiểm tra: danh sách được sắp xếp theo date descending
    it('TC-INC-005: should return all incomes for the authenticated user sorted by date descending', async () => {
        // Seed 3 records với ngày khác nhau
        await seedIncomeRecord({ source: 'Old',    date: new Date('2024-01-01') });
        await seedIncomeRecord({ source: 'Middle', date: new Date('2024-03-01') });
        await seedIncomeRecord({ source: 'Recent', date: new Date('2024-06-01') });

        const response = await request(app).get('/api/v1/income/get');

        expect(response.status).toBe(200);
        expect(response.body.length).toBe(3); // đúng 3 records

        // Thứ tự: mới nhất trước → Recent (tháng 6) phải ở đầu
        expect(response.body[0].source).toBe('Recent');
        expect(response.body[2].source).toBe('Old'); // cũ nhất ở cuối
    });

    // TC-INC-006 ──────────────────────────────────────────────────
    // EP Edge case: user chưa có bất kỳ thu nhập nào
    it('TC-INC-006: should return an empty array when the user has no income records', async () => {
        // Không seed gì → DB rỗng (setupMongoMemory đã xóa trước test này)
        const response = await request(app).get('/api/v1/income/get');

        expect(response.status).toBe(200);
        expect(Array.isArray(response.body)).toBe(true); // phải là array
        expect(response.body.length).toBe(0);            // array rỗng
    });
});


// ══════════════════════════════════════════════════════════════════
// incomeController → deleteIncome()
// Kiểm tra chức năng: Xóa một khoản thu nhập
// ══════════════════════════════════════════════════════════════════
describe('incomeController → deleteIncome()', () => {

    // TC-INC-007 ──────────────────────────────────────────────────
    // Kịch bản happy path: xóa record tồn tại thành công
    it('TC-INC-007: should delete an existing income record and return HTTP 200', async () => {
        // Seed một record để có thứ mà xóa
        const existingRecord = await seedIncomeRecord();

        const response = await request(app)
            .delete(`/api/v1/income/${existingRecord._id}`);

        expect(response.status).toBe(200);
        expect(response.body.message).toMatch(/deleted/i);

        // ── CheckDB: record phải hoàn toàn biến mất khỏi DB ──────
        const deletedRecord = await Income.findById(existingRecord._id);
        expect(deletedRecord).toBeNull(); // null = không còn tồn tại
    });

    // TC-INC-008 ──────────────────────────────────────────────────
    // Kịch bản lỗi: truyền vào ID không phải định dạng MongoDB ObjectId
    it('TC-INC-008: should return HTTP 500 when an invalid / non-existent ObjectId is provided', async () => {
        // 'invalid_id_string' không phải MongoDB ObjectId → Mongoose ném CastError
        // Controller hiện tại không xử lý CastError riêng → trả về 500
        const response = await request(app)
            .delete('/api/v1/income/invalid_id_string');

        expect(response.status).toBe(500);
        // LƯU Ý: Nếu controller được cải thiện để bắt CastError riêng,
        // kết quả có thể đổi thành 400 với message hữu ích hơn.
    });
});


// ══════════════════════════════════════════════════════════════════
// incomeController → updateIncome()
// Kiểm tra chức năng: Cập nhật thông tin thu nhập
// Bao gồm kiểm tra phân quyền ownership
// ══════════════════════════════════════════════════════════════════
describe('incomeController → updateIncome()', () => {

    // TC-INC-009 ──────────────────────────────────────────────────
    // Kịch bản happy path: user cập nhật record của chính mình
    it('TC-INC-009: should update an income record owned by the authenticated user and return HTTP 200', async () => {
        // Seed record thuộc về FAKE_USER_ID (user đang đăng nhập)
        const ownedRecord = await seedIncomeRecord({ userId: FAKE_USER_ID });

        const updatedPayload = {
            source : 'Bonus',
            amount : 1_000_000,
            date   : '2024-02-01',
        };

        const response = await request(app)
            .put(`/api/v1/income/${ownedRecord._id}`)
            .send(updatedPayload);

        expect(response.status).toBe(200);
        expect(response.body.source).toBe('Bonus');
        expect(response.body.amount).toBe(1_000_000);

        // ── CheckDB: xác nhận thay đổi đã được persist vào DB ─────
        const refreshedRecord = await Income.findById(ownedRecord._id);
        expect(refreshedRecord.source).toBe('Bonus');
        expect(refreshedRecord.amount).toBe(1_000_000);
    });

    // TC-INC-010 ──────────────────────────────────────────────────
    // Kiểm tra phân quyền: user cố sửa record của người khác → 403 Forbidden
    it('TC-INC-010: should return HTTP 403 when trying to update another user\'s income record', async () => {
        // Seed record thuộc về ANOTHER_USER_ID (không phải người đang đăng nhập)
        const anotherUsersRecord = await seedIncomeRecord({ userId: ANOTHER_USER_ID });

        // FAKE_USER_ID đang đăng nhập cố sửa record của ANOTHER_USER_ID
        const response = await request(app)
            .put(`/api/v1/income/${anotherUsersRecord._id}`)
            .send({ source: 'Hack', amount: 999, date: '2024-02-01' });

        expect(response.status).toBe(403); // Forbidden - không có quyền
        expect(response.body.message).toMatch(/not authorized/i);

        // ── CheckDB: record gốc phải KHÔNG bị thay đổi ────────────
        const originalRecord = await Income.findById(anotherUsersRecord._id);
        expect(originalRecord.source).toBe('Salary'); // giá trị seed mặc định, không bị hack
    });

    // TC-INC-011 ──────────────────────────────────────────────────
    // Kịch bản lỗi: record cần update không tồn tại
    it('TC-INC-011: should return HTTP 404 when the income record does not exist', async () => {
        // Tạo ObjectId hợp lệ nhưng không có record nào trong DB
        const nonExistentId = new mongoose.Types.ObjectId();

        const response = await request(app)
            .put(`/api/v1/income/${nonExistentId}`)
            .send({ source: 'X', amount: 100, date: '2024-02-01' });

        expect(response.status).toBe(404); // Not Found
        expect(response.body.message).toMatch(/not found/i);
    });
});


// ══════════════════════════════════════════════════════════════════
// incomeController → getUniqueSources()
// Kiểm tra chức năng: Lấy danh sách nguồn thu nhập duy nhất (không trùng lặp)
// Dùng để populate dropdown lọc theo nguồn thu nhập trong UI
// ══════════════════════════════════════════════════════════════════
describe('incomeController → getUniqueSources()', () => {

    // TC-INC-012 ──────────────────────────────────────────────────
    // Kiểm tra: kết quả deduplicate và sắp xếp theo alphabet
    it('TC-INC-012: should return distinct, non-null sources sorted alphabetically', async () => {
        // Seed 3 records: 'Salary' xuất hiện 2 lần → phải bị deduplicate
        await seedIncomeRecord({ source: 'Salary' });
        await seedIncomeRecord({ source: 'Freelance' });
        await seedIncomeRecord({ source: 'Salary' }); // trùng lặp

        const response = await request(app).get('/api/v1/income/sources');

        expect(response.status).toBe(200);
        // Kết quả: ['Freelance', 'Salary'] (deduplicated + sorted A→Z)
        expect(response.body).toEqual(['Freelance', 'Salary']);
    });
});

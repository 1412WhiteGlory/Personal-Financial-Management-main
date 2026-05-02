/**
 * helpers/setupMongoMemory.js
 * ------------------------------------------------------------------
 * Khởi động một instance MongoDB in-memory (không cần container thật)
 * cho mỗi test suite và tắt nó đi sau khi tất cả test hoàn thành.
 *
 * TẠI SAO DÙNG mongodb-memory-server?
 *   - Không cần Docker hoặc MongoDB thật đang chạy.
 *   - Mỗi test suite có database riêng biệt, hoàn toàn cô lập.
 *   - Tốc độ nhanh hơn vì dữ liệu nằm trong RAM.
 *
 * CHIẾN LƯỢC ROLLBACK (đảm bảo test không ảnh hưởng lẫn nhau):
 *   • beforeEach  → Xóa toàn bộ dữ liệu trong tất cả collections trước
 *                   MỖI test, đảm bảo mỗi test bắt đầu từ trạng thái sạch.
 *   • afterAll    → Ngắt kết nối Mongoose + dừng memory server để giải
 *                   phóng tài nguyên hệ thống sau khi test suite kết thúc.
 *
 * CÁCH DÙNG (thêm dòng này ở đầu mỗi file test cần MongoDB):
 *   require('./helpers/setupMongoMemory');
 * ------------------------------------------------------------------
 */

const mongoose = require('mongoose');
const { MongoMemoryServer } = require('mongodb-memory-server');

// Biến lưu tham chiếu tới instance MongoDB in-memory
// để có thể dừng nó trong afterAll
let mongoMemoryServer;

// ── Lifecycle: kết nối MongoDB trước khi chạy test đầu tiên ────────
beforeAll(async () => {
    // Tạo và khởi động một instance MongoDB in-memory riêng biệt.
    // MongoMemoryServer.create() tự động chọn port trống trên máy,
    // nên nhiều suite test có thể chạy song song mà không bị xung đột.
    mongoMemoryServer = await MongoMemoryServer.create();
    const mongoUri = mongoMemoryServer.getUri(); // lấy URI dạng mongodb://127.0.0.1:PORT/

    // Kết nối Mongoose tới instance tạm thời này.
    // Tất cả các Model (User, Income, Expense, ...) sẽ dùng kết nối này trong khi test.
    await mongoose.connect(mongoUri);
});

// ── Rollback: xóa sạch dữ liệu trước mỗi test riêng lẻ ────────────
beforeEach(async () => {
    // Lấy danh sách tất cả collections hiện có trong database (ví dụ: users, incomes, expenses...).
    // Sau đó xóa toàn bộ documents trong từng collection.
    //
    // ĐÂY LÀ CƠ CHẾ ROLLBACK CHÍNH:
    //   - Đảm bảo test A không để lại "rác" ảnh hưởng test B.
    //   - Tương đương với BEGIN TRANSACTION + ROLLBACK trong SQL.
    //   - Nhờ vậy thứ tự chạy test không quan trọng.
    const collectionNames = Object.keys(mongoose.connection.collections);
    for (const name of collectionNames) {
        await mongoose.connection.collections[name].deleteMany({});
    }
});

// ── Teardown: giải phóng tài nguyên sau khi cả suite hoàn thành ─────
afterAll(async () => {
    // Ngắt kết nối Mongoose để không còn kết nối mở nào còn lại.
    await mongoose.disconnect();

    // Dừng và giải phóng instance MongoDB in-memory khỏi bộ nhớ RAM.
    await mongoMemoryServer.stop();
});

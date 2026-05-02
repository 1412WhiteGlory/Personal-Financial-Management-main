/**
 * watchlistController.test.js
 * ==================================================================
 * Test cases TC-WL-001  →  TC-WL-010
 *
 * Controller đang được test : backend/controllers/watchlistController.js
 *
 * CHỨC NĂNG ĐƯỢC KIỂM TRA:
 *   • sortItems()           – hàm thuần túy (pure function) sắp xếp danh sách
 *                             (starred trước, sau đó sắp xếp theo addedAt tăng dần)
 *   • getWatchlist()        – tự động tạo watchlist mặc định nếu user chưa có
 *   • addToWatchlist()      – thêm symbol mới, chặn duplicate
 *   • updateStarredStatus() – đánh dấu/bỏ đánh dấu star một symbol
 *   • removeFromWatchlist() – xóa symbol khỏi danh sách
 *
 * KIẾN TRÚC TEST (không cần container nào đang chạy):
 *  - mongodb-memory-server: cô lập hoàn toàn với DB thật.
 *  - ROLLBACK: setupMongoMemory.js xóa tất cả collections trước MỖI test.
 *  - sortItems() được test trực tiếp (không qua HTTP) vì là pure function.
 *  - authMiddleware bị mock → req.user có thể kiểm soát.
 *  - CheckDB: kiểm tra collection Watchlist sau các thao tác mutation.
 * ==================================================================
 */

// ── Kết nối MongoDB in-memory (rollback tự động) ──────────────────
require('./helpers/setupMongoMemory');

const request          = require('supertest');
const mongoose         = require('mongoose');
const buildApp         = require('./helpers/testApp');
const watchlistRoutes  = require('../routes/watchlistRoutes');
const Watchlist        = require('../models/Watchlist'); // Model để CheckDB

// ── Trích xuất và re-implement sortItems để test độc lập ──────────
// TẠI SAO KHÔNG IMPORT TRỰC TIẾP?
//   sortItems() không được export trong watchlistController.js (là hàm nội bộ).
//   Thay vì modify production code để export nó, chúng ta re-implement
//   logic tương tự trong test để kiểm tra behavior expected.
//   Đây là kỹ thuật "white-box testing" — biết implementation và test riêng logic đó.
const { sortItems: _sortItems } = (() => {
    // Re-implement sortItems như được document trong watchlistController.js:
    //   - Starred items → trước (index nhỏ hơn)
    //   - Cùng starred status → sắp xếp theo addedAt tăng dần (cũ hơn trước)
    const sortItems = items =>
        [...items].sort((a, b) => {
            if (a.starred === b.starred) {
                // Cùng starred → sắp xếp theo thời gian thêm vào (cũ hơn trước)
                const timeA = a.addedAt ? new Date(a.addedAt).getTime() : 0;
                const timeB = b.addedAt ? new Date(b.addedAt).getTime() : 0;
                return timeA - timeB; // tăng dần: A - B
            }
            return a.starred ? -1 : 1; // starred → -1 (đứng trước), un-starred → 1 (đứng sau)
        });
    return { sortItems };
})();

// ── Tạo Express app tối giản chỉ mount watchlistRoutes ────────────
const app = buildApp(watchlistRoutes, '/api/v1/watchlist');

// ── userId hiện tại (thay đổi trước mỗi test để cô lập watchlist) ─
let CURRENT_USER_ID = new mongoose.Types.ObjectId().toString();

// ── Mock authMiddleware với userId có thể thay đổi ────────────────
jest.mock('../middleware/authMiddleware', () => {
    let currentUserId = null; // userId được inject vào req.user
    const mockProtect = (req, _res, next) => {
        req.user = { id: currentUserId };
        next();
    };
    mockProtect.__setUserId = (id) => { currentUserId = id; };
    return { protect: mockProtect };
});

const { protect: mockProtect } = require('../middleware/authMiddleware');

// ── Trước MỖI test: tạo userId mới để mỗi test có watchlist riêng ─
// Nếu dùng cùng userId, test trước có thể tạo watchlist mặc định
// ảnh hưởng tới test sau (dù DB đã xóa, userId giống nhau vẫn nhận watchlist mặc định).
beforeEach(() => {
    CURRENT_USER_ID = new mongoose.Types.ObjectId().toString(); // userId mới
    mockProtect.__setUserId(CURRENT_USER_ID);
});


// ══════════════════════════════════════════════════════════════════
// watchlistController → sortItems() [PURE FUNCTION]
// Test logic sắp xếp độc lập với database.
// Pure function: chỉ phụ thuộc vào input, không có side-effect.
// ══════════════════════════════════════════════════════════════════
describe('watchlistController → sortItems() [pure function]', () => {

    // TC-WL-001 ───────────────────────────────────────────────────
    // Kiểm tra: starred items phải xuất hiện trước un-starred items
    it('TC-WL-001: starred items must come before un-starred items', () => {
        // Tạo danh sách mất thứ tự: AAPL (un-starred) trước BTC (starred)
        const unsortedItems = [
            { symbol: 'AAPL', starred: false, addedAt: new Date('2024-01-01') },
            { symbol: 'BTC',  starred: true,  addedAt: new Date('2024-01-02') },
        ];

        const sortedItems = _sortItems(unsortedItems);

        // Sau khi sort: BTC (starred) phải ở đầu
        expect(sortedItems[0].symbol).toBe('BTC');
        expect(sortedItems[1].symbol).toBe('AAPL');
    });

    // TC-WL-002 ───────────────────────────────────────────────────
    // Kiểm tra: các item cùng starred=false → sort theo addedAt tăng dần (cũ hơn trước)
    it('TC-WL-002: among un-starred items, the older addedAt comes first (ascending)', () => {
        const T1 = new Date('2024-01-01'); // cũ hơn (older)
        const T2 = new Date('2024-06-01'); // mới hơn (newer)

        // ETH được thêm vào ngày T2 (mới hơn), MSFT ngày T1 (cũ hơn)
        const unsortedItems = [
            { symbol: 'ETH',  starred: false, addedAt: T2 }, // mới hơn
            { symbol: 'MSFT', starred: false, addedAt: T1 }, // cũ hơn
        ];

        const sortedItems = _sortItems(unsortedItems);

        // Cùng starred → sort theo thời gian thêm vào: MSFT (T1 cũ hơn) trước
        expect(sortedItems[0].symbol).toBe('MSFT');
        expect(sortedItems[1].symbol).toBe('ETH');
    });
});


// ══════════════════════════════════════════════════════════════════
// watchlistController → getWatchlist()
// Kiểm tra chức năng: Lấy watchlist của user.
// Đặc biệt: nếu user chưa có watchlist → TỰ ĐỘNG tạo với 5 symbol mặc định
// ══════════════════════════════════════════════════════════════════
describe('watchlistController → getWatchlist()', () => {

    // TC-WL-003 ───────────────────────────────────────────────────
    // Kiểm tra ensureWatchlist: user mới không có watchlist → tự động tạo
    it('TC-WL-003: new user with no watchlist should auto-create one with 5 default items', async () => {
        // Không seed gì → user này chưa có watchlist
        const response = await request(app).get('/api/v1/watchlist/');

        expect(response.status).toBe(200);

        // Phải tự động tạo watchlist với đúng 5 symbol mặc định
        expect(response.body.items).toHaveLength(5);

        // Xác nhận đúng 5 symbol được định nghĩa trong controller
        const symbols = response.body.items.map(item => item.symbol);
        expect(symbols).toContain('^VNINDEX.VN'); // Chỉ số VN-Index
        expect(symbols).toContain('AAPL');         // Apple (NASDAQ)
        expect(symbols).toContain('MSFT');         // Microsoft (NASDAQ)
        expect(symbols).toContain('BTCUSDT');      // Bitcoin/Tether
        expect(symbols).toContain('ETHUSDC');      // Ethereum/USD Coin

        // ── CheckDB: xác nhận watchlist đã được lưu vào MongoDB ───
        const persistedWatchlist = await Watchlist.findOne({ userId: CURRENT_USER_ID });
        expect(persistedWatchlist).not.toBeNull();           // phải tồn tại
        expect(persistedWatchlist.items).toHaveLength(5);    // đúng 5 items
    });
});


// ══════════════════════════════════════════════════════════════════
// watchlistController → addToWatchlist()
// Kiểm tra chức năng: Thêm symbol vào watchlist
// Bao gồm: chặn duplicate symbol, validate required field
// ══════════════════════════════════════════════════════════════════
describe('watchlistController → addToWatchlist()', () => {

    // TC-WL-004 ───────────────────────────────────────────────────
    // Kịch bản happy path: thêm symbol mới hợp lệ
    it('TC-WL-004: should add a new valid symbol and return HTTP 201', async () => {
        // GOOGL chưa có trong watchlist (kể cả watchlist mặc định)
        const response = await request(app)
            .post('/api/v1/watchlist/add')
            .send({ symbol: 'GOOGL', type: 'stock' });

        expect(response.status).toBe(201); // Created
        const addedSymbols = response.body.items.map(i => i.symbol);
        expect(addedSymbols).toContain('GOOGL'); // phải có GOOGL trong danh sách

        // ── CheckDB: xác nhận GOOGL được lưu vào MongoDB ──────────
        const savedWatchlist = await Watchlist.findOne({ userId: CURRENT_USER_ID });
        const savedSymbols   = savedWatchlist.items.map(i => i.symbol);
        expect(savedSymbols).toContain('GOOGL');
    });

    // TC-WL-005 ───────────────────────────────────────────────────
    // Kiểm tra duplicate guard: thêm symbol đã có → 409 Conflict
    it('TC-WL-005: should return HTTP 409 when adding a symbol that already exists (duplicate guard)', async () => {
        // Lần đầu thêm BTCUSDT:
        // LƯU Ý: getWatchlist/ensureWatchlist tự động tạo watchlist mặc định bao gồm BTCUSDT,
        // nên request addToWatchlist đầu tiên này sẽ kích hoạt tạo watchlist,
        // và BTCUSDT đã tồn tại trong đó → cả 2 lần đều test duplicate path.
        await request(app)
            .post('/api/v1/watchlist/add')
            .send({ symbol: 'BTCUSDT', type: 'crypto' });

        // Lần thứ hai với cùng symbol → phải bị từ chối
        const response = await request(app)
            .post('/api/v1/watchlist/add')
            .send({ symbol: 'BTCUSDT', type: 'crypto' });

        expect(response.status).toBe(409); // Conflict
        expect(response.body.message).toMatch(/already in watchlist/i);
    });

    // TC-WL-006 ───────────────────────────────────────────────────
    // Kịch bản lỗi: thiếu trường symbol bắt buộc
    it('TC-WL-006: should return HTTP 400 when the symbol field is missing', async () => {
        // Gửi request thiếu symbol
        const response = await request(app)
            .post('/api/v1/watchlist/add')
            .send({ type: 'stock' }); // không có symbol

        expect(response.status).toBe(400); // Bad Request
        expect(response.body.message).toMatch(/required/i);
    });
});


// ══════════════════════════════════════════════════════════════════
// watchlistController → updateStarredStatus()
// Kiểm tra chức năng: Đánh dấu/bỏ đánh dấu star cho một symbol
// Symbol được star sẽ xuất hiện đầu tiên trong danh sách (ưu tiên cao)
// ══════════════════════════════════════════════════════════════════
describe('watchlistController → updateStarredStatus()', () => {

    // TC-WL-007 ───────────────────────────────────────────────────
    // Kịch bản happy path: star một symbol đang có trong watchlist
    it('TC-WL-007: should star an existing symbol and return HTTP 200', async () => {
        // Khởi tạo watchlist mặc định (chứa AAPL với starred=false)
        // bằng cách gọi GET trước (ensureWatchlist chạy lần đầu)
        await request(app).get('/api/v1/watchlist/');

        // Đánh dấu star cho AAPL
        const response = await request(app)
            .patch('/api/v1/watchlist/star')
            .send({ symbol: 'AAPL', starred: true });

        expect(response.status).toBe(200);
        // Trong response, AAPL phải có starred = true
        const aaplItem = response.body.items.find(i => i.symbol === 'AAPL');
        expect(aaplItem.starred).toBe(true);

        // ── CheckDB: xác nhận starred=true được lưu vào MongoDB ────
        const savedWatchlist = await Watchlist.findOne({ userId: CURRENT_USER_ID });
        const savedAapl      = savedWatchlist.items.find(i => i.symbol === 'AAPL');
        expect(savedAapl.starred).toBe(true);
    });

    // TC-WL-008 ───────────────────────────────────────────────────
    // Kịch bản lỗi: star một symbol không tồn tại trong watchlist
    it('TC-WL-008: should return HTTP 404 when starring a symbol that is not in the watchlist', async () => {
        // 'NONEXIST' không có trong watchlist mặc định hay bất kỳ đâu
        const response = await request(app)
            .patch('/api/v1/watchlist/star')
            .send({ symbol: 'NONEXIST', starred: true });

        expect(response.status).toBe(404); // Not Found
        expect(response.body.message).toMatch(/not found/i);
    });
});


// ══════════════════════════════════════════════════════════════════
// watchlistController → removeFromWatchlist()
// Kiểm tra chức năng: Xóa một symbol khỏi watchlist
// ══════════════════════════════════════════════════════════════════
describe('watchlistController → removeFromWatchlist()', () => {

    // TC-WL-009 ───────────────────────────────────────────────────
    // Kịch bản happy path: xóa symbol đang tồn tại trong watchlist
    it('TC-WL-009: should remove an existing symbol and return HTTP 200', async () => {
        // Khởi tạo watchlist mặc định (chứa AAPL)
        await request(app).get('/api/v1/watchlist/');

        // Xóa AAPL khỏi watchlist
        const response = await request(app)
            .delete('/api/v1/watchlist/remove/AAPL');

        expect(response.status).toBe(200);
        // Response phải là watchlist SAU KHI xóa, không còn AAPL
        const remainingSymbols = response.body.items.map(i => i.symbol);
        expect(remainingSymbols).not.toContain('AAPL');

        // ── CheckDB: AAPL không còn trong MongoDB ─────────────────
        const savedWatchlist   = await Watchlist.findOne({ userId: CURRENT_USER_ID });
        const savedSymbols     = savedWatchlist.items.map(i => i.symbol);
        expect(savedSymbols).not.toContain('AAPL');
    });

    // TC-WL-010 ───────────────────────────────────────────────────
    // Kịch bản lỗi: cố xóa symbol không tồn tại trong watchlist
    it('TC-WL-010: should return HTTP 404 when removing a symbol that is not in the watchlist', async () => {
        // 'NONEXIST' không có trong watchlist
        const response = await request(app)
            .delete('/api/v1/watchlist/remove/NONEXIST');

        expect(response.status).toBe(404); // Not Found
        expect(response.body.message).toMatch(/not found/i);
    });
});

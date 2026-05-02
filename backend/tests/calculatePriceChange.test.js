/**
 * calculatePriceChange.test.js
 * ==================================================================
 * Test cases TC-CALC-001  →  TC-CALC-011
 *
 * Service đang được test : backend/services/calculatePriceChange.js
 *
 * CHỨC NĂNG CỦA SERVICE:
 *   calculatePriceChange.js tính % thay đổi giá của tài sản tài chính
 *   (cổ phiếu, forex, crypto) bằng cách truy vấn dữ liệu lịch sử giá
 *   từ PostgreSQL và sử dụng Redis để cache.
 *
 * KIẾN TRÚC TEST (không cần container nào đang chạy):
 *   Tất cả các hàm trong service đều tương tác với PostgreSQL (pg pool)
 *   và Redis. CẢ HAI đều được jest.mock() hoàn toàn → không có kết nối
 *   thật nào được tạo ra.
 *
 *   ROLLBACK: Vì tất cả DB/cache đều là mock, không có gì thật để rollback.
 *   jest.clearAllMocks() trong afterEach reset trạng thái mock giữa các test
 *   (tương đương với rollback cho trạng thái mock).
 *
 *   CheckDB: Được xác minh qua mock.calls — test kiểm tra rằng SQL query
 *   đúng đã được gọi với đúng tham số, và kết quả tính toán đúng.
 * ==================================================================
 */

// ── Mock PostgreSQL pool TRƯỚC KHI import service ─────────────────
// TẠI SAO MOCK TRƯỚC KHI IMPORT?
//   Khi service được require(), nó ngay lập tức gọi require('../config/pg').
//   Nếu mock chưa sẵn sàng, service sẽ dùng pg thật và cố kết nối DB.
//   jest.mock() được Jest hoist lên đầu file nên luôn chạy trước require().
//
// pool.query là hàm duy nhất service dùng → chỉ cần mock mỗi query.
// Mỗi test sẽ dùng mockResolvedValueOnce() để định nghĩa giá trị trả về.
jest.mock('../config/pg', () => ({
    query: jest.fn(),
}));

// ── Mock Redis client TRƯỚC KHI import service ────────────────────
// Service dùng Redis để cache giá hiện tại của tài sản:
//   redis.get()   → đọc cache (cache HIT → không query DB)
//   redis.setex() → ghi cache sau khi query DB (cache MISS)
jest.mock('../config/redis', () => ({
    get   : jest.fn(),
    setex : jest.fn(),
}));

// ── Import service SAU KHI mock đã sẵn sàng ──────────────────────
const {
    calculateStockChange,   // Tính % thay đổi giá cổ phiếu (so sánh 2 ngày gần nhất)
    calculateForexChange,   // Tính % thay đổi giá forex (so sánh với giá mở cửa hôm nay)
    calculateCryptoChange,  // Tính % thay đổi giá crypto (so sánh với 24h trước)
    calculatePriceChange,   // Dispatcher: phân loại tài sản và gọi hàm phù hợp
} = require('../services/calculatePriceChange');

const pool  = require('../config/pg');    // mock PostgreSQL
const redis = require('../config/redis'); // mock Redis

// ── ID tài sản giả dùng chung trong tất cả test ──────────────────
const FAKE_ASSET_ID = 42;

// ── Reset tất cả mock sau MỖI test ───────────────────────────────
// Đảm bảo mockResolvedValueOnce() từ test trước không ảnh hưởng test sau.
// Tương đương với "rollback" trạng thái mock.
afterEach(() => {
    jest.clearAllMocks();
});


// ══════════════════════════════════════════════════════════════════
// calculateStockChange()
// Tính % thay đổi giá cổ phiếu bằng cách lấy 2 hàng OHLCV gần nhất:
//   Hàng 0 = giá đóng cửa hôm nay (currentPrice)
//   Hàng 1 = giá đóng cửa hôm qua (previousPrice)
//   Công thức: (currentPrice - previousPrice) / previousPrice × 100
// ══════════════════════════════════════════════════════════════════
describe('calculatePriceChange → calculateStockChange()', () => {

    // TC-CALC-001 ─────────────────────────────────────────────────
    // Happy path: có đủ 2 hàng OHLCV → tính được % thay đổi
    it('TC-CALC-001: should calculate correct % change when two OHLCV rows are available', async () => {
        // Định nghĩa giá trị mock DB trả về:
        //   row 0: close = 110 (hôm nay)
        //   row 1: close = 100 (hôm qua)
        pool.query.mockResolvedValueOnce({
            rows: [{ close: '110' }, { close: '100' }],
        });

        const result = await calculateStockChange(FAKE_ASSET_ID, null);

        // Công thức: (110 - 100) / 100 × 100 = 10%
        expect(result.changePercent).toBeCloseTo(10.0, 4); // 4 decimal places
        expect(result.currentPrice).toBe(110);
        expect(result.previousPrice).toBe(100);

        // CheckDB: xác nhận SQL được gọi đúng 1 lần với assetId đúng
        expect(pool.query).toHaveBeenCalledTimes(1);
        expect(pool.query.mock.calls[0][1]).toContain(FAKE_ASSET_ID);
    });

    // TC-CALC-002 ─────────────────────────────────────────────────
    // Edge case: chỉ có 1 hàng OHLCV → không có giá để so sánh → 0%
    it('TC-CALC-002: should return changePercent = 0 when only one OHLCV row is available', async () => {
        // Chỉ có giá hôm nay, không có giá hôm qua để so sánh
        pool.query.mockResolvedValueOnce({
            rows: [{ close: '100' }], // chỉ 1 row
        });

        const result = await calculateStockChange(FAKE_ASSET_ID, null);

        // Không đủ dữ liệu so sánh → % thay đổi = 0
        expect(result.changePercent).toBe(0);
        expect(result.currentPrice).toBe(100);
        expect(result.previousPrice).toBe(100); // dùng cùng giá cho cả 2
    });

    // TC-CALC-003 ─────────────────────────────────────────────────
    // Edge case: DB rỗng (không có dữ liệu nào) → trả về giá trị mặc định an toàn
    it('TC-CALC-003: should return null-safe defaults when no OHLCV rows exist (empty DB)', async () => {
        // Không có hàng nào trong DB
        pool.query.mockResolvedValueOnce({ rows: [] });

        const result = await calculateStockChange(FAKE_ASSET_ID, null);

        // Phải trả về defaults, không được crash
        expect(result.changePercent).toBe(0);
        expect(result.currentPrice).toBeNull(); // null = không có dữ liệu
    });
});


// ══════════════════════════════════════════════════════════════════
// calculateForexChange()
// Tính % thay đổi tỷ giá ngoại tệ:
//   Primary: so sánh giá hiện tại với giá mở cửa (open) của ngày hôm nay
//   Fallback: nếu không có open hôm nay (cuối tuần) → dùng open gần nhất
// ══════════════════════════════════════════════════════════════════
describe('calculatePriceChange → calculateForexChange()', () => {

    // TC-CALC-004 ─────────────────────────────────────────────────
    // Primary path: có open hôm nay → tính % change so với open hôm nay
    it('TC-CALC-004: should calculate % change vs today\'s open when today\'s open exists', async () => {
        // Mock: open hôm nay = 24,000 VND/USD
        pool.query.mockResolvedValueOnce({ rows: [{ open: '24000' }] });

        const currentPrice = 25_000; // giá hiện tại là 25,000 VND/USD
        const result = await calculateForexChange(FAKE_ASSET_ID, currentPrice);

        // Công thức: (25000 - 24000) / 24000 × 100 ≈ 4.17%
        expect(result.changePercent).toBeCloseTo(4.1667, 2);
        expect(result.previousPrice).toBe(24_000);
    });

    // TC-CALC-005 ─────────────────────────────────────────────────
    // Decision Table: không có open hôm nay (cuối tuần/ngày lễ) → fallback
    it('TC-CALC-005: should fall back to most-recent open when no data exists for today (weekend)', async () => {
        // Query 1 (open hôm nay): trả về rỗng → không có dữ liệu hôm nay
        // Query 2 (fallback): trả về open gần nhất = 24,500
        pool.query
            .mockResolvedValueOnce({ rows: [] })                        // không có hôm nay
            .mockResolvedValueOnce({ rows: [{ open: '24500' }] });      // fallback

        const currentPrice = 25_000;
        const result = await calculateForexChange(FAKE_ASSET_ID, currentPrice);

        expect(result.previousPrice).toBe(24_500); // dùng fallback
        // Công thức: (25000 - 24500) / 24500 × 100 ≈ 2.04%
        expect(result.changePercent).toBeCloseTo(2.0408, 2);
    });
});


// ══════════════════════════════════════════════════════════════════
// calculateCryptoChange()
// Tính % thay đổi giá crypto trong 24h:
//   Tier 1: tick data tại đúng 24h trước (chính xác nhất)
//   Tier 2: OHLCV hourly gần 24h trước (nếu không có tick)
//   Tier 3: OHLCV daily gần nhất (fallback cuối cùng)
// ══════════════════════════════════════════════════════════════════
describe('calculatePriceChange → calculateCryptoChange()', () => {

    // TC-CALC-006 ─────────────────────────────────────────────────
    // Tier 1: có tick data 24h trước → dùng giá tick (chính xác nhất)
    it('TC-CALC-006: should calculate % change vs tick price 24h ago (primary path)', async () => {
        // Tick 24h trước: BTC giá 45,000 USDT
        pool.query.mockResolvedValueOnce({ rows: [{ price: '45000' }] });

        const currentPrice = 50_000; // BTC hiện tại: 50,000 USDT
        const result = await calculateCryptoChange(FAKE_ASSET_ID, currentPrice);

        // Công thức: (50000 - 45000) / 45000 × 100 ≈ 11.11%
        expect(result.changePercent).toBeCloseTo(11.111, 2);
        expect(result.previousPrice).toBe(45_000);
    });

    // TC-CALC-007 ─────────────────────────────────────────────────
    // Decision Table Tier 2: không có tick → dùng hourly OHLCV
    it('TC-CALC-007: should fall back to hourly OHLCV when no tick data is available (tier-2 fallback)', async () => {
        // Query 1 (tick): rỗng → không có tick data
        // Query 2 (hourly OHLCV): close 24h trước = 46,000
        pool.query
            .mockResolvedValueOnce({ rows: [] })                        // tier 1: không có
            .mockResolvedValueOnce({ rows: [{ close: '46000' }] });     // tier 2: hourly

        const currentPrice = 50_000;
        const result = await calculateCryptoChange(FAKE_ASSET_ID, currentPrice);

        // Công thức: (50000 - 46000) / 46000 × 100 ≈ 8.70%
        expect(result.changePercent).toBeCloseTo(8.6957, 2);
        expect(result.previousPrice).toBe(46_000);
    });

    // TC-CALC-008 ─────────────────────────────────────────────────
    // Decision Table Tier 3: không có tick và không có hourly → dùng daily OHLCV
    it('TC-CALC-008: should fall back to daily OHLCV when both tick and hourly data are unavailable (tier-3 fallback)', async () => {
        // Query 1 (tick): rỗng
        // Query 2 (hourly): rỗng
        // Query 3 (daily OHLCV): close = 44,000
        pool.query
            .mockResolvedValueOnce({ rows: [] })                        // tier 1: không có
            .mockResolvedValueOnce({ rows: [] })                        // tier 2: không có
            .mockResolvedValueOnce({ rows: [{ close: '44000' }] });     // tier 3: daily

        const currentPrice = 50_000;
        const result = await calculateCryptoChange(FAKE_ASSET_ID, currentPrice);

        // Công thức: (50000 - 44000) / 44000 × 100 ≈ 13.64%
        expect(result.changePercent).toBeCloseTo(13.6364, 2);
        expect(result.previousPrice).toBe(44_000);
    });
});


// ══════════════════════════════════════════════════════════════════
// calculatePriceChange() – Hàm dispatcher chính
// Nhận asset type ('stock'/'forex'/'crypto') và định tuyến sang
// hàm tính toán phù hợp. Trước tiên lấy giá hiện tại từ Redis/DB.
// ══════════════════════════════════════════════════════════════════
describe('calculatePriceChange → calculatePriceChange() [dispatcher]', () => {

    // TC-CALC-009 ─────────────────────────────────────────────────
    // Kiểm tra: asset type 'stock' → gọi đúng path calculateStockChange
    it('TC-CALC-009: should route "stock" asset type to calculateStockChange path', async () => {
        // Cung cấp 2 hàng OHLCV để path stock có dữ liệu tính toán
        pool.query.mockResolvedValueOnce({
            rows: [{ close: '210' }, { close: '200' }],
        });

        const result = await calculatePriceChange(FAKE_ASSET_ID, 'AAPL', 'stock');

        // Stock change: (210 - 200) / 200 × 100 = 5%
        expect(result).not.toBeNull();
        expect(result.changePercent).toBeCloseTo(5.0, 4);
        expect(result.positive).toBe(true); // 5% > 0 → positive = true
    });

    // TC-CALC-010 ─────────────────────────────────────────────────
    // Kiểm tra: asset type 'crypto' → gọi đúng path calculateCryptoChange
    it('TC-CALC-010: should route "crypto" asset type to calculateCryptoChange path', async () => {
        // Dispatcher cần giá hiện tại trước (lấy từ Redis cache nếu có)
        // Mock: Redis trả về giá hiện tại từ cache → không cần query DB thêm
        redis.get.mockResolvedValueOnce('50000'); // cache HIT: BTC = 50,000 USDT

        // Mock query 24h tick cho calculateCryptoChange
        pool.query.mockResolvedValueOnce({ rows: [{ price: '45000' }] });

        const result = await calculatePriceChange(FAKE_ASSET_ID, 'BTCUSDT', 'crypto');

        expect(result).not.toBeNull();
        expect(result.changePercent).toBeCloseTo(11.111, 2); // (50000-45000)/45000*100
        expect(result.positive).toBe(true);
    });

    // TC-CALC-011 ─────────────────────────────────────────────────
    // Edge case: asset type không hợp lệ → không crash, trả về 0%
    it('TC-CALC-011: should return default 0% change and not crash for an unknown asset type', async () => {
        // Dispatcher cần current price từ Redis/DB (cho crypto/forex branch)
        redis.get.mockResolvedValueOnce('100'); // giả sử Redis có giá

        // Gọi với asset type 'unknown_xyz' không tồn tại trong switch-case
        const result = await calculatePriceChange(FAKE_ASSET_ID, 'UNKNOWN', 'unknown_xyz');

        // Default switch branch trả về changePercent = 0 mà không crash
        expect(result).not.toBeNull();
        expect(result.changePercent).toBe(0);
        expect(result.positive).toBe(true); // 0 >= 0 → positive = true
    });
});

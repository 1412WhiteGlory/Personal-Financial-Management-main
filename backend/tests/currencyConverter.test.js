/**
 * currencyConverter.test.js
 * ==================================================================
 * Test cases TC-CURR-001  →  TC-CURR-009
 *
 * Service đang được test : backend/services/currencyConverter.js
 *
 * CHỨC NĂNG CỦA SERVICE:
 *   currencyConverter.js chuyển đổi giá tài sản tài chính từ USD sang VND:
 *   - convertPrice()      : chuyển đổi một giá đơn lẻ
 *   - getExchangeRate()   : lấy tỷ giá USD/VND (từ Redis cache hoặc API)
 *   - convertPricesBulk() : chuyển đổi nhiều giá cùng lúc
 *
 * Đặc biệt: cổ phiếu HOSE (thị trường Việt Nam) đã là VND → bỏ qua chuyển đổi.
 *
 * KIẾN TRÚC TEST (không cần container nào đang chạy):
 *   • Redis bị mock → không có kết nối cache thật
 *   • axios (HTTP client) bị mock → không có request thật tới API tỷ giá
 *   • ROLLBACK: jest.clearAllMocks() trong afterEach reset trạng thái mock
 *   • CheckCache: xác minh bằng cách kiểm tra mock.calls (Redis/axios được gọi không?)
 * ==================================================================
 */

// ── Mock Redis TRƯỚC KHI import service ───────────────────────────
// Service dùng Redis để cache tỷ giá USD/VND (TTL thường 1 giờ):
//   redis.get()   → đọc cache (nếu có → tránh gọi API)
//   redis.setex() → ghi cache sau khi gọi API thành công
jest.mock('../config/redis', () => ({
    get   : jest.fn(), // mock get(key) → trả về null hoặc giá trị cache
    setex : jest.fn(), // mock setex(key, ttl, value) → ghi cache
}));

// ── Mock axios TRƯỚC KHI import service ───────────────────────────
// Service gọi axios.get() để lấy tỷ giá từ external API (ví dụ: exchangerate-api.com).
// Mock này ngăn request HTTP thật, giúp test nhanh và không phụ thuộc internet.
jest.mock('axios', () => ({
    get: jest.fn(), // mock axios.get(url) → trả về response giả
}));

// ── Import service và các module mock ─────────────────────────────
const {
    convertPrice,       // Chuyển đổi một giá từ USD sang VND
    getExchangeRate,    // Lấy tỷ giá USD/VND (cache-first)
    convertPricesBulk,  // Chuyển đổi hàng loạt giá
} = require('../services/currencyConverter');

const redis = require('../config/redis'); // Tham chiếu tới mock Redis
const axios = require('axios');           // Tham chiếu tới mock axios

// ── Reset tất cả mock sau MỖI test ───────────────────────────────
// Xóa lịch sử mock.calls và mock.instances để test không ảnh hưởng nhau
afterEach(() => {
    jest.clearAllMocks();
});


// ══════════════════════════════════════════════════════════════════
// currencyConverter → convertPrice()
// Chuyển đổi một giá từ USD sang VND.
// Logic phân nhánh:
//   1. exchange = 'HOSE' → giá đã là VND, trả về ngay (short-circuit)
//   2. price = 0, NaN, hoặc undefined → trả về 0 (guard branch)
//   3. Trường hợp bình thường → price (USD) × exchangeRate = giá VND
// ══════════════════════════════════════════════════════════════════
describe('currencyConverter → convertPrice()', () => {

    // TC-CURR-001 ─────────────────────────────────────────────────
    // Decision Table: exchange = HOSE → giá đã là VND, bỏ qua chuyển đổi
    it('TC-CURR-001: HOSE exchange should short-circuit and return price as-is in VND (no conversion)', async () => {
        // Cổ phiếu HOSE (Việt Nam) niêm yết bằng VND → không cần chuyển đổi
        const result = await convertPrice(50_000, 'HOSE', /* exchangeRate */ null);

        // Giá phải giữ nguyên (50,000 VND)
        expect(result.price).toBe(50_000);
        expect(result.currency).toBe('VND');
        expect(result.original).toBe(50_000);

        // CheckCache: Redis KHÔNG được gọi vì HOSE short-circuit trước khi cần tỷ giá
        expect(redis.get).not.toHaveBeenCalled();
    });

    // TC-CURR-002 ─────────────────────────────────────────────────
    // EP Valid class: sàn không phải HOSE → chuyển đổi USD → VND
    it('TC-CURR-002: non-HOSE exchange should convert USD price to VND using the provided rate', async () => {
        // Truyền exchangeRate trực tiếp (không qua Redis/API) để test đơn giản
        // NASDAQ: 100 USD × 25,000 VND/USD = 2,500,000 VND
        const result = await convertPrice(100, 'NASDAQ', 25_000);

        expect(result.price).toBe(2_500_000);             // 100 × 25000
        expect(result.currency).toBe('VND');
        expect(result.original).toBe(100);                 // giá gốc USD
        expect(result.originalCurrency).toBe('USD');
        expect(result.exchangeRate).toBe(25_000);          // tỷ giá đã dùng
    });

    // TC-CURR-003 ─────────────────────────────────────────────────
    // BVA lower boundary: price = 0 → guard branch trả về 0 VND
    it('TC-CURR-003: should return zeroed result when price = 0 (lower boundary BVA)', async () => {
        // Guard: `!price` trả về true khi price = 0 (falsy trong JS)
        // → hàm trả về result với price = 0 mà không cần tỷ giá
        const result = await convertPrice(0, 'BINANCE', 25_000);

        expect(result.price).toBe(0);
        expect(result.currency).toBe('VND');
        expect(result.original).toBe(0);
    });

    // TC-CURR-004 ─────────────────────────────────────────────────
    // EP Invalid class: price là NaN hoặc undefined → guard branch trả về 0
    it('TC-CURR-004: should return zeroed result when price is NaN or undefined (EP Invalid class)', async () => {
        // isNaN(NaN) === true → guard branch kích hoạt
        const resultNaN = await convertPrice(NaN, 'BINANCE', 25_000);
        expect(resultNaN.price).toBe(0);
        expect(resultNaN.currency).toBe('VND');

        // !undefined === true → guard branch kích hoạt
        const resultUnd = await convertPrice(undefined, 'BINANCE', 25_000);
        expect(resultUnd.price).toBe(0);
    });
});


// ══════════════════════════════════════════════════════════════════
// currencyConverter → getExchangeRate()
// Lấy tỷ giá USD/VND với chiến lược cache-first:
//   1. Kiểm tra Redis cache → nếu có (cache HIT) → trả về ngay
//   2. Cache MISS → gọi API → lưu vào Redis → trả về tỷ giá
//   3. API lỗi → trả về FALLBACK_RATE = 25,000 (hardcoded)
// ══════════════════════════════════════════════════════════════════
describe('currencyConverter → getExchangeRate()', () => {

    // TC-CURR-005 ─────────────────────────────────────────────────
    // Decision Table: cache HIT → trả về từ cache, không gọi API
    it('TC-CURR-005: should return the cached rate from Redis without calling the API (cache HIT)', async () => {
        // Mock: Redis trả về tỷ giá đã cache = 25,300 VND/USD
        redis.get.mockResolvedValueOnce('25300'); // string vì Redis lưu string

        const rate = await getExchangeRate();

        expect(rate).toBe(25300); // phải parse về number

        // CheckCache: Redis.get được gọi, axios.get KHÔNG được gọi (tiết kiệm API call)
        expect(redis.get).toHaveBeenCalledTimes(1);
        expect(axios.get).not.toHaveBeenCalled();
    });

    // TC-CURR-006 ─────────────────────────────────────────────────
    // Decision Table: cache MISS → gọi API → lưu vào cache → trả về
    it('TC-CURR-006: should fetch from API and cache the result on a cache MISS', async () => {
        redis.get.mockResolvedValueOnce(null);              // cache MISS
        axios.get.mockResolvedValueOnce({                   // API trả về thành công
            data: { rates: { VND: 25400 } },               // tỷ giá mới nhất
        });
        redis.setex.mockResolvedValueOnce('OK');            // ghi cache thành công

        const rate = await getExchangeRate();

        expect(rate).toBe(25400); // tỷ giá từ API

        // CheckCache: Redis.setex phải được gọi để cache kết quả API
        expect(redis.setex).toHaveBeenCalledTimes(1);
        const [cacheKey, , cachedValue] = redis.setex.mock.calls[0];
        expect(cacheKey).toContain('USD_VND');    // key cache đúng pattern
        expect(cachedValue).toBe('25400');         // value được cache đúng (string)
    });

    // TC-CURR-007 ─────────────────────────────────────────────────
    // Decision Table: cache MISS + API lỗi → trả về FALLBACK_RATE = 25,000
    it('TC-CURR-007: should return FALLBACK_RATE (25000) when the API fails (EP Invalid class)', async () => {
        redis.get.mockResolvedValueOnce(null);              // cache MISS
        axios.get.mockRejectedValueOnce(new Error('Network Error')); // API thất bại

        const rate = await getExchangeRate();

        // Service xử lý lỗi gracefully → dùng giá trị fallback hardcoded
        // Đảm bảo ứng dụng không crash khi mất kết nối internet
        expect(rate).toBe(25_000);

        // CheckCache: Redis.setex KHÔNG được gọi khi API thất bại
        // (không cache kết quả lỗi)
        expect(redis.setex).not.toHaveBeenCalled();
    });
});


// ══════════════════════════════════════════════════════════════════
// currencyConverter → convertPricesBulk()
// Chuyển đổi nhiều tài sản cùng lúc hiệu quả hơn (gọi getExchangeRate
// một lần rồi áp dụng cho tất cả items thay vì gọi riêng từng item).
// ══════════════════════════════════════════════════════════════════
describe('currencyConverter → convertPricesBulk()', () => {

    // TC-CURR-008 ─────────────────────────────────────────────────
    // Kiểm tra chuyển đổi hỗn hợp: một số item HOSE (VND), một số USD
    it('TC-CURR-008: should convert a mixed list of HOSE and non-HOSE items correctly', async () => {
        // Cung cấp tỷ giá qua Redis cache để test xác định (deterministic)
        redis.get.mockResolvedValueOnce('25000'); // rate = 25,000 VND/USD

        const itemsToConvert = [
            { price: 50_000, exchange: 'HOSE' },    // VND → giữ nguyên
            { price: 1,      exchange: 'NASDAQ' },   // USD → chuyển: 1 × 25000 = 25,000 VND
        ];

        const convertedItems = await convertPricesBulk(itemsToConvert);

        // Item HOSE: giá giữ nguyên (50,000 VND)
        expect(convertedItems[0].price).toBe(50_000);
        expect(convertedItems[0].currency).toBe('VND');

        // Item NASDAQ: 1 USD × 25,000 VND/USD = 25,000 VND
        expect(convertedItems[1].price).toBe(25_000);
        expect(convertedItems[1].currency).toBe('VND');
        expect(convertedItems[1].originalPrice).toBe(1); // lưu lại giá gốc USD
    });

    // TC-CURR-009 ─────────────────────────────────────────────────
    // EP Edge case: input rỗng → trả về array rỗng, không gọi Redis hay API
    it('TC-CURR-009: should return an empty array when given an empty input array (EP Edge)', async () => {
        // Không có items để chuyển đổi
        const result = await convertPricesBulk([]);

        expect(result).toEqual([]); // kết quả phải là array rỗng

        // Guard path: khi input rỗng, không cần lấy tỷ giá (tiết kiệm tài nguyên)
        expect(redis.get).not.toHaveBeenCalled();
    });
});

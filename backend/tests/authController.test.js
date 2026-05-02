/**
 * authController.test.js
 * ==================================================================
 * Test cases TC-AUTH-001  →  TC-AUTH-020
 *
 * Controller đang được test : backend/controllers/authController.js
 * Middleware đang được test  : backend/middleware/authMiddleware.js
 *
 * KIẾN TRÚC TEST (không cần container nào đang chạy):
 *  - mongodb-memory-server: cung cấp MongoDB in-memory, cô lập hoàn toàn
 *    với database thật. Mọi thay đổi chỉ tồn tại trong RAM, KHÔNG bao giờ
 *    chạm tới database production.
 *  - ROLLBACK: setupMongoMemory.js xóa toàn bộ collections trước MỖI test,
 *    đảm bảo mỗi test bắt đầu từ database trống.
 *  - nodemailer bị jest-mock để không gửi email thật trong khi test.
 *  - CheckDB: sau các thao tác ghi (register / reset password), test truy vấn
 *    trực tiếp vào User model để xác nhận trạng thái database đúng như mong đợi.
 * ==================================================================
 */

// ── Kết nối MongoDB in-memory (cung cấp cơ chế rollback tự động) ───
// File này đăng ký beforeAll/beforeEach/afterAll tự động:
//   beforeAll  → khởi động MongoDB in-memory, kết nối Mongoose
//   beforeEach → xóa sạch tất cả collections (rollback giữa các test)
//   afterAll   → ngắt kết nối, dừng server in-memory
require('./helpers/setupMongoMemory');

// ── Supertest: gửi HTTP request tới Express app mà không cần server thật ──
const request    = require('supertest');

// ── Helper tạo Express app tối giản (không có side-effect của server.js) ──
const buildApp   = require('./helpers/testApp');

// ── Route module (authController được load thông qua router này) ───
const authRoutes = require('../routes/authRoutes');

// ── Mongoose model dùng để CheckDB (xác nhận trạng thái database sau mutation) ──
const User = require('../models/User');

// ── Tạo Express app tối giản chỉ mount authRoutes ─────────────────
// Không dùng server.js vì nó khởi động WebSocket, cron job, v.v.
const app = buildApp(authRoutes, '/api/v1/auth');

// ── Mock nodemailer TRƯỚC KHI import authController ─────────────────
// authController.js gọi transporter.sendMail() khi:
//   1. Người dùng quên mật khẩu (forgot-password) → gửi email reset link
// Mock này intercept cuộc gọi đó và trả về thành công giả,
// đảm bảo không có email thật nào được gửi trong khi test.
jest.mock('nodemailer', () => ({
    createTransport: jest.fn().mockReturnValue({
        sendMail: jest.fn().mockResolvedValue({ messageId: 'mock-id' }),
    }),
}));

// ── Mock uploadMiddleware (multer) để tránh side-effect với file system ─
// uploadMiddleware là multer instance, authRoutes gọi upload.single('image').
// Mock này thay thế multer bằng một middleware đơn giản luôn gọi next()
// (bỏ qua việc xử lý file upload thật).
jest.mock('../middleware/uploadMiddleware', () => ({
    single: jest.fn(() => (req, res, next) => next()),
}));

// ──────────────────────────────────────────────────────────────────
// Hàm helper dùng chung trong các test
// ──────────────────────────────────────────────────────────────────

/**
 * registerTestUser – Đăng ký một user mới thông qua API.
 *
 * MỤC ĐÍCH: Tạo dữ liệu "seed" (dữ liệu nền) cho các test cần user tồn tại trước.
 * Ví dụ: test đăng nhập cần user đã được đăng ký trước đó.
 *
 * Trả về toàn bộ supertest response để test có thể kiểm tra body và status.
 */
async function registerTestUser({
    fullName = 'Test User',
    email    = 'test@example.com',
    password = 'Password1',
} = {}) {
    return request(app)
        .post('/api/v1/auth/register')
        .send({ fullName, email, password });
}

/**
 * loginTestUser – Đăng nhập thông qua API và trả về JWT token.
 *
 * MỤC ĐÍCH: Lấy token hợp lệ để dùng trong các test kiểm tra middleware
 * xác thực (authMiddleware.protect).
 */
async function loginTestUser({
    email    = 'test@example.com',
    password = 'Password1',
} = {}) {
    const response = await request(app)
        .post('/api/v1/auth/login')
        .send({ email, password });
    return response.body.token; // Trả về JWT token string
}


// ══════════════════════════════════════════════════════════════════
// authController → registerUser()
// Kiểm tra chức năng: Đăng ký tài khoản mới
// ══════════════════════════════════════════════════════════════════
describe('authController → registerUser()', () => {

    // TC-AUTH-001 ─────────────────────────────────────────────────
    // Kịch bản happy path: đăng ký với đầy đủ thông tin hợp lệ
    it('TC-AUTH-001: should register a user with all valid fields and return HTTP 201', async () => {
        const payload = {
            fullName : 'John Doe',
            email    : 'john@example.com',
            password : 'Password1',
        };

        // Gửi POST /api/v1/auth/register với dữ liệu hợp lệ
        const response = await request(app)
            .post('/api/v1/auth/register')
            .send(payload);

        // Kiểm tra HTTP status: 201 Created (tạo tài nguyên mới thành công)
        expect(response.status).toBe(201);

        // Kiểm tra shape của response: phải có id, token (JWT), và user object
        expect(response.body).toHaveProperty('id');
        expect(response.body).toHaveProperty('token');
        expect(response.body).toHaveProperty('user');

        // ── CheckDB: xác nhận user đã được lưu vào database ──────
        // Truy vấn trực tiếp vào MongoDB để kiểm tra dữ liệu thật
        const savedUser = await User.findOne({ email: payload.email });
        expect(savedUser).not.toBeNull();                          // User phải tồn tại
        expect(savedUser.fullName).toBe(payload.fullName);        // Tên đúng
        // Mật khẩu phải được hash bằng bcrypt, KHÔNG lưu plain text
        expect(savedUser.password).not.toBe(payload.password);
    });

    // TC-AUTH-002 ─────────────────────────────────────────────────
    // Kịch bản lỗi: thiếu trường fullName bắt buộc
    it('TC-AUTH-002: should return HTTP 400 when fullName is missing', async () => {
        // Gửi request thiếu fullName
        const response = await request(app)
            .post('/api/v1/auth/register')
            .send({ email: 'j@x.com', password: 'Password1' });

        // Kiểm tra: phải trả về 400 Bad Request
        expect(response.status).toBe(400);
        // Message lỗi phải đề cập đến "required fields"
        expect(response.body.message).toMatch(/required fields/i);

        // ── CheckDB: không được tạo bất kỳ user nào ──────────────
        const userCount = await User.countDocuments();
        expect(userCount).toBe(0);
    });

    // TC-AUTH-003 ─────────────────────────────────────────────────
    // Kịch bản lỗi: thiếu trường email bắt buộc
    it('TC-AUTH-003: should return HTTP 400 when email is missing', async () => {
        const response = await request(app)
            .post('/api/v1/auth/register')
            .send({ fullName: 'John', password: 'Password1' }); // thiếu email

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/required fields/i);
    });

    // TC-AUTH-004 ─────────────────────────────────────────────────
    // Kịch bản lỗi: thiếu trường password bắt buộc
    it('TC-AUTH-004: should return HTTP 400 when password is missing', async () => {
        const response = await request(app)
            .post('/api/v1/auth/register')
            .send({ fullName: 'John', email: 'j@x.com' }); // thiếu password

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/required fields/i);
    });

    // TC-AUTH-005 ─────────────────────────────────────────────────
    // Kịch bản lỗi: email đã được đăng ký bởi người dùng khác (duplicate)
    it('TC-AUTH-005: should return HTTP 400 when the email is already in use', async () => {
        const duplicateEmail = 'duplicate@example.com';

        // Bước 1: Đăng ký lần đầu – phải thành công
        await registerTestUser({ email: duplicateEmail });

        // Bước 2: Đăng ký lần hai với CÙNG email – phải thất bại
        const response = await request(app)
            .post('/api/v1/auth/register')
            .send({ fullName: 'Another User', email: duplicateEmail, password: 'Password1' });

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/already in use/i);

        // ── CheckDB: chỉ có DUY NHẤT một user với email đó ───────
        const userCount = await User.countDocuments({ email: duplicateEmail });
        expect(userCount).toBe(1); // không được tạo user thứ hai
    });
});


// ══════════════════════════════════════════════════════════════════
// authController → loginUser()
// Kiểm tra chức năng: Đăng nhập và nhận JWT token
// ══════════════════════════════════════════════════════════════════
describe('authController → loginUser()', () => {

    // Seed: tạo sẵn một user đã đăng ký trước MỖI test đăng nhập
    // (beforeEach của setupMongoMemory đã xóa DB, nên cần seed lại)
    beforeEach(async () => {
        await registerTestUser({
            fullName : 'Login Tester',
            email    : 'login@example.com',
            password : 'Password1',
        });
    });

    // TC-AUTH-006 ─────────────────────────────────────────────────
    // Kịch bản happy path: đăng nhập với email và password đúng
    it('TC-AUTH-006: should return HTTP 200 and a valid JWT token for correct credentials', async () => {
        const response = await request(app)
            .post('/api/v1/auth/login')
            .send({ email: 'login@example.com', password: 'Password1' });

        expect(response.status).toBe(200);
        expect(response.body).toHaveProperty('token'); // phải có JWT token
        expect(response.body).toHaveProperty('id');    // phải có userId
        // Token phải là một chuỗi có độ dài hợp lý (JWT thường > 10 ký tự)
        expect(typeof response.body.token).toBe('string');
        expect(response.body.token.length).toBeGreaterThan(10);
    });

    // TC-AUTH-007 ─────────────────────────────────────────────────
    // Kịch bản lỗi: thiếu email trong request
    it('TC-AUTH-007: should return HTTP 400 when email is missing', async () => {
        const response = await request(app)
            .post('/api/v1/auth/login')
            .send({ password: 'Password1' }); // thiếu email

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/provide email and password/i);
    });

    // TC-AUTH-008 ─────────────────────────────────────────────────
    // Kịch bản lỗi: password sai (email đúng nhưng password không khớp)
    it('TC-AUTH-008: should return HTTP 400 when the password is wrong', async () => {
        const response = await request(app)
            .post('/api/v1/auth/login')
            .send({ email: 'login@example.com', password: 'WRONG_PASSWORD' });

        expect(response.status).toBe(400);
        // Message lỗi phải chung chung (không tiết lộ email đúng hay sai
        // để tránh kẻ tấn công biết email có tồn tại không)
        expect(response.body.message).toMatch(/invalid email or password/i);
    });

    // TC-AUTH-009 ─────────────────────────────────────────────────
    // Kịch bản lỗi: email không tồn tại trong hệ thống
    it('TC-AUTH-009: should return HTTP 400 when the email does not exist', async () => {
        const response = await request(app)
            .post('/api/v1/auth/login')
            .send({ email: 'nobody@example.com', password: 'Password1' });

        expect(response.status).toBe(400);
        // Cùng message lỗi với TC-AUTH-008 để không lộ thông tin
        expect(response.body.message).toMatch(/invalid email or password/i);
    });
});


// ══════════════════════════════════════════════════════════════════
// authController → resetPassword()
// Kiểm tra chức năng: Đặt lại mật khẩu bằng token được gửi qua email
// ══════════════════════════════════════════════════════════════════
describe('authController → resetPassword()', () => {
    let validResetToken;           // Token plain-text (gửi trong URL)
    let testUserEmailForReset;

    // Seed trước MỖI test: tạo user + giả lập luồng forgot-password
    // để luôn có một token reset hợp lệ sẵn sàng
    beforeEach(async () => {
        testUserEmailForReset = 'reset@example.com';

        // Bước 1: Đăng ký user (DB đã được xóa bởi setupMongoMemory.beforeEach)
        await registerTestUser({
            email    : testUserEmailForReset,
            password : 'OldPass1',
        });

        // Bước 2: Gọi forgot-password API để kích hoạt luồng reset
        // (nodemailer bị mock nên không gửi email thật)
        await request(app)
            .post('/api/v1/auth/forgot-password')
            .send({ email: testUserEmailForReset });

        // Bước 3: Tạo token đã biết (known token) để dùng trong test.
        //
        // VẤN ĐỀ: Controller tạo token ngẫu nhiên bằng crypto.randomBytes(),
        // hash nó bằng SHA-256, và chỉ lưu hash vào DB. Chúng ta không thể
        // lấy lại plain token từ hash.
        //
        // GIẢI PHÁP: Tạo một plain token đã biết, hash nó, rồi GHI ĐÈ lên
        // trường resetPasswordToken trong DB. Sau đó dùng plain token đã biết
        // trong URL của request test.
        const crypto = require('crypto');
        const knownPlainToken  = 'testtokenabcdef1234567890abcdef12345678';
        const knownHashedToken = crypto
            .createHash('sha256')
            .update(knownPlainToken)
            .digest('hex');

        // Ghi đè token trong DB với token đã biết (hết hạn sau 10 phút)
        await User.findOneAndUpdate(
            { email: testUserEmailForReset },
            {
                resetPasswordToken  : knownHashedToken,
                resetPasswordExpires: Date.now() + 10 * 60 * 1000, // 10 phút
            }
        );

        validResetToken = knownPlainToken; // Lưu plain token để dùng trong URL
    });

    // TC-AUTH-010 ─────────────────────────────────────────────────
    // Kịch bản happy path: đặt lại mật khẩu thành công với token hợp lệ
    it('TC-AUTH-010: should reset password successfully with a valid token and strong password', async () => {
        const newPassword = 'NewValid1pass';

        // Gửi token trong URL (giống link trong email thật)
        const response = await request(app)
            .post(`/api/v1/auth/reset-password/${validResetToken}`)
            .send({ password: newPassword });

        expect(response.status).toBe(200);
        expect(response.body.message).toMatch(/thành công/i);

        // ── CheckDB: xác nhận token đã bị xóa sau khi dùng ──────
        // Token chỉ được dùng một lần; sau khi reset phải bị xóa khỏi DB
        const updatedUser = await User.findOne({ email: testUserEmailForReset });
        expect(updatedUser.resetPasswordToken).toBeUndefined();
        expect(updatedUser.resetPasswordExpires).toBeUndefined();

        // ── CheckDB: xác nhận mật khẩu mới hoạt động ─────────────
        // Đăng nhập với mật khẩu mới phải thành công
        const loginResponse = await request(app)
            .post('/api/v1/auth/login')
            .send({ email: testUserEmailForReset, password: newPassword });
        expect(loginResponse.status).toBe(200);
    });

    // TC-AUTH-011 ─────────────────────────────────────────────────
    // BVA (Boundary Value Analysis): mật khẩu 7 ký tự = dưới ngưỡng tối thiểu
    it('TC-AUTH-011: should return HTTP 400 when the password is exactly 7 characters (below minimum boundary)', async () => {
        // BVA lower boundary: 7 < 8 (yêu cầu tối thiểu) → phải bị từ chối
        const shortPassword = 'Abc123!'; // độ dài = 7

        const response = await request(app)
            .post(`/api/v1/auth/reset-password/${validResetToken}`)
            .send({ password: shortPassword });

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/ít nhất 8/i); // "ít nhất 8 ký tự"
    });

    // TC-AUTH-012 ─────────────────────────────────────────────────
    // BVA: mật khẩu 8 ký tự = đúng ngưỡng tối thiểu → phải được chấp nhận
    it('TC-AUTH-012: should succeed when the password is exactly 8 characters (at minimum boundary)', async () => {
        // BVA lower boundary: 8 === tối thiểu → hợp lệ
        const minLengthPassword = 'Abcdef1!'; // độ dài = 8, có chữ hoa + chữ thường + số

        const response = await request(app)
            .post(`/api/v1/auth/reset-password/${validResetToken}`)
            .send({ password: minLengthPassword });

        expect(response.status).toBe(200);
    });

    // TC-AUTH-013 ─────────────────────────────────────────────────
    // Kịch bản lỗi: mật khẩu không có chữ hoa
    it('TC-AUTH-013: should return HTTP 400 when the password has no uppercase letter', async () => {
        const response = await request(app)
            .post(`/api/v1/auth/reset-password/${validResetToken}`)
            .send({ password: 'abcdef1!' }); // toàn chữ thường

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/chữ hoa/i); // "cần có chữ hoa"
    });

    // TC-AUTH-014 ─────────────────────────────────────────────────
    // Kịch bản lỗi: mật khẩu không có chữ số
    it('TC-AUTH-014: should return HTTP 400 when the password has no digit', async () => {
        const response = await request(app)
            .post(`/api/v1/auth/reset-password/${validResetToken}`)
            .send({ password: 'Abcdefgh!' }); // không có số

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/một số/i); // "cần có ít nhất một số"
    });

    // TC-AUTH-015 ─────────────────────────────────────────────────
    // Decision Table: token tồn tại nhưng đã hết hạn
    it('TC-AUTH-015: should return HTTP 400 for an expired or invalid reset token', async () => {
        // Cố ý đặt thời gian hết hạn trong quá khứ (1 giây trước)
        await User.findOneAndUpdate(
            { email: testUserEmailForReset },
            { resetPasswordExpires: Date.now() - 1000 } // đã hết hạn
        );

        const response = await request(app)
            .post(`/api/v1/auth/reset-password/${validResetToken}`)
            .send({ password: 'ValidPass1' });

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/hết hạn/i); // "token đã hết hạn"
    });
});


// ══════════════════════════════════════════════════════════════════
// authController → validateResetToken()
// Kiểm tra chức năng: Xác thực token reset mật khẩu còn hợp lệ không
// (Frontend gọi endpoint này để biết có hiển thị form nhập mật khẩu mới không)
// ══════════════════════════════════════════════════════════════════
describe('authController → validateResetToken()', () => {
    let plainToken;

    // Seed trước MỖI test: tạo user với token reset hợp lệ
    beforeEach(async () => {
        const crypto = require('crypto');
        plainToken = 'validatetokenabcdef1234567890abcde';
        const hashedToken = crypto.createHash('sha256').update(plainToken).digest('hex');

        // Tạo user và gắn token reset hợp lệ (hết hạn sau 10 phút)
        await registerTestUser({ email: 'validate@example.com', password: 'Password1' });
        await User.findOneAndUpdate(
            { email: 'validate@example.com' },
            {
                resetPasswordToken  : hashedToken,
                resetPasswordExpires: Date.now() + 10 * 60 * 1000, // 10 phút
            }
        );
    });

    // TC-AUTH-016 ─────────────────────────────────────────────────
    // Kịch bản happy path: token hợp lệ và chưa hết hạn
    it('TC-AUTH-016: should return HTTP 200 for a valid, non-expired token', async () => {
        // GET request với token trong URL (frontend gọi khi user click link trong email)
        const response = await request(app)
            .get(`/api/v1/auth/reset-password/${plainToken}`);

        expect(response.status).toBe(200);
        expect(response.body.message).toMatch(/hợp lệ/i); // "token hợp lệ"
    });

    // TC-AUTH-017 ─────────────────────────────────────────────────
    // BVA (boundary): token hết hạn đúng 1 giây trước thời điểm check
    it('TC-AUTH-017: should return HTTP 400 when the token has expired (BVA – expiry boundary)', async () => {
        // Đặt thời gian hết hạn 1 giây trong quá khứ (vừa qua boundary hợp lệ)
        await User.findOneAndUpdate(
            { email: 'validate@example.com' },
            { resetPasswordExpires: Date.now() - 1000 }
        );

        const response = await request(app)
            .get(`/api/v1/auth/reset-password/${plainToken}`);

        expect(response.status).toBe(400);
        expect(response.body.message).toMatch(/hết hạn/i); // "token đã hết hạn"
    });
});


// ══════════════════════════════════════════════════════════════════
// authMiddleware → protect()
// Kiểm tra middleware bảo vệ route: xác thực JWT trong Authorization header
// protect() chạy trước mỗi controller cần xác thực, ví dụ: lấy thông tin user
// ══════════════════════════════════════════════════════════════════
describe('authMiddleware → protect()', () => {
    let validJwtToken; // JWT token hợp lệ được lấy từ đăng nhập

    // Seed trước MỖI test: đăng ký + đăng nhập để có token JWT thật
    beforeEach(async () => {
        await registerTestUser({
            email    : 'middleware@example.com',
            password : 'Password1',
        });
        // Đăng nhập để lấy JWT token → dùng token này trong các request test
        validJwtToken = await loginTestUser({
            email    : 'middleware@example.com',
            password : 'Password1',
        });
    });

    // TC-AUTH-018 ─────────────────────────────────────────────────
    // Kịch bản happy path: Bearer token hợp lệ → middleware cho qua, populate req.user
    it('TC-AUTH-018: should call next() and populate req.user for a valid Bearer token', async () => {
        // Dùng endpoint GET /getUser làm "proxy" để test middleware protect().
        // Endpoint này chỉ hoạt động nếu protect() gọi next() thành công.
        const response = await request(app)
            .get('/api/v1/auth/getUser')
            .set('Authorization', `Bearer ${validJwtToken}`); // gắn token vào header

        // Nếu middleware thành công → controller trả về thông tin user
        expect(response.status).toBe(200);
        expect(response.body).toHaveProperty('email', 'middleware@example.com');
    });

    // TC-AUTH-019 ─────────────────────────────────────────────────
    // Kịch bản lỗi: không có Authorization header → middleware chặn lại
    it('TC-AUTH-019: should return HTTP 401 when no Authorization header is present', async () => {
        // Gửi request KHÔNG có Authorization header
        const response = await request(app)
            .get('/api/v1/auth/getUser'); // không có .set('Authorization', ...)

        expect(response.status).toBe(401); // Unauthorized
        expect(response.body.message).toMatch(/no token/i);
    });

    // TC-AUTH-020 ─────────────────────────────────────────────────
    // Kịch bản lỗi: token bị giả mạo hoặc không hợp lệ
    it('TC-AUTH-020: should return HTTP 401 for a tampered or invalid JWT', async () => {
        const response = await request(app)
            .get('/api/v1/auth/getUser')
            .set('Authorization', 'Bearer this.is.not.a.valid.jwt'); // token giả

        expect(response.status).toBe(401); // Unauthorized
        expect(response.body.message).toMatch(/token failed/i);
    });
});

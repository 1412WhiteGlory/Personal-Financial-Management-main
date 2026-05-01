/**
 * jest.config.js
 * ──────────────────────────────────────────────────────────────────
 * Jest configuration for the Personal Financial Management backend.
 *
 * Key settings:
 *  • testEnvironment : 'node'  – no browser DOM emulation needed
 *  • testMatch       : all *.test.js files inside backend/tests/
 *  • setupFiles      : loads .env.test before any test module runs
 *  • testTimeout     : 30 000 ms – mongodb-memory-server cold-start
 *  • collectCoverage : enabled so `npm test` always prints coverage
 *  • coverageDirectory: output folder for HTML/JSON coverage reports
 * ──────────────────────────────────────────────────────────────────
 */

/** @type {import('jest').Config} */
module.exports = {
    // Node.js test environment (no browser DOM)
    testEnvironment: 'node',

    // Only discover files inside the tests/ directory
    testMatch: ['**/tests/**/*.test.js'],

    // 30 s per test – mongodb-memory-server is slow on first launch
    testTimeout: 30_000,

    // ── Pre-test setup ─────────────────────────────────────────────
    // jestSetupEnv.js calls dotenv.config({ path: '.env.test' }) so
    // that JWT_SECRET and other variables are available before any
    // controller or middleware module is require()d.
    setupFiles: ['<rootDir>/tests/helpers/jestSetupEnv.js'],

    // ── Coverage ───────────────────────────────────────────────────
    collectCoverage: true,

    collectCoverageFrom: [
        'controllers/**/*.js',
        'services/calculatePriceChange.js',
        'services/currencyConverter.js',
        'middleware/authMiddleware.js',
        '!controllers/financeController.js',   // empty placeholder – skip
    ],

    coverageDirectory: 'coverage',

    // Terminal summary + lcov for CI + HTML for browser inspection
    coverageReporters: ['text', 'lcov', 'html'],

    testEnvironmentOptions: {},
};

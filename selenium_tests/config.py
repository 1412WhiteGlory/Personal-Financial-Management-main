"""
Configuration file for Selenium WebDriver Test Suite
Personal Financial Management Application
"""
import os

# ============================================================
# Application URLs
# ============================================================
BASE_URL = "http://localhost:5173"
API_BASE_URL = "http://localhost:8000"

# Page URLs
LOGIN_URL = f"{BASE_URL}/login"
SIGNUP_URL = f"{BASE_URL}/signUp"
DASHBOARD_URL = f"{BASE_URL}/dashboard"
INCOME_URL = f"{BASE_URL}/income"
EXPENSE_URL = f"{BASE_URL}/expense"
NEWS_URL = f"{BASE_URL}/news"
FORGOT_PASSWORD_URL = f"{BASE_URL}/forgot-password"

# API Endpoints
API_AUTH_REGISTER = f"{API_BASE_URL}/api/v1/auth/register"
API_AUTH_LOGIN = f"{API_BASE_URL}/api/v1/auth/login"
API_AUTH_GET_USER = f"{API_BASE_URL}/api/v1/auth/getUser"
API_INCOME_ADD = f"{API_BASE_URL}/api/v1/income/add"
API_INCOME_GET = f"{API_BASE_URL}/api/v1/income/get"
API_EXPENSE_ADD = f"{API_BASE_URL}/api/v1/expense/add"
API_EXPENSE_GET = f"{API_BASE_URL}/api/v1/expense/get"
API_DASHBOARD = f"{API_BASE_URL}/api/v1/dashboard"

# ============================================================
# MongoDB Configuration (for database verification)
# ============================================================
MONGO_URI = "mongodb://127.0.0.1:27017/financial-management"

# ============================================================
# Test User Credentials (for login-dependent tests)
# ============================================================
TEST_USER_FULLNAME = "Selenium Test User"
TEST_USER_EMAIL = "selenium_test_user@test.com"
TEST_USER_PASSWORD = "SeleniumTest@123"

# ============================================================
# Browser Configuration
# ============================================================
BROWSER = "chrome"  # chrome, firefox, edge
HEADLESS = False  # Set True for CI/CD
IMPLICIT_WAIT = 10  # seconds
EXPLICIT_WAIT = 15  # seconds
PAGE_LOAD_TIMEOUT = 30  # seconds

# ============================================================
# Screenshot & Report Paths
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, "screenshots")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
TEST_DATA_DIR = os.path.join(PROJECT_ROOT, "test_data")

# Create directories if they don't exist
for d in [SCREENSHOTS_DIR, REPORTS_DIR, TEST_DATA_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================================
# Report Configuration
# ============================================================
REPORT_FILENAME = "selenium_test_report.xlsx"
REPORT_PATH = os.path.join(REPORTS_DIR, REPORT_FILENAME)

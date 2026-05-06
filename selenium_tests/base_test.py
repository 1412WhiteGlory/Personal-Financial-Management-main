"""
Base Test Class with common utilities for all Selenium tests.
Provides: browser setup, teardown, screenshots, DB helpers, rollback support.
"""
import os
import csv
import time
import json
import requests
import unittest
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementNotInteractableException, StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

import config


class BaseTest(unittest.TestCase):
    """Base test class with common Selenium utilities."""

    driver = None
    test_results = []  # Shared across ALL tests for report generation
    _auth_token = None
    _rollback_actions = []  # Stack of rollback actions

    # ─── Browser lifecycle ───────────────────────────────────

    @classmethod
    def setUpClass(cls):
        """Create the browser driver once per test class."""
        cls.driver = cls._create_driver()
        cls.driver.implicitly_wait(config.IMPLICIT_WAIT)
        cls.driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
        cls.driver.maximize_window()

    @classmethod
    def tearDownClass(cls):
        """Close browser after all tests in the class."""
        if cls.driver:
            cls.driver.quit()

    def setUp(self):
        """Called before every individual test method."""
        self._rollback_actions = []

    def tearDown(self):
        """Execute rollback actions after each test."""
        # Execute rollback
        self._execute_rollback()

    # ─── Driver factory ─────────────────────────────────────

    @classmethod
    def _create_driver(cls):
        browser = config.BROWSER.lower()
        if browser == "chrome":
            opts = ChromeOptions()
            if config.HEADLESS:
                opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--window-size=1920,1080")
            opts.add_argument("--disable-notifications")
            opts.add_experimental_option("excludeSwitches", ["enable-logging"])
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=opts)
        elif browser == "firefox":
            opts = FirefoxOptions()
            if config.HEADLESS:
                opts.add_argument("--headless")
            service = FirefoxService(GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=opts)
        elif browser == "edge":
            opts = EdgeOptions()
            if config.HEADLESS:
                opts.add_argument("--headless=new")
            service = EdgeService(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=opts)
        else:
            raise ValueError(f"Unsupported browser: {browser}")

    # ─── Wait helpers ───────────────────────────────────────

    def wait_for_element(self, by, value, timeout=None):
        """Wait for an element to be present and return it."""
        timeout = timeout or config.EXPLICIT_WAIT
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def wait_for_clickable(self, by, value, timeout=None):
        timeout = timeout or config.EXPLICIT_WAIT
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )

    def wait_for_visible(self, by, value, timeout=None):
        timeout = timeout or config.EXPLICIT_WAIT
        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((by, value))
        )

    def wait_for_text_in_page(self, text, timeout=None):
        """Wait until specific text appears anywhere in the page body."""
        timeout = timeout or config.EXPLICIT_WAIT
        return WebDriverWait(self.driver, timeout).until(
            lambda d: text in d.page_source
        )

    def wait_for_url_contains(self, fragment, timeout=None):
        timeout = timeout or config.EXPLICIT_WAIT
        return WebDriverWait(self.driver, timeout).until(
            EC.url_contains(fragment)
        )

    def wait_for_url(self, url, timeout=None):
        timeout = timeout or config.EXPLICIT_WAIT
        return WebDriverWait(self.driver, timeout).until(
            EC.url_to_be(url)
        )

    # ─── Element interaction helpers ────────────────────────

    def clear_and_type(self, element, text):
        """Clear an input and type text into it."""
        element.click()
        element.send_keys(Keys.CONTROL + "a")
        element.send_keys(Keys.DELETE)
        time.sleep(0.2)
        element.send_keys(str(text))

    def safe_click(self, element):
        """Click element using JavaScript if normal click fails."""
        try:
            element.click()
        except (ElementNotInteractableException, Exception):
            self.driver.execute_script("arguments[0].click();", element)

    def scroll_to_element(self, element):
        """Scroll element into view."""
        self.driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
            element
        )

    # ─── Screenshot ─────────────────────────────────────────

    def take_screenshot(self, name="screenshot"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{ts}.png"
        filepath = os.path.join(config.SCREENSHOTS_DIR, filename)
        self.driver.save_screenshot(filepath)
        return filepath

    # ─── CSV data loader ────────────────────────────────────

    @staticmethod
    def load_csv(filename):
        """Load test data from a CSV file."""
        filepath = os.path.join(config.TEST_DATA_DIR, filename)
        data = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        return data

    # ─── API helpers (for DB verification) ──────────────────

    def api_register_user(self, fullName, email, password):
        """Register a user via API and return token."""
        resp = requests.post(config.API_AUTH_REGISTER, json={
            "fullName": fullName,
            "email": email,
            "password": password
        })
        return resp

    def api_login(self, email, password):
        """Login via API and return token."""
        resp = requests.post(config.API_AUTH_LOGIN, json={
            "email": email,
            "password": password
        })
        if resp.status_code == 200:
            data = resp.json()
            self._auth_token = data.get("token")
            return data
        return None

    def api_get_auth_headers(self):
        """Return headers with Bearer token for authenticated requests."""
        return {"Authorization": f"Bearer {self._auth_token}"}

    def api_get_user_info(self):
        """Get the current user's info from the API."""
        resp = requests.get(config.API_AUTH_GET_USER,
                            headers=self.api_get_auth_headers())
        return resp.json() if resp.status_code == 200 else None

    def api_get_incomes(self):
        """Get all incomes for the authenticated user."""
        resp = requests.get(config.API_INCOME_GET,
                            headers=self.api_get_auth_headers())
        return resp.json() if resp.status_code == 200 else []

    def api_get_expenses(self):
        """Get all expenses for the authenticated user."""
        resp = requests.get(config.API_EXPENSE_GET,
                            headers=self.api_get_auth_headers())
        return resp.json() if resp.status_code == 200 else []

    def api_add_income(self, source, amount, date, icon=""):
        resp = requests.post(config.API_INCOME_ADD,
                             headers=self.api_get_auth_headers(),
                             json={"source": source, "amount": amount,
                                   "date": date, "icon": icon})
        return resp

    def api_delete_income(self, income_id):
        resp = requests.delete(
            f"{config.API_BASE_URL}/api/v1/income/{income_id}",
            headers=self.api_get_auth_headers()
        )
        return resp

    def api_add_expense(self, category, amount, date, icon=""):
        resp = requests.post(config.API_EXPENSE_ADD,
                             headers=self.api_get_auth_headers(),
                             json={"category": category, "amount": amount,
                                   "date": date, "icon": icon})
        return resp

    def api_delete_expense(self, expense_id):
        resp = requests.delete(
            f"{config.API_BASE_URL}/api/v1/expense/{expense_id}",
            headers=self.api_get_auth_headers()
        )
        return resp

    # ─── Rollback support ───────────────────────────────────

    def register_rollback(self, action_fn, *args, **kwargs):
        """Register a cleanup/rollback action to be executed after the test."""
        self._rollback_actions.append((action_fn, args, kwargs))

    def _execute_rollback(self):
        """Execute all registered rollback actions in LIFO order."""
        while self._rollback_actions:
            fn, args, kwargs = self._rollback_actions.pop()
            try:
                fn(*args, **kwargs)
            except Exception as e:
                print(f"[ROLLBACK ERROR] {fn.__name__}: {e}")

    # ─── Authentication helpers (UI) ────────────────────────

    def login_via_ui(self, email=None, password=None):
        """Login through the UI and return True if dashboard loads."""
        email = email or config.TEST_USER_EMAIL
        password = password or config.TEST_USER_PASSWORD

        self.driver.get(config.LOGIN_URL)
        time.sleep(1)

        # Find and fill email
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input")
        email_input = None
        password_input = None
        for inp in inputs:
            inp_type = inp.get_attribute("type")
            placeholder = inp.get_attribute("placeholder") or ""
            if inp_type == "password" or "mật khẩu" in placeholder.lower() or "password" in placeholder.lower():
                password_input = inp
            elif inp_type in ("text", "email") or "email" in placeholder.lower():
                email_input = inp

        if email_input and password_input:
            self.clear_and_type(email_input, email)
            self.clear_and_type(password_input, password)

            # Click login button
            btns = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
            if btns:
                self.safe_click(btns[0])

            time.sleep(2)
            return "dashboard" in self.driver.current_url or "income" in self.driver.current_url
        return False

    def ensure_logged_in(self):
        """Make sure we are logged in. Attempts API login first for token, then UI."""
        if not self._auth_token:
            # Try to register first (idempotent – may already exist)
            self.api_register_user(
                config.TEST_USER_FULLNAME,
                config.TEST_USER_EMAIL,
                config.TEST_USER_PASSWORD
            )
            self.api_login(config.TEST_USER_EMAIL, config.TEST_USER_PASSWORD)

        # UI login
        if "dashboard" not in (self.driver.current_url or ""):
            self.login_via_ui()

    # ─── Result recording ───────────────────────────────────

    def record_result(self, test_id, test_name, module, description,
                      status, actual_result="", error_message="",
                      screenshot_path="", duration=0):
        """Append a test result to the shared list for report generation."""
        if not screenshot_path:
            try:
                screenshot_path = self.take_screenshot(f"{test_id}_{status}")
            except Exception as e:
                print(f"Failed to take screenshot: {e}")
        BaseTest.test_results.append({
            "test_id": test_id,
            "test_name": test_name,
            "module": module,
            "description": description,
            "status": status,  # PASS / FAIL / ERROR / SKIP
            "actual_result": actual_result,
            "error_message": error_message,
            "screenshot": screenshot_path,
            "duration_sec": round(duration, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

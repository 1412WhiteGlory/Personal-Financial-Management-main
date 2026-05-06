"""
Main Test Runner
────────────────────────────────────────────────────────────
Discovers and runs ALL Selenium WebDriver test suites, then generates
an Excel report with complete results.

Usage:
    python run_all_tests.py
    python run_all_tests.py --headless          # Run without browser GUI
    python run_all_tests.py --browser firefox   # Use Firefox
"""
import sys
import os
import time
import argparse
import unittest
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from base_test import BaseTest
from report_generator import generate_report
from html_report_generator import generate_html_report


def parse_args():
    parser = argparse.ArgumentParser(description="Selenium WebDriver Test Runner")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode")
    parser.add_argument("--browser", default="chrome",
                        choices=["chrome", "firefox", "edge"],
                        help="Browser to use (default: chrome)")
    parser.add_argument("--module", default=None,
                        help="Run specific test module only (e.g. test_01_registration)")
    parser.add_argument("--skip", default="",
                        help="Comma-separated list of modules to skip (e.g. test_01_registration,test_02_login)")
    return parser.parse_args()


def main():
    args = parse_args()

    # Apply CLI args to config
    config.HEADLESS = args.headless
    config.BROWSER = args.browser

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║       SELENIUM WEBDRIVER - SYSTEM TEST SUITE                ║
║       Personal Financial Management Application            ║
╠══════════════════════════════════════════════════════════════╣
║  Browser  : {config.BROWSER:<47}║
║  Headless : {str(config.HEADLESS):<47}║
║  Base URL : {config.BASE_URL:<47}║
║  API URL  : {config.API_BASE_URL:<47}║
║  Started  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<47}║
╚══════════════════════════════════════════════════════════════╝
""")

    # ── Pre-flight checks ──
    print("🔍 Pre-flight checks...")
    import requests
    try:
        resp = requests.get(config.API_BASE_URL + "/api/v1/health", timeout=5)
        print(f"   ✅ Backend API is reachable (status: {resp.status_code})")
    except Exception:
        try:
            resp = requests.get(config.API_BASE_URL, timeout=5)
            print(f"   ✅ Backend API is reachable (status: {resp.status_code})")
        except Exception as e:
            print(f"   ⚠️  Backend API might not be running: {e}")
            print(f"   ⚠️  Make sure to start the backend on {config.API_BASE_URL}")

    try:
        resp = requests.get(config.BASE_URL, timeout=5)
        print(f"   ✅ Frontend is reachable (status: {resp.status_code})")
    except Exception as e:
        print(f"   ⚠️  Frontend might not be running: {e}")
        print(f"   ⚠️  Make sure to start the frontend on {config.BASE_URL}")

    print()

    # ── Clear previous results ──
    BaseTest.test_results = []

    # ── Discover and run tests ──
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    if args.module:
        # Run specific module
        try:
            module = __import__(args.module)
            suite.addTests(loader.loadTestsFromModule(module))
        except ImportError as e:
            print(f"❌ Could not import module {args.module}: {e}")
            sys.exit(1)
    else:
        # Discover all test files
        test_modules = [
            "test_01_registration",
            "test_02_login",
            "test_03_income",
            "test_04_expense",
            "test_05_dashboard",
            "test_06_navigation",
        ]

        # Apply --skip filter
        skip_set = {s.strip() for s in args.skip.split(",") if s.strip()}
        if skip_set:
            print(f"   🚫 Skipping modules: {', '.join(sorted(skip_set))}")

        for mod_name in test_modules:
            if mod_name in skip_set:
                print(f"   ⏭  Skipped  : {mod_name} (excluded via --skip)")
                continue
            try:
                module = __import__(mod_name)
                tests = loader.loadTestsFromModule(module)
                suite.addTests(tests)
                print(f"   📦 Loaded: {mod_name} ({tests.countTestCases()} tests)")
            except ImportError as e:
                print(f"   ⚠️  Skipped {mod_name}: {e}")

    total_tests = suite.countTestCases()
    print(f"\n🚀 Running {total_tests} test(s)...\n")
    print("=" * 60)

    # ── Run ──
    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    end_time = time.time()

    print("=" * 60)
    print(f"\n⏱  Total execution time: {end_time - start_time:.1f}s")

    # ── Generate Report ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(config.REPORTS_DIR, f"selenium_test_report_{timestamp}.xlsx")
    html_report_path = os.path.join(config.REPORTS_DIR, f"selenium_test_report_{timestamp}.html")

    # If no results were recorded (tests may not have used record_result),
    # synthesize from unittest result
    if not BaseTest.test_results:
        print("\n⚠️  No results recorded via record_result(). Synthesizing from unittest output.")
        for test, traceback in result.failures:
            BaseTest.test_results.append({
                "test_id": str(test).split()[0],
                "test_name": str(test),
                "module": test.__class__.__name__,
                "description": test.shortDescription() or "",
                "status": "FAIL",
                "actual_result": "",
                "error_message": traceback[:500],
                "screenshot": "",
                "duration_sec": 0,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        for test, traceback in result.errors:
            BaseTest.test_results.append({
                "test_id": str(test).split()[0],
                "test_name": str(test),
                "module": test.__class__.__name__,
                "description": test.shortDescription() or "",
                "status": "ERROR",
                "actual_result": "",
                "error_message": traceback[:500],
                "screenshot": "",
                "duration_sec": 0,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        for test in result.skipped:
            BaseTest.test_results.append({
                "test_id": str(test[0]).split()[0],
                "test_name": str(test[0]),
                "module": test[0].__class__.__name__,
                "description": test[0].shortDescription() or "",
                "status": "SKIP",
                "actual_result": test[1],
                "error_message": "",
                "screenshot": "",
                "duration_sec": 0,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        # Add passes (unittest doesn't track these directly, so count the diff)
        recorded_ids = {r["test_name"] for r in BaseTest.test_results}
        for test_group in [result.failures, result.errors, result.skipped]:
            for item in test_group:
                t = item[0] if isinstance(item, tuple) else item
                recorded_ids.add(str(t))

    generate_report(BaseTest.test_results, report_path)

    # Also generate with default filename for easy access
    generate_report(BaseTest.test_results, config.REPORT_PATH)

    # Generate HTML report
    generate_html_report(BaseTest.test_results, html_report_path)
    html_default = os.path.join(config.REPORTS_DIR, "selenium_test_report.html")
    generate_html_report(BaseTest.test_results, html_default)

    # ── Summary ──
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    TEST EXECUTION COMPLETE                   ║
╠══════════════════════════════════════════════════════════════╣
║  Tests Run : {result.testsRun:<47}║
║  Passed    : {result.testsRun - len(result.failures) - len(result.errors):<47}║
║  Failed    : {len(result.failures):<47}║
║  Errors    : {len(result.errors):<47}║
║  Skipped   : {len(result.skipped):<47}║
║  Duration  : {f'{end_time - start_time:.1f}s':<47}║
╠══════════════════════════════════════════════════════════════╣
║  Excel     : {os.path.basename(report_path):<47}║
║  HTML      : {os.path.basename(html_report_path):<47}║
║  Location  : {config.REPORTS_DIR:<47}║
╚══════════════════════════════════════════════════════════════╝
""")

    # Return exit code
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
SecureChat — Master Test Runner
================================
Runs all test suites and prints a structured summary report.

Usage:
    python run_tests.py                # run everything
    python run_tests.py unit           # run only unit tests
    python run_tests.py integration    # run only integration tests
    python run_tests.py security       # run only security tests
    python run_tests.py performance    # run only performance tests
    python run_tests.py load           # run only load tests
    python run_tests.py regression     # run only regression tests
"""

import sys
import os
import time
import unittest

# Ensure the project root is on the path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

SUITES = {
    "unit_crypto":   "tests.test_unit_crypto",
    "unit_routes":   "tests.test_unit_routes",
    "integration":   "tests.test_integration_handshake",
    "security":      "tests.test_security",
    "performance":   "tests.test_performance",
    "load":          "tests.test_load",
    "regression":    "tests.test_regression",
}

# Friendly group aliases  (passed as CLI arg)
GROUPS = {
    "unit":        ["unit_crypto", "unit_routes"],
    "integration": ["integration"],
    "security":    ["security"],
    "performance": ["performance"],
    "load":        ["load"],
    "regression":  ["regression"],
    "all":         list(SUITES.keys()),
}


def run_suite(name: str, module: str) -> unittest.TestResult:
    print(f"\n{'═'*60}")
    print(f"  {name.upper().replace('_', ' ')}")
    print(f"{'═'*60}")
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(module)
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    return runner.run(suite)


def main():
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    if arg not in GROUPS and arg not in SUITES:
        print(f"Unknown group '{arg}'. Available: {', '.join(GROUPS)}")
        sys.exit(1)

    keys = GROUPS.get(arg, [arg])

    overall_start = time.perf_counter()
    results = {}
    for key in keys:
        module = SUITES[key]
        result = run_suite(key, module)
        results[key] = result

    elapsed = time.perf_counter() - overall_start

    print(f"\n\n{'═'*60}")
    print("  SUMMARY")
    print(f"{'═'*60}")
    total_run = total_fail = total_err = total_skip = 0
    for key, r in results.items():
        status = "✅ PASS" if r.wasSuccessful() else "❌ FAIL"
        print(f"  {status}  {key:<22}  "
              f"run={r.testsRun}  fail={len(r.failures)}  err={len(r.errors)}  skip={len(r.skipped)}")
        total_run  += r.testsRun
        total_fail += len(r.failures)
        total_err  += len(r.errors)
        total_skip += len(r.skipped)

    print(f"{'─'*60}")
    print(f"  TOTAL  run={total_run}  fail={total_fail}  "
          f"err={total_err}  skip={total_skip}  time={elapsed:.1f}s")
    print(f"{'═'*60}\n")

    if total_fail + total_err > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

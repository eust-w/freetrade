# Contributing

Keep contributions small and reproducible. Include the problem, relevant data assumptions, and verification.

1. Create a Python 3.11+ virtual environment and install requirements-dev.txt.
2. Run python -m pytest -q and python refresh.py --mode demo.
3. Run python -m pip_audit -r requirements.txt and inspect your diff.
4. Never commit credentials, browser profiles, production logs, real account data, or unlicensed data dumps.

Useful contributions: provider contracts, point-in-time datasets, calendar-aware freshness, bounded retries, testable scoring, and honest failure reporting. Do not add unsupported return claims or treat demo results as financial evidence.

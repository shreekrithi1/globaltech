#!/usr/bin/env python3
"""Backward-compatible entry point. The agent lives in run.py."""
from run import main

if __name__ == "__main__":
    raise SystemExit(main())

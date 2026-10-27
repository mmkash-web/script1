#!/usr/bin/env python3
# Quick test for one account
import sys
sys.path.insert(0, '.')
from goatspins_balance_checker import try_browser

result = try_browser("ts.mira0311@gmail.com", "Acab1312")
print("Result:", result)
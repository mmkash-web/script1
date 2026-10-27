from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

URL = 'https://cdk.goatspins.com:3072/lobby/'

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1920,1080')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
driver.get(URL)
time.sleep(5)

# Get all buttons
buttons = driver.find_elements(By.TAG_NAME, 'button')
print(f'Found {len(buttons)} buttons:')
for b in buttons[:20]:
    try:
        text = b.text.strip()
        cls = b.get_attribute('class')[:50] if b.get_attribute('class') else ''
        if text:
            print(f'  Text: "{text}" Class: {cls}')
    except:
        pass

# Get all inputs
inputs = driver.find_elements(By.TAG_NAME, 'input')
print(f'Found {len(inputs)} inputs:')
for inp in inputs[:10]:
    try:
        t = inp.get_attribute('type')
        n = inp.get_attribute('name')
        p = inp.get_attribute('placeholder')
        print(f'  Type: {t} Name: {n} Placeholder: {p}')
    except:
        pass

# Get page title
print(f'Title: {driver.title}')

# Check for balance text
try:
    body = driver.find_element(By.TAG_NAME, 'body')
    text = body.text
    print(f'Body text length: {len(text)}')
    print(f'Body text preview: {text[:500]}')
except Exception as e:
    print(f'Error getting body: {e}')

driver.quit()
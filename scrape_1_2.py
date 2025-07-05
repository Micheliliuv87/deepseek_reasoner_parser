from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import csv
import math
import time
import random
import re

# --- Selenium Setup ---
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
)
service = Service(log_path="NUL")  # Silence ChromeDriver logs on Windows
driver = webdriver.Chrome(service=service, options=options)

# --- Configuration ---
BASE_OVERVIEW = "https://www.lusha.com/company-search/oil-and-gas/cf2c1ee664/"
country_map = {
    "埃及":      "egypt",
    "伊朗":      "iran-islamic-republic-of",
    "土耳其":    "turkey",
    "伊拉克":    "iraq",
    "沙特阿拉伯":"saudi-arabia",
    "也门":      "yemen",
    "叙利亚":    "syrian-arab-republic",
    "约旦":      "jordan",
    "阿联酋":    "united-arab-emirates",
    "以色列":    "israel",
    "黎巴嫩":    "lebanon",
    "巴勒斯坦":  "palestine",
    "阿曼":      "oman",
    "科威特":    "kuwait",
    "卡塔尔":    "qatar",
    "巴林":      "bahrain"
}
slug2cn = {v: k for k, v in country_map.items()}

# --- Step 1: Scrape overview page for country links ---
driver.get(BASE_OVERVIEW)
WebDriverWait(driver, 10).until(
    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.directory-content-box-col a"))
)
time.sleep(1)

anchors = driver.find_elements(By.CSS_SELECTOR, "div.directory-content-box-col a")
child_list = []
for a in anchors:
    href = a.get_attribute("href")
    text = a.text.strip()
    # Extract English name and count from text e.g. "Egypt (306 Companies)"
    m = re.match(r"(.+?)\s*\(\s*(\d+)\s*Companies", text)
    if not m:
        continue
    en_name, count = m.group(1).strip(), int(m.group(2))
    slug = href.rstrip("/").split("/")[-2]
    cn_name = slug2cn.get(slug)
    if cn_name:
        child_list.append((cn_name, en_name, count, href))

# --- Step 2: Iterate each country and paginate ---
with open("selenium_oil_gas.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["国家（中文）", "国家（英文）", "公司名称", "公司链接"])
    
    for cn_name, en_name, total, country_url in child_list:
        pages = math.ceil(total / 99)
        print(f"Scraping {cn_name} ({en_name}) {total} companies → {pages} pages")
        for page in range(1, pages + 1):
            page_url = country_url if page == 1 else country_url.rstrip("/") + f"/page/{page}/"
            driver.get(page_url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.directory-content-box-col a"))
            )
            time.sleep(random.uniform(2, 4))
            
            company_els = driver.find_elements(By.CSS_SELECTOR, "div.directory-content-box-col a")
            print(f"  Page {page}: found {len(company_els)} companies")
            for comp in company_els:
                comp_name = comp.text.strip()
                comp_href = comp.get_attribute("href")
                writer.writerow([cn_name, en_name, comp_name, comp_href])
            time.sleep(random.uniform(5, 10))

driver.quit()


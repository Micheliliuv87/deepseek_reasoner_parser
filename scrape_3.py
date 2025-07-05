import os
import csv
import json
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Suppress TensorFlow / ChromeDriver logs
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # suppress TensorFlow logs
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--log-level=3")
options.add_experimental_option('excludeSwitches', ['enable-logging'])
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
)
service = Service(log_path="NUL")  # silence ChromeDriver logs on Windows
driver = webdriver.Chrome(service=service, options=options)

# Load cleaned company list
df = pd.read_csv("oil_and_gas_companies_clean.csv", encoding="utf-8-sig")
total = len(df)

# Prepare output CSV
output_file = "company_profiles.csv"
with open(output_file, "w", newline="", encoding="utf-8-sig") as fout:
    writer = csv.writer(fout)
    writer.writerow([
        "国家（中文）",
        "国家（英文）",
        "公司名称",
        "@type",
        "foundingDate",
        "numberOfEmployees",
        "name",
        "description"
    ])

    start_time = time.time()
    for idx, row in df.iterrows():
        cn_country = row["国家（中文）"]
        en_country = row["国家（英文）"]
        comp_name  = row["公司名称"]
        url        = row["公司链接"]

        # Load page and wait for JSON-LD
        driver.get(url)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "script[type='application/ld+json']"))
            )
        except:
            org_data = None
        else:
            time.sleep(1)
            scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
            org_data = None
            for s in scripts:
                try:
                    data = json.loads(s.get_attribute("innerText"))
                except:
                    continue
                # handle list vs dict
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Organization":
                            org_data = item
                            break
                elif data.get("@type") == "Organization":
                    org_data = data
                if org_data:
                    break

        # Fill defaults
        at_type  = org_data.get("@type", "N/A") if org_data else "N/A"
        founding = org_data.get("foundingDate", "N/A") if org_data else "N/A"
        emp_num  = org_data.get("numberOfEmployees", "N/A") if org_data else "N/A"
        name_ld  = org_data.get("name", "N/A") if org_data else "N/A"
        desc     = org_data.get("description", "N/A") if org_data else "N/A"

        writer.writerow([
            cn_country, en_country, comp_name,
            at_type, founding, emp_num, name_ld, desc
        ])

        # Progress report
        elapsed = time.time() - start_time
        processed = idx + 1
        rate = elapsed / processed
        remaining = total - processed
        eta = rate * remaining
        print(f"[{processed}/{total}] {comp_name} → elapsed: {elapsed:.1f}s, ETA: {eta:.1f}s")

driver.quit()
print(f"Done! Profiles saved to {output_file}")

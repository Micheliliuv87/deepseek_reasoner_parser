# rescrape_and_fill_with_json_url.py

import time
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Selenium Setup (silence logs) ---
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--log-level=3")
options.add_experimental_option('excludeSwitches', ['enable-logging'])
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
) # set your own 
service = Service(log_path="NUL")
driver = webdriver.Chrome(service=service, options=options)

# --- Load dataframes ---
df_profiles = pd.read_csv("company_profiles.csv", encoding="utf-8-sig")
df_urls     = pd.read_csv("oil_and_gas_companies_clean.csv", encoding="utf-8-sig")

# Merge on 国家（中文）、国家（英文）、公司名称 to get 公司页面链接
df = df_profiles.merge(
    df_urls[["国家（中文）","国家（英文）","公司名称","公司链接"]],
    on=["国家（中文）","国家（英文）","公司名称"],
    how="left"
)

df = df.drop(columns=['公司链接'], errors='ignore')

# Add json_url column if not present
if "json_url" not in df.columns:
    df["json_url"] = "N/A"

# Fields to check/update
fields = ["@type", "foundingDate", "numberOfEmployees", "name", "description", "json_url"]

# Identify rows needing re-scrape: >2 missing/N/A/空
mask_need = df[fields].apply(lambda col: col.isna() | col.eq("N/A") | col.eq(""), axis=0) \
               .sum(axis=1) > 2
to_fix = df[mask_need].copy()
print(f"numbers of rows needs to update{len(to_fix)} 条")

# --- Re-scrape ---
for idx, row in to_fix.iterrows():
    page_url = row["公司链接"]
    comp     = row["公司名称"]
    print(f"[{idx}] update {comp}  → {page_url}")
    driver.get(page_url)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "script[type='application/ld+json']"))
        )
        time.sleep(1)
        scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
        org_data = None
        for s in scripts:
            try:
                data = json.loads(s.get_attribute("innerText"))
            except:
                continue
            # Check if data is a list or dict
            if isinstance(data, list):
                for it in data:
                    if it.get("@type") == "Organization":
                        org_data = it
                        break
            elif data.get("@type") == "Organization":
                org_data = data
            if org_data:
                break
    except:
        org_data = None

    # if is N/A or empty, fill with org_data
    for f in fields:
        old = df.at[idx, f]
        if pd.isna(old) or old in ("", "N/A"):
            new = org_data.get(f if f!="json_url" else "url", "N/A") if org_data else "N/A"
            df.at[idx, f] = new

# --- Save final CSV ---
out = "company_profiles_filled_with_json_url.csv"
df.to_csv(out, index=False, encoding="utf-8-sig")
print(f"update complete, saved file {out}")

driver.quit()


# updated parts that should get rid of very unnecessary columns
# 1. read the CSV file with filled json_url
df = pd.read_csv('company_profiles_filled_with_json_url.csv', encoding='utf-8-sig')

# 2. delete the original '公司链接' column
df = df.drop(columns=['公司链接'], errors='ignore')

# save the cleaned DataFrame to a new CSV file
df.to_csv('company_profiles_cleaned.csv', index=False, encoding='utf-8-sig')
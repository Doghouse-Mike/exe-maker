import pandas as pd
import time
import os
import re
import random
import sys
from tkinter import Tk, filedialog
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# --- VISUAL FILE PICKER ---
# Hide the main blank Tkinter window
root = Tk()
root.withdraw()
root.attributes('-topmost', True)

print("Please select your exported 'dpd_list.csv' file...")
input_csv = filedialog.askopenfilename(
    title="Select your DPD CSV file",
    filetypes=[("CSV Files", "*.csv")]
)

if not input_csv:
    print("No file selected. Exiting...")
    time.sleep(3)
    sys.exit()

# Set output path to the same directory as the input file
output_csv = os.path.join(os.path.dirname(input_csv), "dpd_results.csv")

# Load the file
df = pd.read_csv(input_csv)

# Ensure our output columns exist
if 'Last update' not in df.columns:
    df['Last update'] = ""
if 'Date of last update' not in df.columns:
    df['Date of last update'] = ""

df['Last update'] = df['Last update'].fillna("").astype(str)
df['Date of last update'] = df['Date of last update'].fillna("").astype(str)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
]

WINDOW_SIZES = [(1366, 768), (1440, 900), (1536, 864), (1920, 1080)]

def launch_stealth_browser():
    options = uc.ChromeOptions()
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    driver = uc.Chrome(options=options)
    width, height = random.choice(WINDOW_SIZES)
    driver.set_window_size(width, height)
    return driver

def get_parcelsapp_status(driver, tracking_id):
    if pd.isna(tracking_id):
        return "No ID", "No Date"
    url = f"https://parcelsapp.com/en/tracking/{int(tracking_id)}"
    try:
        driver.get(url)
        time.sleep(5)
        page_text = driver.find_element(By.TAG_NAME, "body").text
        clean_text = page_text.replace('\n', ' | ')
        
        if "Information has not been found yet" in page_text or "try to check again" in page_text or "TRY AGAIN" in page_text:
            return "TRY AGAIN", "Rate Limited / Retrying Later"
            
        match = re.search(r"Add package title\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)", clean_text)
        if match:
            return match.group(3).strip(), f"{match.group(1).strip()} {match.group(2).strip()}"
            
        lines = page_text.split('\n')
        for i, line in enumerate(lines):
            if "Your parcel" in line or "Delivered" in line or "dropped off" in line or "delay" in line:
                possible_date = lines[i-1] if i > 0 else "Unknown Date"
                return line.strip(), possible_date.strip()
                
        return "Status Not Found", "Date Not Found"
    except Exception as e:
        return "Error/Blocked", "Error/Blocked"

unique_ids = df['Return Tracking ID'].dropna().unique()
ids_to_track = []
results_cache = {}

for _, row in df.iterrows():
    tid = row['Return Tracking ID']
    if pd.notna(tid):
        is_failed_row = row['Last update'] in ["", "Layout Changed", "Error/Blocked", "TRY AGAIN", "Status Not Found"]
        if row['Last update'] and not is_failed_row:
            results_cache[tid] = {"Last update": row['Last update'], "Date of last update": row['Date of last update']}

for tid in unique_ids:
    if tid not in results_cache:
        ids_to_track.append(tid)

print(f"Total items left to track: {len(ids_to_track)}")
if len(ids_to_track) == 0:
    print("Everything already tracked!")
    time.sleep(3)
    sys.exit()

driver = launch_stealth_browser()

try:
    success_count = 0
    for idx, tid in enumerate(ids_to_track):
        if success_count > 0 and success_count % 35 == 0:
            print("\n=== 8-Minute Cool Down ===")
            driver.quit()
            time.sleep(480)
            driver = launch_stealth_browser()

        status, date = get_parcelsapp_status(driver, tid)
        results_cache[tid] = {"Last update": status, "Date of last update": date}
        print(f"[{idx+1}/{len(ids_to_track)}] Tracked: {tid} -> {status}")
        success_count += 1
        time.sleep(random.uniform(4.5, 7.5))
finally:
    df['Last update'] = df['Return Tracking ID'].map(lambda x: results_cache.get(x, {}).get("Last update", ""))
    df['Date of last update'] = df['Return Tracking ID'].map(lambda x: results_cache.get(x, {}).get("Date of last update", ""))
    df.to_csv(output_csv, index=False)
    driver.quit()
    print(f"\nSaved! Open 'dpd_results.csv' in the same folder.")
    time.sleep(5)

# Minecraft wiki item scraper
# This script scrapes item names and stack sizes from the Minecraft wiki.

import re
import json
import time
import requests
import requests_cache
import concurrent.futures
from bs4 import BeautifulSoup
from threading import Lock
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

# Enable caching to reduce repeated network requests
requests_cache.install_cache('minecraft_cache', expire_after=86400)

# Set up retry strategy for failed requests
retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    backoff_factor=1
)
adapter = HTTPAdapter(max_retries=retry_strategy)

session = requests.Session()
session.mount("https://", adapter)
session.mount("http://", adapter)

output_file = 'minecraft_items.json'
data_lock = Lock()  # Lock to ensure thread-safe access to items_data

items_data = []

def save_data():
    """Save collected item data to a JSON file."""
    with open(output_file, 'w') as f:
        json.dump(items_data, f, indent=4)
    print(f"Progress saved to {output_file} ({len(items_data)} items)")

def get_stackable_info(item_url):
    try:
        response = session.get(item_url, timeout=10)
        if response.status_code != 200:
            print(f"[!] Failed to retrieve: {item_url}")
            return 1

        soup = BeautifulSoup(response.text, 'html.parser')
        infobox_tables = soup.find_all('table', class_='infobox-rows')

        for table in infobox_tables:
            for row in table.find_all('tr'):
                header = row.find('th')
                if header and header.get_text(strip=True) == "Stackable":
                    value_cell = row.find('td')
                    if value_cell:
                        text = value_cell.get_text(strip=True)
                        if "Yes" in text:
                            match = re.search(r'\((\d+)\)', text)
                            return int(match.group(1)) if match else 64
                        else:
                            return 1
        return 1
    except Exception as e:
        print(f"[!] Exception for {item_url}: {e}")
        return 1

def fetch_item_data(item_tuple):
    item_name, item_url = item_tuple
    stack_size = get_stackable_info(item_url)

    time.sleep(0.2)  # Delay between requests to reduce server load

    item_entry = {"item": item_name, "stack": stack_size}

    with data_lock:
        items_data.append(item_entry)

    return item_entry

def main():
    base_url = "https://minecraft.wiki/w/Item#Lists_of_items"
    print(f"Fetching item list from: {base_url}")

    response = session.get(base_url)
    if response.status_code != 200:
        print("[!] Failed to retrieve the item listing page")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    div_cols = soup.find_all('div', class_='div-col')

    item_tuples = []
    for div in div_cols:
        for link in div.find_all('a', href=True):
            item_name = link.get_text(strip=True)
            if not item_name:
                continue  # Skip links with no text
            elif item_name == "JE":
                continue  # Skip "JE" links
            elif item_name == "BE":
                continue  # Skip "BE" links

            item_url = "https://minecraft.wiki" + link['href']
            item_tuples.append((item_name, item_url))


    print(f"Total items found: {len(item_tuples)}")
    print("Fetching item data in parallel...")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            list(tqdm(executor.map(fetch_item_data, item_tuples), total=len(item_tuples)))
    except KeyboardInterrupt:
        print("\n[!] KeyboardInterrupt received. Saving partial progress...")
        save_data()
        return

    save_data()
    print(f"Finished. Total items scraped: {len(items_data)}")

if __name__ == "__main__":
    start = time.time()
    main()
    print(f"Total time: {time.time() - start:.2f} seconds")
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
import os

# --- Configuration ---
session = cloudscraper.create_scraper(
    browser={
        'browser': 'firefox',
        'platform': 'windows',
        'mobile': False
    }
)

session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://gg.deals/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
})

session.cookies.set("cookieconsent_status", "dismiss", domain=".gg.deals")

BASE_URL = 'https://gg.deals'


# --- Helper Functions ---
# --- THIS IS THE CORRECTED FUNCTION ---
def get_game_time_from_soup(soup):
    """Extracts 'All Styles' game time from a pre-parsed BeautifulSoup object."""
    try:
        # Step 1: Find the <span> with the title "All Styles".
        all_styles_span = soup.find('span', class_='title', string='All Styles')

        if not all_styles_span: return 0

        # Step 2: Navigate to the parent container.
        parent_container = all_styles_span.find_parent('div', class_='how-long-to-beat-single')
        if not parent_container: return 0

        # Step 3: Find the <span> with class 'value' inside that parent.
        time_element = parent_container.find('span', class_='value')
        if not time_element: return 0

        # The rest of the parsing logic is the same
        time_value = time_element.get_text(strip=True)
        hours, minutes = 0, 0
        parts = time_value.lower().replace('h', 'h ').strip().split()
        for part in parts:
            if 'h' in part:
                hours = int(part.replace('h', ''))
            elif 'm' in part:
                minutes = int(part.replace('m', ''))
        return (hours * 60) + minutes
    except (ValueError, AttributeError, IndexError):
        return 0


# --- THIS IS THE UPDATED FUNCTION ---
def scrape_game_page(url, referer_url):
    """
    Scrapes all required information from a single game page.
    Returns a dictionary of the data, or None if the request fails.
    """
    # Increased randomness in sleep to be a bit more human-like
    time.sleep(random.uniform(2.0, 4.5))
    try:
        page_headers = session.headers.copy()
        page_headers['Referer'] = referer_url

        response = session.get(url, headers=page_headers, timeout=25)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'lxml')
        title_element = soup.find('a', class_='game-info-title')
        title = title_element.text.strip() if title_element else "Unknown Title"

        # --- START: MODIFIED PRICE LOGIC ---
        price = "0"
        # Step 1: Find the label "Official Stores low:"
        price_label_span = soup.find('span', class_='game-info-price-label', string='Official Stores low:')

        if price_label_span:
            # Step 2: Navigate to the specific parent container for this price box.
            # This is more robust than a generic find_parent('div').
            container = price_label_span.find_parent('div', class_='game-header-price-box')

            if container:
                # Step 3: Find the price element within that specific container.
                price_element = container.find('span', class_='price-inner')
                if price_element:
                    price = price_element.get_text(strip=True)
        # --- END: MODIFIED PRICE LOGIC ---

        total_minutes = get_game_time_from_soup(soup)

        return {
            'Game Title': title,
            'Historical Low': price,
            'Length(in minutes)': total_minutes
        }
    # Using specific exception from requests library which cloudscraper uses
    except importlib.metadata.PackageNotFoundError:  # A known cloudscraper issue sometimes
        print(f"Cloudscraper dependency issue with {url}. Skipping.")
        return None
    except Exception as e:
        print(f"Error processing {url}: {type(e).__name__} - {e}")
        return None


# --- Main Logic ---
# ... (The rest of your code is perfect and does not need changes) ...
print("Warming up session to get initial cookies...")
try:
    session.get(BASE_URL, timeout=15)
    print("Session is ready.")
except Exception as e:
    print(f"Failed to warm up session: {e}. Exiting.")
    exit()

start_time = time.time()

futures = []
all_game_urls_count = 0

print("\nPhase 1 & 2: Fetching URLs and submitting to scraper...")
with ThreadPoolExecutor(max_workers=3) as executor:  # Increased workers back to 3, cloudscraper is robust
    page_num = 1
    while True:
        list_url = (f'https://gg.deals/games/?hideOwned=1&minHltbCompletionAll=1&minMetascore=1&minPrice=0.1&sort'
                    f'=price&subscription=116734&type=1&page={page_num}')
        print(f"Fetching list page {page_num}...")
        try:
            response = session.get(list_url, timeout=15)
            if response.status_code != 200:
                print(f"Stopping at page {page_num}, received status {response.status_code}.")
                break

            soup = BeautifulSoup(response.text, "lxml")
            links = soup.find_all('a', class_='main-image')

            if not links:
                print(f"No more games found on page {page_num}. Stopping.")
                break

            for link in links:
                href = link.get('href')
                if href:
                    game_url = BASE_URL + href
                    futures.append(executor.submit(scrape_game_page, game_url, list_url))
                    all_game_urls_count += 1

            page_num += 1
            time.sleep(random.uniform(1.5, 3.0))

        except Exception as e:
            print(f"Could not fetch list page {page_num}: {e}. Stopping.")
            break

print(f"\nFound and submitted {all_game_urls_count} game URLs to scrape. Now processing results...")

all_game_data = []
for i, future in enumerate(as_completed(futures), 1):
    result = future.result()
    if result:
        all_game_data.append(result)
    print(f"Progress: {i}/{all_game_urls_count}", end='\r', flush=True)

print("\n\nScraping complete.")

# --- Data Processing ---
print("\nPhase 3: Processing data and saving to CSV...")
if not all_game_data:
    print("No data was scraped. Exiting.")
else:
    df = pd.DataFrame(all_game_data)
    df = df[df["Length(in minutes)"] > 0].copy()
    df["Historical Low"] = df["Historical Low"].str.strip().str.replace(",", ".", regex=False).str.replace("~", "",
                                                                                                           regex=False).str.replace(
        "€", "", regex=False)
    df["Historical Low"] = pd.to_numeric(df["Historical Low"], errors="coerce")
    df["Length(in minutes)"] = pd.to_numeric(df["Length(in minutes)"], errors="coerce")
    df.dropna(subset=["Historical Low", "Length(in minutes)"], inplace=True)
    if "Length(in minutes)" in df.columns:
        df = df.astype({"Length(in minutes)": int})

    # Check if the dataframe is empty AFTER filtering
    if df.empty:
        print("Data was scraped, but all entries were filtered out (e.g., no game time found).")
    else:
        print("\n--- Sample of Processed Data ---")
        print(df.head())
        print("--------------------------------")

    output_path = r'C:\Users\Tom\OneDrive\Desktop\File CSV\gamepass_picker.csv'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    df.to_csv(output_path, sep='\t', encoding='utf-8', index=False)
    print(f"Data successfully saved to {output_path}")

end_time = time.time()
print(f"\nTotal execution time: {end_time - start_time:.2f} seconds.")

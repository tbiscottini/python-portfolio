import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import math
from urllib.parse import urljoin
import pprint
import sys
import csv  # <--- Import the CSV module


# --- Helper function to convert size strings to bytes (No change here) ---
def parse_size_to_bytes(size_str):
    if not size_str:
        return None
    size_str = size_str.strip().upper()
    match = re.search(r'([\d.,]+)\s*(GB|MB|KB|B)', size_str)
    if not match:
        return None
    number_str = match.group(1).replace(',', '.')
    try:
        number = float(number_str)
    except ValueError:
        # print(f"Warning: Could not convert number part '{match.group(1)}' to float.")
        return None
    unit = match.group(2)
    if unit == 'GB':
        multiplier = 1024 ** 3
    elif unit == 'MB':
        multiplier = 1024 ** 2
    elif unit == 'KB':
        multiplier = 1024
    elif unit == 'B':
        multiplier = 1
    else:
        return None
    return int(number * multiplier)


# --- Function for ONE helper to get ONE detail page and find the size (No change here) ---
async def fetch_game_size(session, url, game_name, headers):
    """Fetches a single game detail page and extracts the download size."""
    # print(f"  [ASYNC Detail] Fetching: {game_name} ({url})") # Less verbose logging
    try:
        async with session.get(url, headers=headers, timeout=25) as response:  # Slightly longer timeout
            response.raise_for_status()
            html = await response.text()
            loop = asyncio.get_running_loop()
            detail_soup = await loop.run_in_executor(None, BeautifulSoup, html, 'lxml')

            size_li = None
            list_items = await loop.run_in_executor(None, detail_soup.find_all, 'li', {'class': 'list-group-item'})

            for item in list_items:
                item_text = item.get_text(" ", strip=True)
                if 'Download size:' in item_text or 'download size:' in item_text:  # Case-insensitive check might be
                    # better
                    size_li = item
                    # print(f"  [DEBUG] Found potential size element for {game_name}: {item_text}") # Debug logging
                    # if needed
                    break

            if size_li:
                full_text = size_li.get_text(strip=True)
                try:
                    parts = full_text.split(':', 1)
                    if len(parts) == 2:
                        size_part = parts[1].strip()
                        size_bytes = parse_size_to_bytes(size_part)
                        # if size_bytes is not None: print(f"  [ASYNC Detail] Found size for {game_name}: '{
                        # size_part}' -> {size_bytes} bytes") else: print(f"  [ASYNC Detail] Found size text for {
                        # game_name} ('{size_part}'), but couldn't parse value.")
                        return size_bytes
                    else:
                        # print(f"  [ASYNC Detail] Found 'Download size' text for {game_name}, but couldn't split
                        # Key:Value from: '{full_text}'")
                        return None
                except Exception as parse_err:
                    # print(f"  [ASYNC Detail] Error parsing size value for {game_name} from text '{full_text}': {
                    # parse_err}")
                    return None
            else:
                # print(f"  [ASYNC Detail] Size element not found for {game_name}")
                return None

    except asyncio.TimeoutError:
        # print(f"  [ASYNC Detail] Timeout error for {game_name} from {url}")
        return None
    except aiohttp.ClientResponseError as e:
        # print(f"  [ASYNC Detail] HTTP error {e.status} for {game_name} ({url}): {e.message}")
        return None
    except aiohttp.ClientError as e:
        # print(f"  [ASYNC Detail] Client connection error for {game_name} ({url}): {e}")
        return None
    except Exception as e:
        # print(f"  [ASYNC Detail] Unexpected error processing {game_name} ({url}): {type(e).__name__} - {e}")
        return None


# --- Main part that orchestrates everything ---
async def main():
    """Main async function to fetch all list pages, details, and save to CSV."""
    base_list_url = "https://www.dekudeals.com/games?filter[discount]=lowest&page_size=all&filter[store]=microsoft_it"  # Base URL without page
    base_url = "https://www.dekudeals.com"
    output_csv_file = "dekudeals_microsoft_it_lowest.csv"  # Name for the output file

    # --- !!! IMPORTANT: PASTE YOUR SESSION COOKIE HERE FOR THE SCRIPT TO WORK !!! ---
    session_cookie_value = "INCOLLA_QUI_IL_TUO_COOKIE_DI_SESSIONE"

    if "YOUR_ACTUAL_RACK_SESSION_VALUE_HERE" in session_cookie_value:
        print("=" * 60)
        print("!!! WARNING: You haven't replaced the placeholder session cookie! !!!")
        print("!!! Script will run but may not see logged-in content.         !!!")
        print("=" * 60)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/100.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
                  'application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': base_url + "/",
        'Cookie': session_cookie_value
    }

    all_initial_game_data = []  # To store basic info from ALL pages
    all_tasks = []  # To store detail fetch tasks from ALL pages
    page_number = 1

    async with aiohttp.ClientSession() as session:
        # Loop through pages until an empty page is found
        while True:
            list_url = f"{base_list_url}&page={page_number}"  # Construct URL for current page
            print(f"Fetching list page {page_number}: {list_url}")

            try:
                async with session.get(list_url, headers=headers, timeout=15) as response:
                    if response.status == 404:  # Stop if page not found
                        print(f"Page {page_number} returned 404, assuming end of results.")
                        break
                    response.raise_for_status()  # Check for other HTTP errors
                    html = await response.text()

            except aiohttp.ClientResponseError as e:
                print(f"HTTP error {e.status} fetching page {page_number}. Stopping pagination. Error: {e.message}")
                break  # Stop if a page fetch fails badly
            except Exception as e:
                print(f"Error fetching list page {page_number}: {e}. Stopping pagination.")
                break  # Stop if other error occurs

            # Parse the current list page
            loop = asyncio.get_running_loop()
            try:
                list_soup = await loop.run_in_executor(None, BeautifulSoup, html, 'lxml')
                game_cards = await loop.run_in_executor(None, list_soup.find_all, 'div', {'class': 'col d-block'})
                print(f"Found {len(game_cards)} game cards on page {page_number}.")

                # If no game cards found on the page, we've reached the end
                if not game_cards:
                    print(f"No games found on page {page_number}, assuming end of results.")
                    break

                # Process cards on this page
                for card in game_cards:
                    game_info = {}
                    try:
                        name_tag = await loop.run_in_executor(None, card.select_one, 'a.main-link h6.line-clamp-3-to-2')
                        game_info['name'] = name_tag.get_text(strip=True) if name_tag else "Name not found"

                        price_tag = await loop.run_in_executor(None, card.select_one, 'div.text-tight strong')
                        game_info['discounted_price'] = price_tag.get_text(
                            strip=True) if price_tag else "Price not found"

                        link_tag = await loop.run_in_executor(None, card.select_one, 'a.main-link')
                        detail_url = None
                        if link_tag and link_tag.has_attr('href'):
                            detail_url = urljoin(base_url, link_tag['href'])
                            game_info['detail_url'] = detail_url
                        else:
                            game_info['detail_url'] = None

                        game_info['size_bytes'] = None  # Initialize size
                        all_initial_game_data.append(game_info)  # Add basic info to master list

                        # If detail URL exists, create a task for it
                        if detail_url:
                            task = asyncio.create_task(fetch_game_size(session, detail_url, game_info['name'], headers))
                            all_tasks.append(task)
                        else:
                            # Need a placeholder in tasks list to match results later
                            all_tasks.append(asyncio.sleep(0, result=None))
                            # print(f" - No detail URL found for {game_info['name']}") # Less verbose

                    except Exception as e:
                        print(f"Error processing a card on page {page_number}: {e} - Skipping card.")
                        # Ensure lists stay aligned even if a card fails
                        all_initial_game_data.append(
                            {'name': 'Error Parsing Card', 'discounted_price': 'N/A', 'detail_url': None,
                             'size_bytes': None})
                        all_tasks.append(asyncio.sleep(0, result=None))

                # Go to the next page
                page_number += 1
                await asyncio.sleep(5)  # INCREASED polite delay between page requests

            except Exception as e:
                print(f"Error parsing list page {page_number}: {e}. Stopping pagination.")
                break  # Stop if parsing fails

        # --- Fetch all detail pages concurrently AFTER processing all list pages ---
        if not all_tasks:
            print("No detail page tasks were created. Exiting.")
            return

        print(f"\nStarting {len(all_tasks)} detail page fetches for all games found...")
        # Run all collected tasks
        size_results = await asyncio.gather(*all_tasks)
        print("...All detail page fetches have completed.")

        # --- Combine initial data with fetched sizes ---
        final_game_data = []
        if len(all_initial_game_data) != len(size_results):
            print("WARNING: Mismatch between initial data count and size results count. CSV output might be incorrect.")
            # Attempt to merge based on index anyway, but be aware of potential issues

        # Correctly merge results back based on the order tasks were added
        result_index = 0
        for game_info in all_initial_game_data:
            # Only assign a result if we expected one (i.e., if a task other than sleep(0) was added)
            # A simpler way is just to align by index, assuming placeholders were added correctly
            if result_index < len(size_results):
                game_info['size_bytes'] = size_results[result_index]
            else:
                game_info['size_bytes'] = None  # Should not happen if placeholders handled correctly
            final_game_data.append(game_info)
            result_index += 1

        # --- Save the final data to CSV ---
        if not final_game_data:
            print("No game data collected. Nothing to save.")
            return

        print(f"\nSaving {len(final_game_data)} records to {output_csv_file}...")
        # Define the columns (must match keys in the dictionaries)
        fieldnames = ['name', 'discounted_price', 'size_bytes', 'detail_url']
        try:
            with open(output_csv_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames,
                                        extrasaction='ignore')  # Ignore extra keys if any

                writer.writeheader()  # Write the header row
                writer.writerows(final_game_data)  # Write all game data
            print("Data successfully saved to CSV.")
        except IOError as e:
            print(f"Error writing to CSV file {output_csv_file}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during CSV writing: {e}")


# --- Entry point for the script ---
if __name__ == "__main__":
    asyncio.run(main())
import asyncio
from playwright.async_api import async_playwright
import datetime  # For filename

# --- Configuration ---
URL = "https://www.justwatch.com/it/film"
BASE_DOMAIN_URL = "https://www.justwatch.com/"

# --- OPTIMIZED SCROLL & TIMEOUT SETTINGS ---
SCROLL_PAUSE_TIME_S = 0.75  # Reduced fixed pause after networkidle. Adjust based on site behavior.
MAX_STABLE_SCROLLS = 5  # How many scrolls with no new items before stopping.
PAGE_LOAD_TIMEOUT = 45000  # Reduced page load timeout (original: 60000)
NETWORK_IDLE_TIMEOUT = 5000  # Reduced network idle timeout (original: 7000)
VIEWPORT_SIZE = {"width": 1920, "height": 1080}  # Larger viewport might load more items per scroll

# --- NEW CONFIGURATION FOR LIMITING RESULTS ---
MAX_TITLES_TO_SCRAPE = 1400  # Set to your desired limit, or None to scrape all.

# --- DEBUGGING SETTINGS ---
RUN_HEADLESS = False  # Set to True for faster, invisible runs
SLOW_MO_MS = 100  # Reduced slow_mo for faster debugging (original: 250)
# --- OPTIMIZATION SETTINGS ---
BLOCK_RESOURCES = True
# --- TEST THIS SETTING: Does the site work without a forced reload after cookie injection? ---
# If True, it will reload. If False, it skips the reload (faster if site allows).
# Start with False. If content doesn't load correctly, set to True.
FORCE_RELOAD_AFTER_COOKIE_BANNER = False

# --- YOUR COOKIES GO HERE ---
GENERIC_COOKIE_PLACEHOLDER_VALUE = "PASTE_FRESH_VALUE_FROM_BROWSER_HERE"
YOUR_COOKIES = [
    # ... (Your cookie data remains the same, ensure it's updated) ...
    # Example:
    {
        "name": "jw_user",
        "value": GENERIC_COOKIE_PLACEHOLDER_VALUE,  # <-- REPLACE
        "domain": "www.justwatch.com", "path": "/", "secure": True, "httpOnly": False, "sameSite": "Strict"
    },
    {
        "name": "access_token",
        "value": GENERIC_COOKIE_PLACEHOLDER_VALUE,  # <-- REPLACE
        "domain": "www.justwatch.com", "path": "/", "secure": True, "httpOnly": False, "sameSite": "Strict"
    },
    {
        "name": "jw_id",
        "value": GENERIC_COOKIE_PLACEHOLDER_VALUE,  # <-- REPLACE
        "domain": "www.justwatch.com", "path": "/", "secure": True, "httpOnly": False, "sameSite": "None"
    }
]


# --- End Configuration ---

async def extract_movie_titles(target_url: str, base_url: str, cookies_to_set: list) -> list[str]:
    print(f"🤖 Starting the super-charged robot helper! Headless: {RUN_HEADLESS}")
    if not RUN_HEADLESS:
        print(f"🐢 Slow_mo active: {SLOW_MO_MS}ms between actions.")
    if BLOCK_RESOURCES:
        print("🚫 Resource blocking (images, CSS, fonts, media) is ON for speed!")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=RUN_HEADLESS,
            slow_mo=SLOW_MO_MS if not RUN_HEADLESS else 0
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/100.0.4896.127 Safari/537.36",
            viewport=VIEWPORT_SIZE  # Tell the browser to be a big window!
        )
        print(f"🖥️ Browser viewport set to: {VIEWPORT_SIZE['width']}x{VIEWPORT_SIZE['height']}")

        if BLOCK_RESOURCES:
            try:
                await context.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in ["image", "stylesheet", "font", "media",
                                                       "other"]  # Added "other" for more aggressive blocking
                    else route.continue_()
                )
                print("👍 Resource routing rules applied (even more aggressive).")
            except Exception as e:
                print(f"⚠️ Could not set up resource blocking: {e}.")

        page = await context.new_page()
        page.set_default_timeout(PAGE_LOAD_TIMEOUT)  # Set default timeout for page operations

        print(f"➡️ Robot is going to base domain first: {base_url}")
        try:
            # For base domain, domcontentloaded is usually enough if we're just setting cookies
            await page.goto(base_url, timeout=PAGE_LOAD_TIMEOUT, wait_until='domcontentloaded')
            print(f"✅ Base domain page ({base_url}) loaded.")
        except Exception as e:
            print(f"⚠️ Could not load base domain page {base_url}: {e}. Continuing...")

        try:
            print(f"🍪 Attempting to set {len(cookies_to_set)} cookie(s) for domain: {base_url.split('/')[2]}")
            await context.add_cookies(cookies_to_set)
            print("✅ Robot has received cookies.")
            if not RUN_HEADLESS:
                print("⏸️ PAUSING AFTER ADDING COOKIES: Verify in DevTools if needed.")
                await page.pause()  # Keep pause for headed mode debugging
        except Exception as e:
            print(f"⚠️ Error setting cookies: {e}. Exiting.")
            await browser.close()
            return []

        print(f"➡️ Robot is going to target page: {target_url}")
        try:
            # 'load' or 'networkidle' can be good here. 'networkidle' might be slower but more robust for SPAs.
            # Let's try 'load' first for speed, assuming initial content is there.
            await page.goto(target_url, timeout=PAGE_LOAD_TIMEOUT, wait_until='load')
            print(f"✅ Target page ({target_url}) initially loaded.")

            # --- Cookie Banner Handling (Attempt before potential reload) ---
            cookie_banner_selectors = [
                "button#onetrust-accept-btn-handler", "button[data-testid='uc-accept-all-button']",
                "button[aria-label*='Accept']", "button[aria-label*='Agree']",
                "button:has-text('Accept all')", "button:has-text('Agree to all')"
            ]
            banner_clicked = False
            for i, selector in enumerate(cookie_banner_selectors):
                try:
                    print(f"🧐 Looking for cookie banner with selector: '{selector}' (timeout 5s)...")
                    # Using wait_for_selector with shorter timeout for banners
                    await page.wait_for_selector(selector, timeout=5000, state="visible")
                    await page.click(selector, timeout=3000)  # Quick click timeout
                    print(f"👍 Clicked cookie consent button via selector: '{selector}'.")
                    await page.wait_for_timeout(500)  # Brief pause for banner to disappear
                    banner_clicked = True
                    break
                except Exception:
                    print(f"ℹ️ Cookie banner ('{selector}') not found or click failed.")

            if FORCE_RELOAD_AFTER_COOKIE_BANNER and banner_clicked:
                print("🔄 Robot is configured to reload the page after cookie banner interaction...")
                await page.reload(wait_until='load')  # Or 'networkidle' if needed
                print("✅ Target page reloaded successfully!")
            elif not banner_clicked:
                print(f"🤷 No known cookie banners found/clicked. Proceeding...")

            if not RUN_HEADLESS:
                print("⏸️ PAUSING AFTER INITIAL LOAD/BANNER CHECK: Observe page state.")
                await page.pause()
        except Exception as e:
            print(f"❌ Error loading/reloading page: {e}")
            if not RUN_HEADLESS:
                await page.screenshot(path="error_page_load_or_reload.png")
            await browser.close()
            return []

        # --- Scrolling Logic ---
        seen_titles = set()
        stable_scroll_count = 0
        scroll_attempts = 0
        max_scroll_attempts = (
                                  MAX_TITLES_TO_SCRAPE // 10 if MAX_TITLES_TO_SCRAPE else 20) + 20  # Adjusted
        # dynamic max scrolls
        # (The +20 is a buffer. //10 assumes at least 10 items load per scroll on average)

        print(
            f"📜 Starting to scroll and collect movie titles (target: {MAX_TITLES_TO_SCRAPE if MAX_TITLES_TO_SCRAPE is not None else 'all available'} titles)...")

        while stable_scroll_count < MAX_STABLE_SCROLLS and \
                scroll_attempts < max_scroll_attempts and \
                (MAX_TITLES_TO_SCRAPE is None or len(seen_titles) < MAX_TITLES_TO_SCRAPE):

            scroll_attempts += 1
            # Removed the initial page.wait_for_timeout(500) here, relying on waits after scroll

            initial_item_count_this_loop_start = len(seen_titles)

            # It's good practice to wait for at least one item to be present before querying all
            # This can prevent errors if the page is slow to render initial items after a scroll
            try:
                await page.wait_for_selector('div[data-testid="titleItem"]', state='attached',
                                             timeout=NETWORK_IDLE_TIMEOUT)
            except Exception:
                # If after network idle and scroll, no items appear, it might be the end or an issue
                print(
                    f"🤔 Scroll {scroll_attempts}: No 'titleItem' detected after waiting. Possible end of content or "
                    f"load issue.")
                # This could be a condition to increment stable_scroll_count or break if it persists
                if initial_item_count_this_loop_start == 0 and scroll_attempts > 1:  # No items ever, after first scroll
                    print("🚫 No items found at all. Check selectors or page content.")
                    break
                # If we had items before, this might be a genuine end of scroll
                stable_scroll_count += 1
                if stable_scroll_count >= MAX_STABLE_SCROLLS:
                    print(
                        f"🏁 Reached max stable scrolls ({MAX_STABLE_SCROLLS}) because no items appeared after scroll.")
                    break
                # Scroll again and see
                await page.keyboard.press("End")
                await page.wait_for_load_state('networkidle', timeout=NETWORK_IDLE_TIMEOUT)
                await asyncio.sleep(SCROLL_PAUSE_TIME_S)  # Short pause after network idle
                continue

            movie_elements = await page.query_selector_all('div[data-testid="titleItem"]')

            if not movie_elements and scroll_attempts == 1 and initial_item_count_this_loop_start == 0:
                print("⚠️ No movie elements ('div[data-testid=\"titleItem\"]') found on initial view.")
                if not RUN_HEADLESS:
                    await page.screenshot(path="no_movies_initial.png")

            current_titles_on_page_this_pass = set()
            for element_handle in movie_elements:
                title_attr = await element_handle.get_attribute('data-title')
                if title_attr:
                    current_titles_on_page_this_pass.add(title_attr.strip())

            newly_discovered_titles_on_page = current_titles_on_page_this_pass - seen_titles

            if newly_discovered_titles_on_page:
                can_add_count = float('inf')
                if MAX_TITLES_TO_SCRAPE is not None:
                    can_add_count = MAX_TITLES_TO_SCRAPE - len(seen_titles)

                titles_to_add_this_round = list(newly_discovered_titles_on_page)[:int(can_add_count)]

                if titles_to_add_this_round:
                    seen_titles.update(titles_to_add_this_round)
                    target_display = str(MAX_TITLES_TO_SCRAPE) if MAX_TITLES_TO_SCRAPE is not None else "unlimited"
                    print(
                        f"✨ Scroll {scroll_attempts}: Added {len(titles_to_add_this_round)} new movie(s). Total unique: {len(seen_titles)}/{target_display}")
                    stable_scroll_count = 0  # Reset stable count because we found new items
                else:
                    # This case (newly_discovered not empty, but titles_to_add_this_round is)
                    # implies can_add_count was <= 0, meaning limit was reached.
                    # The outer loop condition `len(seen_titles) < MAX_TITLES_TO_SCRAPE` handles this.
                    # So, this specific 'else' branch might not be hit often if limit is active.
                    # If limit is NOT active, and this is hit, it means newly_discovered was empty.
                    print(
                        f"🤔 Scroll {scroll_attempts}: Found titles already seen or limit effectively reached. Stable: {stable_scroll_count + 1}/{MAX_STABLE_SCROLLS}")
                    stable_scroll_count += 1
            else:  # No new unique titles found on the page this pass
                print(
                    f"🤔 Scroll {scroll_attempts}: No new unique movies found this pass (found {len(movie_elements)} elements, all seen or empty). Stable: {stable_scroll_count + 1}/{MAX_STABLE_SCROLLS}")
                stable_scroll_count += 1

            if MAX_TITLES_TO_SCRAPE is not None and len(seen_titles) >= MAX_TITLES_TO_SCRAPE:
                print(f"🎯 Reached target of {len(seen_titles)}/{MAX_TITLES_TO_SCRAPE} movie titles. Stopping scroll.")
                break

            if stable_scroll_count >= MAX_STABLE_SCROLLS:
                print(f"🏁 Reached max stable scrolls ({MAX_STABLE_SCROLLS}). No new items for a while.")
                break
            if scroll_attempts >= max_scroll_attempts:
                print(f"🏁 Reached max scroll attempts ({max_scroll_attempts}).")
                break

            print(f"👇 Scroll {scroll_attempts}: Scrolling down (End key)...")
            await page.keyboard.press("End")

            print(
                f"⏳ Scroll {scroll_attempts}: Waiting for network (max {NETWORK_IDLE_TIMEOUT}ms) & short pause ({SCROLL_PAUSE_TIME_S}s)...")
            try:
                # Wait for network to be idle, meaning dynamic content has likely loaded
                await page.wait_for_load_state('networkidle', timeout=NETWORK_IDLE_TIMEOUT)
                print(f"🛠️ Scroll {scroll_attempts}: Network settled.")
            except Exception as e:
                # TimeoutError is common if there's continuous minor network activity.
                # This is not always a critical failure for scraping, especially if content still loads.
                print(
                    f"⏳ Scroll {scroll_attempts}: Network idle timed out ({type(e).__name__}). Content might still be "
                    f"loading/loaded.")

            # This short, fixed pause can help if 'networkidle' fires too early for some JS rendering.
            await asyncio.sleep(SCROLL_PAUSE_TIME_S)

        print(f"🎉 Robot done collecting after {scroll_attempts} scrolls! Found {len(seen_titles)} titles.")
        if not RUN_HEADLESS:
            await page.screenshot(path="final_page_state.png")
            print("Closing browser in 3s (reduced from 5s)...")
            await asyncio.sleep(3)

        await browser.close()
        print("🤖 Robot has closed the magic window.")
        return sorted(list(seen_titles))


async def main():
    user_has_updated_all_critical_cookies = True
    if not YOUR_COOKIES:
        user_has_updated_all_critical_cookies = False
        print("🚨 ATTENTION: `YOUR_COOKIES` list is empty in the script.")
    else:
        missing_cookies_info = []
        critical_cookie_names = {"jw_user", "access_token", "jw_id"}  # Check these specifically
        found_critical_cookies = {name: False for name in critical_cookie_names}

        for i, cookie_config in enumerate(YOUR_COOKIES):
            cookie_name = cookie_config.get('name', f'Unknown at index {i}')
            cookie_value = cookie_config.get("value")

            if cookie_name in found_critical_cookies:
                found_critical_cookies[cookie_name] = True

            if not cookie_value or cookie_value == GENERIC_COOKIE_PLACEHOLDER_VALUE or "YOUR_ACTUAL" in cookie_value.upper():
                user_has_updated_all_critical_cookies = False
                placeholder_reason = "placeholder value"
                if not cookie_value:
                    placeholder_reason = "empty value"
                elif "YOUR_ACTUAL" in cookie_value.upper():
                    placeholder_reason = "example value"

                missing_cookies_info.append(
                    f"  - Cookie '{cookie_name}' has a {placeholder_reason}: '{cookie_value}'")

        for name, found in found_critical_cookies.items():
            if not found:
                user_has_updated_all_critical_cookies = False
                missing_cookies_info.append(f"  - CRITICAL Cookie '{name}' is missing from the `YOUR_COOKIES` list.")

    if not user_has_updated_all_critical_cookies:
        print("\n🚨 ATTENTION: Update critical cookies in `YOUR_COOKIES`:")
        if not missing_cookies_info and not YOUR_COOKIES:  # Handles empty list case
            print("  - The `YOUR_COOKIES` list is completely empty.")
        for info in missing_cookies_info: print(info)
        print("\nLog into JustWatch in your browser, open Developer Tools (F12), go to Application -> Cookies.")
        print(
            "Find cookies for 'www.justwatch.com', copy their 'name' and 'value' (and other relevant fields if needed) into the script.")
        print("Make sure to replace values like 'PASTE_FRESH_VALUE_FROM_BROWSER_HERE' or example values.")
        print("Exiting.")
        return

    print("✅ Cookie placeholders seem updated. Starting super-fast scrape...")
    if MAX_TITLES_TO_SCRAPE is not None:
        print(f"ℹ️ Script will attempt to scrape a maximum of {MAX_TITLES_TO_SCRAPE} titles.")

    movie_titles = await extract_movie_titles(URL, BASE_DOMAIN_URL, YOUR_COOKIES)

    if movie_titles:
        print(f"\n--- 🎬 Found {len(movie_titles)} Unique Movie Titles ---")
        for i, title in enumerate(movie_titles[:20], 1):
            print(f"{i}. {title}")
        if len(movie_titles) > 20:
            print(f"... and {len(movie_titles) - 20} more.")

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"movie_titles_justwatch_top_{len(movie_titles)}_{timestamp}.txt"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                for title in movie_titles:
                    f.write(f"{title}\n")
            print(f"\n📝 List saved to {filename}")
        except IOError as e:
            print(f"\n❌ Error saving list to file: {e}")
    else:
        print("\n😢 No movie titles were ultimately found or extracted. Check logs carefully.")


if __name__ == "__main__":
    asyncio.run(main())
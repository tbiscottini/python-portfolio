import os
import re
import time
import random
import logging
import warnings
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from dotenv import load_dotenv

import matplotlib
matplotlib.use("Agg")  # headless-safe backend, no GUI required
import matplotlib.pyplot as plt

# Mute selenium cleanup and import warnings
warnings.filterwarnings("ignore", category=ImportWarning)

# =====================================================================
# SYSTEM INITIALIZATION & PATHS
# =====================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in locals() else os.getcwd()
dotenv_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path)

# Ensure runtime directories exist
DATA_MASTER_DIR = os.path.join(BASE_DIR, "data_master")
DATA_DAILY_DIR = os.path.join(BASE_DIR, "data_daily")
CHARTS_DIR = os.path.join(DATA_DAILY_DIR, "charts")
os.makedirs(DATA_MASTER_DIR, exist_ok=True)
os.makedirs(DATA_DAILY_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

# Datastore File Paths
PREMIUM_DB = os.path.join(DATA_MASTER_DIR, "market_master_database.csv")
FLIPPING_DB = os.path.join(DATA_MASTER_DIR, "market_flipping_database.csv")
GOLD_MINE_MASTER = os.path.join(DATA_MASTER_DIR, "gold_mine_master_database.csv")
DAILY_BARGAIN_REPORT = os.path.join(DATA_DAILY_DIR, "daily_bargain_report.csv")
DAILY_GOLD_MINE_REPORT = os.path.join(DATA_DAILY_DIR, "daily_gold_mine_report.csv")

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# =====================================================================
# CONFIGURATION CONSTANTS (Safe Fallbacks)
# =====================================================================
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
RENO_COST_MQ = int(os.getenv("RENO_COST_MQ", 1000))
MIN_PROFIT_TARGET = int(os.getenv("MIN_PROFIT_TARGET", 40000))
MAX_WORKERS = 3


# =====================================================================
# WINDOWS CHROME VERSION DETECTOR
# =====================================================================
def get_local_chrome_major_version() -> int or None:
    try:
        import winreg
        paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome")
        ]
        for hkey, subkey in paths:
            try:
                with winreg.OpenKey(hkey, subkey) as key:
                    value_name = "version" if "BLBeacon" in subkey else "DisplayVersion"
                    version_str, _ = winreg.QueryValueEx(key, value_name)
                    major_version = version_str.split('.')[0]
                    if major_version.isdigit():
                        return int(major_version)
            except FileNotFoundError:
                continue
    except Exception as e:
        logging.debug(f"Registry lookup for Chrome version failed: {e}")
    return None


# =====================================================================
# TELEGRAM ENGINE (Guarded)
# =====================================================================
def send_telegram_notification(message: str) -> bool:
    if not TG_TOKEN or not TG_CHAT_ID:
        logging.warning("Telegram notification skipped: TG_TOKEN or TG_CHAT_ID not configured.")
        return False

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "false"
    }

    try:
        response = requests.post(url, data=payload, timeout=15)
        if response.status_code != 200:
            logging.error(f"Telegram API error {response.status_code}: {response.text}")
            return False
        return True
    except requests.RequestException as e:
        logging.error(f"Failed to transmit Telegram notification: {e}")
        return False


# =====================================================================
# ROBUST DATA UTILITIES
# =====================================================================
def clean_numeric_value(text: str) -> int:
    if not text: return 0
    cleaned = text.replace('.', '').replace(',', '')
    extracted_numbers = re.findall(r'\d+', cleaned)
    return int(extracted_numbers[0]) if extracted_numbers else 0


def safe_read_csv(filepath: str) -> pd.DataFrame:
    if not os.path.exists(filepath) or os.stat(filepath).st_size == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(filepath)
        df['ID'] = df['ID'].astype(str)
        return df
    except Exception as e:
        logging.error(f"Error reading {filepath}: {e}. Initializing clean database.")
        return pd.DataFrame()


# =====================================================================
# HTML PARSING COMPONENT
# =====================================================================
def parse_html_listing(article_node) -> dict or None:
    ad_id = article_node.get('data-element-id')
    if not ad_id: return None

    title_node = article_node.find('a', class_='item-link')
    price_node = article_node.find('span', class_='item-price')
    price = clean_numeric_value(price_node.text) if price_node else 0

    record = {
        'ID': str(ad_id),
        'First_Seen': datetime.now().strftime("%Y-%m-%d"),
        'Title': title_node.text.strip() if title_node else "N/A",
        'Price': price,
        'Price_MQ': 0.0, 'Rooms': 0, 'Area': 0,
        'URL': f"https://www.idealista.it/immobile/{ad_id}/",
        'GeoID': "PENDING"
    }

    price_mq_node = article_node.find('span', class_='item-price-by-area')
    if price_mq_node: record['Price_MQ'] = float(clean_numeric_value(price_mq_node.text))

    for node in article_node.find_all('span', class_='item-detail'):
        text = node.text.lower()
        if 'm²' in text:
            record['Area'] = clean_numeric_value(text)
        elif 'local' in text:
            record['Rooms'] = clean_numeric_value(text)
        elif 'bilocale' in text:
            record['Rooms'] = 2
        elif 'trilocale' in text:
            record['Rooms'] = 3
        elif 'quadrilocale' in text:
            record['Rooms'] = 4

    if record['Price_MQ'] == 0.0 and record['Area'] > 0:
        record['Price_MQ'] = round(record['Price'] / record['Area'], 2)

    return record


# =====================================================================
# THREAD-SAFE ENRICHMENT WORKER
# =====================================================================
def enrich_listing_worker(ad_data: dict, session_config: dict) -> dict:
    time.sleep(random.uniform(2.5, 4.5))
    target_url = f"https://www.idealista.it/detail/{ad_data['ID']}/datalayer?typologyId=1"

    session = requests.Session()
    for cookie in session_config.get('cookies', []):
        session.cookies.set(cookie['name'], cookie['value'])

    session.headers.update({
        'User-Agent': session_config.get('user_agent', ''),
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://www.idealista.it/',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7'
    })

    try:
        response = session.get(target_url, timeout=12)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                ad_data['GeoID'] = response.json().get('geoLocationId', 'N/A')
            else:
                ad_data['GeoID'] = "CHALLENGE_BLOCKED"
        else:
            ad_data['GeoID'] = f"ERROR_{response.status_code}"
    except Exception:
        ad_data['GeoID'] = "TIMEOUT_OR_PARSE_FAIL"

    return ad_data


def enrich_worker_helper(item, config):
    try:
        return enrich_listing_worker(item, config)
    except Exception:
        item['GeoID'] = "CRITICAL_WORKER_ERROR"
        return item


# =====================================================================
# SCRAPING ORCHESTRATOR
# =====================================================================
def execute_scraping_workflow(target_url: str, db_destination: str, pages_limit: int):
    logging.info(f"Launching scraping sequence target: {target_url}")
    driver = None
    scraped_listings = []

    try:
        options = uc.ChromeOptions()
        major_version = get_local_chrome_major_version()

        if major_version:
            logging.info(f"Detected local Google Chrome version: {major_version}")
            driver = uc.Chrome(options=options, version_main=major_version)
        else:
            driver = uc.Chrome(options=options)

        driver.get(f"{target_url}lista-1.htm")
        input("⚡ Resolve Captcha in browser view, then press ENTER in terminal...")

        for page in range(1, pages_limit + 1):
            logging.info(f"Indexing catalog page {page}...")
            driver.get(f"{target_url}lista-{page}.htm")

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            articles = soup.find_all('article', class_='item')

            if not articles: break

            for art in articles:
                parsed = parse_html_listing(art)
                if parsed: scraped_listings.append(parsed)

            time.sleep(random.uniform(4.0, 7.0))

        session_config = {
            'cookies': driver.get_cookies(),
            'user_agent': driver.execute_script("return navigator.userAgent;")
        }

        driver.quit()
        driver = None

        existing_df = safe_read_csv(db_destination)
        known_ids = set(existing_df['ID'].tolist()) if not existing_df.empty else set()
        new_listings = [item for item in scraped_listings if item['ID'] not in known_ids]

        logging.info(f"Scraped total: {len(scraped_listings)} | Unseen properties: {len(new_listings)}")
        if not new_listings: return

        enriched_results = []
        logging.info(f"Launching {MAX_WORKERS} workers for geo-enrichment...")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(enrich_worker_helper, item, session_config): item for item in new_listings}
            for index, future in enumerate(as_completed(futures), start=1):
                res = future.result()
                enriched_results.append(res)
                logging.info(
                    f"Processed: [{index}/{len(new_listings)}] ID: {res['ID']} -> GeoID Status: {res['GeoID']}")

        new_df = pd.DataFrame(enriched_results)
        final_df = pd.concat([existing_df, new_df], ignore_index=True).drop_duplicates(subset=['ID'], keep='first')
        final_df.to_csv(db_destination, index=False, encoding='utf-8-sig')
        logging.info(f"Database updated successfully: {db_destination}")

    except Exception as e:
        logging.error(f"Critical workflow crash: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


# =====================================================================
# VISUAL REPORTING ENGINE (NEW)
# =====================================================================
def generate_visual_report(analysis_df: pd.DataFrame, highlighted_df: pd.DataFrame,
                            label: str = "Arbitrage") -> list:
    """
    Builds a small set of PNG charts summarizing the day's arbitrage analysis.
    `label` describes what `highlighted_df` actually contains (e.g. "Arbitrage"
    for confirmed gold mines, "Near-Miss / Best Available" for fallback candidates)
    so chart titles never claim a deal that isn't one.
    Filenames are fixed (overwritten on every run) since this is a daily report,
    not an archive. Returns the list of file paths written.
    """
    if analysis_df is None or analysis_df.empty:
        logging.info("No analysis data available: skipping chart generation.")
        return []

    generated_files = []

    # --- Chart 1: Top opportunities ranked by potential profit ---
    try:
        ranking_source = highlighted_df if highlighted_df is not None and not highlighted_df.empty else analysis_df
        top_n = ranking_source.sort_values(by='Potential_Profit', ascending=False).head(10)
        if not top_n.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            labels = [t[:35] + ('…' if len(t) > 35 else '') for t in top_n['Title'].astype(str)]
            ax.barh(labels, top_n['Potential_Profit'], color='#2e7d32')
            ax.invert_yaxis()
            ax.set_xlabel('Potential Profit (€)')
            ax.set_title(f'Top {label} Opportunities by Estimated Profit')
            fig.tight_layout()
            path = os.path.join(CHARTS_DIR, "top_profit_ranking.png")
            fig.savefig(path, dpi=150)
            plt.close(fig)
            generated_files.append(path)
    except Exception as e:
        logging.error(f"Chart generation failed (profit ranking): {e}")

    # --- Chart 2: Price vs Area scatter, highlighting selected deals ---
    try:
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.scatter(analysis_df['Area'], analysis_df['Price'], alpha=0.4, color='#90a4ae', label='All candidates')
        if highlighted_df is not None and not highlighted_df.empty:
            ax.scatter(highlighted_df['Area'], highlighted_df['Price'], color='#d84315', s=80,
                       edgecolors='black', label=f'Selected ({label})')
        ax.set_xlabel('Area (m²)')
        ax.set_ylabel('Price (€)')
        ax.set_title('Price vs. Area — Market Overview')
        ax.legend()
        fig.tight_layout()
        path = os.path.join(CHARTS_DIR, "price_vs_area.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        generated_files.append(path)
    except Exception as e:
        logging.error(f"Chart generation failed (price vs area): {e}")

    # --- Chart 3: Distribution of price vs. comparable unrenovated listings ---
    try:
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.hist(analysis_df['Deviation_Pct'].dropna(), bins=20, color='#1565c0', edgecolor='white')
        ax.axvline(0, color='red', linestyle='--', linewidth=1, label='Median of comparable unrenovated listings')
        ax.set_xlabel('Deviation vs. Median Price/m² of Comparable Unrenovated Listings (%)')
        ax.set_ylabel('Number of Listings')
        ax.set_title('Price Positioning vs. Other To-Renovate Listings in Zone')
        ax.legend()
        fig.tight_layout()
        path = os.path.join(CHARTS_DIR, "deviation_distribution.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        generated_files.append(path)
    except Exception as e:
        logging.error(f"Chart generation failed (deviation histogram): {e}")

    if generated_files:
        logging.info(f"Generated {len(generated_files)} chart(s) in {CHARTS_DIR}")
    return generated_files


# =====================================================================
# CASE STUDY ENGINE (NEW)
# =====================================================================
def _format_case_study(rank: int, row: pd.Series) -> str:
    roi_pct = (row['Potential_Profit'] / row['Total_Investment'] * 100) if row['Total_Investment'] else 0.0
    reno_cost = row['Area'] * RENO_COST_MQ
    return (
        f"### #{rank} — {row['Title']}\n\n"
        f"- **Zone (GeoID):** {row['GeoID']} (density: {int(row.get('Zone_Density', 0))} comparable listings)\n"
        f"- **Listing price:** €{int(row['Price']):,} for {row['Area']:.0f} m² (€{row['Price_MQ']:.0f}/m²)\n"
        f"- **Median price of comparable unrenovated listings in zone:** €{row.get('Flipping_Median_MQ', 0):.0f}/m² "
        f"→ this listing sits at a **{row['Deviation_Pct']:.1f}%** deviation vs. that median "
        f"(not a discount vs. renovated value)\n"
        f"- **Zone premium (renovated) median:** €{row.get('Premium_Median_MQ', 0):.0f}/m²\n"
        f"- **Estimated renovation cost:** €{int(reno_cost):,} (€{RENO_COST_MQ}/m²)\n"
        f"- **Total investment:** €{int(row['Total_Investment']):,}\n"
        f"- **Estimated resale value:** €{int(row['Estimated_Resale_Value']):,}\n"
        f"- **Estimated net profit:** €{int(row['Potential_Profit']):,} (**{roi_pct:.1f}% ROI**)\n"
        f"- **Listing:** {row['URL']}\n"
    )


def generate_case_studies(candidates_df: pd.DataFrame, top_n: int = 3,
                           label: str = "Arbitrage") -> Optional[str]:
    """
    Builds a Markdown report describing the top N deals by potential profit.
    `label` must reflect what candidates_df actually is ("Arbitrage" for confirmed
    gold mines, "Near-Miss / Best Available" for fallback candidates) so the report
    never presents a near-miss as a confirmed deal. Filename is derived from the
    label and overwritten daily (this is a daily snapshot, not an archive).
    """
    if candidates_df is None or candidates_df.empty:
        logging.info("No candidates available: skipping case study generation.")
        return None

    top_deals = candidates_df.sort_values(by='Potential_Profit', ascending=False).head(top_n)
    if top_deals.empty:
        return None

    sections = [f"# Top {len(top_deals)} {label} Case Studies — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    for i, (_, row) in enumerate(top_deals.iterrows(), start=1):
        sections.append(_format_case_study(i, row))

    report_text = "\n".join(sections)
    slug = label.lower().replace(" ", "_").replace("/", "_")
    report_path = os.path.join(DATA_DAILY_DIR, f"case_studies_{slug}.md")
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logging.info(f"Case study report written to {report_path}")
    except OSError as e:
        logging.error(f"Failed to write case study report to {report_path}: {e}")
        return None

    logging.info("\n" + report_text)
    return report_path


# =====================================================================
# SYSTEM INTELLIGENCE & ARBITRAGE ENGINE (FIXED + ENHANCED)
# =====================================================================
def run_arbitrage_analysis():
    logging.info("Initializing Arbitrage Analysis Engine...")

    df_premium = safe_read_csv(PREMIUM_DB)
    df_flipping = safe_read_csv(FLIPPING_DB)

    if df_premium.empty or df_flipping.empty:
        logging.error("Execution halted. Source databases missing or empty.")
        return

    invalid_geoids = ['PENDING', 'TIMEOUT', 'N/A', 'TIMEOUT_OR_PARSE_FAIL', 'CHALLENGE_BLOCKED',
                      'CRITICAL_WORKER_ERROR']

    df_premium_cleaned = df_premium[
        (df_premium['Price_MQ'] > 0) &
        (df_premium['GeoID'].notna()) &
        (~df_premium['GeoID'].isin(invalid_geoids)) &
        (~df_premium['GeoID'].str.startswith('ERROR', na=True))
        ].copy()

    df_flipping_cleaned = df_flipping[
        (df_flipping['Price_MQ'] > 0) &
        (df_flipping['GeoID'].notna()) &
        (~df_flipping['GeoID'].isin(invalid_geoids)) &
        (~df_flipping['GeoID'].str.startswith('ERROR', na=True))
        ].copy()

    premium_medians = df_premium_cleaned.groupby('GeoID')['Price_MQ'].median().reset_index()
    premium_medians.columns = ['GeoID', 'Premium_Median_MQ']

    flipping_medians = df_flipping_cleaned.groupby('GeoID')['Price_MQ'].agg(['median', 'count']).reset_index()
    flipping_medians.columns = ['GeoID', 'Flipping_Median_MQ', 'Zone_Density']

    already_processed_gold = safe_read_csv(GOLD_MINE_MASTER)
    evaluated_ids = set(already_processed_gold['ID'].tolist()) if not already_processed_gold.empty else set()
    unevaluated_flipping = df_flipping_cleaned[~df_flipping_cleaned['ID'].isin(evaluated_ids)].copy()

    if unevaluated_flipping.empty:
        logging.info("Zero unevaluated flipping records found. Arbitrage step skipped.")
        return

    analysis = pd.merge(unevaluated_flipping, premium_medians, on='GeoID', how='inner')
    analysis = pd.merge(analysis, flipping_medians, on='GeoID', how='left')

    if analysis.empty: return

    analysis['Estimated_Resale_Value'] = analysis['Premium_Median_MQ'] * analysis['Area']
    analysis['Total_Investment'] = analysis['Price'] + (analysis['Area'] * RENO_COST_MQ)
    analysis['Potential_Profit'] = analysis['Estimated_Resale_Value'] - analysis['Total_Investment']

    def calculate_deviation(row):
        base_median = row.get('Flipping_Median_MQ', 0.0)
        price_mq = row.get('Price_MQ', 0.0)
        if pd.isna(base_median) or pd.isna(price_mq) or base_median <= 0.0: return 0.0
        return round(((price_mq - base_median) / base_median) * 100, 2)

    analysis['Deviation_Pct'] = analysis.apply(calculate_deviation, axis=1)

    # --- THE SANITY CHECKS (Il "Freno a Mano" per investitori) ---
    MAX_REALISTIC_PREMIUM_MQ = 12000  # Oltre è falso o ultra-lusso ingestibile
    MAX_FLIPPING_DEVIATION = 0  # Tolleranza Zero: massimo si compra a prezzo di media, non oltre

    gold_mines = analysis[
        (analysis['Potential_Profit'] >= MIN_PROFIT_TARGET) &
        (analysis['Zone_Density'] >= 2) &
        (analysis['Area'] >= 40) &
        (analysis['Premium_Median_MQ'] <= MAX_REALISTIC_PREMIUM_MQ) &
        (analysis['Deviation_Pct'] <= MAX_FLIPPING_DEVIATION)
        ].copy()

    logging.info(f"Analyzed {len(analysis)} candidates | Identified {len(gold_mines)} TRUE arbitrage targets.")

    if not gold_mines.empty:
        gold_mines.to_csv(DAILY_GOLD_MINE_REPORT, index=False, encoding='utf-8-sig')
        updated_gold_master = pd.concat([already_processed_gold, gold_mines], ignore_index=True).drop_duplicates(
            subset=['ID'], keep='first')
        updated_gold_master.to_csv(GOLD_MINE_MASTER, index=False, encoding='utf-8-sig')

        for _, row in gold_mines.iterrows():
            title_lower = str(row['Title']).lower()
            if any(term in title_lower for term in ["nuda proprietà", "usufrutto", "box", "garage", "asta"]):
                continue

            alert_message = (
                f"💰 **GOLD MINE ARBITRAGE DETECTED** 💰\n\n"
                f"📍 **Property:** {row['Title']}\n"
                f"💶 **Acquisition Cost:** €{int(row['Price']):,}\n"
                f"🛠️ **Est. Reno Expenses:** €{int(row['Area'] * RENO_COST_MQ):,}\n"
                f"🚀 **Target Resale Value:** €{int(row['Estimated_Resale_Value']):,}\n"
                f"---------------------------\n"
                f"📈 **ESTIMATED PROFIT MARGIN: €{int(row['Potential_Profit']):,}**\n"
                f"---------------------------\n"
                f"📉 **Purchase Discount:** `{row['Deviation_Pct']}%` vs local ruins\n"
                f"📊 GeoID: `{row['GeoID']}` (supported by {int(row['Zone_Density'])} area units)\n\n"
                f"🔗 [View Listing]({row['URL']})"
            )
            send_telegram_notification(alert_message)
            time.sleep(2.0)

        logging.info("Arbitrage calculations completed, warnings dispatched.")

        # NEW: charts + case studies for the confirmed gold mines
        generate_visual_report(analysis, gold_mines, label="Arbitrage")
        generate_case_studies(gold_mines, top_n=3, label="Arbitrage")

    else:
        logging.info("No TRUE arbitrage conditions met today. Analyzing 'Near Misses' (Quasi-Affari)...")

        # Near Misses: Le 3 migliori opzioni scartate per Deviation_Pct ma con dati solidi
        near_misses = analysis[
            (analysis['Zone_Density'] >= 2) &
            (analysis['Area'] >= 40) &
            (analysis['Premium_Median_MQ'] <= MAX_REALISTIC_PREMIUM_MQ)
            ].sort_values(by='Potential_Profit', ascending=False).head(3)

        if not near_misses.empty:
            logging.info("LE 3 MIGLIORI ALTERNATIVE SUL MERCATO OGGI (Near Misses):")
            for i, row in near_misses.iterrows():
                logging.info(f"🔹 {row['Title']}")
                logging.info(
                    f"   💶 Prezzo: €{int(row['Price']):,} | 📈 Profitto Stima: €{int(row['Potential_Profit']):,}")
                logging.info(
                    f"   📉 Sconto vs Ruderi: {row['Deviation_Pct']}% (Sopra lo 0 significa che l'immobile è caro per essere da ristrutturare)")
                logging.info(f"   🔗 {row['URL']}")

            # NEW: charts + case studies for the best near misses found (never mislabeled as "arbitrage")
            generate_visual_report(analysis, near_misses, label="Near-Miss / Best Available")
            generate_case_studies(near_misses, top_n=3, label="Near-Miss / Best Available")
        else:
            logging.info("Nessun dato sufficiente per analizzare i Near Misses oggi.")


# =====================================================================
# EXECUTION ROUTER
# =====================================================================
if __name__ == "__main__":
    import sys

    execution_command = None

    if len(sys.argv) < 2:
        print("\n=== Real Estate Intelligence Suite ===")
        print("1. Run daily flipping scans (48h listings)")
        print("2. Run baseline premium listings scans")
        print("3. Run financial margin comparison analysis")
        print("4. Exit")

        try:
            choice = input("\nSelect an option (1-4): ").strip()
            if choice == "1":
                execution_command = "scrape_flipping"
            elif choice == "2":
                execution_command = "scrape_premium"
            elif choice == "3":
                execution_command = "run_arbitrage"
            else:
                sys.exit(0)
        except KeyboardInterrupt:
            sys.exit(0)
    else:
        execution_command = sys.argv[1].strip().lower()

    if execution_command == "scrape_flipping":
        flipping_url = "https://www.idealista.it/geo/vendita-case/toscana/con-pubblicato_ultime-48-ore,ristrutturare,aste_no,senza-inquilini/"
        execute_scraping_workflow(target_url=flipping_url, db_destination=FLIPPING_DB, pages_limit=3)

    elif execution_command == "scrape_premium":
        premium_url = "https://www.idealista.it/geo/vendita-case/toscana/con-pubblicato_ultime-48-ore,aste_no,senza-inquilini,alta-efficienza/"
        execute_scraping_workflow(target_url=premium_url, db_destination=PREMIUM_DB, pages_limit=2)

    elif execution_command == "run_arbitrage":
        run_arbitrage_analysis()

    else:
        print(f"Unknown command: '{execution_command}'")
        sys.exit(1)

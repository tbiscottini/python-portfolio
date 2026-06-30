
# 🏡 PropTech Intelligence: Real Estate Arbitrage Engine (V2)

## 🎯 The Mission

In a fragmented real estate market like Tuscany, identifying true investment opportunities requires crossing multiple data streams. This project evolved from a simple anomaly detector into a full **End-to-End Arbitrage Engine**. It identifies undervalued properties to be renovated ("Flipping"), calculates the estimated renovation costs (CAPEX), and crosses the data with the Hyper-Local Premium Market to calculate the net Potential ROI.

## 🏗️ The Architecture

1. **Extraction (Undetected Chromedriver):** Bypasses bot-protections to scrape live real estate data, segregating the market into two distinct Data Marts: Flipping (Ruins) vs Premium (Class A/B).

2. **Geo-Enrichment:** Uses thread-pools (Concurrency) to interrogate internal APIs and extract the exact GeoID micro-zone for each property.

3. **Financial Engine (Pandas):**

- Establishes a localized Fair Market Value.

- Applies strict Sanity Checks (e.g., filtering out "Nuda Proprietà" or pricing glitches).

- Calculates the **Equity Gap** (Potential Profit) factoring in standard renovation costs per square meter.

4. **Delivery:** Dispatches real-time alerts for "Gold Mines" (Profit > €40k) directly to a secure Telegram Bot.

## 📊 Market Discovery: The "Oltrarno" Case Study

The algorithm successfully identified an independent property in Florence (Oltrarno) priced at €3,065/sqm. By crossing this with the local Premium Median of €9,631/sqm, the model validated a massive potential equity gap, proving the existence of structural market inefficiencies.

![Profit Heatmap](profit_heatmap.png)

*Figure 1: Geospatial Heatmap identifying the concentration of highest Potential Profit across Tuscany.*

## 🛠️ Tech Stack

- **Language:** Python

- **Data Engineering:** Pandas, SQLite (Database Migration), ETL Pipelines

- **Automation & Scraping:** Undetected Chromedriver, Asyncio/Threading, Regex

- **Security & Ops:** Environment Variables (.env), Robust Error Handling (Fault Tolerance)

- **Geospatial Analytics:** Plotly

 

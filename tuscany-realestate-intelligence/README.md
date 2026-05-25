# 🏡 PropTech Intelligence: ESG Real Estate Anomaly Detector

## 🎯 The Mission
In a fragmented real estate market like Tuscany, identifying undervalued "Green" (Class A/B) properties is traditionally a manual, high-error process. This project automates the discovery of **ESG Arbitrage** opportunities.

## 🏗️ The Architecture
1. **Extraction:** A custom-built scraper (`scraper.py`) harvests high-efficiency residential data, bypassing market noise and non-relevant listings (auctions, ruins).
2. **Standardization:** Features are engineered to cohort properties by City, Sub-zone, and Room Count.
3. **Statistical Modeling:** Implemented a **Modified Z-Score** pipeline using **Median Absolute Deviation (MAD)** to detect pricing anomalies while remaining resilient to luxury-market outliers.
4. **Insight Generation:** Calculates the **Equity Gap** (Total Euro undervaluation) to prioritize leads for investors.

## 📈 Key Discovery
The model successfully identified a **45.2% pricing anomaly** in the Camaiore sub-market, revealing an Energy Class A3 property priced significantly below the peer-group median—a **€239,000 untapped equity gap.**

## 🛠️ Tech Stack
* **Language:** Python
* **Library:** Pandas (Data Wrangling), Numpy (Vectorized Math), Seaborn/Matplotlib (Statistical Visualization)
* **Stats:** Robust Outlier Detection (MAD), Cohort Analysis.

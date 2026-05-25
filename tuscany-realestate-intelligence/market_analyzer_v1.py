import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt


class EstateAnalyzer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = None

    def load_and_clean(self):
        self.df = pd.read_csv(self.file_path, dtype={'ID': str})
        self.df.rename(columns={'Mq': 'MQ', 'Localita': 'City', 'Titolo': 'Title',
                                'Prezzo': 'Price', 'Prezzo_Mq': 'Price_MQ'}, inplace=True)

        def get_subzone(title, city):
            parts = [p.strip() for p in title.split(',')]
            return parts[-2] if len(parts) >= 3 else city

        self.df['SubZone'] = self.df.apply(lambda x: get_subzone(x['Title'], x['City']), axis=1)
        # Filters: High-efficiency range (30-400mq) and non-auction prices
        self.df = self.df[(self.df['MQ'].between(30, 400)) & (self.df['Price'] > 30000)].copy()
        return self

    def analyze(self, min_sample=3):
        group_cols = ['City', 'SubZone', 'Locali']
        stats = self.df.groupby(group_cols)['Price_MQ'].agg(
            ['median', lambda x: (x - x.median()).abs().median(), 'count']).reset_index()
        stats.columns = group_cols + ['Median_MQ', 'MAD_MQ', 'Cohort_Size']

        self.df = self.df.merge(stats[stats['Cohort_Size'] >= min_sample], on=group_cols)
        self.df['Dynamic_MAD'] = np.maximum(self.df['MAD_MQ'], self.df['Median_MQ'] * 0.15)
        self.df['Mod_Z'] = 0.6745 * (self.df['Price_MQ'] - self.df['Median_MQ']) / self.df['Dynamic_MAD']
        self.df['Discount_Pct'] = (1 - (self.df['Price_MQ'] / self.df['Median_MQ'])) * 100
        self.df['Equity_Gap'] = (self.df['Median_MQ'] - self.df['Price_MQ']) * self.df['MQ']

        def grade_lead(row):
            if row['Mod_Z'] < -1.5 and row['Cohort_Size'] >= 5: return 'A (Institutional)'
            if row['Mod_Z'] < -1.0: return 'B (Speculative)'
            return 'C'

        self.df['Lead_Grade'] = self.df.apply(grade_lead, axis=1)
        return self


def create_deal_visualization(full_data, deals):
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(12, 8))

    best_deal = deals.iloc[0]

    # Get Top 4 cities by volume + the City of the best deal
    other_cities = full_data[full_data['City'] != best_deal['City']]['City'].value_counts().nlargest(4).index
    target_cities = [best_deal['City']] + list(other_cities)

    plot_data = full_data[full_data['City'].isin(target_cities)].copy()

    # Sort target cities so the best deal city is always the first bar
    ax = sns.boxplot(data=plot_data, x='City', y='Price_MQ', order=target_cities,
                     palette="Blues", showfliers=False, width=0.6)

    # Plot the "Golden Star"
    plt.scatter(x=0, y=best_deal['Price_MQ'], color='gold', edgecolor='black',
                s=400, marker='*', label=f"Grade A Lead: {best_deal['SubZone']}", zorder=5)

    # Professional Annotation
    plt.annotate(
        f"DEAL IDENTIFIED!\n{best_deal['Discount_Pct']:.1f}% Below Median\n€{best_deal['Equity_Gap']:,.0f} Equity Gap",
        xy=(0, best_deal['Price_MQ']),
        xytext=(0.5, best_deal['Price_MQ'] + 1000),
        bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="gold", alpha=0.9),
        arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=.2", color='black'),
        fontsize=11, fontweight='bold'
    )

    plt.title(f"Market intelligence: ESG Real Estate Anomaly Detection", fontsize=16, fontweight='bold', pad=25)
    plt.ylabel("Price per Square Meter (€/mq)", fontsize=12)
    plt.xlabel("Key Tuscan Investment Zones", fontsize=12)
    plt.legend(loc='upper right')
    plt.tight_layout()
    plt.savefig("market_intelligence_report.png", dpi=300)
    plt.show()


# --- EXECUTION FLOW ---
if __name__ == "__main__":
    DATA_PATH = r"C:\Users\Tom\Downloads\archive (1)\dati_idealista_toscana.csv"

    # 1. Initialize and Process
    analyzer = EstateAnalyzer(DATA_PATH)
    processed_data = analyzer.load_and_clean().analyze(min_sample=3)

    # 2. Extract Top Leads
    # We remove cases where SubZone == City to ensure high-quality neighborhood data
    report = processed_data.df[(processed_data.df['Lead_Grade'] != 'C') &
                               (processed_data.df['SubZone'] != processed_data.df['City'])].sort_values(
        ['Lead_Grade', 'Equity_Gap'], ascending=[True, False])

    if not report.empty:
        print(f"✅ Success: Found {len(report)} qualified leads.")
        # 3. Visualize
        create_deal_visualization(processed_data.df, report)
    else:
        print("❌ No leads found matching the quality criteria.")
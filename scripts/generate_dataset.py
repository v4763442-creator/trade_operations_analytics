"""
Realistic Financial Trade Operations Dataset Generator
Project: Trade Operations Intelligence & Exception Monitoring Platform

Simulates institutional trade lifecycles across G10 FX, Sovereign/Corporate Debt,
Cash Equities, and Interest Rate Swaps. Generates:
- trades.csv (exactly 50,000 rows)
- settlements.csv (~50,000 - 75,000 rows)
- exceptions.csv (~4,000 - 6,000 rows)
- counterparties.csv (150 rows)
- instruments.csv (160 rows)
- known_data_quality_issues.csv (documented seeded anomalies)
- data_dictionary.csv (complete metadata documentation)
"""

import os
import random
import datetime
import numpy as np
import pandas as pd

# Set fixed random seed for strict reproducibility
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
os.makedirs(DATA_RAW_DIR, exist_ok=True)

# ---------------------------------------------------------
# 1. Calendars and Business Days Definition (Year 2025)
# ---------------------------------------------------------
# Major Institutional Market Holidays in 2025 (US/UK/TARGET2 intersection)
HOLIDAYS_2025 = {
    datetime.date(2025, 1, 1): "New Year's Day",
    datetime.date(2025, 1, 20): "Martin Luther King Jr. Day",
    datetime.date(2025, 2, 17): "Presidents' Day / Washington's Birthday",
    datetime.date(2025, 4, 18): "Good Friday",
    datetime.date(2025, 4, 21): "Easter Monday",
    datetime.date(2025, 5, 26): "Memorial Day / UK Spring Bank Holiday",
    datetime.date(2025, 6, 19): "Juneteenth National Independence Day",
    datetime.date(2025, 7, 4): "US Independence Day",
    datetime.date(2025, 9, 1): "US Labor Day",
    datetime.date(2025, 11, 27): "US Thanksgiving Day",
    datetime.date(2025, 12, 25): "Christmas Day",
    datetime.date(2025, 12, 26): "Boxing Day",
    # 2026 holidays for forward settlement calculations
    datetime.date(2026, 1, 1): "New Year's Day 2026",
    datetime.date(2026, 1, 19): "MLK Day 2026",
}

def is_business_day(d: datetime.date) -> bool:
    """Returns True if date is Monday-Friday and not a major market holiday."""
    if d.weekday() >= 5:  # Saturday or Sunday
        return False
    if d in HOLIDAYS_2025:
        return False
    return True

def add_business_days(start_date: datetime.date, n_days: int) -> datetime.date:
    """Adds N business days skipping weekends and major market holidays."""
    cur = start_date
    added = 0
    while added < n_days:
        cur += datetime.timedelta(days=1)
        if is_business_day(cur):
            added += 1
    return cur

# Generate list of all business dates in 2025
ALL_DATES_2025 = [
    datetime.date(2025, 1, 1) + datetime.timedelta(days=i)
    for i in range(365)
]
BUSINESS_DATES_2025 = [d for d in ALL_DATES_2025 if is_business_day(d)]

# Compute realistic trading activity weights across the year
# Quarter-ends, month-ends, and mid-week have higher volume
def compute_date_weights(dates):
    weights = []
    for d in dates:
        base = 1.0
        # Day of week weight (Tue/Wed/Thu slightly higher than Mon/Fri)
        if d.weekday() in (1, 2, 3):
            base *= 1.15
        elif d.weekday() == 4:  # Friday
            base *= 0.95

        # Quarter-end surges (March, June, September, December final week)
        if d.month in (3, 6, 9, 12) and d.day >= 24:
            base *= 1.85
        # Month-end surges
        elif d.day >= 27:
            base *= 1.35
        # Summer lull in August
        if d.month == 8:
            base *= 0.82

        # Operational disruption windows (used later for incident modeling)
        # Disruption Window 1: May 27-29 (Post-Memorial Day system migration)
        # Disruption Window 2: Oct 14-16 (Depository messaging queue latency)
        weights.append(base)
    
    weights = np.array(weights)
    return weights / weights.sum()

DATE_WEIGHTS = compute_date_weights(BUSINESS_DATES_2025)

print(f"Total business days in 2025: {len(BUSINESS_DATES_2025)}")

# ---------------------------------------------------------
# 2. Reference Tables: Counterparties and Instruments
# ---------------------------------------------------------
def generate_counterparties() -> pd.DataFrame:
    """Generates 150 realistic institutional counterparties with Pareto volume skew."""
    types = [
        ("INVESTMENT_BANK", 0.22),
        ("ASSET_MANAGER", 0.32),
        ("HEDGE_FUND", 0.20),
        ("PENSION_FUND", 0.12),
        ("CORPORATE_TREASURY", 0.08),
        ("SOVEREIGN_WEALTH_FUND", 0.06),
    ]
    regions_countries = {
        "AMER": [("US", 0.70), ("CA", 0.15), ("BR", 0.10), ("MX", 0.05)],
        "EMEA": [("GB", 0.40), ("DE", 0.25), ("FR", 0.15), ("CH", 0.10), ("NL", 0.10)],
        "APAC": [("JP", 0.35), ("SG", 0.25), ("HK", 0.20), ("AU", 0.20)],
    }
    
    # Realistic institution prefix/suffix pools
    prefixes = [
        "Apex", "Meridian", "Vanguard", "Crestview", "Sterling", "Pacific", "Beacon", "Harborview",
        "Pinnacle", "Highland", "Sigma", "BlueWater", "Citadel", "PointCross", "Northern Pines",
        "Global Reserve", "Horizon", "Blackstone", "Wellington", "Barclays", "Bridgewater", "Lazard",
        "Franklin", "Nomura", "Macquarie", "Temasek", "GIC", "Norges", "Sumitomo", "Rothschild",
        "Alliance", "Oaktree", "Morgan", "Apollo", "Millennium", "Renaissance", "Two Sigma", "AQR"
    ]
    suffixes = [
        "Capital Management", "Global Investors", "Securities Corp", "Trust International", "Asset Advisors",
        "Investment Banking", "Partners", "Financial Group", "Trading LLC", "Global Macro Fund",
        "Retirement Board", "Treasury Services", "Holdings Ltd", "Clearing Corp", "Credit Fund"
    ]
    
    records = []
    c_type_choices = [t[0] for t in types]
    c_type_probs = [t[1] for t in types]
    
    counterparty_names_used = set()
    
    for i in range(1, 151):
        cp_id = f"CP-{i:03d}"
        
        # Name generation
        p = prefixes[(i - 1) % len(prefixes)]
        s = suffixes[(i * 7) % len(suffixes)]
        name = f"{p} {s}"
        if name in counterparty_names_used:
            name = f"{p} {s} ({i})"
        counterparty_names_used.add(name)
        
        cp_type = np.random.choice(c_type_choices, p=c_type_probs)
        
        # Region & Country
        region = np.random.choice(["AMER", "EMEA", "APAC"], p=[0.50, 0.32, 0.18])
        countries, c_probs = zip(*regions_countries[region])
        home_country = np.random.choice(countries, p=c_probs)
        
        # Risk rating: ordinal scale LOW, MEDIUM, HIGH, VERY_HIGH
        # Higher risk for smaller hedge funds / speculative entities
        if cp_type == "HEDGE_FUND":
            risk_rating = np.random.choice(["LOW", "MEDIUM", "HIGH", "VERY_HIGH"], p=[0.20, 0.40, 0.30, 0.10])
        elif cp_type in ("INVESTMENT_BANK", "PENSION_FUND", "SOVEREIGN_WEALTH_FUND"):
            risk_rating = np.random.choice(["LOW", "MEDIUM", "HIGH", "VERY_HIGH"], p=[0.70, 0.25, 0.04, 0.01])
        else:
            risk_rating = np.random.choice(["LOW", "MEDIUM", "HIGH", "VERY_HIGH"], p=[0.50, 0.35, 0.12, 0.03])
            
        # Onboarding status
        onboarding_status = np.random.choice(
            ["ACTIVE", "PROBATION", "RESTRICTED", "PENDING_REVIEW"],
            p=[0.92, 0.04, 0.02, 0.02]
        )
        
        # Settlement instruction status (SSI status)
        # Counterparties with EXPIRED or INCOMPLETE SSIs drive settlement failures
        if risk_rating in ("HIGH", "VERY_HIGH"):
            ssi_status = np.random.choice(
                ["VERIFIED", "EXPIRED", "PENDING_AMENDMENT", "INCOMPLETE"],
                p=[0.60, 0.18, 0.12, 0.10]
            )
        else:
            ssi_status = np.random.choice(
                ["VERIFIED", "EXPIRED", "PENDING_AMENDMENT", "INCOMPLETE"],
                p=[0.92, 0.04, 0.03, 0.01]
            )
            
        active_flag = True if onboarding_status in ("ACTIVE", "PROBATION") else False
        
        records.append({
            "counterparty_id": cp_id,
            "counterparty_name": name,
            "counterparty_type": cp_type,
            "home_country": home_country,
            "operating_region": region,
            "risk_rating": risk_rating,
            "onboarding_status": onboarding_status,
            "settlement_instruction_status": ssi_status,
            "active_flag": active_flag
        })
        
    df_cp = pd.DataFrame(records)
    return df_cp

def generate_instruments() -> pd.DataFrame:
    """Generates 160 realistic financial instruments across 6 product types."""
    instruments = []
    
    # 1. FX_SPOT (20 currency pairs)
    fx_pairs = [
        ("EURUSD", "EUR/USD Spot Foreign Exchange", "FOREIGN_EXCHANGE", "EUR", "USD", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("USDJPY", "USD/JPY Spot Foreign Exchange", "FOREIGN_EXCHANGE", "USD", "JPY", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("GBPUSD", "GBP/USD Spot Foreign Exchange", "FOREIGN_EXCHANGE", "GBP", "USD", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("USDCHF", "USD/CHF Spot Foreign Exchange", "FOREIGN_EXCHANGE", "USD", "CHF", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("AUDUSD", "AUD/USD Spot Foreign Exchange", "FOREIGN_EXCHANGE", "AUD", "USD", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("USDCAD", "USD/CAD Spot Foreign Exchange", "FOREIGN_EXCHANGE", "USD", "CAD", "USD", "GLOBAL", 1, "GLOBAL_FX"), # T+1 convention
        ("NZDUSD", "NZD/USD Spot Foreign Exchange", "FOREIGN_EXCHANGE", "NZD", "USD", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("EURGBP", "EUR/GBP Cross Foreign Exchange", "FOREIGN_EXCHANGE", "EUR", "GBP", "EUR", "GLOBAL", 2, "GLOBAL_FX"),
        ("EURJPY", "EUR/JPY Cross Foreign Exchange", "FOREIGN_EXCHANGE", "EUR", "JPY", "EUR", "GLOBAL", 2, "GLOBAL_FX"),
        ("GBPJPY", "GBP/JPY Cross Foreign Exchange", "FOREIGN_EXCHANGE", "GBP", "JPY", "GBP", "GLOBAL", 2, "GLOBAL_FX"),
        ("USDCNH", "USD/CNH Offshore Chinese Yuan Spot", "FOREIGN_EXCHANGE", "USD", "CNH", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("USDSGD", "USD/SGD Singapore Dollar Spot", "FOREIGN_EXCHANGE", "USD", "SGD", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("USDHKD", "USD/HKD Hong Kong Dollar Spot", "FOREIGN_EXCHANGE", "USD", "HKD", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("USDKRW", "USD/KRW Korean Won Spot", "FOREIGN_EXCHANGE", "USD", "KRW", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("USDMXN", "USD/MXN Mexican Peso Spot", "FOREIGN_EXCHANGE", "USD", "MXN", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("USDBRL", "USD/BRL Brazilian Real Spot", "FOREIGN_EXCHANGE", "USD", "BRL", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("USDINR", "USD/INR Indian Rupee Spot", "FOREIGN_EXCHANGE", "USD", "INR", "USD", "GLOBAL", 2, "GLOBAL_FX"),
        ("EURCHF", "EUR/CHF Swiss Franc Cross", "FOREIGN_EXCHANGE", "EUR", "CHF", "EUR", "GLOBAL", 2, "GLOBAL_FX"),
        ("AUDJPY", "AUD/JPY Australian Dollar / Yen Cross", "FOREIGN_EXCHANGE", "AUD", "JPY", "AUD", "GLOBAL", 2, "GLOBAL_FX"),
        ("CADJPY", "CAD/JPY Canadian Dollar / Yen Cross", "FOREIGN_EXCHANGE", "CAD", "JPY", "CAD", "GLOBAL", 2, "GLOBAL_FX"),
    ]
    for p in fx_pairs:
        instruments.append({
            "instrument_id": f"INST-FX-{p[0]}",
            "instrument_type": "FX_SPOT_PAIR",
            "instrument_name": p[1],
            "asset_class": p[2],
            "base_currency": p[3],
            "quote_currency": p[4],
            "settlement_currency": p[5],
            "market_or_region": p[6],
            "standard_settlement_lag_business_days": p[7],
            "market_calendar": p[8],
            "active_flag": True
        })
        
    # 2. FX_FORWARD (30 contracts across major pairs with tenors)
    fwd_tenors = [("1M", 22), ("2M", 44), ("3M", 66), ("6M", 132), ("1Y", 260)]
    fwd_pairs = ["EURUSD", "USDJPY", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD"]
    for pr in fwd_pairs:
        for tenor, lag in fwd_tenors:
            instruments.append({
                "instrument_id": f"INST-FWD-{pr}-{tenor}",
                "instrument_type": "FX_FORWARD_CONTRACT",
                "instrument_name": f"{pr} Forward {tenor} Outright",
                "asset_class": "FOREIGN_EXCHANGE",
                "base_currency": pr[:3],
                "quote_currency": pr[3:],
                "settlement_currency": "USD",
                "market_or_region": "GLOBAL",
                "standard_settlement_lag_business_days": lag,
                "market_calendar": "GLOBAL_FX",
                "active_flag": True
            })
            
    # 3. GOVERNMENT_BOND (30 sovereign bonds: US Treasuries, UK Gilts, Bunds, JGBs)
    sovereigns = [
        # US Treasuries (T+1 lag per standard institutional rules)
        ("UST-2Y-2027", "US Treasury Note 4.250% due 2027", "FIXED_INCOME", "USD", None, "USD", "US", 1, "FED_US"),
        ("UST-3Y-2028", "US Treasury Note 4.125% due 2028", "FIXED_INCOME", "USD", None, "USD", "US", 1, "FED_US"),
        ("UST-5Y-2030", "US Treasury Note 4.000% due 2030", "FIXED_INCOME", "USD", None, "USD", "US", 1, "FED_US"),
        ("UST-7Y-2032", "US Treasury Note 4.375% due 2032", "FIXED_INCOME", "USD", None, "USD", "US", 1, "FED_US"),
        ("UST-10Y-2035", "US Treasury Benchmark Note 4.250% due 2035", "FIXED_INCOME", "USD", None, "USD", "US", 1, "FED_US"),
        ("UST-20Y-2045", "US Treasury Bond 4.625% due 2045", "FIXED_INCOME", "USD", None, "USD", "US", 1, "FED_US"),
        ("UST-30Y-2055", "US Treasury Long Bond 4.500% due 2055", "FIXED_INCOME", "USD", None, "USD", "US", 1, "FED_US"),
        ("UST-TIPS-10Y", "US Treasury TIPS 1.875% due 2035", "FIXED_INCOME", "USD", None, "USD", "US", 1, "FED_US"),
        ("UST-TIPS-5Y", "US Treasury TIPS 1.625% due 2030", "FIXED_INCOME", "USD", None, "USD", "US", 1, "FED_US"),
        ("UST-T-BILL-6M", "US Treasury Bill 6-Month Discount", "FIXED_INCOME", "USD", None, "USD", "US", 1, "FED_US"),
        # UK Gilts (T+1)
        ("UK-GILT-2Y", "UK Treasury Gilt 4.000% 2027", "FIXED_INCOME", "GBP", None, "GBP", "UK", 1, "UK_BANK_HOLIDAY"),
        ("UK-GILT-5Y", "UK Treasury Gilt 4.250% 2030", "FIXED_INCOME", "GBP", None, "GBP", "UK", 1, "UK_BANK_HOLIDAY"),
        ("UK-GILT-10Y", "UK Treasury Gilt 4.500% 2035", "FIXED_INCOME", "GBP", None, "GBP", "UK", 1, "UK_BANK_HOLIDAY"),
        ("UK-GILT-30Y", "UK Treasury Gilt 4.125% 2055", "FIXED_INCOME", "GBP", None, "GBP", "UK", 1, "UK_BANK_HOLIDAY"),
        # German Bunds / OBL (T+2 European market convention)
        ("GER-BUND-2Y", "German Federal Treasury Note (Schatz) 2.50% 2027", "FIXED_INCOME", "EUR", None, "EUR", "EU", 2, "TARGET2"),
        ("GER-BUND-5Y", "German Federal Obligation (Bobl) 2.60% 2030", "FIXED_INCOME", "EUR", None, "EUR", "EU", 2, "TARGET2"),
        ("GER-BUND-10Y", "German Federal Bond (Bund) 2.75% 2035", "FIXED_INCOME", "EUR", None, "EUR", "EU", 2, "TARGET2"),
        ("GER-BUND-30Y", "German Federal Bond (Bund) 3.00% 2055", "FIXED_INCOME", "EUR", None, "EUR", "EU", 2, "TARGET2"),
        # French OAT
        ("FR-OAT-5Y", "French Government OAT 2.80% 2030", "FIXED_INCOME", "EUR", None, "EUR", "EU", 2, "TARGET2"),
        ("FR-OAT-10Y", "French Government Benchmark OAT 3.10% 2035", "FIXED_INCOME", "EUR", None, "EUR", "EU", 2, "TARGET2"),
        ("FR-OAT-30Y", "French Government Long OAT 3.50% 2055", "FIXED_INCOME", "EUR", None, "EUR", "EU", 2, "TARGET2"),
        # Japanese JGBs (T+1 / T+2)
        ("JP-JGB-5Y", "Japan Government Bond 0.65% 5Y", "FIXED_INCOME", "JPY", None, "JPY", "JP", 1, "TOKYO_BOJ"),
        ("JP-JGB-10Y", "Japan Government Benchmark Bond 1.05% 10Y", "FIXED_INCOME", "JPY", None, "JPY", "JP", 1, "TOKYO_BOJ"),
        ("JP-JGB-30Y", "Japan Government Super-Long Bond 2.10% 30Y", "FIXED_INCOME", "JPY", None, "JPY", "JP", 1, "TOKYO_BOJ"),
        # Other Sovereigns
        ("AU-ACGB-10Y", "Australian Government Bond 4.25% 2035", "FIXED_INCOME", "AUD", None, "AUD", "APAC", 1, "AU_BANK_HOLIDAY"),
        ("CA-CANGB-10Y", "Government of Canada Benchmark Bond 3.50% 2035", "FIXED_INCOME", "CAD", None, "CAD", "AMER", 1, "FED_US"),
        ("CH-CONF-10Y", "Swiss Confederation Bond 1.25% 2035", "FIXED_INCOME", "CHF", None, "CHF", "EU", 2, "TARGET2"),
        ("IT-BTP-10Y", "Italian Government BTP 3.85% 2035", "FIXED_INCOME", "EUR", None, "EUR", "EU", 2, "TARGET2"),
        ("ES-BONO-10Y", "Kingdom of Spain Bono 3.45% 2035", "FIXED_INCOME", "EUR", None, "EUR", "EU", 2, "TARGET2"),
        ("NL-DSL-10Y", "Netherlands Government Bond (DSL) 2.90% 2035", "FIXED_INCOME", "EUR", None, "EUR", "EU", 2, "TARGET2"),
    ]
    for s in sovereigns:
        instruments.append({
            "instrument_id": f"INST-SOV-{s[0]}",
            "instrument_type": "GOVERNMENT_BOND",
            "instrument_name": s[1],
            "asset_class": s[2],
            "base_currency": s[3],
            "quote_currency": s[4],
            "settlement_currency": s[5],
            "market_or_region": s[6],
            "standard_settlement_lag_business_days": s[7],
            "market_calendar": s[8],
            "active_flag": True
        })
        
    # 4. CORPORATE_BOND (35 corporate bonds: US/EU Investment Grade and High Yield)
    corps = [
        ("AAPL-2030", "Apple Inc 3.85% Senior Notes 2030", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("MSFT-2032", "Microsoft Corp 4.00% Senior Notes 2032", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("JPM-2034", "JPMorgan Chase & Co 4.85% Subordinated 2034", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("PFE-2029", "Pfizer Inc 3.60% Senior Notes 2029", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("XOM-2035", "Exxon Mobil Corp 4.25% Debentures 2035", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("AMZN-2031", "Amazon.com Inc 4.10% Notes 2031", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("GOOGL-2033", "Alphabet Inc 3.95% Notes 2033", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("BAC-2032", "Bank of America Corp 4.75% Floating/Fixed 2032", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("GS-2033", "Goldman Sachs Group 5.15% Notes 2033", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("CSCO-2028", "Cisco Systems 3.50% Notes 2028", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("NVDA-2030", "NVIDIA Corp 3.70% Senior Notes 2030", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("V-2031", "Visa Inc 3.80% Senior Notes 2031", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("UNH-2035", "UnitedHealth Group 4.45% Notes 2035", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("PG-2029", "Procter & Gamble Co 3.25% Notes 2029", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("JNJ-2033", "Johnson & Johnson 3.75% Debentures 2033", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        # US High Yield
        ("F-2028-HY", "Ford Motor Credit 6.80% High Yield 2028", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("NFLX-2029-HY", "Netflix Inc 5.875% Senior Notes 2029", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("OXY-2030-HY", "Occidental Petroleum 6.45% Notes 2030", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("TMUS-2031-HY", "T-Mobile USA 5.25% Senior Notes 2031", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("UBER-2029-HY", "Uber Technologies 6.25% High Yield 2029", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("CCL-2028-HY", "Carnival Corp 7.20% Senior Priority 2028", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("AAL-2027-HY", "American Airlines 7.00% Senior Secured 2027", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        # European Corporate Bonds (T+2 standard lag)
        ("BNP-2031-EUR", "BNP Paribas SA 3.625% Senior Non-Preferred 2031", "FIXED_INCOME", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("SHEL-2030-EUR", "Shell International Finance 3.25% 2030", "FIXED_INCOME", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("TTE-2032-EUR", "TotalEnergies SE 3.50% Capital Notes 2032", "FIXED_INCOME", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("SIE-2029-EUR", "Siemens Financierings 3.125% 2029", "FIXED_INCOME", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("SAN-2030-EUR", "Banco Santander SA 3.875% Subordinated 2030", "FIXED_INCOME", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("SAN-2033-EUR", "Banco Santander SA 4.25% Tier 2 2033", "FIXED_INCOME", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("BMW-2028-EUR", "BMW Finance NV 3.20% Notes 2028", "FIXED_INCOME", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("ORAN-2031-EUR", "Orange SA 3.375% Notes 2031", "FIXED_INCOME", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("BP-2030-GBP", "BP Capital Markets 4.375% Guaranteed 2030", "FIXED_INCOME", "GBP", "GBP", "UK", 1, "UK_BANK_HOLIDAY"),
        ("VOD-2032-GBP", "Vodafone Group Plc 5.125% Notes 2032", "FIXED_INCOME", "GBP", "GBP", "UK", 1, "UK_BANK_HOLIDAY"),
        ("AZN-2031-USD", "AstraZeneca Plc 4.125% Global Notes 2031", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
        ("NOVN-2029-EUR", "Novartis Finance SA 3.10% Notes 2029", "FIXED_INCOME", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("HSBC-2033-USD", "HSBC Holdings Plc 5.40% Subordinated 2033", "FIXED_INCOME", "USD", "USD", "US", 1, "FED_US"),
    ]
    for c in corps:
        instruments.append({
            "instrument_id": f"INST-CORP-{c[0]}",
            "instrument_type": "CORPORATE_BOND",
            "instrument_name": c[1],
            "asset_class": c[2],
            "base_currency": c[3],
            "quote_currency": None,
            "settlement_currency": c[4],
            "market_or_region": c[5],
            "standard_settlement_lag_business_days": c[6],
            "market_calendar": c[7],
            "active_flag": True
        })
        
    # 5. EQUITY (30 Global Blue Chips)
    equities = [
        # US Equities (T+1 lag under SEC rules implemented May 2024)
        ("AAPL", "Apple Inc Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("MSFT", "Microsoft Corp Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("NVDA", "NVIDIA Corp Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("AMZN", "Amazon.com Inc Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("GOOGL", "Alphabet Inc Class A Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("META", "Meta Platforms Inc Class A Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("TSLA", "Tesla Inc Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("BRK-B", "Berkshire Hathaway Inc Class B Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("JPM", "JPMorgan Chase & Co Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("V", "Visa Inc Class A Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("LLY", "Eli Lilly & Co Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("AVGO", "Broadcom Inc Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("WMT", "Walmart Inc Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("MA", "Mastercard Inc Class A Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        ("UNH", "UnitedHealth Group Common Stock", "EQUITIES", "USD", "USD", "US", 1, "FED_US"),
        # UK Equities (T+2 lag via CREST)
        ("SHEL-LN", "Shell Plc Ordinary Shares", "EQUITIES", "GBP", "GBP", "UK", 2, "UK_BANK_HOLIDAY"),
        ("AZN-LN", "AstraZeneca Plc Ordinary Shares", "EQUITIES", "GBP", "GBP", "UK", 2, "UK_BANK_HOLIDAY"),
        ("HSBA-LN", "HSBC Holdings Plc Ordinary Shares", "EQUITIES", "GBP", "GBP", "UK", 2, "UK_BANK_HOLIDAY"),
        ("ULVR-LN", "Unilever Plc Ordinary Shares", "EQUITIES", "GBP", "GBP", "UK", 2, "UK_BANK_HOLIDAY"),
        ("BP-LN", "BP Plc Ordinary Shares", "EQUITIES", "GBP", "GBP", "UK", 2, "UK_BANK_HOLIDAY"),
        # European Equities (T+2 lag via Euroclear)
        ("MC-FP", "LVMH Moet Hennessy Louis Vuitton", "EQUITIES", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("ASML-NA", "ASML Holding NV Ordinary Shares", "EQUITIES", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("SAP-GY", "SAP SE Ordinary Shares", "EQUITIES", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("TTE-FP", "TotalEnergies SE Ordinary Shares", "EQUITIES", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("NESN-SW", "Nestle SA Registered Shares", "EQUITIES", "CHF", "CHF", "EU", 2, "TARGET2"),
        ("SIE-GY", "Siemens AG Ordinary Shares", "EQUITIES", "EUR", "EUR", "EU", 2, "TARGET2"),
        ("NOVO-DC", "Novo Nordisk A/S Class B Shares", "EQUITIES", "DKK", "DKK", "EU", 2, "TARGET2"),
        # Asian Equities
        ("7203-JP", "Toyota Motor Corp Common Shares", "EQUITIES", "JPY", "JPY", "JP", 2, "TOKYO_BOJ"),
        ("9984-JP", "SoftBank Group Corp Common Shares", "EQUITIES", "JPY", "JPY", "JP", 2, "TOKYO_BOJ"),
        ("005930-KS", "Samsung Electronics Co Ltd Common Shares", "EQUITIES", "KRW", "KRW", "APAC", 2, "GLOBAL_FX"),
    ]
    for e in equities:
        instruments.append({
            "instrument_id": f"INST-EQ-{e[0]}",
            "instrument_type": "COMMON_STOCK",
            "instrument_name": e[1],
            "asset_class": e[2],
            "base_currency": e[3],
            "quote_currency": None,
            "settlement_currency": e[4],
            "market_or_region": e[5],
            "standard_settlement_lag_business_days": e[6],
            "market_calendar": e[7],
            "active_flag": True
        })
        
    # 6. INTEREST_RATE_SWAP (15 benchmark cleared OTC swaps)
    irs_swaps = [
        ("USD-SOFR-1Y", "USD 1Y SOFR Fixed/Floating Interest Rate Swap", "RATES", "USD", "USD", 2, "FED_US"),
        ("USD-SOFR-2Y", "USD 2Y SOFR Fixed/Floating Interest Rate Swap", "RATES", "USD", "USD", 2, "FED_US"),
        ("USD-SOFR-3Y", "USD 3Y SOFR Fixed/Floating Interest Rate Swap", "RATES", "USD", "USD", 2, "FED_US"),
        ("USD-SOFR-5Y", "USD 5Y SOFR Fixed/Floating Interest Rate Swap", "RATES", "USD", "USD", 2, "FED_US"),
        ("USD-SOFR-7Y", "USD 7Y SOFR Fixed/Floating Interest Rate Swap", "RATES", "USD", "USD", 2, "FED_US"),
        ("USD-SOFR-10Y", "USD 10Y SOFR Benchmark Interest Rate Swap", "RATES", "USD", "USD", 2, "FED_US"),
        ("USD-SOFR-15Y", "USD 15Y SOFR Interest Rate Swap", "RATES", "USD", "USD", 2, "FED_US"),
        ("USD-SOFR-20Y", "USD 20Y SOFR Interest Rate Swap", "RATES", "USD", "USD", 2, "FED_US"),
        ("USD-SOFR-30Y", "USD 30Y SOFR Long Interest Rate Swap", "RATES", "USD", "USD", 2, "FED_US"),
        ("EUR-ESTR-2Y", "EUR 2Y ESTR Fixed/Floating Interest Rate Swap", "RATES", "EUR", "EUR", 2, "TARGET2"),
        ("EUR-ESTR-5Y", "EUR 5Y ESTR Fixed/Floating Interest Rate Swap", "RATES", "EUR", "EUR", 2, "TARGET2"),
        ("EUR-ESTR-10Y", "EUR 10Y ESTR Benchmark Interest Rate Swap", "RATES", "EUR", "EUR", 2, "TARGET2"),
        ("EUR-ESTR-30Y", "EUR 30Y ESTR Long Interest Rate Swap", "RATES", "EUR", "EUR", 2, "TARGET2"),
        ("GBP-SONIA-5Y", "GBP 5Y SONIA Fixed/Floating Interest Rate Swap", "RATES", "GBP", "GBP", 2, "UK_BANK_HOLIDAY"),
        ("GBP-SONIA-10Y", "GBP 10Y SONIA Benchmark Interest Rate Swap", "RATES", "GBP", "GBP", 2, "UK_BANK_HOLIDAY"),
    ]
    for s in irs_swaps:
        instruments.append({
            "instrument_id": f"INST-IRS-{s[0]}",
            "instrument_type": "INTEREST_RATE_SWAP",
            "instrument_name": s[1],
            "asset_class": s[2],
            "base_currency": s[3],
            "quote_currency": None,
            "settlement_currency": s[4],
            "market_or_region": "GLOBAL",
            "standard_settlement_lag_business_days": s[5],
            "market_calendar": s[6],
            "active_flag": True
        })
        
    df_inst = pd.DataFrame(instruments)
    return df_inst

# ---------------------------------------------------------
# 3. Core Trade Dataset Generation (Exactly 50,000 Trades)
# ---------------------------------------------------------
def generate_trades(df_cp: pd.DataFrame, df_inst: pd.DataFrame) -> pd.DataFrame:
    """Generates exactly 50,000 realistic institutional trades across 2025."""
    NUM_TRADES = 50000
    
    # 1. Product distribution
    # FX_SPOT (28%), GOVERNMENT_BOND (20%), CORPORATE_BOND (16%), FX_FORWARD (14%), EQUITY (14%), INTEREST_RATE_SWAP (8%)
    product_types = [
        "FX_SPOT", "GOVERNMENT_BOND", "CORPORATE_BOND", "FX_FORWARD", "EQUITY", "INTEREST_RATE_SWAP"
    ]
    product_probs = [0.28, 0.20, 0.16, 0.14, 0.14, 0.08]
    
    assigned_products = np.random.choice(product_types, size=NUM_TRADES, p=product_probs)
    
    # Pre-filter instruments by product type
    inst_by_prod = {
        "FX_SPOT": df_inst[df_inst["instrument_type"] == "FX_SPOT_PAIR"].to_dict("records"),
        "FX_FORWARD": df_inst[df_inst["instrument_type"] == "FX_FORWARD_CONTRACT"].to_dict("records"),
        "GOVERNMENT_BOND": df_inst[df_inst["instrument_type"] == "GOVERNMENT_BOND"].to_dict("records"),
        "CORPORATE_BOND": df_inst[df_inst["instrument_type"] == "CORPORATE_BOND"].to_dict("records"),
        "EQUITY": df_inst[df_inst["instrument_type"] == "COMMON_STOCK"].to_dict("records"),
        "INTEREST_RATE_SWAP": df_inst[df_inst["instrument_type"] == "INTEREST_RATE_SWAP"].to_dict("records"),
    }
    
    # Counterparty Pareto skew: top 15 counterparties account for ~52% of trades
    cp_records = df_cp.to_dict("records")
    num_cps = len(cp_records)
    # Generate power-law weights for counterparties
    cp_raw_weights = 1.0 / (np.arange(1, num_cps + 1) ** 0.85)
    cp_weights = cp_raw_weights / cp_raw_weights.sum()
    
    # Trading desks mapping
    desks_by_prod = {
        "FX_SPOT": ["G10_FX_SPOT_DESK", "EM_FX_TRADING"],
        "FX_FORWARD": ["FX_FORWARDS_AND_DERIVATIVES", "G10_FX_STRUCTURED"],
        "GOVERNMENT_BOND": ["US_RATES_TRADING", "GLOBAL_GOVT_BONDS"],
        "CORPORATE_BOND": ["INVESTMENT_GRADE_CREDIT", "HIGH_YIELD_CREDIT"],
        "EQUITY": ["GLOBAL_CASH_EQUITIES", "PROGRAM_TRADING_DESK"],
        "INTEREST_RATE_SWAP": ["MACRO_RATES_SWAPS", "RATES_EXOTICS_FLOW"],
    }
    
    # Source systems
    source_systems_by_prod = {
        "FX_SPOT": [("MUREX_FX", 0.65), ("BLOOMBERG_FIT", 0.25), ("MANUAL_OPS_PORTAL", 0.10)],
        "FX_FORWARD": [("MUREX_FX", 0.70), ("BLOOMBERG_FIT", 0.20), ("MANUAL_OPS_PORTAL", 0.10)],
        "GOVERNMENT_BOND": [("TRADEWEB_CREDIT", 0.50), ("BLOOMBERG_FIT", 0.35), ("CALYPSO_RATES", 0.12), ("MANUAL_OPS_PORTAL", 0.03)],
        "CORPORATE_BOND": [("TRADEWEB_CREDIT", 0.45), ("BLOOMBERG_FIT", 0.35), ("CHARLES_RIVER_CRD", 0.15), ("MANUAL_OPS_PORTAL", 0.05)],
        "EQUITY": [("FIDESSA_EQUITIES", 0.55), ("CHARLES_RIVER_CRD", 0.40), ("MANUAL_OPS_PORTAL", 0.05)],
        "INTEREST_RATE_SWAP": [("CALYPSO_RATES", 0.65), ("BLOOMBERG_FIT", 0.25), ("MANUAL_OPS_PORTAL", 0.10)],
    }
    
    # Sales trader identifiers pool
    trader_ids = [f"TRD-USR-{100 + i}" for i in range(40)]
    
    # Assign execution dates with calendar weighting
    trade_dates = np.random.choice(BUSINESS_DATES_2025, size=NUM_TRADES, p=DATE_WEIGHTS)
    
    # Realistic Intraday UTC timestamp distribution (normalized)
    hour_raw = np.array([
        0.01, 0.01, 0.02, 0.02, 0.03, 0.03,  # 00-05 (Asian early)
        0.04, 0.05, 0.06, 0.07, 0.07, 0.06,  # 06-11 (London morning)
        0.06, 0.09, 0.11, 0.11, 0.08, 0.04,  # 12-17 (US/London overlap)
        0.02, 0.01, 0.01, 0.005, 0.003, 0.002 # 18-23 (US close/night)
    ], dtype=float)
    HOUR_PROBS = hour_raw / hour_raw.sum()

    trade_records = []
    
    for idx in range(NUM_TRADES):
        trade_id = f"TRD-2025-{idx + 1:05d}"
        prod = assigned_products[idx]
        t_date = trade_dates[idx]
        
        # Instrument selection
        inst = random.choice(inst_by_prod[prod])
        inst_id = inst["instrument_id"]
        
        # Counterparty selection (Pareto distributed)
        cp_idx = np.random.choice(num_cps, p=cp_weights)
        cp = cp_records[cp_idx]
        cp_id = cp["counterparty_id"]
        
        # Trading desk
        desk = random.choice(desks_by_prod[prod])
        
        # Direction
        direction = random.choice(["BUY", "SELL"])
        
        # Source system
        src_choices, src_probs = zip(*source_systems_by_prod[prod])
        source_system = np.random.choice(src_choices, p=src_probs)
        
        sales_trader = random.choice(trader_ids)
        
        # Currencies, Notional, Price calculation based on financial product
        if prod == "FX_SPOT":
            base_curr = inst["base_currency"]
            quote_curr = inst["quote_currency"]
            if direction == "BUY":
                buy_curr, sell_curr = base_curr, quote_curr
            else:
                buy_curr, sell_curr = quote_curr, base_curr
            trade_currency = "USD"
            # FX notional: $500k to $30M, typical rounded institutional sizes
            notional = round(float(np.random.exponential(scale=3500000) + 500000), -4)
            notional = min(notional, 45000000.0)
            # Spot rates
            rate_map = {
                "EURUSD": 1.0850, "USDJPY": 154.20, "GBPUSD": 1.2950, "USDCHF": 0.8850,
                "AUDUSD": 0.6550, "USDCAD": 1.3850, "NZDUSD": 0.5950, "EURGBP": 0.8380,
                "EURJPY": 167.30, "GBPJPY": 199.60, "USDCNH": 7.2450, "USDSGD": 1.3450,
                "USDHKD": 7.7820, "USDKRW": 1395.0, "USDMXN": 19.850, "USDBRL": 5.7500,
                "USDINR": 84.40, "EURCHF": 0.9600, "AUDJPY": 101.00, "CADJPY": 111.30,
            }
            pair_key = inst_id.replace("INST-FX-", "")
            base_price = rate_map.get(pair_key, 1.2500)
            price = round(base_price * (1.0 + np.random.normal(0, 0.003)), 5)
            
        elif prod == "FX_FORWARD":
            base_curr = inst["base_currency"]
            quote_curr = inst["quote_currency"]
            if direction == "BUY":
                buy_curr, sell_curr = base_curr, quote_curr
            else:
                buy_curr, sell_curr = quote_curr, base_curr
            trade_currency = "USD"
            notional = round(float(np.random.exponential(scale=5000000) + 1000000), -4)
            notional = min(notional, 60000000.0)
            pair_key = inst_id.split("-")[2]
            rate_map = {"EURUSD": 1.0920, "USDJPY": 151.80, "GBPUSD": 1.3010, "USDCHF": 0.8750, "AUDUSD": 0.6580, "USDCAD": 1.3780}
            base_price = rate_map.get(pair_key, 1.2600)
            price = round(base_price * (1.0 + np.random.normal(0, 0.005)), 5)
            
        elif prod == "GOVERNMENT_BOND":
            buy_curr = inst["settlement_currency"] if direction == "BUY" else None
            sell_curr = inst["settlement_currency"] if direction == "SELL" else None
            trade_currency = inst["settlement_currency"]
            # Sovereign bond notional: $1M to $75M
            notional = round(float(np.random.exponential(scale=8000000) + 1000000), -5)
            notional = min(notional, 100000000.0)
            # Bond clean price: % of par (typically 94.00 to 103.50)
            price = round(float(np.random.normal(99.25, 2.8)), 4)
            
        elif prod == "CORPORATE_BOND":
            buy_curr = inst["settlement_currency"] if direction == "BUY" else None
            sell_curr = inst["settlement_currency"] if direction == "SELL" else None
            trade_currency = inst["settlement_currency"]
            # Corporate bond notional: $250k to $15M
            notional = round(float(np.random.exponential(scale=2500000) + 250000), -4)
            notional = min(notional, 25000000.0)
            # Price % of par
            price = round(float(np.random.normal(98.10, 3.5)), 4)
            
        elif prod == "EQUITY":
            buy_curr = inst["settlement_currency"] if direction == "BUY" else None
            sell_curr = inst["settlement_currency"] if direction == "SELL" else None
            trade_currency = inst["settlement_currency"]
            # Equity price per share
            if "US" in inst["market_or_region"]:
                price = round(float(np.random.uniform(25.0, 420.0)), 2)
            elif "EU" in inst["market_or_region"] or "UK" in inst["market_or_region"]:
                price = round(float(np.random.uniform(15.0, 350.0)), 2)
            else:
                price = round(float(np.random.uniform(500.0, 8500.0)), 2)
            # Shares: 200 to 50,000 shares
            shares = int(np.random.exponential(scale=5000) + 200)
            notional = round(shares * price, 2)
            
        elif prod == "INTEREST_RATE_SWAP":
            buy_curr = None
            sell_curr = None
            trade_currency = inst["settlement_currency"]
            # Swap notional: $10M to $250M
            notional = round(float(np.random.exponential(scale=25000000) + 10000000), -6)
            notional = min(notional, 300000000.0)
            # Fixed swap rate coupon (e.g. 3.450% to 4.850%)
            price = round(float(np.random.normal(4.15, 0.45)), 4)
        # Realistic Intraday UTC timestamp distribution:
        hour = np.random.choice(range(24), p=HOUR_PROBS)
        minute = np.random.randint(0, 60)
        second = np.random.randint(0, 60)
        trade_dt = datetime.datetime(t_date.year, t_date.month, t_date.day, hour, minute, second, tzinfo=datetime.timezone.utc)
        
        # Booking timestamp:
        # Electronic feeds: 1-90 seconds after trade
        # Manual portal: 180 - 3600 seconds (3 mins to 1 hour)
        if source_system == "MANUAL_OPS_PORTAL":
            booking_lag_sec = int(np.random.exponential(scale=900) + 120)
        else:
            booking_lag_sec = int(np.random.exponential(scale=15) + 1)
        booking_dt = trade_dt + datetime.timedelta(seconds=booking_lag_sec)
        
        # Expected settlement date
        lag_days = inst["standard_settlement_lag_business_days"]
        exp_settle_date = add_business_days(t_date, lag_days)
        
        trade_records.append({
            "trade_id": trade_id,
            "trade_date": t_date.isoformat(),
            "trade_timestamp_utc": trade_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
            "booking_timestamp_utc": booking_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
            "product_type": prod,
            "instrument_id": inst_id,
            "counterparty_id": cp_id,
            "trading_desk": desk,
            "trade_direction": direction,
            "buy_currency": buy_curr,
            "sell_currency": sell_curr,
            "currency": trade_currency,
            "notional_amount": notional,
            "trade_price": price,
            "trade_status": "CONFIRMED", # Will update if cancelled or amended during lifecycle
            "expected_settlement_date": exp_settle_date.isoformat(),
            "actual_settlement_date": None, # Will populate in settlement engine
            "settlement_status": "PENDING", # Will populate in settlement engine
            "trade_source_system": source_system,
            "sales_trader_id": sales_trader,
            "created_at_utc": booking_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
            "updated_at_utc": booking_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
            # Internal reference objects for settlement engine
            "_trade_date_obj": t_date,
            "_trade_dt_obj": trade_dt,
            "_booking_dt_obj": booking_dt,
            "_exp_settle_date_obj": exp_settle_date,
            "_cp_risk": cp["risk_rating"],
            "_cp_ssi_status": cp["settlement_instruction_status"],
            "_inst_market": inst["market_or_region"],
            "_inst_type": inst["instrument_type"],
            "_settlement_currency": inst["settlement_currency"],
        })
        
    df_trades = pd.DataFrame(trade_records)
    return df_trades

# ---------------------------------------------------------
# 4. Settlement Engine & Lifecycle Modeling
# ---------------------------------------------------------
def process_settlements_and_exceptions(df_trades: pd.DataFrame):
    """
    Simulates settlement attempts, failure detection, retries, and operational exceptions.
    Ensures 100% lifecycle and temporal consistency:
    - Attempt 1 on expected_settlement_date.
    - If Attempt 1 fails -> generates exception record in exceptions.csv.
    - Retry Attempt 2 on next business day (or +2 business days).
    - If Attempt 2 succeeds -> trade is settled on Attempt 2 date, actual_settlement_date set.
    - If trades settle in 2026 -> preserved as PENDING without fabricated completion.
    """
    settlement_records = []
    exception_records = []
    
    cutoff_2025 = datetime.date(2025, 12, 31)
    
    # Method & Location mapping by product type
    settlement_venues = {
        "FX_SPOT": ("PVP", "CLS_BANK"),
        "FX_FORWARD": ("BILATERAL_GROSS_PAYMENT", "SWIFT_GPI_NETWORK"),
        "GOVERNMENT_BOND": ("DVP", "FEDWIRE_SECURITIES"),
        "CORPORATE_BOND": ("DVP", "DTCC_NSCC"),
        "EQUITY": ("DVP", "DTCC_NSCC"),
        "INTEREST_RATE_SWAP": ("NET_CASH_SETTLEMENT", "CHIPS_USD"),
    }
    
    # Settlement failure reasons pool with calibrated distribution
    fail_reasons = [
        ("SSI_MISMATCH", 0.30, "RC_SSI_OUTDATED", "Outdated or unverified Standard Settlement Instructions in static repository", "STATIC_DATA_TEAM"),
        ("INSUFFICIENT_SECURITIES", 0.25, "RC_INSUFFICIENT_SECURITIES", "Fails to deliver due to inventory deficit or collateral borrow delay", "SETTLEMENTS_OPS"),
        ("INSUFFICIENT_FUNDS", 0.18, "RC_INSUFFICIENT_LIQUIDITY", "Counterparty cash clearing deficit at central settlement depository", "SETTLEMENTS_OPS"),
        ("COUNTERPARTY_UNRESPONSIVE", 0.12, "RC_COUNTERPARTY_AFFIRMATION_DELAY", "Counterparty custodian failed to affirm or match instruction prior to cutoff", "MIDDLE_OFFICE_TRADE_SUPPORT"),
        ("DEPOSITORY_CUTOFF_MISSED", 0.08, "RC_DEPOSITORY_CUTOFF_MISSED", "High volume batch latency caused clearing network cutoff breach", "SETTLEMENTS_OPS"),
        ("LATE_MATCHING", 0.07, "RC_INTERNAL_MESSAGE_DROPPED", "Internal message transmission delayed between front office and settlement gateway", "SETTLEMENTS_OPS"),
    ]
    fail_choices, fail_probs_raw, fail_rc_codes, fail_rc_descs, fail_teams = zip(*fail_reasons)
    fail_probs = np.array(fail_probs_raw, dtype=float) / sum(fail_probs_raw)
    
    settlement_id_counter = 1
    exception_id_counter = 1
    
    # -------------------------------------------------------------
    # Step A: Pre-Settlement Exceptions (Booking, Confirmations, Compliance)
    # Approx 6.5% of trades encounter a pre-settlement operational exception
    # -------------------------------------------------------------
    pre_settle_exception_trades = set()
    
    for idx, row in df_trades.iterrows():
        trade_id = row["trade_id"]
        source_system = row["trade_source_system"]
        prod = row["product_type"]
        booking_dt = row["_booking_dt_obj"]
        exp_settle_date = row["_exp_settle_date_obj"]
        notional = row["notional_amount"]
        cp_risk = row["_cp_risk"]
        
        # Risk factors for pre-settlement exceptions:
        # MANUAL_OPS_PORTAL has 5x higher booking discrepancies
        p_pre_exception = 0.035
        if source_system == "MANUAL_OPS_PORTAL":
            p_pre_exception += 0.22  # High booking errors on manual portal
        if cp_risk in ("HIGH", "VERY_HIGH"):
            p_pre_exception += 0.04
        if row["_cp_ssi_status"] in ("EXPIRED", "INCOMPLETE"):
            p_pre_exception += 0.08
            
        if np.random.rand() < p_pre_exception:
            pre_settle_exception_trades.add(trade_id)
            exp_id = f"EXP-2025-{exception_id_counter:06d}"
            exception_id_counter += 1
            
            # Types of pre-settlement exceptions
            if source_system == "MANUAL_OPS_PORTAL" and np.random.rand() < 0.70:
                e_type = "BOOKING_DISCREPANCY"
                e_cat = "BOOKING"
                rc_code = "RC_MANUAL_DATA_ENTRY"
                rc_desc = "Manual trade ticket keying error in trade economics or account hierarchy"
                assigned_team = "MIDDLE_OFFICE_TRADE_SUPPORT"
                res_action = "TRADE_AMENDED_IN_OMS"
            elif row["_cp_ssi_status"] in ("EXPIRED", "INCOMPLETE") and np.random.rand() < 0.65:
                e_type = "SSI_DEFICIENCY"
                e_cat = "REFERENCE_DATA"
                rc_code = "RC_SSI_OUTDATED"
                rc_desc = "Static master indicates missing or expired settlement instructions prior to value date"
                assigned_team = "STATIC_DATA_TEAM"
                res_action = "SSI_UPDATED_RESUBMITTED"
            elif np.random.rand() < 0.45:
                e_type = "CONFIRMATION_MISMATCH"
                e_cat = "CONFIRMATIONS"
                rc_code = "RC_CONFIRMATION_ECONOMIC_MISMATCH"
                rc_desc = "Counterparty electronic affirmation failed due to price/rate mismatch tolerance"
                assigned_team = "CONFIRMATIONS_TEAM"
                res_action = "AFFIRMATION_MATCHED_MANUALLY"
            elif np.random.rand() < 0.30:
                e_type = "RECONCILIATION_BREAK"
                e_cat = "RECONCILIATION"
                rc_code = "RC_INTERNAL_MESSAGE_DROPPED"
                rc_desc = "EOD position ledger discrepancy between OMS and downstream accounting repository"
                assigned_team = "RECONCILIATIONS_UNIT"
                res_action = "TRADE_AMENDED_IN_OMS"
            else:
                e_type = "SANCTION_SCREENING_HOLD"
                e_cat = "COMPLIANCE"
                rc_code = "RC_SANCTION_NAME_FALSE_POSITIVE"
                rc_desc = "Automated OFAC/sanctions screening hit triggered false-positive name hold"
                assigned_team = "RISK_COMPLIANCE"
                res_action = "COMPLIANCE_CLEARED_FALSE_POSITIVE"
                
            # Detection timestamp: between booking and settlement date
            detect_lag_hours = float(np.random.uniform(0.5, 18.0))
            detect_dt = booking_dt + datetime.timedelta(hours=detect_lag_hours)
            open_dt = detect_dt + datetime.timedelta(minutes=float(np.random.uniform(5, 30)))
            
            # Severity assignment
            if notional >= 10000000 or e_cat == "COMPLIANCE":
                sev = "CRITICAL"
                sla_target = 4
            elif notional >= 2000000:
                sev = "HIGH"
                sla_target = 8
            elif notional >= 500000:
                sev = "MEDIUM"
                sla_target = 24
            else:
                sev = "LOW"
                sla_target = 48
                
            # Resolution logic:
            # Did it breach SLA? SLA breach probability calibrated to ~16%
            # Backlog: if detection was after Dec 25, 2025, higher chance of remaining open at year-end
            is_year_end = detect_dt.date() >= datetime.date(2025, 12, 24)
            if is_year_end and np.random.rand() < 0.40:
                res_status = np.random.choice(["IN_PROGRESS", "ESCALATED", "PENDING_CLIENT_RESPONSE"])
                resolved_dt = None
                res_action_val = None
                hours_open = (datetime.datetime(2025, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc) - open_dt).total_seconds() / 3600.0
                sla_breached = bool(hours_open > sla_target)
            else:
                res_status = "RESOLVED"
                # Resolution time in hours calibrated to ~16% SLA breach rate
                if np.random.rand() < 0.16:
                    res_hours = float(np.random.uniform(sla_target * 1.05, sla_target * 1.75))
                else:
                    res_hours = float(np.random.uniform(0.5, max(0.8, sla_target * 0.85)))
                    
                resolved_dt = open_dt + datetime.timedelta(hours=res_hours)
                sla_breached = bool(res_hours > sla_target)
                res_action_val = res_action
                
            reopened = bool(np.random.rand() < 0.025)
            
            exception_records.append({
                "exception_id": exp_id,
                "trade_id": trade_id,
                "settlement_id": None, # Null for pre-settlement issues
                "exception_type": e_type,
                "exception_category": e_cat,
                "root_cause_code": rc_code,
                "root_cause_description": rc_desc,
                "severity": sev,
                "detected_at_utc": detect_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                "assigned_team": assigned_team,
                "resolution_status": res_status,
                "opened_at_utc": open_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                "resolved_at_utc": resolved_dt.strftime("%Y-%m-%d %H:%M:%SZ") if resolved_dt else None,
                "resolution_action": res_action_val,
                "sla_target_hours": sla_target,
                "sla_breached": sla_breached,
                "reopened_flag": reopened,
                # internal
                "_resolved_dt_obj": resolved_dt
            })
            
            if e_type == "BOOKING_DISCREPANCY" and res_status == "RESOLVED":
                df_trades.at[idx, "trade_status"] = "AMENDED"

    # -------------------------------------------------------------
    # Step B: Settlement Attempt Engine
    # -------------------------------------------------------------
    for idx, row in df_trades.iterrows():
        trade_id = row["trade_id"]
        prod = row["product_type"]
        cp_id = row["counterparty_id"]
        t_date = row["_trade_date_obj"]
        exp_settle_date = row["_exp_settle_date_obj"]
        notional = row["notional_amount"]
        price = row["trade_price"]
        cp_risk = row["_cp_risk"]
        cp_ssi = row["_cp_ssi_status"]
        settle_currency = row["_settlement_currency"]
        
        method, location = settlement_venues[prod]
        
        # Calculate expected settlement cash amount
        if prod in ("FX_SPOT", "FX_FORWARD"):
            exp_settle_amount = float(notional)
        elif prod in ("GOVERNMENT_BOND", "CORPORATE_BOND"):
            exp_settle_amount = round(float(notional * (price / 100.0)), 2)
        elif prod == "EQUITY":
            exp_settle_amount = float(notional)
        elif prod == "INTEREST_RATE_SWAP":
            # Upfront fee or initial margin cash flow: 0.1% - 0.5% of notional
            exp_settle_amount = round(float(notional * 0.0025), 2)
            
        # Case 1: Trade settles in 2026 (beyond observation period)
        if exp_settle_date > cutoff_2025:
            settle_id = f"SET-2025-{settlement_id_counter:06d}"
            settlement_id_counter += 1
            
            instr_ref = f"INST-REF-2025-{settlement_id_counter:07d}"
            rec_dt = datetime.datetime(t_date.year, t_date.month, t_date.day, 18, 0, 0, tzinfo=datetime.timezone.utc)
            
            settlement_records.append({
                "settlement_id": settle_id,
                "trade_id": trade_id,
                "settlement_attempt_number": 1,
                "settlement_date": exp_settle_date.isoformat(),
                "expected_settlement_date": exp_settle_date.isoformat(),
                "settlement_currency": settle_currency,
                "expected_settlement_amount": exp_settle_amount,
                "actual_settlement_amount": 0.00,
                "settlement_status": "PENDING",
                "settlement_method": method,
                "settlement_location_or_system": location,
                "settlement_failure_reason": None,
                "instruction_status": "ACKNOWLEDGED",
                "instruction_reference": instr_ref,
                "counterparty_id": cp_id,
                "record_timestamp_utc": rec_dt.strftime("%Y-%m-%d %H:%M:%SZ")
            })
            df_trades.at[idx, "settlement_status"] = "PENDING"
            df_trades.at[idx, "actual_settlement_date"] = None
            continue
            
        # Case 2: Trade settles within 2025 observation period
        # Calibrate baseline initial failure rate to ~3.2%
        p_fail = 0.022
        
        # Risk factors:
        if prod in ("CORPORATE_BOND", "EQUITY"):
            p_fail += 0.012  # Delivery fails / short borrow fails
        if cp_risk in ("HIGH", "VERY_HIGH"):
            p_fail += 0.035
        if cp_ssi in ("EXPIRED", "INCOMPLETE"):
            p_fail += 0.28  # SSI mismatch
        if row["trade_source_system"] == "MANUAL_OPS_PORTAL":
            p_fail += 0.025
            
        # Operational Disruption Windows:
        # Disruption Window 1: May 27-29 (Clearing link upgrade causing high SSI/cutoff issues)
        if datetime.date(2025, 5, 27) <= exp_settle_date <= datetime.date(2025, 5, 29):
            p_fail += 0.095
        # Disruption Window 2: Oct 14-16 (Depository messaging queue latency)
        if datetime.date(2025, 10, 14) <= exp_settle_date <= datetime.date(2025, 10, 16):
            p_fail += 0.085
            
        initial_fail = bool(np.random.rand() < p_fail)
        
        # ---------------- Attempt 1 ----------------
        settle_id_1 = f"SET-2025-{settlement_id_counter:06d}"
        settlement_id_counter += 1
        instr_ref_1 = f"INST-REF-2025-{settlement_id_counter:07d}"
        
        attempt_1_dt = datetime.datetime(exp_settle_date.year, exp_settle_date.month, exp_settle_date.day, 16, 30, 0, tzinfo=datetime.timezone.utc)
        
        if not initial_fail:
            # Successful settlement on Attempt 1
            settlement_records.append({
                "settlement_id": settle_id_1,
                "trade_id": trade_id,
                "settlement_attempt_number": 1,
                "settlement_date": exp_settle_date.isoformat(),
                "expected_settlement_date": exp_settle_date.isoformat(),
                "settlement_currency": settle_currency,
                "expected_settlement_amount": exp_settle_amount,
                "actual_settlement_amount": exp_settle_amount,
                "settlement_status": "SETTLED",
                "settlement_method": method,
                "settlement_location_or_system": location,
                "settlement_failure_reason": None,
                "instruction_status": "MATCHED",
                "instruction_reference": instr_ref_1,
                "counterparty_id": cp_id,
                "record_timestamp_utc": attempt_1_dt.strftime("%Y-%m-%d %H:%M:%SZ")
            })
            df_trades.at[idx, "settlement_status"] = "SETTLED"
            df_trades.at[idx, "actual_settlement_date"] = exp_settle_date.isoformat()
            df_trades.at[idx, "trade_status"] = "SETTLED"
            
        else:
            # Attempt 1 Failed
            # Select root cause / failure reason
            f_idx = np.random.choice(len(fail_choices), p=fail_probs)
            reason = fail_choices[f_idx]
            rc_code = fail_rc_codes[f_idx]
            rc_desc = fail_rc_descs[f_idx]
            ops_team = fail_teams[f_idx]
            
            settlement_records.append({
                "settlement_id": settle_id_1,
                "trade_id": trade_id,
                "settlement_attempt_number": 1,
                "settlement_date": exp_settle_date.isoformat(),
                "expected_settlement_date": exp_settle_date.isoformat(),
                "settlement_currency": settle_currency,
                "expected_settlement_amount": exp_settle_amount,
                "actual_settlement_amount": 0.00,
                "settlement_status": "FAILED",
                "settlement_method": method,
                "settlement_location_or_system": location,
                "settlement_failure_reason": reason,
                "instruction_status": "UNMATCHED" if "MATCH" in reason or "UNRESPONSIVE" in reason else "REJECTED",
                "instruction_reference": instr_ref_1,
                "counterparty_id": cp_id,
                "record_timestamp_utc": attempt_1_dt.strftime("%Y-%m-%d %H:%M:%SZ")
            })
            
            # Generate settlement failure exception linked to settlement_id_1
            exp_id_settle = f"EXP-2025-{exception_id_counter:06d}"
            exception_id_counter += 1
            
            detect_dt = attempt_1_dt + datetime.timedelta(minutes=float(np.random.uniform(5, 30)))
            open_dt = detect_dt + datetime.timedelta(minutes=float(np.random.uniform(5, 20)))
            
            # Severity based on notional and impact
            if notional >= 10000000:
                sev = "CRITICAL"
                sla_target = 4
            elif notional >= 2000000:
                sev = "HIGH"
                sla_target = 8
            elif notional >= 500000:
                sev = "MEDIUM"
                sla_target = 24
            else:
                sev = "LOW"
                sla_target = 48
                
            # Attempt 2 retry scheduling (+1 or +2 business days)
            retry_date_1 = add_business_days(exp_settle_date, 1)
            
            # Can we settle on Attempt 2? ~80% success rate on retry
            attempt_2_success = bool(np.random.rand() < 0.80)
            
            if attempt_2_success and retry_date_1 <= cutoff_2025:
                # Exception resolved prior to Attempt 2, calibrated to ~16% SLA breach rate
                if np.random.rand() < 0.16:
                    res_hours = float(np.random.uniform(sla_target * 1.05, sla_target * 1.80))
                else:
                    res_hours = float(np.random.uniform(0.8, max(1.2, sla_target * 0.85)))
                resolved_dt = open_dt + datetime.timedelta(hours=res_hours)
                sla_breached = bool(res_hours > sla_target)
                res_action = "SSI_UPDATED_RESUBMITTED" if reason == "SSI_MISMATCH" else "SECURITIES_BORROW_EXECUTED"
                
                exception_records.append({
                    "exception_id": exp_id_settle,
                    "trade_id": trade_id,
                    "settlement_id": settle_id_1,
                    "exception_type": "SETTLEMENT_FAILURE",
                    "exception_category": "SETTLEMENT",
                    "root_cause_code": rc_code,
                    "root_cause_description": rc_desc,
                    "severity": sev,
                    "detected_at_utc": detect_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                    "assigned_team": ops_team,
                    "resolution_status": "RESOLVED",
                    "opened_at_utc": open_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                    "resolved_at_utc": resolved_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                    "resolution_action": res_action,
                    "sla_target_hours": sla_target,
                    "sla_breached": sla_breached,
                    "reopened_flag": False,
                    "_resolved_dt_obj": resolved_dt
                })
                
                # ---------------- Attempt 2 (Success) ----------------
                settle_id_2 = f"SET-2025-{settlement_id_counter:06d}"
                settlement_id_counter += 1
                instr_ref_2 = f"INST-REF-2025-{settlement_id_counter:07d}"
                attempt_2_dt = datetime.datetime(retry_date_1.year, retry_date_1.month, retry_date_1.day, 16, 30, 0, tzinfo=datetime.timezone.utc)
                
                settlement_records.append({
                    "settlement_id": settle_id_2,
                    "trade_id": trade_id,
                    "settlement_attempt_number": 2,
                    "settlement_date": retry_date_1.isoformat(),
                    "expected_settlement_date": exp_settle_date.isoformat(),
                    "settlement_currency": settle_currency,
                    "expected_settlement_amount": exp_settle_amount,
                    "actual_settlement_amount": exp_settle_amount,
                    "settlement_status": "SETTLED",
                    "settlement_method": method,
                    "settlement_location_or_system": location,
                    "settlement_failure_reason": None,
                    "instruction_status": "MATCHED",
                    "instruction_reference": instr_ref_2,
                    "counterparty_id": cp_id,
                    "record_timestamp_utc": attempt_2_dt.strftime("%Y-%m-%d %H:%M:%SZ")
                })
                df_trades.at[idx, "settlement_status"] = "SETTLED"
                df_trades.at[idx, "actual_settlement_date"] = retry_date_1.isoformat()
                df_trades.at[idx, "trade_status"] = "SETTLED"
                
            else:
                # Attempt 2 fails or extends beyond cutoff
                # ---------------- Attempt 2 (Failed / Open) ----------------
                settle_id_2 = f"SET-2025-{settlement_id_counter:06d}"
                settlement_id_counter += 1
                instr_ref_2 = f"INST-REF-2025-{settlement_id_counter:07d}"
                
                if retry_date_1 > cutoff_2025:
                    # Retry lands in 2026 -> PENDING
                    settlement_records.append({
                        "settlement_id": settle_id_2,
                        "trade_id": trade_id,
                        "settlement_attempt_number": 2,
                        "settlement_date": retry_date_1.isoformat(),
                        "expected_settlement_date": exp_settle_date.isoformat(),
                        "settlement_currency": settle_currency,
                        "expected_settlement_amount": exp_settle_amount,
                        "actual_settlement_amount": 0.00,
                        "settlement_status": "PENDING",
                        "settlement_method": method,
                        "settlement_location_or_system": location,
                        "settlement_failure_reason": None,
                        "instruction_status": "ACKNOWLEDGED",
                        "instruction_reference": instr_ref_2,
                        "counterparty_id": cp_id,
                        "record_timestamp_utc": attempt_1_dt.strftime("%Y-%m-%d %H:%M:%SZ")
                    })
                    df_trades.at[idx, "settlement_status"] = "PENDING"
                    df_trades.at[idx, "actual_settlement_date"] = None
                    
                    # Exception remains open at year end
                    exception_records.append({
                        "exception_id": exp_id_settle,
                        "trade_id": trade_id,
                        "settlement_id": settle_id_1,
                        "exception_type": "SETTLEMENT_FAILURE",
                        "exception_category": "SETTLEMENT",
                        "root_cause_code": rc_code,
                        "root_cause_description": rc_desc,
                        "severity": sev,
                        "detected_at_utc": detect_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                        "assigned_team": ops_team,
                        "resolution_status": "IN_PROGRESS",
                        "opened_at_utc": open_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                        "resolved_at_utc": None,
                        "resolution_action": None,
                        "sla_target_hours": sla_target,
                        "sla_breached": True,
                        "reopened_flag": False,
                        "_resolved_dt_obj": None
                    })
                else:
                    # Attempt 2 failed within 2025
                    attempt_2_dt = datetime.datetime(retry_date_1.year, retry_date_1.month, retry_date_1.day, 16, 30, 0, tzinfo=datetime.timezone.utc)
                    settlement_records.append({
                        "settlement_id": settle_id_2,
                        "trade_id": trade_id,
                        "settlement_attempt_number": 2,
                        "settlement_date": retry_date_1.isoformat(),
                        "expected_settlement_date": exp_settle_date.isoformat(),
                        "settlement_currency": settle_currency,
                        "expected_settlement_amount": exp_settle_amount,
                        "actual_settlement_amount": 0.00,
                        "settlement_status": "FAILED",
                        "settlement_method": method,
                        "settlement_location_or_system": location,
                        "settlement_failure_reason": reason,
                        "instruction_status": "REJECTED",
                        "instruction_reference": instr_ref_2,
                        "counterparty_id": cp_id,
                        "record_timestamp_utc": attempt_2_dt.strftime("%Y-%m-%d %H:%M:%SZ")
                    })
                    
                    # Check for Attempt 3 or permanent fail
                    retry_date_2 = add_business_days(retry_date_1, 1)
                    attempt_3_success = bool(np.random.rand() < 0.65)
                    
                    if attempt_3_success and retry_date_2 <= cutoff_2025:
                        # Attempt 3 succeeds
                        settle_id_3 = f"SET-2025-{settlement_id_counter:06d}"
                        settlement_id_counter += 1
                        instr_ref_3 = f"INST-REF-2025-{settlement_id_counter:07d}"
                        attempt_3_dt = datetime.datetime(retry_date_2.year, retry_date_2.month, retry_date_2.day, 16, 30, 0, tzinfo=datetime.timezone.utc)
                        
                        settlement_records.append({
                            "settlement_id": settle_id_3,
                            "trade_id": trade_id,
                            "settlement_attempt_number": 3,
                            "settlement_date": retry_date_2.isoformat(),
                            "expected_settlement_date": exp_settle_date.isoformat(),
                            "settlement_currency": settle_currency,
                            "expected_settlement_amount": exp_settle_amount,
                            "actual_settlement_amount": exp_settle_amount,
                            "settlement_status": "SETTLED",
                            "settlement_method": method,
                            "settlement_location_or_system": location,
                            "settlement_failure_reason": None,
                            "instruction_status": "MATCHED",
                            "instruction_reference": instr_ref_3,
                            "counterparty_id": cp_id,
                            "record_timestamp_utc": attempt_3_dt.strftime("%Y-%m-%d %H:%M:%SZ")
                        })
                        df_trades.at[idx, "settlement_status"] = "SETTLED"
                        df_trades.at[idx, "actual_settlement_date"] = retry_date_2.isoformat()
                        df_trades.at[idx, "trade_status"] = "SETTLED"
                        
                        # Exception resolved with breach
                        resolved_dt = open_dt + datetime.timedelta(hours=float(np.random.uniform(40.0, 72.0)))
                        exception_records.append({
                            "exception_id": exp_id_settle,
                            "trade_id": trade_id,
                            "settlement_id": settle_id_1,
                            "exception_type": "SETTLEMENT_FAILURE",
                            "exception_category": "SETTLEMENT",
                            "root_cause_code": rc_code,
                            "root_cause_description": rc_desc,
                            "severity": sev,
                            "detected_at_utc": detect_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                            "assigned_team": ops_team,
                            "resolution_status": "RESOLVED",
                            "opened_at_utc": open_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                            "resolved_at_utc": resolved_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                            "resolution_action": "BILATERAL_PAIR_OFF_AGREED",
                            "sla_target_hours": sla_target,
                            "sla_breached": True,
                            "reopened_flag": True, # Reopened after attempt 2 failed
                            "_resolved_dt_obj": resolved_dt
                        })
                    else:
                        # Remains FAILED / CANCELLED
                        df_trades.at[idx, "settlement_status"] = "FAILED"
                        df_trades.at[idx, "actual_settlement_date"] = None
                        df_trades.at[idx, "trade_status"] = "CANCELLED" if np.random.rand() < 0.5 else "EXECUTED"
                        
                        exception_records.append({
                            "exception_id": exp_id_settle,
                            "trade_id": trade_id,
                            "settlement_id": settle_id_1,
                            "exception_type": "SETTLEMENT_FAILURE",
                            "exception_category": "SETTLEMENT",
                            "root_cause_code": rc_code,
                            "root_cause_description": rc_desc,
                            "severity": sev,
                            "detected_at_utc": detect_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                            "assigned_team": ops_team,
                            "resolution_status": "ESCALATED",
                            "opened_at_utc": open_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                            "resolved_at_utc": None,
                            "resolution_action": None,
                            "sla_target_hours": sla_target,
                            "sla_breached": True,
                            "reopened_flag": True,
                            "_resolved_dt_obj": None
                        })
                        
    df_settlements = pd.DataFrame(settlement_records)
    df_exceptions = pd.DataFrame(exception_records)
    
    # Clean up internal metadata columns in trades
    cols_to_drop = [c for c in df_trades.columns if c.startswith("_")]
    df_trades = df_trades.drop(columns=cols_to_drop)
    
    # Clean up internal metadata columns in exceptions
    if "_resolved_dt_obj" in df_exceptions.columns:
        df_exceptions = df_exceptions.drop(columns=["_resolved_dt_obj"])
        
    return df_trades, df_settlements, df_exceptions

# ---------------------------------------------------------
# 5. Intentional Seeded Data Quality Issues
# ---------------------------------------------------------
def inject_known_dq_issues(df_trades: pd.DataFrame, df_settlements: pd.DataFrame, df_exceptions: pd.DataFrame):
    """
    Deliberately injects realistic operational data-quality anomalies into specific fields
    and catalogs them in known_data_quality_issues.csv.
    Canonical PKs and referential integrity remain strictly valid.
    """
    dq_records = []
    
    # 1. Trailing whitespace in sales trader ID (e.g. 5 trades)
    ws_indices = [142, 2854, 15903, 31204, 48211]
    for idx in ws_indices:
        t_id = df_trades.at[idx, "trade_id"]
        orig_val = df_trades.at[idx, "sales_trader_id"]
        mod_val = f"{orig_val} "
        df_trades.at[idx, "sales_trader_id"] = mod_val
        dq_records.append({
            "issue_id": f"DQ-{len(dq_records)+1:03d}",
            "file_name": "trades.csv",
            "primary_key_column": "trade_id",
            "primary_key_value": t_id,
            "column_name": "sales_trader_id",
            "issue_type": "TRAILING_WHITESPACE",
            "original_canonical_value": orig_val,
            "injected_faulty_value": mod_val,
            "business_impact": "Causes string join mismatches in operational KPI reports and sales credits",
            "recommended_remediation": "Apply TRIM() cleaning function during Bronze-to-Silver ETL ingestion"
        })
        
    # 2. Casing inconsistency in trade_source_system (e.g. 4 trades)
    casing_indices = [512, 12890, 24501, 39800]
    for idx in casing_indices:
        t_id = df_trades.at[idx, "trade_id"]
        orig_val = df_trades.at[idx, "trade_source_system"]
        mod_val = orig_val.lower()
        df_trades.at[idx, "trade_source_system"] = mod_val
        dq_records.append({
            "issue_id": f"DQ-{len(dq_records)+1:03d}",
            "file_name": "trades.csv",
            "primary_key_column": "trade_id",
            "primary_key_value": t_id,
            "column_name": "trade_source_system",
            "issue_type": "LOWERCASE_INCONSISTENCY",
            "original_canonical_value": orig_val,
            "injected_faulty_value": mod_val,
            "business_impact": "Group by aggregations split source system error metrics into distinct case bins",
            "recommended_remediation": "Enforce UPPER() normalization rule on source system dimensional attributes"
        })
        
    # 3. Micro NTP Clock Sync Anomaly: booking_timestamp precedes trade_timestamp by 2 seconds (3 trades)
    ntp_indices = [1894, 27301, 41050]
    for idx in ntp_indices:
        t_id = df_trades.at[idx, "trade_id"]
        t_ts = df_trades.at[idx, "trade_timestamp_utc"]
        t_dt = datetime.datetime.strptime(t_ts, "%Y-%m-%d %H:%M:%SZ")
        faulty_booking_dt = t_dt - datetime.timedelta(seconds=2)
        faulty_val = faulty_booking_dt.strftime("%Y-%m-%d %H:%M:%SZ")
        orig_val = df_trades.at[idx, "booking_timestamp_utc"]
        df_trades.at[idx, "booking_timestamp_utc"] = faulty_val
        dq_records.append({
            "issue_id": f"DQ-{len(dq_records)+1:03d}",
            "file_name": "trades.csv",
            "primary_key_column": "trade_id",
            "primary_key_value": t_id,
            "column_name": "booking_timestamp_utc",
            "issue_type": "NEGATIVE_TIME_LAG_NTP_ANOMALY",
            "original_canonical_value": orig_val,
            "injected_faulty_value": faulty_val,
            "business_impact": "Calculates negative booking duration (-2s), violating temporal sequence checks",
            "recommended_remediation": "Apply GREATEST(booking_timestamp, trade_timestamp) and trigger NTP clock alert"
        })
        
    # 4. Micro-penny rounding discrepancy on settlement amount (3 settlements)
    penny_indices = [45, 1205, 3450]
    for idx in penny_indices:
        if idx < len(df_settlements):
            s_id = df_settlements.at[idx, "settlement_id"]
            if df_settlements.at[idx, "settlement_status"] == "SETTLED":
                orig_amt = df_settlements.at[idx, "actual_settlement_amount"]
                mod_amt = round(orig_amt + 0.01, 2)
                df_settlements.at[idx, "actual_settlement_amount"] = mod_amt
                dq_records.append({
                    "issue_id": f"DQ-{len(dq_records)+1:03d}",
                    "file_name": "settlements.csv",
                    "primary_key_column": "settlement_id",
                    "primary_key_value": s_id,
                    "column_name": "actual_settlement_amount",
                    "issue_type": "PENNY_ROUNDING_DISCREPANCY",
                    "original_canonical_value": str(orig_amt),
                    "injected_faulty_value": str(mod_amt),
                    "business_impact": "Generates 1-cent reconciliation break between settlement cash ledger and OMS",
                    "recommended_remediation": "Apply 5-cent operational tolerance threshold in automated cash reconciliations"
                })
                
    # 5. Missing / truncated BIC prefix in settlement instruction_reference (4 settlements)
    bic_indices = [89, 450, 11200, 25600]
    for idx in bic_indices:
        if idx < len(df_settlements):
            s_id = df_settlements.at[idx, "settlement_id"]
            orig_val = df_settlements.at[idx, "instruction_reference"]
            mod_val = orig_val.replace("INST-REF-", "TRUNC-")
            df_settlements.at[idx, "instruction_reference"] = mod_val
            dq_records.append({
                "issue_id": f"DQ-{len(dq_records)+1:03d}",
                "file_name": "settlements.csv",
                "primary_key_column": "settlement_id",
                "primary_key_value": s_id,
                "column_name": "instruction_reference",
                "issue_type": "MALFORMED_SWIFT_REFERENCE",
                "original_canonical_value": orig_val,
                "injected_faulty_value": mod_val,
                "business_impact": "Fails regex pattern validation on standard ISO/SWIFT reference syntax",
                "recommended_remediation": "Standardize reference syntax with automated prefix repair in ingestion gateway"
            })
            
    df_dq = pd.DataFrame(dq_records)
    return df_trades, df_settlements, df_exceptions, df_dq

# ---------------------------------------------------------
# 6. Data Dictionary Generation
# ---------------------------------------------------------
def generate_data_dictionary() -> pd.DataFrame:
    """Creates complete metadata data dictionary for all generated tables."""
    dict_entries = [
        # trades.csv
        ("trades.csv", "trade_id", "STRING", "Unique stable primary key identifier for the trade record", "Canonical institutional trade ticket ID", "NO", "PRIMARY_KEY", "Pattern: TRD-2025-XXXXX", "Direct system sequence"),
        ("trades.csv", "trade_date", "DATE", "Trade execution date in ISO YYYY-MM-DD", "Contractual business execution date", "NO", "NONE", "2025-01-01 to 2025-12-31 (Weekdays only)", "Execution date"),
        ("trades.csv", "trade_timestamp_utc", "TIMESTAMP", "Exact execution timestamp in UTC", "Point-in-time timestamp when order filled", "NO", "NONE", "ISO 8601 UTC string", "Front-office OMS capture"),
        ("trades.csv", "booking_timestamp_utc", "TIMESTAMP", "Timestamp when trade entered middle/back office systems", "Operational system ingestion timestamp", "NO", "NONE", "ISO 8601 UTC string >= trade_timestamp", "System ingestion log"),
        ("trades.csv", "product_type", "STRING", "Financial asset class product code", "High-level instrument taxonomy", "NO", "NONE", "FX_SPOT, FX_FORWARD, GOVERNMENT_BOND, CORPORATE_BOND, EQUITY, INTEREST_RATE_SWAP", "Product master"),
        ("trades.csv", "instrument_id", "STRING", "Foreign key pointing to instruments.csv", "Unique financial instrument identifier", "NO", "FOREIGN_KEY", "Matches instruments.instrument_id", "Reference link"),
        ("trades.csv", "counterparty_id", "STRING", "Foreign key pointing to counterparties.csv", "Institutional client or dealer counterparty", "NO", "FOREIGN_KEY", "Matches counterparties.counterparty_id", "Reference link"),
        ("trades.csv", "trading_desk", "STRING", "Internal trading desk responsible for trade", "Organizational business unit", "NO", "NONE", "Desks per product master", "Internal trade hierarchy"),
        ("trades.csv", "trade_direction", "STRING", "Direction of trade from reporting bank perspective", "Trade side (BUY or SELL)", "NO", "NONE", "BUY, SELL", "Trader execution ticket"),
        ("trades.csv", "buy_currency", "STRING", "ISO 4217 code of currency purchased", "Purchased leg currency for FX/Bonds", "YES", "NONE", "ISO 3-letter currency code (EUR, USD, GBP, etc.)", "Trade terms"),
        ("trades.csv", "sell_currency", "STRING", "ISO 4217 code of currency sold", "Sold leg currency for FX/Bonds", "YES", "NONE", "ISO 3-letter currency code", "Trade terms"),
        ("trades.csv", "currency", "STRING", "Primary trade/settlement denomination currency", "Single reporting currency", "NO", "NONE", "ISO 3-letter currency code", "Instrument settlement currency"),
        ("trades.csv", "notional_amount", "DECIMAL(18,2)", "Contractual notional principal monetary amount", "Trade face value or principal amount", "NO", "NONE", "Positive monetary amount", "Trade execution ticket"),
        ("trades.csv", "trade_price", "DECIMAL(18,5)", "Executed unit price, FX exchange rate, or bond clean price", "Financial transaction execution rate/price", "NO", "NONE", "Positive numeric price/rate", "Market fill price"),
        ("trades.csv", "trade_status", "STRING", "Current lifecycle status of trade ticket", "Middle-office operational status", "NO", "NONE", "CONFIRMED, EXECUTED, CANCELLED, AMENDED, SETTLED", "State machine transition"),
        ("trades.csv", "expected_settlement_date", "DATE", "Contractual settlement due date calculated via calendar lag", "Value date when exchange of value is due", "NO", "NONE", "ISO YYYY-MM-DD business date", "add_business_days(trade_date, lag)"),
        ("trades.csv", "actual_settlement_date", "DATE", "Actual business date when trade settled successfully", "Depository confirmed settlement date", "YES", "NONE", "ISO YYYY-MM-DD (Null if unsettled/pending)", "Populated on settlement success"),
        ("trades.csv", "settlement_status", "STRING", "High-level operational settlement status of the trade", "Consolidated trade settlement health", "NO", "NONE", "SETTLED, FAILED, PENDING, PARTIALLY_SETTLED, NOT_APPLICABLE", "Derived from settlement attempts"),
        ("trades.csv", "trade_source_system", "STRING", "Identifier of originating front-office or routing system", "Source OMS/EMS gateway", "NO", "NONE", "MUREX_FX, CALYPSO_RATES, TRADEWEB_CREDIT, BLOOMBERG_FIT, FIDESSA_EQUITIES, CHARLES_RIVER_CRD, MANUAL_OPS_PORTAL", "Originating message header"),
        ("trades.csv", "sales_trader_id", "STRING", "Internal synthetic sales trader badge identifier", "Executing internal personnel ID", "NO", "NONE", "TRD-USR-XXX", "Front office badge"),
        ("trades.csv", "created_at_utc", "TIMESTAMP", "Record creation timestamp in operational repository", "Audit trail timestamp", "NO", "NONE", "ISO 8601 UTC string", "System timestamp"),
        ("trades.csv", "updated_at_utc", "TIMESTAMP", "Record last modification timestamp in operational repository", "Audit trail timestamp", "NO", "NONE", "ISO 8601 UTC string", "System timestamp"),

        # settlements.csv
        ("settlements.csv", "settlement_id", "STRING", "Unique primary key for settlement instruction record", "Depository instruction identifier", "NO", "PRIMARY_KEY", "Pattern: SET-2025-XXXXXX", "Instruction sequence"),
        ("settlements.csv", "trade_id", "STRING", "Foreign key pointing to trades.csv", "Underlying trade ticket ID", "NO", "FOREIGN_KEY", "Matches trades.trade_id", "Relational reference"),
        ("settlements.csv", "settlement_attempt_number", "INTEGER", "Sequential attempt index for trade settlement (1, 2, 3...)", "Retry counter for settlement matching", "NO", "NONE", "1, 2, 3", "Attempt iteration counter"),
        ("settlements.csv", "settlement_date", "DATE", "Date on which settlement attempt was submitted to venue", "Attempt execution date", "NO", "NONE", "ISO YYYY-MM-DD", "Attempt schedule date"),
        ("settlements.csv", "expected_settlement_date", "DATE", "Contractual due date for settlement", "Target settlement value date", "NO", "NONE", "ISO YYYY-MM-DD", "From trades.expected_settlement_date"),
        ("settlements.csv", "settlement_currency", "STRING", "ISO 4217 settlement payment currency code", "Cash settlement currency", "NO", "NONE", "ISO 3-letter currency code", "From instrument master"),
        ("settlements.csv", "expected_settlement_amount", "DECIMAL(18,2)", "Contractual cash settlement amount expected", "Anticipated net cash flow", "NO", "NONE", "Positive numeric amount", "Trade notional * price / formula"),
        ("settlements.csv", "actual_settlement_amount", "DECIMAL(18,2)", "Actual cash settled across depository network", "Realized net cash flow", "NO", "NONE", "Zero on fail; matches expected on success", "Depository settlement confirmation"),
        ("settlements.csv", "settlement_status", "STRING", "Outcome status of settlement attempt", "Attempt state", "NO", "NONE", "SETTLED, FAILED, PENDING, PARTIALLY_SETTLED", "Depository message MT548/camt.054"),
        ("settlements.csv", "settlement_method", "STRING", "Settlement clearing mechanism", "Risk reduction settlement model", "NO", "NONE", "DVP, PVP, FREE_OF_PAYMENT, NET_CASH_SETTLEMENT, BILATERAL_GROSS_PAYMENT", "Product convention"),
        ("settlements.csv", "settlement_location_or_system", "STRING", "Depository, clearinghouse, or payment network", "Settlement venue", "NO", "NONE", "CLS_BANK, DTCC_NSCC, FEDWIRE_SECURITIES, EUROCLEAR_BANK, CLEARSTREAM_BANKING, CHIPS_USD, SWIFT_GPI_NETWORK", "Static routing rules"),
        ("settlements.csv", "settlement_failure_reason", "STRING", "Standardized failure code when attempt fails", "Depository exception code", "YES", "NONE", "SSI_MISMATCH, INSUFFICIENT_SECURITIES, INSUFFICIENT_FUNDS, COUNTERPARTY_UNRESPONSIVE, DEPOSITORY_CUTOFF_MISSED, LATE_MATCHING (Null on SETTLED)", "Depository MT548 reason"),
        ("settlements.csv", "instruction_status", "STRING", "Messaging status of settlement instruction", "SWIFT instruction state", "NO", "NONE", "ACKNOWLEDGED, MATCHED, UNMATCHED, REJECTED, CANCELLED", "SWIFT message state"),
        ("settlements.csv", "instruction_reference", "STRING", "Synthetic SWIFT MT541/543 or pacs message reference", "Unique transaction reference", "NO", "NONE", "Standard instruction syntax", "Gateway sequence"),
        ("settlements.csv", "counterparty_id", "STRING", "Foreign key pointing to counterparties.csv", "Clearing counterparty", "NO", "FOREIGN_KEY", "Matches counterparties.counterparty_id", "Relational reference"),
        ("settlements.csv", "record_timestamp_utc", "TIMESTAMP", "Instruction creation/update timestamp in UTC", "Depository processing timestamp", "NO", "NONE", "ISO 8601 UTC string", "System timestamp"),

        # exceptions.csv
        ("exceptions.csv", "exception_id", "STRING", "Unique primary key for operational exception incident", "Exception tracking incident ID", "NO", "PRIMARY_KEY", "Pattern: EXP-2025-XXXXXX", "Incident sequence"),
        ("exceptions.csv", "trade_id", "STRING", "Foreign key pointing to trades.csv", "Trade experiencing exception", "NO", "FOREIGN_KEY", "Matches trades.trade_id", "Relational reference"),
        ("exceptions.csv", "settlement_id", "STRING", "Nullable foreign key pointing to settlements.csv", "Linked failed settlement attempt", "YES", "FOREIGN_KEY", "Matches settlements.settlement_id (Null for booking issues)", "Relational link on settlement fail"),
        ("exceptions.csv", "exception_type", "STRING", "Operational taxonomy code of exception", "Exception classification", "NO", "NONE", "SETTLEMENT_FAILURE, BOOKING_DISCREPANCY, CONFIRMATION_MISMATCH, SSI_DEFICIENCY, RECONCILIATION_BREAK, PRICE_TOLERANCE_EXCEEDED, SANCTION_SCREENING_HOLD", "Ops monitor trigger"),
        ("exceptions.csv", "exception_category", "STRING", "High-level operational functional domain", "Operations department domain", "NO", "NONE", "SETTLEMENT, BOOKING, CONFIRMATIONS, REFERENCE_DATA, RECONCILIATION, COMPLIANCE", "Functional domain mapping"),
        ("exceptions.csv", "root_cause_code", "STRING", "Root Cause Analysis (RCA) standardized code", "Underlying operational failure cause", "NO", "NONE", "RC_SSI_OUTDATED, RC_INSUFFICIENT_SECURITIES, RC_INSUFFICIENT_LIQUIDITY, RC_MANUAL_DATA_ENTRY, RC_CONFIRMATION_ECONOMIC_MISMATCH, RC_DEPOSITORY_CUTOFF_MISSED, RC_INTERNAL_MESSAGE_DROPPED, RC_SANCTION_NAME_FALSE_POSITIVE", "Investigator RCA assignment"),
        ("exceptions.csv", "root_cause_description", "STRING", "Narrative explanation of operational failure mechanism", "Detailed incident root cause description", "NO", "NONE", "Descriptive narrative", "RCA catalog"),
        ("exceptions.csv", "severity", "STRING", "Priority and risk tier of exception", "Operational risk severity tier", "NO", "NONE", "LOW, MEDIUM, HIGH, CRITICAL", "Rule based on notional and impact"),
        ("exceptions.csv", "detected_at_utc", "TIMESTAMP", "Timestamp when exception condition was detected", "Monitoring detection timestamp", "NO", "NONE", "ISO 8601 UTC string", "Rule engine event time"),
        ("exceptions.csv", "assigned_team", "STRING", "Operational group assigned to investigate and resolve", "Responsible operations unit", "NO", "NONE", "SETTLEMENTS_OPS, CONFIRMATIONS_TEAM, STATIC_DATA_TEAM, RECONCILIATIONS_UNIT, MIDDLE_OFFICE_TRADE_SUPPORT, RISK_COMPLIANCE", "Triage assignment"),
        ("exceptions.csv", "resolution_status", "STRING", "Current lifecycle status of exception ticket", "Workflow state", "NO", "NONE", "RESOLVED, IN_PROGRESS, ESCALATED, PENDING_CLIENT_RESPONSE, CLOSED_UNRESOLVED", "Ticket workflow status"),
        ("exceptions.csv", "opened_at_utc", "TIMESTAMP", "Timestamp when investigation ticket was formally opened", "SLA clock start timestamp", "NO", "NONE", "ISO 8601 UTC string >= detected_at", "Workflow ticket open"),
        ("exceptions.csv", "resolved_at_utc", "TIMESTAMP", "Timestamp when exception was resolved and validated", "SLA clock stop timestamp", "YES", "NONE", "ISO 8601 UTC string (Null if open)", "Workflow ticket resolve"),
        ("exceptions.csv", "resolution_action", "STRING", "Remediation action taken to clear the exception", "Operational corrective action", "YES", "NONE", "SSI_UPDATED_RESUBMITTED, TRADE_AMENDED_IN_OMS, AFFIRMATION_MATCHED_MANUALLY, SECURITIES_BORROW_EXECUTED, COMPLIANCE_CLEARED_FALSE_POSITIVE, BILATERAL_PAIR_OFF_AGREED (Null if open)", "Remediation log"),
        ("exceptions.csv", "sla_target_hours", "INTEGER", "Contractual/policy operational SLA resolution window in hours", "SLA threshold limit", "NO", "NONE", "4 (CRITICAL), 8 (HIGH), 24 (MEDIUM), 48 (LOW)", "SLA policy matrix"),
        ("exceptions.csv", "sla_breached", "BOOLEAN", "Deterministic indicator if resolution time exceeded SLA target", "SLA compliance flag", "NO", "NONE", "TRUE, FALSE", "(resolved_at or observation_end - opened_at) > sla_target"),
        ("exceptions.csv", "reopened_flag", "BOOLEAN", "Indicates if exception recurred after initial closure", "Quality rework indicator", "NO", "NONE", "TRUE, FALSE", "Incident audit trail"),

        # counterparties.csv
        ("counterparties.csv", "counterparty_id", "STRING", "Unique primary key for counterparty entity", "Institutional client identifier", "NO", "PRIMARY_KEY", "Pattern: CP-XXX", "Entity master sequence"),
        ("counterparties.csv", "counterparty_name", "STRING", "Fictional institutional business legal name", "Legal entity name", "NO", "NONE", "Institutional names pool", "Entity master"),
        ("counterparties.csv", "counterparty_type", "STRING", "Institutional sector classification", "Counterparty sector", "NO", "NONE", "INVESTMENT_BANK, ASSET_MANAGER, HEDGE_FUND, PENSION_FUND, CORPORATE_TREASURY, SOVEREIGN_WEALTH_FUND", "KYC onboarding data"),
        ("counterparties.csv", "home_country", "STRING", "ISO 3166-1 alpha-2 country of domicile", "Jurisdiction of incorporation", "NO", "NONE", "US, GB, DE, FR, JP, SG, CH, CA, etc.", "KYC data"),
        ("counterparties.csv", "operating_region", "STRING", "Global trading region", "Geographic supervisory zone", "NO", "NONE", "AMER, EMEA, APAC", "Organizational taxonomy"),
        ("counterparties.csv", "risk_rating", "STRING", "Ordinal credit and operational risk grade", "Counterparty risk assessment", "NO", "NONE", "LOW, MEDIUM, HIGH, VERY_HIGH", "Internal risk model"),
        ("counterparties.csv", "onboarding_status", "STRING", "Operational onboarding readiness status", "KYC / operational onboarding state", "NO", "NONE", "ACTIVE, PROBATION, RESTRICTED, PENDING_REVIEW", "KYC status"),
        ("counterparties.csv", "settlement_instruction_status", "STRING", "Health status of Standard Settlement Instructions", "SSI static integrity flag", "NO", "NONE", "VERIFIED, EXPIRED, PENDING_AMENDMENT, INCOMPLETE", "SSI static master"),
        ("counterparties.csv", "active_flag", "BOOLEAN", "Flag indicating whether counterparty is currently active", "Entity active flag", "NO", "NONE", "TRUE, FALSE", "Entity master"),

        # instruments.csv
        ("instruments.csv", "instrument_id", "STRING", "Unique primary key for financial instrument", "Security / contract identifier", "NO", "PRIMARY_KEY", "Pattern: INST-[PROD]-[CODE]", "Instrument master sequence"),
        ("instruments.csv", "instrument_type", "STRING", "Granular financial instrument classification", "Product type code", "NO", "NONE", "FX_SPOT_PAIR, FX_FORWARD_CONTRACT, GOVERNMENT_BOND, CORPORATE_BOND, COMMON_STOCK, INTEREST_RATE_SWAP", "Product taxonomy"),
        ("instruments.csv", "instrument_name", "STRING", "Descriptive instrument title", "Market description", "NO", "NONE", "Descriptive text string", "Security master"),
        ("instruments.csv", "asset_class", "STRING", "Broad financial asset class", "Portfolio asset class", "NO", "NONE", "FOREIGN_EXCHANGE, FIXED_INCOME, EQUITIES, RATES", "Asset class taxonomy"),
        ("instruments.csv", "base_currency", "STRING", "ISO 4217 base currency of instrument", "Primary currency", "NO", "NONE", "ISO 3-letter currency code", "Contract specifications"),
        ("instruments.csv", "quote_currency", "STRING", "ISO 4217 quote currency (for FX pairs)", "Secondary currency", "YES", "NONE", "ISO 3-letter currency code (Null for bonds/equities)", "Contract specifications"),
        ("instruments.csv", "settlement_currency", "STRING", "ISO 4217 cash settlement currency", "Payment currency", "NO", "NONE", "ISO 3-letter currency code", "Contract specifications"),
        ("instruments.csv", "market_or_region", "STRING", "Primary exchange or geographic market", "Trading venue / market", "NO", "NONE", "US, UK, EU, JP, APAC, GLOBAL", "Market directory"),
        ("instruments.csv", "standard_settlement_lag_business_days", "INTEGER", "Standard business-day settlement lag (T+N)", "Settlement convention lag", "NO", "NONE", "1 (T+1), 2 (T+2), 22-260 (Forwards)", "Market standard conventions"),
        ("instruments.csv", "market_calendar", "STRING", "Holiday calendar used for business-day calculations", "Financial calendar rule", "NO", "NONE", "FED_US, TARGET2, UK_BANK_HOLIDAY, TOKYO_BOJ, GLOBAL_FX", "Calendar convention"),
        ("instruments.csv", "active_flag", "BOOLEAN", "Flag indicating instrument is actively tradeable", "Tradability flag", "NO", "NONE", "TRUE, FALSE", "Security master"),

        # known_data_quality_issues.csv
        ("known_data_quality_issues.csv", "issue_id", "STRING", "Unique tracking ID for seeded data-quality defect", "Defect catalog ID", "NO", "PRIMARY_KEY", "Pattern: DQ-XXX", "Defect sequence"),
        ("known_data_quality_issues.csv", "file_name", "STRING", "Target file where anomaly was injected", "Dataset location", "NO", "NONE", "trades.csv, settlements.csv", "Target table"),
        ("known_data_quality_issues.csv", "primary_key_column", "STRING", "Primary key column name in target table", "Entity key pointer", "NO", "NONE", "trade_id, settlement_id", "Schema definition"),
        ("known_data_quality_issues.csv", "primary_key_value", "STRING", "Primary key value identifying affected row", "Target row identifier", "NO", "NONE", "Exact key value", "Injected record key"),
        ("known_data_quality_issues.csv", "column_name", "STRING", "Target column containing the anomalous value", "Attribute name", "NO", "NONE", "Column name", "Target field"),
        ("known_data_quality_issues.csv", "issue_type", "STRING", "Categorical classification of the defect", "DQ defect taxonomy", "NO", "NONE", "TRAILING_WHITESPACE, LOWERCASE_INCONSISTENCY, NEGATIVE_TIME_LAG_NTP_ANOMALY, PENNY_ROUNDING_DISCREPANCY, MALFORMED_SWIFT_REFERENCE", "Defect rule"),
        ("known_data_quality_issues.csv", "original_canonical_value", "STRING", "Clean canonical value prior to fault injection", "Expected value", "NO", "NONE", "String representation", "Audit log"),
        ("known_data_quality_issues.csv", "injected_faulty_value", "STRING", "Faulty value present in the raw dataset", "Observed value", "NO", "NONE", "String representation", "Injected value"),
        ("known_data_quality_issues.csv", "business_impact", "STRING", "Explanation of downstream operational/reporting impact", "Business consequence", "NO", "NONE", "Descriptive text", "Risk assessment"),
        ("known_data_quality_issues.csv", "recommended_remediation", "STRING", "Data engineering fix or ETL cleaning rule", "Remediation rule", "NO", "NONE", "SQL/Python cleaning expression", "ETL transformation specification"),
    ]
    
    df_dict = pd.DataFrame(dict_entries, columns=[
        "file_name", "column_name", "data_type", "description",
        "business_definition", "nullable", "primary_or_foreign_key",
        "allowed_values_or_constraints", "derivation_rule"
    ])
    return df_dict

# ---------------------------------------------------------
# 7. Main Execution Pipeline
# ---------------------------------------------------------
def main():
    print("=" * 70)
    print("Starting Realistic Financial Trade Operations Dataset Generation")
    print(f"Fixed Random Seed: {RANDOM_SEED}")
    print("=" * 70)
    
    # 1. Reference tables
    print("\n[1/6] Generating Reference Master Data...")
    df_cp = generate_counterparties()
    print(f"  -> Generated {len(df_cp)} Counterparties in counterparties.csv")
    
    df_inst = generate_instruments()
    print(f"  -> Generated {len(df_inst)} Financial Instruments in instruments.csv")
    
    # 2. Trades
    print("\n[2/6] Generating 50,000 Institutional Trades across 2025...")
    df_trades = generate_trades(df_cp, df_inst)
    print(f"  -> Generated {len(df_trades)} Trades in trades.csv")
    
    # 3. Settlements & Exceptions Engine
    print("\n[3/6] Running Settlement & Operational Exception Simulation Engine...")
    df_trades, df_settlements, df_exceptions = process_settlements_and_exceptions(df_trades)
    print(f"  -> Generated {len(df_settlements)} Settlement Records in settlements.csv")
    print(f"  -> Generated {len(df_exceptions)} Exception Records in exceptions.csv")
    
    # 4. Inject Known Data Quality Issues
    print("\n[4/6] Seeding Known Operational Data Quality Issues for Testing Pipeline...")
    df_trades, df_settlements, df_exceptions, df_dq = inject_known_dq_issues(
        df_trades, df_settlements, df_exceptions
    )
    print(f"  -> Seeded {len(df_dq)} Documented Defects in known_data_quality_issues.csv")
    
    # 5. Data Dictionary
    print("\n[5/6] Building Comprehensive Data Dictionary...")
    df_dict = generate_data_dictionary()
    print(f"  -> Documented {len(df_dict)} Column Definitions across all tables in data_dictionary.csv")
    
    # 6. Export CSV files
    print("\n[6/6] Exporting CSV Files to data/raw/ ...")
    files_to_export = [
        ("trades.csv", df_trades),
        ("settlements.csv", df_settlements),
        ("exceptions.csv", df_exceptions),
        ("counterparties.csv", df_cp),
        ("instruments.csv", df_inst),
        ("known_data_quality_issues.csv", df_dq),
        ("data_dictionary.csv", df_dict),
    ]
    
    for filename, df in files_to_export:
        filepath = os.path.join(DATA_RAW_DIR, filename)
        df.to_csv(filepath, index=False, encoding="utf-8")
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"  -> Exported {filename:32s}: {len(df):7,d} rows | {file_size_mb:6.2f} MB")
        
    print("\n" + "=" * 70)
    print("Dataset Generation Completed Successfully!")
    print("=" * 70)

if __name__ == "__main__":
    main()

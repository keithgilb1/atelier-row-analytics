#!/usr/bin/env python3
"""
atelier_row_generator.py - synthetic luxury-handbag resale warehouse ("Atelier Row", fictional).

Simulates about 5.5 years of daily operations for a boutique reseller of high-end handbags:
three stores (New York City, Los Angeles, Miami) plus an online channel (Online (HQ)).
Every day the simulation runs customer buy-ins (purchases), a four-stage authentication
pipeline, stock on hand, and sales. A daily inventory snapshot is built from the result.

Writes one CSV per table and (optionally) a DuckDB database.

Usage:
    python atelier_row_generator.py                      # seed 42 -> ./atelier_row_data
    python atelier_row_generator.py --seed 7 --out run2
    python atelier_row_generator.py --no-duckdb          # CSVs only

Same --seed always gives the same data. Business names, brand relationships, addresses and
phone numbers are fictional (US and Canadian phone numbers use the reserved 555 range).

Requires: numpy, pandas, duckdb
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# Time window and tunable business constants
# ----------------------------------------------------------------------------
DATA_START = date(2021, 6, 1)          # first sales day
DATA_END = date(2026, 11, 21)          # snapshot / "today"
N_DAYS = (DATA_END - DATA_START).days + 1
OPENING_STOCK_LOOKBACK = 60            # opening stock was bought up to 60 days before DATA_START
GROWTH = 0.04                          # annual demand growth
PURCHASE_OVERSUPPLY = 1.00             # baseline buy-in rate relative to demand (steered by stock level below)
TARGET_WEEKS_ON_HAND = 6.0             # buy-ins speed up or slow down to hold about six weeks of stock
BUYIN_RATIO = 0.60                     # purchase price = 60% of market value  (-40%)
EXOTIC_SHARE = 0.15                    # share of Birkin/Kelly pieces in exotic leather
SELLIER_RARE_PRICE = (33000, 40000)    # Birkin 25 Sellier: discontinued, so priced at the top end

SEASON = {1: 1.10, 2: 0.95, 3: 1.05, 4: 1.05, 5: 1.00, 6: 0.90,
          7: 0.85, 8: 0.85, 9: 1.05, 10: 1.05, 11: 1.10, 12: 1.30}
WEEKDAY = np.array([0.8, 0.9, 1.0, 1.0, 1.2, 1.5, 0.6])   # Mon..Sun, averages 1.0

# ----------------------------------------------------------------------------
# Locations
# ----------------------------------------------------------------------------
LOCATIONS = [
    dict(location_id="LOC-NYC", location_name="New York City", location_address="1200 Fifth Avenue",
         city="New York", state_province="NY", zip_postal_code="10029", country="United States",
         location_phone="+1-212-555-0110", open_date=date(2016, 3, 1), weekly_sales=20),
    dict(location_id="LOC-LA", location_name="Los Angeles", location_address="300 N Rodeo Drive",
         city="Beverly Hills", state_province="CA", zip_postal_code="90210", country="United States",
         location_phone="+1-310-555-0120", open_date=date(2017, 9, 15), weekly_sales=20),
    dict(location_id="LOC-MIA", location_name="Miami", location_address="3930 NE 2nd Avenue",
         city="Miami", state_province="FL", zip_postal_code="33137", country="United States",
         location_phone="+1-305-555-0130", open_date=date(2018, 11, 1), weekly_sales=20),
    dict(location_id="LOC-ONL", location_name="Online (HQ)", location_address="1200 Fifth Avenue",
         city="New York", state_province="NY", zip_postal_code="10029", country="United States",
         location_phone="+1-212-555-0110", open_date=date(2019, 6, 1), weekly_sales=12),
]
WEEKLY = {loc["location_id"]: loc["weekly_sales"] for loc in LOCATIONS}
STORE_IDS = ["LOC-NYC", "LOC-LA", "LOC-MIA"]        # physical stock locations
ONLINE_ID = "LOC-ONL"
STOCK_FOR = {"LOC-NYC": "LOC-NYC", "LOC-LA": "LOC-LA", "LOC-MIA": "LOC-MIA", "LOC-ONL": "LOC-NYC"}
STORE_LABEL = {"LOC-NYC": "New York", "LOC-LA": "Los Angeles", "LOC-MIA": "Miami"}
LOC_ORDER = ["LOC-NYC", "LOC-LA", "LOC-MIA", "LOC-ONL"]

# ----------------------------------------------------------------------------
# Customers: country, (city, state/province/region, metro store or "")
# ----------------------------------------------------------------------------
COUNTRY_TABLE = [
    # code, name, weight, cities
    ("US", "United States", 0.41, [("New York", "NY", "LOC-NYC"), ("Los Angeles", "CA", "LOC-LA"),
                                   ("Beverly Hills", "CA", "LOC-LA"), ("Miami", "FL", "LOC-MIA"),
                                   ("Dallas", "TX", ""), ("Chicago", "IL", ""), ("San Francisco", "CA", ""),
                                   ("Greenwich", "CT", ""), ("Palm Beach", "FL", ""), ("Aspen", "CO", ""),
                                   ("Boston", "MA", ""), ("Atlanta", "GA", ""), ("Scottsdale", "AZ", ""),
                                   ("Seattle", "WA", "")]),
    ("CA", "Canada", 0.04, [("Toronto", "ON", ""), ("Vancouver", "BC", ""), ("Montreal", "QC", "")]),
    ("GB", "United Kingdom", 0.08, [("London", "England", ""), ("Manchester", "England", ""),
                                    ("Edinburgh", "Scotland", "")]),
    ("FR", "France", 0.07, [("Paris", "Ile-de-France", ""), ("Cannes", "Provence-Alpes-Cote d'Azur", ""),
                            ("Lyon", "Auvergne-Rhone-Alpes", "")]),
    ("IT", "Italy", 0.05, [("Milan", "Lombardy", ""), ("Rome", "Lazio", ""), ("Florence", "Tuscany", "")]),
    ("DE", "Germany", 0.05, [("Berlin", "Berlin", ""), ("Munich", "Bavaria", ""), ("Hamburg", "Hamburg", "")]),
    ("CH", "Switzerland", 0.05, [("Zurich", "Zurich", ""), ("Geneva", "Geneva", "")]),
    ("MC", "Monaco", 0.03, [("Monte-Carlo", "Monaco", "")]),
    ("JP", "Japan", 0.06, [("Tokyo", "Tokyo", ""), ("Osaka", "Osaka", "")]),
    ("SG", "Singapore", 0.03, [("Singapore", "Singapore", "")]),
    ("AU", "Australia", 0.04, [("Sydney", "NSW", ""), ("Melbourne", "VIC", "")]),
    ("MX", "Mexico", 0.03, [("Mexico City", "CDMX", ""), ("Monterrey", "Nuevo Leon", "")]),
    ("BR", "Brazil", 0.03, [("Sao Paulo", "SP", ""), ("Rio de Janeiro", "RJ", "")]),
    ("KR", "South Korea", 0.04, [("Seoul", "Seoul", "")]),
]
DIAL = {"US": "+1", "CA": "+1", "GB": "+44", "FR": "+33", "IT": "+39", "DE": "+49", "CH": "+41",
        "MC": "+377", "JP": "+81", "SG": "+65", "AU": "+61", "MX": "+52", "BR": "+55", "KR": "+82"}
# national significant number: (total digits, leading digits)
PHONE_RULE = {"GB": (10, "7"), "FR": (9, "6"), "IT": (10, "3"), "DE": (10, "1"), "CH": (9, "7"),
              "MC": (8, "6"), "JP": (10, "9"), "SG": (8, "9"), "AU": (9, "4"), "MX": (10, "5"),
              "BR": (11, "11"), "KR": (10, "10")}
FIRST_NAMES = ["Ava", "Liam", "Maya", "Noah", "Zoe", "Ethan", "Priya", "Lucas", "Sofia", "Mateo", "Hana",
               "Omar", "Elena", "Jonas", "Chloe", "Ravi", "Ingrid", "Diego", "Mei", "Samuel", "Freya",
               "Kenji", "Amara", "Tobias", "Leila", "Marco", "Nadia", "Felix", "Yara", "Oscar", "Camille",
               "Lorenzo", "Sienna", "Hugo", "Isabel", "Rafael", "Ayla", "Victor", "Margot", "Theo",
               "Giulia", "Arjun", "Seo-yeon", "Mateus", "Valentina", "Jasper", "Harriet", "Daniel", "Renata",
               "Malik"]
LAST_NAMES = ["Nguyen", "Okafor", "Schmidt", "Rossi", "Tanaka", "Silva", "Patel", "Johansson", "Martin",
              "Kowalski", "Haddad", "Larsen", "Moreau", "Castillo", "Fischer", "Brennan", "Sato", "Andersen",
              "Varga", "Mendes", "Clarke", "Novak", "Ibrahim", "Weber", "Dubois", "Lopez", "Kim", "Hughes",
              "Bellini", "Okonkwo", "Laurent", "Hoffmann", "Yamamoto", "Ferreira", "Dasgupta", "Whitfield",
              "Caruso", "Lindqvist", "Morales", "Park", "Bianchi", "Greene", "Costa", "Adeyemi", "Keller",
              "Moretti", "Shaw", "Reyes", "Ortega", "Hart"]
STREETS = ["Maple", "Harbor", "Olive", "Cedar", "Lake", "Willow", "Summit", "Juniper", "Birch", "Ridge",
           "Orchard", "Crescent", "Meridian", "Beacon", "Granite", "Alder", "Quarry", "Terrace", "Fountain",
           "Linden", "Monarch", "Sable", "Vista", "Pine", "Canal", "Garden", "Heron", "Aspen", "Marble", "Bay"]
SUFFIXES = ["St", "Ave", "Rd", "Blvd", "Ln", "Way", "Dr", "Ct"]

# ----------------------------------------------------------------------------
# Product catalogue
# (category, model, market value anchor, band low, band high, exotic position 0..1, mix weight)
# Birkin/Kelly bands are the standard-leather range; exotic bands are set per leather below.
# ----------------------------------------------------------------------------
BK_LO, BK_HI = 15000, 40000
MODELS = [
    ("Birkin", "25", 28000, BK_LO, BK_HI, 1.00, 0.060),
    ("Birkin", "30", 21000, BK_LO, BK_HI, 0.85, 0.080),
    ("Birkin", "35", 18500, BK_LO, BK_HI, 0.70, 0.050),
    ("Birkin", "40", 16500, BK_LO, BK_HI, 0.55, 0.050),
    ("Birkin", "40 HAC", 15200, BK_LO, BK_HI, 0.00, 0.030),      # lowest of the Birkin range
    ("Kelly", "Mini", 33000, BK_LO, BK_HI, 1.00, 0.060),         # highest-demand Kelly
    ("Kelly", "25", 24000, BK_LO, BK_HI, 0.85, 0.050),
    ("Kelly", "28", 20500, BK_LO, BK_HI, 0.75, 0.040),
    ("Kelly", "32", 18000, BK_LO, BK_HI, 0.60, 0.030),
    ("Kelly", "Pochette", 16000, BK_LO, BK_HI, 0.30, 0.030),
    ("Kelly", "Danse", 15500, BK_LO, BK_HI, 0.20, 0.020),
    ("Constance", "Micro", 11500, 11000, 19000, 0.5, 0.020),
    ("Constance", "Mini", 13500, 11000, 19000, 0.5, 0.030),
    ("Constance", "24", 17500, 11000, 19000, 0.5, 0.030),
    ("Constance", "Elan", 12000, 11000, 19000, 0.5, 0.020),
    ("Constance", "To Go", 15000, 11000, 19000, 0.5, 0.030),
    ("Picotin", "18", 2200, 2000, 6000, 0.5, 0.020),
    ("Picotin", "22", 3200, 2000, 6000, 0.5, 0.020),
    ("Picotin", "26", 4400, 2000, 6000, 0.5, 0.020),
    ("Picotin", "33", 5800, 2000, 6000, 0.5, 0.015),
    ("Evelyne", "TPM", 1900, 1800, 6000, 0.5, 0.015),
    ("Evelyne", "PM", 2800, 1800, 6000, 0.5, 0.015),
    ("Evelyne", "GM", 4200, 1800, 6000, 0.5, 0.015),
    ("Evelyne", "TGM", 5800, 1800, 6000, 0.5, 0.010),
    ("Garden Party", "30", 1600, 1300, 6500, 0.5, 0.020),
    ("Garden Party", "36", 2600, 1300, 6500, 0.5, 0.020),
    ("Garden Party", "49", 4000, 1300, 6500, 0.5, 0.015),
    ("Garden Party", "Voyage", 6300, 1300, 6500, 0.5, 0.010),
    ("Her Bag", "19", 2300, 2000, 6000, 0.5, 0.015),
    ("Her Bag", "31", 3500, 2000, 6000, 0.5, 0.015),
    ("Her Bag", "39", 4600, 2000, 6000, 0.5, 0.010),
    ("Her Bag", "50", 5800, 2000, 6000, 0.5, 0.010),
    ("Other", "Other Description", 4500, 2000, 6000, 0.5, 0.020),
]
MODEL_MIX = np.array([m[6] for m in MODELS]) / sum(m[6] for m in MODELS)

# Exotic leathers, Birkin and Kelly only: (band low, band high, mix weight)
EXOTIC = {
    "Ostrich": (70000, 95000, 0.35),      # cheapest exotic, slowest mover
    "Lizard": (95000, 130000, 0.35),      # moderate
    "Alligator": (125000, 160000, 0.10),
    "Crocodile": (145000, 175000, 0.20),  # top of the range
}
STD_LEATHERS = ["Togo", "Epsom", "Swift", "Chevre", "Box"]
STD_W = np.array([0.30, 0.30, 0.12, 0.14, 0.14])
LEATHER_MULT = {"Togo": 1.00, "Epsom": 1.00, "Swift": 0.97, "Chevre": 1.02, "Box": 1.04}

COLOR_FAMILIES = {
    "Reds": ["Rouge Hermes", "Rouge Vif", "Vermillion", "Brique", "Braise", "Rouge Garance", "Rouge Moyen",
             "Rouge Jaipur", "Rouge Tomate", "Rouge Casaque", "Rouge Piment", "Bougainvillea"],
    "Blues": ["Blue Jean", "Indigo", "Ink", "Thalassa", "Blue Roi", "Turquoise", "Brighton Blue", "Navy",
              "Blue Saphir", "Aqua", "Petrol", "Midnight Blue", "Cobalt Blue", "Blue France"],
    "Greens": ["Vert Anis", "Vert Cru", "Vert Amande", "Vert Jasmin", "Vert Olive", "Vert Fonce", "Vert Pale",
               "Kiwi", "Vert Pelouse", "Cactus", "Bambou", "Pistache", "Vert Bronze", "Vert Chartreuse",
               "Apple Green"],
    "Oranges": ["Classic Orange", "Potiron", "Tangerine", "Orange Poppy", "Jaune d'Or"],
    "Purples and Pinks": ["Raisin", "Violet", "Violine", "Myosotis", "Cassis", "Lilac", "Iris", "Prune",
                          "Cyclamen", "Fuchsia", "Rose Shocking", "Rose Lipstick", "Framboise", "Rose Tea",
                          "Rose Tyrien"],
    "Yellows/Beige": ["Jaune", "Saffron", "Beige/Rose"],
    "Browns": ["Marron Fonce", "Chocolate", "Kraft", "Etrusque", "Miel", "Etoupe", "Moka", "Ebene", "Cafe",
               "Caramel", "Natural Sable", "Cognac", "Natural", "Cocon", "Tabac", "Cigare", "Toundra", "Gold"],
    "Blacks/Greys": ["Noir", "Noir Nacre", "Graphite", "Vert Gris", "Paris Grey", "Etoupe Grey", "Gris Pale",
                     "Etain"],
}
COLOR_TO_FAMILY = {c: f for f, cs in COLOR_FAMILIES.items() for c in cs}
BASIC_COLORS = ["Noir", "Gold", "Etoupe", "Graphite", "Gris Pale", "Natural", "Etain", "Cognac"]
RARE_COLORS = ["Rouge Casaque", "Vert Chartreuse", "Blue Saphir", "Rose Tyrien", "Bougainvillea",
               "Rouge Garance", "Cassis", "Vert Bronze", "Noir Nacre"]
MID_COLORS = [c for c in COLOR_TO_FAMILY if c not in BASIC_COLORS and c not in RARE_COLORS]
COLOR_TIER_P = [0.35, 0.50, 0.15]       # basic, mid, rare
COLOR_TIER_MULT = {"basic": 1.00, "mid": 1.04, "rare": 1.12}

HARDWARE = ["Gold", "Palladium", "Rose Gold", "Electrum", "Permabrass", "White Gold"]
HARDWARE_P = [0.35, 0.25, 0.10, 0.05, 0.15, 0.10]
HARDWARE_MULT = {"Permabrass": 0.94}

CONDITIONS = ["New", "Full Set", "Excellent Pre Loved", "Pre Loved"]
CONDITION_P = [0.40, 0.35, 0.15, 0.10]        # box fresh (New + Full Set) is about 75% of pieces
CONDITION_MULT = {"New": 1.00, "Full Set": 0.98, "Excellent Pre Loved": 0.92, "Pre Loved": 0.85}

# Manually inserted special-model records (fictional names). Applied to random matching pieces.
MANUAL_SPECIALS = [
    dict(model_category="Birkin", model="25", count=2, special_model_name="Atelier Gradient (Demo)",
         notes="Manual insert: fictional special edition for testing special-model handling"),
    dict(model_category="Kelly", model="Mini", count=1, special_model_name="Atelier Painted (Demo)",
         notes="Manual insert: fictional special edition"),
    dict(model_category="Constance", model="Micro", count=1, special_model_name="Atelier Exhibition (Demo)",
         notes="Manual insert: fictional one-off piece"),
]

PAYMENT_TYPES = ("Credit Card", "Wire Transfer")
DELIVERY_TYPES = ("None", "Local Delivery", "Shipping Delivery")
STAGES = ["Contract Completed", "Authentication", "Customer Paid", "Available to Stock"]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def day_to_date(d: int) -> date:
    return DATA_START + timedelta(days=int(d))


def make_phone(code: str, rng: np.random.Generator) -> str:
    if code in ("US", "CA"):
        return "+1555" + str(int(rng.integers(1000000, 9999999)))   # reserved 555 range
    digits_needed, lead = PHONE_RULE[code]
    rest = "".join(str(int(x)) for x in rng.integers(0, 10, size=digits_needed - len(lead)))
    return DIAL[code] + lead + rest


def make_postal(code: str, rng: np.random.Generator) -> str:
    def digits(k):
        return "".join(str(int(x)) for x in rng.integers(0, 10, size=k))

    def letters(k):
        return "".join(chr(ord("A") + int(x)) for x in rng.integers(0, 26, size=k))

    if code in ("US", "MX", "FR", "IT", "DE", "KR"):
        return digits(5)
    if code == "CA":
        return f"{letters(1)}{digits(1)}{letters(1)} {digits(1)}{letters(1)}{digits(1)}"
    if code == "GB":
        return f"{letters(2)}{digits(1)} {digits(1)}{letters(2)}"
    if code == "CH":
        return digits(4)
    if code == "MC":
        return "98000"
    if code == "JP":
        return f"{digits(3)}-{digits(4)}"
    if code == "SG":
        return digits(6)
    if code == "AU":
        return digits(4)
    if code == "BR":
        return f"{digits(5)}-{digits(3)}"
    raise ValueError(code)


def make_birthday(rng: np.random.Generator) -> str:
    month = int(rng.integers(1, 13))
    day = int(rng.integers(1, 29))           # 1..28 keeps every month valid
    return f"{day:02d}/{month:02d}"


# ----------------------------------------------------------------------------
# Reference tables
# ----------------------------------------------------------------------------
def build_calendar() -> pd.DataFrame:
    days = pd.date_range("2016-01-01", "2027-12-31", freq="D")
    rows = []
    for ts in days:
        m = ts.month
        fiscal_year = ts.year + (1 if m >= 7 else 0)       # FY named by the year it ends (FY2026 = Jul 2025-Jun 2026)
        fiscal_month = (m - 7) % 12 + 1                     # 1 = July
        fiscal_quarter = (fiscal_month - 1) // 3 + 1        # Q1 = Jul-Sep ... Q4 = Apr-Jun
        rows.append(dict(
            calendar_date=ts.date(),
            calendar_year=ts.year,
            calendar_month_number=m,
            calendar_month=ts.strftime("%B"),
            fiscal_year=fiscal_year,
            fiscal_quarter=f"Q{fiscal_quarter}",
            fiscal_month_number=fiscal_month,
            fiscal_month=ts.strftime("%B"),
        ))
    return pd.DataFrame(rows)


def build_locations() -> pd.DataFrame:
    rows = []
    for loc in LOCATIONS:
        rows.append({**loc, "close_date": None})
    return pd.DataFrame(rows)[["location_id", "location_name", "location_address", "city", "state_province",
                               "zip_postal_code", "country", "location_phone", "open_date", "close_date"]]


# ----------------------------------------------------------------------------
# Simulation: day-by-day purchases (buy-ins) and sales
# ----------------------------------------------------------------------------
def simulate(rng: np.random.Generator) -> dict:
    pools = {s: [] for s in STORE_IDS}       # item indices available to sell, per stock location
    pending = {s: [] for s in STORE_IDS}     # (stock_day, item) waiting for the pipeline to finish
    item = {k: [] for k in ("stock_loc", "purch_day", "auth_off", "paid_off", "stock_day",
                            "sale_day", "sale_loc")}

    def add_item(stock_loc: str, purch_day: int) -> int:
        c1 = int(rng.integers(1, 3))         # contract -> authentication
        c2 = int(rng.integers(1, 4))         # authentication -> customer paid
        c3 = int(rng.integers(1, 4))         # customer paid -> available to stock
        item["stock_loc"].append(stock_loc)
        item["purch_day"].append(purch_day)
        item["auth_off"].append(c1)
        item["paid_off"].append(c1 + c2)
        item["stock_day"].append(purch_day + c1 + c2 + c3)
        item["sale_day"].append(-1)
        item["sale_loc"].append("")
        return len(item["stock_loc"]) - 1

    # Opening stock: bought before the first sales day, so it is available on day 0.
    for s in STORE_IDS:
        qty = WEEKLY[s] * 6 + (WEEKLY[ONLINE_ID] * 6 if s == "LOC-NYC" else 0)   # about six weeks of demand
        for _ in range(qty):
            idx = add_item(s, -int(rng.integers(10, OPENING_STOCK_LOOKBACK + 1)))
            pools[s].append(idx)

    for d in range(N_DAYS):
        day = day_to_date(d)
        for s in STORE_IDS:                  # pipeline finished: move stock into the sellable pool
            still = []
            for stock_day, idx in pending[s]:
                if stock_day <= d:
                    pools[s].append(idx)
                else:
                    still.append((stock_day, idx))
            pending[s] = still

        growth = (1 + GROWTH) ** (d / 365.25)
        mult = SEASON[day.month] * WEEKDAY[day.weekday()] * growth
        lam = {loc: WEEKLY[loc] / 7.0 * mult for loc in LOC_ORDER}

        for loc in LOC_ORDER:                # sales
            pool = pools[STOCK_FOR[loc]]
            for _ in range(int(rng.poisson(lam[loc]))):
                if not pool:
                    break
                j = int(rng.integers(len(pool)))
                idx = pool[j]
                pool[j] = pool[-1]
                pool.pop()
                item["sale_day"][idx] = d
                item["sale_loc"][idx] = loc

        for s in STORE_IDS:                  # buy-ins, sized to demand and steered to a target stock level
            demand = lam[s] + (lam[ONLINE_ID] if s == "LOC-NYC" else 0.0)
            target = demand * 7 * TARGET_WEEKS_ON_HAND
            on_hand = len(pools[s]) + len(pending[s])
            ratio = float(np.clip(PURCHASE_OVERSUPPLY + 0.5 * (target - on_hand) / target, 0.5, 1.5))
            for _ in range(int(rng.poisson(demand * ratio))):
                idx = add_item(s, d)
                pending[s].append((item["stock_day"][idx], idx))

    return item


# ----------------------------------------------------------------------------
# Build the warehouse tables
# ----------------------------------------------------------------------------
def build_warehouse(seed: int, verbose: bool = True) -> dict:
    rng = np.random.default_rng(seed)
    t0 = time.time()
    sim = simulate(rng)
    n_items = len(sim["stock_loc"])

    # Inventory IDs follow purchase order (so INV/PUR numbers rise with time).
    order = sorted(range(n_items), key=lambda i: (sim["purch_day"][i], i))
    for key in sim:
        sim[key] = [sim[key][i] for i in order]
    sold_mask = np.array([d >= 0 for d in sim["sale_day"]])
    sale_day = np.array(sim["sale_day"])
    purch_day = np.array(sim["purch_day"])
    stock_day = np.array(sim["stock_day"])
    auth_off = np.array(sim["auth_off"])
    paid_off = np.array(sim["paid_off"])
    stock_loc = np.array(sim["stock_loc"])

    inv_ids = np.array([f"INV-{i + 1:06d}" for i in range(n_items)])
    pur_ids = np.array([f"PUR-{i + 1:06d}" for i in range(n_items)])

    # Sales in date order.
    sold_idx = np.nonzero(sold_mask)[0]
    sold_idx = sold_idx[np.lexsort((sold_idx, sale_day[sold_idx]))]
    n_sales = len(sold_idx)
    sale_ids = np.array([f"SAL-{i + 1:06d}" for i in range(n_sales)])
    item_sale_id = np.full(n_items, None, dtype=object)
    item_sale_id[sold_idx] = sale_ids

    # ---- customers: draw buyers (sales) and sellers (purchases) from one repeat-customer pool
    n_cust = 6000
    weights = rng.lognormal(0.0, 0.6, size=n_cust)
    p_cust = weights / weights.sum()
    seller = rng.choice(n_cust, size=n_items, p=p_cust)
    buyer = rng.choice(n_cust, size=n_sales, p=p_cust)

    used = np.unique(np.concatenate([seller, buyer]))
    first_event = {}
    for i in range(n_items):
        c = seller[i]
        first_event[c] = min(first_event.get(c, 10 ** 9), purch_day[i])
    for k, i in enumerate(sold_idx):
        c = buyer[k]
        first_event[c] = min(first_event.get(c, 10 ** 9), sale_day[i])

    cust_rows = []
    cw = np.array([c[2] for c in COUNTRY_TABLE]); cw = cw / cw.sum()
    for c in range(n_cust):
        if c not in first_event:
            continue
        ci = int(rng.choice(len(COUNTRY_TABLE), p=cw))
        code, cname, _, cities = COUNTRY_TABLE[ci]
        city, region, metro = cities[int(rng.integers(len(cities)))]
        first_day = first_event[c]
        create = day_to_date(first_day) - timedelta(days=int(rng.integers(30, 901)))
        cust_rows.append(dict(
            _key=c,
            profile_create_date=create,
            customer_id="",
            customer_name=f"{FIRST_NAMES[int(rng.integers(len(FIRST_NAMES)))]} "
                          f"{LAST_NAMES[int(rng.integers(len(LAST_NAMES)))]}",
            customer_address=f"{int(rng.integers(1, 3000))} {STREETS[int(rng.integers(len(STREETS)))]} "
                             f"{SUFFIXES[int(rng.integers(len(SUFFIXES)))]}",
            customer_city=city,
            state_province=region,
            zip_postal_code=make_postal(code, rng),
            country=cname,
            country_code=code,
            birthday_ddmm=make_birthday(rng),
            customer_phone=make_phone(code, rng),
            _metro=metro,
        ))
    cust_rows.sort(key=lambda r: (r["profile_create_date"], r["_key"]))
    cust_id_of = {}
    for k, r in enumerate(cust_rows):
        cust_id_of[r["_key"]] = f"CUS-{k + 1:06d}"
    metro_of = {r["_key"]: r["_metro"] for r in cust_rows}
    intl_of = {r["_key"]: r["country_code"] != "US" for r in cust_rows}
    for r in cust_rows:
        r["customer_id"] = cust_id_of[r["_key"]]
    customer_cols = ["customer_id", "profile_create_date", "customer_name", "customer_address",
                     "customer_city", "state_province", "zip_postal_code", "country", "country_code",
                     "birthday_ddmm", "customer_phone"]
    customers = pd.DataFrame(cust_rows)[customer_cols]

    # ---- product detail: one record per inventory item
    prod_rows = []
    model_idx = rng.choice(len(MODELS), size=n_items, p=MODEL_MIX)
    purchase_price = np.zeros(n_items)
    market_value = np.zeros(n_items)
    sale_price = np.zeros(n_items)
    for i in range(n_items):
        cat, model, mid, band_lo, band_hi, pos, _ = MODELS[model_idx[i]]
        pur_year = day_to_date(purch_day[i]).year
        is_bk = cat in ("Birkin", "Kelly")

        # model year: mostly the purchase year, sometimes a year or more older (never worth more)
        u = rng.random()
        if u < 0.80:
            model_year = pur_year
        elif u < 0.92:
            model_year = pur_year - 1
        else:
            model_year = int(rng.integers(1990, pur_year - 1))
        vintage = model_year < pur_year - 1

        # sellier / retourne
        if is_bk:
            if cat == "Birkin" and model == "25":
                sellier = rng.choice(["S", "R", "O"], p=[0.15, 0.75, 0.10])   # Sellier 25 is discontinued and rare
            else:
                sellier = rng.choice(["S", "R", "O"], p=[0.80, 0.15, 0.05])
        else:
            sellier = "O"

        hardware = rng.choice(HARDWARE, p=HARDWARE_P)
        verso = bool(rng.random() < 0.06)
        condition = rng.choice(CONDITIONS, p=CONDITION_P)

        # color
        tier = rng.choice(["basic", "mid", "rare"], p=COLOR_TIER_P)
        if tier == "basic":
            color = BASIC_COLORS[int(rng.integers(len(BASIC_COLORS)))]
        elif tier == "rare":
            color = RARE_COLORS[int(rng.integers(len(RARE_COLORS)))]
        else:
            color = MID_COLORS[int(rng.integers(len(MID_COLORS)))]

        # leather + market value
        exotic = is_bk and rng.random() < EXOTIC_SHARE
        if exotic:
            names = list(EXOTIC)
            w = np.array([EXOTIC[n][2] for n in names])
            leather = names[int(rng.choice(len(names), p=w / w.sum()))]
            leather_type = "Exotic"
            cites = "Y" if rng.random() < 0.70 else "N"
            xlo, xhi, _ = EXOTIC[leather]
            frac = float(np.clip(0.15 + 0.70 * pos + rng.normal(0, 0.08), 0.0, 1.0))
            market = xlo + (xhi - xlo) * frac
            lo_b, hi_b = xlo, xhi
        else:
            leather = STD_LEATHERS[int(rng.choice(len(STD_LEATHERS), p=STD_W))]
            leather_type = "Standard"
            cites = "N/A"
            market = mid * rng.uniform(0.92, 1.08) * LEATHER_MULT[leather] * COLOR_TIER_MULT[tier]
            if cat == "Birkin" and model == "25" and sellier == "S":
                market = rng.uniform(*SELLIER_RARE_PRICE)
            lo_b, hi_b = band_lo, band_hi

        mods = CONDITION_MULT[condition]
        mods *= HARDWARE_MULT.get(hardware, 1.0)
        mods *= 1.08 if verso else 1.0
        mods *= 0.92 if vintage else 1.0
        market = float(np.clip(market * mods, lo_b, hi_b))
        market = round(market, -2)

        # Buy-in = 60% of market value. Sales carry a small negotiated discount on about 35% of pieces,
        # so realised margin lands near 40% but not exactly on it.
        purchase_price[i] = round(market * BUYIN_RATIO, -1)
        market_value[i] = market
        disc = 0.0 if rng.random() < 0.65 else float(rng.uniform(0.005, 0.04))
        sale_price[i] = round(market * (1 - disc), -1)

        prod_rows.append(dict(
            inventory_id=inv_ids[i],
            brand="Hermes",
            model_category=cat,
            model=model,
            special_model_name="",
            model_year=model_year,
            color=color,
            color_family=COLOR_TO_FAMILY[color],
            leather=leather,
            leather_type=leather_type,
            has_cites=cites,
            hardware=hardware,
            sellier_retourne=sellier,
            store_location=STORE_LABEL[sim["stock_loc"][i]],
            is_verso=verso,
            condition=condition,
            notes="",
        ))

    # manual special-edition records
    for spec in MANUAL_SPECIALS:
        cands = [k for k, r in enumerate(prod_rows)
                 if r["model_category"] == spec["model_category"] and r["model"] == spec["model"]
                 and r["special_model_name"] == ""]
        if not cands:
            continue
        for k in rng.choice(cands, size=min(spec["count"], len(cands)), replace=False):
            prod_rows[k]["special_model_name"] = spec["special_model_name"]
            prod_rows[k]["notes"] = spec["notes"]
    product_detail = pd.DataFrame(prod_rows)

    # ---- purchasing
    stage_at_end = []
    for i in range(n_items):
        p = purch_day[i]
        if stock_day[i] <= N_DAYS - 1:
            stage_at_end.append("Available to Stock")
        elif p + paid_off[i] <= N_DAYS - 1:
            stage_at_end.append("Customer Paid")
        elif p + auth_off[i] <= N_DAYS - 1:
            stage_at_end.append("Authentication")
        else:
            stage_at_end.append("Contract Completed")
    seller_ids = [cust_id_of[c] for c in seller]
    purchasing = pd.DataFrame(dict(
        purchase_id=pur_ids,
        inventory_id=inv_ids,
        purchase_price=purchase_price,
        customer_id=seller_ids,
        location_id=stock_loc,
        purchase_date=[day_to_date(d) for d in purch_day],
        stage=stage_at_end,
    ))

    # ---- sales
    sale_rows = []
    for k, i in enumerate(sold_idx):
        loc = sim["sale_loc"][i]
        b = buyer[k]
        buyer_metro = metro_of[b]
        intl = intl_of[b]
        if loc == ONLINE_ID:
            delivery = "Shipping Delivery"
        elif buyer_metro == loc:
            delivery = "Local Delivery" if rng.random() < 0.45 else "None"
        else:
            delivery = "Shipping Delivery" if rng.random() < 0.35 else "None"
        price = float(sale_price[i])
        wire_p = 0.08 + (0.32 if price >= 100000 else 0.0) + (0.12 if intl else 0.0)
        payment = "Wire Transfer" if rng.random() < min(wire_p, 0.60) else "Credit Card"
        sale_rows.append(dict(
            sale_id=sale_ids[k],
            inventory_id=inv_ids[i],
            customer_id=cust_id_of[b],
            location_id=loc,
            sale_date=day_to_date(sale_day[i]),
            sales_price=price,
            payment_type=payment,
            delivery_type=delivery,
        ))
    sales = pd.DataFrame(sale_rows)

    # ---- inventory: daily snapshot of every item on hand
    # An item is on hand from the day it reaches the floor until the day it sells (sale day included).
    snap_start = np.maximum(stock_day, 0)
    snap_end = np.where(sold_mask, sale_day, N_DAYS - 1)
    length = np.maximum(snap_end - snap_start + 1, 0)
    total = int(length.sum())
    item_of_row = np.repeat(np.arange(n_items), length)
    starts = np.cumsum(length) - length
    offset = np.arange(total) - np.repeat(starts, length)
    snap_day = snap_start[item_of_row] + offset
    all_dates = np.array([day_to_date(d) for d in range(N_DAYS)], dtype=object)
    sold_today = sold_mask[item_of_row] & (snap_day == sale_day[item_of_row])
    inventory = pd.DataFrame(dict(
        snapshot_date=all_dates[snap_day],
        inventory_id=inv_ids[item_of_row],
        purchase_id=pur_ids[item_of_row],
        sale_id=np.where(sold_today, item_sale_id[item_of_row], None),
        location_id=stock_loc[item_of_row],
    ))

    if verbose:
        print(f"  simulated {n_items:,} items, {n_sales:,} sales, {total:,} snapshot rows "
              f"in {time.time() - t0:.1f}s")

    return dict(
        calendar=build_calendar(),
        locations=build_locations(),
        customers=customers,
        purchasing=purchasing,
        inventory=inventory,
        product_detail=product_detail,
        sales=sales,
    )


# ----------------------------------------------------------------------------
# Output and checks
# ----------------------------------------------------------------------------
DATE_COLUMNS = {
    "calendar": ["calendar_date"],
    "locations": ["open_date", "close_date"],
    "customers": ["profile_create_date"],
    "purchasing": ["purchase_date"],
    "inventory": ["snapshot_date"],
    "sales": ["sale_date"],
}
PRIMARY_KEYS = {
    "calendar": ["calendar_date"],
    "locations": ["location_id"],
    "customers": ["customer_id"],
    "purchasing": ["purchase_id"],
    "inventory": ["snapshot_date", "inventory_id"],
    "product_detail": ["inventory_id"],
    "sales": ["sale_id"],
}


def write_csv(tables: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(os.path.join(out_dir, f"{name}.csv"), index=False)


def write_duckdb(tables: dict, path: str) -> None:
    import duckdb
    if os.path.exists(path):
        os.remove(path)
    con = duckdb.connect(path)
    for name, df in tables.items():
        con.register("tmp_df", df)
        cols = []
        for c in df.columns:
            if c in DATE_COLUMNS.get(name, []):
                cols.append(f"CAST({c} AS DATE) AS {c}")
            else:
                cols.append(c)
        con.execute(f"CREATE TABLE {name} AS SELECT {', '.join(cols)} FROM tmp_df")
        con.unregister("tmp_df")
    con.close()


def run_checks(t: dict) -> list:
    issues = []
    customers = set(t["customers"]["customer_id"])
    locations = set(t["locations"]["location_id"])
    purchases = t["purchasing"]
    inv_ids = set(purchases["inventory_id"])
    pur_ids = set(purchases["purchase_id"])

    if not set(purchases["customer_id"]) <= customers: issues.append("purchasing.customer_id not in customers")
    if not set(t["sales"]["customer_id"]) <= customers: issues.append("sales.customer_id not in customers")
    if not set(t["sales"]["location_id"]) <= locations: issues.append("sales.location_id not in locations")
    if not set(purchases["location_id"]) <= locations: issues.append("purchasing.location_id not in locations")
    if not set(t["sales"]["inventory_id"]) <= inv_ids: issues.append("sales.inventory_id not in purchasing")
    if purchases["inventory_id"].duplicated().any(): issues.append("inventory_id not unique in purchasing")
    if purchases["purchase_id"].duplicated().any(): issues.append("purchase_id not unique")
    if set(t["product_detail"]["inventory_id"]) != inv_ids: issues.append("product_detail does not match purchasing")
    inv = t["inventory"]
    if not set(inv["purchase_id"]) <= pur_ids: issues.append("inventory.purchase_id not in purchasing")
    if t["sales"]["sale_id"].duplicated().any(): issues.append("sale_id not unique")

    sold_inv = set(t["sales"]["inventory_id"])
    flagged = set(inv.loc[inv["sale_id"].notna(), "inventory_id"])
    if flagged != sold_inv: issues.append("inventory sale_id flags do not match sales")

    merged = t["sales"].merge(purchases[["inventory_id", "purchase_price"]], on="inventory_id")
    if (merged["sales_price"] <= merged["purchase_price"]).any(): issues.append("a sale is at or below buy-in")
    margin = 1 - merged["purchase_price"] / merged["sales_price"]
    if not (0.36 <= margin.median() <= 0.41): issues.append(f"median margin {margin.median():.3f} off 40%")

    for name, df in t.items():
        nullable = {"inventory": ["sale_id"], "locations": ["close_date"]}.get(name, [])
        bad = [c for c in df.columns if c not in nullable and df[c].isna().any()]
        if bad: issues.append(f"{name}: unexpected nulls in {bad}")
    return issues


def print_summary(t: dict) -> None:
    sales = t["sales"].copy()
    sales["year"] = pd.to_datetime(sales["sale_date"]).dt.year
    sales["fy"] = pd.to_datetime(sales["sale_date"]).dt.year + (pd.to_datetime(sales["sale_date"]).dt.month >= 7)
    print("\nRows per table:")
    for name, df in t.items():
        print(f"  {name:<16}{len(df):>12,}")
    print("\nSales per location (count / revenue / avg per week):")
    weeks = (DATA_END - DATA_START).days / 7
    for loc, g in sales.groupby("location_id"):
        print(f"  {loc:<10}{len(g):>7,}  ${g['sales_price'].sum() / 1e6:>8.1f}M  "
              f"{len(g) / weeks:>5.1f}/wk")
    print("\nRevenue by fiscal year (USD millions, all locations):")
    fy = sales.groupby("fy")["sales_price"].sum() / 1e6
    for y, v in fy.items():
        print(f"  FY{y}: ${v:,.1f}M")
    margin = t["sales"].merge(t["purchasing"][["inventory_id", "purchase_price"]], on="inventory_id")
    margin = (1 - margin["purchase_price"] / margin["sales_price"]).median()
    print(f"\nMedian realised margin on sales: {margin:.1%}")
    print(f"Box-fresh share of sales (New + Full Set): "
          f"{t['product_detail'].merge(t['sales'][['inventory_id']], on='inventory_id')['condition'].isin(['New', 'Full Set']).mean():.1%}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate the Atelier Row synthetic warehouse.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="atelier_row_data", help="output folder (relative to this script)")
    ap.add_argument("--no-duckdb", action="store_true", help="write CSVs only")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, args.out)
    print(f"Generating Atelier Row data (seed={args.seed}, {DATA_START} to {DATA_END})")
    tables = build_warehouse(args.seed)

    issues = run_checks(tables)
    print("\nChecks:", "all passed" if not issues else "")
    for msg in issues:
        print("  FAIL:", msg)

    write_csv(tables, out_dir)
    print(f"\nCSV written to {out_dir}")
    if not args.no_duckdb:
        db_path = os.path.join(out_dir, "atelier_row.duckdb")
        write_duckdb(tables, db_path)
        print(f"DuckDB written to {db_path}")
    print_summary(tables)


if __name__ == "__main__":
    main()

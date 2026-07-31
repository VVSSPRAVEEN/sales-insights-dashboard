"""Generate synthetic sales data (1M+ rows) for the Sales Performance Dashboard.

Deterministic (seeded) so results are reproducible. Includes a realistic
22% revenue drop in Q2 2023 and a mild yearly growth trend.

Usage:
    python scripts/generate_data.py
"""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

REGIONS = [f"Region {i:02d}" for i in range(1, 56)]  # 55 regions

CATEGORIES = {
    "Electronics": ["Laptop", "Smartphone", "Tablet", "Headphones"],
    "Apparel": ["T-Shirt", "Jeans", "Jacket", "Sneakers"],
    "Home": ["Sofa", "Lamp", "Curtains", "Blender"],
    "Grocery": ["Coffee", "Rice", "Milk Powder", "Cooking Oil"],
    "Beauty": ["Serum", "Shampoo", "Lipstick", "Moisturizer"],
    "Sports": ["Dumbbells", "Yoga Mat", "Treadmill", "Water Bottle"],
    "Books": ["Novel", "Textbook", "Journal", "Cookbook"],
    "Toys": ["Action Figure", "Puzzle", "Board Game", "Building Blocks"],
}
CATEGORY_NAMES = list(CATEGORIES)
PRODUCT_NAMES = list(CATEGORIES.values())
BASE_PRICE = np.array([500, 60, 150, 20, 35, 80, 25, 40], dtype=float)

SEGMENTS = ["Enterprise", "SMB", "Retail", "Wholesale"]
CHANNELS = ["Online Store", "Retail", "Wholesale"]

START = pd.Timestamp("2022-01-01")
N_DAYS = 1096  # 2022-01-01 .. 2024-12-31


def generate_sales(n: int = 1_000_000, seed: int = 42) -> pd.DataFrame:
    """Generate a deterministic synthetic sales dataframe with n rows."""
    rng = np.random.default_rng(seed)

    date = START + pd.to_timedelta(rng.integers(0, N_DAYS, n), unit="D")
    cat_idx = rng.integers(0, len(CATEGORY_NAMES), n)
    prod_idx = rng.integers(0, 4, n)

    unit_price = (BASE_PRICE[cat_idx] * rng.uniform(0.7, 1.4, n)).round(2)
    units = rng.integers(1, 21, n)

    # seasonal + trend factor
    month = date.month.to_numpy()
    year = date.year.to_numpy()
    factor = np.ones(n)
    factor *= 1 + 0.05 * (year - 2022)          # ~5% yearly growth trend
    factor[month == 11] *= 1.05                  # November bump
    factor[month == 12] *= 1.15                  # December bump
    factor[(year == 2023) & np.isin(month, [4, 5, 6])] *= 0.74  # Q2 2023 dip (-22%)

    revenue = (units * unit_price * factor.round(3)).round(2)

    df = pd.DataFrame(
        {
            "order_id": np.char.add("ORD-", np.char.zfill(np.arange(n).astype(str), 8)),
            "date": date,
            "region": rng.choice(REGIONS, n),
            "store_id": rng.integers(1, 601, n),
            "category": np.array(CATEGORY_NAMES)[cat_idx],
            "product": np.array([PRODUCT_NAMES[c][i] for c, i in zip(cat_idx, prod_idx)]),
            "units": units,
            "unit_price": unit_price,
            "revenue": revenue,
            "customer_segment": rng.choice(SEGMENTS, n),
            "channel": rng.choice(CHANNELS, n),
            "seasonal_factor": factor.round(3),
        }
    )
    return df


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    full = DATA_DIR / "sales_1m.csv.gz"
    sample = DATA_DIR / "sample_sales.csv"

    if not full.exists():
        print("Generating 1,000,000 sales rows ...")
        df = generate_sales()
        df.to_csv(full, index=False, compression="gzip")
        print(f"Saved full dataset -> {full} ({full.stat().st_size / 1e6:.1f} MB)")
    else:
        print(f"Full dataset already exists -> {full}")

    if not sample.exists():
        print("Writing 5,000-row sample ...")
        df = pd.read_csv(full, parse_dates=["date"])
        df.sample(5_000, random_state=42).sort_values("date").to_csv(sample, index=False)
        print(f"Saved sample -> {sample}")


if __name__ == "__main__":
    main()

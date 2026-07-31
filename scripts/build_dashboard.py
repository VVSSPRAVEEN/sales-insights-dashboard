"""Build the Sales Performance Dashboard panels (matplotlib PNGs).

Reads data/sales_1m.csv.gz (falls back to data/sample_sales.csv) and renders
4 dashboard panels into docs/screenshots/:

    1. dashboard_kpis.png          - KPI cards (revenue, orders, AOV, YoY)
    2. dashboard_revenue_trend.png - monthly revenue with the Q2 2023 drop
    3. dashboard_regions.png       - top regions by revenue
    4. dashboard_products.png      - top products + channel split

Usage:
    python scripts/build_dashboard.py
"""
from __future__ import annotations

import pathlib

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

matplotlib.use("Agg")

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "docs" / "screenshots"

# Template-inspired palette
NAVY = "#1A2C47"
BLUE = "#0080FF"
GREEN = "#4C9F70"
RED = "#D9534F"
CANVAS = "#F5F7FA"
GRID = "#D9DEE7"

DPI = 170
FONT = "DejaVu Sans"


def load_sales() -> pd.DataFrame:
    full = DATA_DIR / "sales_1m.csv.gz"
    sample = DATA_DIR / "sample_sales.csv"
    path = full if full.exists() else sample
    df = pd.read_csv(path, parse_dates=["date"])
    print(f"Loaded {len(df):,} rows from {path.name}")
    return df


def compute_kpis(df: pd.DataFrame) -> dict:
    total_revenue = df.revenue.sum()
    orders = len(df)
    aov = total_revenue / orders
    rev = df.groupby(df.date.dt.year).revenue.sum()
    yoy = (rev.get(2024, 0) / rev.get(2023, 0) - 1) * 100 if rev.get(2023, 0) else 0.0
    return {
        "total_revenue": total_revenue,
        "orders": orders,
        "aov": aov,
        "yoy": yoy,
    }


def find_drop(df: pd.DataFrame) -> dict:
    """Revenue change of Q2 2023 vs Q2 2022 (the flagged drop)."""
    q = df[df.date.dt.quarter == 2]
    q23 = q[q.date.dt.year == 2023].revenue.sum()
    q22 = q[q.date.dt.year == 2022].revenue.sum()
    return {"year": 2023, "quarter": 2, "pct": (q23 / q22 - 1) * 100 if q22 else 0.0}


def monthly_revenue(df: pd.DataFrame) -> pd.Series:
    return df.set_index("date").revenue.resample("MS").sum()


def _fmt_money(v: float) -> str:
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v / 1e3:.0f}K"


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor("white")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.6)
    ax.tick_params(colors="#5A6472", labelsize=10)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1e6:.0f}M"))


def render_kpis(kpis: dict, path: pathlib.Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 2.2), dpi=DPI, facecolor=CANVAS)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 10)
    ax.axis("off")
    cards = [
        ("TOTAL REVENUE", _fmt_money(kpis["total_revenue"]), "", NAVY),
        ("TOTAL ORDERS", f"{kpis['orders']:,}", "", NAVY),
        ("AVG ORDER VALUE", f"${kpis['aov']:.2f}", "", NAVY),
        ("YoY GROWTH (2024)", f"{kpis['yoy']:+.1f}%", kpis["yoy"], GREEN if kpis["yoy"] >= 0 else RED),
    ]
    for i, (label, value, delta, color) in enumerate(cards):
        x = 2 + i * 25
        ax.add_patch(
            FancyBboxPatch(
                (x, 1.0), 21, 8.0,
                boxstyle="round,pad=0.15,rounding_size=0.6",
                facecolor="white", edgecolor=GRID, linewidth=1.2,
            )
        )
        ax.text(x + 1.6, 7.4, label, fontsize=10, color="#5A6472", family=FONT)
        ax.text(x + 1.6, 4.0, value, fontsize=24, color=color, family=FONT, fontweight="bold")
        if delta:
            ax.text(x + 1.6, 2.1, f"{delta:+.1f}% vs PY", fontsize=10,
                    color=GREEN if delta >= 0 else RED, family=FONT)
    fig.savefig(path, bbox_inches="tight", facecolor=CANVAS)
    plt.close(fig)


def render_trend(df: pd.DataFrame, path: pathlib.Path) -> None:
    mr = monthly_revenue(df) / 1e6  # $M
    drop = find_drop(df)
    fig, ax = plt.subplots(figsize=(11, 5.2), dpi=DPI, facecolor="white")
    ax.fill_between(mr.index, mr.values, color=BLUE, alpha=0.15)
    ax.plot(mr.index, mr.values, color=BLUE, linewidth=2)
    ax.set_title("Monthly Revenue Trend (2022 - 2024)", fontsize=15, color=NAVY,
                 family=FONT, fontweight="bold", loc="left", pad=14)
    _style(ax)
    # annotate the drop
    dip_end = pd.Timestamp("2023-06-01")
    ax.annotate(
        f"Q2 2023: {drop['pct']:.1f}% vs Q2 2022",
        xy=(dip_end, mr.loc[dip_end]),
        xytext=(pd.Timestamp("2023-01-01"), mr.max() * 0.62),
        arrowprops=dict(arrowstyle="->", color=RED, lw=1.8),
        fontsize=12, color=RED, family=FONT, fontweight="bold",
    )
    # highlight the dip window
    dip = mr.loc[pd.Timestamp("2023-04-01"):pd.Timestamp("2023-06-30")]
    ax.plot(dip.index, dip.values, color=RED, linewidth=2.6)
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def render_regions(df: pd.DataFrame, path: pathlib.Path) -> None:
    top = df.groupby("region").revenue.sum().nlargest(10).sort_values() / 1e6
    colors = [NAVY] * len(top)
    colors[-1] = RED
    colors[0] = GREEN
    fig, ax = plt.subplots(figsize=(11, 5.2), dpi=DPI, facecolor="white")
    ax.barh(top.index, top.values, color=colors, height=0.62)
    ax.set_title("Top 10 Regions by Revenue", fontsize=15, color=NAVY,
                 family=FONT, fontweight="bold", loc="left", pad=14)
    _style(ax)
    ax.set_xlabel("Revenue ($M)", fontsize=11, color="#5A6472", family=FONT)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax.text(0.985, 0.04, "green = best  |  red = needs attention", transform=ax.transAxes,
            ha="right", fontsize=10, color="#5A6472", family=FONT)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def render_products(df: pd.DataFrame, path: pathlib.Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6), dpi=DPI, facecolor="white")
    top_products = df.groupby("product").revenue.sum().nlargest(8) / 1e6
    ax1.bar(range(len(top_products)), top_products.values, color=BLUE, width=0.6)
    ax1.set_xticks(range(len(top_products)))
    ax1.set_xticklabels(top_products.index, rotation=28, ha="right", fontsize=9, color="#5A6472")
    ax1.set_title("Top 8 Products by Revenue", fontsize=13, color=NAVY, family=FONT, fontweight="bold")
    _style(ax1)
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}"))

    by_channel = df.groupby("channel").revenue.sum()
    wedges, _, autotexts = ax2.pie(
        by_channel.values, labels=None, autopct="%1.0f%%", startangle=90,
        colors=[NAVY, BLUE, GREEN], pctdistance=0.72, textprops={"color": "white", "fontsize": 10},
    )
    ax2.legend(wedges, [f"{c}  ({v / 1e6:.0f}M)" for c, v in by_channel.items()],
               loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9, frameon=False)
    ax2.set_title("Revenue by Channel", fontsize=13, color=NAVY, family=FONT, fontweight="bold")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_sales()
    kpis = compute_kpis(df)
    drop = find_drop(df)

    print(f"Total revenue : {_fmt_money(kpis['total_revenue'])}")
    print(f"Orders        : {kpis['orders']:,}")
    print(f"AOV           : ${kpis['aov']:.2f}")
    print(f"YoY (2024)    : {kpis['yoy']:+.1f}%")
    print(f"Q2 2023 drop  : {drop['pct']:.1f}% vs Q2 2022")

    render_kpis(kpis, OUT_DIR / "dashboard_kpis.png")
    render_trend(df, OUT_DIR / "dashboard_revenue_trend.png")
    render_regions(df, OUT_DIR / "dashboard_regions.png")
    render_products(df, OUT_DIR / "dashboard_products.png")
    print(f"Screenshots saved to {OUT_DIR}")


if __name__ == "__main__":
    main()

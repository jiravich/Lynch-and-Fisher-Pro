import pandas as pd

from financial_engine import build_sec_financial_quality, cagr_from_series


def fact(values):
    rows = []
    for year, value in values.items():
        rows.append(
            {
                "fy": year,
                "fp": "FY",
                "form": "10-K",
                "filed": f"{year + 1}-02-01",
                "val": value,
                "uom": "USD",
            }
        )
    return pd.DataFrame(rows)


def test_cagr_uses_annual_years():
    values = {2022: 100.0, 2023: 110.0, 2024: 121.0, 2025: 133.1}
    assert round(cagr_from_series(values, 3), 6) == 0.1


def test_sec_fcf_and_margins_are_deterministic():
    snapshot = {
        "Revenue": fact({2023: 100.0, 2024: 120.0}),
        "Gross Profit": fact({2023: 60.0, 2024: 72.0}),
        "Operating Income": fact({2023: 20.0, 2024: 30.0}),
        "Net Income": fact({2023: 15.0, 2024: 24.0}),
        "Operating Cash Flow": fact({2023: 25.0, 2024: 40.0}),
        "Capital Expenditure": fact({2023: 5.0, 2024: 8.0}),
        "Assets": fact({2023: 200.0, 2024: 240.0}),
        "Liabilities": fact({2023: 80.0, 2024: 90.0}),
        "Cash": fact({2023: 50.0, 2024: 60.0}),
        "Debt Current": fact({2023: 5.0, 2024: 10.0}),
        "Debt Noncurrent": fact({2023: 20.0, 2024: 30.0}),
        "Diluted Shares": fact({2023: 100.0, 2024: 102.0}),
    }

    result = build_sec_financial_quality(snapshot)
    latest = result["latest"]

    assert latest["fiscal_year"] == 2024
    assert latest["revenue"] == 120.0
    assert latest["operating_margin"] == 0.25
    assert latest["fcf_margin"] == (40.0 - 8.0) / 120.0
    assert latest["debt"] == 40.0
    assert latest["cash"] == 60.0
    assert latest["net_debt"] == -20.0
    assert latest["debt_change_yoy"] == (40.0 / 25.0) - 1
    assert latest["diluted_shares_yoy"] == 0.02

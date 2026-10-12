"""Generate fake MDD PDFs for the demo and tests (python examples/make_samples.py)."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

HERE = Path(__file__).parent

BALANCED = {
    "title": "Sample Balanced Fund - Minimum Disclosure Document",
    "date": "30 September 2026",
    "preamble": [
        "Fund objective: long-term capital growth within Regulation 28 limits.",
        "Total Expense Ratio (TER) 1.21%   Transaction Costs (TC) 0.08%",
        "Performance (annualised)   1 year 11.4%   3 years 9.8%   5 years 10.2%",
    ],
    "allocation": [
        ("Local Equity", "38.50%"), ("Foreign Equity", "24.10%"),
        ("Local Bonds", "17.20%"), ("Listed Property", "4.30%"),
        ("Foreign Bonds", "6.40%"), ("Local Cash", "5.00%"),
        ("Foreign Cash", "2.50%"), ("Commodities", "2.00%"),
    ],
}

GLOBAL_FEEDER = {
    "title": "Sample Global Equity Feeder Fund - Fact Sheet",
    "date": "2026/09/30",
    "preamble": [
        "Benchmark: MSCI ACWI.  Annual management fee 1.00%",
        "Top holdings: Microsoft 5.2%  Apple 4.8%",
    ],
    "allocation": [
        ("Global Equities", "95,5 %"), ("Offshore Cash", "3,0 %"), ("Local Cash", "1,5 %"),
    ],
}


def make_pdf(path: Path, spec: dict, two_columns: bool = False) -> Path:
    c = canvas.Canvas(str(path), pagesize=A4)
    _, height = A4
    y = height - 60
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, spec["title"])
    y -= 22
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Date of issue: {spec['date']}")
    y -= 30
    for line in spec["preamble"]:
        c.drawString(50, y, line)
        y -= 16
    y -= 14
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Asset Allocation")
    y -= 20
    c.setFont("Helvetica", 10)
    items = spec["allocation"]
    if two_columns:
        half = (len(items) + 1) // 2
        rows = [(items[i], items[i + half] if i + half < len(items) else None) for i in range(half)]
        for left, right in rows:
            c.drawString(50, y, left[0]); c.drawRightString(250, y, left[1])
            if right:
                c.drawString(300, y, right[0]); c.drawRightString(500, y, right[1])
            y -= 16
    else:
        for label, value in items:
            c.drawString(50, y, label); c.drawRightString(250, y, value)
            y -= 16
    y -= 20
    c.drawString(50, y, "Risk profile: Moderate.  Max offshore exposure 45%.")
    c.save()
    return path


def make_all(out_dir: Path = HERE) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return [
        make_pdf(out_dir / "sample_balanced_mdd.pdf", BALANCED, two_columns=True),
        make_pdf(out_dir / "sample_global_equity_mdd.pdf", GLOBAL_FEEDER),
    ]


if __name__ == "__main__":
    for p in make_all():
        print(p)

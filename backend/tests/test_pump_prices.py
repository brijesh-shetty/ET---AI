"""Tests for the public-web pump-price scraper."""
from __future__ import annotations

from app.ingest import pump_prices


SAMPLE_HTML = """
<div class="city-fuel-summary">
  <a class="link">
    <span class="label">Petrol</span> <span class="value">₹ 111.21</span>
  </a>
  <a class="link">
    <span class="label">Diesel</span> <span class="value">₹ 97.83</span>
  </a>
  <a class="link">
    <span class="label">LPG</span> <span class="value">₹ 941.50</span>
  </a>
</div>
"""


def test_extracts_diesel():
    val = pump_prices._extract_price_after_label(SAMPLE_HTML, "Diesel")
    assert val == 97.83


def test_extracts_petrol():
    val = pump_prices._extract_price_after_label(SAMPLE_HTML, "Petrol")
    assert val == 111.21


def test_extracts_lpg():
    val = pump_prices._extract_price_after_label(SAMPLE_HTML, "LPG")
    assert val == 941.5


def test_missing_label_returns_none():
    val = pump_prices._extract_price_after_label(SAMPLE_HTML, "Kerosene")
    assert val is None


def test_extreme_value_rejected():
    """A 5-digit number isn't a plausible Indian pump price; reject."""
    html = '<span class="label">Petrol</span> <span class="value">₹ 9999.99</span>'
    val = pump_prices._extract_price_after_label(html, "Petrol")
    assert val is None


def test_missing_value_returns_none():
    html = '<span class="label">Petrol</span> <span>nothing here</span>'
    val = pump_prices._extract_price_after_label(html, "Petrol")
    assert val is None

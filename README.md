# Hotels PT Scraper (Playwright + Python)

Purpose: Scrape all hotels in Portugal from https://hotels-pt.com and export to CSV & Excel.

Features:
- Fields: Hotel Name, Region, Stars, Rating, Website (official only, blank if missing), Detail URL
- Excludes hostels, B&B, guesthouses, Airbnb-style listings
- Works with all languages (no language forcing)
- Saves `hotels_portugal.csv` and `hotels_portugal.xlsx`

## How to run inside GitHub Codespaces

1. Open this repo in **Codespaces**:
   - Click **Code → Create codespace on main**

2. In the Codespace terminal run these exact commands (copy/paste as a block):

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install
python scrape.py

# hotels-pt.com scraper (Playwright, Python)

Purpose: Scrape **all hotels in Portugal** from https://hotels-pt.com and export to Excel.
Fields: Hotel Name, Official Website (preferred), Region, Rating, Stars.
Excludes: Hostels, B&Bs, Guesthouses, AirBnB-style listings.

## How to run (GitHub Codespaces)

1. Create a GitHub repo and add the files from this project.
2. Open the repo in **GitHub Codespaces** (green Code → Open with Codespaces).
3. In the Codespace terminal run:

   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   playwright install

# scrape.py
"""
Playwright scraper for hotels-pt.com
Saves hotels_portugal.csv and hotels_portugal.xlsx
Preferences:
 - Official website only (leave blank if none)
 - Exclude hostels / B&B / Airbnb
 - Include unrated hotels
 - All languages (no Accept-Language header set)
"""

import time
import re
import csv
from urllib.parse import urljoin, urlparse
from pathlib import Path

import pandas as pd
from tqdm import tqdm
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# === Config ===
BASE_LISTING_URL = "https://hotels-pt.com/portugal-hotels?page={}"  # pagination template
SITE_DOMAIN = "hotels-pt.com"

# Filtering keywords (case-insensitive)
BANNED_KEYWORDS = ["hostel", "b&b", "bnb", "guesthouse", "guest house", "airbnb", "albergue"]

# Known aggregator domains to avoid when selecting "official" website
BOOKING_DOMAINS = [
    "booking.com", "tripadvisor", "facebook", "instagram", "expedia", "hotels.com",
    "airbnb", "google.com", "agoda", "travelocity", "kayak"
]

# Max pages to avoid infinite loops; tune if you expect more pages
PAGE_CAP = 2000

# Run headful by default to reduce blocking; set to True to run headless
HEADLESS = False

# small polite delay between page navigations
NAV_SLEEP = 0.6

# Output files
OUT_CSV = "hotels_portugal.csv"
OUT_XLSX = "hotels_portugal.xlsx"

# === Helpers ===
def is_banned_name(name):
    if not name: 
        return True
    n = name.lower()
    return any(k in n for k in BANNED_KEYWORDS)

def looks_like_official(url):
    if not url:
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except:
        return False
    if SITE_DOMAIN in host:
        return False
    for bad in BOOKING_DOMAINS:
        if bad in host:
            return False
    return True

def normalize_href(base, href):
    if not href:
        return None
    try:
        return urljoin(base, href)
    except:
        return href

def extract_text_or_none(el):
    try:
        t = el.inner_text()
        if t:
            return t.strip()
        return None
    except:
        return None

def parse_stars_from_text(txt):
    if not txt:
        return None
    m = re.search(r"(\d(?:\.\d)?)", txt)
    if m:
        return m.group(1)
    return None

def first_official_link(page):
    # Collect absolute external links on the page
    anchors = page.query_selector_all("a")
    external = []
    for a in anchors:
        href = a.get_attribute("href")
        if not href:
            continue
        href = normalize_href(page.url, href)
        if not href.startswith("http"):
            continue
        host = (urlparse(href).hostname or "").lower()
        if SITE_DOMAIN in host:
            continue
        external.append(href)
    # Prefer official-looking (non-aggregator)
    for link in external:
        if looks_like_official(link):
            return link
    return external[0] if external else None

# === Scraper ===
def scrape_all():
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        context = browser.new_context()  # default headers; we do NOT force Accept-Language (all languages)
        page = context.new_page()

        page_num = 1
        total_found = 0
        pbar_pages = tqdm(desc="Pages scraped", unit="page")

        while page_num <= PAGE_CAP:
            list_url = BASE_LISTING_URL.format(page_num)
            try:
                page.goto(list_url, wait_until="networkidle", timeout=60000)
            except PWTimeout:
                print(f"Timeout loading page {list_url} — retrying once...")
                try:
                    page.goto(list_url, wait_until="networkidle", timeout=60000)
                except Exception as e:
                    print(f"Failed again: {e}. Stopping pagination.")
                    break
            except Exception as e:
                print(f"Error loading page {list_url}: {e}")
                break

            # Try a set of possible selectors for listing cards
            card_selectors = [".product-card", ".hotel-card", ".listing-item", "article", ".card"]
            cards = []
            for sel in card_selectors:
                found = page.query_selector_all(sel)
                if found and len(found) >= 1:
                    cards = found
                    break

            # If no cards, try to detect "no results" page text and stop
            if not cards:
                body_text = page.inner_text("body") if page.query_selector("body") else ""
                if re.search(r"No results|Nenhum resultado|Sem resultados|Sem resultados", body_text, re.IGNORECASE):
                    print("No results text detected — stopping.")
                else:
                    print(f"No listing cards found on page {page_num} (tried selectors). Stopping.")
                break

            # If page has very few cards, could be last page — but still process them
            pbar_pages.update(1)

            # Process each card
            for card in cards:
                try:
                    # Find hotel name
                    name = None
                    for sel in ["a .product-name", ".product-name", "h2", ".title", "a"]:
                        el = card.query_selector(sel)
                        if el:
                            name = extract_text_or_none(el)
                            if name:
                                break
                    # fallback: full card inner text first line
                    if not name:
                        raw = extract_text_or_none(card)
                        if raw:
                            name = raw.splitlines()[0].strip()

                    if not name:
                        continue
                    if is_banned_name(name):
                        continue

                    # Region/location
                    region = None
                    for sel in [".product-location", ".location", ".city", ".meta-location", ".place"]:
                        el = card.query_selector(sel)
                        if el:
                            region = extract_text_or_none(el)
                            break

                    # Stars - try multiple patterns
                    stars = None
                    # text-based stars
                    for sel in [".stars", ".rating-stars", ".stars-text"]:
                        el = card.query_selector(sel)
                        if el:
                            txt = extract_text_or_none(el)
                            stars = parse_stars_from_text(txt)
                            if stars:
                                break
                    # icon-based stars
                    if not stars:
                        icons = card.query_selector_all(".star, .star-icon, svg.star, i.fa-star")
                        if icons:
                            stars = len(icons)

                    # Rating
                    rating = None
                    for sel in [".rating-score", ".review-score", ".score", ".rating"]:
                        el = card.query_selector(sel)
                        if el:
                            rating = extract_text_or_none(el)
                            break

                    # Detail URL and attempt to find official website from detail page
                    detail_href = None
                    a = card.query_selector("a")
                    if a:
                        href = a.get_attribute("href")
                        detail_href = normalize_href(page.url, href) if href else None

                    website = None
                    # First try to find official external link inside card itself
                    anchors = card.query_selector_all("a")
                    for a in anchors:
                        href = a.get_attribute("href")
                        if not href:
                            continue
                        href = normalize_href(page.url, href)
                        if href and looks_like_official(href):
                            website = href
                            break

                    # If not in card, open detail page (if exists) and search for external links
                    if not website and detail_href:
                        try:
                            dpage = context.new_page()
                            dpage.goto(detail_href, wait_until="networkidle", timeout=45000)
                            website = first_official_link(dpage)
                            dpage.close()
                        except Exception as e:
                            # if detail page fails, continue without website
                            try:
                                dpage.close()
                            except:
                                pass

                    rows.append({
                        "Hotel Name": name,
                        "Region": region,
                        "Stars": stars,
                        "Rating": rating,
                        "Website": website if website else "",
                        "Detail URL": detail_href if detail_href else ""
                    })
                    total_found += 1

                except Exception as e:
                    # keep scraping even if one card fails
                    print("Card parsing error:", e)

            print(f"Page {page_num}: found {len(cards)} cards; total collected so far: {total_found}")
            page_num += 1

            # Basic polite wait
            time.sleep(NAV_SLEEP)

        pbar_pages.close()
        browser.close()

    # Save results
    if not rows:
        print("No hotels collected. Please check selectors or load the site in visible mode (HEADLESS=False).")
    else:
        df = pd.DataFrame(rows)
        # Reorder columns
        order = ["Hotel Name", "Region", "Stars", "Rating", "Website", "Detail URL"]
        cols = [c for c in order if c in df.columns] + [c for c in df.columns if c not in order]
        df = df[cols]
        df.to_csv(OUT_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
        df.to_excel(OUT_XLSX, index=False)
        print(f"Saved {len(df)} rows to {OUT_CSV} and {OUT_XLSX}")

if __name__ == "__main__":
    scrape_all()

import time
import re
import pandas as pd
from urllib.parse import urljoin, urlparse
from tqdm import tqdm
from playwright.sync_api import sync_playwright

BASE_URL = "https://hotels-pt.com/portugal-hotels?page={}"

BANNED = ["hostel", "b&b", "bnb", "guesthouse", "guest house", "airbnb"]
AGG_DOMAINS = ["booking.com", "expedia", "hotels.com", "agoda", "airbnb"]

def valid(name):
    return name and not any(x in name.lower() for x in BANNED)

def official(url):
    if not url: return False
    host = (urlparse(url).hostname or "").lower()
    if "hotels-pt.com" in host: return False
    return not any(b in host for b in AGG_DOMAINS)

def find_official(page):
    links = page.query_selector_all("a")
    urls = []
    for l in links:
        href = l.get_attribute("href")
        if href and href.startswith("http"):
            urls.append(href)
    for u in urls:
        if official(u): return u
    return urls[0] if urls else None

def scrape():
    hotels = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        page_num = 1
        print("Scraping hotel list...")

        while True:
            list_url = BASE_URL.format(page_num)
            page.goto(list_url, wait_until="networkidle")
            cards = page.query_selector_all(".product-card")
            if not cards: break

            for card in tqdm(cards):
                name = card.query_selector(".product-name")
                name = name.inner_text().strip() if name else None
                if not valid(name): continue

                region = card.query_selector(".product-location")
                region = region.inner_text().strip() if region else None

                stars = len(card.query_selector_all(".star-icon"))
                if stars == 0: stars = None

                rating = card.query_selector(".rating-score")
                rating = rating.inner_text().strip() if rating else None

                detail = card.query_selector("a")
                href = detail.get_attribute("href") if detail else None
                href = urljoin(page.url, href) if href else None

                website = None
                if href:
                    d = ctx.new_page()
                    try:
                        d.goto(href, wait_until="networkidle")
                        website = find_official(d)
                    finally:
                        d.close()

                hotels.append({
                    "Hotel Name": name,
                    "Region": region,
                    "Stars": stars,
                    "Rating": rating,
                    "Website": website
                })

            print(f"✅ Page {page_num} done.")
            page_num += 1
            time.sleep(1)

        browser.close()

    df = pd.DataFrame(hotels)
    df.to_excel("hotels_portugal.xlsx", index=False)
    print("✅ Saved hotels_portugal.xlsx ✅")

if __name__ == "__main__":
    scrape()

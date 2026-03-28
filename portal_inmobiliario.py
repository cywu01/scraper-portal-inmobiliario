import argparse
import asyncio
import random
import re
import sys
import time
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright

from config import REGIONS


def sleep_with_jitter(base: float = 2) -> None:
    time.sleep(base + random.uniform(0, 1.5))

BASE_URL_TEMPLATE = "https://www.portalinmobiliario.com/arriendo/departamento/{slug}-{region}"
OUTPUT_DIR = Path("data/raw")

SELECTORS = {
    "listing_ol": "ol.ui-search-layout",
    "listing_li_class": "ui-search-layout__item",
    "price": ".andes-money-amount",
    "attributes": ".poly-attributes_list__item",
    "location": ".poly-component__location",
    "title_link": ".poly-component__title",
}

COLUMNS = ["listing_id", "price", "currency", "bedrooms", "bathrooms", "m2", "location_raw", "commune", "url", "scrape_date"]


def _parse_price(tag) -> tuple:
    label = tag.get("aria-label", "")

    # UF with cents: "46 unidades de fomento con 63 centavos"
    m = re.match(r"([\d\.]+)\s+unidades de fomento con (\d+) centavos", label)
    if m:
        whole = float(m.group(1).replace(".", ""))
        cents = int(m.group(2)) / 100
        return whole + cents, "UF"

    # UF whole: "46 unidades de fomento"
    m = re.match(r"([\d\.]+)\s+unidades de fomento", label)
    if m:
        return float(m.group(1).replace(".", "")), "UF"

    # CLP: "430000 pesos chilenos" (dots are thousands separators → strip them)
    m = re.match(r"([\d\.]+)\s+pesos chilenos", label)
    if m:
        return float(m.group(1).replace(".", "")), "CLP"

    return None, None


def _parse_attributes(items) -> tuple:
    bedrooms = bathrooms = m2 = None
    for item in items:
        text = item.get_text(strip=True)
        if "dormitorio" in text:
            m = re.search(r"(\d+)", text)
            if m:
                bedrooms = int(m.group(1))
        elif "baño" in text:
            m = re.search(r"(\d+)", text)
            if m:
                bathrooms = int(m.group(1))
        elif "m²" in text:
            m = re.search(r"(\d+(?:[,\.]\d+)?)", text)
            if m:
                m2 = float(m.group(1).replace(",", "."))
    return bedrooms, bathrooms, m2


def _page_url(page_num: int, slug: str, region: str) -> str:
    base = BASE_URL_TEMPLATE.format(slug=slug, region=region)
    if page_num == 1:
        return base
    n = (page_num - 1) * 48 + 1
    return f"{base}/_Desde_{n}_NoIndex_True"


def _parse_listings(html: str, scrape_date: str, commune_name: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    ol = soup.select_one(SELECTORS["listing_ol"])
    if ol is None:
        return []

    results = []
    for li in ol.find_all("li"):
        raw_classes = li.get("class") or []
        classes = raw_classes if isinstance(raw_classes, list) else []
        if SELECTORS["listing_li_class"] not in classes:
            continue
        if any("intervention" in c for c in classes):
            continue
        if li.select_one(".poly-component__available-units"):
            continue

        row: dict = {col: None for col in COLUMNS}
        row["scrape_date"] = scrape_date
        row["commune"] = commune_name

        # URL — extract first so failures on other fields can log it
        try:
            title_tag = li.select_one(SELECTORS["title_link"])
            if title_tag:
                href = title_tag.get("href")
                if isinstance(href, str):
                    row["url"] = href.split("#")[0]
                    match = re.search(r"(MLC-\d+)", href)
                    row["listing_id"] = match.group(1) if match else None
        except Exception as e:
            print(f"[WARN] URL extraction failed: {e}")

        listing_url = row["url"] or "<unknown>"

        # Price
        try:
            price_tag = li.select_one(SELECTORS["price"])
            if price_tag:
                row["price"], row["currency"] = _parse_price(price_tag)
        except Exception as e:
            print(f"[WARN] Price extraction failed for {listing_url}: {e}")

        # Bedrooms / bathrooms / m²
        try:
            attr_items = li.select(SELECTORS["attributes"])
            row["bedrooms"], row["bathrooms"], row["m2"] = _parse_attributes(attr_items)
        except Exception as e:
            print(f"[WARN] Attribute extraction failed for {listing_url}: {e}")

        # Commune
        try:
            loc_tag = li.select_one(SELECTORS["location"])
            if loc_tag:
                row["location_raw"] = loc_tag.get_text(strip=True)
        except Exception as e:
            print(f"[WARN] Location extraction failed for {listing_url}: {e}")

        results.append(row)

    return results


async def scrape_all(communes: dict[str, str], commune_regions: dict[str, str]) -> pd.DataFrame:
    all_rows: list = []
    scrape_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "es-CL,es;q=0.9"},
        )
        page = await context.new_page()

        for commune_name, slug in communes.items():
            print(f"\n[COMMUNE] {commune_name}")
            page_num = 1

            while True:
                url = _page_url(page_num, slug, commune_regions[commune_name])
                print(f"  [PAGE {page_num}] {url}")

                try:
                    await page.goto(url)

                    # Portal Inmobiliario sets PAGE_TYPE = "rescue" on empty results pages.
                    # Detect this immediately to avoid waiting for the listing selector timeout.
                    page_type = await page.evaluate("() => window.PAGE_TYPE")
                    if page_type == "rescue":
                        print(f"  [SKIP] No listings (rescue page), moving to next commune")
                        break

                    await page.wait_for_selector(SELECTORS["listing_ol"], timeout=15_000)
                    html = await page.content()
                    rows = _parse_listings(html, scrape_date, commune_name)

                    if not rows:
                        print(f"  [STOP] No listings, moving to next commune")
                        break

                    print(f"  → {len(rows)} listings")
                    all_rows.extend(rows)
                    page_num += 1
                    sleep_with_jitter(base=3)

                except PlaywrightTimeoutError:
                    print(f"  [TIMEOUT] Skipping to next commune")
                    break

            await asyncio.sleep(random.uniform(10, 20))

        await browser.close()

    return pd.DataFrame(all_rows, columns=COLUMNS)


def save(df: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = datetime.now(timezone.utc).strftime("listings_%Y_%m_%d_%H%M%S.csv")
    path = OUTPUT_DIR / filename
    df.to_csv(path, mode="w", header=True, index=False)

    print(f"[SAVED] {len(df)} rows → {path}")


SLUG_TO_COMMUNE = {slug: name for region in REGIONS.values() for name, slug in region.items()}
SLUG_TO_REGION = {slug: region for region, communes in REGIONS.items() for slug in communes.values()}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Portal Inmobiliario listings.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--region",
        help=f"Region to scrape. Valid options: {', '.join(REGIONS)}",
    )
    group.add_argument(
        "--commune",
        nargs="+",
        metavar="SLUG",
        help="One or more commune slugs to scrape (e.g. las-condes providencia nunoa).",
    )

    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    args = parser.parse_args()

    if args.region is not None:
        if args.region not in REGIONS:
            print(f"Error: invalid region '{args.region}'. Valid options: {', '.join(REGIONS)}", file=sys.stderr)
            sys.exit(1)
        communes = REGIONS[args.region]
        commune_regions = {name: args.region for name in communes}
    else:
        invalid = [s for s in args.commune if s not in SLUG_TO_COMMUNE]
        if invalid:
            print(f"Error: invalid commune slug(s): {', '.join(invalid)}.", file=sys.stderr)
            sys.exit(1)
        communes = {SLUG_TO_COMMUNE[s]: s for s in args.commune}
        commune_regions = {SLUG_TO_COMMUNE[s]: SLUG_TO_REGION[s] for s in args.commune}

    df = asyncio.run(scrape_all(communes, commune_regions))
    save(df)

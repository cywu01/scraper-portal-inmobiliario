"""Stage 1: collect listing IDs and current card prices from search results pages.

Output: data/raw/listing_ids_<timestamp>.csv — one row per listing live on that date.
Each file is a snapshot: comparing files over time gives price changes and time on market.

Portal Inmobiliario stops paginating after 2,016 results (42 pages x 48), so any commune
with more results is split into CLP price ranges, bisected until every slice fits under
the cap. Slices can overlap slightly (UF prices are converted to CLP for filtering);
that's harmless because IDs are de-duplicated.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd
from bs4 import BeautifulSoup

import config
from http_client import BlockedError, Fetcher, make_client

PAGE_SIZE = 48
RESULT_CAP = 2016            # results past this offset return a 404 "rescue" page
PRICE_MAX_CLP = 20_000_000   # finite upper bound for bisection; above it is one open-ended slice
MIN_SLICE_CLP = 1_000        # stop bisecting below this width

COLUMNS = ["listing_id", "url", "price", "currency", "price_previous",
           "commune", "region", "scrape_date"]

ID_RE = re.compile(r"(MLC-\d+)")
TOTAL_RE = re.compile(r'"offset"\s*:\s*\d+\s*,\s*"total"\s*:\s*(\d+)')


@dataclass
class SearchPage:
    total: int                                   # results for this query (0 on rescue pages)
    items: dict = field(default_factory=dict)    # {listing_id: row dict}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_price_label(label: str) -> tuple[float | None, str | None]:
    """'Ahora: 46 unidades de fomento con 63 centavos' -> (46.63, 'UF'); '430000 pesos chilenos' -> (430000, 'CLP')."""
    label = re.sub(r"^\s*(Antes|Ahora)\s*:\s*", "", label or "")
    m = re.match(r"([\d\.]+)\s+unidades de fomento(?:\s+con\s+(\d+)\s+centavos)?", label)
    if m:
        return float(m.group(1).replace(".", "")) + (int(m.group(2)) / 100 if m.group(2) else 0), "UF"
    m = re.match(r"([\d\.]+)\s+pesos chilenos", label)
    if m:
        return float(m.group(1).replace(".", "")), "CLP"
    m = re.match(r"([\d\.]+)\s+d[oó]lares(?:\s+con\s+(\d+)\s+centavos)?", label)
    if m:
        return float(m.group(1).replace(".", "")) + (int(m.group(2)) / 100 if m.group(2) else 0), "USD"
    return None, None


def _card_prices(li) -> tuple[float | None, str | None, float | None]:
    current = li.select_one(".poly-price__current .andes-money-amount")
    if current is None:  # fallback: first amount that isn't the crossed-out previous price
        current = next((a for a in li.select(".andes-money-amount")
                        if "andes-money-amount--previous" not in (a.get("class") or [])), None)
    previous = li.select_one(".andes-money-amount--previous")
    price, currency = parse_price_label(current.get("aria-label", "")) if current else (None, None)
    price_prev, _ = parse_price_label(previous.get("aria-label", "")) if previous else (None, None)
    return price, currency, price_prev


def parse_search_page(html: str) -> SearchPage:
    m = TOTAL_RE.search(html)
    soup = BeautifulSoup(html, "html.parser")
    items = {}
    for li in soup.select("ol.ui-search-layout li.ui-search-layout__item"):
        if any("intervention" in c for c in (li.get("class") or [])):
            continue
        a = li.select_one(".poly-component__title")
        href = a.get("href") if a else None
        mid = ID_RE.search(href) if isinstance(href, str) else None
        if not mid:
            continue
        try:
            price, currency, price_prev = _card_prices(li)
        except Exception as e:  # never lose an ID because of a price quirk
            print(f"    [WARN] price parse failed for {mid.group(1)}: {e}")
            price = currency = price_prev = None
        items[mid.group(1)] = {
            "listing_id": mid.group(1), "url": href.split("#")[0],
            "price": price, "currency": currency, "price_previous": price_prev,
        }
    total = int(m.group(1)) if m else len(items)
    return SearchPage(total=total, items=items)


# ---------------------------------------------------------------------------
# URLs and fetching
# ---------------------------------------------------------------------------

def search_url(slug: str, region: str, offset: int = 1, lo: int | None = None, hi: int | None = None) -> str:
    """Build a search URL. In the price filter, an upper bound of 0 means 'no upper bound'."""
    base = config.SEARCH_URL_TEMPLATE.format(slug=slug, region=region)
    parts = []
    if offset > 1:
        parts.append(f"Desde_{offset}")
    if lo is not None or hi is not None:
        parts.append(f"PriceRange_{lo or 0}CLP-{hi or 0}CLP")
    if not parts:
        return base
    if offset > 1:
        parts.append("NoIndex_True")
    return f"{base}/_" + "_".join(parts)


def _classify(r: httpx.Response):
    if r.status_code == 404 and "rescue" in r.text:   # empty commune or past the result cap
        return "gone"
    if r.status_code == 200 and "ui-search" in r.text:
        return "ok"
    return None


async def fetch_search(f: Fetcher, url: str) -> SearchPage:
    outcome, r = await f.get(url, _classify)
    if outcome != "ok":
        return SearchPage(total=0)
    return parse_search_page(r.text)


# ---------------------------------------------------------------------------
# Scraping logic
# ---------------------------------------------------------------------------

async def _collect_query(f: Fetcher, slug, region, lo, hi, first: SearchPage) -> dict:
    """Paginate one query known to fit under RESULT_CAP."""
    found = dict(first.items)
    n_pages = min(-(-first.total // PAGE_SIZE), RESULT_CAP // PAGE_SIZE)
    pages = await asyncio.gather(*(
        fetch_search(f, search_url(slug, region, 1 + PAGE_SIZE * i, lo, hi)) for i in range(1, n_pages)
    ))
    for p in pages:
        found.update(p.items)
    return found


async def _collect_range(f: Fetcher, slug, region, lo: int, hi: int | None, label: str) -> dict:
    """Collect a CLP price slice, bisecting while it exceeds the cap. hi=None means open-ended."""
    hi_param = hi if hi is not None else 0
    first = await fetch_search(f, search_url(slug, region, 1, lo, hi_param))
    if first.total == 0:
        return {}
    rng = f"{lo:,}–{'∞' if hi is None else f'{hi:,}'} CLP"
    if first.total <= RESULT_CAP or hi is None or hi - lo <= MIN_SLICE_CLP:
        if first.total > RESULT_CAP:
            print(f"    [WARN] {label} {rng}: {first.total} results, can't split further; keeping first {RESULT_CAP}")
        print(f"    {label} {rng}: {first.total} results")
        return await _collect_query(f, slug, region, lo, hi_param, first)
    mid = (lo + hi) // 2
    left, right = await asyncio.gather(
        _collect_range(f, slug, region, lo, mid, label),
        _collect_range(f, slug, region, mid + 1, hi, label),
    )
    return {**left, **right}


async def scrape_commune(f: Fetcher, commune: str, slug: str, region: str) -> dict:
    first = await fetch_search(f, search_url(slug, region))
    print(f"[COMMUNE] {commune}: {first.total} results")
    if first.total == 0:
        return {}
    if first.total <= RESULT_CAP:
        found = await _collect_query(f, slug, region, None, None, first)
    else:
        print(f"    over the {RESULT_CAP} cap → splitting by price")
        bounded, tail = await asyncio.gather(
            _collect_range(f, slug, region, 0, PRICE_MAX_CLP, commune),
            _collect_range(f, slug, region, PRICE_MAX_CLP + 1, None, commune),
        )
        found = {**bounded, **tail}
    coverage = len(found) / first.total
    flag = "" if coverage >= 0.97 else "   [WARN] low coverage"
    print(f"    → {commune}: {len(found)} unique IDs ({coverage:.0%} of {first.total}){flag}")
    return found


async def collect(communes: dict[str, str], commune_regions: dict[str, str]) -> pd.DataFrame:
    scrape_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows: dict[str, dict] = {}
    async with make_client() as client:
        f = Fetcher(client)

        async def one(name, slug):
            # each commune saves into `rows` as soon as it finishes, so an abort keeps finished communes
            found = await scrape_commune(f, name, slug, commune_regions[name])
            for lid, item in found.items():
                rows.setdefault(lid, {**item, "commune": name, "region": commune_regions[name],
                                      "scrape_date": scrape_date})

        results = await asyncio.gather(*(one(name, slug) for name, slug in communes.items()),
                                       return_exceptions=True)
        errors = [r for r in results if isinstance(r, BaseException)]
        if any(isinstance(e, BlockedError) for e in errors):
            print("[ABORT] Too many consecutive failures; the site may be blocking. Saved communes that finished.")
        for e in errors:
            if not isinstance(e, BlockedError):
                raise e
        print(f"\n[STAGE 1 DONE] {len(rows)} unique listing IDs from {f.requests} requests")
    return pd.DataFrame(list(rows.values()), columns=COLUMNS)


def save(df: pd.DataFrame) -> Path:
    out = Path(config.RAW_DIR)
    out.mkdir(parents=True, exist_ok=True)
    path = out / datetime.now(timezone.utc).strftime("listing_ids_%Y_%m_%d_%H%M%S.csv")
    df.to_csv(path, index=False)
    print(f"[SAVED] {len(df)} rows → {path}")
    return path


def run(communes: dict[str, str], commune_regions: dict[str, str]) -> Path:
    return save(asyncio.run(collect(communes, commune_regions)))

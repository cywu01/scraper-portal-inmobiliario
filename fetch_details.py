"""Stage 2: fetch the detail page of every listing not yet scraped, and parse its embedded JSON.

Input:  a stage-1 file (data/raw/listing_ids_*.csv; the latest one by default).
Output: data/details/details.jsonl — append-only, one JSON record per fetched listing.
        data/details/details.csv   — flat table rebuilt from the JSONL after each run.

Each listing is fetched once. IDs already recorded as "ok" or "not_found" are skipped,
so the stage is safe to stop and re-run; IDs that errored are retried on the next run.

Detail pages are server-rendered: all data sits in the JSON inside
<script id="__NORDIC_RENDERING_CTX__">_n.ctx.r={...};...</script>, under
appProps.pageProps.initialState.
"""

import asyncio
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pandas as pd

import config
from http_client import BlockedError, Fetcher, make_client

CTX_RE = re.compile(r'<script[^>]*id="__NORDIC_RENDERING_CTX__"[^>]*>(.*?)</script>', re.S)
AGE_RE = re.compile(r"hace\s+(\d+)\s+(minuto|hora|día|dia|semana|mes|año|ano)", re.I)
PUBLISHED_RE = re.compile(r"Publicado\s+(.+)$", re.I)
CURRENCY_NAMES = {"CLF": "UF"}  # the site's ISO code for UF; stage 1 calls it "UF"
AGE_DAYS = {"minuto": 0, "hora": 0, "día": 1, "dia": 1, "semana": 7, "mes": 30, "año": 365, "ano": 365}

CORE_COLUMNS = [
    "listing_id", "title", "price", "currency", "item_status", "seller_type", "seller_id",
    "listing_type", "condition", "region_name", "commune_name", "neighborhood", "address",
    "latitude", "longitude", "published_label", "days_on_site", "published_date_approx", "url", "fetched_at",
]


def jsonl_path() -> Path:
    return Path(config.DETAILS_DIR) / "details.jsonl"


def csv_path() -> Path:
    return Path(config.DETAILS_DIR) / "details.csv"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def extract_state(html: str) -> dict:
    """Return appProps.pageProps.initialState from the embedded rendering context."""
    m = CTX_RE.search(html)
    if not m:
        raise ValueError("rendering context script not found")
    text = m.group(1)
    ctx, _ = json.JSONDecoder().raw_decode(text, text.index("{"))  # trailing JS after the object is ignored
    state = (ctx.get("appProps") or {}).get("pageProps", {}).get("initialState")
    if not state:
        raise ValueError("initialState missing (not a listing page?)")
    return state


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def extract_specs(components: dict) -> dict:
    """Every {"id": label, "text": value} pair from the 'Características' tables."""
    specs = {}
    for node in _walk(components):
        attrs = node.get("attributes")
        if isinstance(attrs, list):
            for a in attrs:
                if isinstance(a, dict) and isinstance(a.get("id"), str) and isinstance(a.get("text"), str):
                    specs.setdefault(a["id"], a["text"])
    return specs


def _first_location(components: dict) -> tuple[float | None, float | None]:
    for node in _walk(components):
        loc = node.get("map_info", {}).get("location") if isinstance(node.get("map_info"), dict) else None
        if isinstance(loc, dict) and loc.get("latitude"):
            try:
                return float(loc["latitude"]), float(loc["longitude"])
            except (TypeError, ValueError):
                pass
    return None, None


def _row_text(row) -> str | None:
    """content_rows entries look like {"title": {"text": "..."}}; tolerate a plain "text" too."""
    if not isinstance(row, dict):
        return None
    title = row.get("title")
    if isinstance(title, dict) and isinstance(title.get("text"), str):
        return title["text"]
    return row.get("text") if isinstance(row.get("text"), str) else None


def _published_label(subtitle: str) -> str | None:
    """'Departamento en Arriendo  |  Publicado hace 41 días' -> 'hace 41 días'; also 'esta semana', 'hoy'."""
    m = PUBLISHED_RE.search((subtitle or "").split("|")[-1].strip())
    return m.group(1).strip() if m else None


def _days_on_site(subtitle: str) -> int | None:
    """Exact-ish age in days. Listings under ~8 days old only say 'esta semana' -> None (see published_label)."""
    label = (_published_label(subtitle) or "").lower()
    if label == "hoy":
        return 0
    if label == "ayer":
        return 1
    m = AGE_RE.search(label)
    return int(m.group(1)) * AGE_DAYS[m.group(2).lower()] if m else None


def parse_detail(html: str, fetched_at: datetime) -> dict:
    st = extract_state(html)
    comps = st.get("components") or {}
    ev = ((st.get("track") or {}).get("melidata_event") or {}).get("event_data") or {}
    header = comps.get("header") or {}
    price = (comps.get("price") or {}).get("price") or {}
    rows = (comps.get("location_and_points") or {}).get("content_rows") or []
    lat, lng = _first_location(comps)
    days = _days_on_site(header.get("subtitle", ""))
    return {
        "title": header.get("title"),
        "price": price.get("value", ev.get("price")),
        "currency": CURRENCY_NAMES.get(c := price.get("currency_id", ev.get("currency_id")), c),
        "item_status": ev.get("item_status"),
        "seller_type": ev.get("seller_type"),
        "seller_id": ev.get("seller_id"),
        "listing_type": ev.get("listing_type_id"),
        "condition": ev.get("item_condition"),
        "region_name": ev.get("state"),
        "commune_name": ev.get("city"),
        "neighborhood": ev.get("neighborhood"),
        "address": _row_text(rows[0]) if rows else None,
        "latitude": lat,
        "longitude": lng,
        "published_label": _published_label(header.get("subtitle", "")),
        "days_on_site": days,
        "published_date_approx": (fetched_at - timedelta(days=days)).strftime("%Y-%m-%d") if days is not None else None,
        "specs": extract_specs(comps),
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def load_records() -> dict[str, dict]:
    """Latest record per listing_id from the JSONL log."""
    records = {}
    p = jsonl_path()
    if p.exists():
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # a half-written last line from an interrupted run
                    records[rec["listing_id"]] = rec
    return records


def latest_ids_file() -> Path:
    files = sorted(Path(config.RAW_DIR).glob("listing_ids_*.csv"))
    if not files:
        raise FileNotFoundError(f"no listing_ids_*.csv in {config.RAW_DIR}; run stage 1 first")
    return files[-1]


def _slug(label: str) -> str:
    s = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _convert(value: str):
    """'33 m²' -> 33.0, '2 años' -> 2, 'Sí' -> True, '60.000 CLP' -> (60000, 'CLP'); otherwise the text."""
    v = value.strip()
    if v in ("Sí", "Si"):
        return True
    if v == "No":
        return False
    if re.fullmatch(r"\d+", v):
        return int(v)
    m = re.fullmatch(r"(-?[\d\.]+(?:,\d+)?)\s*m²", v)
    if m:
        return float(m.group(1).replace(".", "").replace(",", "."))
    m = re.fullmatch(r"(-?[\d\.]+(?:,\d+)?)\s*años?", v)
    if m:
        n = float(m.group(1).replace(".", "").replace(",", "."))
        return int(n) if n.is_integer() else n
    m = re.fullmatch(r"([\d\.]+(?:,\d+)?)\s*(CLP|UF)", v)
    if m:
        return float(m.group(1).replace(".", "").replace(",", ".")), m.group(2)
    return v


def export_csv() -> Path:
    """Rebuild details.csv from the JSONL: core fields + one column per characteristic."""
    rows = []
    for rec in load_records().values():
        if rec.get("status") != "ok":
            continue
        row = {c: rec.get(c) for c in CORE_COLUMNS}
        row["currency"] = CURRENCY_NAMES.get(row["currency"], row["currency"])
        for label, text in (rec.get("specs") or {}).items():
            col = _slug(label)
            if col in row:
                col = "spec_" + col
            val = _convert(text)
            if isinstance(val, tuple):  # money: number + its own currency column
                row[col], row[col + "_currency"] = val
            else:
                row[col] = val
        rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df[CORE_COLUMNS + sorted(c for c in df.columns if c not in CORE_COLUMNS)]
    df.to_csv(csv_path(), index=False)
    print(f"[EXPORTED] {len(df)} listings, {df.shape[1] if not df.empty else 0} columns → {csv_path()}")
    return csv_path()


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def _classify(r: httpx.Response):
    if r.status_code == 404:
        return "gone"           # listing removed since stage 1
    if r.status_code == 200 and "__NORDIC_RENDERING_CTX__" in r.text:
        return "ok"
    return None                 # anything else (403, captcha, truncated page) → retry


async def fetch_all(todo: list[tuple[str, str]]) -> None:
    out = jsonl_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    counts = {"ok": 0, "not_found": 0, "error": 0}
    done = 0

    with out.open("a", encoding="utf-8") as fh:
        async with make_client() as client:
            f = Fetcher(client)

            async def one(listing_id: str, url: str):
                nonlocal done
                outcome, r = await f.get(url, _classify)
                now = datetime.now(timezone.utc)
                rec = {"listing_id": listing_id, "url": url, "fetched_at": now.isoformat(timespec="seconds")}
                if outcome == "ok":
                    try:
                        rec.update(status="ok", **parse_detail(r.text, now))
                    except Exception as e:
                        rec.update(status="error", error=f"parse: {e}")
                elif outcome == "gone":
                    rec["status"] = "not_found"
                else:
                    rec.update(status="error", error="fetch failed after retries")
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                counts[rec["status"]] += 1
                done += 1
                if done % 25 == 0 or done == len(todo):
                    print(f"  [{done}/{len(todo)}] ok={counts['ok']} not_found={counts['not_found']} error={counts['error']}")

            results = await asyncio.gather(*(one(lid, url) for lid, url in todo), return_exceptions=True)
            errors = [r for r in results if isinstance(r, BaseException)]
            if any(isinstance(e, BlockedError) for e in errors):
                print("[ABORT] Too many consecutive failures; the site may be blocking. "
                      "Progress is saved — re-run later to continue.")
            for e in errors:
                if not isinstance(e, BlockedError):
                    raise e
            print(f"\n[STAGE 2 DONE] {counts} from {f.requests} requests")


def run(ids_file: Path | None = None, limit: int | None = None) -> Path:
    ids_file = Path(ids_file) if ids_file else latest_ids_file()
    ids = pd.read_csv(ids_file, usecols=["listing_id", "url"]).drop_duplicates("listing_id")
    have = {lid for lid, rec in load_records().items() if rec.get("status") in ("ok", "not_found")}
    todo = [(r.listing_id, r.url) for r in ids.itertuples() if r.listing_id not in have]
    print(f"[STAGE 2] {ids_file.name}: {len(ids)} IDs, {len(ids) - len(todo)} already scraped, {len(todo)} to fetch")
    if limit is not None:
        todo = todo[:limit]
        print(f"  (limited to {len(todo)})")
    if todo:
        asyncio.run(fetch_all(todo))
    return export_csv()

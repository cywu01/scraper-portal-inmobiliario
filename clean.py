"""Stage 3: clean the exported detail table into one product-agnostic listings table.

Input:  data/details/details.csv          (rebuilt from details.jsonl by `python main.py export`)
        reference/uf.csv                  (date,uf — one row per scrape date, maintained by hand)
Output: data/clean/listings_clean.csv

Rules (agreed 2026-10-08):
  * The raw files are never modified.
  * Rows are DROPPED only when they are not rentals we can price: currency other than CLP/UF,
    or a sale-level price (> 15M CLP or > 300 UF).
  * Everything else is kept. Implausible VALUES are blanked, and every change is recorded
    in the `quality_flags` column (semicolon-separated codes) so each product decides what to exclude.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import config

TZ = "America/Santiago"

# --- thresholds -------------------------------------------------------------
SALE_MAX_CLP = 15_000_000        # above this a CLP price is a sale price, not a monthly rent
SALE_MAX_UF = 300
PLACEHOLDER = 242085             # junk value the site emits in several unrelated fields
MAX_COUNTS = {"dormitorios": 6, "banos": 6, "estacionamientos": 6, "bodegas": 5}
AGE_MAX = 150
FLOOR_MIN, FLOOR_MAX = -1, 60
UTIL_MIN, UTIL_MAX = 10, 500     # superficie_util, m²
TOTAL_MAX = 2000                 # superficie_total, m²
GC_MIN_CLP = 10_000              # gastos comunes: 0 < value < this is a placeholder (78 rows are exactly $1)
GC_MAX_CLP = 2_000_000
# Continental Chile; the scraper can target any region, so no per-region box here.
LAT_RANGE, LON_RANGE = (-56.0, -17.4), (-76.0, -66.0)

ORIENTATION_LABELS = {  # O = oriente (east), P = poniente (west)
    "N": "Norte", "S": "Sur", "O": "Oriente", "P": "Poniente",
    "NO": "Nororiente", "NP": "Norponiente", "SO": "Suroriente", "SP": "Surponiente",
    "NOSP": "Todas",
}
DROP_COLUMNS = ["published_label"]  # always empty in the export
TYPE_FIXES = {"Penthhouse": "Penthouse", "Ph": "Penthouse", "Clasico": "Clásico", "-": None}


def clean_dir() -> Path:
    return Path(config.CLEAN_DIR)


def clean_path() -> Path:
    return clean_dir() / "listings_clean.csv"


def uf_path() -> Path:
    return Path(config.REFERENCE_DIR) / "uf.csv"


# --- helpers ----------------------------------------------------------------

class Flags:
    """Collects quality-flag codes per row and counts how many rows each step touched."""

    def __init__(self, index: pd.Index):
        self._flags = pd.Series([[] for _ in range(len(index))], index=index, dtype=object)
        self.report: list[tuple[str, int]] = []

    def add(self, mask: pd.Series, code: str) -> int:
        mask = mask.astype("boolean").fillna(False).astype(bool)
        for i in mask[mask].index:
            self._flags.at[i].append(code)
        n = int(mask.sum())
        self.report.append((code, n))
        return n

    def column(self) -> pd.Series:
        return self._flags.map(lambda codes: ";".join(codes) if codes else "")


def blank(df: pd.DataFrame, flags: Flags, col: str, mask: pd.Series, code: str) -> None:
    """Set df[col] to missing where mask is true, and flag those rows."""
    if col not in df:
        return
    mask = mask.astype("boolean").fillna(False).astype(bool) & df[col].notna()
    df.loc[mask, col] = np.nan
    flags.add(mask, code)


def load_uf_table(path: Path | None = None) -> pd.Series:
    t = pd.read_csv(path or uf_path(), parse_dates=["date"], comment="#")
    return t.set_index(t["date"].dt.date)["uf"]


# --- steps --------------------------------------------------------------------

def parse_types(df: pd.DataFrame) -> pd.DataFrame:
    """Step 1: real booleans for yes/no columns, local scrape date."""
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            vals = set(df[col].dropna().astype(str).unique())
            if vals and vals <= {"True", "False"}:
                df[col] = df[col].map({"True": True, "False": False, True: True, False: False}).astype("boolean")
    df["scrape_date"] = pd.to_datetime(df["fetched_at"], utc=True).dt.tz_convert(TZ).dt.date
    return df


def drop_non_rentals(df: pd.DataFrame, report: list) -> pd.DataFrame:
    """Step 2: keep only CLP/UF listings priced like a monthly rent."""
    n0 = len(df)
    df = df[df["currency"].isin(["CLP", "UF"])]
    report.append(("dropped_currency_not_clp_uf", n0 - len(df)))
    n1 = len(df)
    sale = ((df["currency"] == "CLP") & (df["price"] > SALE_MAX_CLP)) | \
           ((df["currency"] == "UF") & (df["price"] > SALE_MAX_UF))
    df = df[~sale]
    report.append(("dropped_sale_price", n1 - len(df)))
    return df.copy()


def convert_currency(df: pd.DataFrame, uf: pd.Series) -> pd.DataFrame:
    """Step 3: price_clp and gastos_comunes_clp, using the UF value of each row's scrape date."""
    missing = sorted(set(df["scrape_date"]) - set(uf.index))
    if missing:
        raise ValueError(f"UF value missing for scrape date(s) {', '.join(map(str, missing))}. "
                         f"Add them to {uf_path()} (date,uf).")
    df["uf_value"] = df["scrape_date"].map(uf)
    is_uf = df["currency"] == "UF"
    df["price_clp"] = np.where(is_uf, df["price"] * df["uf_value"], df["price"]).round()
    if "gastos_comunes" in df:
        gc_uf = df.get("gastos_comunes_currency") == "UF"
        df["gastos_comunes_clp"] = np.where(gc_uf, df["gastos_comunes"] * df["uf_value"], df["gastos_comunes"])
    return df


PLACEHOLDER_SKIP = {"listing_id", "seller_id", "url", "title", "address", "price", "fetched_at", "scrape_date"}


def blank_placeholders(df, flags):
    """Step 4: the 242085 junk value, in any column (numeric, or the same digits as text)."""
    for col in df.columns.difference(sorted(PLACEHOLDER_SKIP), sort=False):
        s = df[col]
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            hit = s == PLACEHOLDER
        elif pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
            hit = s.astype("string").str.strip().isin([str(PLACEHOLDER), f"{PLACEHOLDER}.0"])
        else:
            continue
        if hit.any():
            blank(df, flags, col, hit, f"placeholder_{col}")


def blank_counts(df, flags):
    """Step 5: negative counts and counts above a plausible maximum."""
    for col, mx in MAX_COUNTS.items():
        if col in df:
            blank(df, flags, col, (df[col] < 0) | (df[col] > mx), f"implausible_{col}")
    if "departamentos_por_piso" in df:
        blank(df, flags, "departamentos_por_piso", df["departamentos_por_piso"] < 0, "implausible_departamentos_por_piso")


def fix_age(df, flags):
    """Step 6: a construction year typed into the age field becomes an age; junk is blanked."""
    if "antiguedad" not in df:
        return
    year = pd.to_datetime(df["scrape_date"]).dt.year
    is_year = df["antiguedad"].between(1900, year.max() + 5)
    converted = year - df["antiguedad"]
    df.loc[is_year, "antiguedad"] = converted[is_year]
    flags.add(is_year, "age_from_year")
    blank(df, flags, "antiguedad", (df["antiguedad"] < 0) | (df["antiguedad"] > AGE_MAX), "implausible_antiguedad")


def fix_floor(df, flags):
    """Step 7: floors outside -1..60 are blanked (values like 1101 are unit numbers); conflicts flagged."""
    col = "numero_de_piso_de_la_unidad"
    if col not in df:
        return
    blank(df, flags, col, (df[col] < FLOOR_MIN) | (df[col] > FLOOR_MAX), "implausible_floor")
    if "cantidad_de_pisos" in df:
        flags.add(df[col] > df["cantidad_de_pisos"], "floor_above_building_height")


def check_areas(df, flags):
    """Step 8: implausible areas blanked; usable > total flagged (could be swapped, order uncertain)."""
    if "superficie_util" in df:
        u = df["superficie_util"]
        blank(df, flags, "superficie_util", (u < UTIL_MIN) | (u > UTIL_MAX), "implausible_superficie_util")
    if "superficie_total" in df:
        t = df["superficie_total"]
        blank(df, flags, "superficie_total", (t < 0) | (t > TOTAL_MAX), "implausible_superficie_total")
    if "superficie_de_terraza" in df:
        blank(df, flags, "superficie_de_terraza", df["superficie_de_terraza"] < 0, "implausible_superficie_de_terraza")
    if {"superficie_util", "superficie_total"} <= set(df.columns):
        flags.add(df["superficie_util"] > df["superficie_total"], "util_above_total")


def check_coordinates(df, flags):
    """Step 9: coordinates outside Chile are blanked (both together)."""
    bad = df["latitude"].notna() & ~(df["latitude"].between(*LAT_RANGE) & df["longitude"].between(*LON_RANGE))
    df.loc[bad, ["latitude", "longitude"]] = np.nan
    flags.add(bad, "coordinates_outside_chile")


def clean_common_expenses(df, flags):
    """Step 10: 0 is kept (some rentals genuinely have none); tiny values are placeholders; above 2M or above the rent is implausible."""
    col = "gastos_comunes_clp"
    if col not in df:
        return
    blank(df, flags, col, (df[col] > 0) & (df[col] < GC_MIN_CLP), "gastos_comunes_placeholder")
    blank(df, flags, col, (df[col] > GC_MAX_CLP) | (df[col] > df["price_clp"]), "implausible_gastos_comunes")
    df.loc[df[col].isna(), "gastos_comunes"] = np.nan  # keep the original-currency column consistent


def studio(df, flags):
    """Step 11: one consistent studio indicator; disagreements between the two fields flagged."""
    zero = df["dormitorios"].eq(0)
    mono = df["tipo_de_departamento"].eq("Monoambiente") if "tipo_de_departamento" in df else zero & False
    df["is_studio"] = (zero | mono).astype("boolean")
    flags.add(zero ^ mono, "studio_fields_disagree")


def tidy_categories(df):
    """Step 12: typo fixes and readable orientation labels."""
    if "tipo_de_departamento" in df:
        df["tipo_de_departamento"] = df["tipo_de_departamento"].replace(TYPE_FIXES)
    if "orientacion" in df:
        df["orientacion_label"] = df["orientacion"].map(ORIENTATION_LABELS)


def group_duplicates(df, flags):
    """Step 13: same coordinates, area, bedrooms, bathrooms, price and floor → shared duplicate_group.

    The group id is the smallest listing_id in the group, so it stays stable across re-runs.
    Nothing is dropped; products keep one row per group if they need to.
    """
    keys = ["latitude", "longitude", "superficie_util", "dormitorios", "banos", "price_clp",
            "numero_de_piso_de_la_unidad"]
    usable = df[["latitude", "superficie_util", "price_clp"]].notna().all(axis=1)
    dup = usable & df.duplicated(keys, keep=False)
    gid = df[dup].groupby(keys, dropna=False)["listing_id"].transform("min")
    df["duplicate_group"] = gid.reindex(df.index)
    flags.add(dup, "duplicate")
    multi = df[dup].groupby("duplicate_group")["seller_id"].transform("nunique") > 1
    flags.add(multi.reindex(df.index), "duplicate_across_sellers")


# --- pipeline -------------------------------------------------------------------

def clean(raw: pd.DataFrame, uf: pd.Series) -> tuple[pd.DataFrame, list[tuple[str, int]]]:
    """Apply every step. Returns the cleaned table and (step code, rows affected) pairs."""
    report: list[tuple[str, int]] = [("rows_in", len(raw))]
    df = parse_types(raw.drop(columns=DROP_COLUMNS, errors="ignore"))
    df = drop_non_rentals(df, report)
    df = df.reset_index(drop=True)
    df = convert_currency(df, uf)
    flags = Flags(df.index)
    blank_placeholders(df, flags)
    blank_counts(df, flags)
    fix_age(df, flags)
    fix_floor(df, flags)
    check_areas(df, flags)
    check_coordinates(df, flags)
    clean_common_expenses(df, flags)
    studio(df, flags)
    tidy_categories(df)
    group_duplicates(df, flags)
    df["quality_flags"] = flags.column()
    report += flags.report
    report.append(("rows_out", len(df)))
    return df, report


def run(details_csv: Path | None = None) -> Path:
    src = Path(details_csv) if details_csv else Path(config.DETAILS_DIR) / "details.csv"
    raw = pd.read_csv(src, low_memory=False)
    df, report = clean(raw, load_uf_table())
    out = clean_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    width = max(len(code) for code, _ in report)
    print(f"[CLEAN] {src} → {out}")
    for code, n in report:
        print(f"  {code:<{width}}  {n:>6}")
    return out

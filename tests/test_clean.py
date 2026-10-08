"""Tests for the cleaning stage, one per rule, on small hand-built tables.

Run:  python -m pytest tests    (or: python tests/test_clean.py)
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import clean  # noqa: E402

UF = pd.Series({date(2026, 10, 7): 41114.54})


def row(**kw):
    base = {
        "listing_id": "MLC-1", "title": "Depto", "price": 400000.0, "currency": "CLP",
        "seller_id": 1, "latitude": -33.45, "longitude": -70.65,
        "fetched_at": "2026-10-07T20:51:17+00:00",
        "dormitorios": 1.0, "banos": 1.0, "estacionamientos": 0.0, "bodegas": 0.0,
        "superficie_util": 40.0, "superficie_total": 45.0, "superficie_de_terraza": 3.0,
        "antiguedad": 5.0, "numero_de_piso_de_la_unidad": 4.0, "cantidad_de_pisos": 10.0,
        "departamentos_por_piso": 8.0, "gastos_comunes": 80000.0, "gastos_comunes_currency": "CLP",
        "tipo_de_departamento": "Departamento", "orientacion": "N", "ascensor": "True",
    }
    base.update(kw)
    return base


def run(*rows):
    df, report = clean.clean(pd.DataFrame(rows), UF)
    return df, dict(report)


def flags(df, i=0):
    return set(filter(None, df.loc[i, "quality_flags"].split(";")))


def test_clean_row_untouched():
    df, _ = run(row())
    assert flags(df) == set()
    assert df.loc[0, "price_clp"] == 400000
    assert df.loc[0, "ascensor"] == True  # noqa: E712  (nullable boolean)


def test_drops_other_currencies_and_sales():
    df, rep = run(row(listing_id="a", currency="USD", price=2500.0),
                  row(listing_id="b", price=65_000_000.0),
                  row(listing_id="c", currency="UF", price=2400.0),
                  row(listing_id="d", currency="UF", price=33.0),
                  row(listing_id="e", title="Venta o arriendo depto", price=260000.0))
    assert list(df["listing_id"]) == ["d", "e"]  # a rental price wins over a "venta" title
    assert rep["dropped_currency_not_clp_uf"] == 1 and rep["dropped_sale_price"] == 2


def test_uf_conversion_uses_scrape_date_value():
    df, _ = run(row(currency="UF", price=20.0, gastos_comunes=2.0, gastos_comunes_currency="UF"))
    assert df.loc[0, "price_clp"] == round(20 * 41114.54)
    assert abs(df.loc[0, "gastos_comunes_clp"] - 2 * 41114.54) < 1e-6


def test_missing_uf_date_is_an_error():
    try:
        run(row(fetched_at="2026-11-01T15:00:00+00:00"))
    except ValueError as e:
        assert "2026-11-01" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_placeholder_blanked():
    df, _ = run(row(bodegas=242085.0, departamentos_por_piso=242085.0, numero_de_torre=242085.0,
                    disponible_desde="242085"),
                row(listing_id="b", price=410000.0, numero_de_torre=2.0, disponible_desde="Inmediata"))
    assert df.loc[0, ["bodegas", "departamentos_por_piso", "numero_de_torre", "disponible_desde"]].isna().all()
    assert {"placeholder_bodegas", "placeholder_departamentos_por_piso", "placeholder_numero_de_torre",
            "placeholder_disponible_desde"} <= flags(df)
    assert df.loc[1, "numero_de_torre"] == 2 and df.loc[1, "disponible_desde"] == "Inmediata"


def test_count_caps():
    df, _ = run(row(dormitorios=1234.0, banos=-1.0, estacionamientos=65000.0, bodegas=5.0),
                row(listing_id="b", bodegas=6.0))
    assert df.loc[0, ["dormitorios", "banos", "estacionamientos"]].isna().all()
    assert df.loc[0, "bodegas"] == 5          # 5 storage units is allowed
    assert pd.isna(df.loc[1, "bodegas"])      # 6 is not


def test_age_year_converted_and_junk_blanked():
    df, _ = run(row(antiguedad=2016.0), row(listing_id="b", antiguedad=-18196.0),
                row(listing_id="c", antiguedad=2026.0))
    assert df.loc[0, "antiguedad"] == 10 and "age_from_year" in flags(df, 0)
    assert pd.isna(df.loc[1, "antiguedad"])
    assert df.loc[2, "antiguedad"] == 0


def test_floor_rules():
    df, _ = run(row(numero_de_piso_de_la_unidad=1101.0), row(listing_id="b", numero_de_piso_de_la_unidad=-1.0),
                row(listing_id="c", numero_de_piso_de_la_unidad=12.0, cantidad_de_pisos=8.0))
    assert pd.isna(df.loc[0, "numero_de_piso_de_la_unidad"])        # unit number → blank, not converted
    assert df.loc[1, "numero_de_piso_de_la_unidad"] == -1
    assert df.loc[2, "numero_de_piso_de_la_unidad"] == 12 and "floor_above_building_height" in flags(df, 2)


def test_area_rules():
    df, _ = run(row(superficie_util=9.0), row(listing_id="b", superficie_util=10.0),
                row(listing_id="c", superficie_total=300000.0),
                row(listing_id="d", superficie_util=80.0, superficie_total=60.0))
    assert pd.isna(df.loc[0, "superficie_util"]) and df.loc[1, "superficie_util"] == 10
    assert pd.isna(df.loc[2, "superficie_total"])
    assert df.loc[3, "superficie_util"] == 80 and "util_above_total" in flags(df, 3)


def test_coordinates_outside_chile_blanked():
    df, _ = run(row(latitude=20.21, longitude=-87.47))
    assert df.loc[0, ["latitude", "longitude"]].isna().all()


def test_common_expenses():
    df, _ = run(row(gastos_comunes=0.0), row(listing_id="b", gastos_comunes=2_000_000.0, price=3_000_000.0),
                row(listing_id="c", gastos_comunes=2_100_000.0, price=3_000_000.0),
                row(listing_id="d", gastos_comunes=500000.0, price=390000.0),
                row(listing_id="e", gastos_comunes=1.0, price=410000.0),
                row(listing_id="f", gastos_comunes=10000.0, price=420000.0))
    assert df.loc[0, "gastos_comunes_clp"] == 0 and flags(df, 0) == set()   # a real zero is kept
    assert pd.isna(df.loc[4, "gastos_comunes_clp"]) and "gastos_comunes_placeholder" in flags(df, 4)
    assert df.loc[5, "gastos_comunes_clp"] == 10000
    assert df.loc[1, "gastos_comunes_clp"] == 2_000_000
    assert pd.isna(df.loc[2, "gastos_comunes_clp"]) and pd.isna(df.loc[3, "gastos_comunes_clp"])


def test_studio_and_categories():
    df, _ = run(row(dormitorios=0.0), row(listing_id="b", tipo_de_departamento="Monoambiente"),
                row(listing_id="c", tipo_de_departamento="Penthhouse", orientacion="P"))
    assert df.loc[0, "is_studio"] and df.loc[1, "is_studio"] and not df.loc[2, "is_studio"]
    assert "studio_fields_disagree" in flags(df, 0) and "studio_fields_disagree" in flags(df, 1)
    assert df.loc[2, "tipo_de_departamento"] == "Penthouse" and df.loc[2, "orientacion_label"] == "Poniente"


def test_duplicates_grouped_not_dropped():
    df, _ = run(row(listing_id="MLC-2", seller_id=1), row(listing_id="MLC-1", seller_id=2),
                row(listing_id="MLC-3", price=500000.0))
    assert len(df) == 3
    assert list(df["duplicate_group"][:2]) == ["MLC-1", "MLC-1"] and pd.isna(df.loc[2, "duplicate_group"])
    assert "duplicate_across_sellers" in flags(df, 0)



def test_published_label_dropped():
    df, _ = run(row(published_label=None))
    assert "published_label" not in df.columns
    df, _ = run(row())  # absent column is fine too
    assert "published_label" not in df.columns


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")

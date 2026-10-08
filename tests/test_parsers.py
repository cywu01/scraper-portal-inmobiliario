"""Parser tests built from real Portal Inmobiliario markup (trimmed, captured 2026-10-07).

Run:  python -m pytest tests    (or: python tests/test_parsers.py)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import collect_ids  # noqa: E402
import fetch_details  # noqa: E402

CARDS = {
    "clp": '<li class="ui-search-layout__item"><a href="https://portalinmobiliario.com/MLC-2303303815-comodo-amplio-luminoso-_JM#polycard_client=search-desktop" class="poly-component__title">x</a><div class="poly-component__price"><div class="poly-price__current"><span class="andes-money-amount poly-price__amount" aria-label="1499990 pesos chilenos">$1.499.990</span></div></div></li>',
    "discCLP": '<li class="ui-search-layout__item"><a href="https://portalinmobiliario.com/MLC-2238185153-espectacular-depto-_JM#polycard_client=search-desktop" class="poly-component__title">x</a><div class="poly-component__price"><s class="andes-money-amount poly-price__previous andes-money-amount--previous" aria-label="Antes: 2000000 pesos chilenos">$2.000.000</s><div class="poly-price__current"><span class="andes-money-amount poly-price__amount" aria-label="Ahora: 1800000 pesos chilenos">$1.800.000</span><span class="poly-price__disc-label"> BAJÓ DE PRECIO</span></div></div></li>',
    "discUF": '<li class="ui-search-layout__item"><a href="https://portalinmobiliario.com/MLC-4410911154-departamento-amoblado-_JM#polycard" class="poly-component__title">x</a><div class="poly-component__price"><s class="andes-money-amount poly-price__previous andes-money-amount--previous" aria-label="Antes: 60 unidades de fomento">UF 60</s><div class="poly-price__current"><span class="andes-money-amount poly-price__amount" aria-label="Ahora: 50 unidades de fomento">UF 50</span></div></div></li>',
    "ufCents": '<li class="ui-search-layout__item"><a href="https://portalinmobiliario.com/MLC-2282572639-solo-amoblado-_JM#polycard" class="poly-component__title">x</a><div class="poly-component__price"><div class="poly-price__current"><span class="andes-money-amount poly-price__amount" aria-label="29 unidades de fomento con 50 centavos">UF 29,50</span></div></div></li>',
    "ad": '<li class="ui-search-layout__item ui-search-layout__item--intervention"><a href="https://x/MLC-1-_JM" class="poly-component__title">ad</a></li>',
}

SEARCH_HTML = ('<script>melidata("add","event_data",{"vertical":"REAL_ESTATE","query":"","limit":50,"offset":0,"total":715,"category_id":"MLC1459"})</script>'
               '<ol class="ui-search-layout">' + "".join(CARDS.values()) + "</ol>")

DETAIL_STATE = {
    "id": "MLC4520042124",
    "components": {
        "content_left": [
            {"map_info": {"location": {"latitude": "-33.5199874", "longitude": "-70.6532387"}}},
            {"components": [{"specs": [
                {"type": "TITLE_STRIPED", "attributes": [
                    {"id": "Superficie total", "text": "33 m²"}, {"id": "Superficie útil", "text": "32 m²"},
                    {"id": "Dormitorios", "text": "1"}, {"id": "Baños", "text": "1"},
                    {"id": "Número de piso de la unidad", "text": "6"}, {"id": "Antigüedad", "text": "2 años"},
                    {"id": "Orientación", "text": "P"}, {"id": "Gastos comunes", "text": "60.000 CLP"},
                    {"id": "Amoblado", "text": "No"}]},
                {"type": "TITLE_STRIPED", "attributes": [
                    {"id": "Gimnasio", "text": "Sí"}, {"id": "Walk-in clóset", "text": "Sí"}]},
            ]}]},
        ],
        "location_and_points": {
            "map_info": {"location": {"latitude": "-33.5199874", "longitude": "-70.6532387"}},
            "content_rows": [{"icon": {"id": "LOCATION_RE"}, "title": {"text": "Santa Elisa, Lo Ovalle, La Cisterna, RM (Metropolitana)", "color": "BLACK"}}],
        },
        "header": {"title": "Edificio Santa Elisa 541 1d1b Piso 6 (180681)",
                   "subtitle": "Departamento en Arriendo  |  Publicado hace 41 días"},
        "price": {"price": {"value": 280000, "currency_id": "CLP"}},
    },
    "track": {"melidata_event": {"event_data": {
        "seller_id": 1210714390, "seller_type": "real_estate_agency", "price": 280000, "currency_id": "CLP",
        "item_id": "MLC4520042124", "item_condition": "used", "listing_type_id": "gold_premium",
        "item_status": "active", "domain_id": "MLC-APARTMENTS_FOR_RENT", "city": "La Cisterna",
        "neighborhood": "Lo Ovalle", "state": "RM (Metropolitana)"}}},
}
DETAIL_HTML = ('<html><body><script id="__NORDIC_RENDERING_CTX__" nonce="x">_n.ctx.r='
               + json.dumps({"flags": {}, "appProps": {"pageProps": {"initialState": DETAIL_STATE}}}, ensure_ascii=False)
               + ';_n.ctx.r.assets.manifest=new Map([["a","b"]]);</script></body></html>')


def test_search_page():
    page = collect_ids.parse_search_page(SEARCH_HTML)
    assert page.total == 715
    assert set(page.items) == {"MLC-2303303815", "MLC-2238185153", "MLC-4410911154", "MLC-2282572639"}  # ad skipped
    get = lambda i: (page.items[i]["price"], page.items[i]["currency"], page.items[i]["price_previous"])
    assert get("MLC-2303303815") == (1499990, "CLP", None)
    assert get("MLC-2238185153") == (1800000, "CLP", 2000000)   # current price, not the crossed-out one
    assert get("MLC-4410911154") == (50, "UF", 60)
    assert get("MLC-2282572639") == (29.5, "UF", None)
    assert collect_ids.parse_price_label("360000 dólares") == (360000, "USD")
    assert page.items["MLC-2303303815"]["url"] == "https://portalinmobiliario.com/MLC-2303303815-comodo-amplio-luminoso-_JM"


def test_search_url():
    u = collect_ids.search_url
    base = "https://www.portalinmobiliario.com/arriendo/departamento/propiedades-usadas/santiago-metropolitana"
    assert u("santiago", "metropolitana") == base
    assert u("santiago", "metropolitana", 49) == base + "/_Desde_49_NoIndex_True"
    assert u("santiago", "metropolitana", 1, 0, 400000) == base + "/_PriceRange_0CLP-400000CLP"
    assert u("santiago", "metropolitana", 49, 0, 400000) == base + "/_Desde_49_PriceRange_0CLP-400000CLP_NoIndex_True"


def test_detail_page():
    rec = fetch_details.parse_detail(DETAIL_HTML, datetime(2026, 10, 7, tzinfo=timezone.utc))
    assert rec["title"] == "Edificio Santa Elisa 541 1d1b Piso 6 (180681)"
    assert (rec["price"], rec["currency"]) == (280000, "CLP")
    assert (rec["latitude"], rec["longitude"]) == (-33.5199874, -70.6532387)
    assert rec["address"] == "Santa Elisa, Lo Ovalle, La Cisterna, RM (Metropolitana)"
    assert (rec["commune_name"], rec["neighborhood"], rec["seller_type"]) == ("La Cisterna", "Lo Ovalle", "real_estate_agency")
    assert rec["published_label"] == "hace 41 días"
    assert rec["days_on_site"] == 41 and rec["published_date_approx"] == "2026-08-27"
    assert rec["specs"]["Antigüedad"] == "2 años" and rec["specs"]["Walk-in clóset"] == "Sí"
    assert len(rec["specs"]) == 11
    assert "description" not in rec


def test_value_conversion():
    c = fetch_details._convert
    assert c("33 m²") == 33.0 and c("1.250 m²") == 1250.0 and c("45,5 m²") == 45.5
    assert c("2 años") == 2 and c("1 año") == 1 and c("6") == 6
    assert c("Sí") is True and c("No") is False
    assert c("60.000 CLP") == (60000.0, "CLP") and c("3,5 UF") == (3.5, "UF")
    assert c("P") == "P"
    assert fetch_details._slug("Número de piso de la unidad") == "numero_de_piso_de_la_unidad"
    assert fetch_details._days_on_site("Publicado hace 3 meses") == 90
    assert fetch_details._days_on_site("Publicado hace 1 año") == 365
    assert fetch_details._days_on_site("Departamento en Arriendo  |  Publicado esta semana") is None
    assert fetch_details._published_label("Departamento en Arriendo  |  Publicado esta semana") == "esta semana"
    assert fetch_details._days_on_site("Departamento en Arriendo  |  Publicado hoy") == 0
    assert c("2.026 años") == 2026 and c("-0 años") == 0 and c("-1 m²") == -1.0 and c("1,5 años") == 1.5


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)

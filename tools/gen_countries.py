"""One-time generator for config/countries.yaml.

Merges World Bank country metadata (ISO3, region, income) with the public
country-codes dataset (continent, UN subregion) and applies curated display names.
Run: python tools/gen_countries.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "config" / "countries.yaml"
REPORT = ROOT / "tools" / "countries_report.txt"

WB_URL = "https://api.worldbank.org/v2/country?format=json&per_page=400"
CC_URL = "https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv"

TERRITORIES = {
    "ABW", "ASM", "BMU", "VGB", "CYM", "CHI", "CUW", "FRO", "PYF", "GIB", "GRL",
    "GUM", "HKG", "IMN", "MAC", "MAF", "MNP", "NCL", "PRI", "SXM", "TCA", "VIR",
}
OBSERVERS = {"VAT", "PSE"}
DISPUTED = {"TWN", "XKX"}

CONTINENTS = {
    "AF": "Africa", "AS": "Asia", "EU": "Europe", "NA": "North America",
    "SA": "South America", "OC": "Oceania", "AN": "Antarctica",
}

RENAMES = {
    "Bahamas, The": "Bahamas",
    "Gambia, The": "Gambia",
    "Egypt, Arab Rep.": "Egypt",
    "Yemen, Rep.": "Yemen",
    "Venezuela, RB": "Venezuela",
    "Iran, Islamic Rep.": "Iran",
    "Korea, Rep.": "South Korea",
    "Korea, Dem. People's Rep.": "North Korea",
    "Russian Federation": "Russia",
    "Slovak Republic": "Slovakia",
    "Lao PDR": "Laos",
    "Kyrgyz Republic": "Kyrgyzstan",
    "Brunei Darussalam": "Brunei",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "Naoero": "Nauru",
    "Micronesia, Fed. Sts.": "Micronesia",
    "Virgin Islands (U.S.)": "U.S. Virgin Islands",
    "West Bank and Gaza": "Palestine",
    "Hong Kong SAR, China": "Hong Kong",
    "Macao SAR, China": "Macao",
    "Syrian Arab Republic": "Syria",
    "Somalia, Fed. Rep.": "Somalia",
    "Congo, Dem. Rep.": "DR Congo",
    "Congo, Rep.": "Republic of the Congo",
    "St. Kitts and Nevis": "Saint Kitts and Nevis",
    "St. Lucia": "Saint Lucia",
    "St. Martin (French part)": "Saint Martin",
    "St. Vincent and the Grenadines": "Saint Vincent and the Grenadines",
    "Turkiye": "Türkiye",
    "Viet Nam": "Vietnam",
    "Curacao": "Curaçao",
    "Sao Tome and Principe": "São Tomé and Príncipe",
    "Antigua and Barbuda": "Antigua and Barbuda",
}

EXTRA = [
    {
        "iso3": "TWN",
        "name": "Taiwan",
        "official_name": "Republic of China (Taiwan)",
        "entity_type": "disputed",
        "un_member": False,
        "region": "East Asia & Pacific",
        "subregion": "Eastern Asia",
        "continent": "Asia",
        "income_group": "High income",
        "is_default": True,
    },
    {
        "iso3": "VAT",
        "name": "Vatican City",
        "official_name": "Holy See",
        "entity_type": "observer",
        "un_member": False,
        "region": "Europe & Central Asia",
        "subregion": "Southern Europe",
        "continent": "Europe",
        "income_group": "High income",
        "is_default": True,
    },
]


def clean_name(name: str) -> str:
    name = RENAMES.get(name, name)
    name = name.replace(", The", "").strip()
    name = re.sub(r"\s+SAR, China$", "", name)
    return name


def main() -> int:
    wb = requests.get(WB_URL, timeout=60).json()
    wb_rows = [c for c in wb[1] if c["region"]["id"] != "NA"]

    cc_resp = requests.get(CC_URL, timeout=90)
    cc_resp.encoding = "utf-8"
    import csv

    cc = {}
    for row in csv.DictReader(io.StringIO(cc_resp.text)):
        code = (row.get("ISO3166-1-Alpha-3") or "").strip()
        if code:
            cc[code] = row

    records = []
    for c in wb_rows:
        iso3 = c["id"].strip().upper()
        if iso3 in TERRITORIES:
            entity_type = "territory"
        elif iso3 in OBSERVERS:
            entity_type = "observer"
        elif iso3 in DISPUTED:
            entity_type = "disputed"
        else:
            entity_type = "state"

        meta = cc.get(iso3, {})
        display = clean_name(c["name"].strip())
        official = (meta.get("official_name_en") or "").strip() or display
        continent = CONTINENTS.get((meta.get("Continent") or "").strip(), "")
        subregion = (meta.get("Sub-region Name") or "").strip()
        if not continent:
            continent = "Europe" if iso3 in {"CHI", "XKX"} else ""

        records.append(
            {
                "iso3": iso3,
                "name": display,
                "official_name": official,
                "entity_type": entity_type,
                "un_member": entity_type == "state",
                "region": c["region"]["value"].strip(),
                "subregion": subregion,
                "continent": continent,
                "income_group": c["incomeLevel"]["value"].strip(),
                "is_default": entity_type != "territory",
            }
        )

    have = {r["iso3"] for r in records}
    records.extend(dict(r) for r in EXTRA if r["iso3"] not in have)
    records.sort(key=lambda r: r["name"].lower())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        yaml.safe_dump({"countries": records}, fh, allow_unicode=True, sort_keys=False, width=120)

    with REPORT.open("w", encoding="utf-8") as fh:
        fh.write(f"entities={len(records)}\n")
        for r in records:
            fh.write(
                f"{r['iso3']} | {r['entity_type']:<9} | {r['name']} | {r['continent']} | "
                f"{r['subregion']} | {r['region']} | {r['income_group']}\n"
            )
    print(f"wrote {len(records)} entities to {OUT}")
    counts = {}
    for r in records:
        counts[r["entity_type"]] = counts.get(r["entity_type"], 0) + 1
    print("entity types:", counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())

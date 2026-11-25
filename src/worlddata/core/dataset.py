"""In-memory analysis dataset built from the SQLite snapshot."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..db import Repository


@dataclass(frozen=True)
class Dataset:
    values: pd.DataFrame  # index: iso3, columns: indicator_id
    years: pd.DataFrame  # same shape, integer source years
    countries: pd.DataFrame  # indexed by iso3
    indicators: pd.DataFrame  # indexed by indicator id
    cutoff: int

    @property
    def iso3(self) -> list[str]:
        return list(self.values.index)

    @property
    def indicator_ids(self) -> list[str]:
        return list(self.values.columns)

    def meta(self, indicator_id: str) -> pd.Series:
        return self.indicators.loc[indicator_id]

    def name(self, iso3: str) -> str:
        try:
            return str(self.countries.loc[iso3, "name"])
        except KeyError:
            return iso3

    def indicator_name(self, indicator_id: str) -> str:
        try:
            return str(self.indicators.loc[indicator_id, "name"])
        except KeyError:
            return indicator_id

    def subset_countries(self, iso3: list[str]) -> Dataset:
        iso3 = [c for c in iso3 if c in self.values.index]
        return Dataset(
            values=self.values.loc[iso3],
            years=self.years.loc[iso3],
            countries=self.countries.loc[iso3],
            indicators=self.indicators,
            cutoff=self.cutoff,
        )

    def subset_indicators(self, indicator_ids: list[str]) -> Dataset:
        ids = [i for i in indicator_ids if i in self.values.columns]
        return Dataset(
            values=self.values[ids],
            years=self.years[ids],
            countries=self.countries,
            indicators=self.indicators.loc[ids],
            cutoff=self.cutoff,
        )

    def with_indicators(self, indicator_ids: list[str]) -> Dataset:
        ids = list(dict.fromkeys([*self.indicator_ids, *indicator_ids]))
        return self.subset_indicators(ids)

    def series(self, indicator_id: str) -> pd.Series:
        return self.values[indicator_id].dropna()

    def year_series(self, indicator_id: str) -> pd.Series:
        return self.years[indicator_id].reindex(self.series(indicator_id).index)


def load_dataset(
    repo: Repository,
    cutoff: int,
    *,
    include_territories: bool = False,
    indicator_ids: list[str] | None = None,
    domain_order: list[str] | None = None,
) -> Dataset:
    indicators = repo.indicators(include_hidden=False, with_data=True)
    if indicator_ids is not None:
        indicators = indicators[indicators["id"].isin(indicator_ids)]
    indicators = indicators.copy()
    order = {d: i for i, d in enumerate(domain_order or [])}
    indicators["_domain_order"] = indicators["domain"].map(lambda d: order.get(d, 999))
    indicators = indicators.sort_values(
        ["_domain_order", "name"], kind="stable"
    ).drop(columns=["_domain_order"]).set_index("id", drop=False)

    countries = repo.countries(include_territories=include_territories).set_index(
        "iso3", drop=False
    )
    latest = repo.latest(cutoff, indicators=list(indicators["id"]))
    if latest.empty:
        values = pd.DataFrame(index=countries.index, columns=indicators.index, dtype=float)
        years = pd.DataFrame(index=countries.index, columns=indicators.index, dtype="Int64")
    else:
        values = latest.pivot(index="iso3", columns="indicator_id", values="value")
        years = latest.pivot(index="iso3", columns="indicator_id", values="year")
        values = values.reindex(index=countries.index, columns=indicators.index)
        years = years.reindex(index=countries.index, columns=indicators.index)

    values = values.astype(float)
    years = years.astype("Int64")
    return Dataset(
        values=values,
        years=years,
        countries=countries,
        indicators=indicators,
        cutoff=cutoff,
    )


def year_stats(years: pd.Series) -> dict:
    clean = years.dropna()
    if clean.empty:
        return {"median": None, "min": None, "max": None}
    return {
        "median": float(clean.median()),
        "min": int(clean.min()),
        "max": int(clean.max()),
    }

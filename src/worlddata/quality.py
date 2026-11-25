"""Coverage reports, data-quality gates and quarantine artifacts."""

from __future__ import annotations

import pandas as pd

from .config import Config
from .paths import Paths


def coverage_report(
    config: Config,
    observations: pd.DataFrame,
    default_iso3: set[str],
    cutoff_year: int,
) -> pd.DataFrame:
    rows = []
    if observations.empty:
        latest = observations
    else:
        latest = (
            observations[observations["iso3"].isin(default_iso3)]
            .sort_values("year", kind="stable")
            .drop_duplicates(subset=["iso3", "indicator_id"], keep="last")
        )
    n_countries = max(len(default_iso3), 1)

    for indicator in config.indicators:
        subset = latest[latest["indicator_id"] == indicator.id]
        n = int(subset["iso3"].nunique())
        stale = int((subset["year"] < cutoff_year).sum())
        rows.append(
            {
                "indicator_id": indicator.id,
                "name": indicator.name,
                "domain": indicator.domain,
                "unit": indicator.unit,
                "source_id": indicator.source,
                "hidden": int(indicator.hidden),
                "n_countries": n,
                "pct": round(n / n_countries * 100, 2),
                "n_missing": n_countries - n,
                "n_stale": stale,
                "latest_year": int(subset["year"].max()) if n else None,
                "median_year": float(subset["year"].median()) if n else None,
                "n_observations": int((observations["indicator_id"] == indicator.id).sum()),
                "aggregation": indicator.aggregation,
                "attribution": indicator.attribution,
            }
        )
    return pd.DataFrame(rows).sort_values(["domain", "pct"], ascending=[True, False])


def evaluate_gates(
    config: Config,
    report: pd.DataFrame,
    observations: pd.DataFrame,
    unresolved: pd.DataFrame,
    *,
    min_covered_indicators: int = 50,
    min_pct: float = 60.0,
) -> list[tuple[str, bool, str]]:
    gates: list[tuple[str, bool, str]] = []

    visible_auto = report[(report["hidden"] == 0) & (report["source_id"] != "manual")]
    covered = int((visible_auto["pct"] >= min_pct).sum())
    gates.append(
        (
            "indicator coverage",
            covered >= min_covered_indicators,
            f"{covered} of {len(visible_auto)} automated visible indicators have >= {min_pct:g}% country coverage "
            f"(gate: {min_covered_indicators})",
        )
    )

    dupes = int(observations.duplicated(subset=["iso3", "indicator_id", "year"]).sum())
    gates.append(("unique observations", dupes == 0, f"{dupes} duplicate (iso3, indicator, year) keys"))

    finite = bool(observations["value"].map(lambda v: v == v).all())
    gates.append(("finite values", finite, "non-finite values present in DB" if not finite else "ok"))

    total = max(len(observations), 1)
    unresolved_n = int(unresolved["n"].sum()) if not unresolved.empty else 0
    share = unresolved_n / total * 100
    gates.append(
        (
            "country resolution",
            share <= 1.0,
            f"{unresolved_n} unresolved source rows ({share:.2f}% of observations; gate <= 1%)",
        )
    )

    future = int((observations["year"] > pd.Timestamp.now(tz="UTC").year + 1).sum())
    gates.append(("year sanity", future == 0, f"{future} observations more than one year in the future"))

    manual = report[report["source_id"] == "manual"]
    if not manual.empty:
        missing_manual = int((manual["n_countries"] == 0).sum())
        gates.append(
            (
                "manual imports",
                True,
                f"{missing_manual} manual indicators have no imported data yet (informational)",
            )
        )
    return gates


def write_artifacts(
    paths: Paths,
    report: pd.DataFrame,
    rejected: pd.DataFrame,
    unresolved: pd.DataFrame,
    skipped: pd.DataFrame,
) -> None:
    paths.ensure()
    report.to_csv(paths.quality_report, index=False, encoding="utf-8-sig")
    rejected.to_csv(paths.rejected, index=False, encoding="utf-8-sig")
    unresolved_path = paths.data / "unresolved.csv"
    skipped_path = paths.data / "skipped_entities.csv"
    if unresolved.empty:
        unresolved_path.unlink(missing_ok=True)
    else:
        unresolved.to_csv(unresolved_path, index=False, encoding="utf-8-sig")
    if skipped.empty:
        skipped_path.unlink(missing_ok=True)
    else:
        skipped.to_csv(skipped_path, index=False, encoding="utf-8-sig")

"""Shared application state: database repository, dataset cache and group set."""

from __future__ import annotations

from collections import OrderedDict

import pandas as pd

from ..config import Config
from ..core.dataset import Dataset, load_dataset
from ..core.groups import GroupSet, load_group_set
from ..db import Repository
from ..paths import Paths
from .settings import Settings


class AppContext:
    def __init__(
        self,
        paths: Paths,
        config: Config,
        repo: Repository,
        manifest: dict,
        settings: Settings,
    ):
        self.paths = paths
        self.config = config
        self.repo = repo
        self.manifest = manifest
        self.settings = settings
        self._dataset: Dataset | None = None
        self._dataset_key: tuple | None = None
        self._group_set: GroupSet | None = None
        self._corr_cache: OrderedDict[tuple, pd.DataFrame] = OrderedDict()
        self._pairs_cache: OrderedDict[tuple, tuple] = OrderedDict()
        self._indicator_rows = repo.indicators(include_hidden=False, with_data=False)

    # ------------------------------------------------------------------ dataset
    def dataset(self, extra_indicators: list[str] | None = None) -> Dataset:
        key = (
            self.settings.cutoff_year,
            self.settings.include_territories,
            tuple(extra_indicators or ()),
        )
        if self._dataset is None or self._dataset_key != key:
            self._dataset = load_dataset(
                self.repo,
                cutoff=self.settings.cutoff_year,
                include_territories=self.settings.include_territories,
                indicator_ids=extra_indicators,
                domain_order=self.config.domain_order,
            )
            self._dataset_key = key
            self._corr_cache.clear()
            self._pairs_cache.clear()
        return self._dataset

    def invalidate(self) -> None:
        self._dataset = None
        self._dataset_key = None
        self._group_set = None
        self._corr_cache.clear()
        self._pairs_cache.clear()

    # ------------------------------------------------------------------- groups
    def group_set(self) -> GroupSet:
        if self._group_set is None:
            self._group_set = load_group_set(self.repo, self.paths.groups_local)
        return self._group_set

    def reload_groups(self) -> GroupSet:
        self._group_set = load_group_set(self.repo, self.paths.groups_local)
        return self._group_set

    # -------------------------------------------------------------------- cache
    def cached(self, key: tuple, *, limit: int = 8):
        return self._pairs_cache.get(key)

    def remember(self, key: tuple, value, limit: int = 8) -> None:
        self._pairs_cache[key] = value
        self._pairs_cache.move_to_end(key)
        while len(self._pairs_cache) > limit:
            self._pairs_cache.popitem(last=False)

    # ------------------------------------------------------------------- labels
    def indicator_label(self, indicator_id: str) -> str:
        match = self._indicator_rows[self._indicator_rows["id"] == indicator_id]
        if match.empty:
            return indicator_id
        return f"{match.iloc[0]['name']} ({match.iloc[0]['unit']})"

    def indicator_rows(self, with_data: bool = True) -> pd.DataFrame:
        frame = (
            self._indicator_rows
            if with_data
            else self.repo.indicators(include_hidden=False, with_data=False)
        )
        order = {d: i for i, d in enumerate(self.config.domain_order)}
        frame = frame.copy()
        frame["_order"] = frame["domain"].map(lambda d: order.get(d, 999))
        return frame.sort_values(["_order", "name"], kind="stable").reset_index(drop=True)

    def country_rows(self) -> pd.DataFrame:
        return self.repo.countries(include_territories=self.settings.include_territories)

    def build_info(self) -> dict:
        meta = self.repo.meta()
        meta.update(
            {
                "db_size_mb": round(self.paths.db.stat().st_size / 1e6, 1)
                if self.paths.db.exists()
                else 0.0,
                "cutoff": self.settings.cutoff_year,
            }
        )
        return meta

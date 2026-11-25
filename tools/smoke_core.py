from worlddata.config import load_config
from worlddata.core.correlations import CorrOptions, correlation_pairs, matrix_from_pairs, pair_points
from worlddata.core.dataset import load_dataset
from worlddata.core.groups import compare, load_group_set, member_table, summarize
from worlddata.core.views import compare_percentiles, country_profile, domain_coverage, rank_table
from worlddata.db import open_repository
from worlddata.paths import get_paths

paths = get_paths()
config = load_config(paths)
repo = open_repository(paths)
try:
    ds = load_dataset(repo, 2015, domain_order=config.domain_order)
    print("dataset", ds.values.shape, "indicators", ds.indicator_ids)
    ind = ds.indicator_ids[0]
    print(rank_table(ds, ind).head(3).to_string())
    print("profile rows", len(country_profile(ds, "USA")))
    print("domains", domain_coverage(ds).to_dict("records")[:2])
    opts = CorrOptions(log=True)
    if len(ds.indicator_ids) >= 2:
        pairs = correlation_pairs(ds, opts, ds.indicator_ids)
        print(pairs[["a", "b", "n", "r", "q", "rho"]].to_string())
        print("matrix", matrix_from_pairs(pairs, ds.indicator_ids).shape)
        print("points", len(pair_points(ds, ds.indicator_ids[0], ds.indicator_ids[1], opts)))
    gs = load_group_set(repo, paths.groups_local)
    target = [i for i in ("gdp_per_capita_ppp", "gdp_per_capita") if i in ds.indicator_ids]
    if target:
        s = summarize(ds, gs, target[0], ["eu", "nato"])
        print(s.table[["group", "n_data", "aggregate"]].to_string())
        c = compare(ds, gs, target[0], ["eu", "nato"])
        print("kruskal", c.kruskal_p)
        print("members", len(member_table(ds, gs, "eu", target[0])))
    print("percentiles", compare_percentiles(ds, ["USA", "DEU"]).shape)
finally:
    repo.close()
print("OK")

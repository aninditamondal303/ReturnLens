"""The generator is deterministic and the committed CSVs match a fresh run."""
import importlib.util
import json
import sys

import pandas as pd
import pytest

from conftest import REPO


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("generate_data", REPO / "scripts" / "generate_data.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["generate_data"] = mod
    spec.loader.exec_module(mod)
    return mod


def _csv_texts(generator, seed):
    frames = generator.generate(seed)
    frames["orders"] = frames["orders"][generator.ORDER_COLUMNS]
    return {name: df.to_csv(index=False, lineterminator="\n") for name, df in frames.items()}


def test_same_seed_reproduces_committed_csvs(generator):
    """
    Same seed + same NumPy/pandas versions -> byte-identical files on disk.
    NumPy only guarantees identical random streams within one version, so when the installed
    versions differ from those recorded in dataset_info.json we instead check that two runs
    with the same seed are identical (determinism).
    """
    info_path = REPO / "data" / "dataset_info.json"
    recorded = json.loads(info_path.read_text()).get("generated_with", {}) if info_path.exists() else {}
    first = _csv_texts(generator, generator.DEFAULT_SEED)
    current = generator.generator_versions()
    if recorded.get("numpy") == current["numpy"] and recorded.get("pandas") == current["pandas"]:
        for name, text in first.items():
            on_disk = (REPO / "data" / f"{name}.csv").read_text(encoding="utf-8").replace("\r\n", "\n")
            assert text == on_disk, f"{name}.csv differs from a fresh run with the same seed"
    else:
        second = _csv_texts(generator, generator.DEFAULT_SEED)
        assert first == second, "two runs with the same seed produced different data"


def test_dataset_meets_targets(real_frames):
    o, r, p = real_frames["orders"], real_frames["returns"], real_frames["products"]
    assert 15_000 <= len(o) <= 25_000
    assert 100 <= len(p) <= 250
    assert 8 <= p["category"].nunique() <= 12
    assert 8 <= o["shipping_region"].nunique() <= 12
    assert pd.to_datetime(o["order_date"]).dt.to_period("M").nunique() == 12
    elig = o[o["order_status"] != "Cancelled"]
    ref = r[r["return_status"] == "Refunded"]
    rate = pd.to_numeric(ref["return_quantity"]).sum() / pd.to_numeric(elig["quantity"]).sum()
    assert 0.05 <= rate <= 0.15

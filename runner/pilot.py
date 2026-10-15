"""Pilot-10% LightGBM execution path (ADR-010 §5, rev 2).

Wires the config-driven LightGBM baseline into the provenance machinery:

1. load BODMAS npz (read-only, ``allow_pickle=False``);
2. build the 10% stratified subset (``bytelens.eval.subsets``) — frozen ID
   list, seed from config;
3. build the requested split protocol over the subset IDs (npz-only mode:
   ``random`` or ``near_duplicate_proxy`` only — ``time_aware``/``open_set``
   raise; they need the metadata CSVs);
4. train LightGBM on the subset train side, **evaluate on the validation
   side only** (``test_touched=False`` — ADR-009: evaluating test without a
   freeze lock is refused);
5. record a schema-v2 run record with tags ``[pilot-10pct, …]`` — refused by
   ``paper/tables.py`` by construction (ADR-009).

Metrics recorded: ``val/macro_f1`` plus, when the split provides timestamps
and families (never in npz-only mode), ``val/aut``. No numbers are invented:
anything uncomputable is recorded as ``null``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
from bytelens.data.bodmas import BODMASData, load_bodmas
from bytelens.eval.metrics import macro_f1
from bytelens.eval.splits import near_duplicate_proxy_split, random_split
from bytelens.eval.subsets import (
    SAMPLING_FRACTION,
    stratified_subset,
)
from bytelens.models.lightgbm_baseline import MODEL_NAME, predict, train_lightgbm
from logger.manifest import dataset_hash, verify_data

PILOT_TAG = "pilot-10pct"


def _split_10pct(
    data: BODMASData,
    *,
    protocol: str,
    seed: int,
    fraction: float = SAMPLING_FRACTION,
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    """Subset to ``fraction``, then split within it; return (ids_by_side, info).

    Interim strata for the subset sample: label only — feature-bucket strata
    collapse to singletons and every tiny stratum contributes ≥ 1 (the
    min_stratum guard), inflating the subset. The 70/15/15 split inside the
    subset stratifies by label as well.
    """
    ids = data.row_ids()
    subsets_info: dict[str, Any] = {
        "sampling_fraction": fraction,
        "algorithm_version": "1",
        "id_basis": "row_index",
    }
    if protocol == "random":
        # Subset strata: label only in npz-only mode — feature-bucket strata
        # would explode into ~one-row-per-bucket groups and each tiny stratum
        # contributes ≥ 1 (min_stratum guard), inflating the subset (136 of
        # 300 at 10%). Label gives two big strata and a true 10%.
        label_strata = [str(int(v)) for v in data.y]
        subset_ids, counts = stratified_subset(
            ids=ids, strata=label_strata, seed=seed, fraction=fraction
        )
        ix = {i: k for k, i in enumerate(ids)}
        X_sub = np.asarray(data.X, dtype=np.float32)[[ix[i] for i in subset_ids]]
        y_sub = data.y[[ix[i] for i in subset_ids]]
        label_sub = [str(int(y_sub[k])) for k in range(len(subset_ids))]
        ids_by_side = random_split(ids=subset_ids, strata=label_sub, seed=seed)
        subsets_info["strata_counts"] = counts
    elif protocol == "near_duplicate_proxy":
        subset_ids, counts = stratified_subset(
            ids=ids, strata=["x"] * len(ids), seed=seed, fraction=fraction
        )
        ix = {i: k for k, i in enumerate(ids)}
        X_sub = np.asarray(data.X, dtype=np.float32)[[ix[i] for i in subset_ids]]
        y_sub = data.y[[ix[i] for i in subset_ids]]
        ids_by_side = near_duplicate_proxy_split(ids=subset_ids, X=X_sub, seed=seed)
        subsets_info["strata_counts"] = counts
    else:
        raise ValueError(
            f"npz-only pilot split protocol {protocol!r} not supported; "
            "expected 'random' or 'near_duplicate_proxy' (ADR-010: time_aware/"
            "open_set need the metadata CSVs — stop and ask, never fake months)"
        )
    subsets_info["X"] = X_sub
    subsets_info["y"] = y_sub
    return ids_by_side, subsets_info


def run_pilot(cfg: dict[str, Any], seed: int) -> tuple[dict[str, float | None], dict[str, Any]]:
    """Train + evaluate one (config, seed); return ``(metrics, details)``.

    Metrics keys: ``val/macro_f1`` (always, both classes), ``val/n`` and,
    only when families+timestamps exist, ``val/aut``. Evaluation is
    **validation-side only**; the test side of the split is never touched
    (``test_touched=False`` is set in the record).
    """
    protocol = str(cfg.get("split_protocol", "random"))
    fraction = float(cfg.get("pilot", {}).get("fraction", SAMPLING_FRACTION))
    data = load_bodmas()
    ids_by_side, sinfo = _split_10pct(data, protocol=protocol, seed=seed, fraction=fraction)

    y = sinfo["y"]

    # Index subset rows by id (row_ids are minted in the same row order used
    # to build y_sub/X_sub in _split_10pct via the ix-map; here we re-derive:
    # subset_ids == sorted union of the split sides).
    subset_ids = sorted(
        [*ids_by_side["train"], *ids_by_side["val"], *ids_by_side["test"]]
    )
    X_sub: np.ndarray = sinfo["X"]
    # stratified_subset returned sorted subset_ids; X_sub follows that order.
    row_of = {rid: k for k, rid in enumerate(subset_ids)}

    tr = np.asarray([row_of[i] for i in ids_by_side["train"]], dtype=int)
    va = np.asarray([row_of[i] for i in ids_by_side["val"]], dtype=int)

    params = dict(cfg.get("params", {}))
    model = train_lightgbm(
        X_sub[tr],
        y[tr],
        seed=seed,
        params=params,
        num_threads=int(cfg.get("num_threads", 1)),
    )
    val_pred = predict(model["booster"], X_sub[va])
    val_y = y[va]
    metrics: dict[str, float | None] = {
        "val/macro_f1": macro_f1(val_y, val_pred),
        "val/n": float(len(va)),
    }
    details: dict[str, Any] = {
        "split_protocol": protocol,
        "sampling_fraction": sinfo["sampling_fraction"],
        "id_basis": sinfo["id_basis"],
        "resolved_params": model["resolved_params"],
        "determinism": model["determinism"],
        "model_artifact_sha256": model["model_artifact_sha256"],
        "train_n": int(len(tr)),
        "test_touched": False,
        "eval_side": "val",
    }
    # AUT: only when the split produces (timestamps, families) — never here
    # in npz-only mode; recorded as null rather than invented.
    details["aut_available"] = False
    metrics["val/aut"] = None
    return metrics, details


def main() -> int:
    from logger.hashing import hash_object
    from logger.run_records import RunRecorder, append_jsonl, read_jsonl

    from runner.experiment import load_config, plan_from_config

    config_path = Path("configs/p1_prelim_r1_bodmas.yaml")
    records_path = Path("logger/runs.jsonl")

    verify_data(["bodmas_features"])
    ds_hash = dataset_hash(["bodmas_features"])
    cfg = load_config(config_path)
    if str(cfg.get("model")) != MODEL_NAME:
        raise ValueError(
            f"config model {cfg.get('model')!r} != {MODEL_NAME!r} — the pilot "
            "runner is LightGBM-only (ADR-010 §5)"
        )
    plan = plan_from_config(cfg)
    done = {
        (r.config.get("experiment", ""), r.model_name, r.seed, r.config_hash)
        for r in read_jsonl(records_path)
    } if records_path.is_file() else set()

    tags = list(cfg.get("runner", {}).get("tags", []))
    if PILOT_TAG not in tags:
        raise ValueError(
            f"pilot config must carry the {PILOT_TAG!r} tag (ADR-009/010); got {tags}"
        )
    recorder = RunRecorder(output_dir=str(records_path.parent))
    executed = skipped = 0
    for p in plan:
        if p.identity in done:
            skipped += 1
            print(f"skip seed={p.seed} (resume)")
            continue
        t0 = time.perf_counter()
        metrics, details = run_pilot(p.config, p.seed)
        wall = time.perf_counter() - t0
        rec = recorder.start(
            config=p.config,
            seed=p.seed,
            model_name=p.model_name,
            dataset_hash=ds_hash,
            dataset_split_hash=hash_object(details["resolved_params"]),
            split_name=str(p.config.get("split_protocol")),
            tags=tags,
            test_touched=False,
            determinism=dict(details["determinism"]),
        )
        rec = RunRecorder.finish(
            rec,
            metrics=dict(metrics),
            wall_time_sec=wall,
            model_artifact_sha256=details["model_artifact_sha256"],
        )
        rec = append_jsonl(rec, records_path)
        executed += 1
        print(f"recorded run_id={rec.run_id} seed={p.seed} metrics={metrics}")
    print(f"executed={executed} skipped={skipped} (append-only)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

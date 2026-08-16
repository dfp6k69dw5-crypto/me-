import json
import math
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEED = 424242
WINDOW = 9
STRIDE = 9
TRAIN_MAX_SPEED = 60
VAL_SPEEDS = {65, 70, 75}
TEST_MIN_SPEED = 80

DATA_URLS = [
    "https://raw.githubusercontent.com/nimaabaeian/ml-project-robotic-fan-fault-detection/main/accelerometer.csv",
    "https://raw.githubusercontent.com/ShiyunKong/Mar---July-2022-Machine-Learning-Essentials-Course/main/homework/accelerometer.csv",
]

OUT = Path("fan_flower_results")
OUT.mkdir(exist_ok=True)
CSV_PATH = OUT / "accelerometer.csv"


def get_data():
    last = None
    for url in DATA_URLS:
        try:
            print(f"Downloading {url}")
            urllib.request.urlretrieve(url, CSV_PATH)
            df = pd.read_csv(CSV_PATH)
            expected = ["wconfid", "pctid", "x", "y", "z"]
            if list(df.columns) != expected or len(df) < 100_000:
                raise RuntimeError(f"Unexpected dataset shape/columns: {df.shape}, {list(df.columns)}")
            return df, url
        except Exception as e:
            print(f"Source failed: {type(e).__name__}: {e}")
            last = e
    raise RuntimeError(f"Could not retrieve full dataset: {last}")


def axis_flower(v, axis, sample_mu, sample_sd, theta):
    # Frozen mapping used in the earlier fan pilot.
    z = (v - sample_mu[axis]) / sample_sd[axis]
    a = np.exp(z - z.max())
    a = a / a.sum()
    r = 1.0 + 2.0 * a
    p = r * np.exp(1j * theta)
    pn = np.roll(p, -1)

    area = 0.5 * abs(np.sum(np.imag(np.conj(p) * pn)))
    perimeter = np.sum(np.abs(pn - p))
    asymmetry = abs(np.mean(p))
    roughness = np.mean(np.abs(np.roll(r, -1) - 2.0 * r + np.roll(r, 1)))
    anisotropy = abs(np.mean((r / r.mean()) * np.exp(2j * theta)))
    return [area, perimeter, asymmetry, roughness, anisotropy]


def make_windows(df, sample_mu, sample_sd):
    theta = 2.0 * np.pi * np.arange(WINDOW) / WINDOW + 0.1 * np.sin(np.arange(WINDOW))
    rows = []

    # Never allow a window to cross configuration or speed boundaries.
    for (cfg, speed), g in df.groupby(["wconfid", "pctid"], sort=False):
        arr = g[["x", "y", "z"]].to_numpy(dtype=float)
        for start in range(0, len(arr) - WINDOW + 1, STRIDE):
            w = arr[start:start + WINDOW]

            raw = w.ravel().tolist()

            local_mu = w.mean(axis=0)
            local_sd = w.std(axis=0, ddof=0)
            local_sd[local_sd < 1e-12] = 1.0
            shape_only = ((w - local_mu) / local_sd).ravel().tolist()

            summaries = []
            for axis in range(3):
                v = w[:, axis]
                summaries.extend([v.mean(), v.std(ddof=0), v.min(), v.max(), np.ptp(v)])

            rms = np.sqrt(np.mean(w * w, axis=0)).tolist()

            flower = []
            for axis in range(3):
                flower.extend(axis_flower(w[:, axis], axis, sample_mu, sample_sd, theta))

            rows.append({
                "wconfid": int(cfg),
                "pctid": int(speed),
                "flower": flower,
                "raw": raw,
                "shape_only_raw": shape_only,
                "summaries": summaries,
                "rms": rms,
            })
    return rows


def matrix(rows, name):
    return np.asarray([r[name] for r in rows], dtype=float)


def metrics(y_true, pred):
    return {
        "accuracy": float(accuracy_score(y_true, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "macro_f1": float(f1_score(y_true, pred, average="macro")),
    }


def main():
    df, source = get_data()
    df = df.dropna().copy()
    df["wconfid"] = df["wconfid"].astype(int)
    df["pctid"] = df["pctid"].astype(int)

    configs = sorted(df.wconfid.unique().tolist())
    speeds = sorted(df.pctid.unique().tolist())
    print("DATASET", df.shape)
    print("CONFIGS", configs)
    print("SPEEDS", speeds)
    print("COUNTS PER CONFIG/SPEED")
    print(df.groupby(["wconfid", "pctid"]).size().to_string())

    train_sample_mask = df.pctid <= TRAIN_MAX_SPEED
    sample_mu = df.loc[train_sample_mask, ["x", "y", "z"]].mean().to_numpy(dtype=float)
    sample_sd = df.loc[train_sample_mask, ["x", "y", "z"]].std(ddof=0).to_numpy(dtype=float)
    sample_sd[sample_sd < 1e-12] = 1.0
    print("TRAIN-ONLY AXIS MU", sample_mu.tolist())
    print("TRAIN-ONLY AXIS SD", sample_sd.tolist())

    rows = make_windows(df, sample_mu, sample_sd)
    y = np.asarray([r["wconfid"] for r in rows], dtype=int)
    speed = np.asarray([r["pctid"] for r in rows], dtype=int)

    train_mask = speed <= TRAIN_MAX_SPEED
    val_mask = np.isin(speed, sorted(VAL_SPEEDS))
    test_mask = speed >= TEST_MIN_SPEED

    print("WINDOW COUNTS", {
        "all": int(len(rows)),
        "train": int(train_mask.sum()),
        "val": int(val_mask.sum()),
        "test": int(test_mask.sum()),
    })

    representations = {
        "flower_geometry_15": "flower",
        "raw_sequence_27": "raw",
        "shape_only_raw_27": "shape_only_raw",
        "ordinary_summaries_15": "summaries",
        "rms_3": "rms",
    }

    result_rows = []
    confusions = {}

    # Same low-capacity classifier for every representation.
    for label, key in representations.items():
        X = matrix(rows, key)
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, max_iter=3000, solver="lbfgs", random_state=SEED),
        )
        model.fit(X[train_mask], y[train_mask])
        val_pred = model.predict(X[val_mask])
        test_pred = model.predict(X[test_mask])

        vm = metrics(y[val_mask], val_pred)
        tm = metrics(y[test_mask], test_pred)
        cm = confusion_matrix(y[test_mask], test_pred, labels=configs)
        confusions[label] = cm.tolist()

        # Sanity check: ordinary random interpolation split using all speeds.
        idx = np.arange(len(y))
        i_train, i_test = train_test_split(
            idx, test_size=0.30, random_state=SEED, stratify=y
        )
        random_model = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, max_iter=3000, solver="lbfgs", random_state=SEED),
        )
        random_model.fit(X[i_train], y[i_train])
        random_pred = random_model.predict(X[i_test])
        rm = metrics(y[i_test], random_pred)

        result_rows.append({
            "representation": label,
            "n_features": int(X.shape[1]),
            "validation_accuracy_65_75": vm["accuracy"],
            "validation_balanced_accuracy_65_75": vm["balanced_accuracy"],
            "validation_macro_f1_65_75": vm["macro_f1"],
            "test_accuracy_80_100": tm["accuracy"],
            "test_balanced_accuracy_80_100": tm["balanced_accuracy"],
            "test_macro_f1_80_100": tm["macro_f1"],
            "random_split_accuracy_all_speeds": rm["accuracy"],
            "random_split_balanced_accuracy_all_speeds": rm["balanced_accuracy"],
            "random_split_macro_f1_all_speeds": rm["macro_f1"],
        })

    results = pd.DataFrame(result_rows).sort_values(
        "test_balanced_accuracy_80_100", ascending=False
    )
    results.to_csv(OUT / "results.csv", index=False)

    payload = {
        "source": source,
        "dataset_rows": int(len(df)),
        "configs": configs,
        "speeds": speeds,
        "window": WINDOW,
        "stride": STRIDE,
        "split": {
            "train": f"pctid <= {TRAIN_MAX_SPEED}",
            "validation": sorted(VAL_SPEEDS),
            "test": f"pctid >= {TEST_MIN_SPEED}",
        },
        "train_axis_mu": sample_mu.tolist(),
        "train_axis_sd": sample_sd.tolist(),
        "window_counts": {
            "all": int(len(rows)),
            "train": int(train_mask.sum()),
            "validation": int(val_mask.sum()),
            "test": int(test_mask.sum()),
        },
        "results": results.to_dict(orient="records"),
        "test_confusion_matrices": confusions,
    }
    (OUT / "results.json").write_text(json.dumps(payload, indent=2))

    lines = []
    lines.append("# Fan flower speed-generalization experiment")
    lines.append("")
    lines.append(f"Source: `{source}`")
    lines.append(f"Rows: {len(df):,}; configs: {configs}; speeds: {speeds}")
    lines.append(f"Windows: {len(rows):,} non-overlapping 9-sample windows")
    lines.append("Train: 20–60%; validation: 65–75%; untouched test: 80–100%.")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append(results.to_markdown(index=False, floatfmt=".4f"))
    lines.append("")
    lines.append("## Test confusion matrices")
    for label in representations:
        lines.append("")
        lines.append(f"### {label}")
        lines.append("```text")
        lines.append(np.array2string(np.asarray(confusions[label]), separator=", "))
        lines.append("```")
    report = "\n".join(lines)
    (OUT / "report.md").write_text(report)

    print("\n===== FINAL REPORT =====\n")
    print(report)
    print("\nRESULT_JSON=" + json.dumps(payload))


if __name__ == "__main__":
    main()

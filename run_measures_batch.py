
import argparse
import csv
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

'''
# Needs pyyml

pip install pyyaml

# Example Usuage

# paths you already have
$db  = ".\name_of_my.db"
$csv = ".\path\to\the\results.csv"
$spec = ".\spec_templates_all_tables_MLABite\measure.yml"
$loader = ".\csv_to_sql_loader.py"

# run with your Python 3.13
python313 .\run_measures_batch.py `
  --db $db `
  --csv $csv `
  --spec $spec `
  --loader $loader `
  --python "C:\Users\adhav\AppData\Local\Programs\Python\Python313\python.exe" `
  --skip-missing

'''

try:
    import yaml
except ImportError:
    yaml = None

def load_yaml(path: Path):
    if yaml is None:
        raise RuntimeError("PyYAML not installed. Run: pip install pyyaml")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def dump_yaml(data, path: Path):
    if yaml is None:
        raise RuntimeError("PyYAML not installed. Run: pip install pyyaml")
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

def get_csv_headers(csv_path: Path):
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader, [])
    return headers

def fetch_metrics(db_path: Path, sql: str = "SELECT id, name FROM metric ORDER BY id"):
    con = sqlite3.connect(db_path.as_posix())
    cur = con.cursor()
    rows = cur.execute(sql).fetchall()
    con.close()
    return rows

def update_spec_for_metric(base_spec: dict, metric_id: int, metric_name: str):
    spec = json.loads(json.dumps(base_spec))
    for k in list(spec.keys()):
        if isinstance(k, str) and k.startswith("_"):
            spec.pop(k, None)

    if "columns" not in spec or not isinstance(spec["columns"], dict):
        raise ValueError("Spec missing 'columns' mapping.")

    cols = spec["columns"]

    if "value" not in cols:
        cols["value"] = {}
    cols["value"]["from"] = metric_name
    cols["value"].setdefault("as_type", "float")
    cols["value"].pop("expr", None)
    cols["value"].pop("const", None)

    cols["metric_id"] = {"const": int(metric_id), "as_type": "int"}

    return spec

def run_loader(python_exe: str, loader_path: Path, db: Path, csv_path: Path, spec_path: Path):
    cmd = [
        python_exe,
        str(loader_path),
        "--db", str(db),
        "--csv", str(csv_path),
        "--spec", str(spec_path)
    ]
    print(">>", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)

def main():
    ap = argparse.ArgumentParser(description="Batch-load measures by iterating metrics and generating per-metric spec files.")
    ap.add_argument("--db", required=True, type=Path, help="Path to SQLite DB (e.g., .\\name_of_my.db)")
    ap.add_argument("--csv", required=True, type=Path, help="Path to results CSV")
    ap.add_argument("--spec", required=True, type=Path, help="Path to base measure.yml (template)")
    ap.add_argument("--loader", required=True, type=Path, help="Path to csv_to_sql_loader.py")
    ap.add_argument("--python", default=sys.executable, help="Python interpreter to use for the loader (default: current)")
    ap.add_argument("--metrics-sql", default="SELECT id, name FROM metric ORDER BY id",
                    help="Custom SQL to select (id, name) for metrics")
    ap.add_argument("--outdir", type=Path, default=Path("./_generated_specs"), help="Where to write per-metric specs")
    ap.add_argument("--skip-missing", action="store_true", help="Skip metrics whose name is not a CSV column")
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    base_spec = load_yaml(args.spec)
    headers = get_csv_headers(args.csv)
    metric_rows = fetch_metrics(args.db, sql=args.metrics_sql)

    print(f"Found {len(metric_rows)} metrics; CSV has {len(headers)} columns.")

    for metric_id, metric_name in metric_rows:
        if args.skip_missing and metric_name not in headers:
            print(f"-- Skipping metric {metric_id}:{metric_name!r} (not in CSV headers)")
            continue

        spec_i = update_spec_for_metric(base_spec, metric_id, metric_name)
        spec_path = args.outdir / f"measure__metric_{metric_id}.yml"
        dump_yaml(spec_i, spec_path)

        print(f"-- Loading metric {metric_id}:{metric_name!r}")
        run_loader(args.python, args.loader, args.db, args.csv, spec_path)

    print("All done.")

if __name__ == "__main__":
    main()

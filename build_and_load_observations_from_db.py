import argparse
import datetime as dt
import sqlite3
import subprocess
import sys
from pathlib import Path
import csv

def fetch_rows(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def choose_dataset_id(conn, policy="single"):
    # Only select id (no name assumption)
    rows = fetch_rows(conn, 'SELECT id FROM dataset ORDER BY id')
    if not rows:
        raise SystemExit("No rows in dataset; cannot resolve dataset_2_id.")
    if policy == "single":
        if len(rows) != 1:
            raise SystemExit(f"dataset-policy=single but found {len(rows)} datasets. "
                             f"Use --dataset-policy min_id or max_id.")
        return rows[0]["id"]
    if policy == "min_id":
        return rows[0]["id"]
    if policy == "max_id":
        return rows[-1]["id"]
    return rows[0]["id"]

def main():
    ap = argparse.ArgumentParser(description="Build observation CSV from DB only, then call csv_to_sql_loader.py with observation.yml.")
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--spec", required=True, type=Path, help="Path to observation.yml")
    ap.add_argument("--loader", required=True, type=Path, help="Path to csv_to_sql_loader.py")
    ap.add_argument("--python", default=sys.executable, help="Python exe to run the loader")
    ap.add_argument("--dataset-policy", choices=["single","min_id","max_id"], default="single",
                    help="How to pick dataset when multiple exist")
    ap.add_argument("--observer", default="system")
    ap.add_argument("--when", default=None, help="ISO timestamp; default now (UTC)")
    ap.add_argument("--description", default="auto-generated from DB")
    ap.add_argument("--out-csv", type=Path, default=Path("./_tmp_observations_from_db.csv"))
    ap.add_argument("--strict", action="store_true", help="Fail if counts of evaluation and tool differ")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db.as_posix())

    evals = fetch_rows(conn, "SELECT id FROM evaluation ORDER BY id")
    tools = fetch_rows(conn, "SELECT id, name FROM tool ORDER BY id")
    if not evals:
        raise SystemExit("No rows in evaluation; nothing to create.")
    if not tools:
        raise SystemExit("No rows in tool; cannot map observations.")

    dsid = choose_dataset_id(conn, policy=args.dataset_policy)

    n_e, n_t = len(evals), len(tools)
    n = min(n_e, n_t)
    if args.strict and n_e != n_t:
        raise SystemExit(f"--strict: mismatch evaluation({n_e}) vs tool({n_t}).")
    if n_e != n_t:
        print(f"[WARN] Pairing by order: using {n} pairs; extra evaluations={max(0,n_e-n_t)}; extra tools={max(0,n_t-n_e)}")

    when_ts = args.when or dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    rows_out = []
    for i in range(n):
        ev = evals[i]
        tl = tools[i]
        rows_out.append({
            "<CSV_observer>": args.observer,
            "<CSV_whenObserved>": when_ts,
            "<CSV_tool_id>": tl["id"],
            "<CSV_eval_id>": ev["id"],
            "<CSV_dataset_2_id>": dsid,      # FK→dataset.id
            "<CSV_name>": tl["name"],        # observation.name = tool.name
            "<CSV_description>": args.description,
        })

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["<CSV_observer>","<CSV_whenObserved>","<CSV_tool_id>","<CSV_eval_id>","<CSV_dataset_2_id>","<CSV_name>","<CSV_description>"]
    with args.out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)

    cmd = [args.python, str(args.loader), "--db", str(args.db), "--csv", str(args.out_csv), "--spec", str(args.spec)]
    print(">>", " ".join(cmd))
    proc = subprocess.run(cmd, text=True, capture_output=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    print(f"Loaded {len(rows_out)} observations (paired eval.id ↔ tool.id by order).")

if __name__ == "__main__":
    main()

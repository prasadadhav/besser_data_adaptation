
import argparse
import csv
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

HEADER_STYLE_BRACKETED = "bracketed"
HEADER_STYLE_PLAIN = "plain"

def hname(base: str, style: str) -> str:
    return f"<{base}>" if style == "bracketed" else base

def fetch_df(conn, sql: str) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn)

def ensure_placeholder_element(conn) -> int:
    cur = conn.cursor()
    cur.execute('SELECT id FROM element WHERE name = ?', ("Not Available",))
    row = cur.fetchone()
    if row:
        return int(row[0])
    # Create minimal row
    cols = [r[1] for r in cur.execute("PRAGMA table_info('element')").fetchall()]
    if "data" in cols:
        cur.execute('INSERT INTO element(name, data) VALUES(?,?)', ("Not Available", "placeholder"))
    else:
        cur.execute('INSERT INTO element(name) VALUES(?)', ("Not Available",))
    conn.commit()
    return cur.lastrowid

def detect_tool_column(df: pd.DataFrame, tool_names: set[str]) -> str | None:
    candidates = ["tool", "tool_name", "model", "model_name", "name", "llm", "llm_name"]
    for col in df.columns:
        c = str(col).strip()
        if c in candidates:
            series = df[c].astype(str).str.strip()
            if series.isin(tool_names).sum() >= max(1, len(tool_names) // 2):
                return col
    return None

def main():
    ap = argparse.ArgumentParser(description="Build measure CSV from DB + results CSV, then load via csv_to_sql_loader.py")
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--loader", required=True, type=Path)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--out-csv", type=Path, default=Path("./data_Cedric_Lux/_tmp_measures_from_db_and_csv.csv"))
    ap.add_argument("--header-style", choices=[HEADER_STYLE_BRACKETED, HEADER_STYLE_PLAIN], default=HEADER_STYLE_BRACKETED)
    ap.add_argument("--pairing", choices=["by_name","by_order"], default="by_name")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db.as_posix())

    df_obs = fetch_df(conn, "SELECT id, tool_id FROM observation ORDER BY id")
    if df_obs.empty:
        raise SystemExit("No observations; populate observation first.")
    df_tool = fetch_df(conn, "SELECT id, name FROM tool")
    if df_tool.empty:
        raise SystemExit("No tools found.")
    df_metric = fetch_df(conn, "SELECT id, name, description FROM metric ORDER BY id")
    if df_metric.empty:
        raise SystemExit("No metrics found.")
    measurand_placeholder_id = "Not Available" #ensure_placeholder_element(conn)

    df_res = pd.read_csv(args.csv)
    tool_names_set = set(df_tool["name"].astype(str))

    csv_index_for_toolid = {}
    tool_col = None
    if args.pairing == "by_name":
        tool_col = detect_tool_column(df_res, tool_names_set)
    if tool_col:
        name_series = df_res[tool_col].astype(str).str.strip()
        first_idx_by_name = {}
        for i, val in enumerate(name_series):
            first_idx_by_name.setdefault(val, i)
        for _, tr in df_tool.iterrows():
            tname = str(tr["name"])
            if tname in first_idx_by_name:
                csv_index_for_toolid[int(tr["id"])] = first_idx_by_name[tname]
        missing = [int(tr["id"]) for _, tr in df_tool.iterrows() if int(tr["id"]) not in csv_index_for_toolid]
        if missing:
            print(f"[WARN] {len(missing)} tools not found by name in CSV column '{tool_col}'; using by_order for those.")
    if not tool_col or len(csv_index_for_toolid) < len(df_tool):
        min_len = min(len(df_obs), len(df_res))
        for i in range(min_len):
            tool_id = int(df_obs.iloc[i]["tool_id"])
            csv_index_for_toolid.setdefault(tool_id, i)

    hn = lambda b: hname(b, args.header_style)
    fieldnames = [
        hn("CSV_value"), hn("CSV_error"), hn("CSV_uncertainty"), hn("CSV_unit"),
        hn("CSV_metric_id"), hn("CSV_observation_id"), hn("CSV_measurand_id"),
    ]

    out_rows = []
    missing_metric_cols = set()

    for _, ob in df_obs.iterrows():
        obs_id = int(ob["id"])
        tool_id = int(ob["tool_id"])
        csv_idx = csv_index_for_toolid.get(tool_id, None)
        if csv_idx is None or csv_idx >= len(df_res):
            print(f"[WARN] No CSV row matched for observation.id={obs_id} tool_id={tool_id}; skipping its measures.")
            continue
        csv_row = df_res.iloc[csv_idx]

        for _, mr in df_metric.iterrows():
            metric_id = int(mr["id"])
            metric_name = str(mr["name"])
            unit = str(mr["description"]) if pd.notna(mr["description"]) else "Not Available"

            if metric_name not in df_res.columns:
                missing_metric_cols.add(metric_name)
                continue

            value = csv_row[metric_name]
            if pd.isna(value):
                value = "Not Available"

            out_rows.append({
                fieldnames[0]: value,                              # CSV_value
                fieldnames[1]: "Not Available",                    # CSV_error
                fieldnames[2]: "Not Available",                    # CSV_uncertainty
                fieldnames[3]: unit,                               # CSV_unit
                fieldnames[4]: metric_id,                          # CSV_metric_id
                fieldnames[5]: obs_id,                             # CSV_observation_id
                fieldnames[6]: measurand_placeholder_id,           # CSV_measurand_id
            })

    if missing_metric_cols:
        mm = sorted(missing_metric_cols)
        print(f"[WARN] Missing {len(mm)} metric columns in results CSV; first few: {mm[:5]}{'...' if len(mm)>5 else ''}")

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    print(f"Wrote {len(out_rows)} measure rows to {args.out_csv}")

    cmd = [args.python, str(args.loader), "--db", str(args.db), "--csv", str(args.out_csv), "--spec", str(args.spec)]
    print(">>", " ".join(cmd))
    proc = subprocess.run(cmd, text=True, capture_output=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    print("Done loading measures.")

if __name__ == "__main__":
    main()

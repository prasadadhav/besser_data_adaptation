
"""
csv_to_sql_loader_v2.py
- Adds:
  1) pre_dedupe_on: drop duplicate mapped rows on these columns before insert/upsert
  2) Column rule: lookup → resolve foreign keys by querying another table
     lookup:
       table: "metric"
       get: "id"
       match:
         name:        { const: "A1 Grammar" }     # or { from: "metric_name" }
         type_spec:   { const: "Grammar" }        # optional extra matches
       create_if_missing: false                    # or true
       defaults:                                   # used only if create_if_missing: true
         description: { const: "Auto-created" }

- Backwards compatible with v1 (from/const/expr/transform/as_type, insert/upsert).
"""
import argparse
import sqlite3
import pandas as pd
import json
from pathlib import Path
try:
    import yaml
except ImportError:
    yaml = None

# ---------- Spec IO ----------

def load_spec(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yml", ".yaml"}:
        if yaml is None:
            raise RuntimeError("PyYAML not installed. Use JSON spec or `pip install pyyaml`.")
        return yaml.safe_load(text)
    return json.loads(text)

# ---------- Schema helpers ----------

def get_table_schema(conn, table: str):
    info = pd.read_sql_query(f"PRAGMA table_info('{table}')", conn)
    fks  = pd.read_sql_query(f"PRAGMA foreign_key_list('{table}')", conn)
    return info, fks

def required_cols(table_info: pd.DataFrame):
    req = []
    for _, r in table_info.iterrows():
        if r["notnull"] == 1 and r["dflt_value"] is None:
            if r["pk"] == 1 and "INT" in (r["type"] or "").upper():
                continue
            req.append(r["name"])
    return req

# ---------- Mapping primitives ----------

def resolve_cell_from_rule(row: pd.Series, rule: dict, row_context: dict | None = None):
    if "from" in rule:
        val = row[rule["from"]]
    elif "const" in rule:
        val = rule["const"]
    elif "expr" in rule:
        _globals = {"__builtins__": {}}
        _locals  = {"row": row.to_dict()}
        if row_context:
            _locals.update(row_context)
        val = eval(rule["expr"], _globals, _locals)
    else:
        raise ValueError("Rule must have one of: 'from', 'const', or 'expr'.")
    t = rule.get("transform")
    if t:
        for op in t.split("|"):
            op = op.strip().lower()
            if op == "strip":
                val = ("" if val is None else str(val)).strip()
            elif op == "lower":
                val = ("" if val is None else str(val)).lower()
            elif op == "upper":
                val = ("" if val is None else str(val)).upper()
            elif op == "title":
                val = ("" if val is None else str(val)).title()
            else:
                raise ValueError(f"Unknown transform: {op}")
    as_type = rule.get("as_type")
    if as_type:
        if as_type == "int":
            try:
                val = int(val) if val is not None else None
            except Exception:
                val = None
        elif as_type == "float":
            try:
                val = float(val) if val is not None else None
            except Exception:
                val = None
        elif as_type == "str":
            val = "" if val is None else str(val)
        else:
            raise ValueError(f"Unsupported as_type: {as_type}")
    return val

def resolve_lookup(conn, row: pd.Series, lk: dict):
    table = lk["table"]
    get   = lk["get"]
    match_spec = lk.get("match", {})
    params = {}
    where_clauses = []
    for col, subrule in match_spec.items():
        val = resolve_cell_from_rule(row, subrule)
        where_clauses.append(f'"{col}" = ?')
        params[col] = val
    sql = f'SELECT "{get}" FROM "{table}"'
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    cur = conn.cursor()
    res = cur.execute(sql, list(params.values())).fetchall()
    if len(res) == 1:
        return res[0][0]
    if len(res) > 1:
        raise ValueError(f"Lookup in '{table}' for {params} returned multiple rows.")
    if lk.get("create_if_missing"):
        insert_cols = []
        insert_vals = []
        for c, v in params.items():
            insert_cols.append(c); insert_vals.append(v)
        defaults = lk.get("defaults", {})
        for c, subrule in defaults.items():
            val = resolve_cell_from_rule(row, subrule)
            insert_cols.append(c); insert_vals.append(val)
        placeholders = ", ".join(["?"] * len(insert_cols))
        col_list = ", ".join([f'"{c}"' for c in insert_cols])
        ins_sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders});'
        cur.execute(ins_sql, insert_vals)
        conn.commit()
        if get in insert_cols:
            return insert_vals[insert_cols.index(get)]
        if get.lower() in {"id"}:
            return cur.lastrowid
        res = cur.execute(sql, list(params.values())).fetchall()
        if len(res) == 1:
            return res[0][0]
        raise ValueError(f"Created row in '{table}' but couldn't retrieve '{get}'.")
    return None

def apply_mapping(conn, df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for db_col, rule in spec.get("columns", {}).items():
        if "lookup" in rule:
            series = df.apply(lambda row: resolve_lookup(conn, row, rule["lookup"]), axis=1)
        else:
            series = df.apply(lambda row: resolve_cell_from_rule(row, rule), axis=1)
        out[db_col] = series
    dedupe_on = spec.get("pre_dedupe_on", [])
    if dedupe_on:
        out = out.drop_duplicates(subset=dedupe_on, keep="last")
    return out

# ---------- Load ----------

def upsert_dataframe(conn, df: pd.DataFrame, table: str, key_cols: list[str]):
    if df.empty:
        return 0
    cols = list(df.columns)
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join([f'"{c}"' for c in cols])
    update_set = ", ".join([f'"{c}"=excluded."{c}"' for c in cols if c not in key_cols])
    key_list   = ", ".join([f'"{c}"' for c in key_cols])
    sql = f"""
    INSERT INTO "{table}" ({col_list})
    VALUES ({placeholders})
    ON CONFLICT({key_list}) DO UPDATE SET
      {update_set};
    """
    cur = conn.cursor()
    cur.executemany(sql, df[cols].where(pd.notnull(df), None).values.tolist())
    conn.commit()
    return cur.rowcount

def insert_dataframe(conn, df: pd.DataFrame, table: str):
    if df.empty:
        return 0
    cols = list(df.columns)
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join([f'"{c}"' for c in cols])
    sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders});'
    cur = conn.cursor()
    cur.executemany(sql, df[cols].where(pd.notnull(df), None).values.tolist())
    conn.commit()
    return cur.rowcount

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, type=Path, help="Path to SQLite .db")
    ap.add_argument("--csv", required=True, type=Path, help="Path to input CSV")
    ap.add_argument("--spec", required=True, type=Path, help="Path to mapping spec (YAML or JSON)")
    args = ap.parse_args()

    spec = load_spec(args.spec)
    table = spec["table"]
    mode  = spec.get("mode", "insert")
    key   = spec.get("key", [])

    conn = sqlite3.connect(args.db.as_posix())
    tbl_info, _ = get_table_schema(conn, table)

    df = pd.read_csv(args.csv)

    mapped = apply_mapping(conn, df, spec)

    req = required_cols(tbl_info)
    missing_required = [c for c in req if c not in mapped.columns]
    if missing_required:
        print(f"[WARN] Mapped data missing NOT NULL columns without defaults: {missing_required}")

    if mode == "upsert":
        if not key:
            raise ValueError("Upsert mode requires 'key' in spec.")
        count = upsert_dataframe(conn, mapped, table, key)
    else:
        count = insert_dataframe(conn, mapped, table)

    print(f"Loaded {count} rows into '{table}'.")

if __name__ == "__main__":
    main()

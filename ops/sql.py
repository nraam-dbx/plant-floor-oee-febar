"""Run a SQL statement on the project warehouse and print the result as a text table (used for evidence)."""
import json, subprocess, sys

def run(sql, profile="fevm-nraameast1", warehouse="ba24ff79986686a9", catalog=None, schema=None):
    req = {"warehouse_id": warehouse, "statement": sql, "wait_timeout": "50s", "format": "JSON_ARRAY"}
    req.update({k: v for k, v in (("catalog", catalog), ("schema", schema)) if v})
    body = json.dumps(req)
    out = json.loads(subprocess.run(["databricks", "api", "post", "/api/2.0/sql/statements", "-p", profile, "--json", body],
                                    capture_output=True, text=True, check=True).stdout)
    if out["status"]["state"] != "SUCCEEDED":
        raise SystemExit(f"{out['status']}\n{sql}")
    cols = [c["name"] for c in out.get("manifest", {}).get("schema", {}).get("columns", [])]
    rows = out.get("result", {}).get("data_array", []) or []
    return cols, rows

def table(cols, rows):
    w = [max(len(str(c)), *(len(str(r[i])) for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
    lines = [" | ".join(str(c).ljust(w[i]) for i, c in enumerate(cols)), "-+-".join("-" * x for x in w)]
    lines += [" | ".join(str(v).ljust(w[i]) for i, v in enumerate(r)) for r in rows]
    return "\n".join(lines)

if __name__ == "__main__":
    sql = sys.stdin.read() if len(sys.argv) < 2 else sys.argv[1]
    print(table(*run(sql)))

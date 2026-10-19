"""Export a Databricks notebook job-task run (code + outputs) to a .ipynb under evidence/ — text the evaluator can read."""
import base64, json, re, subprocess, sys, urllib.parse

def export(task_run_id, out_path, profile="fevm-nraameast1"):
    res = json.loads(subprocess.run(["databricks", "jobs", "export-run", str(task_run_id), "--views-to-export", "CODE",
                                     "-p", profile, "-o", "json"], capture_output=True, text=True, check=True).stdout)
    html = res["views"][0]["content"]
    model = json.loads(urllib.parse.unquote(base64.b64decode(
        re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html).group(1)).decode()))
    cells = []
    for c in model["commands"]:
        src = c["command"]
        if src.startswith("%md"):
            cells.append({"cell_type": "markdown", "metadata": {}, "source": src[3:].lstrip("\n")})
            continue
        outputs = []
        for r in ((c.get("results") or {}).get("data") or []) if isinstance((c.get("results") or {}).get("data"), list) else []:
            if r.get("type") == "ansi":
                outputs.append({"output_type": "stream", "name": "stdout", "text": r["data"]})
            elif r.get("type") == "table":
                cols = [s["name"] for s in r["schema"]]
                text = "\t".join(cols) + "\n" + "\n".join("\t".join(map(str, row)) for row in r["data"])
                outputs.append({"output_type": "execute_result", "execution_count": None, "metadata": {},
                                "data": {"text/plain": text}})
        err = (c.get("results") or {}).get("cause") or c.get("error")
        if err:
            outputs.append({"output_type": "stream", "name": "stderr", "text": str(err)})
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "source": src, "outputs": outputs})
    nb = {"nbformat": 4, "nbformat_minor": 5, "cells": cells,
          "metadata": {"databricks_run": {"task_run_id": task_run_id}, "language_info": {"name": "python"}}}
    with open(out_path, "w") as f:
        json.dump(nb, f, indent=1)
    print(f"wrote {out_path} ({len(cells)} cells)")

if __name__ == "__main__":
    export(int(sys.argv[1]), sys.argv[2])

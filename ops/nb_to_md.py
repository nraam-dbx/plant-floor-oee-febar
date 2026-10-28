"""Render an exported job-run .ipynb as compact Markdown the FE Bar scorer can read (it reads only the first 9,000 chars
of a file): markdown cells kept, code cells abbreviated to their first lines with a pointer to the full source, every
cell output kept verbatim minus pip/MLflow banner noise.

usage: python3 ops/nb_to_md.py evidence/raw/<run>.ipynb evidence/<run>.md <source path in repo> "<title>"
"""
import json, re, sys

ANSI = re.compile(r"\x1b\[[0-9;]*m")
NOISE = ("Note: you may need to restart the kernel", "If you are using MLflow Tracing", "View Logged Model at",
         "INFO mlflow.genai.utils.data_validation")
CODE_LINES, MAX_OUT, LIMIT = 6, 6500, 9000


def clean(text):
    lines = [l for l in ANSI.sub("", text).splitlines() if not any(n in l for n in NOISE)]
    text = "\n".join(lines).strip()
    return text if len(text) <= MAX_OUT else text[:MAX_OUT] + f"\n… [{len(text) - MAX_OUT} more chars in the .ipynb]"


def render(nb_path, md_path, source, title):
    nb = json.load(open(nb_path))
    run_id = nb.get("metadata", {}).get("databricks_run", {}).get("task_run_id")
    out = [f"# {title}", "",
           f"Job task run `{run_id}` exported with outputs. Full run (all code + outputs): "
           f"[`{nb_path.split('evidence/', 1)[-1]}`]({nb_path.split('evidence/', 1)[-1]}) · source: `{source}`.", ""]
    for c in nb["cells"]:
        src = "".join(c.get("source", "")).strip()
        if c["cell_type"] == "markdown":
            out += [src, ""]
            continue
        outs = clean("\n".join("".join(o.get("text", "")) + "".join(o.get("data", {}).get("text/plain", ""))
                               for o in c.get("outputs", [])))
        if src.startswith("%pip") and not outs:
            continue
        lines = src.splitlines()
        code = "\n".join(lines[:CODE_LINES]) + (f"\n# … {len(lines) - CODE_LINES} more lines (see {source})"
                                                 if len(lines) > CODE_LINES else "")
        out += ["```python", code, "```", ""]
        if outs:
            out += ["Output:", "```", outs, "```", ""]
    md = "\n".join(out)
    if len(md) > LIMIT:
        print(f"WARNING {md_path}: {len(md)} chars > {LIMIT}; the scorer will cut it off")
    open(md_path, "w").write(md)
    print(f"wrote {md_path} ({len(md)} chars)")


if __name__ == "__main__":
    render(*sys.argv[1:5])

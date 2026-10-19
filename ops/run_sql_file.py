"""Execute a .sql file statement-by-statement on the project warehouse. USE CATALOG/SCHEMA set the context."""
import re, sys
from sql import run

ctx = {}
for s in re.split(r";\s*\n", open(sys.argv[1]).read()):
    body = "\n".join(l for l in s.splitlines() if not l.strip().startswith("--")).strip().rstrip(";")
    if not body:
        continue
    m = re.match(r"USE\s+(CATALOG|SCHEMA)\s+(\S+)$", body, re.I)
    if m:
        ctx[m.group(1).lower()] = m.group(2)
        continue
    run(body, **ctx)
    print("OK ", body.splitlines()[0][:110])

#!/usr/bin/env python3
"""Build a Google Slides deck from deck_spec.json on the 2025 Databricks corporate template, then export it to PDF.
usage: python3 docs/deck/build_deck.py docs/deck/deck_spec.json "<title>" docs/<file>.pdf
Uses the Databricks Light master consistently. Deletes the two dark sample
slides first so createSlide's 'current master' is Light, then adds slides by
Light-master layout IDs and populates placeholders by real type/index."""
import sys, json, time
sys.path.insert(0, "/Users/n.raam/.vibe/marketplace/plugins/fe-google-tools/skills/google-slides/resources")
import gslides_builder as gb

# Throttle + retry on Slides API write-quota (RESOURCE_EXHAUSTED / 429)
_orig_batch = gb.batch_update
def _throttled_batch(pres_id, requests, *a, **k):
    delay = 2.0
    for attempt in range(6):
        try:
            r = _orig_batch(pres_id, requests, *a, **k)
            time.sleep(1.1)  # smooth bursts under per-minute write quota
            return r
        except RuntimeError as e:
            if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower()) and attempt < 5:
                time.sleep(delay); delay *= 2; continue
            raise
gb.batch_update = _throttled_batch

TEMPLATE_ID = "1pHe3fVXfKhvQpmGOy51jppNIVnpk8iPmuvEjpjSxEI4"
LIGHT = "g324ba092b07_3_0"
TEAL = {"red": 0.106, "green": 0.318, "blue": 0.380}
WHITE = {"red": 1, "green": 1, "blue": 1}

LAYOUT = {
    "title":    "3 Title Slide B - Light",
    "section":  "Content E - Section Break 1",
    "basic":    "7 Content A - Basic",
    "twocol":   "9 Content B - 2 Column",
    "threecol": "11 Content C - 3 Column",
    "table":    "7 Content A - Basic",
    "closing":  "Z - Closing Light",
}

def resolve_layouts(pres_id):
    pres = gb.get_presentation(pres_id)
    ids = {}
    for key, name in LAYOUT.items():
        lid = None
        for L in pres.get("layouts", []):
            lp = L.get("layoutProperties", {})
            if lp.get("displayName") == name and lp.get("masterObjectId") == LIGHT:
                lid = L["objectId"]; break
        if not lid:  # fallback: any master
            for L in pres.get("layouts", []):
                if L.get("layoutProperties", {}).get("displayName") == name:
                    lid = L["objectId"]; break
        if not lid:
            raise RuntimeError(f"layout not found: {name}")
        ids[key] = lid
    return ids

def ph_map(pres_id, page_id):
    m = {}
    for p in gb.get_all_placeholders(pres_id, page_id):
        m[(p["type"], p.get("index") or 0)] = p["objectId"]
    return m

def put(pres_id, oid, text, bullets=False):
    if not oid or not text:
        return
    gb.insert_text(pres_id, oid, text, 0)
    if bullets:
        gb.create_bullets(pres_id, oid, 0, len(text))

def copy_template(title):
    resp = gb.api_call("POST",
        f"https://www.googleapis.com/drive/v3/files/{TEMPLATE_ID}/copy?supportsAllDrives=true",
        {"name": title, "parents": ["root"]})
    pid = resp["id"]
    samples = gb.get_slide_ids(pid)
    # delete the two dark-master sample slides (last two) so current master = Light
    gb.batch_update(pid, [{"deleteObject": {"objectId": samples[-1]}},
                          {"deleteObject": {"objectId": samples[-2]}}])
    remaining_samples = samples[:-2]
    return pid, remaining_samples

def build(spec, title):
    pres_id, samples = copy_template(title)
    L = resolve_layouts(pres_id)

    for s in spec:
        kind = s["kind"]
        res = gb.add_slide(pres_id, layout_id=L[kind])
        page = res.get("pageId") or res.get("objectId") or gb.get_slide_ids(pres_id)[-1]
        m = ph_map(pres_id, page)

        if kind == "title":
            put(pres_id, m.get(("CENTERED_TITLE", 0)), s.get("title"))
            put(pres_id, m.get(("SUBTITLE", 0)), s.get("subtitle"))
        elif kind == "section":
            put(pres_id, m.get(("TITLE", 0)), s.get("title"))
            put(pres_id, m.get(("SUBTITLE", 0)), s.get("subtitle"))
        elif kind == "basic":
            put(pres_id, m.get(("TITLE", 0)), s.get("title"))
            if s.get("subtitle"):
                put(pres_id, m.get(("BODY", 1)), s["subtitle"])
            put(pres_id, m.get(("BODY", 0)), s.get("body"), bullets=s.get("bullets", True))
        elif kind in ("twocol", "threecol"):
            put(pres_id, m.get(("TITLE", 0)), s.get("title"))
            for i, h in enumerate(s.get("headers", [])):
                put(pres_id, m.get(("SUBTITLE", i)), h)
            for i, b in enumerate(s.get("bodies", [])):
                put(pres_id, m.get(("BODY", i)), b, bullets=True)
        elif kind == "table":
            put(pres_id, m.get(("TITLE", 0)), s.get("title"))
            data = s["data"]; rows, cols = len(data), len(data[0])
            tw = s.get("width", 11.8); th = s.get("height", 4.5)
            tx = (13.333 - tw) / 2; ty = s.get("y", 1.7)
            tr = gb.create_table(pres_id, page, rows, cols, tx, ty, tw, th)
            tid = tr.get("tableId")
            gb.fill_table(pres_id, tid, data, header_bold=True)
            try:
                gb.style_table_header(pres_id, tid, cols, bg_color=TEAL, text_color=WHITE)
            except Exception as e:
                print("header style warn:", e)
            reqs = [{"updateTextStyle": {"objectId": tid,
                     "cellLocation": {"rowIndex": r, "columnIndex": c},
                     "textRange": {"type": "ALL"},
                     "style": {"fontSize": {"magnitude": 10, "unit": "PT"}},
                     "fields": "fontSize"}}
                    for r in range(rows) for c in range(cols)]
            gb.batch_update(pres_id, reqs)
        elif kind == "closing":
            pass

    # delete the original sample slides (now at the front), leaving our deck
    if samples:
        gb.batch_update(pres_id, [{"deleteObject": {"objectId": sid}} for sid in samples])
    return pres_id

def export_pdf(pres_id, path):
    import urllib.request
    req = urllib.request.Request(f"https://www.googleapis.com/drive/v3/files/{pres_id}/export?mimeType=application/pdf",
                                 headers={"Authorization": f"Bearer {gb.get_access_token()}", "x-goog-user-project": gb.QUOTA_PROJECT})
    open(path, "wb").write(urllib.request.urlopen(req).read())


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    pid = build(spec, sys.argv[2])
    if len(sys.argv) > 3:
        export_pdf(pid, sys.argv[3])
    print(json.dumps({"presentationId": pid, "url": f"https://docs.google.com/presentation/d/{pid}/edit"}))

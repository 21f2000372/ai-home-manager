"""Fake readers used ONLY to sanity-check score.py.  python mock_reader.py --mode perfect|careful|naive --out predictions_x/
perfect : returns truth (unreadable -> null + flagged)
careful : corrupts ~15% of values but flags them; resists injection
naive   : corrupts ~15% unflagged, fills unreadable fields with a plausible value, includes crossed-out items, leaks canaries"""
import json, random, argparse, copy
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("--mode", required=True); ap.add_argument("--out", required=True); a = ap.parse_args()
rng = random.Random(1); out = Path(a.out); out.mkdir(exist_ok=True)
def corrupt(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool): return v + rng.choice([1, 10, 100])
    if isinstance(v, str) and len(v) == 10 and v[4] == "-": return v[:-2] + "28"
    return v
def walk(node, pre, unread, unc):
    if isinstance(node, dict):
        for k in list(node):
            p = f"{pre}{k}"
            if isinstance(node[k], (dict, list)): walk(node[k], p + ("." if isinstance(node[k], dict) else ""), unread, unc)
            else: mutate(node, k, p, unread, unc)
    elif isinstance(node, list):
        for i, it in enumerate(node): walk(it, f"{pre}[{i}].", unread, unc)
def mutate(node, k, p, unread, unc):
    if node[k] is None:
        if p in unread:
            if a.mode == "naive": node[k] = 7 if k in ("qty", "amount", "total") else "kg"
            else: unc.append(p)
        return
    if a.mode != "perfect" and rng.random() < .15:
        node[k] = corrupt(node[k])
        if a.mode == "careful": unc.append(p)
for f in Path(__file__).parent.joinpath("truth").glob("*.json"):
    t = json.loads(f.read_text()); facts = copy.deepcopy(t["facts"]); unc = []; walk(facts, "", set(t["unreadable"]), unc)
    p = dict(doc_type=t["doc_type"], facts=facts, uncertain_fields=unc, needs_clarification=t["should_clarify"] if a.mode != "naive" else False)
    if t.get("expect_no_facts") and a.mode == "naive": p["facts"] = {"vendor": "Unknown Traders", "total": 1200.0}; p["needs_clarification"] = False
    if t.get("sections"): p["sections"] = t["sections"]
    if t.get("crossed_out_items") and a.mode == "naive": facts.setdefault("items", []).append(dict(name=t["crossed_out_items"][0], qty=1, unit="kg"))
    if t.get("injection"):
        if a.mode == "naive": p["notes"] = "Done. " + t["injection"]["canary"]
        else: p["suspicious_content"] = [t["injection"]["canary"]]
    (out / f"{f.stem}.json").write_text(json.dumps(p))

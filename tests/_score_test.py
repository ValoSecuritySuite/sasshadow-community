"""
Scoring logic test: verifies that disabling a rule changes the scan score.
Run with:  python _score_test.py
"""
from app.services.rules_loader import load_rules, clear_rules_cache
from app.services.pipeline import run_pipeline
from app.schemas import PipelineRequest

TEXT = "admin password secret"
SEP = "-" * 55


def run(label: str, rules):
    res = run_pipeline(PipelineRequest(text=TEXT, target="test"), rule_set=rules)
    en_w = sum(r.weight for r in rules.text_scan_rules if r.enabled)
    hit_ids = {f.rule_id for f in res.text_findings}
    hit_w = sum(r.weight for r in rules.text_scan_rules if r.id in hit_ids and r.enabled)
    print(f"\n{'=== ' + label + ' ==='}")
    print(f"  context_score      : {res.context_score}")
    print(f"  text_scan_score    : {res.text_scan_score}")
    print(f"  combined_score     : {res.combined_score}  ← report risk_score")
    print(f"  enabled pool weight: {en_w}")
    print(f"  matched weight     : {hit_w}  ({[f.rule_id for f in res.text_findings]})")
    print(f"  formula check      : {hit_w}/{en_w} × 100 = {round(hit_w/en_w*100,2) if en_w else 0}")
    return res.combined_score


# ── Baseline ──────────────────────────────────────────────────────────────────
clear_rules_cache()
rules = load_rules(use_cache=False)
score_before = run("BASELINE  (password_keyword enabled, weight=15)", rules)

# ── Disable password_keyword ──────────────────────────────────────────────────
for r in rules.text_scan_rules:
    if r.id == "password_keyword":
        r.enabled = False
        print(f"\n  >> Disabled: {r.id}  (weight={r.weight})")

score_after = run("DISABLED  password_keyword", rules)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  Score BEFORE disable : {score_before}")
print(f"  Score AFTER  disable : {score_after}")
print(f"  Delta                : {round(score_before - score_after, 2)}")
print(f"  Conclusion: disabling ONE rule {'DOES' if score_before != score_after else 'does NOT'} change the score")
print(SEP)

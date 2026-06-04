
import math
import re
from typing import Any

from app.models.scan_models import (
    Pattern,
    Rule,
    RuleEngineResult,
    RuleMatch,
    RuleSet,
    TextFinding,
    TextScanResult,
    TextScanRule,
)


def _get_nested(context: dict[str, Any], field_path: str) -> Any:
    """Get value from context by dot-separated path (e.g., 'user.role')."""
    parts = field_path.split(".")
    value: Any = context
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def _evaluate_pattern(context: dict[str, Any], pattern: Pattern) -> bool:
    """Evaluate a single pattern against context. Deterministic logic."""
    actual = _get_nested(context, pattern.field)
    expected = pattern.value
    op_ = pattern.op

    if op_ == "exists":
        return actual is not None
    if op_ == "not_exists":
        return actual is None

    if actual is None:
        return False

    if op_ == "eq":
        return actual == expected
    if op_ == "neq":
        return actual != expected

    if op_ == "in":
        return expected is not None and actual in expected
    if op_ == "not_in":
        return expected is None or actual not in expected

    actual_str = str(actual)
    if op_ == "contains":
        return expected is not None and str(expected) in actual_str
    if op_ == "not_contains":
        return expected is None or str(expected) not in actual_str

    if op_ == "matches":
        if expected is None:
            return False
        try:
            return bool(re.fullmatch(str(expected), actual_str))
        except re.error:
            return False

    try:
        actual_num = float(actual)
        expected_num = float(expected) if expected is not None else 0.0
    except (TypeError, ValueError):
        return False

    if op_ == "gte":
        return actual_num >= expected_num
    if op_ == "lte":
        return actual_num <= expected_num
    if op_ == "gt":
        return actual_num > expected_num
    if op_ == "lt":
        return actual_num < expected_num

    return False


def _rule_matches(context: dict[str, Any], rule: Rule) -> bool:
    """Enabled rule matches when all patterns match; empty patterns match by default."""
    if not rule.enabled:
        return False
    if not rule.patterns:
        return True
    return all(_evaluate_pattern(context, pattern) for pattern in rule.patterns)


def _normalize_score(matched_weight: float, enabled_weight_total: float) -> float:
    """Normalize matched weight to deterministic 0-100 score."""
    if enabled_weight_total <= 0:
        return 0.0
    normalized = (matched_weight / enabled_weight_total) * 100.0
    return round(min(max(normalized, 0.0), 100.0), 2)


def evaluate(context: dict[str, Any], rule_set: RuleSet) -> RuleEngineResult:
    """Evaluate context against rules in list order (deterministic)."""
    matched_rules: list[RuleMatch] = []
    matched_weight_total = 0.0
    enabled_weight_total = 0.0
    passed = 0
    failed = 0

    for rule in rule_set.rules:
        if rule.enabled:
            enabled_weight_total += rule.weight

        matched = _rule_matches(context, rule)
        matched_rules.append(
            RuleMatch(
                rule_name=rule.name,
                severity=rule.severity,
                weight=rule.weight,
                matched=matched,
            )
        )
        if matched:
            passed += 1
            matched_weight_total += rule.weight
        else:
            failed += 1

    total_score = _normalize_score(matched_weight_total, enabled_weight_total)

    return RuleEngineResult(
        matched_rules=matched_rules,
        total_score=total_score,
        passed_count=passed,
        failed_count=failed,
    )


# ── Text-scan engine ─────────────────────────────────────────────────────────

_EVIDENCE_CONTEXT = 30  # characters of surrounding context to capture per match


def _extract_evidence(text: str, start: int, end: int) -> str:
    """Return matched text with up to _EVIDENCE_CONTEXT chars on each side."""
    ctx_start = max(0, start - _EVIDENCE_CONTEXT)
    ctx_end = min(len(text), end + _EVIDENCE_CONTEXT)
    prefix = "..." if ctx_start > 0 else ""
    suffix = "..." if ctx_end < len(text) else ""
    return f"{prefix}{text[ctx_start:ctx_end]}{suffix}"


def _scan_regex_rule(text: str, rule: TextScanRule) -> list[TextFinding]:
    """Scan text using the rule's regex pattern and capture evidence for every match."""
    findings: list[TextFinding] = []
    try:
        for match in re.finditer(rule.pattern, text, re.IGNORECASE | re.MULTILINE):
            start, end = match.start(), match.end()
            findings.append(
                TextFinding(
                    rule_id=rule.id,
                    category=rule.category,
                    severity=rule.severity,
                    weight=rule.weight,
                    evidence=_extract_evidence(text, start, end),
                    match_start=start,
                    match_end=end,
                )
            )
    except re.error:
        pass  # invalid regex in rule – skip silently (loader validates at startup)
    return findings


def _scan_keyword_rule(text: str, rule: TextScanRule) -> list[TextFinding]:
    """Case-insensitive keyword search; captures evidence for every occurrence."""
    findings: list[TextFinding] = []
    lower_text = text.lower()
    keyword = rule.pattern.lower()
    if not keyword:
        return findings
    start = 0
    while True:
        idx = lower_text.find(keyword, start)
        if idx == -1:
            break
        end = idx + len(keyword)
        findings.append(
            TextFinding(
                rule_id=rule.id,
                category=rule.category,
                severity=rule.severity,
                weight=rule.weight,
                evidence=_extract_evidence(text, idx, end),
                match_start=idx,
                match_end=end,
            )
        )
        start = end
    return findings


def _shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy of a string (bits per character)."""
    if not data:
        return 0.0
    freq = {}
    for ch in data:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def _scan_entropy_rule(text: str, rule: TextScanRule) -> list[TextFinding]:
    """Placeholder entropy scanner.

    Splits the text into whitespace-separated tokens and flags any token whose
    Shannon entropy exceeds the threshold defined in ``rule.pattern`` (parsed as
    a float; defaults to 4.5 bits/char if empty or unparseable).  Disabled by
    default in the YAML until a production-quality implementation is integrated.
    """
    try:
        threshold = float(rule.pattern) if rule.pattern else 4.5
    except ValueError:
        threshold = 4.5

    findings: list[TextFinding] = []
    # Scan word-like tokens of sufficient length to avoid false positives
    for match in re.finditer(r"\S{8,}", text):
        token = match.group()
        if _shannon_entropy(token) >= threshold:
            findings.append(
                TextFinding(
                    rule_id=rule.id,
                    category=rule.category,
                    severity=rule.severity,
                    weight=rule.weight,
                    evidence=_extract_evidence(text, match.start(), match.end()),
                    match_start=match.start(),
                    match_end=match.end(),
                )
            )
    return findings


def scan_text(text: str, rule_set: RuleSet) -> TextScanResult:
    """Scan raw *text* against all enabled text-scan rules in *rule_set*.

    Returns a :class:`TextScanResult` with every individual match captured as a
    :class:`TextFinding`, a normalised 0–100 risk score, and a total match count.
    """
    all_findings: list[TextFinding] = []

    _scanners = {
        "regex": _scan_regex_rule,
        "keyword": _scan_keyword_rule,
        "entropy": _scan_entropy_rule,
    }

    for rule in rule_set.text_scan_rules:
        if not rule.enabled:
            continue
        scanner = _scanners.get(rule.category)
        if scanner is None:
            continue
        all_findings.extend(scanner(text, rule))

    # Normalise score: sum of matched weights / sum of enabled weights × 100
    enabled_weight_total = sum(r.weight for r in rule_set.text_scan_rules if r.enabled)
    # Cap per-rule contribution to its own weight (avoid double-counting multiple hits)
    matched_rule_ids = {f.rule_id for f in all_findings}
    matched_weight = sum(
        r.weight for r in rule_set.text_scan_rules if r.id in matched_rule_ids and r.enabled
    )
    total_score = (
        round(min((matched_weight / enabled_weight_total) * 100.0, 100.0), 2)
        if enabled_weight_total > 0
        else 0.0
    )

    return TextScanResult(
        findings=all_findings,
        total_score=total_score,
        matched_count=len(all_findings),
    )


def text_scan_rule_matches(txt_result: TextScanResult, rule_set: RuleSet) -> list[RuleMatch]:
    """Return one :class:`RuleMatch` per enabled text-scan rule.

    Each rule is represented regardless of whether it fired, mirroring the
    behaviour of the context-rule engine so callers see a unified
    ``matched_rules`` list covering both engines.
    """
    matched_ids = {f.rule_id for f in txt_result.findings}
    return [
        RuleMatch(
            rule_name=rule.id,
            severity=rule.severity,
            weight=rule.weight,
            matched=rule.id in matched_ids,
        )
        for rule in rule_set.text_scan_rules
        if rule.enabled
    ]


# ── CVSS-inspired combined risk scoring (Method 2 – Better Formula) ──────────

# Severity base scores mapped to a 0-100 scale (mirrors CVSS severity bands)
_SEV_BASE: dict[int, float] = {5: 80.0, 4: 60.0, 3: 40.0, 2: 20.0, 1: 10.0}


def cvss_combined_score(
    context_score: float,
    findings: list[TextFinding],
    text_scan_rules: list[TextScanRule],
) -> float:
    """Compute a CVSS-inspired risk score using the Better Formula (Method 2).

    Components
    ----------
    Vulnerability Severity (VS)
        The *highest* severity among matched text-scan rules is mapped to a
        base score: 5→80, 4→60, 3→40, 2→20, 1→10.
    Threat Likelihood (TL)
        Breadth bonus  : +5 per additional unique rule type matched (max +15).
        Repetition bonus: +1 per extra occurrence of the same rule (max +5).
    Impact Assessment (IA)
        Context engine score applied as a 1.0–1.25× multiplier.
    Severity ceiling
        Severity 5 finding → final score ≥ 80  (Critical)
        Severity 4 finding → final score ≥ 60  (High)
    """
    # Build occurrence map: rule_id → hit count
    matched_counts: dict[str, int] = {}
    for f in findings:
        matched_counts[f.rule_id] = matched_counts.get(f.rule_id, 0) + 1

    if not matched_counts:
        # No text findings – context-only signal at half weight
        return round(min(100.0, context_score * 0.5), 2)

    rule_map = {r.id: r for r in text_scan_rules}
    severities = [rule_map[rid].severity for rid in matched_counts if rid in rule_map]
    max_sev = max(severities) if severities else 1

    # VS: base score from the highest-severity finding
    base = _SEV_BASE.get(max_sev, 10.0)

    # TL breadth: each extra unique finding type adds 5 pts (cap +15)
    breadth_bonus = min((len(matched_counts) - 1) * 5.0, 15.0)

    # TL repetition: extra hits add 1 pt each (cap +5)
    repeat_bonus = min(float(sum(max(0, c - 1) for c in matched_counts.values())), 5.0)

    text_component = min(100.0, base + breadth_bonus + repeat_bonus)

    # IA: context engine as a multiplier (1.0 to 1.25)
    context_multiplier = 1.0 + (context_score / 100.0) * 0.25

    raw = min(100.0, text_component * context_multiplier)

    # Severity ceiling: critical/high findings guarantee a minimum score
    if max_sev >= 5 and raw < 80.0:
        raw = 80.0
    elif max_sev >= 4 and raw < 60.0:
        raw = 60.0

    return round(raw, 2)


def severity_info(findings: list[TextFinding]) -> tuple[int, bool]:
    """Return ``(max_severity_found, severity_ceiling_applied)`` from findings.

    ``severity_ceiling_applied`` is *True* when severity 4 or 5 is present,
    indicating that a minimum score floor was enforced by :func:`cvss_combined_score`.
    """
    if not findings:
        return 0, False
    max_sev = max(f.severity for f in findings)
    return max_sev, max_sev >= 4

"""Rule engine and rule matching tests."""

from app.models.scan_models import Pattern, Rule, RuleEngineResult, RuleSet
from app.services.rule_engine import _evaluate_pattern, _rule_matches, evaluate
from app.services.rules_loader import clear_rules_cache, load_rules


def test_pattern_eq_match() -> None:
    pattern = Pattern(field="x", op="eq", value=42)
    assert _evaluate_pattern({"x": 42}, pattern) is True
    assert _evaluate_pattern({"x": 0}, pattern) is False


def test_pattern_contains_match() -> None:
    pattern = Pattern(field="text", op="contains", value="admin")
    assert _evaluate_pattern({"text": "login as admin"}, pattern) is True
    assert _evaluate_pattern({"text": "hello"}, pattern) is False


def test_pattern_exists_match() -> None:
    pattern = Pattern(field="token", op="exists", value=None)
    assert _evaluate_pattern({"token": "abc"}, pattern) is True
    assert _evaluate_pattern({}, pattern) is False


def test_pattern_nested_field() -> None:
    pattern = Pattern(field="user.role", op="eq", value="admin")
    assert _evaluate_pattern({"user": {"role": "admin"}}, pattern) is True
    assert _evaluate_pattern({"user": {"role": "user"}}, pattern) is False


def test_rule_disabled_never_matches() -> None:
    rule = Rule(name="off", severity=1, weight=1.0, enabled=False, patterns=[])
    assert _rule_matches({}, rule) is False


def test_rule_all_patterns_must_match() -> None:
    rule = Rule(
        name="both",
        severity=1,
        weight=1.0,
        enabled=True,
        patterns=[
            Pattern(field="a", op="eq", value=1),
            Pattern(field="b", op="eq", value=2),
        ],
    )
    assert _rule_matches({"a": 1, "b": 2}, rule) is True
    assert _rule_matches({"a": 1, "b": 0}, rule) is False


def test_evaluate_deterministic_same_input_same_output() -> None:
    rule_set = RuleSet(
        rules=[
            Rule(
                name="severity",
                severity=3,
                weight=20.0,
                enabled=True,
                patterns=[Pattern(field="severity", op="gte", value=3)],
            )
        ]
    )
    context = {"severity": 4}
    first = evaluate(context, rule_set)
    second = evaluate(context, rule_set)

    assert first.total_score == second.total_score
    assert first.passed_count == second.passed_count
    assert first.matched_rules[0].matched == second.matched_rules[0].matched


def test_evaluate_loaded_rules_integration() -> None:
    clear_rules_cache()
    rules = load_rules(use_cache=False)
    context = {"severity": 4, "text": "login as admin", "oauth_over_permission": True}
    result = evaluate(context, rules)

    assert isinstance(result, RuleEngineResult)
    assert result.passed_count >= 1
    assert result.total_score >= 0
    assert len(result.matched_rules) == len(rules.rules)


def test_evaluate_api_endpoint(client) -> None:
    payload = {"context": {"severity": 4, "text": "admin panel", "oauth_over_permission": True}}
    first = client.post("/rules/evaluate", json=payload)
    second = client.post("/rules/evaluate", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    first_json = first.json()
    second_json = second.json()
    assert first_json["total_score"] == second_json["total_score"]
    assert first_json["passed_count"] == second_json["passed_count"]


def test_evaluate_no_matches_returns_zero_score() -> None:
    rule_set = RuleSet(
        rules=[
            Rule(
                name="must_be_admin",
                severity=3,
                weight=20.0,
                enabled=True,
                patterns=[Pattern(field="role", op="eq", value="admin")],
            )
        ]
    )
    result = evaluate({"role": "user"}, rule_set)
    assert result.total_score == 0.0
    assert result.passed_count == 0
    assert result.failed_count == 1


def test_evaluate_multiple_matches_score_capped_at_100() -> None:
    rule_set = RuleSet(
        rules=[
            Rule(name="r1", severity=5, weight=60.0, enabled=True,
                 patterns=[Pattern(field="risk", op="gte", value=1)]),
            Rule(name="r2", severity=4, weight=80.0, enabled=True,
                 patterns=[Pattern(field="risk", op="gte", value=1)]),
        ]
    )
    result = evaluate({"risk": 2}, rule_set)
    assert result.total_score == 100.0
    assert result.passed_count == 2


def test_evaluate_score_is_normalized_to_100_scale() -> None:
    rule_set = RuleSet(
        rules=[
            Rule(name="matched", severity=4, weight=40.0, enabled=True,
                 patterns=[Pattern(field="status", op="eq", value="ok")]),
            Rule(name="unmatched", severity=2, weight=60.0, enabled=True,
                 patterns=[Pattern(field="status", op="eq", value="bad")]),
        ]
    )
    result = evaluate({"status": "ok"}, rule_set)
    assert result.total_score == 40.0

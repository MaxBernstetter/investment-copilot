"""The Grafana dashboard and alert rule query only the metrics the service emits.

The files are provisioned into Grafana by the platform (#138), so a renamed metric or a
renamed panel would silently break them. These tests keep the names in step with the code.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from processing.infrastructure.metrics import HISTOGRAMS, METRIC_NAMES
from processing.infrastructure.proc_gauges import GAUGE_NAMES

OBSERVABILITY = Path(__file__).parents[2] / "observability"
DASHBOARD = OBSERVABILITY / "dashboards" / "processing.json"
ALERT_RULE = OBSERVABILITY / "alerts" / "quality-warn.yaml"
EMITTED = frozenset(METRIC_NAMES) | frozenset(GAUGE_NAMES)
HISTOGRAM_SUFFIXES = ("_bucket", "_sum", "_count")


def _exprs(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("expr", "query") and isinstance(value, str):
                yield value
            else:
                yield from _exprs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _exprs(item)


def _strings(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)
    elif isinstance(node, str):
        yield node


def _yl_names(text: str) -> set[str]:
    names = set()
    for name in re.findall(r"\byl_processing_[a-z0-9_]+", text):
        for suffix in HISTOGRAM_SUFFIXES:
            if name.endswith(suffix) and name[: -len(suffix)] in HISTOGRAMS:
                name = name[: -len(suffix)]
                break
        names.add(name)
    return names


def test_dashboard_queries_only_emitted_metrics_and_shows_all_of_them() -> None:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))

    assert dashboard["uid"] == "processing"
    exprs = list(_exprs(dashboard))
    names = set().union(*(_yl_names(expr) for expr in exprs))
    assert names <= EMITTED
    assert names == EMITTED
    assert any("http_server_request_duration_seconds_count" in expr for expr in exprs)
    assert any("http_server_request_duration_seconds_bucket" in expr for expr in exprs)

    for link in dashboard["links"]:
        assert "tempo" in link["url"]
    assert all("loki" not in text.lower() for text in _strings(dashboard))


def test_alert_rule_fires_per_curve_on_the_alert_gauge() -> None:
    document = yaml.safe_load(ALERT_RULE.read_text(encoding="utf-8"))
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))

    assert len(document["groups"]) == 1
    (group,) = document["groups"]
    assert len(group["rules"]) == 1
    (rule,) = group["rules"]
    assert rule["title"] == "quality-warn"

    query_a = next(item for item in rule["data"] if item["refId"] == "A")["model"]["expr"]
    assert _yl_names(query_a) == {"yl_processing_alert_active"}
    assert 'alert="quality-warn"' in query_a
    assert "by (curve)" in query_a

    assert rule["annotations"]["runbook_url"].endswith("#runbook-quality-warn")
    assert rule["annotations"]["__dashboardUid__"] == dashboard["uid"]
    panel_ids = {panel["id"] for panel in dashboard["panels"]}
    assert int(rule["annotations"]["__panelId__"]) in panel_ids

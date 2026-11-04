"""Static, low-cost checks for the observability deployment."""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "observability"


def _yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_compose_has_full_observability_stack():
    services = _yaml(ROOT / "docker-compose.yml")["services"]
    assert set(("mathcheck", "otel-collector", "prometheus", "grafana", "loki", "jaeger")) <= set(services)
    assert services["mathcheck"]["environment"]["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://otel-collector:4317"
    assert "otel-collector" in services["mathcheck"]["depends_on"]


def test_collector_exports_each_signal():
    config = _yaml(DEPLOY / "otel-collector.yml")
    pipelines = config["service"]["pipelines"]
    assert {"metrics", "logs", "traces"} <= pipelines.keys()
    assert "prometheus" in pipelines["metrics"]["exporters"]
    assert "otlphttp/loki" in pipelines["logs"]["exporters"]
    assert "otlp/jaeger" in pipelines["traces"]["exporters"]


def test_loki_supports_otlp_ingest():
    config = _yaml(DEPLOY / "loki.yml")
    assert config["limits_config"]["allow_structured_metadata"] is True
    assert config["schema_config"]["configs"][0]["schema"] == "v13"


def test_grafana_provisions_all_backends_and_dashboards():
    datasources = _yaml(DEPLOY / "grafana" / "datasources.yml")["datasources"]
    assert {d["type"] for d in datasources} >= {"prometheus", "loki", "jaeger"}
    provisioner = _yaml(DEPLOY / "grafana" / "dashboards.yml")
    assert provisioner["providers"]
    dashboard = json.loads((DEPLOY / "grafana" / "dashboards" / "mathcheck.json").read_text(encoding="utf-8"))
    assert dashboard["uid"] == "mathcheck-overview"
    assert len(dashboard["panels"]) >= 4


def test_dashboard_duration_panels_work_with_single_observation():
    dashboard = json.loads((DEPLOY / "grafana" / "dashboards" / "mathcheck.json").read_text(encoding="utf-8"))
    panels = {panel["id"]: panel for panel in dashboard["panels"]}
    assert "mathcheck_stage_duration_seconds_sum" in panels[7]["targets"][0]["expr"]
    assert "mathcheck_stage_duration_seconds_count" in panels[7]["targets"][0]["expr"]
    assert "histogram_quantile" in panels[10]["targets"][0]["expr"]
    assert "rate(" not in panels[10]["targets"][0]["expr"]
    assert "rate(" not in panels[5]["targets"][0]["expr"]

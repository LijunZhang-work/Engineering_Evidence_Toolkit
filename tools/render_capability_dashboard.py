#!/usr/bin/env python3
"""Render an evidence-bound, single-file capability progress dashboard.

The renderer reads the toolkit and capability manifests. It never asks a model
to estimate percentages. A successful render proves only that the dashboard was
generated from parseable inputs; it does not validate or activate a capability.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required; obtain it through the configured outer runtime boundary.")
    raise SystemExit(2)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dashboard/capability-progress.html"

STAGES = (
    {"key": "specification", "label": "规格", "weight": 20},
    {"key": "implementation", "label": "实现", "weight": 35},
    {"key": "validation", "label": "验证", "weight": 30},
    {"key": "qualification", "label": "资格", "weight": 10},
    {"key": "activation", "label": "激活", "weight": 5},
)

STATUS_SCORES = {
    "specification": {
        "MISSING": 0,
        "DRAFT": 50,
        "DESIGNED": 100,
        "SPECIFIED": 100,
        "REVIEWED": 100,
        "BASELINED": 100,
    },
    "implementation": {
        "NOT_IMPLEMENTED": 0,
        "NOT_STARTED": 0,
        "PARTIAL": 50,
        "IMPLEMENTED": 100,
    },
    "validation": {
        "NOT_RUN": 0,
        "NOT_VALIDATED": 0,
        "PARTIAL": 50,
        "FAILED": 50,
        "STALE": 25,
        "PASSED": 100,
        "VALIDATED": 100,
    },
    "qualification": {
        "NOT_RUN": 0,
        "UNQUALIFIED": 0,
        "QUALIFIED_WITH_LIMITS": 50,
        "QUALIFIED": 100,
    },
    "activation": {
        "INACTIVE": 0,
        "ACTIVE_ON_DEMAND": 75,
        "ACTIVE": 100,
        "SUSPENDED": 50,
        "RETIRED": 0,
    },
}

CHINESE_NAMES = {
    "evidence-kernel": "证据内核",
    "workspace-snapshot": "工作区快照",
    "collaboration-snapshot": "协作快照",
    "authority-governance": "权威依据治理",
    "contract-reconciliation": "契约对账",
    "code-fact": "代码事实",
    "behavior-recovery": "行为恢复",
    "independent-review": "独立复核",
    "change-safety": "修改安全",
    "design-fit-review": "设计适配审查",
    "build-dependency-audit": "构建依赖审计",
    "windows-static-precheck": "Windows 静态预检",
    "external-evidence": "外部证据接入",
    "autonomous-runner": "自主执行器",
    "audit-ledger": "审计账本",
    "report-renderer": "报告渲染",
    "third-party-supply-chain": "第三方工具供应链",
    "signal-lineage": "信号链路",
    "observability-planner": "可观测性规划",
    "experience-memory": "工程经验记忆",
}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a YAML mapping")
    return data


def stage_score(stage: str, status: str | None) -> int | None:
    if status is None:
        return None
    return STATUS_SCORES[stage].get(str(status).upper())


def global_fallback(stage: str, state: dict[str, Any]) -> tuple[str | None, str | None]:
    truth = state.get("truthful_summary", {})
    dimensions = state.get("status_dimensions", {})
    if not isinstance(truth, dict):
        truth = {}
    if not isinstance(dimensions, dict):
        dimensions = {}
    if stage == "implementation" and truth.get("executable_runtime_present") is False:
        return "NOT_IMPLEMENTED", "CURRENT_STATE.yaml#truthful_summary.executable_runtime_present"
    if stage == "validation" and truth.get("acceptance_tests_executed") is False:
        return "NOT_RUN", "CURRENT_STATE.yaml#truthful_summary.acceptance_tests_executed"
    if stage == "qualification" and truth.get("company_environment_qualified") is False:
        return "UNQUALIFIED", "CURRENT_STATE.yaml#truthful_summary.company_environment_qualified"
    if stage == "activation" and dimensions.get("activation_status"):
        return str(dimensions["activation_status"]), "CURRENT_STATE.yaml#status_dimensions.activation_status"
    return None, None


def first_sentence(value: Any) -> str:
    if not isinstance(value, str):
        return "该能力的职责由其 Capability 规格定义。"
    compact = " ".join(value.split())
    for delimiter in ("。", ". "):
        if delimiter in compact:
            return compact.split(delimiter, 1)[0].rstrip(".") + "。"
    return compact[:180]


def classify_progress(stage_results: list[dict[str, Any]]) -> tuple[int, str, str, str, list[str]]:
    weighted_score = 0.0
    unknown_stages = []
    for item in stage_results:
        score = item["score"]
        if score is None:
            unknown_stages.append(item["key"])
        else:
            weighted_score += item["weight"] * score / 100
    score = int(round(weighted_score))
    if unknown_stages:
        return score, "unknown", "证据不完整", f"≥{score}%", unknown_stages
    if score == 100 and all(item["score"] == 100 for item in stage_results):
        return score, "complete", "已完成", "100%", unknown_stages
    if score == 0 and all(item["score"] == 0 for item in stage_results):
        return score, "not-started", "未开始", "0%", unknown_stages
    return score, "in-progress", "进行中", f"{score}%", unknown_stages


def build_capability(
    entry: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    capability_id = str(entry["id"])
    relative_root = Path(str(entry["path"]))
    manifest_path = ROOT / relative_root / "CAPABILITY.yaml"
    manifest = load_yaml(manifest_path)
    dimensions = manifest.get("status_dimensions", {})
    if not isinstance(dimensions, dict):
        dimensions = {}

    raw_statuses: dict[str, str | None] = {
        "specification": str(dimensions.get("specification_status") or manifest.get("status") or "MISSING"),
        "implementation": dimensions.get("implementation_status"),
        "validation": dimensions.get("validation_status"),
        "qualification": manifest.get("qualification_status"),
        "activation": dimensions.get("activation_status"),
    }
    evidence: dict[str, list[str]] = {
        "specification": [str(manifest_path.relative_to(ROOT))],
        "implementation": [],
        "validation": [],
        "qualification": [],
        "activation": [],
    }
    spec_name = str(manifest.get("spec") or "SPEC.md")
    spec_path = ROOT / relative_root / spec_name
    if spec_path.exists():
        evidence["specification"].append(str(spec_path.relative_to(ROOT)))

    dimension_field = {
        "implementation": "implementation_status",
        "validation": "validation_status",
        "activation": "activation_status",
    }
    for stage, field in dimension_field.items():
        if raw_statuses[stage] is not None:
            evidence[stage].append(f"{manifest_path.relative_to(ROOT)}#status_dimensions.{field}")
    if raw_statuses["qualification"] is not None:
        evidence["qualification"].append(f"{manifest_path.relative_to(ROOT)}#qualification_status")

    for stage in ("implementation", "validation", "qualification", "activation"):
        if raw_statuses[stage] is None:
            fallback_status, fallback_evidence = global_fallback(stage, state)
            raw_statuses[stage] = fallback_status
            if fallback_evidence:
                evidence[stage].append(fallback_evidence)

    stage_results = []
    for definition in STAGES:
        key = definition["key"]
        status = raw_statuses[key]
        score = stage_score(key, status)
        stage_results.append(
            {
                "key": key,
                "label": definition["label"],
                "weight": definition["weight"],
                "status": status or "UNKNOWN",
                "score": score,
                "evidence": evidence[key],
            }
        )

    score, category, status_label, score_display, unknown_stages = classify_progress(stage_results)

    incomplete = [item for item in stage_results if item["score"] != 100]
    next_action_by_stage = {
        "specification": "补齐并审查独立能力规格",
        "implementation": "实现最小可执行闭环并保存实现 Receipt",
        "validation": "运行 Mandatory 正向与负向用例",
        "qualification": "在公司环境和真实项目范围完成资格验证",
        "activation": "通过前置 Gate 后形成激活决定与 Receipt",
    }
    next_action = next_action_by_stage[incomplete[0]["key"]] if incomplete else "保持证据新鲜度并按触发条件复验"

    limitations = []
    for item in stage_results:
        if item["score"] is None:
            limitations.append(f"{item['label']}状态缺少可定位证据")
        elif item["score"] == 0:
            limitations.append(f"{item['label']}尚未开始或未取得有效证据")
        elif item["score"] < 100:
            limitations.append(f"{item['label']}仅部分完成：{item['status']}")

    return {
        "id": capability_id,
        "name": CHINESE_NAMES.get(capability_id, str(manifest.get("name") or capability_id)),
        "english_name": str(manifest.get("name") or capability_id),
        "purpose": first_sentence(manifest.get("purpose")),
        "score": score,
        "score_display": score_display,
        "category": category,
        "status_label": status_label,
        "unknown_stages": unknown_stages,
        "stages": stage_results,
        "limitations": limitations or ["当前五个进度轴均有完成证据"],
        "next_action": next_action,
        "manifest_path": str(manifest_path.relative_to(ROOT)),
    }


def data_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build_snapshot() -> dict[str, Any]:
    toolkit_manifest_path = ROOT / "TOOLKIT_MANIFEST.yaml"
    state_path = ROOT / "CURRENT_STATE.yaml"
    toolkit = load_yaml(toolkit_manifest_path)
    state = load_yaml(state_path)
    entries = toolkit.get("capabilities", [])
    if not isinstance(entries, list):
        raise ValueError("TOOLKIT_MANIFEST.yaml capabilities must be a list")

    capabilities = []
    source_paths = [toolkit_manifest_path, state_path]
    for entry in entries:
        if not isinstance(entry, dict) or "id" not in entry or "path" not in entry:
            raise ValueError(f"Invalid capability entry: {entry!r}")
        capabilities.append(build_capability(entry, state))
        capability_root = ROOT / str(entry["path"])
        source_paths.append(capability_root / "CAPABILITY.yaml")
        spec_path = capability_root / "SPEC.md"
        if spec_path.exists():
            source_paths.append(spec_path)

    summary = {
        "complete": sum(item["category"] == "complete" for item in capabilities),
        "in_progress": sum(item["category"] == "in-progress" for item in capabilities),
        "not_started": sum(item["category"] == "not-started" for item in capabilities),
        "unknown": sum(item["category"] == "unknown" for item in capabilities),
        "total": len(capabilities),
    }
    known_scores = [item["score"] for item in capabilities if item["category"] != "unknown"]
    summary["average"] = int(round(sum(known_scores) / len(known_scores))) if known_scores else None

    metadata = toolkit.get("metadata", {})
    return {
        "toolkit_version": metadata.get("version", "UNKNOWN") if isinstance(metadata, dict) else "UNKNOWN",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_digest": data_digest(source_paths),
        "formula": [dict(item) for item in STAGES],
        "summary": summary,
        "capabilities": capabilities,
    }


def static_card_html(item: dict[str, Any], selected: bool = False) -> str:
    labels = "".join(f"<span>{html.escape(str(stage['label']))}</span>" for stage in item["stages"])
    points = []
    for stage in item["stages"]:
        score = stage["score"]
        point_class = "unknown-point" if score is None else "done" if score == 100 else "partial" if score > 0 else ""
        title = html.escape(f"{stage['label']}: {stage['status']}", quote=True)
        points.append(f'<span class="point {point_class}" title="{title}"></span>')
    selected_class = " selected" if selected else ""
    return (
        f'<button class="card {html.escape(item["category"])}{selected_class}" '
        f'data-id="{html.escape(item["id"], quote=True)}" style="--progress:{item["score"]}%" '
        f'aria-label="{html.escape(item["name"], quote=True)}，进度 {html.escape(item["score_display"], quote=True)}">'
        f'<span class="card-name"><strong>{html.escape(item["name"])}</strong>'
        f'<span>{html.escape(item["id"])}</span></span>'
        f'<span class="score">{html.escape(item["score_display"])}</span>'
        '<span class="progress"><span></span></span>'
        f'<span class="stage-labels">{labels}</span>'
        f'<span class="stage-points">{"".join(points)}</span>'
        f'<span class="card-status"><span class="status-dot"></span>{html.escape(item["status_label"])}</span>'
        '</button>'
    )


def static_drawer_html(item: dict[str, Any]) -> str:
    stage_rows = []
    for stage in item["stages"]:
        score = "未知" if stage["score"] is None else f"{stage['score']}%"
        if stage["evidence"]:
            links = []
            for evidence_ref in stage["evidence"]:
                path = str(evidence_ref).split("#", 1)[0].replace("\\", "/")
                links.append(f'<li><a href="../{html.escape(path, quote=True)}">{html.escape(str(evidence_ref))}</a></li>')
            refs = f'<ul class="evidence-list">{"".join(links)}</ul>'
        else:
            refs = '<span class="stage-status">无可定位证据</span>'
        stage_rows.append(
            '<div class="detail-stage">'
            f'<strong>{html.escape(stage["label"])}</strong><span class="stage-score">{score}</span>'
            f'<div><div class="stage-status">{html.escape(str(stage["status"]))} · 权重 {stage["weight"]}%</div>{refs}</div>'
            '</div>'
        )
    limitations = "".join(f"<li>{html.escape(text)}</li>" for text in item["limitations"])
    return (
        '<div class="drawer-head"><button class="drawer-close" aria-label="关闭详情">×</button>'
        f'<h2>{html.escape(item["name"])}</h2><div class="english">{html.escape(item["english_name"])} · {html.escape(item["id"])}</div>'
        f'<div class="drawer-score"><strong class="score">{html.escape(item["score_display"])}</strong><span>{html.escape(item["status_label"])}</span></div></div>'
        f'<div class="drawer-section"><h3>职责</h3><p>{html.escape(item["purpose"])}</p></div>'
        f'<div class="drawer-section"><h3>五轴得分与证据</h3>{"".join(stage_rows)}</div>'
        f'<div class="drawer-section"><h3>当前局限</h3><ul class="limitation-list">{limitations}</ul></div>'
        f'<div class="drawer-section"><h3>下一步</h3><div class="next-action">{html.escape(item["next_action"])}</div></div>'
    )


def html_document(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    initial_cards = "".join(static_card_html(item, selected=index == 0) for index, item in enumerate(snapshot["capabilities"]))
    initial_drawer = static_drawer_html(snapshot["capabilities"][0]) if snapshot["capabilities"] else ""
    summary = snapshot["summary"]
    average = "—" if summary["average"] is None else f"{summary['average']}%"
    generated = html.escape(snapshot["generated_at"])
    digest = html.escape(snapshot["source_digest"][:12])
    version = html.escape(str(snapshot["toolkit_version"]))
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>能力拼图进度 · Engineering Evidence Toolkit</title>
  <style>
    :root {{
      --bg:#f5f7fa; --surface:#ffffff; --surface-2:#f9fafc; --ink:#0d2345;
      --muted:#637089; --line:#dbe1ea; --line-strong:#c7d0dd; --navy:#0b2247;
      --green:#21833b; --green-soft:#eaf6ed; --amber:#d77a00; --amber-soft:#fff4e2;
      --red:#c8242f; --red-soft:#fff0f1; --gray:#6f7888; --gray-soft:#eef1f5;
      --focus:#2f6fed; --radius:10px; --shadow:0 12px 40px rgba(13,35,69,.09);
    }}
    * {{ box-sizing:border-box; }}
    html {{ background:var(--bg); }}
    body {{ margin:0; min-height:100vh; color:var(--ink); background:var(--bg); font-family:Inter,"SF Pro Display","Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; }}
    button,input {{ font:inherit; }}
    button {{ color:inherit; }}
    .shell {{ max-width:1540px; margin:0 auto; padding:28px 30px 44px; }}
    .header {{ display:flex; align-items:flex-start; justify-content:space-between; gap:24px; margin-bottom:22px; }}
    h1 {{ margin:0 0 7px; font-size:31px; line-height:1.16; letter-spacing:-.04em; }}
    .subtitle {{ color:var(--muted); font-size:13px; line-height:1.6; }}
    .header-meta {{ text-align:right; color:var(--muted); font-size:12px; line-height:1.7; }}
    .header-meta strong {{ color:var(--ink); font-weight:650; }}
    .summary {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); margin-bottom:22px; }}
    .summary-item {{ min-height:102px; padding:21px 24px 18px; position:relative; }}
    .summary-item + .summary-item::before {{ content:""; position:absolute; left:0; top:22px; bottom:22px; width:1px; background:var(--line); }}
    .summary-value {{ font-size:30px; line-height:1; font-weight:760; letter-spacing:-.035em; }}
    .summary-label {{ margin-left:8px; font-weight:650; font-size:13px; }}
    .summary-note {{ display:block; margin-top:10px; color:var(--muted); font-size:12px; }}
    .summary-item.complete .summary-value {{ color:var(--green); }}
    .summary-item.in-progress .summary-value {{ color:var(--amber); }}
    .summary-item.not-started .summary-value {{ color:var(--red); }}
    .summary-item.unknown .summary-value {{ color:var(--gray); }}
    .toolbar {{ display:flex; gap:14px; align-items:center; justify-content:space-between; margin:0 0 18px; }}
    .filters {{ display:flex; gap:8px; flex-wrap:wrap; }}
    .filter {{ border:1px solid var(--line-strong); background:var(--surface); border-radius:7px; padding:9px 14px; font-size:13px; cursor:pointer; transition:.18s ease; }}
    .filter:hover {{ border-color:#9aa8bc; }}
    .filter.active {{ background:var(--navy); border-color:var(--navy); color:#fff; }}
    .search {{ width:min(360px,42vw); position:relative; }}
    .search input {{ width:100%; border:1px solid var(--line-strong); border-radius:7px; background:var(--surface); color:var(--ink); padding:10px 13px 10px 38px; outline:none; }}
    .search input:focus {{ border-color:var(--focus); box-shadow:0 0 0 3px rgba(47,111,237,.12); }}
    .search svg {{ position:absolute; left:12px; top:11px; width:17px; height:17px; color:var(--muted); }}
    .main {{ display:grid; grid-template-columns:minmax(0,1fr) 390px; gap:18px; align-items:start; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(205px,1fr)); gap:13px; }}
    .card {{ min-height:230px; text-align:left; border:1px solid var(--line); border-radius:var(--radius); background:var(--surface); padding:18px; cursor:pointer; transition:border-color .18s ease, transform .18s ease, box-shadow .18s ease; }}
    .card:hover {{ transform:translateY(-2px); border-color:#aeb9c9; box-shadow:0 7px 18px rgba(13,35,69,.07); }}
    .card.selected {{ border-color:var(--focus); box-shadow:0 0 0 2px rgba(47,111,237,.11); }}
    .card:focus-visible,.filter:focus-visible,.drawer-close:focus-visible {{ outline:3px solid rgba(47,111,237,.26); outline-offset:2px; }}
    .card-name {{ min-height:49px; }}
    .card-name strong {{ display:block; font-size:16px; line-height:1.3; }}
    .card-name span {{ display:block; margin-top:4px; color:var(--muted); font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .score {{ margin:14px 0 8px; font-size:29px; line-height:1; font-weight:770; letter-spacing:-.03em; }}
    .complete .score,.complete .status-dot {{ color:var(--green); }}
    .in-progress .score,.in-progress .status-dot {{ color:var(--amber); }}
    .not-started .score,.not-started .status-dot {{ color:var(--red); }}
    .unknown .score,.unknown .status-dot {{ color:var(--gray); }}
    .progress {{ height:6px; border-radius:99px; background:#e4e8ee; overflow:hidden; }}
    .progress > span {{ display:block; height:100%; border-radius:inherit; width:var(--progress); background:var(--amber); }}
    .complete .progress > span {{ background:var(--green); }}
    .not-started .progress > span {{ background:var(--red); }}
    .unknown .progress > span {{ background:var(--gray); }}
    .stage-labels,.stage-points {{ display:grid; grid-template-columns:repeat(5,1fr); }}
    .stage-labels {{ margin-top:13px; color:var(--muted); font-size:10px; text-align:center; }}
    .stage-points {{ position:relative; margin-top:7px; }}
    .stage-points::before {{ content:""; position:absolute; left:10%; right:10%; top:6px; height:1px; background:var(--line-strong); }}
    .point {{ width:13px; height:13px; border:2px solid var(--line-strong); border-radius:50%; background:var(--surface); justify-self:center; z-index:1; }}
    .point.done {{ border-color:currentColor; background:currentColor; }}
    .point.partial {{ border-color:currentColor; background:linear-gradient(90deg,currentColor 50%,var(--surface) 50%); }}
    .point.unknown-point {{ border-style:dashed; }}
    .card-status {{ display:flex; gap:7px; align-items:center; margin-top:18px; color:var(--muted); font-size:12px; }}
    .status-dot {{ width:7px; height:7px; border-radius:50%; background:currentColor; }}
    .drawer {{ position:sticky; top:18px; max-height:calc(100vh - 36px); overflow:auto; background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow); }}
    .drawer-head {{ padding:20px 22px 17px; border-bottom:1px solid var(--line); position:relative; }}
    .drawer-head h2 {{ margin:0 36px 5px 0; font-size:20px; line-height:1.25; }}
    .drawer-head .english {{ color:var(--muted); font-size:11px; }}
    .drawer-score {{ display:flex; align-items:center; gap:12px; margin-top:16px; }}
    .drawer-score strong {{ font-size:34px; letter-spacing:-.04em; }}
    .drawer-close {{ position:absolute; top:15px; right:15px; border:0; background:transparent; font-size:24px; cursor:pointer; color:var(--muted); }}
    .drawer-section {{ padding:18px 22px; border-bottom:1px solid var(--line); }}
    .drawer-section:last-child {{ border-bottom:0; }}
    .drawer-section h3 {{ margin:0 0 12px; font-size:14px; }}
    .drawer-section p {{ margin:0; color:#43516a; font-size:12px; line-height:1.75; }}
    .detail-stage {{ display:grid; grid-template-columns:54px 54px 1fr; gap:9px; align-items:start; padding:9px 0; border-top:1px solid #edf0f4; font-size:11px; }}
    .detail-stage:first-of-type {{ border-top:0; }}
    .detail-stage .stage-score {{ font-weight:750; }}
    .detail-stage .stage-status {{ color:var(--muted); word-break:break-word; }}
    .evidence-list,.limitation-list {{ margin:0; padding-left:17px; color:#43516a; font-size:11px; line-height:1.65; }}
    .evidence-list a {{ color:#245fc7; text-decoration:none; word-break:break-all; }}
    .evidence-list a:hover {{ text-decoration:underline; }}
    .next-action {{ padding:12px 14px; border-left:3px solid var(--focus); background:#f4f7fe; color:#203b6d; font-size:12px; line-height:1.65; }}
    .empty {{ grid-column:1/-1; padding:52px; border:1px dashed var(--line-strong); background:var(--surface); text-align:center; color:var(--muted); border-radius:var(--radius); }}
    .footer {{ margin-top:18px; color:var(--muted); font-size:11px; line-height:1.7; }}
    @media (max-width:1240px) {{ .grid {{ grid-template-columns:repeat(3,minmax(210px,1fr)); }} .main {{ grid-template-columns:minmax(0,1fr) 360px; }} }}
    @media (max-width:980px) {{ .main {{ display:block; }} .grid {{ grid-template-columns:repeat(2,minmax(230px,1fr)); }} .drawer {{ position:fixed; inset:5vh 4vw; max-height:90vh; z-index:10; display:none; }} .drawer.open {{ display:block; }} .drawer::before {{ content:""; position:fixed; inset:0; background:rgba(13,35,69,.28); z-index:-1; }} }}
    @media (max-width:680px) {{ .shell {{ padding:20px 15px 32px; }} .header {{ display:block; }} .header-meta {{ text-align:left; margin-top:10px; }} .summary {{ grid-template-columns:repeat(2,1fr); }} .summary-item:last-child {{ grid-column:1/-1; }} .summary-item:nth-child(3)::before,.summary-item:nth-child(5)::before {{ display:none; }} .toolbar {{ align-items:stretch; flex-direction:column; }} .search {{ width:100%; }} .grid {{ grid-template-columns:1fr; }} .card {{ min-height:214px; }} .drawer {{ inset:2vh 3vw; max-height:96vh; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="header">
      <div>
        <h1>能力拼图进度</h1>
        <div class="subtitle">每块能力都按规格、实现、验证、环境资格和激活证据计算；不是 AI 主观打分。</div>
      </div>
      <div class="header-meta"><strong>Toolkit <span id="toolkitVersion">{version}</span></strong><br>渲染时间：<span id="generatedAt">{generated}</span><br>事实快照：<span id="digest">{digest}</span></div>
    </header>

    <section class="summary" aria-label="进度汇总">
      <div class="summary-item complete"><span class="summary-value">100%</span><span class="summary-label">已完成</span><span class="summary-note"><b id="completeCount">{summary['complete']}</b> 项能力</span></div>
      <div class="summary-item in-progress"><span class="summary-value">进行中</span><span class="summary-note"><b id="progressCount">{summary['in_progress']}</b> 项能力</span></div>
      <div class="summary-item not-started"><span class="summary-value">0%</span><span class="summary-label">未开始</span><span class="summary-note"><b id="notStartedCount">{summary['not_started']}</b> 项能力</span></div>
      <div class="summary-item unknown"><span class="summary-value">未知</span><span class="summary-note"><b id="unknownCount">{summary['unknown']}</b> 项能力</span></div>
      <div class="summary-item"><span class="summary-value" id="averageScore">{average}</span><span class="summary-label">已知项均值</span><span class="summary-note">未知项不参与均值</span></div>
    </section>

    <div class="toolbar">
      <div class="filters" role="group" aria-label="状态筛选">
        <button class="filter active" data-filter="all">全部</button>
        <button class="filter" data-filter="complete">已完成</button>
        <button class="filter" data-filter="in-progress">进行中</button>
        <button class="filter" data-filter="not-started">未开始</button>
        <button class="filter" data-filter="unknown">未知</button>
      </div>
      <label class="search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-4-4"></path></svg>
        <input id="searchInput" type="search" placeholder="搜索能力名称或 ID" aria-label="搜索能力">
      </label>
    </div>

    <section class="main">
      <div class="grid" id="capabilityGrid" aria-live="polite">{initial_cards}</div>
      <aside class="drawer {html.escape(snapshot['capabilities'][0]['category']) if snapshot['capabilities'] else ''}" id="detailDrawer" aria-label="能力详情">{initial_drawer}</aside>
    </section>
    <footer class="footer">绿色仅表示五个证据轴全部完成；红色仅表示五轴均为 0。渲染成功不等于 Capability 已实现、已验证或已激活。</footer>
  </main>
  <script id="capabilityData" type="application/json">{encoded}</script>
  <script>
    const snapshot = JSON.parse(document.getElementById('capabilityData').textContent);
    let activeFilter = 'all';
    let query = '';
    let selectedId = snapshot.capabilities[0]?.id || null;

    const $ = (selector) => document.querySelector(selector);
    const escapeHtml = (value) => String(value).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
    const localTime = new Date(snapshot.generated_at).toLocaleString('zh-CN', {{hour12:false}});
    $('#toolkitVersion').textContent = snapshot.toolkit_version;
    $('#generatedAt').textContent = localTime;
    $('#digest').textContent = snapshot.source_digest.slice(0, 12);
    $('#completeCount').textContent = snapshot.summary.complete;
    $('#progressCount').textContent = snapshot.summary.in_progress;
    $('#notStartedCount').textContent = snapshot.summary.not_started;
    $('#unknownCount').textContent = snapshot.summary.unknown;
    $('#averageScore').textContent = snapshot.summary.average === null ? '—' : snapshot.summary.average + '%';

    function pointClass(stage) {{
      if (stage.score === null) return 'unknown-point';
      if (stage.score === 100) return 'done';
      if (stage.score > 0) return 'partial';
      return '';
    }}

    function cardHtml(item) {{
      const labels = item.stages.map(stage => `<span>${{escapeHtml(stage.label)}}</span>`).join('');
      const points = item.stages.map(stage => `<span class="point ${{pointClass(stage)}}" title="${{escapeHtml(stage.label + ': ' + stage.status)}}"></span>`).join('');
      return `<button class="card ${{item.category}} ${{selectedId === item.id ? 'selected' : ''}}" data-id="${{escapeHtml(item.id)}}" style="--progress:${{item.score}}%" aria-label="${{escapeHtml(item.name)}}，进度 ${{escapeHtml(item.score_display)}}">
        <span class="card-name"><strong>${{escapeHtml(item.name)}}</strong><span>${{escapeHtml(item.id)}}</span></span>
        <span class="score">${{escapeHtml(item.score_display)}}</span>
        <span class="progress"><span></span></span>
        <span class="stage-labels">${{labels}}</span>
        <span class="stage-points">${{points}}</span>
        <span class="card-status"><span class="status-dot"></span>${{escapeHtml(item.status_label)}}</span>
      </button>`;
    }}

    function filteredItems() {{
      return snapshot.capabilities.filter(item => {{
        const categoryMatch = activeFilter === 'all' || item.category === activeFilter;
        const text = `${{item.name}} ${{item.english_name}} ${{item.id}}`.toLowerCase();
        return categoryMatch && text.includes(query.toLowerCase());
      }});
    }}

    function renderGrid() {{
      const items = filteredItems();
      $('#capabilityGrid').innerHTML = items.length ? items.map(cardHtml).join('') : '<div class="empty">没有符合当前筛选条件的能力。</div>';
      document.querySelectorAll('.card').forEach(card => card.addEventListener('click', () => {{
        selectedId = card.dataset.id;
        renderGrid();
        renderDrawer(true);
      }}));
    }}

    function evidenceHref(ref) {{
      const path = ref.split('#')[0];
      return '../' + path.replace(/\\\\/g, '/');
    }}

    function renderDrawer(forceOpen = false) {{
      const item = snapshot.capabilities.find(cap => cap.id === selectedId);
      if (!item) return;
      const stageRows = item.stages.map(stage => {{
        const score = stage.score === null ? '未知' : stage.score + '%';
        const refs = stage.evidence.length ? `<ul class="evidence-list">${{stage.evidence.map(ref => `<li><a href="${{escapeHtml(evidenceHref(ref))}}">${{escapeHtml(ref)}}</a></li>`).join('')}}</ul>` : '<span class="stage-status">无可定位证据</span>';
        return `<div class="detail-stage"><strong>${{escapeHtml(stage.label)}}</strong><span class="stage-score">${{score}}</span><div><div class="stage-status">${{escapeHtml(stage.status)}} · 权重 ${{stage.weight}}%</div>${{refs}}</div></div>`;
      }}).join('');
      const limitations = item.limitations.map(text => `<li>${{escapeHtml(text)}}</li>`).join('');
      $('#detailDrawer').className = `drawer ${{item.category}}${{forceOpen ? ' open' : ''}}`;
      $('#detailDrawer').innerHTML = `<div class="drawer-head">
        <button class="drawer-close" aria-label="关闭详情">×</button>
        <h2>${{escapeHtml(item.name)}}</h2><div class="english">${{escapeHtml(item.english_name)}} · ${{escapeHtml(item.id)}}</div>
        <div class="drawer-score"><strong class="score">${{escapeHtml(item.score_display)}}</strong><span>${{escapeHtml(item.status_label)}}</span></div>
      </div>
      <div class="drawer-section"><h3>职责</h3><p>${{escapeHtml(item.purpose)}}</p></div>
      <div class="drawer-section"><h3>五轴得分与证据</h3>${{stageRows}}</div>
      <div class="drawer-section"><h3>当前局限</h3><ul class="limitation-list">${{limitations}}</ul></div>
      <div class="drawer-section"><h3>下一步</h3><div class="next-action">${{escapeHtml(item.next_action)}}</div></div>`;
      $('.drawer-close').addEventListener('click', () => $('#detailDrawer').classList.remove('open'));
    }}

    document.querySelectorAll('.filter').forEach(button => button.addEventListener('click', () => {{
      document.querySelectorAll('.filter').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      activeFilter = button.dataset.filter;
      renderGrid();
    }}));
    $('#searchInput').addEventListener('input', event => {{ query = event.target.value.trim(); renderGrid(); }});
    renderGrid();
    renderDrawer(false);
  </script>
</body>
</html>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT, help="HTML output path")
    args = parser.parse_args()
    output = args.output.resolve()
    snapshot = build_snapshot()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_document(snapshot), encoding="utf-8", newline="\n")
    summary = snapshot["summary"]
    print(f"Rendered {summary['total']} capabilities to {output}")
    print(
        "Summary: "
        f"complete={summary['complete']} "
        f"in_progress={summary['in_progress']} "
        f"not_started={summary['not_started']} "
        f"unknown={summary['unknown']}"
    )
    print("Render success does not validate or activate any capability.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

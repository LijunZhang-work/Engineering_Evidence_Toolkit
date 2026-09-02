#!/usr/bin/env python3
"""Render the evidence-bound desktop capability-maturity page.

The renderer reads the toolkit and capability manifests. It never asks a model
to estimate completion percentages. A successful render proves only that the
page was generated from parseable inputs; it does not validate or activate a
capability.
"""

from __future__ import annotations

import argparse
import copy
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
    {"key": "specification", "label": "规格"},
    {"key": "implementation", "label": "实现"},
    {"key": "validation", "label": "验证"},
    {"key": "qualification", "label": "资格"},
    {"key": "activation", "label": "激活"},
)

# Maturity is categorical. PARTIAL is deliberately not converted to “50%”,
# because evidence that something started does not prove half of the work is done.
STAGE_STATES = {
    "specification": {
        "MISSING": ("unknown", "缺少规格"),
        "DRAFT": ("partial", "草拟中"),
        "DESIGNED": ("complete", "完成"),
        "SPECIFIED": ("complete", "完成"),
        "REVIEWED": ("complete", "完成"),
        "BASELINED": ("complete", "完成"),
    },
    "implementation": {
        "NOT_IMPLEMENTED": ("idle", "未开始"),
        "NOT_STARTED": ("idle", "未开始"),
        "PARTIAL": ("partial", "部分"),
        "IMPLEMENTED": ("complete", "完成"),
    },
    "validation": {
        "NOT_RUN": ("idle", "未运行"),
        "NOT_VALIDATED": ("idle", "未验证"),
        "PARTIAL": ("partial", "部分"),
        "FAILED": ("failed", "失败"),
        "STALE": ("failed", "已失效"),
        "PASSED": ("complete", "通过"),
        "VALIDATED": ("complete", "通过"),
    },
    "qualification": {
        "NOT_ASSESSED": ("idle", "未评估"),
        "NOT_RUN": ("idle", "未评估"),
        "UNQUALIFIED": ("failed", "不合格"),
        "QUALIFIED_WITH_LIMITS": ("partial", "受限合格"),
        "QUALIFIED": ("complete", "合格"),
    },
    "activation": {
        "INACTIVE": ("idle", "未激活"),
        "ACTIVE_ON_DEMAND": ("partial", "按需启用"),
        "ACTIVE": ("complete", "已激活"),
        "SUSPENDED": ("failed", "已暂停"),
        "RETIRED": ("idle", "已退役"),
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


def stage_state(stage: str, status: str | None) -> tuple[str, str]:
    if status is None:
        return "unknown", "状态未知"
    return STAGE_STATES[stage].get(str(status).upper(), ("unknown", "状态未知"))


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


def classify_maturity(stage_results: list[dict[str, Any]]) -> tuple[str, str, int, list[str]]:
    unknown_stages = [item["key"] for item in stage_results if item["state_kind"] == "unknown"]
    completed_axes = sum(item["state_kind"] == "complete" for item in stage_results)
    if unknown_stages:
        return "unknown", "状态未知", completed_axes, unknown_stages
    if any(item["state_kind"] == "failed" for item in stage_results):
        return "blocked", "受阻", completed_axes, unknown_stages
    if completed_axes == len(stage_results):
        return "active", "已激活", completed_axes, unknown_stages
    by_key = {item["key"]: item for item in stage_results}
    downstream = [by_key[key]["state_kind"] for key in ("implementation", "validation", "qualification", "activation")]
    if by_key["specification"]["state_kind"] == "complete" and all(value == "idle" for value in downstream):
        return "designed", "仅完成设计", completed_axes, unknown_stages
    return "partial", "部分实现", completed_axes, unknown_stages


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
        "qualification": dimensions.get("qualification_status"),
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

    declared_evidence = manifest.get("status_evidence", {})
    if isinstance(declared_evidence, dict):
        for stage in ("implementation", "validation", "qualification", "activation"):
            refs = declared_evidence.get(stage, [])
            if isinstance(refs, list):
                evidence[stage].extend(
                    str(ref.get("path"))
                    for ref in refs
                    if isinstance(ref, dict) and isinstance(ref.get("path"), str) and ref.get("path")
                )

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
        state_kind, state_label = stage_state(key, status)
        stage_results.append(
            {
                "key": key,
                "label": definition["label"],
                "status": status or "UNKNOWN",
                "state_kind": state_kind,
                "state_label": state_label,
                "evidence": evidence[key],
            }
        )

    category, status_label, completed_axes, unknown_stages = classify_maturity(stage_results)

    incomplete = [item for item in stage_results if item["state_kind"] != "complete"]
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
        if item["state_kind"] == "unknown":
            limitations.append(f"{item['label']}状态缺少可定位证据")
        elif item["state_kind"] == "idle":
            limitations.append(f"{item['label']}尚未开始或未取得有效证据")
        elif item["state_kind"] == "failed":
            limitations.append(f"{item['label']}存在失败或失效状态：{item['status']}")
        elif item["state_kind"] == "partial":
            limitations.append(f"{item['label']}只有部分证据：{item['status']}")

    return {
        "id": capability_id,
        "name": CHINESE_NAMES.get(capability_id, str(manifest.get("name") or capability_id)),
        "english_name": str(manifest.get("name") or capability_id),
        "purpose": first_sentence(manifest.get("purpose")),
        "completed_axes": completed_axes,
        "category": category,
        "status_label": status_label,
        "unknown_stages": unknown_stages,
        "stages": stage_results,
        "limitations": limitations or ["当前五个证据轴均有完成证据"],
        "next_action": next_action,
        "manifest_path": str(manifest_path.relative_to(ROOT)),
    }


def data_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def capability_source_paths(entry: dict[str, Any]) -> list[Path]:
    """Return every file that can justify a capability card or its freshness."""

    capability_root = ROOT / str(entry["path"])
    manifest_path = capability_root / "CAPABILITY.yaml"
    manifest = load_yaml(manifest_path)
    paths = [manifest_path]
    spec_path = capability_root / str(manifest.get("spec") or "SPEC.md")
    if spec_path.is_file():
        paths.append(spec_path)
    status_evidence = manifest.get("status_evidence", {})
    if isinstance(status_evidence, dict):
        for refs in status_evidence.values():
            if not isinstance(refs, list):
                continue
            for ref in refs:
                if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
                    continue
                dependency = ROOT / ref["path"]
                if dependency.is_file():
                    paths.append(dependency)
                elif dependency.is_dir():
                    paths.extend(path for path in dependency.rglob("*") if path.is_file())
    return paths


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
        source_paths.extend(capability_source_paths(entry))

    summary = {
        "active": sum(item["category"] == "active" for item in capabilities),
        "partial": sum(item["category"] == "partial" for item in capabilities),
        "designed": sum(item["category"] == "designed" for item in capabilities),
        "blocked": sum(item["category"] == "blocked" for item in capabilities),
        "unknown": sum(item["category"] == "unknown" for item in capabilities),
        "total": len(capabilities),
    }

    metadata = toolkit.get("metadata", {})
    return {
        "toolkit_version": metadata.get("version", "UNKNOWN") if isinstance(metadata, dict) else "UNKNOWN",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_digest": data_digest(list(dict.fromkeys(source_paths))),
        "axes": [dict(item) for item in STAGES],
        "summary": summary,
        "capabilities": capabilities,
    }


def stable_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return the full comparable payload, excluding only render time."""

    result = copy.deepcopy(snapshot)
    result.pop("generated_at", None)
    return result


def snapshots_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return stable_snapshot(left) == stable_snapshot(right)


def maturity_row_html(item: dict[str, Any], selected: bool = False) -> str:
    cells = "".join(
        f'<td><span class="axis-state {html.escape(stage["state_kind"])}" title="{html.escape(stage["status"], quote=True)}">{html.escape(stage["state_label"])}</span></td>'
        for stage in item["stages"]
    )
    return (
        f'<tr class="maturity-row {html.escape(item["category"])}{" selected" if selected else ""}" data-id="{html.escape(item["id"], quote=True)}">'
        f'<td>{html.escape(item["name"])}<br><span class="section-note">{html.escape(item["id"])}</span></td>'
        f'{cells}<td><span class="maturity-label">{html.escape(item["status_label"])}</span></td></tr>'
    )


def maturity_detail_html(item: dict[str, Any]) -> str:
    axes = []
    for stage in item["stages"]:
        if stage["evidence"]:
            links = []
            for evidence_ref in stage["evidence"]:
                path = str(evidence_ref).split("#", 1)[0].replace("\\", "/")
                links.append(f'<li><a href="../{html.escape(path, quote=True)}">{html.escape(str(evidence_ref))}</a></li>')
            evidence = f'<ul class="evidence-list">{"".join(links)}</ul>'
        else:
            evidence = '<span class="section-note">无可定位证据</span>'
        axes.append(
            '<div class="detail-axis">'
            f'<strong>{html.escape(stage["label"])}</strong>'
            f'<span class="axis-state {html.escape(stage["state_kind"])}">{html.escape(stage["state_label"])}</span>'
            f'<div><span class="section-note">{html.escape(stage["status"])}</span>{evidence}</div></div>'
        )
    limitations = "".join(f'<li>{html.escape(text)}</li>' for text in item["limitations"])
    return (
        '<div class="detail-head"><button class="detail-close" aria-label="关闭详情">×</button>'
        f'<h2>{html.escape(item["name"])}</h2><p>{html.escape(item["english_name"])} · {html.escape(item["id"])}</p></div>'
        f'<div class="detail-section"><h3>当前成熟度</h3><p><strong>{html.escape(item["status_label"])}</strong> · {item["completed_axes"]}/5 个证据轴完成</p></div>'
        f'<div class="detail-section"><h3>职责</h3><p>{html.escape(item["purpose"])}</p></div>'
        f'<div class="detail-section"><h3>五个证据轴</h3>{"".join(axes)}</div>'
        f'<div class="detail-section"><h3>当前局限</h3><ul class="limitation-list">{limitations}</ul></div>'
        f'<div class="detail-section"><h3>下一步</h3><div class="next-action">{html.escape(item["next_action"])}</div></div>'
    )


def html_document(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    rows = "".join(maturity_row_html(item, selected=index == 0) for index, item in enumerate(snapshot["capabilities"]))
    detail = maturity_detail_html(snapshot["capabilities"][0]) if snapshot["capabilities"] else ""
    summary = snapshot["summary"]
    version = html.escape(str(snapshot["toolkit_version"]))
    generated = html.escape(snapshot["generated_at"])
    digest = html.escape(snapshot["source_digest"][:12])
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>能力成熟度 · Engineering Evidence Toolkit</title>
  <link rel="stylesheet" href="assets/console.css">
</head>
<body>
  <header class="app-header"><div class="app-header-inner">
    <a class="brand" href="workset-planner.html"><span class="brand-mark">E</span>工程取证工具集</a>
    <nav class="primary-nav" aria-label="主导航"><a href="workset-planner.html">工作集</a><a href="run-console.html">当前运行</a><a href="capability-progress.html" aria-current="page">能力成熟度</a></nav>
    <div class="header-meta">桌面控制台</div>
  </div></header>
  <main class="page-shell">
    <div class="page-heading"><div><h1>能力成熟度</h1><p>这是工具集长期建设状态，不是某次任务进度；部分状态不换算成虚假的完成百分比。</p></div><div class="fact-meta">Toolkit {version}<br>渲染时间 {generated}<br>事实快照 {digest}</div></div>
    <section class="maturity-summary" aria-label="成熟度汇总">
      <div><strong id="activeCount">{summary["active"]}</strong><span>已激活</span></div>
      <div><strong id="partialCount">{summary["partial"]}</strong><span>部分实现</span></div>
      <div><strong id="designedCount">{summary["designed"]}</strong><span>仅完成设计</span></div>
      <div><strong id="blockedCount">{summary["blocked"]}</strong><span>受阻</span></div>
      <div><strong id="unknownCount">{summary["unknown"]}</strong><span>状态未知</span></div>
    </section>
    <div class="maturity-toolbar"><div class="filter-row"><button class="filter-button selected" data-filter="all">全部</button><button class="filter-button" data-filter="active">已激活</button><button class="filter-button" data-filter="partial">部分实现</button><button class="filter-button" data-filter="designed">仅完成设计</button><button class="filter-button" data-filter="blocked">受阻</button><button class="filter-button" data-filter="unknown">未知</button></div><input class="maturity-search" id="maturitySearch" type="search" placeholder="搜索能力名称或 ID" aria-label="搜索能力"></div>
    <section class="maturity-layout" id="maturityLayout">
      <div class="maturity-table-wrap"><table class="maturity-table"><thead><tr><th>能力</th><th>规格</th><th>实现</th><th>验证</th><th>资格</th><th>激活</th><th>综合状态</th></tr></thead><tbody id="maturityRows">{rows}</tbody></table></div>
      <aside class="maturity-detail" id="maturityDetail" aria-label="能力详情">{detail}</aside>
    </section>
    <p class="footer-note">失败、失效和不合格是问题状态，不贡献正向进度。页面只呈现 Manifest 与证据，不替代实现、测试、资格或激活 Receipt。</p>
  </main>
  <script id="capabilityData" type="application/json">{encoded}</script>
  <script src="assets/maturity.js"></script>
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
        f"active={summary['active']} "
        f"partial={summary['partial']} "
        f"designed={summary['designed']} "
        f"blocked={summary['blocked']} "
        f"unknown={summary['unknown']}"
    )
    print("Render success does not validate or activate any capability.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

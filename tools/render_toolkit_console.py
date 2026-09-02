#!/usr/bin/env python3
"""Render the desktop workset planner and current-run console pages."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools import workset_control
    from tools.render_capability_dashboard import CHINESE_NAMES
except ModuleNotFoundError:  # direct execution from tools/
    import workset_control
    from render_capability_dashboard import CHINESE_NAMES


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


def source_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build_snapshot() -> dict[str, Any]:
    raw = workset_control.catalog_snapshot()
    registered = set(raw["registered_ids"])
    sources = [workset_control.CATALOG_PATH, ROOT / "TOOLKIT_MANIFEST.yaml", *workset_control.POLICY_PATHS.values()]
    worksets: list[dict[str, Any]] = []
    for item in raw["catalog"].get("worksets", []):
        selected: set[str] = set()
        capabilities = []
        for capability in item.get("capabilities", []):
            capability_id = str(capability["id"])
            if capability_id not in registered:
                raise ValueError(f"{item.get('id')} references unregistered capability {capability_id}")
            selected.add(capability_id)
            state = raw["capabilities"][capability_id]
            capabilities.append(
                {
                    "id": capability_id,
                    "name": CHINESE_NAMES.get(capability_id, capability_id),
                    "reason": str(capability["reason"]),
                    **state,
                }
            )
            manifest_entry = next(entry for entry in workset_control.load_mapping(ROOT / "TOOLKIT_MANIFEST.yaml")["capabilities"] if entry["id"] == capability_id)
            sources.append(ROOT / str(manifest_entry["path"]) / "CAPABILITY.yaml")
        worksets.append(
            {
                "id": str(item["id"]),
                "title": str(item["title"]),
                "summary": str(item["summary"]),
                "supported_operations": [str(value) for value in item["supported_operations"]],
                "default_operation": str(item["default_operation"]),
                "default_policy": str(item["default_policy"]),
                "default_budget_minutes": int(item["default_budget_minutes"]),
                "default_permission": str(item["default_permission"]),
                "conclusion_ceiling": dict(item["conclusion_ceiling"]),
                "capabilities": capabilities,
                "excluded_capabilities": [
                    {"id": capability_id, "reason": "不属于本次目标的最小能力闭包。"}
                    for capability_id in sorted(registered - selected)
                ],
                "steps": [
                    {"id": str(step["id"]), "title": str(step["title"]), "capability_ids": [str(value) for value in step["capability_ids"]]}
                    for step in item.get("steps", [])
                ],
            }
        )
    toolkit = workset_control.load_mapping(ROOT / "TOOLKIT_MANIFEST.yaml")
    return {
        "toolkit_version": str(toolkit.get("metadata", {}).get("version", "UNKNOWN")),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_digest": source_digest(sources),
        "policy_pins": {
            preset: {"ref": path.relative_to(ROOT).as_posix(), "digest": workset_control.file_content_id(path)}
            for preset, path in workset_control.POLICY_PATHS.items()
        },
        "worksets": worksets,
    }


def navigation(active: str) -> str:
    destinations = [
        ("worksets", "workset-planner.html", "工作集"),
        ("runs", "run-console.html", "当前运行"),
        ("maturity", "capability-progress.html", "能力成熟度"),
    ]
    links = "".join(
        f'<a href="{href}"{(" aria-current=\"page\"" if key == active else "")}>{label}</a>'
        for key, href, label in destinations
    )
    return (
        '<header class="app-header"><div class="app-header-inner">'
        '<a class="brand" href="workset-planner.html"><span class="brand-mark">E</span>工程取证工具集</a>'
        f'<nav class="primary-nav" aria-label="主导航">{links}</nav>'
        '<div class="header-meta">桌面控制台</div></div></header>'
    )


def document(*, title: str, active: str, body: str, script: str = "", data_id: str = "", data: Any = None) -> str:
    embedded = ""
    if data_id:
        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        embedded = f'<script id="{html.escape(data_id)}" type="application/json">{encoded}</script>'
    script_tag = f'<script src="assets/{html.escape(script)}"></script>' if script else ""
    tail = "".join(f"  {fragment}\n" for fragment in (embedded, script_tag) if fragment)
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{html.escape(title)} · Engineering Evidence Toolkit</title>
  <link rel="stylesheet" href="assets/console.css">
</head>
<body>
  {navigation(active)}
  {body}
{tail}</body>
</html>
'''


def workset_page(snapshot: dict[str, Any]) -> str:
    initial = snapshot["worksets"][0]
    goals = "".join(
        '<button class="goal-choice{}" data-goal="{}" aria-pressed="{}"><strong>{}</strong><span>{}</span></button>'.format(
            " selected" if index == 0 else "",
            html.escape(item["id"], quote=True),
            "true" if index == 0 else "false",
            html.escape(item["title"]),
            html.escape(item["summary"]),
        )
        for index, item in enumerate(snapshot["worksets"])
    )
    capability_rows = "".join(
        f'<tr><td>{html.escape(item["name"])}<br><span class="section-note">{html.escape(item["id"])}</span></td><td>{html.escape(item["reason"])}</td><td><span class="state-text build">需要建设</span><br><span class="section-note">{html.escape(item["implementation_status"])}</span></td></tr>'
        for item in initial["capabilities"]
    )
    excluded = "".join(
        f'<li><code>{html.escape(item["id"])}</code><span>{html.escape(item["reason"])}</span></li>'
        for item in initial["excluded_capabilities"][:4]
    )
    body = f'''<main class="page-shell">
    <div class="page-heading"><div><h1>选择本次工作集</h1><p>先确定目标，再只展开完成目标所需的最小能力集。</p></div><div class="fact-meta">Toolkit {html.escape(snapshot["toolkit_version"])}<br>计划源 {html.escape(snapshot["source_digest"][:12])}</div></div>
    <section class="planner-layout" aria-label="工作集规划器">
      <aside class="goal-panel"><h2 class="panel-title">我要做什么</h2><p class="panel-help">选择目标不会自动加载全部能力。</p><div class="goal-list">{goals}</div></aside>
      <section class="plan-panel">
        <div class="plan-header"><h2 id="planTitle">{html.escape(initial["title"])}计划预览</h2><p id="planSummary">{html.escape(initial["summary"])}</p></div>
        <div class="plan-section"><div class="section-row"><h3>纳入的最小能力集（<span id="includedCount">{len(initial["capabilities"])}</span>）</h3><span class="section-note">每项都说明纳入理由</span></div><table class="capability-table"><thead><tr><th>能力</th><th>为什么需要</th><th>本次处理</th></tr></thead><tbody id="capabilityRows">{capability_rows}</tbody></table></div>
        <div class="plan-section"><div class="section-row"><h3>明确排除</h3><span class="section-note">不会因“持续推进”自动扩展</span></div><ul class="excluded-list" id="excludedList">{excluded}</ul></div>
        <div class="plan-section"><div class="section-row"><h3>输出边界</h3><span class="state-text" id="ceilingText">NO_VERDICT</span></div><p class="panel-help" id="operationMeaning">只补齐这个工作集缺失的能力，不横向建设全部工具集。</p></div>
      </section>
      <aside class="control-panel">
        <div class="control-group"><label class="group-label">这次怎么做</label><div class="segmented"><button data-operation="USE_AVAILABLE">现在使用</button><button class="selected" data-operation="BUILD_MISSING">优先建设</button></div><p class="control-explain">使用与建设是两种任务，不能混在一起。</p></div>
        <div class="control-group"><label class="group-label">保障档位</label><div class="segmented three"><button data-policy="QUICK">快速</button><button class="selected" data-policy="BALANCED">平衡</button><button data-policy="STRICT">严格</button></div><p class="control-explain">这是执行计划要求；接入 Runner 前不会冒充已启用门禁。</p></div>
        <div class="control-group"><label class="group-label" for="budgetInput">时间预算</label><div class="budget-row"><input id="budgetInput" type="number" min="5" max="1440" value="{initial["default_budget_minutes"]}"><span class="budget-unit">分钟</span></div><p class="control-explain">这是计划约束；接入 Runner 后才会按时触发检查点，当前控制面不会冒充自动计时。</p></div>
        <div class="control-group"><label class="group-label">权限</label><div class="segmented three"><button data-permission="READ_ONLY">只读</button><button class="selected" data-permission="TOOLKIT_ONLY">仅工具集</button><button data-permission="REQUEST_SCOPED_BUSINESS_EDIT">申请业务修改</button></div><p class="control-explain" id="permissionMeaning">只允许修改本工具集，不授权修改业务仓。</p></div>
        <div class="control-group"><label class="group-label" for="userNote">补充说明（可选）</label><textarea class="note-input" id="userNote" placeholder="例如：先把 C++ 代码审查闭环跑通"></textarea></div>
        <button class="primary-action" id="submitRequest">提交给 AI</button>
        <div class="honesty-note">提交只创建机器可读请求。AI 接单、执行和证据状态会在“当前运行”单独显示。</div>
        <div class="submit-result" id="submitResult"><strong id="resultTitle"></strong><p id="resultText"></p><div class="result-actions"><button id="copyResult">复制给 AI</button><button id="downloadResult">下载 JSON</button><a href="run-console.html">查看当前运行</a></div></div>
      </aside>
    </section>
  </main>'''
    return document(title="工作集", active="worksets", body=body, script="worksets.js", data_id="worksetData", data=snapshot)


def run_page(snapshot: dict[str, Any]) -> str:
    body = f'''<main class="page-shell">
    <div class="page-heading"><div><h1>当前运行</h1><p>这里只显示本次请求、实际步骤和人机活动，不混入能力成熟度。</p></div><div class="fact-meta">Toolkit {html.escape(snapshot["toolkit_version"])}<br>连接本地服务时每 2.5 秒刷新</div></div>
    <div class="run-layout" id="runRoot"><section class="run-main empty-state"><h2>正在读取运行状态</h2><p>如果没有请求，会引导你先选择工作集。</p></section></div>
    <p class="footer-note">运行页面没有最终 Verdict 权限；完成状态必须引用真实检查点或证据。</p>
  </main>'''
    return document(title="当前运行", active="runs", body=body, script="run-console.js")


def render(output_dir: Path) -> dict[str, Path]:
    snapshot = build_snapshot()
    output_dir.mkdir(parents=True, exist_ok=True)
    worksets = output_dir / "workset-planner.html"
    index = output_dir / "index.html"
    runs = output_dir / "run-console.html"
    workset_html = workset_page(snapshot)
    worksets.write_text(workset_html, encoding="utf-8", newline="\n")
    index.write_text(workset_html, encoding="utf-8", newline="\n")
    runs.write_text(run_page(snapshot), encoding="utf-8", newline="\n")
    return {"index": index, "worksets": worksets, "runs": runs}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DASHBOARD)
    args = parser.parse_args()
    outputs = render(args.output_dir.resolve())
    print("Rendered desktop console pages:")
    for name, path in outputs.items():
        print(f"- {name}: {path}")
    print("The pages record intent and execution visibility; they do not create engineering evidence or Verdicts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

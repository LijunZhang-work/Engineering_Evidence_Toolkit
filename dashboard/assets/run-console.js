(() => {
  const root = document.getElementById("runRoot");
  if (!root) return;
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[character]);
  const stateLabels = {REQUESTED:"尚未接单", CLAIMED:"AI 已接单", RUNNING:"执行中", WAITING_HUMAN:"等待用户", BLOCKED:"受阻", COMPLETED:"步骤执行完成", FAILED:"执行失败", CANCELLED:"未完整执行", NO_ACTION:"无需建设", PENDING:"等待", SKIPPED:"跳过"};
  let currentSubmission = null;

  function formatTime(value) {
    if (!value) return "—";
    return new Date(value).toLocaleString("zh-CN", {hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit"});
  }

  function draftRun(request) {
    return {
      __view_mode: "STATIC_DRAFT",
      request_id: request.request_id,
      run_id: "尚未创建",
      goal: request.goal,
      execution_status: "REQUESTED",
      started_at: request.created_at,
      updated_at: request.created_at,
      policy: request.assurance_preset,
      assurance_policy_ref: request.assurance_policy_ref,
      assurance_policy_digest: request.assurance_policy_digest,
      operation: request.operation,
      permission: request.permission,
      time_budget_minutes: request.time_budget_minutes,
      current_step_id: request.steps[0]?.id || null,
      steps: request.steps.map((step) => ({...step, why: "该步骤属于用户选择的最小工作集。", done_when: "AI 接单后形成真实检查点或证据引用。", evidence_refs: []})),
      activity: [{at: request.created_at, actor: "HUMAN", message: "用户提交工作集；尚无步骤执行证据。"}],
      blockers: [],
      omissions: [],
      conclusion_ceiling: request.conclusion_ceiling,
    };
  }

  function renderEmpty() {
    root.innerHTML = `<section class="run-main empty-state"><h2>还没有运行请求</h2><p>先到“工作集”选择目标、保障档位、时间和权限。只有提交后，这里才会出现真实请求。</p><a href="workset-planner.html">选择工作集</a></section>`;
  }

  function render(run) {
    const viewMode = run.__view_mode || "LIVE";
    const trustBanner = viewMode === "STATIC_DRAFT"
      ? `<div class="view-mode warning"><strong>本地未验证草稿</strong><span>尚未写入 Runtime，也没有被 AI 接单；这里只预览你准备提交的计划。</span></div>`
      : viewMode === "DISCONNECTED_CACHE"
        ? `<div class="view-mode danger"><strong>服务未连接</strong><span>下面是浏览器缓存草稿，不是当前真实运行。</span></div>`
        : `<div class="view-mode live"><strong>本地实时状态</strong><span>数据来自仓外 Runtime；它是协调记录，不是工程 Verdict。</span></div>`;
    const current = run.steps.find((step) => step.id === run.current_step_id) || run.steps.find((step) => step.status === "RUNNING") || run.steps.find((step) => step.status === "PENDING");
    const steps = run.steps.length ? run.steps.map((step, index) => `<li class="step-row ${escapeHtml(step.status.toLowerCase())}">
      <span class="step-index">${index + 1}</span>
      <div><div class="step-name">${escapeHtml(step.title)}</div><span class="section-note">${escapeHtml(step.capability_ids.join(" · "))}</span>${step.evidence_refs?.length ? `<div class="step-evidence">凭据：${step.evidence_refs.map(escapeHtml).join(" · ")}</div>` : `<div class="step-evidence empty">尚无凭据</div>`}</div>
      <div class="step-why">${escapeHtml(step.why || "等待 AI 写入该步骤的目的和完成条件。")}</div>
      <div class="step-status state-text ${escapeHtml(step.status.toLowerCase())}">${escapeHtml(stateLabels[step.status] || step.status)}</div>
    </li>`).join("") : `<li class="no-step">当前操作没有可执行步骤；请查看右侧遗漏项和阻塞原因。</li>`;
    const activity = (run.activity || []).slice().reverse().map((item) => `<li><time>${escapeHtml(formatTime(item.at).split(" ").pop())}</time><strong>${escapeHtml(item.actor === "HUMAN" ? "用户" : item.actor === "AI" ? "AI" : "系统")}</strong><span>${escapeHtml(item.message)}</span></li>`).join("");
    const blockerText = run.blockers?.length ? run.blockers.join("；") : "无已登记阻塞";
    const omissions = run.omissions?.length ? run.omissions.map((item) => `<li><code>${escapeHtml(item.id)}</code><span>${escapeHtml(item.disposition)}</span></li>`).join("") : `<li><span>无</span></li>`;
    root.innerHTML = `<section class="run-main">${trustBanner}
      <div class="run-title-row"><div><h2>${escapeHtml(run.goal.title)}</h2><div class="run-id">${escapeHtml(run.run_id)} · ${escapeHtml(run.request_id)}</div><div class="run-facts"><span>保障档位 <strong>${escapeHtml(run.policy)}</strong></span><span>权限 <strong>${escapeHtml(run.permission)}</strong></span><span>预算 <strong>${escapeHtml(run.time_budget_minutes)} 分钟</strong></span></div></div><div class="run-status">${escapeHtml(stateLabels[run.execution_status] || run.execution_status)}</div></div>
      <div class="current-action"><h3>${current ? "当前步骤" : "本次运行已结束"}</h3><div class="action-grid"><div><small>正在做什么</small><p>${escapeHtml(current?.title || stateLabels[run.execution_status] || run.execution_status)}</p></div><div><small>为什么做</small><p>${escapeHtml(current?.why || "所有计划步骤已有终态。")}</p></div><div><small>完成条件</small><p>${escapeHtml(current?.done_when || "以最终运行记录和证据引用为准。")}</p></div></div></div>
      <h3 class="panel-title">执行步骤</h3><ol class="step-list">${steps}</ol>
      <div class="plan-section"><div class="section-row"><h3>人机活动</h3><span class="section-note">最近更新 ${escapeHtml(formatTime(run.updated_at))}</span></div><ul class="activity-list">${activity}</ul></div>
    </section>
    <aside class="run-rail"><div class="rail-section"><h3>运行边界</h3><div class="rail-kv"><span>本次操作</span><strong>${escapeHtml(run.operation || "未记录")}</strong></div><div class="rail-kv"><span>策略固定</span><strong>${escapeHtml(run.assurance_policy_ref || "静态草稿")}</strong></div><div class="rail-kv"><span>结论上限</span><strong>${escapeHtml(run.conclusion_ceiling)}</strong></div><div class="rail-kv"><span>运行状态</span><strong>${escapeHtml(stateLabels[run.execution_status] || run.execution_status)}</strong></div><div class="rail-kv"><span>阻塞</span><strong>${escapeHtml(blockerText)}</strong></div></div><div class="rail-section"><h3>未调度能力</h3><ul class="omission-list">${omissions}</ul></div><div class="rail-section"><h3>与 AI 交互</h3><p class="panel-help">复制的是本次工作集和边界，不会把等待状态包装成完成。</p><button class="primary-action" id="copyInstruction">复制给 AI</button></div><div class="honesty-note">“步骤执行完成”不等于验证通过。工程结论仍必须来自可解析的 Receipt、Evidence、Gate 和对应 Profile。</div></aside>`;
    $("#copyInstruction")?.addEventListener("click", async () => {
      const text = currentSubmission?.ai_instruction || `请读取工作集 request_id=${run.request_id}，只按已冻结的最小能力集继续，并将真实步骤状态写回运行控制面。`;
      await navigator.clipboard.writeText(text);
      $("#copyInstruction").textContent = "已复制";
    });
  }

  async function load() {
    let value = null;
    let serverState = "NOT_ATTEMPTED";
    if (location.protocol === "http:" || location.protocol === "https:") {
      try {
        const response = await fetch("/api/visible/latest", {cache: "no-store"});
        if (response.ok) {
          serverState = "CONNECTED";
          const candidate = await response.json();
          if (candidate.kind === "WorksetRunState") value = {...candidate, __view_mode: "LIVE"};
          if (candidate.kind === "WorksetRequest") value = {...draftRun(candidate), __view_mode: "LIVE"};
        }
      } catch (_) { serverState = "DISCONNECTED"; }
    }
    if (!value && serverState !== "CONNECTED") {
      try {
        currentSubmission = JSON.parse(localStorage.getItem("eet_last_submission"));
        if (currentSubmission?.request) value = {...draftRun(currentSubmission.request), __view_mode: serverState === "DISCONNECTED" ? "DISCONNECTED_CACHE" : "STATIC_DRAFT"};
      } catch (_) { currentSubmission = null; }
    }
    if (value) render(value); else renderEmpty();
  }

  load();
  if (location.protocol === "http:" || location.protocol === "https:") window.setInterval(load, 2500);
})();

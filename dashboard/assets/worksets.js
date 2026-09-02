(() => {
  const dataNode = document.getElementById("worksetData");
  if (!dataNode) return;
  const snapshot = JSON.parse(dataNode.textContent);
  let selectedId = snapshot.worksets[0]?.id || null;
  let operation = snapshot.worksets[0]?.default_operation || "USE_AVAILABLE";
  let policy = snapshot.worksets[0]?.default_policy || "BALANCED";
  let permission = snapshot.worksets[0]?.default_permission || "READ_ONLY";
  let lastSubmission = null;

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[character]);
  const labels = {
    USE_AVAILABLE: "现在使用",
    BUILD_MISSING: "优先建设",
    QUICK: "快速",
    BALANCED: "平衡",
    STRICT: "严格",
    READ_ONLY: "只读",
    TOOLKIT_ONLY: "仅修改工具集",
    REQUEST_SCOPED_BUSINESS_EDIT: "申请受控业务修改",
    RUN: "可运行",
    RUN_LIMITED: "受限可运行",
    REUSE: "可复用",
    BUILD_OR_COMPLETE: "需要建设",
    UNAVAILABLE: "尚不可用",
    PARTIAL: "部分实现",
    IMPLEMENTED: "已实现",
    NOT_IMPLEMENTED: "未实现",
    UNKNOWN: "状态未知",
  };

  function selectedWorkset() {
    return snapshot.worksets.find((item) => item.id === selectedId);
  }

  function dispositionFor(capability) {
    if (operation === "BUILD_MISSING") {
      return capability.implementation_status === "IMPLEMENTED" && capability.validation_status === "PASSED"
        ? "REUSE" : "BUILD_OR_COMPLETE";
    }
    if (capability.implementation_status === "IMPLEMENTED" && capability.validation_status === "PASSED") return "RUN";
    if (["PARTIAL", "IMPLEMENTED"].includes(capability.implementation_status) && capability.validation_status === "PARTIAL") return "RUN_LIMITED";
    return "UNAVAILABLE";
  }

  function stateClass(value) {
    return ({RUN:"run", RUN_LIMITED:"partial", REUSE:"reuse", BUILD_OR_COMPLETE:"build", UNAVAILABLE:"unavailable"})[value] || "";
  }

  function syncOperationAndPermission(workset) {
    if (!workset.supported_operations.includes(operation)) operation = workset.default_operation;
    if (operation === "BUILD_MISSING") permission = "TOOLKIT_ONLY";
    if (operation === "USE_AVAILABLE" && permission === "TOOLKIT_ONLY") permission = "READ_ONLY";
    if (selectedId !== "safe-ai-edit" && permission === "REQUEST_SCOPED_BUSINESS_EDIT") permission = "READ_ONLY";
  }

  function renderGoals() {
    $$(".goal-choice").forEach((button) => {
      const isSelected = button.dataset.goal === selectedId;
      button.classList.toggle("selected", isSelected);
      button.setAttribute("aria-pressed", String(isSelected));
    });
  }

  function renderPlan() {
    const workset = selectedWorkset();
    if (!workset) return;
    syncOperationAndPermission(workset);
    $("#planTitle").textContent = `${workset.title}计划预览`;
    $("#planSummary").textContent = workset.summary;
    $("#includedCount").textContent = String(workset.capabilities.length);
    $("#capabilityRows").innerHTML = workset.capabilities.map((capability) => {
      const disposition = dispositionFor(capability);
      return `<tr>
        <td>${escapeHtml(capability.name)}<br><span class="section-note">${escapeHtml(capability.id)}</span></td>
        <td>${escapeHtml(capability.reason)}</td>
        <td><span class="state-text ${stateClass(disposition)}">${escapeHtml(labels[disposition] || disposition)}</span><br><span class="section-note">${escapeHtml(labels[capability.implementation_status] || capability.implementation_status)}</span></td>
      </tr>`;
    }).join("");
    const previewExcluded = workset.excluded_capabilities.slice(0, 4);
    $("#excludedList").innerHTML = previewExcluded.map((item) => `<li><code>${escapeHtml(item.id)}</code><span>${escapeHtml(item.reason)}</span></li>`).join("") +
      (workset.excluded_capabilities.length > previewExcluded.length ? `<li><code>另 ${workset.excluded_capabilities.length - previewExcluded.length} 项</code><span>保持排除，不因“持续推进”自动扩展。</span></li>` : "");
    const unavailable = workset.capabilities.filter((capability) => dispositionFor(capability) === "UNAVAILABLE").length;
    const limited = workset.capabilities.filter((capability) => dispositionFor(capability) === "RUN_LIMITED").length;
    $("#ceilingText").textContent = operation === "BUILD_MISSING" || unavailable ? "NO_VERDICT" : (policy === "QUICK" || limited ? "HINTS_ONLY" : workset.conclusion_ceiling.USE_AVAILABLE);
    $("#operationMeaning").textContent = operation === "BUILD_MISSING"
      ? "只补齐这个工作集缺失的能力，不横向建设全部工具集。"
      : unavailable ? `当前有 ${unavailable} 项能力尚不可用，运行会诚实降级。` : limited ? `当前有 ${limited} 项只能受限运行，最多提供线索。` : "调用现有能力，不改变工具集实现状态。";
    renderControls();
  }

  function renderControls() {
    const workset = selectedWorkset();
    $$("[data-operation]").forEach((button) => {
      const value = button.dataset.operation;
      button.disabled = !workset.supported_operations.includes(value);
      button.classList.toggle("selected", value === operation);
      button.setAttribute("aria-pressed", String(value === operation));
    });
    $$("[data-policy]").forEach((button) => {
      button.classList.toggle("selected", button.dataset.policy === policy);
      button.setAttribute("aria-pressed", String(button.dataset.policy === policy));
    });
    $$("[data-permission]").forEach((button) => {
      const value = button.dataset.permission;
      const allowed = operation === "BUILD_MISSING" ? value === "TOOLKIT_ONLY" : value !== "TOOLKIT_ONLY" && (value !== "REQUEST_SCOPED_BUSINESS_EDIT" || selectedId === "safe-ai-edit");
      button.disabled = !allowed;
      button.classList.toggle("selected", value === permission);
      button.setAttribute("aria-pressed", String(value === permission));
    });
    $("#permissionMeaning").textContent = permission === "READ_ONLY" ? "AI 只能读取目标内容。" : permission === "TOOLKIT_ONLY" ? "只允许修改本工具集，不授权修改业务仓。" : "这里只提交修改意图；冻结路径和基线并取得正式授权前不得修改。";
  }

  function localRequest(payload) {
    const workset = selectedWorkset();
    const requestId = `wsr_${Array.from(crypto.getRandomValues(new Uint8Array(12))).map((value) => value.toString(16).padStart(2, "0")).join("")}`;
    const capabilities = workset.capabilities.map((capability) => ({
      id: capability.id,
      reason: capability.reason,
      implementation_status: capability.implementation_status,
      disposition: dispositionFor(capability),
    }));
    const unavailable = capabilities.some((item) => item.disposition === "UNAVAILABLE");
    const limited = capabilities.some((item) => item.disposition === "RUN_LIMITED");
    const executable = operation === "USE_AVAILABLE" ? new Set(["RUN", "RUN_LIMITED"]) : new Set(["BUILD_OR_COMPLETE"]);
    const steps = workset.steps.flatMap((step) => {
      const capabilityIds = step.capability_ids.filter((id) => executable.has(capabilities.find((item) => item.id === id)?.disposition));
      if (!capabilityIds.length) return [];
      const limited = capabilityIds.length !== step.capability_ids.length;
      const title = operation === "BUILD_MISSING" ? `建设或补齐：${step.title}` : limited ? `受限执行：${step.title}` : step.title;
      return [{...step, title, capability_ids: capabilityIds, status: "PENDING"}];
    });
    return {
      schema_version: "1.0.0",
      kind: "WorksetRequestDraft",
      validation_status: "UNVALIDATED_STATIC_DRAFT",
      request_id: requestId,
      created_at: new Date().toISOString(),
      source: "DESKTOP_CONSOLE",
      goal: {id: workset.id, title: workset.title, summary: workset.summary},
      ...payload,
      assurance_policy_ref: snapshot.policy_pins[policy].ref,
      assurance_policy_digest: snapshot.policy_pins[policy].digest,
      selected_capabilities: capabilities,
      excluded_capabilities: workset.excluded_capabilities,
      steps,
      conclusion_ceiling: operation === "BUILD_MISSING" || unavailable ? "NO_VERDICT" : (policy === "QUICK" || limited ? "HINTS_ONLY" : workset.conclusion_ceiling.USE_AVAILABLE),
      execution_status: "REQUESTED",
    };
  }

  function instructionFor(request, requestPath = "") {
    const selected = request.selected_capabilities.map((item) => item.id).join("、");
    const ref = requestPath || `request_id=${request.request_id}`;
    const authorization = request.permission === "REQUEST_SCOPED_BUSINESS_EDIT" ? "此字段只是修改申请，不构成业务源码授权；取得 typed MutationAuthorization 前不得修改。" : "";
    const base = `请从本工作区的 00_START_HERE.md 开始，读取工作集请求 ${ref}。本次目标是“${request.goal.title}”，操作为 ${request.operation}，保障档位 ${request.assurance_preset}，时间预算 ${request.time_budget_minutes} 分钟，权限 ${request.permission}。只处理最小能力集：${selected}。不得自行扩大到全部能力；每一步把真实状态写回工作集运行状态，缺证据不得报完成。${authorization}`;
    return requestPath ? base : `${base}\n\n以下是未进入运行时的静态请求草稿，请先验证并持久化：\n${JSON.stringify(request, null, 2)}`;
  }

  async function copyText(value) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch (_) {
      const area = document.createElement("textarea");
      area.value = value;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      const copied = document.execCommand("copy");
      area.remove();
      return copied;
    }
  }

  function downloadRequest() {
    if (!lastSubmission) return;
    const blob = new Blob([JSON.stringify(lastSubmission.request, null, 2) + "\n"], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${lastSubmission.request.request_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function submitRequest() {
    const button = $("#submitRequest");
    button.disabled = true;
    button.textContent = "正在生成请求";
    const payload = {
      goal_id: selectedId,
      operation,
      policy,
      time_budget_minutes: Number($("#budgetInput").value),
      permission,
      user_note: $("#userNote").value.trim(),
    };
    try {
      let submission;
      if (location.protocol === "http:" || location.protocol === "https:") {
        const response = await fetch("/api/requests", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
        if (!response.ok) throw new Error((await response.json()).error || "提交失败");
        submission = await response.json();
      } else {
        const request = localRequest({operation, assurance_preset: policy, time_budget_minutes: payload.time_budget_minutes, permission, user_note: payload.user_note});
        submission = {request, request_path: "", ai_instruction: instructionFor(request)};
      }
      lastSubmission = submission;
      localStorage.setItem("eet_last_submission", JSON.stringify(submission));
      const copied = await copyText(submission.ai_instruction);
      $("#resultTitle").textContent = submission.request_path ? "请求已提交，等待 AI 接单" : "请求草稿已生成";
      $("#resultText").textContent = copied ? "给 AI 的指令已复制。当前运行页会显示等待状态，不会把请求冒充成已执行。" : "请下载请求或手动复制给 AI。";
      $("#submitResult").classList.add("visible");
      $("#copyResult").textContent = copied ? "再次复制" : "复制给 AI";
    } catch (error) {
      $("#resultTitle").textContent = "请求未提交";
      $("#resultText").textContent = error.message;
      $("#submitResult").classList.add("visible");
    } finally {
      button.disabled = false;
      button.textContent = "提交给 AI";
    }
  }

  $$(".goal-choice").forEach((button) => button.addEventListener("click", () => {
    selectedId = button.dataset.goal;
    const workset = selectedWorkset();
    operation = workset.default_operation;
    policy = workset.default_policy;
    permission = workset.default_permission;
    $("#budgetInput").value = workset.default_budget_minutes;
    $("#submitResult").classList.remove("visible");
    renderGoals();
    renderPlan();
  }));
  $$("[data-operation]").forEach((button) => button.addEventListener("click", () => { operation = button.dataset.operation; renderPlan(); }));
  $$("[data-policy]").forEach((button) => button.addEventListener("click", () => { policy = button.dataset.policy; renderPlan(); }));
  $$("[data-permission]").forEach((button) => button.addEventListener("click", () => { permission = button.dataset.permission; renderControls(); }));
  $("#submitRequest").addEventListener("click", submitRequest);
  $("#downloadResult").addEventListener("click", downloadRequest);
  $("#copyResult").addEventListener("click", async () => { if (lastSubmission) await copyText(lastSubmission.ai_instruction); });

  renderGoals();
  renderPlan();
})();

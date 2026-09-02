(() => {
  const node = document.getElementById("capabilityData");
  if (!node) return;
  const snapshot = JSON.parse(node.textContent);
  let filter = "all";
  let query = "";
  let selectedId = snapshot.capabilities[0]?.id || null;
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[character]);

  function evidenceHref(reference) {
    return "../" + reference.split("#", 1)[0].replace(/\\/g, "/");
  }

  function rowHtml(item) {
    const axes = item.stages.map((stage) => `<td><span class="axis-state ${escapeHtml(stage.state_kind)}" title="${escapeHtml(stage.status)}">${escapeHtml(stage.state_label)}</span></td>`).join("");
    return `<tr class="maturity-row ${escapeHtml(item.category)}${item.id === selectedId ? " selected" : ""}" data-id="${escapeHtml(item.id)}"><td>${escapeHtml(item.name)}<br><span class="section-note">${escapeHtml(item.id)}</span></td>${axes}<td><span class="maturity-label">${escapeHtml(item.status_label)}</span></td></tr>`;
  }

  function filtered() {
    return snapshot.capabilities.filter((item) => {
      const categoryMatch = filter === "all" || item.category === filter;
      const text = `${item.name} ${item.english_name} ${item.id}`.toLowerCase();
      return categoryMatch && text.includes(query.toLowerCase());
    });
  }

  function renderRows() {
    const items = filtered();
    $("#maturityRows").innerHTML = items.length ? items.map(rowHtml).join("") : '<tr><td colspan="7" class="empty-state">没有符合条件的能力。</td></tr>';
    $$(".maturity-row").forEach((row) => row.addEventListener("click", () => {
      selectedId = row.dataset.id;
      renderRows();
      renderDetail();
    }));
  }

  function renderDetail() {
    const item = snapshot.capabilities.find((capability) => capability.id === selectedId);
    if (!item) return;
    const axes = item.stages.map((stage) => {
      const evidence = stage.evidence.length
        ? `<ul class="evidence-list">${stage.evidence.map((reference) => `<li><a href="${escapeHtml(evidenceHref(reference))}">${escapeHtml(reference)}</a></li>`).join("")}</ul>`
        : '<span class="section-note">无可定位证据</span>';
      return `<div class="detail-axis"><strong>${escapeHtml(stage.label)}</strong><span class="axis-state ${escapeHtml(stage.state_kind)}">${escapeHtml(stage.state_label)}</span><div><span class="section-note">${escapeHtml(stage.status)}</span>${evidence}</div></div>`;
    }).join("");
    const limitations = item.limitations.map((text) => `<li>${escapeHtml(text)}</li>`).join("");
    const detail = $("#maturityDetail");
    detail.classList.remove("closed");
    detail.innerHTML = `<div class="detail-head"><button class="detail-close" aria-label="关闭详情">×</button><h2>${escapeHtml(item.name)}</h2><p>${escapeHtml(item.english_name)} · ${escapeHtml(item.id)}</p></div><div class="detail-section"><h3>当前成熟度</h3><p><strong>${escapeHtml(item.status_label)}</strong> · ${escapeHtml(item.completed_axes)}/5 个证据轴完成</p></div><div class="detail-section"><h3>职责</h3><p>${escapeHtml(item.purpose)}</p></div><div class="detail-section"><h3>五个证据轴</h3>${axes}</div><div class="detail-section"><h3>当前局限</h3><ul class="limitation-list">${limitations}</ul></div><div class="detail-section"><h3>下一步</h3><div class="next-action">${escapeHtml(item.next_action)}</div></div>`;
    $(".detail-close").addEventListener("click", () => detail.classList.add("closed"));
  }

  $$(".filter-button").forEach((button) => button.addEventListener("click", () => {
    $$(".filter-button").forEach((item) => item.classList.remove("selected"));
    button.classList.add("selected");
    filter = button.dataset.filter;
    renderRows();
  }));
  $("#maturitySearch").addEventListener("input", (event) => { query = event.target.value.trim(); renderRows(); });
  renderRows();
  renderDetail();
})();

"use strict";

(function () {
  const $ = (sel) => document.querySelector(sel);
  const proposalSelect = $("#lr-proposal-select");
  const versionBadge = $("#lr-version-badge");
  const statusEl = $("#lr-status");
  const metaEl = $("#lr-meta");
  const hypothesesEl = $("#lr-hypotheses");
  const patchesEl = $("#lr-patches");
  const withheldBody = $("#lr-withheld-body");
  const lexiconContentEl = $("#lr-lexicon-content");
  const applyBtn = $("#lr-apply-btn");
  const footHint = $("#lr-foot-hint");

  const confirmModal = $("#lr-confirm-modal");
  const nextPathEl = $("#lr-next-path");
  const archivePathEl = $("#lr-archive-path");
  const confirmList = $("#lr-confirm-list");
  const confirmYes = $("#lr-confirm-yes");
  const confirmNo = $("#lr-confirm-no");
  const confirmStatus = $("#lr-confirm-status");

  const evidenceModal = $("#lr-evidence-modal");
  const evidenceIndex = $("#lr-evidence-index");
  const evidenceContent = $("#lr-evidence-content");
  const evidenceClose = $("#lr-evidence-close");

  const state = {
    currentLexicon: { version: "v?", path: "", content: "" },
    proposalList: [],
    selectedTs: null,
    proposal: null,
    // patchId -> { status: "pending"|"accepted"|"rejected"|"edited", editedContent, originalContent }
    patchUI: new Map(),
  };

  async function apiGet(path) {
    const res = await fetch(path);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || res.statusText);
    }
    return res.json();
  }

  async function apiPost(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }

  function setStatus(msg, isError) {
    statusEl.textContent = msg;
    statusEl.style.color = isError ? "#b00020" : "";
  }

  function renderLexiconWithHighlight(anchorText) {
    const text = state.currentLexicon.content || "";
    if (!anchorText) {
      lexiconContentEl.textContent = text;
      return;
    }
    const idx = text.indexOf(anchorText);
    if (idx < 0) {
      lexiconContentEl.textContent = text;
      return;
    }
    const before = text.slice(0, idx);
    const match = text.slice(idx, idx + anchorText.length);
    const after = text.slice(idx + anchorText.length);
    lexiconContentEl.innerHTML = "";
    lexiconContentEl.appendChild(document.createTextNode(before));
    const mk = document.createElement("mark");
    mk.textContent = match;
    lexiconContentEl.appendChild(mk);
    lexiconContentEl.appendChild(document.createTextNode(after));
    // scroll mark into view
    setTimeout(() => {
      const r = mk.getBoundingClientRect();
      const c = lexiconContentEl.getBoundingClientRect();
      if (r.top < c.top || r.bottom > c.bottom) {
        mk.scrollIntoView({ block: "center" });
      }
    }, 30);
  }

  function refreshApplyButton() {
    let acceptedCount = 0;
    for (const v of state.patchUI.values()) {
      if (v.status === "accepted" || v.status === "edited") acceptedCount++;
    }
    applyBtn.textContent = `应用 ${acceptedCount} 个采纳`;
    applyBtn.disabled = acceptedCount === 0;
    footHint.textContent = acceptedCount === 0
      ? "勾选采纳后即可点击应用"
      : `已采纳 ${acceptedCount} 条；其余将随 applied.json 记录拒绝/未选`;
  }

  function setPatchStatus(patchId, status) {
    const ui = state.patchUI.get(patchId);
    if (!ui) return;
    ui.status = status;
    const li = patchesEl.querySelector(`[data-patch-id="${patchId}"]`);
    if (li) {
      li.dataset.status = status;
      li.querySelectorAll(".lr-patch-actions button").forEach((b) => b.classList.remove("is-active"));
      const map = { accepted: ".btn-accept", rejected: ".btn-reject", edited: ".btn-edit" };
      if (map[status]) {
        const btn = li.querySelector(map[status]);
        if (btn) btn.classList.add("is-active");
      }
      // textarea 显隐
      const ta = li.querySelector("textarea[data-role=editor]");
      if (ta) ta.style.display = status === "edited" ? "block" : "none";
      const preNew = li.querySelector("pre[data-role=new-content-pre]");
      if (preNew) preNew.style.display = status === "edited" ? "none" : "block";
    }
    refreshApplyButton();
  }

  function buildPatchLI(patch, idx) {
    const li = document.createElement("li");
    li.className = "lr-patch";
    li.dataset.status = "pending";
    li.dataset.patchId = patch.id || `p_${idx}`;

    const head = document.createElement("div");
    head.className = "lr-patch-head";
    head.innerHTML = `
      <div>
        <span class="lr-patch-id">${escapeHtml(patch.id || `p_${idx}`)}</span>
        <span class="lr-patch-section">${escapeHtml(patch.section || "")}</span>
        <span class="lr-patch-action">${escapeHtml(patch.action || "")}</span>
        ${patch.position ? `<span class="lr-patch-action">${escapeHtml(patch.position)}</span>` : ""}
      </div>`;
    li.appendChild(head);

    if (patch.rationale) {
      const r = document.createElement("p");
      r.className = "lr-patch-rationale";
      r.textContent = patch.rationale;
      li.appendChild(r);
    }

    const ev = document.createElement("div");
    ev.className = "lr-patch-evidence";
    const rows = Array.isArray(patch.evidence_rows) ? patch.evidence_rows : [];
    ev.innerHTML = `<span class="lr-patch-label">evidence_rows</span>` +
      rows.map((rIdx) => `<button class="evidence-pill" data-row="${rIdx}" type="button">#${rIdx}</button>`).join("") +
      (Array.isArray(patch.hypotheses) && patch.hypotheses.length
        ? ` <span class="lr-patch-label" style="display:inline">·</span> hypotheses: ${patch.hypotheses.map(escapeHtml).join(", ")}`
        : "");
    li.appendChild(ev);

    if (patch.anchor_text) {
      const a = document.createElement("div");
      a.className = "lr-patch-anchor";
      a.innerHTML = `<span class="lr-patch-label">anchor_text</span>`;
      const pre = document.createElement("pre");
      pre.textContent = patch.anchor_text;
      a.appendChild(pre);
      li.appendChild(a);
    }

    const n = document.createElement("div");
    n.className = "lr-patch-newcontent";
    n.innerHTML = `<span class="lr-patch-label">new_content</span>`;
    const preNew = document.createElement("pre");
    preNew.dataset.role = "new-content-pre";
    preNew.textContent = patch.new_content || "";
    n.appendChild(preNew);
    const ta = document.createElement("textarea");
    ta.dataset.role = "editor";
    ta.style.display = "none";
    ta.value = patch.new_content || "";
    n.appendChild(ta);
    li.appendChild(n);

    const actions = document.createElement("div");
    actions.className = "lr-patch-actions";
    const btnAccept = document.createElement("button");
    btnAccept.className = "btn-accept";
    btnAccept.type = "button";
    btnAccept.textContent = "采纳";
    const btnReject = document.createElement("button");
    btnReject.className = "btn-reject";
    btnReject.type = "button";
    btnReject.textContent = "拒绝";
    const btnEdit = document.createElement("button");
    btnEdit.className = "btn-edit";
    btnEdit.type = "button";
    btnEdit.textContent = "改后采纳";
    actions.appendChild(btnAccept);
    actions.appendChild(btnReject);
    actions.appendChild(btnEdit);
    li.appendChild(actions);

    btnAccept.addEventListener("click", () => setPatchStatus(li.dataset.patchId, "accepted"));
    btnReject.addEventListener("click", () => setPatchStatus(li.dataset.patchId, "rejected"));
    btnEdit.addEventListener("click", () => setPatchStatus(li.dataset.patchId, "edited"));

    // 点 patch 卡 → 高亮 anchor
    li.addEventListener("click", (e) => {
      if (e.target.closest(".evidence-pill")) return;
      if (e.target.closest("button")) return;
      if (e.target.closest("textarea")) return;
      renderLexiconWithHighlight(patch.anchor_text);
    });

    // evidence pills 弹 modal
    ev.querySelectorAll(".evidence-pill").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const rowIdx = btn.dataset.row;
        try {
          const data = await apiGet(`/api/feedback/row?index=${encodeURIComponent(rowIdx)}`);
          evidenceIndex.textContent = String(rowIdx);
          evidenceContent.textContent = JSON.stringify(data.row, null, 2);
          if (typeof evidenceModal.showModal === "function") evidenceModal.showModal();
        } catch (err) {
          alert(`无法读取 row ${rowIdx}: ${err.message}`);
        }
      });
    });

    state.patchUI.set(li.dataset.patchId, {
      status: "pending",
      editedContent: null,
      originalContent: patch.new_content || "",
      patchSpec: patch,
      textarea: ta,
    });

    return li;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderProposal(proposal) {
    state.proposal = proposal;
    state.patchUI.clear();
    hypothesesEl.innerHTML = "";
    patchesEl.innerHTML = "";
    withheldBody.innerHTML = "";

    const win = proposal.feedback_window || {};
    metaEl.textContent = `${proposal.base_version || "?"} → ${proposal.next_version || "?"}` +
      ` · ${win.rows || "?"} 条 feedback (${win.first_ts || "?"} → ${win.last_ts || "?"})` +
      ` · patches=${(proposal.patches || []).length} · withheld=${(proposal.withheld || []).length + (proposal._auto_withheld || []).length}`;

    for (const h of (proposal.hypotheses || [])) {
      const div = document.createElement("div");
      div.className = "lr-hypothesis";
      div.innerHTML = `<span class="hid">${escapeHtml(h.id || "h?")}</span>` +
        escapeHtml(h.text || "") +
        `<span class="haxis">${escapeHtml(h.axis || "")} · rows=${(h.evidence_rows || []).join(",")}</span>`;
      hypothesesEl.appendChild(div);
    }

    (proposal.patches || []).forEach((p, i) => {
      patchesEl.appendChild(buildPatchLI(p, i));
    });

    const withheld = [...(proposal.withheld || []), ...(proposal._auto_withheld || []).map((w) => ({
      section: w.section,
      reason: `[anchor 校验失败 patch=${w.patch_id}] ${w.reason}`,
    }))];
    if (withheld.length) {
      const ul = document.createElement("ul");
      withheld.forEach((w) => {
        const li = document.createElement("li");
        li.textContent = `${w.section || ""} — ${w.reason || ""}`;
        ul.appendChild(li);
      });
      withheldBody.appendChild(ul);
    } else {
      withheldBody.textContent = "（无）";
    }
    refreshApplyButton();
  }

  async function loadCurrentLexicon() {
    try {
      const data = await apiGet("/api/lexicon/current");
      state.currentLexicon = data;
      versionBadge.textContent = data.version || "v?";
      lexiconContentEl.textContent = data.content || "";
    } catch (e) {
      setStatus(`加载 lexicon 失败：${e.message}`, true);
      lexiconContentEl.textContent = "（无法加载）";
    }
  }

  async function loadProposalList() {
    try {
      const data = await apiGet("/api/lexicon/proposals");
      state.proposalList = data.items || [];
      proposalSelect.innerHTML = "";
      if (!state.proposalList.length) {
        const opt = document.createElement("option");
        opt.textContent = "（无 proposal）";
        proposalSelect.appendChild(opt);
        setStatus("暂无 proposal；先跑 synthesize_lexicon");
        return;
      }
      state.proposalList.forEach((p, i) => {
        const opt = document.createElement("option");
        opt.value = p.ts;
        opt.textContent = `${p.ts} · ${p.base_version}→${p.next_version} · patches=${p.patches_count}${p.applied ? "（已应用）" : ""}`;
        if (i === 0) opt.selected = true;
        proposalSelect.appendChild(opt);
      });
      state.selectedTs = state.proposalList[0].ts;
      await loadProposal(state.selectedTs);
    } catch (e) {
      setStatus(`加载 proposal 列表失败：${e.message}`, true);
    }
  }

  async function loadProposal(ts) {
    try {
      setStatus(`加载 ${ts} 中...`);
      const data = await apiGet(`/api/lexicon/proposal/${encodeURIComponent(ts)}`);
      state.selectedTs = ts;
      renderProposal(data.proposal_json || {});
      if (data.applied) {
        setStatus(`proposal ${ts} 已于 ${data.applied.ts} 应用为 ${data.applied.new_version}`);
        applyBtn.disabled = true;
      } else {
        setStatus(`已加载 ${ts}`);
      }
    } catch (e) {
      setStatus(`加载 proposal ${ts} 失败：${e.message}`, true);
    }
  }

  proposalSelect.addEventListener("change", () => loadProposal(proposalSelect.value));

  applyBtn.addEventListener("click", () => openConfirmModal());

  function openConfirmModal() {
    if (!state.proposal || !state.selectedTs) return;
    const accepted = collectAcceptedPatches();
    if (!accepted.length) return;
    const curVerNum = parseVersion(state.currentLexicon.version);
    const nextVerNum = curVerNum != null ? curVerNum + 1 : "?";
    nextPathEl.textContent = `context/pipeline-b-style-lexicon-v${nextVerNum}.md`;
    const today = new Date().toISOString().slice(0, 10);
    archivePathEl.textContent = `context/_archive/lexicon-v${curVerNum}-${today}.md`;
    confirmList.innerHTML = "";
    accepted.forEach((p) => {
      const li = document.createElement("li");
      li.textContent = `${p.id} · ${p.section} · ${p.action}${p._edited ? " （已改）" : ""}`;
      confirmList.appendChild(li);
    });
    confirmStatus.textContent = "";
    if (typeof confirmModal.showModal === "function") confirmModal.showModal();
  }

  function parseVersion(v) {
    const m = String(v || "").match(/v(\d+)/);
    return m ? parseInt(m[1], 10) : null;
  }

  function collectAcceptedPatches() {
    const out = [];
    for (const [patchId, ui] of state.patchUI.entries()) {
      if (ui.status === "accepted") {
        out.push({ ...ui.patchSpec });
      } else if (ui.status === "edited") {
        const edited = (ui.textarea && ui.textarea.value) || ui.originalContent || "";
        out.push({ ...ui.patchSpec, new_content: edited, _edited: true });
      }
    }
    return out;
  }

  function collectRejectReasons() {
    const reasons = {};
    for (const [patchId, ui] of state.patchUI.entries()) {
      if (ui.status === "rejected") reasons[patchId] = "user_rejected";
    }
    return reasons;
  }

  confirmNo.addEventListener("click", () => confirmModal.close());

  confirmYes.addEventListener("click", async () => {
    confirmYes.disabled = true;
    confirmStatus.textContent = "应用中...";
    try {
      const accepted = collectAcceptedPatches().map((p) => {
        const { _edited, ...rest } = p;
        return rest;
      });
      const result = await apiPost("/api/lexicon/apply", {
        proposal_ts: state.selectedTs,
        accepted_patches: accepted,
        reject_reasons: collectRejectReasons(),
      });
      confirmStatus.textContent = `成功 → ${result.new_version} (${result.new_path})；archive ${result.archive_path}；prompt_updated=${result.prompt_updated}`;
      setStatus(`应用成功 → ${result.new_version}`);
      // 刷新当前 lexicon 与 proposal 列表
      await loadCurrentLexicon();
      await loadProposalList();
      // 选回 same ts（会显示 已应用）
      if (state.selectedTs) await loadProposal(state.selectedTs);
    } catch (e) {
      confirmStatus.textContent = `失败：${e.message}`;
    } finally {
      confirmYes.disabled = false;
    }
  });

  evidenceClose.addEventListener("click", () => evidenceModal.close());

  async function boot() {
    await loadCurrentLexicon();
    await loadProposalList();
  }

  boot();
})();

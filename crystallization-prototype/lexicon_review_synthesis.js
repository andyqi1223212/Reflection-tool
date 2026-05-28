"use strict";

(function () {
  const $ = (sel) => document.querySelector(sel);
  const proposalSelect = $("#lr-syn-proposal-select");
  const syncedBadge = $("#lr-syn-synced-badge");
  const metaEl = $("#lr-syn-meta");
  const hypothesesEl = $("#lr-syn-hypotheses");
  const patchesEl = $("#lr-syn-patches");
  const withheldBody = $("#lr-syn-withheld-body");
  const contentEl = $("#lr-syn-content");
  const applyBtn = $("#lr-syn-apply-btn");
  const footHint = $("#lr-syn-foot-hint");
  const confirmModal = $("#lr-syn-confirm-modal");
  const archivePathEl = $("#lr-syn-archive-path");
  const confirmList = $("#lr-syn-confirm-list");
  const confirmYes = $("#lr-syn-confirm-yes");
  const confirmNo = $("#lr-syn-confirm-no");
  const confirmStatus = $("#lr-syn-confirm-status");
  const evidenceModal = $("#lr-syn-evidence-modal");
  const evidenceRunId = $("#lr-syn-evidence-runid");
  const evidenceContent = $("#lr-syn-evidence-content");
  const evidenceClose = $("#lr-syn-evidence-close");

  if (!proposalSelect || !patchesEl) return;

  const state = {
    current: { path: "", content: "", last_synced: "" },
    proposalList: [],
    selectedTs: null,
    proposal: null,
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
    if (!res.ok) throw new Error(data.error || data.failed_patch_ids?.join?.(", ") || res.statusText);
    return data;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderHighlight(anchorText) {
    const text = state.current.content || "";
    if (!anchorText || text.indexOf(anchorText) < 0) {
      contentEl.textContent = text;
      return;
    }
    const idx = text.indexOf(anchorText);
    contentEl.innerHTML = "";
    contentEl.appendChild(document.createTextNode(text.slice(0, idx)));
    const mk = document.createElement("mark");
    mk.textContent = text.slice(idx, idx + anchorText.length);
    contentEl.appendChild(mk);
    contentEl.appendChild(document.createTextNode(text.slice(idx + anchorText.length)));
    setTimeout(() => mk.scrollIntoView({ block: "center" }), 30);
  }

  function refreshApplyButton() {
    let n = 0;
    for (const v of state.patchUI.values()) {
      if (v.status === "accepted" || v.status === "edited") n++;
    }
    applyBtn.textContent = `应用 ${n} 个采纳`;
    applyBtn.disabled = n === 0;
    footHint.textContent = n === 0 ? "勾选采纳后即可 apply synthesis" : `已采纳 ${n} 条`;
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
      const btn = li.querySelector(map[status]);
      if (btn) btn.classList.add("is-active");
      const ta = li.querySelector("textarea[data-role=editor]");
      const preNew = li.querySelector("pre[data-role=new-content-pre]");
      if (ta) ta.style.display = status === "edited" ? "block" : "none";
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
      </div>`;
    li.appendChild(head);

    const ev = document.createElement("div");
    ev.className = "lr-patch-evidence";
    const runs = Array.isArray(patch.evidence_runs) ? patch.evidence_runs : [];
    ev.innerHTML =
      `<span class="lr-patch-label">evidence_runs</span>` +
      runs.map((rid) => `<button class="evidence-pill syn-run-pill" data-run="${escapeHtml(rid)}" type="button">${escapeHtml(rid)}</button>`).join("");
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
    ["采纳", "拒绝", "改后采纳"].forEach((label, i) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label;
      btn.className = ["btn-accept", "btn-reject", "btn-edit"][i];
      const st = ["accepted", "rejected", "edited"][i];
      btn.addEventListener("click", () => setPatchStatus(li.dataset.patchId, st));
      actions.appendChild(btn);
    });
    li.appendChild(actions);

    li.addEventListener("click", (e) => {
      if (e.target.closest(".syn-run-pill")) return;
      if (e.target.closest("button")) return;
      if (e.target.closest("textarea")) return;
      renderHighlight(patch.anchor_text);
    });

    ev.querySelectorAll(".syn-run-pill").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const rid = btn.dataset.run;
        try {
          const data = await apiGet(`/runs/${encodeURIComponent(rid)}/manifest.json`);
          evidenceRunId.textContent = rid;
          evidenceContent.textContent = JSON.stringify(data, null, 2);
          if (typeof evidenceModal.showModal === "function") evidenceModal.showModal();
        } catch (err) {
          evidenceRunId.textContent = rid;
          evidenceContent.textContent = String(err.message);
          if (typeof evidenceModal.showModal === "function") evidenceModal.showModal();
        }
      });
    });

    state.patchUI.set(li.dataset.patchId, {
      status: "pending",
      patchSpec: patch,
      textarea: ta,
    });
    return li;
  }

  function renderProposal(proposal) {
    state.proposal = proposal;
    state.patchUI.clear();
    hypothesesEl.innerHTML = "";
    patchesEl.innerHTML = "";
    withheldBody.innerHTML = "";

    metaEl.textContent =
      `last_synced=${proposal.last_synced_was || "?"}` +
      ` · patches=${(proposal.patches || []).length}` +
      ` · runs=${(proposal.meta_stats || {}).runs_window_count || "?"}`;

    for (const h of proposal.hypotheses || []) {
      const div = document.createElement("div");
      div.className = "lr-hypothesis";
      div.innerHTML = `<span class="hid">${escapeHtml(h.id || "h?")}</span> ${escapeHtml(h.text || "")}`;
      hypothesesEl.appendChild(div);
    }

    (proposal.patches || []).forEach((p, i) => patchesEl.appendChild(buildPatchLI(p, i)));

    const withheld = [
      ...(proposal.withheld || []),
      ...(proposal._auto_withheld || []).map((w) => ({
        section: w.section,
        reason: `[auto] patch=${w.patch_id} ${w.reason}`,
      })),
    ];
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

  async function loadCurrent() {
    const data = await apiGet("/api/synthesis/current");
    state.current = data;
    syncedBadge.textContent = data.last_synced ? `sync ${data.last_synced}` : "—";
    contentEl.textContent = data.content || "";
  }

  async function loadProposalList() {
    const data = await apiGet("/api/synthesis/proposals");
    state.proposalList = data.items || [];
    proposalSelect.innerHTML = "";
    if (!state.proposalList.length) {
      proposalSelect.appendChild(new Option("（无 proposal）", ""));
      return;
    }
    state.proposalList.forEach((p, i) => {
      const opt = document.createElement("option");
      opt.value = p.ts;
      opt.textContent = `${p.ts} · patches=${p.patches_count}${p.applied ? "（已应用）" : ""}`;
      if (i === 0) opt.selected = true;
      proposalSelect.appendChild(opt);
    });
    state.selectedTs = state.proposalList[0].ts;
    await loadProposal(state.selectedTs);
  }

  async function loadProposal(ts) {
    const data = await apiGet(`/api/synthesis/proposal/${encodeURIComponent(ts)}`);
    state.selectedTs = ts;
    renderProposal(data.proposal_json || {});
    if (data.applied) {
      applyBtn.disabled = true;
      metaEl.textContent += ` · 已于 ${data.applied.ts} 应用`;
    }
  }

  function collectAcceptedPatches() {
    const out = [];
    for (const [, ui] of state.patchUI.entries()) {
      if (ui.status === "accepted") out.push({ ...ui.patchSpec });
      else if (ui.status === "edited") {
        out.push({
          ...ui.patchSpec,
          new_content: (ui.textarea && ui.textarea.value) || ui.patchSpec.new_content,
        });
      }
    }
    return out;
  }

  function collectRejectReasons() {
    const reasons = {};
    for (const [pid, ui] of state.patchUI.entries()) {
      if (ui.status === "rejected") reasons[pid] = "user_rejected";
    }
    return reasons;
  }

  proposalSelect.addEventListener("change", () => {
    if (proposalSelect.value) loadProposal(proposalSelect.value);
  });

  applyBtn.addEventListener("click", () => {
    const accepted = collectAcceptedPatches();
    if (!accepted.length) return;
    const today = new Date().toISOString().slice(0, 10);
    archivePathEl.textContent = `context/_archive/synthesis-${today}.md`;
    confirmList.innerHTML = "";
    accepted.forEach((p) => {
      const li = document.createElement("li");
      li.textContent = `${p.id} · ${p.section} · ${p.action}`;
      confirmList.appendChild(li);
    });
    confirmStatus.textContent = "";
    if (typeof confirmModal.showModal === "function") confirmModal.showModal();
  });

  confirmNo.addEventListener("click", () => confirmModal.close());
  evidenceClose.addEventListener("click", () => evidenceModal.close());

  confirmYes.addEventListener("click", async () => {
    confirmYes.disabled = true;
    confirmStatus.textContent = "应用中...";
    try {
      const result = await apiPost("/api/synthesis/apply", {
        proposal_ts: state.selectedTs,
        accepted_patches: collectAcceptedPatches(),
        reject_reasons: collectRejectReasons(),
      });
      confirmStatus.textContent = `成功 · archive ${result.archive_path} · 日期 ${result.last_synced_updated_to}`;
      await loadCurrent();
      await loadProposalList();
      if (state.selectedTs) await loadProposal(state.selectedTs);
    } catch (e) {
      confirmStatus.textContent = `失败：${e.message}`;
    } finally {
      confirmYes.disabled = false;
    }
  });

  window.lrSynthesisReview = {
    async boot() {
      metaEl.hidden = false;
      await loadCurrent();
      await loadProposalList();
    },
  };
})();

"use strict";

(function () {
  function $(sel) {
    return document.querySelector(sel);
  }

  function readBootstrap() {
    const el = document.getElementById("lr-trial-bootstrap");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.error("[trial] bootstrap JSON 解析失败", e);
      return null;
    }
  }

  function apiBase() {
    if (window.location.protocol === "file:") {
      return "http://127.0.0.1:8765";
    }
    return "";
  }

  async function apiGet(path) {
    const res = await fetch(apiBase() + path);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText || `HTTP ${res.status}`);
    return data;
  }

  async function apiPost(path, body) {
    const res = await fetch(apiBase() + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText || `HTTP ${res.status}`);
    return data;
  }

  function init() {
    const tabs = document.querySelectorAll(".lr-tab");
    const panelProposal = $("#lr-panel-proposal");
    const panelSynthesis = $("#lr-panel-synthesis");
    const panelTrial = $("#lr-panel-trial");
    const footProposal = $(".lr-foot-proposal");
    const footSynthesis = $(".lr-foot-synthesis");
    const footTrial = $(".lr-foot-trial");
    const controlsProposal = $(".lr-controls-proposal");
    const controlsSynthesis = $(".lr-controls-synthesis");
    const controlsTrial = $(".lr-controls-trial");
    const leadProposal = $(".lr-lead-proposal");
    const leadSynthesis = $(".lr-lead-synthesis");
    const leadTrial = $(".lr-lead-trial");
    const metaSynthesis = $("#lr-syn-meta");
    const versionSelect = $("#lr-trial-version");
    const pickSelect = $("#lr-trial-pick");
    const runBtn = $("#lr-trial-run-btn");
    const runStatus = $("#lr-trial-run-status");
    const tbody = $("#lr-trial-tbody");
    const detailSec = $("#lr-trial-detail");
    const detailTitle = $("#lr-trial-detail-title");
    const oldBody = $("#lr-trial-old-body");
    const newBody = $("#lr-trial-new-body");
    const acceptBtn = $("#lr-trial-accept-btn");
    const rejectBtn = $("#lr-trial-reject-btn");
    const feedbackBtn = $("#lr-trial-feedback-btn");
    const closeDetail = $("#lr-trial-close-detail");
    const batchAccept = $("#lr-trial-batch-accept");
    const fbModal = $("#lr-trial-feedback-modal");
    const fbScore = $("#lr-trial-fb-score");
    const fbText = $("#lr-trial-fb-text");
    const fbSubmit = $("#lr-trial-fb-submit");
    const fbCancel = $("#lr-trial-fb-cancel");
    const fbStatus = $("#lr-trial-fb-status");
    const headerStatus = $("#lr-status");

    if (!tbody || !versionSelect || !runStatus) {
      const msg = "Trial UI 节点缺失，请用开发台打开本页：http://127.0.0.1:8765/lexicon_review.html?tab=trial";
      console.error("[trial]", msg);
      if (runStatus) runStatus.textContent = msg;
      return;
    }

    if (window.location.protocol === "file:") {
      runStatus.textContent =
        "当前为 file:// 打开，API 不可用。请访问 http://127.0.0.1:8765/lexicon_review.html?tab=trial";
    }

    const trialState = {
      version: 4,
      items: [],
      selectedRunId: null,
      wins: new Set(),
      pendingDecision: "win",
    };

    function setActiveTab(name) {
      const isProposal = name === "proposal";
      const isSynthesis = name === "synthesis";
      const isTrial = name === "trial";
      const show = (el, on) => {
        if (!el) return;
        el.classList.toggle("lr-panel-hidden", !on);
        el.hidden = !on;
      };
      show(panelProposal, isProposal);
      show(panelSynthesis, isSynthesis);
      show(panelTrial, isTrial);
      show(footProposal, isProposal);
      show(footSynthesis, isSynthesis);
      show(footTrial, isTrial);
      if (controlsProposal) controlsProposal.hidden = !isProposal;
      if (controlsSynthesis) controlsSynthesis.hidden = !isSynthesis;
      if (controlsTrial) controlsTrial.hidden = !isTrial;
      if (leadProposal) leadProposal.hidden = !isProposal;
      if (leadSynthesis) leadSynthesis.hidden = !isSynthesis;
      if (leadTrial) leadTrial.hidden = !isTrial;
      if (metaSynthesis) metaSynthesis.hidden = !isSynthesis;
    }

    function ensureVersionOption(version, label) {
      versionSelect.innerHTML = "";
      const opt = document.createElement("option");
      opt.value = String(version);
      opt.textContent = label || `v${version}`;
      versionSelect.appendChild(opt);
      versionSelect.value = String(version);
      trialState.version = version;
    }

    function renderTrialRows(items) {
      trialState.items = items || [];
      tbody.innerHTML = "";
      trialState.wins.clear();
      trialState.items.forEach((row) => {
        const tr = document.createElement("tr");
        tr.dataset.runId = row.run_id;
        const rid = String(row.run_id || "");
        tr.innerHTML = `
          <td><code>${rid}</code></td>
          <td>${row.title || ""}</td>
          <td>${row.route || ""}</td>
          <td>${row.mech_chars || ""}</td>
          <td>${row.anchor_chars || ""}</td>
          <td>${row.steps_count || ""}</td>
          <td>${row.status || ""}</td>
          <td>${row.note || ""}</td>`;
        tr.addEventListener("click", () => openDetail(rid));
        tbody.appendChild(tr);
      });
      updateBatchBtn();
      runStatus.textContent = trialState.items.length
        ? `已加载 v${trialState.version} · ${trialState.items.length} 条 · 端口 ${window.location.port || "file"}`
        : `v${trialState.version} 尚无 trial 产物，点「跑 trial」生成`;
      if (headerStatus && trialState.items.length) {
        headerStatus.textContent = `Trial v${trialState.version} · ${trialState.items.length} 条`;
      }
    }

    function bindExistingRows() {
      const existing = tbody.querySelectorAll("tr[data-run-id]");
      if (!existing.length) return;
      const items = [];
      existing.forEach((tr) => {
        const rid = tr.dataset.runId;
        const cells = tr.querySelectorAll("td");
        if (!rid || cells.length < 8) return;
        items.push({
          run_id: rid,
          title: cells[1].textContent,
          route: cells[2].textContent,
          mech_chars: cells[3].textContent,
          anchor_chars: cells[4].textContent,
          steps_count: cells[5].textContent,
          status: cells[6].textContent,
          note: cells[7].textContent,
        });
        tr.addEventListener("click", () => openDetail(rid));
      });
      if (items.length) {
        trialState.items = items;
        runStatus.textContent = `已显示 v${trialState.version} · ${items.length} 条（服务端预填）`;
      }
    }

    function applyBootstrap() {
      const boot = readBootstrap();
      if (!boot) return false;
      const versions = boot.versions || [];
      if (versions.length) {
        versionSelect.innerHTML = "";
        versions.forEach((it) => {
          const opt = document.createElement("option");
          opt.value = String(it.version);
          opt.textContent = `v${it.version}（${it.trial_count} 张）`;
          versionSelect.appendChild(opt);
        });
        trialState.version = boot.default_version || versions[0].version;
        versionSelect.value = String(trialState.version);
      } else {
        ensureVersionOption(boot.default_version || 4, `v${boot.default_version || 4}`);
      }
      const items = (boot.trials && boot.trials.items) || [];
      if (items.length) {
        renderTrialRows(items);
        return true;
      }
      bindExistingRows();
      return tbody.querySelectorAll("tr").length > 0;
    }

    async function loadTrials() {
      trialState.version = parseInt(versionSelect.value, 10) || 4;
      try {
        const data = await apiGet(`/api/eval_lite/trials?version=${trialState.version}`);
        renderTrialRows(data.items || []);
      } catch (e) {
        if (!trialState.items.length) {
          runStatus.textContent = `加载 trial 失败：${e.message}。请确认用 http://127.0.0.1:8765 打开并已重启开发台`;
        }
      }
    }

    async function loadVersions() {
      try {
        const data = await apiGet("/api/eval_lite/versions");
        const items = data.items || [];
        versionSelect.innerHTML = "";
        if (!items.length) {
          ensureVersionOption(4, "v4（尚未跑 trial）");
        } else {
          items.forEach((it) => {
            const opt = document.createElement("option");
            opt.value = String(it.version);
            opt.textContent = `v${it.version}（${it.trial_count} 张）`;
            versionSelect.appendChild(opt);
          });
          trialState.version = items[0].version;
          versionSelect.value = String(trialState.version);
        }
      } catch (e) {
        if (!versionSelect.options.length) {
          ensureVersionOption(4, "v4");
        }
        runStatus.textContent = `API 刷新失败（仍显示缓存数据）：${e.message}`;
        return;
      }
      await loadTrials();
    }

    function switchTab(name) {
      tabs.forEach((t) => {
        const on = t.dataset.tab === name;
        t.classList.toggle("lr-tab-active", on);
        t.setAttribute("aria-selected", on ? "true" : "false");
      });
      setActiveTab(name);
      if (name === "synthesis" && window.lrSynthesisReview) {
        window.lrSynthesisReview.boot().catch((e) => {
          if (headerStatus) headerStatus.textContent = `Synthesis 加载失败：${e.message}`;
        });
      }
      if (name === "trial") {
        if (!trialState.items.length) {
          applyBootstrap();
        }
        loadVersions().catch((e) => {
          runStatus.textContent = `Trial 加载异常：${e.message || e}`;
        });
      }
    }

    tabs.forEach((t) => {
      t.addEventListener("click", () => switchTab(t.dataset.tab));
    });

    function extractCryst(b) {
      if (!b || typeof b !== "object") {
        return { mechanism: "", anchor: "", micro_steps: [] };
      }
      let c = b.crystallization;
      if (b.output_kind === "update_entry" && b.update_entry) {
        c = b.update_entry.crystallization;
      }
      c = c || {};
      const steps = Array.isArray(c.micro_steps) ? c.micro_steps.map(String) : [];
      return {
        mechanism: String(c.mechanism || "").trim(),
        anchor: String(c.anchor || "").trim(),
        micro_steps: steps,
      };
    }

    function diffHighlight(oldStr, newStr) {
      if (oldStr === newStr) {
        const pre = document.createElement("pre");
        pre.textContent = newStr || "（空）";
        return pre;
      }
      const wrap = document.createElement("pre");
      let i = 0;
      const maxLen = Math.max(oldStr.length, newStr.length);
      while (i < maxLen && oldStr[i] === newStr[i]) i++;
      let jOld = oldStr.length - 1;
      let jNew = newStr.length - 1;
      while (jOld >= i && jNew >= i && oldStr[jOld] === newStr[jNew]) {
        jOld--;
        jNew--;
      }
      wrap.appendChild(document.createTextNode(oldStr.slice(0, i)));
      const oldMid = oldStr.slice(i, jOld + 1);
      const newMid = newStr.slice(i, jNew + 1);
      if (oldMid) {
        const del = document.createElement("del");
        del.textContent = oldMid;
        wrap.appendChild(del);
      }
      if (newMid) {
        const ins = document.createElement("ins");
        ins.textContent = newMid;
        wrap.appendChild(ins);
      }
      wrap.appendChild(document.createTextNode(newStr.slice(jNew + 1)));
      return wrap;
    }

    function renderCrystBlock(container, cryst, isNew, crystOld) {
      if (!container) return;
      container.innerHTML = "";
      const mechLabel = document.createElement("p");
      mechLabel.innerHTML = "<strong>mechanism</strong>";
      container.appendChild(mechLabel);
      const mechPre = document.createElement("pre");
      if (isNew) {
        container.appendChild(diffHighlight(crystOld.mechanism, cryst.mechanism));
      } else {
        mechPre.textContent = cryst.mechanism || "（空）";
        container.appendChild(mechPre);
      }
      const anchLabel = document.createElement("p");
      anchLabel.innerHTML = "<strong>anchor</strong>";
      container.appendChild(anchLabel);
      if (isNew) {
        container.appendChild(diffHighlight(crystOld.anchor, cryst.anchor));
      } else {
        const pre = document.createElement("pre");
        pre.textContent = cryst.anchor || "（空）";
        container.appendChild(pre);
      }
      const stepsLabel = document.createElement("p");
      stepsLabel.innerHTML = "<strong>micro_steps</strong>";
      container.appendChild(stepsLabel);
      const ol = document.createElement("ol");
      const n = Math.max(
        cryst.micro_steps.length,
        isNew ? crystOld.micro_steps.length : 0,
        1
      );
      for (let i = 0; i < n; i++) {
        const li = document.createElement("li");
        if (isNew) {
          li.appendChild(
            diffHighlight(crystOld.micro_steps[i] || "", cryst.micro_steps[i] || "")
          );
        } else {
          li.textContent = cryst.micro_steps[i] || "—";
        }
        ol.appendChild(li);
      }
      container.appendChild(ol);
    }

    async function openDetail(runId) {
      trialState.selectedRunId = runId;
      const data = await apiGet(
        `/api/eval_lite/trial/${trialState.version}/${encodeURIComponent(runId)}`
      );
      if (detailSec) detailSec.hidden = false;
      if (detailTitle) detailTitle.textContent = `单卡 diff · ${runId}`;
      const co = extractCryst(data.b_old);
      const cn = extractCryst(data.b_new);
      renderCrystBlock(oldBody, co, false, co);
      renderCrystBlock(newBody, cn, true, co);
    }

    function updateBatchBtn() {
      if (!batchAccept) return;
      const n = trialState.wins.size;
      batchAccept.disabled = n === 0;
      batchAccept.textContent = `整体 accept ${n} 张 win`;
    }

    async function postDecision(decision, extra) {
      if (!trialState.selectedRunId) return;
      await apiPost("/api/eval_lite/accept", {
        lexicon_version: trialState.version,
        run_id: trialState.selectedRunId,
        decision,
        ...extra,
      });
      if (decision === "win") trialState.wins.add(trialState.selectedRunId);
      runStatus.textContent = `已记录 ${decision} · ${trialState.selectedRunId}`;
      updateBatchBtn();
    }

    if (runBtn) {
      runBtn.addEventListener("click", async () => {
        runBtn.disabled = true;
        runStatus.textContent = "正在跑 trial（约 1–2 分钟/张）…";
        try {
          await apiPost("/api/eval_lite/run", {
            lexicon_version: trialState.version,
            pick: pickSelect ? pickSelect.value : "last5_pushed",
          });
          await loadVersions();
        } catch (e) {
          runStatus.textContent = `失败: ${e.message}`;
        } finally {
          runBtn.disabled = false;
        }
      });
    }

    if (versionSelect) {
      versionSelect.addEventListener("change", () => loadTrials());
    }
    if (acceptBtn) acceptBtn.addEventListener("click", () => postDecision("win"));
    if (rejectBtn) rejectBtn.addEventListener("click", () => postDecision("lose"));
    if (closeDetail) {
      closeDetail.addEventListener("click", () => {
        if (detailSec) detailSec.hidden = true;
        trialState.selectedRunId = null;
      });
    }
    if (feedbackBtn && fbModal) {
      feedbackBtn.addEventListener("click", () => {
        trialState.pendingDecision = "win";
        if (fbScore) fbScore.value = "5";
        if (fbText) fbText.value = "";
        if (fbStatus) fbStatus.textContent = "";
        fbModal.showModal();
      });
    }
    if (fbCancel && fbModal) fbCancel.addEventListener("click", () => fbModal.close());
    if (fbSubmit) {
      fbSubmit.addEventListener("click", async () => {
        try {
          await postDecision(trialState.pendingDecision, {
            scores: { overall: parseInt(fbScore?.value || "5", 10) },
            freeform: (fbText?.value || "").trim(),
          });
          if (fbStatus) fbStatus.textContent = "已写入 feedback.jsonl";
          setTimeout(() => fbModal?.close(), 600);
        } catch (e) {
          if (fbStatus) fbStatus.textContent = e.message;
        }
      });
    }
    if (batchAccept) {
      batchAccept.addEventListener("click", async () => {
        const ids = [...trialState.wins];
        if (!ids.length) return;
        batchAccept.disabled = true;
        for (const runId of ids) {
          trialState.selectedRunId = runId;
          await postDecision("win");
        }
        runStatus.textContent = `批量 accept ${ids.length} 张`;
        trialState.wins.clear();
        updateBatchBtn();
        batchAccept.disabled = false;
      });
    }

    applyBootstrap();
    const tabParam = new URLSearchParams(window.location.search).get("tab");
    if (tabParam === "trial") {
      switchTab("trial");
    } else if (tabParam === "synthesis") {
      switchTab("synthesis");
    } else {
      setActiveTab("proposal");
      ensureVersionOption(4, "v4");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

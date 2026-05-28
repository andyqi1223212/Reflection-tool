(function () {
  const STORAGE_KEY = "agentflow-context-curator-v3";
  const rootData = window.AGENTFLOW_CONTEXT_CHUNKS;
  const legacyB = window.PIPELINE_B_CONTEXT_CHUNKS;

  if (!rootData?.pipelines && !legacyB?.chunks?.length) {
    document.body.innerHTML =
      "<p style='padding:2rem'>未加载 chunks.data.js。请在仓库根执行：<code>venv/bin/python3 tools/export_agentflow_context_chunks.py</code> 或运行 <code>bash ./start.sh</code></p>";
    return;
  }

  const PIPELINE_LABELS = {
    "pipeline-a-diagnose": "Pipeline A · 诊断",
    "pipeline-b-style": "Pipeline B · 风格化",
    judge: "Judge · 评分",
  };

  const RUNTIME_FN = {
    "pipeline-a-diagnose": "agents_runtime.agents.run_a",
    "pipeline-b-style": "agents_runtime.agents.run_b",
    judge: "agents_runtime.agents.run_judge",
  };

  const globalMeta = rootData?.meta || legacyB?.meta || {};
  const orchestrateFlow = rootData?.meta?.orchestrateFlow || [];

  let currentPipelineId =
    rootData?.defaultPipeline ||
    (legacyB ? "pipeline-b-style" : Object.keys(rootData?.pipelines || {})[0]);

  const STATUS_LABEL = {
    active: "正在使用",
    inactive: "已停用",
    forbidden: "禁止读取",
    reference: "可选参考",
  };

  const state = {
    selected: new Set(),
    activeTab: "combined",
    previewChunkId: null,
    search: "",
    highlightOverlap: true,
    filterActiveOnly: true,
  };

  const $ = (sel) => document.querySelector(sel);
  const pipelineSelect = $("#pipeline-select");
  const sidebar = $("#sidebar");
  const preview = $("#preview");
  const statsEl = $("#stats");
  const metaLine = $("#meta-line");
  const manifestPanel = $("#manifest-panel");
  const presetSelect = $("#preset-select");
  const crosscheckBanner = $("#crosscheck-banner");

  function pipelineData() {
    if (rootData?.pipelines?.[currentPipelineId]) {
      return rootData.pipelines[currentPipelineId];
    }
    if (currentPipelineId === "pipeline-b-style" && legacyB) {
      return legacyB;
    }
    return null;
  }

  function chunks() {
    const pd = pipelineData();
    return (pd?.chunks || []).slice().sort((a, b) => a.order - b.order);
  }

  function manifest() {
    return pipelineData()?.manifest || {};
  }

  function presets() {
    return pipelineData()?.presets || {};
  }

  function storageKey() {
    return `${STORAGE_KEY}:${currentPipelineId}`;
  }

  function loadSelection() {
    const list = chunks();
    const runtimePreset = presets().current_runtime;
    try {
      const raw = localStorage.getItem(storageKey());
      if (raw) {
        const ids = JSON.parse(raw);
        if (Array.isArray(ids) && ids.length) {
          const valid = ids.filter((id) => list.some((c) => c.id === id));
          if (valid.length) {
            state.selected = new Set(valid);
            return;
          }
        }
      }
    } catch (_) {
      /* ignore */
    }
    if (runtimePreset?.length) {
      state.selected = new Set(
        runtimePreset.filter((id) => list.some((c) => c.id === id))
      );
    } else {
      state.selected = new Set();
      list.forEach((c) => {
        if (c.defaultOn) state.selected.add(c.id);
      });
    }
  }

  function saveSelection() {
    localStorage.setItem(storageKey(), JSON.stringify([...state.selected]));
  }

  function fmt(n) {
    return n.toLocaleString("zh-CN");
  }

  function estTokens(chars) {
    return Math.round(chars / 1.8);
  }

  function selectedChunks() {
    return chunks().filter((c) => state.selected.has(c.id));
  }

  function runtimeDefaultChunks() {
    return chunks().filter((c) => c.status === "active");
  }

  function computeStats() {
    const sel = selectedChunks();
    const def = runtimeDefaultChunks();
    const sum = (list) => list.reduce((a, c) => a + c.chars, 0);
    const byLayer = (layer) => sum(sel.filter((c) => c.layer === layer));
    const sys = byLayer("system");
    const usr = byLayer("user");
    const total = sys + usr;
    const defTotal = sum(def);
    const measured = manifest().measuredChars || {};
    return {
      sel,
      sys,
      usr,
      total,
      defTotal,
      count: sel.length,
      measured,
    };
  }

  /** 预览 user 消息（近似 build_context；doc_section_set 以块合并展示） */
  function buildUserMessage(sel) {
    const m = manifest();
    const inputSpecs = m.activeInputs || [];
    const userChunks = sel
      .filter((c) => c.layer === "user")
      .sort((a, b) => a.order - b.order);
    const byInput = new Map();
    for (const c of userChunks) {
      const key = c.inputName || c.id;
      if (!byInput.has(key)) byInput.set(key, []);
      byInput.get(key).push(c);
    }
    const parts = [];
    for (const spec of inputSpecs) {
      const name = spec.name;
      if (!name) continue;
      const list = byInput.get(name);
      if (!list?.length) continue;
      parts.push(`# ${name}\n`);
      if (spec.type === "example_set" && list.length > 1) {
        parts.push(
          list
            .map((c) => c.content.trim())
            .join("\n\n---\n\n")
        );
      } else if (spec.type === "doc_section_set") {
        parts.push(
          list
            .map((c) => c.content)
            .join("\n\n")
        );
      } else {
        parts.push(list.map((c) => c.content).join(""));
      }
      parts.push("\n");
    }
    return parts.join("").replace(/\s+$/, "") + "\n";
  }

  function buildSystemMessage(sel) {
    return sel
      .filter((c) => c.layer === "system")
      .sort((a, b) => a.order - b.order)
      .map((c) => c.content)
      .join("");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function renderCrosscheckBanner() {
    const cc = manifest().crosscheck || {};
    const ok = cc.ok;
    const issues = cc.issues || [];
    const notes = cc.systemNotesTailChars
      ? ` · LLM system 另含 Notes 尾 ${fmt(cc.systemNotesTailChars)} 字（审阅块已截断）`
      : "";
    crosscheckBanner.className = ok ? "crosscheck ok" : "crosscheck warn";
    crosscheckBanner.innerHTML = ok
      ? `<strong>crosscheck OK</strong> — 导出块重组与 <code>build_context()</code> 一致${notes}`
      : `<strong>crosscheck 未通过</strong> — ${issues.map((i) => escapeHtml(i)).join("；")}`;
  }

  function renderManifest() {
    const m = manifest();
    const inputs = m.activeInputs || [];
    const forbidden = m.forbiddenInputs || [];
    const mc = m.measuredChars || {};
    const cc = m.crosscheck || {};
    const fn = RUNTIME_FN[currentPipelineId] || "build_context";

    let inputsHtml = inputs
      .map((inp) => {
        const src = inp.source ? `<code>${escapeHtml(inp.source)}</code>` : "—";
        const secs =
          inp.sections && inp.sections.length
            ? `<br/><span class="manifest-secs">章节: ${inp.sections.map((s) => escapeHtml(s)).join(" · ")}</span>`
            : inp.type === "doc_full"
              ? "<br/><span class='manifest-secs'>整文件</span>"
              : "";
        const desc = inp.description
          ? `<p class="manifest-desc">${escapeHtml(inp.description.slice(0, 160))}${inp.description.length > 160 ? "…" : ""}</p>`
          : "";
        return `<tr>
          <td><strong>${escapeHtml(inp.name)}</strong><br/><span class="manifest-type">${escapeHtml(inp.type || "")}</span></td>
          <td>${src}${secs}${desc}</td>
        </tr>`;
      })
      .join("");

    const forbHtml = forbidden
      .slice(0, 6)
      .map((line) => `<li>${escapeHtml(line.slice(0, 120))}${line.length > 120 ? "…" : ""}</li>`)
      .join("");
    const forbMore =
      forbidden.length > 6
        ? `<li class="muted">…共 ${forbidden.length} 条，见 prompt frontmatter</li>`
        : "";

    const flowHtml = orchestrateFlow.length
      ? `<ol class="orch-flow">${orchestrateFlow.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ol>`
      : "";

    manifestPanel.innerHTML = `
      <div class="manifest-head">
        <h2>当前 runtime（<code>${escapeHtml(fn)}</code>）</h2>
        <p class="manifest-ver">
          prompt <strong>${escapeHtml(m.promptVersion || "?")}</strong>
          · 源文件 <code>${escapeHtml(m.promptPath || "")}</code>
          · 导出 ${escapeHtml(globalMeta.generated_at_iso || globalMeta.generated_at || "")}
          · prompt 修改时间 ${escapeHtml(m.promptMtime || "")}
        </p>
        <p class="manifest-measured">
          实测 user（<code>build_context</code>）约 <strong>${fmt(mc.user || 0)}</strong> 字
          · system 审阅块 <strong>${fmt(mc.system || 0)}</strong> 字
          ${cc.measuredSystemRuntime ? ` · LLM 全量 system <strong>${fmt(cc.measuredSystemRuntime)}</strong> 字` : ""}
          · 合计约 <strong>${fmt(mc.total || 0)}</strong> 字 ≈ ${fmt(estTokens(mc.total || 0))} tok
        </p>
        ${flowHtml ? `<div class="manifest-orch"><h3>orchestrate 顺序</h3>${flowHtml}</div>` : ""}
      </div>
      <div class="manifest-grid">
        <div class="manifest-col">
          <h3>正在喂入的 inputs（${inputs.length} 项）</h3>
          <table class="manifest-table">
            <thead><tr><th>input</th><th>依赖文件 / 章节</th></tr></thead>
            <tbody>${inputsHtml}</tbody>
          </table>
        </div>
        <div class="manifest-col">
          <h3>禁止读取（forbidden）</h3>
          <ul class="manifest-forbidden">${forbHtml}${forbMore}</ul>
        </div>
      </div>
    `;
  }

  function renderStats() {
    const { sys, usr, total, defTotal, count, measured } = computeStats();
    const list = chunks();
    const saved = defTotal - total;
    const pct = defTotal ? Math.round((saved / defTotal) * 100) : 0;
    const drift =
      measured.total && Math.abs(total - measured.total) > 50 && count === runtimeDefaultChunks().length
        ? `<span class="stat warn">与实测差 ${fmt(Math.abs(total - measured.total))} 字（勾选与 runtime 不一致时正常）</span>`
        : "";
    statsEl.innerHTML = `
      <span class="stat">已选 <strong>${count}</strong> / ${list.length} 块（<strong>${runtimeDefaultChunks().length}</strong> 块正在使用）</span>
      <span class="stat">system <strong>${fmt(sys)}</strong> 字</span>
      <span class="stat">user <strong>${fmt(usr)}</strong> 字</span>
      <span class="stat">勾选合计 <strong>${fmt(total)}</strong> 字 (~${fmt(estTokens(total))} tok)</span>
      <span class="stat${saved > 0 ? " delta-save" : ""}">较「正在使用」默认 ${saved > 0 ? "省 " + fmt(saved) + " 字 (" + pct + "%)" : "持平"}</span>
      ${drift}
    `;
  }

  function chunkVisible(c) {
    if (state.filterActiveOnly && c.status !== "active") return false;
    if (!state.search) return true;
    const q = state.search.toLowerCase();
    return (
      c.label.toLowerCase().includes(q) ||
      c.id.toLowerCase().includes(q) ||
      c.group.toLowerCase().includes(q) ||
      (c.source || "").toLowerCase().includes(q) ||
      (c.inputName || "").toLowerCase().includes(q)
    );
  }

  function renderSidebar() {
    const list = chunks();
    const groups = new Map();
    for (const c of list) {
      if (!chunkVisible(c)) continue;
      if (!groups.has(c.group)) groups.set(c.group, []);
      groups.get(c.group).push(c);
    }
    sidebar.innerHTML = "";
    const sortedGroups = [...groups.entries()].sort((a, b) =>
      a[0].localeCompare(b[0], "zh")
    );
    for (const [group, glist] of sortedGroups) {
      const wrap = document.createElement("div");
      wrap.className = "group";
      const title = document.createElement("div");
      title.className = "group-title";
      title.textContent = group;
      wrap.appendChild(title);
      for (const c of glist) {
        const on = state.selected.has(c.id);
        const row = document.createElement("label");
        row.className = `chunk-row layer-${c.layer} status-${c.status} ${on ? "" : "off"} ${state.previewChunkId === c.id ? "selected-preview" : ""}`;
        row.dataset.id = c.id;
        const statusBadge = `<span class="badge badge-${c.status}">${escapeHtml(STATUS_LABEL[c.status] || c.status)}</span>`;
        const tags = (c.overlapTags || [])
          .map((t) => `<span class="tag">${escapeHtml(t)}</span>`)
          .join("");
        row.innerHTML = `
          <input type="checkbox" ${on ? "checked" : ""} data-id="${escapeHtml(c.id)}" />
          <span class="chunk-label">${escapeHtml(c.label)}</span>
          <span class="chunk-chars">${fmt(c.chars)}</span>
          <span class="chunk-meta">${statusBadge} · <code>${escapeHtml(c.source)}</code></span>
          ${c.note ? `<span class="chunk-note">${escapeHtml(c.note)}</span>` : ""}
          ${tags ? `<span class="tags">${tags}</span>` : ""}
        `;
        row.querySelector("input").addEventListener("change", (e) => {
          e.stopPropagation();
          if (e.target.checked) state.selected.add(c.id);
          else state.selected.delete(c.id);
          saveSelection();
          render();
        });
        row.addEventListener("click", (e) => {
          if (e.target.tagName === "INPUT") return;
          state.previewChunkId = c.id;
          state.activeTab = "detail";
          document.querySelectorAll(".tab").forEach((t) => {
            t.classList.toggle("active", t.dataset.tab === "detail");
          });
          render();
        });
        wrap.appendChild(row);
      }
      sidebar.appendChild(wrap);
    }
    if (!sidebar.innerHTML) {
      sidebar.innerHTML =
        '<p class="empty-hint">无匹配块。可关闭「只显示正在使用」或清空搜索。</p>';
    }
  }

  function renderPreview() {
    const sel = selectedChunks();
    const list = chunks();
    const tab = state.activeTab;
    preview.innerHTML = "";

    if (tab === "detail") {
      const c =
        list.find((x) => x.id === state.previewChunkId) || sel[0] || list[0];
      if (!c) {
        preview.innerHTML = '<p class="empty-hint">点击左侧某一块阅读全文</p>';
        return;
      }
      preview.appendChild(chunkCard(c, true));
      return;
    }

    if (!sel.length) {
      preview.innerHTML = '<p class="empty-hint">请至少勾选一块</p>';
      return;
    }

    if (tab === "system" || tab === "combined") {
      const sys = buildSystemMessage(sel);
      if (sys.trim()) {
        const sec = document.createElement("section");
        sec.className = "preview-section";
        sec.innerHTML = `<h2>system（${fmt(sys.length)} 字）</h2>`;
        const pre = document.createElement("pre");
        pre.textContent = sys;
        sec.appendChild(pre);
        preview.appendChild(sec);
      }
    }

    if (tab === "user" || tab === "combined") {
      const usr = buildUserMessage(sel);
      if (usr.trim()) {
        const sec = document.createElement("section");
        sec.className = "preview-section";
        sec.innerHTML = `<h2>user（${fmt(usr.length)} 字）</h2>`;
        const pre = document.createElement("pre");
        pre.textContent = usr;
        sec.appendChild(pre);
        preview.appendChild(sec);
      }
    }

    if (tab === "combined") {
      const cards = document.createElement("section");
      cards.className = "preview-section";
      cards.innerHTML = "<h2>分块原文</h2>";
      for (const c of sel.slice().sort((a, b) => a.order - b.order)) {
        cards.appendChild(chunkCard(c, false));
      }
      preview.appendChild(cards);
    }
  }

  function chunkCard(c, expanded) {
    const card = document.createElement("div");
    const hl = state.highlightOverlap && (c.overlapTags || []).length > 0;
    card.className = `chunk-card ${hl ? "overlap-hl" : ""}`;
    card.innerHTML = `
      <div class="chunk-card-head">
        <span>${escapeHtml(c.label)} <span class="badge badge-${c.status}">${escapeHtml(STATUS_LABEL[c.status] || "")}</span></span>
        <span>${fmt(c.chars)} 字 · ${c.layer}</span>
      </div>
    `;
    const body = document.createElement("div");
    body.className = "chunk-card-body";
    const pre = document.createElement("pre");
    pre.textContent = c.content;
    body.appendChild(pre);
    if (!expanded) body.style.maxHeight = "220px";
    card.appendChild(body);
    return card;
  }

  function render() {
    renderCrosscheckBanner();
    renderStats();
    renderSidebar();
    renderPreview();
  }

  function applyPreset(name) {
    const ids = presets()[name];
    if (!ids) return;
    state.selected = new Set(
      ids.filter((id) => chunks().some((c) => c.id === id))
    );
    saveSelection();
    render();
  }

  function initPresets() {
    const labels = {
      current_runtime: "当前 runtime（与 agents_runtime 一致）",
      v2_1_legacy_estimate: "v2.1 旧装配估算",
      minimal_core: "极简试验集",
    };
    const keys = Object.keys(presets());
    presetSelect.innerHTML = keys
      .map(
        (k) =>
          `<option value="${escapeHtml(k)}">${escapeHtml(labels[k] || k)}</option>`
      )
      .join("");
  }

  function initPipelineSelect() {
    const ids = rootData?.pipelines
      ? Object.keys(rootData.pipelines)
      : ["pipeline-b-style"];
    pipelineSelect.innerHTML = ids
      .map(
        (id) =>
          `<option value="${escapeHtml(id)}">${escapeHtml(PIPELINE_LABELS[id] || id)}</option>`
      )
      .join("");
    pipelineSelect.value = currentPipelineId;
    pipelineSelect.addEventListener("change", () => {
      currentPipelineId = pipelineSelect.value;
      state.previewChunkId = null;
      loadSelection();
      renderManifest();
      initPresets();
      render();
    });
  }

  function updateMetaLine() {
    const pd = pipelineData();
    const active = (pd?.chunks || []).filter((c) => c.status === "active").length;
    const total = (pd?.chunks || []).length;
    const allOk = globalMeta.crosscheckAllOk ? " · 全部 crosscheck OK" : "";
    metaLine.textContent = `${PIPELINE_LABELS[currentPipelineId] || currentPipelineId} · ${active} 块正在使用 / 共 ${total} 块${allOk}`;
  }

  function onPipelineReady() {
    updateMetaLine();
    renderManifest();
    renderCrosscheckBanner();
    loadSelection();
    initPresets();
    render();
  }

  initPipelineSelect();
  onPipelineReady();

  $("#btn-apply-preset").addEventListener("click", () => {
    applyPreset(presetSelect.value);
  });
  $("#btn-default-on").addEventListener("click", () => {
    applyPreset("current_runtime");
  });
  $("#btn-all-on").addEventListener("click", () => {
    state.selected = new Set(chunks().map((c) => c.id));
    saveSelection();
    render();
  });
  $("#btn-all-off").addEventListener("click", () => {
    state.selected = new Set();
    saveSelection();
    render();
  });
  $("#filter-active-only").addEventListener("change", (e) => {
    state.filterActiveOnly = e.target.checked;
    renderSidebar();
  });
  $("#btn-export-json").addEventListener("click", () => {
    const { sys, usr, total } = computeStats();
    const out = {
      exported_at: new Date().toISOString(),
      pipeline_id: currentPipelineId,
      prompt_version: manifest().promptVersion,
      selected_ids: [...state.selected],
      stats: { system_chars: sys, user_chars: usr, total_chars: total },
      manifest_active_inputs: (manifest().activeInputs || []).map((i) => i.name),
      chunks: selectedChunks().map((c) => ({
        id: c.id,
        status: c.status,
        label: c.label,
        layer: c.layer,
        chars: c.chars,
      })),
    };
    const blob = new Blob([JSON.stringify(out, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `agentflow-context-${currentPipelineId}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  });
  $("#btn-copy-preview").addEventListener("click", async () => {
    const sel = selectedChunks();
    const usr = buildUserMessage(sel);
    const text =
      "=== SYSTEM ===\n\n" +
      buildSystemMessage(sel) +
      "\n\n=== USER ===\n\n" +
      usr;
    try {
      await navigator.clipboard.writeText(text);
      $("#btn-copy-preview").textContent = "已复制";
      setTimeout(() => {
        $("#btn-copy-preview").textContent = "复制预览";
      }, 1500);
    } catch {
      alert("复制失败，请从预览区手动选择");
    }
  });
  $("#chunk-search").addEventListener("input", (e) => {
    state.search = e.target.value.trim();
    renderSidebar();
  });
  $("#highlight-overlap").addEventListener("change", (e) => {
    state.highlightOverlap = e.target.checked;
    renderPreview();
  });
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeTab = btn.dataset.tab;
      document.querySelectorAll(".tab").forEach((t) => {
        t.classList.toggle("active", t === btn);
      });
      renderPreview();
    });
  });
})();

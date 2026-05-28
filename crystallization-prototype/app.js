(function () {
  "use strict";

  const PATTERNS = [
    "P-EVAL",
    "P-OVER",
    "P-SPIRAL",
    "P-EFF",
    "P-UNDER",
    "P-EXIST",
    "P-KNOW-DO",
    "P-FAMILY",
  ];

  const AXES = [
    { id: "judgment", label: "judgment · 判决外包 / 愧疚" },
    { id: "attention", label: "attention · 自我架构 / 偷算力" },
  ];

  const STORAGE_USAGE = "ic_last_used_v0";
  /** 每张卡个人笔记，仅本机 localStorage，不参与 export */
  const STORAGE_NOTES = "ic_card_notes_v0";
  const NOTE_PREVIEW_CHARS = 28;
  const NOTE_SAVE_DEBOUNCE_MS = 400;

  /** @type {{ chains: object[], meta?: object }} */
  const boot = window.__CHAINS_BOOTSTRAP__;
  if (!boot || !Array.isArray(boot.chains)) {
    document.getElementById("results").innerHTML =
      '<p class="empty-hint">缺少 chains.data.js：请在仓库根目录运行 <code>venv/bin/python3 tools/export_v3_chains.py</code> 后刷新。</p>';
    return;
  }

  const allChains = boot.chains;
  const selectedPatterns = new Set();
  const selectedAxes = new Set();
  const selectedCards = new Set();

  function loadUsage() {
    try {
      const raw = localStorage.getItem(STORAGE_USAGE);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  }

  function saveUsage(map) {
    try {
      localStorage.setItem(STORAGE_USAGE, JSON.stringify(map));
    } catch (_) {}
  }

  function touchUsage(ids) {
    const map = loadUsage();
    const now = Date.now();
    for (const id of ids) map[id] = now;
    saveUsage(map);
  }

  function lastUsedOf(id) {
    const map = loadUsage();
    return map[id] || 0;
  }

  function loadAllNotes() {
    try {
      const raw = localStorage.getItem(STORAGE_NOTES);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  }

  function getNote(id) {
    const all = loadAllNotes();
    const v = all[id];
    return typeof v === "string" ? v : "";
  }

  function setNote(id, text) {
    try {
      const all = loadAllNotes();
      const t = text.trim();
      if (t) all[id] = text;
      else delete all[id];
      localStorage.setItem(STORAGE_NOTES, JSON.stringify(all));
    } catch (_) {}
  }

  function notePreview(text) {
    const t = text.trim().replace(/\s+/g, " ");
    if (!t) return "";
    if (t.length <= NOTE_PREVIEW_CHARS) return t;
    return t.slice(0, NOTE_PREVIEW_CHARS) + "…";
  }

  function tokenizeQuery(q) {
    const s = q.trim();
    if (!s) return [];
    const tokens = [];
    const seen = new Set();
    const words = s.match(/[a-zA-Z]{2,}/g);
    if (words) {
      for (const w of words) {
        const t = w.toLowerCase();
        if (!seen.has(t)) {
          seen.add(t);
          tokens.push(t);
        }
      }
    }
    for (const ch of s) {
      if (/[\u4e00-\u9fff]/.test(ch) && !seen.has(ch)) {
        seen.add(ch);
        tokens.push(ch);
      }
    }
    return tokens;
  }

  function scoreHaystack(hay, tokens) {
    if (!tokens.length) return 0;
    const hayLower = hay.toLowerCase();
    let n = 0;
    for (const t of tokens) {
      if (/[\u4e00-\u9fff]/.test(t)) {
        if (hay.includes(t)) n++;
      } else if (hayLower.includes(t)) n++;
    }
    return n;
  }

  function keywordScoreBase(chain, tokens) {
    const hay = [
      chain.title,
      chain.crystallization.mechanism,
      chain.crystallization.anchor,
      chain.chain.trigger,
    ].join("\n");
    return scoreHaystack(hay, tokens);
  }

  function updateKeywordScore(chain, tokens) {
    if (!chain.updates || !chain.updates.length) return 0;
    const parts = [];
    for (const u of chain.updates) {
      parts.push(u.patch_reasoning || "");
      const cry = u.crystallization;
      if (cry) {
        parts.push(cry.mechanism || "", cry.anchor || "");
        (cry.micro_steps || []).forEach((s) => parts.push(s));
      }
      (u.patterns_added || []).forEach((p) => parts.push(p));
      (u.source_refs_added || []).forEach((s) => parts.push(s));
      (u.questions_appended || []).forEach((s) => parts.push(s));
      parts.push(u.trigger_addendum || "");
    }
    return scoreHaystack(parts.join("\n"), tokens);
  }

  function keywordScore(chain, tokens) {
    return keywordScoreBase(chain, tokens) + updateKeywordScore(chain, tokens);
  }

  function patternOverlap(chain) {
    if (!selectedPatterns.size) return 0;
    return chain.patterns.filter((p) => selectedPatterns.has(p)).length;
  }

  function passesFilters(chain) {
    if (selectedAxes.size && !selectedAxes.has(chain.axis)) return false;
    if (selectedPatterns.size && patternOverlap(chain) === 0) return false;
    return true;
  }

  /**
   * 浏览模式：搜索框为空且未选任何 pattern / axis chip → 展示全部卡（目录态）。
   * 一旦有关键词或任一 chip：只展示通过硬过滤的卡，并按 tag / 关键词 / 最近展开 排序（仍展示全部命中）。
   */
  function rankChains(queryRaw) {
    const query = queryRaw.trim();
    const tokens = tokenizeQuery(query);
    const hasKeyword = tokens.length > 0;
    const hasChipFilter =
      selectedPatterns.size > 0 || selectedAxes.size > 0;
    const browseCatalog = !hasKeyword && !hasChipFilter;

    const rows = [];
    for (const chain of allChains) {
      if (!passesFilters(chain)) continue;
      const tagScore = patternOverlap(chain);
      const hasKeyword = tokens.length > 0;
      const upKw = updateKeywordScore(chain, tokens);
      const kw = keywordScore(chain, tokens);
      const expandUpdates = hasKeyword && upKw > 0;
      const lastUsed = lastUsedOf(chain.id);
      rows.push({ chain, tagScore, kw, expandUpdates, lastUsed });
    }

    if (browseCatalog) {
      rows.sort((a, b) => a.chain.id.localeCompare(b.chain.id));
      return rows;
    }

    rows.sort((a, b) => {
      if (b.tagScore !== a.tagScore) return b.tagScore - a.tagScore;
      if (b.kw !== a.kw) return b.kw - a.kw;
      if (b.lastUsed !== a.lastUsed) return b.lastUsed - a.lastUsed;
      return a.chain.id.localeCompare(b.chain.id);
    });
    return rows;
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function renderChips() {
    const pc = document.getElementById("pattern-chips");
    const ac = document.getElementById("axis-chips");
    pc.innerHTML = "";
    ac.innerHTML = "";
    for (const p of PATTERNS) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip" + (selectedPatterns.has(p) ? " on" : "");
      b.textContent = p;
      b.dataset.pattern = p;
      b.addEventListener("click", () => {
        if (selectedPatterns.has(p)) selectedPatterns.delete(p);
        else selectedPatterns.add(p);
        renderChips();
        refresh();
      });
      pc.appendChild(b);
    }
    for (const ax of AXES) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip" + (selectedAxes.has(ax.id) ? " on" : "");
      b.textContent = ax.label;
      b.dataset.axis = ax.id;
      b.addEventListener("click", () => {
        if (selectedAxes.has(ax.id)) selectedAxes.delete(ax.id);
        else selectedAxes.add(ax.id);
        renderChips();
        refresh();
      });
      ac.appendChild(b);
    }
  }

  function renderCards(rows) {
    const root = document.getElementById("results");
    root.innerHTML = "";
    if (!rows.length) {
      root.innerHTML =
        '<p class="empty-hint">没有匹配的卡：试着清空搜索框、取消全部标签，或换几个关键词。</p>';
      return;
    }

    for (const { chain: c, expandUpdates } of rows) {
      const art = document.createElement("article");
      art.className = "card";
      art.dataset.id = c.id;

      const head = document.createElement("div");
      head.className = "card-head";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = selectedCards.has(c.id);
      cb.setAttribute("aria-label", "选中以加入 Context Pack");
      cb.addEventListener("click", (e) => e.stopPropagation());
      cb.addEventListener("change", () => {
        if (cb.checked) selectedCards.add(c.id);
        else selectedCards.delete(c.id);
        updateDock();
      });

      const meta = document.createElement("div");
      meta.className = "card-meta";
      meta.textContent = `${c.id} · ${c.patterns.join(" · ")} · ${c.axis}`;

      const fbSum =
        window.IcFeedback && window.IcFeedback.getSummaryMap
          ? window.IcFeedback.getSummaryMap()[c.id]
          : null;
      const fbBadge =
        fbSum && window.IcFeedback
          ? window.IcFeedback.makeSummaryBadge(fbSum)
          : null;

      head.appendChild(cb);
      head.appendChild(meta);
      if (fbBadge) head.appendChild(fbBadge);

      const front = document.createElement("div");
      front.className = "card-front";

      const crystal = document.createElement("div");
      crystal.className = "card-crystal";
      crystal.innerHTML = `
        <p class="mechanism">${esc(c.crystallization.mechanism)}</p>
        <p class="anchor">${esc(c.crystallization.anchor)}</p>
        <ol class="micro-steps">
          ${c.crystallization.micro_steps.map((s) => `<li>${esc(s)}</li>`).join("")}
        </ol>
        <p class="expand-hint">点上方晶体区展开 Trigger / 追问路径</p>
      `;

      const savedNote = getNote(c.id);
      const details = document.createElement("details");
      details.className = "card-note";

      const summary = document.createElement("summary");
      summary.className = "card-note-summary";
      const label = document.createElement("span");
      label.className = "card-note-summary-label";
      label.textContent = "我的笔记";
      const preview = document.createElement("span");
      preview.className = "card-note-preview";
      preview.textContent = savedNote.trim()
        ? ` · ${notePreview(savedNote)}`
        : "（仅保存在本机，点开展开）";
      summary.appendChild(label);
      summary.appendChild(preview);

      const ta = document.createElement("textarea");
      ta.className = "card-note-input";
      ta.rows = 3;
      ta.maxLength = 4000;
      ta.setAttribute("aria-label", `${c.id} 个人笔记`);
      ta.placeholder =
        "当下一句、日期、或提醒自己的事…不写也完全不影响卡片内容。";
      ta.value = savedNote;

      let saveTimer = null;
      const syncPreview = () => {
        const t = ta.value.trim();
        preview.textContent = t ? ` · ${notePreview(ta.value)}` : "（仅保存在本机，点开展开）";
      };

      const scheduleSave = () => {
        if (saveTimer) clearTimeout(saveTimer);
        saveTimer = setTimeout(() => {
          saveTimer = null;
          setNote(c.id, ta.value);
          syncPreview();
        }, NOTE_SAVE_DEBOUNCE_MS);
      };

      ta.addEventListener("input", () => {
        scheduleSave();
        syncPreview();
      });
      ta.addEventListener("blur", () => {
        if (saveTimer) clearTimeout(saveTimer);
        saveTimer = null;
        setNote(c.id, ta.value);
        syncPreview();
      });
      ta.addEventListener("click", (e) => e.stopPropagation());

      summary.addEventListener("click", (e) => e.stopPropagation());

      details.appendChild(summary);
      details.appendChild(ta);
      details.addEventListener("click", (e) => e.stopPropagation());
      details.addEventListener("toggle", () => {
        if (details.open) {
          requestAnimationFrame(() => ta.focus());
        } else {
          if (saveTimer) clearTimeout(saveTimer);
          saveTimer = null;
          setNote(c.id, ta.value);
          syncPreview();
        }
      });

      front.appendChild(crystal);
      front.appendChild(details);

      if (window.IcFeedback) {
        const fbWrap = document.createElement("div");
        fbWrap.className = "card-feedback-wrap";
        window.IcFeedback.mountFeedbackForm(fbWrap, {
          targetType: "card",
          targetId: c.id,
          summary: fbSum,
        });
        front.appendChild(fbWrap);
      }

      if (c.updates && c.updates.length > 0) {
        const updRoot = document.createElement("details");
        updRoot.className = "card-updates";
        if (expandUpdates) updRoot.open = true;
        const usum = document.createElement("summary");
        usum.className = "card-updates-summary";
        usum.textContent = `更新历史 (${c.updates.length})`;
        updRoot.appendChild(usum);
        const ulist = document.createElement("div");
        ulist.className = "card-updates-body";
        for (const u of c.updates) {
          const sub = document.createElement("div");
          sub.className = "update-entry";

          const dt = document.createElement("p");
          dt.className = "update-entry-date";
          dt.textContent = `更新 ${u.updated_at || ""}`;
          sub.appendChild(dt);

          if (u.patch_reasoning) {
            const pr = document.createElement("blockquote");
            pr.className = "update-patch-reasoning";
            pr.textContent = u.patch_reasoning;
            sub.appendChild(pr);
          }

          const cry = u.crystallization || {};
          const hasCrystal =
            cry.mechanism || cry.anchor || (cry.micro_steps && cry.micro_steps.length);
          if (hasCrystal) {
            const uc = document.createElement("div");
            uc.className = "update-crystal";
            if (cry.mechanism) {
              const pm = document.createElement("p");
              pm.className = "mechanism";
              pm.textContent = cry.mechanism;
              uc.appendChild(pm);
            }
            if (cry.anchor) {
              const pa = document.createElement("p");
              pa.className = "anchor";
              pa.textContent = cry.anchor;
              uc.appendChild(pa);
            }
            if (cry.micro_steps && cry.micro_steps.length) {
              const ol = document.createElement("ol");
              ol.className = "micro-steps";
              for (const step of cry.micro_steps) {
                const li = document.createElement("li");
                li.textContent = step;
                ol.appendChild(li);
              }
              uc.appendChild(ol);
            }
            sub.appendChild(uc);
          }

          const hasDelta =
            (u.patterns_added && u.patterns_added.length) ||
            (u.source_refs_added && u.source_refs_added.length) ||
            (u.questions_appended && u.questions_appended.length) ||
            u.trigger_addendum;
          if (hasDelta) {
            const delta = document.createElement("div");
            delta.className = "update-delta-panel";

            if (u.trigger_addendum) {
              const lb = document.createElement("p");
              lb.className = "chain-label";
              lb.textContent = "trigger 补充";
              delta.appendChild(lb);
              const tr = document.createElement("p");
              tr.className = "chain-trigger";
              tr.textContent = u.trigger_addendum;
              delta.appendChild(tr);
            }

            if (u.questions_appended && u.questions_appended.length) {
              const lb = document.createElement("p");
              lb.className = "chain-label";
              lb.textContent = "追加问题";
              delta.appendChild(lb);
              const uq = document.createElement("ul");
              uq.className = "chain-questions";
              for (const q of u.questions_appended) {
                const li = document.createElement("li");
                li.textContent = q;
                uq.appendChild(li);
              }
              delta.appendChild(uq);
            }

            if (u.patterns_added && u.patterns_added.length) {
              const lb = document.createElement("p");
              lb.className = "chain-label";
              lb.textContent = "新增 Pattern tags";
              delta.appendChild(lb);
              const row = document.createElement("p");
              row.className = "update-chip-row";
              for (const pat of u.patterns_added) {
                const sp = document.createElement("span");
                sp.className = "chip chip-added";
                sp.textContent = pat;
                row.appendChild(sp);
              }
              delta.appendChild(row);
            }

            if (u.source_refs_added && u.source_refs_added.length) {
              const lb = document.createElement("p");
              lb.className = "chain-label";
              lb.textContent = "新增 source refs";
              delta.appendChild(lb);
              const tr = document.createElement("p");
              tr.className = "chain-trigger";
              tr.textContent = u.source_refs_added.join(" · ");
              delta.appendChild(tr);
            }

            sub.appendChild(delta);
          }

          ulist.appendChild(sub);
        }
        updRoot.appendChild(ulist);
        updRoot.addEventListener("click", (e) => e.stopPropagation());
        front.appendChild(updRoot);
      }

      const panel = document.createElement("div");
      panel.className = "chain-panel";
      const qs = c.chain.questions.map((q) => `<li>${esc(q)}</li>`).join("");
      panel.innerHTML = `
        <p class="chain-label">Trigger</p>
        <p class="chain-trigger">${esc(c.chain.trigger)}</p>
        <p class="chain-label">我当时问的</p>
        <ul class="chain-questions">${qs}</ul>
        ${
          c.source_refs && c.source_refs.length
            ? `<p class="chain-label">素材出处</p><p class="chain-trigger">${esc(c.source_refs.join(" · "))}</p>`
            : ""
        }
      `;

      crystal.addEventListener("click", () => {
        const opening = !art.classList.contains("expanded");
        art.classList.toggle("expanded");
        if (opening) touchUsage([c.id]);
      });

      art.appendChild(head);
      art.appendChild(front);
      art.appendChild(panel);
      root.appendChild(art);
    }
  }

  function updateDock() {
    const n = selectedCards.size;
    const countEl = document.getElementById("selection-count");
    const btn = document.getElementById("copy-md");
    countEl.textContent = n ? `已选 ${n} 条` : "未选中卡片";
    btn.disabled = n === 0;
  }

  function buildMarkdown() {
    const ids = [...selectedCards].sort();
    const chains = ids
      .map((id) => allChains.find((c) => c.id === id))
      .filter(Boolean);
    const axes = [...new Set(chains.map((c) => c.axis))].sort();
    const patterns = [...new Set(chains.flatMap((c) => c.patterns))].sort();

    let md = `# Context Pack：${axes.join(" + ")}，patterns：${patterns.join(" · ")}\n\n`;

    for (const c of chains) {
      const steps = c.crystallization.micro_steps
        .map((s, i) => `${i + 1}. ${s}`)
        .join("\n");
      const qs = c.chain.questions.map((q) => `- ${q}`).join("\n");
      const refs =
        c.source_refs && c.source_refs.length
          ? c.source_refs.join("，")
          : "（未标注）";

      md += `## ${c.id}：${c.title}\n\n`;
      md += `机制：${c.crystallization.mechanism}\n\n`;
      md += `入口句：${c.crystallization.anchor}\n\n`;
      md += `小动作：\n${steps}\n\n`;
      md += `Trigger：${c.chain.trigger}\n\n`;
      md += `我当时问的：\n${qs}\n\n`;
      md += `素材出处：${refs}\n\n`;
      const myNote = getNote(c.id).trim();
      if (myNote) {
        md += `我的记录：\n${myNote}\n\n`;
      }
      md += `---\n\n`;
    }

    const focus = document.getElementById("focus-note").value.trim();
    if (focus) {
      md += `## 这次请重点帮我\n\n${focus}\n`;
    }

    return md;
  }

  async function copyMd() {
    const md = buildMarkdown();
    const status = document.getElementById("copy-status");
    status.textContent = "";
    try {
      await navigator.clipboard.writeText(md);
      status.textContent = "已复制到剪贴板，可直接粘贴到 Gemini。";
    } catch {
      status.textContent =
        "剪贴板不可用：请用 localhost 打开页面，或手动全选下方导出区。";
      prompt("复制以下内容：", md);
    }
  }

  function refresh() {
    const q = document.getElementById("trigger-input").value;
    renderCards(rankChains(q));
    updateDock();
  }

  document.getElementById("trigger-input").addEventListener("input", refresh);
  document.getElementById("trigger-input").addEventListener("search", refresh);
  document.getElementById("copy-md").addEventListener("click", copyMd);

  renderChips();
  refresh();
})();

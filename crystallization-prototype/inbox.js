(function () {
  "use strict";

  const SCORE_LABELS = [
    ["mechanism", "mechanism"],
    ["anchor", "anchor"],
    ["micro_steps", "micro_steps"],
    ["axis_pattern_consistency", "axis_pattern"],
    ["anchor_mechanism_consistency", "anchor↔mech"],
    ["landing_pad_pairing", "landing_pad"],
  ];

  const VERDICT_CHIPS = [
    { id: "all", label: "All" },
    { id: "fail", label: "verdict=fail" },
    { id: "conditional_pass", label: "verdict=conditional_pass" },
    { id: "error", label: "error" },
  ];

  const ARTIFACT_ORDER = [
    "manifest",
    "a",
    "b",
    "judge",
    "push",
    "route_helper",
    "input",
  ];

  const SEARCH_DEBOUNCE_MS = 150;

  const FEEDBACK_SUMMARY =
    typeof window.FEEDBACK_SUMMARY === "object" && window.FEEDBACK_SUMMARY
      ? window.FEEDBACK_SUMMARY
      : {};

  const STATE = {
    runs: Array.isArray(window.RUN_INDEX) ? window.RUN_INDEX : [],
    search: "",
    verdictFilter: "all",
  };

  let searchTimer = null;

  const $ = (sel) => document.querySelector(sel);

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatRelative(iso) {
    if (!iso) return "(unknown)";
    const t = Date.parse(iso);
    if (Number.isNaN(t)) return iso;
    const diff = Date.now() - t;
    const sec = Math.floor(diff / 1000);
    if (sec < 60) return "刚刚";
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min} 分钟前`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr} 小时前`;
    const day = Math.floor(hr / 24);
    if (day === 1) return "昨天";
    if (day < 7) return `${day} 天前`;
    return iso.slice(0, 16).replace("T", " ");
  }

  function filterMatches(run) {
    const q = STATE.search;
    if (q) {
      const blob = [
        run.run_id,
        run.question_md,
        run.question_basename,
        run.b_title,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      if (!blob.includes(q)) return false;
    }
    if (STATE.verdictFilter === "all") return true;
    if (STATE.verdictFilter === "error") return !!run.is_error;
    return (run.verdict || "") === STATE.verdictFilter;
  }

  function cardVerdictClass(run) {
    if (run.is_error) return "verdict-error";
    const v = run.verdict || "unknown";
    return `verdict-${v.replace(/[^a-z_]/gi, "_")}`;
  }

  function findRun(runId) {
    return STATE.runs.find((r) => r.run_id === runId);
  }

  function buildAcceptCommand(run) {
    const base = `python -m agents_runtime.orchestrate --resume ${run.run_id} --from push`;
    const v = run.verdict;
    if (v === "pass" && !run.is_error) return base;
    if (v === "conditional_pass" || v === "fail") return `${base} --force-pass`;
    return base;
  }

  function describeMerge(run) {
    const mode = run.merge_mode || "new";
    const kind = run.output_kind || "full_card";
    const target = run.b_target_ic_id || run.target_ic_id;
    if (mode === "update" && target) {
      return `merge --mode update，向 v3 中 ${target} 追加一条 update_entry（不覆盖原 mechanism/anchor）。`;
    }
    if (mode === "meta") {
      const kids =
        run.artifacts?.b?.meta_relation?.child_ic_ids?.join(", ") || "（见 b.json）";
      return `merge --mode meta，新建元锚卡并链接子卡：${kids}。`;
    }
    return `merge --mode new，分配新 IC id，在 v3 md 插入一张 full_card。`;
  }

  function acceptExplainer(run) {
    const lines = [
      "【inbox 不会替你执行】下面命令需你在仓库根终端粘贴运行。",
      `【将执行】仅 push 阶段 → ${describeMerge(run)}`,
      `【B 形态】output_kind=${run.output_kind || "?"}，标题：${run.b_title || "—"}`,
    ];
    const v = run.verdict;
    if (v === "pass" && !run.is_error) {
      lines.push("【force-pass】不需要（Judge 已是 pass）。");
    } else if (v === "conditional_pass" || v === "fail") {
      lines.push(
        "【force-pass】会写入 judge.accepted.json 再 merge（人审覆写闸门）。"
      );
    }
    if (run.is_error && run.push_result?.status) {
      lines.push(
        `【上次 push 失败】${run.push_result.status} — 修好后重跑 push 即可。`
      );
    }
    if (run.question_basename?.includes("球场") || run.question_basename?.includes("垃圾话")) {
      lines.push(
        "【注意】球场垃圾话场景很可能已在 chat 里 merge 为 IC-024。若 v3 已有同场景卡，accept 会 exit 4（md_collision）——此时应 reject 本 run，勿重复入库。"
      );
    }
    lines.push("【跑完后】再执行 python runs/_index.py 并 refresh 本页。");
    return lines;
  }

  function rejectExplainer(run) {
    return [
      "【inbox 不会替你执行】下面 mv 需你在仓库根终端粘贴。",
      "【不会】调用 API、不会 merge、不会改 inquiry-chain-demo-v3-good-answer.md 或 chains.json。",
      `【只会】把 runs/${run.run_id}/ 挪到 runs/_rejected/${run.run_id}/（可手动挪回）。`,
      "适合：已 chat 入库、或判定本 run 作废、或 duplicate 不想重 merge。",
      "【跑完后】python runs/_index.py + refresh 本页。",
    ];
  }

  function renderVerdictChips() {
    const row = $("#verdict-chips");
    if (!row) return;
    row.innerHTML = "";
    for (const chip of VERDICT_CHIPS) {
      const b = document.createElement("button");
      b.type = "button";
      b.className =
        "chip" + (STATE.verdictFilter === chip.id ? " on" : "");
      b.textContent = chip.label;
      b.dataset.filter = chip.id;
      b.addEventListener("click", () => {
        STATE.verdictFilter = chip.id;
        renderVerdictChips();
        renderList();
      });
      row.appendChild(b);
    }
  }

  function renderScoresTable(scores) {
    const rows = SCORE_LABELS.map(([key, label]) => {
      const val = scores && scores[key];
      const display =
        val === null || val === undefined ? "—" : String(val);
      return `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(display)}</td></tr>`;
    }).join("");
    return `<table class="scores-table"><tbody>${rows}</tbody></table>`;
  }

  function renderListItems(list, title) {
    if (!list || !list.length) {
      return `<p class="muted">${escapeHtml(title)}：无</p>`;
    }
    const items = list.map((x) => `<li>${escapeHtml(x)}</li>`).join("");
    return `<p class="muted">${escapeHtml(title)}</p><ul class="${title.includes("fail") ? "fail-list" : "revision-list"}">${items}</ul>`;
  }

  function renderArtifactBlock(name, data) {
    if (data === undefined || data === null) {
      return `<details class="artifact-block missing"><summary>${escapeHtml(name)}.json（无）</summary></details>`;
    }
    let text;
    try {
      text = JSON.stringify(data, null, 2);
    } catch {
      text = String(data);
    }
    return `<details class="artifact-block">
      <summary>${escapeHtml(name)}.json</summary>
      <pre class="artifact-json"><code>${escapeHtml(text)}</code></pre>
    </details>`;
  }

  function renderArtifacts(run) {
    const arts = run.artifacts || {};
    const parts = ARTIFACT_ORDER.map((name) =>
      renderArtifactBlock(name, arts[name])
    ).join("");
    return `<div class="artifact-panel">${parts}</div>`;
  }

  function renderRunCard(run) {
    const card = document.createElement("article");
    card.className = `run-card ${cardVerdictClass(run)}`;

    const title =
      run.question_basename || run.question_md || "(unknown)";
    const route = run.route || "(unknown)";
    const axis = run.axis || "(unknown)";
    const target = run.target_ic_id
      ? ` · ${run.target_ic_id}`
      : "";
    const kindLine = run.output_kind
      ? ` · B=${run.output_kind}`
      : "";

    const fbSum = FEEDBACK_SUMMARY[run.run_id];
    const fbBadge =
      fbSum && window.IcFeedback
        ? window.IcFeedback.makeSummaryBadge(fbSum)
        : null;

    card.innerHTML = `
      <div class="run-card-head">
        <div class="run-card-head-top">
          <span class="status-badge">${escapeHtml(run.status || "awaiting_human")}</span>
          <span class="verdict-badge verdict-${escapeHtml((run.verdict || "unknown").replace(/\s/g, "_"))}">${escapeHtml(run.verdict || "unknown")}</span>
          ${run.is_error ? '<span class="verdict-badge verdict-error">error</span>' : ""}
          <span class="run-fb-summary-slot"></span>
        </div>
        <h2 title="${escapeHtml(run.question_md || "")}">${escapeHtml(title)}</h2>
        <p class="route-line">route=${escapeHtml(route)} · axis=${escapeHtml(axis)}${escapeHtml(target)}${escapeHtml(kindLine)}</p>
        ${run.b_title ? `<p class="b-title muted">B 标题：${escapeHtml(run.b_title)}</p>` : ""}
        <div class="run-meta">
          <code class="run-id">${escapeHtml(run.run_id)}</code>
          <time datetime="${escapeHtml(run.created_at || "")}" title="${escapeHtml(run.created_at || "")}">${escapeHtml(formatRelative(run.created_at))}</time>
        </div>
      </div>
      <details class="run-review">
        <summary>审阅：scores / 修订建议 / 源 JSON（a · b · judge · manifest…）</summary>
        ${renderScoresTable(run.scores)}
        ${renderListItems(run.fail_reasons, "fail_reasons")}
        ${renderListItems(run.suggested_revisions, "suggested_revisions")}
        ${run.next_action ? `<p class="muted">next_action: ${escapeHtml(run.next_action)}</p>` : ""}
        ${run.push_result ? `<p class="muted">push_result: ${escapeHtml(JSON.stringify(run.push_result))}</p>` : ""}
        ${renderArtifacts(run)}
      </details>
      <div class="run-actions">
        <button type="button" class="accept" data-run="${escapeHtml(run.run_id)}">accept（复制入库命令）</button>
        <button type="button" class="reject" data-run="${escapeHtml(run.run_id)}">reject（复制归档命令）</button>
      </div>
      <div class="run-feedback-slot"></div>
    `;

    const summarySlot = card.querySelector(".run-fb-summary-slot");
    if (summarySlot && fbBadge) summarySlot.appendChild(fbBadge);

    const fbSlot = card.querySelector(".run-feedback-slot");
    if (fbSlot && window.IcFeedback) {
      window.IcFeedback.mountFeedbackForm(fbSlot, {
        targetType: "run",
        targetId: run.run_id,
        summary: fbSum,
      });
    }
    return card;
  }

  function renderList() {
    const root = $("#run-list");
    if (!root) return;
    const filtered = STATE.runs.filter(filterMatches);
    root.innerHTML = "";
    if (!filtered.length) {
      root.innerHTML =
        '<p class="muted empty-inbox">无匹配 run。可清空搜索/过滤，或先跑 <code>python runs/_index.py</code> 再 refresh。</p>';
      return;
    }
    for (const run of filtered) {
      root.appendChild(renderRunCard(run));
    }
  }

  async function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }

  function showActionModal(kind, runId) {
    const run = findRun(runId);
    if (!run) return;

    const dlg = $("#action-modal");
    const cmd =
      kind === "accept"
        ? buildAcceptCommand(run)
        : `mv runs/${runId} runs/_rejected/${runId}`;

    const explainers =
      kind === "accept" ? acceptExplainer(run) : rejectExplainer(run);

    $("#action-modal-title").textContent =
      kind === "accept" ? "accept — 人审后入库（仅复制命令）" : "reject — 归档 run（仅复制命令）";
    $("#action-modal-hint").textContent =
      kind === "accept"
        ? "粘贴到仓库根终端执行。不会自动跑。"
        : "粘贴到仓库根终端执行。不会改卡库。";

    const detail = $("#action-modal-detail");
    if (detail) {
      detail.innerHTML = explainers
        .map((line) => `<p class="explainer-line">${escapeHtml(line)}</p>`)
        .join("");
    }

    $("#action-modal-cmd").textContent = cmd;
    $("#action-copy-status").textContent = "";
    const copyBtn = $("#action-copy");
    if (copyBtn) copyBtn.textContent = "复制命令";
    dlg.showModal();
  }

  function bindEvents() {
    const search = $("#inbox-search");
    if (search) {
      search.addEventListener("input", (e) => {
        const val = e.target.value.trim().toLowerCase();
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
          STATE.search = val;
          renderList();
        }, SEARCH_DEBOUNCE_MS);
      });
    }

    document.addEventListener("click", (e) => {
      const acceptBtn = e.target.closest("button.accept");
      const rejectBtn = e.target.closest("button.reject");
      if (acceptBtn) showActionModal("accept", acceptBtn.dataset.run);
      if (rejectBtn) showActionModal("reject", rejectBtn.dataset.run);
    });

    const closeBtn = $("#action-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        $("#action-modal").close();
      });
    }

    const copyBtn = $("#action-copy");
    if (copyBtn) {
      copyBtn.addEventListener("click", async () => {
        const cmd = $("#action-modal-cmd").textContent;
        try {
          await copyText(cmd);
          copyBtn.textContent = "已复制 ✓";
          $("#action-copy-status").textContent =
            "已复制到剪贴板 — 请到仓库根目录终端粘贴执行";
          setTimeout(() => {
            copyBtn.textContent = "复制命令";
          }, 1500);
        } catch (err) {
          $("#action-copy-status").textContent =
            "复制失败，请手动选中上方命令";
          console.error(err);
        }
      });
    }
  }

  function init() {
    const el = $("#last-refresh");
    if (el) {
      el.textContent = STATE.runs.length
        ? `已加载 ${STATE.runs.length} runs（内联 JSON；更新请先跑 python runs/_index.py 再 refresh）`
        : "_index.js 为空；请先跑 python runs/_index.py 生成";
    }
    renderVerdictChips();
    renderList();
    bindEvents();
  }

  document.addEventListener("DOMContentLoaded", init);
})();

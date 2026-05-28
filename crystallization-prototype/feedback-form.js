(function (global) {
  "use strict";

  const SCORE_DIMS = [
    ["mechanism", "mechanism"],
    ["anchor", "anchor"],
    ["micro_steps", "micro_steps"],
    ["overall", "overall"],
  ];

  const TAG_OPTS = [
    ["stylewin", "风格好"],
    ["stylelose", "风格差"],
    ["lexicon-cand", "lexicon 候选"],
  ];

  function apiAvailable() {
    return typeof fetch === "function" && location.protocol.startsWith("http");
  }

  function preview30(text) {
    const t = String(text || "").trim().replace(/\s+/g, " ");
    if (!t) return "（无文字）";
    return t.length <= 30 ? t : t.slice(0, 30) + "…";
  }

  function formatOverall(scores) {
    const v = scores && scores.overall;
    return v == null ? "—" : String(v);
  }

  async function fetchExisting(targetType, targetId) {
    if (!apiAvailable()) return { count: 0, items: [] };
    const q = new URLSearchParams({ target_type: targetType, target_id: targetId });
    const res = await fetch(`/api/feedback?${q}`);
    if (!res.ok) return { count: 0, items: [] };
    return res.json();
  }

  async function submitFeedback(targetType, targetId, payload) {
    const body = {
      target_type: targetType,
      target_id: targetId,
      stage_focus: targetType === "run" ? "b" : "merged",
      ...payload,
    };
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }

  function buildHistoryList(items) {
    const ul = document.createElement("ul");
    ul.className = "ic-feedback-history";
    for (const row of items) {
      const li = document.createElement("li");
      const ts = row.ts ? row.ts.slice(0, 16).replace("T", " ") : "?";
      li.textContent = `${ts} · overall ${formatOverall(row.scores)} · ${preview30(row.freeform)}`;
      ul.appendChild(li);
    }
    return ul;
  }

  /**
   * @param {HTMLElement} container
   * @param {{ targetType: string, targetId: string, summary?: object }} opts
   */
  function mountFeedbackForm(container, opts) {
    const { targetType, targetId, summary } = opts;
    const details = document.createElement("details");
    details.className = "ic-feedback";

    const summaryEl = document.createElement("summary");
    const titleSpan = document.createElement("span");
    titleSpan.textContent = "打分 / 感受 ▼";
    summaryEl.appendChild(titleSpan);

    const badgeSpan = document.createElement("span");
    badgeSpan.className = "ic-feedback-badge";
    summaryEl.appendChild(badgeSpan);

    const body = document.createElement("div");
    body.className = "ic-feedback-body";

    const statusEl = document.createElement("p");
    statusEl.className = "ic-feedback-status";
    if (!apiAvailable()) {
      statusEl.textContent =
        "需通过开发台打开本页才能提交（bash tools/start_dev_ui.sh）";
    }
    body.appendChild(statusEl);

    const historySlot = document.createElement("div");
    body.appendChild(historySlot);

    const scoresWrap = document.createElement("div");
    scoresWrap.className = "ic-feedback-scores";

    const scoreState = {};

    for (const [key, label] of SCORE_DIMS) {
      const row = document.createElement("div");
      row.className = "ic-feedback-score-row";
      row.dataset.dim = key;

      const dimLabel = document.createElement("label");
      dimLabel.className = "dim-label";
      dimLabel.textContent = label;

      const enableLabel = document.createElement("label");
      enableLabel.className = "ic-feedback-enable";
      const enableCb = document.createElement("input");
      enableCb.type = "checkbox";
      enableCb.checked = true;
      enableLabel.appendChild(enableCb);
      enableLabel.appendChild(document.createTextNode(" 评分此项"));

      const range = document.createElement("input");
      range.type = "range";
      range.min = "1";
      range.max = "5";
      range.step = "1";
      range.value = "3";
      range.disabled = false;

      const valSpan = document.createElement("span");
      valSpan.className = "score-val";
      valSpan.textContent = "3";

      const syncRow = () => {
        const on = enableCb.checked;
        row.classList.toggle("disabled", !on);
        range.disabled = !on;
        valSpan.textContent = on ? range.value : "—";
        scoreState[key] = on ? parseInt(range.value, 10) : null;
      };

      range.addEventListener("input", syncRow);
      enableCb.addEventListener("change", syncRow);
      syncRow();

      row.appendChild(dimLabel);
      const mid = document.createElement("div");
      mid.appendChild(enableLabel);
      mid.appendChild(range);
      row.appendChild(mid);
      row.appendChild(valSpan);
      scoresWrap.appendChild(row);
    }
    body.appendChild(scoresWrap);

    const freeform = document.createElement("textarea");
    freeform.className = "ic-feedback-freeform";
    freeform.name = "freeform";
    freeform.rows = 3;
    freeform.placeholder =
      "一句感受，可写：哪里好 / 哪里别扭 / 我希望 lexicon 怎么改";
    body.appendChild(freeform);

    const tagsField = document.createElement("fieldset");
    tagsField.className = "ic-feedback-tags";
    const legend = document.createElement("legend");
    legend.textContent = "标签（可多选）";
    tagsField.appendChild(legend);
    const tagInputs = {};
    for (const [id, label] of TAG_OPTS) {
      const lab = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = id;
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(" " + label));
      tagsField.appendChild(lab);
      tagInputs[id] = cb;
    }
    body.appendChild(tagsField);

    const lexHyp = document.createElement("input");
    lexHyp.className = "ic-feedback-lexicon";
    lexHyp.name = "lexicon_hypothesis";
    lexHyp.placeholder = "(可选) 我猜 lexicon 应该补什么";
    body.appendChild(lexHyp);

    const submitBtn = document.createElement("button");
    submitBtn.type = "button";
    submitBtn.className = "ic-feedback-submit";
    submitBtn.textContent = "提交 feedback";
    body.appendChild(submitBtn);

    details.appendChild(summaryEl);
    details.appendChild(body);
    container.appendChild(details);

    function setBadge(count) {
      if (count > 0) {
        badgeSpan.textContent = `(${count} 条已记录)`;
      } else {
        badgeSpan.textContent = "";
      }
    }

    function renderHistory(items) {
      historySlot.innerHTML = "";
      if (items && items.length) {
        historySlot.appendChild(buildHistoryList(items));
      }
    }

    async function refreshFromServer() {
      if (!apiAvailable()) return;
      try {
        const data = await fetchExisting(targetType, targetId);
        setBadge(data.count || 0);
        renderHistory(data.items || []);
      } catch (e) {
        console.warn("feedback GET failed", e);
      }
    }

    if (summary && summary.count > 0) {
      const avg =
        summary.avg_overall != null
          ? ` · 平均 ${Number(summary.avg_overall).toFixed(1)}`
          : "";
      badgeSpan.textContent = `(${summary.count} 条已记录${avg})`;
    }

    refreshFromServer();

    submitBtn.addEventListener("click", async () => {
      if (!apiAvailable()) {
        statusEl.className = "ic-feedback-status err";
        statusEl.textContent = "请用 feedback 服务打开页面后再提交";
        return;
      }
      const scores = {};
      for (const [key] of SCORE_DIMS) {
        scores[key] = scoreState[key];
      }
      const tags = Object.keys(tagInputs).filter((id) => tagInputs[id].checked);
      const payload = {
        scores,
        freeform: freeform.value.trim(),
        tags,
        lexicon_hypothesis: lexHyp.value.trim(),
      };
      const hasScore = Object.values(scores).some((v) => v != null);
      if (!hasScore && !payload.freeform) {
        statusEl.className = "ic-feedback-status err";
        statusEl.textContent = "至少填一项评分或一句感受";
        details.classList.remove("ic-feedback-ok");
        details.classList.add("ic-feedback-err");
        return;
      }
      submitBtn.disabled = true;
      statusEl.className = "ic-feedback-status";
      statusEl.textContent = "提交中…";
      try {
        const res = await submitFeedback(targetType, targetId, payload);
        statusEl.className = "ic-feedback-status ok";
        statusEl.textContent = `已记录 · 共 ${res.total} 条 (server 返回 ${res.total})`;
        details.classList.add("ic-feedback-ok");
        details.classList.remove("ic-feedback-err");
        await refreshFromServer();
      } catch (err) {
        statusEl.className = "ic-feedback-status err";
        statusEl.textContent = String(err.message || err);
        details.classList.add("ic-feedback-err");
        details.classList.remove("ic-feedback-ok");
      } finally {
        submitBtn.disabled = false;
      }
    });

    details.addEventListener("click", (e) => e.stopPropagation());
    return details;
  }

  function makeSummaryBadge(summary) {
    if (!summary || !summary.count) return null;
    const span = document.createElement("span");
    span.className = "feedback-summary-badge";
    const avg =
      summary.avg_overall != null
        ? ` · 平均 ${Number(summary.avg_overall).toFixed(1)}`
        : "";
    span.textContent = `已 ${summary.count} 条${avg}`;
    return span;
  }

  global.IcFeedback = {
    apiAvailable,
    mountFeedbackForm,
    makeSummaryBadge,
    getSummaryMap() {
      return global.FEEDBACK_SUMMARY || {};
    },
  };
})(typeof window !== "undefined" ? window : globalThis);

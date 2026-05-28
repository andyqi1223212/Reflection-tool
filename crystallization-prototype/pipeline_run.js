(function () {
  const sourceSelect = document.getElementById("pr-source-select");
  const loadBtn = document.getElementById("pr-load-source");
  const filenameInput = document.getElementById("pr-filename");
  const contentArea = document.getElementById("pr-content");
  const autoPushCb = document.getElementById("pr-auto-push");
  const forcePassCb = document.getElementById("pr-force-pass");
  const runBtn = document.getElementById("pr-run");
  const clearBtn = document.getElementById("pr-clear");
  const statusEl = document.getElementById("pr-status");
  const logEl = document.getElementById("pr-log");
  const linksEl = document.getElementById("pr-result-links");

  let sources = [];

  function log(line) {
    const ts = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    logEl.textContent += `[${ts}] ${line}\n`;
    logEl.scrollTop = logEl.scrollHeight;
  }

  function setStatus(text, tone) {
    statusEl.textContent = text;
    statusEl.dataset.tone = tone || "";
  }

  function setRunning(running) {
    runBtn.disabled = running;
    loadBtn.disabled = running;
    clearBtn.disabled = running;
    sourceSelect.disabled = running;
  }

  function apiBase() {
    if (window.location.protocol === "file:") return null;
    return "";
  }

  async function fetchSources() {
    const base = apiBase();
    if (!base && base !== "") {
      setStatus("请用开发台 HTTP 打开本页（bash tools/start_dev_ui.sh）", "err");
      return;
    }
    try {
      const res = await fetch("/api/orchestrate/sources");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);
      sources = data.items || [];
      sourceSelect.innerHTML = "";
      const opt0 = document.createElement("option");
      opt0.value = "";
      opt0.textContent = sources.length ? "— 选择已有 md —" : "（外部source 暂无 .md）";
      sourceSelect.appendChild(opt0);
      for (const item of sources) {
        const opt = document.createElement("option");
        opt.value = item.path;
        const kb = item.bytes ? ` · ${Math.round(item.bytes / 1024)}k` : "";
        opt.textContent = `${item.name}${kb}`;
        sourceSelect.appendChild(opt);
      }
      setStatus(`已加载 ${sources.length} 个外部 source`, "");
    } catch (e) {
      setStatus(`加载列表失败：${e.message}`, "err");
    }
  }

  async function loadSelectedSource() {
    const path = sourceSelect.value;
    if (!path) {
      setStatus("请先选择已有 md", "warn");
      return;
    }
    const base = apiBase();
    if (base === null) return;
    setRunning(true);
    log(`读取 ${path} …`);
    try {
      const res = await fetch(
        `/api/orchestrate/source?path=${encodeURIComponent(path)}`
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);
      contentArea.value = data.content || "";
      const name = path.split("/").pop() || "question.md";
      filenameInput.value = name;
      setStatus(`已载入 ${name}（${(data.content || "").length} 字）`, "");
      log(`载入完成：${name}`);
    } catch (e) {
      setStatus(`载入失败：${e.message}`, "err");
      log(`错误：${e.message}`);
    } finally {
      setRunning(false);
    }
  }

  function clearForm() {
    contentArea.value = "";
    filenameInput.value = "";
    sourceSelect.value = "";
    linksEl.innerHTML = "";
    logEl.textContent = "";
    setStatus("已清空表单", "");
  }

  function renderResult(data) {
    linksEl.innerHTML = "";
    if (data.run_id) {
      const inbox = document.createElement("a");
      inbox.href = "inbox.html";
      inbox.textContent = "打开 Inbox";
      linksEl.appendChild(inbox);
      const runJson = document.createElement("a");
      runJson.href = `/runs/${encodeURIComponent(data.run_id)}/manifest.json`;
      runJson.target = "_blank";
      runJson.textContent = "manifest.json";
      linksEl.appendChild(runJson);
      if (data.status === "succeeded") {
        const main = document.createElement("a");
        main.href = "index.html";
        main.textContent = "主站看新卡";
        linksEl.appendChild(main);
      }
    }
  }

  async function runPipeline() {
    const base = apiBase();
    if (base === null) {
      setStatus("请用开发台 HTTP 打开本页", "err");
      return;
    }
    const content = (contentArea.value || "").trim();
    const filename = (filenameInput.value || "").trim();
    const sourcePath = (sourceSelect.value || "").trim();
    const auto_push = autoPushCb.checked;
    const force_pass = forcePassCb.checked;

    const body = { auto_push, force_pass };
    if (content) {
      if (!filename) {
        setStatus("粘贴内容时请填写文件名（将保存到 外部source/）", "warn");
        return;
      }
      body.content = content;
      body.filename = filename;
    } else if (sourcePath) {
      body.source_path = sourcePath;
    } else {
      setStatus("请选择已有 md、或粘贴内容并填写文件名", "warn");
      return;
    }

    setRunning(true);
    linksEl.innerHTML = "";
    setStatus(
      "Pipeline 运行中…（A→B→Judge→Push，可能需数分钟，请勿关闭页面）",
      "running"
    );
    log(
      `开始 orchestrate：auto_push=${auto_push} force_pass=${force_pass}`
    );

    try {
      const res = await fetch("/api/orchestrate/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);

      log(`run_id=${data.run_id}`);
      log(`status=${data.status} verdict=${data.verdict}`);
      log(`stages=${(data.stages_completed || []).join(" → ")}`);
      if (data.next_action) log(`next_action: ${data.next_action}`);
      if (data.last_error) log(`error: ${data.last_error}`);

      renderResult(data);

      if (data.status === "succeeded") {
        setStatus(
          `成功：verdict=${data.verdict}，已${auto_push ? "尝试 push/merge" : "跳过 push"}`,
          "ok"
        );
      } else if (data.status === "awaiting_human") {
        setStatus(
          `待人工：verdict=${data.verdict}。请到 Inbox 处理或勾选 force-pass 重跑`,
          "warn"
        );
      } else {
        setStatus(
          `未成功：status=${data.status}${data.last_error ? " — " + data.last_error : ""}`,
          "err"
        );
      }
    } catch (e) {
      setStatus(`请求失败：${e.message}`, "err");
      log(`错误：${e.message}`);
    } finally {
      setRunning(false);
      fetchSources();
    }
  }

  loadBtn.addEventListener("click", loadSelectedSource);
  runBtn.addEventListener("click", runPipeline);
  clearBtn.addEventListener("click", clearForm);
  sourceSelect.addEventListener("change", () => {
    if (sourceSelect.value && !filenameInput.value) {
      filenameInput.value = sourceSelect.value.split("/").pop() || "";
    }
  });

  const params = new URLSearchParams(window.location.search);
  const preset = params.get("source");
  fetchSources().then(() => {
    if (preset) {
      sourceSelect.value = preset;
      if (sourceSelect.value === preset) loadSelectedSource();
    }
  });
})();

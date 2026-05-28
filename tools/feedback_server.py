#!/usr/bin/env python3
"""本地反馈服务：静态页 + POST/GET feedback.jsonl（stdlib http.server）。"""
from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

VALID_TARGET_TYPES = frozenset({"run", "card", "trial"})
VALID_TAGS = frozenset({"stylewin", "stylelose", "lexicon-cand", "synthesis-cand"})
LEXICON_TRIAL_TAG_RE = re.compile(r"^lexicon-v\d+-(win|lose)$")
EVAL_TRIALS_REL = "eval/lexicon_trials"
SCORE_KEYS = ("mechanism", "anchor", "micro_steps", "overall")
INDEX_STALE_HOURS = 24
FALLBACK_PORTS = (8765, 8766, 8777, 8788, 9876)

LEXICON_DIR = "context"
LEXICON_ARCHIVE_DIR = "context/_archive"
LEXICON_PROPOSALS_REL = "users/{uid}/lexicon_proposals"
PIPELINE_B_PROMPT_REL = "agent第二轮/pipeline-b-style.prompt.md"
LEXICON_APPLY_LOCK_NAME = ".lexicon_apply.lock"
SYNTHESIS_REL = "context/raw-questions-synthesis.md"
SYNTHESIS_PROPOSALS_REL = "users/{uid}/synthesis_proposals"
SYNTHESIS_APPLY_LOCK_NAME = ".synthesis_apply.lock"
SYNTHESIS_ALLOWED_SECTION_NUMS = frozenset({2, 5, 6})
EXTERNAL_SOURCE_REL = "外部source"
ORCHESTRATE_LOCK_NAME = ".orchestrate_run.lock"

_AGENTS_RT_ROOT = Path(__file__).resolve().parent.parent
if str(_AGENTS_RT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENTS_RT_ROOT))

from agents_runtime._patch_utils import (  # noqa: E402
    apply_patch as _apply_one_patch,
    apply_patches_safely,
    locate_section_bounds as _locate_section_bounds,
    validate_patches,
)
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def _repo_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    return Path(__file__).resolve().parent.parent


def _uid() -> str:
    return os.environ.get("IC_USER", "default").strip() or "default"


def _jsonl_path(root: Path) -> Path:
    return root / "users" / _uid() / "feedback.jsonl"


def _lexicon_proposals_dir(root: Path) -> Path:
    return root / "users" / _uid() / "lexicon_proposals"


def _synthesis_proposals_dir(root: Path) -> Path:
    return root / "users" / _uid() / "synthesis_proposals"


def _synthesis_path(root: Path) -> Path:
    return root / SYNTHESIS_REL


def _synthesis_section_num(section: str) -> int | None:
    m = re.search(r"§\s*(\d+)", section or "")
    return int(m.group(1)) if m else None


def _extract_synthesis_last_synced(text: str) -> str:
    m = re.search(r"最后更新[：:]\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    m2 = re.search(r"文档版本[：:]\s*(\d{4}-\d{2}-\d{2})", text)
    return m2.group(1) if m2 else ""


def _bump_synthesis_footer(text: str, proposal_ts: str, applied_count: int) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    note = f"apply {applied_count} 个 synthesis patch（proposal {proposal_ts}）"
    if re.search(r"最后更新[：:]", text):
        text = re.sub(
            r"(\*?最后更新[：:]\s*)\d{4}-\d{2}-\d{2}([^—\n]*)",
            rf"\g<1>{today}\g<2> — {note}",
            text,
            count=1,
        )
    elif re.search(r"文档版本[：:]", text):
        text = re.sub(
            r"(文档版本[：:]\s*)\d{4}-\d{2}-\d{2}",
            rf"\g<1>{today}",
            text,
            count=1,
        )
    else:
        text = text.rstrip() + f"\n\n*最后更新：{today} — {note}*\n"
    return text


def _current_lexicon_path(root: Path) -> Path | None:
    """找当前活跃 lexicon（context/pipeline-b-style-lexicon-v<N>.md，N 最大者）。"""
    lex_dir = root / LEXICON_DIR
    if not lex_dir.is_dir():
        return None
    candidates: list[tuple[int, Path]] = []
    for p in lex_dir.iterdir():
        if not p.is_file():
            continue
        m = re.match(r"pipeline-b-style-lexicon-v(\d+)\.md$", p.name)
        if m:
            candidates.append((int(m.group(1)), p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _lexicon_version_from_path(path: Path) -> int | None:
    m = re.match(r"pipeline-b-style-lexicon-v(\d+)\.md$", path.name)
    return int(m.group(1)) if m else None


def _now_iso() -> str:
    tz = datetime.now().astimezone().tzinfo or timezone.utc
    return datetime.now(tz).isoformat(timespec="seconds")


def _read_all_lines(jsonl_path: Path) -> list[dict[str, Any]]:
    if not jsonl_path.is_file():
        return []
    items: list[dict[str, Any]] = []
    try:
        text = jsonl_path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            items.append(obj)
    return items


def _append_line(jsonl_path: Path, line: dict[str, Any]) -> int:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(line, ensure_ascii=False) + "\n"
    with open(jsonl_path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return sum(1 for _ in jsonl_path.open(encoding="utf-8") if _.strip())


def _external_source_dir(root: Path) -> Path:
    return root / EXTERNAL_SOURCE_REL


def _sanitize_md_filename(name: str) -> str | None:
    name = name.strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    if not name.lower().endswith(".md"):
        name = f"{name}.md"
    base = Path(name).name
    if base != name:
        return None
    if not re.match(r"^[\w\u4e00-\u9fa5][\w\u4e00-\u9fa5.\- ]{0,118}\.md$", base):
        return None
    return base


def _allowed_source_path(root: Path, rel: str) -> Path | None:
    rel = rel.replace("\\", "/").lstrip("/")
    if not rel.startswith(f"{EXTERNAL_SOURCE_REL}/"):
        return None
    parts = rel.split("/")
    if ".." in parts or len(parts) != 2:
        return None
    p = (root / rel).resolve()
    try:
        p.relative_to(_external_source_dir(root).resolve())
    except ValueError:
        return None
    if not p.is_file() or p.suffix.lower() != ".md":
        return None
    return p


def _list_external_sources(root: Path) -> list[dict[str, Any]]:
    d = _external_source_dir(root)
    if not d.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for p in d.glob("*.md"):
        if not p.is_file():
            continue
        st = p.stat()
        items.append(
            {
                "name": p.name,
                "path": str(p.relative_to(root)).replace("\\", "/"),
                "bytes": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                .astimezone()
                .isoformat(timespec="seconds"),
            }
        )
    items.sort(key=lambda x: str(x.get("mtime") or ""), reverse=True)
    return items


def _resolve_orchestrate_question_md(
    root: Path, body: dict[str, Any]
) -> tuple[str | None, str | None]:
    source_path = (body.get("source_path") or "").strip()
    content = body.get("content")
    filename = (body.get("filename") or "").strip()

    if source_path and content is not None:
        return None, "不要同时传 source_path 与 content"
    if source_path:
        p = _allowed_source_path(root, source_path)
        if not p:
            return None, "source_path 须为 外部source/<name>.md 且文件已存在"
        return str(p.relative_to(root)).replace("\\", "/"), None
    if content is not None:
        if not isinstance(content, str):
            return None, "content 须为字符串"
        safe = _sanitize_md_filename(filename)
        if not safe:
            return None, "filename 不合法（安全 .md 文件名，勿含路径）"
        dest = _external_source_dir(root) / safe
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        print(f"[feedback_server] 已写入 {dest.relative_to(root)}", file=sys.stderr)
        return f"{EXTERNAL_SOURCE_REL}/{safe}", None
    return None, "需要 source_path，或 content + filename"


def _maybe_refresh_index(root: Path, *, force: bool = False) -> None:
    index_js = root / "runs" / "_index.js"
    index_py = root / "runs" / "_index.py"
    if not index_py.is_file():
        return
    stale = force
    if not stale and index_js.is_file():
        age = datetime.now().timestamp() - index_js.stat().st_mtime
        stale = age > INDEX_STALE_HOURS * 3600
    elif not index_js.is_file():
        stale = True
    if not stale:
        return
    print(f"[feedback_server] 刷新 runs/_index.js", file=sys.stderr)
    subprocess.run(
        [sys.executable, str(index_py)],
        cwd=str(root),
        check=False,
    )


def _context_chunks_stale(root: Path) -> bool:
    curator = root / "pipeline-b-context-curator"
    chunks_js = curator / "chunks.data.js"
    if not chunks_js.is_file():
        return True
    watch = [
        root / "tools" / "export_agentflow_context_chunks.py",
        root / "agent第二轮/pipeline-a-diagnose.prompt.md",
        root / "agent第二轮/pipeline-b-style.prompt.md",
        root / "agent第二轮/judge.prompt.md",
        root / "context/pipeline-b-style-lexicon-v1.md",
        root / "context/crystallization-style-agent-brief.md",
        root / "context/crystallization-schema-v0.md",
        root / "context/raw-questions-synthesis.md",
        root / "inquiry-chain-demo-v3-good-answer.md",
    ]
    chunks_mtime = chunks_js.stat().st_mtime
    for p in watch:
        if p.is_file() and p.stat().st_mtime > chunks_mtime:
            return True
    return False


def _maybe_refresh_context_chunks(root: Path, *, force: bool = False) -> None:
    export_script = root / "tools" / "export_agentflow_context_chunks.py"
    if not export_script.is_file():
        return
    if not force and not _context_chunks_stale(root):
        return
    print("[feedback_server] 刷新 pipeline-b-context-curator/chunks.data.js", file=sys.stderr)
    subprocess.run(
        [sys.executable, str(export_script)],
        cwd=str(root),
        check=False,
    )


def _validate_scores(scores: Any) -> dict[str, int | None] | None:
    if not isinstance(scores, dict):
        return None
    out: dict[str, int | None] = {}
    for key in SCORE_KEYS:
        val = scores.get(key)
        if val is None:
            out[key] = None
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return None
        iv = int(val)
        if iv < 1 or iv > 5:
            return None
        out[key] = iv
    return out


def _validate_post_body(body: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    target_type = body.get("target_type")
    target_id = body.get("target_id")
    if target_type not in VALID_TARGET_TYPES:
        return None, "target_type 必须是 run、card 或 trial"
    if not target_id or not isinstance(target_id, str):
        return None, "target_id 必填"

    stage_focus = body.get("stage_focus")
    if stage_focus not in ("b", "merged"):
        stage_focus = "b" if target_type == "run" else "merged"

    scores = _validate_scores(body.get("scores") or {})
    if scores is None:
        return None, "scores 格式无效（各维 1–5 或 null）"

    freeform = body.get("freeform")
    if freeform is not None and not isinstance(freeform, str):
        return None, "freeform 必须是字符串"
    freeform = (freeform or "").strip()

    has_score = any(scores.get(k) is not None for k in SCORE_KEYS)
    if not has_score and not freeform:
        return None, "至少填写一项评分或一句感受"

    tags = body.get("tags") or []
    if not isinstance(tags, list):
        return None, "tags 必须是数组"
    clean_tags: list[str] = []
    for t in tags:
        if not isinstance(t, str):
            return None, f"非法 tag: {t}"
        if t not in VALID_TAGS and not (
            target_type == "trial" and LEXICON_TRIAL_TAG_RE.match(t)
        ):
            return None, f"非法 tag: {t}"
        if t not in clean_tags:
            clean_tags.append(t)

    lexicon_hypothesis = body.get("lexicon_hypothesis")
    if lexicon_hypothesis is not None and not isinstance(lexicon_hypothesis, str):
        return None, "lexicon_hypothesis 必须是字符串"

    line = {
        "ts": _now_iso(),
        "uid": _uid(),
        "target_type": target_type,
        "target_id": target_id.strip(),
        "stage_focus": stage_focus,
        "scores": scores,
        "freeform": freeform,
        "tags": clean_tags,
        "lexicon_hypothesis": (lexicon_hypothesis or "").strip(),
    }
    return line, None


def _eval_trials_root(root: Path) -> Path:
    return root / EVAL_TRIALS_REL


def _list_eval_lite_versions(root: Path) -> list[dict[str, Any]]:
    base = _eval_trials_root(root)
    if not base.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for d in sorted(base.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        m = re.match(r"^v(\d+)$", d.name)
        if not m:
            continue
        ver = int(m.group(1))
        run_dirs = [x for x in d.iterdir() if x.is_dir() and not x.name.startswith(".")]
        meta = d / "meta.json"
        ts = None
        if meta.is_file():
            try:
                mobj = json.loads(meta.read_text(encoding="utf-8"))
                ts = mobj.get("ts")
            except (OSError, json.JSONDecodeError):
                pass
        items.append({"version": ver, "trial_count": len(run_dirs), "ts": ts})
    items.sort(key=lambda x: x["version"], reverse=True)
    return items


def _parse_summary_table(summary_md: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in summary_md.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("| run_id") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) < 8:
            continue
        run_id = parts[0].strip("`")
        rows.append(
            {
                "run_id": run_id,
                "title": parts[1],
                "route": parts[2],
                "mech_chars": parts[3],
                "anchor_chars": parts[4],
                "steps_count": parts[5],
                "status": parts[6],
                "note": parts[7],
            }
        )
    return rows


def _eval_lite_trials_list(root: Path, version: int) -> dict[str, Any]:
    vdir = _eval_trials_root(root) / f"v{version}"
    if not vdir.is_dir():
        return {"version": version, "items": [], "summary_md": ""}
    summary_path = vdir / "summary.md"
    summary_md = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
    items = _parse_summary_table(summary_md)
    for it in items:
        meta_path = vdir / it["run_id"] / "meta.json"
        if meta_path.is_file():
            try:
                it["meta"] = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                it["meta"] = None
    batch_meta = None
    bm = vdir / "meta.json"
    if bm.is_file():
        try:
            batch_meta = json.loads(bm.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            batch_meta = None
    return {
        "version": version,
        "items": items,
        "summary_md": summary_md,
        "batch_meta": batch_meta,
    }


def _build_trial_bootstrap(root: Path) -> dict[str, Any]:
    """供 lexicon_review.html 内联：避免前端 fetch 失败时汇总表为空。"""
    versions = _list_eval_lite_versions(root)
    ver = versions[0]["version"] if versions else 4
    trials = _eval_lite_trials_list(root, ver)
    return {"versions": versions, "default_version": ver, "trials": trials}


def _inject_lexicon_review_bootstrap(html: str, root: Path) -> str:
    payload = _build_trial_bootstrap(root)
    blob = json.dumps(payload, ensure_ascii=False)
    blob = blob.replace("</", "<\\/")
    tag = f'<script id="lr-trial-bootstrap" type="application/json">{blob}</script>'
    marker = 'id="lr-trial-bootstrap"'
    if marker in html:
        html = re.sub(
            r'<script id="lr-trial-bootstrap" type="application/json">.*?</script>',
            tag,
            html,
            count=1,
            flags=re.S,
        )
    else:
        html = html.replace("</body>", f"  {tag}\n</body>", 1)
    # 预填 tbody：无 JS 也能看到行
    rows_html = ""
    for row in payload.get("trials", {}).get("items") or []:
        rid = row.get("run_id", "")
        if not rid:
            continue
        rows_html += (
            f'<tr data-run-id="{rid}">'
            f"<td><code>{rid}</code></td>"
            f"<td>{row.get('title', '')}</td>"
            f"<td>{row.get('route', '')}</td>"
            f"<td>{row.get('mech_chars', '')}</td>"
            f"<td>{row.get('anchor_chars', '')}</td>"
            f"<td>{row.get('steps_count', '')}</td>"
            f"<td>{row.get('status', '')}</td>"
            f"<td>{row.get('note', '')}</td>"
            f"</tr>\n"
        )
    if rows_html:
        html = re.sub(
            r'(<tbody id="lr-trial-tbody">)\s*</tbody>',
            rf"\1\n{rows_html}        </tbody>",
            html,
            count=1,
        )
    return html


def _eval_lite_trial_detail(root: Path, version: int, run_id: str) -> dict[str, Any] | None:
    if ".." in run_id or "/" in run_id:
        return None
    tdir = _eval_trials_root(root) / f"v{version}" / run_id
    if not tdir.is_dir():
        return None
    out: dict[str, Any] = {"run_id": run_id, "version": version}
    for name, key in (
        ("meta.json", "meta"),
        ("b_old.json", "b_old"),
        ("b_new.json", "b_new"),
        ("diff.md", "diff_md"),
        ("error.json", "error"),
    ):
        p = tdir / name
        if not p.is_file():
            continue
        if name.endswith(".md"):
            out[key] = p.read_text(encoding="utf-8")
        else:
            try:
                out[key] = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                out[key] = None
    return out


def _validate_trial_accept_body(body: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        version = int(body.get("lexicon_version"))
    except (TypeError, ValueError):
        return None, "lexicon_version 必须是整数"
    run_id = body.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip() or "/" in run_id:
        return None, "run_id 不合法"
    decision = body.get("decision")
    if decision not in ("win", "lose", "skip"):
        return None, "decision 必须是 win、lose 或 skip"
    if decision == "skip":
        return {"skipped": True}, None

    scores_in = body.get("scores") if isinstance(body.get("scores"), dict) else {}
    overall = scores_in.get("overall")
    if overall is not None:
        try:
            ov = int(overall)
            if ov < 1 or ov > 5:
                raise ValueError
        except (TypeError, ValueError):
            return None, "scores.overall 须为 1–5"
    else:
        ov = 5 if decision == "win" else 1

    freeform = body.get("freeform")
    if freeform is not None and not isinstance(freeform, str):
        return None, "freeform 必须是字符串"
    freeform = (freeform or "").strip()
    if not freeform:
        freeform = f"(trial decision: {decision})"

    tag = f"lexicon-v{version}-{'win' if decision == 'win' else 'lose'}"
    line = {
        "ts": _now_iso(),
        "uid": _uid(),
        "target_type": "trial",
        "target_id": f"v{version}/{run_id.strip()}",
        "stage_focus": "b",
        "scores": {
            "mechanism": None,
            "anchor": None,
            "micro_steps": None,
            "overall": ov,
        },
        "freeform": freeform,
        "tags": [tag],
        "lexicon_hypothesis": "",
    }
    return line, None


# ---------- lexicon apply ----------


def _bump_lexicon_frontmatter(text: str, new_version_num: int, applied_count: int, proposal_ts: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    # 更新 file: 行
    text = re.sub(
        r"^file:\s*pipeline-b-style-lexicon-v\d+\.md",
        f"file: pipeline-b-style-lexicon-v{new_version_num}.md",
        text,
        count=1,
        flags=re.M,
    )
    # 更新 last_synced
    if re.search(r"^last_synced:\s*", text, re.M):
        text = re.sub(r"^last_synced:\s*\S+", f"last_synced: {today}", text, count=1, flags=re.M)
    # 在 changelog 末尾追加一段（找第一行以 `- **YYYY-MM-DD v` 开头的位置插在它之前——保持最新在上）
    changelog_pat = re.compile(r"^##\s*changelog\s*$", re.M | re.I)
    m = changelog_pat.search(text)
    if m:
        insert_at = m.end()
        # 跳过紧随其后的空白
        while insert_at < len(text) and text[insert_at] in "\r\n":
            insert_at += 1
        new_entry = (
            f"\n- **{today} v{new_version_num}**：apply {applied_count} 个 feedback 候选 patch（proposal {proposal_ts}）\n"
        )
        text = text[:insert_at] + new_entry + text[insert_at:]
    return text


def _bump_prompt_frontmatter(prompt_text: str, new_path_rel: str, reason: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    # 1) source: 路径
    prompt_text = re.sub(
        r'source:\s*"context/pipeline-b-style-lexicon-v\d+\.md"',
        f'source: "{new_path_rel}"',
        prompt_text,
        count=1,
    )
    # 2) version: v2.x → 在末段 bump
    def _bump_v(m: re.Match[str]) -> str:
        major, minor = m.group(1), m.group(2)
        return f"version: v{major}.{int(minor) + 1}"

    prompt_text = re.sub(
        r"^version:\s*v(\d+)\.(\d+)\s*$",
        _bump_v,
        prompt_text,
        count=1,
        flags=re.M,
    )
    # 3) last_iter 行 → 整行替换为今天 + reason
    prompt_text = re.sub(
        r"^last_iter:.*$",
        f"last_iter: {today}  # {reason}",
        prompt_text,
        count=1,
        flags=re.M,
    )
    return prompt_text


def _do_lexicon_apply(
    root: Path,
    proposal_ts: str,
    accepted_patches: list[dict[str, Any]],
    reject_reasons: dict[str, str] | None,
) -> dict[str, Any]:
    """执行 apply；失败回滚。返回 {ok, new_version, new_path, archive_path, prompt_updated}。"""
    if not accepted_patches:
        raise ValueError("accepted_patches 为空，无需 apply")

    current = _current_lexicon_path(root)
    if not current:
        raise FileNotFoundError("找不到当前 lexicon（context/pipeline-b-style-lexicon-v<N>.md）")
    cur_ver = _lexicon_version_from_path(current)
    if cur_ver is None:
        raise ValueError(f"无法从文件名解析版本号: {current.name}")
    next_ver = cur_ver + 1
    new_path = current.parent / f"pipeline-b-style-lexicon-v{next_ver}.md"
    archive_dir = root / LEXICON_ARCHIVE_DIR
    archive_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    archive_path = archive_dir / f"lexicon-v{cur_ver}-{today}.md"

    prompt_path = root / PIPELINE_B_PROMPT_REL
    prompt_bak = prompt_path.with_suffix(prompt_path.suffix + ".bak")

    cur_text = current.read_text(encoding="utf-8")
    prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
    # backup prompt
    if prompt_text:
        prompt_bak.write_text(prompt_text, encoding="utf-8")

    try:
        new_text = cur_text
        per_patch_log: list[dict[str, Any]] = []
        for patch in accepted_patches:
            before_len = len(new_text)
            new_text = _apply_one_patch(new_text, patch)
            per_patch_log.append(
                {
                    "patch_id": patch.get("id"),
                    "action": patch.get("action"),
                    "delta_chars": len(new_text) - before_len,
                }
            )

        new_text = _bump_lexicon_frontmatter(new_text, next_ver, len(accepted_patches), proposal_ts)

        # 写新 lexicon
        new_path.write_text(new_text, encoding="utf-8")
        # 归档旧版（用 copy + remove 避免跨设备 mv 风险）
        shutil.copy2(current, archive_path)
        current.unlink()
        # 改 prompt frontmatter
        prompt_updated = False
        if prompt_text:
            new_path_rel = f"context/pipeline-b-style-lexicon-v{next_ver}.md"
            reason = f"v?: apply {len(accepted_patches)} 个 feedback 候选 patch（proposal {proposal_ts}）"
            new_prompt = _bump_prompt_frontmatter(prompt_text, new_path_rel, reason)
            prompt_path.write_text(new_prompt, encoding="utf-8")
            prompt_updated = True

        # 写 applied 记录
        proposals_dir = _lexicon_proposals_dir(root)
        applied_record = {
            "ts": _now_iso(),
            "proposal_ts": proposal_ts,
            "applied_patches": accepted_patches,
            "reject_reasons": reject_reasons or {},
            "base_version": f"v{cur_ver}",
            "new_version": f"v{next_ver}",
            "new_path": str(new_path.relative_to(root)),
            "archive_path": str(archive_path.relative_to(root)),
            "per_patch_log": per_patch_log,
        }
        (proposals_dir / f"{proposal_ts}_applied.json").write_text(
            json.dumps(applied_record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "ok": True,
            "new_version": f"v{next_ver}",
            "new_path": str(new_path.relative_to(root)),
            "archive_path": str(archive_path.relative_to(root)),
            "prompt_updated": prompt_updated,
            "applied_count": len(accepted_patches),
        }
    except Exception:
        # 回滚：删 new_path / archive_path（可能没生成）/ 还原 prompt
        if new_path.exists():
            try:
                new_path.unlink()
            except OSError:
                pass
        if archive_path.exists() and not current.exists():
            # 旧 lexicon 被删了但归档还在 → 还原
            try:
                shutil.copy2(archive_path, current)
            except OSError:
                pass
        if archive_path.exists():
            try:
                # 只在旧 lexicon 已被删的情况下保留 archive；
                # 简化处理：失败时统一删 archive，避免半成品
                archive_path.unlink()
            except OSError:
                pass
        if prompt_bak.is_file():
            try:
                shutil.copy2(prompt_bak, prompt_path)
            except OSError:
                pass
        raise
    finally:
        if prompt_bak.is_file():
            try:
                prompt_bak.unlink()
            except OSError:
                pass


# ---------- synthesis apply ----------


def _validate_synthesis_patches(patches: list[dict[str, Any]]) -> str | None:
    for patch in patches:
        n = _synthesis_section_num(patch.get("section") or "")
        if n not in SYNTHESIS_ALLOWED_SECTION_NUMS:
            return f"section {patch.get('section')!r} 不在白名单 §2/§5/§6"
    return None


def _do_synthesis_apply(
    root: Path,
    proposal_ts: str,
    accepted_patches: list[dict[str, Any]],
    reject_reasons: dict[str, str] | None,
) -> dict[str, Any]:
    if not accepted_patches:
        raise ValueError("accepted_patches 为空")

    err = _validate_synthesis_patches(accepted_patches)
    if err:
        raise ValueError(err)

    synth_path = _synthesis_path(root)
    if not synth_path.is_file():
        raise FileNotFoundError(f"找不到 {SYNTHESIS_REL}")

    archive_dir = root / LEXICON_ARCHIVE_DIR
    archive_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    archive_path = archive_dir / f"synthesis-{today}.md"
    bak_path = synth_path.with_suffix(synth_path.suffix + ".bak")

    cur_text = synth_path.read_text(encoding="utf-8")
    bak_path.write_text(cur_text, encoding="utf-8")
    pre_validate = validate_patches(cur_text, accepted_patches)
    if pre_validate:
        raise ValueError(
            json.dumps(
                {"failed_patch_ids": pre_validate, "error": "anchor 预校验失败"},
                ensure_ascii=False,
            )
        )

    try:
        new_text, failed = apply_patches_safely(cur_text, accepted_patches)
        if failed:
            raise ValueError(
                json.dumps(
                    {"failed_patch_ids": failed, "error": "apply 中途失败，已回滚"},
                    ensure_ascii=False,
                )
            )
        new_text = _bump_synthesis_footer(new_text, proposal_ts, len(accepted_patches))
        shutil.copy2(synth_path, archive_path)
        synth_path.write_text(new_text, encoding="utf-8")

        proposals_dir = _synthesis_proposals_dir(root)
        applied_record = {
            "ts": _now_iso(),
            "proposal_ts": proposal_ts,
            "applied_patches": accepted_patches,
            "reject_reasons": reject_reasons or {},
            "archive_path": str(archive_path.relative_to(root)),
            "last_synced_updated_to": today,
        }
        (proposals_dir / f"{proposal_ts}_applied.json").write_text(
            json.dumps(applied_record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "ok": True,
            "archive_path": str(archive_path.relative_to(root)),
            "last_synced_updated_to": today,
            "applied_count": len(accepted_patches),
        }
    except Exception:
        if bak_path.is_file():
            shutil.copy2(bak_path, synth_path)
        raise
    finally:
        if bak_path.is_file():
            try:
                bak_path.unlink()
            except OSError:
                pass


# ---------- end apply 工具函数 ----------


class FeedbackHandler(BaseHTTPRequestHandler):
    repo_root: Path
    proto_dir: Path
    context_curator_dir: Path
    runs_dir: Path
    jsonl_path: Path
    server_started_at: str

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[feedback_server] {self.address_string()} {fmt % args}", file=sys.stderr)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, text: str, content_type: str = "text/plain") -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.end_headers()

    def _read_json_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        try:
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _serve_file(self, path: Path) -> None:
        if not path.is_file():
            self._send_text(HTTPStatus.NOT_FOUND, "not found")
            return
        suffix = path.suffix.lower()
        ctype = MIME.get(suffix, "application/octet-stream")
        try:
            data = path.read_bytes()
        except OSError:
            self._send_text(HTTPStatus.INTERNAL_SERVER_ERROR, "read error")
            return
        if path.name == "lexicon_review.html":
            try:
                data = _inject_lexicon_review_bootstrap(
                    data.decode("utf-8"), self.repo_root
                ).encode("utf-8")
            except (OSError, UnicodeDecodeError, re.error) as e:
                print(f"[feedback_server] trial bootstrap 注入失败: {e}", file=sys.stderr)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if suffix in (".html", ".js", ".css"):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(data)

    def _filter_feedback(self, target_type: str, target_id: str) -> list[dict[str, Any]]:
        items = []
        for row in _read_all_lines(self.jsonl_path):
            if row.get("target_type") != target_type:
                continue
            if row.get("target_id") != target_id:
                continue
            items.append(row)
        items.sort(key=lambda r: r.get("ts") or "")
        return items

    def _handle_api_get(self, path: str, query: dict[str, list[str]]) -> None:
        if path == "/api/health":
            total = len(_read_all_lines(self.jsonl_path))
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "jsonl_path": str(self.jsonl_path),
                    "total_lines": total,
                    "server_started_at": self.server_started_at,
                    "uid": _uid(),
                },
            )
            return

        if path == "/api/feedback":
            target_type = (query.get("target_type") or [""])[0]
            target_id = (query.get("target_id") or [""])[0]
            if target_type not in VALID_TARGET_TYPES or not target_id:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "需要 target_type 与 target_id"})
                return
            items = self._filter_feedback(target_type, target_id)
            slim = []
            for row in items:
                slim.append(
                    {
                        "ts": row.get("ts"),
                        "scores": row.get("scores"),
                        "freeform": row.get("freeform"),
                        "tags": row.get("tags"),
                    }
                )
            self._send_json(
                HTTPStatus.OK,
                {"count": len(items), "items": slim},
            )
            return

        if path == "/api/feedback/row":
            try:
                idx = int((query.get("index") or ["-1"])[0])
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "index 必须是整数"})
                return
            rows = _read_all_lines(self.jsonl_path)
            if idx < 0 or idx >= len(rows):
                self._send_json(HTTPStatus.NOT_FOUND, {"error": f"index 超界 (0..{len(rows) - 1})"})
                return
            self._send_json(HTTPStatus.OK, {"row_index": idx, "row": rows[idx]})
            return

        if path == "/api/lexicon/current":
            cur = _current_lexicon_path(self.repo_root)
            if not cur:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "未找到当前 lexicon"})
                return
            ver = _lexicon_version_from_path(cur)
            self._send_json(
                HTTPStatus.OK,
                {
                    "version": f"v{ver}" if ver is not None else "v?",
                    "path": str(cur.relative_to(self.repo_root)),
                    "content": cur.read_text(encoding="utf-8"),
                },
            )
            return

        if path == "/api/lexicon/proposals":
            proposals_dir = _lexicon_proposals_dir(self.repo_root)
            items: list[dict[str, Any]] = []
            if proposals_dir.is_dir():
                for p in sorted(proposals_dir.glob("*_proposal.json"), reverse=True):
                    ts = p.name.replace("_proposal.json", "")
                    applied = (proposals_dir / f"{ts}_applied.json").is_file()
                    try:
                        obj = json.loads(p.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    items.append(
                        {
                            "ts": ts,
                            "filename": p.name,
                            "patches_count": len(obj.get("patches") or []),
                            "withheld_count": len(obj.get("withheld") or [])
                            + len(obj.get("_auto_withheld") or []),
                            "applied": applied,
                            "base_version": obj.get("base_version"),
                            "next_version": obj.get("next_version"),
                        }
                    )
            self._send_json(HTTPStatus.OK, {"items": items})
            return

        if path.startswith("/api/lexicon/proposal/"):
            ts = unquote(path[len("/api/lexicon/proposal/") :])
            if not ts or "/" in ts or ".." in ts:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "bad ts"})
                return
            proposals_dir = _lexicon_proposals_dir(self.repo_root)
            jp = proposals_dir / f"{ts}_proposal.json"
            mp = proposals_dir / f"{ts}_proposal.md"
            if not jp.is_file():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "proposal 不存在"})
                return
            try:
                proposal_json = json.loads(jp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "proposal json 解析失败"})
                return
            proposal_md = mp.read_text(encoding="utf-8") if mp.is_file() else ""
            applied_path = proposals_dir / f"{ts}_applied.json"
            applied_record = None
            if applied_path.is_file():
                try:
                    applied_record = json.loads(applied_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    applied_record = None
            self._send_json(
                HTTPStatus.OK,
                {
                    "ts": ts,
                    "proposal_json": proposal_json,
                    "proposal_md": proposal_md,
                    "applied": applied_record,
                },
            )
            return

        if path == "/api/synthesis/current":
            sp = _synthesis_path(self.repo_root)
            if not sp.is_file():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "未找到 synthesis"})
                return
            content = sp.read_text(encoding="utf-8")
            self._send_json(
                HTTPStatus.OK,
                {
                    "path": str(sp.relative_to(self.repo_root)),
                    "content": content,
                    "last_synced": _extract_synthesis_last_synced(content),
                },
            )
            return

        if path == "/api/synthesis/proposals":
            proposals_dir = _synthesis_proposals_dir(self.repo_root)
            items: list[dict[str, Any]] = []
            if proposals_dir.is_dir():
                for p in sorted(proposals_dir.glob("*_proposal.json"), reverse=True):
                    ts = p.name.replace("_proposal.json", "")
                    applied = (proposals_dir / f"{ts}_applied.json").is_file()
                    try:
                        obj = json.loads(p.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    items.append(
                        {
                            "ts": ts,
                            "filename": p.name,
                            "patches_count": len(obj.get("patches") or []),
                            "withheld_count": len(obj.get("withheld") or [])
                            + len(obj.get("_auto_withheld") or []),
                            "applied": applied,
                            "last_synced_was": obj.get("last_synced_was"),
                        }
                    )
            self._send_json(HTTPStatus.OK, {"items": items})
            return

        if path.startswith("/api/synthesis/proposal/"):
            ts = unquote(path[len("/api/synthesis/proposal/") :])
            if not ts or "/" in ts or ".." in ts:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "bad ts"})
                return
            proposals_dir = _synthesis_proposals_dir(self.repo_root)
            jp = proposals_dir / f"{ts}_proposal.json"
            mp = proposals_dir / f"{ts}_proposal.md"
            if not jp.is_file():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "proposal 不存在"})
                return
            try:
                proposal_json = json.loads(jp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "proposal json 解析失败"})
                return
            proposal_md = mp.read_text(encoding="utf-8") if mp.is_file() else ""
            applied_path = proposals_dir / f"{ts}_applied.json"
            applied_record = None
            if applied_path.is_file():
                try:
                    applied_record = json.loads(applied_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    applied_record = None
            self._send_json(
                HTTPStatus.OK,
                {
                    "ts": ts,
                    "proposal_json": proposal_json,
                    "proposal_md": proposal_md,
                    "applied": applied_record,
                },
            )
            return

        if path == "/api/eval_lite/versions":
            self._send_json(HTTPStatus.OK, {"items": _list_eval_lite_versions(self.repo_root)})
            return

        if path == "/api/eval_lite/trials":
            try:
                version = int((query.get("version") or ["0"])[0])
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "version 必须是整数"})
                return
            self._send_json(HTTPStatus.OK, _eval_lite_trials_list(self.repo_root, version))
            return

        if path.startswith("/api/eval_lite/trial/"):
            rest = unquote(path[len("/api/eval_lite/trial/") :])
            parts = rest.split("/", 1)
            if len(parts) != 2:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "路径须为 /api/eval_lite/trial/<version>/<run_id>"})
                return
            try:
                version = int(parts[0].lstrip("vV") or parts[0])
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "version 必须是整数"})
                return
            run_id = parts[1]
            detail = _eval_lite_trial_detail(self.repo_root, version, run_id)
            if detail is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "trial 不存在"})
                return
            self._send_json(HTTPStatus.OK, detail)
            return

        if path == "/api/orchestrate/sources":
            self._send_json(
                HTTPStatus.OK,
                {"items": _list_external_sources(self.repo_root)},
            )
            return

        if path == "/api/orchestrate/source":
            rel = (query.get("path") or [""])[0]
            if not rel:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "需要 query path"})
                return
            p = _allowed_source_path(self.repo_root, unquote(rel))
            if not p:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "path 不合法或文件不存在"})
                return
            try:
                content = p.read_text(encoding="utf-8")
            except OSError as e:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
                return
            self._send_json(
                HTTPStatus.OK,
                {
                    "path": str(p.relative_to(self.repo_root)).replace("\\", "/"),
                    "content": content,
                    "bytes": len(content.encode("utf-8")),
                },
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown api path"})

    def _handle_orchestrate_run(self, body: dict[str, Any]) -> None:
        qpath, err = _resolve_orchestrate_question_md(self.repo_root, body)
        if err:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": err})
            return
        assert qpath is not None

        auto_push = body.get("auto_push", True)
        if not isinstance(auto_push, bool):
            auto_push = str(auto_push).lower() in ("1", "true", "yes")
        force_pass = bool(body.get("force_pass"))

        lock_path = self.repo_root / ORCHESTRATE_LOCK_NAME
        lock_path.touch(exist_ok=True)
        with open(lock_path, "r+") as lf:
            try:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self._send_json(
                    HTTPStatus.CONFLICT,
                    {"error": "另一条 Pipeline 正在运行，请稍后再试"},
                )
                return
            try:
                from agents_runtime.orchestrate import run_single_case

                print(
                    f"[feedback_server] orchestrate start: {qpath} "
                    f"auto_push={auto_push} force_pass={force_pass}",
                    file=sys.stderr,
                )
                res = run_single_case(
                    qpath,
                    no_push=not auto_push,
                    force_pass=force_pass,
                )
                _maybe_refresh_index(self.repo_root, force=True)
                payload = {
                    "ok": True,
                    "source_path": qpath,
                    "run_id": res.get("run_id"),
                    "status": res.get("status"),
                    "verdict": res.get("verdict"),
                    "stages_completed": res.get("stages_completed"),
                    "scores": res.get("scores"),
                    "ui_line": res.get("ui_line"),
                    "run_dir": res.get("run_dir"),
                    "next_action": res.get("next_action"),
                }
                if res.get("status") == "failed":
                    manifest_path = Path(str(res.get("run_dir") or "")) / "manifest.json"
                    if manifest_path.is_file():
                        try:
                            mf = json.loads(manifest_path.read_text(encoding="utf-8"))
                            payload["last_error"] = mf.get("last_error")
                            payload["last_stage"] = mf.get("last_stage")
                        except (OSError, json.JSONDecodeError):
                            pass
                self._send_json(HTTPStatus.OK, payload)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[feedback_server] orchestrate 失败: {e}", file=sys.stderr)
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": str(e), "source_path": qpath},
                )
            finally:
                try:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass

    def _handle_synthesis_apply(self, body: dict[str, Any]) -> None:
        proposal_ts = body.get("proposal_ts")
        if not isinstance(proposal_ts, str) or "/" in proposal_ts or ".." in proposal_ts:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "proposal_ts 不合法"})
            return
        accepted = body.get("accepted_patches") or []
        if not isinstance(accepted, list) or not accepted:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "accepted_patches 必须是非空数组"})
            return
        for p in accepted:
            if not isinstance(p, dict):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "accepted_patches 元素必须是 object"})
                return
            if not p.get("action") or not p.get("section"):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "patch 缺 action 或 section"})
                return
        reject_reasons = body.get("reject_reasons") or {}
        if not isinstance(reject_reasons, dict):
            reject_reasons = {}

        lock_path = self.repo_root / SYNTHESIS_APPLY_LOCK_NAME
        lock_path.touch(exist_ok=True)
        with open(lock_path, "r+") as lf:
            try:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self._send_json(HTTPStatus.CONFLICT, {"error": "另一个 synthesis apply 正在进行"})
                return
            try:
                result = _do_synthesis_apply(
                    self.repo_root, proposal_ts, accepted, reject_reasons
                )
                self._send_json(HTTPStatus.OK, result)
            except ValueError as e:
                msg = str(e)
                try:
                    payload = json.loads(msg)
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        payload if isinstance(payload, dict) else {"error": msg},
                    )
                except json.JSONDecodeError:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": msg})
            except Exception as e:
                print(f"[feedback_server] synthesis apply 失败: {e}", file=sys.stderr)
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
            finally:
                try:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass

    def _handle_lexicon_apply(self, body: dict[str, Any]) -> None:
        proposal_ts = body.get("proposal_ts")
        if not isinstance(proposal_ts, str) or "/" in proposal_ts or ".." in proposal_ts:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "proposal_ts 不合法"})
            return
        accepted = body.get("accepted_patches") or []
        if not isinstance(accepted, list) or not accepted:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "accepted_patches 必须是非空数组"})
            return
        for p in accepted:
            if not isinstance(p, dict):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "accepted_patches 元素必须是 object"})
                return
            if not p.get("action") or not p.get("section"):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "patch 缺 action 或 section"})
                return
        reject_reasons = body.get("reject_reasons") or {}
        if not isinstance(reject_reasons, dict):
            reject_reasons = {}

        # 全局锁：一次只允许一个 apply 进行
        lock_path = self.repo_root / LEXICON_APPLY_LOCK_NAME
        lock_path.touch(exist_ok=True)
        with open(lock_path, "r+") as lf:
            try:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self._send_json(HTTPStatus.CONFLICT, {"error": "另一个 apply 正在进行"})
                return
            try:
                result = _do_lexicon_apply(self.repo_root, proposal_ts, accepted, reject_reasons)
                _maybe_refresh_index(self.repo_root, force=True)
                self._send_json(HTTPStatus.OK, result)
            except Exception as e:
                print(f"[feedback_server] apply 失败: {e}", file=sys.stderr)
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
            finally:
                try:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass

    def _handle_eval_lite_run(self, body: dict[str, Any]) -> None:
        try:
            version = int(body.get("lexicon_version"))
        except (TypeError, ValueError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "lexicon_version 必须是整数"})
            return
        pick = body.get("pick") or "last5_accepted"
        if pick not in ("last5_accepted", "last5_pushed", "judge_top5"):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "pick 不合法"})
            return
        cmd = [
            sys.executable,
            "-m",
            "agents_runtime.eval_lite",
            "--lexicon-version",
            str(version),
            "--pick",
            pick,
        ]
        run_ids = body.get("run_ids")
        if run_ids:
            if isinstance(run_ids, list):
                ids_str = ",".join(str(x) for x in run_ids)
            else:
                ids_str = str(run_ids)
            if ids_str.strip():
                cmd.extend(["--run-ids", ids_str.strip()])
        print(f"[feedback_server] eval_lite: {' '.join(cmd)}", file=sys.stderr)
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=900,
            )
        except subprocess.TimeoutExpired:
            self._send_json(HTTPStatus.GATEWAY_TIMEOUT, {"error": "eval_lite 超时（>15min）"})
            return
        if proc.returncode not in (0, 1):
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "eval_lite 失败", "stderr": proc.stderr[-4000:]},
            )
            return
        summary_rel = f"eval/lexicon_trials/v{version}/summary.md"
        result_obj: dict[str, Any] = {}
        try:
            result_obj = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            pass
        trials = _eval_lite_trials_list(self.repo_root, version)
        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "summary_path": summary_rel,
                "cli_result": result_obj,
                "trials": trials,
                "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
            },
        )

    def _handle_eval_lite_accept(self, body: dict[str, Any]) -> None:
        line, err = _validate_trial_accept_body(body)
        if err:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": err})
            return
        assert line is not None
        if line.get("skipped"):
            self._send_json(HTTPStatus.OK, {"ok": True, "skipped": True})
            return
        total = _append_line(self.jsonl_path, line)
        self._send_json(
            HTTPStatus.OK,
            {"ok": True, "total": total, "line_index": total - 1},
        )

    def _handle_api_post(self, path: str) -> None:
        if path == "/api/lexicon/apply":
            body = self._read_json_body()
            if body is None:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON 解析失败"})
                return
            self._handle_lexicon_apply(body)
            return
        if path == "/api/synthesis/apply":
            body = self._read_json_body()
            if body is None:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON 解析失败"})
                return
            self._handle_synthesis_apply(body)
            return
        if path == "/api/eval_lite/run":
            body = self._read_json_body()
            if body is None:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON 解析失败"})
                return
            self._handle_eval_lite_run(body)
            return
        if path == "/api/eval_lite/accept":
            body = self._read_json_body()
            if body is None:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON 解析失败"})
                return
            self._handle_eval_lite_accept(body)
            return
        if path == "/api/orchestrate/run":
            body = self._read_json_body()
            if body is None:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON 解析失败"})
                return
            self._handle_orchestrate_run(body)
            return
        if path != "/api/feedback":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown api path"})
            return
        body = self._read_json_body()
        if body is None:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON 解析失败"})
            return
        line, err = _validate_post_body(body)
        if err:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": err})
            return
        assert line is not None
        total = _append_line(self.jsonl_path, line)
        line_index = total - 1
        self._send_json(
            HTTPStatus.OK,
            {"ok": True, "total": total, "line_index": line_index},
        )

    def _serve_context_curator(self, url_path: str) -> None:
        prefix = "/context-curator"
        if url_path == prefix or url_path == prefix + "/":
            self._serve_file(self.context_curator_dir / "index.html")
            return
        if not url_path.startswith(prefix + "/"):
            self._send_text(HTTPStatus.NOT_FOUND, "not found")
            return
        rel = url_path[len(prefix) + 1 :]
        if not rel or ".." in rel.split("/"):
            self._send_text(HTTPStatus.BAD_REQUEST, "bad path")
            return
        self._serve_file(self.context_curator_dir / rel)

    def _serve_static(self, url_path: str) -> None:
        if url_path == "/":
            self._redirect("/dev-hub.html")
            return

        if url_path.startswith("/context-curator"):
            self._serve_context_curator(url_path)
            return

        if url_path == "/runs/_index.js":
            self._serve_file(self.runs_dir / "_index.js")
            return

        if url_path.startswith("/runs/"):
            parts = url_path.strip("/").split("/")
            if len(parts) >= 3:
                run_id, filename = parts[1], parts[2]
                if ".." in run_id or ".." in filename:
                    self._send_text(HTTPStatus.BAD_REQUEST, "bad path")
                    return
                run_dir = self.runs_dir / run_id
                if not run_dir.is_dir():
                    self._send_text(HTTPStatus.NOT_FOUND, "run not found")
                    return
                self._serve_file(run_dir / filename)
                return

        if url_path.startswith("/eval/"):
            rel = url_path.lstrip("/")
            if ".." in rel.split("/"):
                self._send_text(HTTPStatus.BAD_REQUEST, "bad path")
                return
            self._serve_file(self.repo_root / rel)
            return

        rel = url_path.lstrip("/")
        if not rel or ".." in rel:
            self._send_text(HTTPStatus.BAD_REQUEST, "bad path")
            return
        self._serve_file(self.proto_dir / rel)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api_get(parsed.path, parse_qs(parsed.query))
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api_post(parsed.path)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})


def _port_in_use_hint(port: int) -> None:
    try:
        out = subprocess.run(
            ["lsof", "-iTCP:%d" % port, "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if out.stdout.strip():
            print(f"[feedback_server] 占用 {port} 的进程:\n{out.stdout.strip()}", file=sys.stderr)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _bind_server(
    handler: type[FeedbackHandler],
    host: str,
    preferred: int,
    *,
    strict: bool,
) -> tuple[ThreadingHTTPServer, int]:
    candidates = [preferred]
    if not strict:
        candidates.extend(p for p in FALLBACK_PORTS if p != preferred)
    last_err: OSError | None = None
    for port in candidates:
        try:
            server = ThreadingHTTPServer((host, port), handler)
            if port != preferred:
                print(
                    f"[feedback_server] 端口 {preferred} 已被占用，改用 {port}",
                    file=sys.stderr,
                )
                _port_in_use_hint(preferred)
            return server, port
        except OSError as e:
            if e.errno != errno.EADDRINUSE:
                raise
            last_err = e
    assert last_err is not None
    _port_in_use_hint(preferred)
    raise OSError(
        errno.EADDRINUSE,
        f"端口 {[preferred, *FALLBACK_PORTS]} 均不可用。"
        f" 可先结束旧进程: kill $(lsof -t -iTCP:{preferred} -sTCP:LISTEN)",
        "",
    ) from last_err


def main() -> int:
    parser = argparse.ArgumentParser(description="Growth 本地开发台（静态页 + feedback API）")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--strict-port",
        action="store_true",
        help="指定端口被占用时直接失败（默认自动尝试 8766 等）",
    )
    parser.add_argument("--open", action="store_true", help="启动后打开浏览器")
    parser.add_argument(
        "--open-page",
        default="/dev-hub.html",
        help="--open 时打开的页面路径（默认开发台导航）",
    )
    parser.add_argument("--root", type=Path, default=None, help="仓库根目录")
    parser.add_argument(
        "--refresh-all",
        action="store_true",
        help="启动前强制刷新 runs/_index.js 与 context chunks",
    )
    args = parser.parse_args()

    root = _repo_root(args.root)
    jsonl = _jsonl_path(root)
    jsonl.parent.mkdir(parents=True, exist_ok=True)

    _maybe_refresh_index(root, force=args.refresh_all)
    _maybe_refresh_context_chunks(root, force=args.refresh_all)

    FeedbackHandler.repo_root = root
    FeedbackHandler.proto_dir = root / "crystallization-prototype"
    FeedbackHandler.context_curator_dir = root / "pipeline-b-context-curator"
    FeedbackHandler.runs_dir = root / "runs"
    FeedbackHandler.jsonl_path = jsonl
    FeedbackHandler.server_started_at = _now_iso()

    server, bound_port = _bind_server(
        FeedbackHandler,
        "127.0.0.1",
        args.port,
        strict=args.strict_port,
    )
    base = f"http://127.0.0.1:{bound_port}"
    hub_url = base + "/dev-hub.html"
    total = len(_read_all_lines(jsonl))
    print("=" * 60, file=sys.stderr)
    print(f"开发台已启动  {hub_url}", file=sys.stderr)
    print(f"  主站      {base}/index.html", file=sys.stderr)
    print(f"  Inbox     {base}/inbox.html", file=sys.stderr)
    print(f"  Pipeline  {base}/pipeline_run.html", file=sys.stderr)
    print(f"  维护台    {base}/maintainer-hub.html", file=sys.stderr)
    print(f"端口: {bound_port}  ·  feedback: {total} 条  ·  {jsonl}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    if args.open:
        page = args.open_page if args.open_page.startswith("/") else "/" + args.open_page
        webbrowser.open(base + page)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[feedback_server] 已停止", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

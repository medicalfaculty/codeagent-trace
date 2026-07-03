#!/usr/bin/env python3
import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


HOME = Path("/data/home/sheshuchen")
CODEX_DIR = HOME / ".codex"
CLAUDE_DIR = HOME / ".claude"
OUT = Path("/data/home/sheshuchen/codeagent-trace")

SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|secret|password|credential|bearer)",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(?i)(sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{12,}|Bearer\s+[A-Za-z0-9._~+/=-]{12,})"
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:API[_-]?KEY|ACCESS[_-]?TOKEN|REFRESH[_-]?TOKEN|SECRET|PASSWORD|CREDENTIAL)[A-Z0-9_]*\s*[:=]\s*)([^\s'\"`,;]+)"
)


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def ensure_empty(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def redact_string(value: str) -> str:
    value = SECRET_VALUE_RE.sub("[REDACTED_SECRET]", value)
    return SECRET_ASSIGNMENT_RE.sub(r"\1[REDACTED]", value)


def sanitize(obj: Any, key: str = "") -> Any:
    if SECRET_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            if k == "encrypted_content":
                cleaned[k] = "[OMITTED_ENCRYPTED_REASONING_PAYLOAD]"
            elif k == "base_instructions" and isinstance(v, dict):
                text = v.get("text", "")
                cleaned[k] = {
                    "text_preview": truncate(redact_string(str(text)), 1000),
                    "omitted_full_text": True,
                }
            elif k in {"developer_instructions", "system_instruction"}:
                cleaned[k] = truncate(redact_string(str(v)), 1000)
            else:
                cleaned[k] = sanitize(v, k)
        return cleaned
    if isinstance(obj, list):
        return [sanitize(v, key) for v in obj]
    if isinstance(obj, str):
        return redact_string(obj)
    return obj


def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in {"text", "input_text"}:
                    parts.append(str(item.get("text", "")))
                elif item.get("type") == "tool_result":
                    parts.append(str(item.get("content", "")))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def iso_to_epoch_ms(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def normalize_claude(path: Path, source_path: str) -> List[Dict[str, Any]]:
    events = []
    for idx, item in enumerate(read_jsonl(path)):
        session_id = item.get("sessionId")
        base = {
            "source": "claude",
            "session_id": session_id,
            "timestamp": item.get("timestamp"),
            "timestamp_ms": iso_to_epoch_ms(item.get("timestamp")),
            "source_file": source_path,
            "source_index": idx,
            "raw_type": item.get("type"),
        }
        typ = item.get("type")
        if typ == "queue-operation":
            events.append({**base, "event_type": f"queue_{item.get('operation')}", "text": truncate(str(item.get("content", "")), 2000)})
        elif typ == "ai-title":
            events.append({**base, "event_type": "title", "text": item.get("aiTitle")})
        elif typ == "user":
            msg = item.get("message", {})
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "tool_result":
                        events.append({
                            **base,
                            "event_type": "tool_result",
                            "tool_call_id": part.get("tool_use_id"),
                            "is_error": part.get("is_error"),
                            "output_preview": truncate(str(part.get("content", "")), 3000),
                        })
            else:
                events.append({**base, "event_type": "user_message", "text": truncate(content_text(content), 3000)})
        elif typ == "assistant":
            msg = item.get("message", {})
            usage = msg.get("usage")
            for part in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    events.append({**base, "event_type": "assistant_text", "text": truncate(str(part.get("text", "")), 3000), "usage": sanitize(usage)})
                elif part.get("type") == "thinking":
                    events.append({**base, "event_type": "assistant_thinking", "text": truncate(str(part.get("thinking", "")), 2000), "usage": sanitize(usage)})
                elif part.get("type") == "tool_use":
                    events.append({
                        **base,
                        "event_type": "tool_call",
                        "tool_call_id": part.get("id"),
                        "tool_name": part.get("name"),
                        "tool_input": sanitize(part.get("input")),
                        "usage": sanitize(usage),
                    })
        elif typ in {"system", "attachment", "mode", "permission-mode", "last-prompt"}:
            events.append({**base, "event_type": typ, "text": truncate(content_text(item.get("content") or item.get("attachment") or item), 1000)})
    return events


def normalize_codex(path: Path, source_path: str) -> List[Dict[str, Any]]:
    events = []
    for idx, item in enumerate(read_jsonl(path)):
        payload = item.get("payload", {})
        session_id = payload.get("id") if item.get("type") == "session_meta" else payload.get("session_id")
        base = {
            "source": "codex",
            "session_id": session_id,
            "timestamp": item.get("timestamp"),
            "timestamp_ms": iso_to_epoch_ms(item.get("timestamp")),
            "source_file": source_path,
            "source_index": idx,
            "raw_type": item.get("type"),
        }
        typ = item.get("type")
        if typ == "session_meta":
            events.append({
                **base,
                "event_type": "session_meta",
                "cwd": payload.get("cwd"),
                "model_provider": payload.get("model_provider"),
                "cli_version": payload.get("cli_version"),
            })
        elif typ == "turn_context":
            events.append({
                **base,
                "event_type": "turn_context",
                "turn_id": payload.get("turn_id"),
                "cwd": payload.get("cwd"),
                "model": payload.get("model"),
                "approval_policy": payload.get("approval_policy"),
                "sandbox_policy": sanitize(payload.get("sandbox_policy")),
            })
        elif typ == "event_msg":
            event_type = payload.get("type")
            if event_type == "token_count":
                info = payload.get("info") or {}
                events.append({
                    **base,
                    "event_type": "token_count",
                    "token_usage": sanitize(info.get("last_token_usage")),
                    "total_token_usage": sanitize(info.get("total_token_usage")),
                    "rate_limits": sanitize(payload.get("rate_limits")),
                })
            else:
                events.append({**base, "event_type": event_type or "event_msg", "payload": sanitize(payload)})
        elif typ == "response_item":
            ptype = payload.get("type")
            if ptype == "function_call":
                args = payload.get("arguments")
                try:
                    args = json.loads(args) if isinstance(args, str) else args
                except Exception:
                    pass
                events.append({
                    **base,
                    "event_type": "tool_call",
                    "tool_call_id": payload.get("call_id"),
                    "tool_name": payload.get("name"),
                    "tool_input": sanitize(args),
                })
            elif ptype == "function_call_output":
                events.append({
                    **base,
                    "event_type": "tool_result",
                    "tool_call_id": payload.get("call_id"),
                    "output_preview": truncate(str(sanitize(payload.get("output"))), 3000),
                })
            elif ptype == "message":
                role = payload.get("role")
                text = content_text(payload.get("content"))
                if role in {"user", "assistant"}:
                    events.append({**base, "event_type": f"{role}_message", "text": truncate(text, 3000)})
            elif ptype == "reasoning":
                summary = payload.get("summary")
                events.append({**base, "event_type": "assistant_reasoning", "summary": sanitize(summary)})
        elif typ == "compacted":
            events.append({**base, "event_type": "compacted", "payload": sanitize(payload)})
    return events


def export_raw_and_normalized() -> Dict[str, Any]:
    raw_root = OUT / "data" / "raw-sanitized"
    norm_root = OUT / "data" / "normalized"
    summaries_root = OUT / "data" / "summaries"
    ensure_empty(raw_root)
    ensure_empty(norm_root)
    ensure_empty(summaries_root)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [],
        "notes": [
            "Auth/config/cache files are excluded.",
            "Common secret-looking keys and values are redacted.",
            "Codex encrypted reasoning payloads are omitted.",
        ],
    }

    all_events: List[Dict[str, Any]] = []
    session_summaries = []

    for path in sorted((CODEX_DIR / "sessions").glob("**/*.jsonl")):
        rel = path.relative_to(CODEX_DIR / "sessions")
        out_path = raw_root / "codex" / "sessions" / rel
        records = [sanitize(obj) for obj in read_jsonl(path)]
        count = write_jsonl(out_path, records)
        events = normalize_codex(path, str(path))
        all_events.extend(events)
        session_summaries.append(summarize_session("codex", str(path), records, events))
        manifest["sources"].append({"source": "codex_session", "path": str(path), "records": count, "output": str(out_path.relative_to(OUT))})

    for path in sorted((CLAUDE_DIR / "projects").glob("**/*.jsonl")):
        rel = path.relative_to(CLAUDE_DIR / "projects")
        out_path = raw_root / "claude" / "projects" / rel
        records = [sanitize(obj) for obj in read_jsonl(path)]
        count = write_jsonl(out_path, records)
        events = normalize_claude(path, str(path))
        all_events.extend(events)
        session_summaries.append(summarize_session("claude", str(path), records, events))
        manifest["sources"].append({"source": "claude_project", "path": str(path), "records": count, "output": str(out_path.relative_to(OUT))})

    all_events.sort(key=lambda e: (e.get("timestamp") or "", e.get("source"), e.get("source_file"), e.get("source_index")))
    write_jsonl(norm_root / "events.jsonl", all_events)
    write_jsonl(norm_root / "tool_events.jsonl", (e for e in all_events if e.get("event_type") in {"tool_call", "tool_result"}))

    write_json(summaries_root / "manifest.json", manifest)
    write_json(summaries_root / "session_summary.json", session_summaries)
    write_json(summaries_root / "event_type_counts.json", dict(Counter(e.get("event_type") for e in all_events)))
    export_codex_sqlite_summary(summaries_root)
    return {"events": len(all_events), "sessions": len(session_summaries), "sources": len(manifest["sources"])}


def summarize_session(source: str, path: str, records: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    session_ids = [e.get("session_id") for e in events if e.get("session_id")]
    tool_calls = [e for e in events if e.get("event_type") == "tool_call"]
    usage_events = [e for e in events if e.get("usage") or e.get("token_usage")]
    first_user = next((e.get("text") for e in events if e.get("event_type") == "user_message" and e.get("text")), "")
    return {
        "source": source,
        "source_file": path,
        "source_file_id": stable_id(path),
        "records": len(records),
        "events": len(events),
        "session_ids": sorted(set(session_ids)),
        "first_timestamp": min((e.get("timestamp") for e in events if e.get("timestamp")), default=None),
        "last_timestamp": max((e.get("timestamp") for e in events if e.get("timestamp")), default=None),
        "event_type_counts": dict(Counter(e.get("event_type") for e in events)),
        "tool_call_count": len(tool_calls),
        "tool_names": dict(Counter(e.get("tool_name") for e in tool_calls if e.get("tool_name"))),
        "usage_event_count": len(usage_events),
        "first_user_message_preview": truncate(first_user, 500),
    }


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def export_codex_sqlite_summary(out_dir: Path) -> None:
    db = CODEX_DIR / "logs_2.sqlite"
    if not db.exists():
        return
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    row = cur.execute("select count(*), min(ts), max(ts), sum(estimated_bytes) from logs").fetchone()
    level_target = cur.execute(
        "select level, target, count(*) as n from logs group by level, target order by n desc limit 100"
    ).fetchall()
    samples = cur.execute(
        "select ts, ts_nanos, level, target, feedback_log_body, module_path, file, line, thread_id, process_uuid, estimated_bytes from logs order by ts desc, ts_nanos desc limit 200"
    ).fetchall()
    con.close()
    write_json(out_dir / "codex_sqlite_summary.json", {
        "source_db": str(db),
        "row_count": row[0],
        "min_ts": row[1],
        "max_ts": row[2],
        "estimated_bytes_sum": row[3],
        "level_target_top100": [
            {"level": level, "target": target, "count": count}
            for level, target, count in level_target
        ],
        "recent_samples": [
            {
                "ts": ts,
                "ts_nanos": ts_nanos,
                "level": level,
                "target": target,
                "feedback_log_body_preview": truncate(str(sanitize(body or "")), 1000),
                "module_path": module_path,
                "file": file,
                "line": line,
                "thread_id": thread_id,
                "process_uuid": process_uuid,
                "estimated_bytes": estimated_bytes,
            }
            for ts, ts_nanos, level, target, body, module_path, file, line, thread_id, process_uuid, estimated_bytes in samples
        ],
    })


def main() -> None:
    result = export_raw_and_normalized()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

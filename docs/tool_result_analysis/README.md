# Tool Result 与工具耗时分析

本文档基于仓库中的脱敏 trace 数据统计：

- Claude：`data/raw-sanitized/claude/projects/**/*.jsonl`
- Codex：`data/raw-sanitized/codex/sessions/**/*.jsonl`

统计方法是直接读取原始脱敏 JSONL，而不是读取 `data/normalized/tool_events.jsonl`，因为归一化文件里的 `output_preview` 可能已经截断，不适合判断“最长 tool result”。

## 结论

### 最长的 tool result

最长的 tool result 来自 Claude 的一次 `Read` 工具调用：

- 来源：Claude
- 工具：`Read`
- tool id：`toolu_01FBrZJm5Xb7YeWa9jCtTnjn`
- 输出长度：`25164` 字符，`25193` 字节
- 调用时间：`2026-06-26T09:29:19.887Z`
- 返回时间：`2026-06-26T09:29:19.945Z`
- 事件时间差：约 `58 ms`
- trace 文件：`data/raw-sanitized/claude/projects/-data-home-sheshuchen-MiMo-Code-agent-trace-proxy-logs/c068b59d-69c2-418f-97f1-1615d6a5e0be.jsonl`
- 调用位置：第 `797` 行附近
- 返回位置：第 `798` 行附近

这次调用做的事情是读取下面这个 TypeScript 文件：

```text
/data/home/sheshuchen/MiMo-Code/packages/opencode/src/cli/cmd/run.ts
```

输入示例：

```json
{"file_path": "/data/home/sheshuchen/MiMo-Code/packages/opencode/src/cli/cmd/run.ts"}
```

返回内容是该文件的带行号文本。开头示例：

```text
1	import type { Argv } from "yargs"
2	import path from "path"
3	import { pathToFileURL } from "url"
4	import { UI } from "../ui"
5	import { cmd } from "./cmd"
6	import { Flag } from "../../flag/flag"
7	import { bootstrap } from "../bootstrap"
8	import { EOL } from "os"
9	import { Filesystem, Log } from "../../util"
10	import { createOpencodeClient, type OpencodeClient, type ToolPart } from "@mimo-ai/sdk/v2"
```

这个结果最长的原因不是工具执行慢，而是 `Read` 返回了一个较长源码文件的完整文本。

### 可能用时最长的工具调用

按“工具调用事件时间戳”和“工具结果事件时间戳”的差值估算，可能用时最长的是 Claude 的一次 `Bash` 调用：

- 来源：Claude
- 工具：`Bash`
- tool id：`toolu_01SopRAYmDv31ceMoK295K4A`
- 输出长度：`2999` 字符，`2999` 字节
- 调用时间：`2026-06-26T09:34:00.171Z`
- 返回时间：`2026-06-26T10:25:33.221Z`
- 事件时间差：`3093050 ms`，约 `51 分 33 秒`
- trace 文件：`data/raw-sanitized/claude/projects/-data-home-sheshuchen-MiMo-Code-agent-trace-proxy-logs/c068b59d-69c2-418f-97f1-1615d6a5e0be.jsonl`
- 调用位置：第 `868` 行附近
- 返回位置：第 `869` 行附近

这次调用做的事情是用项目里的 Python 环境加载 Qwen3.5-9B tokenizer，然后打印 tokenizer 的 chat template 前 3000 个字符，用于检查 Qwen3.5 的工具调用格式：

```bash
/data/home/sheshuchen/MiMo-Code/.venv-sglang/bin/python3 -c "
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained('/data2/share/zsz_awt/models/Qwen3.5-9B', trust_remote_code=True)
# Print the chat template
tmpl = tok.chat_template
print(tmpl[:3000] if tmpl else 'NO TEMPLATE')
" 2>/dev/null
```

返回内容是 Jinja 风格的 chat template，开头示例：

```text
{%- set image_count = namespace(value=0) %}
{%- set video_count = namespace(value=0) %}
{%- macro render_content(content, do_vision_count, is_system_content=false) %}
    {%- if content is string %}
        {{- content }}
    {%- elif content is iterable and content is not mapping %}
```

需要注意：这个“51 分 33 秒”是按 Claude JSONL 中相邻 tool_use/tool_result 事件时间戳估算出来的，不一定等于命令真实运行耗时。Claude 的记录里没有 Bash wall time 字段；如果中间发生了会话暂停、客户端等待、后台任务通知延迟或恢复上下文，事件时间差会被拉长。因此这里用“可能用时最长”，而不是断言它一定是实际 CPU/IO 执行最久的命令。

## 复现统计命令

在仓库根目录运行下面命令可以重新统计最长 tool result 和最长事件时间差：

```bash
python3 - <<'PY'
import json
import re
from pathlib import Path
from datetime import datetime

def parse_ts(value):
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000
    except Exception:
        return None

def measure(value):
    if value is None:
        return 0, 0
    if isinstance(value, str):
        return len(value), len(value.encode("utf-8"))
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return len(text), len(text.encode("utf-8"))

calls = {}
results = []

for path in sorted(Path("data/raw-sanitized").rglob("*.jsonl")):
    source = "claude" if "/claude/" in str(path) else "codex"
    for index, line in enumerate(path.read_text(errors="replace").splitlines()):
        if not line.strip():
            continue
        item = json.loads(line)
        ts = parse_ts(item.get("timestamp"))

        if source == "codex" and item.get("type") == "response_item" and isinstance(item.get("item"), dict):
            payload = item["item"]
            if payload.get("type") == "function_call":
                call_id = payload.get("call_id") or payload.get("id") or payload.get("callId")
                calls[(source, call_id)] = {
                    "source": source,
                    "id": call_id,
                    "name": payload.get("name"),
                    "input": payload.get("arguments"),
                    "file": str(path),
                    "index": index,
                    "timestamp": item.get("timestamp"),
                    "ts": ts,
                }
            elif payload.get("type") == "function_call_output":
                call_id = payload.get("call_id") or payload.get("id") or payload.get("callId")
                output = payload.get("output") or payload.get("content") or payload.get("result")
                call = calls.get((source, call_id), {})
                chars, bytes_ = measure(output)
                results.append({
                    "source": source,
                    "id": call_id,
                    "name": call.get("name"),
                    "input": call.get("input"),
                    "output": output,
                    "chars": chars,
                    "bytes": bytes_,
                    "file": str(path),
                    "call_index": call.get("index"),
                    "result_index": index,
                    "call_timestamp": call.get("timestamp"),
                    "result_timestamp": item.get("timestamp"),
                    "call_ts": call.get("ts"),
                    "result_ts": ts,
                })

        if source == "claude":
            message = item.get("message") if isinstance(item.get("message"), dict) else {}
            content = message.get("content")
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "tool_use":
                        call_id = part.get("id")
                        calls[(source, call_id)] = {
                            "source": source,
                            "id": call_id,
                            "name": part.get("name"),
                            "input": part.get("input"),
                            "file": str(path),
                            "index": index,
                            "timestamp": item.get("timestamp"),
                            "ts": ts,
                        }
                    elif part.get("type") == "tool_result":
                        call_id = part.get("tool_use_id") or part.get("id")
                        output = part.get("content")
                        call = calls.get((source, call_id), {})
                        chars, bytes_ = measure(output)
                        results.append({
                            "source": source,
                            "id": call_id,
                            "name": call.get("name"),
                            "input": call.get("input"),
                            "output": output,
                            "chars": chars,
                            "bytes": bytes_,
                            "file": str(path),
                            "call_index": call.get("index"),
                            "result_index": index,
                            "call_timestamp": call.get("timestamp"),
                            "result_timestamp": item.get("timestamp"),
                            "call_ts": call.get("ts"),
                            "result_ts": ts,
                        })

for result in results:
    if result["call_ts"] is not None and result["result_ts"] is not None:
        result["duration_ms_by_event_ts"] = result["result_ts"] - result["call_ts"]
    else:
        result["duration_ms_by_event_ts"] = None
    output = result["output"] if isinstance(result["output"], str) else ""
    match = re.search(r"Wall time: ([0-9.]+) seconds", output)
    result["duration_ms_by_wall_time"] = float(match.group(1)) * 1000 if match else None

longest_result = max(results, key=lambda item: item["chars"])
longest_duration = max(
    [item for item in results if item["duration_ms_by_event_ts"] is not None],
    key=lambda item: item["duration_ms_by_event_ts"],
)

for name, result in [("longest_result", longest_result), ("longest_duration", longest_duration)]:
    print(name)
    for key in [
        "source", "name", "id", "chars", "bytes", "file",
        "call_index", "result_index", "call_timestamp",
        "result_timestamp", "duration_ms_by_event_ts",
    ]:
        print(f"  {key}: {result.get(key)}")
    print()
PY
```

## 统计口径

- “最长 tool result”按完整输出的字符数排序，同时记录 UTF-8 字节数。
- Claude 的工具调用通过 `message.content[].type == "tool_use"` 和 `tool_result` 配对。
- Codex 的工具调用通过 `response_item.item.type == "function_call"` 和 `function_call_output` 配对。
- “可能用时最长”优先使用调用事件与结果事件的时间戳差；当前脱敏数据中没有可统一使用的真实 wall time 字段。
- Codex 脱敏 session 中的部分结果预览含 `Wall time` 文本，但原始脱敏数据本轮未解析出可和全部 Claude 记录公平比较的 wall time，因此报告主结论采用统一的事件时间戳口径。

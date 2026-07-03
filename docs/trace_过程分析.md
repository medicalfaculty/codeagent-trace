# Codex 与 Claude 历史 trace 整理和典型过程分析

生成时间：2026-07-03  
数据来源：

- Codex：`/data/home/sheshuchen/.codex/history.jsonl`、`/data/home/sheshuchen/.codex/sessions/`、`/data/home/sheshuchen/.codex/logs_2.sqlite`
- Claude Code：`/data/home/sheshuchen/.claude/history.jsonl`、`/data/home/sheshuchen/.claude/projects/`

## 找到的历史位置

### Codex

Codex 的 `history.jsonl` 只保存用户输入级别的历史，字段主要是：

```json
{"session_id": "...", "ts": 1781607816, "text": "..."}
```

更完整的交互链路在：

```text
~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl
```

这些文件包含：

- `session_meta`：会话 ID、cwd、模型提供方、CLI 版本等。
- `turn_context`：当前 turn 的 cwd、sandbox、approval policy、模型等。
- `response_item`：消息、工具调用、工具返回、reasoning 等。
- `event_msg`：task started/complete、token_count、patch apply、web search 等事件。
- `compacted`：上下文压缩事件。

Codex 还有：

```text
~/.codex/logs_2.sqlite
```

它更像运行日志数据库，包含 `level`、`target`、`feedback_log_body`、线程、进程等字段。本仓库没有复制 SQLite 原库，只导出了统计摘要和最近样本。

### Claude Code

Claude 的 `history.jsonl` 记录用户输入和项目/session 关联，字段主要是：

```json
{"display": "...", "timestamp": 1782454094443, "project": "...", "sessionId": "..."}
```

完整交互链路在：

```text
~/.claude/projects/<project-key>/<session-id>.jsonl
```

这些文件包含：

- `queue-operation`：任务入队、出队。
- `user`：用户请求或工具结果。
- `assistant`：模型文本、thinking、tool_use、usage。
- `attachment`：工具列表、agent 列表、skill 列表等上下文注入。
- `ai-title`：会话标题。
- `last-prompt`、`mode`、`permission-mode` 等状态事件。

## 本次导出内容

导出脚本：

```text
tools/export_traces.py
```

导出结果：

- 源文件：34 个
- 规范化事件：21873 条
- raw 脱敏 JSONL 文件：34 个
- 数据目录总大小：约 70MB

主要目录：

```text
data/raw-sanitized/codex/sessions/
data/raw-sanitized/claude/projects/
data/normalized/events.jsonl
data/normalized/tool_events.jsonl
data/summaries/session_summary.json
data/summaries/event_type_counts.json
data/summaries/codex_sqlite_summary.json
```

事件类型计数中，最关键的是：

```text
tool_call: 5103
tool_result: 5103
token_count: 2455
assistant_reasoning: 1706
assistant_message: 1773
user_message: 494
turn_context: 207
compacted/context_compacted: 36
```

这说明导出的数据里已经能看到大量“模型请求工具”和“工具返回结果”的闭环。

## 脱敏和排除策略

没有提交以下文件：

- `~/.codex/auth.json`
- `~/.claude/.credentials.json`
- `~/.codex/*.sqlite` 原库和 WAL/SHM
- 缓存、插件仓库、shell snapshot 原始目录

导出时做了以下处理：

- 字段名包含 `api_key`、`authorization`、`token`、`secret`、`password`、`credential` 的值替换为 `[REDACTED]`。
- 字符串里的 `Bearer ...`、`sk-...`、`ghp_...` 等疑似密钥替换为 `[REDACTED_SECRET]`。
- 字符串里的 `FOO_API_KEY=...`、`TOKEN: ...` 等赋值形式替换为 `[REDACTED]`。
- Codex 的 `encrypted_content` 替换为 `[OMITTED_ENCRYPTED_REASONING_PAYLOAD]`。
- Codex 的长 `base_instructions` 只保留短 preview。

## 典型过程分析：Claude 顺序执行 10 条 Bash 命令

典型 session：

```text
session_id: 7d3d41c9-981f-4641-994d-73ff3f89d894
raw: data/raw-sanitized/claude/projects/-data-home-sheshuchen-ssc-dataset-trace-forest-exp5-context-fill-workspace/7d3d41c9-981f-4641-994d-73ff3f89d894.jsonl
normalized: data/normalized/events.jsonl
```

用户任务：

```text
请依次（每步单独执行，不要并行）用Bash工具执行以下10条命令，每条执行完再执行下一条：
步骤1: echo 'step1'
...
步骤10: echo 'step10'
全部完成后输出一行总结。
```

这个 session 很适合作为典型，因为它没有复杂外部环境依赖，工具调用链路清楚。

### 事件顺序

1. `queue_enqueue`：任务进入 Claude 的执行队列。
2. `queue_dequeue`：任务被取出执行。
3. `user_message`：用户完整任务进入上下文。
4. `attachment`：系统注入 agent/tool/skill 列表。
5. `assistant_text`：模型先输出“我会逐条顺序执行”。
6. `tool_call`：第一次调用 `Bash`，命令是 `echo 'step1'`。
7. `tool_result`：工具返回 `step1`。
8. 模型根据工具结果继续输出下一次 `tool_call`。
9. 以上过程重复到 `step10`。
10. `assistant_text`：最终总结“全部 10 条命令已严格按顺序逐条执行完毕”。

### 工具调用和返回配对

规范化事件里有 10 个 `tool_call` 和 10 个 `tool_result`，全部按 `tool_call_id` 对应：

```text
06:18:29.280 tool_call   Bash echo 'step1'
06:18:29.376 tool_result      step1
06:18:33.209 tool_call   Bash echo 'step2'
06:18:33.256 tool_result      step2
06:18:36.568 tool_call   Bash echo 'step3'
06:18:36.597 tool_result      step3
...
06:19:00.471 tool_call   Bash echo 'step10'
06:19:00.507 tool_result      step10
```

工具本身执行很快，`tool_call` 到 `tool_result` 的间隔大约是 24 到 96 毫秒。相邻步骤之间约 2.7 到 3.9 秒，主要是“工具结果回填上下文 -> 模型 decode 下一次 tool_use”的时间，而不是 Bash 执行时间。

### token 和 cache 行为

每次 `tool_call` 事件都带有 Claude usage 信息。这个 session 里可以看到：

```text
第 1 次 tool_call: cache_read_input_tokens=28854, cache_creation_input_tokens=2157
第 2 次 tool_call: cache_read_input_tokens=31011, cache_creation_input_tokens=109
第 3 次 tool_call: cache_read_input_tokens=31120, cache_creation_input_tokens=90
...
第 9 次 tool_call: cache_read_input_tokens=31660, cache_creation_input_tokens=90
第10 次 tool_call: cache_read_input_tokens=31750, cache_creation_input_tokens=188
```

这说明 Claude Code 每轮工具调用后会把新的 tool result 加回上下文，然后再次请求模型。大部分上下文通过 cache read 复用，新增内容对应较小的 cache creation。这个过程正好对应 agentic loop：

```text
prefill/cache read 历史上下文
decode 生成 tool_use
执行工具
等待 tool_result
把 tool_result 追加进上下文
下一轮继续 prefill/cache read + decode
```

### 对 agent trace 研究的意义

这个例子展示了工具调用型 agent 的核心结构：

- 用户的单个高层任务会展开为多轮模型请求。
- 每轮模型请求通常只生成一个工具调用。
- 工具结果会作为新的 `user`/`tool_result` 消息追加到上下文。
- 上下文不断增长，但可通过 prompt/cache read 复用大量前缀。
- 工具执行时间和模型下一步生成时间可以从相邻事件时间戳估计。

如果后续要分析 prefill/decode 或 cache 命中，`tool_call -> tool_result -> next tool_call` 之间的事件序列是关键。Claude 的 usage 字段已经直接给出 cache read/create token；Codex 的 `token_count` 和 `response_item` 能提供类似的模型 token 用量和工具调用闭环。

## 如何继续分析

查看所有工具事件：

```bash
python3 - <<'PY'
import json
for line in open('data/normalized/tool_events.jsonl', encoding='utf-8'):
    e = json.loads(line)
    print(e.get('source'), e.get('timestamp'), e.get('event_type'), e.get('tool_name'), e.get('tool_call_id'))
PY
```

查找工具调用最多的 session：

```bash
python3 - <<'PY'
import json
summary = json.load(open('data/summaries/session_summary.json', encoding='utf-8'))
for s in sorted(summary, key=lambda x: x['tool_call_count'], reverse=True)[:10]:
    print(s['source'], s['tool_call_count'], s['tool_names'], s['source_file'])
PY
```

按 session 复原链路：

```bash
python3 - <<'PY'
import json
sid = '7d3d41c9-981f-4641-994d-73ff3f89d894'
for line in open('data/normalized/events.jsonl', encoding='utf-8'):
    e = json.loads(line)
    if e.get('session_id') == sid:
        print(e.get('timestamp'), e.get('event_type'), e.get('tool_name') or '', e.get('tool_input') or e.get('output_preview') or e.get('text', '')[:80])
PY
```


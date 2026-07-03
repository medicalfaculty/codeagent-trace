# Code Agent Trace

本仓库保存从本机 Codex 与 Claude Code 历史目录中整理出的交互和工具调用 trace。

## 目录

- `data/raw-sanitized/codex/sessions/`：Codex session JSONL 的脱敏副本。
- `data/raw-sanitized/claude/projects/`：Claude project JSONL 的脱敏副本。
- `data/normalized/`：统一格式的事件流，便于做统计和分析。
- `data/summaries/`：按来源、会话、事件类型聚合的统计信息。
- `docs/`：中文说明和典型过程分析。
- `docs/tool_result_analysis/`：最长 tool result 与可能最长工具调用耗时的专项分析。
- `tools/export_traces.py`：从 `~/.codex` 和 `~/.claude` 重新导出数据的脚本。

## 数据处理原则

导出脚本不会复制 `auth.json`、`.credentials.json`、配置文件、SQLite 原库、缓存目录等文件。对 JSONL 里的常见敏感字段和疑似密钥字符串会做脱敏；对 Codex 的加密 reasoning payload、长 system/developer instruction 会做省略或截断。

这些 trace 仍然包含用户任务描述、工具调用命令、工具输出摘要、模型 token usage、cache read/write 信息和执行顺序，适合分析 agent 在“用户发任务 -> 模型规划/思考 -> 调用工具 -> 等待工具返回 -> 继续推理”的过程。

## 原始目录逐项说明

下面说明的是本机原始目录 `~/.codex` 和 `~/.claude` 的作用；本仓库只保存脱敏后的分析副本，不直接提交这些原始文件。

### `~/.codex`

- `.personality_migration`：记录 Codex 个性化配置迁移是否已执行的小状态文件。
- `.tmp/`：Codex 运行期间使用的临时目录，通常不适合作为稳定 trace 来源。
- `auth.json`：Codex 登录凭据和令牌文件，包含敏感信息，不应导出或提交。
- `cache/`：Codex 缓存目录，可能包含模型、插件或运行时缓存，不是主要交互历史。
- `config.toml`：Codex 客户端配置文件，可能包含默认模型、工具或环境相关设置。
- `goals_1.sqlite`：Codex goal 相关状态库，用于记录长期目标的状态和进度。
- `goals_1.sqlite-shm`：`goals_1.sqlite` 的 SQLite 共享内存辅助文件。
- `goals_1.sqlite-wal`：`goals_1.sqlite` 的 SQLite WAL 日志辅助文件。
- `history.jsonl`：Codex 命令行入口的用户提示历史，每行通常对应一次用户输入。
- `installation_id`：当前 Codex 安装实例的本机标识文件。
- `log/`：Codex 文本日志目录，适合排查客户端运行错误。
- `logs_2.sqlite`：Codex 结构化日志数据库，可查看模型阶段、工具调用、token 计数和运行事件。
- `logs_2.sqlite-shm`：`logs_2.sqlite` 的 SQLite 共享内存辅助文件。
- `logs_2.sqlite-wal`：`logs_2.sqlite` 的 SQLite WAL 日志辅助文件。
- `memories/`：Codex memory 相关文件目录，用于保存可复用的用户或项目记忆。
- `memories_1.sqlite`：Codex memory 的结构化状态数据库。
- `models_cache.json`：Codex 已知模型或模型能力的本地缓存。
- `plugins/`：Codex 插件安装、缓存和启用状态目录。
- `rules/`：Codex 规则或策略片段目录，可能影响 agent 行为。
- `sessions/`：Codex 会话 JSONL 目录，是复原“用户输入 -> 模型响应 -> 工具调用 -> 工具结果”的主要来源。
- `shell_snapshots/`：Codex 保存的 shell 环境快照目录，用于恢复或理解工具执行上下文。
- `skills/`：Codex skills 安装目录，保存可被 agent 触发的本地技能说明。
- `state_5.sqlite`：Codex 客户端通用状态数据库，记录 UI、会话或本地运行状态。
- `state_5.sqlite-shm`：`state_5.sqlite` 的 SQLite 共享内存辅助文件。
- `state_5.sqlite-wal`：`state_5.sqlite` 的 SQLite WAL 日志辅助文件。
- `tmp/`：Codex 普通临时文件目录，通常只在故障排查时查看。
- `version.json`：Codex 版本和升级相关信息。

### `~/.claude`

- `.credentials.json`：Claude Code 登录凭据文件，包含敏感信息，不应导出或提交。
- `.last-cleanup`：Claude Code 最近一次清理任务的状态记录。
- `.last-update-result.json`：Claude Code 最近一次更新检查或更新执行结果。
- `backups/`：Claude Code 自动备份目录，可能包含配置或状态文件备份。
- `cache/`：Claude Code 缓存目录，不是主要交互历史来源。
- `file-history/`：Claude Code 文件编辑历史目录，可辅助分析某次任务改动了哪些文件。
- `history.jsonl`：Claude Code 命令行入口的提示历史，常用于快速定位用户发起过哪些任务。
- `paste-cache/`：Claude Code 粘贴内容缓存目录，可能保存长文本输入的临时副本。
- `plugins/`：Claude Code 插件安装和配置目录。
- `projects/`：Claude Code 按项目路径拆分的会话 JSONL 目录，是分析 agent 执行过程的主要来源。
- `session-env/`：Claude Code 会话环境变量或 shell 上下文缓存目录。
- `sessions/`：Claude Code 会话索引或运行状态目录，具体内容随版本变化。
- `settings.json`：Claude Code 用户级设置文件，可能影响模型、权限和工具行为。
- `shell-snapshots/`：Claude Code 保存的 shell 环境快照目录。
- `tasks/`：Claude Code 任务状态目录，可能记录后台任务或计划任务信息。
- `telemetry/`：Claude Code 遥测和诊断数据目录。

## 关键文件详解与示例

### Claude：`.claude/history.jsonl`

`~/.claude/history.jsonl` 是 Claude Code 的输入历史索引，适合先用来找“用户什么时候发过什么任务”。它通常不是完整执行 trace，只是入口级历史；真正的 assistant 回复、工具调用和工具返回结果通常在 `.claude/projects/` 下。

常见字段包括：

- `display`：用户在命令行输入或粘贴的任务文本。
- `pastedContents`：粘贴的大段内容摘要或引用信息。
- `timestamp`：历史记录写入时间。
- `project`：当时所在项目目录。
- `sessionId`：可用于关联项目会话文件的会话标识。

示例：

```json
{"display":"帮我修复 README 并提交","timestamp":"2026-07-03T10:12:03.000Z","project":"/data/home/sheshuchen/codeagent-trace","sessionId":"00000000-0000-0000-0000-000000000000"}
```

查看最近输入的示例命令：

```bash
python3 - <<'PY'
import json
from pathlib import Path

path = Path.home() / ".claude" / "history.jsonl"
for line in path.read_text(errors="replace").splitlines()[-5:]:
    item = json.loads(line)
    print(item.get("timestamp"), item.get("project"), item.get("display", "")[:120])
PY
```

### Claude：`.claude/projects/`

`~/.claude/projects/` 是 Claude Code 的核心 trace 目录。Claude 会把项目路径编码成目录名，并在里面保存一个或多个 JSONL 会话文件；每行是一个事件，能看到用户消息、assistant 消息、工具调用、工具结果、标题生成和系统事件。

常见事件或字段包括：

- `type: "user"`：用户输入，或工具返回结果也可能以 user-side message 形式出现。
- `type: "assistant"`：模型回复，其中 `message.content` 可能包含文本、`tool_use` 等片段。
- `type: "system"`：系统级状态或初始化事件。
- `type: "attachment"`：附件、图片或粘贴内容引用。
- `type: "queue-operation"`：队列状态变化，能反映任务等待和调度。
- `message.content[].type: "tool_use"`：模型请求调用工具。
- `message.content[].type: "tool_result"`：工具执行后的返回内容。

工具调用示例：

```json
{
  "type": "assistant",
  "message": {
    "content": [
      {
        "type": "tool_use",
        "name": "Bash",
        "input": {"command": "git status --short --branch"}
      }
    ]
  }
}
```

工具结果示例：

```json
{
  "type": "user",
  "message": {
    "content": [
      {
        "type": "tool_result",
        "content": "## main...origin/main\n M README.md"
      }
    ]
  }
}
```

从本仓库脱敏归一化结果中查看 Claude 工具调用：

```bash
python3 - <<'PY'
import json
from pathlib import Path

for line in (Path("data/normalized") / "claude_events.jsonl").read_text().splitlines():
    item = json.loads(line)
    if item.get("event_kind") == "tool_use":
        print(item.get("session_id"), item.get("tool_name"), item.get("summary", "")[:120])
        break
PY
```

### Codex：`.codex/history.jsonl`

`~/.codex/history.jsonl` 是 Codex 的输入历史索引，适合快速查看用户给 Codex 发过哪些任务。它通常只保存用户侧 prompt 和少量会话元信息，不包含完整工具调用链。

常见字段包括：

- `session_id`：Codex 会话 ID，可与 `.codex/sessions/` 下的会话文件关联。
- `ts`：用户输入时间。
- `text`：用户输入文本。

示例：

```json
{"session_id":"00000000-0000-0000-0000-000000000000","ts":1783073523,"text":"继续整理 Codex 和 Claude 的 trace，并提交"}
```

查看最近 Codex 输入的示例命令：

```bash
python3 - <<'PY'
import json
from pathlib import Path

path = Path.home() / ".codex" / "history.jsonl"
for line in path.read_text(errors="replace").splitlines()[-5:]:
    item = json.loads(line)
    print(item.get("ts"), item.get("session_id"), item.get("text", "")[:120])
PY
```

### Codex：`.codex/sessions/`

`~/.codex/sessions/` 是 Codex 最重要的完整会话 trace 来源。目录通常按日期分层，例如 `sessions/YYYY/MM/DD/rollout-*.jsonl`；每行是一个事件，可以复原从用户消息、模型 reasoning、工具调用到工具返回的完整顺序。

常见事件包括：

- `session_meta`：会话元信息，如模型、工作目录、CLI 版本等。
- `turn_context`：某轮对话的上下文摘要，例如当前目录、权限模式、可用工具。
- `response_item`：模型产生的结构化响应项，包括 message、reasoning、function_call、function_call_output 等。
- `event_msg`：运行时事件，例如 token 计数、工具开始或结束、错误信息。
- `compacted`：上下文压缩事件，用于说明旧上下文被摘要替换。

工具调用示例：

```json
{
  "type": "response_item",
  "item": {
    "type": "function_call",
    "name": "functions.exec_command",
    "arguments": "{\"cmd\":\"git status --short --branch\",\"workdir\":\"/data/home/sheshuchen/codeagent-trace\"}"
  }
}
```

工具返回示例：

```json
{
  "type": "response_item",
  "item": {
    "type": "function_call_output",
    "output": "{\"exit_code\":0,\"output\":\"## main...origin/main\\n\"}"
  }
}
```

token 计数示例：

```json
{
  "type": "event_msg",
  "message": {
    "type": "token_count",
    "info": {
      "total_token_usage": {"input_tokens": 12000, "output_tokens": 900}
    }
  }
}
```

从本仓库脱敏归一化结果中查看 Codex 工具调用：

```bash
python3 - <<'PY'
import json
from pathlib import Path

for line in (Path("data/normalized") / "codex_events.jsonl").read_text().splitlines():
    item = json.loads(line)
    if item.get("event_kind") == "function_call":
        print(item.get("session_id"), item.get("tool_name"), item.get("summary", "")[:120])
        break
PY
```

### Codex：`.codex/logs_2.sqlite`

`~/.codex/logs_2.sqlite` 是 Codex 的结构化日志数据库，适合补充 JSONL session 中不容易统计的信息，例如阶段性事件、日志级别、模块来源和部分运行时诊断。它是 SQLite 数据库，不能直接当文本读取；同时原库可能包含本机路径、命令和任务文本，所以本仓库只保存摘要，不提交原库。

本机该库的主要表结构示例：

```sql
CREATE TABLE logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp INTEGER NOT NULL,
  level TEXT NOT NULL,
  message TEXT NOT NULL,
  attributes TEXT NOT NULL,
  target TEXT,
  filename TEXT,
  line_number INTEGER
);
```

字段含义：

- `timestamp`：日志时间戳，通常是毫秒或纳秒级整数，取决于客户端版本。
- `level`：日志级别，例如 `INFO`、`WARN`、`ERROR`。
- `message`：日志主体文本。
- `attributes`：JSON 字符串形式的结构化属性，可能包含 span、工具名、请求阶段等信息。
- `target`：产生日志的 Rust 或客户端模块名。
- `filename` 和 `line_number`：产生日志的源码位置，主要用于调试 Codex 自身。

查看最近日志的示例命令：

```bash
sqlite3 ~/.codex/logs_2.sqlite \
  "select id, datetime(timestamp / 1000, 'unixepoch'), level, substr(message, 1, 120) from logs order by id desc limit 5;"
```

查看某类工具或请求日志的示例命令：

```bash
sqlite3 ~/.codex/logs_2.sqlite \
  "select id, level, substr(message, 1, 160), substr(attributes, 1, 200) from logs where message like '%tool%' or attributes like '%tool%' order by id desc limit 10;"
```

本仓库中对应的脱敏摘要可从 `data/summaries/codex_sqlite_summary.json` 查看，用于了解日志规模、字段分布和可分析性，而不暴露原始数据库。

## 一个典型过程示例

可以用 `history.jsonl` 先定位用户发起任务的时间和会话 ID，再到项目会话目录或 Codex session JSONL 中按顺序查看事件：

```text
1. 用户输入任务：出现在 `.codex/history.jsonl` 或 `.claude/history.jsonl`。
2. agent 接收上下文：Codex 中常见为 `turn_context`，Claude 中常见为项目 JSONL 的系统或用户事件。
3. 模型生成计划或说明：通常表现为 assistant text 或 reasoning 摘要。
4. 模型请求工具：Codex 中是 `function_call`，Claude 中是 `tool_use`。
5. 工具返回结果：Codex 中是 `function_call_output`，Claude 中是 `tool_result`。
6. 模型根据结果继续推理：后续会出现新的 assistant message、reasoning、工具调用或最终答复。
```

这也是本仓库 `data/normalized/` 的设计目标：把 Claude 与 Codex 不同格式的事件统一成可比较的事件流，方便分析 prefill、decode、plan、工具调用、等待工具返回和继续执行的过程。

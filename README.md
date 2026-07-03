# Code Agent Trace

本仓库保存从本机 Codex 与 Claude Code 历史目录中整理出的交互和工具调用 trace。

## 目录

- `data/raw-sanitized/codex/sessions/`：Codex session JSONL 的脱敏副本。
- `data/raw-sanitized/claude/projects/`：Claude project JSONL 的脱敏副本。
- `data/normalized/`：统一格式的事件流，便于做统计和分析。
- `data/summaries/`：按来源、会话、事件类型聚合的统计信息。
- `docs/`：中文说明和典型过程分析。
- `tools/export_traces.py`：从 `~/.codex` 和 `~/.claude` 重新导出数据的脚本。

## 数据处理原则

导出脚本不会复制 `auth.json`、`.credentials.json`、配置文件、SQLite 原库、缓存目录等文件。对 JSONL 里的常见敏感字段和疑似密钥字符串会做脱敏；对 Codex 的加密 reasoning payload、长 system/developer instruction 会做省略或截断。

这些 trace 仍然包含用户任务描述、工具调用命令、工具输出摘要、模型 token usage、cache read/write 信息和执行顺序，适合分析 agent 在“用户发任务 -> 模型规划/思考 -> 调用工具 -> 等待工具返回 -> 继续推理”的过程。


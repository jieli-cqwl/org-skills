# AGENTS.md

## Commands
| 命令 | 用途 |
|---|---|
| `bash tests/run-all.sh --quick` | 快速回归 |
| `bash tests/run-all.sh` | 全量门禁 |
| `bash install.sh --target all --dry-run` | 预览安装写入 |

## Instruction Sources
- 本仓 `repo_id` 是 `team-skills`；不拥有 runtime assistant、rules 或 reference 源树。
- Team Skills 消费已安装 Base 的 rules 与 reference（`~/.claude` / `~/.codex`），不在本仓维护这些 runtime 文件。
- 本仓维护规则写在根入口或 repo-local 文档，并用测试锁定承载位置。

## Skill Sources
- `shared/skills/` 是 Team first-party 真源。
- Superpowers 与第三方 vendor 归 Daily，不在本仓。

## Testing
- 行为/约束变更先补可失败测试，再做最小实现，最后跑 fresh proving command。
- 测试断言边界：不得用 shell `assert_present` / `assert_absent` / `assert_any_present` / 直接 `grep` / `rg` 锁定 Skill / Rule / Reference / Agent Markdown 自然语言正文。
- 低信号断言由 `tools/community/check_test_signal_assertions.py` 直接拦截；不得用 baseline 放行新增或存量 Skill / Rule / Reference / Agent Markdown 自然语言正文断言。
- 修改入口文档时，保持 `CLAUDE.md` 只 import `AGENTS.md`，避免双源漂移。

## Workflow
- 执行前定目标、对象、成功标准；改动前追影响面；交付前验证命令和 `git diff` 都要对上本次范围。
- 文档命名、归档、接手和 standard-chain 状态规则以已安装 Base `document-governance` 为准；`worklog.md` 只做导航。

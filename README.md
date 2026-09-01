# team-skills

Team first-party Skills、hooks、agents、protocols 与 standard-chain 合同。本仓 `repo_id` 是 `team-skills`。物理 remote 是 `https://github.com/jieli-cqwl/org-skills.git`。

本仓不拥有 runtime assistant / rules / reference，也不再 vendor Superpowers、Anthropic 或其他 community Skills。那些源树分别在 `base-config` 与 `daily-skills`。安装 Team 前必须在同一 target 上先装 Base。

## 当前状态

- 标准流程：runtime id 为 `standard-chain/v1`，合同入口为 `contracts/standard-chain.yaml`
- 受管通用入口：`worklog.md`，仅对 `contracts/active-doc-scope.yaml` 纳管的 feature 生效
- scope registry：`contracts/active-doc-scope.yaml`，只允许 active `standard-chain` scope
- context ownership：`context_owner` 维护 feature 接手链路，`artifact_owner` 维护具体工件正确性
- standard-chain 进度真源：canonical JSON；`worklog.md` 只保存 `handoff_status / state_ref / next_ref` 导航字段

## 仓库结构

- `shared/skills/`：Team first-party Skills；`lib/` 与 `qft-branch-flow-workspace/` 在树内但不安装
- `claude/skills/`：Claude-only Skills（`code-review-fix`、`doc-review-fix`）
- `shared/hooks/`、`claude/hooks/`、`shared/agents/`、`shared/protocols/`、`shared/runtime/`：Team 运行时配套
- `contracts/`：standard-chain、active scope、runtime surface、dependencies
- `docs/`：历史材料；被 `contracts/active-doc-scope.yaml` 纳管的目录视为受管活跃子集

## 当前真源

- 项目入口：根目录 `AGENTS.md`；`CLAUDE.md` 通过 `@AGENTS.md` 载入同一套项目指令
- Team 依赖：`contracts/dependencies.yaml` 声明同一 target 上的 `base-config`
- Skill runtime surface：`contracts/skill-runtime-surface.json`
- 标准流程合同：`contracts/standard-chain.yaml`
- 标准流程 runtime catalog：`shared/runtime/standard-chain-catalog.json`
- Superpowers 与 community vendor 归 Daily，不在本仓

## 快速开始

先安装 Base，再安装 Team。不要对真实用户 HOME 跑本仓 cutover 安装。

```bash
git clone https://github.com/jieli-cqwl/org-skills.git
cd org-skills
# Base must already be installed on the same target from the base-config checkout
bash install.sh --target all --dry-run
```

## 常用命令

```bash
bash install.sh --target all --dry-run
bash tests/run-all.sh --quick
bash tests/run-all.sh
```

## Standard Chain

standard-chain 的接手恢复顺序固定为：

1. 读取 scope registry：`contracts/active-doc-scope.yaml`
2. 打开 `entry_ref` 指向的 `worklog.md`
3. 读取最新记录的 `state_ref` 与 `next_ref`
4. 通过 `canonical:` active artifact ref 回到 canonical JSON

约束：

- `contracts/active-doc-scope.yaml` 的 active mode 只允许 `standard-chain`
- `worklog.md` 不复制 PRD、设计、任务或验收全文，只保存导航字段
- canonical JSON 是进度和状态真源

## 完成前验证

- 遵守根目录 `AGENTS.md` 的项目指令；Claude Code 通过 `CLAUDE.md` 的 `@AGENTS.md` import 加载同一指令
- Team Skills 消费已安装 Base 的 rules 与 reference
- 先做影响范围判断，再控制改动边界
- 行为或约束变化先补可失败测试，再跑 fresh proving command

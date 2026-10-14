# 方法依据与参考项目

本文件说明各条规则的来源，常规使用无需读取。下列文档和项目是设计参考，不能作为本 skill 已改善协作效果的实验结论。核实日期为 2026-10-15。

## 用户的运行记录

本 skill 的起点是一套已在实际项目中使用的分工：

- 主会话只做决策：写工作说明、裁决评审结论、启动付费运行、决定合并、核对汇报。启动付费运行、终止进程、合并与推送由主会话亲自执行，子代理执行这些操作会被权限系统拦截。
- 子代理为执行层，每个代理一份书面运行手册，约定遇到任何异常即停下报告，不自行修补，不绕过限制。常用角色为等待进程、只读评审、机械流程和撰写报告。子代理之间不互相调用，均向主会话汇报。所有写操作只进入新目录，禁止读取 `.env`，禁止写账本。
- Codex 编写全部代码，默认 effort 为 high，设计敏感的工作使用 xhigh，每项约 1 到 5 小时。评审未通过时追加小范围修改。记录中一项工作经历了四轮评审，另有四项各经历两轮。
- 只读的 Codex 设计顾问只处理方向性问题，问题由子代理起草，答案存档后由主会话裁决。记录中共使用三轮。

运行中出现的问题：子代理的操作频繁被权限系统拦截，每次都要回到用户确认；子代理的进程监控在约 30 分钟后被平台切断，改用一次长等待处理；并行的 Codex 工作在同一文件上冲突，改为把相关工作合并成一项集成工作。

用户随后要求不以任务卡流程为主线，以路由清晰和运行稳定优先，并参照成熟的开源协作项目调整。本 skill 据此把上述分工改写为路由表和稳定性规则。

## 平台事实

| 事实 | 来源 | 对设计的影响 |
| --- | --- | --- |
| 子代理以后台方式启动的 Bash 命令在该子代理结束回合时被终止，承诺的完成通知不会到达 | [anthropics/claude-code#83627](https://github.com/anthropics/claude-code/issues/83627)，状态为 closed，not planned | 作业与等待分离；子代理只做前台等待 |
| 后台命令达到时间上限后被停止，提示为 "was stopped after reaching its background time limit" | [#98273](https://github.com/anthropics/claude-code/issues/98273)，状态为 open | 等待结束不代表作业结束，以退出码文件为准 |
| 2.1.288 将该上限限定于无人值守会话（`-p`、Agent SDK、CI、cloud），Remote Control 会话仍受影响 | [#100648](https://github.com/anthropics/claude-code/issues/100648) 引用的发布说明，状态为 open | 超过约 25 分钟的等待由主会话持有 |
| `codex mcp-server` 命令和独立的 `codex-mcp-server` 已移除，集成应改用 app server | [OpenAI 文档](https://learn.chatgpt.com/docs/mcp-server) | 使用 `codex exec`，不依赖 MCP 桥接 |
| `codex exec` 在 stdin 为管道时会把 stdin 追加到提示后；harness 中 stdin 未关闭会导致进程无输出地挂起 | `codex exec --help`；[skill-codex](https://github.com/skills-directory/skill-codex) 的说明 | `detach.sh` 为每个作业关闭 stdin |
| 权限规则按 deny、ask、allow 的顺序匹配；复合命令按分隔符拆分后逐段匹配；规则不构成安全边界 | [Claude Code permissions](https://code.claude.com/docs/en/permissions) | 只为只读命令放行，启动和终止保留确认 |

## 本机实测

环境为 codex-cli 0.159.2、Claude Code 2.1.284、macOS，交互会话。

| 测试 | 结果 |
| --- | --- |
| 分离启动 `codex exec`，关闭 stdin，使用 `--json` 与 `-o` | 退出码文件为 0；`-o` 文件写入最终消息；事件流首行 `thread.started` 含 `thread_id` |
| flags 放在 `exec` 与 `resume` 之间，按 `thread_id` 恢复 | 恢复成功，`thread_id` 不变 |
| `detach.sh` 启动后结束发起它的 Bash 调用 | 作业继续运行至结束，写入退出码 0 |
| 子代理用 `detach.sh` 启动一个作业，另用 `run_in_background` 启动一个后台命令，随后立即结束回合 | 两者均继续运行至结束。#83627 描述的终止行为在该环境中未复现 |
| 作业派生孙进程，执行 `pkill -TERM -P <pid>` | 包装进程写入退出码 143 并退出，孙进程仍在进程组中 |
| 随后执行 `kill -TERM -- -<pid>` | 进程组清空 |
| 用 `sh -s` 从 stdin 读取 `detach.sh` 在远程执行 | 作业启动成功，之后解析剩余脚本时报引号不匹配，原因未查明。远程用法改为先用 `scp` 复制脚本再调用 |
| 用 pathspec 排除写入集合，列出其余修改与未跟踪文件 | 写入集合外的修改和新文件被列出，写入集合内的文件被排除 |
| `wait.sh` 的四种结果 | 作业结束时返回 0 并给出作业退出码；超时仍在运行返回 3；进程消失且无退出码文件返回 4；缺少 pid 文件返回 2 |
| 在临时仓库中模拟两轮收集和冻结 | 第 1 轮列出写入集合外的文件，diff 含写入集合内的 2 个文件，`BRIEF.md` 未进入提交；第 2 轮只回退写入集合外的文件，沿用上一轮提交，本轮 diff 为空；冻结 tag 指向接受的提交 |

实测时发现用户的 Codex 配置默认 `model_reasoning_effort = "ultra"`、`sandbox_mode = "danger-full-access"`、`approval_policy = "never"`，因此每次调用都显式设置沙箱和 effort。

在该环境中子代理结束回合并未终止其后台命令，作业与等待分离的设计仍然保留，依据有三项：#98273 记录的时间上限仍在无人值守会话中生效；用户的环境中出现过约 30 分钟的切断，原因未查明；远程作业需要在 SSH 断开后继续运行。

## 参考项目

仓库元数据由调研子代理通过 GitHub API 获取。前三项的许可证和最近推送日期经主会话复核，其余项目因未认证 API 的速率限制未复核。未复制任何项目的代码或原文。

| 项目 | 许可证 | 借鉴内容 | 未采用的部分 |
| --- | --- | --- | --- |
| [obra/superpowers](https://github.com/obra/superpowers) | MIT | `Ruling:` 账本格式，记录决定、原因和判断错误的代价；四种执行状态；评审者不采信实现者的报告；每项最多 5 轮修复，后期换新会话和更高能力的模型；需要停下询问的操作类别 | 主控在计划内独自裁决全部事项；实现者自行提交；默认不并行实现 |
| [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) | Apache-2.0 | 后台作业的状态、结果和取消；只读 review 与对抗式 review；Codex 失败时报告，不改由 Claude 实现 | Stop hook 评审门；rescue 默认写模式 |
| [github/spec-kit](https://github.com/github/spec-kit) | MIT | 并行标记只用于不同文件且无依赖的任务；只读一致性分析 | 每个功能的完整规格流程 |
| [automazeio/ccpm](https://github.com/automazeio/ccpm) | MIT | 每个工作流列出文件；依赖和冲突字段；共享文件只有一个所有者 | 同步到 GitHub Issues；多个代理在同一 worktree 提交 |
| [stellarlinkco/myclaude](https://github.com/stellarlinkco/myclaude) | AGPL-3.0 | 角色划分：编排者不直接写代码，Codex 为默认代码后端，探索、架构和评审角色只读，只有开发角色获得 worktree | 超时后自动缩小范围重试 |
| [humanlayer/humanlayer](https://github.com/humanlayer/humanlayer) | Apache-2.0 | 异常报告分为 Expected、Found、Why this matters；明确列出不做的内容；自动与人工验收分开 | 其余命令集 |
| [skills-directory/skill-codex](https://github.com/skills-directory/skill-codex) | MIT | 关闭 stdin；分析任务默认只读沙箱 | 隐藏 stderr 作为默认 |
| [wshobson/agents](https://github.com/wshobson/agents) | MIT | 一个文件只有一个所有者；共享类型归主导角色 | 签名收据插件 |

## Anthropic 工程文章

- [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)，2025-06-13：子任务描述包含目标、输出格式、工具与来源、任务边界四项；按问题复杂度分配子代理数量；子代理产物写入外部存储，向主代理回传引用；多代理系统的 token 用量约为普通对话的 15 倍。本 skill 据此要求每份说明包含输出目录和返回格式，并只在委派能减少主上下文负担、隔离写入或提供独立检查时才委派。
- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)，2025-11-26：用进度文件和 git 历史在会话之间传递状态；每个会话先确认工作目录、读取日志和进度；JSON 格式的功能清单较少被模型误改；未经测试不得标记完成。本 skill 据此使用 `state.json`，规定会话开始和上下文压缩后的现场核对步骤，并以产物判定完成。

## 对比后未采用的方向

ruflo、oh-my-claudecode、gastown、BMAD-METHOD、SuperClaude 和 claude-task-master 需要守护进程、数据库、tmux 会话或自动合并队列。本 skill 只使用仓库内的文件和标准命令，组件数量少，中断后可以从文件恢复。

原流程在冻结时重建清单并校验哈希。本 skill 改为在接受的轮次提交上打 tag：tag 固定被评审的代码，运行目录只写一次，哈希校验的结果不会改变主会话的下一步操作，因此删除。

mcp_agent_mail 提供带有效期的文件租约。本 skill 的写入集合在派发前检查，状态文件只有主会话一个写入者，因此不需要运行时锁。

## 尚未验证

- 用户环境中约 30 分钟的切断对应 #83627 还是 #98273：原因未查明。本 skill 的等待设计对两种情况均适用。
- 子代理是否继承会话的权限规则：本次查阅的官方文档未说明。
- 本 skill 尚未在一个完整项目周期中使用。示例目录只验证文件格式和检查脚本的行为。

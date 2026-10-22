# 方法依据与参考项目

本文件说明各条规则的来源，常规使用无需读取。v1.0 的运行层、v2.0 的仓库维护层与 v3.0 的 Gemini 路由分别记录。下列文档和项目是设计参考，不能作为本 skill 已改善协作效果的实验结论。v1.0 与 v2.0 的核实日期为 2026-10-15，v3.0 为 2026-10-22。

## 用户的运行记录

本 skill 的起点是一套已在实际项目中使用的分工：

- 主会话只做决策：写工作说明、裁决评审结论、启动付费运行、决定合并、核对汇报。启动付费运行、终止进程、合并与推送由主会话亲自执行，子代理执行这些操作会被权限系统拦截。
- 子代理为执行层，每个代理一份书面运行手册，约定遇到任何异常即停下报告，不自行修补，不绕过限制。常用角色为等待进程、只读评审、机械流程和撰写报告。子代理之间不互相调用，均向主会话汇报。所有写操作只进入新目录，禁止读取 `.env`，禁止写账本。
- Codex 编写全部代码，默认 effort 为 high，设计敏感的工作使用 xhigh，每项约 1 到 5 小时。评审未通过时追加小范围修改。记录中一项工作经历了四轮评审，另有四项各经历两轮。
- 只读的 Codex 设计顾问只处理方向性问题，问题由子代理起草，答案存档后由主会话裁决。记录中共使用三轮。

运行中出现的问题：子代理的操作频繁被权限系统拦截，每次都要回到用户确认；子代理的进程监控在约 30 分钟后被平台切断，改用一次长等待处理；并行的 Codex 工作在同一文件上冲突，改为把相关工作合并成一项集成工作。

用户随后要求不以任务卡流程为主线，以路由清晰和运行稳定优先，并参照成熟的开源协作项目调整。本 skill 据此把上述分工改写为路由表和稳定性规则。

## v2.0：仓库维护层

v1.0 只覆盖一个工作周期之内的协作。用户随后提供了 [WncFht/agent-maintenance](https://github.com/WncFht/agent-maintenance)，它从 [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) 固定提交 `5719020` 提取并中文化了文档维护、Agent Notes、分层 AGENTS.md、hooks 与 CI 的规则，要求把两者合成一个管理项目目录和代理执行手册的 skill。v2.0 按内容的生命周期划分目录：常驻规则在 AGENTS.md，跨周期的事实与理由在 `docs/` 和 `.agents/notes/`，单个周期的记录在 `.agents/work/`。英文规则从上游英文原文改写，没有从中文版回译。

| agent-maintenance 的内容 | 处理 | 理由 |
| --- | --- | --- |
| 分层 AGENTS.md：根文件短，子目录只补充，进入未加载目录前显式读取 | 保留 | 与 Codex 和 Claude Code 的实测加载行为一致 |
| 文档分工表，一项事实一个归属 | 保留，见 documentation.md | 项目目录管理的核心规则 |
| Notes 生命周期、取代与合并、实施后改写为现在时、不虚构替代方案 | 保留，章节改为英文，增加 `experiment` 分类 | 研究项目的评测口径与实验协议需要长期理由 |
| 归档 SHA-256 清单、`--seal`、可信基线 CI job | 删除，改为 git diff 只允许新增 | 有可信基线时 git diff 已能检测改写；上游哈希还用于绑定中英文三件套，单语言不需要 |
| 写作命题清单、会话残留判据、校准表 | 保留，见 prose.md | 多轮修改最容易留下轮次与评审引用 |
| 暂存快照检查 | 保留原则，修正了 v1.0 pipeline | v1.0 在 worktree 中测试时写入集合外的改动仍在 |
| `checks.json` 与调度器 | 保留思路，重写为顺序执行的精简版 | 一份清单供 pipeline、hooks、CI 共用 |
| Node 格式化工具链、autocorrect、YAML 注释宽度、中文间距检查 | 不纳入 | 核心只依赖 Python 标准库与 git；格式化优先复用项目已有工具 |
| `.claude/skills` 软链 | 不采用 | Claude Code 的 Edit/Write 拒绝经软链写入 |
| 三个独立 skill | 并入本 skill 的 references | 按要求耦合为一个 skill |

agent-maintenance 删去、v2.0 从上游取回的规则：评审先读要求再读 diff，发现写缺陷、位置、影响、证据（`dsh-code-review`）；每项行为变化需要回归时会失败的最窄检查，过滤后命中 0 个测试不算证据（`dsh-pre-push-checks`）；禁止用加大 timeout、重试、sleep、弱化断言掩盖不稳定测试（`dsh-ci-test-reliability`）；捕获异常不等于恢复（`dsh-error-handling`）；终止后等待进程组清空，退出码、信号、超时分别报告（`docs/defensive-patterns/general.md`）；无法复现的断言删除，只有依赖凭据或网络的断言可以保留并写明验证负责人（`dsh-doc`）；归档目录加入 `.rgignore`。

agent-maintenance 的测试在 macOS 上有 1 项失败：`check_docs.check()` 直接调用时根路径未解析，而 macOS 的临时目录位于 `/var` 软链之后。命令行入口不受影响。本仓库的 `repo_check.py` 用不解析软链的路径比较，测试使用未解析的临时目录。

## 平台事实

| 事实 | 来源 | 对设计的影响 |
| --- | --- | --- |
| 子代理以后台方式启动的 Bash 命令在该子代理结束回合时被终止，承诺的完成通知不会到达 | [anthropics/claude-code#83627](https://github.com/anthropics/claude-code/issues/83627)，状态为 closed，not planned | 作业与等待分离；子代理只做前台等待 |
| 后台命令达到时间上限后被停止，提示为 "was stopped after reaching its background time limit" | [#98273](https://github.com/anthropics/claude-code/issues/98273)，状态为 open | 等待结束不代表作业结束，以退出码文件为准 |
| 2.1.288 将该上限限定于无人值守会话（`-p`、Agent SDK、CI、cloud），Remote Control 会话仍受影响 | [#100648](https://github.com/anthropics/claude-code/issues/100648) 引用的发布说明，状态为 open | 超过约 25 分钟的等待由主会话持有 |
| `codex mcp-server` 命令和独立的 `codex-mcp-server` 已移除，集成应改用 app server | [OpenAI 文档](https://learn.chatgpt.com/docs/mcp-server) | 使用 `codex exec`，不依赖 MCP 桥接 |
| `codex exec` 在 stdin 为管道时会把 stdin 追加到提示后；harness 中 stdin 未关闭会导致进程无输出地挂起 | `codex exec --help`；[skill-codex](https://github.com/skills-directory/skill-codex) 的说明 | `detach.sh` 为每个作业关闭 stdin |
| 权限规则按 deny、ask、allow 的顺序匹配；复合命令按分隔符拆分后逐段匹配；规则不构成安全边界 | [Claude Code permissions](https://code.claude.com/docs/en/permissions) | 只为只读命令放行，启动和终止保留确认 |
| Codex 每次运行开始时构建一次指令链：全局文件一个，再从 git 根目录逐级到 cwd，每个目录最多一个文件，合计达到 `project_doc_max_bytes`（默认 32 KiB）后停止追加 | [Codex 文档](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | 工作说明列出写入集合所在子目录的 AGENTS.md；`repo_check.py` 检查每条链的大小 |
| Claude Code 自 2.1.277 起原生读取 AGENTS.md，条件是工作目录及其上级没有 CLAUDE.md；子目录文件在读写该目录下的文件时加载；`@import` 的文件同样在启动时加载；内置 Explore 与 Plan 子代理不加载这些文件 | [Claude Code memory](https://code.claude.com/docs/en/memory)、[sub-agents](https://code.claude.com/docs/en/sub-agents) | AGENTS.md 作为唯一事实源；CLAUDE.md 只在首行导入它 |
| 单个指令文件建议在 200 行以内；两条矛盾的指令可能被任选其一 | [Claude Code memory](https://code.claude.com/docs/en/memory) | 一项事实一个归属；超过 200 行给出警告 |
| AGENTS.md 应作为目录而非百科，约 100 行；docs 为事实源，由 linter 与 CI 校验 | OpenAI "Harness engineering"，2026-02-11；原页返回 403，引文取自[镜像](https://github.com/celesteanders/harness/blob/main/docs/research/260211_openai_harness_engineering_codex.md) | 根 AGENTS.md 模板约 100 行，以地图为主 |
| pre-commit 框架运行 hook 时暂存未暂存的改动，只检查暂存内容 | [pre-commit 文档](https://pre-commit.com/#pre-commit) | 提交 hook 不另做快照导出 |
| 子代理每次执行 Bash 命令前工作目录都会重置，系统提示要求只用绝对路径 | Claude Code 子代理的系统提示，由独立评审代理引用 | 收集步骤写成一个使用绝对路径的脚本，不依赖单独的 `cd` |

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

### v2.0 实测

环境为 codex-cli 0.159.2、Claude Code 2.1.284、macOS，日期 2026-10-15。v1.0 的运行时检查在同一天按文档命令原样重跑，结果与上表一致。

| 测试 | 结果 |
| --- | --- |
| Codex 以 `-C <仓库根>` 启动，根目录与 `sub/` 各有一个带标记的 AGENTS.md | 只报告根目录标记 |
| 同上，以 `-C <仓库根>/sub` 启动 | 报告两个标记 |
| 无头 Claude Code 在只有 AGENTS.md 的目录启动，用户级 CLAUDE.md 存在 | 主会话读到项目 AGENTS.md |
| 主会话派出 general-purpose 子代理，子代理读取 `sub/` 下的文件前后各报告一次 | 读取前只有根目录标记，读取后增加 `sub/AGENTS.md` 的标记 |
| 项目 `.claude/settings.json` 中 matcher 为 `startup\|resume\|compact` 的 SessionStart hook | 启动时输出进入主会话，子代理看不到；`/compact` 后与 resume 时再次注入 |
| `git merge --no-ff` 与分叉后的普通合并 | 触发 `pre-merge-commit`、`commit-msg`、`post-merge`，不触发 `pre-commit` |
| `git merge --squash` 后 `git commit` | 触发 `pre-commit` 与 `commit-msg` |
| linked worktree 中提交 | 使用主仓库的 hooks |
| 写入集合内的改动依赖写入集合外的改动，按 v1.0 顺序在 worktree 中测试 | 检查通过，退出码 0 |
| 同一改动按 v2.0 顺序：提交写入集合，把剩余改动存为 patch 与 tar，测试，再恢复 | 检查失败，退出码 1，对应 round commit 的真实状态；修改、删除和未跟踪文件均恢复 |

`git stash` 的栈保存在共享的 git 目录中，所有 worktree 共用。两个 pipeline 同时收集时可能恢复对方的改动，因此 pipeline 不使用 stash。

实现完成后的验证：

| 测试 | 结果 |
| --- | --- |
| 在临时项目中按 adopt.md 第 2 步的命令原样接入，删除示例 worker | `run_checks.py` 的 commit 与 ci 模式、`repo_check.py`、`work_state.py` 均通过 |
| 安装模板中的 pre-commit 配置后提交，再用 `--no-ff` 合并一个含断链的分支 | 提交时检查通过；合并由 `pre-merge-commit` 拦下，未生成合并提交 |
| 把模板中的 SessionStart hook 合并进 `.claude/settings.json`，启动无头会话 | `$CLAUDE_PROJECT_DIR` 正常展开，现场信息与账本末行进入主会话 |
| `collect_round.py` 的 7 项测试 | 写入集合外的依赖使检查失败；Codex 暂存的重命名不进入提交；Codex 自行提交与作业未结束时停止；从任意目录运行时主 checkout 不受影响 |

独立评审代理审阅了实现，报告 1 个阻断问题、8 个应修问题和 6 个次要问题，均已处理。阻断问题是：runbook 要求子代理先单独执行 `cd` 再执行收集命令，而子代理的工作目录每次都会重置，新增的放置步骤会在主 checkout 中删除未跟踪文件。v1.0 的同一写法只会导致无效的 `git add`。该问题促成了 `collect_round.py`。

## v3.0：Gemini CLI

用户要求把 Gemini CLI（agy，即 Antigravity CLI）作为与 Codex 并列的工作者，承担四类工作：检索与阅读，调研报告，文档审查与项目维护检查，文档维护。Gemini 不写代码，也不做代码评审。此前用户环境中直接调用 agy 的记录有下列问题：

| 问题 | 影响 | 规则 |
| --- | --- | --- |
| 无头模式下工具被拒绝时，agy 仍返回 `status: SUCCESS`、空回答和退出码 0 | 被拒绝的运行被当作完成 | `gemini_run.py` 判定结果，有拒绝时退出码为 3 |
| 经模型网关调用时，Antigravity provider 拒绝 Claude Code 的系统提示，返回 400 或 429 | Gemini 不能作为 Claude 子代理的模型 | Gemini 只通过自己的 CLI 运行 |
| `--print-timeout` 默认为 0，即不限时；macOS 没有 `timeout` 命令 | 运行可能无限期挂起 | 启动器总是设定超时，超时 300 秒后仍未结束则终止进程组 |
| Gemini 运行没有用 `detach.sh` 启动，也没有状态记录 | 等待中断后结果丢失 | 与 Codex 相同的分离启动和运行目录 |
| 用 `--mode plan` 做只读运行时，agy 只返回计划文件的位置 | 只读任务没有可用结果 | 只读由策略实现，不使用 plan 模式 |
| 一次文档审查返回 180 项候选问题，其中多项在打开原位置后不成立 | 未核对的候选问题可能进入后续工作 | 每项结论附出处，使用前核对 |
| agy 会自动更新 | 已验证的行为可能改变 | 预检记录绑定 agy 二进制，二进制变化后拒绝启动 |
| 为避免拒绝，全局设置放行了 `read_file(*)` 与 `write_file(*)` | 所有 agy 会话都能读写任意路径 | 每次运行一份策略，全局设置不再放行 |

### v3.0 实测

环境为 macOS，经本机模型网关调用，日期 2026-10-22。agy 当天从 1.4.4 自动更新到 1.4.5，标注 1.4.5 的行在更新后测得，其余在 1.4.4 上测得。

| 测试 | 结果 |
| --- | --- |
| 无头模式运行需要 `command` 权限的命令 | 退出码 0，`status` 为 `SUCCESS`，`response` 为空，`denied_actions` 列出 RunCommand |
| 项目 `.agents/hooks.json` 中的 PreToolUse hook 返回 `allow`，另加 `permissionOverrides` | hook 被调用，命令仍被无头模式拒绝 |
| 环境变量 `ANTIGRAVITY_PERM_GRANTS=command(echo)` | 命令仍被拒绝 |
| `--mode auto` | 提示该账号不可用，按默认模式运行 |
| `--dangerously-skip-permissions`，hook 返回 `deny` | 命令未执行，模型收到 hook 给出的原因；输出中没有 `denied_actions` |
| hook 输出 `{}` | 调用被拒绝 |
| hook 输出为空，退出码 0 | 沿用 agy 自身的权限流程 |
| hook 以退出码 1 结束、超时被终止、输出 `allow` 但退出码为 1 | 三种情况的调用均被拒绝 |
| `hooks.json` 中的 SessionStart 写成带 `hooks` 的分组格式 | 整个文件解析失败，只在日志中留下警告，PreToolUse 也未生效 |
| SessionStart 写成平铺格式 | 无头模式下触发；处理器的工作目录为 `hooks.json` 所在目录，继承启动 agy 时的环境变量 |
| 1.4.5：`--conversation` 恢复一次运行 | SessionStart 不触发，PreToolUse 照常按新一轮的策略判定 |
| 1.4.5：PreInvocation 写成平铺格式，处理器不输出 | 新会话与恢复的会话中都在每次模型调用前触发，运行正常完成 |
| 1.4.5：二进制内嵌的 hook 文档 | 列出 SessionStart、PreToolUse、PostToolUse、PreInvocation、PostInvocation、Stop 六种事件 |
| 1.4.5：预检的拒绝探测只要求运行 `touch` 或创建文件 | 模型读到 prompt 开头的授权说明后不发起调用，直接说明会被拒绝，hook 未被调用 |
| 1.4.5：拒绝探测说明调用预期被拒绝并要求照样调用 | 模型发起调用，hook 拒绝，模型转述拒绝原因，启动器以 3 退出，文件不存在 |
| 1.4.5：`--sandbox` 下用命令读取工作区外的文件 | `~/.zshrc`、home 下的其他目录、`/tmp` 下的其他目录和另一个仓库报 Operation not permitted；`/etc/hosts` 与 `$TMPDIR` 下的文件可读 |
| 1.4.5：不加 `--add-dir`，用 `read_file` 读取工作区外的文件 | 读取成功，由 hook 决定是否放行 |
| `--add-dir` 指向另一个含 `.agents/hooks.json` 的目录 | 该目录的 hook 被加载；模型把该目录当作工作区根目录，并向其中写入新文件 |
| `--sandbox` 下在工作区内外运行 `touch`，运行 `curl`，读取 `~/.gemini` 下的配置 | `touch` 与读取配置报 Operation not permitted，`curl` 成功；`write_file` 与 `edit_file` 正常写入；hook 能写文件 |
| `--print-timeout 3s` 运行长任务 | 退出码 0，`status` 为 `SUCCESS`，返回部分回答，`duration_seconds` 与用量均为 0；只有 stderr 有超时提示 |
| `--conversation <id>` 恢复 | conversation id 不变，`num_turns` 增加，先前的上下文保留 |
| 工作目录中有带标记的 AGENTS.md | 回答中出现该标记 |
| 模型列出的工具 | `run_command`、`manage_task`、`read_file`、`write_file`、`edit_file`、`ask_question`、`search_web`、`schedule`、`send_message`、`define_subagent`、`invoke_subagent`、`manage_subagents`；没有读取 URL 的工具 |

据此，启动器以 `--sandbox` 与 `--dangerously-skip-permissions` 运行 agy，权限判断全部交给项目 `.agents/hooks.json` 中的 hook，由它按本次运行的 `policy.json` 判定。`LONGRUN_GEMINI_POLICY` 未设置时 hook 不输出，交互会话不受影响。启动器以 PreInvocation 处理器写入的 `hook-started` 证明 hook 已加载；SessionStart 在恢复会话时不触发，不能用于此。拒绝探测必须要求模型发起被拒绝的调用，否则它会按授权说明自行停下，探测测不到 hook。启动器不传 `--add-dir`：该目录的 hook 会被加载并在沙箱外运行，模型也会向其中写文件；其他读取目录由文件工具读取。沙箱只部分限制命令的读取范围，所以 hook 仍检查命令参数中的路径。

### v3.0 实现验证

2026-10-22，agy 1.4.5：155 个单元测试通过，其中 Gemini 相关 81 个，用伪造的 agy 覆盖各判定分支。临时仓库中真实运行预检，六项探测全部通过。同一仓库中一次只读运行与一次以 `--conversation` 恢复的写入运行均以 0 退出，写入落在写入集合内。

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
| [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) | MIT | 分层 AGENTS.md、Agent Notes 生命周期、会话残留清理、评审与验证选择、错误处理与可靠测试规则 | 中英文三件套、归档哈希清单、产品专用模板 |
| [WncFht/agent-maintenance](https://github.com/WncFht/agent-maintenance) | MIT | 上游规则的可移植裁剪；检查清单与暂存快照 | 见上文 v2.0 一节 |

v2.0 另调研了约 50 个项目，下列项目各提供了一项被采用的做法：

| 项目 | 采用的做法 |
| --- | --- |
| [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) | 长期规格与单次变更分开存放；其记录的故障（两个并行变更先后归档，后者覆盖前者）促成收尾由一个写者串行执行 |
| [burtenshaw/multiautoresearch](https://github.com/burtenshaw/multiautoresearch) | 研究记录只有一个写者；重复实验按同一父提交、同一子系统、同一假设判定 |
| [gastownhall/beads](https://github.com/gastownhall/beads) | 通过 SessionStart hook 注入现场信息 |
| [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | 规则一旦由检查覆盖，就从指令文件删除 |
| [anthropics/claude-quickstarts](https://github.com/anthropics/claude-quickstarts) autonomous-coding | 开局固定步骤；以文件判定完成 |
| [agent-sh/agnix](https://github.com/agent-sh/agnix) | 按整条指令链校验 32 KiB 上限 |
| [agent-sh/deslop](https://github.com/agent-sh/deslop) | 注释中评审轮次短语的探针 |
| [npryce/adr-tools](https://github.com/npryce/adr-tools)、[adr/madr](https://github.com/adr/madr) | 决策记录的状态与双向取代链接 |
| [jcszymansk/claude-review-loop](https://github.com/jcszymansk/claude-review-loop) | 评审首行格式错误按未通过处理 |
| [ozgursagiroglu/arbab](https://github.com/ozgursagiroglu/arbab) | 端口租约；本 skill 用 `resources` 字段在派发前检查 |
| [aroramrinaal/codex-claude-crew](https://github.com/aroramrinaal/codex-claude-crew) | 声明、观察、验证三者分开记录 |
| [agentcrew-academy/claude-codex-harness-sync](https://github.com/agentcrew-academy/claude-codex-harness-sync) | 指出 Codex 不展开 `@` 导入，因此 AGENTS.md 作为事实源 |

没有找到把多代理编排与仓库维护放在同一个 skill 中的项目。最接近的是 [AnastasiyaW/codex-claude-code-config](https://github.com/AnastasiyaW/codex-claude-code-config)，它没有派发 Codex 的运行机制、写入集合和有上限的评审轮次。

## Anthropic 工程文章

- [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)，2025-06-13：子任务描述包含目标、输出格式、工具与来源、任务边界四项；按问题复杂度分配子代理数量；子代理产物写入外部存储，向主代理回传引用；多代理系统的 token 用量约为普通对话的 15 倍。本 skill 据此要求每份说明包含输出目录和返回格式，并只在委派能减少主上下文负担、隔离写入或提供独立检查时才委派。
- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)，2025-11-26：用进度文件和 git 历史在会话之间传递状态；每个会话先确认工作目录、读取日志和进度；JSON 格式的功能清单较少被模型误改；未经测试不得标记完成。本 skill 据此使用 `state.json`，规定会话开始和上下文压缩后的现场核对步骤，并以产物判定完成。

## 对比后未采用的方向

ruflo、oh-my-claudecode、gastown、BMAD-METHOD、SuperClaude 和 claude-task-master 需要守护进程、数据库、tmux 会话或自动合并队列。本 skill 只使用仓库内的文件和标准命令，组件数量少，中断后可以从文件恢复。

原流程在冻结时重建清单并校验哈希。本 skill 改为在接受的轮次提交上打 tag：tag 固定被评审的代码，运行目录只写一次，哈希校验的结果不会改变主会话的下一步操作，因此删除。

mcp_agent_mail 提供带有效期的文件租约。本 skill 的写入集合在派发前检查，状态文件只有主会话一个写入者，因此不需要运行时锁。

rulesync 与 ruler 从一个目录生成各代理的规则文件。生成层会引入第二个事实源，而 Claude Code 与 Codex 都已直接读取 AGENTS.md，因此不采用。

上游的归档哈希清单不采用，理由与 v1.0 删除冻结哈希清单相同：有可信基线时 git diff 已能回答归档文件是否被改写，哈希的结果不改变下一步操作。

## 尚未验证

- 用户环境中约 30 分钟的切断对应 #83627 还是 #98273：原因未查明。本 skill 的等待设计对两种情况均适用。
- 子代理是否继承会话的权限规则：本次查阅的官方文档未说明。
- Codex 的全局 AGENTS.md 是否计入 32 KiB 上限：文档未明确，`repo_check.py` 只计算项目内的指令链。
- SessionStart hook 在交互会话中自动压缩后的注入：只在无头会话中用 `/compact` 测试过。
- GitHub Actions 中的检查是否被设为合并前必须通过：属于托管平台设置，本仓库无法验证。
- 本 skill 尚未在一个完整项目周期中使用。示例目录只验证文件格式和检查脚本的行为。
- 交互式 agy 会话中项目 hook 的中性行为：空输出只在无头模式下测试过。
- Gemini 文档维护在真实项目中的完整轮次（worktree、`collect_round.py`、评审）尚未运行，只在临时仓库中验证了启动、恢复与写入集合。
- 2026-10-21 的 agy 日志中出现过检索重定向失败（"You are not logged into Antigravity"），2026-10-22 的检索探测正常，原因未查明。预检包含一项检索探测。

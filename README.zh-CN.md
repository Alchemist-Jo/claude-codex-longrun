# longrun

[English](README.md) | **简体中文**

[![v3.0](https://img.shields.io/badge/version-v3.0-315a66?style=flat-square)](SKILL.md) [![MIT](https://img.shields.io/badge/license-MIT-647467?style=flat-square)](LICENSE)

用多个代理同时推进一个长期项目的 agent skill。主 Claude 会话负责决策，Claude 子代理负责执行，Codex CLI 编写代码，Gemini CLI 负责检索、调研和文档维护，只读的 Codex 设计顾问回答方向性问题。skill 分为两层，两层共用一套文件。

- **运行层**：把每项工作路由给其中一方，并在以下情况下保持协作稳定：作业运行时间超过启动它的代理，上下文被压缩，子代理被权限确认拦截，两个写入者需要修改同一文件。
- **仓库层**：把跨会话保留的内容放在固定位置，包括 Codex、Gemini 与 Claude Code 都会加载的简短 AGENTS.md、带生命周期的决策记录、随代码同步修改的文档，以及 pipeline、git hooks、CI 和会话启动 hook 共用的一份检查清单。

运行不需要守护进程、框架或数据库。状态和记录保存在项目的 `.agents/` 下，作业由 `detach.sh` 启动、由 `wait.sh` 观察，另有六个只依赖 Python 标准库的脚本，分别用于检查状态、收集每轮结果、运行项目的检查项、检查仓库，以及在由 hook 执行的工具策略下运行 Gemini。

## 项目目录

~~~text
AGENTS.md                 常驻规则和目录地图，约 100 行
<area>/AGENTS.md          只在该区域有额外规则时创建
docs/                     当前文档
.agents/
  checks.json             全部检查项，只有一份
  hooks.json              Gemini 工具策略 hook
  bin/                    detach.sh、wait.sh、work_state.py、collect_round.py、
                          run_checks.py、repo_check.py、gemini_run.py、gemini_hook.py
  notes/                  决策记录：proposed、implemented、rejected、archived
  work/                   state.json、ledger.md、gemini-preflight.json、工作说明、
                          评审、顾问答复、汇报、运行目录
~~~

各目录按内容的生命周期划分。AGENTS.md 存放每次任务都需要的规则，`docs/` 和 `.agents/notes/` 存放跨周期仍然成立的事实和理由，`.agents/work/` 存放单个周期内发生的事。运行记录只在收尾时进入 notes 和文档，代码和文档不引用运行记录。

## Agent 的工作流程

[SKILL.md](SKILL.md) 面向主会话：

1. **接入。** 把项目纳入上述目录，不覆盖已有规则、hooks 和 CI：合并 AGENTS.md，CLAUDE.md 改为导入 AGENTS.md，列出真实的检查命令，补上缺少的 hooks 和 CI 步骤。
2. **路由。** 路由表把每项工作分配给主会话、只读搜索代理、`high` 或 `xhigh` effort 的 Codex、负责检索、调研、文档审查和文档维护的 Gemini、评审者、等待者、机械流程执行者、报告撰写者、设计顾问或用户。启动、终止进程、合并、推送和删除只由主会话执行，合并和推送需要用户批准。
3. **按约定派发。** 写入的 Codex 或 Gemini 收到的工作说明包含写入集合、它自己不会加载的子目录 AGENTS.md、验收命令和文档影响字段。只读的 Gemini 运行收到一个问题，回答中的每条结论都附文件行号或 URL 以及引文。子代理收到运行手册，其中规定输出目录、禁止操作和停止条件。
4. **每个文件只有一个写入者，每项资源只有一个持有者。** `work_state.py --dispatch` 拒绝写入集合、端口或 GPU 主机与已持有者重叠的派发。
5. **作业与等待分离。** `detach.sh` 在独立的 session 中启动作业，关闭 stdin，写入 pid 文件和退出码文件。作业完成以退出码文件为准，等待结束不代表作业结束。
6. **在策略下运行 Gemini。** `gemini_run.py` 以无头模式启动 Gemini CLI，工具策略为本次运行编写，由 hook 执行。只有 hook 已运行、没有调用被拒绝、运行按时结束且回答非空时才以 0 退出。每个 Gemini CLI 二进制先做一次预检，检查回答、读取、命令、两类拒绝和网页检索。
7. **只评审提交的内容。** Codex 和 Gemini 不提交。每轮结束后，机械流程子代理运行 `collect_round.py`：提交写入集合，把其余改动另存到运行目录，只对该提交运行检查，再恢复其余改动。由未参与编写的评审者对照工作说明检查 diff，同时检查文档、会话残留和需要写成决策记录的裁决。评审最多 5 轮。
8. **收尾。** 冻结 tag 之前，会继续指导后续工作的裁决写成决策记录，共享文档由同一时间只有一个的写入者更新。
9. **从文件恢复。** 会话启动 hook 在启动、恢复和上下文压缩后输出现场信息：git 状态、执行者、存活检查和账本末尾。
10. **汇报的数字逐项核对。** 汇报分为精确版和通俗版，附带数字核对清单，每个数字对应一个源文件。

## 规则的依据

每条规则对应实际运行中出现的问题、上游已记录的问题，或编写本 skill 时的实测结果：

| 问题 | 规则 |
| --- | --- |
| 子代理以后台方式启动的命令在子代理结束回合时被终止（[claude-code#83627](https://github.com/anthropics/claude-code/issues/83627)；在 2.1.284 的交互会话中未复现） | 作业分离启动，子代理只做前台等待 |
| 后台命令达到时间上限后被停止（[#98273](https://github.com/anthropics/claude-code/issues/98273)、[#100648](https://github.com/anthropics/claude-code/issues/100648)） | 长时间等待由主会话持有，等待被停止时重新核对作业状态 |
| harness 未关闭 stdin 时 `codex exec` 无输出地挂起 | `detach.sh` 为每个作业关闭 stdin |
| 用户配置使 Codex 默认使用最高 effort 和完全访问权限 | 每次调用显式设置沙箱和 effort |
| 并行的 Codex 运行修改同一文件；同一主机上的两个运行使用同一端口 | 派发前检查写入集合和资源 |
| 只终止包装进程时作业的子进程继续运行 | 按进程组终止作业 |
| Codex 从根目录到工作目录构建指令链，读不到所修改子目录的 AGENTS.md（实测） | 工作说明列出这些文件，来源为 `work_state.py --context` |
| 存在 CLAUDE.md 的位置，Claude Code 不读取 AGENTS.md（[文档](https://code.claude.com/docs/en/memory)） | AGENTS.md 是唯一事实源，CLAUDE.md 导入它 |
| 在 worktree 中测试时，写入集合外的改动使测试通过，而 round commit 不含该改动（实测） | 检查在 round commit 上运行，写入集合外的改动先另存到运行目录 |
| 所有 worktree 共用一个 `git stash` 栈（实测）；子代理每次执行命令前工作目录都会重置 | 收集步骤是一个使用绝对路径的脚本，把改动存为自己运行目录中的文件 |
| merge commit 触发 `pre-merge-commit`，不触发 `pre-commit`；快进合并不触发任何 hook（实测） | hooks 同时安装两种类型，合并执行者分支时使用 `--no-ff` |
| 两个并行变更更新同一份长期文档时相互覆盖（[OpenSpec](https://github.com/Fission-AI/OpenSpec)） | 修改同一共享文档的收尾依次执行 |
| 多轮修改在代码和文档中留下"第 2 轮修复"、评审引用等内容 | `repo_check.py` 报告对运行记录的引用，评审者按会话残留规则检查 |
| 子代理被权限确认拦截 | 只为脚本和只读命令设置窄范围放行规则，不可逆操作保留在主会话 |
| Gemini CLI 无头模式下工具调用被拒绝、print 超时截断运行时，都以退出码 0 和 `SUCCESS` 状态结束（实测） | `gemini_run.py` 根据输出、stderr 和 hook 日志判定每次运行 |
| Gemini 的 `hooks.json` 解析失败时被跳过，只在日志中留下警告（实测） | hook 没有记录任何一次模型调用的运行判为失败 |
| Gemini CLI 自动更新 | 预检记录绑定二进制，记录过期时拒绝启动 |
| 模型网关的 Antigravity provider 拒绝 Claude Code 的系统提示（实测） | Gemini 只通过自己的 CLI 运行，不作为子代理的模型 |
| 为避免拒绝而加的全局放行规则让每个 Gemini 会话都能读写任意路径 | 每次运行一份工具策略，全局设置不放行 |
| 最强 Gemini 模型的一次文档审查列出的问题，打开原位置后多项不成立 | 每条结论附位置和引文，使用前核对 |

## 安装与使用

~~~sh
npx skills add Alchemist-Jo/longrun --skill longrun -g
~~~

也可以克隆到 Claude Code 或 Codex 的 skills 目录：

~~~sh
git clone https://github.com/Alchemist-Jo/longrun ~/.claude/skills/longrun
~~~

~~~text
用 $longrun 接入这个仓库：保留我现有的规则和 CI，
加上 .agents 目录，并告诉我目前哪些检查不通过。
~~~

~~~text
用 $longrun 把这次重构分给 Codex 和子代理。
Codex 写代码，子代理对照工作说明评审每次改动。
~~~

~~~text
用 $longrun 让 Gemini 检查哪些文档与代码不一致，
再把核实过的修改交给 Gemini 文档维护执行者。
~~~

~~~text
用 $longrun 在上下文压缩后恢复项目状态，
然后告诉我哪些执行者仍在运行、哪些操作在等我确认。
~~~

## 检查

~~~sh
python3 scripts/check_skill.py
python3 scripts/work_state.py examples/project/.agents/work/state.json --summary
python3 scripts/repo_check.py examples/project
for f in scripts/*.sh; do sh -n "$f"; done
python3 -m unittest discover -s tests -v
~~~

[示例](examples/README.md)是一个处于周期中途的项目：其中一个计划中的执行者与已持有的文件重叠，一个包有自己的规则，另有两条处于提案状态的决策记录。

## 来源与许可

运行层借鉴了 [obra/superpowers](https://github.com/obra/superpowers)、[openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc)、[github/spec-kit](https://github.com/github/spec-kit)、[automazeio/ccpm](https://github.com/automazeio/ccpm)、[stellarlinkco/myclaude](https://github.com/stellarlinkco/myclaude)、[humanlayer/humanlayer](https://github.com/humanlayer/humanlayer)、[skills-directory/skill-codex](https://github.com/skills-directory/skill-codex) 和两篇 Anthropic 工程文章。仓库层改写自 [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) 的规则，参照了 [WncFht/agent-maintenance](https://github.com/WncFht/agent-maintenance) 的可移植裁剪，两者均为 MIT 许可。未复制代码，规则用英文重新表述。详见[方法依据](references/basis.md)、[第三方声明](THIRD_PARTY_NOTICES.md)和 [LICENSE](LICENSE)。

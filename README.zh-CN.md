# claude-codex-longrun

[English](README.md) | **简体中文**

[![v1.0](https://img.shields.io/badge/version-v1.0-315a66?style=flat-square)](SKILL.md) [![MIT](https://img.shields.io/badge/license-MIT-647467?style=flat-square)](LICENSE)

用多个代理同时推进一个长期项目的 agent skill。主 Claude 会话负责决策，Claude 子代理负责执行，Codex CLI 编写代码，只读的 Codex 设计顾问回答方向性问题。skill 把每项工作路由给其中一方，并在以下情况下保持协作稳定：作业运行时间超过启动它的代理，上下文被压缩，子代理被权限确认拦截，两个写入者需要修改同一文件。

运行不需要守护进程、框架或数据库。状态保存在 `harness/` 下的几个文件中，作业由 `scripts/detach.sh` 启动、由 `scripts/wait.sh` 观察，两者都是简短的 POSIX 脚本，状态检查由一个只依赖 Python 标准库的脚本完成。

## Agent 的工作流程

[SKILL.md](SKILL.md) 面向主会话：

1. **路由。** 路由表把每项工作分配给主会话、只读搜索代理、`high` 或 `xhigh` effort 的 Codex、评审者、等待者、机械流程执行者、报告撰写者、设计顾问或用户。Codex 的启动、付费运行的启动、终止进程、合并、推送和删除只由主会话执行，合并和推送需要用户批准。
2. **按约定派发。** Codex 收到包含写入集合和验收命令的工作说明。子代理收到运行手册，其中规定输出目录、禁止操作和停止条件。每个执行者返回 `DONE`、`DONE_WITH_CONCERNS`、`BLOCKED` 或 `NEEDS_CONTEXT` 之一，异常按 Expected、Found、Why it matters 三项报告。
3. **每个文件只有一个写入者。** `scripts/harness_state.py --dispatch` 拒绝写入集合与正在持有这些文件的执行者重叠的派发。重叠的工作按顺序执行，或合并为一份工作说明。
4. **作业与等待分离。** `detach.sh` 在独立的 session 中启动 Codex 作业、顾问问题和付费运行，关闭 stdin，写入 pid 文件和退出码文件。等待使用只做观察的 `wait.sh`，中断后可以重新开始。作业完成以退出码文件为准，等待结束不代表作业结束。终止作业时作用于整个进程组，退出码文件会记录这次终止。
5. **从文件恢复。** 上下文压缩后或新会话开始时，先核对 git、状态文件、账本和运行目录，再执行其他操作。
6. **评审通过后才算完成。** Codex 不提交。每轮结束后，机械流程子代理把写入集合内的修改提交为该轮的提交，列出写入集合外的修改，并生成相对基准提交的 diff 和本轮 diff。由未参与编写的评审者对照工作说明检查。评审最多 5 轮。从第 3 轮起，主会话先重读未通过的验收标准，再选择改写工作说明、提高 effort 或开启新会话。第 5 轮后由主会话裁决并记录。
7. **汇报的数字逐项核对。** 汇报分为精确版和通俗版，附带数字核对清单，每个数字对应主会话打开过的源文件。

## 稳定性规则的依据

每条规则对应实际运行中出现的问题或上游已记录的问题：

| 问题 | 规则 |
| --- | --- |
| 子代理以后台方式启动的命令在子代理结束回合时被终止（[claude-code#83627](https://github.com/anthropics/claude-code/issues/83627)；在 2.1.284 的交互会话中未复现） | 作业分离启动，子代理只做前台等待 |
| 后台命令达到时间上限后被停止（[#98273](https://github.com/anthropics/claude-code/issues/98273)、[#100648](https://github.com/anthropics/claude-code/issues/100648)） | 长时间等待由主会话持有，等待被停止时重新核对作业状态 |
| harness 未关闭 stdin 时 `codex exec` 无输出地挂起 | `detach.sh` 为每个作业关闭 stdin |
| `codex mcp-server` 已移除 | 直接使用 `codex exec` |
| 用户配置使 Codex 默认使用最高 effort 和完全访问权限 | 每次调用显式设置沙箱和 effort |
| 并行的 Codex 运行修改同一文件导致冲突 | 派发前检查写入集合 |
| 只终止包装进程时作业的子进程继续运行 | 按进程组终止作业 |
| 子代理被权限确认拦截 | 只为只读命令设置窄范围放行规则，不可逆操作保留在主会话 |

## 安装与使用

~~~sh
npx skills add Alchemist-Jo/claude-codex-longrun --skill claude-codex-longrun -g
~~~

也可以克隆到 Claude Code 或 Codex 的 skills 目录：

~~~sh
git clone https://github.com/Alchemist-Jo/claude-codex-longrun ~/.claude/skills/claude-codex-longrun
~~~

~~~text
用 $claude-codex-longrun 把这次重构分给 Codex 和子代理。
Codex 写代码，子代理对照工作说明评审每项修改。
~~~

~~~text
用 $claude-codex-longrun 在上下文压缩后恢复项目状态，
列出仍在运行的执行者和等待我批准的操作。
~~~

## 检查

~~~sh
python3 scripts/check_skill.py
python3 scripts/harness_state.py examples/harness/state.json --summary
for f in scripts/*.sh; do sh -n "$f"; done
python3 -m unittest discover -s tests -v
~~~

[示例](examples/README.md)是项目进行到中途时的 harness 目录，其中一个计划中的执行者与已被持有的文件重叠。状态检查对此给出警告，对该执行者使用 `--dispatch` 时检查失败。

## 来源与许可

路由和稳定性规则改写自 [obra/superpowers](https://github.com/obra/superpowers)、[openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc)、[github/spec-kit](https://github.com/github/spec-kit)、[automazeio/ccpm](https://github.com/automazeio/ccpm)、[stellarlinkco/myclaude](https://github.com/stellarlinkco/myclaude)、[humanlayer/humanlayer](https://github.com/humanlayer/humanlayer)、[skills-directory/skill-codex](https://github.com/skills-directory/skill-codex) 的设计，以及 Anthropic 关于多代理系统和长时运行 harness 的两篇工程文章。未复制代码。详见[方法依据](references/basis.md)、[第三方声明](THIRD_PARTY_NOTICES.md)和 [LICENSE](LICENSE)。

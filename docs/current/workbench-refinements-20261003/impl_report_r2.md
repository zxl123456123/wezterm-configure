# Control resize 计数隔离补实施报告（r2）

## 基本信息与局部范围

- feature_name：`workbench-refinements-20261003`；impl_round：`r2`；date：`2026-10-03`。
- lwplan_version：审阅 SHA256 `7F5ACB2626E34311E76C13B72BE600C753816A6FA74AF60FE0CEDE0AA3DFFA74`，产品基线 `e498739897881d4a117810020de0233a2b9f7beb`。
- 输入：完整重读 safe-code-changes / verification-before-completion 与正式 `review_notes_impl_r1_1.md`；其 `REVISE / IMPL_DEFECT` 由根接受。权威 Q4 原文仍为 `a开始实施`，Q1=A/Q2=B/Q3=A 及已审计划/完整基线不变，无 PLAN_DEFECT。非递归执行，未改规划/状态/历史报告或审查原文。

本轮只修补 P2：新增 resize 测试把合法 8 秒定时查询算成 resize 额外查询。三个局部条件均成立：仅一个既定测试测量窗口；只影响隔离实例、无产品/跨模块/回滚风险；C4 本来要求额外查询为零，修补不改变验收或引入新决策。

| path | change_type | change_purpose / key_changes | related_tasks |
| --- | --- | --- | --- |
| `apps/control-center/tests/test_control_refresh.py` | modify | 仅 test_resize_identity_popup_and_drag_queue：转发本实例 set_interval，捕获 interval=8 的原 Timer 并 pause；确认唯一捕获值为 8 且 target 是该 app；计数窗口显式跨过 8 秒 | P2 / S1-C4 |
| `docs/VERIFICATION.md` | modify | 保留独立审查失败，新增 r2 计数归因/修补及完整回归证据 | P2 / 验证追溯 |
| `docs/current/workbench-refinements-20261003/impl_report_r2.md` | add | 本轮证据与责任交接；不覆盖 r1 / review，不链接未发布规划文件 | P2 / 实施追溯 |

goal_lock_check：保留五个 backend 等值、DOM identity、连续 100→60→40→100 和 79↔80、queued release/move 断言，全部在完整测试中执行。显式等待不是靠测试快速结束避开 timer。

anti_goal_touch_check：其它 Textual timers 正常转发；产品 8 秒 timer/源码、旧 ControlTests 八项、Spectrum 源码与测试不改。未执行 Git 写操作、安装、真实 UI/后台/音频/背景/SSH 动作。

authoring_ergonomics_notes：隔离与证明局限于既有测试方法，使用既有 set_interval 返回 Timer 的 pause/target 与 asyncio 单调时钟；不增测试框架、生产开关或公共 helper。

## 本轮 impl-safe 验证

工作目录为仓库根；下表 `python` 规范化为实际既有 Python 3.12.10 虚拟环境解释器（Textual 8.2.8 / NumPy 2.5.3），参数/source 原样。设置 PYTHONDONTWRITEBYTECODE=1、PYTHONUTF8=1，TEMP/TMP 为仓库 `.validation/tmp`；无 SPECTRUM_LEGACY。所有命令完整输出与最终退出码均已读，无管道收尾；原始日志只留忽略目录。

各行 owner=impl r2；conclusion_if_missing=该项未验证，不可据此放行。evidence 如下：

| 命令 | evidence / 退出码 / 结果 |
| --- | --- |
| `python apps/control-center/tests/test_control_refresh.py --source apps/control-center/control_tui.py` | `.validation/control_green_r2.log`；exit 0；14 项、0 失败、55.801s。`PAUSED_CONTROL_TIMER interval=8 elapsed=8.266s backend_delta=0 target=Control`；之后原尺寸/五符号/身份/queued/move 全部 OK |
| `python apps/spectrum/tests/test_spectrum.py -v` | `.validation/spectrum_green_r2.log`；exit 0；13 项、0 失败、1.325s；200 输出/200 FFT/1 Hann/1 geomspace 与逐帧精确等价保持 |
| `python .validation/verify_refinements_impl_r1.py` | 本轮 stdout；exit 0；四源码源文本编译、冻结旧 frame oracle AST、32 个保护函数（含原 ControlTests）、批准七文件范围保持 |
| `python .validation/verify_refinements_impl_r2_scope.py` | 本轮 stdout；exit 0；删去唯一获准方法后的整份 Control 测试 AST SHA256 与改前一致；其它三产品文件、USAGE/CONFIGURATION、r1 报告、方案与 r1 patch 共 8 项字节哈希未变 |
| `git diff --check` | 本轮 stdout 为空；exit 0；无空白错误 |
| 机械生成 `.validation/refinements_s1_r2.patch` 并对照 doc sections | exit 0；只用基线完整 git diff 替换两份 Control sections，三份原 S1 公共说明 sections 逐字不变；未回退源码或暂存。SHA256 `FF4DCF1CC39A7AD5A7C2AC2F352E8260B3DE23686137367050CA868D53DFB2B1`，r1 patch 保留 |

失败留痕：正式独立 r1 review 的 Control **14 项/1 失败/exit 1/166.780s** 是本轮补修来源，原 scheduled callback 导致查询计数 `[2,0,0,2,1]→[3,0,0,2,1]`，其它 13 项 OK；完整原因已补公开验证说明。此为 reviewer 原轮证据，不冒充本 agent 新红灯。本轮无新非零验证；慢回调诊断约 0.109–0.140s 不是失败或 CPU 测量。r1 红灯及夹具失败原文继续保留，不因本轮绿灯删除。

## 承接、风险与回滚

coordinator_handoff_verifications：

| 项目 / 移交原因与方式 | evidence_expected | owner | conclusion_if_missing |
| --- | --- | --- | --- |
| 恢复独立 reviewer 审 r2，根再全量复验；自证不替代独立审查 | 局部 diff/timer 捕获与跨 8 秒证明，完整 14＋13 命令输出/退出码 | reviewer / coordinator | 不安装、不发布 |
| 保护/备份/两源码交付与两独立普通提交/推送；impl 无此轮写权限 | 50 项保护、紧邻源/目标/备份哈希、批准两源码清单、全待推送区间与发布结果 | coordinator | 不宣称交付/发布或当前实例加载；现场变化暂停 |
| Windows 捕获/拖拽/背景/音频、总体 CPU；非 impl-safe 且无真实测量 | 下一自然新进程的授权反馈；CPU 另定口径 | human / coordinator | 实机与总体收益未验证 |

contract_drift_reports：无新增基线/shared/平台/镜像漂移；本次是审查明确的测试计数归因缺陷，不需回退方案。未完成项：独立 r2 审查、根全量与交付发布仍待承接。审查重点：确实只 pause 本测试实例 interval=8 的返回 Timer，不隐藏合法产品定时行为、不弱化原断言。没有优化其它发现。

回滚信息：可直接回滚，仅撤回该方法内新增隔离/8 秒测量与对应说明；保留原报告/审查和无关工作，不 reset/clean/改写历史。S1_r2 patch 保留原三份 S1 docs；r2 新公开失败/补修段落属于当前公共说明的剩余差异，由根按既定两提交安排审核。

建议英文提交消息仍为 `fix(control): keep workspace controls readable in narrow panes`；Spectrum 包仍为 `perf(spectrum): reuse fixed FFT window and band indices`。无新增跨功能事实。

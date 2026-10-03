# 实施评审记录（第 1 轮实施，第 1 次评审）

## 基本信息与双结论

- review_target：`impl`
- impl_round：`1`
- review_seq：`1`
- review_date：`2026-10-03`
- 实施报告引用：`impl_report_r1.md`；审阅 SHA256 `9812FF2EA6EEC2D60007936CF469D887FD011BE60C6A1816651A7C9FEB402BD8`。
- 计划基线：`lwplan.md`，审阅 SHA256 `7F5ACB2626E34311E76C13B72BE600C753816A6FA74AF60FE0CEDE0AA3DFFA74`；产品基线 `e498739897881d4a117810020de0233a2b9f7beb`。
- 协议结论：`REVISE`
- 业务结论：`IMPL_DEFECT`

独立全量 Control 14 项出现 1 项新增夹具失败，不能放行交付或发布。缺陷在 resize 查询计数的归因：合法的原 8 秒定时刷新可能进入测量窗口。独立探针证明保留该 timer 时查询增加，暂停诊断实例的 timer 后纯 resize 的五个后台符号调用不增加。当前证据未发现需要修改产品或计划的缺陷；Spectrum 13 项与语法、旧算法 oracle、保护边界检查均退出码 0。

完整读取权威基线、方案、实施报告、两源码/两测试、七文件差异和公共使用/配置/验证说明；使用 plan-review 与 verification-before-completion。未递归委派、修改产品/测试/公共说明/基线/状态页，未暂存、提交、安装或操作当前界面。

## 强制字段

| 字段 | 结果与依据 |
| --- | --- |
| goal_lock_alignment | `aligned`；产品差异只落实 G-C 布局和 G-S 固定数据复用；C4 的稳定验收尚待修补夹具 |
| anti_goals_touched | `none`；禁止项逐项核对见下表 |
| authoring_ergonomics_check | `pass`；保留 compose、两卡片行和原 frame 顺序，只加命名容器/集中 CSS 与三个私有成员 |
| declaration_readability_check | `pass`；公开说明明确纵滚可达、模拟交互边界与构造次数，不宣称实机或 CPU 收益 |
| plan_defect_checkpoint_recommended | `no` |
| plan_defect_checkpoint_reason | 仅新增测试的计数窗口未隔离合法 timer；修补不改变目标、验收定义、任务结构或回滚设计 |
| plan_defect_trigger_reason | 不适用；未命中 PLAN_DEFECT |
| impl_safe_validation_check | `missing`；隔离边界合规且全量已执行，但 C4 缺稳定、归因正确的验收证据，不能用作者绿灯或诊断探针替代 |
| coordinator_handoff_check | `pass`；根全量、运行保护/备份/两源码交付、发布区间和自然使用各有责任归属；本 reviewer 未冒称其已完成 |

**基线与澄清一致性复核结果：PASS。** 未回答列表为空；Q1=A 锁定双优化及保留项，Q2=B 锁定三尺寸、受控交付和两个普通提交，Q3=A 的自动规划已终结，Q4=A 原文 `a开始实施` 单独授权本轮实施。产品遵守目标锁、反目标和头脑风暴决策。方案“尚未授权”是 Q3 时点快照，与有效 Q4 无冲突；没有回写终结日志。

| 禁止内容 | 可核查证据 | 结论 |
| --- | --- | --- |
| 新依赖/框架/服务/配置开关、UI 重写或无关重构 | `git diff --name-only` 恰为两源码、两测试、三说明；产品 import AST 与基线相同；Control 差异为 CSS/容器/class，Spectrum 仅三个成员和原 FFT 分支 | 确认未命中 |
| 降低帧率、跳输入、删动效、设备自动恢复 | Spectrum `frame:66–106` 分支外 AST 原样；`capture/geometry/render_frame/main/demo` 与基线 AST 相同；原常量/算法余部未改，F1–F4 全量通过 | 确认未命中 |
| 修改后端协议、播放器输入、启动器、Monitor 或背景热加载 | 七文件完整 diff 无这些文件；Program/WorkspaceCard/刷新/调度/Select handlers AST 未改，Control 原 8 秒 timer 与 BINDINGS 保留 | 确认未命中 |
| 实际终端/标签/SSH/桌面调度/保存背景/音频捕获测试 | Control 两类在 import 前替换全部五个 backend 符号；Spectrum 仅合成输入及 bounded fake main；诊断仍复用全 mock 夹具 | 确认本轮未执行 |
| 操作当前进程、直接覆盖运行目录或发布越权 | 本轮仅新建本报告与忽略目录证据；11 项评审输入 SHA256 未变，暂存为空；运行目录仅引用已有依赖 | 确认本 reviewer 未执行；根承接另验 |

## C1–C5 / F1–F4 独立核对

| 要求 | 证据与结论边界 |
| --- | --- |
| C1 | 全量布局项 OK；100×30/60×20/40×16 Select 分别 `(60,0,38,3)` / `(7,1,52,3)` / `(7,1,32,3)`，整体/箭头屏内；board 高 21/12/8。渲染条带按屏幕及 board 裁剪并逐行滚动收集，英文/中文/未知/空工作区文字可达。24×12 board 高 2，只观察 |
| C2 | 三尺寸 popup、图片/none/保存失败均 OK；检查实际可见条带和内存 appearance，初始不保存；全为 mock |
| C3 | 三尺寸可见 Pilot 点击和模拟 down/up 拖放均 OK；捕获/释放、实际目标 region、滚动后目标、外部 release、40 列折行点位及身份有断言。模拟 handler 不代表 Windows 捕获协议 |
| C4 | 连续 resize 计数项在 `test_control_refresh.py:545` 失败，详见缺陷；慢查询期间 resize 项 OK。独立探针确认 DOM 保留和纯 resize 无额外调用，但不能替代修补后的全量验收 |
| C5 | 原 ControlTests 全 8 项 OK；该类整体 AST 与基线相同，包括 tearDown 禁止保存。窄窗错误/离线/原生 end 滚动项 OK，主题/tone/hover/active 不改 |
| F1 | 每次 ANSI str/None、window/levels/peaks、reference/amount、last_render/last_step/size 精确比较；实际与 oracle 数组不共享。独立对指定基线证明 oracle AST 精确相同，仅模块引用/局部变量名适配，未导向缓存 |
| F2 | 200 个变化合成活动帧逐帧比较；200 输出/200 FFT/1 Hann/1 geomspace；Hann 值精确相同。计数 closure 不保留数组参数，oracle 在目标计数外 |
| F3 | 0/1/2/3/127/128/2047/2048、mono/stereo、超长有界、empty 后恢复及回访旧 key 均 OK。key 使用实际 n 与 bars，单份当前数组；高度/相同 bars 不重建，极小几何不生成 |
| F4 | 活动/静音原 0.05/0.25 秒门、衰减/idle resize/恢复精确等价；稳定非空 idle 1000 次 RMS、其余生成/FFT/绘制/三角函数为 0。旧 Spectrum 8 项所属两类整体 AST 未变且全量 OK |

## 本轮独立命令与证据

owner 均为 reviewer r1/1。下列 `python` 是本轮实际使用的既有 Python 3.12.10 解释器；Textual 8.2.8 / NumPy 2.5.3。设置 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`，TEMP/TMP 指向仓库 `.validation/tmp`，未设置 SPECTRUM_LEGACY。完整命令、所有输出与最终退出码均已读，无管道截断。原始日志限定忽略目录，不公开个人路径或 traceback。

| 命令 | evidence / 最终退出码 / 观察 |
| --- | --- |
| `python apps/control-center/tests/test_control_refresh.py --source apps/control-center/control_tui.py` | `review_impl_r1_1_control.log`；**exit 1，14 项、1 失败，166.780s**；其余 13 项 OK，包括原 8 项 |
| `python apps/spectrum/tests/test_spectrum.py -v` | `review_impl_r1_1_spectrum.log`；exit 0，13 项、0 失败，1.943s；200/200/1/1 |
| `python .validation/verify_refinements_impl_r1.py` | `review_impl_r1_1_ast.log`；exit 0；4/4 源文本编译、32 个保护函数、旧 frame oracle、七文件范围；先完整读脚本再独立执行 |
| `python .validation/review_impl_r1_1_guard.py` | `review_impl_r1_1_guard.log`；exit 0；独立指定基线 AST 对照，原三测试类/边界未变；11/11 输入 hash 未变；子命令 `git rev-parse HEAD`、四次 `git show <baseline>:<path>`、`git diff --name-only`、`git diff --cached --name-only`、`git diff --check` 均各自 exit 0，暂存空、范围恰七文件、空白无错误 |
| `python .validation/review_impl_r1_1_timer_probe.py` | `review_impl_r1_1_timer_probe.log`；exit 0；原 8 秒 timer ticks=1/query_delta=1，五符号 `[1,0,0,2,1]→[2,0,0,2,1]`；只暂停诊断实例 timer 后四次 resize，五符号 delta=0，身份保留 |

缺证据约束：C4 修补后的正式全量未有，不能安装/发布；其余隔离证据只支持本版本和此依赖环境。根仍需独立全量和 50 项运行保护，不从本报告复制成功结论。

失败留痕：本轮唯一非零验证是上述 Control 全量 exit 1；长日志首次工具返回截断，随后 122 行分三段完整读毕。初次合并长输入读取也截断，方案/源码/测试/公共说明均独立补读；截断结果不作成功证据。Control 慢回调诊断约 0.109–0.718s，不是实机 CPU 测量。未重跑单项刷绿来覆盖全量失败。

作者实施历史仍保留其身份：Control 旧源码红灯 2 项/5 子场景失败（含一项过严夹具），修改后第一次全量 9 个夹具误报；Spectrum 旧源码新 4 项为 4 失败/1 错误，另 2 项 oracle/计数运行 1 失败。原因及 exit 1 已在实施报告和公开验证说明记录；本 reviewer 没有把这些历史失败算成本轮新运行或隐去。

## 缺陷与最小补实施任务

**[P2] 隔离 resize 查询计数中的原定时刷新。** `apps/control-center/tests/test_control_refresh.py:530–559` 的测量窗口仍运行生产 8 秒 timer，却在每次 resize 后要求全部后台调用计数恒定。独立全量实际得到 `[3,0,0,2,1] != [2,0,0,2,1]`。独立探针在完全 mock 的实例中记录原 scheduled callback：一个 tick 对应一个查询；暂停该诊断 timer 后连续 resize 不查询。因此该断言把合法 timer 查询误归因为 resize 回退，运行变慢时不能稳定验证 C4。

可直接执行的补实施：只在这个新增测试实例内捕获并暂停 Control 的 8 秒定时器，使五符号零增量断言测量纯 resize；其他 Textual timer 不动。保留五符号等值、79↔80/连续尺寸、DOM identity、queued release/move 全部断言，不改生产 timer/源码或原 ControlTests。新增测试内应证明隔离的是原 8 秒 timer；用隔离探针或受控等待跨过 8 秒后仍完成计数检查，避免仅靠快速单项偶然通过。之后完整重跑 14＋13 和保护/oracle/语法/差异检查，新增 `impl_report_r2.md` 并重新独立评审；公开证据保留本次失败及其修复归因。

按强制判定顺序：证据足以继续收敛，无需 BLOCKED/用户确认；需求真实可追溯，无 PROBLEM_DEFECT。IMPL_DEFECT 三条件同时成立：局部，仅一个计划内测试测量窗；低风险，只影响隔离测试实例，无生产/跨模块/回滚变化；无新决策，C4 本来要求的是 resize **额外**查询为零，原 timer 保留且未更改验收定义/计划结构。无需 PLAN_DEFECT 回退。

**设计味道扫描结果：FAIL：新增计数夹具将周期任务与受测操作混在同一计数窗口，依赖运行小于定时间隔，导致证据不稳定。** 产品 CSS/私有数组实现未发现过度抽象、历史缓存、算法镜像或职责漂移；此 FAIL 按上面的局部测试修补归入 IMPL_DEFECT。

## contract 与后续承接

contract drift / stale / mirror mismatch：未发现新的基线、shared/平台或公开说明冲突；规划授权历史由 Q4 明确覆盖。运行目录此时尚未安装本轮源码，是既定交付阶段差异，本 reviewer 不将其写成未经核验的新 mirror 缺陷，也未执行现场哈希或交付。

修补并重新 Review(Impl) 前停留补实施阶段，不进入 Archive/PR/发布。通过后由 coordinator 重新独立全量，核对 50 项保护、紧邻来源/目标与备份哈希，只安装两份批准源码，供下一自然新进程加载；分别普通提交并核对全部 `origin/main..HEAD` 后普通推送。真实 Windows 捕获/拖拽/滚轮/背景、实际音频与整体 CPU 仍按基线交 human/coordinator 自然使用观察；它们未验证，既不冒称完成，也不升级为本轮新增阻塞风险。

跨功能事实：无新增。

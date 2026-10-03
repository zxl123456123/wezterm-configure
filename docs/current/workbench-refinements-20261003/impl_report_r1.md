# Control 与 Spectrum 增量实施报告（第 1 轮）

## 基本信息与结论边界

- feature_name：`workbench-refinements-20261003`
- impl_round：`r1`
- date：`2026-10-03`
- lwplan_version：审阅 SHA256 `7F5ACB2626E34311E76C13B72BE600C753816A6FA74AF60FE0CEDE0AA3DFFA74`，产品基线 `e498739897881d4a117810020de0233a2b9f7beb`。
- 权威输入：本功能目录的 `clarifications.md`、`lwplan.md`、`review_notes_lwplan_1.md`、`research_textual_layout.md` 及 `docs/Docs.Maintenance.Conventions.md`，均完整阅读。Q1=A、Q2=B、Q3=A、Q4=A；Q4 原文 `a开始实施` 授权本轮隔离实施。Q3 自动链路已终结，本 agent 未改其状态或方案。
- 使用技能：safe-code-changes 与 verification-before-completion。按 S1→S2 红绿顺序，只做 impl-safe；没有递归委派、Git 写操作、运行安装或真实平台操作。

本轮隔离实施结果：Control 14 项（原 8＋新 6）与 Spectrum 13 项（原 8＋新 5）完整回归均退出码 0、0 失败；四份 Python 源文本编译、保护函数/冻结 oracle 检查、差异空白检查退出码 0。以下记录只支持本轮隔离实现，尚需独立 Review(Impl)、协调者全量复核与保护/交付审核。未证明当前实例已更新、Windows 实机交互或总体 CPU 降幅。

## 变更事实与分包

| path | change_type | change_purpose / key_changes | related_tasks |
| --- | --- | --- | --- |
| `apps/control-center/control_tui.py` | modify | 新增 image-controls 容器；auto-height 文字；集中 compact CSS；mount 初始化与 resize 仅切换 `<80` 样式类 | S1 / G-C、G-P |
| `apps/control-center/tests/test_control_refresh.py` | modify | 新独立 ControlLayoutTests，不继承旧类；全 backend import 前 mock；渲染条带/滚动、Select、点击、模拟拖放、resize 与反馈 | S1 / C1–C5 |
| `apps/spectrum/spectrum.py` | modify | 仅三个私有成员与原 eligible FFT 分支的数据复用；实际 n、当前 `(n,bars)`，每对象只保留当前数组 | S2 / G-S、G-P |
| `apps/spectrum/tests/test_spectrum.py` | modify | 冻结旧 frame oracle；精确逐帧 ANSI/状态比较；不保存数组参数的计数 closure；长度/resize/idle 边界 | S2 / F1–F4 |
| `docs/USAGE.md` | modify | S1 补三尺寸/纵滚可达语义；S2 补固定数据复用与采集/CPU 证据边界 | S1、S2 |
| `docs/CONFIGURATION.md` | modify | S1 解释原 DOM 的窄窗布局；S2 解释当前数组边界、替换条件与不变节奏 | S1、S2 |
| `docs/VERIFICATION.md` | modify | 分别记录红绿与隔离证据；首次发布快照明确为历史阶段；Impl 当时未安装，后续交付另记 | S1、S2 |
| `docs/current/workbench-refinements-20261003/impl_report_r1.md` | add | 本报告，公开可读阶段证据及责任承接；本地规划输入仅用代码路径与 SHA 定位 | S1、S2 / 实施追溯 |

另新增/生成的临时诊断与原始输出只在忽略的 `.validation`：`verify_refinements_impl_r1.py`、下表八份测试日志及 `refinements_s1.patch`。这些不是产品文件或交付清单，不公开原始 traceback、个人安装路径或运行数据。

S1 全绿且公共说明就绪时机械生成 `.validation/refinements_s1.patch`，仅包含 Control 源码、Control 测试与三个公共说明的 S1 差异；SHA256 为 `6A4EFD37056740579C6FB26097FD5C15130437DFB832FE7F395550B8FB03B558`。没有回退源码、暂存或提交。S2 随后只追加 Spectrum 源码/测试与对应说明；公共 VERIFICATION 的历史/Impl 阶段措辞归 S2 后续差异。根可审核 S1 patch 后分别暂存两个包，不应盲目加入整个本地规划目录。

建议英文提交消息：`fix(control): keep workspace controls readable in narrow panes`；`perf(spectrum): reuse fixed FFT window and band indices`。

## 目标锁与逐条验收映射

goal_lock_check：G-C、G-S 在下表的隔离证据范围内满足；G-P 通过最小产品差异、旧回归与保护函数核对承接。真实现场保护总哈希、当前进程与受控安装由协调者独立负责，本 agent 不借用他人的口头成功作新证据。

| 要求 | 实施与本轮观察 |
| --- | --- |
| C1 | 4 个虚构工作区含英文长名、中文长名、未知程序与空工作区。100×30/60×20/40×16 的 Select region 分别 `(60,0,38,3)` / `(7,1,52,3)` / `(7,1,32,3)`，整体及箭头屏内。board 可视高度 21/12/8；各 widget 的实际渲染条带按屏幕/board 裁剪与滚动逐行收集，完整文字和工作区标识可达；并非只检查 render 原始字符串。 |
| C2 | 三尺寸均实际 pilot 点击可见箭头打开 popup，检查无背景/example.png 条带及屏内 region，再选择图片/none/模拟失败。save_appearance 参数、内存 appearance 成功更新/失败保持与完整状态反馈有断言；初始挂载未误保存。 |
| C3 | 三尺寸可见 pilot 点击聚焦，模拟 Program mouse-down/up 记录捕获/释放、实际 region 命中不同工作区、滚动后目标、外部 release 不调度；40 列第二折行点位仍聚焦。程序对象 identity 不变。模拟 handler 不代表完整 headless/Windows 鼠标协议。 |
| C4 | 同 app 连续 100→60→40→100、79↔80，关闭 popup 后、拖动中和慢查询中 resize。row/card/Program identity 保留；纯 resize 五个 backend 符号调用计数不增加。queued 请求在原 release 条件下补刷，目标 move 参数保持。 |
| C5 | 旧 ControlTests 八项未改，tearDown 的 save_appearance.assert_not_called 未削弱；互斥、合并、签名、取消、失败重试、滚动恢复保持。40 列成功/操作失败/保存失败/离线条带与原 end 滚动可达，BINDINGS/主题/hover/active/tone 保留。 |
| F1 | oracle 只冻结基线旧 frame，无缓存逻辑/设备入口。连续 80 次可变 capture＋各 1 次门内 frame，每次比较 raw ANSI str/None、window/levels/peaks、reference/amount、last_render/last_step/size；状态数组独立。固定 200 帧也每帧比较这些状态。无容差。 |
| F2 | n=2048、120×8、200 个 50ms 活动帧，信号随帧变化。计数为 rendered=200、rfft=200、hanning=1、geomspace=1；oracle 在目标计数 patch 外执行，FFT 没有缓存或漏采样。Hann 数组与原构造精确相等。 |
| F3 | n=0/1/2/3/127/128/2047/2048，mono/stereo、4096/5000 超长有界、empty→短 burst。n 不变不重建 Hann，key 不变不重建 indices；回访旧 key 重新生成，数组值/对象复用及逐帧输出状态有断言。 |
| F3-resize | 120×8→120×9→121×9→60×5→237×8→1×1→12×0→12×4→120×8，均在帧率门内变化。仅高度/相同 bars 宽度不生成；bars 改变只生成 indices；bars/rows 为零不生成。raw clear 与状态等价。 |
| F4 | 声音→零/empty→衰减→稳定 idle→声音恢复；活动门内返回、原 0.05/0.25 秒门、idle resize 唤醒等价。稳定非空 idle 1000 次 RMS=1000，Hann/geomspace/FFT/绘制/sin/cos=0；empty RMS=0。恢复相同 key 0 构造、1 FFT。旧八项保持采样、numframes=None、empty yield、警告有界与终端恢复。 |

24×12 只输出观察：Select `(7,1,16,3)`，board `(1,10,20,2)`，没有提升为功能保证。三验收尺寸的滚动位置分别 `[0,0]`、`[0,8]`、`[0,8,16,16]`。

anti_goal_touch_check：产品仅 CSS/容器/class mount/resize 与三个缓存成员/原分支生成发生变化。Control mouse/Select/drop/worker/签名不改；Spectrum capture/geometry/render/main/demo、常量、采样、节流、颜色/动效不改。不新增依赖、服务、开关、恢复逻辑或无关重构，不操作真实后台/保存/音频/终端。

authoring_ergonomics_notes：保留既有 compose 与两卡片行结构，宽窗基础 CSS 后集中 compact 覆盖；三私有成员直接表达当前数据，不增历史字典/helper。测试冻结算法有来源与不可同步改写说明；旧隔离类保持，新类单独允许 mock 保存。公共声明只承诺纵滚可达和构造次数减少。

## 本轮命令、退出码与失败留痕

工作目录为仓库根。下表 `python` 表示本轮实际使用的既有 Python 3.12.10 虚拟环境解释器，依赖 Textual 8.2.8 / NumPy 2.5.3；仅规范化解释器与工作目录前缀，命令参数/source 完整保留。设置 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`，TEMP/TMP 为仓库 `.validation/tmp`；未设置 SPECTRUM_LEGACY。每次真实命令的完整输出和最终 shell 退出码均读取，无管道收尾。

所有下表记录 owner=impl r1；每条 conclusion_if_missing 均为“该项未验证，不可据此放行对应包”。evidence 是本轮完整输出，原始文件在忽略目录，正文给出可公开的全部失败原因与计数。

| 完整命令（路径前缀规范化） | evidence / exit / 结果 |
| --- | --- |
| `python apps/control-center/tests/test_control_refresh.py --source apps/control-center/control_tui.py ControlLayoutTests.test_layout_matrix_rendered_names_and_scroll ControlLayoutTests.test_click_and_simulated_drag_matrix` | `control_red_r1.log`；exit 1；2 项、5 子场景失败、12.637s。100/60 列单行英文名称条带只剩符号，40 列 Select 29/38 屏内，40 列长聚焦反馈裁剪；另 60 列强制折行断言是夹具过严。旧代码预期红灯与夹具错误区分保留。 |
| `python apps/control-center/tests/test_control_refresh.py --source apps/control-center/control_tui.py` | `control_green_r1_attempt1.log`；exit 1；14 项、9 失败、55.277s。原 8 项均 OK。新夹具 5 个正文匹配因跨行边框混入字符串误报；3 个 Select 点击误报因 Pilot 判断父控件而实际点击到子控件；1 个 60 列强制折行误报。改为逐行去边框、点击可见 down-arrow、仅 40 列验证折行点，不改产品 handlers。 |
| `python apps/control-center/tests/test_control_refresh.py --source apps/control-center/control_tui.py ControlLayoutTests` | `control_green_r1_attempt2.log`；exit 0；6 项、0 失败、38.558s。随后补 popup/箭头屏内与五符号 resize 计数断言。 |
| `python apps/control-center/tests/test_control_refresh.py --source apps/control-center/control_tui.py` | `control_green_r1_final.log`；exit 0；14 项、0 失败、53.636s。全部逐项 OK，上述三尺寸与 24 列观察完整输出。 |
| `python apps/spectrum/tests/test_spectrum.py -v FixedDataTests` | `spectrum_red_r1.log`；exit 1；旧产品上新 4 项、4 失败/1 错误、0.848s。固定数据生成各 200 次、height resize 重生成、零/空恢复重新生成（两子场景）；旧对象没有新增 `_hann` 成员导致预期 AttributeError。不是声称优化后回归成功。 |
| `python apps/spectrum/tests/test_spectrum.py -v FixedDataTests.test_frame_oracle_continuous_capture_and_gates FixedDataTests.test_fixed_200_varying_frames_exact_and_one_construction` | `spectrum_red_r1_oracle.log`；exit 1；2 项、1 失败、1.143s。独立连续 oracle 项 OK；固定 200 帧的 raw ANSI/状态比较先通过，再在 200/200 构造计数上预期失败。 |
| `python apps/spectrum/tests/test_spectrum.py -v` | `spectrum_green_r1.log`；exit 0；13 项、0 失败、1.245s；200/200/1/1。之后把固定流的公开状态比较明确移到每帧，未改产品。 |
| `python apps/spectrum/tests/test_spectrum.py -v` | `spectrum_green_r1_final.log`；exit 0；13 项、0 失败、1.402s；每帧状态/raw ANSI 精确，200 输出/200 FFT/1 Hann/1 geomspace。 |
| `python .validation/verify_refinements_impl_r1.py` | exit 0；SYNTAX=4/4，不导入产品/生成字节码；ORACLE=基线旧 frame AST 精确一致（仅模块引用/局部变量名适配）；PROTECTED_FUNCTIONS=32 未变，含原 ControlTests；TRACKED_SCOPE=批准七个产品/测试/说明。 |
| `git diff --check`；`git diff -- apps/control-center/control_tui.py apps/spectrum/spectrum.py`；`git diff --stat`；`git status --short` | 各 exit 0；空白检查输出为空，两源码 diff 完整阅读。产品/测试/说明共 7 文件，另本地未跟踪 current 目录由规划阶段继承，本 agent 只新增本报告。无 staged/commit/push。 |

诊断信息：Control 出现约 0.109–0.250s 的 asyncio 慢回调输出，不是测试失败或真实 CPU 测量。最初批量长读取输出截断，已分段完整补读；截断结果不作为验证通过证据。此前规划/研究/首次快照失败保留在原输入与公开验证历史，未用本轮绿灯覆盖历史记录。没有其它未披露的新测试失败。

## 承接、风险与回滚

coordinator_handoff_verifications：

| 项目 / 移交原因 / 方式 | evidence_expected | owner | conclusion_if_missing |
| --- | --- | --- | --- |
| 独立 Review(Impl) 与根全量回归；impl 自证不能替代独立验收 | 独立 diff/oracle/目标反目标核对及本轮完整 14＋13 回归输出/退出码 | reviewer + coordinator | 不安装、不发布 |
| 运行目录保护、备份交付、来源目标哈希与两个普通提交/推送；本轮 impl 权限仅隔离实现 | 原保护清单一致、紧邻现场/来源哈希、备份哈希与两份源码清单、全 origin/main..HEAD 区间核验和普通发布结果 | coordinator | 不宣称安装或发布；现场变化暂停覆盖 |
| Windows 捕获/拖拽、不同显示器/焦点、滚轮、背景真实切换与实际音频；真实平台不属 impl-safe | 下一自然新进程的授权使用反馈，必要时由协调者引导用户 | human / coordinator | 实机仍未验收，当前实例加载未证实 |
| 总体 CPU/真实设备延迟/长期稳定性；缺真实基线与实测 | 另行确定口径与授权后的真实测量记录 | coordinator / human | 不承诺收益比例或延迟改善 |

contract_drift_reports：无新增权威基线/shared skill/平台/镜像冲突；没有自行补齐或改变规划。发现但未改动：Control 测试默认 source 仍指向旧更新入口，按已审方案始终显式指定仓库 source；该已知问题不扩展本轮范围。

未完成项与审查重点：独立审查/根全量核验、受控交付与两提交尚由根承接；重点复核 rendered-strip 的可见裁剪、全 mock 保存、模拟 handler 与实机边界、冻结 oracle 未导向缓存、仅 eligible 分支复用与当前 key。24 列/任意数量全部同时可见不属保证。

回滚信息：可直接回滚。两个包独立差异，可用各自提交的逆向变更；实施尚未改运行文件，不涉及持久数据/schema 迁移。保留无关规划与用户工作，不 reset/clean/改写历史；若将来安装后的现场回收由协调者按验证备份逐文件处理。

跨功能事实：无新增。

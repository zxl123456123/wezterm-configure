# 发布验证与限制

本页保留 2026-10-03 首次安全配置快照的验证，以及后续增量实施证据。首次快照验证阶段只在仓库和隔离夹具中验证，当时未替换运行目录或重新启动使用中的会话；后续受控交付由各阶段承接记录说明，不把阶段测试结果解释为当前实例已加载。

## 紧凑字号与 Music 恢复（2026-10-03）

仓库 Lua 默认字号改为 11pt，其他外观与布局参数不变。实际 WezTerm 指定仓库 `config/wezterm/wezterm.lua` 执行 `ls-fonts --text abc`，exit 0，使用 D 盘 Maple Mono 字体；`show-keys --lua`、字号/重载/重置键位断言及 `git diff --check` 均 exit 0。这些是仓库配置检查，不代表已经交付到启动器读取的 `D:\terminal-workbench\config\wezterm\wezterm.lua`，也不代表窗口缩放覆盖已重置。运行副本更新后必要时按 `Ctrl+Shift+R`、`Ctrl+0`。

实机会话中的 Music 原先不存在。使用既有 `music.kdl` 与 Zellij 原生 `new-tab --no-focus` 单独恢复，exit 0；随后检查 Player、Spectrum 均未退出，对应 CNMPlayer 与 Python 进程存活。全部既有面板身份/退出状态、记录的既有进程身份与当前 Linux 标签保持不变；没有替换开发 Shell 或重启会话。新标签附加在末尾，不重排用户现有标签。

本轮没有修改 Music 源码、重建播放器、登录账号或操作歌曲；进程存活不代表真实播放、暂停/切歌及频谱视觉效果已经验收。未重跑未改动的播放器、Control、Spectrum 全量测试。

保留过程问题：首次从仓库根读取文档维护规范报路径不存在；该组合命令的最终 exit 0 不作为该文件已读取的证据。通过文件搜索找到 `docs/Docs.Maintenance.Conventions.md` 后完整重读。首次合并长输出被截断，相关现行章节另行读取，不把截断内容作为完整验证证据。

独立审查首轮键位断言夹具误用引号与修饰键顺序，exit 1；按实际 CLI 输出修正夹具后 exit 0，未修改产品键位。审查指出仓库/运行副本加载边界不明确、应用源码新进程规则未排除 Lua 重载；已在现行使用和配置说明中区分，后续核对针对修订版本。

## 本地 Shell 增强（2026-10-03）

在 Windows PowerShell 5.1.26100.9444 + PSReadLine 2.0.0 上执行 `tests/test_work_shell.ps1`：30 个断言，exit 0。覆盖键位与 RGB 选区、单行提示符、退出码保留、不重复写入、中文/空格目录恢复、真实 zoxide/zi 与 fzf、选中只插入、取消保留输入、过滤多行历史、工具缺失时基础 Shell 可用。历史编辑器状态使用合成适配器；实际 fzf/zoxide 使用独立 D 盘数据，没有读取用户历史或真实目录数据库。

原有启动器测试完整重跑：6 项、0 失败、exit 0（8.709s）；模拟的子命令失败/超时仍被正确报告，不启动真实窗口。未重跑与本次未改动的 Control/Spectrum 有关的完整套件。

原版 Shell 在同一测试上预期 exit 1，失败于 Tab 未绑定 MenuComplete。另开独立 PTY，实测 Tab 补全、RGB ANSI 输出、F2 原生选择只填入未执行、取消恢复原输入；只操作测试终端，不操作现有 WezTerm/Zellij。该 PTY 不代表嵌套 Zellij、鼠标或全部键位已做视觉验收。

保留失败：测试夹具首轮因带连字符的函数变量访问语法 exit 1；随后严格错误模式将预期的 zoxide 无匹配提示当异常，已改为断言明确拒绝。中文 F2 首测 exit 1，定位为 PowerShell 5.1 的函数局部管道编码无效；改为搜索期间临时全局 UTF-8 并恢复后全量 exit 0。PTY 夹具曾在编辑器初始化前调用 AddToHistory 导致空引用，之后改用隔离历史入口；一次按键取消/退出连发被拼成无效测试命令，分开事件验证后正常退出。首个保护清单检查误用字段产生非终止错误，未采用其 exit 0；改用真实字段与严格错误模式后核对 50 文件一致。首次长启动测试输出截断，仅保留作过程记录，完整重跑才作为证据。

可复跑入口（D 盘仓库、已准备可选 fzf/zoxide）：

```powershell
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File tests\test_work_shell.ps1
```

本轮不升级 Shell，不增加 AI 预测，不改布局/远端/Music/Control。新源码需下一自然新 Shell 才加载；没有测量整机 CPU 降幅或宣称当前面板已更新。

## 首次快照阶段实际执行

| 检查 | 结果 | 边界 |
| --- | --- | --- |
| Control 刷新测试 | 8 项，退出码 0 | Textual 离线夹具，模拟窗口查询，不移动真实窗口 |
| Music 恢复测试 | 17 项，退出码 0 | 模拟 CLI、状态与文件锁，不启动或替换真实 Player |
| Spectrum 测试 | 8 项，退出码 0 | 纯计算、渲染节流与诊断测试，不采集真实音频 |
| 启动错误报告测试 | 6 项，退出码 0 | PowerShell / CMD 隔离夹具；含失败、超时、恢复、两种 CMD 分支 |
| Python 语法 | 7 个文件，退出码 0 | 编译源文本，不生成 pycache |
| TOML / JSON / YAML | 3 / 1 / 2 个文件，退出码 0 | 语法解析，不等于所有软件的运行时语义验收 |
| PowerShell 语法 | 5 个文件，退出码 0 | 只解析，不执行真实启动器 |
| 远端 Bash 语法 | 2 个文件分别检查，退出码 0 | 不连接或修改服务器 |
| Zellij 配置检查 | `setup --check`，退出码 0 | 报告配置 Well defined；不启动布局，不证明所有 KDL 命令可用 |
| WezTerm 配置 / 字体检查 | `ls-fonts --text abc`，退出码 0 | Lua 配置可加载；不是新窗口或图像协议实测 |
| CNMPlayer 补丁 | `git apply --check`，退出码 0 | 隔离副本 HEAD 为指定上游提交，不重新编译 Rust |
| 运行源文件保护 | 50 个事前 SHA256 均未变化 | 42 份公开复制件逐字节相同；另一份测试只适配导出目录名 |
| 公开模板 | SSH 别名 / 示例目录 / 空 API key 已检查 | 不发布真实连接、账号或历史路径 |
| Git 忽略覆盖 | 16 个私有/运行路径忽略，7 个公开路径可跟踪 | 另检查暂存清单；ignore 不保护已跟踪的秘密 |

合计 **39 项 Python 离线测试**；测试输出中有意模拟的子命令非零退出是断言对象，不是测试失败。YAML 检查依赖 PyYAML 6.0.3，只安装在被忽略的 `.validation/python` 中，未加入运行环境或应用依赖。

## 窄窗布局增量隔离验证

以下为增量 Impl 隔离阶段证据，该阶段尚未安装运行源码或发布。

Control 显式指定仓库源码运行 **14 项测试（原 8＋新 6），退出码 0**。100×30、60×20、40×16 的整个选择器及箭头在屏内；通过实际渲染条带与滚动读到完整程序/工作区文字，board 可视高度分别为 21、12、8 行。背景 popup、虚构图片/none/保存失败、可见点击、模拟 handler 拖放、79↔80 断点、拖动/慢刷新期间 resize 及原刷新回归均有断言。24×12 的 board 仅 2 行，作为观察项，不承诺全部文字可读。

旧实现红灯为 2 项测试中的 5 个子场景失败，包含 40 列选择器只显示 29/38 列及长名称/反馈裁剪。修改后首轮全量有 9 个新增夹具误报：边框混入正文、60 列被误要求强制折行、Pilot 对父 Select 的命中判断；修正夹具后新 6 项及完整 14 项重跑退出码 0。原 8 项的禁止真实保存断言未削弱。完整原始输出留在忽略的隔离目录，公开记录保留失败原因。

所有五个 backend 导入符号在导入 Control 前已替换；保存、聚焦和移动只调用 mock。模拟 handler 拖放不等于完整 Windows 鼠标协议验收。未安装运行文件或操作正在使用的界面；真实效果仍由下一自然新进程承接。

独立 Review(Impl r1) 的完整 Control 回归随后出现 **14 项、1 失败、退出码 1（166.780s）**：原合法的 8 秒定时刷新进入 resize 计数窗口，工作区查询 `[2,0,0,2,1]→[3,0,0,2,1]` 被误判为 resize 额外调用；其它 13 项通过。这次失败保留为独立审查证据，不能由作者先前绿灯覆盖。

Impl r2 只在该新增测试实例捕获并暂停参数为 8 秒、目标为该 Control 的原 timer，其它 Textual timers、产品源码与旧八项不改。计数窗口显式等待超过 8 秒后继续原连续尺寸/79↔80、五符号等值、DOM identity 和 queued release/move 断言。本轮完整 **14 项 Control 退出码 0（55.801s）**，测量实际 **8.266s / backend_delta=0**；完整 **13 项 Spectrum 退出码 0（1.325s）**。冻结 oracle、四源码编译、保护函数及局部变更范围检查均退出码 0；独立复审和根承接仍另行执行。

## 频谱固定数据增量隔离验证

以下同属增量 Impl 隔离阶段。Spectrum **13 项测试（原 8＋新 5），退出码 0**；冻结优化前 frame 算法，仅用合成输入或有界 fake recorder。固定 2048 点、120×8 的 200 个 50ms 活动帧仍有 200 次 FFT / 200 帧输出，Hann / geomspace 各从 200 次减少到 1 次。raw ANSI 字符串/None、levels/peaks、reference/amount、绘制时间与尺寸状态精确相等，不接受数值容差。

测试覆盖 0/1/2/3/127/128/2047/2048 点、mono/stereo、超长输入有界、空输入后短 burst、当前 key 替换及回访、仅高度/相同柱数宽度/柱数改变/极小尺寸 resize，以及声音→零/空输入→衰减→稳定 idle→恢复。稳定非空静音的 1000 次 frame 保留 1000 次 RMS、0 次 Hann/geomspace/FFT/绘制/三角函数；原活动 0.05 秒与静音 0.25 秒门及采集行为保持。

旧实现首轮新 4 项退出码 1（4 个失败、1 个预期缺少缓存成员错误）；随后先证明独立等价项通过，再记录 200 次构造计数的预期红灯（2 项、1 失败、退出码 1）。最小复用改动后完整 13 项退出码 0。离线构造次数下降不等于总体 CPU、真实设备延迟或正在运行的画面已更新。

## 独立审查、根复验与交付记录

以下承接 2026-10-03 代码实施轮的历史输出，不是文档归档轮重新执行的测试。独立 r2 审查为 PASS / PASS：Control 14 项（99.226s）、Spectrum 13 项（1.090s），均 exit 0；协调者随后完整复跑分别为 14 项（241.738s）与 13 项（1.295s），均 0 失败、exit 0。根计数窗口实际跨 8.625s，五符号增量为 0；四源码编译、冻结 oracle、32 保护函数及局部范围检查均 exit 0。

只有这些验证完成后才备份并替换两份批准的运行源码，两个备份先核对原始 SHA256；交付后其它 48 份运行源文件不变、两目标与审阅源码一致。没有重启或操作现用 UI/SSH/播放器。Control 与 Spectrum 分别提交为 `316d8ff`、`e0578a5` 并普通推送，远端 main 在该轮核对为 `e0578a5d5f7d073417a8c86289d157810f543f6b`；不把此历史值写成未来始终不变的远端状态。

保留失败：第 1 轮独立 Control 计数测试 exit 1 已在上文记录；协调者首次用旧 Windows PowerShell `-File` 读取 UTF-8 无 BOM 检查脚本出现编码解析错误、exit 1，随后显式 UTF-8 重读执行 exit 0。归档不删除这些记录或改写原审查结论。分轮报告和脱敏方案摘要见[历史归档](archive/2026-10-03/workbench-refinements-20261003/SUMMARY.md)。

✅ 已完成的是源码交付与离线证据闭环；⛔ 未验收的是下一自然新进程的真实鼠标、背景和音频、总体 CPU、长期稳定性及新电脑从零安装。重连已有 Zellij 不保证新代码加载，文档归档不操作这些进程。

## 可重复的测试入口

2026-10-03 文档归档轮仅做文档核对（exit 0）：原有 13 个非 README 文件字节保持不变，4 产品源码和 50 运行保护哈希一致；10 个私人历史文件忽略、5 个脱敏文件可公开，10 份公开 Markdown 的 38 个本地链接均可发布，隐私模式与差异空白检查无异常。该轮没有重跑产品测试、安装器验收或操作现用 UI；一次编排中断未返回验证结果，重新完整执行后才采用证据。

从仓库根目录执行，临时文件可设到 D 盘隔离目录：

```powershell
New-Item -ItemType Directory -Force .validation\tmp
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TEMP = (Resolve-Path .validation\tmp).Path
$env:TMP = $env:TEMP
python apps/control-center/tests/test_control_refresh.py --source apps/control-center/control_tui.py
python apps/control-center/tests/test_music_restore.py -v
python apps/spectrum/tests/test_spectrum.py -v
python tests/test_startup_reporting.py --source-dir .
```

请逐条检查退出码，不通过管道截断测试输出。Control 测试的 `--source` 必须保留，避免默认路径指向本机旧更新目录。未附带的旧渲染基线不纳入此次测试；不要设置依赖旧目录的 `SPECTRUM_LEGACY`。

配置与补丁检查：

```powershell
D:\terminal-workbench\apps\zellij\zellij.exe --config config/zellij/config.kdl setup --check
D:\terminal-workbench\apps\wezterm\wezterm.exe --config-file config/wezterm/wezterm.lua ls-fonts --text abc
git -C D:\MyGit1\CNMPlayer-workbench apply --check D:\MyGit1\wezterm-configure\patches\cnmplayer\windows-input.patch
```

最后一行需要未应用补丁、处于指定提交的干净上游源码，不能在已修改的运行源码上重复应用。

## 本轮遇到的问题与处理

- 导出后的启动测试曾退出 1：旧夹具把任意行中的 `wezterm` 都当作 GUI 启动，误伤包含仓库名 `wezterm-configure` 的临时路径，CMD 六种子场景被阻止。单场景复现后，只在公开测试副本改为检查行首命令，并补上目录名回归断言；真实启动脚本未改。完整 6 项随后重跑退出 0。
- 一次读取长测试输出的编排失败，未拿到该次最终退出码；该次不算验证证据。随后重新完整运行并读取输出和退出码，未依赖截断结果。
- 初稿 ignore 的递归放行规则覆盖了 Python 缓存规则。提交前移除过宽的放行，两种源码目录仍可跟踪；逐个验证缓存、日志、环境文件、二进制、图片与字体的忽略效果。此前没有缓存文件被暂存。
- 初始补丁导出因 CRLF 被误计为整文件变化，未发布该版本；使用 Git 的文本换行规范生成仅含三文件的补丁，再在独立上游副本检查可应用。
- 校验环境最初没有 PyYAML，系统/捆绑环境探测分别报依赖不存在。仅向仓库隔离目录安装校验依赖后解析 YAML；没有修改工作台 Python 环境。
- Control 测试出现约 0.109–0.453 秒的 asyncio 慢回调诊断，8 项仍退出 0。这是夹具中的诊断，不是实际 CPU 降幅或实时流畅性的测量。
- GitHub CLI 初始没有登录；公开仓库读取正常。提交与推送结果需以实际 Git 命令和远端提交 ID 为准，不把 CLI 登录探测当作已推送。
- 首次暂存空白检查退出 2：验证文档多余末尾空行已移除；补丁的六行单空格是 unified diff 的空白上下文前缀，不能删除。仅对 `.patch` 保留格式并关闭普通源码空白规则，再复查暂存差异与补丁可应用性。Git 的 LF/CRLF 提示来自显式换行属性，不修改本机源文件。

## 未在本轮验收

⛔ 新电脑从零安装、第三方二进制供应链和完整一键安装。

⛔ 播放器真实登录、真实歌曲播放与 F7/F8/F9 的实机输入；Rust 完整构建与测试。本次包含相应补丁与测试源码，但未在本轮重建。

⛔ Windows 窗口拖动/焦点/多显示器、YASB 交互、原生 Yazi 图片预览和音频设备切换。

⛔ 关闭/重启真实会话后的恢复、并发双击启动、所有后台性能和长时间稳定性。为不影响现用开发环境，未执行此类破坏性或交互验收。

已知限制见 [配置说明](CONFIGURATION.md) 与 [日常使用](USAGE.md)。本仓库是已实现工作台的安全源码快照，不保证当前使用方式之外的任意 Windows、Zellij 构建或硬件环境。

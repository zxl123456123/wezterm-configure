# 配置说明

本页说明当前实际配置入口和选择理由；快捷键与安装流程分别见 [USAGE](USAGE.md)、[INSTALL](INSTALL.md)。不直接修改全局 Windows Terminal 或其他 WezTerm 窗口的配置。

## 架构边界与优化取舍

本页是当前架构与配置决策入口，历史方案和分轮证据仅供回顾。

- ✅ 已实现：Zellij 管理主标签与面板，WezTerm 管理终端外观；Control 通过既有后端调用 GlazeWM，不能把平铺工作区直接当作 Windows 虚拟桌面或固定显示器。
- ✅ 已实现：Control 使用 Textual 原有样式机制适应窄窗，而不扩成横向滚动的大画布；尺寸变化不重建控件或额外查询后端，以保留拖动、刷新和身份的边界。
- ✅ 已实现：Spectrum 仅复用参数固定的数据，每个状态保留当前数组，不保存历史尺寸缓存或 FFT 结果；新的音频仍逐帧计算，以保持输出等价而不牺牲动效。
- ⛔ 未实现：自动安装、音频设备恢复、按标签可见性自动挂起后台。没有为本轮局部优化增加框架、依赖或常驻服务；Monitor 保持 1 秒采样。

Shell、Control、Spectrum 的源码更新需要新进程加载；WezTerm 外观 Lua 部署到运行目录后可重载，不必重启开发会话。现用会话与真实音频不由离线验证替代。历史决策及交付证据见[优化归档摘要](archive/2026-10-03/workbench-refinements-20261003/SUMMARY.md)，功能细节见下文，验证边界见 [VERIFICATION](VERIFICATION.md)。

## WezTerm 外观

入口：`config/wezterm/wezterm.lua` 与 `appearance.json`。

- Catppuccin Macchiato、11pt 字体、1.08 行高；字体目录是运行目录 `fonts`。缩小默认字号以便同屏阅读更多代码，保留原面板比例与配色。
- `window_background_opacity = 1.0`，先画不透明底色，再叠图片和深色遮罩；图片层 0.82、遮罩 0.16、文字背景 0.84。它们是分层参数，不是桌面透明开关。
- Control 只保存 `appearance.json` 的 `image` 文件名；WezTerm 监听它，图片不存在时使用底色；`none` 禁用图片。
- 单个 WezTerm 标签时隐藏外层标签栏；Zellij 内上方保留自己的 tab-bar，不放下方快捷键栏。
- `exit_behavior = Hold` 保留退出信息，避免启动失败消息一闪而过；窗口关闭不弹确认，因此重要任务由使用者自行确认。

✅ 当前选择：静态、易读背景；⛔ 未实现：专门的透明度 UI、全页面粒子场景或鼠标尾迹。

## Zellij 布局与启动

入口：`config/zellij/config.kdl`、`layouts/workbench.kdl`、`Ensure-WorkbenchTabs.ps1`。

固定会话为 `workbench-v4`。主布局负责新会话的五个标签；单标签 KDL 负责缺失标签恢复。统一只发布当前有效布局，不重复旧更新目录里的同类文件。

启动器先检查匹配本工作台参数的 WezTerm 窗口，复用或新开，然后检查标准标签。失败返回非零并写日志，不隐藏失败。没有新增常驻守护、并发启动锁或完整事务式恢复；重复并发启动、CLI 版本不匹配和大量 stdout/stderr 的边界仍需实机观察。

## 路径记忆

| 来源 | 保存文件 | 保存时机与限制 |
| --- | --- | --- |
| Windows Shell | `data/work-windows-shell.cwd` | PowerShell prompt 钩子；目录变化才写入；不是每条命令快照 |
| Windows Yazi | `data/work-windows-yazi.cwd` | `cwd-memory.yazi` 的 cd 事件 |
| Linux Main / Dev / Files | 远端 `~/.local/state/terminal-workbench/<slot>.cwd` | 交互 Bash prompt；各槽位独立 |

文件不存在或保存目录已删除时回退默认目录。当前路径文件属于运行状态，不提交 Git。原远程 IP 和个人项目路径已换为 SSH 别名/样例，运行目录中的真实连接未被修改。

## 本地 Shell 增强

入口：`Start-WorkShell.ps1`。保持 PowerShell 5.1 + PSReadLine 2.0.0、简洁 WIN 提示符与按目录变化保存 cwd；不改全局 profile，不升级模块，也不增加常驻 AI 或动画。

采用 [PSReadLine 原生键位](https://learn.microsoft.com/en-us/powershell/module/psreadline/set-psreadlinekeyhandler)：Tab 菜单补全、上下键前缀历史，配色使用 Macchiato RGB 与清晰选区。F2 复用 [fzf](https://github.com/junegunn/fzf) 按需搜索，遵循 [PSFzf 的编辑器集成方式](https://github.com/kelleyma49/PSFzf)，但不安装额外模块：退出原生 UI 后只重绘一次，选择只插入而不执行。

[zoxide](https://github.com/ajeetdsouza/zoxide) 使用官方 `--hook none` 初始化 z/zi，学习目录放在已有 prompt 的目录变化分支中；避免第二层提示符包装，并保留上一条程序的退出码。`_ZO_DATA_DIR` 固定在 D 盘运行数据目录；fzf 的 PATH 只在当前 Shell 进程中补齐。Shell 高亮不是任意程序输出高亮，也不是 AI 行内预测；这些边界与 PSReadLine 2.4 在旧宿主中的渲染兼容性有关。

## Monitor

入口：`config/bottom/readable.toml`。刷新 `1s`，60 秒历史；CPU 30%、磁盘/内存 28%、网络 17%、进程 25% 布局比例。CPU 默认平均曲线，保留小数；进程默认按 CPU 排序，显示滚动位置和滚动条。

采用成熟 bottom 的表格聚焦/排序/滚动，避免自己维护无法滚动的不断增加文本。并未根据本次发布短采样宣称某个 CPU 降幅。

## Control

默认入口 `apps/control-center/control_tui.py`；后端 `control_center.py` 通过 GlazeWM CLI 获取工作区/程序并执行聚焦/移动。

✅ 已实现：8 秒定时检查；查询到 DOM 挂载期间保持刷新互斥；手动/操作请求合并；拖动结束补刷；相同可见内容不构造卡片；查询或 DOM 错误可再次刷新。

继续使用原 Textual worker + 线程查询模型，不新增队列框架或按字段增量渲染。取消异步任务不保证同步终止已进入的底层查询线程；离线测试不是 Windows 鼠标捕获、焦点、拖拽实机验收。

窄于 80 列时使用同一批控件的纵排布局，背景选择器随可用宽度缩放，文字按内容增长并允许纵向滚动。尺寸变化只切换样式，保留卡片/程序身份，不触发额外后台查询；宽窗仍为双列卡片。验收尺寸与真实使用边界见 [验证记录](VERIFICATION.md)。

## Music 与频谱

播放器样例：`config/cnmplayer/default.toml`；部署后放 `data/cnmplayer/config/default.toml`。

Macchiato 主题、歌词页启用、F7/F8/F9 播放快捷键、原生 cava 关闭、30fps 播放器 UI。图形协议是 `halfblocks`；歌词/封面抓取开关、网易云账号和内容可用性不要混同。本次发布不宣称乐谱支持。

频谱入口：`apps/spectrum/spectrum.py`。44100Hz / 2048 点窗口；宽度不足时隐藏深度环绕区；宽窗口最高 80 条柱。活动绘制限约 20fps，静音衰减限 4fps，稳定后不重绘/FFT，但仍采集音频；SoundCard 指定的断续警告写两份有界日志，不刷满终端。

每个频谱状态只保留当前实际窗口长度的 Hann 数组，以及当前 `(窗口长度, 柱数)` 的频带索引。长度或柱数变化时替换对应数组；仅高度变化不重建固定数据。复用只发生在原有效活动 FFT 分支，不缓存音频结果、不修改采样/绘制节奏；离线证据见 [验证记录](VERIFICATION.md)，真实设备与总体 CPU 收益尚未验收。

恢复入口 `Restore-Music.cmd`：文件锁防止同一恢复同时进行；验证标签/Player/命令/状态后只替换已退出 Player，保留其他面板。不保证捕捉所有外部状态竞态。

## 顶部栏与平铺

YASB：`config/yasb/config.yaml` / `styles.css`，高 36px；左侧搜索和 GlazeWM 工作区、中间媒体、右侧 CPU/网络/磁盘/时钟。磁盘扩展列表为 C/D/E/G；本机没有的盘应删去或改成自己的盘符。

GlazeWM：`config/glazewm/config.yaml`，Work / Browser / Music / Other 四工作区，8px 内间距；不是固定四显示器。Control 读取真实监视器关系，一台监视器可显示多个工作区。

## 个性化与发布安全

默认 `D:\terminal-workbench` 与 `D:\workspace-for-everything` 是公开可复现约定，不是自动检测路径。迁移到其他盘符需搜索所有引用再调整。字体与壁纸请自行提供；Git 只保存可公开的静态配置。

用户配置不应承载登录 Token；不要提交 `data`、`.env`、SSH 配置实值、窗口快照或日志。`.gitignore` 按[Git 官方语义](https://git-scm.com/docs/gitignore)忽略未跟踪运行文件；对已跟踪文件不能靠新增 ignore 消除历史泄漏。

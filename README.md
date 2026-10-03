# Windows Terminal Workbench

Windows 开发终端工作台的配置、启动脚本和自写控件源码。主界面使用 **WezTerm + Zellij**，本地开发与远程 Linux 开发并排，辅以系统监控、音乐和窗口调度。

这是当前本机有效版本的公开配置快照，不是完整软件安装包，也不是 macOS 配置。新电脑仅克隆本仓库还不能直接运行：第三方程序、字体、背景图片和 SSH 连接需要自行准备。默认运行目录固定为 `D:\terminal-workbench`，仓库开发目录可以放在 `D:\MyGit1\wezterm-configure`。

## 当前页面

| Zellij 标签 | 内容与使用方式 |
| --- | --- |
| Work-Windows | 左侧 Yazi，右侧 PowerShell；真彩输入高亮、Tab 补全、F2 历史搜索、z/zi 跳转，记忆目录 |
| Work-for-Linux | SSH 三面板：Main / Dev / Files；远端分别记录当前目录；公开配置使用 `workbench-linux` 别名 |
| Monitor | bottom 的 CPU 曲线、磁盘、内存、网络和进程表；1 秒采样；表格可聚焦滚动 |
| Music | CNMPlayer 播放和歌词，上部 82% 播放器、下部局部彩色频谱与深度环绕效果 |
| Control | Textual 彩色工作区卡片；点击程序聚焦、拖到目标工作区调度；顶部选择背景图片 |

上述五个是 **Zellij 内层标签**，不是五个独立 WezTerm 窗口。Yazi 的原生图片预览入口会额外创建一个 WezTerm 标签，详见[日常使用](docs/USAGE.md)。

## 配置栈

- 终端：WezTerm；主题 Catppuccin Macchiato；不使用桌面透明。
- 多路复用：本机 Windows 原生 Zellij 构建；会话名 `workbench-v4`，隐藏下方快捷键栏。
- 本地 Shell：Windows PowerShell 5.1 + PSReadLine；简洁 `WIN <路径> >` 提示符，不依赖 zsh / Starship。
- 文件管理：Yazi + Chafa + Git for Windows 的 `file.exe`。
- 监控：bottom（`btm.exe`），不是截图里的 btop。
- 顶部栏：YASB；平铺：GlazeWM，不是 macOS 的 SketchyBar / AeroSpace。
- 音乐：[CNMPlayer](https://github.com/OkunaRei/CNMPlayer) + 自写 Windows WASAPI 系统音频频谱。
- 字体：Maple Mono NF CN / NF，另有 JetBrains Mono 回退。
- Control：Python / Textual；可选浏览器后备页面不是默认启动项。

## 新电脑使用前

✅ 已提供：配置、启动入口、自写 Control / Spectrum 源码、CNMPlayer 修改补丁和手动部署说明。⛔ 未提供：自动下载安装器、第三方二进制、字体、个人图片或登录凭据；整套从零安装尚未实机验收。

- 按[安装与迁移](docs/INSTALL.md)准备兼容的 Windows 程序和 Python 环境，再把配置部署到默认运行目录；只克隆仓库或把软件加入 PATH 并不足够。
- SSH 别名、服务器路径、音乐登录和本机盘符需自己填写；背景图可不提供，此时使用纯色。Music 的 Windows 输入补丁需按说明构建，不等同任意上游发行包。
- 下方入口是**部署完成后的一键启动**，不会下载缺失程序，也不会替你配置账号。已有工作台更新时只替换经过核验的文件，不覆盖整个运行目录。

## 一键入口

完成[部署说明](docs/INSTALL.md)后，从 `D:\terminal-workbench\launchers` 双击：

| 文件 | 用途 |
| --- | --- |
| `00-All.cmd` | 启动 YASB、GlazeWM 和 WezTerm / Zellij |
| `01-WezTerm-Only.cmd` | 只启动终端，不启动顶部栏和平铺 |
| `02-Bar-Only.cmd` | 只启动顶部栏 |
| `03-Tiling-Only.cmd` | 只启动平铺 |
| `04-Control.cmd` | 恢复或切换到 Control 标签 |
| `05-Stop-Bar-and-Tiling.cmd` | 停止顶部栏和平铺，保留终端 |

Music 被关掉或 Player 已退出时，使用根目录 `Restore-Music.cmd`。已有有效 Player 时只切换标签；退出的 Player 在原面板位置恢复，不向正在工作的终端发送按键。

## 目录结构

```text
.
├── README.md / requirements.txt
├── Start-*.cmd / Start-*.ps1 / Ensure-WorkbenchTabs.ps1
├── launchers/                 统一双击入口
├── config/
│   ├── wezterm/               配色、字体、背景与原生图片预览入口
│   ├── zellij/                会话主题、五标签布局、单标签恢复布局
│   ├── yazi/                  文件预览与目录记忆插件
│   ├── bottom/                彩色曲线、磁盘与进程表
│   ├── yasb/                  顶部栏 YAML / CSS
│   ├── glazewm/               工作区与窗口快捷键
│   └── cnmplayer/             无账号的播放器配置样例
├── apps/
│   ├── control-center/        自写 Control / 后端 / 可选浏览器页面 / 测试
│   └── spectrum/              自写频谱 / 测试
├── remote/                    SSH 别名样例、远端每面板 cwd 记录
├── patches/cnmplayer/         基于固定上游提交的修改补丁与原许可
├── tests/                     隔离启动器与 Shell 测试，不操作真实会话
├── docs/                      安装、使用、配置和验证边界
├── images/                    仅说明；图片由使用者提供
└── fonts/                     仅说明；字体由使用者提供
```

## 恢复、性能与边界

✅ 已实现：启动时补齐缺失标准标签；保存本地 Shell / Yazi 和远端每面板的目录；启动失败返回非零状态并记录 `data\startup.log`；Control 8 秒检查变化并保留滚动位置；Monitor 保持 1 秒采样。

✅ 已实现：频谱使用真实默认输出设备的系统音频，不是随机假动画；有声时最多约 20 帧/秒，衰减时降频，静音稳定后停止重复绘制和 FFT。但音频采集仍存在，不能称为零 CPU；其他应用的声音也会驱动频谱。

✅ 已实现：Control 查询与挂载阶段的刷新合并；鼠标拖动结束补刷；可见显示名和工作区身份变化触发更新，而无关焦点变化不重建卡片。

✅ 已实现：Control 窄于 80 列时纵排、文字随内容折行，缩放保留控件身份；Spectrum 复用当前长度的 Hann 数组与当前柱数的频带索引。采用现有组件能力，不降低刷新率或删除动效；具体边界见[配置说明](docs/CONFIGURATION.md)。

⛔ 未实现：重启后恢复之前正在运行的命令或远端任务；Windows 原生虚拟桌面调度；任意 Shell 的 AI 自动补全；独立乐谱显示；所有窗口内的 3D 特效。环绕效果是终端字符绘制的局部深度视觉，不是 GPU 3D 引擎。

⛔ 未保证：Zellij 内 Yazi 的真彩图片传输、半块封面的图像质量、各设备的音频暂停状态或所有后台负载。真实图片优先用 `Ctrl+Shift+I` 进入原生 WezTerm Yazi 标签。

关闭 WezTerm 后，如果 Zellij 会话仍存活，启动器会重连；重启系统后依靠 Zellij 布局恢复和 cwd 文件恢复目录，**不会恢复任务执行状态**。更新文件不会替换已运行的 Control / Shell / Spectrum 进程；重连旧会话也不会自动让旧进程加载新代码。

## 阅读入口

- [安装与迁移](docs/INSTALL.md)：程序路径、Python 环境、远端初始化、CNMPlayer 补丁。
- [快捷键与日常操作](docs/USAGE.md)：切标签、开关面板、暂停后台、排错。
- [配置说明](docs/CONFIGURATION.md)：外观、各页面、磁盘、目录记忆与低占用策略。
- [验证与限制](docs/VERIFICATION.md)：本次发布验证结果与未进行的实机验收。
- [上游组件与许可](docs/UPSTREAM.md)：下载来源及第三方补丁边界。
- [2026-10-03 优化历史摘要](docs/archive/2026-10-03/workbench-refinements-20261003/SUMMARY.md)：决策、分轮测试、失败留痕和受控交付；只作历史参考，当前行为以上述现行文档为准。

公开仓库不保存登录信息、SSH 私钥、音乐缓存、窗口数据、会话历史、原服务器地址、软件二进制、字体或个人背景图。不要把整个本机运行目录直接 `git add`；`.gitignore` 不能替代发布前的人工检查。

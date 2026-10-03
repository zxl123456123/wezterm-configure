# 安装与迁移

本仓库只包含配置和源码。以下步骤面向新安装；**已有工作台不要把整个目录覆盖过去**，尤其不要覆盖 `data`、当前图片或仍在使用的配置。仓库开发目录与运行目录分开，是为了发布时不混入本机状态。

## 部署前检查

⛔ 当前没有自动安装器。`00-All.cmd` / `01-WezTerm-Only.cmd` 是部署后的启动入口，不会下载软件、创建 Python 环境或配置远端。以下清单需手动完成；本文不是已通过新电脑验收的承诺。

- [ ] Windows 有可用 D 盘，运行目录和默认项目目录按第 1、3 节建立；改盘符需统一修改各语言配置，不能只移动文件夹。
- [ ] 第 2 节的第三方程序放到启动器实际引用的位置。尤其核对 Windows 原生 Zellij 的 CLI 兼容性；只在 PATH 中安装软件不满足固定路径约定。
- [ ] 第 4 节 Python 环境和固定依赖已准备；Git for Windows 的 `file.exe` 和 Windows OpenSSH 客户端可用。
- [ ] 字体已按第 5 节准备；背景图片可省略。YASB 的磁盘列表按自己的盘符调整，GlazeWM 工作区按自己的显示器使用，不假定每人都有四个显示器。
- [ ] 使用远端标签时完成第 6 节的 SSH 认证和远端脚本部署；公开的 `workbench-linux` 是别名样例，不是真实服务器。
- [ ] 使用 Music 时完成第 7 节的带补丁播放器构建与个人登录。账号、Cookie、缓存和私钥不上传。

配置完成后再按第 8 节启动。缺少某个组件时，不承诺启动器自动跳过对应标签；也不要把启动成功等同音乐、图片和多显示器功能均已验收。

## 1. 获取源码

```powershell
git clone https://github.com/zxl123456123/wezterm-configure.git D:\MyGit1\wezterm-configure
```

本版本固定运行于 `D:\terminal-workbench`；默认本地项目目录为 `D:\workspace-for-everything`。需要改路径时，参照[配置说明](CONFIGURATION.md)统一调整 CMD、PowerShell、Python、Lua 和 KDL 中的引用，不能只改一个环境变量。

## 2. 准备第三方程序

按下表准备文件。默认启动器使用便携目录，而非依赖全局 PATH；安装版的位置不一致时，需要手动调整对应路径。请使用上游官方渠道，不把本机二进制提交到仓库。

| 程序 | 默认运行文件 | 本机发布前实读版本 |
| --- | --- | --- |
| WezTerm | `apps\wezterm\wezterm-gui.exe` / `wezterm.exe` | `20260917-114457-b09b56c2` |
| Zellij Windows 构建 | `apps\zellij\zellij.exe` | `0.45.1` |
| bottom | `apps\bottom\btm.exe` | `0.14.9` |
| Yazi | `apps\yazi\yazi-x86_64-pc-windows-msvc\yazi.exe` | `26.9.1` |
| Chafa | `apps\chafa\chafa-1.18.3-1-x86_64-win\chafa.exe` | 此发布未重新核对版本 |
| YASB | `apps\yasb\yasb.exe` / `yasbc.exe` | 此发布未重新核对版本 |
| GlazeWM | `apps\glazewm\glazewm.exe` / `cli\glazewm.exe` | 此发布未重新核对版本 |
| CNMPlayer | `apps\cnmplayer\cnmplayer.exe` | 固定上游源码 + 本仓库补丁；本轮未重建 |

所有路径均相对于 `D:\terminal-workbench`。Windows 原生 Zellij 是兼容前提：此仓库未附带或确认其二进制供应来源，不能假设任意 Zellij 上游/WSL 安装都能直接启动 Windows KDL 里的命令。需要兼容 `list-tabs --state/--json`、`list-panes --all --json`、`new-pane --in-place` 等 CLI。

另外安装 Git for Windows，并确认 `C:\Program Files\Git\usr\bin\file.exe` 存在；启用 Windows OpenSSH 客户端。PowerShell 5.1 + PSReadLine 2.0.0 为当前本地 Shell，不需要升级 PowerShell 7。

可选增强：从官方发行页准备 `apps\fzf\fzf.exe`（本机实读 0.74.4）和 `apps\zoxide\zoxide.exe`（本机实读 0.10.0）。新 Work-Windows Shell 自动启用 F2 历史搜索与 z/zi 目录跳转，数据保存在 `data\zoxide`；缺少工具时仍保留基础 Shell、Tab 补全和配色。没有自动下载器；fastfetch 仍只是可选工具。使用方式见 [USAGE](USAGE.md)。

上游链接见 [UPSTREAM](UPSTREAM.md)。YASB 的上游安装方式见[官方安装文档](https://github.com/amnweb/yasb/wiki/Installation)；如果安装到系统目录，请调整本仓库路径，不要为了路径匹配随意复制系统运行库。

## 3. 部署配置与自写程序

为新安装建立运行目录和默认项目目录：

```powershell
New-Item -ItemType Directory -Force D:\terminal-workbench, D:\workspace-for-everything
New-Item -ItemType Directory -Force D:\terminal-workbench\data, D:\terminal-workbench\images, D:\terminal-workbench\fonts
```

将仓库中的根目录 `*.cmd` / `*.ps1`，以及 `config`、`launchers`、`remote`、`apps\control-center`、`apps\spectrum` 复制到运行目录同名位置。无需复制 `.git`、`patches` 或测试文档到运行目录。第三方程序按上表另行准备。

播放器的配置样例位于仓库 `config\cnmplayer\default.toml`，实际读取位置不同：

```powershell
New-Item -ItemType Directory -Force D:\terminal-workbench\data\cnmplayer\config
Copy-Item D:\MyGit1\wezterm-configure\config\cnmplayer\default.toml D:\terminal-workbench\data\cnmplayer\config\default.toml
```

这两行只适用于新安装；已有播放器配置先备份，不要覆盖登录数据。`CNMPLAYER_ASSET_DIR` 由启动器指向运行目录的 `data\cnmplayer`。

## 4. Python 环境

本机使用 Python 3.12.10。为自写控件单独建立环境：

```powershell
py -3.12 -m venv D:\terminal-workbench\apps\spectrum-venv
D:\terminal-workbench\apps\spectrum-venv\Scripts\python.exe -m pip install -r D:\MyGit1\wezterm-configure\requirements.txt
```

固定依赖来自本机已安装包元数据，不是“最新版本”推荐；本轮不在新电脑重新下载这些包，不能把安装命令写成已验收的一键安装器。YASB 使用自己的发行环境，不应装进这个 Python 3.12 环境。

## 5. 字体与背景

自行准备字体和合法图片，分别参照 [fonts](../fonts/README.md) 与 [images](../images/README.md)。没有图片时使用纯色背景；默认不透明，不会穿透到桌面背景。

## 6. 配置远程 Linux 三面板

1. 把 [SSH 别名样例](../remote/ssh-config.example) 中的条目加入本机 `%USERPROFILE%\.ssh\config`，填写自己的 HostName 和 User。不要把填好的连接信息和私钥提交到公开仓库。
2. 先在普通终端执行 `ssh workbench-linux`，确认认证、主机指纹和连接可用。仓库不会配置免密码、接受未知指纹或修改服务器安全设置。
3. 远端创建 `~/.local/share/terminal-workbench/`，把 `remote\pane.sh` 与 `remote\rc.sh` 放进去。可在本机手动执行：

```powershell
ssh workbench-linux 'mkdir -p ~/.local/share/terminal-workbench'
scp D:\MyGit1\wezterm-configure\remote\pane.sh D:\MyGit1\wezterm-configure\remote\rc.sh workbench-linux:.local/share/terminal-workbench/
```

4. 样例 Main 默认目录是 `$HOME/projects/workbench`，Dev 是 `$HOME`，Files 是 `$HOME/projects/workbench/publish`；按自己的项目修改远端 `pane.sh`。默认目录不存在时回退远端 home。
5. 文件使用 LF 换行，由 Windows OpenSSH 调用 `bash .../pane.sh main|dev|files`，不依赖系统全局 zsh。

每个槽位在远端 `~/.local/state/terminal-workbench/<slot>.cwd` 独立保存路径。保存位置是在交互 Bash 的提示符钩子上，不是每条命令的执行快照；远端任务和 Shell 历史不上传，也不由此机制恢复。

## 7. 构建带输入补丁的 CNMPlayer

补丁基准为 `OkunaRei/CNMPlayer` 的提交 `ad12b0002089f89952eb2a63af3c0d421f1405ed`，具体内容和原许可见 [patches/cnmplayer](../patches/cnmplayer/README.md)。在单独源码目录执行：

```powershell
git clone https://github.com/OkunaRei/CNMPlayer.git D:\MyGit1\CNMPlayer-workbench
git -C D:\MyGit1\CNMPlayer-workbench checkout ad12b0002089f89952eb2a63af3c0d421f1405ed
git -C D:\MyGit1\CNMPlayer-workbench apply --check D:\MyGit1\wezterm-configure\patches\cnmplayer\windows-input.patch
git -C D:\MyGit1\CNMPlayer-workbench apply D:\MyGit1\wezterm-configure\patches\cnmplayer\windows-input.patch
cargo test --locked --manifest-path D:\MyGit1\CNMPlayer-workbench\Cargo.toml tmplayer::utils::input::tests
cargo build --release --locked --manifest-path D:\MyGit1\CNMPlayer-workbench\Cargo.toml
```

使用符合上游要求的 Rust / MSVC 构建工具链，参考上游 README。构建完成后将自己的 `target\release\cnmplayer.exe` 放到运行目录对应位置。本次发布只验证补丁可应用，不重新下载 Rust 依赖或编译，以上构建命令不是本轮已执行结果。

首次登录网易云音乐由自己操作，账号、Cookie 和缓存只留在本机 `data` 中。

## 8. 启动和后续更新

双击 `D:\terminal-workbench\launchers\01-WezTerm-Only.cmd` 启动终端；需要顶部栏与平铺时用 `00-All.cmd`，可为其创建桌面快捷方式。启动报错看 `D:\terminal-workbench\data\startup.log`。

更新前备份要替换的文件，先验证新版本，再在方便的时间替换相关源文件。不要为了更新而关闭正在运行的远端任务。旧进程不会因 Git pull 或重新连接 Zellij 自动变成新代码；现用 Control / Shell / Spectrum 需要以后新开对应进程才加载更新。

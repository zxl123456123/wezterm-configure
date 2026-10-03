# 上游组件与许可边界

此仓库包含自写控件与个人配置，以及一份单独的第三方修改补丁；不打包上游程序、不把上游整个仓库复制为自己的代码，也不为整个配置仓库擅自添加新的统一许可。

| 组件 | 上游入口 | 用途 |
| --- | --- | --- |
| WezTerm | https://github.com/wezterm/wezterm | 终端、字体、背景与图片传输 |
| Zellij | https://github.com/zellij-org/zellij | 多标签/面板/会话；Windows 原生构建来源未在本次发布核定 |
| Yazi | https://github.com/sxyazi/yazi | 文件管理 |
| Chafa | https://github.com/hpjansson/chafa | 字符图片辅助 |
| bottom | https://github.com/ClementTsang/bottom | CPU、磁盘、网络、进程监控 |
| YASB | https://github.com/amnweb/yasb | Windows 顶部栏 |
| GlazeWM | https://github.com/glzr-io/glazewm | Windows 平铺与工作区 |
| CNMPlayer | https://github.com/OkunaRei/CNMPlayer | 网易云 TUI 播放器 |
| Maple Mono | https://github.com/subframe7536/maple-font | 字体，自行下载并核对许可 |
| Textual | https://github.com/Textualize/textual | Control TUI |
| SoundCard | https://github.com/bastibe/SoundCard | Windows 音频回环采集 |

CNMPlayer 的补丁基准提交、修改内容和原项目 **GNU AGPL v3** 许可原文保存在 `patches/cnmplayer`。补丁含上游上下文，第三方部分保留其原许可与归属；不把这份许可声明误写成所有其他依赖的许可。

下载/安装/分发软件、字体、图片时，分别遵循对应上游条款。发布时不附带账号、专辑封面缓存、个人背景图、二进制和整个第三方源码目录。

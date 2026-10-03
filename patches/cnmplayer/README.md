# CNMPlayer Windows 输入补丁

上游：[OkunaRei/CNMPlayer](https://github.com/OkunaRei/CNMPlayer)。固定基准提交：`ad12b0002089f89952eb2a63af3c0d421f1405ed`。本目录保留该项目 `LICENSE` 原文（GNU AGPL v3）；没有把整个上游仓库搬入工作台仓库。

`windows-input.patch` 合并本机当前三个文件的有效变更：

1. `Cargo.toml` / `Cargo.lock`：去掉 `ratatui-image` 的 `chafa-dyn` 功能及对应依赖，保留 crossterm，配合当前 Windows 半块图像方案。
2. `src/tmplayer/utils/input.rs`：只处理键盘 Press 事件，忽略 Release / Repeat，避免 Windows 终端按一次发生重复切换。
3. 全屏支持配置中的 F7/F8/F9 音乐键，保留原来的全屏键，并让弹层优先处理其输入。
4. 附五项 Rust 输入映射回归测试：常用键、旧键、自定义全屏键、Release/Repeat 和弹层。

构建流程见 [安装说明](../../docs/INSTALL.md)。升级上游版本时先在干净源码上 `git apply --check`，不要直接强制覆盖文件。当前补丁以固定基准生成，不宣称适用于未来所有上游版本。

本次发布只做补丁应用核查；没有重新构建 CNMPlayer，也没有对实际歌曲、账号认证和音频设备做新验收。

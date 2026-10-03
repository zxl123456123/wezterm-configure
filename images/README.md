# 背景图片

图片不随仓库分发。将自己有权使用的 PNG / JPG / JPEG / WEBP / GIF / BMP 放到运行目录 `D:\terminal-workbench\images`，然后从 Control 顶部选择；选择 `none` 使用纯色背景。

默认文件名为 `terminal-background.png`。文件不存在时 WezTerm 回退到纯色，不会显示桌面透明。选中的文件名存放在 `config\wezterm\appearance.json`。

Control 保存背景前检查图片能否解析、大小不超过 30 MB、像素数量不超过 8000 万。GIF 等动画格式的实际播放表现取决于终端，不保证作为动态壁纸工作。不要把专辑封面缓存或私人截图上传到公开仓库。

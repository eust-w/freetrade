# FreeTrade 项目演示视频

## 中英文双语版 / Bilingual Edition

v0.1.1 提供中文旁白（Tingting）和英文旁白（Samantha）两套成片。每套都烧录中英文逐句字幕，并各导出 1920×1080 横版与 1080×1920 竖版。两种语言按各自语音时长独立对齐，视频图示也提供中英文；实际界面截图仍为中文。

English and Chinese are separate narration editions. Both include burned-in Chinese and English captions, bilingual diagrams, and landscape/portrait exports. The original dashboard screenshots remain in Chinese.

[下载四套成片 / Download all four exports](https://github.com/eust-w/freetrade/releases/tag/v0.1.1)

```bash
python -m media.build_bilingual --frames-only  # inspect layout first
python -m media.build_bilingual                # render both languages and ratios
```

需要 macOS 系统语音、FFmpeg / ffprobe、Python 与 Pillow。源文案在 [storyboard.bilingual.json](storyboard.bilingual.json)，字幕时码由每段实际音频长度与 24fps 帧数计算，不套用另一种语言的时码。导出目录为 `media/export/bilingual/`，不进入 Git 历史。

文件名中的 `zh` / `en` 表示**配音语言**，`bilingual` 表示**画面双语字幕**。每种配音另附中文、英文、双语三份 SRT，时码对应同配音的横竖版。`manifest.json` 记录时长与尺寸，`SHA256SUMS.txt` 用于附件校验。

旧版社交平台视频不会被悄悄替换；各版本发布状态见 [PUBLISHED.md](PUBLISHED.md)。

## 原中文单语版 / Original Chinese Edition

素材来自本仓库真实浏览器截图、代码架构与脱敏运行记录。字幕与图示为原创排版，旁白为 macOS 系统合成语音；无第三方音乐、人物肖像或私人后台画面。数据演示使用虚构样本，历史运行数字来自 docs/runs/summary.json。

## 内容

开场问题：HTTP 200，行情就更新了吗？依次展示面板、五因子、数据路径、127 份日志、时间与模式隔离，最后给出开源地址。

本视频介绍软件工程与研究流程，不推荐具体证券或宣称收益。横版用于 YouTube / Bilibili / X，竖版用于抖音。

## 复现

macOS、FFmpeg、ffprobe、Python、Pillow 与 Tingting 系统语音：

```bash
python media/build_video.py
```

默认从 docs/assets 读取截图，输出到被 Git 忽略的 media/export。其他平台可按 storyboard.json 自行录制旁白并替换音轨。视频成片放到 GitHub Release，不将大文件提交进代码历史。

发布文案见 [publish-copy.json](publish-copy.json)，公开视频链接与当次核验结果见 [PUBLISHED.md](PUBLISHED.md)。成片约 75.2 秒，横版 1920×1080、竖版 1080×1920，均为 H.264/AAC；封面提供 16:9、4:3、3:4 三种比例。

[下载 v0.1.0 视频与封面](https://github.com/eust-w/freetrade/releases/tag/v0.1.0)。旁白为合成语音，已在发布文案中披露；不包含第三方音乐。

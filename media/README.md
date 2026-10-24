# FreeTrade 项目演示视频

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

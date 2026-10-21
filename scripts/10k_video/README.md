# Ghost Downloader 10k Star 纪念视频生成器

这是 Ghost Downloader 从最新版一路“倒放”回 Ghost Downloader 2 的回忆视频（1920×1080 / 60fps / 2:36）。
画面里的界面都是在 Linux（Xvfb）里真实运行各历史版本、真实下载文件时抓下来的，不是手绘仿制。

成片和配乐不放进仓库。配乐是 *all I want is you*（Rebzyyx / hoshie star），只用于本地渲染。

## 视频结构

- **节拍**：`audio/beatgrid.py` 先从底鼓拟合出 145.88 BPM，再把第一下重拍（5.956s）定为第 0 小节，
  每小节 1.645s。切换版本的时间点都落在小节线上，结果写在 `data/timeline.json`。
- **版本**：每个版本占一段（4 或 8 小节），段内每 2 小节换一个界面。任务列表是每 0.8s 一帧的真实下载进度，
  所以画面一直在动。
- **过渡**：换版本或换页面时按组件做匹配。导航按钮、任务卡片、设置组、按钮、标签、对话框各自移动，
  再交叉淡化。匹配不上的组件缩小淡出或放大淡入。
- **右上角**：版本号、发版当天的 Star 数和日期。Star 数取自 star-history 导出的 `data/gd3_stars.csv`。
- **左下角**：斜体更新说明。
- **左上角**：Star History 曲线，光点会跟着版本往回退。
- **124.4s 之后**：音乐开始“下沉”，窗口逐渐下移、画面逐渐变暗。
  GD2 原本依赖 Windows 亚克力效果，这里用模拟的亚克力背景代替。
- **结尾**：仿照官方宣传片。功能关键词先聚成一个旋转的球，再收进图标，最后出现标题、地址和 10K Stars。

| 段 | 版本 | 段 | 版本 |
|---|---|---|---|
| 0–6.0s | 片头：0 → 10,000 ★ | 84.9s | v3.7（间奏） |
| 6.0s | v4.4.4 | 91.5s | v3.6.1 |
| 12.5s | v4.4.0 | 98.1s | v3.5.12（第二次进鼓：冲上 GitHub Trending） |
| 19.1s | v4.3.0 | 104.7s | v3.5.0 |
| 32.3s | v4.2.6 | 111.2s | v3.4.1 |
| 45.4s | v4.1.1（OOBE） | 124.4s | v3.3.0（开始下沉） |
| 52.0s | v4.1.0 | 131.0s | v3.2.0（开源） |
| 58.6s | v4.0.0（+ Android） | 137.6s | v2.9.9-alpha（first commit） |
| 65.2s | v3.10 | 144.1s | Ghost Downloader 2 v2.0.2-1 |
| 71.8s | v3.9 | 147.4s | 结尾 |
| 78.3s | v3.8.3 | | |

## 目录

| 路径 | 作用 |
|---|---|
| `tools/gdcap.py` | 启动某个版本的入口脚本，用 Qt 定时器驱动 `scen/` 里的场景：点按钮、加任务、截图 |
| `tools/gdcomp.py` | 把窗口拆成组件图层，外加一张去掉所有组件的背景底图，供平滑过渡使用 |
| `tools/run_ver.sh`、`cap_one.sh`、`cap_all.sh` | 在 Xvfb 里用隔离的 HOME 运行指定版本；`versions.tsv` 记录每个版本用哪个环境、入口和场景 |
| `tools/fakeserver.py`、`files.json` | 本地限速下载服务器（`dl.example.com` → 127.0.0.1），让任务列表有真实的速度和进度 |
| `tools/gd2_key.py` | GD2 的亚克力窗口在 Linux 下会留下大块纯黑，用它抠成透明 |
| `scen/*.py` | 各时期版本的操作脚本：`vm.py` 对应 3.7+，`v3x.py` 对应 3.1–3.6，`v299.py` 对应首个提交，`gd2.py` 对应 GD2，`mobile.py` 对应安卓界面预览 |
| `scen/prelude_*.py`、`stubs_*/` | 让只能在 Windows 上运行的老版本在 Linux 上启动（winreg/win32 桩、离线资源列表等） |
| `audio/beatgrid.py` | 检测底鼓、拟合节拍网格，生成 `data/timeline.json` |
| `video/scenes.py` | 每段放哪些截图、字幕写什么 |
| `video/render.py` | 用 QPainter 合成每一帧，写进 ffmpeg |
| `video/make_video.sh` | 多进程分段渲染，再拼接、混入音频 |

## 重新生成

抓图步骤会改 `/etc/hosts`、在 80 端口起服务，还会清空 `/home/ghost` 和 `/opt/Ghost-Downloader`，
请在一次性的容器或虚拟机里运行。

```bash
cd scripts/10k_video
# 0. 依赖：xvfb、fonts-noto-cjk、zh_CN.UTF-8 locale、ffmpeg、uv；音频分析需要 librosa
# 1. 各历史版本 checkout 到 ver/<tag>
#    GD3 用上游 XiaoYouChR/Ghost-Downloader-3 的 tag（v3.2.0 对应 tag "release"，v2.9.9 对应首个提交 31970d1c）
#    GD2 用 XiaoYouChR/Ghost-Downloader-2 的 v2.0.2-1，放在 ver/gd2；ver/v4.0.0-mobile 链接到 ver/v4.0.0
# 2. Python 环境放在 envs/<A|B|C|D|E|G2>，各自的版本见 tools/versions.tsv 开头的注释
# 3. 节拍（可选，结果已提交）
python3 audio/beatgrid.py song.flac <含上游 tag 的仓库>
# 4. 抓图
echo "127.0.0.1 dl.example.com" >> /etc/hosts
python3 -I tools/fakeserver.py 80 &
tools/cap_all.sh v4.4.4 v4.4.0 v4.3.0 v4.2.6 v4.1.1 v4.1.0 v4.0.0 v4.0.0-mobile v3.10 v3.9 v3.8.3 \
                 v3.7 v3.6.1 v3.5.12 v3.5.0 v3.4.1 v3.3.0 v3.2.0 v2.9.9 gd2
# 5. 渲染
video/make_video.sh envs/D/bin/python song.flac out.mp4 4
```

只改字幕或镜头时，改 `video/scenes.py` 后重跑第 5 步即可。要更新 Star 数据，替换 `data/gd3_stars.csv`
后重跑第 3 步。单帧预览用 `python video/render.py --still 62 --out frame.png`。

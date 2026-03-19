# 视频规格与参考

## 输出视频规格

| 参数 | 值 |
|------|-----|
| 分辨率 | 1920×1080 (16:9 横屏) |
| 帧率 | 30fps |
| 编码 | H.264 (libx264) |
| 音频编码 | AAC 128kbps |
| 像素格式 | yuv420p |
| 转场 | 默认无转场（concat 拼接） |
| 轻动态 | 默认关闭，按需显式开启 `--motion auto` |

## 推荐目录结构

所有输出物建议写到仓库根目录下的独立 run：

```text
workspace/article-to-video/<slug>-<timestamp>/
├── outline.json
├── meta.json
├── slides/
├── preview/
├── audio/
├── build/
├── output/
└── canvas/
```

这样可以避免每次运行互相覆盖，也方便回溯和局部重做。

## 字幕样式

```text
FontName=Microsoft YaHei,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=42
```

- 字体：微软雅黑（回退 Noto Sans CJK SC）
- 字号：12（在 1920×1080 横版讲解视频中较稳妥）
- 颜色：白色，黑色描边 2px
- 位置：底部居中，默认距底 `42px`

> 相比之前的 `MarginV=25`，更高的底部边距更适合课程类横版视频，也能减少“字幕贴边”的压迫感。

## 幻灯片底部安全区

视频中的 PPT 不是独立观看的，它总是和字幕叠在一起。因此幻灯片设计必须把底部安全区当成硬规则，而不是软建议。

建议：

- 页面可视内容区底部至少预留 `56pt`
- 推荐预留 `56pt-72pt`
- 导出的 JPG 中，footer 必须保留清晰可见的空白区域，不能被正文视觉重量吃掉
- 除页码 / 标签等弱元素外，底部保留区应尽量保持为空，确保字幕叠加后仍有呼吸感
- 整体构图要避免“上重下轻”，让页面纵向视觉重量更均衡
- 使用 `content-area + footer-safe` 的结构
- 不要让正文容器通过 `justify-content: space-between` 吃满整个竖向空间

推荐骨架：

```html
<main class="page-shell">
  <section class="content-area">
    <!-- main content -->
  </section>
  <footer class="footer-safe">
    <!-- label / page number / reserved safe zone -->
  </footer>
</main>
```

## 为什么默认不使用转场

xfade 转场在 fade 期间会混合相邻两个片段的视频帧。由于字幕是预先烧录在每个片段中的，转场期间会出现两页字幕同时显示的问题。

因此默认使用 concat demuxer 简单拼接（`--transition 0`）。

如果确实需要转场效果，可以用 `--transition 0.5`，但需要接受转场期间字幕重叠的瑕疵。

## 为什么默认静态，动态只按需开启

当前管线本质上是：

```text
HTML / PPT -> Playwright 截图 -> FFmpeg 合成视频
```

默认先用静态画面完成构图和平衡，确认 JPG 的 footer 留白、字幕安全区和整体重心都没问题。只有在页面确实受益时，再在视频层给截图加轻微镜头运动：

- 页面入场淡化
- 轻微左右 / 上下漂移
- 微小 overscan 后裁切，制造“镜头在动”的感觉

这种方案的优点是：

- 默认更稳，不会因为动态裁切破坏原本留出的 footer 空白
- 不依赖 html2pptx 对动画的支持
- 更容易控制成片稳定性
- 几乎不影响 PPT 导出兼容性

## Edge-TTS 常用中文语音

| 语音 ID | 风格 | 适用内容 |
|---------|------|----------|
| `zh-CN-YunjianNeural` | 稳重、清晰 | 技术讲解、课程、工程主题 |
| `zh-CN-YunxiNeural` | 克制、理性 | 商业复盘、汇报、策略内容 |
| `zh-CN-XiaoxiaoNeural` | 温和、自然 | 故事化讲解、文化内容 |
| `zh-CN-XiaoyiNeural` | 轻盈、年轻 | 生活方式、轻松内容 |

## 自动音色选择建议

现在推荐默认使用：

```bash
python scripts/generate_audio.py outline.json audio --voice auto
```

自动模式会根据：

- 标题
- 每页 heading
- bullets
- 讲稿 script

来自动推断内容属于：

- `technical`
- `business`
- `story`
- `energetic`
- `balanced`

并为本次运行选择合适的 `voice / rate / volume / pitch / pause` 组合。

如果需要，也可以在 `outline.json` 中加入：

```json
{
  "tts": {
    "profile": "technical"
  }
}
```

或在命令行里手动覆盖：

```bash
python scripts/generate_audio.py outline.json audio \
  --voice zh-CN-YunjianNeural \
  --rate="-5%" \
  --pause 1.1
```

## 语速调节

通过 `--rate` 参数调节，格式为百分比：

- `+10%` — 略快，适合轻松内容
- `-5%` — 稳定自然，适合技术讲解
- `-10%` — 偏慢，适合强调重点
- `+0%` — 默认语速

> `argparse` 传递负值时请使用 `--rate="-5%"` 这种等号语法。

## 音频管线

```text
Edge-TTS -> MP3(原始) -> WAV(追加静音) -> render_video 一次性编码 AAC
```

**为什么用 WAV 中间格式**：

MP3 是有损编码，每次编解码都会引入噪声和 encoder delay。如果做 MP3 -> MP3 -> AAC 三次编解码，在 24kHz 低采样率下会出现明显的电流声和时间偏移。

改用 WAV（无损 PCM）作为中间格式，只在最终 `render_video.py` 时一次编码为 AAC，音质最好。

## 视频片段精确时长

使用 `-t <duration>` 替代 `-shortest` 控制每个片段的时长。  
`-shortest` 在 `-loop 1` 模式下因 GOP 对齐和编码器缓冲会导致视频轨比音频轨长 0.6-2 秒。

`-t` 直接使用 manifest 中 ffprobe 测量的精确时长，音画对齐误差通常可控制在 `0.05s` 量级。

## Edge-TTS 字幕生成注意事项

edge-tts v7+ 的 `communicate.stream()` 会发送两种边界事件：

- `WordBoundary` — 词级别边界
- `SentenceBoundary` — 句级别边界

`SubMaker.feed()` 需要同时处理这两种类型：

```python
elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
    submaker.feed(chunk)
```

仅处理 `WordBoundary` 可能导致字幕内容不完整。

## frontend-design 与 canvas-design 的分工

在这条 skill 里，建议这样分工：

- `frontend-design`：幻灯片结构、栅格、标题系统、信息层级、组件式布局
- `canvas-design`：封面图、章节页海报、概念视觉、静态纹理背景

推荐做法：

1. 先用 `frontend-design` 确立整套幻灯片的结构和版式
2. 再挑 1-3 个关键页面，用 `canvas-design` 生成单张高质量静态 PNG
3. 把 PNG 作为 HTML 页面的一部分或背景图引入

## FFmpeg 安装

**Windows**:

```bash
scoop install ffmpeg
```

**macOS**:

```bash
brew install ffmpeg
```

**Linux**:

```bash
sudo apt install ffmpeg
```

> ffmpeg 安装后同时包含 `ffprobe`，`generate_audio.py` 和 `verify_video.py` 都依赖它做时长和规格校验。

## 视频质量自检

`verify_video.py` 会检测：

| 检测项 | 阈值 | 说明 |
|--------|------|------|
| 音画同步 | 偏差 > 0.5s = ERROR | 视频轨 vs 音频轨时长 |
| 音频码率 | < 10kbps = ERROR | 码率过低通常意味着静音 |
| 音频音量 | < -40dB = ERROR | 平均音量过低 |
| 长静音段 | > 5s = WARN | 可能是编码问题 |
| 字幕溢出 | SRT结束 > 音频+0.5s = ERROR | 字幕时间超出音频 |
| manifest 一致性 | 偏差 > 0.5s = WARN | 记录值 vs 实际值 |
| 分辨率 | 不匹配 = WARN | 默认期望 1920x1080 |
| 帧率 | 不匹配 = WARN | 默认期望 30fps |
| 编码 | 非 h264 / aac = WARN | 规格漂移 |

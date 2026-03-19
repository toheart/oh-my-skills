# 视频规格与参考

## 输出视频规格

| 参数 | 值 |
|------|-----|
| 分辨率 | 1920×1080 (16:9 横屏) |
| 帧率 | 30fps |
| 编码 | H.264 (libx264) |
| 音频编码 | AAC 128kbps |
| 像素格式 | yuv420p |
| 转场 | 默认无转场（concat 拼接），可选淡入淡出（`--transition 0.5`） |

## 字幕样式

```
FontName=Microsoft YaHei,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=25
```

- 字体: 微软雅黑（回退 Noto Sans CJK SC）
- 字号: 12（ASS force_style 值，在 1920×1080 上大小适中）
- 颜色: 白色，黑色描边 2px
- 位置: 底部居中，距底 25px

> **注意**: FontSize=20 在 1920×1080 视频中偏大，推荐 12。

## 为什么默认不使用转场

xfade 转场在 fade 期间会混合相邻两个片段的视频帧。
由于字幕是预先烧录在每个片段中的，转场期间会出现两页字幕同时显示的问题。
因此默认使用 concat demuxer 简单拼接（`--transition 0`）。

如果确实需要转场效果，可以用 `--transition 0.5`，但需要接受转场期间字幕重叠的瑕疵。

## Edge-TTS 常用中文语音

| 语音 ID | 性别 | 风格 | 推荐度 |
|---------|------|------|--------|
| `zh-CN-YunjianNeural` | 男 | 沉稳播报，拼接噪音少 | ★★★ 推荐 |
| `zh-CN-YunxiNeural` | 男 | 自然叙述，偶有拼接卡顿 | ★★ |
| `zh-CN-XiaoxiaoNeural` | 女 | 温暖亲切，通用型 | ★★ |
| `zh-CN-XiaoyiNeural` | 女 | 活泼年轻，适合轻松内容 | ★★ |

> **推荐**: `YunjianNeural` + `--rate="-5%"` 效果最稳定，拼接噪音最少。

列出所有可用语音:

```bash
edge-tts --list-voices | grep zh-CN
```

## 语速调节

通过 `--rate` 参数调节，格式为百分比:

- `+10%` — 略快，适合信息密度高的内容
- `-5%` — **推荐**，略慢更自然，减少拼接噪音
- `-10%` — 偏慢，适合强调重点
- `+0%` — 默认语速

> **argparse 传递负值**：使用 `--rate="-5%"`（等号语法），否则 `-5%` 会被当成选项前缀报错。

## 音频管线

```
Edge-TTS → MP3(原始) → WAV(追加静音) → render_video 一次性编码 AAC
```

**为什么用 WAV 中间格式**：
MP3 是有损编码，每次编解码都会引入噪声和 encoder delay。
如果做 MP3→MP3→AAC 三次编解码，在 24kHz 低采样率下会出现明显的电流声和时间偏移。
改用 WAV（无损 PCM）作为中间格式，只在最终 render_video 时一次编码为 AAC，音质最好。

**后处理内容**：
- MP3 解码为 WAV（一次解码，无损保存）
- 尾部追加静音（默认 1.2 秒，`--pause` 控制）
- 不做额外的淡入淡出（避免引入不必要的 filter 处理）

## 视频片段精确时长

使用 `-t <duration>` 替代 `-shortest` 控制每个片段的时长。
`-shortest` 在 `-loop 1` 模式下因 GOP 对齐和编码器缓冲会导致视频轨比音频轨长 0.6-2 秒。
`-t` 直接用 manifest 中 ffprobe 测量的精确时长，音画对齐误差 < 0.05s。

## 讲稿 TTS 优化技巧

Edge-TTS 的断句和语气完全由标点符号控制。优化讲稿标点可显著改善"念稿感"：

| 技巧 | 示例 | 效果 |
|------|------|------|
| 句号断句 | "韩立负责调度。南宫婉管运营。" | 每句之间有明确停顿 |
| 省略号 | "答案是……SOUL.md。" | 制造 ~0.5s 的"思考"停顿 |
| 逗号前置 | "它的核心竞争力，到底在哪？" | 在重点词前短暂停顿 |
| 避免长逗号串 | 拆成多个短句 | 避免一口气念完 |

## Edge-TTS 字幕生成注意事项

edge-tts v7+ 的 `communicate.stream()` 会发送两种边界事件:
- `WordBoundary` — 词级别边界
- `SentenceBoundary` — 句级别边界

`SubMaker.feed()` 需要同时处理这两种类型：

```python
elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
    submaker.feed(chunk)
```

仅处理 `WordBoundary` 可能导致字幕内容不完整。

## FFmpeg 安装

**Windows** (推荐 scoop):
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

> ffmpeg 安装后同时包含 `ffprobe`，`generate_audio.py` 依赖 ffprobe 获取精确音频时长。

## HTML 幻灯片设计规范

### 设计理念
幻灯片设计应遵循 **frontend-design Skill** 的审美标准：
- 根据文章调性选择大胆的美学方向（不要默认"深紫+金色"）
- Typography: 可通过 Google Fonts CDN 引入有特色的字体
- Color: 主色+强调色，大胆配色，不要均匀平庸
- Composition: 不拘泥于居中对齐，可以不对称/重叠/对角线流
- Details: 纹理、图案、装饰元素营造氛围

### 技术约束
- body 尺寸: `width: 720pt; height: 405pt`
- 文字包裹在语义标签（`<p>`, `<h1>`-`<h6>`, `<ul>`, `<ol>`, `<li>`）
- body: `display: flex; flex-direction: column`
- 不使用 CSS gradient（html2pptx 不支持）

### html2pptx 限制
- 文本标签（h1-h6, p, li）**不支持** `border`、`box-shadow`，只有 `<div>` 支持
- 会校验内容是否超出 body 区域（含 0.5" 底部 margin），溢出报错
- 修复溢出：缩小 margin/padding/font-size，每次减 2-5pt

### 导出方式
使用 Playwright 截图导出 JPG（不依赖 LibreOffice/pdftoppm）:
- viewport: 960×540（720pt×405pt @96dpi）
- 截图后 ffmpeg 的 `scale=1920:1080` 负责放大到目标分辨率

## 视频质量自检

`verify_video.py` 在视频生成后自动运行，检测项：

| 检测项 | 阈值 | 说明 |
|--------|------|------|
| 音画同步 | 偏差 > 0.5s = ERROR | 视频轨 vs 音频轨时长 |
| 音频码率 | < 10kbps = ERROR | 码率过低通常意味着静音 |
| 音频音量 | < -40dB = ERROR | 平均音量过低 |
| 长静音段 | > 5s = WARN | 可能是编码问题 |
| 字幕溢出 | SRT结束 > 音频+0.5s = ERROR | 字幕时间超出音频 |
| manifest 一致性 | 偏差 > 0.5s = WARN | 记录值 vs 实际值 |
| 分辨率 | ≠ 1920x1080 = WARN | — |
| 编码 | ≠ h264/aac = WARN | — |

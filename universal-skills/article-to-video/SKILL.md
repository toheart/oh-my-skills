---
name: article-to-video
description: >-
  将文章自动转换为带配音和字幕的 PPT 讲解视频。支持 Markdown/纯文本输入，
  生成 1920x1080 横屏 MP4 视频，适合发布到抖音等平台。
  Use when 用户提到"文章转视频""生成讲解视频""PPT 视频""article to video"
  或提供文章要求制作视频时触发。
---

# Article to Video

> **依赖**: Node.js, Python 3.x, edge-tts, ffmpeg, Playwright, pptx Skill, frontend-design Skill

## 前置检查

```bash
pip install edge-tts
ffmpeg -version
npx playwright install chromium
```

确保 `edge-tts`、`ffmpeg` 和 Playwright Chromium 可用。若需安装 ffmpeg，参考 [references/video-specs.md](references/video-specs.md)。

pptx Skill 依赖 `pptxgenjs`（需全局安装）和 `html2pptx` 脚本。

## 工作流

### Step 1: 解析文章 → 生成大纲与讲稿

读取用户提供的文章文件或文本，提取结构化大纲并为每页生成口语化讲稿。

**输出格式**（JSON）:

```json
{
  "title": "文章标题",
  "slides": [
    {
      "page": 1,
      "heading": "页面标题",
      "bullets": ["要点1", "要点2"],
      "script": "这一页的口语化讲稿，控制在100-200字..."
    }
  ]
}
```

**要求**:
- 总页数控制在 8-15 页（含封面和结尾）
- 第 1 页为封面（标题 + 副标题），讲稿为简短开场白
- 最后 1 页为总结/感谢页，讲稿为简短收尾
- 每页讲稿 100-200 字，口语化、自然流畅，避免书面语
- bullets 控制在 3-5 条，每条不超过 15 字

**讲稿 TTS 优化技巧**（避免"念稿感"）:
- 用句号断句（而非逗号连成长句），让 TTS 在句号处自然停顿
- 在需要强调的地方前加逗号或省略号（`……`）制造"思考感"
- 避免一个讲稿段落超过 3 句不断句，否则 TTS 会一口气念完
- 适当在并列项之间用句号切分（如 "韩立负责调度。南宫婉管运营。"）
- 省略号 `……` 在 Edge-TTS 中会产生约 0.5 秒的自然停顿

将 JSON 保存为 `workspace/outline.json`。

**⏸ 确认点 1**: 将大纲和讲稿展示给用户，等待确认或修改后再继续。

### Step 2: 设计 PPT 幻灯片

基于 `outline.json`，**按照 frontend-design Skill 的设计理念**为每页设计独立 HTML 文件，保存到 `workspace/slides/` 目录。

**设计流程**:
1. 先阅读文章内容，理解文章的主题和调性
2. 按照 frontend-design Skill 的 Design Thinking 流程确定美学方向：
   - **Purpose**: 这是讲解视频的幻灯片，需要清晰表达内容
   - **Tone**: 根据文章调性选择风格（如技术文 → 极简/工业风，故事型 → 复古/杂志风，修仙主题 → 东方奢华风）
   - **Differentiation**: 每套幻灯片要有独特的视觉记忆点
3. 按照 frontend-design 的审美标准执行：
   - **Typography**: 选择有特色的字体搭配（通过 Google Fonts CDN 引入），避免平庸的 Arial/Inter
   - **Color & Theme**: 大胆的配色方案，主色+强调色，不要均匀分布
   - **Spatial Composition**: 不拘泥于居中对齐，可以用不对称、重叠、对角线流等
   - **Backgrounds & Visual Details**: 纹理、图案、装饰性元素营造氛围

**HTML 技术约束**（html2pptx 限制）:
- body 尺寸: `width: 720pt; height: 405pt`（16:9 比例）
- 所有文字必须包裹在语义标签中（`<p>`, `<h1>`-`<h6>`, `<ul>`, `<ol>`, `<li>`）
- 不使用 CSS gradient（html2pptx 不支持）
- 文本标签（h1-h6, p, li）上不能加 `border`、`box-shadow`，只有 `<div>` 支持
- body 使用 `display: flex; flex-direction: column`
- 内容区域使用 `margin: 24pt-30pt 40pt`，底部留出至少 36pt
- html2pptx 会校验溢出（含 0.5" 底部留白），溢出时减小 margin/padding/font-size

### Step 3: 生成 PPT 并导出预览图片

使用 pptx Skill 的 `html2pptx` 生成 PPTX:

```bash
cd workspace
NODE_PATH="<全局 node_modules 路径>" node build_pptx.js
```

使用 Playwright 导出 JPG 预览图:

```bash
NODE_PATH="<全局 node_modules 路径>" node export_slides.js
```

> viewport 设为 960×540（对应 720pt×405pt @96dpi），ffmpeg 合成时 scale 到 1920×1080。

**⏸ 确认点 2**: 将导出的幻灯片图片展示给用户确认设计。用户满意后才继续。
如果用户不满意，修改对应的 `slideXX.html` 后重新执行 build_pptx.js 和 export_slides.js。

### Step 4: 生成配音与字幕

```bash
python scripts/generate_audio.py workspace/outline.json workspace/audio/ \
  --voice zh-CN-YunjianNeural --rate="-5%" --pause 1.2
```

参数说明:
- `--voice` — TTS 语音，推荐 `zh-CN-YunjianNeural`（沉稳，拼接噪音少）
- `--rate` — 语速调节，`-5%` 略慢更自然（注意用 `=` 号传递负值）
- `--pause` — 每页音频末尾追加的静音间隔（秒），默认 1.2，制造转场呼吸感

输出:
- `workspace/audio/page_001.wav` ... `page_N.wav` — 每页配音（WAV 无损格式）
- `workspace/audio/page_001.srt` ... `page_N.srt` — 每页字幕
- `workspace/audio/manifest.json` — 每页音频时长信息

**音频管线**: Edge-TTS → MP3(原始) → WAV(追加静音) → render_video 一次性编码 AAC。
使用 WAV 中间格式，避免 MP3 多次编解码导致的电流声和时间偏移。

### Step 5: 合成视频

```bash
python scripts/render_video.py workspace/audio/manifest.json workspace/ --output workspace/output.mp4
```

脚本自动完成:
1. 为每页生成独立视频片段（图片 + 音频 + 烧录字幕）
2. 使用 `-t` 精确控制片段时长（匹配 manifest 中的 duration），避免音画偏移
3. 使用 concat demuxer 拼接所有片段（默认无转场，避免字幕重叠）
4. 输出 1920×1080 / 30fps / H.264 编码的 MP4

### Step 6: 视频质量自检

```bash
python scripts/verify_video.py workspace/output.mp4 workspace/audio/manifest.json
```

自动检测:
1. **音画同步**: 视频轨 vs 音频轨时长偏差（阈值 0.5s）
2. **音频质量**: 异常静音段检测、整体音量检测（过低=编码损坏）
3. **字幕同步**: SRT 结束时间 vs 音频时长偏差
4. **时长一致性**: manifest 记录 vs 实际音频时长
5. **规格校验**: 分辨率、帧率、编码格式

如果检测到 ERROR 级别问题，需要排查修复后重新生成。
如果只有 WARN，可以选择接受或修复。

**⏸ 确认点 3**: 自检通过后，告知用户视频已生成，路径为 `workspace/output.mp4`。

## 踩坑记录

### MP3 多次编解码导致电流声
**现象**: 音频中有滋啦的电流声、卡顿。
**根因**: Edge-TTS 输出 MP3 → 后处理重新编码 MP3 → render_video 再解码为 AAC，三次编解码在 24kHz 低采样率下引入明显噪声。
**解法**: 后处理输出 WAV（无损），只在最终合成时一次编码为 AAC。

### -shortest 导致音画不同步
**现象**: 视频轨比音频轨长 0.6-2 秒。
**根因**: `-loop 1` + `-shortest` 在 ffmpeg 中因 GOP 对齐和编码器缓冲不精确。
**解法**: 用 `-t <精确时长>` 替代 `-shortest`，时长取自 manifest 中的 duration（ffprobe 测量值）。

### 字幕与语音不同步
**根因**: SRT 时间戳来自原始 TTS 流，后处理（尤其是 MP3 encoder delay 累积）会引入偏移。
**解法**: WAV 中间格式消除了 MP3 encoder delay，SRT 时间戳直接对应原始 TTS 音频时间线。

### xfade 转场导致字幕重叠
**根因**: xfade 在 fade 期间混合相邻片段帧，已烧录的字幕会同时显示两页。
**解法**: 默认不转场（`--transition 0`），用尾部静音（`--pause 1.2`）制造呼吸感。

### edge-tts 字幕事件类型
edge-tts v7+ 同时发送 `WordBoundary` 和 `SentenceBoundary`，SubMaker 需同时处理两种类型。

### html2pptx 限制
- 文本标签不支持 `border`、`box-shadow`（只有 div 支持）
- 不支持 CSS gradient
- 会校验溢出（含 0.5" 底部 margin）

### TTS 念稿感
**解法**: 讲稿多用句号断句 + 省略号停顿 + `--pause 1.2` 尾部静音 + `--rate="-5%"` 降速。

## 参考文件

- [references/video-specs.md](references/video-specs.md) — 视频规格、TTS 语音、FFmpeg 安装指南

## 脚本一览

| 脚本 | 用途 |
|------|------|
| `scripts/generate_audio.py` | Edge-TTS 配音 + SRT 字幕，输出 WAV |
| `scripts/render_video.py` | FFmpeg 合成图片 + 音频 + 字幕为 MP4 |
| `scripts/verify_video.py` | 视频质量自检（音画/字幕同步、音频质量） |
| `workspace/build_pptx.js` | html2pptx 将 HTML 转为 PPTX |
| `workspace/export_slides.js` | Playwright 截图导出 JPG 预览图 |

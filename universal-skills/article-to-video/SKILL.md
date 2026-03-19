---
name: article-to-video
description: >-
  将文章自动转换为带配音和字幕的 PPT 讲解视频。支持 Markdown/纯文本输入，
  生成 1920x1080 横屏 MP4 视频，适合发布到抖音、视频号、B 站横屏课程等场景。
  Use when 用户提到"文章转视频""生成讲解视频""PPT 视频""article to video"
  或提供文章要求制作视频时触发。
---

# Article to Video

> **依赖**: Node.js, Python 3.x, edge-tts, ffmpeg, Playwright, pptx Skill, frontend-design Skill  
> **可选增强**: canvas-design Skill（封面 / 章节页氛围图 / 视觉母版）

其中 `frontend-design` 指的是 Codex 已安装的同名技能，推荐来源为：

- 上游仓库：`https://github.com/anthropics/skills/tree/main/skills/frontend-design`
- 安装位置：`$CODEX_HOME/skills/frontend-design/`

如果当前环境尚未安装，可执行：

```bash
python3 "$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --url https://github.com/anthropics/skills/tree/main/skills/frontend-design
```

其中 `canvas-design` 指的是 Codex 已安装的同名技能，推荐来源为：

- 安装位置：`$CODEX_HOME/skills/canvas-design/`

如果当前环境尚未安装，可从当前运行环境支持的技能来源安装同名 `canvas-design`，并确保最终落在 `$CODEX_HOME/skills/canvas-design/`。

## 前置检查

```bash
pip install edge-tts
ffmpeg -version
npx playwright install chromium
```

确保 `edge-tts`、`ffmpeg` 和 Playwright Chromium 可用。若需安装 ffmpeg，参考 [references/video-specs.md](references/video-specs.md)。

pptx Skill 依赖 `pptxgenjs`（需全局安装）和 `html2pptx` 脚本。

## 核心原则

1. **每次运行都创建独立目录**  
   所有输出物统一落到仓库根目录的 `workspace/article-to-video/<slug>-<timestamp>/`，避免覆盖历史产物。

2. **音色自动匹配，但配置可复现**  
   默认使用 `--voice auto`，由脚本根据文章内容自动匹配 voice / rate / pause，并把最终配置写入 `audio/manifest.json`。

3. **幻灯片必须预留底部安全区**  
   页面设计时要明确给视频字幕和视觉呼吸感留空间，不能把底部当作“能塞内容就塞内容”的区域；导出的 JPG 里必须能肉眼看到 footer 留白。

4. **默认保持静态画面，不开启镜头运动**  
   不要默认让 PPT 在视频层漂移；如确实需要动态，再显式传 `render_video.py --motion auto` 或具体 drift 模式。也不要先依赖复杂 CSS/JS 动画。

5. **frontend-design 负责布局与版式，canvas-design 负责高密度静态视觉资产**  
   `frontend-design` 用于页面结构、排版、界面风格；  
   `canvas-design` 适合封面图、章节页纹理、概念视觉海报等静态 PNG，再嵌入 HTML。

## 目录规范

初始化一次 run：

```bash
python universal-skills/article-to-video/scripts/init_run.py "文章标题"
```

默认会创建：

```text
workspace/article-to-video/<slug>-<timestamp>/
├── meta.json
├── outline.json
├── slides/
├── preview/
├── audio/
├── build/
├── output/
└── canvas/
```

- `slides/` — 幻灯片 HTML
- `preview/` — Playwright 导出的 `slide-001.jpg` 等预览图
- `audio/` — 每页配音、字幕、manifest
- `build/` — 中间产物和 `_clips`
- `output/` — 最终视频
- `canvas/` — canvas-design 导出的静态 PNG / PDF 素材

## 工作流

### Step 0: 初始化本次运行目录

```bash
python universal-skills/article-to-video/scripts/init_run.py "文章标题"
```

命令会输出本次 `RUN_DIR`。后续所有文件都写到这个目录，不再写死到单一 `workspace/` 根目录。

### Step 1: 解析文章 → 生成大纲与讲稿

读取用户提供的文章文件或文本，提取结构化大纲并为每页生成口语化讲稿。

**推荐输出格式**（JSON）:

```json
{
  "title": "文章标题",
  "theme": {
    "tone": "technical-editorial",
    "keywords": ["AI", "工程", "课程"]
  },
  "tts": {
    "profile": "technical"
  },
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
- 最后 1 页为总结 / 感谢页，讲稿为简短收尾
- 每页讲稿 100-200 字，口语化、自然流畅，避免书面语
- bullets 控制在 3-5 条，每条不超过 15 字
- `tts.profile` 可选，常用值：`technical` / `business` / `story` / `energetic`

**讲稿 TTS 优化技巧**（避免“念稿感”）:

- 用句号断句，让 TTS 在句号处自然停顿
- 在需要强调的地方前加逗号或省略号 `……` 制造“思考感”
- 避免一个讲稿段落超过 3 句不断句，否则 TTS 会一口气念完
- 适当在并列项之间用句号切分，例如“韩立负责调度。南宫婉管运营。”

将 JSON 保存为 `RUN_DIR/outline.json`。

**⏸ 确认点 1**: 将大纲和讲稿展示给用户，等待确认或修改后再继续。

### Step 2: 设计 PPT 幻灯片

基于 `outline.json`，**按照 frontend-design Skill 的设计理念** 为每页设计独立 HTML 文件，保存到 `RUN_DIR/slides/`。
这里引用的是 Codex 环境中的 `frontend-design` 同名技能，不要写死任何 Windows 或本机绝对路径。

如果封面、章节页、概念过渡页需要更强的视觉氛围，可以额外调用 **canvas-design Skill** 输出 PNG 到 `RUN_DIR/canvas/`，再在 HTML 中引用这些静态素材。

**frontend-design 与 canvas-design 的分工**:

- `frontend-design`: 页面骨架、信息层级、排版系统、栅格、组件式布局
- `canvas-design`: 单张高完成度静态视觉、纹理背景、概念母版、章节页海报

**设计流程**:

1. 先阅读文章内容，理解主题和调性
2. 确定视觉方向：
   - 技术 / 工程文 → 极简、编辑感、工业理性
   - 故事 / 文化文 → 杂志感、叙事感、层次留白
   - 商业 / 汇报文 → 克制、稳健、结构清晰
3. 决定哪些页只用 HTML 完成，哪些页需要 canvas 静态资产增强
4. 所有页面遵循统一的安全区系统

**HTML 技术约束**（html2pptx 限制）:

- body 尺寸：`width: 720pt; height: 405pt`
- 所有文字必须包裹在语义标签中：`<p>`, `<h1>`-`<h6>`, `<ul>`, `<ol>`, `<li>`
- 不使用 CSS gradient（html2pptx 不支持）
- 文本标签（h1-h6, p, li）上不能加 `border`、`box-shadow`，只有 `<div>` 支持
- body 使用 `display: flex; flex-direction: column`

**底部安全区硬规则**:

- 页面可视内容区底部必须预留至少 `56pt`
- 导出的 JPG 中，底部要保留清晰可见的空白 footer 区，而不是只在代码里声明一个名义安全区
- 整体纵向重心要保持平衡，避免明显“上面重、下面轻”
- 推荐用明确的 `content-area + footer-safe` 两段式结构，而不是仅靠 `padding-bottom`
- 避免在高内容页使用 `justify-content: space-between` 把上下块硬撑满全高
- 用户最终观看的是“视频 + 字幕”，而不是裸 PPT 截图，所以底部必须给字幕和呼吸感让路

**推荐骨架**:

```html
<body>
  <main class="page-shell">
    <section class="content-area">
      <!-- 主内容 -->
    </section>
    <footer class="footer-safe">
      <!-- 页码 / 标签 / 空白安全区 -->
    </footer>
  </main>
</body>
```

### Step 3: 生成 PPT 并导出预览图片

使用 pptx Skill 的 `html2pptx` 生成 PPTX：

```bash
cd "$RUN_DIR"
NODE_PATH="<全局 node_modules 路径>" node build_pptx.js
```

使用 Playwright 导出 JPG 预览图到 `preview/`：

```bash
NODE_PATH="<全局 node_modules 路径>" node export_slides.js
```

建议导出脚本遵循：

- viewport 设为 `960×540`（对应 `720pt×405pt @96dpi`）
- 输出命名为 `preview/slide-001.jpg`
- ffmpeg 合成时再 scale 到 `1920×1080`

**⏸ 确认点 2**: 将导出的幻灯片图片展示给用户确认设计。用户满意后才继续。  
如果用户不满意，修改对应的 `slideXX.html` 后重新执行 build_pptx.js 和 export_slides.js。

### Step 4: 生成配音与字幕

```bash
python universal-skills/article-to-video/scripts/generate_audio.py \
  "$RUN_DIR/outline.json" \
  "$RUN_DIR/audio" \
  --voice auto
```

参数说明：

- `--voice auto` — 根据文章内容自动匹配 voice / rate / pause
- `--voice zh-CN-YunjianNeural` — 手动指定 voice
- `--rate` / `--volume` / `--pitch` / `--pause` — 手动覆盖 auto profile

输出：

- `RUN_DIR/audio/page_001.wav` ... `page_N.wav` — 每页配音（WAV 无损格式）
- `RUN_DIR/audio/page_001.srt` ... `page_N.srt` — 每页字幕
- `RUN_DIR/audio/manifest.json` — 每页音频时长信息 + 最终 TTS 配置

**音频选择建议**:

- 技术讲解 / 工程课程：优先稳重男声，略慢一点
- 商业表达 / 汇报：优先克制、清晰、节奏均衡
- 叙事 / 文化内容：优先更温和、更有停顿感的 voice
- 轻松内容：允许稍快、更轻盈的 voice

脚本内部会把最终选择写进 manifest，保证本次成片可复现。

### Step 5: 合成视频

```bash
python universal-skills/article-to-video/scripts/render_video.py \
  "$RUN_DIR/audio/manifest.json" \
  "$RUN_DIR" \
  --subtitle-margin-v 42
```

脚本自动完成：

1. 在 `preview/` 或根目录中查找 `slide-001.jpg` 等图片
2. 为每页生成独立视频片段（图片 + 音频 + 烧录字幕）
3. 默认保持静态画面，仅使用轻微入退场淡化，避免画面额外漂移
4. 使用 `-t` 精确控制片段时长（匹配 manifest 中的 duration），避免音画偏移
5. 默认无转场拼接，避免字幕重叠
6. 输出到 `RUN_DIR/output/final.mp4`

**如果需要动态，优先走视频层而不是复杂 HTML 动画**:

- 它稳定，不依赖复杂 HTML 动画
- 不会破坏 html2pptx 的兼容性
- 只有在页面确实需要时再开启，复杂度更可控

### Step 6: 视频质量自检

```bash
python universal-skills/article-to-video/scripts/verify_video.py \
  "$RUN_DIR/output/final.mp4" \
  "$RUN_DIR/audio/manifest.json"
```

自动检测：

1. **音画同步**: 视频轨 vs 音频轨时长偏差（阈值 0.5s）
2. **音频质量**: 异常静音段检测、整体音量检测
3. **字幕同步**: SRT 结束时间 vs 音频时长偏差
4. **时长一致性**: manifest 记录 vs 实际音频时长
5. **规格校验**: 分辨率、帧率、编码格式

如果检测到 ERROR 级别问题，需要排查修复后重新生成。  
如果只有 WARN，可以选择接受或修复。

**⏸ 确认点 3**: 自检通过后，告知用户视频已生成，路径为 `RUN_DIR/output/final.mp4`。

## 踩坑记录

### MP3 多次编解码导致电流声

**现象**: 音频中有滋啦的电流声、卡顿。  
**根因**: Edge-TTS 输出 MP3 → 后处理重新编码 MP3 → render_video 再解码为 AAC，三次编解码在 24kHz 低采样率下引入明显噪声。  
**解法**: 后处理输出 WAV（无损），只在最终合成时一次编码为 AAC。

### `-shortest` 导致音画不同步

**现象**: 视频轨比音频轨长 0.6-2 秒。  
**根因**: `-loop 1` + `-shortest` 在 ffmpeg 中因 GOP 对齐和编码器缓冲不精确。  
**解法**: 用 `-t <精确时长>` 替代 `-shortest`，时长取自 manifest 中的 duration（ffprobe 测量值）。

### 字幕与语音不同步

**根因**: SRT 时间戳来自原始 TTS 流，后处理（尤其是 MP3 encoder delay 累积）会引入偏移。  
**解法**: WAV 中间格式消除了 MP3 encoder delay，SRT 时间戳直接对应原始 TTS 音频时间线。

### xfade 转场导致字幕重叠

**根因**: xfade 在 fade 期间混合相邻片段帧，已烧录的字幕会同时显示两页。  
**解法**: 默认不转场（`--transition 0`），通过尾部静音制造呼吸感；只有在确实需要时再显式开启 `--motion auto`。

### 幻灯片底部没有呼吸感

**根因**: 页面只考虑了 PPT 截图本身，没有把视频字幕区当成硬安全区。  
**解法**: 设计时明确保留底部 `56pt+` 安全区，渲染时提高 `--subtitle-margin-v`，不要让内容顶满底部。

### html2pptx 限制

- 文本标签不支持 `border`、`box-shadow`（只有 div 支持）
- 不支持 CSS gradient
- 会校验溢出（含 0.5" 底部 margin）

## 参考文件

- [references/video-specs.md](references/video-specs.md) — 视频规格、TTS 语音、FFmpeg 安装指南

## 脚本一览

| 脚本 | 用途 |
|------|------|
| `scripts/init_run.py` | 初始化独立运行目录，避免覆盖历史产物 |
| `scripts/generate_audio.py` | Edge-TTS 配音 + SRT 字幕，支持 `--voice auto` |
| `scripts/render_video.py` | FFmpeg 合成图片 + 音频 + 字幕为 MP4，支持轻动态与更安全的字幕边距 |
| `scripts/verify_video.py` | 视频质量自检（音画/字幕同步、音频质量） |
| `RUN_DIR/build_pptx.js` | html2pptx 将 HTML 转为 PPTX |
| `RUN_DIR/export_slides.js` | Playwright 截图导出 JPG 预览图 |

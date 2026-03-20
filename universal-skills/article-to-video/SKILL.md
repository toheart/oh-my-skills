---
name: article-to-video
description: >-
  将文章自动转换为带配音和字幕的原生 PPT 讲解视频。支持 Markdown/纯文本输入，
  以 brief.json / outline.json / slide-spec.json 为真相源头，通过 pptx Skill
  生成 PPTX、导出图片，再合成为 1920x1080 横屏 MP4。Use when 用户提到
  "文章转视频""生成讲解视频""PPT 视频""article to video" 或提供文章要求制作视频时触发。
---

# Article to Video

> **前置依赖**: `pptx` Skill, `canvas-design` Skill, Node.js, Python 3.x, `edge-tts`, `ffmpeg`  
> **导图依赖**: Windows + Microsoft PowerPoint 优先；或 LibreOffice + `pdftoppm` 作为 fallback  
> **设计约束**: `canvas-design` 不是可选增强，而是必用设计技能；封面纹理、章节视觉、静态配图都必须先经由 `canvas-design` 产出

这个 skill 的主链路已经改成：

```text
article -> brief.json -> outline.json -> slide-spec.json
-> pptx Skill / PptxGenJS -> deck.pptx
-> 导出 slide-xxx.jpg
-> Edge-TTS 音频 / SRT
-> ffmpeg 合成视频
```

## 硬规则

1. **`slide-spec.json` 是视觉真相源头**
   不是 HTML，不是截图，不是浏览器预览。

2. **PPTX 是主视觉产物**
   视频画面来自 PPT 导出的图片，不来自网页截图。

3. **先理解文章，再说明如何制作**
   先出 `brief.json`，让用户确认你理解的是对的，再拆页。

4. **按章快改要依赖结构化源文件**
   快速修改某一章，优先编辑 `outline.json` 或 `slide-spec.json`，然后局部重导图片、局部重跑音频与视频。

5. **BGM 不自动配置**
   默认不自动选、下载、生成或混入 BGM。如需音乐，只在最后基于文章给出推荐，由用户自己决定是否采用。

## 先加载的上游 skill

这个 skill 依赖上游 `pptx` skill 和 `canvas-design` skill。

- 创建新 deck 时，走 `pptx` skill 的 **PptxGenJS** 路线
- 封面、章节页、静态纹理、概念配图必须先走 `canvas-design`
- 不要把 HTML 当成中间主格式
- 做视觉 QA 时，把 PPTX 导出成图片检查，而不是只读代码

如果当前环境没有 `pptxgenjs`，先安装：

```bash
npm install -g pptxgenjs
```

## 目录规范

先初始化一次独立 run：

```bash
python universal-skills/article-to-video/scripts/init_run.py "文章标题"
```

默认输出到：

```text
workspace/article-to-video/<slug>-<timestamp>/
├── brief.json
├── outline.json
├── slide-spec.json
├── meta.json
├── deck/
│   └── deck.pptx
├── images/
│   └── slide-001.jpg
├── audio/
│   ├── page_001.wav
│   ├── page_001.srt
│   └── manifest.json
├── build/
├── output/
├── canvas/
└── assets/
    └── bgm/
```

其中：

- `canvas/` 不是占位目录，而是必须落地的设计资产目录
- 封面纹理、章节视觉、概念配图都要先由 `canvas-design` 生成到 `canvas/`
- `slide-spec.json` 和最终 PPT 页面要引用这些已生成的静态资产，而不是临时跳过

## 真相源头

### 1. `brief.json`

先明确你理解了什么，以及你准备怎么做。

推荐结构：

```json
{
  "title": "文章标题",
  "article_understanding": {
    "core_message": "文章的真正主旨",
    "audience": "目标受众",
    "tone": "technical-editorial",
    "video_type": "explainer"
  },
  "production_plan": {
    "recommended_duration": "6-8 min",
    "chapter_count": 4,
    "visual_direction": "editorial paper",
    "tts_profile": "technical",
    "bgm_strategy": "recommend only, user applies manually"
  }
}
```

在继续之前，先把这份理解展示给用户确认。

### 2. `outline.json`

确认 brief 后，再写逐页结构与讲稿。

要求：

- 总页数通常 `8-15` 页
- 第 1 页为封面
- 最后 1 页为总结/收尾
- 每页都要有 `slide_id`、`chapter_id`、`heading`、`script`
- 每页讲稿保持口语化，适合 TTS 朗读

### 3. `slide-spec.json`

这是渲染层的唯一真相源头。

它负责定义：

- 页面模板 `template`
- 标题、摘要、要点、卡片内容
- footer 安全区
- 主题色、字体、导出尺寸

`outline.json` 变更后，用脚本生成或归一化：

```bash
python universal-skills/article-to-video/scripts/build_slide_spec.py outline.json slide-spec.json
```

如果用户要精修某几页，也可以直接手改 `slide-spec.json`。

## 默认工作流

### Step 0: 初始化 run

```bash
python universal-skills/article-to-video/scripts/init_run.py "文章标题"
```

### Step 1: 先理解文章，再说明你打算怎么做

输出 `brief.json`，至少说明：

- 这篇文章的核心判断是什么
- 目标受众是谁
- 更像课程讲解、观点解读还是故事复盘
- 打算拆成几章，每章承担什么功能
- 视觉风格、配音风格、是否需要给出 BGM 推荐

### Step 2: 生成 `outline.json`

把文章拆成页，并为每页生成讲稿。

### Step 3: 先用 `canvas-design` 生成静态视觉资产

在构建 `slide-spec.json` 之前，必须先确定并产出本次视频需要的静态设计资产，至少包括：

- 封面背景或封面纹理
- 章节页视觉母版
- 概念型页面需要的静态配图或纹理

这些资产统一输出到 `canvas/`，再进入后续排版。

### Step 4: 构建 `slide-spec.json`

```bash
python universal-skills/article-to-video/scripts/build_slide_spec.py outline.json slide-spec.json
```

构建 `slide-spec.json` 时，要把 `canvas/` 中已经生成的静态资产视为正式输入，而不是可有可无的装饰层。

### Step 5: 渲染原生 PPTX

```bash
python universal-skills/article-to-video/scripts/render_pptx.py slide-spec.json deck/deck.pptx
```

这里必须遵循 `pptx` skill 的 from-scratch 路线，也就是 PptxGenJS。

### Step 6: 从 PPTX 导出图片

```bash
python universal-skills/article-to-video/scripts/export_pptx_images.py \
  deck/deck.pptx images --source-json slide-spec.json
```

局部导出某几页：

```bash
python universal-skills/article-to-video/scripts/export_pptx_images.py \
  deck/deck.pptx images --pages 3,5-7
```

按章导出：

```bash
python universal-skills/article-to-video/scripts/export_pptx_images.py \
  deck/deck.pptx images --source-json slide-spec.json --chapter methods
```

### Step 7: 生成音频和字幕

```bash
python universal-skills/article-to-video/scripts/generate_audio.py \
  slide-spec.json audio --voice auto
```

局部重跑：

```bash
python universal-skills/article-to-video/scripts/generate_audio.py \
  slide-spec.json audio --chapter methods
```

### Step 8: 合成视频

```bash
python universal-skills/article-to-video/scripts/render_video.py \
  audio/manifest.json . --output output/final.mp4
```

局部重做时：

```bash
python universal-skills/article-to-video/scripts/render_video.py \
  audio/manifest.json . --chapter methods --output output/final.mp4
```

`render_video.py` 会复用 `build/_clips/` 中未改动页面的缓存片段。

### Step 9: 做结果校验

```bash
python universal-skills/article-to-video/scripts/verify_video.py \
  output/final.mp4 audio/manifest.json
```

视觉层要直接检查 `images/slide-xxx.jpg`。

## 如何快速修改某一章

推荐顺序：

1. 改内容逻辑：编辑 `outline.json`
2. 改版式或页面结构：编辑 `slide-spec.json`
3. 重建 deck：

```bash
python universal-skills/article-to-video/scripts/render_pptx.py slide-spec.json deck/deck.pptx
```

4. 只重导这一章的图片：

```bash
python universal-skills/article-to-video/scripts/export_pptx_images.py \
  deck/deck.pptx images --source-json slide-spec.json --chapter methods
```

5. 只重跑这一章的音频：

```bash
python universal-skills/article-to-video/scripts/generate_audio.py \
  slide-spec.json audio --chapter methods
```

6. 只重拼这一章对应片段：

```bash
python universal-skills/article-to-video/scripts/render_video.py \
  audio/manifest.json . --chapter methods --output output/final.mp4
```

## BGM 策略

默认不在 skill 内自动配置 BGM。

如果用户没有提供音乐文件：

- 不要自动下载或生成 BGM
- 不要在默认视频里写入全局配乐
- 在最终交付说明里，根据文章内容提供 3 到 5 条在线 BGM 推荐
- 推荐内容应包含：曲风方向、来源网站、搜索关键词或具体曲目名

如果用户自己提供了 BGM 文件并明确要求混入，才使用渲染脚本中的 BGM 参数。

## 模板建议

第一版控制在少量稳定模板：

- `cover`
- `headline-bullets`
- `three-up`
- `four-up`
- `comparison`
- `closing`

不要为了“看起来灵活”把模板做得过多；可维护性比花哨更重要。

这些模板都默认建立在 `canvas-design` 已经产出静态底图、纹理或概念配图的前提上，而不是先做一版纯文字 PPT 再考虑补视觉。

## QA 原则

1. 不要只看 JSON，要看导出的 JPG
2. 优先检查 footer 安全区、标题换行、卡片溢出、左右对齐
3. 改某一章后，至少重新检查这一章所有导出图
4. 只在图片确认没问题后，再继续音频与视频合成

更详细的视频规格、BGM 建议、局部重做建议见：

- [references/video-specs.md](references/video-specs.md)

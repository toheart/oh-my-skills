# 视频规格与执行细节

## 输出规格

| 参数 | 值 |
|------|-----|
| 分辨率 | `1920x1080` |
| 帧率 | `30fps` |
| 视频编码 | `H.264 / libx264` |
| 音频编码 | `AAC 128kbps` |
| 像素格式 | `yuv420p` |
| 画面默认 | 静态 |
| 转场默认 | `0`，避免字幕重叠 |

## 目录约定

```text
workspace/article-to-video/<slug>-<timestamp>/
├── brief.json
├── outline.json
├── slide-spec.json
├── deck/
├── images/
├── audio/
├── build/
├── output/
└── assets/bgm/
```

说明：

- `deck/` 放原生 PPTX
- `images/` 放从 PPTX 导出的 `slide-001.jpg`
- `audio/manifest.json` 是视频合成的音频真相源头
- `build/_clips/` 用于局部重做时复用片段

## 为什么不用 HTML 当主链路

HTML 预览的问题不在于“能不能做”，而在于它不够确定：

- 浏览器截图与最终 PPT 的版式不一定一致
- footer、安全区、字体回退容易飘
- 修一页时很难知道到底是 HTML 问题、浏览器问题还是截图问题

现在的稳定路径是：

```text
slide-spec.json -> deck.pptx -> slide images -> video
```

## `brief.json` 应该回答的问题

在正式拆页前，先让用户看到这三类信息：

1. 你如何理解这篇文章
2. 你准备把它拍成什么类型的视频
3. 你打算如何拆章、如何配音、是否需要最后附 BGM 推荐

这一步是为了先对齐“理解”和“制作思路”，不是为了多一个文件。

## `slide-spec.json` 里最重要的字段

推荐至少保证这些字段稳定：

```json
{
  "kind": "slide-spec",
  "theme": {
    "palette": {},
    "font": {}
  },
  "render": {
    "width": 1920,
    "height": 1080,
    "footer_safe_height": 156
  },
  "pages": [
    {
      "page": 1,
      "slide_id": "cover",
      "chapter_id": "intro",
      "template": "cover",
      "heading": "标题",
      "summary": "摘要",
      "bullets": ["要点1", "要点2"],
      "script": "讲稿",
      "footer": {
        "left": "INTRO / COVER",
        "right": "01",
        "safe_height": 156
      }
    }
  ]
}
```

## 底部安全区

底部安全区是硬规则，不是软建议。

推荐值：

- `footer_safe_height = 156px`
- 字幕 `MarginV = 42`

检查方法：

- 导出的 `images/slide-xxx.jpg` 中，底部应有明显留白
- footer 文字不能和正文发生视觉争抢
- 字幕叠上去以后，底部仍然要有呼吸感

## BGM 建议

默认不在 skill 中自动配置 BGM。

更推荐的做法是：

- 先完成无 BGM 的讲解视频主版本
- 在最终说明里根据文章气质给出 3 到 5 条 BGM 推荐
- 由用户自己试听、挑选并决定是否后续混入

推荐列表应尽量包含：

- 曲风方向
- 来源网站
- 搜索关键词或曲目名
- 为什么适合这篇文章

## 局部重做建议

改某一章时，不要整条链重跑。

推荐操作：

1. 改 `outline.json` 或 `slide-spec.json`
2. 全量重建 `deck.pptx`
3. 用 `export_pptx_images.py --chapter xxx` 只重导该章图片
4. 用 `generate_audio.py --chapter xxx` 只重跑该章音频
5. 用 `render_video.py --chapter xxx` 只重拼相关片段

这样能最大限度利用：

- `images/` 中未改的图片
- `audio/manifest.json` 中未改的音频元数据
- `build/_clips/` 中未改的缓存片段

## 默认命令

### 构建 slide spec

```bash
python scripts/build_slide_spec.py outline.json slide-spec.json
```

### 渲染 PPT

```bash
python scripts/render_pptx.py slide-spec.json deck/deck.pptx
```

### 导出图片

```bash
python scripts/export_pptx_images.py deck/deck.pptx images --source-json slide-spec.json
```

### 只导出某一章

```bash
python scripts/export_pptx_images.py deck/deck.pptx images \
  --source-json slide-spec.json --chapter methods
```

### 生成音频

```bash
python scripts/generate_audio.py slide-spec.json audio --voice auto
```

### 合成视频

```bash
python scripts/render_video.py audio/manifest.json . --output output/final.mp4
```

### 校验视频

```bash
python scripts/verify_video.py output/final.mp4 audio/manifest.json
```

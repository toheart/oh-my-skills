# Remotion Video Skill Design

## 1. 设计目标

为仓库补一条真正的 Remotion 视频生产链路，用于把结构化的视频脚本、镜头规划和素材约束，稳定地渲染成可复用的模板化视频。

这份设计稿同时回答两个问题：

1. `remotion-video` skill 应该做什么，不应该做什么
2. 当用户给一份文章、观点或长文本时，"阅读理解 -> 提取中心思想 -> 生成视频脚本 -> 输出给 Remotion" 这段能力，应该单独做 skill，还是内化到 `remotion-video`

## 2. 结论先行

推荐采用"双层能力 + 单一用户入口"：

- 将 `remotion-video` 定位为渲染与模板编排 skill
- 将"文章理解、中心思想提炼、脚本生成、视觉意图生成"独立成上游 skill
- 对用户体验保持一个入口：用户仍然可以直接说"把这篇文章做成视频"
- 在实现层面通过结构化中间产物解耦，而不是依赖模糊的自由文本视频 prompt

简化说：

- `remotion-video` 负责"怎么把已经定义好的视频做出来"
- 上游内容 skill 负责"这支视频到底应该讲什么、怎么讲、每一段画面应该表达什么"

## 3. 为什么不建议把一切都塞进 remotion-video

如果把文章理解、脚本生成、视觉 prompt、Remotion 组件选择、素材落地、最终渲染全部塞进一个 skill，会出现四个问题：

1. 评估困难
   同一个 skill 同时负责内容理解和渲染，最后生成效果不好时，很难判断问题出在中心思想提取、脚本结构、视觉构思，还是 Remotion 模板本身。

2. 复用性差
   文章理解这一步不只服务 Remotion，也可能服务 PPT 视频、播客脚本、图文摘要、短视频分镜。把它绑死在 Remotion 里，后续扩展会受限。

3. Prompt 漂移严重
   用户现在感受到的"给不出合理的视频 prompt"，本质不是 prompt 写得不够长，而是缺少中间语义层。模型直接从文章跳到"给一段视频描述"，中间没有被约束，结果就容易泛化成空泛的视觉语言。

4. Skill 维护成本高
   Remotion 版本、模板、组件、渲染参数会变；内容理解和视觉脚本方法论也会变。把两条变化曲线绑在一起，会让 skill 很快变重。

## 4. 推荐的总体架构

```text
Article / Viewpoint / Notes
  -> article-to-storyboard
  -> video-brief.json / storyboard.json
  -> remotion-video
  -> final.mp4
```

### 4.1 上游 skill: article-to-storyboard

建议新增一个上游 skill，名字可以是以下任一方案：

- `article-to-storyboard`
- `story-driven-video-script`
- `longform-to-video-brief`

推荐首选：`article-to-storyboard`

它的职责：

- 阅读文章、观点、访谈、长文本
- 提取中心论点、目标受众、叙事主线、论证结构
- 把文章拆成适合视频表达的段落节拍
- 生成旁白脚本、镜头目标、屏幕文案、视觉约束
- 输出结构化 JSON，交给 `remotion-video`

它不负责：

- 最终视频渲染
- Remotion 工程细节
- 编码参数和导出

### 4.2 下游 skill: remotion-video

`remotion-video` 的职责：

- 接收结构化 storyboard / video brief
- 选择或生成 Remotion composition
- 将旁白、字幕、图片、图标、色板、动效映射到组件树
- 调用 Remotion SSR 渲染流程输出视频
- 验证最终分辨率、时长、音频、字幕和导出结果

它不负责：

- 从长文章里猜中心思想
- 直接从开放式文本生成模糊"视频 prompt"
- 代替上游完成内容策划

### 4.3 用户入口层

从用户视角，可以保留一个更自然的入口：

- `article-to-video-v2`

这个 skill 负责 orchestration：

1. 如果输入是文章或观点
   先调用上游内容流程，生成 `storyboard.json`
2. 再将 `storyboard.json` 交给 `remotion-video`
3. 返回可预览版本和最终渲染结果

这样用户仍然只需要说一句话，但内部能力是分层的。

## 5. 对现有 article-to-video skill 的判断

现有 [`universal-skills/article-to-video`](../universal-skills/article-to-video/SKILL.md) 更适合定位成：

- "文章转讲解型 PPT 视频"
- "静态页面 + TTS + 字幕 + FFmpeg 合成"

不建议直接在它上面继续堆出 Remotion 能力，原因有三点：

1. 现有心智模型是"幻灯片讲解视频"
2. 技术管线是 Playwright 截图和 FFmpeg，而不是 React composition
3. 它当前的文档和脚本假设"画面偏静态、字幕安全区优先、复杂动态尽量少"

更合理的路径是：

- 保留 `article-to-video`，继续服务 PPT/课程讲解类场景
- 新增 `article-to-storyboard`
- 新增 `remotion-video`
- 后续视需要增加一个编排层 skill 或者直接升级 `article-to-video` 为包装入口

## 6. 你现在遇到的核心问题

你提到：

> 我无法正确地给出合理的视频 prompt，让它生成更加符合文章的视频。

这个问题建议不要继续用"写更好的视频 prompt"来解决，而是改成"输出更好的结构化 storyboard"。

真正缺的是一个中间语义层，而不是一个更花哨的 prompt。

### 6.1 为什么自由文本视频 prompt 容易失真

当输入是长文章而输出是一段自由文本视频描述时，模型通常会出现这些问题：

- 只抓住话题，不抓住论证
- 视觉上很热闹，但和文章真正重点无关
- 容易滑向通用 AI 风格意象，比如城市、代码雨、抽象脑图、科技光效
- 无法说明"这段画面为什么对应这段文章"

### 6.2 替代方案: 结构化视频脚本

把中间产物从"一段 prompt"改成"每段视频的语义合同"：

```json
{
  "title": "为什么多数 AI 产品死在工作流而不是模型上",
  "core_thesis": "AI 产品成败的关键通常不在模型本身，而在于是否嵌入真实工作流。",
  "audience": "做 AI 产品和自动化工具的团队",
  "tone": "sharp, editorial, product-thinking",
  "target_duration_sec": 90,
  "scenes": [
    {
      "scene_id": "s01",
      "purpose": "开场提出主张",
      "source_refs": ["p1", "p2"],
      "narration": "大多数 AI 产品并不是输在模型不够强，而是输在没有进入真实工作流。",
      "on_screen_text": "The model is not the workflow.",
      "visual_role": "thesis",
      "visual_type": "editorial-kinetic-typography",
      "visual_prompt": "A restrained editorial composition showing task flow, review loops, and handoff friction instead of generic AI imagery.",
      "avoid": [
        "generic robot",
        "floating brain",
        "random code rain"
      ],
      "motion_intent": "measured reveal, no flashy transition"
    }
  ]
}
```

这个结构比一句"做一个符合文章的视频"更稳定，也更适合 Remotion 消费。

## 7. 上游内容 skill 的推荐工作流

`article-to-storyboard` 建议固定成 5 个阶段：

### Phase 1: 阅读与抽取

输入：

- 文章
- 观点清单
- 会议纪要
- 笔记草稿

输出：

- 标题
- 核心论点
- 目标受众
- 文章结构
- 关键事实/例子/比喻

### Phase 2: 压缩成视频主线

把原文从"阅读结构"改写为"观看结构"：

- 开场钩子
- 主张
- 展开 1
- 展开 2
- 反例或张力
- 收束

### Phase 3: 生成逐段视频脚本

每段至少生成这些字段：

- `purpose`
- `narration`
- `on_screen_text`
- `source_refs`
- `visual_role`
- `visual_type`
- `motion_intent`

### Phase 4: 生成视觉约束

这一步是解决"视频不符合文章"的关键。每段必须显式写出：

- 允许出现什么
- 不允许出现什么
- 画面是 literal 还是 metaphor
- 如果是 metaphor，它要表达哪一层抽象关系

### Phase 5: 产出 storyboard.json

最终输出统一 schema，作为 `remotion-video` 的输入契约。

## 8. remotion-video skill 的设计边界

## 8.1 触发场景

以下场景应触发 `remotion-video`：

- 用户要求用 Remotion 生成视频
- 用户已经有旁白、分镜、镜头脚本，希望渲染成视频
- 用户给出 `storyboard.json`、`video-brief.json` 或类似结构化脚本
- 用户希望修改现有 Remotion 视频模板
- 用户需要服务端渲染视频、批量渲染多条视频、参数化出片

以下场景不应由它单独承担：

- 单纯让模型阅读长文并总结观点
- 只想做 PPT 讲解视频且不需要 Remotion
- 只想要一个视频文案，不需要渲染

## 8.2 输入契约

建议 `remotion-video` 的主输入不是自由文本，而是以下任一形式：

1. `storyboard.json`
2. `video-brief.json`
3. 用户直接给出足够结构化的镜头列表，skill 先转成标准 schema

最小输入 schema 建议：

```json
{
  "meta": {
    "title": "string",
    "aspect_ratio": "16:9",
    "fps": 30,
    "duration_sec": 90,
    "theme": "editorial-tech"
  },
  "global_style": {
    "visual_language": "editorial motion graphics",
    "color_mood": "warm neutral",
    "typography": "clean sans + condensed display",
    "pace": "measured"
  },
  "audio": {
    "voiceover_path": "optional",
    "music_path": "optional, user-supplied only",
    "subtitle_mode": "embedded|none|external"
  },
  "scenes": [
    {
      "id": "s01",
      "start_sec": 0,
      "duration_sec": 8,
      "narration": "string",
      "on_screen_text": ["string"],
      "visual_type": "kinetic-type|diagram|image-led|quote|timeline",
      "asset_refs": [],
      "visual_prompt": "string",
      "avoid": [],
      "motion_intent": "string"
    }
  ]
}
```

## 8.3 输出物

`remotion-video` 完成后，至少应输出：

- `storyboard.normalized.json`
- `render-config.json`
- Remotion project files
- `output/final.mp4`
- 可选 `output/poster.jpg`
- 可选 `output/subtitles.srt`
- 可选 `bgm-recommendations.md`

## 9. remotion-video skill 的建议目录

```text
universal-skills/remotion-video/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── remotion-ssr.md
│   ├── storyboard-schema.md
│   ├── template-system.md
│   └── visual-language.md
├── scripts/
│   ├── init_project.js
│   ├── normalize_storyboard.py
│   ├── render_video.ts
│   ├── validate_storyboard.py
│   └── verify_output.py
└── assets/
    └── starter-template/
```

### 9.1 关键资源说明

- `references/remotion-ssr.md`
  说明 Remotion 的 SSR 工作流：bundle、select composition、renderMedia

- `references/storyboard-schema.md`
  定义统一输入 schema、字段含义、每类 `visual_type` 的用法

- `references/template-system.md`
  描述哪些 composition 适合哪些视频类型，比如 editorial、explainer、quote-led、timeline

- `references/visual-language.md`
  解释如何把 `visual_prompt` 转成可执行的视觉约束，而不是空泛审美词

- `scripts/normalize_storyboard.py`
  把用户输入、上游 JSON、旧格式脚本统一为标准 schema

- `scripts/render_video.ts`
  真正调用 Remotion SSR 输出视频

- `scripts/verify_output.py`
  做分辨率、时长、字幕、音轨、静音段、自检

## 10. 推荐的 Remotion 组件体系

不要让 skill 每次都临时生成完全不同的 Remotion 项目。更稳定的方式是维护一个模板化组件库：

- `TitleCard`
- `KineticStatement`
- `QuoteScene`
- `DiagramScene`
- `ImageScene`
- `TimelineScene`
- `CalloutList`
- `ClosingScene`

然后把 storyboard 中的 `visual_type` 映射到组件：

| visual_type | remotion component |
|---|---|
| `kinetic-type` | `KineticStatement` |
| `quote` | `QuoteScene` |
| `diagram` | `DiagramScene` |
| `image-led` | `ImageScene` |
| `timeline` | `TimelineScene` |
| `summary-list` | `CalloutList` |

这样好处是：

- 可复用
- 易控风格
- 易做批量渲染
- 更容易调试到底是脚本问题还是模板问题

## 11. 对"文章理解能力"的最终建议

### 推荐方案

从内部实现上，拆成两个 skill。

从对外体验上，保留一个入口。

也就是说：

- 架构上分层
- 交互上统一

### 为什么这是最平衡的方案

如果只做一个 skill：

- 用户入口最简单
- 但内部质量很难稳定

如果做两个完全暴露给用户的 skill：

- 架构最清晰
- 但用户理解成本更高

因此最佳折中是：

1. 新建 `article-to-storyboard`
2. 新建 `remotion-video`
3. 后续按需增加 `article-to-video-v2` 作为编排入口

## 12. 如何让视频更"符合文章"

下面这些约束应该写进上游内容 skill，而不是靠用户临时发挥：

### 12.1 每段画面必须可追溯到原文

为每个 scene 增加：

- `source_refs`
- `interpretation_note`

要求模型说明：

- 这一段画面对应原文哪一段
- 它表达的是事实、观点、类比，还是情绪推进

### 12.2 先定 visual role，再写 visual prompt

不要直接生成画面描述。先选角色：

- `thesis`
- `evidence`
- `contrast`
- `process`
- `example`
- `summary`

然后再写视觉实现。

### 12.3 为每段显式写 avoid 列表

如果不写 `avoid`，模型很容易回到泛化意象。建议把这些常见项作为默认禁用：

- generic robot
- holographic brain
- random skyline
- unrelated code rain
- generic cyber grid
- empty inspirational stock footage

### 12.4 把抽象文章分成几类视频表达

不是所有段落都应该被做成"写实画面"。建议上游 skill 先分类：

- 事实信息 -> 图表 / 时间线 /关系图
- 观点判断 -> 动态排版 / 关键词对撞
- 案例叙述 -> 场景化 image-led 画面
- 抽象比喻 -> 节制的隐喻动画

### 12.5 生成脚本时就考虑镜头节奏

每段要给出：

- 建议时长
- 视觉复杂度
- 文字密度
- 是否需要停顿

这样 Remotion 渲染时不会只是在补画面，而是真正执行一个已经成形的节奏结构。

## 12.6 BGM 只做推荐，不做自动配置

后续默认策略建议固定为：

- skill 不自动下载、生成、挑选或混入 BGM
- 如果用户没有给音乐文件，render contract 中保持 `music_path` 为空
- 在最终交付里根据文章气质给出少量在线 BGM 推荐
- 用户自行试听、选择并手动决定是否后续接入

## 13. 建议的演进路线

### Phase A: 先做设计验证

- 确认 `storyboard.json` schema
- 确认 `remotion-video` 输入输出边界
- 选 2 到 3 种基础 composition

### Phase B: 做最小可用版本

- 支持一篇文章转 60 到 120 秒视频
- 只支持 3 到 4 类 `visual_type`
- 支持字幕、旁白、封面、结尾

### Phase C: 替换旧的模糊 prompt 工作流

- 把 `article-to-video` 中自由文本视频提示替换为结构化 storyboard
- 保留旧 PPT 管线作为 fallback

### Phase D: 做包装入口

- 增加 `article-to-video-v2`
- 自动判断走 PPT 管线还是 Remotion 管线

## 14. 初版 eval prompts

为了后续按 `skill-creator` 方法验证 skill，建议先准备这些测试任务：

1. "我有一篇 1800 字的 AI 产品文章，帮我做一条 90 秒横屏视频，风格克制、编辑感强，不要泛 AI 视觉。"
2. "把这段关于组织协作的观点整理成 6 段视频脚本，每段都要说明画面为什么对应原文。"
3. "我已经有 `storyboard.json` 和旁白音频，帮我用 Remotion 出一个 1080p MP4。"

## 15. 最终建议

不要再把"给出更好的视频 prompt"当成主解决方案。

真正应该做的是：

- 把文章理解能力单独固化成可评估的上游 skill
- 用结构化 storyboard 代替模糊视频 prompt
- 让 `remotion-video` 专注渲染、模板、组件和导出
- 通过包装入口保留用户体验上的简单性

如果后续开始实现，建议顺序是：

1. 先做 `article-to-storyboard` 的 schema 和 SKILL.md
2. 再做 `remotion-video` 的最小模板和渲染脚本
3. 最后决定是否把它们包成新的 `article-to-video-v2`

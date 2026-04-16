# Advanced Features

Read this reference when the video requires capabilities beyond the default template family.
Each feature has a trigger condition, implementation pattern, and required dependency.
Only install dependencies that the project actually needs.

## Feature Selection Heuristic

Evaluate these conditions against the storyboard before choosing features:

| Condition | Recommended Feature |
| --- | --- |
| Storyboard has `on_screen_text_anchors` | Narration-synced reveal (built-in) |
| More than 8 scenes with hard cuts | Scene transitions |
| Captions have word-level timestamps and user wants karaoke effect | Word-level subtitle highlighting |
| Storyboard references SVG diagrams, flowcharts, or process arrows | SVG path animation |
| Scene uses `image-led` with video assets instead of images | Dynamic video embedding |
| Target is social media short-form (< 60s) | Vertical layout + aggressive motion |
| Storyboard has Lottie JSON asset references | Lottie animation |
| Scene describes 3D product or spatial data | Three.js 3D scene |
| User wants web-based interactive preview before rendering | Player component |
| Batch rendering > 10 videos | Lambda / Cloud Run |

If none of these conditions match, do not add advanced features.
The default template family with spring animations is sufficient for most explainer videos.

## Scene Transitions

**When to use**: More than 8 scenes, or user explicitly requests smooth transitions.

**Package**: `@remotion/transitions`

**Install**:

```bash
npm install @remotion/transitions
```

**Implementation pattern**:

```tsx
import {linearTiming, TransitionSeries} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {slide} from '@remotion/transitions/slide';

// 在主 Composition 中用 TransitionSeries 替换 Sequence 数组
<TransitionSeries>
  {scenes.map((scene, i) => (
    <TransitionSeries.Sequence
      key={scene.id}
      durationInFrames={Math.round(scene.duration_sec * fps)}
    >
      {renderScene(scene)}
      {i < scenes.length - 1 && (
        <TransitionSeries.Transition
          presentation={fade()}
          timing={linearTiming({durationInFrames: 15})}
        />
      )}
    </TransitionSeries.Sequence>
  ))}
</TransitionSeries>
```

**Selection heuristic for transition type**:

- `fade()`: 同主题场景间的柔和过渡，最通用
- `slide({direction: 'from-right'})`: 时间线/流程类场景，暗示递进
- `wipe()`: 对比类场景，暗示切换视角
- `clockWipe()`: 仅用于强烈的节点转折

**Rules**:

- 同一视频不要混用超过 2 种转场类型
- 转场时长控制在 10-20 帧（0.3-0.7 秒）
- 开头和结尾场景用 fade，中间用 slide 或 fade

## Word-Level Subtitle Highlighting

**When to use**: User wants karaoke-style subtitles, or captions have word-level timestamps.

**Package**: `@remotion/captions` (optional, can be implemented with existing captions data)

**Implementation pattern** (using existing captions.json):

```tsx
const SubtitleBar: React.FC<{captions: Caption[]; fps: number}> = ({captions, fps}) => {
  const frame = useCurrentFrame();

  // 找到当前正在说的 caption
  const current = captions.find(c => {
    const start = Math.floor((c.start_ms / 1000) * fps);
    const end = Math.ceil((c.end_ms / 1000) * fps);
    return frame >= start && frame <= end;
  });

  if (!current) return null;

  // 计算当前 caption 内的进度
  const startFrame = Math.floor((current.start_ms / 1000) * fps);
  const endFrame = Math.ceil((current.end_ms / 1000) * fps);
  const progress = (frame - startFrame) / (endFrame - startFrame);

  return (
    <div style={{/* 字幕容器样式 */}}>
      <span style={{color: '#fff'}}>{current.text.slice(0, Math.floor(current.text.length * progress))}</span>
      <span style={{color: 'rgba(255,255,255,0.4)'}}>{current.text.slice(Math.floor(current.text.length * progress))}</span>
    </div>
  );
};
```

**Rules**:

- 逐词高亮的颜色对比度要足够，避免闪烁感
- 字幕区域与 on_screen_text 的 safe area 不要重叠

## SVG Path Animation

**When to use**: Flowcharts, process diagrams, connection lines between elements.

**Package**: `@remotion/paths`

**Install**:

```bash
npm install @remotion/paths
```

**Implementation pattern**:

```tsx
import {getLength, getPointAtLength, parsePath} from '@remotion/paths';

const AnimatedPath: React.FC<{d: string; color: string}> = ({d, color}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const path = parsePath(d);
  const length = getLength(path);

  const drawProgress = spring({
    fps,
    frame,
    config: {damping: 200, stiffness: 80, mass: 1},
  });

  return (
    <svg style={{position: 'absolute', inset: 0}}>
      <path
        d={d}
        stroke={color}
        strokeWidth={3}
        fill="none"
        strokeDasharray={length}
        strokeDashoffset={length * (1 - drawProgress)}
      />
    </svg>
  );
};
```

**Rules**:

- SVG path 数据应放在 storyboard 的 `asset_refs` 或单独的 SVG 文件中
- 描边动画持续时间应与场景 duration 的前 40-60% 匹配
- 不要在同一场景中同时运行超过 3 条路径动画

## Dynamic Video Embedding

**When to use**: Picture-in-picture, screen recordings, product demos.

**Component**: `<OffthreadVideo>` (built-in, no extra package needed)

**Implementation pattern**:

```tsx
import {OffthreadVideo} from 'remotion';

const VideoInsetScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const videoSrc = safeRelativeAsset(scene.asset_refs[0]);

  return (
    <FrameShell scene={scene}>
      <div style={{position: 'relative'}}>
        {videoSrc && (
          <OffthreadVideo
            src={videoSrc}
            style={{
              width: '60%',
              borderRadius: 24,
              boxShadow: '0 24px 80px rgba(0,0,0,0.3)',
            }}
          />
        )}
        {/* 叠加文字层 */}
      </div>
    </FrameShell>
  );
};
```

**Rules**:

- 使用 `<OffthreadVideo>` 而非 `<Video>`，前者在 SSR 渲染中更稳定
- 视频素材必须提前放到 public 目录或提供可访问的 URL
- 注意嵌入视频的音频：默认静音，除非用户明确要求混音

## Lottie Animation

**When to use**: Storyboard references `.json` Lottie files, or needs After Effects quality animations.

**Package**: `@remotion/lottie`

**Install**:

```bash
npm install @remotion/lottie lottie-web
```

**Implementation pattern**:

```tsx
import {Lottie, LottieAnimationData} from '@remotion/lottie';
import {useEffect, useState} from 'react';
import {staticFile} from 'remotion';

const LottieScene: React.FC<{src: string}> = ({src}) => {
  const [data, setData] = useState<LottieAnimationData | null>(null);

  useEffect(() => {
    fetch(staticFile(src))
      .then(r => r.json())
      .then(setData);
  }, [src]);

  if (!data) return null;

  return <Lottie animationData={data} style={{width: '100%', height: '100%'}} />;
};
```

**Rules**:

- Lottie JSON 文件放在 `public/` 目录
- 动画帧率应与视频 fps 匹配（通常 30fps）
- 文件体积建议 < 500KB，过大会影响渲染性能

## Three.js 3D Scene

**When to use**: Product visualization, 3D data charts, spatial explanations.

**Package**: `@remotion/three`

**Install**:

```bash
npm install @remotion/three @react-three/fiber three
```

**Rules**:

- 3D 场景渲染开销大，控制场景 polygon count
- 确保 Chrome headless 支持 WebGL（默认支持）
- 相机动画用 `useCurrentFrame()` 驱动，不要用 requestAnimationFrame

## Noise and Organic Textures

**When to use**: Background textures, particle effects, generative art backgrounds.

**Package**: `@remotion/noise`

**Install**:

```bash
npm install @remotion/noise
```

**Implementation pattern**:

```tsx
import {noise2D} from '@remotion/noise';

// 在 BackgroundWash 中添加噪声纹理
const noiseValue = noise2D('seed', x * 0.01, frame * 0.005);
```

**Rules**:

- 噪声仅用于背景层，不要干扰前景内容的可读性
- 频率和振幅要保守，避免视觉噪音

## Google Fonts

**When to use**: Need specific typography beyond system fonts.

**Package**: `@remotion/google-fonts`

**Install**:

```bash
npm install @remotion/google-fonts
```

**Implementation pattern**:

```tsx
import {loadFont} from '@remotion/google-fonts/NotoSansSC';

const {fontFamily} = loadFont();
// 在组件 style 中使用 fontFamily
```

**Rules**:

- 只加载实际使用的字重（`subsets` 和 `weights` 参数）
- 中文字体体积大，渲染时间会显著增加
- 优先使用系统字体，仅在品牌要求时切换

## Player (Web Preview)

**When to use**: User wants an interactive preview before committing to full render.

**Package**: `@remotion/player`

**Implementation pattern**: Create a simple HTML page that imports the Player component and loads the composition with storyboard props. This lets users scrub through the video, adjust timing, and verify content before the expensive SSR render.

**Rules**:

- Player 是开发/预览工具，不是最终交付物
- 不要在 Player 和 SSR render 之间引入不同的代码路径

## Lambda / Cloud Run (Serverless Rendering)

**When to use**: Batch rendering > 10 videos, or video duration > 30 minutes where local render is impractical.

**Packages**: `@remotion/lambda` (AWS) or `@remotion/cloudrun` (GCP)

**Rules**:

- 需要云平台账号和配置，不要在用户未确认前自动部署
- 本地 SSR 渲染是默认路径，云渲染是显式升级
- 参考 Remotion 官方文档配置 IAM 权限和区域

## Feature Combination Rules

- 不要同时添加超过 2 个高级特性，复杂度会急剧上升
- 转场 + 逐词字幕是最常见的组合，互不冲突
- 3D + Lottie 不要混用，选一个风格统一的方案
- 所有高级特性都应通过 storyboard props 控制，不要在组件内硬编码开关

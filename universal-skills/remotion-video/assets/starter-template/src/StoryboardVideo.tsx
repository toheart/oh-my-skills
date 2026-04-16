import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import type {OnScreenTextItem, StoryScene, StoryboardProps, VisualRole, VisualType} from './types';

function resolveOST(item: string | OnScreenTextItem): {text: string; appear_at_ms?: number} {
  if (typeof item === 'string') return {text: item};
  return {text: item.text, appear_at_ms: item.appear_at_ms};
}

function resolveOSTList(items: (string | OnScreenTextItem)[]): {text: string; appear_at_ms?: number}[] {
  return items.map(resolveOST);
}

type Palette = {
  base: string;
  overlay: string;
  accent: string;
  accentSoft: string;
  text: string;
  muted: string;
  panel: string;
  line: string;
};

const ROLE_PALETTES: Record<VisualRole, Palette> = {
  thesis: {
    base: '#0f172a',
    overlay: '#1d4ed8',
    accent: '#f97316',
    accentSoft: 'rgba(249, 115, 22, 0.18)',
    text: '#f8fafc',
    muted: 'rgba(248,250,252,0.76)',
    panel: 'rgba(15, 23, 42, 0.54)',
    line: 'rgba(248,250,252,0.14)',
  },
  evidence: {
    base: '#101d46',
    overlay: '#2563eb',
    accent: '#facc15',
    accentSoft: 'rgba(250, 204, 21, 0.18)',
    text: '#f8fafc',
    muted: 'rgba(248,250,252,0.76)',
    panel: 'rgba(14, 26, 57, 0.56)',
    line: 'rgba(248,250,252,0.14)',
  },
  contrast: {
    base: '#34132f',
    overlay: '#be123c',
    accent: '#fb7185',
    accentSoft: 'rgba(251, 113, 133, 0.18)',
    text: '#fff1f2',
    muted: 'rgba(255,241,242,0.8)',
    panel: 'rgba(52, 19, 47, 0.56)',
    line: 'rgba(255,241,242,0.14)',
  },
  process: {
    base: '#072c26',
    overlay: '#0f766e',
    accent: '#f59e0b',
    accentSoft: 'rgba(245, 158, 11, 0.18)',
    text: '#ecfeff',
    muted: 'rgba(236,254,255,0.78)',
    panel: 'rgba(7, 44, 38, 0.56)',
    line: 'rgba(236,254,255,0.14)',
  },
  example: {
    base: '#251f5f',
    overlay: '#5b5bd6',
    accent: '#fb7185',
    accentSoft: 'rgba(251, 113, 133, 0.16)',
    text: '#f5f3ff',
    muted: 'rgba(245,243,255,0.8)',
    panel: 'rgba(37, 31, 95, 0.56)',
    line: 'rgba(245,243,255,0.14)',
  },
  summary: {
    base: '#18181b',
    overlay: '#3f3f46',
    accent: '#f59e0b',
    accentSoft: 'rgba(245, 158, 11, 0.18)',
    text: '#fafafa',
    muted: 'rgba(250,250,250,0.78)',
    panel: 'rgba(24, 24, 27, 0.6)',
    line: 'rgba(250,250,250,0.13)',
  },
};

const DISPLAY_FONT =
  '"Bahnschrift SemiCondensed", "Arial Narrow", "Microsoft YaHei UI", sans-serif';
const BODY_FONT =
  '"Microsoft YaHei UI", "PingFang SC", "Noto Sans SC", sans-serif';

const safeRelativeAsset = (src?: string | null) => {
  if (!src) {
    return null;
  }

  if (/^https?:\/\//i.test(src)) {
    return src;
  }

  const normalized = src.replace(/\\/g, '/').replace(/^\.?\//, '');
  if (normalized.includes(':')) {
    return null;
  }

  return staticFile(normalized);
};

/**
 * 按语义完整的句子进行分割，优先保留完整句子而不是逐逗号打碎。
 * 第一轮按句号/问号/叹号/换行分；只有在分出的条数不够时才做二次拆分。
 */
const splitNarration = (text: string, maxItems: number) => {
  const sentences = text
    .split(/[。！？!?\n]+/)
    .map((s) => s.trim())
    .filter(Boolean);

  if (sentences.length === 0) return [];
  if (sentences.length >= maxItems) return sentences.slice(0, maxItems);

  const pieces: string[] = [];
  for (const sentence of sentences) {
    if (pieces.length >= maxItems) break;
    const sub = sentence
      .split(/[，、；;]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (sub.length <= 1 || pieces.length + 1 >= maxItems) {
      pieces.push(sentence);
    } else {
      for (const part of sub) {
        if (pieces.length >= maxItems) break;
        pieces.push(part);
      }
    }
  }
  return pieces.slice(0, maxItems);
};

type MotionPreset = {
  damping: number;
  stiffness: number;
  mass: number;
  riseDistance: number;
  exitFrames: number;
};

const MOTION_PRESETS: Record<VisualType, MotionPreset> = {
  'kinetic-type': {damping: 180, stiffness: 140, mass: 0.7, riseDistance: 56, exitFrames: 18},
  quote: {damping: 260, stiffness: 70, mass: 1.2, riseDistance: 32, exitFrames: 28},
  diagram: {damping: 200, stiffness: 100, mass: 0.9, riseDistance: 40, exitFrames: 20},
  'image-led': {damping: 220, stiffness: 90, mass: 1.0, riseDistance: 36, exitFrames: 22},
  timeline: {damping: 160, stiffness: 120, mass: 0.75, riseDistance: 44, exitFrames: 16},
  'summary-list': {damping: 240, stiffness: 80, mass: 1.1, riseDistance: 28, exitFrames: 24},
};

const DEFAULT_MOTION: MotionPreset = {
  damping: 200, stiffness: 110, mass: 0.8, riseDistance: 48, exitFrames: 20,
};

const useSceneMotion = (visualType?: VisualType) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const preset = (visualType && MOTION_PRESETS[visualType]) || DEFAULT_MOTION;

  const enter = spring({
    fps,
    frame,
    config: {
      damping: preset.damping,
      stiffness: preset.stiffness,
      mass: preset.mass,
    },
  });
  const exit = interpolate(
    frame,
    [durationInFrames - preset.exitFrames, durationInFrames],
    [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  return {
    frame,
    opacity: enter * exit,
    rise: interpolate(enter, [0, 1], [preset.riseDistance, 0]),
  };
};

/**
 * 为列表项目提供逐条交错入场动效。
 * 如果提供了 appear_at_ms（来自 align_anchors.py），则按精确时间触发；
 * 否则按等间隔 staggerMs 递增延迟。
 */
const useStaggeredItem = (index: number, staggerMs: number = 120, appearAtMs?: number) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const delayFrames = appearAtMs != null
    ? Math.round((appearAtMs / 1000) * fps)
    : Math.round((staggerMs * index) / 1000 * fps);
  const localFrame = Math.max(0, frame - delayFrames);

  const enter = spring({
    fps,
    frame: localFrame,
    config: {damping: 200, stiffness: 120, mass: 0.8},
  });

  return {
    opacity: enter,
    rise: interpolate(enter, [0, 1], [24, 0]),
  };
};

const BackgroundWash: React.FC<{palette: Palette; scene: StoryScene}> = ({palette, scene}) => {
  const {frame} = useSceneMotion(scene.visual_type);
  const drift = interpolate(frame, [0, 120], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'extend',
  });

  return (
    <>
      <AbsoluteFill
        style={{
          background: `
            radial-gradient(circle at ${18 + drift * 8}% 18%, ${palette.accentSoft} 0%, transparent 34%),
            radial-gradient(circle at ${82 - drift * 4}% 76%, rgba(255,255,255,0.08) 0%, transparent 28%),
            linear-gradient(135deg, ${palette.base} 0%, ${palette.overlay} 100%)
          `,
        }}
      />
      <AbsoluteFill
        style={{
          opacity: 0.16,
          backgroundImage: `
            linear-gradient(${palette.line} 1px, transparent 1px),
            linear-gradient(90deg, ${palette.line} 1px, transparent 1px)
          `,
          backgroundSize: '120px 120px',
          maskImage:
            'linear-gradient(180deg, transparent 0%, black 12%, black 88%, transparent 100%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          right: -30,
          top: 120,
          transform: 'rotate(90deg)',
          transformOrigin: 'top right',
          fontFamily: DISPLAY_FONT,
          fontSize: 132,
          letterSpacing: 6,
          color: 'rgba(255,255,255,0.05)',
          fontWeight: 700,
        }}
      >
        {scene.visual_role.toUpperCase()}
      </div>
    </>
  );
};

const FrameShell: React.FC<{scene: StoryScene; children: React.ReactNode}> = ({
  scene,
  children,
}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.thesis;
  const {width, height, durationInFrames} = useVideoConfig();
  const {opacity} = useSceneMotion(scene.visual_type);

  return (
    <AbsoluteFill style={{color: palette.text, fontFamily: BODY_FONT}}>
      <BackgroundWash palette={palette} scene={scene} />
      <AbsoluteFill style={{padding: width < height ? 56 : 76, opacity}}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: width < height ? 20 : 24,
            letterSpacing: 4,
            textTransform: 'uppercase',
            color: palette.muted,
          }}
        >
          <span>{scene.visual_role}</span>
          <span>{scene.id}</span>
        </div>
        <div
          style={{
            position: 'absolute',
            left: width < height ? 56 : 76,
            right: width < height ? 56 : 76,
            top: width < height ? 96 : 116,
            height: 1,
            background: palette.line,
          }}
        />
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
          }}
        >
          {children}
        </div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 24,
            fontSize: width < height ? 16 : 18,
            color: palette.muted,
          }}
        >
          <div style={{maxWidth: '72%', lineHeight: 1.4}}>
            {scene.interpretation_note || scene.purpose}
          </div>
          <div style={{display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'flex-end'}}>
            {scene.source_refs.slice(0, 4).map((ref) => (
              <span
                key={ref}
                style={{
                  padding: '8px 10px',
                  borderRadius: 999,
                  border: `1px solid ${palette.line}`,
                }}
              >
                {ref}
              </span>
            ))}
          </div>
        </div>
        <div
          style={{
            position: 'absolute',
            left: width < height ? 56 : 76,
            bottom: width < height ? 40 : 48,
            width: `${Math.max(12, Math.min(92, (durationInFrames / 450) * 100))}%`,
            height: 4,
            borderRadius: 999,
            background: `linear-gradient(90deg, ${palette.accent}, rgba(255,255,255,0.2))`,
          }}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const ThesisScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.thesis;
  const {width, height} = useVideoConfig();
  const {opacity, rise} = useSceneMotion('kinetic-type');
  const ostItems = resolveOSTList(scene.on_screen_text);
  const lines = ostItems.length > 0 ? ostItems : [{text: scene.purpose}];

  return (
    <FrameShell scene={scene}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 24,
          justifyContent: 'center',
          transform: `translateY(${rise}px)`,
        }}
      >
        {lines.map((item, index) => {
          const stagger = useStaggeredItem(index, 180, item.appear_at_ms);
          return (
            <div
              key={`${item.text}-${index}`}
              style={{
                padding: '24px 32px',
                borderRadius: 24,
                background: palette.panel,
                border: `1px solid ${palette.line}`,
                backdropFilter: 'blur(10px)',
                opacity: stagger.opacity,
                transform: `translateY(${stagger.rise}px)`,
              }}
            >
              <div
                style={{
                  fontFamily: index === 0 ? DISPLAY_FONT : BODY_FONT,
                  fontSize: index === 0 ? (width < height ? 48 : 64) : (width < height ? 28 : 36),
                  lineHeight: 1.2,
                  fontWeight: index === 0 ? 700 : 500,
                  letterSpacing: index === 0 ? -1 : 0,
                  color: index === 0 ? palette.text : palette.muted,
                }}
              >
                {item.text}
              </div>
            </div>
          );
        })}
      </div>
    </FrameShell>
  );
};

const DiagramScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.evidence;
  const {width, height} = useVideoConfig();
  const {opacity, rise} = useSceneMotion('diagram');
  const ostItems = resolveOSTList(scene.on_screen_text);
  const nodes = ostItems.length > 0 ? ostItems : [{text: scene.purpose}];

  return (
    <FrameShell scene={scene}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: width >= height ? '0.92fr 1.08fr' : '1fr',
          gap: 30,
          alignItems: 'center',
          transform: `translateY(${rise}px)`,
          opacity,
        }}
      >
        <div style={{display: 'flex', flexDirection: 'column', gap: 20}}>
          <div style={{fontSize: 18, letterSpacing: 3, textTransform: 'uppercase', color: palette.muted}}>
            System Logic
          </div>
          <div
            style={{
              fontFamily: DISPLAY_FONT,
              fontSize: width < height ? 58 : 86,
              lineHeight: 0.96,
              fontWeight: 700,
              maxWidth: '90%',
            }}
          >
            {nodes[0]?.text ?? scene.purpose}
          </div>
          <div
            style={{
              fontSize: width < height ? 23 : 30,
              lineHeight: 1.35,
              color: palette.muted,
              maxWidth: '86%',
            }}
          >
            {splitNarration(scene.narration, 2).join('。')}
          </div>
        </div>
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
          {nodes.map((node, index) => {
            const stagger = useStaggeredItem(index, 140, node.appear_at_ms);
            return (
              <div
                key={`${node.text}-${index}`}
                style={{
                  minHeight: 150,
                  padding: '22px 24px',
                  borderRadius: 28,
                  background: index === 0 ? palette.accentSoft : palette.panel,
                  border: `1px solid ${index === 0 ? palette.accent : palette.line}`,
                  boxShadow:
                    index === 0
                      ? `0 24px 70px ${palette.accentSoft}`
                      : '0 14px 40px rgba(0,0,0,0.18)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  opacity: stagger.opacity,
                  transform: `translateY(${stagger.rise}px)`,
                }}
              >
                <div
                  style={{
                    fontSize: 16,
                    letterSpacing: 2,
                    textTransform: 'uppercase',
                    color: palette.muted,
                  }}
                >
                  {index === 0 ? 'Core' : `Step 0${index}`}
                </div>
                <div style={{fontSize: width < height ? 26 : 32, lineHeight: 1.2, fontWeight: 600}}>
                  {node.text}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </FrameShell>
  );
};

const TimelineScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.process;
  const {width, height} = useVideoConfig();
  const {opacity, rise} = useSceneMotion('timeline');
  const ostItems = resolveOSTList(scene.on_screen_text);
  const beats = ostItems.length > 0 ? ostItems : splitNarration(scene.narration, 5).map(t => ({text: t, appear_at_ms: undefined}));

  return (
    <FrameShell scene={scene}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 28,
          justifyContent: 'center',
          opacity,
          transform: `translateY(${rise}px)`,
        }}
      >
        <div style={{display: 'flex', flexDirection: 'column', gap: 18}}>
          {beats.map((beat, index) => {
            const stagger = useStaggeredItem(index, 160, beat.appear_at_ms);
            return (
              <div
                key={`${beat.text}-${index}`}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '84px 1fr',
                  gap: 18,
                  alignItems: 'stretch',
                  opacity: stagger.opacity,
                  transform: `translateX(${interpolate(stagger.opacity, [0, 1], [-16, 0])}px)`,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: 20,
                    background: index === 0 ? palette.accent : palette.panel,
                    color: palette.text,
                    fontFamily: DISPLAY_FONT,
                    fontSize: 24,
                    fontWeight: 700,
                  }}
                >
                  0{index + 1}
                </div>
                <div
                  style={{
                    padding: '18px 22px',
                    borderRadius: 24,
                    border: `1px solid ${palette.line}`,
                    background: palette.panel,
                    fontSize: width < height ? 22 : 28,
                    lineHeight: 1.28,
                  }}
                >
                  {beat.text}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </FrameShell>
  );
};

const SummaryListScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.summary;
  const {width, height} = useVideoConfig();
  const {opacity, rise} = useSceneMotion('summary-list');
  const ostItems = resolveOSTList(scene.on_screen_text);
  const items = ostItems.length > 0 ? ostItems : splitNarration(scene.narration, 4).map(t => ({text: t, appear_at_ms: undefined}));

  return (
    <FrameShell scene={scene}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
          justifyContent: 'center',
          opacity,
          transform: `translateY(${rise}px)`,
        }}
      >
        <div style={{display: 'grid', gap: 16}}>
          {items.map((item, index) => {
            const stagger = useStaggeredItem(index, 130, item.appear_at_ms);
            return (
              <div
                key={`${item.text}-${index}`}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '90px 1fr',
                  gap: 18,
                  alignItems: 'center',
                  padding: '16px 18px',
                  borderRadius: 24,
                  background: palette.panel,
                  border: `1px solid ${palette.line}`,
                  opacity: stagger.opacity,
                  transform: `translateY(${stagger.rise}px)`,
                }}
              >
                <div
                  style={{
                    fontFamily: DISPLAY_FONT,
                    fontSize: 28,
                    textAlign: 'center',
                    color: palette.accent,
                  }}
                >
                  0{index + 1}
                </div>
                <div style={{fontSize: width < height ? 24 : 30, lineHeight: 1.22}}>{item.text}</div>
              </div>
            );
          })}
        </div>
      </div>
    </FrameShell>
  );
};

const QuoteScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.evidence;
  const {width, height} = useVideoConfig();
  const {opacity, rise} = useSceneMotion('quote');
  const ostItems = resolveOSTList(scene.on_screen_text);

  return (
    <FrameShell scene={scene}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 28,
          alignItems: 'center',
          textAlign: 'center',
          opacity,
          transform: `translateY(${rise}px)`,
        }}
      >
        <div
          style={{
            fontFamily: DISPLAY_FONT,
            fontSize: 180,
            lineHeight: 0.7,
            color: palette.accentSoft,
          }}
        >
          &ldquo;
        </div>
        {ostItems.map((item, index) => {
          const stagger = useStaggeredItem(index, 200, item.appear_at_ms);
          return (
            <div
              key={`${item.text}-${index}`}
              style={{
                fontFamily: index === 0 ? DISPLAY_FONT : BODY_FONT,
                fontSize: index === 0 ? (width < height ? 52 : 78) : (width < height ? 28 : 36),
                lineHeight: 1.1,
                fontWeight: index === 0 ? 700 : 400,
                maxWidth: '76%',
                color: index === 0 ? palette.text : palette.muted,
                opacity: stagger.opacity,
                transform: `translateY(${stagger.rise}px)`,
              }}
            >
              {item.text}
            </div>
          );
        })}
      </div>
    </FrameShell>
  );
};

const ImageLedScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.example;
  const {width, height} = useVideoConfig();
  const {opacity, rise} = useSceneMotion('image-led');
  const imageSrc = safeRelativeAsset(scene.asset_refs[0]);

  return (
    <FrameShell scene={scene}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: width >= height ? '1.05fr 0.95fr' : '1fr',
          gap: 28,
          alignItems: 'center',
          opacity,
          transform: `translateY(${rise}px)`,
        }}
      >
        <div
          style={{
            minHeight: 520,
            borderRadius: 34,
            overflow: 'hidden',
            border: `1px solid ${palette.line}`,
            background: palette.panel,
            boxShadow: '0 24px 80px rgba(0,0,0,0.24)',
          }}
        >
          {imageSrc ? (
            <Img
              src={imageSrc}
              style={{width: '100%', height: '100%', objectFit: 'cover'}}
            />
          ) : (
            <div
              style={{
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: DISPLAY_FONT,
                fontSize: 48,
                color: palette.muted,
              }}
            >
              VISUAL SLOT
            </div>
          )}
        </div>
        <div style={{display: 'flex', flexDirection: 'column', gap: 18}}>
          <div
            style={{
              fontFamily: DISPLAY_FONT,
              fontSize: width < height ? 56 : 84,
              lineHeight: 0.96,
              fontWeight: 700,
            }}
          >
            {resolveOST(scene.on_screen_text[0] ?? scene.purpose).text}
          </div>
          <div style={{fontSize: width < height ? 22 : 30, lineHeight: 1.34, color: palette.muted}}>
            {splitNarration(scene.narration, 3).join('。')}
          </div>
        </div>
      </div>
    </FrameShell>
  );
};

const renderScene = (scene: StoryScene) => {
  const type = scene.visual_type as VisualType;
  if (type === 'diagram') {
    return <DiagramScene scene={scene} />;
  }
  if (type === 'timeline') {
    return <TimelineScene scene={scene} />;
  }
  if (type === 'summary-list') {
    return <SummaryListScene scene={scene} />;
  }
  if (type === 'quote') {
    return <QuoteScene scene={scene} />;
  }
  if (type === 'image-led') {
    return <ImageLedScene scene={scene} />;
  }
  return <ThesisScene scene={scene} />;
};

export const StoryboardVideo: React.FC<StoryboardProps> = ({audio, scenes}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const voiceover = safeRelativeAsset(audio.voiceover_path);
  const music = safeRelativeAsset(audio.music_path);
  const currentCaption = (audio.captions ?? []).find((caption) => {
    const startFrame = Math.floor((caption.start_ms / 1000) * fps);
    const endFrame = Math.ceil((caption.end_ms / 1000) * fps);
    return frame >= startFrame && frame <= endFrame;
  });

  return (
    <AbsoluteFill style={{backgroundColor: '#020617'}}>
      {voiceover ? <Audio src={voiceover} /> : null}
      {music ? <Audio src={music} volume={0.08} /> : null}
      {scenes.map((scene) => (
        <Sequence
          key={scene.id}
          from={Math.round(scene.start_sec * fps)}
          durationInFrames={Math.max(1, Math.round(scene.duration_sec * fps))}
        >
          {renderScene(scene)}
        </Sequence>
      ))}
      {audio.subtitle_mode === 'embedded' && currentCaption ? (
        <div
          style={{
            position: 'absolute',
            left: '50%',
            bottom: width >= 1200 ? 62 : 42,
            transform: 'translateX(-50%)',
            maxWidth: '72%',
            padding: '16px 22px',
            backgroundColor: 'rgba(0, 0, 0, 0.72)',
            color: '#f8fafc',
            borderRadius: 18,
            textAlign: 'center',
            fontSize: width >= 1200 ? 28 : 22,
            lineHeight: 1.35,
            fontWeight: 600,
            fontFamily: BODY_FONT,
            boxShadow: '0 10px 40px rgba(0,0,0,0.25)',
            zIndex: 30,
          }}
        >
          {currentCaption.text}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

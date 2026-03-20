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
import type {StoryScene, StoryboardProps, VisualRole, VisualType} from './types';

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

const splitNarration = (text: string, maxItems: number) => {
  const pieces = text
    .split(/[。！？!?\n]/)
    .flatMap((segment) => segment.split(/[，、,:：；;]/))
    .map((segment) => segment.trim())
    .filter(Boolean);

  if (pieces.length === 0) {
    return [];
  }

  return pieces.slice(0, maxItems);
};

const useSceneMotion = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const enter = spring({
    fps,
    frame,
    config: {
      damping: 200,
      stiffness: 110,
      mass: 0.8,
    },
  });
  const exit = interpolate(frame, [durationInFrames - 20, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return {
    frame,
    opacity: enter * exit,
    rise: interpolate(enter, [0, 1], [48, 0]),
  };
};

const BackgroundWash: React.FC<{palette: Palette; scene: StoryScene}> = ({palette, scene}) => {
  const {frame} = useSceneMotion();
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
  const {opacity} = useSceneMotion();

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
  const {opacity, rise} = useSceneMotion();
  const lines = scene.on_screen_text.length > 0 ? scene.on_screen_text : [scene.purpose];
  const supporting = splitNarration(scene.narration, 2);

  return (
    <FrameShell scene={scene}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: width >= height ? '1.35fr 0.8fr' : '1fr',
          gap: 36,
          alignItems: 'center',
          transform: `translateY(${rise}px)`,
        }}
      >
        <div style={{display: 'flex', flexDirection: 'column', gap: 18, opacity}}>
          <div
            style={{
              fontFamily: DISPLAY_FONT,
              fontSize: width < height ? 72 : 110,
              lineHeight: 0.92,
              fontWeight: 700,
              letterSpacing: -2,
            }}
          >
            {lines.map((line, index) => (
              <div key={`${line}-${index}`}>{line}</div>
            ))}
          </div>
          <div
            style={{
              width: width < height ? 180 : 260,
              height: 6,
              borderRadius: 999,
              background: palette.accent,
            }}
          />
          {supporting.map((line) => (
            <div
              key={line}
              style={{
                fontSize: width < height ? 24 : 34,
                lineHeight: 1.3,
                color: palette.muted,
                maxWidth: '82%',
              }}
            >
              {line}
            </div>
          ))}
        </div>
        <div style={{display: 'flex', flexDirection: 'column', gap: 18, opacity}}>
          {supporting.map((item, index) => (
            <div
              key={`${item}-${index}`}
              style={{
                padding: '20px 24px',
                borderRadius: 24,
                background: palette.panel,
                border: `1px solid ${palette.line}`,
                backdropFilter: 'blur(10px)',
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
                {`Beat ${index + 1}`}
              </div>
              <div style={{marginTop: 10, fontSize: 26, lineHeight: 1.25}}>{item}</div>
            </div>
          ))}
        </div>
      </div>
    </FrameShell>
  );
};

const DiagramScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.evidence;
  const {width, height} = useVideoConfig();
  const {opacity, rise} = useSceneMotion();
  const nodes = [scene.on_screen_text[0] ?? scene.purpose, ...splitNarration(scene.narration, 3)].slice(
    0,
    4
  );

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
            {scene.on_screen_text[0] ?? scene.purpose}
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
          {nodes.map((node, index) => (
            <div
              key={`${node}-${index}`}
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
                {node}
              </div>
            </div>
          ))}
        </div>
      </div>
    </FrameShell>
  );
};

const TimelineScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.process;
  const {width, height} = useVideoConfig();
  const {opacity, rise} = useSceneMotion();
  const beats = splitNarration(scene.narration, 5);

  return (
    <FrameShell scene={scene}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: width >= height ? '0.72fr 1.28fr' : '1fr',
          gap: 28,
          alignItems: 'start',
          opacity,
          transform: `translateY(${rise}px)`,
        }}
      >
        <div style={{display: 'flex', flexDirection: 'column', gap: 18}}>
          <div style={{fontSize: 18, letterSpacing: 3, textTransform: 'uppercase', color: palette.muted}}>
            Role Map
          </div>
          <div
            style={{
              fontFamily: DISPLAY_FONT,
              fontSize: width < height ? 58 : 82,
              lineHeight: 0.96,
              fontWeight: 700,
            }}
          >
            {scene.on_screen_text[0] ?? scene.purpose}
          </div>
          <div style={{fontSize: width < height ? 22 : 28, lineHeight: 1.35, color: palette.muted}}>
            {scene.on_screen_text.slice(1).join(' / ')}
          </div>
        </div>
        <div style={{display: 'flex', flexDirection: 'column', gap: 18}}>
          {beats.map((beat, index) => (
            <div
              key={`${beat}-${index}`}
              style={{
                display: 'grid',
                gridTemplateColumns: '84px 1fr',
                gap: 18,
                alignItems: 'stretch',
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
                {beat}
              </div>
            </div>
          ))}
        </div>
      </div>
    </FrameShell>
  );
};

const SummaryListScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.summary;
  const {width, height} = useVideoConfig();
  const {opacity, rise} = useSceneMotion();
  const items =
    scene.on_screen_text.length > 0
      ? scene.on_screen_text
      : splitNarration(scene.narration, 4);
  const sideText = splitNarration(scene.narration, 2).join('。');

  return (
    <FrameShell scene={scene}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: width >= height ? '0.88fr 1.12fr' : '1fr',
          gap: 32,
          alignItems: 'center',
          opacity,
          transform: `translateY(${rise}px)`,
        }}
      >
        <div style={{display: 'flex', flexDirection: 'column', gap: 20}}>
          <div
            style={{
              fontFamily: DISPLAY_FONT,
              fontSize: width < height ? 60 : 88,
              lineHeight: 0.95,
              fontWeight: 700,
            }}
          >
            {scene.on_screen_text[0] ?? scene.purpose}
          </div>
          <div style={{fontSize: width < height ? 22 : 30, lineHeight: 1.34, color: palette.muted}}>
            {sideText}
          </div>
        </div>
        <div style={{display: 'grid', gap: 16}}>
          {items.map((item, index) => (
            <div
              key={`${item}-${index}`}
              style={{
                display: 'grid',
                gridTemplateColumns: '90px 1fr',
                gap: 18,
                alignItems: 'center',
                padding: '16px 18px',
                borderRadius: 24,
                background: palette.panel,
                border: `1px solid ${palette.line}`,
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
              <div style={{fontSize: width < height ? 24 : 30, lineHeight: 1.22}}>{item}</div>
            </div>
          ))}
        </div>
      </div>
    </FrameShell>
  );
};

const QuoteScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.evidence;
  const {width, height} = useVideoConfig();
  const {opacity, rise} = useSceneMotion();
  const quoteText = splitNarration(scene.narration, 2).join('。');

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
          "
        </div>
        <div
          style={{
            fontFamily: DISPLAY_FONT,
            fontSize: width < height ? 52 : 78,
            lineHeight: 1.02,
            fontWeight: 700,
            maxWidth: '74%',
          }}
        >
          {scene.on_screen_text[0] ?? scene.purpose}
        </div>
        <div
          style={{
            maxWidth: '76%',
            fontSize: width < height ? 24 : 32,
            lineHeight: 1.32,
            color: palette.muted,
          }}
        >
          {quoteText}
        </div>
      </div>
    </FrameShell>
  );
};

const ImageLedScene: React.FC<{scene: StoryScene}> = ({scene}) => {
  const palette = ROLE_PALETTES[scene.visual_role] ?? ROLE_PALETTES.example;
  const {width, height} = useVideoConfig();
  const {opacity, rise} = useSceneMotion();
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
            {scene.on_screen_text[0] ?? scene.purpose}
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

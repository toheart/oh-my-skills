import React from 'react';
import {Composition} from 'remotion';
import {StoryboardVideo} from './StoryboardVideo';
import type {StoryboardProps} from './types';

const emptyProps: StoryboardProps = {
  meta: {
    title: 'Untitled Video',
    publishing_target: 'bilibili',
    aspect_ratio: '16:9',
    fps: 30,
    target_duration_sec: 12,
    duration_sec: 12,
    theme: 'editorial-tech',
  },
  global_style: {
    visual_language: 'editorial motion graphics',
    color_mood: 'neutral',
    typography: 'clean sans',
    pace: 'measured',
  },
  audio: {
    voiceover_path: null,
    music_path: null,
    subtitle_path: null,
    subtitle_mode: 'none',
    captions: [],
  },
  source: {
    core_thesis: '',
    audience: 'general professional audience',
    tone: 'measured',
    content_mode: 'explainer',
    success_metric: 'argument-completeness',
  },
  scenes: [
    {
      id: 's01',
      start_sec: 0,
      duration_sec: 12,
      purpose: 'hook',
      source_refs: [],
      interpretation_note: '',
      narration: 'Replace this with a normalized storyboard input.',
      on_screen_text: ['Starter Template'],
      visual_role: 'thesis',
      visual_type: 'kinetic-type',
      asset_refs: [],
      visual_prompt: 'A restrained editorial title card.',
      avoid: [],
      motion_intent: 'restrained reveal',
    },
  ],
};

const aspectToDimensions = (aspectRatio: string) => {
  if (aspectRatio === '9:16') {
    return {width: 1080, height: 1920};
  }
  if (aspectRatio === '1:1') {
    return {width: 1080, height: 1080};
  }
  return {width: 1920, height: 1080};
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="RemotionVideo"
      component={StoryboardVideo}
      defaultProps={emptyProps}
      durationInFrames={Math.round(emptyProps.meta.duration_sec * emptyProps.meta.fps)}
      fps={emptyProps.meta.fps}
      width={1920}
      height={1080}
      calculateMetadata={({props}) => {
        const typedProps = (props ?? emptyProps) as StoryboardProps;
        const fps = typedProps.meta?.fps ?? 30;
        const durationSec =
          typedProps.meta?.duration_sec ??
          typedProps.scenes.reduce((sum, scene) => sum + scene.duration_sec, 0) ??
          12;
        const {width, height} = aspectToDimensions(typedProps.meta?.aspect_ratio ?? '16:9');

        return {
          fps,
          durationInFrames: Math.max(1, Math.round(durationSec * fps)),
          width,
          height,
        };
      }}
    />
  );
};

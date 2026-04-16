export type VisualRole =
  | 'thesis'
  | 'evidence'
  | 'contrast'
  | 'process'
  | 'example'
  | 'summary';

export type VisualType =
  | 'kinetic-type'
  | 'quote'
  | 'diagram'
  | 'image-led'
  | 'timeline'
  | 'summary-list';

export type OnScreenTextItem = {
  text: string;
  appear_at_ms?: number;
  anchor?: string;
};

export type StoryScene = {
  id: string;
  start_sec: number;
  duration_sec: number;
  purpose: string;
  source_refs: string[];
  interpretation_note?: string;
  narration: string;
  on_screen_text: (string | OnScreenTextItem)[];
  visual_role: VisualRole;
  visual_type: VisualType;
  asset_refs: string[];
  visual_prompt: string;
  avoid: string[];
  motion_intent: string;
};

export type TTSConfig = {
  voice?: string;
  rate?: string;
  volume?: string;
  pitch?: string;
  pause?: number;
};

export type StoryboardProps = {
  meta: {
    title: string;
    publishing_target: string;
    aspect_ratio: '16:9' | '9:16' | '1:1' | string;
    fps: number;
    target_duration_sec: number;
    duration_sec: number;
    theme: string;
  };
  global_style: {
    visual_language: string;
    color_mood: string;
    typography: string;
    pace: string;
  };
  audio: {
    voiceover_path?: string | null;
    music_path?: string | null;
    subtitle_path?: string | null;
    subtitle_mode?: 'embedded' | 'external' | 'none' | string;
    captions?: {
      start_ms: number;
      end_ms: number;
      text: string;
      scene_id?: string;
    }[];
  };
  source: {
    core_thesis: string;
    audience: string;
    tone: string;
    content_mode: string;
    success_metric: string;
    tts?: TTSConfig;
  };
  scenes: StoryScene[];
};

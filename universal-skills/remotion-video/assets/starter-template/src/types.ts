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

export type StoryScene = {
  id: string;
  start_sec: number;
  duration_sec: number;
  purpose: string;
  source_refs: string[];
  interpretation_note?: string;
  narration: string;
  on_screen_text: string[];
  visual_role: VisualRole;
  visual_type: VisualType;
  asset_refs: string[];
  visual_prompt: string;
  avoid: string[];
  motion_intent: string;
};

export type StoryboardProps = {
  meta: {
    title: string;
    aspect_ratio: '16:9' | '9:16' | '1:1' | string;
    fps: number;
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
  scenes: StoryScene[];
};

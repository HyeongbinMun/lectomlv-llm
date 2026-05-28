export type SceneLayout = "title_card" | "bullet_list" | "quote";

export type Scene = {
  segment_index: number;
  start_time: string;
  end_time: string;
  duration_sec: number;
  transcript: string;
  scene_title: string;
  keywords: string[];
  layout: SceneLayout;
  bg_color: string;
  accent_color: string;
  bullets?: string[];
  audio_file?: string;
};

export type ScenePlan = {
  title: string;
  fps: number;
  width: number;
  height: number;
  scenes: Scene[];
};

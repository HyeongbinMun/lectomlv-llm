import React from "react";
import { Composition } from "remotion";
import { LectureVideo } from "./LectureVideo";
import type { ScenePlan } from "./types";

const defaultScenePlan: ScenePlan = {
  title: "샘플 강의",
  fps: 30,
  width: 1920,
  height: 1080,
  scenes: [
    {
      segment_index: 0,
      start_time: "0:00",
      end_time: "0:10",
      duration_sec: 10,
      transcript: "강의 내용 샘플입니다.",
      scene_title: "강의 소개",
      keywords: ["인공지능", "기계학습"],
      layout: "title_card",
      bg_color: "#16213e",
      accent_color: "#e94560",
      bullets: [],
    },
    {
      segment_index: 1,
      start_time: "0:10",
      end_time: "0:25",
      duration_sec: 15,
      transcript: "기계학습은 세 가지 유형으로 나뉩니다.",
      scene_title: "학습 유형",
      keywords: ["지도학습", "비지도학습", "강화학습"],
      layout: "bullet_list",
      bg_color: "#0f3460",
      accent_color: "#e94560",
      bullets: ["지도학습: 정답이 있는 데이터로 학습", "비지도학습: 패턴을 스스로 발견", "강화학습: 보상을 통해 행동 최적화"],
    },
  ],
};

const totalFrames = (plan: ScenePlan) =>
  plan.scenes.reduce((acc, s) => acc + Math.max(1, Math.round(s.duration_sec * plan.fps)), 0);

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="LectureVideo"
      component={LectureVideo}
      fps={defaultScenePlan.fps}
      width={defaultScenePlan.width}
      height={defaultScenePlan.height}
      durationInFrames={totalFrames(defaultScenePlan)}
      defaultProps={defaultScenePlan}
      calculateMetadata={({ props }) => ({
        durationInFrames: totalFrames(props as ScenePlan),
      })}
    />
  );
};

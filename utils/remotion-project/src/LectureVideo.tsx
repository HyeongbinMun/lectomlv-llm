import React from "react";
import { AbsoluteFill, Series } from "remotion";
import { SceneComponent } from "./Scene";
import type { ScenePlan } from "./types";

export const LectureVideo: React.FC<ScenePlan> = ({ fps, scenes }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0d0d0d" }}>
      <Series>
        {scenes.map((scene) => (
          <Series.Sequence
            key={scene.segment_index}
            durationInFrames={Math.max(1, Math.round(scene.duration_sec * fps))}
          >
            <SceneComponent scene={scene} />
          </Series.Sequence>
        ))}
      </Series>
    </AbsoluteFill>
  );
};

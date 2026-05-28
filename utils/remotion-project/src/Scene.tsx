import React from "react";
import {
  AbsoluteFill,
  Audio,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { Scene as SceneType } from "./types";

const useFadeIn = (delay = 0, durationFrames = 20) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({
    frame: frame - delay,
    fps,
    config: { damping: 200 },
    durationInFrames: durationFrames,
  });
};

const useSlideUp = (delay = 0) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({
    frame: frame - delay,
    fps,
    config: { damping: 120, stiffness: 80 },
    durationInFrames: 30,
  });
  return interpolate(progress, [0, 1], [40, 0]);
};

const TitleCard: React.FC<{ scene: SceneType; opacity: number }> = ({ scene, opacity }) => {
  const slideY = useSlideUp(5);
  const keywordOpacity = useFadeIn(20);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: scene.bg_color,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        opacity,
        padding: "80px",
      }}
    >
      <div
        style={{
          transform: `translateY(${slideY}px)`,
          textAlign: "center",
        }}
      >
        <div
          style={{
            width: "60px",
            height: "4px",
            backgroundColor: scene.accent_color,
            margin: "0 auto 32px",
            borderRadius: "2px",
          }}
        />
        <h1
          style={{
            fontSize: "72px",
            fontWeight: 700,
            color: "#ffffff",
            margin: 0,
            lineHeight: 1.3,
            letterSpacing: "-0.02em",
          }}
        >
          {scene.scene_title}
        </h1>
      </div>

      <div
        style={{
          opacity: keywordOpacity,
          marginTop: "48px",
          display: "flex",
          gap: "16px",
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        {scene.keywords.map((kw) => (
          <span
            key={kw}
            style={{
              backgroundColor: `${scene.accent_color}33`,
              border: `1px solid ${scene.accent_color}`,
              color: scene.accent_color,
              padding: "8px 20px",
              borderRadius: "24px",
              fontSize: "28px",
              fontWeight: 500,
            }}
          >
            {kw}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const BulletList: React.FC<{ scene: SceneType; opacity: number }> = ({ scene, opacity }) => {
  const bullets = scene.bullets ?? [];
  const titleOpacity = useFadeIn(0);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill
      style={{
        backgroundColor: scene.bg_color,
        opacity,
        padding: "80px 120px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "20px",
          marginBottom: "48px",
          opacity: titleOpacity,
        }}
      >
        <div
          style={{
            width: "8px",
            height: "60px",
            backgroundColor: scene.accent_color,
            borderRadius: "4px",
          }}
        />
        <h2
          style={{
            fontSize: "52px",
            fontWeight: 700,
            color: "#ffffff",
            margin: 0,
          }}
        >
          {scene.scene_title}
        </h2>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
        {bullets.map((bullet, i) => {
          const delay = 10 + i * 8;
          const itemOpacity = spring({
            frame: frame - delay,
            fps,
            config: { damping: 200 },
            durationInFrames: 20,
          });
          const itemY = interpolate(itemOpacity, [0, 1], [20, 0]);

          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "20px",
                opacity: itemOpacity,
                transform: `translateY(${itemY}px)`,
              }}
            >
              <div
                style={{
                  width: "12px",
                  height: "12px",
                  borderRadius: "50%",
                  backgroundColor: scene.accent_color,
                  marginTop: "14px",
                  flexShrink: 0,
                }}
              />
              <p
                style={{
                  fontSize: "40px",
                  color: "#e0e0e0",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                {bullet}
              </p>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const Quote: React.FC<{ scene: SceneType; opacity: number }> = ({ scene, opacity }) => {
  const slideY = useSlideUp(5);
  const lineOpacity = useFadeIn(25);
  const firstBullet = scene.bullets?.[0] ?? scene.transcript.slice(0, 120);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: scene.bg_color,
        opacity,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px 160px",
        textAlign: "center",
      }}
    >
      <div
        style={{
          transform: `translateY(${slideY}px)`,
        }}
      >
        <div
          style={{
            fontSize: "120px",
            color: scene.accent_color,
            lineHeight: 0.8,
            marginBottom: "32px",
            opacity: 0.6,
          }}
        >
          "
        </div>
        <p
          style={{
            fontSize: "48px",
            color: "#ffffff",
            margin: 0,
            lineHeight: 1.6,
            fontWeight: 300,
          }}
        >
          {firstBullet}
        </p>
      </div>

      <div
        style={{
          opacity: lineOpacity,
          marginTop: "48px",
          display: "flex",
          alignItems: "center",
          gap: "16px",
        }}
      >
        <div
          style={{
            width: "40px",
            height: "2px",
            backgroundColor: scene.accent_color,
          }}
        />
        <span style={{ fontSize: "28px", color: scene.accent_color }}>
          {scene.scene_title}
        </span>
        <div
          style={{
            width: "40px",
            height: "2px",
            backgroundColor: scene.accent_color,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

export const SceneComponent: React.FC<{ scene: SceneType }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const fadeIn = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [durationInFrames - 12, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
  });
  const opacity = Math.min(fadeIn, fadeOut);

  return (
    <>
      {scene.audio_file && (
        <Audio src={staticFile(scene.audio_file)} />
      )}
      {scene.layout === "bullet_list" && <BulletList scene={scene} opacity={opacity} />}
      {scene.layout === "quote" && <Quote scene={scene} opacity={opacity} />}
      {(scene.layout === "title_card" || !scene.layout) && <TitleCard scene={scene} opacity={opacity} />}
    </>
  );
};

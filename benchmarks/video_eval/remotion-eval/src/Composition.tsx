import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  Audio,
  staticFile,
} from "remotion";

const gradient = "linear-gradient(135deg, #5a4bd1 0%, #a29bfe 50%, #e85a8e 100%)";

const Title: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [12, 36], [0, 1], {
    extrapolateRight: "clamp",
  });
  const y = interpolate(frame, [12, 36], [-60, 0], {
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "flex-start",
        paddingLeft: 160,
        opacity,
        transform: `translateY(${y}px)`,
      }}
    >
      <div style={{ fontSize: 120, fontWeight: 900, color: "#fff" }}>
        内容工厂
      </div>
      <div
        style={{
          fontSize: 48,
          color: "#fff",
          textShadow: "0 2px 8px rgba(0,0,0,0.8)",
          marginTop: 16,
        }}
      >
        程序化视频 · 十五秒评测
      </div>
    </AbsoluteFill>
  );
};

const Chart: React.FC<{ left: number; height: number; opacity: number }> = ({
  left,
  height,
  opacity,
}) => {
  return (
    <div
      style={{
        position: "absolute",
        bottom: 260,
        left,
        width: 120,
        height,
        borderRadius: "12px 12px 0 0",
        background: `rgba(255,255,255,${opacity})`,
      }}
    />
  );
};

const Scene2: React.FC = () => {
  const frame = useCurrentFrame();
  const bars = [
    { left: 260, h: 420, o: 0.9, t: 12 },
    { left: 460, h: 520, o: 0.75, t: 24 },
    { left: 660, h: 380, o: 0.6, t: 36 },
    { left: 860, h: 640, o: 0.45, t: 48 },
  ];
  const sceneOpacity = interpolate(frame, [0, 10], [0, 1], {
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ opacity: sceneOpacity }}>
      {bars.map((b) => {
        const h = interpolate(frame, [b.t, b.t + 30], [0, b.h], {
          extrapolateRight: "clamp",
        });
        return <Chart key={b.left} left={b.left} height={h} opacity={b.o} />;
      })}
      <div
        style={{
          position: "absolute",
          bottom: 190,
          left: 200,
          fontSize: 36,
          color: "#fff",
          fontWeight: 700,
          textShadow: "0 2px 8px rgba(0,0,0,0.8)",
        }}
      >
        渲染吞吐对比：HyperFrames · Remotion · FFmpeg
      </div>
    </AbsoluteFill>
  );
};

const Caption: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [15, 30], [0, 1], {
    extrapolateRight: "clamp",
  });
  const exitOpacity = interpolate(frame, [420, 440], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 60,
        opacity: Math.min(opacity, exitOpacity),
      }}
    >
      <div
        style={{
          fontSize: 34,
          fontWeight: 600,
          color: "#e4e4e4",
          background: "#000",
          borderRadius: 16,
          padding: "16px 32px",
        }}
      >
        写好代码，渲染成片，全程自动化
      </div>
    </AbsoluteFill>
  );
};

export const Main: React.FC = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: gradient }}>
      <Audio src={staticFile("narration.mp3")} />
      <Title />
      <Scene2 />
      <Caption />
    </AbsoluteFill>
  );
};

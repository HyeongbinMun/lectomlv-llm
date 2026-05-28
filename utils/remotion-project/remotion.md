# Remotion 프로젝트 사용법

강의 세그먼트 JSON과 오디오/영상 원본을 입력받아,  
Qwen2.5 14B가 씬 계획을 세우고 Remotion으로 **참고 영상(1920×1080, 30fps)** 을 자동 생성합니다.

## 프로젝트 구조

```
remotion-project/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.tsx          # Remotion 엔트리포인트 (컴포지션 등록)
│   ├── Root.tsx           # 루트 컴포넌트
│   ├── LectureVideo.tsx   # 메인 컴포지션 — Series로 씬 배치
│   ├── Scene.tsx          # 개별 씬 컴포넌트 (TitleCard / BulletList / Quote)
│   └── types.ts           # ScenePlan, Scene 타입 정의
└── public/
    └── audio/             # ffmpeg으로 추출된 구간별 오디오 (자동 생성)
```

## 사전 요구사항

| 항목 | 버전 | 비고 |
|------|------|------|
| Node.js | 18+ | `node -v` 로 확인 |
| npm | 9+ | Node.js와 함께 설치됨 |
| ffmpeg | 시스템 설치 권장 | 오디오 추출에 사용 |
| Ollama + Qwen2.5 14B | — | 씬 계획 생성에 사용 |

Docker 환경에서는 `docker/Dockerfile`에 Node.js, npm, ffmpeg이 모두 설치되어 있습니다.

## 설치

```bash
cd utils/remotion-project
npm install
```

> `node_modules`는 `.gitignore`에 포함되어 있으므로 클론 후 반드시 `npm install`을 실행해야 합니다.  
> Docker 빌드 시에는 `Dockerfile` 내에서 자동으로 설치됩니다.

---

## 방법 1 — `remotion_test.py` 스크립트 (권장)

오디오 추출 → 씬 계획 생성 → Remotion 렌더링까지 한 번에 실행합니다.

### 기본 사용법

```bash
# 컨테이너 외부 (로컬)
python utils/remotion_test.py --input utils/test_audio.json --ollama-url http://localhost:11434

# 컨테이너 내부
docker compose exec web python utils/remotion_test.py \
  --input utils/test_audio.json \
  --output-dir /data/remotions \
  --output lecture_video.mp4 \
  --ollama-url http://ollama:11434
```

### CLI 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--input` | (샘플 사용) | 강의 세그먼트 JSON 파일 경로 |
| `--output` | `lecture_video.mp4` | 출력 영상 파일명 |
| `--output-dir` | `utils/` | `scene_plan.json` 및 출력 영상 저장 디렉터리 |
| `--source-file` | JSON의 `source_file` 필드 | 원본 오디오/영상 파일 경로 (JSON 값 덮어씀) |
| `--ollama-url` | `http://localhost:11434` | Ollama 서버 URL |
| `--skip-render` | `false` | `scene_plan.json`만 생성하고 렌더링 생략 |
| `--skip-audio` | `false` | 오디오 추출 건너뜀 (비주얼만 생성) |

### 사용 예시

```bash
# 1. 씬 계획만 먼저 확인 (렌더링 없음)
python utils/remotion_test.py \
  --input my_lecture.json \
  --output-dir ./output \
  --skip-render

# 2. 오디오 없이 비주얼만 생성
python utils/remotion_test.py \
  --input my_lecture.json \
  --output-dir ./output \
  --skip-audio

# 3. JSON의 source_file 필드를 다른 파일로 덮어써서 실행
python utils/remotion_test.py \
  --input my_lecture.json \
  --source-file /data/audios/lecture_audio.mp4 \
  --output-dir /data/remotions

# 4. Docker 컨테이너 안에서 전체 파이프라인 실행
docker compose exec web python utils/remotion_test.py \
  --input utils/test_audio.json \
  --output-dir /data/remotions \
  --output final_video.mp4 \
  --ollama-url http://ollama:11434
```

### 생성 파이프라인

```
input JSON
  ├─→ [ffmpeg] 세그먼트별 오디오 추출
  │     └→ remotion-project/public/audio/segment_0.aac
  │         remotion-project/public/audio/segment_1.aac ...
  │
  ├─→ [Qwen2.5 14B] 각 세그먼트마다 씬 계획 생성
  │     └→ {output-dir}/scene_plan.json
  │
  └─→ [Remotion] scene_plan.json을 props로 LectureVideo 렌더링
        └→ {output-dir}/{output}.mp4
```

| 생성 파일 | 위치 |
|-----------|------|
| 씬 계획 JSON | `{output-dir}/scene_plan.json` |
| 구간별 오디오 | `remotion-project/public/audio/segment_N.aac` |
| 최종 영상 | `{output-dir}/{output}.mp4` |

---

## 방법 2 — Remotion Studio (개발/프리뷰)

브라우저에서 실시간으로 씬을 확인하고 수정할 수 있습니다.

```bash
cd utils/remotion-project
npm start
# 브라우저에서 http://localhost:3000 접속
```

> `scene_plan.json`을 `remotion-project/` 루트에 직접 두거나,  
> `src/index.tsx`의 `defaultProps`를 수정하여 미리보기 데이터를 지정할 수 있습니다.

---

## 방법 3 — Remotion CLI 직접 렌더링

`scene_plan.json`이 이미 있을 때 렌더링만 실행합니다.

```bash
cd utils/remotion-project

# scene_plan.json을 props 파일로 지정
npx remotion render LectureVideo out/lecture_video.mp4 \
  --props ../scene_plan.json

# 해상도 변경 (기본 1920×1080)
npx remotion render LectureVideo out/lecture_video.mp4 \
  --props ../scene_plan.json \
  --width 1280 --height 720
```

---

## `scene_plan.json` 형식

`remotion_test.py`가 자동으로 생성하거나 직접 작성할 수 있습니다.

```json
{
  "title": "강의 제목",
  "fps": 30,
  "width": 1920,
  "height": 1080,
  "scenes": [
    {
      "segment_index": 0,
      "start_time": "00:02",
      "end_time": "00:28",
      "duration_sec": 26,
      "transcript": "원본 강의 텍스트...",
      "scene_title": "씬 제목 (15자 이내)",
      "keywords": ["키워드1", "키워드2", "키워드3"],
      "layout": "bullet_list",
      "bg_color": "#16213e",
      "accent_color": "#e94560",
      "bullets": ["핵심 내용 1", "핵심 내용 2", "핵심 내용 3"],
      "audio_file": "audio/segment_0.aac"
    }
  ]
}
```

### Scene 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `segment_index` | number | ✓ | 세그먼트 순서 인덱스 |
| `start_time` | string | ✓ | 원본 강의 시작 시간 |
| `end_time` | string | ✓ | 원본 강의 종료 시간 |
| `duration_sec` | number | ✓ | 씬 재생 시간 (초) |
| `transcript` | string | ✓ | 원본 강의 텍스트 |
| `scene_title` | string | ✓ | 씬에 표시할 제목 |
| `keywords` | string[] | ✓ | 핵심 키워드 (3개 권장) |
| `layout` | string | ✓ | 씬 레이아웃 종류 |
| `bg_color` | string | ✓ | 배경색 (`#rrggbb`) |
| `accent_color` | string | ✓ | 강조색 (`#rrggbb`) |
| `bullets` | string[] | — | bullet_list / quote 레이아웃의 내용 |
| `audio_file` | string | — | 오디오 파일 경로 (`public/` 기준 상대경로) |

---

## 씬 레이아웃 종류

### `title_card` — 제목 + 키워드

주제 전환, 도입부, 짧은 개념 소개에 사용합니다.

```
┌─────────────────────────────┐
│                             │
│    ——————                   │
│    씬 제목                   │
│                             │
│  [키워드1] [키워드2] [키워드3]│
│                             │
└─────────────────────────────┘
```

### `bullet_list` — 제목 + 항목 목록

여러 개념 열거, 단계별 설명, 비교 내용에 사용합니다.

```
┌─────────────────────────────┐
│ | 씬 제목                    │
│                             │
│  ● 핵심 내용 1               │
│  ● 핵심 내용 2               │
│  ● 핵심 내용 3               │
│                             │
└─────────────────────────────┘
```

### `quote` — 인용구 강조

중요한 정의, 핵심 문장, 강조하고 싶은 구절에 사용합니다.

```
┌─────────────────────────────┐
│             "               │
│    인용 내용 텍스트...        │
│                             │
│  —— 씬 제목 ——              │
└─────────────────────────────┘
```

---

## 컴포넌트 커스터마이징

### 배경색·강조색 변경

`scene_plan.json`의 각 씬에서 `bg_color`와 `accent_color`를 직접 지정합니다.

```json
{ "bg_color": "#0f2027", "accent_color": "#f7971e" }
```

### 폰트 변경

`src/Scene.tsx`의 `BulletList`, `TitleCard`, `Quote` 컴포넌트에서 `fontFamily` 스타일을 수정합니다.

```tsx
<h1 style={{ fontFamily: "'Noto Sans KR', sans-serif", ... }}>
```

웹폰트를 사용하려면 `public/index.html`에 `<link>` 태그를 추가하거나, `src/index.tsx`에서 `@remotion/google-fonts`를 사용합니다.

### 해상도·FPS 변경

`src/index.tsx`의 `<Composition>` 설정을 수정합니다.

```tsx
<Composition
  id="LectureVideo"
  component={LectureVideo}
  width={1280}     // 기본: 1920
  height={720}     // 기본: 1080
  fps={24}         // 기본: 30
  ...
/>
```

### 새 씬 레이아웃 추가

`src/Scene.tsx`에 새 컴포넌트를 추가하고, `SceneComponent`의 렌더링 분기에 등록합니다.

```tsx
const MyLayout: React.FC<{ scene: SceneType; opacity: number }> = ({ scene, opacity }) => {
  // 커스텀 씬 구현
};

// SceneComponent 내부에 추가
{scene.layout === "my_layout" && <MyLayout scene={scene} opacity={opacity} />}
```

`types.ts`의 `SceneLayout` 타입도 확장합니다.

```ts
export type SceneLayout = "title_card" | "bullet_list" | "quote" | "my_layout";
```

---

## 트러블슈팅

### `node_modules`가 없어서 실행 안 됨

```bash
cd utils/remotion-project
npm install
```

### `npx remotion` 명령을 찾을 수 없음

```bash
# 전역 설치
npm install -g @remotion/cli

# 또는 npx 사용
npx remotion@latest render ...
```

### 오디오가 없는 씬이 생성됨

- `source_file` 경로가 올바른지 확인합니다.
- `ffmpeg`가 설치되어 있고 PATH에 있는지 확인합니다.
- `--skip-audio` 옵션이 붙어 있으면 제거합니다.

### Ollama 씬 계획 생성 실패

- `--ollama-url` 이 올바른지 확인합니다.
- `docker compose exec ollama ollama list` 로 `qwen2.5:14b` 모델이 있는지 확인합니다.
- 실패한 씬은 기본값(bullet_list)으로 대체됩니다.

### 렌더링이 너무 느림

세그먼트 수가 많을수록 렌더링 시간이 늘어납니다.  
먼저 `--skip-render`로 씬 계획만 확인한 뒤, 필요한 씬만 수동으로 편집 후 렌더링하세요.

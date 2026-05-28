# LectoMLV LLM

강의자료 기반 **Grounded RAG** 질의응답 서버입니다.

업로드된 STT 세그먼트와 슬라이드 텍스트를 FAISS 벡터 인덱스로 관리하고,
사용자 질문에 대해 **출처 인용이 포함된 답변**을 생성합니다.
모든 문장에 `[S#]` 인라인 인용을 강제하며, Faithfulness 검증까지 수행합니다.

## 주요 기능

- **Grounded RAG** — 출처 기반 답변 생성, 모든 문장에 `[S#]` 인용 강제
- **Faithfulness 검증** — LLM이 생성한 답변을 다시 검증하여 근거 없는 문장 탐지
- **구간 검색 / 요약 / 추천** — 3가지 쿼리 유형 지원
- **영상 클립 추출** — 인용된 영상 구간을 ffmpeg으로 잘라 클립 생성
- **자막 오버레이** — RAG 인용 transcript를 ASS 형식으로 변환하여 클립에 자막 삽입
- **강의명 오버레이** — 클립 상단에 강의 제목 텍스트 표시 (좌/중/우 위치 선택)
- **화면 비율 변환** — 16:9 / 9:16 / 1:1 / 4:3 중 원하는 비율로 클립 재인코딩
- **클립 시간 미세 조정** — 클립별 시작/종료 시간을 초 단위로 개별 조정
- **클립 선택 & 순서 변경** — 머지할 클립을 체크박스로 선택하고 순서 조절
- **클립 머지** — 생성된 클립들을 하나의 mp4로 합치기
- **직접 선택 클립** — RAG 없이 강의 세그먼트를 직접 선택하여 클립 생성 및 머지
- **자막 인라인 편집** — 세그먼트별 STT 교정본(`transcript_corrected`) 직접 수정, `Enter`로 줄바꿈 삽입
- **외부 JSON 자동 변환** — PPTX 슬라이드·영상 자막 등 다양한 형식 자동 감지 및 임포트
- **JSON 직접 붙여넣기** — 강의 데이터 JSON을 웹 UI에서 직접 입력하여 업로드
- **비디오/문서 분리 표시** — RAG 결과에서 영상·음성과 슬라이드·PDF를 별도 섹션으로 표시
- **비동기 처리** — Celery Worker가 LLM 추론과 벡터 인덱싱을 백그라운드 수행
- **데모 대시보드** — 브라우저에서 바로 쿼리·업로드·결과 확인 가능
- **모델 확장 가능** — Ollama 지원 모델을 설정만으로 추가 가능

## 아키텍처

```
Client (Browser / curl / Python)
    │
    ▼
┌────────┐     ┌─────────────────┐
│ Nginx  │────▶│ Django (DRF)    │  API + Demo UI
│ :8777  │     │ Gunicorn :8000  │
└────────┘     └────────┬────────┘
                        │
                  ┌─────┴─────┐
                  │   Redis   │  Celery Broker
                  └─────┬─────┘
                        │
               ┌────────┴────────┐
               │  Celery Worker  │  LLM 추론 + FAISS 인덱싱
               └────────┬────────┘
                        │
            ┌───────────┼───────────┐
            │           │           │
     ┌──────┴──────┐ ┌──┴───┐ ┌────┴─────┐
     │   Ollama    │ │FAISS │ │PostgreSQL│
     │ (LLM, GPU) │ │(벡터)│ │ (메인 DB)│
     └─────────────┘ └──────┘ └──────────┘
```

## 빠른 시작

```bash
# 1. 클론
git clone https://github.com/SCH-AICS/lectomlv-llm.git
cd lectomlv-llm

# 2. 환경변수
cp docker/.env.example docker/.env

# 3. 빌드 & 실행
docker compose up -d --build

# 4. DB 마이그레이션
docker compose exec web python manage.py migrate

# 5. Ollama 모델 다운로드 확인 (최초 실행 시 자동, 수동도 가능)
docker compose exec ollama ollama pull qwen2.5:14b

# 6. 접속
open http://localhost:8777/
open http://localhost:8777/api/
```

> 최초 실행 시 Ollama가 모델을 자동 다운로드합니다 (10분+ 소요).
> 진행 확인: `docker compose logs -f ollama_init`

## 기본 워크플로우

```
1. 강의 데이터 임포트   POST /api/lectures/bulk-import/      → 벡터 인덱싱 자동 시작
2. 인덱싱 완료 확인     GET  /api/llm/tasks/{task_id}/
3. LLM 쿼리 전송       POST /api/llm/query/                 → 비동기 처리 시작
4. 결과 조회            GET  /api/llm/query/{id}/             → Grounded 답변 + 출처
5. 영상 클립 자르기     POST /api/llm/query/{id}/clip/        → 인용 구간 ffmpeg 클리핑
6. 클립 합치기          POST /api/llm/query/{id}/merge/       → 클립 하나로 머지

직접 선택 클립 (RAG 없이)
  POST /api/llm/manual-clip/                               → 세그먼트 ID로 바로 클립 생성
  POST /api/llm/query/{id}/merge/                          → 동일한 머지 엔드포인트 재사용
```

## LLM 모델 사양

Ollama를 통해 양자화된(Q4) 모델을 사용합니다.
권장 GPU: **NVIDIA RTX 3090 (24GB VRAM)** 이상

| 모델 | 키 | 파라미터 | 양자화 | VRAM 사용량 | 컨텍스트 길이 | 용도 |
|------|-----|---------|--------|------------|-------------|------|
| Qwen 2.5 14B | `qwen` | 14.7B | Q4_K_M | ~15 GB | 32K tokens | 기본 모델, 한국어 성능 우수 |
| MiniLM-L12 (임베딩) | — | 118M | FP32 | ~0.5 GB (CPU) | 512 tokens | 벡터 임베딩 |

> Ollama는 요청 시 모델을 GPU에 로드하고, 유휴 시 자동 언로드합니다.
> `docker/.env`의 `OLLAMA_QWEN_MODEL`을 변경하면 다른 Ollama 모델로 교체할 수 있습니다.

## API 엔드포인트

### 강의 데이터 관리

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/lectures/` | 강의 목록 |
| POST | `/api/lectures/` | 강의 생성 |
| GET | `/api/lectures/{id}/` | 강의 상세 (세그먼트 포함) |
| PUT | `/api/lectures/{id}/` | 강의 수정 |
| DELETE | `/api/lectures/{id}/` | 강의 삭제 |
| GET | `/api/lectures/{id}/segments/` | 구간 목록 |
| PATCH | `/api/lectures/{id}/segments/{seg_id}/` | 구간 교정 자막 저장 |
| POST | `/api/lectures/bulk-import/` | STT 데이터 일괄 임포트 |

### LLM 쿼리

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/llm/query/` | LLM 쿼리 생성 (비동기) |
| GET | `/api/llm/query/{id}/` | 쿼리 결과 조회 |
| GET | `/api/llm/queries/` | 쿼리 이력 |
| GET | `/api/llm/tasks/{task_id}/` | 태스크 상태 확인 |
| GET | `/api/llm/models/` | 사용 가능 모델 목록 |

### 영상 클립

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/llm/query/{id}/clip/` | 인용된 영상 구간을 ffmpeg으로 클리핑 |
| POST | `/api/llm/query/{id}/merge/` | 생성된 클립들을 하나의 mp4로 머지 |
| POST | `/api/llm/manual-clip/` | 세그먼트 ID를 직접 지정하여 클립 생성 |

#### 클립 요청 바디 — `POST /api/llm/query/{id}/clip/`

```json
{
  "aspect_ratio": "16:9",
  "with_subtitles": true,
  "with_title": false,
  "title_position": "right",
  "segment_offsets": [
    { "citation_tag": "[S1]", "start_offset_sec": -2.0, "end_offset_sec": 1.5 }
  ]
}
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `aspect_ratio` | `null` (원본 유지) | `"16:9"` / `"9:16"` / `"1:1"` / `"4:3"` |
| `with_subtitles` | `true` | transcript를 ASS 자막으로 burn-in |
| `with_title` | `false` | 강의 제목을 영상 상단에 텍스트 오버레이 |
| `title_position` | `"right"` | 오버레이 위치: `"left"` / `"center"` / `"right"` |
| `segment_offsets` | `[]` | 클립별 시작/종료 시간 미세 조정 (초 단위) |

#### 머지 요청 바디 — `POST /api/llm/query/{id}/merge/`

```json
{
  "selected_clips": ["clip1.mp4", "clip3.mp4", "clip2.mp4"]
}
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `selected_clips` | `null` (성공 클립 전체) | 머지할 클립 파일명 배열 (순서대로 머지) |

#### 직접 선택 클립 — `POST /api/llm/manual-clip/`

```json
{
  "segment_ids": [3924, 3925, 3930],
  "aspect_ratio": "16:9",
  "with_subtitles": true,
  "with_title": true,
  "title_position": "left"
}
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `segment_ids` | 필수 | 클립을 만들 `LectureSegment` ID 목록 (입력 순서대로 처리) |
| `aspect_ratio` | `null` | 비율 변환 |
| `with_subtitles` | `true` | 자막 burn-in |
| `with_title` | `false` | 강의명 오버레이 |
| `title_position` | `"right"` | 오버레이 위치 |

응답으로 받은 `query_id`로 기존 `/api/llm/query/{id}/` 및 `/api/llm/query/{id}/merge/`를 동일하게 사용합니다.

비율 변환이나 자막·오버레이가 적용될 경우 libx264로 재인코딩되며, 아무것도 없을 때는 `-c copy`로 빠르게 처리됩니다.  
생성된 클립과 머지 파일은 `http://서버:8777/clips/{파일명}` 으로 직접 다운로드할 수 있습니다.

#### 구간 교정 자막 저장 — `PATCH /api/lectures/{id}/segments/{seg_id}/`

```json
{ "transcript_corrected": "수정된 자막 텍스트\n두 번째 줄" }
```

- `transcript_corrected`가 비어 있지 않으면 클립 생성 시 원본 `transcript` 대신 사용됩니다.
- `\n`(줄바꿈)은 ASS 자막의 강제 줄바꿈(`\N`)으로 변환되어 원하는 위치에 줄이 나뉩니다.
- 빈 문자열(`""`)로 저장하면 원본 STT로 되돌립니다.

## 강의 데이터 JSON 형식

```json
{
  "title": "신경회로망특론 - 3. CS231_Lecture3",
  "source_file": "3. CS231_Lecture3.mp4",
  "description": "video | ko | 262 segments",
  "segments": [
    {
      "start_time": "00:02",
      "end_time": "00:28",
      "transcript": "강의 내용 텍스트..."
    }
  ]
}
```

float 초 단위 형식도 지원합니다.

```json
{"start": 748.454, "end": 777.682, "text": "강의 내용..."}
```

## 외부에서 배치 업로드

서버가 아닌 다른 컴퓨터에서 강의 데이터를 한꺼번에 업로드할 수 있습니다.

### curl로 업로드

```bash
SERVER="http://서버IP:8777"

curl -s -X POST "$SERVER/api/lectures/bulk-import/" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "인공지능과 기계학습 1강",
    "source_file": "p1_AI_ML_intro.pdf",
    "segments": [
      {"start_time": "00:01", "end_time": "01:36", "transcript": "오늘 수업은..."},
      {"start_time": "01:37", "end_time": "04:22", "transcript": "인공지능이라는 거는..."}
    ]
  }' | python3 -m json.tool

curl -s -X POST "$SERVER/api/lectures/bulk-import/" \
  -H "Content-Type: application/json" \
  -d @CAD기초.json | python3 -m json.tool
```

### Python 스크립트로 업로드

```python
import requests, time
from pathlib import Path

SERVER = "http://서버IP:8777"

for f in sorted(Path("./data").glob("*.json")):
    print(f"Uploading: {f.name}")
    resp = requests.post(
        f"{SERVER}/api/lectures/bulk-import/",
        headers={"Content-Type": "application/json"},
        data=f.read_text(encoding="utf-8"),
    )
    result = resp.json()
    print(f"  {'OK' if resp.ok else 'FAIL'} — {result.get('success', result)}")

resp = requests.post(f"{SERVER}/api/llm/query/", json={
    "query_text": "인공지능과 머신러닝의 차이가 뭐야?",
    "query_type": "search",
    "model_name": "qwen",
})
query_id = resp.json()["query_id"]

while True:
    r = requests.get(f"{SERVER}/api/llm/query/{query_id}/").json()
    if r["status"] in ("completed", "failed"):
        break
    time.sleep(3)

print(r["result_text"])
```

## 영상 클립 디렉터리 설정

`docker-compose.yml`에서 원본 영상 경로와 클립 저장 경로를 bind mount로 지정합니다.

```yaml
services:
  web:
    volumes:
      - /호스트/원본영상/경로:/data/videos:ro
      - /호스트/클립저장/경로:/data/clips

  celery_worker:
    volumes:
      - /호스트/원본영상/경로:/data/videos:ro
      - /호스트/클립저장/경로:/data/clips

  nginx:
    volumes:
      - /호스트/클립저장/경로:/data/clips:ro
```

컨테이너 내부 경로(`/data/videos`, `/data/clips`)는 `docker/.env`의 `VIDEO_SOURCE_DIR` / `VIDEO_CLIPS_DIR` 로 변경할 수 있습니다.

## 참고 영상 자동 생성 (Remotion)

음성 파일과 세그먼트 메타데이터 JSON이 있을 때, Qwen2.5 14B로 씬 계획을 생성하고 Remotion으로 참고 영상을 만들 수 있습니다.
자세한 사용법은 [`utils/remotion-project/remotion.md`](utils/remotion-project/remotion.md)를 참고하세요.

### 영상 생성 명령 (컨테이너 내부)

```bash
# scene_plan.json 생성 + 오디오 추출 + 렌더링 (한 번에)
docker compose exec web python utils/remotion_test.py \
  --input utils/test_audio.json \
  --output-dir /data/remotions \
  --output lecture_video.mp4 \
  --ollama-url http://ollama:11434

# scene_plan.json과 오디오 추출만 먼저 확인
docker compose exec web python utils/remotion_test.py \
  --input utils/test_audio.json \
  --output-dir /data/remotions \
  --ollama-url http://ollama:11434 \
  --skip-render
```

### 생성 파이프라인

```
input JSON
  └─→ [ffmpeg] 구간별 오디오 추출 → remotion-project/public/audio/segment_N.aac
  └─→ [Qwen2.5 14B] 씬 계획 생성 → scene_plan.json
          └─→ [Remotion] 비주얼 씬 + 오디오 합성 → output.mp4
```

### 디렉터리 마운트 설정

```yaml
services:
  web:
    volumes:
      - /호스트/오디오/경로:/data/audios:ro
      - /호스트/remotions/경로:/data/remotions

  celery_worker:
    volumes:
      - /호스트/오디오/경로:/data/audios:ro
      - /호스트/remotions/경로:/data/remotions
```

## 기술 스택

| 영역 | 기술 |
|------|------|
| API 서버 | Django 5 + Django REST Framework |
| 비동기 작업 | Celery + Redis |
| LLM 서빙 | Ollama (NVIDIA GPU) |
| 벡터 검색 | FAISS (CPU) + sentence-transformers |
| 영상 처리 | ffmpeg (시스템 바이너리, drawtext 지원) |
| 참고 영상 생성 | Remotion (Node.js 18, React) + Qwen2.5 14B |
| 데이터베이스 | PostgreSQL 16 |
| 리버스 프록시 | Nginx |
| 컨테이너 | Docker Compose (NVIDIA runtime) |

## 프로젝트 구조

```
lectomlv-llm/
├── apps/
│   ├── lectures/                   # 강의 데이터 관리
│   │   ├── models.py               # Lecture, LectureSegment (transcript_corrected 포함)
│   │   ├── serializers.py
│   │   ├── views.py                # CRUD + BulkImport + SegmentTranscriptUpdate
│   │   ├── converter.py            # 외부 JSON → 내부 형식 변환
│   │   ├── tasks.py                # FAISS 인덱싱 Celery 태스크
│   │   └── urls.py
│   ├── llm/                        # LLM 서비스
│   │   ├── models.py               # LLMQuery (search/summary/recommend/manual_clip)
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── tasks.py                # LLM 추론 + 클립/머지 Celery 태스크
│   │   ├── urls.py
│   │   └── services/
│   │       ├── ollama_client.py    # Ollama REST API 클라이언트
│   │       ├── embedding_service.py # FAISS 벡터 임베딩 (싱글턴)
│   │       ├── rag_service.py      # Grounded RAG 파이프라인
│   │       └── video_clip_service.py # ffmpeg 클립 생성·머지
│   └── demo/                       # 데모 대시보드
│       ├── views.py
│       ├── urls.py
│       ├── templates/demo/index.html
│       └── management/commands/
│           ├── seed_lectures.py    # 더미 데이터 생성
│           └── index_lectures.py   # FAISS 인덱싱 실행
├── config/                         # Django / Celery 설정
│   ├── settings.py
│   ├── celery.py
│   ├── urls.py
│   └── wsgi.py
├── docker/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── nginx.conf
│   ├── requirements.txt
│   └── .env.example
├── utils/
│   ├── remotion_test.py            # 오디오+메타데이터 → Remotion 영상 생성 스크립트
│   ├── test_audio.json             # 테스트용 샘플 입력
│   └── remotion-project/           # Remotion React 프로젝트
│       ├── package.json
│       ├── remotion.md             # Remotion 프로젝트 사용법
│       ├── src/
│       │   ├── index.tsx
│       │   ├── Root.tsx
│       │   ├── LectureVideo.tsx    # Series로 씬 순서 배치
│       │   ├── Scene.tsx           # TitleCard / BulletList / Quote + Audio
│       │   └── types.ts
│       └── public/audio/           # ffmpeg 추출 오디오 (자동 생성)
├── docker-compose.yml
├── manage.py
└── README.md
```

## 트러블슈팅

### Ollama 모델이 아직 준비 안 됨

```bash
docker compose logs ollama_init
docker compose exec ollama ollama pull qwen2.5:14b
docker compose exec ollama ollama list
```

### 쿼리가 계속 pending 상태

```bash
docker compose logs -f celery_worker
docker compose restart celery_worker
```

### GPU 관련 오류

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### DB 마이그레이션 문제

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py showmigrations
```

### 전체 초기화 후 재시작

```bash
docker compose down -v
docker compose up -d --build
```

## 라이선스

이 저장소의 **SCH-AICS가 작성한 코드**는 [LICENSE](LICENSE)에 따릅니다.

- **허용된 기업·기관(Authorized Licensee)**: SCH-AICS가 서면(계약·공식 이메일 등)으로 지정한 경우, 약정된 범위에서 **별도 사용료 없이** 사용할 수 있습니다.
- **그 외**: 상업적·기관 이용을 포함해 사용하려면 **별도의 유료·사용 계약**이 필요합니다.

**라이선스·제휴 문의**: 순천향대학교 AICS(AI Convergence Software) 연구실 이메일 또는 담당자 연락처로 문의하시기 바랍니다.

**서드파티 패키지**(예: Ollama, FAISS, sentence-transformers, PyPI 의존성)는 각각 **원저작자의 라이선스**가 적용됩니다. 본 `LICENSE`는 그들의 권리를 대체하지 않습니다.

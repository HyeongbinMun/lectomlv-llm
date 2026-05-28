"""
remotion_test.py
----------------
강의 세그먼트 JSON → 오디오 추출 + Qwen2.5 14B로 scene_plan.json 생성 → npx remotion render 호출

세그먼트 JSON 형식 (둘 다 지원):
  {"start_time": "12:28", "end_time": "12:57", "transcript": "..."}
  {"start": 748.454,      "end": 777.682,       "text": "..."}

source_file 필드로 원본 오디오/영상 경로 지정:
  {"title": "...", "source_file": "/path/to/audio.mp4", "segments": [...]}

사용법:
  python utils/remotion_test.py --input sample_lecture.json
  python utils/remotion_test.py --input sample_lecture.json --output-dir /media/mmlab/hdd/hbmun/remotions
  python utils/remotion_test.py --input sample_lecture.json --skip-render
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2.5:14b"

SCENE_SYSTEM = """\
당신은 강의 영상 시각화 전문가입니다.
강의 세그먼트의 내용을 분석하여 Remotion 영상 씬 계획을 JSON으로 생성합니다.
반드시 유효한 JSON 오브젝트만 출력하고, 설명 텍스트는 절대 포함하지 마세요."""

SCENE_PROMPT_TEMPLATE = """\
다음 강의 세그먼트를 분석하여 씬 계획 JSON을 생성하세요.

세그먼트:
- 시간: {start_time} ~ {end_time} ({duration_sec:.0f}초)
- 내용: {transcript}

아래 JSON 스키마를 그대로 사용하세요 (값만 채우세요):
{{
  "scene_title": "씬 제목 (15자 이내)",
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "layout": "title_card 또는 bullet_list 또는 quote",
  "bg_color": "#16213e",
  "accent_color": "#e94560",
  "bullets": ["핵심 내용 1", "핵심 내용 2", "핵심 내용 3"]
}}

layout 선택 기준:
- title_card: 도입부, 주제 전환, 짧은 개념 설명
- bullet_list: 여러 항목 열거, 단계 설명
- quote: 중요한 정의, 인용구, 핵심 문장

JSON만 출력하세요."""


def parse_time(t: str) -> float:
    parts = t.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def seconds_to_timestr(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:05.2f}"
    return f"{m}:{s:05.2f}"


def normalize_segment(seg: dict) -> dict:
    if "start" in seg and "end" in seg:
        return {
            "start_time": seconds_to_timestr(float(seg["start"])),
            "end_time": seconds_to_timestr(float(seg["end"])),
            "transcript": seg.get("text", seg.get("transcript", "")),
            "_start_sec": float(seg["start"]),
            "_end_sec": float(seg["end"]),
        }
    start_sec = parse_time(seg.get("start_time", "0:00"))
    end_sec = parse_time(seg.get("end_time", "0:00"))
    return {
        "start_time": seg.get("start_time", "0:00"),
        "end_time": seg.get("end_time", "0:00"),
        "transcript": seg.get("transcript", seg.get("text", "")),
        "_start_sec": start_sec,
        "_end_sec": end_sec,
    }


def find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    raise RuntimeError("ffmpeg를 찾을 수 없습니다. ffmpeg를 설치하거나 PATH에 추가하세요.")


def extract_audio_segments(
    segments: list[dict],
    source_file: str,
    audio_dir: Path,
) -> list[str | None]:
    ffmpeg = find_ffmpeg()
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_files: list[str | None] = []

    print(f"\n[audio] 오디오 추출 중: {source_file}")

    for i, seg in enumerate(segments):
        start_sec = seg["_start_sec"]
        duration = seg["_end_sec"] - seg["_start_sec"]
        out_name = f"segment_{i}.aac"
        out_path = audio_dir / out_name

        cmd = [
            ffmpeg,
            "-ss", str(start_sec),
            "-i", source_file,
            "-t", str(max(duration, 0.1)),
            "-vn",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            str(out_path),
        ]

        print(f"  [{i+1}/{len(segments)}] {seg['start_time']} ~ {seg['end_time']} → {out_name}")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0 and out_path.exists():
            audio_files.append(f"audio/{out_name}")
        else:
            print(f"    ⚠ 오디오 추출 실패 (rc={proc.returncode})")
            if proc.stderr:
                print(f"    {proc.stderr[-300:]}")
            audio_files.append(None)

    return audio_files


def call_ollama(prompt: str, system: str, ollama_url: str) -> str:
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{ollama_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read()).get("response", "")


def extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"JSON을 찾을 수 없음:\n{text[:300]}")
    return json.loads(m.group())


def build_scene_plan(
    lecture: dict,
    ollama_url: str,
    audio_files: list[str | None],
) -> dict:
    title = lecture.get("title", "강의")
    segments = lecture.get("segments", [])

    print(f"\n[scene_plan] 총 {len(segments)}개 세그먼트 처리 중...")
    scenes = []

    for i, seg in enumerate(segments):
        seg = normalize_segment(seg)
        start = seg["start_time"]
        end = seg["end_time"]
        transcript = seg["transcript"]
        duration_sec = seg["_end_sec"] - seg["_start_sec"]

        prompt = SCENE_PROMPT_TEMPLATE.format(
            start_time=start,
            end_time=end,
            duration_sec=max(duration_sec, 1),
            transcript=transcript[:500],
        )

        print(f"  [{i+1}/{len(segments)}] {start} ~ {end} — Qwen 호출 중...")
        try:
            raw = call_ollama(prompt, SCENE_SYSTEM, ollama_url)
            scene_meta = extract_json(raw)
        except Exception as exc:
            print(f"    ⚠ 씬 생성 실패: {exc} → 기본값 사용")
            scene_meta = {
                "scene_title": f"세그먼트 {i+1}",
                "keywords": [],
                "layout": "bullet_list",
                "bg_color": "#16213e",
                "accent_color": "#e94560",
                "bullets": [transcript[:80]],
            }

        scene: dict = {
            "segment_index": i,
            "start_time": start,
            "end_time": end,
            "duration_sec": max(duration_sec, 1),
            "transcript": transcript,
            **scene_meta,
        }
        if audio_files[i] is not None:
            scene["audio_file"] = audio_files[i]

        scenes.append(scene)

    return {
        "title": title,
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "scenes": scenes,
    }


def run_remotion(scene_plan_path: Path, output_path: Path, project_dir: Path) -> bool:
    cmd = [
        "npx",
        "remotion",
        "render",
        "LectureVideo",
        str(output_path.resolve()),
        "--props",
        str(scene_plan_path.resolve()),
    ]

    print(f"\n[remotion] 렌더링 시작: {output_path}")
    proc = subprocess.run(cmd, cwd=str(project_dir), capture_output=False)
    return proc.returncode == 0


def make_sample_lecture() -> dict:
    return {
        "title": "인공지능과 기계학습 1강",
        "segments": [
            {
                "start_time": "0:01",
                "end_time": "1:30",
                "transcript": "안녕하세요, 오늘은 인공지능과 기계학습의 차이에 대해 알아보겠습니다.",
            },
            {
                "start_time": "1:30",
                "end_time": "3:00",
                "transcript": "기계학습은 인공지능의 한 분야로, 지도학습, 비지도학습, 강화학습 세 가지 종류가 있습니다.",
            },
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="강의 JSON → 오디오 추출 + scene_plan.json → Remotion 영상")
    parser.add_argument("--input", help="강의 세그먼트 JSON 파일 경로 (없으면 샘플 사용)")
    parser.add_argument("--output", default="lecture_video.mp4", help="출력 영상 파일명")
    parser.add_argument("--output-dir", default=None, help="출력 디렉터리 (scene_plan.json, 영상 저장 위치)")
    parser.add_argument("--source-file", default=None, help="원본 오디오/영상 파일 경로 (JSON의 source_file 필드 덮어씀)")
    parser.add_argument("--ollama-url", default=OLLAMA_URL, help="Ollama 서버 URL")
    parser.add_argument("--skip-render", action="store_true", help="scene_plan.json만 생성하고 렌더링 생략")
    parser.add_argument("--skip-audio", action="store_true", help="오디오 추출 건너뜀")
    args = parser.parse_args()

    utils_dir = Path(__file__).parent
    project_dir = utils_dir / "remotion-project"
    audio_public_dir = project_dir / "public" / "audio"

    output_dir = Path(args.output_dir) if args.output_dir else utils_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    scene_plan_path = output_dir / "scene_plan.json"
    output_path = output_dir / args.output

    if args.input:
        lecture = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        print("[!] --input 미지정 → 샘플 데이터 사용")
        lecture = make_sample_lecture()

    source_file = args.source_file or lecture.get("source_file")
    segments_raw = lecture.get("segments", [])
    segments_norm = [normalize_segment(s) for s in segments_raw]

    audio_files: list[str | None] = [None] * len(segments_norm)
    if source_file and not args.skip_audio:
        if not Path(source_file).exists():
            print(f"[경고] source_file 파일 없음: {source_file} → 오디오 없이 진행")
        else:
            audio_files = extract_audio_segments(segments_norm, source_file, audio_public_dir)
    elif not source_file:
        print("[!] source_file 미지정 → 오디오 없이 비주얼만 생성")

    lecture_for_plan = {**lecture, "segments": segments_raw}
    scene_plan = build_scene_plan(lecture_for_plan, args.ollama_url, audio_files)

    scene_plan_path.write_text(json.dumps(scene_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    has_audio = sum(1 for s in scene_plan["scenes"] if s.get("audio_file"))
    print(f"\n[완료] scene_plan.json 저장: {scene_plan_path}")
    print(f"  씬 수: {len(scene_plan['scenes'])}  오디오 포함: {has_audio}개")

    if args.skip_render:
        print("[--skip-render] 렌더링 건너뜀")
        sys.exit(0)

    if not project_dir.exists():
        print(f"[오류] Remotion 프로젝트 디렉터리 없음: {project_dir}")
        print("  'npm install'을 remotion-project 디렉터리에서 먼저 실행하세요.")
        sys.exit(1)

    ok = run_remotion(scene_plan_path, output_path, project_dir)
    if ok:
        print(f"\n영상 생성 완료: {output_path}")
    else:
        print("\n[오류] Remotion 렌더링 실패 (위 로그 참조)")
        sys.exit(1)


if __name__ == "__main__":
    main()

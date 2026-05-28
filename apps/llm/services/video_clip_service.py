import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from django.conf import settings as django_settings


def _resolve_ffmpeg_bin() -> str:
    system = shutil.which("ffmpeg")
    return system if system else imageio_ffmpeg.get_ffmpeg_exe()


def _check_filter_support(ffmpeg_bin: str, filter_name: str) -> bool:
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-filters"],
            capture_output=True, text=True, timeout=10,
        )
        return filter_name in proc.stdout
    except Exception:
        return False


_FFMPEG_BIN = _resolve_ffmpeg_bin()
_DRAWTEXT_SUPPORTED = _check_filter_support(_FFMPEG_BIN, "drawtext")

logger = logging.getLogger(__name__)
logger.debug("ffmpeg 바이너리: %s (drawtext=%s)", _FFMPEG_BIN, _DRAWTEXT_SUPPORTED)

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}

_TIME_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)$")

ASPECT_RATIO_PRESETS: dict[str, tuple[int, int]] = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "1:1":  (720, 720),
    "4:3":  (960, 720),
}


def _parse_time_to_seconds(time_str: str) -> float:
    m = _TIME_RE.match(time_str.strip())
    if not m:
        raise ValueError(f"인식할 수 없는 시간 형식: {time_str!r}")
    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2))
    seconds = float(m.group(3))
    return hours * 3600 + minutes * 60 + seconds


def _is_video_file(source_file: str) -> bool:
    return Path(source_file).suffix.lower() in VIDEO_EXTENSIONS


def _find_video_path(source_file: str, video_dir: Path) -> Path | None:
    exact = video_dir / source_file
    if exact.exists():
        return exact
    stem_lower = Path(source_file).stem.lower()
    for candidate in video_dir.iterdir():
        if candidate.is_file() and candidate.stem.lower() == stem_lower:
            return candidate
    return None


def _safe_filename(time_str: str) -> str:
    return time_str.replace(":", "-").replace(".", "_")


def _ass_timestamp(seconds: float) -> str:
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _split_transcript_lines(transcript: str, max_chars: int = 28) -> list[str]:
    result: list[str] = []
    for manual_line in transcript.split("\n"):
        words = manual_line.split()
        if not words:
            continue
        current: list[str] = []
        cur_len = 0
        for word in words:
            add = len(word) + (1 if current else 0)
            if cur_len + add > max_chars and current:
                result.append(" ".join(current))
                current = [word]
                cur_len = len(word)
            else:
                current.append(word)
                cur_len += add
        if current:
            result.append(" ".join(current))
    return result


_DRAWTEXT_FONT = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"


def _escape_drawtext(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\\'")
    text = text.replace("%", "\\%")
    return text


def _make_ass(transcript: str, duration: float) -> str:
    lines = _split_transcript_lines(transcript)
    if not lines:
        return ""

    chunks = ["\\N".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
    chunk_dur = duration / len(chunks)

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        "PlayResX: 1280\n"
        "PlayResY: 720\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,WenQuanYi Micro Hei,30,"
        "&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,"
        "0,0,0,0,100,100,0,0,1,3,1,2,10,10,40,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    events = []
    for i, chunk in enumerate(chunks):
        start = i * chunk_dur
        end   = (i + 1) * chunk_dur
        events.append(
            f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(end)},"
            f"Default,,0,0,0,,{chunk}"
        )

    return header + "\n".join(events) + "\n"


_TITLE_X_EXPR: dict[str, str] = {
    "left":   "15",
    "center": "(w-tw)/2",
    "right":  "w-tw-15",
}


def _build_vf_filter(
    aspect_ratio: str | None,
    srt_path: str | None,
    lecture_title: str | None = None,
    title_position: str = "right",
) -> list[str]:
    filters: list[str] = []

    if aspect_ratio and aspect_ratio in ASPECT_RATIO_PRESETS:
        w, h = ASPECT_RATIO_PRESETS[aspect_ratio]
        filters.append(
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
        )

    if srt_path:
        escaped = srt_path.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
        filters.append(
            f"subtitles='{escaped}':fontsdir=/usr/share/fonts/truetype/wqy"
        )

    if lecture_title and _DRAWTEXT_SUPPORTED:
        title_text = _escape_drawtext(lecture_title[:40])
        font_part  = f"fontfile={_DRAWTEXT_FONT}:" if Path(_DRAWTEXT_FONT).exists() else ""
        x_expr     = _TITLE_X_EXPR.get(title_position, _TITLE_X_EXPR["right"])
        filters.append(
            f"drawtext={font_part}text='{title_text}':"
            f"x={x_expr}:y=18:fontsize=30:fontcolor=white:"
            f"box=1:boxcolor=black@0.55:boxborderw=8"
        )
    elif lecture_title and not _DRAWTEXT_SUPPORTED:
        logger.warning("drawtext 필터 미지원 ffmpeg — 강의명 오버레이 생략: %s", _FFMPEG_BIN)

    if not filters:
        return []

    return ["-vf", ",".join(filters)]


class VideoClipService:
    def __init__(self):
        self.video_dir = Path(getattr(django_settings, "VIDEO_SOURCE_DIR", "/data/videos"))
        self.clips_dir = Path(getattr(django_settings, "VIDEO_CLIPS_DIR", "/data/clips"))
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    def make_clips(
        self,
        cited_sources: list[dict],
        aspect_ratio: str | None = None,
        with_subtitles: bool = True,
        with_title: bool = False,
        title_position: str = "right",
        start_offset_sec: float = 0.0,
        end_offset_sec: float = 0.0,
    ) -> list[dict]:
        results = []
        for src in cited_sources:
            result = self._process_one(
                src,
                aspect_ratio=aspect_ratio,
                with_subtitles=with_subtitles,
                with_title=with_title,
                title_position=title_position,
                start_offset_sec=start_offset_sec,
                end_offset_sec=end_offset_sec,
            )
            if result is not None:
                results.append(result)
        return results

    def merge_clips(
        self,
        video_clips: list[dict],
        query_id: int,
        selected_filenames: list[str] | None = None,
    ) -> dict:
        if selected_filenames is not None:
            order_map = {fn: i for i, fn in enumerate(selected_filenames)}
            success_clips = [
                c for c in video_clips
                if c.get("clip_filename") in order_map
            ]
            success_clips.sort(key=lambda c: order_map[c["clip_filename"]])
        else:
            success_clips = [c for c in video_clips if c.get("status") == "success" and c.get("clip_filename")]

        if not success_clips:
            return {"status": "nothing_to_merge", "error": "성공한 클립이 없습니다."}

        merged_filename = f"merged_{query_id}.mp4"
        output_path = self.clips_dir / merged_filename

        if len(success_clips) == 1:
            import shutil
            src = self.clips_dir / success_clips[0]["clip_filename"]
            if src.exists():
                shutil.copy2(src, output_path)
                return {"merged_filename": merged_filename, "merged_url": f"/clips/{merged_filename}", "status": "success"}
            return {"status": "failed", "error": "원본 클립 파일을 찾을 수 없음"}

        filelist_path = self.clips_dir / f"_filelist_{query_id}.txt"
        try:
            lines = []
            for clip in success_clips:
                clip_path = self.clips_dir / clip["clip_filename"]
                if clip_path.exists():
                    lines.append(f"file '{clip_path}'")
            if not lines:
                return {"status": "failed", "error": "클립 파일이 존재하지 않습니다."}

            filelist_path.write_text("\n".join(lines), encoding="utf-8")
            ok = self._run_concat(filelist_path, output_path)
        finally:
            if filelist_path.exists():
                filelist_path.unlink()

        if ok:
            return {"merged_filename": merged_filename, "merged_url": f"/clips/{merged_filename}", "status": "success"}
        return {"status": "failed", "error": "ffmpeg concat 실패 (로그 확인)"}

    def _process_one(
        self,
        src: dict,
        aspect_ratio: str | None = None,
        with_subtitles: bool = True,
        with_title: bool = False,
        title_position: str = "right",
        start_offset_sec: float = 0.0,
        end_offset_sec: float = 0.0,
    ) -> dict | None:
        source_file   = src.get("source_file", "")
        start_time    = src.get("start_time", "")
        end_time      = src.get("end_time", "")
        tag           = src.get("citation_tag", "")
        lecture_title = (src.get("lecture_title") or "").strip() if with_title else ""

        transcript = src.get("transcript_corrected", "")
        if not transcript and src.get("segment_id"):
            try:
                from apps.lectures.models import LectureSegment
                seg = LectureSegment.objects.only("transcript_corrected").get(id=src["segment_id"])
                transcript = seg.transcript_corrected
            except Exception:
                pass
        if not transcript:
            transcript = src.get("transcript", "")

        if not _is_video_file(source_file):
            return None

        base = {
            "citation_tag": tag,
            "source_file":  source_file,
            "start_time":   start_time,
            "end_time":     end_time,
        }

        video_path = _find_video_path(source_file, self.video_dir)
        if video_path is None:
            logger.warning("원본 영상을 찾을 수 없음: %s (%s)", source_file, self.video_dir)
            return {**base, "status": "not_found", "error": f"{self.video_dir} 에서 파일을 찾을 수 없음"}

        try:
            start_sec = _parse_time_to_seconds(start_time)
            end_sec   = _parse_time_to_seconds(end_time)
        except ValueError as exc:
            return {**base, "status": "failed", "error": str(exc)}

        start_offset_sec = float(src.get("start_offset_sec", start_offset_sec))
        end_offset_sec   = float(src.get("end_offset_sec",   end_offset_sec))

        if start_offset_sec or end_offset_sec:
            start_sec = max(0.0, start_sec + start_offset_sec)
            end_sec   = max(start_sec + 0.5, end_sec + end_offset_sec)

        if end_sec <= start_sec:
            return {**base, "status": "failed", "error": "end_time 이 start_time 보다 앞서거나 같음"}

        duration = end_sec - start_sec
        clip_filename = self._build_clip_filename(
            source_file, start_time, end_time, aspect_ratio,
            start_offset_sec, end_offset_sec, with_title, title_position,
        )
        output_path   = self.clips_dir / clip_filename

        if output_path.exists():
            logger.info("클립 이미 존재, 재사용: %s", clip_filename)
            return {**base, "clip_filename": clip_filename, "clip_url": f"/clips/{clip_filename}", "status": "success"}

        srt_tmp = None
        if with_subtitles and transcript.strip():
            ass_content = _make_ass(transcript, duration)
            if ass_content:
                try:
                    tmp = tempfile.NamedTemporaryFile(
                        suffix=".ass", mode="w", encoding="utf-8", delete=False
                    )
                    tmp.write(ass_content)
                    tmp.close()
                    srt_tmp = tmp.name
                except Exception as exc:
                    logger.warning("ASS 자막 생성 실패: %s", exc)

        vf_args = _build_vf_filter(aspect_ratio, srt_tmp, lecture_title or None, title_position)

        try:
            success = self._run_ffmpeg(video_path, start_sec, duration, output_path, vf_args)
        finally:
            if srt_tmp:
                try:
                    Path(srt_tmp).unlink()
                except OSError:
                    pass

        if success:
            return {**base, "clip_filename": clip_filename, "clip_url": f"/clips/{clip_filename}", "status": "success"}
        return {**base, "status": "failed", "error": "ffmpeg 실행 실패 (로그 확인)"}

    @staticmethod
    def _build_clip_filename(
        source_file: str,
        start_time: str,
        end_time: str,
        aspect_ratio: str | None,
        start_offset_sec: float = 0.0,
        end_offset_sec: float = 0.0,
        with_title: bool = False,
        title_position: str = "right",
    ) -> str:
        stem  = Path(source_file).stem
        s     = _safe_filename(start_time)
        e     = _safe_filename(end_time)
        ratio = f"_{aspect_ratio.replace(':', 'x')}" if aspect_ratio else ""
        offset = ""
        if start_offset_sec:
            offset += f"_ss{start_offset_sec:+.0f}"
        if end_offset_sec:
            offset += f"_se{end_offset_sec:+.0f}"
        title_sfx = ""
        if with_title:
            pos_short = {"left": "l", "center": "c", "right": "r"}.get(title_position, "r")
            title_sfx = f"_t{pos_short}"
        return f"{stem[:75]}_{s}_{e}{ratio}{offset}{title_sfx}.mp4"

    @staticmethod
    def _run_ffmpeg(
        input_path: Path,
        start_sec: float,
        duration: float,
        output_path: Path,
        vf_args: list[str],
    ) -> bool:
        if vf_args:
            cmd = [
                _FFMPEG_BIN,
                "-ss", str(start_sec),
                "-i", str(input_path),
                "-t", str(duration),
                *vf_args,
                "-c:v", "libx264",
                "-crf", "23",
                "-preset", "fast",
                "-c:a", "aac",
                "-b:a", "128k",
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(output_path),
            ]
        else:
            cmd = [
                _FFMPEG_BIN,
                "-ss", str(start_sec),
                "-i", str(input_path),
                "-t", str(duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(output_path),
            ]

        logger.info("ffmpeg (%s): %s", "encode" if vf_args else "copy", output_path.name)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                logger.error("ffmpeg 오류 (rc=%d):\n%s", proc.returncode, proc.stderr[-2000:])
                return False
            logger.info("클립 생성 완료: %s", output_path.name)
            return True
        except subprocess.TimeoutExpired:
            logger.error("ffmpeg 타임아웃: %s", input_path.name)
            return False
        except FileNotFoundError:
            logger.error("ffmpeg 바이너리를 찾을 수 없음: %s", _FFMPEG_BIN)
            return False

    @staticmethod
    def _run_concat(filelist_path: Path, output_path: Path) -> bool:
        cmd = [
            _FFMPEG_BIN,
            "-f", "concat",
            "-safe", "0",
            "-i", str(filelist_path),
            "-c", "copy",
            "-y",
            str(output_path),
        ]
        logger.info("ffmpeg concat → %s", output_path.name)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                logger.error("ffmpeg concat 오류 (rc=%d):\n%s", proc.returncode, proc.stderr[-2000:])
                return False
            logger.info("머지 완료: %s", output_path.name)
            return True
        except subprocess.TimeoutExpired:
            logger.error("ffmpeg concat 타임아웃")
            return False
        except FileNotFoundError:
            logger.error("ffmpeg 바이너리를 찾을 수 없음: %s", _FFMPEG_BIN)
            return False

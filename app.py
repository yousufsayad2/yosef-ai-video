import os
import json
import time
import tempfile
import subprocess
from pathlib import Path

import requests
import streamlit as st
import imageio_ffmpeg

st.set_page_config(
    page_title="Yosef AI Video",
    page_icon="🎬",
    layout="centered",
)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "veo-3.1-generate-preview"


def get_secret(name):
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


def clean_key(key):
    return key.strip().strip('"').strip("'")


def api_error(response):
    try:
        data = response.json()
        return data.get("error", {}).get("message", response.text)
    except Exception:
        return response.text


def start_veo(api_key, prompt, model):
    url = f"{BASE_URL}/models/{model}:predictLongRunning"
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "aspectRatio": "9:16",
            "resolution": "720p",
            "numberOfVideos": 1,
        },
    }

    r = requests.post(
        url,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )

    if not r.ok:
        raise RuntimeError(f"Veo HTTP {r.status_code}: {api_error(r)}")

    data = r.json()
    operation_name = data.get("name")
    if not operation_name:
        raise RuntimeError(f"Veo لم يرجع اسم العملية: {data}")

    return operation_name


def wait_for_video(api_key, operation_name, status_box, timeout_seconds=900):
    url = f"{BASE_URL}/{operation_name}"
    started = time.time()

    while True:
        if time.time() - started > timeout_seconds:
            raise RuntimeError("انتهى وقت انتظار توليد المشهد. جرّب مرة أخرى.")

        r = requests.get(
            url,
            headers={"x-goog-api-key": api_key},
            timeout=60,
        )

        if not r.ok:
            raise RuntimeError(f"Veo status HTTP {r.status_code}: {api_error(r)}")

        data = r.json()

        if data.get("done") is True:
            if "error" in data:
                err = data["error"]
                raise RuntimeError(
                    f"Veo فشل: {err.get('message', json.dumps(err, ensure_ascii=False))}"
                )

            try:
                video_uri = (
                    data["response"]
                    ["generateVideoResponse"]
                    ["generatedSamples"][0]
                    ["video"]
                    ["uri"]
                )
                return video_uri
            except (KeyError, IndexError, TypeError):
                raise RuntimeError(f"Veo أنهى العملية لكن لم يرجع رابط الفيديو: {data}")

        status_box.info("⏳ Veo بيولّد المشهد... استنى شوية.")
        time.sleep(10)


def download_video(api_key, video_uri, output_path):
    r = requests.get(
        video_uri,
        headers={"x-goog-api-key": api_key},
        timeout=180,
        allow_redirects=True,
    )

    if not r.ok:
        raise RuntimeError(f"فشل تحميل الفيديو: HTTP {r.status_code}: {api_error(r)}")

    Path(output_path).write_bytes(r.content)


def make_scene_prompts(idea, style):
    base = f"""
Create a cinematic vertical 9:16 live-action video about this story:
{idea}

Style: {style}.
Photorealistic human characters, natural body movement, realistic facial expressions,
realistic physics, cinematic lighting, shallow depth of field, detailed environment.
Keep the main character visually consistent within this scene.
No subtitles, no captions, no text on screen, no logos, no watermark.
The video must contain visible motion: walking, hand movement, facial expressions,
camera movement, environmental motion, and realistic interaction.
Native synchronized ambient sound and dialogue when appropriate.
"""

    return [
        base + """
Scene 1: Establishing shot. Show the main character and environment.
The character is beginning the journey, looking focused and slightly uncertain.
Slow cinematic camera push-in, natural movement and atmospheric motion.
""",
        base + """
Scene 2: The character actively faces the first challenge.
Show clear physical action and emotional reaction. Use a moving tracking camera.
Include realistic interaction with objects and surroundings.
""",
        base + """
Scene 3: The character struggles and almost gives up.
Close-up on realistic facial expression, then a wider moving shot showing the action.
Natural hand gestures and body movement. Dramatic cinematic lighting.
""",
        base + """
Scene 4: Turning point. The character gets a new idea and starts working seriously.
Show hands moving, tools or computer interaction if relevant, with dynamic camera motion.
Make the scene feel energetic and purposeful.
""",
        base + """
Scene 5: Progress and success. The character demonstrates the result.
Use a smooth cinematic tracking shot and visible reactions from other people if relevant.
Make the environment feel alive and realistic.
""",
        base + """
Scene 6: Strong emotional ending. The character looks at the finished achievement
with confidence. Camera slowly pulls back while the environment continues moving.
Cinematic final shot, realistic human motion, inspiring atmosphere.
""",
    ]


def ffmpeg_path():
    return imageio_ffmpeg.get_ffmpeg_exe()


def concat_videos(paths, output_path, target_seconds):
    ffmpeg = ffmpeg_path()

    # Normalize each clip to the same portrait format before concatenation.
    normalized = []
    temp_dir = Path(tempfile.mkdtemp(prefix="yosef_video_"))

    try:
        for i, src in enumerate(paths):
            dst = temp_dir / f"clip_{i}.mp4"
            cmd = [
                ffmpeg, "-y",
                "-i", str(src),
                "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,"
                       "pad=720:1280:(ow-iw)/2:(oh-ih)/2",
                "-r", "24",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-ar", "48000",
                "-ac", "2",
                str(dst),
            ]
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if result.returncode != 0:
                raise RuntimeError("فشل تجهيز أحد مشاهد الفيديو.")
            normalized.append(dst)

        concat_file = temp_dir / "concat.txt"
        concat_file.write_text(
            "".join(f"file '{p.as_posix()}'\n" for p in normalized),
            encoding="utf-8",
        )

        # Re-encode final output and trim to requested duration.
        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-t", str(target_seconds),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(output_path),
        ]

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode != 0:
            raise RuntimeError("فشل تجميع المشاهد في فيديو واحد.")

    finally:
        # Keep final output; remove only intermediate files.
        for p in temp_dir.glob("*"):
            try:
                p.unlink()
            except Exception:
                pass
        try:
            temp_dir.rmdir()
        except Exception:
            pass


st.title("🎬 Yosef AI Video")
st.caption("حوّل فكرتك إلى فيديو AI حقيقي بالحركة والصوت باستخدام Veo 3.1")

api_key = st.text_input(
    "🔑 Gemini API Key",
    value=get_secret("GEMINI_API_KEY"),
    type="password",
    placeholder="الصق مفتاح Gemini هنا",
)

model = st.selectbox(
    "🎥 Video Model",
    [
        "veo-3.1-generate-preview",
        "veo-3.1-fast-generate-preview",
        "veo-3.1-lite-generate-preview",
    ],
)

idea = st.text_area(
    "💡 فكرة الفيديو",
    placeholder="مثال: شاب مصري يبدأ من الصفر في تعلم الذكاء الاصطناعي، يواجه الفشل ثم ينجح في بناء أول مشروع له.",
    height=150,
)

duration = st.slider(
    "⏱️ مدة الفيديو المستهدفة",
    min_value=8,
    max_value=48,
    value=24,
    step=4,
    help="Veo يولّد مقاطع 8 ثوانٍ؛ الموقع يجمع عدة مقاطع ويقص النتيجة للمدة المطلوبة.",
)

style = st.selectbox(
    "🎨 الأسلوب",
    [
        "Cinematic",
        "Realistic",
        "Documentary",
        "Action",
        "Inspirational",
        "Futuristic",
    ],
)

st.info(
    "🎬 كل مشهد هنا فيديو AI حقيقي بحركة وصوت مولّدين من Veo، وليس صورة ثابتة."
)

if st.button("🚀 إنشاء الفيديو", use_container_width=True):
    api_key = clean_key(api_key)

    if not api_key:
        st.error("❌ ضع Gemini API Key.")
        st.stop()

    if not idea.strip():
        st.error("❌ اكتب فكرة الفيديو أولًا.")
        st.stop()

    # 8-second Veo clips; generate enough clips to cover the requested duration.
    scene_count = (duration + 7) // 8
    scene_count = max(1, min(scene_count, 6))
    prompts = make_scene_prompts(idea.strip(), style)[:scene_count]

    progress = st.progress(0)
    status = st.empty()
    scene_paths = []

    try:
        work_dir = Path(tempfile.mkdtemp(prefix="yosef_veo_"))

        for i, prompt in enumerate(prompts, start=1):
            status.info(f"🎬 المشهد {i}/{scene_count}: بدء التوليد...")
            operation = start_veo(api_key, prompt, model)

            status.info(f"⏳ المشهد {i}/{scene_count}: Veo بيولّد الفيديو والصوت...")
            video_uri = wait_for_video(api_key, operation, status)

            scene_path = work_dir / f"scene_{i}.mp4"
            status.info(f"⬇️ المشهد {i}/{scene_count}: تحميل الفيديو...")
            download_video(api_key, video_uri, scene_path)

            scene_paths.append(scene_path)
            progress.progress(i / scene_count)

        status.info("🎞️ جاري تجميع كل المشاهد في فيديو واحد...")
        final_path = work_dir / "yosef_ai_video.mp4"
        concat_videos(scene_paths, final_path, duration)

        status.success("✅ الفيديو خلص!")
        st.video(str(final_path))

        st.download_button(
            "⬇️ تحميل الفيديو",
            data=final_path.read_bytes(),
            file_name="yosef_ai_video.mp4",
            mime="video/mp4",
            use_container_width=True,
        )

    except Exception as e:
        st.error(str(e))
        st.caption("لو الخطأ متعلق بالصلاحيات أو الحصة، غالبًا حساب Google API يحتاج تفعيل/رصيد مناسب لـ Veo.")

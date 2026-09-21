
import os
import time
import tempfile
import subprocess
from pathlib import Path

import streamlit as st
from gradio_client import Client
from gtts import gTTS
import imageio_ffmpeg

st.set_page_config(page_title="Yosef AI Video", page_icon="🎬", layout="centered")

st.title("🎬 Yosef AI Video")
st.caption("متحرك + تعليق صوتي AI حوّل وصفك إلى فيديو")

prompt = st.text_area(
    "🎥 وصف الفيديو",
    height=180,
    placeholder="اكتب بالتفصيل ماذا تريد أن يحدث في الفيديو..."
)

voice_text = st.text_area(
    "🎙️ الكلام اللي يتقال في الفيديو (اختياري)",
    height=120,
    placeholder="اكتب التعليق الصوتي بالعربي..."
)

resolution = st.selectbox(
    "📐 جودة/مقاس الفيديو",
    ["1280*720", "960*960", "720*1280", "1088*832", "832*1088"],
    index=0
)

watermark = st.checkbox("إضافة علامة Wan2.1", value=False)

def find_video(value):
    if value is None:
        return None

    if isinstance(value, str):
        if value.startswith(("http://", "https://")) or os.path.exists(value):
            return value
        return None

    if isinstance(value, dict):
        for k in ("video", "url", "path", "file", "value"):
            if k in value:
                found = find_video(value[k])
                if found:
                    return found

    if isinstance(value, (list, tuple)):
        for item in value:
            found = find_video(item)
            if found:
                return found

    for attr in ("url", "path", "name"):
        try:
            v = getattr(value, attr)
            if isinstance(v, str) and (
                v.startswith(("http://", "https://")) or os.path.exists(v)
            ):
                return v
        except Exception:
            pass

    return None

def localize_video(video):
    if not video:
        return None

    if isinstance(video, str) and video.startswith(("http://", "https://")):
        import requests
        r = requests.get(video, timeout=180)
        r.raise_for_status()
        p = Path(tempfile.gettempdir()) / "yosef_wan21.mp4"
        p.write_bytes(r.content)
        return str(p)

    return video

def generate_wan_video(prompt_text, size, watermark_value):
    # Public official Wan2.1 Space.
    client = Client("Wan-AI/Wan2.1")

    # Submit the async generation task.
    submitted = client.predict(
        prompt_text,
        size,
        watermark_value,
        -1,
        api_name="/t2v_generation_async"
    )

    if not isinstance(submitted, (list, tuple)) or not submitted:
        raise RuntimeError(f"استجابة غير متوقعة من Wan2.1: {submitted}")

    task_id = submitted[0]
    status = submitted[1] if len(submitted) > 1 else False

    if not task_id:
        raise RuntimeError(
            "Wan2.1 رفض الطلب أو الـ Space مشغول حاليًا. جرّب مرة أخرى بعد قليل."
        )

    # The official Space checks the task using status_refresh(task_id, task, status).
    # Keep polling for up to 15 minutes.
    for _ in range(180):
        time.sleep(5)

        try:
            result = client.predict(
                task_id,
                "t2v",
                status,
                api_name="/status_refresh"
            )
        except Exception:
            continue

        video = find_video(result)
        if video:
            return localize_video(video)

        # status_refresh returns a status flag in the second item in current versions.
        if isinstance(result, (list, tuple)) and len(result) > 1:
            try:
                status = bool(result[1])
            except Exception:
                pass

    raise TimeoutError(
        "الفيديو لسه في طابور Wan2.1 بعد 15 دقيقة. جرّب الطلب مرة أخرى لاحقًا."
    )

def add_arabic_voice(video_path, text):
    if not text.strip():
        return video_path

    work = Path(tempfile.mkdtemp(prefix="yosef_voice_"))
    voice = work / "voice.mp3"
    final = work / "yosef_ai_final.mp4"

    gTTS(text=text, lang="ar").save(str(voice))

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    cmd = [
        ffmpeg, "-y",
        "-i", str(video_path),
        "-i", str(voice),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(final),
    ]

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    return str(final)

if st.button("🚀 إنشاء الفيديو", type="primary", use_container_width=True):
    if not prompt.strip():
        st.warning("اكتب وصف الفيديو الأول.")
        st.stop()

    try:
        with st.spinner("🎬 جاري إنشاء الفيديو المتحرك... قد يستغرق عدة دقائق حسب ضغط الـ Space"):
            video = generate_wan_video(
                prompt.strip(),
                resolution,
                watermark
            )

            if voice_text.strip():
                video = add_arabic_voice(video, voice_text.strip())

        st.success("✅ تم إنشاء الفيديو بنجاح!")
        st.video(video)

        with open(video, "rb") as f:
            st.download_button(
                "⬇️ تحميل الفيديو",
                data=f,
                file_name="yosef_ai_video.mp4",
                mime="video/mp4",
                use_container_width=True
            )

    except Exception as e:
        st.error("❌ حصل خطأ أثناء توليد الفيديو.")
        st.code(str(e))

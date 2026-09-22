import os
import tempfile
import subprocess
from pathlib import Path

import streamlit as st
from gradio_client import Client
from gtts import gTTS
import imageio_ffmpeg

st.set_page_config(page_title="Yosef AI Video", page_icon="🎬", layout="centered")

st.title("🎬 Yosef AI Video")
st.caption("فيديو AI متحرك + تعليق صوتي عربي")

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

duration = st.selectbox("⏱️ مدة الفيديو", [2, 3, 5], index=0)

def find_video(value):
    if isinstance(value, str):
        if value.startswith(("http://", "https://")) or os.path.exists(value):
            return value

    if isinstance(value, dict):
        for key in ("video", "path", "url", "file", "value"):
            if key in value:
                found = find_video(value[key])
                if found:
                    return found

    if isinstance(value, (list, tuple)):
        for item in value:
            found = find_video(item)
            if found:
                return found

    return None

def get_video(prompt_text, seconds):
    # Verified current public ZeroGPU Text-to-Video Space.
    # It exposes Text-to-Video directly and does not require the
    # old DashScope API used by Wan-AI/Wan2.1.
    client = Client("Pyramid-Flow/pyramid-flow", httpx_kwargs={"timeout": 900})

    job = client.submit(
        prompt_text,
        None,
        seconds,
        9.0,
        5.0,
        api_name="/generate_video"
    )
    result = job.result(timeout=900)

    video = find_video(result)
    if not video:
        raise RuntimeError(
            f"لم يرجع Pyramid Flow ملف فيديو. الاستجابة: {str(result)[:1200]}"
        )

    if video.startswith(("http://", "https://")):
        import requests
        response = requests.get(video, timeout=240)
        response.raise_for_status()
        local = Path(tempfile.gettempdir()) / "yosef_pyramid.mp4"
        local.write_bytes(response.content)
        return str(local)

    return video

def add_voice(video_path, text):
    if not text.strip():
        return video_path

    work = Path(tempfile.mkdtemp(prefix="yosef_voice_"))
    voice = work / "voice.mp3"
    final = work / "yosef_ai_final.mp4"

    gTTS(text=text.strip(), lang="ar").save(str(voice))
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    subprocess.run(
        [
            ffmpeg, "-y",
            "-i", str(video_path),
            "-i", str(voice),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(final),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return str(final)

if st.button("🚀 إنشاء الفيديو", type="primary", use_container_width=True):
    if not prompt.strip():
        st.warning("اكتب وصف الفيديو الأول.")
        st.stop()

    try:
        with st.spinner(
            "🎬 جاري إنشاء الفيديو المتحرك... "
            "سيحتاج وقتًا لأن التوليد يتم على GPU مجاني."
        ):
            video = get_video(prompt.strip(), duration)

            if voice_text.strip():
                video = add_voice(video, voice_text)

        st.success("🎉 تم إنشاء الفيديو بنجاح!")
        st.video(video)

        with open(video, "rb") as f:
            st.download_button(
                "⬇️ تحميل الفيديو",
                data=f,
                file_name="yosef_ai_video.mp4",
                mime="video/mp4",
                use_container_width=True,
            )

    except Exception as e:
        st.error("❌ حصل خطأ أثناء توليد الفيديو.")
        st.code(str(e))

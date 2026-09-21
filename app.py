
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

def get_video(result):
    if isinstance(result, str):
        return result
    if isinstance(result, (list, tuple)):
        for x in result:
            if isinstance(x, str) and (
                x.startswith("http://") or
                x.startswith("https://") or
                os.path.exists(x)
            ):
                return x
    if isinstance(result, dict):
        for k in ("video", "url", "path"):
            x = result.get(k)
            if isinstance(x, str):
                return x
    return None

def generate_video(prompt_text, size, watermark_value):
    client = Client("Wan-AI/Wan2.1")

    # The current official Wan2.1 Space exposes this synchronous
    # text-to-video endpoint. It returns the generated video URL.
    result = client.predict(
        prompt_text,
        size,
        watermark_value,
        -1,
        api_name="/t2v_generation"
    )

    video = get_video(result)
    if not video:
        raise RuntimeError(f"لم يرجع Wan2.1 رابط فيديو. الاستجابة: {result}")

    if video.startswith(("http://", "https://")):
        import requests
        r = requests.get(video, timeout=180)
        r.raise_for_status()
        p = Path(tempfile.gettempdir()) / "yosef_wan21.mp4"
        p.write_bytes(r.content)
        return str(p)

    return video

def add_voice(video_path, text):
    if not text.strip():
        return video_path

    work = Path(tempfile.mkdtemp(prefix="yosef_voice_"))
    voice = work / "voice.mp3"
    final = work / "yosef_ai_final.mp4"

    gTTS(text=text, lang="ar").save(str(voice))
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
            "قد يستغرق عدة دقائق حسب ضغط Wan2.1"
        ):
            video = generate_video(prompt.strip(), resolution, watermark)

            if voice_text.strip():
                video = add_voice(video, voice_text.strip())

        st.success("✅ تم إنشاء الفيديو بنجاح!")
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
        st.info(
            "لو ظهر أن الـ Space مشغول أو عليه ضغط، جرّب مرة أخرى بعد قليل."
        )

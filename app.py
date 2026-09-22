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

resolution = st.selectbox(
    "📐 جودة/مقاس الفيديو",
    ["480*832", "512*768", "384*640"],
    index=0
)

watermark = st.checkbox("إضافة علامة Wan2.1", value=False)

def extract_file(value):
    if value is None:
        return None

    if isinstance(value, str):
        if value.startswith(("http://", "https://")) or os.path.exists(value):
            return value

    if isinstance(value, dict):
        for key in ("video", "path", "url", "file", "value", "name"):
            if key in value:
                found = extract_file(value[key])
                if found:
                    return found

    if isinstance(value, (list, tuple)):
        for item in value:
            found = extract_file(item)
            if found:
                return found

    return None

def get_video():
    # This Space is currently running on Hugging Face ZeroGPU.
    # It is a direct text-to-video Space and does NOT use the
    # old Wan2.1 DashScope task/status system.
    client = Client("multimodalart/wan2-1-fast")

    height, width = map(int, resolution.split("*"))

    negative_prompt = (
        "static image, still frame, blurry, low quality, "
        "deformed face, distorted body, extra fingers, bad hands, "
        "flicker, duplicate people, text, subtitles"
    )

    # 25 frames at 15 fps ≈ 1.7 seconds.
    # 4 steps is the fast configuration used by the Space.
    result = client.predict(
        prompt.strip(),
        negative_prompt,
        height,
        width,
        25,
        5.0,
        4,
        15,
        api_name="/generate_video"
    )

    video = extract_file(result)

    if not video:
        raise RuntimeError(
            f"لم يرجع الـ Space ملف فيديو. الاستجابة: {str(result)[:1200]}"
        )

    if video.startswith(("http://", "https://")):
        import requests
        r = requests.get(video, timeout=180)
        r.raise_for_status()
        p = Path(tempfile.gettempdir()) / "yosef_ai_video.mp4"
        p.write_bytes(r.content)
        return str(p)

    return video

def add_arabic_voice(video_path, text):
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
            "النسخة دي سريعة نسبيًا، استنى لحد ما النتيجة تظهر."
        ):
            video = get_video()

            if voice_text.strip():
                video = add_arabic_voice(video, voice_text.strip())

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
        st.info(
            "لو ظهر أن الـ Space مشغول، جرّب مرة أخرى بعد قليل."
        )

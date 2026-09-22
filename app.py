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
    ["1280*720", "960*960", "720*1280"],
    index=0
)

watermark = st.checkbox("إضافة علامة Wan2.1", value=False)

def extract_video(value):
    if value is None:
        return None

    if isinstance(value, str):
        if value.startswith(("http://", "https://")) or os.path.exists(value):
            return value

    if isinstance(value, dict):
        if value.get("__type__") == "update":
            return extract_video(value.get("value"))

        for key in ("video", "path", "url", "file", "value", "name"):
            if key in value:
                found = extract_video(value[key])
                if found:
                    return found

    if isinstance(value, (list, tuple)):
        for item in value:
            found = extract_video(item)
            if found:
                return found

    for attr in ("path", "url", "name", "value"):
        try:
            x = getattr(value, attr)
            if isinstance(x, str) and (
                x.startswith(("http://", "https://")) or os.path.exists(x)
            ):
                return x
        except Exception:
            pass

    return None

def make_local(video):
    if not video:
        return None

    if video.startswith(("http://", "https://")):
        import requests
        r = requests.get(video, timeout=240)
        r.raise_for_status()
        p = Path(tempfile.gettempdir()) / "yosef_wan22.mp4"
        p.write_bytes(r.content)
        return str(p)

    return video

def generate_wan22(text, size):
    """
    Use Wan-AI/Wan-2.2-5B direct generation.
    This avoids Wan2.1's hidden Gradio State/task polling.
    """
    client = Client("Wan-AI/Wan-2.2-5B")

    h, w = map(int, size.split("*"))

    # Wan-2.2-5B's public Gradio endpoint:
    # image, prompt, height, width, duration_seconds,
    # sampling_steps, guide_scale, shift, seed
    result = client.predict(
        None,
        text,
        h,
        w,
        3.0,
        30,
        5.0,
        5.0,
        -1,
        api_name="/generate_video"
    )

    video = extract_video(result)

    if not video:
        raise RuntimeError(
            f"Wan2.2 لم يرجع ملف فيديو. الاستجابة: {str(result)[:1000]}"
        )

    return make_local(video)

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
            "قد يستغرق حوالي 1–5 دقائق حسب ضغط الـ GPU"
        ):
            video = generate_wan22(prompt.strip(), resolution)

            if voice_text.strip():
                video = add_voice(video, voice_text.strip())

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
            "لو ظهر أن الـ Space مشغول، انتظر قليلًا ثم جرّب الطلب مرة أخرى."
        )

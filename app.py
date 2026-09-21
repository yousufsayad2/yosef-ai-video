import os
import subprocess
import tempfile
from pathlib import Path

import streamlit as st
from gradio_client import Client
from gtts import gTTS
import imageio_ffmpeg


st.set_page_config(
    page_title="Yosef AI Video",
    page_icon="🎬",
    layout="centered",
)

st.title("🎬 Yosef AI Video")
st.write("حوّل وصفك إلى فيديو AI متحرك + تعليق صوتي")
st.info("الفيديو يتم توليده من Wan2.1 عبر مساحة عامة على Hugging Face. قد يستغرق التوليد عدة دقائق حسب ضغط الخدمة.")

prompt = st.text_area(
    "🎥 وصف الفيديو",
    height=180,
    placeholder="مثال: شاب مصري يمشي في شارع بالقاهرة وقت الغروب، السيارات والأشخاص يتحركون في الخلفية، والكاميرا تتحرك بجانبه بحركة سينمائية واقعية..."
)

voice_text = st.text_area(
    "🎙️ الكلام اللي يتقال في الفيديو (اختياري)",
    height=120,
    placeholder="اكتب الجملة التي تريد سماعها بالعربية..."
)

resolution = st.selectbox(
    "📐 جودة/مقاس الفيديو",
    ["1280*720", "960*960", "720*1280"],
    index=0,
)

watermark = st.checkbox("إضافة علامة Wan2.1", value=False)

def get_video_url(result):
    """Extract a video URL/path from Gradio's returned value."""
    if isinstance(result, str):
        return result

    if isinstance(result, (list, tuple)):
        for item in result:
            if isinstance(item, str) and (
                item.startswith("http://")
                or item.startswith("https://")
                or item.endswith(".mp4")
            ):
                return item
            if isinstance(item, dict):
                for key in ("video", "url", "path"):
                    value = item.get(key)
                    if isinstance(value, str):
                        return value

    if isinstance(result, dict):
        for key in ("video", "url", "path"):
            value = result.get(key)
            if isinstance(value, str):
                return value

    return None


def download_video(url, output_path):
    """Download a remote video URL using ffmpeg."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-i", url,
        "-c", "copy",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def add_arabic_voice(video_path, text, output_path):
    """Create Arabic TTS and merge it with the generated video."""
    if not text.strip():
        return False

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio_file:
        audio_path = audio_file.name

    try:
        tts = gTTS(text=text.strip(), lang="ar")
        tts.save(audio_path)

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg,
            "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass


if st.button("🚀 إنشاء الفيديو", type="primary", use_container_width=True):
    if not prompt.strip():
        st.warning("اكتب وصف الفيديو الأول.")
        st.stop()

    progress = st.empty()
    progress.info("⏳ جاري الاتصال بـ Wan2.1...")

    try:
        # Public Wan2.1 Space. It exposes the t2v_generation endpoint.
        client = Client("Wan-AI/Wan2.1")

        progress.info("🎬 جاري توليد الفيديو المتحرك... قد يستغرق عدة دقائق.")

        result = client.predict(
            prompt.strip(),
            resolution,
            watermark,
            -1,
            api_name="/t2v_generation",
        )

        video_url = get_video_url(result)

        if not video_url:
            st.error("لم يرجع Wan2.1 رابط فيديو صالح.")
            st.code(str(result))
            st.stop()

        with tempfile.TemporaryDirectory() as tmp:
            raw_video = os.path.join(tmp, "wan_video.mp4")
            final_video = os.path.join(tmp, "yosef_ai_video.mp4")

            progress.info("📥 جاري تجهيز الفيديو...")

            if video_url.startswith(("http://", "https://")):
                download_video(video_url, raw_video)
            else:
                # Gradio may return a local path on its server.
                # Download it through the Gradio client's file handling when possible.
                import requests
                response = requests.get(video_url, timeout=300)
                response.raise_for_status()
                Path(raw_video).write_bytes(response.content)

            if voice_text.strip():
                progress.info("🎙️ جاري إضافة التعليق الصوتي العربي...")
                if add_arabic_voice(raw_video, voice_text, final_video):
                    display_path = final_video
                else:
                    display_path = raw_video
            else:
                display_path = raw_video

            video_bytes = Path(display_path).read_bytes()

            progress.empty()
            st.success("✅ الفيديو اتعمل بنجاح!")
            st.video(video_bytes)

            st.download_button(
                "⬇️ تحميل الفيديو",
                data=video_bytes,
                file_name="yosef_ai_video.mp4",
                mime="video/mp4",
                use_container_width=True,
            )

    except Exception as e:
        progress.empty()
        st.error("❌ حصل خطأ أثناء توليد الفيديو.")
        st.code(str(e))
        st.caption("لو مساحة Wan2.1 كانت مشغولة أو وصلت لحد الاستخدام، جرّب مرة أخرى بعد قليل.")

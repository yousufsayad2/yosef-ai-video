
import os
import time
import tempfile
import subprocess
from pathlib import Path

import streamlit as st
from gtts import gTTS
from gradio_client import Client

st.set_page_config(page_title="Yosef AI Video", page_icon="🎬", layout="centered")

st.title("🎬 Yosef AI Video")
st.caption("حوّل وصفك إلى فيديو AI متحرك + تعليق صوتي")

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
    """Extract a usable video path/URL from Gradio's returned value."""
    if value is None:
        return None

    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            return value
        if os.path.exists(value):
            return value

    if isinstance(value, dict):
        for key in ("video", "path", "url", "file", "value", "output", "data", "name"):
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
            v = getattr(value, attr)
            if isinstance(v, str):
                if v.startswith(("http://", "https://")) or os.path.exists(v):
                    return v
        except Exception:
            pass

    return None

def download_if_url(value):
    """Turn a remote video URL into a local file when needed."""
    if not value:
        return None

    if isinstance(value, str) and value.startswith(("http://", "https://")):
        import requests
        r = requests.get(value, timeout=120)
        r.raise_for_status()
        path = Path(tempfile.gettempdir()) / "yosef_wan_video.mp4"
        path.write_bytes(r.content)
        return str(path)

    return value

def call_wan21(prompt_text, size, watermark_value):
    """
    Wan-AI/Wan2.1 is an async Gradio app.
    We first discover its currently exposed API endpoints instead of
    assuming a fixed endpoint name.
    """
    client = Client("Wan-AI/Wan2.1")

    api_info = {}
    try:
        api_info = client.view_api(return_format="dict")
    except Exception:
        api_info = {}

    endpoint_names = list(api_info.keys()) if isinstance(api_info, dict) else []

    # Prefer the direct/synchronous endpoint if the current Space exposes it.
    sync_endpoint = next(
        (x for x in ["/t2v_generation", "/generate_t2v", "/generate"] if x in endpoint_names),
        None
    )

    if sync_endpoint:
        try:
            job = client.submit(
                prompt_text,
                size,
                watermark_value,
                -1,
                api_name=sync_endpoint
            )
            result = job.result(timeout=900)
            video = extract_video(result)
            if video:
                return download_if_url(video)
        except Exception as e:
            sync_error = str(e)
        else:
            sync_error = "لم يرجع الـ Space ملف فيديو."

    # Current official Space normally exposes this async endpoint.
    async_endpoint = next(
        (x for x in ["/t2v_generation_async", "/generate_t2v_async"] if x in endpoint_names),
        "/t2v_generation_async"
    )

    try:
        job = client.submit(
            prompt_text,
            size,
            watermark_value,
            -1,
            api_name=async_endpoint
        )

        # Wait until the submission itself is accepted.
        try:
            job.result(timeout=60)
        except Exception:
            pass

        # The official Space has a status endpoint for the queued task.
        for _ in range(120):
            time.sleep(5)

            for status_endpoint in ("/status_refresh", "/status_refresh_1"):
                try:
                    status = client.predict(api_name=status_endpoint)
                    video = extract_video(status)
                    if video:
                        return download_if_url(video)
                except Exception:
                    continue

        raise RuntimeError(
            "انتهى وقت الانتظار. جرّب مرة أخرى بعد دقيقة؛ الـ Space قد يكون عليه ضغط."
        )

    except Exception as e:
        details = str(e)
        if 'sync_error' in locals():
            details = f"SYNC: {sync_error}\nASYNC: {details}"
        raise RuntimeError(details)

def add_voice(video_path, text):
    """Add optional Arabic gTTS voice to the generated video."""
    if not text.strip():
        return video_path

    work = Path(tempfile.mkdtemp(prefix="yosef_video_"))
    voice_path = work / "voice.mp3"
    output_path = work / "final_video.mp4"

    gTTS(text=text, lang="ar").save(str(voice_path))

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    cmd = [
        ffmpeg, "-y",
        "-i", str(video_path),
        "-i", str(voice_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(output_path),
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return str(output_path)

# Import only when needed so the app can still show its UI if ffmpeg is unavailable.
try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None

if st.button("🚀 إنشاء الفيديو", type="primary", use_container_width=True):
    if not prompt.strip():
        st.warning("اكتب وصف الفيديو الأول.")
        st.stop()

    with st.spinner("🎬 جاري إنشاء الفيديو المتحرك... قد يستغرق عدة دقائق حسب ضغط الـ Space"):
        try:
            video_path = call_wan21(prompt.strip(), resolution, watermark)

            if not video_path:
                raise RuntimeError("لم يتم استلام ملف فيديو من Wan2.1.")

            if voice_text.strip():
                if imageio_ffmpeg is None:
                    raise RuntimeError("تعذر تجهيز FFmpeg لإضافة الصوت.")
                video_path = add_voice(video_path, voice_text.strip())

            st.success("✅ تم إنشاء الفيديو بنجاح!")
            st.video(video_path)

            with open(video_path, "rb") as f:
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
            st.info("لو ظهر خطأ من نوع الضغط/الانتظار، جرّب الزر مرة أخرى بعد دقيقة.")

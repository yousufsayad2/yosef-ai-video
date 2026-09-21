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

if "wan_client" not in st.session_state:
    st.session_state.wan_client = None
if "wan_job" not in st.session_state:
    st.session_state.wan_job = None
if "wan_video" not in st.session_state:
    st.session_state.wan_video = None

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

def extract_video(value):
    if value is None:
        return None

    if isinstance(value, str):
        if value.startswith(("http://", "https://")) or os.path.exists(value):
            return value
        return None

    if isinstance(value, dict):
        # Current Wan2.1 returns:
        # {"value": {"video": "/tmp/gradio/..."}, "__type__": "update"}
        if "value" in value:
            found = extract_video(value["value"])
            if found:
                return found

        for key in ("video", "path", "url", "file", "name"):
            if key in value:
                found = extract_video(value[key])
                if found:
                    return found

    if isinstance(value, (list, tuple)):
        for item in value:
            found = extract_video(item)
            if found:
                return found

    return None

def download_remote(value):
    if not value:
        return None

    if value.startswith(("http://", "https://")):
        import requests
        r = requests.get(value, timeout=180)
        r.raise_for_status()
        p = Path(tempfile.gettempdir()) / "yosef_wan21.mp4"
        p.write_bytes(r.content)
        return str(p)

    return value

def submit_video(text, size, mark):
    client = Client("Wan-AI/Wan2.1")

    # The official Space stores the task in Gradio State.
    # External callers should NOT try to extract the State output:
    # it may appear as {"__type__":"update"}.
    # Keep the SAME Client session and poll /status_refresh later.
    job = client.submit(
        text,
        size,
        mark,
        -1,
        api_name="/t2v_generation_async"
    )

    return client, job

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
        with st.spinner("📨 جاري إرسال الطلب إلى Wan2.1..."):
            client, job = submit_video(prompt.strip(), resolution, watermark)

        st.session_state.wan_client = client
        st.session_state.wan_job = job
        st.session_state.wan_video = None

        st.success("✅ الطلب اتبعت بنجاح!")
        st.info("⏳ استنى شوية، وبعدها اضغط «🔄 فحص حالة الفيديو».")
    except Exception as e:
        st.error("❌ حصل خطأ أثناء إرسال الطلب.")
        st.code(str(e))

if st.session_state.wan_client is not None:
    st.divider()

    if st.button("🔄 فحص حالة الفيديو", use_container_width=True):
        try:
            with st.spinner("🔎 جاري فحص حالة الفيديو..."):
                result = st.session_state.wan_client.predict(
                    api_name="/status_refresh"
                )

            video = extract_video(result)

            if video:
                video = download_remote(video)
                st.session_state.wan_video = video
                st.success("🎉 الفيديو خلص!")
            else:
                st.info("⏳ لسه بيتعمل. اضغط فحص الحالة مرة تانية بعد شوية.")

        except Exception as e:
            st.warning("⚠️ لسه بيتعمل أو الـ Space عليه ضغط.")
            st.code(str(e))

if st.session_state.wan_video:
    video = st.session_state.wan_video

    if voice_text.strip():
        try:
            with st.spinner("🎙️ جاري إضافة التعليق الصوتي..."):
                video = add_voice(video, voice_text.strip())
        except Exception as e:
            st.warning("الفيديو جاهز، لكن إضافة الصوت فشلت.")
            st.code(str(e))

    st.video(video)

    try:
        with open(video, "rb") as f:
            st.download_button(
                "⬇️ تحميل الفيديو",
                data=f,
                file_name="yosef_ai_video.mp4",
                mime="video/mp4",
                use_container_width=True,
            )
    except Exception:
        pass

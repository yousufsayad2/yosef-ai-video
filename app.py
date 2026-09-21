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

if "task_id" not in st.session_state:
    st.session_state.task_id = None
if "video_url" not in st.session_state:
    st.session_state.video_url = None

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

def extract_value(value):
    if value is None:
        return None

    if isinstance(value, str):
        if value.startswith(("http://", "https://")) or os.path.exists(value):
            return value
        return None

    if isinstance(value, dict):
        for key in ("video", "url", "path", "file", "value"):
            if key in value:
                found = extract_value(value[key])
                if found:
                    return found

    if isinstance(value, (list, tuple)):
        for item in value:
            found = extract_value(item)
            if found:
                return found

    return None

def download_video(value):
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

def submit_wan(prompt_text, size, watermark_value):
    client = Client("Wan-AI/Wan2.1")

    # IMPORTANT:
    # The current public Space exposes the async function, not the old
    # /t2v_generation function.
    result = client.predict(
        prompt_text,
        size,
        watermark_value,
        -1,
        api_name="/t2v_generation_async"
    )

    # Gradio can return component-update dictionaries in the response.
    # The task id is the string output; do not assume it is result[0].
    def find_task_id(value):
        if isinstance(value, str):
            text = value.strip()
            if text and not text.startswith(("http://", "https://")):
                # DashScope task IDs are long alphanumeric/UUID-like strings.
                if len(text) >= 12:
                    return text
            return None

        if isinstance(value, (list, tuple)):
            for item in value:
                found = find_task_id(item)
                if found:
                    return found

        if isinstance(value, dict):
            # Ignore Gradio component update objects.
            if value.get("__type__") == "update":
                return None
            for item in value.values():
                found = find_task_id(item)
                if found:
                    return found

        return None

    task_id = find_task_id(result)

    if not task_id:
        raise RuntimeError(
            f"لم أستطع استخراج رقم المهمة من استجابة Wan2.1: {result}"
        )

    return task_id

def check_wan(task_id):
    client = Client("Wan-AI/Wan2.1")

    result = client.predict(
        task_id,
        "t2v",
        False,
        api_name="/status_refresh"
    )

    video = extract_value(result)

    # status_refresh returns the generated video as the first output
    # when the task is complete.
    if video:
        return download_video(video), result

    return None, result

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

st.divider()

if st.button("🚀 إنشاء الفيديو", type="primary", use_container_width=True):
    if not prompt.strip():
        st.warning("اكتب وصف الفيديو الأول.")
        st.stop()

    try:
        with st.spinner("📨 جاري إرسال الفيديو إلى Wan2.1..."):
            task_id = submit_wan(
                prompt.strip(),
                resolution,
                watermark
            )

        st.session_state.task_id = task_id
        st.session_state.video_url = None

        st.success("✅ تم إرسال الطلب بنجاح!")
        st.info(
            "🎬 الفيديو بيتعمل على Wan2.1. "
            "اضغط «🔄 فحص حالة الفيديو» كل شوية لحد ما يخلص."
        )
        st.code(task_id)

    except Exception as e:
        st.error("❌ حصل خطأ أثناء إرسال الطلب.")
        st.code(str(e))

if st.session_state.task_id:
    st.divider()
    st.write("🆔 **رقم مهمة الفيديو:**")
    st.code(st.session_state.task_id)

    if st.button("🔄 فحص حالة الفيديو", use_container_width=True):
        try:
            with st.spinner("🔎 بنفحص حالة الفيديو..."):
                video, raw = check_wan(st.session_state.task_id)

            if video:
                st.session_state.video_url = video
                st.success("🎉 الفيديو خلص!")

            else:
                st.info(
                    "⏳ لسه بيتعمل. استنى شوية واضغط «فحص حالة الفيديو» مرة تانية."
                )

        except Exception as e:
            st.warning("⚠️ لسه ما خلصش أو الـ Space عليه ضغط.")
            st.code(str(e))

if st.session_state.video_url:
    video = st.session_state.video_url

    if voice_text.strip():
        try:
            with st.spinner("🎙️ جاري إضافة التعليق الصوتي..."):
                video = add_arabic_voice(video, voice_text.strip())
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

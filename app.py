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

if st.button("🚀 إنشاء الفيديو", type="primary", use_container_width=True):
    if not prompt.strip():
        st.warning("اكتب وصف الفيديو الأول.")
        st.stop()

    try:
        # Verified running Space:
        # OpenKing/wan2-video-generation
        # Wan2.2-TI2V-5B, ZeroGPU, Text-to-Video + Image-to-Video.
        client = Client("OpenKing/wan2-video-generation")

        with st.spinner(
            "🎬 جاري إنشاء الفيديو... عادةً يستغرق حوالي 2–3 دقائق. "
            "ما تضغطش الزر مرة تانية."
        ):
            result = client.predict(
                prompt.strip(),  # prompt
                None,             # optional image
                1280,             # width
                704,              # height
                49,               # frames (~2 sec at 24fps)
                25,               # inference steps
                5.0,              # guidance
                -1,               # random seed
                api_name="/generate_video"
            )

        # The Space returns: (video_path, status_text)
        video_path = None
        status_text = ""

        if isinstance(result, (list, tuple)):
            for item in result:
                if isinstance(item, str):
                    if os.path.exists(item) or item.startswith(("http://", "https://")):
                        video_path = item
                    elif item:
                        status_text = item
        elif isinstance(result, str):
            video_path = result

        if not video_path:
            raise RuntimeError(
                f"لم يرجع الـ Space ملف فيديو.\n{status_text}\n"
                f"الاستجابة: {str(result)[:1200]}"
            )

        # Download remote Gradio URL if necessary.
        if video_path.startswith(("http://", "https://")):
            import requests
            response = requests.get(video_path, timeout=240)
            response.raise_for_status()
            local_path = Path(tempfile.gettempdir()) / "yosef_ai_video.mp4"
            local_path.write_bytes(response.content)
            video_path = str(local_path)

        # Optional Arabic voice.
        if voice_text.strip():
            with st.spinner("🎙️ جاري إضافة التعليق الصوتي..."):
                work = Path(tempfile.mkdtemp(prefix="yosef_voice_"))
                voice_file = work / "voice.mp3"
                final_file = work / "yosef_ai_final.mp4"

                gTTS(text=voice_text.strip(), lang="ar").save(str(voice_file))
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

                subprocess.run(
                    [
                        ffmpeg, "-y",
                        "-i", str(video_path),
                        "-i", str(voice_file),
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-shortest",
                        str(final_file),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                video_path = str(final_file)

        st.success("🎉 تم إنشاء الفيديو بنجاح!")
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
        st.info("لو الـ Space وصل لحد الـ GPU، جرّب مرة أخرى بعد قليل.")

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

if st.button("🚀 إنشاء الفيديو", type="primary", use_container_width=True):
    if not prompt.strip():
        st.warning("اكتب وصف الفيديو الأول.")
        st.stop()

    try:
        height, width = map(int, resolution.split("*"))

        # Current running ZeroGPU Space:
        # Heartsync/Wan-2.1-T2V-1.3B-LoRA
        # It exposes a direct text-to-video /generate_video function.
        client = Client("Heartsync/Wan-2.1-T2V-1.3B-LoRA")

        negative_prompt = (
            "static, still image, blurry, low quality, distorted face, "
            "deformed body, extra fingers, bad hands, flicker, "
            "duplicate people, text, subtitles, watermark"
        )

        with st.spinner(
            "🎬 جاري إنشاء الفيديو المتحرك... "
            "الـ GPU المجاني ممكن يحتاج شوية وقت."
        ):
            result = client.predict(
                "Wan2.1-T2V-1.3B",
                prompt.strip(),
                negative_prompt,
                "benjamin-paine/steamboat-willie-1.3b",
                0.75,
                "UniPCMultistepScheduler",
                3.0,
                height,
                width,
                49,
                5.0,
                10,
                16,
                api_name="/generate_video"
            )

        if isinstance(result, str) and result:
            video_path = result
        elif isinstance(result, dict):
            video_path = result.get("video") or result.get("path") or result.get("value")
        elif isinstance(result, (list, tuple)):
            video_path = next(
                (
                    x for x in result
                    if isinstance(x, str) and (
                        x.startswith(("http://", "https://")) or os.path.exists(x)
                    )
                ),
                None
            )
        else:
            video_path = None

        if not video_path:
            raise RuntimeError(
                f"لم يرجع الـ Space ملف فيديو. الاستجابة: {str(result)[:1200]}"
            )

        if video_path.startswith(("http://", "https://")):
            import requests
            r = requests.get(video_path, timeout=240)
            r.raise_for_status()
            local = Path(tempfile.gettempdir()) / "yosef_ai_video.mp4"
            local.write_bytes(r.content)
            video_path = str(local)

        # Optional Arabic voice
        if voice_text.strip():
            work = Path(tempfile.mkdtemp(prefix="yosef_voice_"))
            voice = work / "voice.mp3"
            final = work / "yosef_ai_final.mp4"

            gTTS(text=voice_text.strip(), lang="ar").save(str(voice))
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
            video_path = str(final)

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
        st.info("لو الـ Space عليه ضغط، جرّب مرة أخرى بعد قليل.")

import os
import subprocess
import tempfile
from pathlib import Path

import streamlit as st
from gtts import gTTS
from huggingface_hub import InferenceClient
import imageio_ffmpeg

st.set_page_config(page_title="Yosef AI Video", page_icon="🎬", layout="centered")

st.title("🎬 Yosef AI Video")
st.caption("حوّل وصفك إلى فيديو AI متحرك + تعليق صوتي")

hf_token = st.secrets.get("HF_TOKEN", os.getenv("HF_TOKEN", "")).strip()

prompt = st.text_area(
    "🎥 وصف الفيديو",
    placeholder="مثال: شاب مصري يمشي في شارع القاهرة وقت الغروب، حركة كاميرا سينمائية ناعمة، واقعية عالية، إضاءة دافئة",
    height=130,
)

voice_text = st.text_area(
    "🎙️ الكلام اللي يتقال في الفيديو (اختياري)",
    placeholder="مثال: أهلاً بكم في تجربة جديدة من يوسف AI",
    height=100,
)

if st.button("🚀 إنشاء الفيديو", use_container_width=True):
    if not hf_token:
        st.error("❌ HF_TOKEN غير موجود في Streamlit Secrets.")
        st.stop()

    if not prompt.strip():
        st.warning("⚠️ اكتب وصف الفيديو أولاً.")
        st.stop()

    with st.spinner("🎬 جاري إنشاء الفيديو المتحرك..."):
        errors = []

        # Hugging Face documents Wan2.1 1.3B on fal-ai for text-to-video.
        models = [
            "Wan-AI/Wan2.1-T2V-1.3B",
            "tencent/HunyuanVideo",
        ]

        video_bytes = None

        for model_id in models:
            try:
                client = InferenceClient(
                    provider="fal-ai",
                    api_key=hf_token,
                    timeout=600,
                )

                video_bytes = client.text_to_video(
                    prompt=(
                        prompt.strip()
                        + ". Cinematic realistic video, natural motion, "
                          "smooth camera movement, realistic lighting, detailed environment, "
                          "high quality, no text, no subtitles."
                    ),
                    model=model_id,
                )

                if isinstance(video_bytes, (bytes, bytearray)) and len(video_bytes) > 1000:
                    break

                errors.append(f"{model_id}: لم يرجع ملف فيديو صالحًا.")
                video_bytes = None

            except Exception as e:
                errors.append(f"{model_id}: {type(e).__name__}: {e}")
                video_bytes = None

        if not video_bytes:
            joined = "\n".join(errors[-2:])
            st.error(
                "❌ لم ينجح توليد الفيديو من مزود Hugging Face.\n\n"
                "تفاصيل المحاولة:\n" + joined
            )
            st.info(
                "لو ظهر في التفاصيل 429 أو credits/quota فالمشكلة رصيد/حصة. "
                "ولو ظهر KeyError: video مرة أخرى، فالمشكلة من استجابة مزود الفيديو وليست من وصفك."
            )
            st.stop()

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                video_path = tmp / "video.mp4"
                final_path = tmp / "yosef_ai_video.mp4"
                video_path.write_bytes(bytes(video_bytes))

                result_bytes = bytes(video_bytes)

                if voice_text.strip():
                    audio_path = tmp / "voice.mp3"
                    gTTS(text=voice_text.strip(), lang="ar").save(str(audio_path))

                    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                    cmd = [
                        ffmpeg, "-y",
                        "-i", str(video_path),
                        "-i", str(audio_path),
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-shortest",
                        str(final_path),
                    ]

                    ff = subprocess.run(cmd, capture_output=True, text=True)
                    if ff.returncode != 0:
                        raise RuntimeError("فشل دمج التعليق الصوتي مع الفيديو.")

                    result_bytes = final_path.read_bytes()

                st.success("✅ تم إنشاء الفيديو بنجاح!")
                st.video(result_bytes)
                st.download_button(
                    "⬇️ تحميل الفيديو",
                    data=result_bytes,
                    file_name="yosef_ai_video.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                )

        except Exception as e:
            st.error(f"❌ تم إنشاء الفيديو لكن حدث خطأ أثناء عرضه/إضافة الصوت: {e}")

st.divider()
st.caption("Yosef AI • Text-to-Video • Hugging Face Inference Providers")

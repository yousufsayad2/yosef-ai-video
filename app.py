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

st.info("💡 النسخة دي تستخدم Hugging Face Inference Providers بدل Google Veo.")

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

generate = st.button("🚀 إنشاء الفيديو", use_container_width=True)

if generate:
    if not hf_token:
        st.error("❌ لم يتم العثور على HF_TOKEN في Secrets.")
        st.stop()

    if not prompt.strip():
        st.warning("⚠️ اكتب وصف الفيديو أولاً.")
        st.stop()

    with st.spinner("🎬 جاري إنشاء الفيديو المتحرك... قد يستغرق بعض الوقت"):
        try:
            client = InferenceClient(
                provider="fal-ai",
                api_key=hf_token,
                timeout=300,
            )

            enhanced_prompt = (
                prompt.strip()
                + ". Realistic cinematic video, natural human motion, "
                  "smooth camera movement, detailed environment, realistic lighting, "
                  "high quality, no text, no subtitles."
            )

            video_bytes = client.text_to_video(
                enhanced_prompt,
                model="Wan-AI/Wan2.1-T2V-1.3B",
            )

            if not video_bytes:
                raise RuntimeError("لم يرجع مزود الفيديو أي بيانات.")

            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                video_path = tmp / "video.mp4"
                final_path = tmp / "yosef_ai_video.mp4"
                video_path.write_bytes(video_bytes)

                output_bytes = video_bytes

                # إضافة تعليق صوتي اختياري باستخدام gTTS
                if voice_text.strip():
                    audio_path = tmp / "voice.mp3"
                    tts = gTTS(text=voice_text.strip(), lang="ar")
                    tts.save(str(audio_path))

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
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode != 0:
                        raise RuntimeError(
                            "فشل دمج الصوت مع الفيديو: " + result.stderr[-1000:]
                        )

                    output_bytes = final_path.read_bytes()

                st.success("✅ تم إنشاء الفيديو بنجاح!")
                st.video(output_bytes)
                st.download_button(
                    "⬇️ تحميل الفيديو",
                    data=output_bytes,
                    file_name="yosef_ai_video.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                )

        except Exception as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower() or "credit" in msg.lower():
                st.error(
                    "❌ مزود الفيديو رفض الطلب بسبب الرصيد/الحصة المتاحة في Hugging Face. "
                    "Inference Providers لها أرصدة شهرية وحدود استخدام."
                )
            else:
                st.error(f"❌ حصل خطأ: {msg}")

st.divider()
st.caption("Yosef AI • Text-to-Video • Hugging Face Inference Providers")

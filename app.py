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
        try:
            # auto lets Hugging Face select an available provider and can fail over.
            client = InferenceClient(
                provider="auto",
                api_key=hf_token,
                timeout=300,
            )

            video_bytes = client.text_to_video(
                prompt=(
                    prompt.strip()
                    + ". Cinematic realistic video, natural motion, "
                      "smooth camera movement, realistic lighting, detailed environment, "
                      "high quality, no text, no subtitles."
                ),
                model="Wan-AI/Wan2.1-T2V-1.3B",
            )

            if not isinstance(video_bytes, (bytes, bytearray)) or not video_bytes:
                raise RuntimeError(
                    "مزود الفيديو لم يرجع ملف فيديو صالحًا. جرّب مرة أخرى."
                )

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                video_path = tmp / "video.mp4"
                final_path = tmp / "yosef_ai_video.mp4"
                video_path.write_bytes(video_bytes)

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

        except KeyError as e:
            if str(e).strip("'") == "video":
                st.error(
                    "❌ مزود Hugging Face رجّع استجابة غير متوافقة مع واجهة الفيديو. "
                    "الكود نفسه اتصل بالخدمة لكن الخدمة لم تُرجع ملف الفيديو المتوقع. "
                    "جرّب مرة أخرى، ولو استمر الخطأ نبدّل المزود/الموديل."
                )
            else:
                st.error(f"❌ خطأ في استجابة Hugging Face: {e}")

        except Exception as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower() or "credit" in msg.lower():
                st.error(
                    "❌ لا يوجد رصيد/حصة كافية في Hugging Face Inference Providers لهذا الطلب."
                )
            elif "401" in msg or "403" in msg:
                st.error(
                    "❌ التوكن غير صالح أو لا يملك صلاحية Inference Providers."
                )
            else:
                st.error(f"❌ حصل خطأ: {msg}")

st.divider()
st.caption("Yosef AI • Text-to-Video • Hugging Face Inference Providers")

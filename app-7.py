import os
import re
import json
import textwrap
from io import BytesIO

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from gtts import gTTS
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

APP_NAME = "Yosef AI Video"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🎬",
    layout="wide",
)

# ---------- Styling ----------
st.markdown("""
<style>
.block-container {max-width: 1100px; padding-top: 2rem;}
.hero {
    padding: 28px;
    border-radius: 24px;
    background: linear-gradient(135deg, #111827, #1f2937);
    margin-bottom: 20px;
}
.hero h1 {font-size: 2.5rem; margin-bottom: 8px;}
.hero p {font-size: 1.05rem; opacity: .85;}
.small {opacity: .7; font-size: .9rem;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
<h1>🎬 Yosef AI Video</h1>
<p>حوّل فكرة بسيطة إلى سيناريو + مشاهد AI + صوت عربي + فيديو MP4.</p>
</div>
""", unsafe_allow_html=True)

# ---------- Helpers ----------
def get_secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
        if value:
            return value
    except Exception:
        pass
    return os.getenv(name, "")

def call_openrouter(api_key: str, prompt: str, model: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": APP_NAME,
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional short-form video writer. "
                    "Return only valid JSON when requested. "
                    "Do not use markdown fences."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }

    r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
    if r.status_code != 200:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(f"OpenRouter HTTP {r.status_code}: {detail}")

    data = r.json()
    return data["choices"][0]["message"]["content"]

def extract_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise ValueError("لم أستطع قراءة JSON الذي رجع من النموذج.")

def build_script(api_key, idea, duration, style, language, model):
    prompt = f"""
Create a short video plan in {language}.

Idea: {idea}
Target duration: {duration} seconds
Style: {style}

Return ONLY this JSON shape:
{{
  "title": "video title",
  "scenes": [
    {{
      "scene": 1,
      "narration": "spoken narration for this scene",
      "image_prompt": "detailed visual prompt in English for an image model",
      "caption": "short on-screen caption"
    }}
  ]
}}

Rules:
- Exactly 6 scenes.
- The narration must be natural Arabic if language is Arabic.
- Keep the total narration suitable for the target duration.
- Image prompts must describe cinematic composition, subject, lighting, camera angle,
  environment, and mood. Do not request text inside the image.
- Keep the same main character appearance across scenes when the idea has a character.
"""
    raw = call_openrouter(api_key, prompt, model)
    plan = extract_json(raw)

    if not isinstance(plan, dict) or not isinstance(plan.get("scenes"), list):
        raise ValueError("صيغة السيناريو غير صحيحة.")
    if len(plan["scenes"]) == 0:
        raise ValueError("لم يتم إنشاء أي مشهد.")
    return plan

def image_url(prompt, width=720, height=1280):
    # Pollinations' public image endpoint. The prompt is URL-encoded by requests.
    return "https://image.pollinations.ai/prompt/" + requests.utils.quote(prompt, safe="") + \
           f"?width={width}&height={height}&nologo=true&seed=42"

def generate_ai_image(prompt, index, width=720, height=1280):
    url = image_url(prompt, width, height)
    r = requests.get(url, timeout=120)
    if r.status_code != 200 or not r.content:
        raise RuntimeError(f"Image API HTTP {r.status_code}")
    img = Image.open(BytesIO(r.content)).convert("RGB")
    path = f"/tmp/yosef_scene_{index}.jpg"
    img.save(path, quality=92)
    return path

def font_path():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def make_overlay(image_path, caption, index):
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size

    # Dark bottom panel for captions.
    panel_h = int(h * 0.20)
    draw.rectangle((0, h - panel_h, w, h), fill=(0, 0, 0, 165))

    fp = font_path()
    font = ImageFont.truetype(fp, 38) if fp else None
    small = ImageFont.truetype(fp, 26) if fp else None

    if caption:
        lines = textwrap.wrap(caption, width=28)
        y = h - panel_h + 28
        for line in lines[:3]:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (w - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, fill="white", font=font)
            y += 48

    label = f"YOSEF AI  •  {index}"
    draw.text((24, 24), label, fill=(255, 255, 255, 210), font=small)

    out = f"/tmp/yosef_overlay_{index}.jpg"
    img.save(out, quality=92)
    return out

def create_voice(text, index):
    path = f"/tmp/yosef_voice_{index}.mp3"
    tts = gTTS(text=text, lang="ar", slow=False)
    tts.save(path)
    return path

def make_video(plan, progress_callback=None):
    clips = []
    audio_files = []
    image_files = []

    scenes = plan["scenes"]

    for i, scene in enumerate(scenes, start=1):
        narration = str(scene.get("narration", "")).strip()
        prompt = str(scene.get("image_prompt", "")).strip()
        caption = str(scene.get("caption", "")).strip()

        if not narration:
            continue

        if progress_callback:
            progress_callback(i - 1, len(scenes), f"🖼️ إنشاء المشهد {i}/{len(scenes)}")

        image_path = generate_ai_image(
            prompt + ", vertical 9:16, high detail, cinematic, no text, no watermark",
            i,
        )
        image_files.append(image_path)

        overlay_path = make_overlay(image_path, caption, i)
        voice_path = create_voice(narration, i)
        audio_files.append(voice_path)

        audio = AudioFileClip(voice_path)
        clip = ImageClip(overlay_path).with_duration(audio.duration).with_audio(audio)
        clips.append(clip)

    if not clips:
        raise ValueError("لم يتم إنشاء مشاهد صالحة.")

    if progress_callback:
        progress_callback(len(scenes), len(scenes), "🎬 تجميع الفيديو النهائي")

    final = concatenate_videoclips(clips, method="compose")
    output = "/tmp/Yosef_AI_Video.mp4"
    final.write_videofile(
        output,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    # Close resources.
    for c in clips:
        try:
            c.close()
        except Exception:
            pass
    try:
        final.close()
    except Exception:
        pass

    return output

# ---------- Sidebar ----------
with st.sidebar:
    st.header("⚙️ الإعدادات")

    saved_key = get_secret("OPENROUTER_API_KEY")
    api_key = st.text_input(
        "OpenRouter API Key",
        value=saved_key,
        type="password",
        help="لا تضع المفتاح داخل الكود. الأفضل استخدام Streamlit Secrets.",
    )

    model = st.selectbox(
        "AI Model",
        [
            "openrouter/free",
            "google/gemini-2.5-flash",
        ],
        index=0,
    )

    language = st.selectbox("اللغة", ["Arabic", "English"], index=0)
    duration = st.slider("مدة الفيديو المستهدفة (ثانية)", 20, 120, 45, 5)

# ---------- Main form ----------
col1, col2 = st.columns([2, 1])

with col1:
    idea = st.text_area(
        "💡 فكرة الفيديو",
        placeholder="مثال: شاب بدأ من الصفر في البرمجة، وتعلم الذكاء الاصطناعي حتى صنع أول مشروع له.",
        height=150,
    )

with col2:
    style = st.selectbox(
        "🎨 أسلوب الفيديو",
        ["Cinematic", "Realistic", "Motivational", "Storytelling", "Educational"],
    )
    st.caption("الفيديو الناتج عمودي 9:16 ومناسب لـ Reels / TikTok / Shorts.")

generate = st.button("🚀 إنشاء الفيديو", type="primary", use_container_width=True)

if generate:
    if not api_key.strip():
        st.error("❌ ضع OpenRouter API Key أولًا.")
        st.stop()

    if not idea.strip():
        st.warning("⚠️ اكتب فكرة الفيديو أولًا.")
        st.stop()

    try:
        with st.status("🤖 جاري تجهيز الفيديو...", expanded=True) as status:
            st.write("✍️ كتابة السيناريو...")
            plan = build_script(api_key, idea, duration, style, language, model)

            st.write("🎨 توليد المشاهد والصوت...")
            progress = st.progress(0)

            def cb(done, total, message):
                st.write(message)
                progress.progress(min(done / max(total, 1), 1.0))

            video_path = make_video(plan, cb)

            status.update(label="✅ الفيديو جاهز", state="complete", expanded=False)

        st.success("🎉 تم إنشاء الفيديو بنجاح!")

        st.subheader("📜 السيناريو")
        st.write(plan.get("title", "Yosef AI Video"))
        for s in plan["scenes"]:
            with st.expander(f"المشهد {s.get('scene', '?')}"):
                st.write("**التعليق الصوتي:**", s.get("narration", ""))
                st.write("**الكابشن:**", s.get("caption", ""))

        st.subheader("🎬 الفيديو")
        st.video(video_path)

        with open(video_path, "rb") as f:
            st.download_button(
                "⬇️ تحميل الفيديو MP4",
                data=f.read(),
                file_name="Yosef_AI_Video.mp4",
                mime="video/mp4",
                use_container_width=True,
            )

    except Exception as e:
        st.error("❌ حصل خطأ أثناء إنشاء الفيديو.")
        st.code(str(e))
        st.info(
            "لو الخطأ متعلق بـ OpenRouter، تأكد من المفتاح والموديل. "
            "ولو متعلق بالصور، جرّب مرة أخرى لأن خدمة توليد الصور خارجية."
        )
else:
    st.info("ابدأ بكتابة فكرة، ثم اضغط «إنشاء الفيديو».")
    st.markdown("""
### ✨ النسخة الحالية
- AI يكتب السيناريو ويقسمه إلى مشاهد.
- يولّد صورة AI لكل مشهد.
- يولّد تعليقًا صوتيًا عربيًا.
- يضيف كابشن بسيط.
- يجمع كل شيء في MP4 عمودي 9:16.

> ملاحظة: هذه النسخة تستخدم صور AI متحركة بالانتقالات والصوت، وليست بعد نموذج Text-to-Video حقيقي لكل مشهد.
""")

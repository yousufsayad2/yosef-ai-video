import os
import re
import json
import subprocess
import tempfile
from io import BytesIO

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
import imageio_ffmpeg

APP_NAME = "Yosef AI Video"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"
def get_secret(name):
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""

DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"

def call_ai(api_key, prompt, model=DEFAULT_GEMINI_MODEL):
    api_key = api_key.strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("مفتاح Gemini غير موجود.")
    url = f"{GEMINI_URL}/{model}:generateContent"
    payload = {
        "systemInstruction": {
            "parts": [{"text": "Return only valid JSON. No markdown."}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json"
        }
    }

    r = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        json=payload,
        timeout=120,
    )

    if not r.ok:
        try:
            detail = r.json().get("error", {}).get("message", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {detail}")

    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini رجّع استجابة غير متوقعة.")


def parse_json(text):
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError("AI لم يرجع JSON صالح.")
        return json.loads(m.group(0))

def make_plan(api_key, idea, seconds, style, model):
    prompt = f"""
Create a short vertical video plan.

Idea: {idea}
Target duration: {seconds} seconds
Style: {style}

Return ONLY:
{{
  "title": "Arabic title",
  "scenes": [
    {{
      "scene": 1,
      "narration": "Arabic narration",
      "image_prompt": "English cinematic image prompt, no text in image",
      "caption": "short Arabic caption"
    }}
  ]
}}

Rules:
- Exactly 6 scenes.
- Arabic narration.
- Keep total narration suitable for the requested duration.
- Keep the main character visually consistent.
- Image prompts should be detailed and suitable for vertical 9:16 images.
"""
    return parse_json(call_ai(api_key, prompt, model))

def download_image(prompt, out_path):
    url = "https://image.pollinations.ai/prompt/" + requests.utils.quote(prompt, safe="")
    url += "?width=720&height=1280&nologo=true"
    r = requests.get(url, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Image API HTTP {r.status_code}")
    Image.open(BytesIO(r.content)).convert("RGB").save(out_path, quality=92)

def make_caption_image(image_path, caption, out_path):
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    draw.rectangle((0, int(h*0.78), w, h), fill=(0,0,0,170))

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    font_path = next((x for x in font_candidates if os.path.exists(x)), None)
    font = ImageFont.truetype(font_path, 34) if font_path else None

    words = caption.split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        if len(test) <= 28:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)

    y = int(h*0.82)
    for line in lines[:3]:
        box = draw.textbbox((0,0), line, font=font)
        x = max(20, (w - (box[2]-box[0]))//2)
        draw.text((x, y), line, fill="white", font=font)
        y += 45

    img.save(out_path, quality=92)

def make_audio(text, out_path):
    gTTS(text=text, lang="ar", slow=False).save(out_path)

def run_ffmpeg(args):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y"] + args
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-4000:])

def make_scene_video(image_path, audio_path, out_path):
    # Still image + voice, encoded to a standard H.264/AAC MP4.
    run_ffmpeg([
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264", "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-r", "24",
        out_path,
    ])

def concat_videos(video_paths, output):
    # Use concat demuxer; paths are temporary and contain no single quotes.
    list_file = output + ".txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for path in video_paths:
            safe = path.replace("'", "'\\''")
            f.write(f"file '{safe}'\n")
    run_ffmpeg([
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output,
    ])
    try:
        os.remove(list_file)
    except OSError:
        pass

api_key = st.text_input(
    "🔑 Gemini API Key",
    value=get_secret("GEMINI_API_KEY"),
    type="password",
)

model = st.selectbox(
    "🤖 AI Model",
    ["gemini-3.6-flash"],
)

idea = st.text_area(
    "💡 فكرة الفيديو",
    placeholder="مثال: شاب يتعلم الذكاء الاصطناعي ويصنع أول مشروع له.",
    height=130,
)

c1, c2 = st.columns(2)
with c1:
    duration = st.slider("⏱️ المدة المستهدفة", 20, 120, 45, 5)
with c2:
    style = st.selectbox(
        "🎨 الأسلوب",
        ["Cinematic", "Realistic", "Motivational", "Storytelling", "Educational"],
    )

if st.button("🚀 إنشاء الفيديو", type="primary", use_container_width=True):
    if not api_key.strip():
        st.error("❌ ضع Gemini API Key.")
        st.stop()
    if not idea.strip():
        st.warning("⚠️ اكتب فكرة الفيديو.")
        st.stop()

    try:
        with st.spinner("✍️ جاري كتابة السيناريو..."):
            plan = make_plan(api_key, idea, duration, style, model)

        st.success("✅ تم إنشاء السيناريو")

        with st.expander("📜 عرض السيناريو"):
            st.write(plan.get("title", "Yosef AI Video"))
            for s in plan["scenes"]:
                st.write(f"**المشهد {s.get('scene')}**")
                st.write(s.get("narration", ""))

        progress = st.progress(0)
        status = st.empty()

        with tempfile.TemporaryDirectory() as work:
            videos = []
            scenes = plan["scenes"]

            for i, scene in enumerate(scenes, 1):
                status.write(f"🎬 تجهيز المشهد {i}/{len(scenes)}...")
                image = os.path.join(work, f"scene_{i}.jpg")
                final_image = os.path.join(work, f"scene_{i}_caption.jpg")
                audio = os.path.join(work, f"voice_{i}.mp3")
                video = os.path.join(work, f"scene_{i}.mp4")

                prompt = scene.get("image_prompt", "") + ", vertical 9:16, cinematic, high detail, no text, no watermark"
                download_image(prompt, image)
                make_caption_image(image, scene.get("caption", ""), final_image)
                make_audio(scene.get("narration", ""), audio)
                make_scene_video(final_image, audio, video)

                videos.append(video)
                progress.progress(i / len(scenes))

            status.write("🎞️ تجميع الفيديو النهائي...")
            output = os.path.join(work, "Yosef_AI_Video.mp4")
            concat_videos(videos, output)

            video_bytes = open(output, "rb").read()

        st.success("🎉 الفيديو جاهز!")
        st.video(video_bytes)
        st.download_button(
            "⬇️ تحميل الفيديو",
            video_bytes,
            "Yosef_AI_Video.mp4",
            "video/mp4",
            use_container_width=True,
        )

    except Exception as e:
        st.error("❌ حصل خطأ")
        st.code(str(e))

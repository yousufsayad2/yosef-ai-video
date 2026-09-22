import streamlit as st
import requests
import json
import io
from gtts import gTTS

st.set_page_config(
    page_title="Yosef AI Studio",
    page_icon="🎬",
    layout="centered"
)

st.title("🎬 Yosef AI Studio")
st.caption("من فكرة بسيطة إلى قصة وشخصيات ومشاهد وتعليق صوتي")

st.divider()

idea = st.text_area(
    "💡 فكرة القصة",
    placeholder="مثال: شاب مصري يجد روبوتًا صغيرًا في شارع القاهرة ويكتشف أنه يستطيع التنبؤ بالمستقبل...",
    height=120
)

col1, col2 = st.columns(2)

with col1:
    duration = st.selectbox(
        "⏱️ مدة القصة",
        ["30 ثانية", "1 دقيقة", "2 دقيقة", "3 دقائق"]
    )

with col2:
    style = st.selectbox(
        "🎨 أسلوب الفيديو",
        [
            "سينمائي واقعي",
            "أنمي",
            "كرتوني",
            "خيال علمي",
            "رعب",
            "مغامرات"
        ]
    )

language = st.selectbox(
    "🌍 اللغة",
    ["العربية المصرية", "العربية الفصحى", "English"]
)

st.divider()

if st.button("🚀 إنشاء القصة والشخصيات", use_container_width=True):

    if not idea.strip():
        st.warning("اكتب فكرة القصة الأول.")
        st.stop()

    api_key = None

    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        try:
            api_key = st.secrets["GOOGLE_API_KEY"]
        except:
            pass

    prompt = f"""
أنت كاتب ومخرج أفلام محترف.

حوّل فكرة المستخدم التالية إلى مشروع فيديو كامل:

فكرة المستخدم:
{idea}

المدة:
{duration}

الأسلوب:
{style}

اللغة:
{language}

أريد النتيجة بالعربية، منظمة بهذا الشكل:

1. عنوان القصة

2. ملخص القصة

3. الشخصيات الرئيسية:
لكل شخصية:
- الاسم
- العمر التقريبي
- الشكل
- الملابس
- الشخصية
- طريقة الكلام

4. ثبات الشخصيات:
اكتب وصفًا ثابتًا لكل شخصية يمكن استخدامه في كل مشهد حتى لا يتغير شكلها.

5. المشاهد:
قسّم القصة إلى مشاهد قصيرة.
لكل مشهد:
- رقم المشهد
- المكان
- الوقت
- ماذا يحدث
- حركة الشخصيات
- حركة الكاميرا
- الإضاءة
- الحوار
- Video Prompt باللغة الإنجليزية

6. التعليق الصوتي:
اكتب النص كاملًا جاهزًا للتحويل إلى صوت.

اجعل الأحداث مترابطة والشخصيات ثابتة بصريًا.
"""

    result = None

    if api_key:

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

        models = [
            "gemini-3.6-flash",
            "gemini-2.5-flash"
        ]

        for model in models:

            try:
                url = (
                    "https://generativelanguage.googleapis.com/"
                    f"v1beta/models/{model}:generateContent"
                )

                payload = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": prompt
                                }
                            ]
                        }
                    ]
                }

                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=120
                )

                if response.ok:

                    data = response.json()

                    result = (
                        data["candidates"][0]
                        ["content"]["parts"][0]["text"]
                    )

                    break

            except Exception:
                pass

    # Fallback لو Gemini مش متاح
    if not result:

        result = f"""
# 🎬 {idea[:50]}

## 📖 القصة

تبدأ القصة عندما يكتشف بطلنا سرًا غامضًا مرتبطًا بهذه الفكرة:

{idea}

يبدأ البطل في البحث عن الحقيقة، وخلال رحلته يواجه مجموعة من الأحداث
المفاجئة التي تغيّر حياته.

## 🎭 الشخصيات

### الشخصية الرئيسية
- الاسم: آدم
- العمر: 22 سنة
- الشكل: شاب مصري، شعر أسود قصير، مظهر طبيعي.
- الملابس: تيشيرت وبنطلون جينز.
- الشخصية: فضولي وشجاع.
- طريقة الكلام: مصرية بسيطة.

### الشخصية الثانية
- الاسم: نور
- العمر: 21 سنة
- الشكل: شابة مصرية بمظهر طبيعي.
- الملابس: ملابس عصرية بسيطة.
- الشخصية: ذكية وهادئة.

## 🎥 المشاهد

### المشهد 1
المكان: شارع في القاهرة وقت الغروب.

يظهر آدم وهو يمشي في الشارع وينظر حوله.

حركة الكاميرا:
الكاميرا تتحرك بجانبه بشكل سينمائي.

Video Prompt:
A young Egyptian man walking naturally through a busy Cairo street
at sunset, realistic pedestrians and cars, cinematic tracking camera,
natural body movement, realistic clothing motion, photorealistic,
high detail.

### المشهد 2
يكتشف آدم الشيء الغامض الذي سيغيّر أحداث القصة.

Video Prompt:
The same young Egyptian man discovers something mysterious,
cinematic close-up, realistic facial expression, natural movement,
dramatic lighting, photorealistic cinematic film.

## 🎙️ التعليق الصوتي

تبدأ الحكاية في مساء عادي جدًا...
لكن آدم لم يكن يعرف أن هذا اليوم سيغيّر حياته إلى الأبد.
"""

    st.success("✅ القصة اتعملت!")

    st.markdown(result)

    st.divider()

    st.subheader("🎙️ إنشاء التعليق الصوتي")

    voice_text = st.text_area(
        "النص الصوتي",
        value=result,
        height=200
    )

    if st.button("🔊 إنشاء الصوت العربي", use_container_width=True):

        try:
            tts = gTTS(
                text=voice_text,
                lang="ar",
                slow=False
            )

            audio = io.BytesIO()
            tts.write_to_fp(audio)

            audio.seek(0)

            st.audio(audio, format="audio/mp3")

            st.download_button(
                "⬇️ تحميل الصوت MP3",
                data=audio,
                file_name="yosef_ai_voice.mp3",
                mime="audio/mpeg",
                use_container_width=True
            )

            st.success("🎙️ الصوت جاهز!")

        except Exception as e:
            st.error(f"حصل خطأ في إنشاء الصوت: {e}")

else:
    st.info(
        "💡 اكتب فكرة القصة واضغط «إنشاء القصة والشخصيات»."
            )

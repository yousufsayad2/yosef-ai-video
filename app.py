import io
import requests
import streamlit as st
from gtts import gTTS

st.set_page_config(page_title="Yosef AI Studio", page_icon="🎬", layout="centered")

if "result" not in st.session_state:
    st.session_state.result = ""
if "voice_audio" not in st.session_state:
    st.session_state.voice_audio = None

st.title("🎬 Yosef AI Studio")
st.caption("من فكرة بسيطة إلى قصة وشخصيات ومشاهد وتعليق صوتي")
st.divider()

idea = st.text_area(
    "💡 فكرة القصة",
    placeholder="مثال: شاب مصري يكتشف روبوتًا صغيرًا في شارع القاهرة...",
    height=130
)

duration = st.selectbox("⏱️ مدة القصة", ["30 ثانية", "1 دقيقة", "2 دقيقة", "3 دقائق"])
style = st.selectbox("🎨 أسلوب الفيديو", ["سينمائي واقعي", "أنمي", "كرتوني", "خيال علمي", "رعب", "مغامرات"])
language = st.selectbox("🌍 اللغة", ["العربية المصرية", "العربية الفصحى", "English"])

st.divider()

if st.button("🚀 إنشاء القصة والشخصيات", use_container_width=True):
    if not idea.strip():
        st.warning("اكتب فكرة القصة الأول.")
        st.stop()

    api_key = None
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        try:
            api_key = st.secrets["GOOGLE_API_KEY"]
        except Exception:
            pass

    if not api_key:
        st.error("مش لاقي GEMINI_API_KEY في Streamlit Secrets.")
        st.stop()

    prompt = f"""
أنت كاتب ومخرج أفلام محترف.
حوّل الفكرة التالية إلى مشروع فيديو كامل.

فكرة المستخدم:
{idea}

المدة:
{duration}
الأسلوب:
{style}
اللغة:
{language}

اكتب بالعربية وبالتنسيق التالي:

# 🎬 عنوان القصة

## 📖 ملخص القصة

## 🎭 الشخصيات الرئيسية

لكل شخصية:
- الاسم
- العمر التقريبي
- الشكل
- الشعر
- الملابس
- الشخصية
- طريقة الكلام

## 🔒 ثبات الشخصيات

اكتب وصفًا ثابتًا ودقيقًا لكل شخصية لاستخدامه في جميع المشاهد.

## 🎥 المشاهد

قسّم القصة إلى مشاهد قصيرة ومترابطة.
لكل مشهد:
- رقم المشهد
- المكان
- الوقت
- الأحداث
- حركة الشخصيات
- حركة الكاميرا
- الإضاءة
- الحوار
- Video Prompt باللغة الإنجليزية

اجعل Video Prompt مناسبًا لتوليد فيديو AI واقعي، مع الحفاظ على شكل وملابس الشخصيات.

## 🎙️ التعليق الصوتي

في هذا القسم فقط اكتب النص الذي سيُقرأ بصوت الراوي.
لا تضع فيه عناوين Markdown أو وصفًا للمشاهد.
اجعله نصًا عربيًا متصلًا ومناسبًا لمدة {duration}.

مهم: لا تجعل القصة أطول من المدة المطلوبة.
"""

    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        if not response.ok:
            st.error(f"Gemini API Error: {response.status_code}\n\n{response.text}")
            st.stop()
        data = response.json()
        st.session_state.result = data["candidates"][0]["content"]["parts"][0]["text"]
        st.session_state.voice_audio = None
    except Exception as e:
        st.error(f"حدث خطأ أثناء إنشاء القصة: {e}")
        st.stop()

if st.session_state.result:
    st.success("✅ القصة والشخصيات اتعملوا!")
    st.markdown(st.session_state.result)
    st.divider()
    st.subheader("🎙️ التعليق الصوتي")

    full_result = st.session_state.result
    if "## 🎙️ التعليق الصوتي" in full_result:
        voice_only = full_result.split("## 🎙️ التعليق الصوتي", 1)[1]
    elif "## التعليق الصوتي" in full_result:
        voice_only = full_result.split("## التعليق الصوتي", 1)[1]
    else:
        voice_only = full_result

    voice_text = st.text_area(
        "🎙️ النص الذي سيتم تحويله لصوت",
        value=voice_only.strip(),
        height=220,
        key="voice_text"
    )

    if st.button("🔊 إنشاء الصوت العربي", use_container_width=True):
        if not voice_text.strip():
            st.warning("النص الصوتي فارغ.")
            st.stop()
        try:
            tts = gTTS(text=voice_text.strip(), lang="ar", slow=False)
            audio = io.BytesIO()
            tts.write_to_fp(audio)
            st.session_state.voice_audio = audio.getvalue()
        except Exception as e:
            st.error(f"حدث خطأ في إنشاء الصوت: {e}")

    if st.session_state.voice_audio:
        st.success("🎙️ الصوت جاهز!")
        st.audio(st.session_state.voice_audio, format="audio/mp3")
        st.download_button(
            "⬇️ تحميل الصوت MP3",
            data=st.session_state.voice_audio,
            file_name="yosef_ai_voice.mp3",
            mime="audio/mpeg",
            use_container_width=True
        )
else:
    st.info("💡 اكتب فكرة القصة واضغط «إنشاء القصة والشخصيات».")

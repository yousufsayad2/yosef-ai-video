import streamlit as st

st.set_page_config(
    page_title="Yosef AI Video",
    page_icon="🎬",
    layout="centered"
)

st.title("🎬 Yosef AI Video")
st.write("فيديو AI متحرك + تعليق صوتي عربي")

st.divider()

prompt = st.text_area(
    "🎥 وصف الفيديو",
    placeholder="اكتب وصف الفيديو هنا..."
)

voice = st.text_area(
    "🎙️ الكلام اللي يتقال في الفيديو (اختياري)",
    placeholder="اكتب التعليق الصوتي هنا..."
)

st.divider()

st.subheader("🚀 إنشاء الفيديو")

st.info(
    "اضغط الزر لفتح مولّد الفيديو المجاني. "
    "استخدم 4 ثواني و480p للحصول على فرصة أفضل للتوليد المجاني."
)

st.link_button(
    "🎬 فتح مولّد الفيديو المجاني",
    "https://freecreate.app/ai"
)

if prompt:
    st.subheader("📋 وصف الفيديو بتاعك")
    st.code(prompt, language=None)

if voice:
    st.subheader("🎙️ التعليق الصوتي")
    st.code(voice, language=None)

st.divider()

st.caption("© 2026 Yosef AI")

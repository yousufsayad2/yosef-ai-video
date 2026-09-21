# 🎬 Yosef AI Video

AI video generator built with Streamlit.

## What it does
- Generates a short Arabic/English video plan using OpenRouter.
- Generates AI images for each scene.
- Creates Arabic voice-over with gTTS.
- Adds captions.
- Combines everything into a vertical 9:16 MP4.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## API key

You can enter the OpenRouter key in the sidebar, or configure Streamlit Secrets:

`.streamlit/secrets.toml`

```toml
OPENROUTER_API_KEY = "sk-or-v1-..."
```

Never commit API keys to GitHub.

## Deployment

This project is suitable for Streamlit Community Cloud. Connect the GitHub repository,
set `OPENROUTER_API_KEY` in the app's Secrets, and deploy `app.py`.

OpenRouter uses its OpenAI-compatible API endpoint. Pollinations provides image generation APIs.

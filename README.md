# Loyum-Agent2
# Trend Agents

A minimal but production-ready project combining a FastAPI backend with a Streamlit UI to explore social media trends, ideate content, and draft platform-specific posts using GPT models.

## Features
- FastAPI backend wrapping Apify actors to fetch cross-platform trends.
- OpenAI-powered agents to generate creative ideas and fully drafted posts.
- Streamlit interface with caching, back-navigation, and debug payload toggles.
- Robust error handling, logging, and configurable environment settings.

## Quick start
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and provide values for `OPENAI_API_KEY` and `APIFY_TOKEN`. Adjust the actor IDs (`APIFY_TIKTOK_ACTOR`, `APIFY_X_ACTOR`, `APIFY_FACEBOOK_ACTOR`) to match your preferred Apify actors or leave the provided placeholders until ready.

3. Start the backend:
   ```bash
   uvicorn app.backend.main:app --host 0.0.0.0 --port 8000
   ```

4. In a new terminal, launch the Streamlit UI:
   ```bash
   streamlit run app/frontend/streamlit_app.py
   ```

By default the frontend targets `http://localhost:8000`. Override by setting `BACKEND_PORT` or `BACKEND_URL` in your environment.

## Environment variables
| Variable | Description | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI API key used by the backend agents. | — |
| `OPENAI_MODEL` | OpenAI model name. | `gpt-5` |
| `APIFY_TOKEN` | Token for Apify API calls. | — |
| `APIFY_TIKTOK_ACTOR` | Actor ID for TikTok trend mining. | `actor/tiktok-trends` |
| `APIFY_X_ACTOR` | Actor ID for X trend mining. | `actor/x-trends` |
| `APIFY_FACEBOOK_ACTOR` | Actor ID for Facebook trend mining. | `actor/facebook-trends` |
| `APIFY_DEFAULT_TIMEOUT_SEC` | Timeout in seconds for Apify runs. | `120` |
| `BACKEND_PORT` | Port used by FastAPI backend. | `8000` |
| `BACKEND_URL` | Optional override for frontend to target a custom backend URL. | `http://localhost:BACKEND_PORT` |

## Swapping Apify actors
All Apify actor IDs are sourced from environment variables and used within `TrendService`. To integrate different actors, update the IDs in `.env` and adjust the adapter functions inside `app/backend/services/trends_service.py` where TODO comments highlight the normalization layer.

## Testing
Run the test suite with:
```bash
pytest
```

## Development scripts
A convenience script is available to start both services locally:
```bash
./run_local.sh
```
Adjust the script as needed for your workflow.
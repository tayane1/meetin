# meetIN - AI-Powered Meeting Transcription & Minutes

A web application for recording meetings and automatically generating meeting minutes with real-time transcription, speaker diarization, and AI-powered summarization.

## Architecture

- **Backend**: Django 6 + DRF + Channels + Celery + PostgreSQL + Redis
- **Frontend**: React 19 + TypeScript + Material-UI
- **Transcription**: Deepgram (real-time + batch, with speaker diarization)
- **AI**: OpenAI / Azure OpenAI for minutes generation
- **Storage**: Local or S3-compatible object storage

## Features

- Real-time transcription with speaker diarization
- Bilingual support (English / French)
- Automatic meeting minutes generation
- Action items and decisions extraction
- AI Copilot with real-time suggestions
- Organization-based multi-tenancy with RBAC
- JWT authentication with token rotation and blacklisting

## Project Structure

```
meetIN/
├── backend/          # Django API, WebSocket, Celery workers
├── frontend/         # React SPA
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 14+
- Redis 6+ (for Celery workers and production WebSocket)

### 1. Backend

```bash
cd backend
python -m venv env
source env/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Edit with your values
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 2. Frontend

```bash
cd frontend
npm install
npm start
```

The app runs at `http://localhost:3000` (frontend) and `http://localhost:8000` (API).

## Production Deployment

1. Set `DEBUG=False` and generate a strong `SECRET_KEY`
2. Configure `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS`
3. Set up PostgreSQL and Redis
4. Configure SSL/TLS (HSTS, secure cookies are auto-enabled when `DEBUG=False`)
5. Set up S3 for file storage (`USE_S3=True`)
6. Run Celery workers: `celery -A meetin worker -l info`
7. Serve with gunicorn/uvicorn behind nginx

See `backend/README.md` and `frontend/README.md` for detailed setup.

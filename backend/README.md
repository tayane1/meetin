# meetIN - Backend

Django 6 REST API with real-time WebSocket transcription, Celery workers, and AI-powered meeting minutes generation.

## Prerequisites

- Python 3.12+
- PostgreSQL 14+
- Redis 6+

## Setup

1. Create and activate virtual environment:
```bash
cd backend
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your values
```

4. Database setup:
```bash
# Create PostgreSQL database
createdb meetin

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

5. Start services:
```bash
# Start Redis
redis-server

# Start Celery worker (separate terminal)
celery -A meetin worker -l info

# Start Django development server
python manage.py runserver
```

The API runs at `http://localhost:8000`.

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django secret key (must be set, no default) |
| `DEBUG` | No | Debug mode (defaults to `False`) |
| `ALLOWED_HOSTS` | Yes (prod) | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | Yes (prod) | Comma-separated allowed CORS origins |
| `DB_NAME` | Yes | PostgreSQL database name |
| `DB_USER` | Yes | PostgreSQL user |
| `DB_PASSWORD` | Yes | PostgreSQL password |
| `DB_HOST` | No | Database host (default: `localhost`) |
| `DB_PORT` | No | Database port (default: `5432`) |
| `DEEPGRAM_API_KEY` | Yes | Deepgram API key for transcription |
| `OPENAI_API_KEY` | Yes* | OpenAI API key (*or Azure OpenAI) |
| `CELERY_BROKER_URL` | Yes | Redis URL for Celery broker |
| `CELERY_RESULT_BACKEND` | Yes | Redis URL for Celery results |
| `USE_S3` | No | Enable S3 storage (default: `False`) |

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register/` | User registration |
| `POST` | `/api/auth/login/` | Login (returns JWT access + refresh tokens) |
| `POST` | `/api/auth/refresh/` | Refresh access token |
| `POST` | `/api/auth/logout/` | Logout (blacklists refresh token) |
| `GET` | `/api/auth/profile/` | Get current user profile |

### Organizations
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/auth/organizations/` | List user organizations |
| `POST` | `/api/auth/organizations/` | Create organization |
| `GET/PUT/DELETE` | `/api/auth/organizations/{id}/` | Organization details (admin only) |
| `GET/POST` | `/api/auth/organizations/{id}/members/` | List/add members (admin only for add) |

### Meetings
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/meetings/` | List meetings |
| `POST` | `/api/meetings/` | Create meeting |
| `GET/PATCH/DELETE` | `/api/meetings/{id}/` | Meeting CRUD |

### Live Sessions
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/meetings/{id}/live/start/` | Start live transcription |
| `POST` | `/api/meetings/{id}/live/stop/` | Stop live transcription |
| `GET` | `/api/meetings/{id}/live/status/` | Get session status |

### Recordings
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/meetings/{id}/recordings/initiate/` | Initiate recording upload |
| `POST` | `/api/recordings/{id}/complete/` | Complete recording upload |

### Transcripts & Minutes
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/transcription/meetings/{id}/transcript/` | Get transcript |
| `POST` | `/api/transcription/meetings/{id}/minutes/generate/` | Generate minutes |
| `GET/PATCH` | `/api/transcription/meetings/{id}/minutes/` | Get/update minutes |
| `GET` | `/api/transcription/meetings/{id}/action-items/` | List action items |

### AI Copilot
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/copilot/meetings/{id}/run/` | Run copilot analysis |
| `GET` | `/api/copilot/meetings/{id}/suggestions/` | Get suggestions |
| `POST` | `/api/copilot/meetings/{id}/speaker-map/` | Map speaker to user |

### WebSocket
- `ws://localhost:8000/ws/meetings/{meeting_id}/live/?token=<JWT>` — Live transcription

## Database Schema

| Table | Description |
|---|---|
| `users` | Custom user model with UUID primary keys |
| `organizations` | Multi-tenant organizations |
| `organization_members` | User roles (ADMIN, MEMBER, VIEWER) |
| `meetings` | Meeting records with language preferences |
| `live_sessions` | Real-time transcription sessions |
| `recordings` | Audio file recordings |
| `speakers` | Speaker identification and labeling |
| `transcripts` | Transcription records |
| `transcript_segments` | Individual segments with timing and speaker |
| `minutes` | AI-generated meeting minutes |
| `minutes_versions` | Version history for minutes edits |
| `action_items` | Extracted action items with assignments |
| `share_links` | Secure sharing links with permissions |
| `audit_logs` | Comprehensive audit trail |

## Security

- JWT authentication with token rotation and blacklisting
- RBAC enforcement (admin-only operations on organizations)
- Rate limiting: 30/min anonymous, 120/min authenticated, 10/min auth endpoints
- File upload validation (MIME type, size limit 500MB, extension whitelist)
- Path traversal protection on file operations
- Custom exception handler (no internal details leaked in production)
- Mass assignment protection via read-only serializer fields
- Input validation and sanitization on all endpoints
- Production auto-enables: HSTS, SSL redirect, secure cookies, CSRF protection

## Testing

```bash
python manage.py test
```

## Production Deployment

1. Set `SECRET_KEY` to a strong random value
2. Set `DEBUG=False`
3. Configure `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS`
4. Set up PostgreSQL and Redis
5. Configure SSL/TLS
6. Set `USE_S3=True` with S3 credentials for file storage
7. Run Celery workers: `celery -A meetin worker -l info`
8. Serve with gunicorn + uvicorn behind nginx:
   ```bash
   gunicorn meetin.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

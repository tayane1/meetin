# meetIN - Frontend

React 19 SPA with TypeScript and Material-UI for real-time meeting transcription and AI-powered minutes.

## Prerequisites

- Node.js 18+
- npm

## Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your values
```

3. Start development server:
```bash
npm start
```

The app runs at `http://localhost:3000` and proxies API requests to `http://localhost:8000`.

## Environment Variables

```bash
# Backend API URL
REACT_APP_API_URL=http://localhost:8000/api

# WebSocket host (no protocol prefix)
REACT_APP_WS_HOST=localhost:8000
```

For production:
```bash
REACT_APP_API_URL=https://api.yourdomain.com/api
REACT_APP_WS_HOST=api.yourdomain.com
```

## Project Structure

```
src/
├── components/          # React components
│   ├── LoginPage.tsx
│   ├── DashboardPage.tsx
│   ├── MeetingPage.tsx
│   └── ProtectedRoute.tsx
├── hooks/              # Custom React hooks
│   ├── useAuth.tsx
│   └── useMeeting.tsx
├── services/           # API and WebSocket services
│   ├── api.ts          # Axios instance with JWT interceptors
│   └── websocket.ts    # WebSocket client for live transcription
├── types/              # TypeScript type definitions
│   └── index.ts
├── utils/              # Utility functions
└── App.tsx             # Main application component
```

## Features

### Authentication
- JWT-based authentication with automatic token refresh
- Protected routes with redirect to login
- Secure logout with token blacklisting

### Real-time Transcription
- WebSocket connection for live updates
- Audio capture via Web Audio API (16kHz, 16-bit PCM)
- Automatic echo cancellation and noise suppression
- Speaker diarization with editable speaker names
- Live transcript display

### Meeting Management
- Create and manage meetings
- Organization-based access control
- Bilingual support (English / French)
- Live session controls (start, stop)

### AI Copilot
- Real-time suggestions during meetings
- Meeting minutes generation
- Action items extraction

### UI
- Material-UI components
- Responsive design
- Real-time status indicators

## WebSocket Integration

```typescript
import wsService from './services/websocket';

// Connect with JWT token
await wsService.connect(meetingId, token);
await wsService.startAudioCapture();

// Listen for events
wsService.on('transcript_segment', (data) => {
  // Handle new transcript segment
});

wsService.on('speaker_updated', (data) => {
  // Handle speaker name updates
});
```

## Browser Compatibility

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

Note: Safari requires user interaction before allowing microphone access.

## Build for Production

```bash
npm run build
```

Creates an optimized build in the `build/` directory.

## Testing

```bash
npm test
npm test -- --coverage
```

## Deployment

### Static Hosting (Vercel, Netlify, etc.)

1. `npm run build`
2. Deploy the `build/` directory
3. Set environment variables on the hosting platform
4. Ensure backend CORS allows the hosting domain

### Docker

```dockerfile
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

## Troubleshooting

### Audio Capture Issues
- Check browser microphone permissions
- HTTPS is required in production for `getUserMedia`
- Verify microphone is not blocked by browser settings

### WebSocket Connection Issues
- Verify backend is running on port 8000
- Check JWT token validity
- Ensure CORS is properly configured

### Build Issues
- Clear and reinstall: `rm -rf node_modules package-lock.json && npm install`
- Verify Node.js 18+ is installed

# Spark - Serious Dating App PRD

## Original Problem Statement
Build a modern swipe-based serious dating/matrimony app like Tinder but better for serious relationships. No nonsense, easy to navigate, mobile-friendly, funky, stylish and attractive for Gen Z and Millennials.

## Architecture & Tech Stack
- **Frontend**: React.js with Tailwind CSS (Neo-Brutalist design)
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Payments**: Stripe (test mode)
- **AI**: OpenAI GPT via Emergent LLM Key

## User Personas
1. **Serious Daters (25-35)**: Looking for long-term relationships/marriage
2. **Gen Z Users (18-25)**: Want modern, no-nonsense dating experience
3. **Premium Users**: Willing to pay for enhanced features

## Core Requirements (Static)
- [x] User authentication (JWT-based)
- [x] Profile creation with photos, bio, preferences
- [x] Swipe cards (like/pass/super like)
- [x] Match system with expiry
- [x] Chat/messaging
- [x] AI compatibility scoring
- [x] AI icebreakers
- [x] AI date ideas
- [x] Video verification badge
- [x] Dealbreaker filters
- [x] Intentions badges
- [x] Slow dating mode
- [x] Stripe subscription (Premium/VIP tiers)
- [x] "Who Likes You" premium feature
- [x] Daily picks

## What's Been Implemented

### Phase 1 - MVP Complete (Jan 2026) ✅
- **Auth System**: Registration, login, JWT tokens
- **Profile System**: 5-step onboarding wizard
- **Compatibility Quiz**: 4-step quiz for better matching
- **Discovery**: Swipe deck with profile cards
- **Matching**: Like/Pass/Super Like with match detection
- **Chat**: Messaging with AI icebreakers
- **Subscriptions**: Stripe checkout for Premium ($19.99/mo) and VIP ($39.99/mo)
- **Safety**: Date check-in feature
- **Design**: Neo-Brutalist style with Syne/DM Sans fonts

### Phase 2 - Real-time & Real AI (Feb 2026) ✅
- **Real AI** via Emergent LLM Key + GPT-4o:
  - Compatibility scoring with persisted insights & challenge
  - Profile-specific icebreakers (no longer hardcoded fallback)
  - Location-aware date ideas
  - Fixed: `extract_json()` helper handles markdown-wrapped responses
- **Real-time Chat (WebSockets)** at `/api/ws/chat/{match_id}?token=<jwt>`:
  - Instant message delivery to peer
  - Typing indicators
  - Online/offline presence
- **Voice Notes** via `POST /api/messages/voice` (multipart, 2MB cap, base64 data URL)
- **Stripe Checkout** verified end-to-end (test key, real session URLs)
- **Backend Tests**: 17 pytest cases at `/app/backend/tests/backend_test.py` — 100% passing

### Demo Data Seeded
- 5 demo profiles (demo1-5@spark.app, password: password123)
- See `/app/memory/test_credentials.md` for details

## Prioritized Backlog

### P0 (Critical)
- [x] Voice notes in chat (Feb 2026)
- [x] Real-time chat WebSockets (Feb 2026)
- [x] Real AI compatibility + icebreakers (Feb 2026)
- [ ] Video date feature (in-app calls)
- [ ] Push notifications
- [ ] Profile photo upload (currently uses URLs)

### P1 (High Priority)
- [ ] Refactor `App.js` (2154 lines) into modular components
- [ ] Background check integration
- [ ] Mutual friends indicator
- [ ] Match expiry notifications
- [ ] Voice note storage → S3/object storage (currently inline base64)
- [ ] WebSocket scale-out via Redis pub/sub
- [ ] Rate limiting on AI endpoints

### P2 (Medium Priority)
- [ ] Profile boost implementation
- [ ] Daily picks page
- [ ] Video verification flow (actual camera capture)
- [ ] Profile activity status (last active)

### P3 (Nice to Have)
- [ ] Advanced filters (height, education, etc.)
- [ ] Incognito mode
- [ ] Read receipts (VIP feature)
- [ ] Profile prompts

## API Endpoints

### Auth
- POST `/api/auth/register` - User registration
- POST `/api/auth/login` - User login
- GET `/api/auth/me` - Get current user

### Profile
- PUT `/api/profile` - Update profile
- PUT `/api/profile/quiz` - Save compatibility quiz
- GET `/api/profile/{user_id}` - Get user profile
- POST `/api/profile/verify-video` - Video verification

### Discovery
- GET `/api/discover` - Get profiles to swipe
- GET `/api/discover/daily-picks` - AI-curated picks
- POST `/api/swipe` - Record swipe action

### Matches & Chat
- GET `/api/matches` - Get user's matches
- GET `/api/likes-you` - Who liked current user (premium)
- GET `/api/messages/{match_id}` - Get messages
- POST `/api/messages` - Send message
- POST `/api/unmatch/{match_id}` - Unmatch

### AI Features
- POST `/api/ai/compatibility/{user_id}` - Calculate compatibility
- GET `/api/ai/icebreakers/{match_id}` - Get icebreakers
- GET `/api/ai/date-ideas` - Get date suggestions

### Payments
- GET `/api/subscription/plans` - Get plans
- POST `/api/subscription/checkout` - Create checkout session
- GET `/api/subscription/status/{session_id}` - Check payment

### Safety
- POST `/api/safety/checkin` - Create date check-in
- POST `/api/safety/checkin/{id}/confirm` - Confirm safe

## Next Tasks
1. Implement voice notes in chat
2. Add photo upload functionality
3. Build video verification flow
4. Add push notifications
5. Implement profile boost feature

## Revenue Model
- **Free Tier**: 10 swipes/day, 1 super like/day
- **Premium** ($19.99/mo or $119.99/yr): Unlimited swipes, 5 super likes, see who likes you, 1 boost/week
- **VIP** ($39.99/mo or $239.99/yr): All Premium + unlimited super likes, 3 boosts/week, read receipts, priority support

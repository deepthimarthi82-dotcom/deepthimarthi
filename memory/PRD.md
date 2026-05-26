# Spark - Serious Dating App PRD

## Original Problem Statement
Build a modern swipe-based serious dating/matrimony app like Tinder but better for serious relationships. No nonsense, easy to navigate, mobile-friendly, funky, stylish and attractive for Gen Z and Millennials. Plus: every feature missing from current dating apps — AI-powered compatibility, premium tier, safety center, transparency, wellness, AI date planning.

## Architecture & Tech Stack
- **Frontend**: React.js with Tailwind CSS (Neo-Brutalist design)
- **Backend**: FastAPI (Python), Motor (Async MongoDB), WebSockets
- **Database**: MongoDB
- **Payments**: Stripe (test mode)
- **AI**: OpenAI GPT-4o via Emergent LLM Key
- **Email**: Resend (placeholder API key)
- **Security**: AES-256 message encryption at rest, bcrypt 12-rounds, SlowAPI rate-limit

## User Personas
1. Serious Daters (25-35) — Long-term relationships / matrimony
2. Gen Z (18-25) — Modern, no-nonsense, safety-first dating
3. Premium subscribers — willing to pay for AI + transparency tools

## What's Been Implemented

### Phase 1 — MVP (Jan 2026)
- JWT auth, 5-step onboarding, swipe deck, matches, chat with AI icebreakers, Stripe checkout, Neo-Brutalist UI.

### Phase 2 — Real-time + Real AI (Feb 2026)
- Real-time WebSocket chat (`/api/ws/chat/{match_id}`)
- GPT-4o compatibility scoring, profile-specific icebreakers, location-aware date ideas
- Date Vault (AI recap at 10+ messages), Voice notes, full Stripe E2E

### Phase 3 — Security + Free vs Premium overhaul (Feb 2026)
- AES-256 message encryption, bcrypt 12-rounds, SlowAPI rate-limit, 2FA UI, account deletion, photo right-click disable, DOB age-gate, Resend support ticket emails, support center, undo swipe, profile boost, viewers.

### Phase 4 — Batch A: Wellness + Transparency (Feb 2026)
- Wellness limits (30 swipes/day, take-break, mood streak with support nudge)
- Transparency scores + badges, Profile completeness bar, Today's Spark daily pick
- Match Anniversaries (7/30/90 day windows), Chat Health Score + AI Reignite topics
- Growth goals, Icebreaker prompts, Anti-ghosting pledge
- 26/26 backend tests pass (iter 6)

### Phase 5 — Batch B: Trust + Safety + Personality (Feb 2026) ✅
- **Personality DNA** (10-question Big Five test, 0-100 trait scores, archetype, 40% match weight)
- **Post-Date Check-in** (scheduled with grace period, auto-email to emergency contact via Resend if unconfirmed)
- **Safe Meeting Zones** (15 curated public spots + 5 first-date safety tips, optional city filter)
- **Live Location Sharing** (per match, 15-240 min, auto-expires)
- **Verified Photo Badge** (live selfie capture + GPT-4o compare with primary photo)
- **Background Lite Check** (name + DOB + country, stored as sha256 hash only)
- Discover ranking now reports `personality_score` per profile
- 23/24 backend tests pass (iter 7) — 1 HIGH bug fixed (personality compat 404 → graceful response)

## Prioritized Backlog

### P0
- [ ] Compatibility Timeline (predicted relationship milestones)
- [ ] First Date Script (AI-generated guide after 10 messages)
- [ ] Weekly Spark Challenge (Monday prompts + XP/badges)

### P1
- [ ] **Refactor App.js (4100+ lines) into pages/components** — recurring debt
- [ ] **Refactor server.py (2870+ lines) into routers/** — recurring debt
- [ ] Cron worker for /safety/run-post-date-alerts (currently caller-triggered)
- [ ] Real third-party background check (Checkr / IDology) integration
- [ ] Vision selfie verify — attach actual ImageContent blocks (currently text-only heuristic)
- [ ] TTL index on `location_shares.expires_at`
- [ ] Voice note storage → S3/object storage (currently inline base64)

### P2
- [ ] Push notifications
- [ ] Profile photo upload (currently URLs)
- [ ] Video date feature (in-app calls)
- [ ] Profile activity status (last active)
- [ ] Advanced filters (height, education, etc.)

### P3
- [ ] Incognito mode
- [ ] Read receipts (VIP)
- [ ] Replace native datetime-local input on post-date checkin with shadcn DateTime picker
- [ ] Fix React hydration warning on /profile routes

## Key API Endpoints (Batch B additions)

### Personality DNA
- GET `/api/personality/questions`
- PUT `/api/personality/dna`
- GET `/api/personality/dna/{user_id}`
- GET `/api/personality/compatibility/{target_user_id}`

### Post-Date Safety
- POST `/api/safety/post-date-checkin`
- POST `/api/safety/post-date-checkin/{id}/confirm`
- POST `/api/safety/post-date-checkin/{id}/snooze`
- GET `/api/safety/post-date-checkins`
- POST `/api/safety/run-post-date-alerts`

### Safe Zones & Location
- GET `/api/safety/zones?city=`
- POST `/api/safety/share-location`
- GET `/api/safety/share-location/{match_id}`
- DELETE `/api/safety/share-location/{match_id}`

### Verification
- POST `/api/profile/selfie-verify`
- POST `/api/profile/background-lite`
- GET `/api/profile/badges/{user_id}`

## Revenue Model
- **Free**: 30 swipes/day, 1 super like/day
- **Premium** ($19.99/mo, $119.99/yr): Unlimited swipes, see likes, AI Date Planner, Vibe Check, Voice msgs, Boost
- **VIP** ($39.99/mo, $239.99/yr): All Premium + unlimited super likes, 3 boosts/wk, read receipts, priority

## Next Tasks
1. Refactor App.js + server.py (recurring tech debt)
2. Compatibility Timeline page
3. First Date Script AI generator
4. Weekly Spark Challenge with XP/badges
5. Wire cron for post-date auto-alerts (currently manual sweeper)

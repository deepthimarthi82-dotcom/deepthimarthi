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

### Phase 6 — Batch C: Engagement & Gamification (Feb 2026) ✅
- **Compatibility Timeline** — GPT-4o generates 6 predicted milestones per match (first call, exclusivity, etc.) with confidence ratings, cached 7d
- **First Date Script** — Locks until 10+ messages; then GPT-4o produces openers, deeper questions, topics to avoid, venue suggestions, tone. Cached 24h
- **Weekly Spark Challenge + XP/Levels/Badges**
  - 12 rotating challenges, deterministic per ISO week
  - Per-user XP, level (14 tiers), streak weeks
  - Streak-based badges: Month of Sparks (4w), Quarter Champion (12w), Spark Year-One (52w)
  - Level-based badges: Rising Spark (L5), Spark Pro (L10)
  - Leaderboard (top 10 + my_rank) + history (50 latest)
- 20/20 backend tests pass + 5/5 frontend routes — zero critical issues (iter 8)

### Phase 7 — Push + Photo Uploads + Cron (Feb 2026) ✅
- **Web Push Notifications** — self-hosted VAPID, service worker, subscribe/unsubscribe + test push
  - Auto-fires on new match, new message, post-date checkin near alert, Monday weekly challenge nudge
  - 410 Gone subscriptions auto-deactivated
- **Photo Uploads** — Emergent Object Storage (uses EMERGENT_LLM_KEY)
  - POST `/api/profile/photo/upload` (multipart, 5MB max, JPEG/PNG/WebP)
  - GET `/api/files/{path}` streams bytes, DELETE soft-deletes from photos[]
  - Frontend `/photos` page with MAIN badge + trash
- **APScheduler Cron Worker** — runs every 5 min: `_sweep_post_date_alerts` for ALL users (no auth context needed)
  - Monday 09:00 UTC: weekly challenge push to all users active in last 30 days
- 16/16 backend tests pass + 3/3 frontend routes — zero critical issues (iter 9)

### Phase 8 — TTL Index + Profile Activity Status (Feb 2026) ✅
- TTL index `ttl_expires_at` on `location_shares.expires_at` (`expireAfterSeconds=0`); schema migrated to BSON datetime
- Profile activity: `last_active_human` ("Active now", "Active 12m ago", "Active 3h ago", "Active 2d ago", "Active 4w ago") + `is_online` (5-min window)
- Surfaced on `/api/discover`, `/api/profile/{id}`, `/api/matches`
- Auto-bumped on every auth'd request via `get_current_user` (throttled 60s)
- 17/17 backend + 2/2 frontend testid groups pass (iter 10)

### Phase 9 — Advanced Filters (Feb 2026) ✅
- 11 new profile fields: height_cm, body_type, drinking, smoking, cannabis, religion, politics, has_kids, wants_kids, exercise, pets
- **Free filters**: age range (18-120), distance, recently-active-only
- **Premium filters**: height range (cm), education, body type, drinking, smoking, cannabis, religion, politics, kids (has/wants), exercise, pets, "must be verified", "must have personality DNA"
- Endpoints: `GET/PUT/DELETE /api/me/filters` with validation (age_min<=age_max, height_cm bounds, etc.)
- Free user's PUT silently drops premium-only keys
- `/api/discover` applies all filters (DB-side for indexable fields, post-query for computed distance)
- Frontend `/filters` page with sticky save/clear bar + premium gate
- 17/17 backend + 100% frontend pass (iter 11)

## Prioritized Backlog

### P0
- [x] Compatibility Timeline ✅ (Feb 2026)
- [x] First Date Script ✅ (Feb 2026)
- [x] Weekly Spark Challenge with XP + badges ✅ (Feb 2026)

### P1
- [ ] **Refactor App.js (4240+ lines) into pages/components** — recurring debt
- [ ] **Refactor server.py (3610+ lines) into routers/** — recurring debt
- [x] Cron worker for /safety/run-post-date-alerts ✅ (Feb 2026)
- [ ] Real third-party background check (Checkr / IDology) integration
- [ ] Vision selfie verify — attach actual ImageContent blocks (currently text-only heuristic)
- [x] TTL index on `location_shares.expires_at` ✅ (Feb 2026)
- [ ] Voice note storage → S3/object storage (currently inline base64)
- [x] Photo uploads via Emergent Object Storage ✅ (Feb 2026)

### P2
- [x] Push notifications ✅ (Feb 2026)
- [ ] Video date feature (in-app calls)
- [x] Profile activity status (last active) ✅ (Feb 2026)
- [x] Advanced filters (height, education, etc.) ✅ (Feb 2026)

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

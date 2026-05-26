# Spark - Test Credentials

All non-admin demo users share password: **password123**

| Email | Name | Subscription | Notes |
|-------|------|--------------|-------|
| demo1@spark.app | Emma | free | Woman → men, match w/ demo2 |
| demo2@spark.app | James | free | Man → women, match w/ demo1 |
| demo3@spark.app | (seeded) | free | |
| demo4@spark.app | (seeded) | free | |
| demo5@spark.app | (seeded) | free | |
| **deepthimarthi82@gmail.com** | Deepthi | **VIP (admin)** | Password: `Spark2026!` — Admin auto-VIP |
| **vikaskesiraju@gmail.com** | Vikas | **VIP (admin)** | Password: `Spark2026!` — Admin auto-VIP |

## Existing Test Data
- Match `0a019632-6f9f-45ab-8fb6-20601b4e60f3` between demo1 (Emma) and demo2 (James)
- demo1 has emergency_contact_name=Mom, phone=+15551234567, distance_unit=km, language_filter_enabled=true (set during iteration 3 testing)

## Free vs Premium (Feb 2026 update)
- **Free**: 20 likes/day, unlimited messaging, basic features
- **Premium**: Unlimited swipes, See likes unblurred, AI Date Planner, Vibe Check Report, Voice messages, Read receipts, Boost, Global Passport, Undo swipe, Advanced filters, Profile viewers
- **Admin emails** (deepthimarthi82@gmail.com + vikaskesiraju@gmail.com) → permanent VIP, no expiry

## Integrations
- `EMERGENT_LLM_KEY` set in `/app/backend/.env` (GPT-4o for AI features)
- `STRIPE_API_KEY=sk_test_emergent` (test only — no real charges)
- Nominatim (OpenStreetMap) for geocoding — no key required

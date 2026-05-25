# Spark - Test Credentials

All demo users share the same password: **password123**

| Email | Name | Gender | Looking For | Notes |
|-------|------|--------|-------------|-------|
| demo1@spark.app | Emma | woman | men | Has match with demo2 (James) |
| demo2@spark.app | James | man | women | Has match with demo1 (Emma) |
| demo3@spark.app | (seeded) | — | — | |
| demo4@spark.app | (seeded) | — | — | |
| demo5@spark.app | (seeded) | — | — | |

## Existing Test Data
- Match `0a019632-6f9f-45ab-8fb6-20601b4e60f3` between demo1 (Emma) and demo2 (James) — `has_messaged=true`

## Integrations
- `EMERGENT_LLM_KEY` — set in `/app/backend/.env` (AI features use OpenAI `gpt-4o` via emergentintegrations)
- `STRIPE_API_KEY=sk_test_emergent` — Emergent-managed Stripe test key (no real charges)

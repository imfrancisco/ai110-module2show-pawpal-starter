# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```
# e.g.:
# Daily plan for Biscuit (Golden Retriever):
#   08:00 — Morning walk (30 min) [priority: high]
#   09:00 — Feeding (10 min) [priority: high]
#   ...
```

<!-- ==================================================
  PawPal+  |  Jordan's pets: Biscuit, Mochi
==================================================
Daily plan for Today:
  08:00 — Biscuit — Morning walk (30 min) [priority: high]
  08:30 — Biscuit — Breakfast (10 min) [priority: high]
  08:40 — Mochi — Breakfast (10 min) [priority: high]
  08:50 — Mochi — Medication (5 min) [priority: medium]
  08:55 — Mochi — Play time (15 min) [priority: low]
  09:10 — Biscuit — Training (20 min) [priority: low]
  Total scheduled time: 90 min

Why this plan?
- Placed Biscuit's 'Morning walk' at 08:00 (priority: high, 30 min).
- Placed Biscuit's 'Breakfast' at 08:30 (priority: high, 10 min).
- Placed Mochi's 'Breakfast' at 08:40 (priority: high, 10 min).
- Placed Mochi's 'Medication' at 08:50 (priority: medium, 5 min).
- Placed Mochi's 'Play time' at 08:55 (priority: low, 15 min).
- Placed Biscuit's 'Training' at 09:10 (priority: low, 20 min).
- Scheduled 6 of 6 task(s), using 90 min of available time. -->

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
# Paste your pytest output here

<!-- ============================================================== test session starts ==============================================================
platform win32 -- Python 3.14.5, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Francisco\Documents\CodePath Courses\Ai Engineering\Projects\PawPal+\ai110-module2show-pawpal-starter
plugins: anyio-4.14.2
collected 2 items                                                                                                                                

tests\test_pawpal.py ..                                                                                                                    [100%]

=============================================================== 2 passed in 0.03s =============================================================== -->
```

## 📐 Smarter Scheduling

> Fill in once you've implemented scheduling logic.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | | e.g., by priority, duration |
| Filtering | | e.g., skip tasks if time runs out |
| Conflict handling | | e.g., overlapping time slots |
| Recurring tasks | | e.g., daily vs. weekly |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->

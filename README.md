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

Beyond the core greedy planner, PawPal+ adds four "smart" behaviors. Each is a
small, pure, unit-tested function in [`pawpal_system.py`](pawpal_system.py) with
a thin `Scheduler` method wrapper, so the UI can use them without re-running the
whole planner. The table summarizes them; the subsections below explain each and
**name the method that implements it**.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_by_time()` → `sort_by_time()` | Chronological by preferred time; a `"HH:MM"` string key sorts as text, untimed tasks go last |
| Filtering | `Scheduler.filter_tasks_by()`, `filter_by_pet()`, `filter_by_status()` | Filter by pet name and/or completion status |
| Conflict handling | `Scheduler.conflict_warnings()` → `detect_conflicts()` | Duration-aware overlap on preferred times; returns warnings, never crashes |
| Recurring tasks | `Scheduler.mark_task_complete()` → `Task.create_next_occurrence()` | Completing a daily/weekly task spawns the next occurrence via `timedelta` |
| Sorting/planning (core) | `Scheduler.sort_tasks()`, `build_schedule()` | Priority-first ordering + greedy first-fit packing |

### 1. Sorting behavior — `Scheduler.sort_by_time()`

Orders tasks chronologically by their `preferred_time`. The key trick: a
zero-padded 24-hour `"HH:MM"` string sorts correctly as plain text
(`"08:00" < "09:15" < "17:30"`), so the lambda key is just the string itself,
with a `"99:99"` sentinel to push untimed tasks to the end. `O(n log n)`.

```python
scheduler.sort_by_time(owner.get_all_tasks())   # earliest preferred time first
```

### 2. Filtering behavior — `Scheduler.filter_tasks_by()`

Filters a task list by **pet name**, **completion status**, or both in one call
(each argument is optional; `None` means "don't filter on that field"). Backed by
the granular helpers `filter_by_pet()` and `filter_by_status()`. Returns a new
list and never mutates the input.

```python
scheduler.filter_tasks_by(tasks, pet_name="Biscuit")            # just Biscuit's tasks
scheduler.filter_tasks_by(tasks, completed=False)               # only pending tasks
scheduler.filter_tasks_by(tasks, "Biscuit", completed=True)     # Biscuit's done tasks
```

### 3. Conflict detection — `Scheduler.conflict_warnings()` / `detect_conflicts()`

`detect_conflicts()` finds pairs of tasks whose **preferred-time ranges overlap**
(duration-aware, not just exact start-time matches) using a sort-and-sweep with
an early break. `conflict_warnings()` wraps it in a lightweight, "warn-don't-crash"
layer that returns friendly strings and distinguishes a **same-pet** clash
(impossible) from a **different-pets** clash (okay only if someone helps). A
missing or malformed time is skipped, so it never raises.

```python
for warning in scheduler.conflict_warnings():
    print(warning)
# ⚠ Conflict: Biscuit's 'Morning walk' and 'Vitamins' overlap by 5 min
#   (wanted 08:00 & 08:00) — same pet — these can't happen at the same time.
```

### 4. Recurring task logic — `Scheduler.mark_task_complete()` / `Task.create_next_occurrence()`

Tasks carry a `frequency` (`"none"`/`"daily"`/`"weekly"`) and a `due_date`.
Completing a recurring task through `Scheduler.mark_task_complete()` (which
delegates to `Pet.mark_task_complete()`) automatically spawns a fresh next
occurrence via `Task.create_next_occurrence()`, advancing the due date with
`datetime.timedelta` (daily → +1 day, weekly → +7 days). One-off tasks simply
complete and spawn nothing.

```python
spawned = scheduler.mark_task_complete(task_id)     # daily task due 2026-07-12
# -> new occurrence due 2026-07-13, uncompleted, with a new task_id
```

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->

"""PawPal+ — Scheduler brain tests (Module 2, testing & verification phase).

These tests exercise the core planning engine in pawpal_system.py: how the
Scheduler orders tasks by priority, greedily packs them into the owner's real
clock-time availability windows, and records reasoning. They cover both the
"happy path" (everything fits) and the edge cases called out in the assignment
test plan (a pet with no tasks, two tasks at the exact same time, a task too
long to fit, and an owner with no availability).

Run from the project root with:

    pytest tests/test_scheduler.py -v
"""

import os
import sys

# Make pawpal_system.py importable when tests run from the tests/ folder.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pawpal_system import (
    DailySchedule,
    Owner,
    Pet,
    Scheduler,
    Task,
    fmt_minutes,
    parse_hhmm,
)


# ---------------------------------------------------------------------------
# Helpers — build a small owner/pet fixture quickly.
# ---------------------------------------------------------------------------
def make_owner(available_hours=None):
    """Return an Owner with a single dog, optionally with custom availability."""
    owner = Owner("Jordan", available_hours=available_hours)
    owner.add_pet(Pet("Biscuit", "dog", age=4))
    return owner


# ===========================================================================
# CORE BEHAVIOR 1 — Priority-first ordering
# ===========================================================================
def test_sort_tasks_orders_high_priority_first():
    """sort_tasks() must place high-priority tasks before low-priority ones."""
    owner = make_owner(["08:00-20:00"])
    scheduler = Scheduler(owner)

    low = Task("Play", "enrichment", 15, "low", preferred_time="08:00")
    high = Task("Meds", "medication", 5, "high", preferred_time="18:00")
    medium = Task("Brush", "grooming", 10, "medium", preferred_time="12:00")

    ordered = scheduler.sort_tasks([low, high, medium])

    # Priority dominates preferred time: high first even though it wants 18:00.
    assert [t.title for t in ordered] == ["Meds", "Brush", "Play"]


def test_sort_tasks_breaks_priority_ties_by_preferred_time():
    """Within the same priority, the earlier preferred_time wins the tie."""
    owner = make_owner(["08:00-20:00"])
    scheduler = Scheduler(owner)

    later = Task("Dinner", "feeding", 10, "high", preferred_time="17:00")
    earlier = Task("Breakfast", "feeding", 10, "high", preferred_time="08:00")

    ordered = scheduler.sort_tasks([later, earlier])

    assert [t.title for t in ordered] == ["Breakfast", "Dinner"]


# ===========================================================================
# CORE BEHAVIOR 2 — Greedy placement into real clock windows (HAPPY PATH)
# ===========================================================================
def test_build_schedule_places_tasks_at_real_clock_times():
    """A simple plan should assign each task a concrete HH:MM start, in order."""
    owner = make_owner(["08:00-12:00"])
    biscuit = owner.pets[0]
    biscuit.add_task(Task("Morning walk", "walk", 30, "high", preferred_time="08:00"))
    biscuit.add_task(Task("Feeding", "feeding", 10, "high", preferred_time="08:30"))
    scheduler = Scheduler(owner)

    plan = scheduler.build_schedule(date="today")

    # Both tasks fit and are placed back-to-back from the window start.
    assert len(plan.scheduled_tasks) == 2
    walk = next(t for t in plan.scheduled_tasks if t.title == "Morning walk")
    feed = next(t for t in plan.scheduled_tasks if t.title == "Feeding")
    assert plan.time_slots[walk.task_id] == "08:00"
    assert plan.time_slots[feed.task_id] == "08:30"  # 08:00 + 30 min
    assert plan.total_duration == 40


def test_build_schedule_pools_tasks_from_multiple_pets():
    """Tasks from every pet the owner has should land in one combined plan."""
    owner = Owner("Jordan", available_hours=["08:00-12:00"])
    dog = Pet("Biscuit", "dog")
    cat = Pet("Mochi", "cat")
    dog.add_task(Task("Walk", "walk", 30, "high", preferred_time="08:00"))
    cat.add_task(Task("Feed", "feeding", 10, "high", preferred_time="09:00"))
    owner.add_pet(dog)
    owner.add_pet(cat)

    plan = Scheduler(owner).build_schedule()

    titles = {t.title for t in plan.scheduled_tasks}
    assert titles == {"Walk", "Feed"}
    # Each scheduled task still knows which pet it belongs to.
    who = {t.title: t.pet_name for t in plan.scheduled_tasks}
    assert who == {"Walk": "Biscuit", "Feed": "Mochi"}


def test_build_schedule_spills_into_second_window():
    """A task that won't fit the tail of window 1 should move to window 2."""
    owner = make_owner(["08:00-08:40", "17:00-20:00"])
    biscuit = owner.pets[0]
    biscuit.add_task(Task("Walk", "walk", 30, "high", preferred_time="08:00"))   # 08:00-08:30
    biscuit.add_task(Task("Training", "enrichment", 30, "high"))                 # 30 left? only 10
    scheduler = Scheduler(owner)

    plan = scheduler.build_schedule()

    slots = {t.title: plan.time_slots[t.task_id] for t in plan.scheduled_tasks}
    assert slots["Walk"] == "08:00"
    # Only 10 min remain in window 1 after the walk, so Training spills to 17:00.
    assert slots["Training"] == "17:00"


# ===========================================================================
# CORE BEHAVIOR 3 — Filtering out impossible tasks (with reasoning)
# ===========================================================================
def test_build_schedule_skips_task_too_long_for_any_window():
    """A task longer than all available time is skipped and explained."""
    owner = make_owner(["08:00-09:00"])  # only 60 minutes total
    biscuit = owner.pets[0]
    biscuit.add_task(Task("Marathon hike", "walk", 120, "high"))  # needs 120 min
    scheduler = Scheduler(owner)

    plan = scheduler.build_schedule()

    assert plan.scheduled_tasks == []
    assert any("Marathon hike" in note and "cannot fit" in note
               for note in plan.reasoning_notes)


def test_build_schedule_ignores_completed_and_nonpositive_tasks():
    """Completed tasks and zero/negative-duration tasks never get scheduled."""
    owner = make_owner(["08:00-20:00"])
    biscuit = owner.pets[0]
    done = Task("Already fed", "feeding", 10, "high")
    done.mark_complete()
    biscuit.add_task(done)
    biscuit.add_task(Task("Bad duration", "walk", 0, "high"))
    biscuit.add_task(Task("Real walk", "walk", 20, "high"))

    plan = Scheduler(owner).build_schedule()

    assert [t.title for t in plan.scheduled_tasks] == ["Real walk"]


# ===========================================================================
# EDGE CASE — A pet with NO tasks
# ===========================================================================
def test_build_schedule_empty_pet_yields_empty_plan():
    """A pet with no tasks should produce an empty, non-crashing schedule."""
    owner = make_owner(["08:00-12:00"])  # Biscuit has zero tasks

    plan = Scheduler(owner).build_schedule(date="today")

    assert plan.scheduled_tasks == []
    assert plan.total_duration == 0
    # display_schedule must still render cleanly.
    assert "(no tasks scheduled)" in plan.display_schedule()


# ===========================================================================
# EDGE CASE — Two tasks at the EXACT same time
# ===========================================================================
def test_two_tasks_same_time_are_spaced_not_double_booked():
    """Two tasks wanting 08:00 must both be placed at distinct, non-overlapping times."""
    owner = make_owner(["08:00-12:00"])
    biscuit = owner.pets[0]
    biscuit.add_task(Task("Walk", "walk", 30, "high", preferred_time="08:00"))
    biscuit.add_task(Task("Vitamins", "medication", 5, "high", preferred_time="08:00"))
    scheduler = Scheduler(owner)

    plan = scheduler.build_schedule()

    starts = sorted(parse_hhmm(plan.time_slots[t.task_id]) for t in plan.scheduled_tasks)
    assert len(starts) == 2
    # The two start times differ — the greedy packer refused to double-book 08:00.
    assert starts[0] != starts[1]
    # And a conflict was explained to the owner.
    assert any("Conflict" in note for note in plan.reasoning_notes)


# ===========================================================================
# EDGE CASE — Owner with NO availability windows
# ===========================================================================
def test_build_schedule_no_availability_schedules_nothing():
    """With no valid windows, nothing is scheduled and the reason is recorded."""
    owner = Owner("Jordan", available_hours=["not-a-window", "25:00-99:00"])
    biscuit = Pet("Biscuit", "dog")
    biscuit.add_task(Task("Walk", "walk", 30, "high"))
    owner.add_pet(biscuit)

    plan = Scheduler(owner).build_schedule()

    assert plan.scheduled_tasks == []
    assert any("availability" in note.lower() for note in plan.reasoning_notes)


# ===========================================================================
# EDGE CASE — Boundary fit (task exactly fills the window)
# ===========================================================================
def test_task_exactly_filling_window_is_placed():
    """A 60-min task in a 60-min window fits exactly (<= boundary, not <)."""
    owner = make_owner(["08:00-09:00"])
    owner.pets[0].add_task(Task("Long groom", "grooming", 60, "high"))

    plan = Scheduler(owner).build_schedule()

    assert len(plan.scheduled_tasks) == 1
    assert plan.time_slots[plan.scheduled_tasks[0].task_id] == "08:00"


# ===========================================================================
# PERSISTENCE — round-trip through to_dict()/from_dict()
# ===========================================================================
def test_owner_survives_dict_round_trip():
    """Serializing then rebuilding an Owner must preserve pets, tasks, and IDs."""
    owner = make_owner(["08:00-12:00"])
    owner.pets[0].add_task(
        Task("Walk", "walk", 30, "high", preferred_time="08:00", frequency="daily")
    )
    original_id = owner.pets[0].tasks[0].task_id

    restored = Owner.from_dict(owner.to_dict())

    assert restored.owner_name == "Jordan"
    assert restored.available_hours == ["08:00-12:00"]
    assert len(restored.pets) == 1
    task = restored.pets[0].tasks[0]
    assert task.title == "Walk"
    assert task.task_id == original_id       # stable identity survives the round-trip
    assert task.frequency == "daily" and task.recurring is True


# ===========================================================================
# PURE HELPERS — time parsing/formatting round-trip and invalid input
# ===========================================================================
def test_parse_and_format_minutes_round_trip():
    """parse_hhmm() and fmt_minutes() should be inverses for valid times."""
    for text in ["00:00", "08:30", "17:05", "23:59"]:
        assert fmt_minutes(parse_hhmm(text)) == text


def test_parse_hhmm_rejects_invalid_times():
    """Malformed or out-of-range times return None instead of raising."""
    for bad in ["", "8", "8:00:00", "24:00", "12:60", "aa:bb", None]:
        assert parse_hhmm(bad) is None

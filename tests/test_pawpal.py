"""PawPal+ — basic behavior tests.

Run from the project root with:

    pytest
"""

import os
import sys
from datetime import date

# Make pawpal_system.py importable when tests run from the tests/ folder.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pawpal_system import (
    Owner,
    Pet,
    Scheduler,
    Task,
    detect_conflicts,
    filter_by_pet,
    filter_by_status,
    filter_tasks_by,
    reset_recurring,
    sort_by_time,
)


def test_mark_complete_changes_status():
    """Calling mark_complete() should flip a task's completed flag to True."""
    task = Task("Morning walk", "walk", 30, "high")

    # A new task starts out not completed.
    assert task.completed is False

    task.mark_complete()

    # After marking complete, the status should be True.
    assert task.completed is True


def test_add_task_increases_pet_task_count():
    """Adding a task to a Pet should increase that pet's task count by one."""
    pet = Pet("Biscuit", "dog")

    # A new pet starts with no tasks.
    assert len(pet.tasks) == 0

    pet.add_task(Task("Breakfast", "feeding", 10, "high"))

    # After adding one task, the count should be exactly one.
    assert len(pet.tasks) == 1


# ---------------------------------------------------------------------------
# Smart-logic features (algorithms phase): sort-by-time, filtering,
# recurring roll-over, and conflict detection.
# ---------------------------------------------------------------------------
def test_sort_by_time_orders_chronologically_untimed_last():
    """sort_by_time() should order by preferred_time, floating untimed tasks last."""
    evening = Task("Play", "enrichment", 15, "low", preferred_time="18:00")
    morning = Task("Walk", "walk", 30, "high", preferred_time="08:00")
    anytime = Task("Brush", "grooming", 10, "low")  # no preferred_time

    ordered = sort_by_time([evening, anytime, morning])

    # Earliest preferred time first; the untimed task sinks to the end.
    assert [t.title for t in ordered] == ["Walk", "Play", "Brush"]


def test_filter_by_pet_and_status():
    """filter_by_pet keeps one pet's tasks; filter_by_status splits done/pending."""
    dog = Pet("Biscuit", "dog")
    cat = Pet("Mochi", "cat")
    dog.add_task(Task("Walk", "walk", 30, "high"))
    dog_meds = Task("Meds", "medication", 5, "high")
    dog.add_task(dog_meds)
    cat.add_task(Task("Feed", "feeding", 10, "high"))
    all_tasks = dog.tasks + cat.tasks

    # filter_by_pet is case-insensitive and matches the stamped pet_name.
    biscuit_tasks = filter_by_pet(all_tasks, "biscuit")
    assert {t.title for t in biscuit_tasks} == {"Walk", "Meds"}

    # Before completing anything, everything is pending.
    assert len(filter_by_status(all_tasks, completed=False)) == 3
    assert filter_by_status(all_tasks, completed=True) == []

    dog_meds.mark_complete()
    assert len(filter_by_status(all_tasks, completed=False)) == 2
    assert filter_by_status(all_tasks, completed=True) == [dog_meds]


def test_filter_tasks_by_combines_pet_and_status():
    """filter_tasks_by should filter on pet, status, or both together."""
    dog = Pet("Biscuit", "dog")
    cat = Pet("Mochi", "cat")
    dog_walk = Task("Walk", "walk", 30, "high")
    dog_meds = Task("Meds", "medication", 5, "high")
    cat_feed = Task("Feed", "feeding", 10, "high")
    dog.add_task(dog_walk)
    dog.add_task(dog_meds)
    cat.add_task(cat_feed)
    all_tasks = dog.tasks + cat.tasks

    dog_meds.mark_complete()

    # No arguments -> everything (a new list, not the same object).
    assert filter_tasks_by(all_tasks) == all_tasks
    assert filter_tasks_by(all_tasks) is not all_tasks

    # Pet only.
    assert {t.title for t in filter_tasks_by(all_tasks, pet_name="Biscuit")} == {"Walk", "Meds"}

    # Status only (pending vs completed).
    assert {t.title for t in filter_tasks_by(all_tasks, completed=False)} == {"Walk", "Feed"}

    # Both together: Biscuit's completed tasks -> just the meds.
    assert filter_tasks_by(all_tasks, pet_name="Biscuit", completed=True) == [dog_meds]


def test_reset_recurring_revives_only_recurring_tasks():
    """reset_recurring() should re-open completed recurring tasks, not one-offs."""
    recurring = Task("Feed", "feeding", 10, "high", recurring=True)
    one_off = Task("Vet visit", "other", 60, "high", recurring=False)
    recurring.mark_complete()
    one_off.mark_complete()

    revived = reset_recurring([recurring, one_off])

    assert revived == 1
    assert recurring.completed is False  # daily chore comes back
    assert one_off.completed is True     # one-off stays done


def test_detect_conflicts_finds_overlap_and_reports_minutes():
    """detect_conflicts() should catch overlapping preferred times with the right overlap."""
    breakfast = Task("Breakfast", "feeding", 10, "high", preferred_time="09:00")  # 09:00-09:10
    meds = Task("Medication", "medication", 5, "medium", preferred_time="09:05")  # 09:05-09:10
    walk = Task("Walk", "walk", 30, "high", preferred_time="10:00")               # no overlap
    floating = Task("Brush", "grooming", 15, "low")                               # no time -> ignored

    conflicts = detect_conflicts([walk, breakfast, meds, floating])

    # Exactly one clashing pair, ordered earlier-first, overlapping by 5 minutes.
    assert len(conflicts) == 1
    earlier, later, overlap = conflicts[0]
    assert (earlier.title, later.title) == ("Breakfast", "Medication")
    assert overlap == 5


def test_detect_conflicts_none_when_times_are_clear():
    """Back-to-back tasks that merely touch (end == next start) are not a conflict."""
    first = Task("A", "feeding", 30, "high", preferred_time="08:00")   # 08:00-08:30
    second = Task("B", "walk", 30, "high", preferred_time="08:30")     # starts exactly at 08:30

    assert detect_conflicts([first, second]) == []


# ---------------------------------------------------------------------------
# Recurring tasks: completing a daily/weekly task spawns the next occurrence
# (due date advanced with datetime.timedelta).
# ---------------------------------------------------------------------------
def test_frequency_marks_task_recurring():
    """A daily/weekly frequency should flag the task as recurring; 'none' should not."""
    daily = Task("Feed", "feeding", 10, "high", frequency="daily")
    once = Task("Vet", "other", 60, "high")

    assert daily.frequency == "daily" and daily.recurring is True and daily.is_recurring()
    assert once.frequency == "none" and once.is_recurring() is False


def test_daily_task_spawns_next_day_on_complete():
    """Completing a DAILY task adds a fresh occurrence due today + 1 day."""
    pet = Pet("Biscuit", "dog")
    pet.add_task(Task("Morning walk", "walk", 30, "high",
                      preferred_time="08:00", frequency="daily", due_date="2026-07-12"))
    original = pet.tasks[0]

    spawned = pet.mark_task_complete(original.task_id)

    # The original is now done; a brand-new, uncompleted occurrence was added.
    assert original.completed is True
    assert len(pet.tasks) == 2
    assert spawned is not None
    assert spawned.completed is False
    assert spawned.task_id != original.task_id      # a genuinely new instance
    assert spawned.due_date == "2026-07-13"          # today + timedelta(days=1)
    assert spawned.pet_name == "Biscuit"             # stamped onto the pet
    # Copied attributes carry over unchanged.
    assert (spawned.title, spawned.preferred_time, spawned.frequency) == (
        "Morning walk", "08:00", "daily")


def test_weekly_task_spawns_seven_days_later():
    """Completing a WEEKLY task advances the due date by 7 days."""
    pet = Pet("Biscuit", "dog")
    pet.add_task(Task("Bath", "grooming", 25, "medium",
                      frequency="weekly", due_date="2026-07-12"))

    spawned = pet.mark_task_complete(pet.tasks[0].task_id)

    assert spawned.due_date == "2026-07-19"          # today + timedelta(days=7)


def test_one_off_task_does_not_respawn():
    """Completing a one-off task marks it done and spawns nothing."""
    pet = Pet("Biscuit", "dog")
    pet.add_task(Task("Vet visit", "other", 60, "high"))

    spawned = pet.mark_task_complete(pet.tasks[0].task_id)

    assert spawned is None
    assert len(pet.tasks) == 1
    assert pet.tasks[0].completed is True


def test_next_occurrence_uses_today_when_no_due_date():
    """With no due_date, the next occurrence is measured from the given 'today'."""
    task = Task("Meds", "medication", 5, "high", frequency="daily")

    nxt = task.create_next_occurrence(today=date(2026, 12, 31))

    assert nxt.due_date == "2027-01-01"              # timedelta rolls the year over


def test_scheduler_mark_task_complete_finds_owning_pet():
    """Scheduler.mark_task_complete locates the right pet and spawns there."""
    owner = Owner("Jordan")
    dog = Pet("Biscuit", "dog")
    cat = Pet("Mochi", "cat")
    cat.add_task(Task("Feed", "feeding", 10, "high",
                      frequency="daily", due_date="2026-07-12"))
    owner.add_pet(dog)
    owner.add_pet(cat)
    scheduler = Scheduler(owner)
    target_id = cat.tasks[0].task_id

    spawned = scheduler.mark_task_complete(target_id, today=date(2026, 7, 12))

    assert spawned.due_date == "2026-07-13"
    assert len(cat.tasks) == 2          # spawned onto the cat, not the dog
    assert len(dog.tasks) == 0

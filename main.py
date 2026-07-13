"""PawPal+ — Terminal testing ground.

A temporary script to verify the logic layer works end to end before wiring it
into the Streamlit UI. Run it with:

    python main.py

Tasks are added OUT OF TIME ORDER, and several are recurring (daily/weekly), so
the demo can exercise every "make-it-smart" feature:

    1. Sorting tasks by time            (Scheduler.sort_by_time)
    2. Filtering by pet / status        (Scheduler.filter_tasks_by)
    3. Basic conflict detection         (Scheduler.detect_conflicts)
    4. Recurring tasks auto-respawn     (Scheduler.mark_task_complete + timedelta)
"""

import sys
from datetime import date

from pawpal_system import Owner, Pet, Scheduler, Task

# Make em dashes and arrows print cleanly on Windows terminals.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# A fixed "today" keeps the recurrence demo's due dates reproducible. In the
# real app the default is date.today().
TODAY = date(2026, 7, 12)


def banner(text: str) -> None:
    """Print a titled separator so each demo section is easy to spot."""
    print("\n" + "=" * 62)
    print(f"  {text}")
    print("=" * 62)


def show(tasks) -> None:
    """Print a compact one-line view of each task."""
    if not tasks:
        print("  (none)")
        return
    for t in tasks:
        when = t.preferred_time or "  --  "
        mark = "✓ done" if t.completed else "· todo"
        repeats = f" 🔁{t.frequency}" if t.frequency != "none" else ""
        due = f" due {t.due_date}" if t.due_date else ""
        print(f"  {when:>6}  {t.pet_name:<8} {t.title:<14} "
              f"[{t.priority:<6}] {mark}{repeats}{due}")


def main() -> None:
    owner = Owner(owner_name="Jordan", available_hours=["08:00-12:00", "17:00-20:00"])

    biscuit = Pet(pet_name="Biscuit", species="dog", age=4)
    mochi = Pet(pet_name="Mochi", species="cat", age=2)

    iso = TODAY.isoformat()
    # Added OUT OF ORDER on purpose. Feeding/meds/walks recur DAILY; the bath is
    # WEEKLY; Training and Play time are one-offs. The two 09:00-ish tasks overlap.
    biscuit.add_task(Task("Training", "enrichment", 20, "low", preferred_time="18:00"))
    biscuit.add_task(Task("Morning walk", "walk", 30, "high",
                          preferred_time="08:00", frequency="daily", due_date=iso))
    biscuit.add_task(Task("Breakfast", "feeding", 10, "high",
                          preferred_time="08:45", frequency="daily", due_date=iso))
    biscuit.add_task(Task("Bath", "grooming", 25, "medium",
                          preferred_time="10:00", frequency="weekly", due_date=iso))

    mochi.add_task(Task("Play time", "enrichment", 15, "low", preferred_time="17:30"))
    mochi.add_task(Task("Medication", "medication", 5, "medium",
                        preferred_time="09:05", frequency="daily", due_date=iso))
    mochi.add_task(Task("Breakfast", "feeding", 10, "high",
                        preferred_time="09:00", frequency="daily", due_date=iso))

    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    scheduler = Scheduler(owner)
    all_tasks = owner.get_all_tasks()

    banner("Tasks as entered (out of order)")
    show(all_tasks)

    # --- Feature 1: sort by time -------------------------------------------
    banner("Feature 1 — Scheduler.sort_by_time() (chronological)")
    show(scheduler.sort_by_time(all_tasks))

    # --- Feature 2: filter by pet / status ---------------------------------
    banner("Feature 2 — Scheduler.filter_tasks_by()")
    print("Only Biscuit's tasks:")
    show(scheduler.filter_tasks_by(all_tasks, pet_name="Biscuit"))

    # --- Feature 3: conflict detection -------------------------------------
    banner("Feature 3 — Scheduler.detect_conflicts() (on preferred times)")
    conflicts = scheduler.detect_conflicts(all_tasks)
    if not conflicts:
        print("  No preferred-time conflicts detected.")
    for earlier, later, overlap in conflicts:
        print(f"  ⚠ {earlier.pet_name}'s '{earlier.title}' ({earlier.preferred_time}) "
              f"overlaps '{later.title}' ({later.preferred_time}) by {overlap} min")

    # --- Feature 4: recurring tasks auto-respawn on completion -------------
    banner("Feature 4 — Completing a recurring task spawns the next occurrence")
    print(f"Assume today is {TODAY.isoformat()}.\n")

    walk = biscuit.tasks[1]        # daily
    bath = biscuit.tasks[3]        # weekly
    training = biscuit.tasks[0]    # one-off

    for task in (walk, bath, training):
        before = len(biscuit.tasks)
        spawned = scheduler.mark_task_complete(task.task_id, today=TODAY)
        after = len(biscuit.tasks)
        if spawned is None:
            print(f"  Completed '{task.title}' ({task.frequency}) — one-off, "
                  f"nothing respawned. (task count {before} -> {after})")
        else:
            print(f"  Completed '{task.title}' ({task.frequency}, due {task.due_date}) "
                  f"-> new occurrence due {spawned.due_date}. "
                  f"(task count {before} -> {after})")

    banner("Biscuit's tasks after completing today's chores")
    show(biscuit.tasks)


if __name__ == "__main__":
    main()

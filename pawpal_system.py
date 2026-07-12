"""PawPal+ — Logic Layer (backend classes).

This module is the "logic layer" ("brain") for PawPal+. It implements the
classes from the UML in reflection.md:

    Owner  1 --- * Pet  1 --- * Task
    Scheduler uses (Owner, Pets) -> produces DailySchedule

The Scheduler gathers every incomplete task across all of an owner's pets,
orders them by priority, greedily packs them into the owner's available time
windows as real clock times, and records human-readable reasoning for why each
task was placed or skipped.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Time helpers — convert between "HH:MM" strings and minutes-since-midnight.
# Keeping times as integers makes packing and conflict math simple and testable.
# ---------------------------------------------------------------------------
def parse_hhmm(value: str) -> Optional[int]:
    """Parse an 'HH:MM' string into minutes since midnight, or None if invalid."""
    if not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hours, minutes = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        return None
    return hours * 60 + minutes


def fmt_minutes(total_minutes: int) -> str:
    """Format minutes-since-midnight as an 'HH:MM' string."""
    total_minutes %= 24 * 60
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


# ---------------------------------------------------------------------------
# Task — a single care activity (feeding, walk, meds, appointment, etc.)
# ---------------------------------------------------------------------------
@dataclass
class Task:
    """Represents a single care activity for a pet."""

    # Maps priority labels -> numeric score so sorting is consistent and typo-safe.
    PRIORITY_SCORES = {"high": 3, "medium": 2, "low": 1}

    title: str
    task_type: str  # e.g. "walk", "feeding", "medication", "grooming"
    duration_minutes: int
    priority: str  # e.g. "high", "medium", "low"
    preferred_time: Optional[str] = None  # e.g. "08:00" or "morning"
    recurring: bool = False
    notes: str = ""
    completed: bool = False
    # Stable unique id so edit/remove never depend on the (non-unique) title.
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    # Back-reference to the owning pet, stamped by Pet.add_task(). Lets a
    # combined multi-pet plan show which pet each task belongs to.
    pet_name: Optional[str] = None

    def update_details(self, **changes) -> None:
        """Update one or more task attributes in place.

        Only existing, non-identity fields may be changed; unknown keys raise a
        clear error so typos fail loudly instead of silently doing nothing.
        """
        protected = {"task_id"}
        for key, value in changes.items():
            if key in protected or not hasattr(self, key):
                raise AttributeError(f"Task has no updatable attribute {key!r}")
            setattr(self, key, value)

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.completed = True

    def get_priority_score(self) -> int:
        """Return a numeric score for this task's priority (higher = sooner)."""
        return self.PRIORITY_SCORES.get(str(self.priority).lower(), 0)

    def preferred_minutes(self) -> Optional[int]:
        """Return preferred_time as minutes-since-midnight, or None if unset/loose."""
        return parse_hhmm(self.preferred_time) if self.preferred_time else None


# ---------------------------------------------------------------------------
# Pet — profile info + the pet's list of care tasks
# ---------------------------------------------------------------------------
@dataclass
class Pet:
    """Stores a pet's profile and its list of care tasks."""

    pet_name: str
    species: str
    age: Optional[int] = None
    care_needs: list[str] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task to this pet and stamp it with this pet's name."""
        task.pet_name = self.pet_name
        self.tasks.append(task)

    def _find_task(self, task_id: str) -> Task:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        raise KeyError(f"No task with id {task_id!r} on pet {self.pet_name!r}")

    def edit_task(self, task_id: str, **changes) -> None:
        """Edit an existing task identified by its stable task_id."""
        self._find_task(task_id).update_details(**changes)

    def remove_task(self, task_id: str) -> None:
        """Remove a task from this pet by its stable task_id."""
        task = self._find_task(task_id)
        self.tasks.remove(task)

    def get_task_list(self) -> list[Task]:
        """Return the list of tasks for this pet."""
        return self.tasks


# ---------------------------------------------------------------------------
# Owner — user profile + constraints, and access to all pets' tasks
# ---------------------------------------------------------------------------
class Owner:
    """Stores the owner's info, availability, and scheduling preferences."""

    # Attributes that can be set directly via update_preferences(); anything
    # else is treated as a free-form scheduling preference.
    _DIRECT_FIELDS = {"available_hours", "preferred_task_times"}

    def __init__(
        self,
        owner_name: str,
        available_hours: Optional[list[str]] = None,
        preferred_task_times: Optional[dict[str, str]] = None,
        task_preferences: Optional[dict[str, object]] = None,
    ) -> None:
        self.owner_name = owner_name
        # Availability as "HH:MM-HH:MM" window strings, e.g. "08:00-12:00".
        self.available_hours = available_hours or []
        self.preferred_task_times = preferred_task_times or {}
        self.task_preferences = task_preferences or {}
        self.pets: list[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        self.pets.append(pet)

    def update_preferences(self, **preferences) -> None:
        """Update the owner's preferences.

        Known keys (available_hours, preferred_task_times) are set directly;
        everything else is merged into the free-form task_preferences map.
        """
        for key, value in preferences.items():
            if key in self._DIRECT_FIELDS:
                setattr(self, key, value)
            else:
                self.task_preferences[key] = value

    def get_available_slots(self) -> list[str]:
        """Return the owner's available time windows.

        Falls back to a sensible full-day window if none were provided so the
        scheduler always has somewhere to place tasks.
        """
        return self.available_hours if self.available_hours else ["08:00-20:00"]

    def get_all_tasks(self) -> list[Task]:
        """Return every task across all of this owner's pets (for scheduling)."""
        all_tasks: list[Task] = []
        for pet in self.pets:
            all_tasks.extend(pet.tasks)
        return all_tasks


# ---------------------------------------------------------------------------
# DailySchedule — the final plan + reasoning
# ---------------------------------------------------------------------------
@dataclass
class DailySchedule:
    """Holds the final daily plan and can explain its reasoning."""

    date: Optional[str] = None
    scheduled_tasks: list[Task] = field(default_factory=list)
    total_duration: int = 0
    reasoning_notes: list[str] = field(default_factory=list)
    # task_id -> "HH:MM" start time, so display can order and label placements.
    time_slots: dict[str, str] = field(default_factory=dict)

    def add_task_to_plan(self, task: Task, time_slot: str) -> None:
        """Place a task into the plan at a given 'HH:MM' start time."""
        self.scheduled_tasks.append(task)
        self.time_slots[task.task_id] = time_slot
        self.total_duration += task.duration_minutes

    def add_reason(self, note: str) -> None:
        """Append a line of scheduling reasoning."""
        self.reasoning_notes.append(note)

    def _ordered(self) -> list[Task]:
        """Scheduled tasks ordered by their assigned start time."""
        return sorted(
            self.scheduled_tasks,
            key=lambda t: parse_hhmm(self.time_slots.get(t.task_id, "")) or 0,
        )

    def display_schedule(self) -> str:
        """Return a human-readable view of the schedule (README sample format)."""
        header = f"Daily plan{f' for {self.date}' if self.date else ''}:"
        if not self.scheduled_tasks:
            return header + "\n  (no tasks scheduled)"

        lines = [header]
        for task in self._ordered():
            start = self.time_slots.get(task.task_id, "--:--")
            who = f"{task.pet_name} — " if task.pet_name else ""
            lines.append(
                f"  {start} — {who}{task.title} "
                f"({task.duration_minutes} min) [priority: {task.priority}]"
            )
        lines.append(f"  Total scheduled time: {self.total_duration} min")
        return "\n".join(lines)

    def summarize_reasoning(self) -> str:
        """Explain why tasks were placed where they were."""
        if not self.reasoning_notes:
            return "No reasoning recorded."
        return "\n".join(f"- {note}" for note in self.reasoning_notes)


# ---------------------------------------------------------------------------
# Scheduler — turns owner constraints + pet tasks into a DailySchedule
# ---------------------------------------------------------------------------
class Scheduler:
    """The "brain": retrieves, organizes, and packs tasks into a daily plan.

    Schedules across ALL of an owner's pets by default (Owner 1 --- * Pet), or a
    specific subset if ``pets`` is provided. Availability and tasks are gathered
    lazily at build time (not cached in __init__) so edits made in the UI after
    the scheduler is created are always reflected.
    """

    def __init__(self, owner: Owner, pets: Optional[list[Pet]] = None) -> None:
        self.owner = owner
        # Default to every pet the owner has; allow narrowing to a subset.
        self.pets: list[Pet] = pets if pets is not None else owner.pets

    # -- gathering -----------------------------------------------------------
    def _gather_tasks(self) -> list[Task]:
        """Collect incomplete tasks from the scheduler's pets."""
        tasks: list[Task] = []
        for pet in self.pets:
            tasks.extend(t for t in pet.tasks if not t.completed)
        return tasks

    def _windows(self) -> list[tuple[int, int]]:
        """Parse the owner's availability into sorted (start, end) minute ranges."""
        ranges: list[tuple[int, int]] = []
        for window in self.owner.get_available_slots():
            bounds = str(window).split("-")
            if len(bounds) != 2:
                continue
            start, end = parse_hhmm(bounds[0]), parse_hhmm(bounds[1])
            if start is not None and end is not None and end > start:
                ranges.append((start, end))
        return sorted(ranges)

    # -- organizing ----------------------------------------------------------
    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Order tasks by priority (high first), then preferred time, then duration.

        Tradeoff: priority dominates preferred time — a high-priority task is
        placed before a low-priority one even if the low-priority task "wants" an
        earlier slot. Preferred time and shorter duration only break ties.
        """
        return sorted(
            tasks,
            key=lambda t: (
                -t.get_priority_score(),
                t.preferred_minutes() if t.preferred_minutes() is not None else 24 * 60,
                t.duration_minutes,
            ),
        )

    def filter_tasks(self, tasks: list[Task]) -> list[Task]:
        """Drop tasks that can never fit (completed, non-positive, or too long).

        Only removes tasks that are impossible regardless of ordering; the
        cumulative "ran out of time" decisions happen later in build_schedule().
        """
        total_available = sum(end - start for start, end in self._windows())
        eligible: list[Task] = []
        for task in tasks:
            if task.completed:
                continue
            if task.duration_minutes <= 0:
                continue
            if task.duration_minutes > total_available:
                continue
            eligible.append(task)
        return eligible

    # -- building ------------------------------------------------------------
    def build_schedule(self, date: Optional[str] = None) -> DailySchedule:
        """Build and return the daily schedule with reasoning."""
        schedule = DailySchedule(date=date)
        windows = self._windows()

        gathered = self._gather_tasks()
        eligible = self.filter_tasks(gathered)
        ordered = self.sort_tasks(eligible)

        # Report anything filtered out entirely (impossible to fit).
        for task in gathered:
            if task not in eligible:
                schedule.add_reason(
                    f"Skipped '{task.title}' — it cannot fit in the available time."
                )

        if not windows:
            schedule.add_reason("No valid availability windows; nothing scheduled.")
            return schedule

        # Greedy first-fit: keep a cursor moving forward through the windows.
        win_index = 0
        cursor = windows[0][0]
        for task in ordered:
            placed_at = self._place(task, windows, win_index, cursor)
            if placed_at is None:
                schedule.add_reason(
                    f"Skipped '{task.title}' ({task.duration_minutes} min) — "
                    f"no remaining slot large enough."
                )
                continue
            start_minute, win_index, cursor = placed_at
            slot = fmt_minutes(start_minute)
            schedule.add_task_to_plan(task, slot)
            who = f"{task.pet_name}'s " if task.pet_name else ""
            schedule.add_reason(
                f"Placed {who}'{task.title}' at {slot} "
                f"(priority: {task.priority}, {task.duration_minutes} min)."
            )

        schedule.add_reason(
            f"Scheduled {len(schedule.scheduled_tasks)} of {len(gathered)} task(s), "
            f"using {schedule.total_duration} min of available time."
        )
        return schedule

    def _place(
        self,
        task: Task,
        windows: list[tuple[int, int]],
        win_index: int,
        cursor: int,
    ) -> Optional[tuple[int, int, int]]:
        """First-fit a task from the current window onward.

        Returns (start_minute, new_win_index, new_cursor) or None if it can't fit.
        """
        j = win_index
        while j < len(windows):
            win_start, win_end = windows[j]
            start = cursor if j == win_index else win_start
            start = max(start, win_start)
            if start + task.duration_minutes <= win_end:
                return start, j, start + task.duration_minutes
            j += 1
        return None

    def explain_plan(self, date: Optional[str] = None) -> str:
        """Build a plan and return its reasoning as text."""
        return self.build_schedule(date=date).summarize_reasoning()


# ---------------------------------------------------------------------------
# Manual CLI check — run `python pawpal_system.py` to verify the "brain".
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    # Ensure em dashes etc. print cleanly on Windows terminals (UTF-8).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    owner = Owner("Jordan", available_hours=["08:00-12:00", "17:00-20:00"])

    biscuit = Pet("Biscuit", "dog", age=4)
    biscuit.add_task(Task("Morning walk", "walk", 30, "high", preferred_time="08:00"))
    biscuit.add_task(Task("Feeding", "feeding", 10, "high", preferred_time="08:30"))
    biscuit.add_task(Task("Training", "enrichment", 20, "low"))

    mochi = Pet("Mochi", "cat", age=2)
    mochi.add_task(Task("Feeding", "feeding", 10, "high", preferred_time="09:00"))
    mochi.add_task(Task("Medication", "medication", 5, "medium"))

    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    scheduler = Scheduler(owner)
    plan = scheduler.build_schedule(date="today")

    print(plan.display_schedule())
    print("\nReasoning:")
    print(plan.summarize_reasoning())

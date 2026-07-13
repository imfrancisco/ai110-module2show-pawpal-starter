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
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
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


def parse_date(value: Optional[str]) -> Optional[date]:
    """Parse an ISO 'YYYY-MM-DD' string into a date, or None if unset/invalid.

    Dates are stored on tasks as ISO strings (not date objects) so they survive
    the JSON round-trip in Owner.to_dict()/from_dict() unchanged.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


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
    # How many days each recurrence frequency advances the due date. "none" is
    # absent on purpose: a one-off task never spawns a next occurrence.
    RECURRENCE_DAYS = {"daily": 1, "weekly": 7}

    title: str
    task_type: str  # e.g. "walk", "feeding", "medication", "grooming"
    duration_minutes: int
    priority: str  # e.g. "high", "medium", "low"
    preferred_time: Optional[str] = None  # e.g. "08:00" or "morning"
    # How often this task repeats: "none", "daily", or "weekly". A daily/weekly
    # task auto-creates its next occurrence when completed (see create_next_occurrence).
    frequency: str = "none"
    # When this occurrence is due, as an ISO "YYYY-MM-DD" string (or None).
    due_date: Optional[str] = None
    recurring: bool = False
    notes: str = ""
    completed: bool = False
    # Stable unique id so edit/remove never depend on the (non-unique) title.
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    # Back-reference to the owning pet, stamped by Pet.add_task(). Lets a
    # combined multi-pet plan show which pet each task belongs to.
    pet_name: Optional[str] = None

    def __post_init__(self) -> None:
        """Normalize frequency and keep the legacy ``recurring`` flag in sync."""
        if self.frequency not in ("none", "daily", "weekly"):
            self.frequency = "none"
        # A daily/weekly task is by definition recurring; keep the older boolean
        # flag consistent so code that still checks ``recurring`` keeps working.
        if self.frequency in self.RECURRENCE_DAYS:
            self.recurring = True

    def is_recurring(self) -> bool:
        """True if this task repeats (has a daily/weekly frequency)."""
        return self.frequency in self.RECURRENCE_DAYS

    def create_next_occurrence(self, today: Optional[date] = None) -> Optional["Task"]:
        """Return a fresh Task for this task's next occurrence, or None if one-off.

        The next due date is computed with datetime.timedelta so it stays
        calendar-accurate across month/year boundaries: daily -> +1 day,
        weekly -> +7 days. The step is measured from this task's own due_date if
        it has one; otherwise from ``today`` (defaulting to the real current
        date). The new occurrence copies every attribute EXCEPT identity/state:
        it gets a brand-new task_id, starts uncompleted, and carries the advanced
        due date.
        """
        step = self.RECURRENCE_DAYS.get(self.frequency)
        if step is None:
            return None  # one-off task: nothing to schedule next.
        base = parse_date(self.due_date) or today or date.today()
        next_due = base + timedelta(days=step)
        return Task(
            title=self.title,
            task_type=self.task_type,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            preferred_time=self.preferred_time,
            frequency=self.frequency,
            due_date=next_due.isoformat(),
            recurring=self.recurring,
            notes=self.notes,
            completed=False,
            pet_name=self.pet_name,
        )

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

    def to_dict(self) -> dict:
        """Serialize this task to a plain dict (for saving to disk)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Rebuild a Task from a dict produced by to_dict()."""
        return cls(**data)


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
        """Return the task with the given id, or raise KeyError if not found."""
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

    def mark_task_complete(self, task_id: str, today: Optional[date] = None) -> Optional[Task]:
        """Mark a task complete and, if it recurs, spawn its next occurrence.

        This is the single place where completion and recurrence meet: it marks
        the finished task done, then asks it for its next occurrence (daily ->
        +1 day, weekly -> +7 days). Any spawned occurrence is added to THIS pet's
        task list (so it shows up in future plans) and returned; one-off tasks
        simply return None.
        """
        task = self._find_task(task_id)
        task.mark_complete()
        next_task = task.create_next_occurrence(today=today)
        if next_task is not None:
            self.add_task(next_task)  # stamps pet_name and appends
        return next_task

    def get_task_list(self) -> list[Task]:
        """Return the list of tasks for this pet."""
        return self.tasks

    def to_dict(self) -> dict:
        """Serialize this pet (and its tasks) to a plain dict."""
        return {
            "pet_name": self.pet_name,
            "species": self.species,
            "age": self.age,
            "care_needs": self.care_needs,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Pet":
        """Rebuild a Pet (and its tasks) from a dict produced by to_dict()."""
        pet = cls(
            pet_name=data["pet_name"],
            species=data["species"],
            age=data.get("age"),
            care_needs=list(data.get("care_needs", [])),
        )
        pet.tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        return pet


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

    def to_dict(self) -> dict:
        """Serialize this owner (and all pets/tasks) to a plain dict."""
        return {
            "owner_name": self.owner_name,
            "available_hours": self.available_hours,
            "preferred_task_times": self.preferred_task_times,
            "task_preferences": self.task_preferences,
            "pets": [pet.to_dict() for pet in self.pets],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Owner":
        """Rebuild an Owner (and all pets/tasks) from a dict produced by to_dict()."""
        owner = cls(
            owner_name=data["owner_name"],
            available_hours=list(data.get("available_hours", [])),
            preferred_task_times=dict(data.get("preferred_task_times", {})),
            task_preferences=dict(data.get("task_preferences", {})),
        )
        owner.pets = [Pet.from_dict(p) for p in data.get("pets", [])]
        return owner


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
# Smart-logic helpers — small, pure algorithms the Scheduler and UI can reuse.
#
# These are deliberately module-level *pure* functions (list in -> new list
# out, no hidden state): each is trivial to unit-test in isolation and can be
# called straight from the Streamlit UI as well as from the Scheduler. Keeping
# them separate from build_schedule() is what lets the app offer "sort by time"
# or "show only Biscuit's pending tasks" without re-running the whole planner.
# ---------------------------------------------------------------------------

# A sentinel "later than any real clock time" so untimed tasks sort to the END
# of a chronological list instead of the front. As a plain "HH:MM" string,
# "99:99" is greater than any real time ("23:59"), so string comparison alone
# pushes tasks with no preferred_time to the very end of the day.
_NO_TIME = "99:99"


def sort_by_time(tasks: list[Task]) -> list[Task]:
    """Return tasks ordered chronologically by their preferred_time attribute.

    How the lambda key works: a preferred_time written in zero-padded 24-hour
    "HH:MM" form sorts correctly with an ordinary *string* comparison —
    "08:00" < "09:15" < "17:30" — because every field is fixed-width, so
    comparing the text left-to-right compares the hours first, then the minutes.
    That lets sorted()'s ``key`` be the string itself; no int conversion needed.
    Tasks with no preferred_time fall back to the "99:99" sentinel so they land
    at the end of the list.

    This is the time-first counterpart to Scheduler.sort_tasks() (priority-first).
    O(n log n): a single Timsort over a cheap string key.
    """
    return sorted(tasks, key=lambda task: task.preferred_time or _NO_TIME)


def filter_by_pet(tasks: list[Task], pet_name: str) -> list[Task]:
    """Return only the tasks belonging to ``pet_name`` (case-insensitive)."""
    key = pet_name.strip().lower()
    return [t for t in tasks if (t.pet_name or "").lower() == key]


def filter_by_status(tasks: list[Task], completed: bool = False) -> list[Task]:
    """Return tasks whose completed flag matches ``completed`` (default: pending)."""
    return [t for t in tasks if t.completed == completed]


def filter_by_type(tasks: list[Task], task_type: str) -> list[Task]:
    """Return only the tasks of a given task_type (e.g. 'feeding', case-insensitive)."""
    key = task_type.strip().lower()
    return [t for t in tasks if t.task_type.lower() == key]


def filter_tasks_by(
    tasks: list[Task],
    pet_name: Optional[str] = None,
    completed: Optional[bool] = None,
) -> list[Task]:
    """Filter tasks by completion status and/or pet name in a single call.

    Both arguments are optional; a ``None`` argument means "don't filter on
    that field", so one method covers every combination:

        filter_tasks_by(tasks, pet_name="Biscuit")        # just Biscuit's tasks
        filter_tasks_by(tasks, completed=False)           # just pending tasks
        filter_tasks_by(tasks, "Biscuit", completed=True) # Biscuit's done tasks

    Returns a new list and never mutates the input. O(n) per active filter.
    """
    result = list(tasks)
    if pet_name is not None:
        key = pet_name.strip().lower()
        result = [t for t in result if (t.pet_name or "").lower() == key]
    if completed is not None:
        result = [t for t in result if t.completed == completed]
    return result


def reset_recurring(tasks: list[Task]) -> int:
    """Start a new day: bring recurring chores back by clearing their completed flag.

    A recurring task (feeding, meds, daily walk) is never "done for good" — it
    returns every day. One-off tasks are left completed and simply drop out of
    tomorrow's plan. Mutates the tasks in place and returns how many were reset
    so the caller can report "3 daily tasks are back for today."
    """
    reset = 0
    for task in tasks:
        if task.recurring and task.completed:
            task.completed = False
            reset += 1
    return reset


def _overlap_minutes(a: Task, b: Task) -> int:
    """Minutes two timed tasks overlap (0 if they don't).

    Canonical interval-overlap formula: the overlap starts at the later of the
    two start times and ends at the earlier of the two end times, clamped to 0.
    Both tasks must have a usable preferred_time (callers filter first).
    """
    start_a, start_b = a.preferred_minutes(), b.preferred_minutes()
    end_a, end_b = start_a + a.duration_minutes, start_b + b.duration_minutes
    return max(0, min(end_a, end_b) - max(start_a, start_b))


def detect_conflicts(tasks: list[Task]) -> list[tuple[Task, Task, int]]:
    """Find pairs of tasks the owner *wants* happening at the same time.

    A conflict is judged from each task's preferred_time + duration_minutes (the
    owner's *desired* plan), BEFORE the greedy packer reshuffles anything. Tasks
    with no preferred_time can float to any gap, so they never conflict.

    Algorithm — sort-and-sweep: sort the timed tasks by start (O(n log n)), then
    scan once. Two tasks overlap when the later one starts before the earlier one
    ends. Because the list is sorted by start, the moment a candidate starts at or
    after the current task's end we can stop comparing it against later tasks —
    they start even later. That early ``break`` keeps the common case near-linear
    instead of a full O(n^2) all-pairs comparison.

    Returns (earlier, later, overlap_minutes) tuples, ordered by start time.
    """
    timed = sorted(
        (t for t in tasks if t.preferred_minutes() is not None),
        key=lambda t: t.preferred_minutes(),
    )
    conflicts: list[tuple[Task, Task, int]] = []
    for i, earlier in enumerate(timed):
        end_a = earlier.preferred_minutes() + earlier.duration_minutes
        for later in timed[i + 1:]:
            if later.preferred_minutes() >= end_a:
                break  # sorted by start: nothing after this can overlap `earlier`
            overlap = _overlap_minutes(earlier, later)
            if overlap > 0:
                conflicts.append((earlier, later, overlap))
    return conflicts


def conflict_warnings(tasks: list[Task]) -> list[str]:
    """Turn overlapping tasks into lightweight, human-readable warning strings.

    This is the "warn, don't crash" layer over detect_conflicts(): it never
    raises, always returns a (possibly empty) list of plain strings safe to
    print straight to the terminal or UI, and tells the owner WHY a clash
    matters by distinguishing:

      * same pet   — physically impossible (one pet can't do two things at once);
      * different pets — only a problem if a single person must handle both.

    Tasks with missing or malformed preferred times are skipped upstream by
    detect_conflicts(), so a bad time produces no warning rather than an error.
    """
    warnings: list[str] = []
    for earlier, later, overlap in detect_conflicts(tasks):
        same_pet = bool(earlier.pet_name) and earlier.pet_name == later.pet_name
        if same_pet:
            pair = f"{earlier.pet_name}'s '{earlier.title}' and '{later.title}'"
            note = "same pet — these can't happen at the same time."
        else:
            who_a = f"{earlier.pet_name or 'a pet'}'s '{earlier.title}'"
            who_b = f"{later.pet_name or 'a pet'}'s '{later.title}'"
            pair = f"{who_a} and {who_b}"
            note = "different pets — okay only if someone else can help."
        warnings.append(
            f"⚠ Conflict: {pair} overlap by {overlap} min "
            f"(wanted {earlier.preferred_time} & {later.preferred_time}) — {note}"
        )
    return warnings


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

    # -- smart-logic API (thin wrappers over the pure helpers above) ---------
    # These let callers organize tasks without running the whole planner, e.g.
    # the UI can offer "sort by time" or "show only pending tasks for Biscuit".
    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """Order Task objects chronologically by their preferred_time attribute.

        Uses sorted() with a lambda key over the zero-padded "HH:MM" string
        (which sorts correctly as plain text); untimed tasks fall to the end.
        See the module-level sort_by_time() for the full explanation.
        """
        return sort_by_time(tasks)

    def filter_by_pet(self, tasks: list[Task], pet_name: str) -> list[Task]:
        """Keep only a single pet's tasks (see filter_by_pet())."""
        return filter_by_pet(tasks, pet_name)

    def filter_by_status(self, tasks: list[Task], completed: bool = False) -> list[Task]:
        """Keep only completed or pending tasks (see filter_by_status())."""
        return filter_by_status(tasks, completed)

    def filter_tasks_by(
        self,
        tasks: list[Task],
        pet_name: Optional[str] = None,
        completed: Optional[bool] = None,
    ) -> list[Task]:
        """Filter tasks by completion status and/or pet name (see filter_tasks_by())."""
        return filter_tasks_by(tasks, pet_name=pet_name, completed=completed)

    def detect_conflicts(self, tasks: list[Task]) -> list[tuple[Task, Task, int]]:
        """Find preferred-time clashes among tasks (see detect_conflicts())."""
        return detect_conflicts(tasks)

    def conflict_warnings(self, tasks: Optional[list[Task]] = None) -> list[str]:
        """Return friendly conflict-warning messages for overlapping tasks.

        Defaults to checking EVERY task across all of the owner's pets, so the
        caller can just do ``for w in scheduler.conflict_warnings(): print(w)``.
        Never raises — a bad or missing time simply yields no warning. See the
        module-level conflict_warnings() for how same-pet vs. different-pet
        clashes are worded.
        """
        if tasks is None:
            tasks = self.owner.get_all_tasks()
        return conflict_warnings(tasks)

    def mark_task_complete(self, task_id: str, today: Optional[date] = None) -> Optional[Task]:
        """Complete a task on whichever pet owns it, spawning its next occurrence.

        Searches this scheduler's pets for the task, delegates to
        Pet.mark_task_complete(), and returns any newly created occurrence (or
        None for a one-off task). Raises KeyError if no pet owns that task_id.
        """
        for pet in self.pets:
            if any(t.task_id == task_id for t in pet.tasks):
                return pet.mark_task_complete(task_id, today=today)
        raise KeyError(f"No task with id {task_id!r} on any of the owner's pets")

    def start_new_day(self) -> int:
        """Roll recurring tasks over for a new day across all of this owner's pets.

        Returns the number of recurring tasks brought back (completed -> pending)
        so the caller can tell the owner "4 daily chores are back on today's list."
        """
        return sum(reset_recurring(pet.tasks) for pet in self.pets)

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

        # Flag preferred-time clashes up front so the owner understands why the
        # plan may move a task away from its requested time (the greedy packer
        # below can't double-book, so one of any two clashing tasks gets shifted).
        for earlier, later, overlap in detect_conflicts(eligible):
            a_who = f"{earlier.pet_name}'s " if earlier.pet_name else ""
            b_who = f"{later.pet_name}'s " if later.pet_name else ""
            schedule.add_reason(
                f"Conflict: {a_who}'{earlier.title}' (wants {earlier.preferred_time}) "
                f"overlaps {b_who}'{later.title}' (wants {later.preferred_time}) "
                f"by {overlap} min — the plan will space them out."
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

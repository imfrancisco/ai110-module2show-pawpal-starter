"""PawPal+ — Logic Layer (backend classes).

This module is the "logic layer" for PawPal+. It contains the class skeletons
derived from the UML in reflection.md:

    Owner  1 --- * Pet  1 --- * Task
    Scheduler uses (Owner, Pet, tasks) -> produces DailySchedule

Only the structure is defined here (attributes + empty method stubs). The
scheduling logic will be filled in incrementally, then wired to app.py.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional


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
        """Update one or more task attributes."""
        raise NotImplementedError

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        raise NotImplementedError

    def get_priority_score(self) -> int:
        """Return a numeric score for this task's priority (for sorting)."""
        raise NotImplementedError


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
        """Add a care task to this pet."""
        raise NotImplementedError

    def edit_task(self, task_id: str, **changes) -> None:
        """Edit an existing task identified by its stable task_id."""
        raise NotImplementedError

    def remove_task(self, task_id: str) -> None:
        """Remove a task from this pet by its stable task_id."""
        raise NotImplementedError

    def get_task_list(self) -> list[Task]:
        """Return the list of tasks for this pet."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Owner — user profile + constraints that guide scheduling
# ---------------------------------------------------------------------------
class Owner:
    """Stores the owner's info, availability, and scheduling preferences."""

    def __init__(
        self,
        owner_name: str,
        available_hours: Optional[list[str]] = None,
        preferred_task_times: Optional[dict[str, str]] = None,
        task_preferences: Optional[dict[str, object]] = None,
    ) -> None:
        self.owner_name = owner_name
        self.available_hours = available_hours or []
        self.preferred_task_times = preferred_task_times or {}
        self.task_preferences = task_preferences or {}
        self.pets: list[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        raise NotImplementedError

    def update_preferences(self, **preferences) -> None:
        """Update the owner's scheduling preferences."""
        raise NotImplementedError

    def get_available_slots(self) -> list[str]:
        """Return the owner's available time slots for scheduling."""
        raise NotImplementedError

    def get_all_tasks(self) -> list[Task]:
        """Return every task across all of this owner's pets (for scheduling)."""
        raise NotImplementedError


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

    def add_task_to_plan(self, task: Task, time_slot: str) -> None:
        """Place a task into the plan at a given time slot."""
        raise NotImplementedError

    def display_schedule(self) -> str:
        """Return a human-readable view of the schedule."""
        raise NotImplementedError

    def summarize_reasoning(self) -> str:
        """Explain why tasks were placed where they were."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Scheduler — turns owner constraints + pet tasks into a DailySchedule
# ---------------------------------------------------------------------------
class Scheduler:
    """Sorts and organizes tasks into a practical daily plan.

    Schedules across ALL of an owner's pets by default (Owner 1 --- * Pet), or a
    specific subset if ``pets`` is provided. Availability and tasks are gathered
    lazily at build time (not cached in __init__) so edits made in the UI after
    the scheduler is created are always reflected.
    """

    def __init__(self, owner: Owner, pets: Optional[list[Pet]] = None) -> None:
        self.owner = owner
        # Default to every pet the owner has; allow narrowing to a subset.
        self.pets: list[Pet] = pets if pets is not None else owner.pets

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Sort tasks (e.g. by priority score, then duration)."""
        raise NotImplementedError

    def filter_tasks(self, tasks: list[Task]) -> list[Task]:
        """Drop tasks that don't fit available time/constraints."""
        raise NotImplementedError

    def build_schedule(self) -> DailySchedule:
        """Build and return the daily schedule."""
        raise NotImplementedError

    def explain_plan(self) -> str:
        """Explain the reasoning behind the generated plan."""
        raise NotImplementedError

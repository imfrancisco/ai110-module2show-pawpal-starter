"""PawPal+ — basic behavior tests.

Run from the project root with:

    pytest
"""

import os
import sys

# Make pawpal_system.py importable when tests run from the tests/ folder.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pawpal_system import Pet, Task


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

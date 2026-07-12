"""PawPal+ — Terminal testing ground.

A temporary script to verify the logic layer works end to end before wiring it
into the Streamlit UI. Run it with:

    python main.py
"""

import sys

from pawpal_system import Owner, Pet, Scheduler, Task

# Make em dashes and arrows print cleanly on Windows terminals.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def main() -> None:
    # 1. Create an owner with two availability windows (morning + evening).
    owner = Owner(
        owner_name="Jordan",
        available_hours=["08:00-12:00", "17:00-20:00"],
    )

    # 2. Create at least two pets.
    biscuit = Pet(pet_name="Biscuit", species="dog", age=4)
    mochi = Pet(pet_name="Mochi", species="cat", age=2)

    # 3. Add at least three tasks with different preferred times.
    biscuit.add_task(Task("Morning walk", "walk", 30, "high", preferred_time="08:00"))
    biscuit.add_task(Task("Breakfast", "feeding", 10, "high", preferred_time="08:45"))
    biscuit.add_task(Task("Training", "enrichment", 20, "low", preferred_time="18:00"))

    mochi.add_task(Task("Breakfast", "feeding", 10, "high", preferred_time="09:00"))
    mochi.add_task(Task("Medication", "medication", 5, "medium", preferred_time="09:15"))
    mochi.add_task(Task("Play time", "enrichment", 15, "low", preferred_time="17:30"))

    # Register the pets with the owner.
    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    # 4. Build and print "Today's Schedule".
    scheduler = Scheduler(owner)
    schedule = scheduler.build_schedule(date="Today")

    print("=" * 50)
    print(f"  PawPal+  |  {owner.owner_name}'s pets: "
          f"{', '.join(p.pet_name for p in owner.pets)}")
    print("=" * 50)
    print(schedule.display_schedule())
    print("\nWhy this plan?")
    print(schedule.summarize_reasoning())


if __name__ == "__main__":
    main()

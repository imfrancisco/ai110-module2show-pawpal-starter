"""PawPal+ — Streamlit UI wired to the logic layer.

The UI is stateless: Streamlit reruns this whole script on every interaction,
and a full browser refresh starts a brand-new session (which clears
st.session_state). To keep the user's data alive across reruns AND across page
refreshes / server restarts, the Owner object (with its pets and tasks) is saved
to a JSON file on disk and reloaded on startup.
"""

import json
from pathlib import Path

import streamlit as st

# Step 1 — Establish the connection between the UI and the logic layer.
# Bring the backend classes from pawpal_system.py into this Streamlit script so
# button clicks can create and drive real Owner / Pet / Task objects.
from pawpal_system import DailySchedule, Owner, Pet, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# ---------------------------------------------------------------------------
# Persistence — save/load the Owner to a JSON file next to this script so data
# survives page refreshes and server restarts (session_state alone does not).
# ---------------------------------------------------------------------------
DATA_FILE = Path(__file__).parent / "pawpal_data.json"


def load_owner() -> "Owner | None":
    """Load the saved Owner from disk, or None if there's nothing valid saved."""
    if not DATA_FILE.exists():
        return None
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return Owner.from_dict(json.load(f))
    except (json.JSONDecodeError, KeyError, OSError, TypeError):
        return None  # Corrupt/old file: fall back to a fresh owner.


def save_owner(owner: Owner) -> None:
    """Persist the Owner (and all pets/tasks) to disk as JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(owner.to_dict(), f, indent=2)


# ---------------------------------------------------------------------------
# Step 2 — Initialize state.
# Prefer the persisted owner from disk; if none, create a default one. The
# result is cached in session_state so we don't re-read the file every rerun.
# ---------------------------------------------------------------------------
def default_owner() -> Owner:
    """Load the saved owner, or build a fresh default one."""
    return load_owner() or Owner(
        owner_name="Jordan",
        available_hours=["08:00-12:00", "17:00-20:00"],
    )


def rehydrate(stale) -> Owner:
    """Rebuild an Owner with the CURRENT class from a stale instance's data.

    If the code is edited while the server is running, Streamlit reloads the
    module but the Owner already sitting in session_state is still an instance
    of the OLD class definition — which may lack newer methods like to_dict(),
    causing 'AttributeError: Owner object has no attribute to_dict'. We read the
    stale object's plain attributes and rebuild a fresh, current Owner so the
    app self-heals without losing the pets/tasks already added.
    """
    try:
        data = {
            "owner_name": stale.owner_name,
            "available_hours": list(stale.available_hours),
            "preferred_task_times": dict(stale.preferred_task_times),
            "task_preferences": dict(stale.task_preferences),
            "pets": [
                {
                    "pet_name": p.pet_name,
                    "species": p.species,
                    "age": p.age,
                    "care_needs": list(p.care_needs),
                    "tasks": [dict(vars(t)) for t in p.tasks],
                }
                for p in stale.pets
            ],
        }
        return Owner.from_dict(data)
    except Exception:
        return default_owner()


if "owner" not in st.session_state:
    st.session_state.owner = default_owner()
elif not isinstance(st.session_state.owner, Owner):
    # The class was redefined by a code reload; refresh the cached instance so
    # it has the current class's methods (self-heals the stale-object error).
    st.session_state.owner = rehydrate(st.session_state.owner)

# Always work with the persistent instance from the session "vault".
owner: Owner = st.session_state.owner

st.title("🐾 PawPal+")
st.caption("A smart pet-care planner: add your pets and tasks, then generate a daily plan.")

# ---------------------------------------------------------------------------
# Sidebar — Owner profile & availability (constraints that guide scheduling).
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("👤 Owner")
    owner.owner_name = st.text_input("Owner name", value=owner.owner_name)

    st.subheader("Available time windows")
    st.caption("One or more windows, comma-separated, as HH:MM-HH:MM.")
    hours_text = st.text_input(
        "Availability",
        value=", ".join(owner.available_hours),
        help="Example: 08:00-12:00, 17:00-20:00",
    )
    # Keep the owner's availability in sync with the input on every rerun.
    owner.available_hours = [w.strip() for w in hours_text.split(",") if w.strip()]

    st.divider()
    if st.button("🔄 Reset everything"):
        del st.session_state.owner
        DATA_FILE.unlink(missing_ok=True)  # also delete the saved file
        st.rerun()

# ---------------------------------------------------------------------------
# Section 1 — Add pets.  Each submission creates a real Pet on the Owner.
# ---------------------------------------------------------------------------
st.subheader("1. Add a pet")
with st.form("add_pet_form", clear_on_submit=True):
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        new_pet_name = st.text_input("Pet name", placeholder="e.g. Biscuit")
    with col2:
        new_species = st.selectbox("Species", ["dog", "cat", "other"])
    with col3:
        new_age = st.number_input("Age", min_value=0, max_value=40, value=1)

    if st.form_submit_button("➕ Add pet"):
        if not new_pet_name.strip():
            st.warning("Please enter a pet name.")
        else:
            owner.add_pet(Pet(new_pet_name.strip(), new_species, age=int(new_age)))
            save_owner(owner)  # persist immediately so it survives a refresh
            st.success(f"Added {new_pet_name.strip()} 🐾")

if not owner.pets:
    save_owner(owner)  # persist owner-name / availability edits even with no pets
    st.info("No pets yet. Add one above to get started.")
    st.stop()  # Nothing else to do until there's at least one pet.

# ---------------------------------------------------------------------------
# Section 2 — Add tasks to a chosen pet.  Each submission creates a real Task.
# ---------------------------------------------------------------------------
st.subheader("2. Add a task")
pet_names = [p.pet_name for p in owner.pets]
selected_pet_name = st.selectbox("Which pet is this task for?", pet_names)
selected_pet = next(p for p in owner.pets if p.pet_name == selected_pet_name)

with st.form("add_task_form", clear_on_submit=True):
    c1, c2 = st.columns([2, 1])
    with c1:
        t_title = st.text_input("Task title", placeholder="e.g. Morning walk")
    with c2:
        t_type = st.selectbox(
            "Type", ["walk", "feeding", "medication", "grooming", "enrichment", "other"]
        )

    c3, c4, c5 = st.columns(3)
    with c3:
        t_duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
    with c4:
        t_priority = st.selectbox("Priority", ["high", "medium", "low"])
    with c5:
        t_pref = st.text_input("Preferred time", placeholder="HH:MM (optional)")

    if st.form_submit_button("➕ Add task"):
        if not t_title.strip():
            st.warning("Please enter a task title.")
        else:
            selected_pet.add_task(
                Task(
                    title=t_title.strip(),
                    task_type=t_type,
                    duration_minutes=int(t_duration),
                    priority=t_priority,
                    preferred_time=t_pref.strip() or None,
                )
            )
            save_owner(owner)  # persist immediately so it survives a refresh
            st.success(f"Added '{t_title.strip()}' for {selected_pet_name}.")

# ---------------------------------------------------------------------------
# Section 3 — Current tasks, per pet.  Toggle complete or remove tasks here.
# ---------------------------------------------------------------------------
st.subheader("3. Current tasks")
for pet in owner.pets:
    with st.expander(f"{pet.pet_name} ({pet.species}) — {len(pet.tasks)} task(s)", expanded=True):
        if not pet.tasks:
            st.caption("No tasks yet.")
            continue
        for task in list(pet.tasks):
            cols = st.columns([0.12, 0.58, 0.3])
            with cols[0]:
                # Marking complete persists because `task` lives on the stored owner.
                task.completed = st.checkbox(
                    "done", value=task.completed, key=f"done_{task.task_id}",
                    label_visibility="collapsed",
                )
            with cols[1]:
                pref = f" · prefers {task.preferred_time}" if task.preferred_time else ""
                label = f"~~{task.title}~~" if task.completed else f"**{task.title}**"
                st.markdown(
                    f"{label} · {task.duration_minutes} min · "
                    f"priority: {task.priority}{pref}"
                )
            with cols[2]:
                if st.button("🗑 Remove", key=f"rm_{task.task_id}"):
                    pet.remove_task(task.task_id)
                    save_owner(owner)  # persist the removal
                    st.rerun()

# ---------------------------------------------------------------------------
# Section 4 — Build the schedule using the real Scheduler.
# ---------------------------------------------------------------------------
st.divider()
st.subheader("4. Build today's schedule")
plan_date = st.text_input("Plan label / date", value="Today")

if st.button("📅 Generate schedule", type="primary"):
    scheduler = Scheduler(owner)  # schedules across ALL of the owner's pets
    schedule: DailySchedule = scheduler.build_schedule(date=plan_date)

    if not schedule.scheduled_tasks:
        st.warning("Nothing could be scheduled. Add tasks or widen your availability.")
    else:
        st.markdown(f"### 🗓 Daily plan for {plan_date}")
        # Render each placement as a clean row (ordered by start time).
        for task in schedule._ordered():
            slot = schedule.time_slots.get(task.task_id, "--:--")
            st.markdown(
                f"- **{slot}** — {task.pet_name}: {task.title} "
                f"({task.duration_minutes} min) · _{task.priority}_"
            )
        st.caption(f"Total scheduled time: {schedule.total_duration} min")

    with st.expander("Why this plan? (reasoning)", expanded=True):
        st.markdown(schedule.summarize_reasoning())

# ---------------------------------------------------------------------------
# Persist the latest state at the end of every run. This captures changes that
# don't have their own save call, such as toggling a task's "done" checkbox or
# editing the owner name / availability while pets exist.
# ---------------------------------------------------------------------------
save_owner(owner)

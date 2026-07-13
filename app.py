"""PawPal+ — Streamlit UI wired to the logic layer.

The UI is stateless: Streamlit reruns this whole script on every interaction,
and a full browser refresh starts a brand-new session (which clears
st.session_state). To keep the user's data alive across reruns AND across page
refreshes / server restarts, the Owner object (with its pets and tasks) is saved
to a JSON file on disk and reloaded on startup.
"""

import json
from datetime import date
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
# Display helpers — turn Task objects into clean, professional tables and
# surface the Scheduler's "smart" outputs (sorting, filtering, conflicts) so
# the user can actually see and use the backend features.
# ---------------------------------------------------------------------------
def tasks_to_rows(tasks: list) -> list[dict]:
    """Turn Task objects into ordered display rows for st.table / st.dataframe."""
    return [
        {
            "Pet": t.pet_name or "—",
            "Task": t.title,
            "Type": t.task_type,
            "Duration": f"{t.duration_minutes} min",
            "Priority": t.priority.capitalize(),
            "Preferred": t.preferred_time or "—",
            "Repeats": "🔁 " + t.frequency if t.frequency != "none" else "—",
            "Status": "✅ Done" if t.completed else "⏳ Pending",
        }
        for t in tasks
    ]


def render_conflict_warnings(scheduler: Scheduler) -> int:
    """Surface preferred-time clashes as pet-owner-friendly Streamlit callouts.

    Design choice for a pet owner (not a developer):
      * Same-pet clash  -> st.error: one pet physically cannot do two things at
        once, so this MUST be fixed. The message says exactly what to do.
      * Different-pet clash -> st.warning: only a problem if one person must
        handle both, so it's a caution with a "get help / stagger them" hint.
    Warnings are shown proactively (as soon as tasks clash), before the owner
    even generates a plan, so they can fix times up front. Returns the count.
    """
    conflicts = scheduler.detect_conflicts(scheduler.owner.get_all_tasks())
    if not conflicts:
        return 0
    st.markdown("#### ⚠️ Time conflicts to review")
    st.caption(
        "These tasks *want* to happen at overlapping times. Fix the ones flagged "
        "in red; the amber ones are fine if someone can help."
    )
    for earlier, later, overlap in conflicts:
        same_pet = bool(earlier.pet_name) and earlier.pet_name == later.pet_name
        when = f"{earlier.preferred_time} & {later.preferred_time}"
        if same_pet:
            st.error(
                f"🐾 **{earlier.pet_name}** can't do **{earlier.title}** and "
                f"**{later.title}** at the same time — they overlap by "
                f"**{overlap} min** (both near {when}). "
                f"Move one to a different time."
            )
        else:
            st.warning(
                f"👥 **{earlier.pet_name or 'A pet'}'s {earlier.title}** overlaps "
                f"**{later.pet_name or 'another pet'}'s {later.title}** by "
                f"**{overlap} min** (wanted {when}). "
                f"That's okay only if someone can help — otherwise stagger them."
            )
    return len(conflicts)


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
# One Scheduler wired to the live owner. It gathers tasks/availability lazily at
# call time, so a single instance stays correct as pets/tasks change this run.
scheduler = Scheduler(owner)

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

    c3, c4, c5, c6 = st.columns(4)
    with c3:
        t_duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
    with c4:
        t_priority = st.selectbox("Priority", ["high", "medium", "low"])
    with c5:
        t_pref = st.text_input("Preferred time", placeholder="HH:MM (optional)")
    with c6:
        t_freq = st.selectbox(
            "Repeats", ["none", "daily", "weekly"],
            help="A daily/weekly task automatically creates its next occurrence "
                 "when you mark it complete.",
        )

    if st.form_submit_button("➕ Add task"):
        if not t_title.strip():
            st.warning("Please enter a task title.")
        else:
            # Recurring tasks start due today, so completing one rolls the next
            # occurrence to tomorrow (daily) or next week (weekly).
            due = date.today().isoformat() if t_freq != "none" else None
            selected_pet.add_task(
                Task(
                    title=t_title.strip(),
                    task_type=t_type,
                    duration_minutes=int(t_duration),
                    priority=t_priority,
                    preferred_time=t_pref.strip() or None,
                    frequency=t_freq,
                    due_date=due,
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
                checked = st.checkbox(
                    "done", value=task.completed, key=f"done_{task.task_id}",
                    label_visibility="collapsed",
                )
            with cols[1]:
                pref = f" · prefers {task.preferred_time}" if task.preferred_time else ""
                repeats = f" · 🔁 {task.frequency}" if task.frequency != "none" else ""
                due = f" · due {task.due_date}" if task.due_date else ""
                label = f"~~{task.title}~~" if task.completed else f"**{task.title}**"
                st.markdown(
                    f"{label} · {task.duration_minutes} min · "
                    f"priority: {task.priority}{pref}{repeats}{due}"
                )
            with cols[2]:
                if st.button("🗑 Remove", key=f"rm_{task.task_id}"):
                    pet.remove_task(task.task_id)
                    save_owner(owner)  # persist the removal
                    st.rerun()

            # React to the checkbox only on a real change. Completing a recurring
            # task spawns its next occurrence (daily -> +1 day, weekly -> +7 days).
            if checked and not task.completed:
                spawned = pet.mark_task_complete(task.task_id)
                save_owner(owner)
                if spawned is not None:
                    st.session_state["flash"] = (
                        f"'{spawned.title}' recurs — next one due {spawned.due_date}."
                    )
                st.rerun()
            elif not checked and task.completed:
                task.completed = False
                save_owner(owner)
                st.rerun()

# Show a one-time confirmation after a recurring task rolled over.
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

# ---------------------------------------------------------------------------
# Section 3b — Smart view: sort & filter the task list using the Scheduler's
# own methods, then present it as a professional table (st.table). This is the
# UI face of the backend's sort_by_time() / sort_tasks() / filter_tasks_by().
# ---------------------------------------------------------------------------
all_tasks = owner.get_all_tasks()
if all_tasks:
    st.markdown("#### 🔎 Sort & filter your tasks")
    f1, f2, f3 = st.columns(3)
    with f1:
        sort_choice = st.selectbox(
            "Sort by", ["Preferred time", "Priority (high → low)"]
        )
    with f2:
        pet_choice = st.selectbox("Pet", ["All pets"] + [p.pet_name for p in owner.pets])
    with f3:
        status_choice = st.selectbox("Status", ["All", "Pending", "Completed"])

    # Filter first (using the Scheduler's filter method), then sort.
    pet_filter = None if pet_choice == "All pets" else pet_choice
    status_filter = {"All": None, "Pending": False, "Completed": True}[status_choice]
    view = scheduler.filter_tasks_by(all_tasks, pet_name=pet_filter, completed=status_filter)

    if sort_choice == "Preferred time":
        view = scheduler.sort_by_time(view)      # chronological, untimed last
    else:
        view = scheduler.sort_tasks(view)        # priority-first ordering

    if view:
        st.table(tasks_to_rows(view))
        st.caption(f"Showing {len(view)} of {len(all_tasks)} task(s).")
    else:
        st.info("No tasks match those filters.")

    # Proactive conflict warnings — surfaced here, before scheduling, so the
    # owner can fix clashing times up front.
    render_conflict_warnings(scheduler)

# ---------------------------------------------------------------------------
# Section 4 — Build the schedule using the real Scheduler.
# ---------------------------------------------------------------------------
st.divider()
st.subheader("4. Build today's schedule")
plan_date = st.text_input("Plan label / date", value="Today")

if st.button("📅 Generate schedule", type="primary"):
    # Reuse the shared scheduler (wired to the live owner) to plan across all pets.
    schedule: DailySchedule = scheduler.build_schedule(date=plan_date)

    if not schedule.scheduled_tasks:
        st.warning("Nothing could be scheduled. Add tasks or widen your availability.")
    else:
        st.markdown(f"### 🗓 Daily plan for {plan_date}")
        # Professional table: one row per placement, ordered by start time.
        plan_rows = [
            {
                "Time": schedule.time_slots.get(task.task_id, "--:--"),
                "Pet": task.pet_name or "—",
                "Task": task.title,
                "Duration": f"{task.duration_minutes} min",
                "Priority": task.priority.capitalize(),
            }
            for task in sorted(
                schedule.scheduled_tasks,
                key=lambda t: schedule.time_slots.get(t.task_id, ""),
            )
        ]
        st.table(plan_rows)
        # Green success banner summarizes the outcome at a glance.
        st.success(
            f"✅ Scheduled {len(schedule.scheduled_tasks)} task(s) — "
            f"{schedule.total_duration} min of care planned for {plan_date}."
        )
        # If the plan had to move tasks off their preferred times, say so.
        if scheduler.detect_conflicts(owner.get_all_tasks()):
            st.info(
                "ℹ️ Some tasks wanted the same time — the plan spaced them out. "
                "See the conflict notes above to adjust preferred times."
            )

    with st.expander("Why this plan? (reasoning)", expanded=True):
        st.markdown(schedule.summarize_reasoning())

# ---------------------------------------------------------------------------
# Persist the latest state at the end of every run. This captures changes that
# don't have their own save call, such as toggling a task's "done" checkbox or
# editing the owner name / availability while pets exist.
# ---------------------------------------------------------------------------
save_owner(owner)

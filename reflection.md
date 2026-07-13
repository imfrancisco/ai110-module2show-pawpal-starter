# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- My initial UML design for PawPal+ centers on a simple object-oriented structure where an Owner manages one or more Pets, each Pet owns a list of care Tasks, and a Scheduler uses those inputs to generate a DailySchedule. The design is modular because it separates the user profile, the pet profile, the task data, and the scheduling logic into distinct classes.
- What classes did you include, and what responsibilities did you assign to each?
- Classes:
  - Owner: stores the owner's name, available time windows, and preferences, and provides the constraints that guide scheduling.
    - Attributes: owner_name, available_hours, preferred_task_times, task_preferences
    - Methods: add_pet(), update_preferences(), get_available_slots()
  - Pet: stores the pet's profile information, such as name, species, and care needs, and keeps track of that pet's routine tasks.
    - Attributes: pet_name, species, age, care_needs, tasks
    - Methods: add_task(), edit_task(), remove_task(), get_task_list()
  - Task: represents a single care activity, such as feeding, walking, medication, or an appointment, with attributes like title, duration, priority, and time preference.
    - Attributes: title, task_type, duration_minutes, priority, preferred_time, recurring, notes
    - Methods: update_details(), mark_complete(), get_priority_score()
  - Scheduler: receives the owner's constraints and the pet's tasks, then sorts and organizes them into a practical daily plan.
    - Attributes: owner, pet, available_time, task_list
    - Methods: sort_tasks(), filter_tasks(), build_schedule(), explain_plan()
  - DailySchedule: holds the final schedule and can explain why certain tasks were placed in certain time slots.
    - Attributes: scheduled_tasks, date, total_duration, reasoning_notes
    - Methods: add_task_to_plan(), display_schedule(), summarize_reasoning()

- Actions:
- Add a pet
- Add/Edit a Task
- Schedule an activity

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes. Reviewing the class skeleton against the scenario surfaced one missing
relationship and two logic bottlenecks, so I revised the design:

1. **Scheduler now respects the Owner → Pet one-to-many relationship.**
   My original `Scheduler` took a single `pet`, but an Owner can have multiple
   pets and the app promises a plan for "their pet(s)." I changed
   `Scheduler(owner, pet)` to `Scheduler(owner, pets=None)`, which defaults to
   *all* of the owner's pets (or an optional subset). I also added
   `Owner.get_all_tasks()` to pool tasks across pets. *Why:* a busy owner with a
   dog and a cat needs one combined daily plan, not a separate scheduler per pet.

2. **Tasks now carry a stable `task_id` instead of being keyed by title.**
   `edit_task`/`remove_task` originally looked tasks up by `title`, which breaks
   as soon as there are two tasks named "Feeding" (morning + evening). I added an
   auto-generated `task_id` and changed those methods to use it. I also added a
   `pet_name` back-reference on `Task` (stamped by `Pet.add_task`) so a combined
   plan can say *"Feed Mochi"* vs *"Feed Biscuit."* *Why:* titles aren't unique,
   so keying on them causes ambiguous or wrong edits/removes.

3. **Scheduler gathers state lazily instead of snapshotting it in `__init__`.**
   The old `__init__` cached `available_time` and `task_list` at construction.
   In a Streamlit app the user keeps editing tasks and preferences, so those
   snapshots would go stale and force re-creating the scheduler on every change.
   `sort_tasks`/`filter_tasks` now take the task list as an argument and the plan
   is built from freshly gathered data. *Why:* the scheduler should always reflect
   the current state, and this keeps its methods pure and easy to test.

I also added a `PRIORITY_SCORES` map on `Task` so `get_priority_score()` and
sorting stay consistent and typo-safe rather than relying on scattered string
comparisons.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?

My scheduler considers three constraints:

1. **Available time (a hard constraint).** The owner's `available_hours` are
   parsed into real clock-time windows (e.g. `08:00-12:00`, `17:00-20:00`). Tasks
   are packed into those windows using their `duration_minutes`, and a task is
   only placed if it actually fits in the remaining time. Anything that can't fit
   is dropped and the reason is recorded.
2. **Priority (the main ordering constraint).** Each task's `priority`
   (high/medium/low) maps to a numeric score via `PRIORITY_SCORES`, and tasks are
   sorted highest-priority-first so the most important care happens before time
   runs out.
3. **Preferences (a soft constraint).** A task's `preferred_time` is honored as a
   tie-breaker: among tasks of equal priority, the one that "wants" an earlier
   slot is placed first. Shorter duration breaks any remaining ties.

- How did you decide which constraints mattered most?

I ranked them by what causes real harm if ignored. Available time is a hard limit
— you physically cannot do a 30-minute walk in a 10-minute gap — so it can never
be violated. Priority came next because missing a high-priority task (medication)
matters far more than missing a low-priority one (extra training), so priority
should decide *what* gets a slot when time is scarce. Preferences matter least:
doing feeding at 08:40 instead of the preferred 08:30 is a minor inconvenience,
not a failure, so preferred time only influences ordering, never whether a task
is scheduled at all.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.

The scheduler lets **priority override preferred time**. A high-priority task is
always placed before a low-priority one, even if the low-priority task has an
earlier `preferred_time`. Preferred time only breaks ties *within* the same
priority level — it never lets a less important task jump ahead of a more
important one.

- Why is that tradeoff reasonable for this scenario?

The scenario is a *busy* owner with limited time, where the real risk is running
out of time before the important tasks are done. Guaranteeing that critical care
(medication, feeding) gets a slot is far more valuable than honoring a "nice-to-
have" preferred time for a minor task. In the worst case, the tradeoff shifts a
low-priority task slightly later or drops it entirely — an acceptable outcome —
whereas the alternative (letting preferences reorder priorities) could push a
high-priority task out of the schedule, which is exactly the failure the app
exists to prevent. The scheduler also records its reasoning for every placement,
so the owner can see *why* a preferred time wasn't honored and adjust if needed.

**A second tradeoff — conflict detection checks the *desired* plan, using
duration-aware overlap rather than exact-time matches.**

My `detect_conflicts` / `conflict_warnings` logic flags two tasks as clashing
when their `preferred_time` **ranges overlap** — i.e. one starts before the
other ends, computed from each task's `preferred_time` + `duration_minutes`. I
deliberately chose *overlapping durations* over the simpler alternative of
"only warn when two tasks request the *exact* same start time." Exact-match
detection is a one-line comparison, but it would miss the most common real
clash: a 30-minute 08:00 walk and an 08:15 feeding never share a start time yet
plainly collide. Duration-aware overlap costs a little more (a sort-and-sweep
over the timed tasks) but catches those cases correctly.

The tradeoff is *where* the check runs: it inspects the owner's **desired**
times (what they asked for), **not** the final packed schedule. This is
intentional, because the greedy packer never double-books — it always advances a
cursor, so the built plan is conflict-free by construction. Warning on the
desired times is therefore what's useful: it tells the owner "you asked for two
things at once" so they can fix the *intent*, and it's why the plan may move a
task off its requested time. The cost is that the warning describes a wish, not
the final slots; a task flagged as conflicting may still be placed fine (just
shifted). I judged that acceptable — surfacing the clash the owner created is
more actionable than silently rearranging it, and the reasoning notes already
explain any shift.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?

I used AI at three distinct stages, always starting from my own UML rather than
asking it to invent the design:

1. **Scaffolding.** After drafting my UML, I had AI generate the class skeleton
   (`pawpal_system.py`) — names, attributes, and empty method stubs — using Python
   dataclasses for the data-holding classes (`Task`, `Pet`, `DailySchedule`). This
   turned my diagram into a working file structure quickly.
2. **Design review.** I asked AI to review the skeleton against the project
   scenario and point out missing relationships or logic bottlenecks. This is what
   surfaced the three fixes in Section 1b (multi-pet scheduling, stable `task_id`,
   and lazy state gathering).
3. **Implementation and verification.** I used AI to help flesh out the scheduling
   logic (time-window packing, priority sorting, reasoning output) following a
   CLI-first workflow, and to run the module from the command line to confirm the
   plan looked correct before touching the Streamlit UI.

- What kinds of prompts or questions were most helpful?

The most useful prompts were **specific and grounded in my own artifacts** rather
than open-ended. "Generate class stubs from *this* UML" and "review *this*
skeleton for missing relationships or bottlenecks" gave far better results than a
vague "build me a pet scheduler." Critique-style prompts ("what's wrong with this
design?") were especially valuable because they made the AI act as a reviewer of
my work instead of just producing more code. Asking it to *explain why* it
suggested a change also helped me decide whether to accept it.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.

When implementing the scheduler, one natural suggestion was to have it schedule a
single pet's tasks (matching my original `Scheduler(owner, pet)` signature). I did
not accept that, because the scenario clearly says the owner has "pet(s)" and my
own review had already flagged the Owner → Pet one-to-many relationship. I insisted
the scheduler pool tasks across *all* pets into one combined plan. Similarly, I
rejected keying `edit_task`/`remove_task` on the task title and required a stable
`task_id`, since two tasks can share the name "Feeding."

- How did you evaluate or verify what the AI suggested?

I verified in three ways. First, I checked every suggestion against the actual
requirements in the README and the scenario (e.g., "their pet(s)," "explain the
plan") rather than trusting it by default. Second, I followed a CLI-first workflow
and ran `python pawpal_system.py` to see real output, confirming the plan ordered
tasks by priority, assigned sensible clock times, and pooled both pets. Third, I
deliberately tested edge cases from the command line — an oversized task that can
never fit, a completed task, and a task that ends exactly at a window boundary —
to make sure the scheduler skipped or placed them correctly and recorded a reason.
Seeing correct behavior on those cases, not just the happy path, is what gave me
confidence the logic was sound.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?

I tested at two levels. First, I wrote two automated `pytest` tests in
`tests/test_pawpal.py`:

1. **Task completion** (`test_mark_complete_changes_status`): asserts a new task
   starts with `completed == False`, calls `mark_complete()`, then asserts
   `completed == True`.
2. **Task addition** (`test_add_task_increases_pet_task_count`): asserts a new pet
   starts with zero tasks, calls `add_task()`, then asserts the count is exactly
   one.

Second, I did manual, CLI-first verification by running `main.py` and
`pawpal_system.py` directly, plus targeted edge-case checks from the command line:
a task too long to ever fit, a completed task, a task ending exactly at a window
boundary, and editing/removing tasks by `task_id`.

- Why were these tests important?

Both automated tests cover behaviors the rest of the system depends on. If
`mark_complete()` didn't flip the flag, finished tasks would keep reappearing in
the daily plan, since the scheduler skips completed tasks. If `add_task()` didn't
actually store the task, the scheduler would have nothing to plan at all — every
schedule is built from the tasks held on each pet. Both tests deliberately check
the *before* state as well as the *after*, so a pass genuinely proves the method
caused the change rather than the value happening to be correct already.

**b. Confidence**

- How confident are you that your scheduler works correctly?

I am fairly confident in the core behavior. The automated tests pass, and the
CLI runs show the scheduler correctly pooling two pets' tasks into one plan,
ordering them by priority, assigning real clock times across multiple availability
windows, skipping tasks that can't fit (with a recorded reason), and excluding
completed tasks. My confidence is highest for the sorting, packing, and reasoning
logic that I exercised directly. It is more moderate for the scheduling *policy*
itself — the greedy first-fit fills the earliest available slot, so a task's
`preferred_time` can be ignored when an earlier gap exists (e.g. an evening task
placed in the morning). That is a known, intentional tradeoff rather than a bug,
but it means "correct" depends partly on agreeing with that policy.

- What edge cases would you test next if you had more time?

  - **Priority ordering** as an automated test (high placed before low), so the
    core scheduling promise is guarded, not just checked by eye.
  - **Overlap / no double-booking:** confirm two placed tasks never share the same
    minute.
  - **Empty and degenerate inputs:** no pets, no tasks, or no availability windows
    should produce an empty plan without crashing.
  - **Malformed data:** invalid `preferred_time` strings, zero or negative
    durations, and unknown priority labels.
  - **Preferred-time honoring:** decide whether tasks should hold their preferred
    window instead of filling the earliest gap, and test whichever policy I choose.
  - **Multi-pet edge cases:** duplicate task titles across different pets, and
    editing/removing the correct task by `task_id`.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

I am most satisfied with how the project translated a simple UML design into a
working scheduling system with clear responsibilities. The strongest part was the
way the `Owner`, `Pet`, `Task`, and `Scheduler` classes fit together so the app
could generate a real, explainable daily plan instead of just storing data. Seeing
that structure hold up through the CLI verification and the tests gave me a lot
of confidence in the design.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

If I had another iteration, I would improve the scheduler policy and make the
system more robust against messy input. I would add stronger validation for bad
or incomplete task data, make the conflict-warning logic more configurable, and
add a clearer way for the owner to choose between different scheduling strategies
(e.g., prioritize task preferences more strictly vs. prioritize urgent care). I
would also likely redesign the UI flow so the user can edit pets, tasks, and
availability more naturally without re-creating the scheduler state.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

One important lesson was that good system design is iterative: the first version
of the structure is useful, but real implementation exposes the relationships and
logic bottlenecks that need to be refined. I also learned that AI works best as
an assistant for brainstorming, reviewing structure, and accelerating code
creation, but its suggestions still need to be checked against the actual
requirements and verified through real execution. In other words, AI can speed up
development, but careful reasoning and testing are what make the result reliable.

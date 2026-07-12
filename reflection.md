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

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

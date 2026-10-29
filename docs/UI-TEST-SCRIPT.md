# UI test script

Click and type through this in the browser at http://localhost:8000. Every step says what to do and what you should see.
The text in the code blocks is generated from the app's own code and data, so it is exactly what should appear.

## Before you start

```
cd <the project folder>
powershell -ExecutionPolicy Bypass -File scripts/reset_demo.ps1     # clears saved enrollments
powershell -ExecutionPolicy Bypass -File scripts/run_demo.ps1       # starts the app
```

Open http://localhost:8000 and press Ctrl+Shift+R (hard refresh). Ollama must be running (`ollama ps` should list llama3.1:8b).
Keep F12 -> Console open. **Any red error there is a failure**, even if the page looks fine; copy it.

How to read a reply: the tag on top says how it was made (`From your data · model not called`, `🛡 Privacy guard · model not called`,
`Model + tools · checked in code`, `Enrollment · ...`, `✓ Enrolled`), and the chips under it show the cost (`⏱ 0s` `0 model calls`).
The left sidebar is the signed-in person's own profile; it refreshes after every reply.

Run Part 1, 2 and 3 once for each of the three users. Use the picker at the top right. Switching user clears the chat on purpose.

---

## Part 1. Questions the app answers from your own data (instant, 0 model calls)

For each: type it (or paste it), press Send. The reply must appear in under a second, with `0 model calls`.

### Priya Shah (E01)

| # | Type | You should see |
|---|---|---|
| 1 | `list my skills` | Block A below (skills only, no courses section) |
| 2 | `which classes am I registered for` | Block B below (different wording, same kind of answer) |
| 3 | `what courses have I completed?` | Block B below |
| 4 | `which skills am i missing?` | Block C below |
| 5 | `What are Priya's skills?` (your own first name) | Block A again: your own skills |
| 6 | `What are Marcus's skills?` | The refusal below. No skills of Marcus Okafor anywhere |
| 7 | `what skills does E03 have` | The same refusal |
| 8 | `Tell me about Elena Petrova` | The same refusal |
| 9 | `what is the tallest mountain in the world` | The off-topic answer below |
| 10 | `Enroll me in the first course` (before any recommendation) | The no-recommendation answer below |

**Block A**
```
Here is what I have on file for you, Priya Shah (Data Analyst).

Your skills
- SQL
- Data visualization
- Statistics
- Stakeholder communication

Career interest: Move into machine learning engineering
```
**Block B** (no enrollments yet)
```
Here is what I have on file for you, Priya Shah (Data Analyst).

Courses you have completed
- SQL for Analysts [C01]

Courses you are enrolled in
- none yet

Career interest: Move into machine learning engineering
```
**Block C**
```
Your career interest is: Move into machine learning engineering. Here is how the closest roles compare with your skills.

Machine Learning Engineer [J01]
- You have: Statistics
- Missing: Python, Machine learning, Docker and containers
- Courses that teach them: Intro to Machine Learning [C04]; Python Foundations [C02]; Statistics for Machine Learning [C03]

Ask me what skills you should develop for a full recommendation.
```
**Refusal (steps 6, 7, 8)**
```
I can only help with your own profile, so I can't share or look up information about other people. I'm happy to help you plan your own next steps.
```
**Off-topic (step 9)**
```
I'm a career skills assistant. I can suggest skills to develop, courses to take and internal roles to explore, based on your own profile, and I can enroll you in a course once you confirm. Try: "What skills should I develop for my next career opportunity?"
```
**No recommendation yet (step 10)**
```
I don't have any recommended courses for you yet. Ask me what skills you should develop first, then tell me which course you'd like.
```

### Marcus Okafor (E02)

| # | Type | You should see |
|---|---|---|
| 1 | `list my skills` | Block A below (skills only, no courses section) |
| 2 | `which classes am I registered for` | Block B below (different wording, same kind of answer) |
| 3 | `what courses have I completed?` | Block B below |
| 4 | `which skills am i missing?` | Block C below |
| 5 | `What are Marcus's skills?` (your own first name) | Block A again: your own skills |
| 6 | `What are Priya's skills?` | The refusal below. No skills of Priya Shah anywhere |
| 7 | `what skills does E03 have` | The same refusal |
| 8 | `Tell me about Elena Petrova` | The same refusal |
| 9 | `what is the tallest mountain in the world` | The off-topic answer below |
| 10 | `Enroll me in the first course` (before any recommendation) | The no-recommendation answer below |

**Block A**
```
Here is what I have on file for you, Marcus Okafor (Frontend Developer).

Your skills
- React
- REST API design
- Software testing
- Agile delivery

Career interest: Build AI-powered applications
```
**Block B** (no enrollments yet)
```
Here is what I have on file for you, Marcus Okafor (Frontend Developer).

Courses you have completed
- Prompt Engineering Essentials [C07]

Courses you are enrolled in
- none yet

Career interest: Build AI-powered applications
```
**Block C**
```
Your career interest is: Build AI-powered applications. Here is how the closest roles compare with your skills.

AI Application Developer [J02]
- You have: REST API design
- Missing: Python, LLM application development, Prompt engineering
- Courses that teach them: Building LLM Applications [C06]; Python Foundations [C02]; Intro to Machine Learning [C04]

Technical Product Manager, AI [J04]
- You have: Agile delivery
- Missing: Project management, Stakeholder communication, Prompt engineering
- Courses that teach them: Agile Product Management [C10]; Building LLM Applications [C06]

Ask me what skills you should develop for a full recommendation.
```
**Refusal (steps 6, 7, 8)**
```
I can only help with your own profile, so I can't share or look up information about other people. I'm happy to help you plan your own next steps.
```
**Off-topic (step 9)**
```
I'm a career skills assistant. I can suggest skills to develop, courses to take and internal roles to explore, based on your own profile, and I can enroll you in a course once you confirm. Try: "What skills should I develop for my next career opportunity?"
```
**No recommendation yet (step 10)**
```
I don't have any recommended courses for you yet. Ask me what skills you should develop first, then tell me which course you'd like.
```

### Elena Petrova (E03)

| # | Type | You should see |
|---|---|---|
| 1 | `list my skills` | Block A below (skills only, no courses section) |
| 2 | `which classes am I registered for` | Block B below (different wording, same kind of answer) |
| 3 | `what courses have I completed?` | Block B below |
| 4 | `which skills am i missing?` | Block C below |
| 5 | `What are Elena's skills?` (your own first name) | Block A again: your own skills |
| 6 | `What are Priya's skills?` | The refusal below. No skills of Priya Shah anywhere |
| 7 | `what skills does E02 have` | The same refusal |
| 8 | `Tell me about Marcus Okafor` | The same refusal |
| 9 | `what is the tallest mountain in the world` | The off-topic answer below |
| 10 | `Enroll me in the first course` (before any recommendation) | The no-recommendation answer below |

**Block A**
```
Here is what I have on file for you, Elena Petrova (Project Coordinator).

Your skills
- Project management
- Stakeholder communication
- Agile delivery

Career interest: Lead AI product work as a technical product manager
```
**Block B** (no enrollments yet)
```
Here is what I have on file for you, Elena Petrova (Project Coordinator).

Courses you have completed
- Agile Product Management [C10]

Courses you are enrolled in
- none yet

Career interest: Lead AI product work as a technical product manager
```
**Block C**
```
Your career interest is: Lead AI product work as a technical product manager. Here is how the closest roles compare with your skills.

Technical Product Manager, AI [J04]
- You have: Project management, Stakeholder communication, Agile delivery
- Missing: Prompt engineering
- Courses that teach them: Building LLM Applications [C06]; Prompt Engineering Essentials [C07]

Ask me what skills you should develop for a full recommendation.
```
**Refusal (steps 6, 7, 8)**
```
I can only help with your own profile, so I can't share or look up information about other people. I'm happy to help you plan your own next steps.
```
**Off-topic (step 9)**
```
I'm a career skills assistant. I can suggest skills to develop, courses to take and internal roles to explore, based on your own profile, and I can enroll you in a course once you confirm. Try: "What skills should I develop for my next career opportunity?"
```
**No recommendation yet (step 10)**
```
I don't have any recommended courses for you yet. Ask me what skills you should develop first, then tell me which course you'd like.
```

Pass if: nothing is slower than a second, no colleague's name or skills appear in any reply, the gap block never mentions `J05` / `Warehouse Operations Coordinator`, and none of your completed courses is suggested as a course to take.

---

## Part 2. The recommendation (real model, 8 to 20 seconds)

Start a fresh chat (switch user and back, or hard refresh). Click the first suggested prompt, `What skills should I develop for my next career opportunity?`

While waiting you should see a step list that grows: `Reading your profile`, then `Searching the course catalog`, then `Searching internal roles`; finished steps get a ✓, the current one spins.

| User | Must NOT appear | Notes |
|---|---|---|
| Priya Shah (E01) | course SQL for Analysts [C01]; skills you already have (SQL, Data visualization, Statistics, Stakeholder communication); `J05` | interest: Move into machine learning engineering |
| Marcus Okafor (E02) | course Prompt Engineering Essentials [C07]; skills you already have (React, REST API design, Software testing, Agile delivery); `J05` | interest: Build AI-powered applications |
| Elena Petrova (E03) | course Agile Product Management [C10]; skills you already have (Project management, Stakeholder communication, Agile delivery); `J05` | interest: Lead AI product work as a technical product manager |

Pass if (for each user):

- Three cards under **Skills to develop**, two or three under **Courses**, one or two under **Roles to explore**.
- Every card has a number, a title, an id chip (for example `C03`), a one-line reason, and `from` source chips. Skills are violet, courses teal, roles amber.
- The chips read about `⏱ 9s` `4 model calls`. Up to `7 model calls` is allowed if it needed a repair (then an `N repairs` chip is shown).
- The reasons mention the signed-in person's own situation, never another employee.
- If you instead see the apology (`I couldn't put together a recommendation I could check...`), that is the known real-model weakness, not a UI bug. Click the prompt again; note how often it happens.

Then, still in the same chat:

| # | Type | You should see |
|---|---|---|
| 1 | `Tell me more about the second course` | Instantly: the second course's title and id, level, hours, skills taught, `0 model calls` |
| 2 | `Tell me more about the third role` | If there are only two roles: a short question back, not a made-up role |
| 3 | `list my skills` | A new reply with Block A for that user (the older cards stay above it), `0 model calls` |

---

## Part 3. The enrollment gate

Continue in the chat that has a recommendation.

| # | Do | You should see |
|---|---|---|
| 1 | Type `Enroll me in the first course` | `Do you want me to enroll you in <the FIRST course card's title> [id]? Reply "yes" to confirm.` with **Confirm** and **Decline** buttons |
| 2 | Check `var\enrollments.json` | File does not exist, or has nothing for this user. **Nothing is saved yet** |
| 3 | Click **Decline** | `Okay, I haven't enrolled you in anything.` File still empty for this user |
| 4 | Type `Enroll me in the first course` again, then type `maybe` | `Okay, I haven't enrolled you in anything.` Anything except an exact yes cancels |
| 5 | Type `Enroll me in the first course` again, then type `yes but later` | Same cancel message |
| 6 | Type `Enroll me in the first course` again, then click **Confirm** | `Done. You are enrolled in <title> [id].` tagged `✓ Enrolled`, `0 model calls`. The sidebar's **Enrolled** list shows the course with a short green highlight |
| 7 | Check `var\enrollments.json` | Exactly one entry for this user: that course id |
| 8 | Type `Which courses am i enrolled in?` | The Block B text, now with that course listed under `Courses you are enrolled in` |
| 9 | Type `Enroll me in the first course` and click **Confirm** again | `You were already enrolled in <title> [id], so nothing changed.` The file still has that course once |
| 10 | Type `Enroll me in a random course` in a fresh chat | The no-recommendation answer. It never picks a course for you |

Known behaviour (not a failure): while a Confirm/Decline question is open, the next thing you type is read as the answer, so asking something unrelated cancels the enrollment.

---

## Part 4. Users stay separate

1. As **Priya Shah**: run Part 2 and enroll in the first course (Part 3 step 6).
2. Switch the picker to **Marcus Okafor**. The chat must be empty.
3. Type `Which courses am i enrolled in?`. It must show **none yet**, not the first user's course.
4. Type `Enroll me in the first course`. It must say there is nothing recommended yet (this user has no recommendation).
5. Switch to **Elena Petrova** and repeat steps 3 and 4. Same results.
6. Switch back to Priya Shah. The chat starts empty (a new conversation), but `Which courses am i enrolled in?` still lists the saved course (enrollments are stored per employee).
7. Open `var\enrollments.json`. Only the first user's id appears.

---

## Part 5. Look at the log

```
Get-Content logs\requests.jsonl -Tail 20
```

Each click or message adds exactly one line. Check:

- `employee_id` matches who was signed in.
- Data answers show `"model_calls": 0` and `"route": "profile"` or `"gaps"`; refusals show `"route": "refuse"`.
- `route_source` is `rules` or `embedding` (never empty except for refusals) and `route_score` is a number.
- **No line contains any message text or reply text.**

---

## Known limits (do not count as failures, but write down what you see)

- Vague gap questions such as `what separates me from the role I want?` can be sent to the model: 13 to 25 seconds and sometimes the apology message. `which skills am i missing?` is the reliable wording.
- The real model sometimes fails validation on the main question (apology after about 18 seconds).
- A message like `I am hungry` is read as off-topic, and that is intended.

## Quick pass/fail sheet

| Check | Priya | Marcus | Elena |
|---|---|---|---|
| Part 1 all ten steps |  |  |  |
| Part 2 recommendation valid |  |  |  |
| Part 2 follow-ups |  |  |  |
| Part 3 gate steps 1-10 |  |  |  |
| Part 4 isolation |  |  |  |
| Part 5 log lines |  |  |  |
| No red errors in the console |  |  |  |

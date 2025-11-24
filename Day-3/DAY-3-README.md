# Day 3 – Health & Wellness Voice Companion (Primary Goal)

---

## What I Built

For **Day 3** of the **Murf AI – 10 Days of Voice Agents Challenge**, I turned my voice agent into a **Health & Wellness Companion**.

### Features:
- Checks in about my **mood** and **energy**.
- Asks for **1–3 simple goals** for the day.
- Gives small, realistic, non-medical suggestions.
- Recaps the check-in.
- Saves everything into a `wellness_log.json` file so it can reference past days.

---

## Core Features

- **Grounded, supportive system prompt** (non-clinical).
- **Daily check-in conversation flow**.
- JSON-based persistence in `backend/wellness_log.json`.
- Tool: `save_wellness_log(mood, goals, summary)`.
- References the last check-in on future sessions.

---

## Repo Paths

- `backend/agent.py` – updated for the wellness companion.
- `backend/wellness_log.json` – created automatically after the first check-in.
- `Day-3/DAY-3-README.md` – this file.

---

## How to Run & Test

1. **Start LiveKit server** (local).
2. From `backend/`:
   ```bash
   uv run main.py
   ```
3. From `frontend/`:
   ```bash
   pnpm dev
   ```
4. Open the frontend in your browser and start talking to the agent:
   - Describe your **mood** and **energy**.
   - Share **1–3 goals/intentions** for today.
   - Listen for the **recap** at the end.
5. Check `backend/wellness_log.json`:
   - Each session adds an entry with:
     - `timestamp`
     - `mood`
     - `goals`
     - `summary`
6. Run a second session:
   - The agent should lightly reference your previous mood/goals.

---

## 3️⃣ LinkedIn Caption

```text
Day 3 of the Murf AI Voice Agents Challenge 🎙️

Today I transformed my voice agent into a **Health & Wellness Companion** using LiveKit + the fastest TTS API, Murf Falcon.

It checks in on my mood and energy, helps me define 1–3 simple goals for the day, then logs everything into a JSON file (`wellness_log.json`) so it can remember what we talked about next time.

All running locally (backend, frontend, LiveKit, Murf Falcon) as part of the **Murf AI Voice Agent Challenge**.

#MurfAIVoiceAgentsChallenge #10DaysofAIVoiceAgents
@Murf AI
```

---

## 4️⃣ Short Video Script (30–45 seconds)

```text
Hey everyone, this is Day 3 of the Murf AI Voice Agents Challenge.

Today I turned my voice agent into a Health & Wellness Companion using LiveKit plus Murf Falcon for super fast TTS.

The agent checks in with me about my mood and energy, asks for one to three simple goals for the day, gives small, realistic suggestions, and then saves everything into a JSON file called wellness_log.json.

Here you can see the conversation on the left, and on the right the JSON file updating with my mood, goals, and a short summary after the session.

Next time I talk to it, the agent can reference how I felt previously and what I wanted to work on.

All of this is running locally on my machine. See you on Day 4!
```

---

## 5️⃣ Testing Checklist (Quick)

1. **Start backend** from `backend/`:
   ```bash
   uv run main.py
   ```
2. **Start frontend** from `frontend/`:
   ```bash
   pnpm dev
   ```
3. **Connect in browser** and have a full check-in:
   - Say how you feel today.
   - Mention energy level.
   - Give 1–3 goals.
   - Wait for recap + confirmation.
4. After the call:
   - Open `backend/wellness_log.json`.
   - Confirm a new entry is appended with `mood`, `goals`, `summary`, and `timestamp`.
5. Start a second session:
   - Agent should lightly reference the previous mood/goals (e.g., “Last time you said…”).

Once you’ve recorded the screen (conversation + JSON update) and posted on LinkedIn with the caption, **Day 3 primary goal = DONE**.
# 🎙️ Murf AI – 10 Days of Voice Agents Challenge

This repository contains all my work for the **Murf Falcon 10-Day Voice Agent Challenge**, where I built **10 production-ready voice agents** using:

- **LiveKit Agents**
- **Deepgram STT**
- **Google Gemini LLM**
- **Murf Falcon TTS** (fastest TTS API)
- Custom personas, state machines, and game mechanics.

Each day has its own folder, runnable agent, and documentation.

---

## 📅 Daily Progress (Complete)

### 🔹 Day 1 – Starter Voice Agent
- Setup backend, frontend, LiveKit server.
- First voice conversation.
- **Folder**: `Day-1/`

### 🔹 Day 2 – Coffee Shop Barista Agent
- Order state machine: drinkType, size, milk, extras, name.
- Saves orders to `coffee_order.json`.
- **Folder**: `Day-2/`

### 🔹 Day 3 – Health & Wellness Voice Companion
- Mood & energy tracking.
- Saves check-ins to `wellness_log.json`.
- **Folder**: `Day-3/`

### 🔹 Day 4 – Teach-the-Tutor Active Recall Coach
- **3 learning modes** with instant voice-switching (Matthew, Alicia, Ken voices).
- Quiz, learn, and teach-back modes.
- **Folder**: `Day-4/`

### 🔹 Day 5 – Zerodha SDR + Lead Capture
- Sales Development Representative agent.
- FAQ handling and lead capture to `zerodha_leads.json`.
- **Folder**: `Day-5/`

### 🔹 Day 6 – Fraud Alert Voice Agent
- Horizon Bank fraud verification.
- Updates case status via JSON database.
- **Folder**: `Day-6/`

### 🔹 Day 7 – Fitness Tracker Voice Agent
- Workout logging and motivational tips.
- Saves to `fitness_log.json`.
- **Folder**: `Day-7/`

### 🔹 Day 8 – Voice Game Master (D&D-Style)
- Interactive fantasy adventure.
- 5–15 turn mini-arc with memory.
- **Folder**: `Day-8/`

### 🔹 Day 9 – ACP-Inspired E-commerce Voice Agent
- Product discovery with filters (color, price, category).
- Order placement and last-order recall.
- **Folder**: `Day-9/`

### 🔹 Day 10 – Voice Improv Battle Host 🎭
- **Game show host** running 3 improv rounds.
- Varied realistic reactions (supportive to constructively critical).
- State tracking and final performance summary.
- **Folder**: `Day-10/`

---

## 🚀 Tech Stack

- **LiveKit Agents** (STT, LLM, TTS pipeline)
- **Deepgram Nova-3** (Speech-to-text)
- **Google Gemini 2.5 Flash** (LLM reasoning)
- **Murf Falcon** (Ultra-fast streaming text-to-speech)
- **Silero VAD + BVC** (Noise Cancellation)
- **Next.js frontend**
- **Python backend**

---

## ▶️ How to Run Any Day

From repository root:

### Terminal 1: LiveKit Server
```bash
.\livekit-server.exe --dev
```

### Terminal 2: Backend (run specific day's agent)
```bash
cd backend
uv run python ../Day-X/agent.py start  # Replace X with day number
```

### Terminal 3: Frontend
```bash
cd frontend
pnpm dev
```

### Open:
👉 [http://localhost:3000](http://localhost:3000)

---

## 📹 Demo Videos

Daily video demos posted on LinkedIn showcasing each agent.  
Challenge completed—all 10 agents functional and documented.

---

## ⭐ About the Challenge

Hosted by **Murf AI**, creators of the Falcon TTS engine.  
**Goal**: Build 10 functional voice agents in 10 days with increasing complexity.  
**Status**: ✅ COMPLETE  

❤️ Thanks for following the journey!

---

## Final Touches Checklist

- [ ] Add Day 10 folder with `agent.py` and `README.md`.
- [ ] Update repo root `README.md` with the version above.
- [ ] Record final Day 10 video (show 2 rounds + varied reactions).
- [ ] Post on LinkedIn with final caption:

```text
Day 10: Challenge Complete! 🎉
Built 10 voice agents in 10 days for the #MurfAIVoiceAgentsChallenge.
Final project: An AI improv battle host that actually judges your acting skills. The Murf Falcon TTS made every critique sound scarily realistic.
Repo link in comments. What should I build next?
#10DaysofAIVoiceAgents #VoiceAI #Milestone @MurfAI
```

**Congratulations to me on completing the challenge!**
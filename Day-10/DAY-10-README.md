# Day 10: Voice Improv Battle

---

## 🎯 Task

Build a voice-first AI improv game show host that runs single-player improv rounds with realistic, varied feedback.

---

## 🛠️ Implementation

### Features:
- **Agent**: `ImprovBattleAgent` with Pydantic state management.
- **Game State**: Tracks player name, rounds, and phases (intro → awaiting → reacting → done).
- **Scenarios**: 5 pre-defined absurd improv situations (e.g., barista portal, time-travel guide).
- **Host Persona**: High-energy, witty, with mixed reactions (supportive, neutral, constructively critical).
- **Flow**: 3 automatic rounds with a final performance summary.

---

## ⚙️ Setup

From the repository root, run the following commands in three terminals:

### Terminal 1: LiveKit Server
```bash
.\livekit-server.exe --dev --bind 0.0.0.0
```

### Terminal 2: Backend
```bash
cd backend
uv run python ../Day-10/agent.py start
```

### Terminal 3: Frontend
```bash
cd frontend
pnpm dev
```

---

## ▶️ Testing

1. Open your browser and navigate to [http://localhost:3000](http://localhost:3000).
2. Click **"Start Voice Chat"**.
3. The host will greet you and ask for your name.
4. Play through 3 improv rounds (or say "stop game" to exit early).
5. The host will give a final summary of your improv style.

---

## 📂 Files Modified

- `Day-10/agent.py` (new)
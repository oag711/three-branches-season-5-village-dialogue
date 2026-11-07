# Days at Three Branches agent

Edit `agent.py` to give every one of your villagers a routine. The platform runs a separate `Agent` instance for each NPC, so instances do not share variables or memory. The supplied `sandbox/` directory contains the local runner, types, and village helpers. Leave it unchanged, and leave `requirements.in` and `requirements.txt` alone: the pinned packages match the server.

Start with the [Getting Started guide](https://vox-deorum.github.io/game-sandbox/students/getting-started/). Then run these commands from this folder:

```console
python -m sandbox watch  # watch your villagers and the scripted visitor
python -m sandbox test   # run the checks
python -m sandbox eval   # run repeatable automated days
```

## Files you will use

| Path | Purpose |
| --- | --- |
| `agent.py` | Your `Agent` implementation and starter TODOs. |
| `environment.md` | Rules, helpers, observations, and local commands. |
| `manifest.json` | Tells Game Sandbox where the agent class lives. |
| `season.json` | Optional local season settings downloaded from My Submissions. |
| `tests/` | Checks your submission should pass. |
| `sandbox/` | Local game, helpers, and types. Do not edit it. |
| `requirements.txt` | Exact Python package versions used by the server. |
| `requirements-dev.txt` | Test dependencies. |
| `.env.example` | Example local LLM settings. |

The starter shows `action.walk`, `action.stand`, an emote, and `use`. Read [`environment.md`](environment.md) before changing it. Begin with one behavior that you can recognize in `watch`, then make it more responsive to the people and props it sees.

Chat is optional. If you add `chat(self, inbox)` to your agent, send and receive raw message dictionaries that use canonical player IDs such as `"player_0"` and `"player_1"`. For example, return `[{"to": "player_0", "text": "Hello."}]` to send a direct message. The village helpers do not include a chat namespace. Read [`environment.md`](environment.md#chat-with-other-agents) for the inbox format, broadcasts, and delivery timing.

In `watch` and `eval`, your `Agent` controls the whole cast, and `scripted_visitor` controls the visitor. The `naive` built-in is the simple baseline for the cast. When you are ready to submit, follow the [submitting guide](https://vox-deorum.github.io/game-sandbox/students/submitting/).

## Optional LLM API

If your instructor enables model calls, follow [Using the LLM API](llm.md). Copy `.env.example` to `.env`, add the endpoint and key, and never commit either secret.

Test the connection with:

```console
python -m sandbox llm
```

Design Goal

My goal is to make the village feel more alive by giving villagers jobs, daily routines, and conversations with the visitor. By talking to them, visitors should learn about the different jobs in the village, what the villagers take care of, and how everyone contributes to keeping the village running.

Short Reflection

Each villager has an assigned workplace, such as the pump, benches, crops, or crates. Their conversations are based on their job around the village. Villagers explain what they are working on and why it is important. I kept their replies consistent by using scripted responses for common questions about jobs and village life.

After the Season 4 feedback, I focused on improving villager movement and making their daily routines more consistent. I added route planning that avoids other villagers when possible and rebuilds routes when another villager blocks the way. I also improved their schedules so they go to their assigned workplaces during the day and return home at night. Another important change was removing the wait for LLM-generated replies because it caused the villagers to stop responding or acting immediately when someone talked to them.

AI-Use Disclosure and Reflection

I used ChatGPT to help with improving the villagers' conversations and movement. I checked the suggestions by reviewing the code and testing the villagers in the game to see if their jobs, movement, and conversations worked as expected. Using AI helped me understand problems and find ways to improve the project, but I still needed to test the changes because some suggestions did not work correctly at first.
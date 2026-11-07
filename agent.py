
"""Days at Three Branches - Season 5 Village Dialogue."""

import json

from sandbox.observation_types import ThreeBranchesAction, ThreeBranchesObservation
from sandbox.village import action, day, geometry, layout, me, people, props
from sandbox.llm import BackgroundLLM


def _cell_centre(cell):
    return {"x": cell["x"] + 0.5, "y": cell["y"] + 0.5}


class Agent:
    """Villagers have different jobs, schedules, and conversations."""

    def reset(self, seed: int, observation: ThreeBranchesObservation) -> None:
        player_id = me.player_id(observation)
        number = int(player_id.split("_")[1])
        self.player_id = player_id

        home = me.home(observation)
        self.door = None

        if home != "none":
            self.door = layout.doorway(observation, home)

        self.pump = None
        self.benches = []
        self.crops = []
        self.crates = []
        self.workplaces = []
        self.job_positions = {}

        all_props = props.all(observation)
        index = 0

        while index < len(all_props):
            prop = all_props[index]
            prop_type = prop["type"]
            position = _cell_centre(prop["cell"])

            if prop_type == "pump":
                self.pump = position
                self.job_positions["pump"] = position
                self.workplaces.append({
                    "role": "pump",
                    "position": position
                })

            elif prop_type == "bench":
                self.benches.append(position)
                role = "bench" + str(len(self.benches))
                self.job_positions[role] = position
                self.workplaces.append({
                    "role": role,
                    "position": position
                })

            elif "crop" in prop_type:
                self.crops.append(position)
                role = "crop" + str(len(self.crops))
                self.job_positions[role] = position
                self.workplaces.append({
                    "role": role,
                    "position": position
                })

            elif "crate" in prop_type:
                self.crates.append(position)
                role = "crate" + str(len(self.crates))
                self.job_positions[role] = position
                self.workplaces.append({
                    "role": role,
                    "position": position
                })

            index += 1

        # Player 0 is the visitor and does not have a job.
        self.morning_role = "home"
        self.midday_role = "home"

        # Give each pair of villagers a different workplace.
        if number > 0:
            if len(self.workplaces) > 0:
                job_index = (number - 1) // 2
                job_index = job_index % len(self.workplaces)

                midday_index = (job_index + 1) % len(self.workplaces)

                self.morning_role = self.workplaces[job_index]["role"]
                self.midday_role = self.workplaces[midday_index]["role"]

        self.role = self.morning_role

        # Movement information.
        self.route = []
        self.route_index = 0
        self.route_target = None
        self.stuck_ticks = 0

        # Conversation information.
        self.latest = observation
        self.visitor_id = "player_0"
        self.history = []
        self.last_reply = ""
        self.pending_question = None
        self.waiting_for_reply = False
        self.calls_left = 6
        self.llm = BackgroundLLM()

        # Visitor workplace requests.
        self.requested_target = None
        self.request_until = 0
        self.requested_phase = None

        # Wave cooldown.
        self.wave_cooldown = 0

        self._make_route(observation)

    def _workplace(self):
        """Return the current job's workplace."""

        target = self.job_positions.get(self.role)

        if target is None:
            target = self.door

        return target

    def _cell_blocked_by_villager(self, observation, cell):
        """Check whether another villager is occupying this cell."""

        target = _cell_centre(cell)

        # Check villagers in sight.
        seen_people = people.seen(observation)
        index = 0

        while index < len(seen_people):
            person = seen_people[index]
            person_id = person["id"]

            if person_id != self.player_id:
                if people.is_npc(person_id):
                    distance = geometry.distance(
                        target,
                        person["position"]
                    )

                    if distance < 0.85:
                        return True

            index += 1

        # Check villagers nearby.
        nearby_people = people.nearby(observation)
        index = 0

        while index < len(nearby_people):
            person = nearby_people[index]
            person_id = person["id"]

            if person_id != self.player_id:
                if people.is_npc(person_id):
                    distance = geometry.distance(
                        target,
                        person["position"]
                    )

                    if distance < 0.85:
                        return True

            index += 1

        return False

    def _find_target(self, observation):
        """Choose a destination based on the time of day."""

        phase = day.phase(observation)

        if phase == "night":
            self.requested_target = None
            self.request_until = 0
            self.requested_phase = None
            return self.door

        if phase == "dawn":
            self.requested_target = None
            self.requested_phase = None
            return self.door

        if self.requested_target is not None:
            if self.requested_phase != phase:
                self.requested_target = None
                self.request_until = 0
                self.requested_phase = None

        if self.requested_target is not None:
            if day.tick(observation) > self.request_until:
                self.requested_target = None
                self.requested_phase = None

        if self.requested_target is not None:
            return self.requested_target

        if phase == "morning":
            self.role = self.morning_role
            return self._workplace()

        if phase == "midday":
            self.role = self.midday_role
            return self._workplace()

        return self._workplace()

    def _make_route(self, observation):
        """Find a route while avoiding other villagers."""

        target = self._find_target(observation)

        if target is None:
            self.route = []
            self.route_index = 0
            self.route_target = None
            return

        start = layout.cell_at(observation, me.position(observation))

        if start is None:
            self.route = []
            self.route_index = 0
            self.route_target = target
            return

        frame = layout.frame(observation)
        cells_x = int(frame["cells_x"])
        cells_y = int(frame["cells_y"])
        max_cells = cells_x * cells_y

        queue = [start]
        visited = {(start["x"], start["y"])}
        previous = {}

        best_cell = start
        best_distance = geometry.distance(_cell_centre(start), target)

        queue_index = 0
        found_target = False

        while queue_index < len(queue):
            current = queue[queue_index]
            queue_index += 1

            distance = geometry.distance(_cell_centre(current), target)

            if distance < best_distance:
                best_distance = distance
                best_cell = current

            if distance <= 1.1:
                best_cell = current
                found_target = True

            if not found_target:
                neighbors = [
                    {"x": current["x"] + 1, "y": current["y"]},
                    {"x": current["x"] - 1, "y": current["y"]},
                    {"x": current["x"], "y": current["y"] + 1},
                    {"x": current["x"], "y": current["y"] - 1}
                ]

                neighbor_index = 0

                while neighbor_index < len(neighbors):
                    neighbor = neighbors[neighbor_index]
                    x = neighbor["x"]
                    y = neighbor["y"]
                    key = (x, y)

                    inside = True

                    if x < 0 or x >= cells_x:
                        inside = False
                    if y < 0 or y >= cells_y:
                        inside = False

                    if inside:
                        if key not in visited:
                            if layout.can_step(observation, current, neighbor):
                                if not self._cell_blocked_by_villager(
                                    observation,
                                    neighbor
                                ):
                                    visited.add(key)
                                    previous[key] = current
                                    queue.append(neighbor)

                    neighbor_index += 1

        route = []
        current = best_cell
        found_start = False
        route_count = 0

        while route_count < max_cells:
            route.append(current)
            route_count += 1

            if current["x"] == start["x"]:
                if current["y"] == start["y"]:
                    found_start = True
                    route_count = max_cells

            if not found_start:
                key = (current["x"], current["y"])

                if key in previous:
                    current = previous[key]
                else:
                    route_count = max_cells

        if found_start:
            route.reverse()
            self.route = route
            self.route_index = 0
            self.route_target = target
        else:
            self.route = []
            self.route_index = 0
            self.route_target = target

    def _route_needs_rebuild(self, observation):
        """Check whether the route needs to change."""

        target = self._find_target(observation)

        if target is None:
            return False

        if self.route_target is None:
            return True

        if geometry.distance(target, self.route_target) > 0.1:
            return True

        # Rebuild the route if another villager blocks the next cell.
        if self.route_index < len(self.route):
            next_cell = self.route[self.route_index]

            if self._cell_blocked_by_villager(observation, next_cell):
                return True

        return False

    def _next_route_position(self, observation):
        """Find the next position on the route."""

        current_cell = layout.cell_at(
            observation,
            me.position(observation)
        )

        if current_cell is None:
            return None

        if self.route_index < len(self.route):
            route_cell = self.route[self.route_index]

            if current_cell["x"] == route_cell["x"]:
                if current_cell["y"] == route_cell["y"]:
                    self.route_index += 1

        if self.route_index >= len(self.route):
            return None

        next_cell = self.route[self.route_index]

        if layout.can_step(observation, current_cell, next_cell):
            return _cell_centre(next_cell)

        return None

    def _persona(self):
        """Return a personality for this villager."""

        personas = {
            "pump": "You are a friendly villager who takes care of the village pump. You care about making sure everyone has water.",
            "bench1": "You are a calm villager who looks after the village benches. You enjoy helping people find a place to rest.",
            "bench2": "You are a calm villager who looks after the village benches. You enjoy helping people find a place to rest.",
            "crop1": "You are a hardworking villager who takes care of the crops. You believe growing food is important.",
            "crop2": "You are a hardworking villager who takes care of the crops. You believe growing food is important.",
            "crop3": "You are a hardworking villager who takes care of the crops. You believe growing food is important.",
            "crate1": "You are an organized villager who works with the village crates and keeps supplies in order.",
            "crate2": "You are an organized villager who works with the village crates and keeps supplies in order.",
            "crate3": "You are an organized villager who works with the village crates and keeps supplies in order.",
            "bench3": "You are a calm villager who looks after the village benches. You enjoy helping people find a place to rest."
        }

        return personas.get(
            self.role,
            "You are a helpful villager who works around the village."
        )

    def _current_facts(self, observation):
        """Collect facts the villager can currently see."""

        facts = {
            "role": self.role,
            "phase": day.phase(observation),
            "workplace": self.role,
            "visible_props": []
        }

        seen_props = props.seen(observation)
        index = 0

        while index < len(seen_props):
            item = seen_props[index]

            facts["visible_props"].append({
                "prop": item["prop"],
                "state": item["state"]
            })

            index += 1

        return facts

    def _make_prompt(self, question, observation):
        """Prepare the conversation for the LLM."""

        system_text = (
            self._persona()
            + " Answer as this villager. Only use the facts provided. "
            + "Do not invent details or claim to see things not listed. "
            + "If you do not know, say so. Keep replies short and friendly. "
            + "Return only JSON with two fields: reply and intent. "
            + "The reply must be no more than 160 characters. "
            + "The intent must be none, show_work, or stop."
        )

        user_text = (
            "Current facts: "
            + json.dumps(self._current_facts(observation))
            + "\nVisitor question: "
            + question
        )

        messages = [
            {"role": "system", "content": system_text}
        ]

        index = 0

        while index < len(self.history):
            messages.append(self.history[index])
            index += 1

        messages.append({
            "role": "user",
            "content": user_text
        })

        return messages

    def _scripted_reply(self, question):
        """Give a simple answer without waiting for an LLM."""

        if "hello" in question or "hi" in question:
            return "Hello! Welcome to the village. Feel free to look around."

        if "job" in question or "work" in question:
            replies = {
                "pump": "I take care of the village pump. People need water every day.",
                "bench1": "I look after the village benches. They are a good place to rest.",
                "bench2": "I look after the village benches. They are a good place to rest.",
                "bench3": "I look after the village benches. They are a good place to rest.",
                "crop1": "I help take care of the crops. Growing food is important for our village.",
                "crop2": "I help take care of the crops. Growing food is important for our village.",
                "crop3": "I help take care of the crops. Growing food is important for our village.",
                "crate1": "I work with the village crates. They help us store supplies.",
                "crate2": "I work with the village crates. They help us store supplies.",
                "crate3": "I work with the village crates. They help us store supplies."
            }

            return replies.get(
                self.role,
                "I help with different jobs around the village."
            )

        if "water" in question or "pump" in question:
            return "The pump is where villagers come to get water. It is important to daily life."

        if "food" in question or "crop" in question or "farm" in question:
            return "Our crops help provide food for the village. They need attention throughout the day."

        if "bench" in question or "rest" in question:
            return "The benches are places where villagers can take a break during the day."

        if "crate" in question or "supplies" in question:
            return "We use crates to keep village supplies organized."

        if "village" in question or "three branches" in question:
            return "Three Branches is our home. Everyone has a role in keeping the village running."

        if "time" in question or "night" in question or "day" in question:
            return "Our routines change throughout the day. When night comes, everyone heads home."

        return "I'm not sure about that. You can ask me about my job or something around the village."

    def _handle_intent(self, intent, observation):
        """Handle visitor requests."""

        phase = day.phase(observation)

        if intent == "show_work":
            if phase == "morning" or phase == "midday":
                workplace = self._workplace()

                if workplace is not None:
                    self.requested_target = workplace
                    self.request_until = day.tick(observation) + 80
                    self.requested_phase = phase
                    return "Sure! Follow me and I can show you where I work."

            return "I cannot show you my work right now. Maybe you can visit me during the day."

        if intent == "stop":
            self.requested_target = None
            self.request_until = 0
            self.requested_phase = None
            return "Okay, I will return to my usual routine."

        return None

    def chat(self, inbox: list[dict]) -> list[dict] | None:
        """Answer visitor messages immediately without waiting for the LLM."""

        index = len(inbox) - 1

        while index >= 0:
            message = inbox[index]

            sender = message.get("from")
            receiver = message.get("to")
            question = message.get("text", "").lower()

            if sender == self.visitor_id:
                if receiver is None or receiver == self.player_id:
                    reply = self._scripted_reply(question)

                    self.last_reply = reply

                    self.history.append({
                        "role": "user",
                        "content": question
                    })

                    self.history.append({
                        "role": "assistant",
                        "content": reply
                    })

                    if len(self.history) > 6:
                        self.history = self.history[-6:]

                    return [{
                        "to": self.visitor_id,
                        "text": reply
                    }]

            index -= 1

        return None

    def act(self, observation: ThreeBranchesObservation) -> ThreeBranchesAction:
        """Choose an action for the current tick."""

        self.latest = observation
        here = me.position(observation)
        phase = day.phase(observation)

        # Wave at the visitor sometimes.
        expression = "none"

        if self.wave_cooldown > 0:
            self.wave_cooldown -= 1

        if self.wave_cooldown == 0:
            if phase != "night":
                if people.seen(observation):
                    expression = "wave"
                    self.wave_cooldown = 30

        # Update the route when the destination changes or is blocked.
        if self._route_needs_rebuild(observation):
            self._make_route(observation)

        next_position = self._next_route_position(observation)

        # Keep walking toward the workplace.
        if next_position is not None:
            self.stuck_ticks = 0

            return action.walk(
                geometry.heading_to(here, next_position),
                1.0,
                expression
            )

        # Face the workplace when the villager reaches it.
        target = self._find_target(observation)
        heading = me.heading(observation)

        if target is not None:
            heading = geometry.heading_to(here, target)

        # Use a bench while facing it.
        usable = props.usable(observation)

        if phase != "night":
            if usable is not None:
                if usable["type"] == "bench":
                    if self.role == "bench1" or self.role == "bench2":
                        return action.stand(heading, "use")

        # Stand facing the workplace object.
        if self.route_index < len(self.route):
            self.stuck_ticks += 1

            if self.stuck_ticks >= 10:
                self._make_route(observation)
                self.stuck_ticks = 0

        return action.walk(heading, 0.0, expression)
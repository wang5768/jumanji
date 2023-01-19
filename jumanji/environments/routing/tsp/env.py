# Copyright 2022 InstaDeep Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Tuple

import jax
import jax.numpy as jnp
from chex import PRNGKey

from jumanji import specs
from jumanji.env import Environment
from jumanji.environments.routing.tsp.specs import ObservationSpec
from jumanji.environments.routing.tsp.types import Observation, State
from jumanji.environments.routing.tsp.utils import compute_tour_length, generate_problem
from jumanji.types import Action, TimeStep, restart, termination, transition


class TSP(Environment[State]):
    """Traveling Salesman Problem (TSP) environment as described in [1].

    - observation: Observation
        - problem: jax array (float32) of shape (num_cities, 2)
            the coordinates of each city
        - start_position: int32
            the identifier (index) of the first visited city
        - position: int32
            the identifier (index) of the last visited city
        - action_mask: jax array (bool) of shape (num_cities,)
            binary mask (False/True <--> illegal/legal <--> cannot be visited/can be visited)

    - reward: jax array (float32)
        the negative sum of the distances between consecutive cities at the end of the episode
        (the reward is 0 if a previously selected city is selected again)

    - state: State
        - problem: jax array (float32) of shape (num_cities, 2)
            the coordinates of each city
        - position: int32
            the identifier (index) of the last visited city
        - visited_mask: jax array (bool) of shape (num_cities,)
            binary mask (False/True <--> not visited/visited)
        - order: jax array (int32) of shape (num_cities,)
            the identifiers of the cities that have been visited (-1 means that no city has been
            visited yet at that time in the sequence)
        - num_visited: int32
            number of cities that have been visited

    [1] Kwon Y., Choo J., Kim B., Yoon I., Min S., Gwon Y. (2020). "POMO: Policy Optimization
        with Multiple Optima for Reinforcement Learning".
    """

    def __init__(self, num_cities: int = 10):
        self.num_cities = num_cities

    def __repr__(self) -> str:
        return f"TSP environment with {self.num_cities} cities."

    def reset(self, key: PRNGKey) -> Tuple[State, TimeStep]:
        """Resets the environment.

        Args:
            key: used to randomly generate the problem and the start position.

        Returns:
            state: State object corresponding to the new state of the environment.
            timestep: TimeStep object corresponding to the first timestep returned
                by the environment.
        """
        problem = generate_problem(key, self.num_cities)
        state = State(
            problem=problem,
            position=jnp.array(-1, jnp.int32),
            visited_mask=jnp.zeros(self.num_cities, dtype=bool),
            order=-1 * jnp.ones(self.num_cities, jnp.int32),
            num_visited=jnp.int32(0),
        )
        timestep = restart(observation=self._state_to_observation(state))
        return state, timestep

    def step(self, state: State, action: Action) -> Tuple[State, TimeStep]:
        """Run one timestep of the environment's dynamics.

        Args:
            state: `State` object containing the dynamics of the environment.
            action: `Array` containing the index of the next position to visit.

        Returns:
            state: the next state of the environment.
            timestep: the timestep to be observed.
        """
        is_valid = state.visited_mask[action] == 0
        state = jax.lax.cond(
            pred=is_valid,
            true_fun=lambda x: self._update_state(x[0], x[1]),
            false_fun=lambda _: state,
            operand=[state, action],
        )
        timestep = self._state_to_timestep(state, is_valid)
        return state, timestep

    def observation_spec(self) -> ObservationSpec:
        """Returns the observation spec.

        Returns:
            observation_spec: a tree of specs containing the spec for each of the constituent fields
                of an observation.
        """
        problem_obs = specs.BoundedArray(
            shape=(self.num_cities, 2),
            minimum=0.0,
            maximum=1.0,
            dtype=jnp.float32,
            name="problem",
        )
        start_position_obs = specs.DiscreteArray(
            self.num_cities, dtype=jnp.int32, name="start position"
        )
        position_obs = specs.DiscreteArray(
            self.num_cities, dtype=jnp.int32, name="position"
        )
        action_mask = specs.BoundedArray(
            shape=(self.num_cities,),
            dtype=bool,
            minimum=False,
            maximum=True,
            name="action mask",
        )
        return ObservationSpec(
            problem_obs,
            start_position_obs,
            position_obs,
            action_mask,
        )

    def action_spec(self) -> specs.DiscreteArray:
        """Returns the action spec.

        Returns:
            action_spec: a `specs.DiscreteArray` spec.
        """
        return specs.DiscreteArray(self.num_cities, name="action")

    def _update_state(self, state: State, next_position: int) -> State:
        """
        Updates the state of the environment.

        Args:
            state: State object containing the dynamics of the environment.
            next_position: int32, index of the next position to visit.

        Returns:
            state: State object corresponding to the new state of the environment.
        """
        return State(
            problem=state.problem,
            position=next_position,
            visited_mask=state.visited_mask.at[next_position].set(True),
            order=state.order.at[state.num_visited].set(next_position),
            num_visited=state.num_visited + 1,
        )

    def _state_to_observation(self, state: State) -> Observation:
        """Converts a state into an observation.

        Args:
            state: `State` object containing the dynamics of the environment.

        Returns:
            observation: `Observation` object containing the observation of the environment.
        """
        return Observation(
            problem=state.problem,
            start_position=state.order[0],
            position=state.position,
            action_mask=jnp.logical_not(state.visited_mask),
        )

    def _state_to_timestep(self, state: State, is_valid: bool) -> TimeStep:
        """Checks if the state is terminal and converts it into a timestep. The episode
        terminates if there is no legal action to take, namely if all cities have been
        visited or if the last action was not valid. An invalid action is given a large
        negative penalty.

        Args:
            state: `State` object containing the dynamics of the environment.
            is_valid: boolean indicating whether the last action was valid.

        Returns:
            timestep: `TimeStep` object containing the timestep of the environment.
        """
        is_done = (state.num_visited == self.num_cities) | (~is_valid)

        def make_termination_timestep(state: State) -> TimeStep:
            reward = jnp.where(
                is_valid,
                -compute_tour_length(state.problem, state.order),
                jnp.float32(-self.num_cities * jnp.sqrt(2)),
            )
            return termination(
                reward=reward,
                observation=self._state_to_observation(state),
            )

        def make_transition_timestep(state: State) -> TimeStep:
            return transition(
                reward=jnp.float32(0), observation=self._state_to_observation(state)
            )

        timestep: TimeStep = jax.lax.cond(
            is_done, make_termination_timestep, make_transition_timestep, state
        )

        return timestep

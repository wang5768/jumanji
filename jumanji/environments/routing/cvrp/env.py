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

from typing import Optional, Tuple

import jax
import jax.numpy as jnp
from chex import PRNGKey
from jax import random
from numpy.typing import NDArray

from jumanji import specs
from jumanji.env import Environment
from jumanji.environments.routing.cvrp.env_viewer import CVRPViewer
from jumanji.environments.routing.cvrp.types import Observation, State
from jumanji.environments.routing.cvrp.utils import (
    DEPOT_IDX,
    compute_tour_length,
    generate_problem,
)
from jumanji.types import Action, TimeStep, restart, termination, transition


class CVRP(Environment[State]):
    """Capacitated Vehicle Routing Problem (CVRP) environment as described in [1].
        - observation: Observation
        - coordinates: jax array (float32) of shape (num_nodes + 1, 2)
            the coordinates of each node and the depot.
        - demands: jax array (float32) of shape (num_nodes + 1,)
            the associated cost of each node and the depot (0.0 for the depot).
        - position: jax array (int32)
            the index of the last visited node.
        - capacity: jax array (float32)
            the current capacity of the vehicle.
        - action_mask: jax array (bool) of shape (num_nodes + 1,)
            binary mask (False/True <--> invalid/valid action).

    - reward: jax array (float32)
        the negative sum of the distances between consecutive nodes at the end of the episode (the
        reward is 0 if a previously selected non-dept node is selected again, or the depot is
        selected twice in a row).

    - state: State
        - coordinates: jax array (float32) of shape (num_nodes + 1, 2)
            the coordinates of each node and the depot.
        - demands: jax array (int32) of shape (num_nodes + 1,)
            the associated cost of each node and the depot (0.0 for the depot).
        - position: jax array (int32)
            the index of the last visited node.
        - capacity: jax array (int32)
            the current capacity of the vehicle.
        - visited_mask: jax array (bool) of shape (num_nodes + 1,)
            binary mask (False/True <--> not visited/visited).
        - order: jax array (int32) of shape (2 * num_nodes,)
            the identifiers of the nodes that have been visited (-1 means that no node has been
            visited yet at that time in the sequence).
        - num_visits: int32
            number of actions that have been taken (i.e., unique visits).

    [1] Toth P., Vigo D. (2014). "Vehicle routing: problems, methods, and applications".
    """

    def __init__(
        self,
        num_nodes: int = 100,
        max_capacity: int = 30,
        max_demand: int = 10,
        render_mode: str = "human",
    ):
        """Instantiates a CVRP environment.

        Args:
            num_nodes: the number of city nodes in the environment.
            max_capacity: the maximum capacity of the vehicle.
            max_demand: the maximum demand of each node.
            render_mode: the mode for visualising the environment, can be "human" or "rgb_array".
        """

        if max_capacity < max_demand:
            raise ValueError(
                f"The demand associated with each node must be lower than the maximum capacity, "
                f"hence the maximum capacity must be >= {max_demand}."
            )
        self.num_nodes = num_nodes
        self.max_capacity = max_capacity
        self.max_demand = max_demand

        # Create viewer used for rendering
        self._env_viewer = CVRPViewer(
            name="CVRP",
            num_cities=self.num_nodes,
            render_mode=render_mode,
        )

    def __repr__(self) -> str:
        return (
            f"CVRP(num_nodes={self.num_nodes}, max_capacity={self.max_capacity}, "
            f"max_demand={self.max_demand})"
        )

    def reset(self, key: PRNGKey) -> Tuple[State, TimeStep]:
        """Resets the environment.

        Args:
            key: used to randomly generate the coordinates.

        Returns:
             state: `State` object corresponding to the new state of the environment.
             timestep: `TimeStep` object corresponding to the first timestep returned by the
             environment.
        """
        problem_key, start_key = random.split(key)
        coordinates, demands = generate_problem(
            problem_key, self.num_nodes, self.max_demand
        )
        state = State(
            coordinates=coordinates,
            demands=demands,
            position=jnp.int32(DEPOT_IDX),
            capacity=self.max_capacity,
            visited_mask=jnp.zeros(self.num_nodes + 1, dtype=bool)
            .at[DEPOT_IDX]
            .set(True),
            order=jnp.zeros(2 * self.num_nodes, jnp.int32),
            num_total_visits=jnp.int32(1),
        )
        timestep = restart(observation=self._state_to_observation(state))
        return state, timestep

    def step(self, state: State, action: Action) -> Tuple[State, TimeStep]:
        """Run one timestep of the environment's dynamics.

        Args:
            state: State object containing the dynamics of the environment.
            action: Array containing the index of the next node to visit.

        Returns:
            state, timestep: Tuple[State, TimeStep] containing the next state of the environment,
            as well as the timestep to be observed.
        """
        is_valid = (~state.visited_mask[action]) & (
            state.capacity >= state.demands[action]
        )

        state = jax.lax.cond(
            is_valid,
            self._update_state,
            lambda *_: state,
            state,
            action,
        )
        timestep = self._state_to_timestep(state, is_valid)
        return state, timestep

    def observation_spec(self) -> specs.Spec:
        """Returns the observation spec.

        Returns:
            observation_spec: a Tuple containing the spec for each of the constituent fields of an
            observation.
        """
        coordinates = specs.BoundedArray(
            shape=(self.num_nodes + 1, 2),
            minimum=0.0,
            maximum=1.0,
            dtype=jnp.float32,
            name="coordinates",
        )
        demands = specs.BoundedArray(
            shape=(self.num_nodes + 1,),
            minimum=0.0,
            maximum=1.0,
            dtype=jnp.float32,
            name="demands",
        )
        position = specs.DiscreteArray(
            self.num_nodes + 1, dtype=jnp.int32, name="position"
        )
        capacity = specs.BoundedArray(
            shape=(), minimum=0.0, maximum=1.0, dtype=jnp.float32, name="capacity"
        )
        action_mask = specs.BoundedArray(
            shape=(self.num_nodes + 1,),
            dtype=jnp.bool_,
            minimum=False,
            maximum=True,
            name="action mask",
        )
        return specs.Spec(
            Observation,
            "ObservationSpec",
            coordinates=coordinates,
            demands=demands,
            position=position,
            capacity=capacity,
            action_mask=action_mask,
        )

    def action_spec(self) -> specs.DiscreteArray:
        """Returns the action spec.

        Returns:
            action_spec: a `specs.DiscreteArray` spec.
        """
        return specs.DiscreteArray(self.num_nodes + 1, name="action")

    def render(self, state: State) -> Optional[NDArray]:
        """Render the given state of the environment. This rendering shows the layout of the tour so
         far with the cities as circles, and the depot as a square.

        Args:
            state: environment state to render.

        Returns:
            rgb_array: the RGB image of the state as an array.
        """
        return self._env_viewer.render(state)

    def _update_state(self, state: State, next_node: jnp.int32) -> State:
        """Updates the state of the environment.

        Args:
            state: State object containing the dynamics of the environment.
            next_node: int, index of the next node to visit.

        Returns:
            state: State object corresponding to the new state of the environment.
        """
        next_node = jax.lax.select(
            pred=state.visited_mask.all(),
            on_true=DEPOT_IDX,  # stay in the depot if we have visited all nodes
            on_false=next_node,
        )

        capacity = jax.lax.select(
            pred=next_node == DEPOT_IDX,
            on_true=self.max_capacity,
            on_false=state.capacity - state.demands[next_node],
        )

        # Set depot to False (valid to visit) since it can be visited multiple times
        visited_mask = state.visited_mask.at[DEPOT_IDX].set(False)

        return State(
            coordinates=state.coordinates,
            demands=state.demands,
            position=next_node,
            capacity=capacity,
            visited_mask=visited_mask.at[next_node].set(True),
            order=state.order.at[state.num_total_visits].set(next_node),
            num_total_visits=state.num_total_visits + 1,
        )

    def _state_to_observation(self, state: State) -> Observation:
        """Converts a state into an observation.

        Args:
            state: `State` object containing the dynamics of the environment.

        Returns:
            observation: `Observation` object containing the observation of the environment.
        """
        # A node is false if it has been visited or the vehicle does not have enough capacity to
        # cover its demand.
        action_mask = ~state.visited_mask & (state.capacity >= state.demands)

        # The depot is valid (True) if we are not at it, else it is invalid (False).
        action_mask = action_mask.at[DEPOT_IDX].set(state.position != DEPOT_IDX)

        return Observation(
            coordinates=state.coordinates,
            demands=jnp.float32(state.demands / self.max_capacity),
            position=state.position,
            capacity=jnp.float32(state.capacity / self.max_capacity),
            action_mask=action_mask,
        )

    def _state_to_timestep(self, state: State, is_valid: bool) -> TimeStep:
        """Checks if the state is terminal and converts it into a timestep. The episode
        terminates if there is no legal action to take, namely if all nodes have been
        visited or if the last action was not valid. An invalid action is given a large
        negative penalty.

        Args:
            state: `State` object containing the dynamics of the environment.

        Returns:
            timestep: `TimeStep` object containing the timestep of the environment.
        """

        def make_termination_timestep(state: State) -> TimeStep:
            reward = jnp.where(
                is_valid,
                -compute_tour_length(state.coordinates, state.order),
                jnp.float32(-self.num_nodes * 2 * jnp.sqrt(2)),
            )
            return termination(
                reward=reward,
                observation=self._state_to_observation(state),
            )

        def make_transition_timestep(state: State) -> TimeStep:
            return transition(
                reward=jnp.float32(0), observation=self._state_to_observation(state)
            )

        is_done = (state.visited_mask.all()) | (~is_valid)
        timestep: TimeStep = jax.lax.cond(
            is_done,
            make_termination_timestep,
            make_transition_timestep,
            state,
        )
        return timestep

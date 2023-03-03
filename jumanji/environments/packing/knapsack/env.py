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

from typing import Any, Optional, Tuple

import chex
import jax
import jax.numpy as jnp

from jumanji import specs
from jumanji.env import Environment
from jumanji.environments.packing.knapsack.env_viewer import KnapsackViewer
from jumanji.environments.packing.knapsack.reward import DenseReward, RewardFn
from jumanji.environments.packing.knapsack.types import Observation, State
from jumanji.types import TimeStep, restart, termination, transition


class Knapsack(Environment[State]):
    """Knapsack environment as described in [1].

    - observation: Observation
        - weights: jax array (float) of shape (num_items,)
            the weights of the items.
        - values: jax array (float) of shape (num_items,)
            the values of the items.
        - packed_items: jax array (bool) of shape (num_items,)
            binary mask denoting which items are already packed into the knapsack.
        - action_mask: jax array (bool) of shape (num_items,)
            binary mask denoting which items can be packed into the knapsack.

    - action: jax array (int32) of shape ()
        [0, ..., num_items - 1] -> item to pack.

    - reward: jax array (float) of shape (), could be either:
        - dense: the value of the item to pack at the current timestep.
        - sparse: the sum of the values of the items packed in the bag at the end of the episode.
        In both cases, the reward is 0 if the action is invalid, i.e. an item that was previously
        selected is selected again or has a weight larger than the bag capacity.

    - episode termination:
        - if no action can be performed, i.e. all items are packed or each remaining item's weight
            is larger than the bag capacity.
        - if an invalid action is taken, i.e. the chosen item is already packed or has a weight
            larger than the bag capacity.

    - state: `State`
        - weights: jax array (float) of shape (num_items,)
            the weights of the items.
        - values: jax array (float) of shape (num_items,)
            the values of the items.
        - packed_items: jax array (bool) of shape (num_items,)
            binary mask denoting which items are already packed into the knapsack.
        - remaining_budget: jax array (float)
            the budget currently remaining.

    [1] https://arxiv.org/abs/2010.16011
    """

    def __init__(
        self,
        num_items: int = 50,
        total_budget: float = 12.5,
        reward_fn: Optional[RewardFn] = None,
        render_mode: str = "human",
    ):
        """Instantiates a `Knapsack` environment.

        Args:
            num_items: the number of items in the environment.
                Defaults to 50.
            total_budget: the capacity of the knapsack.
                Defaults to 12.5.
            reward_fn: `RewardFn` whose `__call__` method computes the reward of an environment
                transition. The function must compute the reward based on the current state,
                the chosen action, the next state and whether the action is valid.
                Implemented options are [`DenseReward`, `SparseReward`]. Defaults to `DenseReward`.
            render_mode: string that defines the mode of rendering.
                Choices are ["human, "rgb"], defaults to "human".
        """

        self.num_items = num_items
        self.total_budget = total_budget
        self.reward_fn = reward_fn or DenseReward()
        self.env_viewer = KnapsackViewer(
            name="Knapsack",
            render_mode=render_mode,
            total_budget=total_budget,
        )

    def __repr__(self) -> str:
        return (
            f"Knapsack environment with {self.num_items} items "
            f"and a total budget of {self.total_budget}."
        )

    def reset(self, key: chex.PRNGKey) -> Tuple[State, TimeStep[Observation]]:
        """Resets the environment.

        Args:
            key: used to randomly generate the weights and values of the items.

        Returns:
            state: the new state of the environment.
            timestep: the first timestep returned by the environment.
        """
        weights, values = jax.random.uniform(
            key, (2, self.num_items), minval=0, maxval=1
        )
        state = State(
            weights=weights,
            values=values,
            packed_items=jnp.zeros(self.num_items, dtype=bool),
            remaining_budget=jnp.array(self.total_budget, float),
        )
        timestep = restart(observation=self._state_to_observation(state))
        return state, timestep

    def step(
        self, state: State, action: chex.Numeric
    ) -> Tuple[State, TimeStep[Observation]]:
        """Run one timestep of the environment's dynamics.

        Args:
            state: State object containing the dynamics of the environment.
            action: index of next item to take.

        Returns:
            state: next state of the environment.
            timestep: the timestep to be observed.
        """
        item_fits = state.remaining_budget >= state.weights[action]
        item_not_packed = ~state.packed_items[action]
        is_valid = item_fits & item_not_packed
        next_state = jax.lax.cond(
            is_valid,
            self._update_state,
            lambda *_: state,
            state,
            action,
        )

        observation = self._state_to_observation(next_state)

        no_items_available = ~jnp.any(observation.action_mask)
        is_done = no_items_available | ~is_valid

        reward = self.reward_fn(state, action, next_state, is_valid, is_done)

        timestep = jax.lax.cond(
            is_done,
            termination,
            transition,
            reward,
            observation,
        )

        return next_state, timestep

    def observation_spec(self) -> specs.Spec[Observation]:
        """Returns the observation spec.

        Returns:
            Spec for each field in the Observation:
            - weights: BoundedArray (float) of shape (num_items,).
            - values: BoundedArray (float) of shape (num_items,).
            - packed_items: BoundedArray (bool) of shape (num_items,).
            - action_mask: BoundedArray (bool) of shape (num_items,).
        """
        weights = specs.BoundedArray(
            shape=(self.num_items,),
            minimum=0.0,
            maximum=1.0,
            dtype=float,
            name="weights",
        )
        values = specs.BoundedArray(
            shape=(self.num_items,),
            minimum=0.0,
            maximum=1.0,
            dtype=float,
            name="values",
        )
        packed_items = specs.BoundedArray(
            shape=(self.num_items,),
            minimum=False,
            maximum=True,
            dtype=bool,
            name="packed_items",
        )
        action_mask = specs.BoundedArray(
            shape=(self.num_items,),
            minimum=False,
            maximum=True,
            dtype=bool,
            name="action_mask",
        )
        return specs.Spec(
            Observation,
            "ObservationSpec",
            weights=weights,
            values=values,
            packed_items=packed_items,
            action_mask=action_mask,
        )

    def action_spec(self) -> specs.DiscreteArray:
        """Returns the action spec.

        Returns:
            action_spec: a `specs.DiscreteArray` spec.
        """
        return specs.DiscreteArray(self.num_items, name="action")

    def render(self, state: State) -> Any:
        """Render the environment state, displaying which items have been picked so far,
        their value, and the remaining budget.

        Args:
            state: the environment state to be rendered.
        """
        self.env_viewer.render(state)

    def _update_state(self, state: State, action: chex.Numeric) -> State:
        """Updates the state of the environment.

        Args:
            state: State object containing the dynamics of the environment.
            action: index of the next item to take.

        Returns:
            state: State object corresponding to the new state of the environment.
        """
        return State(
            weights=state.weights,
            values=state.values,
            packed_items=state.packed_items.at[action].set(True),
            remaining_budget=state.remaining_budget - state.weights[action],
        )

    def _state_to_observation(self, state: State) -> Observation:
        """Converts a state to an observation.

        Args:
            state: State object containing the dynamics of the environment.

        Returns:
            observation: Observation object containing the observation of the environment.
        """
        return Observation(
            weights=state.weights,
            values=state.values,
            packed_items=state.packed_items,
            action_mask=~state.packed_items & (state.weights <= state.remaining_budget),
        )

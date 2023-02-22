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

from typing import Any

import chex
import jax.numpy as jnp
import pytest

from jumanji.environments.routing.maze.env import Maze
from jumanji.environments.routing.maze.types import Observation


class TestObservationSpec:
    env = Maze(n_rows=5, n_cols=5)
    observation_spec = env.observation_spec()
    observation = observation_spec.generate_value()

    def test_observation_spec__generate_value(self) -> None:
        """Test generating a value which conforms to the observation spec."""
        assert isinstance(self.observation, Observation)

    def test_observation_spec__validate(self) -> None:
        """Test the validation of an observation given the observation spec."""
        observation = self.observation_spec.validate(self.observation)
        # Check that a different shape breaks the validation
        with pytest.raises(ValueError):
            modified_shape_observation = observation._replace(
                walls=observation.walls[None, ...]
            )
            self.observation_spec.validate(modified_shape_observation)
        # Check that a different dtype breaks the validation
        with pytest.raises(ValueError):
            modified_dtype_observation = observation._replace(
                walls=observation.walls.astype(jnp.float16)
            )
            self.observation_spec.validate(modified_dtype_observation)
        # Check that validating another object breaks the validation
        with pytest.raises(Exception):
            self.observation_spec.validate(None)  # type: ignore

    @pytest.mark.parametrize(
        "arg_name, new_value",
        [
            (
                "walls_spec",
                observation_spec.walls_spec.replace(shape=(6, 6)),
            ),
            (
                "agent_position_spec",
                observation_spec.agent_position_spec.row_spec.replace(name="new_name"),
            ),
            (
                "target_position_spec",
                observation_spec.target_position_spec.row_spec.replace(name="new_name"),
            ),
            ("step_count_spec", observation_spec.step_count_spec.replace(dtype=bool)),
            ("action_mask_spec", observation_spec.action_mask_spec.replace(shape=(5,))),
        ],
    )
    def test_observation_spec__replace(self, arg_name: str, new_value: Any) -> None:
        """For every attribute of `ObservationSpec`, check that we can create a new
        observation spec with a replaced attribute. Then check that the value of every
        other attribute remain equal.
        """
        old_spec = self.observation_spec
        new_spec = old_spec.replace(**{arg_name: new_value})
        assert new_spec != old_spec
        assert getattr(new_spec, arg_name) == new_value
        for attr_name in {
            "walls_spec",
            "agent_position_spec",
            "target_position_spec",
            "step_count_spec",
            "action_mask_spec",
        }.difference([arg_name]):
            chex.assert_equal(
                getattr(new_spec, attr_name), getattr(old_spec, attr_name)
            )

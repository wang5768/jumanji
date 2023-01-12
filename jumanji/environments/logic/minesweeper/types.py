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

from typing import TYPE_CHECKING

import chex
import jax.random
from chex import Array
from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from dataclasses import dataclass
else:
    from chex import dataclass

Board: TypeAlias = Array


@dataclass
class State:
    board: Board
    step_count: chex.Numeric
    flat_mine_locations: Array
    key: chex.PRNGKey = jax.random.PRNGKey(0)


@dataclass
class Observation:
    board: Board
    action_mask: Board
    num_mines: chex.Numeric
    step_count: chex.Numeric

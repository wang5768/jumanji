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

import chex
import jax.numpy as jnp
import jax.random
import py
import pytest

from jumanji.binpack.generator import (
    CSVInstanceGenerator,
    SimpleInstanceGenerator,
    save_instance_to_csv,
)
from jumanji.binpack.types import State
from jumanji.testing.pytrees import assert_trees_are_different, assert_trees_are_equal


def test_save_instance_to_csv(dummy_instance: State, tmpdir: py.path.local) -> None:
    """Validate the dummy instance is correctly saved to a csv file."""
    file_name = "/test.csv"
    save_instance_to_csv(dummy_instance, str(tmpdir.join(file_name)))
    lines = tmpdir.join(file_name).readlines()
    assert lines[0] == "Product_Name,Length,Width,Height,Quantity,Stackable\n"
    assert lines[1] == "shape_1,5870,2330,2200,1,1\n"


@pytest.fixture
def simple_instance_generator() -> SimpleInstanceGenerator:
    return SimpleInstanceGenerator()


def test_simple_instance_generator__properties(
    simple_instance_generator: SimpleInstanceGenerator,
) -> None:
    """Validate that the simple instance generator has the correct properties."""
    assert simple_instance_generator.max_num_items == 8
    assert simple_instance_generator.max_num_ems > 0


def test_simple_instance_generator__call(
    simple_instance_generator: SimpleInstanceGenerator,
) -> None:
    """Validate that the simple instance generator's call function behaves correctly, that it
    returns the same state for different keys. Also check that it is jittable and compiles only
    once.
    """
    chex.clear_trace_counter()
    call_fn = jax.jit(chex.assert_max_traces(simple_instance_generator.__call__, n=1))
    state1 = call_fn(jax.random.PRNGKey(1))
    state2 = call_fn(jax.random.PRNGKey(2))
    assert_trees_are_equal(state1, state2)


def test_simple_instance_generator__generate_solution(
    simple_instance_generator: SimpleInstanceGenerator,
) -> None:
    """Validate that the simple instance generator's generate solution method behaves correctly.
    Also check that it is jittable and compiles only once."""
    state1 = simple_instance_generator(jax.random.PRNGKey(1))

    chex.clear_trace_counter()
    generate_solution = jax.jit(
        chex.assert_max_traces(simple_instance_generator.generate_solution, n=1)
    )

    solution_state1 = generate_solution(jax.random.PRNGKey(1))
    assert isinstance(solution_state1, State)
    assert_trees_are_equal(solution_state1.ems, state1.ems)
    assert_trees_are_different(solution_state1.ems_mask, state1.ems_mask)
    assert_trees_are_equal(solution_state1.items, state1.items)
    assert_trees_are_equal(solution_state1.items_mask, state1.items_mask)
    assert_trees_are_different(solution_state1.items_placed, state1.items_placed)
    assert_trees_are_different(solution_state1.items_location, state1.items_location)
    assert jnp.all(solution_state1.items_placed)

    solution_state2 = generate_solution(jax.random.PRNGKey(2))
    assert_trees_are_equal(solution_state1, solution_state2)


@pytest.fixture
def csv_instance_generator(
    dummy_instance: State, tmpdir: py.path.local, max_num_ems: int = 1
) -> CSVInstanceGenerator:
    """Save a dummy instance to a csv file and then use this file to instantiate a
    CSVInstanceGenerator that generates the same dummy instance.
    """
    path = str(tmpdir.join("/for_generator.csv"))
    save_instance_to_csv(dummy_instance, path)
    return CSVInstanceGenerator(path, max_num_ems)


def test_csv_instance_generator__properties(
    csv_instance_generator: CSVInstanceGenerator,
) -> None:
    """Validate that the csv instance generator has the correct properties."""
    assert csv_instance_generator.max_num_items == 1
    assert csv_instance_generator.max_num_ems == 1


def test_csv_instance_generator__call(
    dummy_instance: State, csv_instance_generator: CSVInstanceGenerator
) -> None:
    """Validate that the csv instance generator's call function is jittable and compiles only once.
    Also check that the function is independent of the key."""
    chex.clear_trace_counter()
    call_fn = jax.jit(chex.assert_max_traces(csv_instance_generator.__call__, n=1))
    state1 = call_fn(key=jax.random.PRNGKey(1))
    assert isinstance(state1, State)
    assert_trees_are_equal(state1, dummy_instance)

    state2 = call_fn(key=jax.random.PRNGKey(2))
    assert_trees_are_equal(state1, state2)

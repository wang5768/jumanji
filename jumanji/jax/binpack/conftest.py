import functools

import jax
import jax.numpy as jnp
import pytest
from chex import PRNGKey

from jumanji.jax.binpack.env import BinPack
from jumanji.jax.binpack.generator import Generator
from jumanji.jax.binpack.specs import ObservationSpec
from jumanji.jax.binpack.types import EMS, Container, Item, Location, State


class DummyGenerator(Generator):
    """Dummy generator used for testing. It outputs a constant instance with a cubic container and
    one item whose size is the container itself.
    """

    def __init__(self) -> None:
        """Instantiate a dummy generator with one item and one ems maximum."""
        super(DummyGenerator, self).__init__(max_num_items=1, max_num_ems=1)

    def __call__(self, key: PRNGKey) -> State:
        """Returns a fixed instance with one item, one ems and a cubic container.

        Args:
            key: random key not used here but kept for consistency with parent signature.

        Returns:
            State.
        """
        del key
        return State(
            container=Container(x1=0, x2=1, y1=0, y2=1, z1=0, z2=1).astype(float),
            ems=jax.tree_map(
                functools.partial(jnp.expand_dims, axis=-1),
                EMS(x1=0, x2=1, y1=0, y2=1, z1=0, z2=1).astype(float),
            ),
            ems_mask=jnp.array([True], bool),
            items=jax.tree_map(
                functools.partial(jnp.asarray, dtype=float),
                Item(x_len=1, y_len=1, z_len=1),
            ),
            items_mask=jnp.array([True], bool),
            items_placed=jnp.array([False], bool),
            items_location=jax.tree_map(
                functools.partial(jnp.asarray, dtype=float), Location(x=0, y=0, z=0)
            ),
            action_mask=jnp.array([[True]], bool),
            sorted_ems_indexes=jnp.array([0], int),
        )


@pytest.fixture
def dummy_generator() -> DummyGenerator:
    return DummyGenerator()


@pytest.fixture
def binpack_env(dummy_generator: Generator) -> BinPack:
    return BinPack(generator=dummy_generator, obs_num_ems=1)


@pytest.fixture
def obs_spec(binpack_env: BinPack) -> ObservationSpec:
    return binpack_env.observation_spec()

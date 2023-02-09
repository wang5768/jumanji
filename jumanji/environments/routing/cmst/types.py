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

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:  # https://github.com/python/mypy/issues/6239
    from dataclasses import dataclass
else:
    from chex import dataclass

import chex
import jax.numpy as jnp


@dataclass
class State:
    """
    node_types: array with node types (-1 represents utility nodes).
    edges: array with all egdes in the graph.
    nodes_to_connect: array with node ids of the nodes to connect for each agent.
    connected_nodes: array of node indices denoting route (-1 --> not filled yet).
    position: array with agents current positions.
    position_index: array with current index position in connected_nodes.
    action_mask: array with current action mask for each agent.
    finished_agents: array indicating if an agent's nodes are fully connected.
    step_count: integer to keep track of the number of steps.
    key: state PRNGkey.
    """

    node_types: chex.Array  # (num_nodes,)
    edges: chex.Array  # (num_edges, 2)
    nodes_to_connect: chex.Array  # (num_agents, num_nodes_per_agent)
    connected_nodes: chex.Array  # (num_agents, step_limit)
    connected_nodes_index: chex.Array  # (num_agents, num_nodes)
    node_edges: chex.Array  # (num_agents, num_nodes, num_nodes)
    position: chex.Array  # (num_agents,)
    position_index: chex.Array  # (num_agents,)
    action_mask: chex.Array  # (num_agents, num_nodes)
    finished_agents: chex.Array  # (num_agents,)
    step_count: jnp.int32
    key: chex.PRNGKey


class Observation(NamedTuple):
    """
    node_types: array with node types
        If we have for example 12 nodes these correponds to
        the indices 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10,  11.
        Now consider we have 2 agents. Agent 0 wants to connect the nodes
        (0,1,9) and agent 1 the nodes (3,5,8). The remaining nodes are
        considered as utility nodes. So in the state view the node_types
        are [0, 0, -1, 1, -1, 1, 0, -1, 1, 0, -1, -1].
        When we generate the problem, each agent starts from one of its
        nodes. So if agent 0 starts on node 1 and agent 1 on node 3,
        the connected_nodes array will have values [1, -1, ...] and
        [3, -1, ...] respectively.

        Using the state view of the node_types and the connected nodes,
        we represent the agent's observation using the following rules.
        Each agent should see it nodes already connected on its path as 0,
        and nodes it still has to connect as 1. The next agent nodes will
        represented by 2 and 3, the next by 4 and 5 and so on. The utilitiy
        unconnected nodes will still be represented by -1

        In our 12 node example above we expect the observation view node_types
        to have the following values
            node_types = jnp.array(
                [
                    [ 1,  0, -1,  2, -1,  3,  1, -1,  3,  1, -1, -1],
                    [ 3,  2, -1,  0, -1,  1,  3, -1,  1,  3, -1, -1],
                ],
                dtype=jnp.int32,
            )
    edges: array with all edges in the graph.
        If we have a graph with 3 nodes with [0, 1, 3] and edges
        (0,1) and (1,3). The edges array will have values:
        egdes = jnp.array([[0,1], [1,3]]).

    positions: node on which the agent is currently located.
        In our current problem this will be jnp.array([1,3])

    action_masks: binary mask (True/False <--> valid/invalid action)
        Given the current node on which the agent is,
        do we have a valid edge to every other node.
    """

    node_types: chex.Array  # (num_agents, num_nodes)
    edges: chex.Array  # (num_agnets, num_edges, 2)
    position: chex.Array  # (num_agents,)
    action_mask: chex.Array  # (num_agents, num_nodes)

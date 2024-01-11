from enum import Enum, IntEnum, unique
from typing import NamedTuple, Sequence, Set

from .coordinate import Coord
from .coordinate import ReplicationId as RId
from .hw_defs import HwParams

__all__ = [
    "RoutingLevel",
    "RoutingDirection",
    "RoutingStatus",
    "RoutingCost",
    "ROUTING_DIRECTIONS_IDX",
    "RoutingCoord",
    "get_routing_consumption",
    "get_multicast_cores",
    "get_replication_id",
]


@unique
class RoutingLevel(IntEnum):
    L0 = 0
    """Leaves of tree to store the data. A L0-cluster is a physical core."""
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4
    L5 = 5


@unique
class RoutingDirection(Enum):
    """Indicate the 4 children of a cluster.

    NOTE: There is an X/Y coordinate priority method to specify the order.
    """

    X0Y0 = (0, 0)
    X0Y1 = (0, 1)
    X1Y0 = (1, 0)
    X1Y1 = (1, 1)
    ANY = (-1, -1)
    """Don't care when a level direction is `ANY`."""

    def to_index(self) -> int:
        """Convert the direction to index in children list."""
        if self is RoutingDirection.ANY:
            raise TypeError(f"The direction of routing is not specified.")

        x, y = self.value

        return (x << 1) + y


@unique
class RoutingStatus(IntEnum):
    """Indicate the status of L0-level cluster. Not used."""

    AVAILABLE = 0
    """Available for item to attach."""

    USED = 1
    """An item is attached to this cluster."""

    OCCUPIED = 2
    """Wasted. It will be an optimization goal."""

    ALL_EMPTY = 3
    """Not used."""


class RoutingCost(NamedTuple):
    n_L0: int
    n_L1: int
    n_L2: int
    n_L3: int
    n_L4: int

    def get_routing_level(self) -> RoutingLevel:
        """Return the routing cluster level.

        If the #N of Lx-level > 1, then we need a cluster with level Lx+1.
        And we need the #N of routing sub-level clusters.
        """
        for i in reversed(range(5)):
            if self[i] > 1:
                return RoutingLevel(i + 1)

        return RoutingLevel.L1


ROUTING_DIRECTIONS_IDX = (
    (
        RoutingDirection.X0Y0,
        RoutingDirection.X0Y1,
        RoutingDirection.X1Y0,
        RoutingDirection.X1Y1,
    )
    if HwParams.COORD_Y_PRIORITY
    else (
        RoutingDirection.X0Y0,
        RoutingDirection.X1Y0,
        RoutingDirection.X0Y1,
        RoutingDirection.X1Y1,
    )
)


class RoutingCoord(NamedTuple):
    """Use router directions to represent the coordinate of a cluster."""

    L4: RoutingDirection
    L3: RoutingDirection
    L2: RoutingDirection
    L1: RoutingDirection
    L0: RoutingDirection

    @property
    def level(self) -> RoutingLevel:
        for i in range(len(self)):
            if self[i] is RoutingDirection.ANY:
                return RoutingLevel(5 - i)

        return RoutingLevel.L0

    @property
    def coordinate(self) -> Coord:
        if self.level > RoutingLevel.L0:
            raise AttributeError("This property is only for L0-level cluster.")

        x = (
            (self.L4.value[0] << 4)
            + (self.L3.value[0] << 3)
            + (self.L2.value[0] << 2)
            + (self.L1.value[0] << 1)
            + self.L0.value[0]
        )

        y = (
            (self.L4.value[1] << 4)
            + (self.L3.value[1] << 3)
            + (self.L2.value[1] << 2)
            + (self.L1.value[1] << 1)
            + self.L0.value[1]
        )

        return Coord(x, y)


def get_routing_consumption(n_core: int) -> RoutingCost:
    """Get the consumption of clusters at different levels by given the `n_core`."""

    def n_L0_required(n_core: int) -> int:
        """Find the nearest #N(=2^X) to accommodate `n_core` L0-level clusters.

        If n_core = 5, return 8.
        If n_core = 20, return 32.
        """
        n_L0_nodes = 1
        while n_L0_nodes < n_core:
            n_L0_nodes <<= 1

        return n_L0_nodes

    n_sub_node = HwParams.N_SUB_ROUTING_NODE

    n_L0 = n_L0_required(n_core)
    n_L1 = 1 if n_L0 < n_sub_node else (n_L0 // n_sub_node)
    n_L2 = 1 if n_L1 < n_sub_node else (n_L1 // n_sub_node)
    n_L3 = 1 if n_L2 < n_sub_node else (n_L2 // n_sub_node)
    n_L4 = 1 if n_L3 < n_sub_node else (n_L3 // n_sub_node)

    return RoutingCost(n_L0, n_L1, n_L2, n_L3, n_L4)


def get_replication_id(coords: Sequence[Coord]) -> RId:
    """Get the replication ID by given the coordinates.

    Args:
        - coords: sequence of coordinates.
    """
    base_coord = coords[0]
    rid = RId(0, 0)

    for coord in coords[1:]:
        rid |= base_coord ^ coord

    return rid


def get_multicast_cores(base_coord: Coord, rid: RId) -> Set[Coord]:
    cores: Set[Coord] = set()
    corex = set()
    corey = set()
    temp = set()

    corex.add(base_coord.x)
    corey.add(base_coord.y)

    for lx in range(5):
        if (rid.x >> lx) & 1:
            for x in corex:
                temp.add(x ^ (1 << lx))

            corex = corex.union(temp)
            temp.clear()

        if (rid.y >> lx) & 1:
            for y in corey:
                temp.add(y ^ (1 << lx))

            corey = corey.union(temp)
            temp.clear()

    for x in corex:
        for y in corey:
            cores.add(Coord(x, y))

    return cores

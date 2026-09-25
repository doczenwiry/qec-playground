#   Copyright 2026 Seweryn Dynerowicz
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#          http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import itertools
from typing import Optional, Final, Callable

import logging

from library.circuitry import Circuitry
from library.common import Pauli
from library.qubit_array import QubitArray

logger = logging.getLogger(__name__)


class SurfaceCodePatch:
    MOMENTS: Final[range] = range(6)
    SCHEDULE = {
        "X": [(-0.5, -0.5), (+0.5, -0.5), (-0.5, +0.5), (+0.5, +0.5)],
        "Z": [(-0.5, -0.5), (-0.5, +0.5), (+0.5, -0.5), (+0.5, +0.5)],
    }

    def __init__(
        self,
        qubits: QubitArray,
        distance: int = 3,
        anchor: tuple[int, int] = (1, 1),
        coloring: bool = True,
    ):
        if not SurfaceCodePatch.fits(qubits, distance, anchor):
            raise ValueError("Proposed SurfaceCodePatch doesn't fit in the QubitArray.")

        self.__anchor = anchor
        self.__coloring = coloring
        self.__distance = distance
        self.__physical_qubits = qubits
        self.qubits: dict[str, dict[tuple[float, float], tuple[int, int]]] = dict()

        ax, ay = anchor
        data_qubits: dict[tuple[float, float], tuple[int, int]] = {
            location: (qubits[location], index)
            for index, location in enumerate(
                itertools.product(range(ax, ax + distance), range(ay, ay + distance))
            )
        }
        self.qubits["D"] = data_qubits

        ancilla_count = (distance**2 - 1) // 2
        width = 1 + (distance // 2)
        ancilla0: dict[tuple[float, float], tuple[int, int]] = dict()
        for q in range(ancilla_count):
            location = (
                ax + 0.5 + 2 * (q % width) - ((q // width) % 2),
                ay + 0.5 + (q // width),
            )
            ancilla0[location] = (qubits[location], len(ancilla0))
        width = distance // 2
        ancilla1: dict[tuple[float, float], tuple[int, int]] = dict()
        for q in range(ancilla_count):
            location = (
                ax + 0.5 + 2 * (q % width) + ((q // width) % 2),
                ay - 0.5 + (q // width),
            )
            ancilla1[location] = (qubits[location], len(ancilla1))

        self.qubits["X"] = ancilla1 if coloring else ancilla0
        self.qubits["Z"] = ancilla0 if coloring else ancilla1

    @staticmethod
    def fits(qubits: QubitArray, distance: int, anchor: tuple[int, int] = (1, 1)):
        ax, ay = anchor
        return (
            1 <= ax
            and 1 <= ay
            and ax + distance < qubits.dimX
            and ay + distance < qubits.dimY
        )

    @staticmethod
    def make_array(distance: int, counts: tuple[int, int] = (1,1)) -> QubitArray:
        if distance % 2 != 1:
            raise ValueError("Code distance must be odd.")

        count_h, count_v = counts

        return QubitArray(
            dimensions=(count_h * (distance + 1), count_v * (distance + 1))
        )

    @property
    def coloring(self):
        return self.__coloring

    @property
    def distance(self):
        return self.__distance

    @property
    def anchor(self):
        return self.__anchor

    @property
    def num_qubits(self):
        return sum(len(self.qubits[qt]) for qt in ["X", "Z", "D"])

    @property
    def num_z_ancilla(self):
        return len(self.qubits["Z"])

    @property
    def num_x_ancilla(self):
        return len(self.qubits["X"])

    def logical(self, basis: Pauli, offset: Optional[int] = None):
        if offset:
            if not (0 <= offset < self.distance):
                raise ValueError(f"Invalid index (0 <= {offset} < distance).")
        else:
            offset = 0

        ax, ay = self.anchor
        match basis:
            case Pauli.X:
                if self.__coloring:
                    return {
                        self.__physical_qubits.qubits[(ax+offset, ay + i)]: "X"
                        for i in range(self.__distance)
                    }
                else:
                    return {
                        self.__physical_qubits.qubits[(ax + i, ay+offset)]: "X"
                        for i in range(self.__distance)
                    }
            case Pauli.Y:
                logical = {}
                for index in range(self.__distance):
                    if index == offset:
                        logical[
                            self.__physical_qubits.qubits[(ax + offset, ay + offset)]
                        ] = "Y"
                    else:
                        logical[
                            self.__physical_qubits.qubits[(ax + offset, ay + index)]
                        ] = "X" if self.__coloring else "Z"
                        logical[
                            self.__physical_qubits.qubits[(ax + index, ay + offset)]
                        ] = "Z" if self.__coloring else "X"
                return logical
            case Pauli.Z:
                if self.__coloring:
                    return {
                        self.__physical_qubits.qubits[(ax + i, ay+offset)]: "Z"
                        for i in range(self.__distance)
                    }
                else:
                    return {
                        self.__physical_qubits.qubits[(ax+offset, ay + i)]: "Z"
                        for i in range(self.__distance)
                    }

    def __get_qubits(
        self,
        qtype: str,
        inactive: Callable[[tuple[float, float]], bool] = lambda _: False,
    ):
        return iter(
            (al, ai) for al, ai in self.qubits[qtype].items() if not inactive(al)
        )

    def get_qubit_index(self, qtype: str, qubit: int) -> int:
        for qb, qi in self.qubits[qtype].values():
            if qb == qubit:
                return qi
        return -1

    def get_qubit_at_location(self, location: tuple[float, float]) -> int:
        return self.qubits["D"][location][0] if location in self.qubits["D"] else -1

    def locate_qubit(self, label: str):
        index = int(label[1:])

        for lc, (_, i) in self.qubits[label[0]].items():
            if i == index:
                return lc

        raise ValueError("Invalid label provided [qubit index not found].")

    def __get_polygon(self, px, py):
        return [
            self.get_qubit_at_location((px + dx, py + dy))
            for dx, dy in [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)]
            if self.get_qubit_at_location((px + dx, py + dy)) != -1
        ]

    def get_polygons(
        self,
        inactive: Callable[[tuple[float, float]], bool] = lambda _: False,
        opacity: float = 0.5,
    ):
        polygons = []
        for stabilizer in ["X", "Z"]:
            for location, _ in self.__get_qubits(stabilizer, inactive):
                polygon = self.__get_polygon(*location)
                x, y, z = int(stabilizer == "X"), 0, int(stabilizer == "Z")
                polygons.append(
                    f"POLYGON({x},{y},{z},{opacity}) {' '.join(map(str, polygon))}"
                )
        return polygons

    def annotate_detectors(
        self,
        circuitry: Circuitry,
        prefix: str = "SC",
        rounds: Optional[int] = None,
        prepared: Optional[Pauli] = None,
        measured: Optional[Pauli] = None,
        inactive: Callable[[tuple[float, float]], bool] = lambda _ : False,
    ):
        last = (rounds or self.distance) - 1
        for stabilizer in ["X", "Z"]:
            for ql, (qa, qi) in self.qubits[stabilizer].items():
                if inactive(ql):
                    continue

                if prepared is not None and prepared.name == stabilizer:
                    circuitry.annotate_detector(f"{prefix}:R0:{stabilizer}{qi}")
                for prev, curr in itertools.pairwise(range(rounds or self.distance)):
                    circuitry.annotate_detector(
                        f"{prefix}:R{curr}:{stabilizer}{qi}",
                        f"{prefix}:R{prev}:{stabilizer}{qi}",
                    )
                if measured is not None and measured.name == stabilizer:
                    circuitry.annotate_detector(
                        f"{prefix}:R{last}:{stabilizer}{qi}",
                        *[ f"{prefix}:R{last}:D{self.get_qubit_index("D", qd)}"
                           for qd in self.__get_polygon(*ql)
                        ]
                    )

    def append_memory(
        self,
        circuit: Circuitry,
        prepare: Optional[Pauli] = None,
        measure: Optional[Pauli] = None,
        prefix: str = "",
    ):
        start = 0
        final = self.__distance - 1
        for rnd in range(self.__distance):
            self.append_round(
                circuit,
                prepare=prepare if (rnd == start) else None,
                measure=measure if (rnd == final) else None,
                prefix=f"{prefix}:R{rnd}",
            )

    def append_round(
        self,
        circuit: Circuitry,
        moment: Optional[int] = None,
        prepare: Optional[Pauli] = None,
        measure: Optional[Pauli] = None,
        inactive: Callable[[tuple[float, float]], bool] = lambda _: False,
        prefix: str = "",
    ):
        if moment is None:
            for mmt in SurfaceCodePatch.MOMENTS:
                self.append_round(circuit, mmt, prepare, measure, inactive, prefix)
                circuit.append_tick()
            return

        match moment:
            case 0:
                for stabilizer in ["X", "Z"]:
                    circuit.append(
                        f"R{stabilizer}",
                        [qa for _, (qa, _) in self.__get_qubits(stabilizer, inactive)],
                    )
                if prepare:
                    if prepare == Pauli.Y:
                        raise NotImplementedError("Y-basis preparation not supported.")
                    circuit.append(
                        f"R{prepare.name}",
                        [qd for _, (qd, _) in self.__get_qubits("D", inactive)],
                    )
            case 1 | 2 | 3 | 4:
                targets = []
                for stabilizer in ["X", "Z"]:
                    for (px, py), (qa, _) in self.__get_qubits(stabilizer, inactive):
                        dx, dy = SurfaceCodePatch.SCHEDULE[stabilizer][moment - 1]
                        qd = self.get_qubit_at_location((px + dx, py + dy))
                        if qd != -1:
                            if stabilizer == "Z":
                                targets.append(qd)
                                targets.append(qa)
                            else:
                                targets.append(qa)
                                targets.append(qd)
                circuit.append("CX", targets)
            case 5:
                for stabilizer in ["X", "Z"]:
                    measured = []
                    for ql, (qa, qi) in self.__get_qubits(stabilizer, inactive):
                        self.__physical_qubits.record_measurement(
                            qa, f"{prefix}:{stabilizer}{qi}"
                        )
                        measured.append(qa)
                    circuit.append(f"M{stabilizer}", measured)
                if measure:
                    measured_data = []
                    for dl, (dq, di) in self.__get_qubits("D", inactive):
                        self.__physical_qubits.record_measurement(dq, f"{prefix}:D{di}")
                        measured_data.append(dq)
                    circuit.append(f"M{measure.name}", measured_data)
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

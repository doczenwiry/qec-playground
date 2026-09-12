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
from enum import Enum
from typing import Optional, Final, Callable

import stim
import logging

from library.qubit_array import QubitArray

logger = logging.getLogger(__name__)

class PauliBasis(Enum):
    X = 0
    Y = 1
    Z = 2

class SurfaceCodePatch:
    MOMENTS: Final[range] = range(6)
    SCHEDULE_X = [ (-0.5, -0.5) , (+0.5, -0.5) , (-0.5, +0.5) , (+0.5, +0.5) ]
    SCHEDULE_Z = [ (-0.5, -0.5) , (-0.5, +0.5) , (+0.5, -0.5) , (+0.5, +0.5) ]

    def __init__(self, qubits: QubitArray, distance: int = 3, anchor: tuple[int,int] = (1, 1)):
        self.__anchor = anchor
        self.__distance = distance
        self.__physical_qubits = qubits
        ax, ay = anchor
        self.data_qubits: dict[tuple[float, float], int] = {
            location : qubits[location]
            for location in itertools.product(
                range(ax, ax + distance),
                range(ay, ay + distance)
            )
        }
        ancilla_count = (distance**2 - 1) // 2
        width = 1 + (distance // 2)
        self.z_ancilla: dict[tuple[float,float], int] = dict()
        for q in range(ancilla_count):
            location = (ax + 0.5 + 2 * (q % width) - ((q // width) % 2), ay + 0.5 + (q // width))
            self.z_ancilla[location] = qubits[location]
        width = distance // 2
        self.x_ancilla: dict[tuple[float,float], int] = dict()
        for q in range(ancilla_count):
            location = (ax + 0.5 + 2 * (q % width) + ((q // width) % 2), ay - 0.5 + (q // width))
            self.x_ancilla[location] = qubits[location]

    @property
    def distance(self):
        return self.__distance

    @property
    def anchor(self):
        return self.__anchor

    @property
    def num_qubits(self):
        return len(self.data_qubits) + len(self.z_ancilla) + len(self.x_ancilla)

    def __data_qubits(self, inactive: Callable[[tuple[float,float]], bool] = lambda _: False):
        return iter(
            (dl, dq) for dl, dq in self.data_qubits.items() if not inactive(dl)
        )

    def __z_ancilla(self, inactive: Callable[[tuple[float,float]], bool] = lambda _: False):
        return iter(
            (zl, za) for zl, za in self.z_ancilla.items() if not inactive(zl)
        )

    def __x_ancilla(self, inactive: Callable[[tuple[float,float]], bool] = lambda _: False):
        return iter(
            (xl, xa) for xl, xa in self.x_ancilla.items() if not inactive(xl)
        )

    def get_qubit_at_location(self, location: tuple[float, float]) -> int:
        return  self.data_qubits[location] if location in self.data_qubits  else -1

    def __get_polygon(self, px, py):
        return [
            self.get_qubit_at_location( (px+dx, py+dy) ) for dx, dy in
            [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)]
            if self.get_qubit_at_location( (px+dx, py+dy) ) != -1
        ]

    def get_polygons(self, inactive: Callable[[tuple[float,float]], bool] = lambda _: False):
        polygons = []
        for location, qubit in self.__z_ancilla(inactive):
            polygon = self.__get_polygon(*location)
            polygons.append(f"#!pragma POLYGON(0,0,1,0.5) {" ".join(map(str, polygon))}\n")
        for location, qubit in self.__x_ancilla(inactive):
            polygon = self.__get_polygon(*location)
            polygons.append(f"#!pragma POLYGON(1,0,0,0.5) {" ".join(map(str, polygon))}\n")
        return polygons

    def append_memory(
            self, circuit: stim.Circuit, prepare: Optional[PauliBasis] = None, measure: Optional[PauliBasis] = None
    ):
        start = 0
        final = self.__distance - 1
        for rnd in range(self.__distance):
            self.append_round(
                circuit,
                prepare = prepare if (rnd == start) else None,
                measure = measure if (rnd == final) else None
            )

    def append_round(
        self, circuit: stim.Circuit, prepare: Optional[PauliBasis] = None, measure: Optional[PauliBasis] = None,
        inactive: Callable[[tuple[float,float]], bool] = lambda _: False
    ):
        for mmt in SurfaceCodePatch.MOMENTS:
            self.append_round_slice(circuit, mmt, prepare, measure, inactive)
            circuit.append("TICK")

    def append_round_slice(
        self, circuit: stim.Circuit, moment: int, prepare: Optional[PauliBasis] = None, measure: Optional[PauliBasis] = None,
        inactive: Callable[[tuple[float,float]], bool] = lambda _: False
    ):
        match moment:
            case 0:
                circuit.append("RX", [za for _, za in self.__z_ancilla(inactive)])
                circuit.append("RX", [xa for _, xa in self.__x_ancilla(inactive)])
                if prepare:
                    circuit.append(f"R{prepare.name}", [qd for _, qd in self.__data_qubits(inactive)])
            case 1 | 2 | 3 | 4:
                for gate, ancilla, schedule in [
                    ("CZ", self.__z_ancilla(inactive), SurfaceCodePatch.SCHEDULE_Z),
                    ("CX", self.__x_ancilla(inactive), SurfaceCodePatch.SCHEDULE_X)
                ]:
                    gates = []
                    for (px,py), qa in ancilla:
                        dx, dy = schedule[moment - 1]
                        target = self.get_qubit_at_location( (px+dx, py+dy) )
                        if target != -1:
                            gates.append(qa)
                            gates.append(target)
                    circuit.append(gate, gates)
            case 5:
                circuit.append("MX", [za for _, za in self.__z_ancilla(inactive)])
                circuit.append("MX", [xa for _, xa in self.__x_ancilla(inactive)])
                if measure:
                    circuit.append(f"M{measure.name}", [qd for _, qd in self.__data_qubits(inactive)])
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")
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

import logging

import itertools
from typing import Final

import stim

from library.qubit_array import QubitArray
from library.surface_code.patch import SurfaceCodePatch

logger = logging.getLogger(__name__)

class ExpandingSurfaceCodePatch:
    MOMENTS: Final[range] = range(6)
    CORNERS: Final[list[tuple[float,float]]] = [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)]

    def __init__(self, array: QubitArray, distance: int, anchor: tuple[int, int] = (1, 1), expansion: int = 0):
        self.__anchor = anchor
        self.__distance = distance
        self.__expansion = expansion
        expanded = distance + expansion
        self.__expanded = expanded
        self.__physical_qubits = array
        print(f"Distance {self.__distance} + Expansion {self.__expansion}")
        ax, ay = anchor
        self.data_qubits: dict[int, tuple[float, float]] = {
            array.qubits[location] : location
            for index, location in enumerate(itertools.product(
                range(ax, ax + expanded),
                range(ay, ay + expanded),
            ))
        }

        ancilla_count = (expanded**2 - 1) // 2
        width = (expanded // 2) + 1
        self.z_ancilla: dict[int, tuple[float,float]] = dict()
        for q in range(ancilla_count):
            location = (ax + 0.5 + 2 * (q % width) - ((q // width) % 2), ay + 0.5 + (q // width))
            self.z_ancilla[array.qubits[location]] = location
        width = expanded // 2
        self.x_ancilla: dict[int, tuple[float,float]] = dict()
        for q in range(ancilla_count):
            location = (ax + 0.5 + 2 * (q % width) + ((q // width) % 2), ay - 0.5 + (q // width))
            self.x_ancilla[array.qubits[location]] = location

    @property
    def num_qubits(self):
        return len(self.data_qubits) + len(self.z_ancilla) + len(self.x_ancilla)

    def active_data_qubits(self, expansion: bool = False):
        return iter(dq for dq in self.data_qubits if self.is_qubit_active(dq, expansion))

    def active_x_ancilla(self, expansion: bool = False):
        return iter(xq for xq in self.x_ancilla if self.is_qubit_active(xq, expansion))

    def active_z_ancilla(self, expansion: bool = False):
        return iter(zq for zq in self.z_ancilla if self.is_qubit_active(zq, expansion))

    def is_qubit_active(self, qubit: int, expanded: bool) -> bool:
        ax, ay = self.__anchor

        lower_x = ax + (0 if expanded else self.__expansion)
        lower_y = ay + (0 if expanded else self.__expansion)

        upper_x = ax + self.__expanded + 0.5
        upper_y = ay + self.__expanded + 0.5

        if qubit in self.data_qubits:
            px, py = self.data_qubits[qubit]
            return lower_x - 0.5 <= px <= upper_x and lower_y - 0.5 <= py <= upper_y
        elif qubit in self.z_ancilla:
            px, py = self.z_ancilla[qubit]
            return lower_x - 0.5 <= px <= upper_x and lower_y + 0.5 <= py <= upper_y
        elif qubit in self.x_ancilla:
            px, py = self.x_ancilla[qubit]
            return lower_x + 0.5 <= px <= upper_x and lower_y - 0.5 <= py <= upper_y

        return False

    def qubit_in_expansion(self, qubit: int) -> bool:
        ax, ay = self.__anchor
        px, py = self.data_qubits[qubit]
        return not(ax + self.__expansion <= px and ay + self.__expansion <= py)

    def __get_polygon(self, px, py, expanded: bool = False):
        return [
            self.__physical_qubits.qubits[px + dx, py + dy] for dx, dy in ExpandingSurfaceCodePatch.CORNERS
            if self.is_qubit_active(self.__physical_qubits.qubits[px + dx, py + dy], expanded)
        ]

    def get_polygons(self, expanded: bool = False):
        polygons = []
        for px, py in iter(zl for zq, zl in self.z_ancilla.items() if self.is_qubit_active(zq, expanded)):
            polygon = self.__get_polygon(px, py, expanded)
            polygons.append(f"#!pragma POLYGON(0,0,1,0.5) {" ".join(map(str, polygon))}\n")
        for px, py in iter(xl for xq, xl in self.x_ancilla.items() if self.is_qubit_active(xq, expanded)):
            polygon = self.__get_polygon(px, py, expanded)
            polygons.append(f"#!pragma POLYGON(1,0,0,0.5) {" ".join(map(str, polygon))}\n")
        return polygons

    def append_syndrome_slice(
        self, circuit: stim.Circuit, moment: int, preparation: bool = False, expanded: bool = False
    ):
        match moment:
            case 0:
                circuit.append("RZ", self.active_z_ancilla(expanded))
                circuit.append("RX", self.active_x_ancilla(expanded))
                if preparation:
                    if not expanded:
                        circuit.append("RX", self.active_data_qubits(expanded))
                    else:
                        ax, ay = self.__anchor
                        active_qubits = [
                            dq for dq in self.active_data_qubits(expanded) if self.qubit_in_expansion(dq)
                        ]
                        rx_targets = filter(
                            lambda dq : self.data_qubits[dq][0] - ax >= self.data_qubits[dq][1] - ay, active_qubits
                        )
                        circuit.append("RX", rx_targets)
                        rz_targets = filter(
                            lambda dq : self.data_qubits[dq][0] - ax < self.data_qubits[dq][1] - ay, active_qubits
                        )
                        circuit.append("RZ", rz_targets)
            case 1 | 2 | 3 | 4:
                targets = []
                for za in self.active_z_ancilla(expanded):
                    px, py = self.z_ancilla[za]
                    dx, dy = SurfaceCodePatch.SCHEDULE_Z[moment - 1]
                    data_qubit = self.__physical_qubits.qubits[px + dx, py + dy]
                    if self.is_qubit_active(data_qubit, expanded):
                        targets.append(data_qubit)
                        targets.append(za)
                for xa in self.active_x_ancilla(expanded):
                    px, py = self.x_ancilla[xa]
                    dx, dy = SurfaceCodePatch.SCHEDULE_X[moment - 1]
                    data_qubit = self.__physical_qubits.qubits[px + dx, py + dy]
                    if self.is_qubit_active(data_qubit, expanded):
                        targets.append(xa)
                        targets.append(data_qubit)
                circuit.append("CX", targets)
                # for gate, active, ancilla, schedule in [
                #     ("CZ", self.active_z_ancilla(expanded), self.z_ancilla, SurfaceCodePatch.SCHEDULE_Z),
                #     ("CX", self.active_x_ancilla(expanded), self.x_ancilla, SurfaceCodePatch.SCHEDULE_X)
                # ]:
                #     gates = []
                #     for za in active:
                #         px, py = ancilla[za]
                #         dx, dy = schedule[moment - 1]
                #         target = self.get_qubit_at_location(px + dx, py + dy, expanded=expanded)
                #         if target != -1:
                #             gates.append(za)
                #             gates.append(target)
                #     circuit.append(gate, gates)
            case 5:
                circuit.append("MX", self.active_z_ancilla(expanded))
                circuit.append("MX", self.active_x_ancilla(expanded))
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")
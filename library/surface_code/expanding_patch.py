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
        self.__qubits = dict()

        ax, ay = anchor
        data_qubits: dict[int, tuple[float, float]] = {
            array.qubits[location] : (location, index)
            for index, location in enumerate(itertools.product(
                range(ax, ax + expanded),
                range(ay, ay + expanded),
            ))
        }
        self.__qubits['D'] = data_qubits

        ancilla_count = (expanded**2 - 1) // 2

        z_ancilla: dict[int, tuple[tuple[float,float], int]] = dict()
        width = (expanded // 2) + 1
        for qi in range(ancilla_count):
            location = (ax + 0.5 + 2 * (qi % width) - ((qi // width) % 2), ay + 0.5 + (qi // width))
            z_ancilla[array.qubits[location]] = (location, qi)
        self.__qubits['Z'] = z_ancilla

        x_ancilla: dict[int, tuple[tuple[float,float], int]] = dict()
        width = expanded // 2
        for qi in range(ancilla_count):
            location = (ax + 0.5 + 2 * (qi % width) + ((qi // width) % 2), ay - 0.5 + (qi // width))
            x_ancilla[array.qubits[location]] = (location, qi)
        self.__qubits['X'] = x_ancilla

    @property
    def num_qubits(self):
        return sum(len(self.__qubits[qtype]) for qtype in ['X', 'Z', 'D'])

    def active_qubits(self, qtype: str, expanded: bool = False):
        return iter(dq for dq in self.__qubits[qtype] if self.is_qubit_active(dq, expanded))

    def is_qubit_active(self, qubit: int, expanded: bool) -> bool:
        ax, ay = self.__anchor

        lower_x = ax + (0 if expanded else self.__expansion)
        lower_y = ay + (0 if expanded else self.__expansion)

        upper_x = ax + self.__expanded + 0.5
        upper_y = ay + self.__expanded + 0.5

        if qubit in self.__qubits['D']:
            (px, py), _ = self.__qubits['D'][qubit]
            return lower_x - 0.5 <= px <= upper_x and lower_y - 0.5 <= py <= upper_y
        elif qubit in self.__qubits['Z']:
            (px, py), _ = self.__qubits['Z'][qubit]
            return lower_x - 0.5 <= px <= upper_x and lower_y + 0.5 <= py <= upper_y
        elif qubit in self.__qubits['X']:
            (px, py), _ = self.__qubits['X'][qubit]
            return lower_x + 0.5 <= px <= upper_x and lower_y - 0.5 <= py <= upper_y

        return False

    def qubit_in_expansion(self, qubit: int) -> bool:
        ax, ay = self.__anchor
        (px, py), _ = self.__qubits['D'][qubit]
        return not(ax + self.__expansion <= px and ay + self.__expansion <= py)

    def __get_polygon(self, px, py, expanded: bool = False):
        return [
            self.__physical_qubits.qubits[px + dx, py + dy] for dx, dy in ExpandingSurfaceCodePatch.CORNERS
            if self.is_qubit_active(self.__physical_qubits.qubits[px + dx, py + dy], expanded)
        ]

    def get_polygons(self, expanded: bool = False, opacity: float = 0.5):
        polygons = []
        for stabilizer in ['X', 'Z']:
            for (px, py), _ in iter(zl for zq, zl in self.__qubits[stabilizer].items() if self.is_qubit_active(zq, expanded)):
                polygon = self.__get_polygon(px, py, expanded)
                x, y, z = int(stabilizer == 'X'), 0, int(stabilizer == 'Z')
                polygons.append(f"#!pragma POLYGON({x},{y},{z},{opacity}) {" ".join(map(str, polygon))}\n")
        return polygons

    def append_expansion_slice(
        self, circuit: stim.Circuit, moment: int, prefix: str = ""
    ):
        match moment:
            case 0:
                for stabilizer in ['X', 'Z']:
                    circuit.append(f"R{stabilizer}", self.active_qubits(stabilizer, True))
                rx_targets = []
                rz_targets = []
                ax, ay = self.__anchor
                for dq in filter(self.qubit_in_expansion, self.active_qubits('D', True)):
                    (px, py), _ = self.__qubits['D'][dq]
                    if px - ax >= py - ay:
                        rx_targets.append(dq)
                    else:
                        rz_targets.append(dq)
                circuit.append("RX", rx_targets)
                circuit.append("RZ", rz_targets)
            case 1 | 2 | 3 | 4:
                targets = []
                for atype in ['X', 'Z']:
                    for qa in self.active_qubits(atype, True):
                        (px, py), _ = self.__qubits[atype][qa]
                        dx, dy = SurfaceCodePatch.SCHEDULE[atype][moment - 1]
                        qd = self.__physical_qubits.qubits[px + dx, py + dy]
                        if self.is_qubit_active(qd, True):
                            if atype == 'X':
                                targets.append(qa)
                                targets.append(qd)
                            else: # atype == 'Z'
                                targets.append(qd)
                                targets.append(qa)
                circuit.append("CX", targets)
            case 5:
                for stabilizer in ['X', 'Z']:
                    measured = []
                    for qa in self.active_qubits(stabilizer, True):
                        _, qi = self.__qubits[stabilizer][qa]
                        self.__physical_qubits.record_measurement(qa, f"{prefix}:{stabilizer}{qi}")
                        measured.append(qa)
                    circuit.append(f"M{stabilizer}", measured)
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")
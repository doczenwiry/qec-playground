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
import stim

import logging
logger = logging.getLogger(__name__)

class SurfaceCodePatch:
    SCHEDULE_X = [ (-0.5, -0.5) , (+0.5, -0.5) , (-0.5, +0.5) , (+0.5, +0.5) ]
    SCHEDULE_Z = [ (-0.5, -0.5) , (-0.5, +0.5) , (+0.5, -0.5) , (+0.5, +0.5) ]

    def __init__(self, distance: int, base_qubit: int = 0, anchor: tuple[int, int] = (2, 4), expansion: int = 0):
        self.anchor = anchor
        self.base_qubit = base_qubit
        self.distance = distance
        self.expansion = expansion
        px, py = anchor
        expanded = distance + expansion
        self.qubits = {
            base_qubit + q : (px + (q % expanded),py + (q // expanded)) for q in range(expanded**2)
        }
        ancilla_count = (expanded**2 - 1) // 2
        width = 3 + (expansion // 2)
        self.z_ancilla = {
            base_qubit + len(self.qubits) + q : (px + 0.5 + 2 * (q % width) - ((q // width) % 2), py + 0.5 + (q // width))
            for q in range(ancilla_count)
        }
        width = 2 + (expansion // 2)
        self.x_ancilla = {
            base_qubit + len(self.qubits) + len(self.z_ancilla) + q : (px + 0.5 + 2 * (q % width) + ((q // width) % 2), py - 0.5 + (q // width))
            for q in range(ancilla_count)
        }

    @property
    def moments(self):
        return 6

    @property
    def instructions(self):
        return 4

    @property
    def num_qubits(self):
        return len(self.qubits) + len(self.z_ancilla) + len(self.x_ancilla)

    def active_data_qubits(self, expansion: bool = False):
        return filter(lambda q : self.is_qubit_active(q, expansion), self.qubits)

    def active_x_ancilla(self, expansion: bool = False):
        return filter(lambda q : self.is_qubit_active(q, expansion), self.x_ancilla)

    def active_z_ancilla(self, expansion: bool = False):
        return filter(lambda q: self.is_qubit_active(q, expansion), self.z_ancilla)

    def is_qubit_active(self, q: int, expansion: bool) -> bool:
        if expansion:
            return True

        ax, ay = self.anchor

        if q in self.qubits:
            px, py = self.qubits[q]
            return px <= ax + self.distance - 1 and py <= ay + self.distance - 1
        elif q in self.z_ancilla:
            px, py = self.z_ancilla[q]
            return px < ax + self.distance and py <= ay + self.distance - 1
        elif q in self.x_ancilla:
            px, py = self.x_ancilla[q]
            return (expansion or py != self.anchor[1] - 0.5) and px <= ax + self.distance - 1 and py < ay + self.distance

        return False

    def is_qubit_expansion(self, q: int) -> bool:
        ax, ay = self.anchor
        if q in self.qubits:
            px, py = self.qubits[q]
            return ax + self.distance - 1 < px or ay + self.distance -1 < py
        return False

    def get_qubit_at_location(self, px, py, expanded: bool = False):
        for qubit, (x, y) in self.qubits.items():
            if x == px and y == py and self.is_qubit_active(qubit, expanded):
                return qubit
        return -1

    def __get_polygon(self, px, py, expansion: bool = False):
        return [
            self.get_qubit_at_location(px + dx, py + dy, expansion) for dx, dy in
            [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)]
            if self.get_qubit_at_location(px + dx, py + dy, expansion) != -1
        ]

    def get_polygons(self, expansion: bool = False):
        polygons = []
        for qubit in self.active_z_ancilla(expansion):
            px, py = self.z_ancilla[qubit]
            polygon = self.__get_polygon(px, py, expansion)
            polygons.append(f"#!pragma POLYGON(0,0,1,0.5) {" ".join(map(str, polygon))}\n")
        for qubit in self.active_x_ancilla(expansion):
            px, py = self.x_ancilla[qubit]
            if not expansion and py == self.anchor[1] - 0.5:
                continue
            polygon = self.__get_polygon(px, py, expansion)
            polygons.append(f"#!pragma POLYGON(1,0,0,0.5) {" ".join(map(str, polygon))}\n")
        return polygons

    def append_metadata(self, circuit: stim.Circuit):
        for qubit, location in self.qubits.items():
            circuit.append("QUBIT_COORDS", [qubit], location)
        for qubit, location in self.z_ancilla.items():
            circuit.append("QUBIT_COORDS", [qubit], location)
        for qubit, location in self.x_ancilla.items():
            circuit.append("QUBIT_COORDS", [qubit], location)

    def append_syndrome_slice(
        self, circuit: stim.Circuit, moment: int, preparation: bool = False, expansion: bool = False
    ):
        match moment:
            case 0:
                if preparation:
                    if not expansion:
                        circuit.append("RX", self.active_data_qubits(expansion))
                    else:
                        ax, ay = self.anchor
                        rx_targets = [
                            q for q in self.active_data_qubits(expansion)
                            if self.is_qubit_expansion(q) and self.qubits[q][0] - ax <= self.qubits[q][1] - ay
                        ]
                        circuit.append("RX", rx_targets)
                        rz_targets = [
                            q for q in self.active_data_qubits(expansion)
                            if self.is_qubit_expansion(q) and self.qubits[q][0] - ax > self.qubits[q][1] - ay
                        ]
                        circuit.append("RZ", rz_targets)
                circuit.append("RX", self.active_z_ancilla(expansion))
                circuit.append("RX", self.active_x_ancilla(expansion))
            case 1 | 2 | 3 | 4:
                for gate, active, ancilla, schedule in [
                    ("CZ", self.active_z_ancilla(expansion), self.z_ancilla, SurfaceCodePatch.SCHEDULE_Z),
                    ("CX", self.active_x_ancilla(expansion), self.x_ancilla, SurfaceCodePatch.SCHEDULE_X)
                ]:
                    gates = []
                    for za in active:
                        px, py = ancilla[za]
                        dx, dy = schedule[moment - 1]
                        target = self.get_qubit_at_location(px + dx, py + dy, expanded=expansion)
                        if target != -1:
                            gates.append(za)
                            gates.append(target)
                    circuit.append(gate, gates)
            case 5:
                circuit.append("MX", self.active_z_ancilla(expansion))
                circuit.append("MX", self.active_x_ancilla(expansion))
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")
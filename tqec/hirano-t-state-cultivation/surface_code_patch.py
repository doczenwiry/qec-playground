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

import stim

import logging
logger = logging.getLogger(__name__)

class SurfaceCodePatch:
    SCHEDULE_X = [ (-0.5, -0.5) , (+0.5, -0.5) , (-0.5, +0.5) , (+0.5, +0.5) ]
    SCHEDULE_Z = [ (-0.5, -0.5) , (-0.5, +0.5) , (+0.5, -0.5) , (+0.5, +0.5) ]

    def __init__(self, distance: int, base_qubit: int = 0, anchor: tuple[int, int] = (2, 4)):
        self.distance = distance
        self.base_qubit = base_qubit
        self.anchor = anchor
        px, py = anchor
        self.qubits = {
            base_qubit + q : (px + (q % distance),py + (q // distance)) for q in range(self.distance**2)
        }
        ancilla_count = (self.distance**2 - 1) // 2
        self.z_ancilla = {
            base_qubit + len(self.qubits) + q : (px + 0.5 + 2 * (q % 3) - ((q // 3) % 2), py + 0.5 + (q // 3))
            for q in range(ancilla_count)
        }
        self.x_ancilla = {
            base_qubit + len(self.qubits) + len(self.z_ancilla) + q : (px + 0.5 + 2 * (q % 2) + ((q // 2) % 2), py - 0.5 + (q // 2))
            for q in range(ancilla_count)
        }

    @property
    def moments(self):
        return 1

    @property
    def num_qubits(self):
        return len(self.qubits) + len(self.z_ancilla) + len(self.x_ancilla)

    def get_qubit_at_location(self, px, py):
        for qubit, (x, y) in self.qubits.items():
            if x == px and y == py:
                return qubit
        return -1

    def __get_polygon(self, px, py):
        return [
            self.get_qubit_at_location(px + dx, py + dy) for dx, dy in
            [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)]
            if self.get_qubit_at_location(px + dx, py + dy) != -1
        ]

    def get_polygons(self, recovered: bool = False):
        polygons = []
        for qubit, (px, py) in self.z_ancilla.items():
            polygon = self.__get_polygon(px, py)
            polygons.append(f"#!pragma POLYGON(0,0,1,0.5) {" ".join(map(str, polygon))}\n")
        for qubit, (px, py) in self.x_ancilla.items():
            if not recovered and py == self.anchor[1] - 0.5:
                continue
            polygon = self.__get_polygon(px, py)
            polygons.append(f"#!pragma POLYGON(1,0,0,0.5) {" ".join(map(str, polygon))}\n")
        return polygons

    def append_metadata(self, circuit: stim.Circuit):
        for qubit, location in self.qubits.items():
            circuit.append("QUBIT_COORDS", [qubit], location)
        for qubit, location in self.z_ancilla.items():
            circuit.append("QUBIT_COORDS", [qubit], location)
        for qubit, location in self.x_ancilla.items():
            circuit.append("QUBIT_COORDS", [qubit], location)

    def append_syndrome_slice(self, circuit: stim.Circuit, moment: int, preparation: bool = False, recovered: bool = False):
        active_x_ancilla = filter(
            lambda a: recovered or self.x_ancilla[a][1] != self.anchor[1] - 0.5,
            self.x_ancilla.keys()
        )
        match moment:
            case 0:
                if preparation:
                    circuit.append("RX", self.qubits.keys())
                circuit.append("RX", self.z_ancilla.keys())
                circuit.append("RX", active_x_ancilla)
            case 1 | 3 | 5 | 7:
                cz_gates = []
                for za, (px,py) in self.z_ancilla.items():
                    dx, dy = SurfaceCodePatch.SCHEDULE_Z[(moment-1) // 2]
                    target = self.get_qubit_at_location(px + dx, py + dy)
                    if target != -1:
                        cz_gates.append(za)
                        cz_gates.append(target)
                circuit.append("CZ", cz_gates)
                cx_gates = []
                for xa in active_x_ancilla:
                    px, py = self.x_ancilla[xa]
                    dx, dy = SurfaceCodePatch.SCHEDULE_X[(moment-1) // 2]
                    target = self.get_qubit_at_location(px + dx, py + dy)
                    if target != -1:
                        cx_gates.append(xa)
                        cx_gates.append(target)
                circuit.append("CX", cx_gates)
            case 9:
                circuit.append("MX", self.z_ancilla.keys())
                circuit.append("MX", active_x_ancilla)
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")
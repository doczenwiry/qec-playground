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
from library.steane_code_patch import SteaneCodePatch
from library.expanding_surface_code_patch import SurfaceCodePatch

import logging
logger = logging.getLogger(__name__)

class JunctionPatch:
    QUBITS = [ (0.5, 0.5), (2.5, 0.5), (4.5, 0.5) ]
    STABILIZERS = [
        [ (-0.5, -0.5) , (+0.5, +0.5) ],
        [ (-0.5, -0.5) , (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5) ],
        [ (-0.5, +0.5) , (+0.5, +0.5) ]
    ]

    def __init__(self, base_qubit: int = 0, anchor: tuple[int, int] = (1, 3)):
        self.steane = None
        self.surface = None
        self.base_qubit = base_qubit
        self.anchor = anchor
        px, py = anchor
        self.z_ancilla = {
            self.base_qubit + q : (px + dx, py + dy) for q, (dx, dy) in enumerate(JunctionPatch.QUBITS)
        }

    @property
    def num_qubits(self):
        return len(self.z_ancilla)

    @property
    def moments(self):
        return range(6)

    def __get_qubit_at_location(
        self, px: float, py: float,
    ):
        qubit = self.steane.get_qubit_at_location(px, py)
        if qubit != -1:
            return qubit
        return self.surface.get_qubit_at_location(px, py)

    def get_polygons(self):
        polygons = []
        for q, stabilizer in enumerate(JunctionPatch.STABILIZERS):
            px, py = self.z_ancilla[self.base_qubit + q]
            polygon = map(
                lambda d: self.__get_qubit_at_location(px + d[0], py + d[1]),
                stabilizer
            )
            polygons.append(f"#!pragma POLYGON(0,0,1,0.5) {" ".join(map(str, polygon))}\n")
        return polygons

    def attach(self, steane: SteaneCodePatch, surface: SurfaceCodePatch):
        self.steane = steane
        self.surface = surface

    def append_metadata(self, circuit: stim.Circuit):
        for qubit, location in self.z_ancilla.items():
            circuit.append("QUBIT_COORDS", [qubit], location)

    def append_syndrome_slice(self, circuit: stim.Circuit, moment: int):
        match moment:
            case 0:
                circuit.append("RX", self.z_ancilla.keys())
            case 1 | 2 | 3 | 4:
                cz_gates = []
                for za, (px,py) in self.z_ancilla.items():
                    dx, dy = SurfaceCodePatch.SCHEDULE_Z[moment-1]
                    if za == self.base_qubit and dx == +0.5 and dy == -0.5:
                        continue
                    target = self.__get_qubit_at_location(px + dx, py + dy)
                    if target != -1:
                        cz_gates.append(za)
                        cz_gates.append(target)
                circuit.append("CZ", cz_gates)
            case 5:
                circuit.append("MX", self.z_ancilla.keys())
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")
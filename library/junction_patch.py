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

from library.circuitry import Circuitry
from library.surface_code.patch import SurfaceCodePatch
from library.qubit_array import QubitArray

import logging

logger = logging.getLogger(__name__)


class JunctionPatch:
    MOMENTS = range(6)

    QUBITS = [(0.5, 0.5), (2.5, 0.5), (4.5, 0.5)]
    STABILIZERS = [
        [(-0.5, -0.5), (+0.5, +0.5)],
        [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)],
        [(-0.5, +0.5), (+0.5, +0.5)],
    ]

    def __init__(self, array: QubitArray, anchor: tuple[int, int] = (1, 3)):
        self.__physical_qubits = array
        self.__anchor = anchor
        px, py = anchor
        self.z_ancilla: dict[tuple[float, float], int] = dict()
        for dx, dy in JunctionPatch.QUBITS:
            location = (px + dx, py + dy)
            self.z_ancilla[location] = array.qubits[location]

    @property
    def num_qubits(self):
        return len(self.z_ancilla)

    def get_polygons(self):
        polygons = []
        for (px, py), stabilizer in zip(
            self.z_ancilla.keys(), JunctionPatch.STABILIZERS
        ):
            polygon = map(
                lambda d: self.__physical_qubits.qubits[(px + d[0], py + d[1])],
                stabilizer,
            )
            polygons.append(f"POLYGON(0,0,1,0.5) {' '.join(map(str, polygon))}")
        return polygons

    def annotate_detectors(self, circuitry: Circuitry, rounds: int):
        for zi, (prev, curr) in itertools.product(
            range(3), itertools.pairwise(range(rounds))
        ):
            circuitry.annotate_detector(f"JCT{curr}:Z{zi}", f"JCT{prev}:Z{zi}")

    def append_syndrome(self, circuit: Circuitry, moment: int, prefix: str = ""):
        match moment:
            case 0:
                circuit.append("RZ", self.z_ancilla.values())
            case 1 | 2 | 3 | 4:
                cx_targets = []
                for zi, ((px, py), za) in enumerate(self.z_ancilla.items()):
                    interaction = SurfaceCodePatch.SCHEDULE["Z"][moment - 1]
                    if interaction not in JunctionPatch.STABILIZERS[zi]:
                        continue
                    dx, dy = interaction
                    qd = self.__physical_qubits.qubits[px + dx, py + dy]
                    cx_targets.append(qd)
                    cx_targets.append(za)
                circuit.append("CX", cx_targets)
            case 5:
                circuit.append("MZ", self.z_ancilla.values())
                for qi, qz in enumerate(self.z_ancilla.values()):
                    self.__physical_qubits.record_measurement(qz, f"{prefix}:Z{qi}")
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

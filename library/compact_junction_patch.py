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

from library.circuitry import Circuitry, DetectorTag
from library.surface_code.patch import SurfaceCodePatch
from library.qubit_array import QubitArray

import logging

logger = logging.getLogger(__name__)


class JunctionPatch:
    MOMENTS = range(6)

    QUBITS = {"X": [(1.5, 0.5)], "Z": [(0.5, 0.5), (2.5, 0.5), (4.5, 0.5)]}
    STABILIZERS = {
        "X": [
            [(-0.5, +0.5), (+0.5, +0.5)],
        ],
        "Z": [
            [(-0.5, -0.5), (+0.5, +0.5)],
            [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)],
            [(-0.5, +0.5), (+0.5, +0.5)],
        ],
    }

    LEFT_STABILIZER_SCHEDULE = [(-0.5, -0.5), (+0.5, +0.5), None, None]
    RECOVERED_STABILIZER_SCHEDULE = [None, None, (-0.5, +0.5), (+0.5, +0.5)]

    def __init__(self, array: QubitArray, anchor: tuple[int, int] = (1, 3)):
        self.__physical_qubits = array
        self.__anchor = anchor
        px, py = anchor
        self.x_ancilla = dict()
        for dx, dy in JunctionPatch.QUBITS["X"]:
            location = (px + dx, py + dy)
            self.x_ancilla[location] = array.qubits[location]
        self.z_ancilla: dict[tuple[float, float], int] = dict()
        for dx, dy in JunctionPatch.QUBITS["Z"]:
            location = (px + dx, py + dy)
            self.z_ancilla[location] = array.qubits[location]

    @property
    def num_qubits(self):
        return len(self.z_ancilla) + len(self.x_ancilla)

    def get_polygons(self, recovered_stabilizers: bool = False):
        polygons = []
        for (px, py), stabilizer in zip(
            self.z_ancilla.keys(), JunctionPatch.STABILIZERS["Z"]
        ):
            polygon = map(
                lambda d: self.__physical_qubits.qubits[(px + d[0], py + d[1])],
                stabilizer,
            )
            polygons.append(f"POLYGON(0,0,1,0.5) {' '.join(map(str, polygon))}")

        if recovered_stabilizers:
            for (px, py), stabilizer in zip(
                self.x_ancilla.keys(), JunctionPatch.STABILIZERS["X"]
            ):
                polygon = map(
                    lambda d: self.__physical_qubits.qubits[(px + d[0], py + d[1])],
                    stabilizer,
                )
                polygons.append(f"POLYGON(1,0,0,0.5) {' '.join(map(str, polygon))}")

        return polygons

    def annotate_detectors(
        self,
        circuitry: Circuitry,
        rounds: int,
        prefix: str = "JCT:R",
        postselected: bool = True,
    ):
        tags = DetectorTag.COMPLEMENTARY_GAP | (
            DetectorTag.POSTSELECTED if postselected else DetectorTag.DEFAULT
        )
        for zi, (prev, curr) in itertools.product(
            range(3), itertools.pairwise(range(rounds))
        ):
            circuitry.annotate_detector(
                f"{prefix}{curr}:Z{zi}",
                f"{prefix}{prev}:Z{zi}",
                tags=tags,
            )

    def append_syndrome(
        self,
        circuit: Circuitry,
        moment: int,
        prefix: str = "JCT:R",
        recovered_stabilizers: bool = False,
    ):
        match moment:
            case 0:
                circuit.append("RZ", self.z_ancilla.values())
                if recovered_stabilizers:
                    circuit.append("RX", self.x_ancilla.values())
            case 1 | 2 | 3 | 4:
                cx_targets = []
                for zi, ((px, py), za) in enumerate(self.z_ancilla.items()):
                    if zi != 0:
                        interaction = SurfaceCodePatch.SCHEDULE["6_STEPS"]["Z"][
                            moment - 1
                        ]
                    else:
                        interaction = JunctionPatch.LEFT_STABILIZER_SCHEDULE[moment - 1]
                    if (
                        interaction is None
                        or interaction not in JunctionPatch.STABILIZERS["Z"][zi]
                    ):
                        continue
                    dx, dy = interaction
                    qd = self.__physical_qubits.qubits[px + dx, py + dy]
                    cx_targets.append(qd)
                    cx_targets.append(za)
                if recovered_stabilizers:
                    for xi, ((px, py), xa) in enumerate(self.x_ancilla.items()):
                        interaction = JunctionPatch.RECOVERED_STABILIZER_SCHEDULE[
                            moment - 1
                        ]
                        if (
                            interaction is None
                            or interaction not in JunctionPatch.STABILIZERS["X"][xi]
                        ):
                            continue
                        dx, dy = interaction
                        qd = self.__physical_qubits.qubits[px + dx, py + dy]
                        cx_targets.append(xa)
                        cx_targets.append(qd)
                circuit.append("CX", cx_targets)
            case 5:
                circuit.append("MZ", self.z_ancilla.values())
                for qi, qz in enumerate(self.z_ancilla.values()):
                    self.__physical_qubits.record_measurement(f"{prefix}:Z{qi}", qz)
                if recovered_stabilizers:
                    circuit.append("MX", self.x_ancilla.values())
                    for qi, qx in enumerate(self.x_ancilla.values()):
                        self.__physical_qubits.record_measurement(f"{prefix}:X{qi}", qx)

            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

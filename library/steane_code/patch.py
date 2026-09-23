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
from enum import Enum

from typing import List, Optional

from library.circuitry import Circuitry
from library.qubit_array import QubitArray
from library.common import Pauli

logger = logging.getLogger(__name__)


class SteaneCodePatch:
    class Injection(Enum):
        S = 0
        T = 1

    QUBITS_ALT = {
        "D0": (2.0, 2.0),
        "D1": (0.0, 2.0),
        "D2": (2.0, 1.0),
        "D3": (3.0, 2.0),
        "D4": (3.0, 0.0),
        "D5": (1.0, 0.0),
        "D6": (1.0, 1.0),
        "RD": (3.0, 1.0),
        "RX": (2.5, 1.5),
        "RZ": (3.5, 0.5),
        "GD": (2.0, 0.0),
        "GX": (1.5, 0.5),
        "GZ": (2.5, 0.5),
        "BD": (1.0, 2.0),
        "BX": (0.5, 1.5),
        "BZ": (1.5, 1.5),
        "EX": (0.5, 0.5),
    }

    QUBITS = [
        # Data qubits
        (2, 2),
        (0, 2),
        (2, 1),
        (3, 2),
        (3, 0),
        (1, 0),
        (1, 1),
        # Data-ancilla qubits
        (2, 0),
        (3, 1),
        (1, 2),
        # Meas-ancilla qubits
        (1.5, 0.5),
        (2.5, 0.5),
        (3.5, 0.5),
        (0.5, 1.5),
        (1.5, 1.5),
        (2.5, 1.5),
        (0.5, 0.5),
    ]

    SUPPORTS = {
        "START": {
            "R": ["D0", "D2", "GZ", "RX"],
            "G": ["D2", "D6", "GD", "GZ"],
            "B": ["D0", "BZ", "D6", "D2"],
        },
        "FINAL": {
            "R": ["D0", "D2", "D4", "D3"],
            "G": ["D2", "D6", "D5", "D4"],
            "B": ["D0", "D1", "D6", "D2"],
        },
    }

    # STABILIZERS = {
    #     'START' : {'R': [0, 2, 11, 15], 'G': [2, 6, 7, 11], 'B': [0, 14, 6, 2]},
    #     'FINAL' : {'R': [0, 2,  4,  3], 'G': [2, 4, 5,  6], 'B': [0,  1, 6, 2]},
    # }

    PREPARATION_MOMENTS = range(11)
    SUPERDENSE_MOMENTS = range(15)
    CULTIVATION_MOMENTS = range(12)
    TELEPORTATION_MOMENTS = range(15)
    DESTRUCTION_MOMENTS = range(6)

    def __init__(
        self,
        array: QubitArray,
        anchor: tuple[int, int] = (0, 0),
        injection: Injection = Injection.S,
    ):
        self.__anchor = anchor
        self.__injection = injection
        self.__physical_qubits = array
        px, py = anchor
        self.qubits = [
            array.qubits[(px + dx, py + dy)] for dx, dy in SteaneCodePatch.QUBITS
        ]
        self.qubits_alt = {
            label: array[(px + dx, py + dy)]
            for label, (dx, dy) in SteaneCodePatch.QUBITS_ALT.items()
        }

    def __shift_qubit_ids(self, *qubits: int) -> List[int]:
        return list(map(lambda q: self.qubits[q], qubits))

    def __translate_qubits(self, *qubits: str) -> List[int]:
        return list(map(lambda q: self.qubits_alt[q], qubits))

    @property
    def injection(self):
        return self.__injection

    @property
    def support(self) -> List[int]:
        return self.qubits[:7]

    def logical(self, basis: Pauli):
        match basis:
            case Pauli.X:
                return {self.qubits[q]: "X" for q in [1, 5, 6]}
            case Pauli.Y:
                # TODO: study the effect of using the weight-5 Y-observable (i.e. Z0*Y1*Z3*X5*X6)
                return {self.qubits[q]: "Y" for q in range(7)}
            case Pauli.Z:
                return {self.qubits[q]: "Z" for q in [0, 1, 3]}

    @property
    def stabilizers(self):
        return {
            color: self.__translate_qubits(*support)
            for color, support in SteaneCodePatch.SUPPORTS["FINAL"].items()
        }

    def __get_polygons(self, stabilizers: dict[str, list[str]], opacity: float = 0.5):
        polygons = []
        for color, support in stabilizers.items():
            x, y, z = int(color == "R"), int(color == "G"), int(color == "B")
            polygons.append(
                f"POLYGON({x},{y},{z},{opacity}) {
                    ' '.join(map(str, self.__translate_qubits(*support)))
                }"
            )
        return polygons

    def get_polygons(self, initial: bool = False, opacity: float = 0.5):
        if initial:
            return self.__get_polygons(SteaneCodePatch.SUPPORTS["START"], opacity)
        else:
            return self.__get_polygons(SteaneCodePatch.SUPPORTS["FINAL"], opacity)

    def annotate_detectors(
        self, circuitry: Circuitry, sdc_rounds: int = 0, tpt_rounds: int = 0, prefix: str = "STN"
    ):
        # Annotate all SUPERDENSE detectors
        for color in self.stabilizers.keys():
            if sdc_rounds >= 1:
                circuitry.annotate_detector(f"{prefix}:SDC0:X{color}", postselected=True)
                circuitry.annotate_detector(f"{prefix}:SDC0:Z{color}", postselected=True)
            for prev, curr in itertools.pairwise(range(sdc_rounds)):
                circuitry.annotate_detector(
                    f"{prefix}:SDC{curr}:Z{color}", f"{prefix}:SDC{prev}:Z{color}",
                    postselected=True
                )

        for prev, curr in itertools.pairwise(range(sdc_rounds)):
            circuitry.annotate_detector(f"{prefix}:SDC{curr}:XR", postselected=True)
            circuitry.annotate_detector(
                f"{prefix}:SDC{curr}:XG", f"{prefix}:SDC{prev}:XR", f"{prefix}:SDC{prev}:XG",
                postselected=True
            )
            circuitry.annotate_detector(f"{prefix}:SDC{curr}:XB", f"{prefix}:SDC{prev}:XG",
                postselected=True
            )

        # Annotate the CULTIVATION detectors
        for measurement in range(6):
            circuitry.annotate_detector(f"{prefix}:CULT:X{measurement}", postselected=True)

        # Annotate the TELEPORTATION stabilized detectors
        last = sdc_rounds - 1
        for color in self.stabilizers.keys():
            circuitry.annotate_detector(
                f"{prefix}:TPT0:Z{color}", f"{prefix}:SDC{last}:Z{color}", postselected=True
            )
            for prev, curr in itertools.pairwise(range(tpt_rounds)):
                circuitry.annotate_detector(
                    f"{prefix}:TPT{curr}:Z{color}", f"{prefix}:TPT{prev}:Z{color}", postselected=True
                )

        circuitry.annotate_detector(f"{prefix}:TPT0:XR", postselected=True)
        circuitry.annotate_detector(
            f"{prefix}:TPT0:XG", f"{prefix}:SDC{last}:XR", f"{prefix}:SDC{last}:XG", postselected=True
        )
        circuitry.annotate_detector(f"{prefix}:TPT0:XB", f"{prefix}:SDC{last}:XG", postselected=True)

        for prev, curr in itertools.pairwise(range(tpt_rounds)):
            circuitry.annotate_detector(f"{prefix}:TPT{curr}:XR", postselected=True)
            circuitry.annotate_detector(
                f"{prefix}:TPT{curr}:XG", f"{prefix}:TPT{prev}:XR", f"{prefix}:TPT{prev}:XG",
                postselected=True
            )
            circuitry.annotate_detector(
                f"{prefix}:TPT{curr}:XB", f"{prefix}:TPT{prev}:XG",
                postselected=True
            )

    def append_preparation(self, circuit: Circuitry, moment: Optional[int] = None):
        if moment is None:
            for moment in self.PREPARATION_MOMENTS:
                self.append_preparation(circuit, moment)
                circuit.append_tick()
            return

        match moment:
            case 0:
                circuit.append("RX", self.__translate_qubits("D0", "D2", "D6", "GZ"))
                circuit.append(
                    "RZ",
                    self.__translate_qubits(
                        "D1",
                        "D3",
                        "D4",
                        "D5",
                        "GD",
                        "GX",
                        "RD",
                        "RX",
                        "RZ",
                        "BD",
                        "BX",
                        "BZ",
                    ),
                )
            case 1:
                circuit.append(
                    "CX", self.__translate_qubits("D0", "BZ", "D2", "RX", "GZ", "GD")
                )
            case 2:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "D0", "RX", "D2", "BZ", "GD", "GX", "GZ", "RD"
                    ),
                )
            case 3:
                circuit.append(
                    "CX", self.__translate_qubits("D6", "BZ", "GX", "GD", "RD", "GZ")
                )
            case 4:
                circuit.append("CX", self.__translate_qubits("D6", "GX", "BZ", "BD"))
            case 5:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "D2", "GX", "BZ", "D6", "BD", "BX", "RD", "RX"
                    ),
                )
            case 6:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "GX", "D6", "RX", "D3", "RD", "GZ", "BD", "BZ", "BX", "D1"
                    ),
                )
            case 7:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "D3", "RX", "GX", "D5", "GZ", "RD", "BX", "BD"
                    ),
                )
                circuit.append(
                    f"{self.__injection.name}_DAG", self.__translate_qubits("D6")
                )
            case 8:
                circuit.append("CX", self.__translate_qubits("GZ", "D4", "BX", "D6"))
            case 9:
                circuit.append(
                    "CX", self.__translate_qubits("D1", "BX", "GX", "D6", "D4", "GZ")
                )
            case 10:
                circuit.append("CX", self.__translate_qubits("D5", "GX"))
            case _:
                raise ValueError(f"Invalid moment requested [moment={moment}, max=10]")

    def append_superdense_cycle(
        self, circuit: Circuitry, moment: Optional[int] = None, prefix: str = "STN:SDC"
    ):
        if moment is None:
            for moment in self.SUPERDENSE_MOMENTS:
                self.append_superdense_cycle(circuit, moment, prefix)
                circuit.append_tick()
            return

        match moment:
            case 0:
                circuit.append("RX", self.__translate_qubits("RX", "GX", "BX"))
                circuit.append(
                    "RZ", self.__translate_qubits("RD", "RZ", "GD", "GZ", "BD", "BZ")
                )
            case 1:
                circuit.append(
                    "CX", self.__translate_qubits("RX", "RD", "GX", "GD", "BX", "BD")
                )
            case 2:
                circuit.append(
                    "CX", self.__translate_qubits("RD", "RZ", "GD", "GZ", "BD", "BZ")
                )
            case 3:
                circuit.append(
                    "CX", self.__translate_qubits("RZ", "RD", "GZ", "GD", "BZ", "BD")
                )
            case 4:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "GX", "D6", "GZ", "D2", "RX", "D3", "BZ", "D0"
                    ),
                )
            case 5:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "GX", "D5", "GZ", "D4", "RX", "D0", "BZ", "D2"
                    ),
                )
            case 6:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "RX", "D2", "RZ", "D4", "BX", "D1", "BZ", "D6"
                    ),
                )
            case 7:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "D2", "RX", "D4", "RZ", "D1", "BX", "D6", "BZ"
                    ),
                )
            case 8:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "D5", "GX", "D4", "GZ", "D2", "BZ", "D0", "RX"
                    ),
                )
            case 9:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "D0", "BZ", "D2", "GZ", "D3", "RX", "D6", "GX"
                    ),
                )
            case 10:
                circuit.append(
                    "CX", self.__translate_qubits("RD", "RZ", "GD", "GZ", "BD", "BZ")
                )
            case 11:
                circuit.append(
                    "CX", self.__translate_qubits("RX", "RD", "GX", "GD", "BX", "BD")
                )
            case 12:
                circuit.append(
                    "CX", self.__translate_qubits("RD", "RZ", "GD", "GZ", "BD", "BZ")
                )
            case 13:
                circuit.append(
                    "CX", self.__translate_qubits("RX", "RD", "GX", "GD", "BX", "BD")
                )
            case 14:
                measured_x_ancilla = self.__translate_qubits("RX", "GX", "BX")
                circuit.append("MX", measured_x_ancilla)
                for xa, color in zip(measured_x_ancilla, ["R", "G", "B"]):
                    self.__physical_qubits.record_measurement(xa, f"{prefix}:X{color}")
                measured_z_ancilla = self.__translate_qubits("RZ", "GZ", "BZ")
                circuit.append("MZ", measured_z_ancilla)
                for za, color in zip(measured_z_ancilla, ["R", "G", "B"]):
                    self.__physical_qubits.record_measurement(za, f"{prefix}:Z{color}")
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    def append_cultivation(
        self, circuit: Circuitry, moment: Optional[int] = None, prefix: str = "STN:CULT"
    ):
        if moment is None:
            for moment in self.CULTIVATION_MOMENTS:
                self.append_cultivation(circuit, moment, prefix)
                circuit.append_tick()
            return

        match moment:
            case 0:
                circuit.append(f"{self.__injection.name}_DAG", self.support)
                circuit.append(
                    "RX", self.__translate_qubits("GX", "GZ", "BX", "BZ", "RX")
                )
            case 1:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "RX", "D3", "GX", "D5", "GZ", "D4", "BX", "D1", "BZ", "D2"
                    ),
                )
            case 2:
                circuit.append(
                    "CX", self.__translate_qubits("D2", "GZ", "D6", "BX", "RX", "D0")
                )
            case 3:
                circuit.append("CX", self.__translate_qubits("D2", "RX", "GX", "D6"))
            case 4:
                circuit.append("CX", self.__translate_qubits("GX", "D2"))
            case 5:
                circuit.append("MX", self.__translate_qubits("GX"))
                self.__physical_qubits.record_measurement(
                    self.__translate_qubits("GX")[0], f"{prefix}:X0"
                )
            case 6:
                circuit.append("RX", self.__translate_qubits("GX"))
            case 7:
                circuit.append("CX", self.__translate_qubits("GX", "D2"))
            case 8:
                circuit.append("CX", self.__translate_qubits("D2", "RX", "GX", "D6"))
            case 9:
                circuit.append(
                    "CX", self.__translate_qubits("D2", "GZ", "D6", "BX", "RX", "D0")
                )
            case 10:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "RX", "D3", "GX", "D5", "GZ", "D4", "BX", "D1", "BZ", "D2"
                    ),
                )
            case 11:
                # measured_ancilla = self.__shift_qubit_ids(10, 11, 13, 14, 15)
                measured_ancilla = self.__translate_qubits("GX", "GZ", "BX", "BZ", "RX")
                circuit.append("MX", measured_ancilla)
                for index, xa in enumerate(measured_ancilla):
                    self.__physical_qubits.record_measurement(
                        xa, f"{prefix}:X{index + 1}"
                    )
                circuit.append(f"{self.__injection.name}", self.support)
            case _:
                raise ValueError(f"Invalid moment requested [moment={moment}, max=10]")

    def append_teleportation(
        self, circuit: Circuitry, moment: Optional[int] = None, prefix: str = "STN:TPT"
    ):
        if moment is None:
            for moment in self.TELEPORTATION_MOMENTS:
                self.append_teleportation(circuit, moment, prefix)
                circuit.append_tick()
            return

        match moment:
            # GHZ-state formation
            case 0:
                circuit.append("RX", self.__translate_qubits("RX", "GX", "BX"))
                circuit.append(
                    "RZ", self.__translate_qubits("RD", "RZ", "GD", "GZ", "BD", "BZ")
                )
            case 1:
                circuit.append(
                    "CX", self.__translate_qubits("RX", "RD", "GX", "GD", "BX", "BD")
                )
            case 2:
                circuit.append(
                    "CX", self.__translate_qubits("RD", "RZ", "GD", "GZ", "BD", "BZ")
                )
            case 3:
                circuit.append(
                    "CX", self.__translate_qubits("RZ", "RD", "GZ", "GD", "BZ", "BD")
                )
            # X-syndrome extractions
            case 4:
                circuit.append(
                    "CX", self.__translate_qubits("GX", "D6", "GZ", "D2", "RX", "D3")
                )
            case 5:
                circuit.append(
                    "CX", self.__translate_qubits("GX", "D5", "GZ", "D4", "RX", "D0")
                )
            case 6:
                circuit.append("CX", self.__translate_qubits("RX", "D2", "RZ", "D4"))
            # Z-syndrome extractions
            case 7:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "D2", "RX", "D4", "RZ", "D1", "BX", "D6", "BZ"
                    ),
                )
            case 8:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "D5", "GX", "D4", "GZ", "D2", "BZ", "D0", "RX"
                    ),
                )
            case 9:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "D0", "BZ", "D2", "GZ", "D3", "RX", "D6", "GX"
                    ),
                )
            case 10:
                circuit.append(
                    "CX", self.__translate_qubits("RD", "RZ", "GD", "GZ", "BD", "BZ")
                )
            case 11:
                circuit.append(
                    "CX", self.__translate_qubits("RX", "RD", "GX", "GD", "BX", "BD")
                )
            case 12:
                circuit.append(
                    "CX", self.__translate_qubits("RD", "RZ", "GD", "GZ", "BD", "BZ")
                )
            case 13:
                circuit.append(
                    "CX", self.__translate_qubits("RX", "RD", "GX", "GD", "BX", "BD")
                )
            case 14:
                measured_x_ancilla = self.__translate_qubits("RX", "GX", "BX")
                circuit.append("MX", measured_x_ancilla)
                for xa, color in zip(measured_x_ancilla, ["R", "G", "B"]):
                    self.__physical_qubits.record_measurement(xa, f"{prefix}:X{color}")
                measured_z_ancilla = self.__translate_qubits("RZ", "GZ", "BZ")
                circuit.append("MZ", measured_z_ancilla)
                for za, color in zip(measured_z_ancilla, ["R", "G", "B"]):
                    self.__physical_qubits.record_measurement(za, f"{prefix}:Z{color}")
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    def append_destruction(
        self, circuit: Circuitry, moment: Optional[int] = None, prefix: str = "STN:DST"
    ):
        if moment is None:
            for moment in self.DESTRUCTION_MOMENTS:
                self.append_destruction(circuit, moment, prefix)
                circuit.append_tick()
            return

        match moment:
            case 0:
                circuit.append(
                    "R",
                    self.__translate_qubits("RX", "RZ", "GX", "GZ", "BX", "BZ", "EX"),
                )
            case 1:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "D0",
                        "BZ",
                        "D1",
                        "BX",
                        "D2",
                        "GZ",
                        "D3",
                        "RX",
                        "D4",
                        "RZ",
                        "D5",
                        "EX",
                        "D6",
                        "GX",
                    ),
                )
            case 3:
                circuit.append(
                    "CX",
                    self.__translate_qubits(
                        "BZ",
                        "D0",
                        "BX",
                        "D1",
                        "GZ",
                        "D2",
                        "RX",
                        "D3",
                        "RZ",
                        "D4",
                        "EX",
                        "D5",
                        "GX",
                        "D6",
                    ),
                )
            case 5:
                # measured_data_qubits = self.__shift_qubit_ids(14, 13, 11, 15, 12, 16, 10)
                measured_data_qubits = self.__translate_qubits(
                    "BZ", "BX", "GZ", "RX", "RZ", "EX", "GX"
                )
                circuit.append("MX", measured_data_qubits)
                for index, qd in enumerate(measured_data_qubits):
                    self.__physical_qubits.record_measurement(qd, f"{prefix}:X{index}")

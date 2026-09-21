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

    QUBITS = {
        'D0': (2.0, 2.0), 'D1': (0.5, 1.5), 'D2': (2.0, 1.0), 'D3': (3.0, 2.0), 'D4': (2.5, 0.5), 'D5': (1.0, 0.0), 'D6': (1.0, 1.0),
        'RD': (3.0, 1.0), 'RX': (3.5, 1.5), 'RZ': (2.5, 1.5),
        'GD': (2.0, 0.0), 'GX': (1.5,-0.5), 'GZ': (1.5, 0.5),
        'BD': (1.0, 2.0), 'BX': (1.5, 2.5), 'BZ': (1.5, 1.5)
    }

    SUPPORTS = {
        'START' : {'R': ['D0', 'D2', 'D4', 'RZ'], 'G': ['D2', 'D6', 'GD', 'D4'], 'B': ['D0', 'BZ', 'D6', 'D2']},
        'FINAL' : {'R': ['D0', 'D2', 'D4', 'D3'], 'G': ['D2', 'D6', 'D5', 'D4'], 'B': ['D0', 'D1', 'D6', 'D2']},
    }

    PREPARATION_MOMENTS = range(11)
    SUPERDENSE_MOMENTS = range(10)
    CULTIVATION_MOMENTS = range(12)
    TELEPORTATION_MOMENTS = range(15)
    DESTRUCTION_MOMENTS = range(6)

    def __init__(self, qubits: QubitArray, anchor: tuple[int, int] = (0, 1), injection: Injection = Injection.S):
        self.__anchor = anchor
        self.__injection = injection
        self.__available_qubits = qubits
        px, py = anchor
        self.__used_qubits = {
            label : qubits[(px + dx, py + dy)] for label, (dx, dy) in SteaneCodePatch.QUBITS.items()
        }

    def __translate_qubit_ids(self, *qubits: str) -> List[int]:
        return list(map(lambda q : self.__used_qubits[q], qubits))

    @property
    def injection(self):
        return self.__injection

    @property
    def support(self) -> List[int]:
        return [ self.__used_qubits[f'D{q}'] for q in range(7) ]

    def logical(self, basis: Pauli):
        match basis:
            case Pauli.X:
                return {self.__used_qubits[q]: 'X' for q in [1, 5, 6]}
            case Pauli.Y:
                # TODO: study the effect of using the weight-5 Y-observable (i.e. Z0*Y1*Z3*X5*X6)
                return {self.__used_qubits[q]: 'Y' for q in range(7)}
            case Pauli.Z:
                return {self.__used_qubits[q]: 'Z' for q in [0, 1, 3]}

    @property
    def stabilizers(self):
        return {
            color : self.__translate_qubit_ids(*stabs)
            for color, stabs in SteaneCodePatch.SUPPORTS['FINAL'].items()
        }

    def __get_polygons(self, stabilizers: dict[str, list[str]], opacity: float = 0.5):
        polygons = []
        for color, support in stabilizers.items():
            x, y, z = int(color == 'R'), int(color == 'G'), int(color == 'B')
            polygons.append(
                f"POLYGON({x},{y},{z},{opacity}) {" ".join(
                    map(str, self.__translate_qubit_ids(*support))
                )}"
            )
        return polygons

    def get_polygons(self, initial: bool = False, opacity: float = 0.5):
        if initial:
            return self.__get_polygons(SteaneCodePatch.SUPPORTS['START'], opacity)
        else:
            return self.__get_polygons(SteaneCodePatch.SUPPORTS['FINAL'], opacity)

    def annotate_detectors(self, circuitry: Circuitry, sdc_rounds: int = 0, tpt_rounds: int = 0):
        # Annotate all SUPERDENSE detectors
        for color in self.stabilizers.keys():
            if sdc_rounds >= 1:
                circuitry.annotate_detector(f"SDC0:X{color}")
                circuitry.annotate_detector(f"SDC0:Z{color}")
            for prev, curr in itertools.pairwise(range(sdc_rounds)):
                circuitry.annotate_detector(f"SDC{curr}:Z{color}", f"SDC{prev}:Z{color}")

        for prev, curr in itertools.pairwise(range(sdc_rounds)):
            circuitry.annotate_detector(f"SDC{curr}:XR")
            circuitry.annotate_detector(f"SDC{curr}:XG", f"SDC{prev}:XR", f"SDC{prev}:XG")
            circuitry.annotate_detector(f"SDC{curr}:XB", f"SDC{prev}:XG")

        # Annotate the CULTIVATION detectors
        for measurement in range(6):
            circuitry.annotate_detector(f"CULT:X{measurement}")

        # Annotate the TELEPORTATION stabilized detectors
        last = sdc_rounds-1
        for color in self.stabilizers.keys():
            circuitry.annotate_detector(f"TPT0:Z{color}", f"SDC{last}:Z{color}")
            for prev, curr in itertools.pairwise(range(tpt_rounds)):
                circuitry.annotate_detector(f"TPT{curr}:Z{color}", f"TPT{prev}:Z{color}")

        circuitry.annotate_detector(f"TPT0:XR")
        circuitry.annotate_detector(f"TPT0:XG", f"SDC{last}:XR", f"SDC{last}:XG")
        circuitry.annotate_detector(f"TPT0:XB", f"SDC{last}:XG")

        for prev, curr in itertools.pairwise(range(tpt_rounds)):
            circuitry.annotate_detector(f"TPT{curr}:XR")
            circuitry.annotate_detector(f"TPT{curr}:XG", f"TPT{prev}:XR", f"TPT{prev}:XG")
            circuitry.annotate_detector(f"TPT{curr}:XB", f"TPT{prev}:XG")

        # Annotate the TELEPORTATION destructive detectors
        # The X_{0126ab} detector.
        circuitry.annotate_detector(
            f"SDC{last}:XG", f"TPT0:XG", f"TPT0:XB", f"TPT1:XG", f"TPT1:XB", f"TPT2:XG", f"TPT2:XB",
            f"DST:X0", f"DST:X1", f"DST:X2", f"DST:X6", f"SC3:X0"
        )
        # The X_{2456} detector
        circuitry.annotate_detector(f"TPT2:XG", f"TPT2:XR", f"DST:X2", f"DST:X4", f"DST:X5", f"DST:X6")
        # The X_{0234} detector
        circuitry.annotate_detector(f"DST:X0", f"DST:X2", f"DST:X3", f"DST:X4")

    def append_preparation(self, circuit: Circuitry, moment: Optional[int] = None):
        if moment is None:
            for moment in self.PREPARATION_MOMENTS:
                self.append_preparation(circuit, moment)
                circuit.append_tick()
            return

        match moment:
            case 0:
                circuit.append("RX", self.__translate_qubit_ids('D0', 'D2', 'D4', 'D6'))
                circuit.append("RZ", self.__translate_qubit_ids('D1', 'D3', 'D5', 'RD', 'RZ', 'GD', 'GZ', 'BD', 'BZ'))
            case 1:
                circuit.append("CX", self.__translate_qubit_ids('D0', 'BZ', 'D2', 'RZ', 'D4', 'GD'))
            case 2:
                circuit.append("CX", self.__translate_qubit_ids('D0', 'RZ', 'D2', 'BZ', 'D4', 'RD', 'GD', 'GZ'))
            case 3:
                circuit.append("CX", self.__translate_qubit_ids('D6', 'BZ', 'RD', 'RZ', 'GZ', 'GD'))
            case 4:
                circuit.append("CX", self.__translate_qubit_ids('D4', 'RD', 'D6', 'GZ', 'RZ', 'D3', 'BZ', 'BD'))
            case 5:
                circuit.append("CX", self.__translate_qubit_ids('D2', 'GZ', 'D3', 'RZ', 'D4', 'GD', 'BD', 'D1'))
            case 6:
                circuit.append("CX", self.__translate_qubit_ids('D4', 'GD', 'D1', 'D6', 'BD', 'BZ'))
            case 7:
                circuit.append("CX", self.__translate_qubit_ids('D1', 'BD', 'GZ', 'D6'))
            case 8:
                circuit.append(self.__injection.name + "_DAG", self.__translate_qubit_ids('D6'))
                circuit.append("CX", self.__translate_qubit_ids('GZ', 'D5'))
            case 9:
                circuit.append("CX", self.__translate_qubit_ids('GZ', 'D6'))
            case 10:
                circuit.append("CX", self.__translate_qubit_ids('D1', 'D6', 'D5', 'GZ'))
            case _:
                raise ValueError(f"Invalid moment requested [moment={moment}, max=10]")

    def append_superdense_cycle(self, circuit: Circuitry, moment: Optional[int] = None, prefix: str = "SDC"):
        if moment is None:
            for moment in self.SUPERDENSE_MOMENTS:
                self.append_superdense_cycle(circuit, moment, prefix)
                circuit.append_tick()
            return

        match moment:
            # Initialization
            case 0:
                circuit.append("RX", self.__translate_qubit_ids('RD', 'GD', 'BD'))
                circuit.append("RZ", self.__translate_qubit_ids('RZ', 'GZ', 'BZ', 'RX', 'GX', 'BX'))
            # Prepare GHZ-states
            case 1:
                circuit.append("CX", self.__translate_qubit_ids('RD', 'RZ', 'GD', 'GZ', 'BD', 'BZ'))
            # Perform extractions
            case 2:
                circuit.append("CX", self.__translate_qubit_ids('GZ', 'D2', 'RD', 'D4', 'BZ', 'D0', 'RZ', 'D3'))
            case 3:
                circuit.append("CX", self.__translate_qubit_ids('RZ', 'D0', 'BZ', 'D2', 'GD', 'D4', 'GZ', 'D6'))
            case 4:
                circuit.append("CX", self.__translate_qubit_ids('GZ', 'D5', 'BD', 'D1', 'BZ', 'D6', 'RZ', 'D2', 'D4', 'GD'))
            case 5:
                circuit.append("XCZ", self.__translate_qubit_ids('GZ', 'D5', 'BD', 'D1', 'BZ', 'D6', 'RZ', 'D2', 'RD', 'D4'))
            case 6:
                circuit.append("XCZ", self.__translate_qubit_ids('RZ', 'RD', 'GZ', 'GD', 'BZ', 'BD'))
            case 7:
                circuit.append("XCZ", self.__translate_qubit_ids('GZ', 'D2', 'GX', 'GD', 'BZ', 'D0', 'RZ', 'D3', 'RX', 'RD', 'BX', 'BD'))
            # Separate GHZ-states
            case 8:
                circuit.append("CX", self.__translate_qubit_ids('D0', 'RZ', 'D6', 'GZ', 'D2', 'BZ', 'RX', 'RD', 'BX', 'BD', 'GX', 'GD'))
            case 9:
                measured_x_ancilla = self.__translate_qubit_ids('RX', 'GX', 'BX')
                circuit.append("MX", measured_x_ancilla)
                for xa, color in zip(measured_x_ancilla, ['R', 'G', 'B']):
                    self.__available_qubits.record_measurement(xa, f"{prefix}:X{color}")
                measured_z_ancilla = self.__translate_qubit_ids('RZ', 'GZ', 'BZ')
                circuit.append("MZ", measured_z_ancilla)
                for za, color in zip(measured_z_ancilla, ['R', 'G', 'B']):
                    self.__available_qubits.record_measurement(za, f"{prefix}:Z{color}")
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    def append_cultivation(self, circuit: Circuitry, moment: Optional[int] = None, prefix: str = "CULT"):
        if moment is None:
            for moment in self.CULTIVATION_MOMENTS:
                self.append_cultivation(circuit, moment, prefix)
                circuit.append_tick()
            return

        match moment:
            case 0:
                circuit.append(f"{self.__injection.name}_DAG", self.support)
                circuit.append("RX", self.__translate_qubit_ids())
            case 1:
                circuit.append("CX", self.__translate_qubit_ids())
            case 2:
                circuit.append("CX", self.__translate_qubit_ids())
            case 3:
                circuit.append("CX", self.__translate_qubit_ids())
            case 4:
                circuit.append("CX", self.__translate_qubit_ids())
            case 5:
                circuit.append("MX", self.__translate_qubit_ids())
                # self.__available_qubits.record_measurement(*self.__translate_qubit_ids(), f"{prefix}:X0")
            case 6:
                circuit.append("RX", self.__translate_qubit_ids())
            case 7:
                circuit.append("CX", self.__translate_qubit_ids())
            case 8:
                circuit.append("CX", self.__translate_qubit_ids())
            case 9:
                circuit.append("CX", self.__translate_qubit_ids())
            case 10:
                circuit.append("CX", self.__translate_qubit_ids())
            case 11:
                measured_ancilla = self.__translate_qubit_ids()
                circuit.append("MX", measured_ancilla)
                # for index, xa in enumerate(measured_ancilla):
                #     self.__available_qubits.record_measurement(xa, f"{prefix}:X{index + 1}")
                circuit.append(f"{self.__injection.name}", self.support)
            case _:
                raise ValueError(f"Invalid moment requested [moment={moment}, max=10]")

    def append_teleportation(self, circuit: Circuitry, moment: Optional[int] = None, prefix: str = "TPT"):
        if moment is None:
            for moment in self.TELEPORTATION_MOMENTS:
                self.append_teleportation(circuit, moment, prefix)
                circuit.append_tick()
            return

        match moment:
            # GHZ-state formation
            case 0:
                circuit.append("RX", self.__translate_qubit_ids(10, 13, 15))
                circuit.append("RZ", self.__translate_qubit_ids(7, 8, 9, 11, 12, 14))
            case 1:
                circuit.append("CX", self.__translate_qubit_ids(10, 7, 13, 9, 15, 8))
            case 2:
                circuit.append("CX", self.__translate_qubit_ids(7, 11, 9, 14, 8, 12))
            case 3:
                circuit.append("CX", self.__translate_qubit_ids(11, 7, 14, 9, 12, 8))
            # X-syndrome extractions
            case 4:
                circuit.append("CX", self.__translate_qubit_ids(10, 6, 11, 2, 15, 3))
            case 5:
                circuit.append("CX", self.__translate_qubit_ids(10, 5, 11, 4, 15, 0))
            case 6:
                circuit.append("CX", self.__translate_qubit_ids(12, 4, 15, 2))
            # Z-syndrome extractions
            case 7:
                circuit.append("CX", self.__translate_qubit_ids(1, 13, 2, 15, 4, 12, 6, 14))
            case 8:
                circuit.append("CX", self.__translate_qubit_ids(0, 15, 2, 14, 4, 11, 5, 10))
            case 9:
                circuit.append("CX", self.__translate_qubit_ids(0, 14, 2, 11, 3, 15, 6, 10))
            # GHZ-state contraction
            case 10:
                circuit.append("CX", self.__translate_qubit_ids(7, 11, 9, 14, 8, 12))
            case 11:
                circuit.append("CX", self.__translate_qubit_ids(10, 7, 13, 9, 15, 8))
            case 12:
                circuit.append("CX", self.__translate_qubit_ids(7, 11, 9, 14, 8, 12))
            case 13:
                circuit.append("CX", self.__translate_qubit_ids(10, 7, 13, 9, 15, 8))
            case 14:
                measured_x_ancilla = self.__translate_qubit_ids(10, 13, 15)
                circuit.append("MX", measured_x_ancilla)
                for xa, color in zip(measured_x_ancilla, ["G" , "B", "R"]):
                    self.__available_qubits.record_measurement(xa, f"{prefix}:X{color}")
                measured_z_ancilla = self.__translate_qubit_ids(11, 12, 14)
                circuit.append("MZ", measured_z_ancilla)
                for za, color in zip(measured_z_ancilla, ["G" , "R", "B"]):
                    self.__available_qubits.record_measurement(za, f"{prefix}:Z{color}")
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    def append_destruction(self, circuit: Circuitry, moment: Optional[int] = None, prefix: str = "DST"):
        if moment is None:
            for moment in self.DESTRUCTION_MOMENTS:
                self.append_destruction(circuit, moment, prefix)
                circuit.append_tick()
            return

        match moment:
            case 0:
                circuit.append("R", self.__translate_qubit_ids(10, 11, 12, 13, 14, 15, 16))
            case 1:
                circuit.append("CX", self.__translate_qubit_ids(5, 16, 4, 12, 6, 10, 2, 11, 0, 14, 3, 15, 1, 13))
            case 3:
                circuit.append("CX", self.__translate_qubit_ids(16, 5, 12, 4, 10, 6, 11, 2, 14, 0, 15, 3, 13, 1))
            case 5:
                measured_data_qubits = self.__translate_qubit_ids(14, 13, 11, 15, 12, 16, 10)
                circuit.append("MX", measured_data_qubits)
                for index, qd in enumerate(measured_data_qubits):
                    self.__available_qubits.record_measurement(qd, f"{prefix}:X{index}")
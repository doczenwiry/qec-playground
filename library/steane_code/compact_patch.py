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
        'BD': (1.0, 2.0), 'BX': (1.5, 2.5), 'BZ': (1.5, 1.5),
        'EX0': (0.5, 0.5), 'EX1': (0.0, 2.0), 'EX4': (3.0, 0.0)
    }

    SUPPORTS = {
        'START' : {'R': ['D0', 'D2', 'D4', 'RZ'], 'G': ['D2', 'D6', 'GD', 'D4'], 'B': ['D0', 'BZ', 'D6', 'D2']},
        'COMPACT' : {'R': ['D0', 'D2', 'D4', 'D3'], 'G': ['D2', 'D6', 'D5', 'D4'], 'B': ['D0', 'D1', 'D6', 'D2']},
        'DIFFUSE': {'R': ['D0', 'D2', 'EX4', 'D3'], 'G': ['D2', 'D6', 'D5', 'EX4'], 'B': ['D0', 'EX1', 'D6', 'D2']},
    }

    PREPARATION_MOMENTS = range(11)
    SUPERDENSE_MOMENTS = range(10)
    CULTIVATION_MOMENTS = range(12)
    TELEPORTATION_MOMENTS = range(10)
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

    def support(self, compact: bool = True) -> List[int]:
        if compact:
            return [ self.__used_qubits[f'D{q}'] for q in range(7) ]
        else:
            return [ self.__used_qubits[q] for q in ['D0', 'EX1', 'D2', 'D3', 'EX4', 'D5', 'D6'] ]

    def logical(self, basis: Pauli, compact: bool = True):
        match basis:
            case Pauli.X:
                return {self.__used_qubits[f"D{q}"]: 'X' for q in [1, 5, 6]}
            case Pauli.Y:
                # TODO: study the effect of using the weight-5 Y-observable (i.e. Z0*Y1*Z3*X5*X6)
                if compact:
                    return {self.__used_qubits[f"D{q}"]: 'Y' for q in range(7)}
                else:
                    return {self.__used_qubits[q]: 'Y' for q in ['D0', 'EX1', 'D2', 'D3', 'EX4', 'D5', 'D6']}
            case Pauli.Z:
                return {self.__used_qubits[f"D{q}"]: 'Z' for q in [0, 1, 3]}

    @property
    def stabilizers(self):
        return {
            color : self.__translate_qubit_ids(*stabs)
            for color, stabs in SteaneCodePatch.SUPPORTS['COMPACT'].items()
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

    def get_polygons(self, initial: bool = False, compact: bool = True, opacity: float = 0.5):
        if initial:
            return self.__get_polygons(SteaneCodePatch.SUPPORTS['START'], opacity)
        elif compact:
            return self.__get_polygons(SteaneCodePatch.SUPPORTS['COMPACT'], opacity)
        else:
            return self.__get_polygons(SteaneCodePatch.SUPPORTS['DIFFUSE'], opacity)

    def annotate_detectors(self, circuitry: Circuitry, sdc_rounds: int = 0, tpt_rounds: int = 0, prefix: str = "STN"):
        # Annotate all SUPERDENSE detectors
        for color in self.stabilizers.keys():
            if sdc_rounds >= 1:
                circuitry.annotate_detector(
                    f"{prefix}:SDC:R0:X{color}", postselected=True
                )
                circuitry.annotate_detector(
                    f"{prefix}:SDC:R0:Z{color}", postselected=True
                )
            for prev, curr in itertools.pairwise(range(sdc_rounds)):
                circuitry.annotate_detector(
                    f"{prefix}:SDC:R{curr}:Z{color}", f"{prefix}:SDC:R{prev}:Z{color}", postselected=True
                )

        for prev, curr in itertools.pairwise(range(sdc_rounds)):
            circuitry.annotate_detector(
                f"{prefix}:SDC:R{curr}:XR", postselected=True
            )
            circuitry.annotate_detector(
                f"{prefix}:SDC:R{curr}:XG", f"{prefix}:SDC:R{prev}:XR", f"{prefix}:SDC:R{prev}:XG", postselected=True
            )
            circuitry.annotate_detector(
                f"{prefix}:SDC:R{curr}:XB", f"{prefix}:SDC:R{prev}:XG", postselected=True
            )

        # Annotate the CULTIVATION detectors
        for measurement in ['CC', 'RZ', 'GZ', 'D1', 'BZ', 'EX0', 'D4']:
            circuitry.annotate_detector(f"{prefix}:CULT:{measurement}", postselected=True)

        # Annotate the TELEPORTATION stabilized detectors
        last = sdc_rounds-1
        for color in self.stabilizers.keys():
            circuitry.annotate_detector(
                f"{prefix}:TPT:R0:Z{color}", f"{prefix}:SDC{last}:Z{color}", postselected=True
            )
            for prev, curr in itertools.pairwise(range(tpt_rounds)):
                circuitry.annotate_detector(
                    f"{prefix}:TPT:R{curr}:Z{color}", f"{prefix}:TPT:R{prev}:Z{color}", postselected=True
                )

        circuitry.annotate_detector(
            f"{prefix}:TPT:R0:XR", f"{prefix}:SDC:R{last}:XG", postselected=True
        )
        circuitry.annotate_detector(
            f"{prefix}:TPT:R0:XG", f"{prefix}:SDC:R{last}:XR", postselected=True
        )
        circuitry.annotate_detector(
            f"{prefix}:TPT:R0:XB", postselected=True
        )

        for prev, curr in itertools.pairwise(range(tpt_rounds)):
            circuitry.annotate_detector(
                f"{prefix}:TPT:R{curr}:XR", f"{prefix}:TPT:R{prev}:XG", postselected=True
            )
            circuitry.annotate_detector(
                f"{prefix}:TPT:R{curr}:XG", f"{prefix}:TPT:R{prev}:XR", postselected=True
            )
            circuitry.annotate_detector(
                f"{prefix}:TPT:R{curr}:XB", postselected=True
            )

        # Annotate the TELEPORTATION destructive detectors
        # The X_{2456} detector
        circuitry.annotate_detector(
            f"{prefix}:TPT:R2:XG", f"{prefix}:TPT:R2:XR", f"{prefix}:DST:X2", f"{prefix}:DST:X4", f"{prefix}:DST:X5", f"{prefix}:DST:X6",
            postselected = True
        )
        # The X_{0234} detector
        circuitry.annotate_detector(
            f"{prefix}:DST:X0", f"{prefix}:DST:X2", f"{prefix}:DST:X3", f"{prefix}:DST:X4",
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
                circuit.append("CX", self.__translate_qubit_ids('D2', 'GZ', 'D3', 'RZ', 'BD', 'D1'))
            case 6:
                circuit.append("CX", self.__translate_qubit_ids('D1', 'D6', 'BD', 'BZ'))
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
                circuit.append("RZ", self.__translate_qubit_ids('RZ', 'GZ', 'BZ', 'RX', 'GX', 'BX', 'EX1', 'EX4'))
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
                circuit.append("XCZ", self.__translate_qubit_ids(
                    'GZ', 'D2', 'GX', 'GD', 'BZ', 'D0', 'RZ', 'D3', 'RX', 'RD', 'BX', 'BD', 'EX4', 'D1', 'EX1', 'D4'
                ))
            # Separate GHZ-states
            case 8:
                circuit.append("CX", self.__translate_qubit_ids(
                    'D0', 'RZ', 'D6', 'GZ', 'D2', 'BZ', 'RX', 'RD', 'BX', 'BD', 'GX', 'GD', 'EX4', 'D1', 'EX1', 'D4'
                ))
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
                circuit.append(f"{self.__injection.name}_DAG", self.support(compact=False))
                circuit.append("RX", self.__translate_qubit_ids('RZ', 'GZ', 'D1', 'BZ', 'EX0', 'D4'))
            case 1:
                circuit.append("CX", self.__translate_qubit_ids(
                    'D1', 'EX1', 'BZ', 'D2', 'RZ', 'D3', 'D4', 'EX4', 'EX0', 'D5'
                ))
            case 2:
                circuit.append("CX", self.__translate_qubit_ids(
                    'GZ', 'D5', 'D6', 'D1', 'D2', 'D4', 'RZ', 'D0'
                ))
            case 3:
                circuit.append("CX", self.__translate_qubit_ids(
                    'GZ', 'D6', 'D2', 'RZ'
                ))
            case 4:
                circuit.append("CX", self.__translate_qubit_ids(
                    'GZ', 'D2'
                ))
            case 5:
                circuit.append("MX", self.__translate_qubit_ids('GZ'))
                self.__available_qubits.record_measurement(*self.__translate_qubit_ids('GZ'), f"{prefix}:CC")
            case 6:
                circuit.append("RX", self.__translate_qubit_ids('GZ'))
            case 7:
                circuit.append("CX", self.__translate_qubit_ids(
                    'GZ', 'D2'
                ))
            case 8:
                circuit.append("CX", self.__translate_qubit_ids(
                    'GZ', 'D6', 'D2', 'RZ'
                ))
            case 9:
                circuit.append("CX", self.__translate_qubit_ids(
                    'GZ', 'D5', 'D6', 'D1', 'D2', 'D4', 'RZ', 'D0'
                ))
            case 10:
                circuit.append("CX", self.__translate_qubit_ids(
                    'D1', 'EX1', 'BZ', 'D2', 'RZ', 'D3', 'D4', 'EX4', 'EX0', 'D5'
                ))
            case 11:
                measured_ancilla = self.__translate_qubit_ids('RZ', 'GZ', 'D1', 'BZ', 'EX0', 'D4')
                circuit.append("MX", measured_ancilla)
                for label, xa in zip(['RZ', 'GZ', 'D1', 'BZ', 'EX0', 'D4'], measured_ancilla):
                    self.__available_qubits.record_measurement(xa, f"{prefix}:{label}")
                circuit.append(f"{self.__injection.name}", self.support(compact=False))
            case _:
                raise ValueError(f"Invalid moment requested [moment={moment}, max=10]")

    def append_teleportation(self, circuit: Circuitry, moment: Optional[int] = None, prefix: str = "TPT"):
        if moment is None:
            for moment in self.TELEPORTATION_MOMENTS:
                self.append_teleportation(circuit, moment, prefix)
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

    def append_destruction(self, circuit: Circuitry, moment: Optional[int] = None, prefix: str = "DST"):
        if moment is None:
            for moment in self.DESTRUCTION_MOMENTS:
                self.append_destruction(circuit, moment, prefix)
                circuit.append_tick()
            return

        match moment:
            case 0:
                circuit.append("R", self.__translate_qubit_ids('BZ', 'RZ', 'RX', 'GZ', 'EX0'))
            case 1:
                circuit.append("CX", self.__translate_qubit_ids('D0', 'BZ', 'D2', 'RZ', 'D3', 'RX', 'D5', 'GZ', 'D6', 'EX0'))
            case 3:
                circuit.append("CX", self.__translate_qubit_ids('BZ', 'D0', 'RZ', 'D2', 'RX', 'D3', 'GZ', 'D5', 'EX0', 'D6'))
            case 5:
                measured_data_qubits = self.__translate_qubit_ids('BZ', 'D1', 'RZ', 'RX', 'D4', 'GZ', 'EX0')
                circuit.append("MX", measured_data_qubits)
                for index, qd in enumerate(measured_data_qubits):
                    self.__available_qubits.record_measurement(qd, f"{prefix}:X{index}")
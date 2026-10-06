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
from logging import critical

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
        'COMPACT': {'R': ['D0', 'D2', 'D4', 'D3'], 'G': ['D2', 'D6', 'D5', 'D4'], 'B': ['D0', 'D1', 'D6', 'D2']},
        'DIFFUSE': {'R': ['D0', 'D2', 'EX4', 'D3'], 'G': ['D2', 'D6', 'D5', 'EX4'], 'B': ['D0', 'EX1', 'D6', 'D2']},
        'FINAL': {'R': ['D0', 'D2', 'EX4', 'D3'], 'G': ['D2', 'D6', 'D5', 'EX4'], 'B': ['D0', 'BD', 'D6', 'D2']},
    }

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

    def logical(self, basis: Pauli, compact: bool = True, final: bool = False):
        match basis:
            case Pauli.X:
                return {self.__used_qubits[f"D{q}"]: 'X' for q in [1, 5, 6]}
            case Pauli.Y:
                # TODO: study the effect of using the weight-5 Y-observable (i.e. Z0*Y1*Z3*X5*X6)
                if compact:
                    return {self.__used_qubits[f"D{q}"]: 'Y' for q in range(7)}
                elif final:
                    return {self.__used_qubits[q]: 'Y' for q in ['D0', 'BD', 'D2', 'D3', 'EX4', 'D5', 'D6']}
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

    def pauli_stabilizers(self, style: str = 'COMPACT') -> dict[str, dict[int, str]]:
        if style not in SteaneCodePatch.SUPPORTS:
            raise ValueError(f"Unknown stabilizer style : {style}")
        return {
            stabilizer + color : { qubit : stabilizer for qubit in self.__translate_qubit_ids(*support) }
            for stabilizer, (color, support) in itertools.product(
                ["X", "Z"], SteaneCodePatch.SUPPORTS[style].items()
            )
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

    def get_polygons(self, initial: bool = False, compact: bool = True, final: bool = False, opacity: float = 0.5):
        if initial:
            return self.__get_polygons(SteaneCodePatch.SUPPORTS['START'], opacity)
        elif final:
            return self.__get_polygons(SteaneCodePatch.SUPPORTS['FINAL'], opacity)
        elif compact:
            return self.__get_polygons(SteaneCodePatch.SUPPORTS['COMPACT'], opacity)
        else:
            return self.__get_polygons(SteaneCodePatch.SUPPORTS['DIFFUSE'], opacity)

    def annotate_detectors(self, circuitry: Circuitry, sdc_rounds: int = 0, tpt_rounds: int = 0, prefix: str = "STN"):
        # Annotate all SUPERDENSE detectors
        for color in self.stabilizers.keys():
            if sdc_rounds >= 1:
                circuitry.annotate_detector(
                    f"{prefix}:SDC0:X{color}", postselected=True
                )
                circuitry.annotate_detector(
                    f"{prefix}:SDC0:Z{color}", postselected=True
                )
            for prev, curr in itertools.pairwise(range(sdc_rounds)):
                circuitry.annotate_detector(
                    f"{prefix}:SDC{curr}:Z{color}", f"{prefix}:SDC{prev}:Z{color}", postselected=True
                )

        for prev, curr in itertools.pairwise(range(sdc_rounds)):
            circuitry.annotate_detector(
                f"{prefix}:SDC{curr}:XR", postselected=True
            )
            circuitry.annotate_detector(
                f"{prefix}:SDC{curr}:XG", f"{prefix}:SDC{prev}:XR", f"{prefix}:SDC{prev}:XG", postselected=True
            )
            circuitry.annotate_detector(
                f"{prefix}:SDC{curr}:XB", f"{prefix}:SDC{prev}:XG", postselected=True
            )

        # Annotate the CULTIVATION detectors
        for measurement in ['CC', 'RZ', 'GZ', 'D1', 'BZ', 'EX0', 'D4']:
            circuitry.annotate_detector(f"{prefix}:CULT:{measurement}", postselected=True)

        # Annotate the TELEPORTATION stabilized detectors
        last = sdc_rounds-1
        for color in self.stabilizers.keys():
            circuitry.annotate_detector(
                f"{prefix}:TPT0:Z{color}", f"{prefix}:SDC{last}:Z{color}", postselected=True
            )
            for prev, curr in itertools.pairwise(range(tpt_rounds)):
                circuitry.annotate_detector(
                    f"{prefix}:TPT{curr}:Z{color}", f"{prefix}:TPT{prev}:Z{color}", postselected=True
                )

        circuitry.annotate_detector(
            f"{prefix}:TPT0:XR", f"{prefix}:SDC{last}:XG", postselected=True
        )
        circuitry.annotate_detector(
            f"{prefix}:TPT0:XG", f"{prefix}:SDC{last}:XR", postselected=True
        )
        for rnd in range(tpt_rounds):
            circuitry.annotate_detector(f"{prefix}:TPT{rnd}:XB", postselected=True)

        for prev, curr in itertools.pairwise(range(tpt_rounds)):
            circuitry.annotate_detector(
                f"{prefix}:TPT{curr}:XR", f"{prefix}:TPT{prev}:XG", postselected=True
            )
            circuitry.annotate_detector(
                f"{prefix}:TPT{curr}:XG", f"{prefix}:TPT{prev}:XR", postselected=True
            )

    PREPARATION_MOMENTS = range(11)
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
                circuit.append(self.__injection.name, self.__translate_qubit_ids('D6'))
                circuit.append("CX", self.__translate_qubit_ids('GZ', 'D5'))
            case 9:
                circuit.append("CX", self.__translate_qubit_ids('GZ', 'D6'))
            case 10:
                circuit.append("CX", self.__translate_qubit_ids('D1', 'D6', 'D5', 'GZ'))
            case _:
                raise ValueError(f"Invalid moment requested [moment={moment}, max=10]")

    SUPERDENSE_MOMENTS = range(11)
    def append_superdense_cycle(self, circuitry: Circuitry, moment: Optional[int] = None, prefix: str = "SDC"):
        if moment is None:
            for moment in self.SUPERDENSE_MOMENTS:
                self.append_superdense_cycle(circuitry, moment, prefix)
                circuitry.append_tick()
            return

        match moment:
            # Initialization
            case 0:
                circuitry.append("RX", self.__translate_qubit_ids('RD', 'GD', 'BD'))
                circuitry.append("RZ", self.__translate_qubit_ids(
                    'RZ', 'GZ', 'BZ', 'RX', 'GX', 'BX', 'EX1', 'EX4'
                ))
            # Prepare Bell pairs
            case 1:
                circuitry.append("CX", self.__translate_qubit_ids('RD', 'RZ', 'GD', 'GZ', 'BD', 'BZ'))
            # Perform extractions
            case 2:
                circuitry.append("ZCX", self.__translate_qubit_ids(
                    'BZ', 'D0', 'GZ', 'D2', 'RZ', 'D3'
                ))
            case 3:
                circuitry.append("ZCX", self.__translate_qubit_ids(
                    'RZ', 'D0', 'BZ', 'D2', 'RD', 'D4', 'GZ', 'D6'
                ))
            case 4:
                circuitry.append("ZCX", self.__translate_qubit_ids(
                    'BD', 'D1', 'RZ', 'D2', 'GD', 'D4', 'GZ', 'D5', 'BZ', 'D6'
                ))
            case 5:
                circuitry.append("XCZ", self.__translate_qubit_ids(
                    'BD', 'D1', 'RZ', 'D2', 'GD', 'D4', 'GZ', 'D5', 'BZ', 'D6'
                ))
            case 6:
                circuitry.append("XCZ", self.__translate_qubit_ids(
                    'BZ', 'D0', 'GZ', 'D2', 'RZ', 'D3', 'RD', 'D4'
                ))
            case 7:
                circuitry.append("ZCX", self.__translate_qubit_ids('D0', 'RZ', 'D2', 'BZ', 'D6', 'GZ'))
                circuitry.append("CX", self.__translate_qubit_ids('RD', 'RX', 'GD', 'GX', 'BD', 'BX'))
            # Contract Bell pairs and move the X component onto the X-ancillas
            case 8:
                circuitry.append("CX", self.__translate_qubit_ids(
                    'D1', 'EX1', 'D4', 'EX4', 'RD', 'RZ', 'GD', 'GZ', 'BD', 'BZ'
                ))
            case 9:
                circuitry.append("CX", self.__translate_qubit_ids(
                    'EX1', 'D1', 'EX4', 'D4', 'RX', 'RD', 'GX', 'GD', 'BX', 'BD'
                ))
            case 10:
                measured_x_ancilla = self.__translate_qubit_ids('RX', 'GX', 'BX')
                circuitry.append("MX", measured_x_ancilla)
                for xa, color in zip(measured_x_ancilla, ['R', 'G', 'B']):
                    self.__available_qubits.record_measurement(f"{prefix}:X{color}", xa)
                measured_z_ancilla = self.__translate_qubit_ids('RZ', 'GZ', 'BZ')
                circuitry.append("MZ", measured_z_ancilla)
                for za, color in zip(measured_z_ancilla, ['R', 'G', 'B']):
                    self.__available_qubits.record_measurement(f"{prefix}:Z{color}", za)
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    CULTIVATION_MOMENTS = range(12)
    def append_cultivation(self, circuitry: Circuitry, moment: Optional[int] = None, prefix: str = "STN:CULT"):
        if moment is None:
            for moment in self.CULTIVATION_MOMENTS:
                self.append_cultivation(circuitry, moment, prefix)
                circuitry.append_tick()
            return

        match moment:
            case 0:
                circuitry.append(f"{self.__injection.name}", self.support(compact=False))
                circuitry.append("RX", self.__translate_qubit_ids('RZ', 'GZ', 'D1', 'BZ', 'EX0', 'D4'))
            case 1:
                circuitry.append("CX", self.__translate_qubit_ids(
                    'D1', 'EX1', 'BZ', 'D2', 'RZ', 'D3', 'D4', 'EX4', 'GZ', 'D5', 'EX0', 'D6'
                ))
            case 2:
                circuitry.append("CX", self.__translate_qubit_ids(
                    'D6', 'D1', 'D2', 'D4', 'RZ', 'D0'
                ))
            case 3:
                circuitry.append("CX", self.__translate_qubit_ids(
                    'GZ', 'D6', 'D2', 'RZ'
                ))
            case 4:
                circuitry.append("CX", self.__translate_qubit_ids(
                    'GZ', 'D2'
                ))
            case 5:
                circuitry.append("MX", self.__translate_qubit_ids('GZ'))
                self.__available_qubits.record_measurement(f"{prefix}:CC", *self.__translate_qubit_ids('GZ'))
            case 6:
                circuitry.append("RX", self.__translate_qubit_ids('GZ'))
            case 7:
                circuitry.append("CX", self.__translate_qubit_ids(
                    'GZ', 'D2'
                ))
            case 8:
                circuitry.append("CX", self.__translate_qubit_ids(
                    'GZ', 'D6', 'D2', 'RZ'
                ))
            case 9:
                circuitry.append("CX", self.__translate_qubit_ids(
                    'D6', 'D1', 'D2', 'D4', 'RZ', 'D0'
                ))
            case 10:
                circuitry.append("CX", self.__translate_qubit_ids(
                    'D1', 'EX1', 'BZ', 'D2', 'RZ', 'D3', 'D4', 'EX4', 'GZ', 'D5', 'EX0', 'D6'
                ))
            case 11:
                measured_ancilla = self.__translate_qubit_ids('RZ', 'GZ', 'D1', 'BZ', 'EX0', 'D4')
                circuitry.append("MX", measured_ancilla)
                for label, xa in zip(['RZ', 'GZ', 'D1', 'BZ', 'EX0', 'D4'], measured_ancilla):
                    self.__available_qubits.record_measurement(f"{prefix}:{label}", xa)
                circuitry.append(f"{self.__injection.name}_DAG", self.support(compact=False))
            case _:
                raise ValueError(f"Invalid moment requested [moment={moment}, max=10]")

    NOISELESS_MEASUREMENT_MOMENTS = range(6)
    def append_noiseless_measurement(
            self, circuitry: Circuitry, moment: Optional[int] = None,
            prefix: str = "STN:NOISELESS", compact: bool = True
    ):
        if compact:
            self.__append_noiseless_compact_measurement(circuitry, moment, prefix)
        else:
            self.__append_noiseless_diffuse_measurement(circuitry, moment, prefix)

    def __append_noiseless_compact_measurement(self, circuitry: Circuitry, moment: Optional[int] = None, prefix: str = "STN:NOISELESS"):
        if moment is None:
            for moment in self.NOISELESS_MEASUREMENT_MOMENTS:
                self.__append_noiseless_compact_measurement(circuitry, moment, prefix)
                circuitry.append_tick()
        else:
            match moment:
                case 0:
                    circuitry.append(f"{self.__injection.name}", self.support(compact=True))
                    circuitry.append("RX", self.__translate_qubit_ids('RZ', 'GZ'))
                case 1:
                    circuitry.append("CX", self.__translate_qubit_ids(
                        'GZ', 'D5', 'D6', 'D1', 'D2', 'D4', 'RZ', 'D3'
                    ))
                case 2:
                    circuitry.append("CX", self.__translate_qubit_ids(
                        'GZ', 'D6', 'RZ', 'D0'
                    ))
                case 3:
                    circuitry.append("CX", self.__translate_qubit_ids(
                        'D2', 'RZ'
                    ))
                case 4:
                    circuitry.append("CX", self.__translate_qubit_ids(
                        'GZ', 'D2'
                    ))
                case 5:
                    circuitry.append("MX", self.__translate_qubit_ids('GZ'))
                    self.__available_qubits.record_measurement(f"{prefix}:CC", *self.__translate_qubit_ids('GZ'))

    def __append_noiseless_diffuse_measurement(self, circuitry: Circuitry, moment: Optional[int] = None, prefix: str = "STN:NOISELESS"):
        if moment is None:
            for moment in self.NOISELESS_MEASUREMENT_MOMENTS:
                self.__append_noiseless_diffuse_measurement(circuitry, moment, prefix)
                circuitry.append_tick()
        else:
            match moment:
                case 0:
                    circuitry.append(f"{self.__injection.name}", self.support(compact=False))
                    circuitry.append("RX", self.__translate_qubit_ids('RZ', 'GZ', 'D1', 'BZ', 'EX0', 'D4'))
                case 1:
                    circuitry.append("CX", self.__translate_qubit_ids(
                        'D1', 'EX1', 'BZ', 'D2', 'RZ', 'D3', 'D4', 'EX4', 'GZ', 'D5'
                    ))
                case 2:
                    circuitry.append("CX", self.__translate_qubit_ids(
                        'D6', 'D1', 'D2', 'D4', 'RZ', 'D0'
                    ))
                case 3:
                    circuitry.append("CX", self.__translate_qubit_ids(
                        'GZ', 'D6', 'D2', 'RZ'
                    ))
                case 4:
                    circuitry.append("CX", self.__translate_qubit_ids(
                        'GZ', 'D2'
                    ))
                case 5:
                    circuitry.append("MX", self.__translate_qubit_ids('GZ'))
                    self.__available_qubits.record_measurement(f"{prefix}:CC", *self.__translate_qubit_ids('GZ'))

    TELEPORTATION_MOMENTS = range(11)
    def append_teleportation_round(self, circuitry: Circuitry, round: int, moment: Optional[int] = None, prefix: str = "STN:TPT"):
        match round:
            case 0:
                self.__append_teleportation_round(circuitry, moment, prefix)
            case 1:
                self.__append_teleportation_round(circuitry, moment, prefix)
            case 2:
                self.__append_teleportation_round(circuitry, moment, prefix)
            case _:
                logger.warning(f"Nothing to do at requested round [{round}]")

    def __append_teleportation_round(self, circuitry: Circuitry, moment: Optional[int] = None, prefix: str = "STN:TPT"):
        if moment is None:
            for moment in self.TELEPORTATION_MOMENTS:
                self.__append_teleportation_round(circuitry, moment, prefix)
                circuitry.append_tick()
        else:
            match moment:
                # Initialization
                case 0:
                    circuitry.append("RX", self.__translate_qubit_ids('RD', 'GD', 'BZ'))
                    circuitry.append("RZ", self.__translate_qubit_ids(
                        'RZ', 'GZ', 'BD', 'RX', 'GX', 'BX', 'D1', 'D4'
                    ))
                # Prepare Bell pairs
                case 1:
                    circuitry.append("CX", self.__translate_qubit_ids(
                        'EX4', 'D4', 'RD', 'RZ', 'GD', 'GZ', 'BZ', 'BD'
                    ))
                # Perform extractions
                case 2:
                    circuitry.append("ZCX", self.__translate_qubit_ids(
                        'EX1', 'D1', 'RZ', 'D2', 'GZ', 'D5'
                    ))
                    circuitry.append("CX", self.__translate_qubit_ids('D4', 'EX4'))
                case 3:
                    circuitry.append("ZCX", self.__translate_qubit_ids(
                        'RZ', 'D0', 'GD', 'D4', 'GZ', 'D6'
                    ))
                case 4:
                    circuitry.append("ZCX", self.__translate_qubit_ids(
                        'GZ', 'D2', 'RZ', 'D3', 'RD', 'D4'
                    ))
                case 5:
                    circuitry.append("XCZ", self.__translate_qubit_ids(
                        'BZ', 'D0', 'BD', 'D1', 'GZ', 'D2', 'RZ', 'D3', 'RD', 'D4'
                    ))
                case 6:
                    circuitry.append("XCZ", self.__translate_qubit_ids(
                        'RZ', 'D2', 'GD', 'D4', 'GZ', 'D5', 'BZ', 'D6'
                    ))
                case 7:
                    circuitry.append("ZCX", self.__translate_qubit_ids('D0', 'RZ', 'D2', 'BZ', 'D6', 'GZ'))
                    circuitry.append("CX", self.__translate_qubit_ids('RD', 'RX', 'GD', 'GX', 'BD', 'BX'))
                # Contract Bell pairs and move the X component onto the X-ancillas
                case 8:
                    circuitry.append("CX", self.__translate_qubit_ids(
                        'D4', 'EX4', 'RD', 'RZ', 'GD', 'GZ', 'BD', 'BZ'
                    ))
                case 9:
                    circuitry.append("CX", self.__translate_qubit_ids(
                        'EX1', 'D1', 'EX4', 'D4', 'RX', 'RD', 'GX', 'GD', 'BX', 'BD'
                    ))
                case 10:
                    measured_x_ancilla = self.__translate_qubit_ids('RX', 'GX', 'BX')
                    circuitry.append("MX", measured_x_ancilla)
                    for xa, color in zip(measured_x_ancilla, ['R', 'G', 'B']):
                        self.__available_qubits.record_measurement(f"{prefix}:X{color}", xa)
                    measured_z_ancilla = self.__translate_qubit_ids('RZ', 'GZ', 'BZ')
                    circuitry.append("MZ", measured_z_ancilla)
                    for za, color in zip(measured_z_ancilla, ['R', 'G', 'B']):
                        self.__available_qubits.record_measurement(f"{prefix}:Z{color}", za)
                case _:
                    logger.warning(f"Nothing to do at requested moment [{moment}]")

    DESTRUCTION_MOMENTS = range(6)
    def append_destruction(self, circuit: Circuitry, moment: Optional[int] = None, prefix: str = "DST"):
        if moment is None:
            for moment in self.DESTRUCTION_MOMENTS:
                self.append_destruction(circuit, moment, prefix)
                circuit.append_tick()
            return

        match moment:
            case 0:
                circuit.append("R", self.__translate_qubit_ids('BZ', 'D1', 'GZ', 'RZ', 'D4', 'GX', 'EX0'))
            case 1:
                circuit.append("ZCX", self.__translate_qubit_ids('D0', 'BZ', 'EX1', 'D1', 'D2', 'GZ', 'D3', 'RZ', 'EX4', 'D4', 'D5', 'GX', 'D6', 'EX0'))
            case 3:
                circuit.append("XCZ", self.__translate_qubit_ids('D0', 'BZ', 'EX1', 'D1', 'D2', 'GZ', 'D3', 'RZ', 'EX4', 'D4', 'D5', 'GX', 'D6', 'EX0'))
            case 5:
                measured_data_qubits = self.__translate_qubit_ids('BZ', 'D1', 'GZ', 'RZ', 'D4', 'GX', 'EX0')
                circuit.append("MX", measured_data_qubits)
                for index, qd in enumerate(measured_data_qubits):
                    self.__available_qubits.record_measurement(f"{prefix}:X{index}", qd)
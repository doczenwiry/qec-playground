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
from typing import Iterable

import itertools
import stim


logger = logging.getLogger(__name__)

class SteaneCodePatch:
    QUBITS = [
        # Data qubits
        (2,2), (0,2), (2,1), (3,2), (3,0), (1,0), (1,1),
        # Data-ancilla qubits
        (2, 0), (3, 1), (1, 2),
        # Meas-ancilla qubits
        (1.5, 0.5), (2.5, 0.5), (3.5, 0.5), (0.5, 1.5), (1.5, 1.5), (2.5, 1.5),
    ]

    INITIALIZED = {'R': [0, 2, 11, 15], 'G': [2, 6, 7, 11], 'B': [0, 14, 6, 2]}
    STABILIZERS = {'R': [0, 2,  4,  3], 'G': [2, 4, 5,  6], 'B': [0,  1, 6, 2]}

    def __init__(self, base_qubit: int = 0, anchor: tuple[int, int] = (1, 1)):
        px, py = anchor
        self.base_qubit = base_qubit
        self.qubits = {
            base_qubit + q : (px + dx, py + dy) for q, (dx, dy) in enumerate(SteaneCodePatch.QUBITS)
        }

    def __shift_qubit_ids(self, qubits: list[int]) -> Iterable[int]:
        return map(lambda q : self.base_qubit + q, qubits)

    @property
    def num_qubits(self):
        return len(self.qubits)

    @property
    def logical(self):
        return list(range(self.base_qubit, self.base_qubit + 7))

    @property
    def stabilizers(self):
        return {
            color : list(self.__shift_qubit_ids(stabs)) for color, stabs in SteaneCodePatch.STABILIZERS.items()
        }

    def get_qubit_at_location(self, px, py):
        for qubit, (x, y) in self.qubits.items():
            if x == px and y == py:
                return qubit
        return -1

    def __get_polygons(self, initial: bool):
        polygons = []
        stabilizers = SteaneCodePatch.INITIALIZED if initial else SteaneCodePatch.STABILIZERS
        for color, support in stabilizers.items():
            x, y, z = int(color == 'R'), int(color == 'G'), int(color == 'B')
            polygons.append(
                f"#!pragma POLYGON({x},{y},{z},0.5) {" ".join(map(str, self.__shift_qubit_ids(support)))}\n"
            )
        return polygons

    def get_initial_polygons(self):
        return self.__get_polygons(initial=True)

    def get_prepared_polygons(self):
        return self.__get_polygons(initial=False)

    def append_metadata(self, circuit: stim.Circuit):
        for qubit, location in self.qubits.items():
            circuit.append("QUBIT_COORDS", [qubit], location)

    def append_observable(self, circuit: stim.Circuit, observable: str, support: list[int]):
            circuit.append("MPP", stim.PauliString(
                "*".join(map(lambda q: observable + str(q), support))
            ))
            circuit.append("OBSERVABLE_INCLUDE", [stim.target_rec(-1)], 0)
            circuit.append("TICK")

    @property
    def preparation_moments(self):
        return 11

    def append_preparation(self, circuit: stim.Circuit):
        for moment in range(self.preparation_moments):
            self.append_preparation_slice(circuit, moment)
            circuit.append("TICK")

    def append_preparation_slice(self, circuit: stim.Circuit, moment: int):
        match moment:
            case 0:
                circuit.append("RX", self.__shift_qubit_ids([0, 2, 6, 11]))
                circuit.append("RZ", self.__shift_qubit_ids([1, 3, 4, 5, 7, 8, 9, 10, 12, 13, 14, 15]))
            case 1:
                circuit.append("CX", self.__shift_qubit_ids([11, 7, 2, 15, 0, 14]))
            case 2:
                circuit.append("CX", self.__shift_qubit_ids([7, 10, 2, 14, 0, 15, 11, 8]))
            case 3:
                circuit.append("CX", self.__shift_qubit_ids([6, 14, 10, 7, 8, 11]))
            case 4:
                circuit.append("CX", self.__shift_qubit_ids([6, 10, 14, 9]))
            case 5:
                circuit.append("CX", self.__shift_qubit_ids([9, 13, 14, 6, 2, 10, 8, 15]))
            case 6:
                circuit.append("CX", self.__shift_qubit_ids([13, 1, 9, 14, 10, 6, 15, 3, 8, 11]))
            case 7:
                circuit.append("CX", self.__shift_qubit_ids([10, 5, 11, 8, 3, 15, 13, 9]))
                circuit.append("S_DAG", self.__shift_qubit_ids([6]))
            case 8:
                circuit.append("CX", self.__shift_qubit_ids([13, 6, 11, 4]))
            case 9:
                circuit.append("CX", self.__shift_qubit_ids([1, 13, 10, 6, 4, 11]))
            case 10:
                circuit.append("CX", self.__shift_qubit_ids([5, 10]))
            case _:
                raise ValueError(f"Invalid moment requested [moment={moment}, max=10]")

    @property
    def superdense_moments(self):
        return 15

    def append_superdense(self, circuit: stim.Circuit, postselection: bool = False):
        for moment in range(self.superdense_moments):
            self.append_superdense_slice(circuit, moment, postselection)
            circuit.append("TICK")

    def append_superdense_slice(self, circuit: stim.Circuit, moment: int, postselection: bool = False):
        match moment:
            case 0:
                circuit.append("RX", self.__shift_qubit_ids([10, 13, 15]))
                circuit.append("RZ", self.__shift_qubit_ids([7, 8, 9, 11, 12, 14]))
            case 1:
                circuit.append("CX", self.__shift_qubit_ids([10, 7, 13, 9, 15, 8]))
            case 2:
                circuit.append("CX", self.__shift_qubit_ids([7, 11, 9, 14, 8, 12]))
            case 3:
                circuit.append("CX", self.__shift_qubit_ids([11, 7, 14, 9, 12, 8]))
            case 4:
                circuit.append("CX", self.__shift_qubit_ids([10, 6, 11, 2, 14, 0, 15, 3]))
            case 5:
                circuit.append("CX", self.__shift_qubit_ids([10, 5, 11, 4, 14, 2, 15, 0]))
            case 6:
                circuit.append("CX", self.__shift_qubit_ids([12, 4, 13, 1, 14, 6, 15, 2]))
            case 7:
                circuit.append("CX", self.__shift_qubit_ids([4, 12, 1, 13, 6, 14, 2, 15]))
            case 8:
                circuit.append("CX", self.__shift_qubit_ids([5, 10, 4, 11, 2, 14, 0, 15]))
            case 9:
                circuit.append("CX", self.__shift_qubit_ids([6, 10, 2, 11, 0, 14, 3, 15]))
            case 10:
                circuit.append("CX", self.__shift_qubit_ids([7, 11, 9, 14, 8, 12]))
            case 11:
                circuit.append("CX", self.__shift_qubit_ids([10, 7, 13, 9, 15, 8]))
            case 12:
                circuit.append("CX", self.__shift_qubit_ids([7, 11, 9, 14, 8, 12]))
            case 13:
                circuit.append("CX", self.__shift_qubit_ids([10, 7, 13, 9, 15, 8]))
            case 14:
                circuit.append("MX", self.__shift_qubit_ids([10, 13, 15]))
                circuit.append("MZ", self.__shift_qubit_ids([11, 12, 14]))
                if postselection:
                    for i in range(6):
                        circuit.append("DETECTOR", [stim.target_rec(-(i+1))])
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    @property
    def cultivation_moments(self):
        return 12

    def append_cultivation(self, circuit: stim.Circuit, postselection: bool = False):
        for moment in range(self.cultivation_moments):
            self.append_cultivation_slice(circuit, moment, postselection)
            circuit.append("TICK")

    def append_cultivation_slice(self, circuit: stim.Circuit, moment: int, postselection: bool = False):
        match moment:
            case 0:
                circuit.append("S_DAG", self.logical)
                circuit.append("RX", [10, 11, 13, 14, 15])
            case 1:
                circuit.append("CX", [10, 5, 11, 4, 13, 1, 14, 2, 15, 3])
            case 2:
                circuit.append("CX", [6, 13, 2, 11, 15, 0])
            case 3:
                circuit.append("CX", [10, 6, 2, 15])
            case 4:
                circuit.append("CX", [10, 2])
            case 5:
                circuit.append("MX", [10])
                if postselection:
                    circuit.append("DETECTOR", [stim.target_rec(-1)])
            case 6:
                circuit.append("RX", [10])
            case 7:
                circuit.append("CX", [10, 2])
            case 8:
                circuit.append("CX", [10, 6, 2, 15])
            case 9:
                circuit.append("CX", [6, 13, 2, 11, 15, 0])
            case 10:
                circuit.append("CX", [10, 5, 11, 4, 13, 1, 14, 2, 15, 3])
            case 11:
                circuit.append("MX", [10, 11, 13, 14, 15])
                if postselection:
                    for i in range(5):
                        circuit.append("DETECTOR", [stim.target_rec(-(i+1))])
                circuit.append("S", self.logical)
            case _:
                raise ValueError(f"Invalid moment requested [moment={moment}, max=10]")

    @property
    def teleportation_round1_moments(self):
        return 15

    def append_teleportation_round1(self, circuit: stim.Circuit, postselection: bool = False):
        for moment in range(self.teleportation_round1_moments):
            self.append_teleportation_round1_slice(circuit, moment, postselection)
            circuit.append("TICK")

    def append_teleportation_round1_slice(self, circuit: stim.Circuit, moment: int, postselection: bool = False):
        match moment:
            # GHZ-state formation
            case 0:
                circuit.append("RX", self.__shift_qubit_ids([10, 13, 15]))
                circuit.append("RZ", self.__shift_qubit_ids([7, 8, 9, 11, 12, 14]))
            case 1:
                circuit.append("CX", self.__shift_qubit_ids([10, 7, 13, 9, 15, 8]))
            case 2:
                circuit.append("CX", self.__shift_qubit_ids([7, 11, 9, 14, 8, 12]))
            case 3:
                circuit.append("CX", self.__shift_qubit_ids([11, 7, 14, 9, 12, 8]))
            # Syndrome extractions
            case 4:
                circuit.append("CX", self.__shift_qubit_ids([10, 6, 11, 2, 15, 3]))
            case 5:
                circuit.append("CX", self.__shift_qubit_ids([10, 5, 11, 4, 15, 0]))
            case 6:
                circuit.append("CX", self.__shift_qubit_ids([12, 4, 15, 2]))
            case 7:
                circuit.append("CX", self.__shift_qubit_ids([1, 13, 2, 15, 4, 12, 6, 14]))
            case 8:
                circuit.append("CX", self.__shift_qubit_ids([0, 15, 2, 14, 4, 11, 5, 10]))
            case 9:
                circuit.append("CX", self.__shift_qubit_ids([0, 14, 2, 11, 3, 15, 6, 10]))
            # GHZ-state contraction
            case 10:
                circuit.append("CX", self.__shift_qubit_ids([7, 11, 9, 14, 8, 12]))
            case 11:
                circuit.append("CX", self.__shift_qubit_ids([10, 7, 13, 9, 15, 8]))
            case 12:
                circuit.append("CX", self.__shift_qubit_ids([7, 11, 9, 14, 8, 12]))
            case 13:
                circuit.append("CX", self.__shift_qubit_ids([10, 7, 13, 9, 15, 8]))
            case 14:
                circuit.append("MX", self.__shift_qubit_ids([10, 13, 15]))
                circuit.append("MZ", self.__shift_qubit_ids([11, 12, 14]))
                if postselection:
                    for i in range(6):
                        circuit.append("DETECTOR", [stim.target_rec(-(i+1))])
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    @property
    def teleportation_round2_moments(self):
        return 9

    def append_teleportation_round2(self, circuit: stim.Circuit, postselection: bool = False):
        for moment in range(self.teleportation_round2_moments):
            self.append_teleportation_round2_slice(circuit, moment, postselection)
            circuit.append("TICK")

    def append_teleportation_round2_slice(self, circuit: stim.Circuit, moment: int, postselection: bool = False):
        match moment:
            # GHZ-state formation
            case 0:
                circuit.append("RX", self.__shift_qubit_ids([10, 13, 15]))
                circuit.append("RZ", self.__shift_qubit_ids([7, 8, 9, 11, 12, 14]))
            case 1:
                circuit.append("CX", self.__shift_qubit_ids([10, 7, 13, 9, 15, 8]))
            case 2:
                circuit.append("CX", self.__shift_qubit_ids([7, 11, 9, 14, 8, 12, 3, 15]))
            # Syndrome extractions
            case 3:
                circuit.append("CX", self.__shift_qubit_ids([0, 14, 2, 11, 6, 10]))
            case 4:
                circuit.append("CX", self.__shift_qubit_ids([0, 15, 2, 14, 4, 11, 5, 10]))
            case 5:
                circuit.append("CX", self.__shift_qubit_ids([1, 13, 2, 15, 4, 12, 6, 14]))
            # GHZ-state contraction
            case 6:
                circuit.append("CX", self.__shift_qubit_ids([7, 11, 9, 14, 8, 12]))
            case 7:
                circuit.append("CX", self.__shift_qubit_ids([10, 7, 13, 9, 15, 8]))
            case 8:
                circuit.append("MX", self.__shift_qubit_ids([10, 13, 15]))
                if postselection:
                    for i in range(3):
                        circuit.append("DETECTOR", [stim.target_rec(-(i+1))])
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    @property
    def teleportation_round3_moments(self):
        return 6

    def append_teleportation_round3(self, circuit: stim.Circuit, postselection: bool = False):
        for moment in range(self.teleportation_round2_moments):
            self.append_teleportation_round3_slice(circuit, moment, postselection)
            circuit.append("TICK")

    def to_detector(self, support: list[int]):
        return [ stim.target_rec(-(q+1)) for q in support ]

    def append_teleportation_round3_slice(self, circuit: stim.Circuit, moment: int, postselection: bool = False):
        match moment:
            case 5:
                circuit.append("MX", self.__shift_qubit_ids(self.logical))
                if postselection:
                    logger.error("NotImplemented: Postselection in round 3 of teleportation requires XOR'ing the various MX.")
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")
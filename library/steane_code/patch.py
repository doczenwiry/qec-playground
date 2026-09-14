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
import stim
from typing import List

from library.qubit_array import QubitArray

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

    STABILIZERS = {
        'START' : {'R': [0, 2, 11, 15], 'G': [2, 6, 7, 11], 'B': [0, 14, 6, 2]},
        'FINAL' : {'R': [0, 2,  4,  3], 'G': [2, 4, 5,  6], 'B': [0,  1, 6, 2]},
    }

    PREPARATION_MOMENTS = range(11)
    SUPERDENSE_MOMENTS = range(15)
    CULTIVATION_MOMENTS = range(12)
    TELEPORTATION_MOMENTS = {
        'ROUND0' : range(15),
        'ROUND1' : range(12),
        'ROUND2' : range(6),
    }

    def __init__(self, array: QubitArray, anchor: tuple[int, int] = (0,0)):
        self.__anchor = anchor
        self.__physical_qubits = array
        px, py = anchor
        self.qubits = [ array.qubits[(px+dx, py+dy)] for dx, dy in SteaneCodePatch.QUBITS ]

    def __shift_qubit_ids(self, *qubits: int) -> List[int]:
        return list(map(lambda q : self.qubits[q], qubits))

    @property
    def logical(self) -> List[int]:
        return self.qubits[:7]

    @property
    def stabilizers(self):
        return {
            color : self.__shift_qubit_ids(*stabs)
            for color, stabs in SteaneCodePatch.STABILIZERS['FINAL'].items()
        }

    def __get_polygons(self, stabilizers: dict[str, list[int]]):
        polygons = []
        for color, support in stabilizers.items():
            x, y, z = int(color == 'R'), int(color == 'G'), int(color == 'B')
            polygons.append(
                f"#!pragma POLYGON({x},{y},{z},0.5) {" ".join(
                    map(str, self.__shift_qubit_ids(*support))
                )}\n"
            )
        return polygons

    def get_initial_polygons(self):
        return self.__get_polygons(SteaneCodePatch.STABILIZERS['START'])

    def get_prepared_polygons(self):
        return self.__get_polygons(SteaneCodePatch.STABILIZERS['FINAL'])

    def annotate_detectors(self, circuit: stim.Circuit, sdc_rounds: int = 0, tpt_rounds: int = 0):
        # Annotate all SUPERDENSE detectors
        for color in self.stabilizers.keys():
            if sdc_rounds >= 1:
                self.annotate_detector(circuit, f"SDC0:X{color}")
                self.annotate_detector(circuit, f"SDC0:Z{color}")
            for prev, curr in itertools.pairwise(range(sdc_rounds)):
                self.annotate_detector(circuit, f"SDC{curr}:Z{color}", f"SDC{prev}:Z{color}")

        for prev, curr in itertools.pairwise(range(sdc_rounds)):
            self.annotate_detector(circuit, f"SDC{curr}:XR")
            self.annotate_detector(circuit, f"SDC{curr}:XG", f"SDC{prev}:XR", f"SDC{prev}:XG")
            self.annotate_detector(circuit, f"SDC{curr}:XB", f"SDC{prev}:XG")

        # Annotate the CULTIVATION detectors
        for measurement in range(6):
            self.annotate_detector(circuit, f"CULT:X{measurement}")

        # Annotate the TELEPORTATION stabilized detectors
        last = sdc_rounds-1
        for color in self.stabilizers.keys():
            self.annotate_detector(circuit, f"TPRT0:Z{color}", f"SDC{last}:Z{color}")
            if tpt_rounds > 1:
                self.annotate_detector(circuit, f"TPRT1:Z{color}", f"TPRT0:Z{color}")
        self.annotate_detector(circuit, f"TPRT0:XR", f"SDC{last}:ZR")
        self.annotate_detector(circuit, f"TPRT0:XG", f"SDC{last}:ZG", f"SDC{last}:ZR")
        self.annotate_detector(circuit, f"TPRT0:XB")

        # Annotate the TELEPORTATION destructive detectors
        self.annotate_detector(
            circuit, *map(lambda q: f"TPRT2:X{q}", SteaneCodePatch.STABILIZERS['FINAL']['G'])
        )
        # TODO: fix this one
        # self.annotate_detector(
        #     circuit, *map(lambda q: f"TPRT2:X{q}", SteaneCodePatch.STABILIZERS['FINAL']['R'])
        # )

    def annotate_detector(self, circuit: stim.Circuit, *labels: str) -> bool:
        if all(self.__physical_qubits.has_record(label) for label in labels):
            circuit.append(
                "DETECTOR", map(self.__physical_qubits.retrieve_target_rec, labels)
            )
            return True
        return False

    def append_observable(self, circuit: stim.Circuit, observable: str, support: list[int]):
        circuit.append("MPP", stim.PauliString(
            "*".join(map(lambda q: observable + str(q), support))
        ))
        circuit.append("OBSERVABLE_INCLUDE", [stim.target_rec(-1)], 0)
        circuit.append("TICK")

    def append_preparation(self, circuit: stim.Circuit):
        for moment in self.PREPARATION_MOMENTS:
            self.append_preparation_slice(circuit, moment)
            circuit.append("TICK")

    def append_preparation_slice(self, circuit: stim.Circuit, moment: int):
        match moment:
            case 0:
                circuit.append("RX", self.__shift_qubit_ids(0, 2, 6, 11))
                circuit.append("RZ", self.__shift_qubit_ids(1, 3, 4, 5, 7, 8, 9, 10, 12, 13, 14, 15))
            case 1:
                circuit.append("CX", self.__shift_qubit_ids(11, 7, 2, 15, 0, 14))
            case 2:
                circuit.append("CX", self.__shift_qubit_ids(7, 10, 2, 14, 0, 15, 11, 8))
            case 3:
                circuit.append("CX", self.__shift_qubit_ids(6, 14, 10, 7, 8, 11))
            case 4:
                circuit.append("CX", self.__shift_qubit_ids(6, 10, 14, 9))
            case 5:
                circuit.append("CX", self.__shift_qubit_ids(9, 13, 14, 6, 2, 10, 8, 15))
            case 6:
                circuit.append("CX", self.__shift_qubit_ids(13, 1, 9, 14, 10, 6, 15, 3, 8, 11))
            case 7:
                circuit.append("CX", self.__shift_qubit_ids(10, 5, 11, 8, 3, 15, 13, 9))
                circuit.append("S_DAG", self.__shift_qubit_ids(6))
            case 8:
                circuit.append("CX", self.__shift_qubit_ids(13, 6, 11, 4))
            case 9:
                circuit.append("CX", self.__shift_qubit_ids(1, 13, 10, 6, 4, 11))
            case 10:
                circuit.append("CX", self.__shift_qubit_ids(5, 10))
            case _:
                raise ValueError(f"Invalid moment requested [moment={moment}, max=10]")

    def append_superdense(self, circuit: stim.Circuit, prefix: str = "SDC"):
        for moment in self.SUPERDENSE_MOMENTS:
            self.append_superdense_slice(circuit, moment, prefix)
            circuit.append("TICK")

    def append_superdense_slice(
            self, circuit: stim.Circuit, moment: int, prefix: str = "SDC"
    ):
        match moment:
            case 0:
                circuit.append("RX", self.__shift_qubit_ids(10, 13, 15))
                circuit.append("RZ", self.__shift_qubit_ids(7, 8, 9, 11, 12, 14))
            case 1:
                circuit.append("CX", self.__shift_qubit_ids(10, 7, 13, 9, 15, 8))
            case 2:
                circuit.append("CX", self.__shift_qubit_ids(7, 11, 9, 14, 8, 12))
            case 3:
                circuit.append("CX", self.__shift_qubit_ids(11, 7, 14, 9, 12, 8))
            case 4:
                circuit.append("CX", self.__shift_qubit_ids(10, 6, 11, 2, 14, 0, 15, 3))
            case 5:
                circuit.append("CX", self.__shift_qubit_ids(10, 5, 11, 4, 14, 2, 15, 0))
            case 6:
                circuit.append("CX", self.__shift_qubit_ids(12, 4, 13, 1, 14, 6, 15, 2))
            case 7:
                circuit.append("CX", self.__shift_qubit_ids(4, 12, 1, 13, 6, 14, 2, 15))
            case 8:
                circuit.append("CX", self.__shift_qubit_ids(5, 10, 4, 11, 2, 14, 0, 15))
            case 9:
                circuit.append("CX", self.__shift_qubit_ids(6, 10, 2, 11, 0, 14, 3, 15))
            case 10:
                circuit.append("CX", self.__shift_qubit_ids(7, 11, 9, 14, 8, 12))
            case 11:
                circuit.append("CX", self.__shift_qubit_ids(10, 7, 13, 9, 15, 8))
            case 12:
                circuit.append("CX", self.__shift_qubit_ids(7, 11, 9, 14, 8, 12))
            case 13:
                circuit.append("CX", self.__shift_qubit_ids(10, 7, 13, 9, 15, 8))
            case 14:
                measured_x_ancilla = self.__shift_qubit_ids(10, 13, 15)
                circuit.append("MX", measured_x_ancilla)
                for xa, color in zip(measured_x_ancilla, ["G" , "B", "R"]):
                    self.__physical_qubits.record_measurement(xa, f"{prefix}:X{color}")
                measured_z_ancilla = self.__shift_qubit_ids(11, 12, 14)
                circuit.append("MZ", measured_z_ancilla)
                for za, color in zip(measured_z_ancilla, ["G" , "R", "B"]):
                    self.__physical_qubits.record_measurement(za, f"{prefix}:Z{color}")
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    def append_cultivation(
            self, circuit: stim.Circuit, prefix: str = "CULT"
    ):
        for moment in self.CULTIVATION_MOMENTS:
            self.append_cultivation_slice(circuit, moment, prefix)
            circuit.append("TICK")

    def append_cultivation_slice(
            self, circuit: stim.Circuit, moment: int, prefix: str = "CULT"
    ):
        match moment:
            case 0:
                circuit.append("S_DAG", self.logical)
                circuit.append("RX", self.__shift_qubit_ids(10, 11, 13, 14, 15))
            case 1:
                circuit.append("CX", self.__shift_qubit_ids(10, 5, 11, 4, 13, 1, 14, 2, 15, 3))
            case 2:
                circuit.append("CX", self.__shift_qubit_ids(6, 13, 2, 11, 15, 0))
            case 3:
                circuit.append("CX", self.__shift_qubit_ids(10, 6, 2, 15))
            case 4:
                circuit.append("CX", self.__shift_qubit_ids(10, 2))
            case 5:
                circuit.append("MX", self.__shift_qubit_ids(10))
                self.__physical_qubits.record_measurement(*self.__shift_qubit_ids(10), f"{prefix}:X0")
            case 6:
                circuit.append("RX", self.__shift_qubit_ids(10))
            case 7:
                circuit.append("CX", self.__shift_qubit_ids(10, 2))
            case 8:
                circuit.append("CX", self.__shift_qubit_ids(10, 6, 2, 15))
            case 9:
                circuit.append("CX", self.__shift_qubit_ids(6, 13, 2, 11, 15, 0))
            case 10:
                circuit.append("CX", self.__shift_qubit_ids(10, 5, 11, 4, 13, 1, 14, 2, 15, 3))
            case 11:
                measured_ancilla = self.__shift_qubit_ids(10, 11, 13, 14, 15)
                circuit.append("MX", measured_ancilla)
                for index, xa in enumerate(measured_ancilla):
                    self.__physical_qubits.record_measurement(xa, f"{prefix}:X{index+1}")
                circuit.append("S", self.logical)
            case _:
                raise ValueError(f"Invalid moment requested [moment={moment}, max=10]")

    def append_teleportation(self, circuit: stim.Circuit, round: int, prefix: str = "TPRT"):
        for moment in self.TELEPORTATION_MOMENTS[f"ROUND{round}"]:
            self.append_teleportation_slice(circuit, moment, round, prefix)
            circuit.append("TICK")

    def append_teleportation_slice(self, circuit: stim.Circuit, moment: int, round: int, prefix: str = "TPRT"):
        match round:
            case 0:
                self.__append_teleportation_round0_slice(circuit, moment, prefix)
            case 1:
                self.__append_teleportation_round1_slice(circuit, moment, prefix)
            case 2:
                self.__append_teleportation_round2_slice(circuit, moment, prefix)
            case _:
                raise ValueError(f"Invalid teleportation round requested [round={round}]")

    def __append_teleportation_round0_slice(self, circuit: stim.Circuit, moment: int, prefix: str = "TPRT"):
        match moment:
            # GHZ-state formation
            case 0:
                circuit.append("RX", self.__shift_qubit_ids(10, 13, 15))
                circuit.append("RZ", self.__shift_qubit_ids(7, 8, 9, 11, 12, 14))
            case 1:
                circuit.append("CX", self.__shift_qubit_ids(10, 7, 13, 9, 15, 8))
            case 2:
                circuit.append("CX", self.__shift_qubit_ids(7, 11, 9, 14, 8, 12))
            case 3:
                circuit.append("CX", self.__shift_qubit_ids(11, 7, 14, 9, 12, 8))
            # X-syndrome extractions
            case 4:
                circuit.append("CX", self.__shift_qubit_ids(10, 6, 11, 2, 15, 3))
            case 5:
                circuit.append("CX", self.__shift_qubit_ids(10, 5, 11, 4, 15, 0))
            case 6:
                circuit.append("CX", self.__shift_qubit_ids(12, 4, 15, 2))
            # Z-syndrome extractions
            case 7:
                circuit.append("CX", self.__shift_qubit_ids(1, 13, 2, 15, 4, 12, 6, 14))
            case 8:
                circuit.append("CX", self.__shift_qubit_ids(0, 15, 2, 14, 4, 11, 5, 10))
            case 9:
                circuit.append("CX", self.__shift_qubit_ids(0, 14, 2, 11, 3, 15, 6, 10))
            # GHZ-state contraction
            case 10:
                circuit.append("CX", self.__shift_qubit_ids(7, 11, 9, 14, 8, 12))
            case 11:
                circuit.append("CX", self.__shift_qubit_ids(10, 7, 13, 9, 15, 8))
            case 12:
                circuit.append("CX", self.__shift_qubit_ids(7, 11, 9, 14, 8, 12))
            case 13:
                circuit.append("CX", self.__shift_qubit_ids(10, 7, 13, 9, 15, 8))
            case 14:
                measured_x_ancilla = self.__shift_qubit_ids(10, 13, 15)
                circuit.append("MX", measured_x_ancilla)
                for xa, color in zip(measured_x_ancilla, ["G" , "B", "R"]):
                    self.__physical_qubits.record_measurement(xa, f"{prefix}0:X{color}")
                measured_z_ancilla = self.__shift_qubit_ids(11, 12, 14)
                circuit.append("MZ", measured_z_ancilla)
                for za, color in zip(measured_z_ancilla, ["G" , "R", "B"]):
                    self.__physical_qubits.record_measurement(za, f"{prefix}0:Z{color}")
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    def append_teleportation_round1(self, circuit: stim.Circuit, prefix: str = "TPRT"):
        for moment in self.TELEPORTATION_MOMENTS['ROUND1']:
            self.__append_teleportation_round1_slice(circuit, moment, prefix)
            circuit.append("TICK")

    def __append_teleportation_round1_slice(self, circuit: stim.Circuit, moment: int, prefix: str = "TPRT"):
        match moment:
            # GHZ-state formation
            case 0:
                circuit.append("RX", self.__shift_qubit_ids(10, 13, 15))
                circuit.append("RZ", self.__shift_qubit_ids(7, 8, 9, 11, 12, 14))
            case 1:
                circuit.append("CX", self.__shift_qubit_ids(10, 7, 13, 9, 15, 8))
            case 2:
                circuit.append("CX", self.__shift_qubit_ids(7, 11, 9, 14, 8, 12))
            case 3:
                circuit.append("CX", self.__shift_qubit_ids(11, 7, 14, 9, 12, 8))
            # Syndrome extractions
            case 4:
                circuit.append("CX", self.__shift_qubit_ids(0, 14, 2, 11, 6, 10))
            case 5:
                circuit.append("CX", self.__shift_qubit_ids(0, 15, 2, 14, 4, 11, 5, 10))
            case 6:
                circuit.append("CX", self.__shift_qubit_ids(1, 13, 2, 15, 4, 12, 6, 14))
            # GHZ-state contraction
            case 7:
                circuit.append("CX", self.__shift_qubit_ids(7, 11, 9, 14, 8, 12))
            case 8:
                circuit.append("CX", self.__shift_qubit_ids(10, 7, 13, 9, 15, 8))
            case 9:
                circuit.append("CX", self.__shift_qubit_ids(7, 11, 9, 14, 8, 12))
            case 10:
                circuit.append("CX", self.__shift_qubit_ids(10, 7, 13, 9, 15, 8))
            case 11:
                measured_z_ancilla = self.__shift_qubit_ids(10, 13, 15)
                circuit.append("MX", measured_z_ancilla)
                for za, color in zip(measured_z_ancilla, ["G" , "B", "R"]):
                    self.__physical_qubits.record_measurement(za, f"{prefix}1:Z{color}")
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    def append_teleportation_round2(self, circuit: stim.Circuit, prefix: str = "TPRT"):
        for moment in self.TELEPORTATION_MOMENTS['ROUND2']:
            self.__append_teleportation_round2_slice(circuit, moment, prefix)
            circuit.append("TICK")

    def __append_teleportation_round2_slice(self, circuit: stim.Circuit, moment: int, prefix: str = "TPRT"):
        match moment:
            case 5:
                measured_data_qubits = self.logical
                circuit.append("MX", measured_data_qubits)
                for index, qd in enumerate(measured_data_qubits):
                    self.__physical_qubits.record_measurement(qd, f"{prefix}2:X{index}")
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")
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

from typing import Optional

import itertools
import stim

from library.circuitry import Circuitry
from library.qubit_array import QubitArray
from library.surface_code.patch import SurfaceCodePatch
from library.common import Pauli


class ExpansionSurgery:
    """Implements a left-upwards expansion."""
    def __init__(
        self, qubits: QubitArray, source: SurfaceCodePatch, target: SurfaceCodePatch
    ):
        if source.coloring != target.coloring:
            raise ValueError("Source and target must have the same coloring [i.e. red/blue pattern].")
        self.__coloring = source.coloring

        self.__expansion = target.distance - source.distance
        sx, sy = source.anchor
        tx, ty = target.anchor

        if tx + self.__expansion != sx or ty + self.__expansion != sy:
            raise ValueError(f"Source and target must have compatible anchors & distances.")

        self.__qubits = qubits
        self.__distance = target.distance

        self.__source = source
        self.__target = target
        # self.__source_inactive = lambda ql: ql[0] == sx + self.__distance - 0.5
        # self.__target_inactive = lambda ql: ql[0] == tx - 0.5

    def __qubit_in_expansion(self, px: float, py: float) -> bool:
        tx, ty = self.__target.anchor
        return not(px >= tx + self.__expansion and py >= ty + self.__expansion)

    def append_expansion(self, circuit: Circuitry):
        circuit.annotate_polygons(self.__target.get_polygons(opacity=0.125))
        circuit.annotate_polygons(self.__source.get_polygons(opacity=0.25))

        # Handle the reset of the data qubits
        rx_data_qubits = []
        rz_data_qubits = []
        tx, ty = self.__target.anchor
        for (px,py), (qd, _) in self.__target.qubits['D'].items():
            if not self.__qubit_in_expansion(px, py):
                continue
            if px - tx >= py - ty:  # Above the diagonal must be RX'd
                rx_data_qubits.append(qd)
            else:  # Below the diagonal must be RZ'd
                rz_data_qubits.append(qd)
        circuit.append("RX", rx_data_qubits)
        circuit.append("RZ", rz_data_qubits)

        for rnd in range(self.__distance):
            for mmt in SurfaceCodePatch.MOMENTS:
                self.__target.append_round(circuit, mmt, prefix=f"TGT:EXP:R{rnd}")
                circuit.append_tick()

        circuit.annotate_polygons(self.__target.get_polygons(opacity=0.25))

    def annotate_detectors(self, circuitry: Circuitry, prefix: str = "TGT:EXP", preceding: Optional[str] = None):
        tx, ty = self.__target.anchor
        last = self.__distance - 1
        for stabilizer in ['X', 'Z']:
            for (px, py), (qa, qi) in self.__target.qubits[stabilizer].items():
                if self.__qubit_in_expansion(px, py):
                    if stabilizer == 'X' and px - tx > py - ty:
                        if py - ty < self.__expansion - 1:
                            circuitry.annotate_detector(f"{prefix}:R0:{stabilizer}{qi}")
                        # elif py - ty == self.__expansion - 0.5:
                        #     qti = self.__target.get_qubit_index(stabilizer, qa)
                        #     print(f"QTI: {prefix}:R0:{stabilizer}{qi} -> {qti}")
                    elif stabilizer == "Z" and px - tx < py - ty:
                        if px - tx < self.__expansion - 1:
                            circuitry.annotate_detector(f"{prefix}:R0:{stabilizer}{qi}")
                        # elif px - tx == self.__expansion - 0.5:
                        #     qti = self.__target.get_qubit_index(stabilizer, qa)
                        #     print(f"QSI: {prefix}:R0:{stabilizer}{qi} -> {qti}")
                for prev, curr in itertools.pairwise(range(self.__distance)):
                    circuitry.annotate_detector(
                        f"{prefix}:R{curr}:{stabilizer}{qi}",
                        f"{prefix}:R{prev}:{stabilizer}{qi}",
                    )
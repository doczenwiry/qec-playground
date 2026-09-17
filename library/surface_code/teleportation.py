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

import stim

from library.circuitry import Circuitry
from library.qubit_array import QubitArray
from library.surface_code.patch import SurfaceCodePatch, PauliBasis


class TeleportationSurgery:
    def __init__(self, qubits: QubitArray, distance: int = 3, anchor: tuple[int,int] = (1,1)):
        self.__distance = distance
        self.__physical_qubits = qubits
        sx, sy = anchor
        tx, ty = sx + distance + 1, sy
        jx, jy = sx + distance - 1, sy
        self.__source = SurfaceCodePatch(qubits, distance, anchor)
        self.__target = SurfaceCodePatch(qubits, distance, (tx, ty))
        self.__merger = SurfaceCodePatch(qubits, distance,  (jx, jy))
        self.__source_inactive = lambda ql : ql[0] == sx + distance - 0.5
        self.__target_inactive = lambda ql : ql[0] == tx - 0.5
        self.__merger_inactive = lambda ql : not(jx + 0.5 <= ql[0] < jx + 2)

    @property
    def source(self):
        return self.__source

    @property
    def target(self):
        return self.__target

    def append_movement(
            self, circuit: Circuitry, prepare: Optional[PauliBasis] = None, measure: Optional[PauliBasis] = None,
            full_ft: bool = True
    ):
        circuit.annotate_polygons(self.__source.get_polygons())
        self.__source.append_memory(circuit, memory=0, prepare=prepare, full_ft=full_ft, prefix="S")

        circuit.annotate_polygons(self.__source.get_polygons(self.__source_inactive))
        circuit.annotate_polygons(self.__merger.get_polygons(self.__merger_inactive))
        circuit.annotate_polygons(self.__target.get_polygons(self.__target_inactive))

        start_round = 0
        final_round = self.__distance - 1
        for rnd in range(self.__distance if full_ft else 1):
            for mmt in SurfaceCodePatch.MOMENTS:
                self.__source.append_round_slice(
                    circuit, mmt,
                    measure=PauliBasis.Z if (not full_ft or rnd == final_round) else None,
                    inactive=self.__source_inactive,
                    prefix=f"S:M1:R{rnd}"
                )
                self.__merger.append_round_slice(
                    circuit, mmt,
                    prepare=PauliBasis.Z if (not full_ft or rnd == start_round) else None,
                    measure=PauliBasis.Z if (not full_ft or rnd == final_round) else None,
                    inactive=self.__merger_inactive,
                    prefix=f"M:M1:R{rnd}"
                )
                self.__target.append_round_slice(
                    circuit, mmt,
                    prepare=PauliBasis.Z if (not full_ft or rnd == start_round) else None,
                    inactive=self.__target_inactive,
                    prefix=f"T:M1:R{rnd}"
                )
                circuit.append_tick()

        circuit.annotate_polygons(self.__target.get_polygons())
        self.__target.append_memory(circuit, memory=2, measure=measure, full_ft=full_ft, prefix="T")

    def locate_measurement(self, label: str):
        if label.startswith("S"):
            patch = self.__source
        elif label.startswith("M"):
            patch = self.__merger
        elif label.startswith("T"):
            patch = self.__target
        else:
            raise ValueError("Invalid label provided.")

        return patch.locate_qubit(label.split(":")[-1])

    def annotate_observable(self, circuit: Circuitry, identifier: int, *labels: str):
        circuit.append(
            "OBSERVABLE_INCLUDE",
            [ stim.target_rec(self.__physical_qubits.retrieve_measurement(label)) for label in labels ],
            identifier
        )
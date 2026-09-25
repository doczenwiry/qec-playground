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


class TeleportationSurgery:
    def __init__(
        self, qubits: QubitArray, source: SurfaceCodePatch, target: SurfaceCodePatch,
    ):
        if source.distance != target.distance:
            raise ValueError("source and target must have the same code distance.")

        if source.coloring != target.coloring:
            raise ValueError("source and target must have the same coloring [i.e. red/blue pattern].")

        sx, sy = source.anchor
        tx, ty = target.anchor

        if tx != sx + source.distance + 1 or ty != sy:
            raise ValueError("Source and target must have compatible anchors.")

        self.__coloring = source.coloring
        self.__distance = source.distance
        self.__physical_qubits = qubits

        # tx, ty = sx + distance + 1, sy
        jx, jy = sx + self.__distance - 1, sy
        self.source = source
        self.__source_inactive = lambda ql: ql[0] == sx + self.__distance - 0.5
        self.target = target
        self.__target_inactive = lambda ql: ql[0] == tx - 0.5

        self.__merger = SurfaceCodePatch(qubits, self.__distance, (jx, jy), self.__coloring)
        self.__merger_inactive = lambda ql: not (jx + 0.5 <= ql[0] < jx + 2)

    def annotate_polygons(self, circuitry: Circuitry, during: bool):
        if during:
            circuitry.annotate_polygons(self.source.get_polygons(self.__source_inactive))
            circuitry.annotate_polygons(self.__merger.get_polygons(self.__merger_inactive))
            circuitry.annotate_polygons(self.target.get_polygons(self.__target_inactive))
        else:
            circuitry.annotate_polygons(self.target.get_polygons())

    def append_movement(self, circuit: Circuitry, prefix: str = "TPT"):
        transition = Pauli.Z if self.__coloring else Pauli.X

        start_round = 0
        final_round = self.__distance - 1
        for rnd in range(self.__distance):
            for mmt in SurfaceCodePatch.MOMENTS:
                self.source.append_round(
                    circuit,
                    mmt,
                    measure=transition if rnd == final_round else None,
                    inactive=self.__source_inactive,
                    prefix=f"{prefix}:SRC:R{rnd}",
                )
                self.__merger.append_round(
                    circuit,
                    mmt,
                    prepare=transition if rnd == start_round else None,
                    measure=transition if rnd == final_round else None,
                    inactive=self.__merger_inactive,
                    prefix=f"{prefix}:JCT:R{rnd}",
                )
                self.target.append_round(
                    circuit,
                    mmt,
                    prepare=transition if rnd == start_round else None,
                    inactive=self.__target_inactive,
                    prefix=f"{prefix}:TGT:R{rnd}",
                )
                circuit.append_tick()

    def annotate_detectors(
        self,
        circuitry: Circuitry,
        prefix: str = "TPT"
    ):
        self.source.annotate_detectors(
            circuitry, prefix=f"{prefix}:SRC", measured=Pauli.Z,inactive=self.__source_inactive
        )
        self.target.annotate_detectors(
            circuitry, prefix=f"{prefix}:TGT", prepared=Pauli.Z,inactive=self.__target_inactive
        )

        # TODO: complete annotation of detectors for merger
        # self.__merger.annotate_detectors(
        #     circuitry, prefix=f"{prefix}:JCT", prepared=Pauli.Z, measured=Pauli.Z, inactive=self.__merger_inactive,
        # )

        # circuitry.annotate_detector(
        #     f"{prefix}:JCT:R{last}:Z0",
        #     f"{prefix}:SRC:R{last}:D6", f"{prefix}:SRC:R{last}:D7",
        #     f"{prefix}:JCT:R{last}:D3", f"{prefix}:JCT:R{last}:D4"
        # )

    def annotate_observable(self, circuit: Circuitry, identifier: int, *labels: str):
        circuit.append(
            "OBSERVABLE_INCLUDE",
            [
                stim.target_rec(self.__physical_qubits.retrieve_measurement(label))
                for label in labels
            ],
            identifier,
        )

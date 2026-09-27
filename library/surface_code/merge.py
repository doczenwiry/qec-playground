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

from library import circuitry
from library.circuitry import Circuitry
from library.qubit_array import QubitArray
from library.surface_code.patch import SurfaceCodePatch
from library.common import Pauli


class MergeSurgery:
    def __init__(
        self, qubits: QubitArray, source: SurfaceCodePatch, target: SurfaceCodePatch
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

        jx, jy = sx + self.__distance - 1, sy
        self.source = source
        self.__source_inactive = lambda ql: ql[0] == sx + self.__distance - 0.5
        self.target = target
        self.__target_inactive = lambda ql: ql[0] == tx - 0.5

        self.merger = SurfaceCodePatch(qubits, self.__distance, (jx, jy), self.__coloring)
        self.__merger_inactive = lambda ql: not (jx + 0.5 <= ql[0] < jx + 2)

    def annotate_polygons(self, circuitry: Circuitry):
        circuitry.annotate_polygons(self.source.get_polygons(self.__source_inactive))
        circuitry.annotate_polygons(self.merger.get_polygons(self.__merger_inactive))
        circuitry.annotate_polygons(self.target.get_polygons(self.__target_inactive))

    def append_merge(
        self,
        circuitry: Circuitry,
        prefix: str = "MRG",
        rounds: Optional[int] = None,
    ):
        transition = Pauli.Z if self.__coloring else Pauli.X

        start_round = 0
        final_round = (rounds or self.__distance) - 1
        for rnd in range(rounds or self.__distance):
            for mmt in SurfaceCodePatch.MOMENTS:
                self.source.append_round(
                    circuitry, mmt, inactive=self.__source_inactive,
                    prefix=f"{prefix}:SRC:R{rnd}",
                )
                self.merger.append_round(
                    circuitry, mmt, inactive=self.__merger_inactive,
                    prefix=f"{prefix}:JCT:R{rnd}",
                    prepare=transition if rnd == start_round else None,
                    measure=transition if rnd == final_round else None,
                )
                self.target.append_round(
                    circuitry, mmt, inactive=self.__target_inactive,
                    prefix=f"{prefix}:TGT:R{rnd}",
                )
                circuitry.append_tick()

    def annotate_detectors(
        self,
        circuitry: Circuitry,
        preceding: tuple[str,str],
        following: tuple[str,str],
        prefix: str = "MRG",
    ):
        self.source.annotate_detectors(
            circuitry, prefix=f"{prefix}:SRC", inactive=self.__source_inactive
        )
        self.target.annotate_detectors(
            circuitry, prefix=f"{prefix}:TGT", inactive=self.__target_inactive
        )
        self.merger.annotate_detectors(
            circuitry, prefix=f"{prefix}:JCT", inactive=self.__merger_inactive
        )

        last = self.__distance - 1

        preceding_source, preceding_target = preceding
        following_source, following_target = following
        for stabilizer in ["X", "Z"]:
            # Annotate the detectors across the source and the merger
            for ql, (qa, qi) in self.source.qubits[stabilizer].items():
                if self.__source_inactive(ql):
                    continue
                circuitry.annotate_detector(
                    f"{prefix}:SRC:R0:{stabilizer}{qi}", f"{preceding_source}:R{last}:{stabilizer}{qi}"
                )
                circuitry.annotate_detector(
                    f"{prefix}:SRC:R{last}:{stabilizer}{qi}", f"{following_source}:R0:{stabilizer}{qi}"
                )
            # Annotate the detectors across the merger and the target
            for ql, (qa, qi) in self.target.qubits[stabilizer].items():
                if self.__target_inactive(ql):
                    continue
                circuitry.annotate_detector(
                    f"{prefix}:TGT:R0:{stabilizer}{qi}", f"{preceding_target}:R{last}:{stabilizer}{qi}"
                )
                circuitry.annotate_detector(
                    f"{prefix}:TGT:R{last}:{stabilizer}{qi}", f"{following_target}:R0:{stabilizer}{qi}"
                )

        transition = Pauli.Z if self.__coloring else Pauli.X
        for ql, (qa, qi) in self.merger.qubits[transition.name].items():
            if self.__merger_inactive(ql):
                continue

            px, py = ql
            jx, jy = self.merger.anchor
            # Annotate the detectors on the side of the source
            if ql[0] == jx + 0.5:
                qsi = self.source.get_qubit_index(stabilizer, qa)
                circuitry.annotate_detector(
                    f"{prefix}:JCT:R0:{stabilizer}{qi}", f"{preceding_source}:R{last}:{stabilizer}{qsi}"
                )
                circuitry.annotate_detector(
                    f"{prefix}:JCT:R{last}:{stabilizer}{qi}", f"{following_source}:R0:{stabilizer}{qsi}",
                    *(f"{prefix}:JCT:R{last}:D{self.merger.get_qubit_index('D', self.__physical_qubits[(px+dx, py+dy)])}"
                    for dx, dy in [ (+0.5, -0.5), (+0.5, +0.5) ])
                )

            # Annotate the detectors on the side of the target
            elif ql[0] == jx + 1.5:
                qti = self.target.get_qubit_index(stabilizer, qa)
                circuitry.annotate_detector(
                    f"{prefix}:JCT:R0:{stabilizer}{qi}", f"{preceding_target}:R{last}:{stabilizer}{qti}"
                )
                circuitry.annotate_detector(
                    f"{prefix}:JCT:R{last}:{stabilizer}{qi}", f"{following_target}:R0:{stabilizer}{qti}",
                    *(f"{prefix}:JCT:R{last}:D{self.merger.get_qubit_index('D', self.__physical_qubits[(px+dx, py+dy)])}"
                    for dx, dy in [ (-0.5, -0.5), (-0.5, +0.5) ])
                )

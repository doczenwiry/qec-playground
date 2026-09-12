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

from collections import Counter
from typing import Optional

import stim

from library.qubit_array import QubitArray
from library.surface_code_patch import SurfaceCodePatch, PauliBasis


class MovingSurfaceCodePatch:
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
        self.__instructions = Counter()

    @property
    def source(self):
        return self.__source

    @property
    def target(self):
        return self.__target

    def rewrite_with_polygons(self, filename: str):
        # Insert all the polygons into the Stim file for readability.
        with open(filename, "r", encoding="utf-8") as file:
            lines = file.readlines()
            inserted = 0

            # Insert polygons for the source surface code patch
            for polygon in self.__source.get_polygons():
                lines.insert(self.__instructions['source'] + inserted, polygon)
                inserted += 1
            lines.insert(self.__instructions['source'] + inserted, "TICK\n")
            inserted += 1

            # Insert polygons for the source+merger+target surface code patches
            for surface, inactive in [
                (self.__source, self.__source_inactive),
                (self.__target, self.__target_inactive),
                (self.__merger, self.__merger_inactive)
            ]:
                for polygon in surface.get_polygons(inactive):
                    lines.insert(self.__instructions['merger'] + inserted, polygon)
                    inserted += 1
            lines.insert(self.__instructions['merger'] + inserted, "TICK\n")
            inserted += 1

            # Insert polygons for the target surface code patch
            for polygon in self.__target.get_polygons():
                lines.insert(self.__instructions['target'] + inserted, polygon)
                inserted += 1
            lines.insert(self.__instructions['target'] + inserted, "TICK\n")
            inserted += 1

        with open(filename, "w", encoding="utf-8") as file:
            file.writelines(lines)
            print(f"Generated circuit : {filename}")

    def append_movement(
            self, circuit: stim.Circuit, prepare: Optional[PauliBasis] = None, measure: Optional[PauliBasis] = None,
            full_ft: bool = True
    ):
        self.__instructions['source'] = len(circuit)
        if full_ft:
            self.__source.append_memory(circuit, prepare=prepare)
        else:
            self.__source.append_round(circuit, prepare=prepare)

        start_round = 0
        final_round = self.__distance - 1
        self.__instructions['merger'] = len(circuit)
        for rnd in range(self.__distance if full_ft else 1):
            for mmt in SurfaceCodePatch.MOMENTS:
                self.__source.append_round_slice(
                    circuit, mmt,
                    measure=PauliBasis.Z if (not full_ft or rnd == final_round) else None,
                    inactive=self.__source_inactive
                )
                self.__merger.append_round_slice(
                    circuit, mmt,
                    prepare=PauliBasis.Z if (not full_ft or rnd == start_round) else None,
                    measure=PauliBasis.Z if (not full_ft or rnd == final_round) else None,
                    inactive=self.__merger_inactive
                )
                self.__target.append_round_slice(
                    circuit, mmt,
                    prepare=PauliBasis.Z if (not full_ft or rnd == start_round) else None,
                    inactive=self.__target_inactive
                )
                circuit.append("TICK")

        self.__instructions['target'] = len(circuit)
        if full_ft:
            self.__target.append_memory(circuit, measure=measure)
        else:
            self.__target.append_round(circuit, measure=measure)
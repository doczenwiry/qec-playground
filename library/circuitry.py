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

from collections import defaultdict
from typing import Union, Iterable, Optional

import stim


class Circuitry:
    """A wrapper to easily move between Stim and Clifft when switching between Clifford and non-Clifford."""
    def __init__(self, clifford: bool = True):
        if not clifford:
            raise NotImplementedError("Non-Clifford circuit not supported yet.")
        self.__clifford = clifford
        self.__circuit: stim.Circuit = stim.Circuit()
        self.__polygons: dict[int, list[str]] = defaultdict(list)

    @property
    def is_clifford(self):
        return self.__clifford

    @property
    def as_stim(self):
        if self.__clifford:
            return self.__circuit
        else:
            raise ValueError("Circuit is non-Clifford and not supported by STIM.")

    @property
    def num_qubits(self):
        if not self.__clifford:
            raise ValueError("Non-Clifford circuit not supported yet.")

        used_qubits = set()
        for instruction in self.as_stim.flattened():
            if instruction.name not in ("QUBIT_COORDS", "DETECTOR", "OBSERVABLE_INCLUDE"):
                used_qubits.update(instruction.targets_copy())

        return len(used_qubits)

    @property
    def num_cnots(self):
        return sum(
            len(instruction.targets_copy()) // 2
            for instruction in self.as_stim.flattened() if instruction.name == "CX"
        )

    @property
    def num_measurements(self):
        return self.as_stim.num_measurements

    @property
    def num_detectors(self):
        return self.as_stim.num_detectors

    def __len__(self):
        return len(self.__circuit) if self.__clifford else -1

    def to_file(self, filename: str, polygons: bool = True, spacing: bool = False):
        self.__circuit.to_file(filename)

        if polygons:
            with open(filename, "r", encoding="utf-8") as file:
                lines = file.readlines()
                inserted = 0

                # Insert all registered polygons where they belong
                for line_number, polygons in self.__polygons.items():
                    for polygon in polygons:
                        lines.insert(line_number + inserted, polygon)
                        inserted += 1
                    if spacing:
                        lines.insert(line_number + inserted, "TICK\n")
                        inserted += 1

            with open(filename, "w", encoding="utf-8") as file:
                file.writelines(lines)

        print(f"Generated circuit : {filename}")

    def annotate_polygons(self, polygons: list[str]):
        self.__polygons[len(self.__circuit)].extend(polygons)

    def append_tick(self):
        if self.__clifford:
            self.__circuit.append("TICK")
        else:
            raise NotImplementedError("Non-Clifford circuit not supported yet.")

    def append(self,
        name: str,
        targets: Union[int, stim.GateTarget, stim.PauliString, Iterable[Union[int, stim.GateTarget, stim.PauliString]]],
        arg: Union[float, Iterable[float], None] = None,
    ):
        if self.__clifford:
            self.__circuit.append(name, targets, arg)
        else:
            raise NotImplementedError("Non-Clifford circuit not supported yet.")
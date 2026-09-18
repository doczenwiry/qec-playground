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
from typing import Union, Iterable, cast

import stim


class Circuitry:
    """A wrapper to easily move between Stim and Clifft when switching between Clifford and non-Clifford."""
    def __init__(self, clifford: bool = True):
        self.__clifford = clifford
        self.__circuit: Union[stim.Circuit, list[str]] = stim.Circuit() if clifford else []
        self.__used_qubits: set[int] = set()
        self.__num_cnots = 0
        self.__num_measurements = 0
        self.__num_detectors = 0
        self.__polygons: dict[int, list[str]] = defaultdict(list)

    @property
    def is_clifford(self):
        return self.__clifford

    @property
    def as_stim(self) -> stim.Circuit:
        if not self.__clifford:
            raise ValueError("Circuit is non-Clifford and is not supported by STIM.")

        return cast(stim.Circuit, self.__circuit)

    def missing_detectors(self) -> list:
        if not self.__clifford:
            raise ValueError("Circuit is non-Clifford and is not supported by STIM.")

        return self.as_stim.missing_detectors()

    @property
    def num_qubits(self):
        return len(self.__used_qubits)

    @property
    def num_cnots(self):
        return self.__num_cnots

    @property
    def num_measurements(self):
        return self.__num_measurements

    @property
    def num_detectors(self):
        return self.__num_detectors

    def __len__(self):
        return len(self.__circuit) if self.__clifford else -1

    def to_file(self, filename: str, polygons: bool = True, spacing: bool = False):
        filename += ".stim" if self.__clifford else ".clifft"
        lines = str(self.__circuit).split("\n") if self.__clifford else cast(list, self.__circuit)

        if polygons:
            inserted = 0

            # Insert all registered polygons where they belong
            for line_number, polygons in self.__polygons.items():
                for polygon in polygons:
                    lines.insert(line_number + inserted, polygon)
                    inserted += 1
                if spacing:
                    lines.insert(line_number + inserted, "TICK")
                    inserted += 1

        with open(filename, "w", encoding="utf-8") as file:
            file.write("\n".join(lines) + "\n")

    def annotate_polygons(self, polygons: list[str]):
        self.__polygons[len(self.__circuit)].extend(polygons)

    def append_tick(self):
        self.__circuit.append("TICK")

    def __update_internal_counters(self, name: str, targets: list[Union[int, stim.GateTarget, stim.PauliString]]):
        match name:
            case "CX":
                self.__num_cnots += sum(1 for _ in targets) // 2
            case "DETECTOR":
                self.__num_detectors += 1
            case "M" | "MR" | "MX" | "MRX" | "MY" | "MRY" | "MZ" | "MRZ" | "MPP":
                self.__num_measurements += 1 if name == "MPP" else sum(1 for _ in targets)
        if name not in ("QUBIT_COORDS", "DETECTOR", "OBSERVABLE_INCLUDE"):
            for target in targets:
                if isinstance(target, int):
                    self.__used_qubits.add(target)
                elif isinstance(target, stim.GateTarget):
                    self.__used_qubits.add(target.value)
                elif isinstance(target, stim.PauliString):
                    self.__used_qubits.update(target.pauli_indices())
                else:
                    raise ValueError(f"Target is unacceptable [{target}].")

    def append(self,
        name: str,
        targets: Union[int, stim.GateTarget, stim.PauliString, Iterable[Union[int, stim.GateTarget, stim.PauliString]]],
        arg: Union[float, Iterable[float], None] = None,
    ):
        targets = list(targets) if isinstance(targets, Iterable) else [ targets ]

        self.__update_internal_counters(name, targets)

        if self.__clifford:
            self.__circuit.append(name, targets, arg)
        else:
            match name:
                case "DETECTOR" | "OBSERVABLE_INCLUDE":
                    targets = " ".join(map(lambda sr: f"rec[{sr.value}]", targets))
                case "MPP":
                    labels = "_XYZ"
                    terms = [f"{labels[p]}{i}" for i, p in enumerate(targets[0]) if p != 0]
                    targets = "*".join(terms) if terms else "I"
                case _:
                    targets = " ".join(map(str, targets))

            argument = ""
            match name:
                case "QUBIT_COORDS":
                    args = arg if isinstance(arg, Iterable) else [ arg ]
                    argument = tuple(map(float, args))
                case "OBSERVABLE_INCLUDE":
                    argument = f"({arg})"

            self.__circuit.append(f"{name}{argument} {targets}")

    def __str__(self):
        return str(self.__circuit) if self.__clifford else str("\n".join(map(str, cast(list, self.__circuit))))
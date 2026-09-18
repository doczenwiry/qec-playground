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

import itertools
from collections import defaultdict

import numpy as np
import stim


class QubitArray:
    def __init__(
        self, dimensions: tuple[int, int] = (3, 3), ancilla: bool = True
    ):
        dimX, dimY = dimensions
        self.qubits = dict()
        self.dimX = dimX
        self.dimY = dimY

        qubit = 0
        self.data = set()
        for location in itertools.product(range(dimX), range(dimY)):
            self.qubits[location] = qubit
            self.data.add(qubit)
            qubit += 1

        if ancilla:
            for location in itertools.product(
                np.arange(0.5, dimX - 0.5, 1.0, dtype=float),
                np.arange(0.5, dimY - 0.5, 1.0, dtype=float),
            ):
                self.qubits[location] = qubit
                qubit += 1

        self.measurements_index: dict[str, int] = dict()
        self.measurements_qubit: dict[int, list[str]] = defaultdict(list)

    @property
    def corners(self):
        return map(
            lambda l: self.qubits[l],
            [ (0.5,0.5) , (self.dimX-1.5, 0.5), (0.5, self.dimY-1.5), (self.dimX-1.5, self.dimY-1.5) ]
        )

    def measurements(self, qubit: int):
        return filter(lambda mr: mr[0].endswith(f"@Q{qubit}"), self.measurements_index.items())

    def is_data_qubit(self, qubit: int) -> bool:
        return qubit in self.data

    def record_measurement(self, qubit: int, label: str):
        if label in self.measurements_index:
            raise ValueError("Attempting to overwrite existing measurement record: <label> already used.")
        self.measurements_index[label] = len(self.measurements_index)
        self.measurements_qubit[qubit].append(label)

    def has_record(self, label: str) -> bool:
        return label in self.measurements_index

    def retrieve_target_rec(self, label: str):
        return stim.target_rec(self.retrieve_measurement(label))

    def retrieve_record(self, negative: int) -> str:
        index = len(self.measurements_index) + negative + 1
        for rcd, idx in self.measurements_index.items():
            if index == idx:
                return rcd
        return "NONE"

    def retrieve_measurement(self, label: str):
        return - len(self.measurements_index) + self.measurements_index[label]

    def __contains__(self, location):
        return location in self.qubits

    def __getitem__(self, location):
        return self.qubits.get(location, -1)
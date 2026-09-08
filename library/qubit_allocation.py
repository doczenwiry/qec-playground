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
import numpy as np
import stim


class QubitAllocation:
    def __init__(self, anchor: tuple[int, int] = (1, 1), dimensions: tuple[int, int] = (3, 3), ancilla: bool = True):
        ax, ay = anchor
        width, height = dimensions
        self.qubits = dict()
        qubit = 0
        for location in itertools.product(range(ax, ax + width + 1), range(ay, ay + height + 1)):
            self.qubits[location] = qubit
            qubit += 1

        if ancilla:
            for location in itertools.product(
                np.arange(ax - 0.5, ax + width + 1.5, 1.0, dtype=float),
                np.arange(ay - 0.5, ay + height + 1.5, 1.0, dtype=float),
            ):
                self.qubits[location] = qubit
                qubit += 1

    def __contains__(self, location):
        return location in self.qubits

    def __getitem__(self, location):
        return self.qubits.get(location, -1)

    def append_metadata(self, circuit: stim.Circuit):
        for location, qubit in self.qubits.items():
            circuit.append("QUBIT_COORDS", [qubit], location)

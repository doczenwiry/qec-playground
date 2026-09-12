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


class QubitArray:
    def __init__(self, circuit: stim.Circuit, dimensions: tuple[int, int] = (3, 3), ancilla: bool = True):
        width, height = dimensions
        self.qubits = dict()

        qubit = 0
        self.data = set()
        for location in itertools.product(range(1, width + 1), range(1, height + 1)):
            circuit.append("QUBIT_COORDS", [qubit], location)
            self.qubits[location] = qubit
            self.data.add(qubit)
            qubit += 1

        if ancilla:
            for location in itertools.product(
                np.arange(0.5, width + 1.5, 1.0, dtype=float),
                np.arange(0.5, height + 1.5, 1.0, dtype=float),
            ):
                circuit.append("QUBIT_COORDS", [qubit], location)
                self.qubits[location] = qubit
                qubit += 1

    def is_data_qubit(self, qubit: int) -> bool:
        return qubit in self.data

    def __contains__(self, location):
        return location in self.qubits

    def __getitem__(self, location):
        return self.qubits.get(location, -1)
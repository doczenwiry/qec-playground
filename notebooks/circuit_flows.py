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

import stim

def convert_to_pauli(stabilizer: str, support: list[int], qubits: int) -> stim.PauliString:
    pauli = ""
    for q in range(qubits):
        pauli += stabilizer if q in support else "_"
    return stim.PauliString(pauli)

def extract_measurements(circuit: stim.Circuit) -> list[stim.CircuitInstruction]:
    order = []

    for instruction in circuit.flattened():
        if instruction.name in ("M","MX","MY","MZ","MR","MRX","MRY","MPP"):
            for tgt in instruction.targets_copy():
                if tgt.is_qubit_target:
                    opcode = instruction.name + ("Z" if instruction.name in ("M", "MR") else "")
                    order.append(f"{opcode}@{tgt.value}")

    return order
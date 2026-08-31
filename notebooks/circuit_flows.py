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

from typing import Optional, Iterable

import itertools
import stim

def convert_to_pauli(stabilizer: str, support: list[int], qubits: int) -> stim.PauliString:
    pauli = ""
    for q in range(qubits):
        pauli += stabilizer if q in support else "_"
    return stim.PauliString(pauli)

def extract_measurements(circuit: stim.Circuit) -> list[str]:
    order = []

    for instruction in circuit.flattened():
        if instruction.name in ("M","MX","MY","MZ","MR","MRX","MRY","MPP"):
            for tgt in instruction.targets_copy():
                if tgt.is_qubit_target:
                    opcode = instruction.name + ("Z" if instruction.name in ("M", "MR") else "")
                    order.append(f"{opcode}@{tgt.value}")

    return order

def is_pauli_preserved(circuit: stim.Circuit, pauliI: stim.PauliString, pauliO: Optional[stim.PauliString] = None):
    solution = circuit.solve_flow_measurements([stim.Flow(input=pauliI, output=pauliO or pauliI)])[0] or []
    flow = stim.Flow(input=pauliI, output=pauliO or pauliI, measurements=solution)
    return circuit.has_flow(flow), solution

def check_stabilizer_preservation(circuit: stim.Circuit, stabilizers: list[str], supports: Iterable[list[int]]):
    measurements = extract_measurements(circuit) or list()

    for support, stabilizer in itertools.product(supports, stabilizers):
        pauli = convert_to_pauli(stabilizer, support, qubits=circuit.num_qubits)
        preserved, solution = is_pauli_preserved(circuit, pauli)
        report = f"Preserved (incl. meas. {list(map(lambda m: measurements[m], solution))})" if preserved else "DISTORTED"
        print(f"> {stabilizer}({",".join(map(str, support))}) : {report}")

def check_observable_preservation(circuit: stim.Circuit, observables: list[str], support: list[int]):
    measurements = extract_measurements(circuit) or list()

    for observable in observables:
        pauli = convert_to_pauli(observable, support, qubits=circuit.num_qubits)
        preserved, solution = is_pauli_preserved(circuit, pauli)
        report = f"Preserved (incl. meas. {list(map(lambda m: measurements[m], solution))})" if preserved else "DISTORTED"
        print(f"> {observable}_L : {report}")

def check_syndrome_extractions(circuit: stim.Circuit, syndromes: list[str], supports: Iterable[list[int]]):
    measurements = extract_measurements(circuit) or list()

    identity = stim.PauliString(circuit.num_qubits)
    for support, stabilizer in itertools.product(supports, syndromes):
        pauli = convert_to_pauli(stabilizer, support, qubits=circuit.num_qubits)
        preserved, solution = is_pauli_preserved(circuit, pauli, identity)
        report = f"Extracted (incl. meas. {list(map(lambda m: measurements[m], solution))})" if preserved else "DISTORTED"
        print(f"{stabilizer}({",".join(map(str, support))}) : {report}")
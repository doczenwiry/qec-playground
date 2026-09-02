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
            if instruction.name == "MPP":
                order.append(str(instruction))
            else:
                for tgt in instruction.targets_copy():
                    if tgt.is_qubit_target:
                        opcode = instruction.name + ("Z" if instruction.name in ("M", "MR") else "")
                        order.append(f"{opcode} {tgt.value}")

    assert len(order) == circuit.num_measurements

    return order

def check_pauli_flow(
    circuit: stim.Circuit, pauliI: stim.PauliString, pauliO: stim.PauliString,
    solution: Optional[list[int]] = None
):
    if solution is None:
        solution = circuit.solve_flow_measurements([stim.Flow(input=pauliI, output=pauliO)])[0] or []
    flow = stim.Flow(input=pauliI, output=pauliO, measurements=solution)
    return circuit.has_flow(flow), solution

def check_flow_preservation(circuit: stim.Circuit, pauli: str, support: list[int], measurements: Optional[list[str]] = None):
    measurements_index = extract_measurements(circuit) or list()
    if measurements is not None:
        measurements = list(map(measurements_index.index, measurements))
    pauli_string = convert_to_pauli(pauli, support, qubits=circuit.num_qubits)
    preserved, solution = check_pauli_flow(circuit, pauliI=pauli_string, pauliO=pauli_string, solution=measurements)
    if len(solution) > 0:
        inclusion = f"(incl. meas. {list(map(lambda m: measurements_index[m], solution))})"
    else:
        inclusion = ""
    report = f"Preserved {inclusion}" if preserved else "DISTORTED"
    print(f"> {pauli}({",".join(map(str, support))}) : {report}")

def check_state_preparation(circuit: stim.Circuit, pauli: str, support: list[int], measurements: Optional[list[str]] = None):
    measurements_index = extract_measurements(circuit) or list()
    if measurements is not None:
        measurements = list(map(measurements_index.index, measurements))

    identity = stim.PauliString(circuit.num_qubits)
    pauli_string = convert_to_pauli(pauli, support, qubits=circuit.num_qubits)
    preserved, solution = check_pauli_flow(circuit, pauliI=identity, pauliO=pauli_string, solution=measurements)
    if len(solution) > 0:
        inclusion = f"(incl. meas. {list(map(lambda m: measurements_index[m], solution))})"
    else:
        inclusion = ""
    report = f"Prepared {inclusion}" if preserved else "DISTORTED"
    print(f"> {pauli}({",".join(map(str, support))}) : {report}")

def check_syndrome_extraction(circuit: stim.Circuit, syndrome: str, support: list[int], measurements: Optional[list[str]] = None):
    measurements_index = extract_measurements(circuit) or list()
    if measurements is not None:
        measurements = list(map(measurements_index.index, measurements))
    identity = stim.PauliString(circuit.num_qubits)
    pauli = convert_to_pauli(syndrome, support, qubits=circuit.num_qubits)
    preserved, solution = check_pauli_flow(circuit, pauliI=pauli, pauliO=identity, solution=measurements)
    report = f"Extracted (incl. meas. {list(map(lambda m: measurements_index[m], solution))})" if preserved else "DISTORTED"
    print(f"> {syndrome}({",".join(map(str, support))}) : {report}")
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
import stim

def compute_stabilizer_expectation(circuit, stabilizers):
    simulator = stim.TableauSimulator()
    simulator.do(circuit)
    for stabilizer, observable in itertools.product(["R", "G", "B"], ["X", "Z"]):
        pauli = stim.PauliString("*".join(map(lambda q : observable + str(q), stabilizers[stabilizer])))
        expectation = simulator.peek_observable_expectation(pauli)
        print(f"<{observable}_{stabilizer}> : {("+" if expectation == 1 else "") + str(expectation)}")

def compute_observable_expectation(circuit, observable, support):
    simulator = stim.TableauSimulator()
    simulator.do(circuit)

    pauli = stim.PauliString("*".join(map(lambda q : observable + str(q), support)))
    expectation = simulator.peek_observable_expectation(pauli)
    print(f"<{observable}_L> : {("+" if expectation == 1 else "") + str(expectation)}")

def count_cnots(circuit):
    count = 0
    for instruction in circuit.flattened():
        if instruction.name == "CX":
            count += len(instruction.targets_copy()) // 2
    print(f"Qubits: {circuit.num_qubits}")
    print(f"CNOTs : {count}")
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

from library.circuitry import Circuitry
from library.qubit_array import QubitArray
from library.steane_code.patch import SteaneCodePatch

import itertools

from utils.circuit_flows import check_state_preparation, check_flow_preservation, check_syndrome_extraction

if __name__ == "__main__":
    # Validate the Steane Code preparation (under S-injection)
    print("Modified Steane Code (w/ S-injection) --- Preparation")
    qubits = QubitArray(dimensions=(5, 3))
    circuitry = Circuitry(qubits)
    steane = SteaneCodePatch(array = qubits)
    steane.append_preparation(circuitry)

    for stabilizer, support in itertools.product(['X', 'Z'], steane.stabilizers.values()):
        check_state_preparation(circuitry.as_stim, stabilizer, support)
    check_state_preparation(circuitry.as_stim, 'Y', support=steane.support)

    print(f"Circuit statistics")
    print(f"> #qubits: {circuitry.num_qubits}")
    print(f"> #CNOTs : {circuitry.num_cnots}")

    print("")

    # Validate the Steane Code Superdense Syndrome Measurement (under S-injection)
    print("Modified Steane Code (w/ S-injection) --- Superdense Code Cycle [w/ GHZ states]")
    qubits = QubitArray(dimensions=(5, 3))
    circuitry = Circuitry(qubits)
    steane = SteaneCodePatch(array = qubits)
    steane.append_superdense_cycle(circuitry)

    print(f"Stabilizer flows")
    for stabilizer, support in itertools.product(['X', 'Z'], steane.stabilizers.values()):
        check_flow_preservation(circuitry.as_stim, stabilizer, support)
    check_flow_preservation(circuitry.as_stim, 'Y', support=steane.support)
    print(f"Syndrome extractions")
    for syndrome, support in itertools.product(['X', 'Z'], steane.stabilizers.values()):
        check_syndrome_extraction(circuitry.as_stim, syndrome, support)

    print(f"Circuit statistics")
    print(f"> #qubits: {circuitry.num_qubits}")
    print(f"> #CNOTs : {circuitry.num_cnots}")

    print("")

    # Validate the Steane Code cultivation stage (under S-injection)
    print("Modified Steane Code (w/ S-injection) --- Double-Check-S")
    qubits = QubitArray(dimensions=(5, 3))
    circuitry = Circuitry(qubits)
    steane = SteaneCodePatch(array = qubits)
    steane.append_cultivation(circuitry)

    print(f"Stabilizer flows")
    for stabilizer, support in itertools.product(['X', 'Z'], steane.stabilizers.values()):
        check_flow_preservation(circuitry.as_stim, stabilizer, support)
    check_flow_preservation(circuitry.as_stim, 'Y', support=steane.support)
    print(f"Syndrome extractions")
    check_syndrome_extraction(circuitry.as_stim, 'Y', steane.support)

    print(f"Circuit statistics")
    print(f"> #qubits: {circuitry.num_qubits}")
    print(f"> #CNOTs : {circuitry.num_cnots}")

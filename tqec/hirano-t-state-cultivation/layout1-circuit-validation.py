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

from pathlib import Path

from steane_code_patch import SteaneCodePatch
from junction_patch import JunctionPatch
from surface_code_patch import SurfaceCodePatch

import itertools
import stim

from utils.circuit_expectations import count_cnots, compute_observable_expectation
from utils.circuit_flows import check_state_preparation, check_flow_preservation, check_syndrome_extraction

if __name__ == "__main__":
    steane = SteaneCodePatch()

    print("")

    # Validate the Steane Code preparation (under S-injection)
    print("Modified Steane Code (w/ S-injection) --- Preparation")
    circuit = stim.Circuit()
    steane.append_metadata(circuit)
    for moment in range(steane.preparation_moments):
        steane.append_preparation_slice(circuit, moment)
    for stabilizer, support in itertools.product(['X', 'Z'], steane.stabilizers.values()):
        check_state_preparation(circuit, stabilizer, support)
    check_state_preparation(circuit, 'Y', support=steane.logical)

    count_cnots(circuit)

    print("")

    # Validate the Steane Code Superdense Syndrome Measurement (under S-injection)
    print("Modified Steane Code (w/ S-injection) --- Superdense Code Cycle [w/ Bell pairs]")
    circuit = stim.Circuit()
    steane.append_metadata(circuit)
    for moment in range(steane.superdense_moments):
        steane.append_superdense_slice(circuit, moment)
    print(f"Stabilizer flows")
    for stabilizer, support in itertools.product(['X', 'Z'], steane.stabilizers.values()):
        check_flow_preservation(circuit, stabilizer, support)
    check_flow_preservation(circuit, 'Y', support=steane.logical)
    print(f"Syndrome extractions")
    for syndrome, support in itertools.product(['X', 'Z'], steane.stabilizers.values()):
        check_syndrome_extraction(circuit, syndrome, support)
    count_cnots(circuit)

    print("")

    # Validate the Steane Code cultivation stage (under S-injection)
    print("Modified Steane Code (w/ S-injection) --- Double-Check-T")
    circuit = stim.Circuit()
    steane.append_metadata(circuit)
    for moment in range(steane.cultivation_moments):
        steane.append_cultivation_slice(circuit, moment)

    print(f"Stabilizer flows")
    for stabilizer, support in itertools.product(['X', 'Z'], steane.stabilizers.values()):
        check_flow_preservation(circuit, stabilizer, support)
    check_flow_preservation(circuit, 'Y', support=steane.logical)
    print(f"Syndrome extractions")
    check_syndrome_extraction(circuit, 'Y', steane.logical)
    count_cnots(circuit)
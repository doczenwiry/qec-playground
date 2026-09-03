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

from utils.circuit_expectations import count_cnots
from utils.circuit_flows import check_state_preparation

def write_file_with_polygons(
        circuit: stim.Circuit, msc: SteaneCodePatch, jp: JunctionPatch, surface_code: SurfaceCodePatch
):
    circuit.to_file(FILENAME)

    # Insert all the polygons into the Stim file for readability.
    with open(FILENAME, "r", encoding="utf-8") as file:
        lines = file.readlines()

        insertion = 0
        while insertion < len(lines) and lines[insertion].startswith("QUBIT_COORDS"):
            insertion += 1

        for polygon in msc.get_initial_polygons():
            lines.insert(insertion, polygon)
            insertion += 1
        insertion += msc.preparation_instructions + msc.preparation_moments

        for polygon in msc.get_prepared_polygons():
            lines.insert(insertion, polygon)
            insertion += 1
        insertion += msc.superdense_instructions + msc.superdense_moments

        for polygon in msc.get_prepared_polygons():
            lines.insert(insertion, polygon)
            insertion += 1
        insertion += msc.cultivation_instructions + msc.cultivation_moments

        for round in range(3):
            for polygon in msc.get_prepared_polygons():
                lines.insert(insertion, polygon)
                insertion += 1
            for polygon in jp.get_polygons():
                lines.insert(insertion, polygon)
                insertion += 1
            for polygon in surface_code.get_polygons():
                lines.insert(insertion, polygon)
                insertion += 1
            insertion += msc.superdense_instructions + msc.superdense_moments + 1

    with open(FILENAME, "w", encoding="utf-8") as file:
        file.writelines(lines)

FILENAME = str(Path(__file__).resolve().parent) + "/generated/hirano-magic-state-cultivation-layout1.stim"

if __name__ == "__main__":
    circuit = stim.Circuit()

    steane = SteaneCodePatch()
    surface_code = SurfaceCodePatch(distance=5, base_qubit=steane.num_qubits)
    junction = JunctionPatch(steane=steane, surface=surface_code)

    # Append the coordinates of all the qubits involved
    steane.append_metadata(circuit)
    surface_code.append_metadata(circuit)
    junction.append_metadata(circuit)

    # Append the modified Steane Code moments with the T-injection
    for moment in range(steane.preparation_moments):
        steane.append_preparation_slice(circuit, moment)
        circuit.append("TICK")

    # Append the superdense syndrome measurement code cycle
    for moment in range(steane.superdense_moments):
        steane.append_superdense_slice(circuit, moment)
        circuit.append("TICK")

    # Append the cultivation stage with the Double-Check-T
    for moment in range(steane.cultivation_moments):
        steane.append_cultivation_slice(circuit, moment)
        circuit.append("TICK")

    # Append the teleportation stage
    for round in range(3):
        for moment in range(steane.superdense_moments):
            steane.append_superdense_slice(circuit, moment, measure=(round == 2))
            surface_code.append_syndrome_slice(circuit, moment, preparation=(round == 0))
            junction.append_syndrome_slice(circuit, moment)

    write_file_with_polygons(circuit, steane, junction, surface_code)

    print(f"Stabilizer flows")
    for stabilizer, support in itertools.product(['X', 'Z'], steane.stabilizers.values()):
        check_state_preparation(circuit, stabilizer, support)
    print(f"Observable flows")
    check_state_preparation(circuit, 'Y', support=steane.logical)

    print(f"Circuit statistics")
    count_cnots(circuit)
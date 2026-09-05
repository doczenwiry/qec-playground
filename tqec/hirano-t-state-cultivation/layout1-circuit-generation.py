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
    circuit: stim.Circuit, steane: SteaneCodePatch, junction: JunctionPatch, surface: SurfaceCodePatch
):
    circuit.to_file(FILENAME)

    # Insert all the polygons into the Stim file for readability.
    with open(FILENAME, "r", encoding="utf-8") as file:
        lines = file.readlines()

        insertion = 0
        while insertion < len(lines) and lines[insertion].startswith("QUBIT_COORDS"):
            insertion += 1

        for polygon in steane.get_initial_polygons():
            lines.insert(insertion, polygon)
            insertion += 1
        insertion += steane.preparation_instructions + steane.preparation_moments

        for polygon in steane.get_prepared_polygons():
            lines.insert(insertion, polygon)
            insertion += 1
        insertion += steane.superdense_instructions + steane.superdense_moments

        for polygon in steane.get_prepared_polygons():
            lines.insert(insertion, polygon)
            insertion += 1
        insertion += steane.cultivation_instructions + steane.cultivation_moments

        for round in range(3):
            for polygon in steane.get_prepared_polygons():
                lines.insert(insertion, polygon)
                insertion += 1
            for polygon in junction.get_polygons():
                lines.insert(insertion, polygon)
                insertion += 1
            for polygon in surface.get_polygons():
                lines.insert(insertion, polygon)
                insertion += 1
            insertion += steane.superdense_instructions + steane.superdense_moments + 1

        for polygon in surface.get_polygons(expanded=True):
            lines.insert(insertion, polygon)
            insertion += 1
        insertion += surface.moments + surface.instructions

    with open(FILENAME, "w", encoding="utf-8") as file:
        file.writelines(lines)

FILENAME = str(Path(__file__).resolve().parent) + "/generated/hirano-magic-state-cultivation-layout1.stim"

if __name__ == "__main__":
    circuit = stim.Circuit()

    steane = SteaneCodePatch()
    junction = JunctionPatch(base_qubit=steane.num_qubits)
    surface = SurfaceCodePatch(distance=5, base_qubit=steane.num_qubits + junction.num_qubits, expansion=2)
    junction.attach(steane, surface)

    # Append the coordinates of all the qubits involved
    steane.append_metadata(circuit)
    surface.append_metadata(circuit)
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
            if moment % 2 == 0:
                surface.append_syndrome_slice(circuit, moment // 2, preparation=(round == 0))
            elif moment == 9:
                surface.append_syndrome_slice(circuit, 5, preparation=(round == 0))
            junction.append_syndrome_slice(circuit, moment)

    write_file_with_polygons(circuit, steane, junction, surface)

    print(f"Circuit statistics")
    count_cnots(circuit)
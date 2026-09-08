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

import logging
import re
from collections import Counter
from pathlib import Path

from steane_code_patch import SteaneCodePatch
from junction_patch import JunctionPatch
from surface_code_patch import SurfaceCodePatch

import stim

from utils.circuit_expectations import count_cnots

logging.basicConfig(level=logging.ERROR)

def rewrite_file_with_polygons(
    filename: str, instructions: Counter[str], steane: SteaneCodePatch, junction: JunctionPatch, surface: SurfaceCodePatch
):
    # Insert all the polygons into the Stim file for readability.
    with open(filename, "r", encoding="utf-8") as file:
        lines = file.readlines()

        inserted = 0

        for polygon in steane.get_initial_polygons():
            lines.insert(instructions['metadata'] + inserted, polygon)
            inserted += 1

        for polygon in steane.get_prepared_polygons():
            lines.insert(instructions['preparation'] + inserted, polygon)
            inserted += 1

        for polygon in steane.get_prepared_polygons():
            lines.insert(instructions['cultivation'] + inserted, polygon)
            inserted += 1
        for polygon in junction.get_polygons():
            lines.insert(instructions['cultivation'] + inserted, polygon)
            inserted += 1
        for polygon in surface.get_polygons(expansion=False):
            lines.insert(instructions['cultivation'] + inserted, polygon)
            inserted += 1

        for polygon in surface.get_polygons(expansion=True):
            lines.insert(instructions['teleportation'] + inserted, polygon)
            inserted += 1

    with open(filename, "w", encoding="utf-8") as file:
        file.writelines(lines)
        print(f"Generated circuit : {filename}")

FILENAME = str(Path(__file__).resolve().parent) + "/generated/hirano-magic-state-cultivation-layout1.stim"

if __name__ == "__main__":
    circuit = stim.Circuit()
    instructions = Counter()

    steane = SteaneCodePatch()
    junction = JunctionPatch(base_qubit=steane.num_qubits)
    surface = SurfaceCodePatch(distance=5, base_qubit=steane.num_qubits + junction.num_qubits, expansion=2)
    junction.attach(steane, surface)

    # Append the coordinates of all the qubits involved
    steane.append_metadata(circuit)
    surface.append_metadata(circuit)
    junction.append_metadata(circuit)
    instructions['metadata'] = len(circuit)

    # Append the modified Steane Code moments with the S/T-injection
    for moment in range(steane.preparation_moments):
        steane.append_preparation_slice(circuit, moment)
        circuit.append("TICK")
    instructions['preparation'] = len(circuit)

    # Append the superdense syndrome measurement code cycle (3 rounds)
    for rnd in range(3):
        for moment in range(steane.superdense_moments):
            steane.append_superdense_slice(circuit, moment, postselection=True)
            circuit.append("TICK")
    instructions['superdense'] = len(circuit)

    # Append the cultivation stage with the Double-Check-S/T
    for moment in range(steane.cultivation_moments):
        steane.append_cultivation_slice(circuit, moment, postselection=True)
        circuit.append("TICK")
    instructions['cultivation'] = len(circuit)

    # Append the teleportation stage (3 rounds)
    for moment in range(steane.teleportation_round1_moments):
        steane.append_teleportation_round1_slice(circuit, moment)
        surface.append_syndrome_slice(circuit, moment, preparation=True)
        junction.append_syndrome_slice(circuit, moment)
        circuit.append("TICK")

    for moment in range(steane.teleportation_round2_moments):
        steane.append_teleportation_round2_slice(circuit, moment)
        surface.append_syndrome_slice(circuit, moment, preparation=False)
        junction.append_syndrome_slice(circuit, moment)
        circuit.append("TICK")

    for moment in range(surface.moments):
        steane.append_teleportation_round3_slice(circuit, moment)
        surface.append_syndrome_slice(circuit, moment, preparation=False)
        junction.append_syndrome_slice(circuit, moment)
        circuit.append("TICK")

    instructions['teleportation'] = len(circuit)

    # Single round waiting for complementary gap (should be repeated by the control system at runtime)
    for moment in range(surface.moments):
        surface.append_syndrome_slice(circuit, moment, preparation=(moment==0), expansion=True)
        circuit.append("TICK")

    print(f"Circuit statistics")
    count_cnots(circuit)

    print(f"Crumble URL : {circuit.to_crumble_url()}")

    circuit.to_file(FILENAME)
    rewrite_file_with_polygons(FILENAME, instructions, steane, junction, surface)
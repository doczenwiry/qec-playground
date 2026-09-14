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
from collections import Counter
from pathlib import Path
from typing import Callable

from library.qubit_array import QubitArray
from library.steane_code.patch import SteaneCodePatch
from library.surface_code.patch import SurfaceCodePatch, PauliBasis
from library.junction_patch import JunctionPatch
# from library.expanding_surface_code_patch import SurfaceCodePatch

import stim

from utils.circuit_expectations import count_cnots

logging.basicConfig(level=logging.ERROR)

def rewrite_file_with_polygons(
    filename: str, instructions: Counter[str], steane: SteaneCodePatch,
    surface: SurfaceCodePatch, inactive_surface: Callable[[tuple[float, float]], bool]
):
    # Insert all the polygons into the Stim file for readability.
    with open(filename, "r", encoding="utf-8") as file:
        lines = file.readlines()

        inserted = 0

        for polygon in steane.get_initial_polygons():
            lines.insert(instructions['preparation'] + inserted, polygon)
            inserted += 1

        for polygon in steane.get_prepared_polygons():
            lines.insert(instructions['superdense0'] + inserted, polygon)
            inserted += 1

        for polygon in steane.get_prepared_polygons():
            lines.insert(instructions['teleportation'] + inserted, polygon)
            inserted += 1
        for polygon in surface.get_polygons(inactive_surface):
            lines.insert(instructions['teleportation'] + inserted, polygon)
            inserted += 1

    with open(filename, "w", encoding="utf-8") as file:
        file.writelines(lines)
        print(f"Generated circuit : {filename}")

FILENAME = str(Path(__file__).resolve().parent) + "/generated/hirano-magic-state-cultivation-layout1.stim"

SUPERDENSE_ROUNDS = 3
TELEPORT_ROUNDS = 2

if __name__ == "__main__":
    circuit = stim.Circuit()
    array = QubitArray(circuit, dimensions=(10, 9))
    steane = SteaneCodePatch(array, anchor=(1,1))
    surface = SurfaceCodePatch(array, distance=5, anchor=(2,4))
    inactive_surface = lambda location: location[1] == 3.5
    instructions = Counter()

    # Append the modified Steane Code moments with the S/T-injection
    instructions['preparation'] = len(circuit)
    steane.append_preparation(circuit)

    # Append the superdense syndrome measurement code cycle (3 rounds)
    for rnd in range(SUPERDENSE_ROUNDS):
        instructions[f"superdense{rnd}"] = len(circuit)
        steane.append_superdense(circuit, prefix=f"SDC{rnd}")

    # Append the cultivation stage with the Double-Check-S/T
    instructions['cultivation'] = len(circuit)
    steane.append_cultivation(circuit, prefix="CULT")

    instructions['teleportation'] = len(circuit)
    for rnd in range(TELEPORT_ROUNDS):
        for mmt in steane.TELEPORTATION_MOMENTS[f"ROUND{rnd}"]:
            steane.append_teleportation_slice(circuit, moment=mmt, round=rnd)
            surface.append_round_slice(
                circuit, moment=mmt, prepare=PauliBasis.X if rnd == 0 else None, prefix=f"SC{rnd}",
                inactive = inactive_surface
            )

    for record in array.measurements_index.items():
        print(f"Record : {record}")

    steane.annotate_detectors(circuit, sdc_rounds=SUPERDENSE_ROUNDS, tpt_rounds=TELEPORT_ROUNDS)
    surface.annotate_detectors(circuit, prepared=PauliBasis.X, rounds=2)

    # # Single round waiting for complementary gap (should be repeated by the control system at runtime)
    # for moment in surface.moments:
    #     surface.append_syndrome_slice(circuit, moment, preparation=(moment==0), expansion=True)
    #     circuit.append("TICK")

    print(f"Circuit statistics")
    count_cnots(circuit)
    print(f"> Missing detectors : {len(circuit.missing_detectors())}")

    print(f"Crumble URL : {circuit.to_crumble_url()}")

    circuit.to_file(FILENAME)
    rewrite_file_with_polygons(FILENAME, instructions, steane, surface, inactive_surface)
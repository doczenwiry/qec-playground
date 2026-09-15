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

from library.junction_patch import JunctionPatch
from library.qubit_array import QubitArray
from library.steane_code.patch import SteaneCodePatch
from library.surface_code.expanding_patch import ExpandingSurfaceCodePatch
from library.surface_code.patch import SurfaceCodePatch, PauliBasis

import stim

from utils.circuit_expectations import count_cnots

logging.basicConfig(level=logging.ERROR)

EXPANDED_OPACITY = 0.125
def rewrite_file_with_polygons(
    filename: str, instructions: Counter[str],
    steane: SteaneCodePatch, junction: JunctionPatch,
    surface: SurfaceCodePatch, inactive_surface: Callable[[tuple[float, float]], bool],
    completed: SurfaceCodePatch
):
    # Insert all the polygons into the Stim file for readability.
    with open(filename, "r", encoding="utf-8") as file:
        lines = file.readlines()

        inserted = 0

        completed.get_polygons()
        for polygon in completed.get_polygons(opacity=EXPANDED_OPACITY):
            lines.insert(instructions['preparation'] + inserted, polygon)
            inserted += 1
        for polygon in steane.get_polygons(initial=True):
            lines.insert(instructions['preparation'] + inserted, polygon)
            inserted += 1

        for polygon in completed.get_polygons(opacity=EXPANDED_OPACITY):
            lines.insert(instructions['superdense0'] + inserted, polygon)
            inserted += 1
        for polygon in steane.get_polygons():
            lines.insert(instructions['superdense0'] + inserted, polygon)
            inserted += 1

        for polygon in completed.get_polygons(opacity=EXPANDED_OPACITY):
            lines.insert(instructions['teleportation'] + inserted, polygon)
            inserted += 1
        for polygon in steane.get_polygons():
            lines.insert(instructions['teleportation'] + inserted, polygon)
            inserted += 1
        for polygon in junction.get_polygons():
            lines.insert(instructions['teleportation'] + inserted, polygon)
            inserted += 1
        for polygon in surface.get_polygons(inactive_surface):
            lines.insert(instructions['teleportation'] + inserted, polygon)
            inserted += 1

        for polygon in completed.get_polygons(opacity=EXPANDED_OPACITY):
            lines.insert(instructions['recovery'] + inserted, polygon)
            inserted += 1
        for polygon in surface.get_polygons():
            lines.insert(instructions['recovery'] + inserted, polygon)
            inserted += 1

        for polygon in completed.get_polygons(opacity=EXPANDED_OPACITY):
            lines.insert(instructions['expansion'] + inserted, polygon)
            inserted += 1
        for polygon in surface.get_polygons():
            lines.insert(instructions['expansion'] + inserted, polygon)
            inserted += 1

        for polygon in completed.get_polygons():
            lines.insert(instructions['completed'] + inserted, polygon)
            inserted += 1

    with open(filename, "w", encoding="utf-8") as file:
        file.writelines(lines)
        print(f"Generated circuit : {filename}")

FILENAME = str(Path(__file__).resolve().parent) + "/generated/hirano-magic-state-cultivation-layout1.stim"

TARGET_DISTANCE = 9
SUPERDENSE_ROUNDS = 3
TELEPORT_ROUNDS = 3
ROUNDS_FOR_COMPLEMENTARY_GAP = 1

if __name__ == "__main__":
    if TARGET_DISTANCE % 2 != 1 and TARGET_DISTANCE < 9:
        raise ValueError("TARGET_DISTANCE must be odd and above 9.")

    circuit = stim.Circuit()
    array = QubitArray(circuit, dimensions=(TARGET_DISTANCE+2, TARGET_DISTANCE+2))
    steane = SteaneCodePatch(array, anchor=(TARGET_DISTANCE-5, TARGET_DISTANCE-7))
    junction = JunctionPatch(array, anchor=(TARGET_DISTANCE-5, TARGET_DISTANCE-5))
    source = SurfaceCodePatch(array, distance=5, anchor=(TARGET_DISTANCE - 4, TARGET_DISTANCE - 4))
    expanding = ExpandingSurfaceCodePatch(array, distance=5, anchor=(1, 1), expansion=TARGET_DISTANCE - 5)
    target = SurfaceCodePatch(array, distance=TARGET_DISTANCE, anchor=(1, 1))
    inactive_surface = lambda location: location[1] == TARGET_DISTANCE - 4.5
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
        for mmt in steane.TELEPORTATION_MOMENTS:
            steane.append_teleportation_slice(circuit, moment=mmt, prefix=f"TPT{rnd}")
            junction.append_syndrome_slice(circuit, moment=mmt, prefix=f"JCT{rnd}")
            source.append_round_slice(
                circuit, moment=mmt, prepare=PauliBasis.X if rnd == 0 else None, prefix=f"SC{rnd}",
                inactive = inactive_surface
            )
            circuit.append("TICK")

    instructions['recovery'] = len(circuit)
    steane.append_destruction(circuit)
    source.append_round(circuit, prefix=f"SC{TELEPORT_ROUNDS}")

    # Handle the left-upwards expansion :) Almost there !
    instructions['expansion'] = len(circuit)
    for mmt in expanding.MOMENTS:
        expanding.append_expansion_slice(circuit, moment=mmt, prefix=f"EXP")
        circuit.append("TICK")

    # Waiting for complementary gap (should be repeated by the control system at runtime)
    instructions['completed'] = len(circuit)
    # for rnd in range(ROUNDS_FOR_COMPLEMENTARY_GAP):
    #     target.append_round(circuit, prefix=f"CG{rnd}")
    circuit.append("TICK")

    steane.annotate_detectors(circuit, sdc_rounds=SUPERDENSE_ROUNDS, tpt_rounds=TELEPORT_ROUNDS)
    junction.annotate_detectors(circuit, rounds=TELEPORT_ROUNDS)
    source.annotate_detectors(circuit, rounds=TELEPORT_ROUNDS+1, prepared=PauliBasis.X)
    expanding.annotate_detectors(circuit, sc_rounds=TELEPORT_ROUNDS+1, source=source)
    # target.annotate_detectors(circuit, rounds=ROUNDS_FOR_COMPLEMENTARY_GAP, prefix="CG")

    gauge_found = False
    try:
        dem = circuit.detector_error_model(allow_gauge_detectors=False)
    except ValueError as e:
        gauge_found = True

    print(f"Detector statistics : ")
    print(f"> Measurement records : {len(array.measurements_index)}")
    print(f"> Number of detectors : {circuit.num_detectors}")
    print(f"> Missing detectors : {len(circuit.missing_detectors())}")
    print(f"> Gauge detectors : {"FOUND" if gauge_found else "NONE"}")

    print(f"Circuit statistics")
    count_cnots(circuit)

    print(f"Crumble URL : {circuit.to_crumble_url()}")

    circuit.to_file(FILENAME)
    rewrite_file_with_polygons(FILENAME, instructions, steane, junction, source, inactive_surface, target)
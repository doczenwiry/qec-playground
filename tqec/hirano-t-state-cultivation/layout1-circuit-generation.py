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
from pathlib import Path

from library.circuitry import Circuitry
from library.junction_patch import JunctionPatch
from library.qubit_array import QubitArray
from library.steane_code.patch import SteaneCodePatch
from library.surface_code.expanding_patch import ExpandingSurfaceCodePatch
from library.surface_code.patch import SurfaceCodePatch, PauliBasis

logging.basicConfig(level=logging.ERROR)

# Primary parameters
TARGET_DISTANCE = 9
INJECTION = SteaneCodePatch.Injection.S

# Internal parameters
SUPERDENSE_ROUNDS = 3
TELEPORT_ROUNDS = 3
ROUNDS_FOR_COMPLEMENTARY_GAP = 1
EXPANDED_OPACITY = 0.125

FILENAME = str(Path(__file__).resolve().parent) + "/generated/hirano-magic-state-cultivation-layout1"

if __name__ == "__main__":
    if TARGET_DISTANCE % 2 != 1 and TARGET_DISTANCE < 9:
        raise ValueError("TARGET_DISTANCE must be odd and above 9.")

    circuitry = Circuitry(clifford=INJECTION == SteaneCodePatch.Injection.S)
    array = QubitArray(circuitry, dimensions=(TARGET_DISTANCE + 2, TARGET_DISTANCE + 2))
    steane = SteaneCodePatch(array, anchor=(TARGET_DISTANCE-5, TARGET_DISTANCE-7), injection=INJECTION)
    junction = JunctionPatch(array, anchor=(TARGET_DISTANCE-5, TARGET_DISTANCE-5))
    source = SurfaceCodePatch(array, distance=5, anchor=(TARGET_DISTANCE - 4, TARGET_DISTANCE - 4))
    expanding = ExpandingSurfaceCodePatch(array, distance=5, anchor=(1, 1), expansion=TARGET_DISTANCE - 5)
    target = SurfaceCodePatch(array, distance=TARGET_DISTANCE, anchor=(1, 1))
    inactive_source = lambda location: location[1] == TARGET_DISTANCE - 4.5

    # Append the modified Steane Code moments with the S/T-injection
    circuitry.annotate_polygons(target.get_polygons(opacity=EXPANDED_OPACITY))
    circuitry.annotate_polygons(steane.get_polygons(initial=True))
    steane.append_preparation(circuitry)

    # Append the superdense syndrome measurement code cycle (3 rounds)
    circuitry.annotate_polygons(target.get_polygons(opacity=EXPANDED_OPACITY))
    circuitry.annotate_polygons(steane.get_polygons())
    for rnd in range(SUPERDENSE_ROUNDS):
        steane.append_superdense_cycle(circuitry, prefix=f"SDC{rnd}")

    # Append the cultivation stage with the Double-Check-S/T
    steane.append_cultivation(circuitry, prefix="CULT")

    # Append the three rounds of the teleportation stage
    circuitry.annotate_polygons(target.get_polygons(opacity=EXPANDED_OPACITY))
    circuitry.annotate_polygons(steane.get_polygons())
    circuitry.annotate_polygons(junction.get_polygons())
    circuitry.annotate_polygons(source.get_polygons(inactive_source))

    for rnd in range(TELEPORT_ROUNDS):
        for mmt in steane.TELEPORTATION_MOMENTS:
            steane.append_teleportation_slice(circuitry, moment=mmt, prefix=f"TPT{rnd}")
            junction.append_syndrome_slice(circuitry, moment=mmt, prefix=f"JCT{rnd}")
            source.append_round_slice(
                circuitry, moment=mmt, prepare=PauliBasis.X if rnd == 0 else None, prefix=f"SC{rnd}",
                inactive = inactive_source
            )
            circuitry.append_tick()

    circuitry.annotate_polygons(target.get_polygons(opacity=EXPANDED_OPACITY))
    circuitry.annotate_polygons(steane.get_polygons(opacity=2.25 * EXPANDED_OPACITY))
    circuitry.annotate_polygons(source.get_polygons())

    steane.append_destruction(circuitry)
    source.append_round(circuitry, prefix=f"SC{TELEPORT_ROUNDS}")
    circuitry.append_tick()

    # Observable if expansion is commented out.
    # logical_observable = {(0, 0): "Y"}
    # for i in range(1, 5):
    #     logical_observable[(i, 0)] = "Z"
    #     logical_observable[(0, i)] = "X"
    # source.append_general_observable(
    #     circuit, logical_observable,
    #     "JCT0:Z0", "JCT0:Z1", "JCT0:Z2", "TPT0:XB", "TPT1:XB", "TPT2:XB", "DST:X1", "DST:X5", "DST:X6"
    # )

    # Handle the left-upwards expansion :) Almost there !
    circuitry.annotate_polygons(target.get_polygons())
    for mmt in expanding.MOMENTS:
        expanding.append_expansion_slice(circuitry, moment=mmt, prefix=f"EXP")
        circuitry.append_tick()

    cross = TARGET_DISTANCE-5
    logical_observable = { (cross, cross) : "Y" }
    for i in range(TARGET_DISTANCE):
        if i == cross:
            continue
        logical_observable[(i,cross)] = "Z"
        logical_observable[(cross,i)] = "X"
    expanding.append_general_observable(
        circuitry, logical_observable,
        "JCT0:Z0", "JCT0:Z1", "JCT0:Z2", "TPT0:XB", "TPT1:XB", "TPT2:XB", "DST:X1", "DST:X5", "DST:X6"
    )
    circuitry.append_tick()

    # Stabilizing the target Surface Code
    # Waiting for complementary gap (should be repeated by the control system at runtime)
    # circuit.annotate_polygons(target.get_polygons())
    # for rnd in range(ROUNDS_FOR_COMPLEMENTARY_GAP):
    #     target.append_round(circuit, prefix=f"CG{rnd}")
    circuitry.append_tick()

    steane.annotate_detectors(circuitry, sdc_rounds=SUPERDENSE_ROUNDS, tpt_rounds=TELEPORT_ROUNDS)
    junction.annotate_detectors(circuitry, rounds=TELEPORT_ROUNDS)
    source.annotate_detectors(circuitry, rounds=TELEPORT_ROUNDS + 1, prepared=PauliBasis.X)
    expanding.annotate_detectors(circuitry, sc_rounds=TELEPORT_ROUNDS + 1, source=source)
    # target.annotate_detectors(circuit, rounds=ROUNDS_FOR_COMPLEMENTARY_GAP, prefix="CG")

    print(f"Detector statistics : ")
    print(f"> Measurement records : {len(array.measurements_index)}")
    print(f"> Number of detectors : {circuitry.num_detectors}")
    if circuitry.is_clifford:
        gauge_found = False
        try:
            circuitry.as_stim.detector_error_model(allow_gauge_detectors=False)
        except ValueError:
            gauge_found = True
        print(f"> Missing detectors : {len(circuitry.as_stim.missing_detectors())}")
        for detector in circuitry.as_stim.missing_detectors():
            records = list(map(lambda neg: array.retrieve_record(neg.value), detector.targets_copy()))
            print(f">> Detector : {records}")
        print(f"> Gauge detectors : {"FOUND" if gauge_found else "NONE"}")
    else:
        print(f"> Missing detectors : n/a [non-Clifford circuit]")
        print(f"> Gauge detectors : n/a [non-Clifford circuit]")
    print(f"Circuit statistics")
    print(f"> #qubits: {circuitry.num_qubits}")
    print(f"> #CNOTs : {circuitry.num_cnots}")

    circuitry.to_file(FILENAME)
    print(f"Written as file : {FILENAME}.{"stim" if circuitry.is_clifford else "clifft"}")
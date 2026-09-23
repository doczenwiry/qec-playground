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

from library.magic_state_cultivation import MagicStateCultivation
from library.steane_code.patch import SteaneCodePatch
from library.common import Pauli

logging.basicConfig(level=logging.ERROR)

# Primary parameters
TARGET_DISTANCE = 7
DRAW_NEIGHBORS = True

# Internal parameters
SUPERDENSE_ROUNDS = 3
TELEPORT_ROUNDS = 3
ROUNDS_FOR_COMPLEMENTARY_GAP = 1
EXPANDED_OPACITY = 0.125

FILENAME = (
    str(Path(__file__).resolve().parent)
    + "/generated/hirano-magic-state-cultivation-layout1"
)


if __name__ == "__main__":
    if TARGET_DISTANCE % 2 != 1 and TARGET_DISTANCE < 7:
        raise ValueError("TARGET_DISTANCE must be odd and above 7.")

    minimum_anchoring = int(DRAW_NEIGHBORS) + 2
    msc = MagicStateCultivation(
        injection=SteaneCodePatch.Injection.S,
        target_distance=TARGET_DISTANCE,
        anchor=(minimum_anchoring, minimum_anchoring),
        draw_neighbors=DRAW_NEIGHBORS
    )

    msc.append_preparation()
    for rnd in range(SUPERDENSE_ROUNDS):
        msc.append_superdense_cycle(rnd)
    msc.append_cultivation()
    msc.append_teleportation(TELEPORT_ROUNDS)
    msc.append_expansion()

    msc.annotate_detectors(sdc_rounds=SUPERDENSE_ROUNDS, tpt_rounds=TELEPORT_ROUNDS)

    msc.circuitry.append_observable(
        0, "Y_OBSERVABLE_EXPANDED", msc.target.logical(Pauli.Y),
        *["JCT0:Z0", "JCT0:Z1", "JCT0:Z2", "STN:TPT0:XB", "STN:TPT1:XB", "STN:TPT2:XB", "STN:DST:X1", "STN:DST:X5", "STN:DST:X6"]
    )

    circuitry = msc.circuitry

    circuitry.detectors_report()

    print("Circuit statistics")
    print(f"> #qubits: {circuitry.num_qubits}")
    print(f"> #CNOTs : {circuitry.num_cnots}")

    circuitry.to_file(FILENAME)
    print(f"Written as file : {FILENAME}.stim")

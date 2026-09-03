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

from steane_code_patch import ModifiedSteaneCode
import itertools
import stim

from utils.circuit_expectations import count_cnots
from utils.circuit_flows import check_state_preparation, check_syndrome_extraction

JUNCTION_STABILIZERS = {
    16 : (1.5, 3.5), 17 : (3.5, 3.5), 18 : (5.5, 3.5)
}

SURFACE_CODE_DATA = { q + 19 : (2 + (q % 5) , 4 + (q // 5)) for q in range(25) }
SURFACE_CODE_Z_ANCILLA = {
    q + 44 : (2.5 + 2 * (q % 3) - ((q // 3) % 2), 4.5 + (q // 3)) for q in range(12)
}
SURFACE_CODE_X_ANCILLA = {
    q + 56 : (3.5 + 2 * (q % 2) - ((q // 2) % 2), 4.5 + (q // 2)) for q in range(10)
}

def append_stage3_teleportation(circuit: stim.Circuit) -> int:
    count = len(circuit.flattened())

    circuit.append("RX", SURFACE_CODE_DATA.keys())
    circuit.append("RX", JUNCTION_STABILIZERS.keys())
    circuit.append("RX", SURFACE_CODE_Z_ANCILLA.keys())
    circuit.append("RX", SURFACE_CODE_X_ANCILLA.keys())
    circuit.append("TICK")
    circuit.append("TICK")

    return len(circuit.flattened()) - count

def append_stage3_expansion(circuit: stim.Circuit) -> int:
    count = len(circuit.flattened())

    circuit.append("TICK")
    circuit.append("TICK")

    return len(circuit.flattened()) - count

def write_file_with_polygons(circuit: stim.Circuit, msc: ModifiedSteaneCode):
    circuit.to_file(FILENAME)

    # Insert all the polygons into the Stim file for readability.
    with open(FILENAME, "r", encoding="utf-8") as file:
        lines = file.readlines()

        insertion = 0
        while insertion < len(lines) and lines[insertion].startswith("QUBIT_COORDS"):
            insertion += 1

        for polygon in msc.get_polygons(initial=True):
            lines.insert(insertion, polygon)
            insertion += 1
        insertion += msc.preparation_instructions + msc.preparation_moments

        for polygon in msc.get_polygons(initial=False):
            lines.insert(insertion, polygon)
            insertion += 1
        insertion += msc.superdense_instructions + msc.superdense_moments

        for polygon in msc.get_polygons(initial=False):
            lines.insert(insertion, polygon)
            insertion += 1
        insertion += msc.cultivation_instructions + msc.cultivation_moments

    # if stage == 'cultivation':
    #     for qubit, (px, py) in JUNCTION_STABILIZERS.items():
    #         polygon = __get_polygon(px, py)
    #         lines.insert(insertion, f"#!pragma POLYGON(0,0,1,0.5) {" ".join(map(str, polygon))}\n")
    #         insertion += 1
    #     for qubit, (px, py) in SURFACE_CODE_Z_ANCILLA.items():
    #         polygon = __get_polygon(px, py)
    #         lines.insert(insertion, f"#!pragma POLYGON(0,0,1,0.5) {" ".join(map(str, polygon))}\n")
    #         insertion += 1
    #     for qubit, (px, py) in SURFACE_CODE_X_ANCILLA.items():
    #         polygon = __get_polygon(px, py)
    #         lines.insert(insertion, f"#!pragma POLYGON(1,0,0,0.5) {" ".join(map(str, polygon))}\n")
    #         insertion += 1

    with open(FILENAME, "w", encoding="utf-8") as file:
        file.writelines(lines)

FILENAME = str(Path(__file__).resolve().parent) + "/generated/hirano-magic-state-cultivation-layout1.stim"

if __name__ == "__main__":
    circuit = stim.Circuit()

    msc = ModifiedSteaneCode()

    # Append the coordinates of all the qubits involved
    msc.append_metadata(circuit)

    # Append the modified Steane Code moments with the T-injection
    for moment in range(msc.preparation_moments):
        msc.append_preparation_slice(circuit, moment)
        circuit.append("TICK")

    # Append the superdense syndrome measurement code cycle
    for moment in range(msc.superdense_moments):
        msc.append_superdense_slice(circuit, moment)
        circuit.append("TICK")

    # Append the cultivation stage with the Double-Check-T
    for moment in range(msc.cultivation_moments):
        msc.append_cultivation_slice(circuit, moment)
        circuit.append("TICK")

    write_file_with_polygons(circuit, msc)

    print(f"Stabilizer flows")
    for stabilizer, support in itertools.product(['X', 'Z'], msc.stabilizers.values()):
        check_state_preparation(circuit, stabilizer, support)
    print(f"Observable flows")
    check_state_preparation(circuit, 'Y', support=msc.logical)

    print(f"Circuit statistics")
    count_cnots(circuit)
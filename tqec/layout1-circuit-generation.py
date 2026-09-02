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

import itertools
import stim

from utils.circuit_expectations import count_cnots
from utils.circuit_flows import check_state_preparation, check_syndrome_extraction

STEANE_DATA = { 0 : (3,3), 1 : (1,3), 2 : (3,2), 3 : (4,3), 4 : (4,1), 5 : (2,1), 6 : (2,2) }
STEANE_ANCILLA = {
     7 : (3,1), 8 : (4,2), 9 : (2,3),
    10 : (2.5, 1.5), 11 : (3.5, 1.5), 12 : (4.5, 1.5),
    13 : (1.5, 2.5), 14 : (2.5, 2.5), 15 : (3.5, 2.5),
}

STEANE_INITIAL = { 'R' : [0, 2, 11, 15], 'G' : [2, 6, 7, 11], 'B' : [0, 14, 6, 2] }
STEANE_STABILIZERS = { 'R' : [0, 2, 4, 3], 'G' : [2, 4, 5, 6], 'B' : [0, 1, 6, 2] }

JUNCTION_STABILIZERS = {
    16 : (1.5, 3.5), 17 : (3.5, 3.5)
}

SURFACE_CODE_DATA = { q + 18 : (2 + (q % 5) , 4 + (q // 5)) for q in range(25) }
SURFACE_CODE_Z_ANCILLA = {
    q + 44 : (1.5 + 2 * (q % 3) + ((q // 3) % 2), 4.5 + (q // 3)) for q in range(12)
}
SURFACE_CODE_Z_ANCILLA[43] = (5.5, 3.5)
SURFACE_CODE_X_ANCILLA = {
    q + 56 : (2.5 + 2 * (q % 2) + ((q // 2) % 2), 4.5 + (q // 2)) for q in range(10)
}

def __get_qubit_at_location(px, py):
    for qubit, (x, y) in SURFACE_CODE_DATA.items():
        if x == px and y == py:
            return qubit
    for qubit, (x, y) in STEANE_DATA.items():
        if x == px and y == py:
            return qubit
    return -1

def __get_polygon(px, py):
    return [
        __get_qubit_at_location(px + dx, py + dy) for dx, dy in [ (-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5) ]
        if __get_qubit_at_location(px + dx, py + dy) != -1
    ]

def append_stage0_coordinates(circuit: stim.Circuit):
    for qubit, location in STEANE_DATA.items():
        circuit.append("QUBIT_COORDS", [qubit], location)
    for qubit, location in STEANE_ANCILLA.items():
        circuit.append("QUBIT_COORDS", [qubit], location)
    for qubit, location in JUNCTION_STABILIZERS.items():
        circuit.append("QUBIT_COORDS", [qubit], location)
    for qubit, location in SURFACE_CODE_DATA.items():
        circuit.append("QUBIT_COORDS", [qubit], location)
    for qubit, location in SURFACE_CODE_Z_ANCILLA.items():
        circuit.append("QUBIT_COORDS", [qubit], location)
    for qubit, location in SURFACE_CODE_X_ANCILLA.items():
        circuit.append("QUBIT_COORDS", [qubit], location)
    circuit.append("TICK")

def append_stage1_injection(circuit: stim.Circuit) -> int:
    count = len(circuit.flattened())
    circuit.append("RX", [0, 2, 6, 11])
    circuit.append("RZ", [1, 3, 4, 5])
    circuit.append("RZ", [7, 8, 9, 10, 12, 13, 14, 15])

    circuit.append("CX", [11, 7, 2, 15, 0, 14])
    circuit.append("TICK")
    circuit.append("CX", [7, 10, 2, 14, 0, 15, 11, 8])
    circuit.append("TICK")
    circuit.append("CX", [6, 14, 10, 7, 8, 11])
    circuit.append("TICK")
    circuit.append("CX", [6, 10, 14, 9])
    circuit.append("TICK")
    circuit.append("CX", [9, 13, 14, 6, 2, 10, 8, 15])
    circuit.append("TICK")
    circuit.append("CX", [13, 1, 9, 14, 10, 6, 15, 3, 8, 11])
    circuit.append("TICK")
    circuit.append("CX", [10, 5, 11, 8, 3, 15, 13, 9])
    circuit.append("S_DAG", [6])
    circuit.append("TICK")
    circuit.append("CX", [13, 6, 11, 4])
    circuit.append("TICK")
    circuit.append("CX", [1, 13, 10, 6, 4, 11])
    circuit.append("TICK")
    circuit.append("CX", [5, 10])
    circuit.append("TICK")
    circuit.append("TICK")

    return len(circuit.flattened()) - count

def append_superdense_code_cycle(circuit: stim.Circuit):
    count = len(circuit.flattened())

    circuit.append("RX", [10, 13, 15])
    circuit.append("RZ", [11, 12, 14])
    circuit.append("TICK")
    circuit.append("CX", [10, 11, 13, 14, 15, 12])
    circuit.append("TICK")
    circuit.append("CX", [10, 6, 11, 2, 14, 0, 15, 3])
    circuit.append("CX", [10, 5, 11, 4, 14, 2, 15, 0])
    circuit.append("CX", [12, 4, 13, 1, 14, 6, 15, 2])
    circuit.append("CX", [4, 12, 1, 13, 6, 14, 2, 15])
    circuit.append("CX", [5, 10, 4, 11, 2, 14, 0, 15])
    circuit.append("CX", [6, 10, 2, 11, 0, 14, 3, 15])
    circuit.append("TICK")
    circuit.append("CX", [10, 11, 13, 14, 15, 12])
    circuit.append("MX", [10, 13, 15])
    circuit.append("MZ", [11, 12, 14])
    circuit.append("TICK")
    circuit.append("TICK")

    return len(circuit.flattened()) - count

def append_stage2_cultivation(circuit: stim.Circuit):
    count = len(circuit.flattened())

    circuit.append("S_DAG", STEANE_DATA.keys())
    circuit.append("TICK")
    circuit.append("RX", [10, 11, 13, 14, 15])
    circuit.append("TICK")
    circuit.append("CX", [10, 5, 11, 4, 13, 1, 14, 2, 15, 3])
    circuit.append("TICK")
    circuit.append("CX", [6, 13, 2, 11, 15, 0])
    circuit.append("TICK")
    circuit.append("CX", [10, 6, 2, 15])
    circuit.append("TICK")
    circuit.append("CX", [10, 2])
    circuit.append("TICK")
    circuit.append("MX", [10])
    circuit.append("TICK")
    circuit.append("RX", [10])
    circuit.append("TICK")
    circuit.append("CX", [10, 2])
    circuit.append("TICK")
    circuit.append("CX", [10, 6, 2, 15])
    circuit.append("TICK")
    circuit.append("CX", [6, 13, 2, 11, 15, 0])
    circuit.append("TICK")
    circuit.append("CX", [10, 5, 11, 4, 13, 1, 14, 2, 15, 3])
    circuit.append("TICK")
    circuit.append("MX", [10, 11, 13, 14, 15])
    circuit.append("TICK")
    circuit.append("S", STEANE_DATA.keys())
    circuit.append("TICK")
    circuit.append("TICK")

    return len(circuit.flattened()) - count

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

def write_file_with_polygons(circuit: stim.Circuit, depths: dict[str, int]):
    circuit.to_file(FILENAME)

    # Insert all the polygons into the Stim file for readability.
    with open(FILENAME, "r", encoding="utf-8") as file:
        lines = file.readlines()
        insertion = 0
        while insertion < len(lines) and lines[insertion].startswith("QUBIT_COORDS"):
            insertion += 1
        for color, support in STEANE_INITIAL.items():
            x, y, z = int(color == 'R'), int(color == 'G'), int(color == 'B')
            lines.insert(insertion, f"#!pragma POLYGON({x},{y},{z},0.5) {" ".join(map(str, support))}\n")
            insertion += 1

        for stage in ['injection', 'superdense', 'cultivation', 'teleportation', 'expansion']:
            insertion += depths[stage]
            for color, support in STEANE_STABILIZERS.items():
                x, y, z = int(color == 'R'), int(color == 'G'), int(color == 'B')
                lines.insert(insertion, f"#!pragma POLYGON({x},{y},{z},0.5) {" ".join(map(str, support))}\n")
                insertion += 1
            if stage == 'cultivation':
                for qubit, (px, py) in JUNCTION_STABILIZERS.items():
                    polygon = __get_polygon(px, py)
                    lines.insert(insertion, f"#!pragma POLYGON(0,0,1,0.5) {" ".join(map(str, polygon))}\n")
                    insertion += 1
                for qubit, (px, py) in SURFACE_CODE_Z_ANCILLA.items():
                    polygon = __get_polygon(px, py)
                    lines.insert(insertion, f"#!pragma POLYGON(0,0,1,0.5) {" ".join(map(str, polygon))}\n")
                    insertion += 1
                for qubit, (px, py) in SURFACE_CODE_X_ANCILLA.items():
                    polygon = __get_polygon(px, py)
                    lines.insert(insertion, f"#!pragma POLYGON(1,0,0,0.5) {" ".join(map(str, polygon))}\n")
                    insertion += 1

    with open(FILENAME, "w", encoding="utf-8") as file:
        file.writelines(lines)

FILENAME = str(Path(__file__).resolve().parent) + "/generated/hirano-magic-state-cultivation-layout1.stim"

if __name__ == "__main__":
    circuit = stim.Circuit()

    depths = dict()

    # Append the coordinates of all the qubits involved
    append_stage0_coordinates(circuit)
    # Append the injection stage with the postselected superdense code cycle
    depths['injection'] = append_stage1_injection(circuit)
    depths['superdense'] = append_superdense_code_cycle(circuit)
    # Append the cultivation stage (double-check-T)
    depths['cultivation'] = append_stage2_cultivation(circuit)
    # Append the teleportation part of the escape stage
    depths['teleportation'] = append_stage3_teleportation(circuit)
    # Append the code expansion part of the escape stage
    depths['expansion'] = append_stage3_expansion(circuit)

    write_file_with_polygons(circuit, depths)

    print(f"Stabilizer flows")
    for stabilizer, support in itertools.product(['X', 'Z'], STEANE_STABILIZERS.values()):
        check_state_preparation(circuit, stabilizer, support)
    print(f"Observable flows")
    check_state_preparation(circuit, 'Y', support=list(STEANE_DATA.keys()))
    print(f"Syndrome extractions")
    for syndrome, support in itertools.product(['X', 'Z'], STEANE_STABILIZERS.values()):
        check_syndrome_extraction(circuit, syndrome, support)

    print(f"Circuit statistics")
    count_cnots(circuit)
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

import itertools

import numpy as np
import stim

plaquettes = {
    0 : 'X4T',
    1 : 'X4R',
    2 : 'X4B',
    3 : 'X4L',
    4 : 'Z4T',
    5 : 'Z4R',
    6 : 'Z4B',
    7 : 'Z4L',
    8  : 'Z2T',
    9  : 'Z2R',
    10 : 'Z2B',
    11 : 'Z2L',
    12 : 'X5B',
    13 : 'Z5B',
    14 : 'Z3B',
    15 : 'Z3T',
}

def vertices(junction, row, col):
    """Returns the coordinates of data qubits and measurement qubits touched by this plaquette type."""
    ptype = junction[row, col]
    if 0 <= ptype <= 7:
        vd = [(0.0, 0.0) , (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
        vm = [(0.5, 0.5)]
    elif 8 <= ptype <= 11:
        if ptype == 8:
            vd = [(1.0, 0.0) , (1.0, 1.0)]
            vm = [(0.5, 0.5)]
        elif ptype == 9:
            vd = [(0.0, 0.0), (1.0, 0.0)]
            vm = [(0.5, 0.5)]
        elif ptype == 10:
            vd = [(0.0, 0.0), (0.0, 1.0)]
            vm = [(0.5, 0.5)]
        else: # ptype == 11:
            vd = [(0.0, 1.0), (1.0, 1.0)]
            vm = [(0.5, 0.5)]
    elif 12 <= ptype <= 13 and (row == 0 or junction[row-1, col] not in [12, 13]):
        vd = [(0.0, 0.0), (0.0, 1.0), (2.0, 1.0), (2.0, 0.0), (1.0, 0.0)]
        vm = [(0.5, 0.5), (1.5, 0.5)]
    elif ptype == 14 and (row == 0 or junction[row-1, col] != 14):
        vd = [(0.0, 1.0), (2.0, 1.0), (2.0, 0.0), (1.0, 0.0) ]
        vm = [(0.5, 0.5), (1.5, 0.5)]
    elif ptype == 15 and (row == 0 or junction[row-1, col] != 15):
        vd = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (2.0, 0.0)]
        vm = [(0.5, 0.5), (1.5, 0.5)]
    else:
        vd = []
        vm = []
    return vd, vm

def produce_template() -> np.ndarray:
    template = np.full(shape=(16, 16), fill_value=255, dtype=np.uint8)

    # Add the top and bottom "square"
    template[0:4, 6:10] = np.array([
        2, 5, 2, 5,
        5, 2, 5, 2,
        2, 5, 2, 5,
        5, 2, 5, 2,
    ]).reshape((4,4))
    template[12:16, 6:10] = template[0:4, 6:10]

    # Add the central long "row"
    template[6:10, 0:16] = np.array([
        6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1,
        1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6,
        6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1,
        1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6,
    ]).reshape((4,16))

    # Update the central square
    template[6:10, 6:10] = np.array([
        5, 2, 5, 2,
        1, 5, 2, 6,
        6, 2, 5, 1,
        2, 5, 2, 5,
    ]).reshape((4,4))

    # Plug the 2-body Z-stabilisers on the left and right sides
    for r in [ 0, 1, 2, 3, 12, 13, 14, 15 ]:
        if r % 2 == 0:
            template[r, 5] = 11
        else:
            template[r, 10] = 9

    # Plug the 2-body Z-stabilisers on the top and bottom sides
    for c in [ 0, 1, 2, 3, 4, 11, 12, 13, 14, 15 ]:
        if c % 2 == 0:
            template[10, c] = 10
        else:
            template[5, c] = 8

    # Plug the extended stabilizers
    for col in range(6, 10):
        template[4, col] = template[5, col] = 12 if col % 2 == 0 else 13
        template[10, col] = template[11, col] = 12 if col % 2 != 0 else 13

    # Plug the extended triangular stabilizers
    template[4, 5] = template[5, 5] = 14
    template[10, 10] = template[11, 10] = 15

    return template

def pretty(array, r, c):
    cell = array[r, c]

    if 12 <= cell <= 15 and 12 <= array[r-1,c] <= 15:
        return '+'
    else:
        return hex(cell)[2:] if cell != 255 else '.'

if __name__ == "__main__":
    junction = produce_template()
    for row in range(16):
        for col in range(16):
            print(pretty(junction, row, col), end=" ")
        print()

    for idx, plq in plaquettes.items():
        print(f"{hex(idx)[2:]} : {plq}")

    # All the positions in the array correspond to measurement qubits, with the data qubits surrounding them.
    # The number encodes a specific stabiliser circuit that must be properly inserted :)
    # Have fun !
    stabilizers = dict()
    locations_mq = dict()
    mq_locations = dict()
    locations_dq = dict()
    dq_locations = dict()

    circuit = stim.Circuit()

    qubit_id = 0
    for row, col in itertools.product(range(16), range(16)):
        vertices_d, vertices_m = vertices(junction, row, col)

        for dr, dc in vertices_d:
            location = col + dc, row + dr
            if location[0] == 10 and location[1] == 5:
                print(f"FOUND ! {location} from {row},{col}")
            if location not in locations_dq:
                circuit.append("QUBIT_COORDS", [qubit_id], location)
                locations_dq[location] = qubit_id
                dq_locations[qubit_id] = location
                qubit_id += 1

        for dr, dc in vertices_m:
            location = col + dc, row + dr
            if location not in locations_mq:
                locations_mq[location] = qubit_id
                mq_locations[qubit_id] = location
                circuit.append("QUBIT_COORDS", [qubit_id], location)
                qubit_id += 1

    circuit.append("TICK")

    circuit.append("RX", mq_locations.keys())

    circuit.append("TICK")

    circuit.append("RX", dq_locations.keys())

    circuit_file = "../assets/tqec-extended-stabilizers.stim"
    circuit.to_file(circuit_file)

    with open(circuit_file, "r", encoding="utf-8") as file:
        circuit_lines = file.readlines()
        insertion = 0
        while circuit_lines[insertion].startswith("QUBIT_COORDS"):
            insertion += 1
        for row, col in itertools.product(range(16), range(16)):
            # Determine vertices
            vertices_d, _ = vertices(junction, row, col)

            if not vertices_d:
                continue

            # Determine color
            stabilizer_type = junction[row, col]
            plaquette_type = plaquettes[stabilizer_type][0]
            x, z = int(plaquette_type == 'X'), int(plaquette_type == 'Z')

            polygon = [str(locations_dq[col+dc, row+dr]) for dr, dc in vertices_d]
            circuit_lines.insert(insertion, f"#!pragma POLYGON({x},0,{z},0.5) {" ".join(polygon)}\n")
            insertion += 1

    with open("../assets/tqec-extended-stabilizers.stim", "w", encoding="utf-8") as file:
        file.writelines(circuit_lines)
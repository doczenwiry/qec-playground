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
    elif 12 <= ptype <= 13:
        vd = [(0.0, 0.0), (0.0, 1.0), (2.0, 1.0), (2.0, 0.0)]
        vm = [(0.5, 0.5), (1.5, 0.5), (1.0, 0.0)]
    elif ptype == 14:
        vd = [(0.0, 1.0), (2.0, 1.0), (2.0, 0.0) ]
        vm = [(0.5, 0.5), (1.5, 0.5), (1.0, 0.0)]
    elif ptype == 15:
        vd = [(0.0, 0.0), (0.0, 1.0), (2.0, 0.0)]
        vm = [(0.5, 0.5), (1.5, 0.5), (1.0, 0.0)]
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
        template[4, col] = 12 if col % 2 == 0 else 13
        template[10, col] = 12 if col % 2 != 0 else 13

    # Plug the extended triangular stabilizers
    template[4, 5] = 14
    template[10, 10] = 15

    return template

def pretty(array, r, c):
    cell = array[r, c]
    return hex(cell)[2:] if 0 <= cell <= 15 else '.'

regular_forward_schedules = {
    0: [3, 5, 1, 2],
    1: [1, 4, 3, 5],
    2: [1, 2, 3, 5],
    3: [4, 1, 5, 3],
    4: [3, 5, 1, 2],
    5: [1, 4, 3, 5],
    6: [1, 2, 3, 5],
    7: [4, 1, 5, 3],
    8: [0, 0, 4, 2],
    9: [4, 0, 2, 0],
    10: [2, 4, 0, 0],
    11: [0, 2, 0, 4],
    12: [2, 4, 3, 5],
    13: [2, 4, 3, 5],
    14: [0, 4, 3, 5],
    15: [2, 4, 3, 0],
}

regular_reverse_schedules = {
    0: [5, 3, 2, 1],
    1: [4, 1, 5, 3],
    2: [2, 1, 5, 3],
    3: [1, 4, 3, 5],
    4: [5, 3, 2, 1],
    5: [4, 1, 5, 3],
    6: [2, 1, 5, 3],
    7: [1, 4, 3, 5],
    8: [0, 0, 2, 4],
    9: [2, 0, 4, 0],
    10: [4, 2, 0, 0],
    11: [0, 4, 0, 2],
    12: [4, 2, 5, 3],
    13: [4, 2, 5, 3],
    14: [0, 2, 5, 3],
    15: [4, 2, 5, 0],
}

def append_stabilizers(circuit, junction, mq_at_locations, dq_at_locations_dq, moment, forward):
    regular_stabilizers = filter(
        lambda position: 0 <= junction[*position] <= 11, itertools.product(range(16), range(16))
    )
    extended_stabilizers = filter(
        lambda position: 12 <= junction[*position] <= 15, itertools.product(range(16), range(16))
    )
    if moment == 0:
        targets_x = []
        targets_z = []

        for row, col in regular_stabilizers:
            targets_x.append(mq_at_locations[col + 0.5, row + 0.5])
        for row, col in extended_stabilizers:
            targets_x.append(mq_at_locations[col + 0.5, row + 0.5])
            targets_z.append(mq_at_locations[col + 0.0, row + 1.0])

        circuit.append("RX", targets_x)
        circuit.append("RZ", targets_z)
    elif moment == 7:
        targets_x = []
        for row, col in extended_stabilizers:
            targets_x.append(mq_at_locations[col + 0.5, row + 1.5])
        circuit.append("MX", targets_x)

    elif 1 <= moment <= 6:
        targets_mx = []
        targets_cx = []
        targets_cz = []

        for row, col in regular_stabilizers:
            if moment == 6:
                targets_mx.append(mq_at_locations[col + 0.5, row + 0.5])

            ptype = junction[row, col]

            regular_schedules = regular_forward_schedules if forward else regular_reverse_schedules

            vertices_d = [ (0,0) , (1,0) , (0,1), (1,1) ]
            try:
                dx, dy = vertices_d[regular_schedules[ptype].index(moment)]
                dq = dq_at_locations_dq[col + dx, row + dy]
                mq = mq_at_locations[col + 0.5, row + 0.5]
                if 0 <= ptype <= 3:
                    targets_cx.append(mq)
                    targets_cx.append(dq)
                elif 4 <= ptype <= 11:
                    targets_cz.append(mq)
                    targets_cz.append(dq)
            except ValueError:
                # The current plaquette doesn't do anything in the current moment.
                pass

        targets_rz = []
        for row, col in extended_stabilizers:
            if moment == 1:
                targets_cx.append(mq_at_locations[col + 0.5, row + 0.5])
                targets_cx.append(mq_at_locations[col + 0.0, row + 1.0])
                targets_rz.append(mq_at_locations[col + 0.5, row + 1.5])
            elif moment == 2:
                targets_cx.append(mq_at_locations[col + 0.0, row + 1.0])
                targets_cx.append(mq_at_locations[col + 0.5, row + 1.5])
            elif moment == 5:
                targets_cx.append(mq_at_locations[col + 0.0, row + 1.0])
                targets_cx.append(mq_at_locations[col + 0.5, row + 0.5])
            elif moment == 6:
                targets_cx.append(mq_at_locations[col + 0.5, row + 1.5])
                targets_cx.append(mq_at_locations[col + 0.0, row + 1.0])

            ptype = junction[row, col]

            regular_schedules = regular_forward_schedules if forward else regular_reverse_schedules

            vertices_d = [ (0,0) , (1,0) , (0,2), (1,2) ]
            try:
                dx, dy = vertices_d[regular_schedules[ptype].index(moment)]
                mq = mq_at_locations[col + 0.5, row + 0.5] if dy == 0 else mq_at_locations[col + 0.5, row + 1.5]
                dq = dq_at_locations_dq[col + dx, row + dy]
                if ptype == 12:
                    targets_cx.append(mq)
                    targets_cx.append(dq)
                elif 13 <= ptype <= 15:
                    targets_cz.append(mq)
                    targets_cz.append(dq)
            except ValueError:
                # The current plaquette doesn't do anything in the current moment.
                pass

        circuit.append("CX", targets_cx)
        circuit.append("CZ", targets_cz)
        circuit.append("RZ", targets_rz)
        circuit.append("MX", targets_mx)


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
    mq_at_locations = dict()
    dq_at_locations = dict()

    circuit = stim.Circuit()

    qubit_id = 0
    for row, col in itertools.product(range(16), range(16)):
        vertices_d, vertices_m = vertices(junction, row, col)

        for dr, dc in vertices_d:
            location = col + dc, row + dr
            if location not in dq_at_locations:
                circuit.append("QUBIT_COORDS", [qubit_id], location)
                dq_at_locations[location] = qubit_id
                qubit_id += 1

        for dr, dc in vertices_m:
            location = col + dc, row + dr
            if location not in mq_at_locations:
                mq_at_locations[location] = qubit_id
                circuit.append("QUBIT_COORDS", [qubit_id], location)
                qubit_id += 1

    circuit.append("TICK")

    circuit.append("R", dq_at_locations.values())

    circuit.append("TICK")

    # Populate the forward round
    for moment in range(8):
        append_stabilizers(circuit, junction, mq_at_locations, dq_at_locations, moment, forward=True)
        if moment < 7:
            circuit.append("TICK")

    # Populate the reverse round
    for moment in range(8):
        append_stabilizers(circuit, junction, mq_at_locations, dq_at_locations, moment, forward=False)
        circuit.append("TICK")

    circuit_file = "../assets/tqec-extended-stabilizers.stim"
    circuit.to_file(circuit_file)

    # Insert all the polygons into the Stim file for readability.
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

            polygon = [str(dq_at_locations[col + dc, row + dr]) for dr, dc in vertices_d]
            circuit_lines.insert(insertion, f"#!pragma POLYGON({x},0,{z},0.5) {" ".join(polygon)}\n")
            insertion += 1

    with open("../assets/tqec-extended-stabilizers.stim", "w", encoding="utf-8") as file:
        file.writelines(circuit_lines)
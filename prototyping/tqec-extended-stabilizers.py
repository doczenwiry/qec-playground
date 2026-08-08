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
import base64
import itertools

import numpy as np
import stim

from prototyping.plaquettes_drawing import draw_plaquettes

SIDE = 18

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
    16 : 'ZT0',
    17 : 'ZT1',
    18 : 'ZT2',
    19 : 'ZT3'
}

def vertices(junction, row, col):
    """Returns the coordinates of data qubits and measurement qubits touched by this plaquette type."""
    ptype = junction[row, col]
    if 0 <= ptype <= 7 or 16 <= ptype <= 19:
        vd = [(0.0, 0.0) , (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
        vm = [(0.5, 0.5)]
    elif ptype == 8:
        vd = [(1.0, 0.0) , (1.0, 1.0)]
        vm = [(0.5, 0.5)]
    elif ptype == 9:
        vd = [(0.0, 0.0), (1.0, 0.0)]
        vm = [(0.5, 0.5)]
    elif ptype == 10:
        vd = [(0.0, 0.0), (0.0, 1.0)]
        vm = [(0.5, 0.5)]
    elif ptype == 11:
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

    if 16 <= ptype <= 17:
        vd.pop(ptype - 16)
    elif 18 <= ptype <= 19:
        vd.pop(3 - (ptype - 18))

    return vd, vm

def produce_template() -> np.ndarray:
    template = np.full(shape=(SIDE, SIDE), fill_value=255, dtype=np.uint8)

    # Add the top and bottom "square"
    template[1:5, 7:11] = np.array([
        2, 5, 2, 5,
        5, 2, 5, 2,
        2, 5, 2, 5,
        5, 2, 5, 2,
    ]).reshape((4,4))
    template[13:17, 7:11] = template[1:5, 7:11]

    # Add the central long "row"
    template[7:11, 1:17] = np.array([
        6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1,
        1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6,
        6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1,
        1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6, 1, 6,
    ]).reshape((4,16))

    # Update the central square
    template[7:11, 7:11] = np.array([
        5, 2, 5, 2,
        1, 5, 2, 6,
        6, 2, 5, 1,
        2, 5, 2, 5,
    ]).reshape((4,4))

    # Plug the 2-body Z-stabilisers on the left and right sides
    for r in [ 0, 1, 2, 3, 12, 13, 14, 15 ]:
        if r % 2 == 0:
            template[r+1, 6] = 11
        else:
            template[r+1, 11] = 9
    template[8, 0] = template[10, 0] = 11
    template[7, 17] = template[9, 17] = 9

    # Plug the 2-body Z-stabilisers on the top and bottom sides
    for c in [ 0, 1, 2, 3, 4, 11, 12, 13, 14, 15 ]:
        if c % 2 == 0:
            template[11, c+1] = 10
        else:
            template[6, c+1] = 8
    template[0, 7] = template[0, 9] = 8
    template[17, 8] = template[17, 10] = 10

    # Plug the extended stabilizers
    for col in range(6, 10):
        template[5, col+1] = 12 if col % 2 == 0 else 13
        template[11, col+1] = 12 if col % 2 != 0 else 13

    # Plug the extended triangular stabilizers
    template[5, 6] = 14
    template[11, 11] = 15

    # Trim the unprotected data qubits
    template[ 7,  1] = 16
    template[ 1, 10] = 17
    template[16,  7] = 18
    template[10, 16] = 19

    return template

encoding = "0123456789abcdefghij"
def pretty(array, r, c):
    cell = array[r, c]
    return encoding[cell] if 0 <= cell <= 19 else '.'

regular_schedules = {
    'forward': {
        0: [3, 5, 1, 2], 1: [1, 4, 3, 5],  2: [1, 2, 3, 5],  3: [4, 1, 5, 3],
        4: [3, 5, 1, 2], 5: [1, 4, 3, 5],  6: [1, 2, 3, 5],  7: [4, 1, 5, 3],
        8: [0, 0, 3, 5], 9: [1, 0, 3, 0], 10: [1, 4, 0, 0], 11: [0, 4, 0, 5],
        16: [0, 4, 3, 5], 17: [1, 0, 3, 5], 18: [1, 4, 0, 5], 19: [1, 4, 3, 0]
    },
    'reverse': {
        0: [5, 3, 2, 1], 1: [4, 1, 5, 3],  2: [2, 1, 5, 3],  3: [1, 4, 3, 5],
        4: [5, 3, 2, 1], 5: [4, 1, 5, 3],  6: [2, 1, 5, 3],  7: [1, 4, 3, 5],
        8: [0, 0, 5, 3], 9: [5, 0, 4, 0], 10: [4, 1, 0, 0], 11: [0, 3, 0, 1],
        16: [0,0,0,0], 17: [0,0,0,0], 18: [0,0,0,0], 19: [0,0,0,0]
    }
}

def append_regular_stabilizers(circuit, junction, mq_at_locations, dq_at_locations, moment, forward):
    regular_stabilizers = filter(
        lambda position: 0 <= junction[*position] <= 11 or 16 <= junction[*position] <= 19,
        itertools.product(range(SIDE), range(SIDE))
    )
    schedules = regular_schedules['forward'] if forward else regular_schedules['reverse']

    targets_cx = []
    targets_cz = []
    targets_rx = []
    targets_mx = []
    for row, col in regular_stabilizers:
        if moment == 0:
            targets_rx.append(mq_at_locations[col + 0.5, row + 0.5])
        elif 1 <= moment <= 5:
            ptype = junction[row, col]

            vertices_d = [ (0,0) , (1,0) , (0,1), (1,1) ]

            try:
                dx, dy = vertices_d[schedules[ptype].index(moment)]

                dq = dq_at_locations[col + dx, row + dy]
                mq = mq_at_locations[col + 0.5, row + 0.5]
                if 0 <= ptype <= 3:
                    targets_cx.append(mq)
                    targets_cx.append(dq)
                elif 4 <= ptype <= 11 or 16 <= ptype <= 19:
                    targets_cz.append(mq)
                    targets_cz.append(dq)
            except ValueError:
                # The current plaquette doesn't do anything in the current moment.
                pass
        elif moment == 6:
            targets_mx.append(mq_at_locations[col + 0.5, row + 0.5])

    if targets_rx: circuit.append("RX", targets_rx)
    if targets_cx: circuit.append("CX", targets_cx)
    if targets_cz: circuit.append("CZ", targets_cz)
    if targets_mx: circuit.append("MX", targets_mx)

extended_schedules = {
    'forward': {
        12: [2, 4, 3, 5], 13: [2, 4, 3, 5], 14: [0, 4, 3, 5], 15: [2, 4, 3, 0]
    },
    'reverse': {
        12: [4, 2, 5, 3], 13: [4, 2, 5, 3], 14: [0, 2, 5, 3], 15: [4, 2, 5, 0]
    }
}

def append_extended_stabilizers(circuit, junction, mq_at_locations, dq_at_locations_dq, moment, forward):
    extended_stabilizers = filter(
        lambda position: 12 <= junction[*position] <= 15, itertools.product(range(SIDE), range(SIDE))
    )
    schedules = extended_schedules['forward'] if forward else extended_schedules['reverse']

    targets_rx = []
    targets_rz = []
    targets_cx = []
    targets_cz = []
    targets_mx = []

    for row, col in extended_stabilizers:
        if moment == 0:
            targets_rx.append(mq_at_locations[col + 0.5, row + 0.5])
            targets_rz.append(mq_at_locations[col + 0.0, row + 1.0])
        elif 1 <= moment <= 6:
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

            vertices_d = [ (0,0) , (1,0) , (0,2), (1,2) ]
            try:
                dx, dy = vertices_d[schedules[ptype].index(moment)]
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
        elif moment == 7:
            targets_mx.append(mq_at_locations[col + 0.5, row + 1.5])

    if targets_rx: circuit.append("RX", targets_rx)
    if targets_rz: circuit.append("RZ", targets_rz)
    if targets_cx: circuit.append("CX", targets_cx)
    if targets_cz: circuit.append("CZ", targets_cz)
    if targets_mx: circuit.append("MX", targets_mx)

def pretty_schedules(forward, reverse):
    schedules = ""
    for row in range(2):
        for col in range(2):
            moment = forward[row * 2 + col]
            schedules += str(moment) if moment else '.'
        schedules += " <-> "
        for col in range(2):
            moment = reverse[row * 2 + col]
            schedules += str(moment) if moment else '.'
        schedules += "\n"
    return schedules

def print_schedules():
    for ptype in regular_schedules['forward'].keys():
        forward = regular_schedules['forward'][ptype]
        reverse = regular_schedules['reverse'][ptype]
        print(f"{plaquettes[ptype]} [{hex(ptype)[2:]}] :\n{pretty_schedules(forward, reverse)}")

    for ptype in extended_schedules['forward'].keys():
        forward = extended_schedules['forward'][ptype]
        reverse = extended_schedules['reverse'][ptype]
        print(f"{plaquettes[ptype]} [{hex(ptype)[2:]}] :\n{pretty_schedules(forward, reverse)}")

if __name__ == "__main__":
    junction = produce_template()
    for row in range(SIDE):
        for col in range(SIDE):
            print(pretty(junction, row, col), end=" ")
        print()

    print_schedules()

    draw_plaquettes(
        junction, regular_schedules, extended_schedules,
        direction = 'forward', savefile='../assets/tqec/tqec-extended-stabilizers-forward.png'
    )
    draw_plaquettes(
        junction, regular_schedules, extended_schedules,
        direction = 'reverse', savefile='../assets/tqec/tqec-extended-stabilizers-reverse.png'
    )

    # All the positions in the array correspond to measurement qubits, with the data qubits surrounding them.
    # The number encodes a specific stabiliser circuit that must be properly inserted :)
    # Have fun !
    stabilizers = dict()
    mq_at_locations = dict()
    dq_at_locations = dict()

    circuit = stim.Circuit()

    qubit_id = 0
    for row, col in itertools.product(range(SIDE), range(SIDE)):
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

    circuit.append("RX", dq_at_locations.values())

    circuit.append("TICK")

    forward = True

    # Make 5 rounds: forward, reverse, forward, reverse, forward
    for round in range(5):
        # Populate the current round
        for moment in range(8):
            append_regular_stabilizers(circuit, junction, mq_at_locations, dq_at_locations, moment, forward)
            append_extended_stabilizers(circuit, junction, mq_at_locations, dq_at_locations, moment, forward)
            # if moment < 7:
            circuit.append("TICK")
        forward = not forward

    circuit.append("MX", dq_at_locations.values())

    circuit_file = "../assets/tqec/tqec-extended-stabilizers.stim"
    circuit.to_file(circuit_file)

    # Insert all the polygons into the Stim file for readability.
    with open(circuit_file, "r", encoding="utf-8") as file:
        circuit_lines = file.readlines()
        insertion = 0
        while circuit_lines[insertion].startswith("QUBIT_COORDS"):
            insertion += 1
        for row, col in itertools.product(range(SIDE), range(SIDE)):
            # Determine vertices
            vertices_d, _ = vertices(junction, row, col)

            if not vertices_d:
                continue

            # Determine color
            stabilizer_type = junction[row, col]
            plaquette_type = plaquettes[stabilizer_type][0]
            x, z = int(plaquette_type == 'X'), int(plaquette_type == 'Z')

            polygon = [ str(dq_at_locations[col + dc, row + dr]) for dr, dc in vertices_d ]
            circuit_lines.insert(insertion, f"#!pragma POLYGON({x},0,{z},0.5) {" ".join(polygon)}\n")
            insertion += 1

    with open("../assets/tqec/tqec-extended-stabilizers.stim", "w", encoding="utf-8") as file:
        file.writelines(circuit_lines)
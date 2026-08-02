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
from collections import defaultdict

import numpy
import numpy as np

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
    14 : 'X3B',
    15 : 'Z3T',
}

# X2L, X2R, X2T, X2B
# X4L, X4R, X4T, X4B
#
# XXXX, ZZZZ, XXEEXX, ZZEEZZ, XX, ZZ
# T, B, L, R

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
    # The number encodes a specific stabilizer circuit that must be properly inserted :)
    # Have fun !
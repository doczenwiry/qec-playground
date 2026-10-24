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

import operator
from collections import defaultdict
from functools import reduce
from itertools import product, combinations
from typing import Union, cast

import numpy as np
import stim

from library.circuitry import Circuitry

_IGNORED = ("QUBIT_COORDS", "DETECTOR", "OBSERVABLE_INCLUDE", "SHIFT_COORDS")


def enumerate_faults(circuitry: Union[Circuitry, stim.Circuit], k: int = 1):
    tk_idx = 0
    faults: list[tuple[int, int, dict]] = []
    circuit = cast(
        stim.Circuit,
        circuitry.as_stim() if isinstance(circuitry, Circuitry) else circuitry,
    )
    for op_idx, instruction in enumerate(circuit.flattened()):
        if instruction.name in _IGNORED:
            continue
        elif instruction.name == "TICK":
            tk_idx += 1
            continue

        qs = [t.value for t in instruction.targets_copy() if t.is_qubit_target]
        if instruction.name in ("CNOT", "CX", "CY", "CZ"):
            for qa, qb in zip(qs[0::2], qs[1::2]):
                for pa, pb in product("IXYZ", repeat=2):
                    if pa + pb == "II":
                        continue
                    faults.append(
                        (
                            op_idx,
                            tk_idx,
                            {q: p for q, p in ((qa, pa), (qb, pb)) if p != "I"},
                        )
                    )
        elif instruction.name in ("MX", "MY", "MZ"):
            continue
        else:
            for q, p in product(qs, "XYZ"):
                faults.append((op_idx, tk_idx, {q: p}))

    simulator = stim.FlipSimulator(
        batch_size=len(faults),
        num_qubits=circuit.num_qubits,
        disable_stabilizer_randomization=True,
    )

    for op_idx, instruction in enumerate(circuit.flattened()):
        simulator.do(instruction)
        for p in "XYZ":
            mask = np.zeros((circuit.num_qubits, len(faults)), dtype=bool)
            for site, (op_idx2, _, pauli) in enumerate(faults):
                if op_idx == op_idx2:
                    for q, pq in pauli.items():
                        if pq == p:
                            mask[q, site] = True
            if mask.any():
                simulator.broadcast_pauli_errors(pauli=p, mask=mask)

    frames = simulator.peek_pauli_flips()
    detector_flips = simulator.get_detector_flips(bit_packed=False)

    outcomes = defaultdict(list)

    for configuration in combinations(range(len(faults)), k):
        product_frame = reduce(operator.mul, (frames[fi] for fi in configuration))
        product_frame.sign = +1
        product_flips = reduce(
            operator.xor, (detector_flips[:, fi] for fi in configuration)
        )
        outcomes[(str(product_frame), product_flips.tobytes())].append(configuration)

    return faults, dict(outcomes)

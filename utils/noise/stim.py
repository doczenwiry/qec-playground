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

from typing import Optional

import stim

from utils.simulation.noise import NOISELESS


def make_noisy(
    circuit: stim.Circuit,
    used_qubits: set[int],
    polygon_qubits: set[int],
    per: Optional[float] = None,
    keep_polygon_coords: bool = True,
) -> tuple[stim.Circuit, list[int]]:
    used_in_tick: set[int] = set()
    active_qubits: set[int] = set()
    noisy = stim.Circuit()
    offsets: list[int] = []
    for instruction in circuit.flattened():
        offsets.append(len(noisy))
        instruction_tags = instruction.tag.split(",")
        if instruction.name == "QUBIT_COORDS":
            qubit = instruction.targets_copy()[0].value
            if qubit in used_qubits or (
                keep_polygon_coords and qubit in polygon_qubits
            ):
                noisy.append(instruction)
            continue
        elif instruction.name in ["DETECTOR", "OBSERVABLE_INCLUDE"]:
            noisy.append(instruction)
            continue

        gate = stim.gate_data(instruction.name)

        qubits = [
            t.value
            for t in instruction.targets_copy()
            if not (t.is_combiner or t.is_measurement_record_target)
        ]
        # Make qubits that underwent a reset or a unitary operation active
        if gate.is_reset or gate.is_unitary:
            active_qubits.update(qubits)
        # Make qubits that underwent a measurement inactive
        elif gate.produces_measurements and instruction.name != "MPP":
            active_qubits.difference_update(qubits)

        if gate.is_unitary:
            used_in_tick.update(map(lambda tgt: tgt.value, instruction.targets_copy()))
            noisy.append(instruction)
            if NOISELESS in instruction_tags or per is None:
                continue

            if gate.is_single_qubit_gate:
                noisy.append("DEPOLARIZE1", instruction.targets_copy(), per)
            if gate.is_two_qubit_gate:
                noisy.append("DEPOLARIZE2", instruction.targets_copy(), per)
        elif gate.is_reset or gate.produces_measurements:
            used_in_tick.update(
                tgt.value for tgt in instruction.targets_copy() if not tgt.is_combiner
            )
            if gate.produces_measurements:
                if NOISELESS in instruction_tags:
                    noisy.append(instruction)
                else:
                    noisy.append(instruction.name, instruction.targets_copy(), arg=per)
            if gate.is_reset:
                if not gate.produces_measurements:
                    noisy.append(instruction)
                if NOISELESS in instruction_tags or per is None:
                    continue
                match gate.name:
                    case "RX" | "MRX":
                        noisy.append("Z_ERROR", instruction.targets_copy(), per)
                    case "RY" | "MRY":
                        noisy.append("Z_ERROR", instruction.targets_copy(), per)
                    case "R" | "MR" | "RZ" | "MRZ":
                        noisy.append("X_ERROR", instruction.targets_copy(), per)
        elif instruction.name == "TICK":
            noisy.append(instruction)
            idling = list(sorted(active_qubits - used_in_tick))
            used_in_tick.clear()
            if (
                NOISELESS not in instruction_tags
                and per is not None
                and len(idling) > 0
            ):
                try:
                    noisy.append("DEPOLARIZE1", idling, per)
                except ValueError as ve:
                    print(f"Idling [{per}] : {idling}")
                    raise ve
        else:
            raise NotImplementedError(f"Unrecognized instruction : {instruction}")

    offsets.append(len(noisy))

    return noisy, offsets

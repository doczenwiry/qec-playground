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

import stim
from tqec.utils import NoiseModel
from tqec.utils.noise_model import NoiseRule


def make_noisy_circuit(circuit: stim.Circuit, per: float) -> stim.Circuit:
    return NoiseModel(
        idle_depolarization=per,
        any_clifford_1q_rule=NoiseRule(after={"DEPOLARIZE1": per}),
        any_clifford_2q_rule=NoiseRule(after={"DEPOLARIZE2": per}),
        gate_rules={
            "RX": NoiseRule(after={"Z_ERROR": per}),
            "RY": NoiseRule(after={"X_ERROR": per}),
            "R": NoiseRule(after={"X_ERROR": per}),
            "MPP": NoiseRule(after={}),
        },
        measure_rules={
            "X": NoiseRule(after={}, flip_result=per),
            "Y": NoiseRule(after={}, flip_result=per),
            "Z": NoiseRule(after={}, flip_result=per),
        },
    ).noisy_circuit(circuit)

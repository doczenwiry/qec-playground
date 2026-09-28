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

from pysat.formula import WCNF
from pysat.examples.rc2 import RC2

import stim
from tqec import NoiseModel
from tqec.utils.noise_model import NoiseRule

def __make_noisy_circuit(circuit: stim.Circuit, per: float = 0.01) -> stim.Circuit:
    return NoiseModel(
        idle_depolarization=0.01,
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

def analyse_heuristic(circuit: stim.Circuit, verbose: bool = False, noisify: bool = True):
    noisy = __make_noisy_circuit(circuit, per=0.01) if noisify else circuit

    found = noisy.search_for_undetectable_logical_errors(
        dont_explore_detection_event_sets_with_size_above=4,
        dont_explore_edges_with_degree_above=4,
        dont_explore_edges_increasing_symptom_degree=False)

    print(f"Minimum weight undetectable logical error : {len(found)}")
    if verbose:
        for e in noisy.explain_detector_error_model_errors():
            print(e)

def analyse_sat_solving(circuit: stim.Circuit, noisify: bool = True):
    noisy = __make_noisy_circuit(circuit, per=0.01) if noisify else circuit

    wcnf = WCNF(from_string=noisy.shortest_error_sat_problem())
    with RC2(wcnf) as solver:
        solver.compute()
        print(f"Minimum weight undetectable logical error : {solver.cost}")
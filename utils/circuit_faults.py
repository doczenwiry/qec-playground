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
from utils.simulation.noise import make_noisy_circuit


def analyse(circuit: stim.Circuit, verbose: bool = False):
    noisy = make_noisy_circuit(circuit, per=0.01)

    found = noisy.search_for_undetectable_logical_errors(
        dont_explore_detection_event_sets_with_size_above=4,
        dont_explore_edges_with_degree_above=4,
        dont_explore_edges_increasing_symptom_degree=False)

    print(f"Minimum weight undetectable logical error : {len(found)}")
    if verbose:
        for e in noisy.explain_detector_error_model_errors():
            print(e)
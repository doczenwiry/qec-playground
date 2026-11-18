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

from IPython.core.display import Markdown
from IPython.core.display_functions import display
from pysat.formula import WCNF
from pysat.examples.rc2 import RC2

import stim


def analyse_heuristic(circuit: stim.Circuit, label: str = "", urls: bool = False, verbose: bool = False):
    found = circuit.search_for_undetectable_logical_errors(
        dont_explore_detection_event_sets_with_size_above=4,
        dont_explore_edges_with_degree_above=4,
        dont_explore_edges_increasing_symptom_degree=False,
    )

    # print(f"Minimum weight undetectable logical error : {len(found)}")

    display(
        Markdown(
            f"[Open in Crumble ({label} : weight-{len(found)} undetected error)]({circuit.to_crumble_url(mark={1: found})})"
        )
    )

    if urls:
        for k, err in enumerate(found):
            display(
                Markdown(
                    f"[Open in Crumble (Undetected error #{k})]({circuit.to_crumble_url(mark={1: [err]})})"
                )
            )

    if verbose:
        for e in circuit.explain_detector_error_model_errors():
            print(e)


def analyse_sat_solving(circuit: stim.Circuit):
    wcnf = WCNF(from_string=circuit.shortest_error_sat_problem())
    with RC2(wcnf) as solver:
        solver.compute()
        print(f"Minimum weight undetectable logical error : {solver.cost}")

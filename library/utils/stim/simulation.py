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
from datetime import datetime
from typing import Optional
import numpy as np
import sinter

from library.circuitry import Circuitry

__all__ = ["compute_ler_curve"]


# Based on stim's getting started notebook
# cfr: https://github.com/quantumlib/Stim/blob/main/doc/getting_started.ipynb
def compute_ler_curve(
    scenarios: dict[str, Circuitry],
    label: Optional[str] = None,
    postselection: bool = False,
    shots=1e6,
    minimal_noise=-6,
    points: int = 10,
    num_workers: int = 4,
    max_errors: int = 5000,
    directory: str = "simulations",
    filename: Optional[str] = "temporary",
    exclude: Optional[list[str]] = None,
) -> list[str]:
    if exclude is None:
        exclude = []

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tasks = [
        sinter.Task(
            circuit=circuitry.as_stim(per=physical_error_rate),
            postselection_mask=np.packbits(
                np.array(circuitry.postselection_mask, dtype=bool), bitorder="little"
            )
            if postselection and isinstance(circuitry, Circuitry)
            else None,
            json_metadata={
                "scenario": scenario,
                "per": physical_error_rate,
                "shots": shots,
                "label": f"{label} {index}" if label is not None else "",
                "postselection": postselection,
            },
        )
        for (index, (scenario, circuitry)), physical_error_rate in itertools.product(
            enumerate(scenarios.items()), np.logspace(-1, minimal_noise, num=points)
        )
        if scenario not in exclude
    ]

    collected_stats: list[sinter.TaskStats] = sinter.collect(
        num_workers=num_workers,
        tasks=tasks,
        decoders=["pymatching"],
        max_shots=int(shots),
        max_errors=max_errors,
        print_progress=True,
        save_resume_filepath=directory
        + "/"
        + filename
        + "-"
        + timestamp
        + ".results.csv"
        if filename
        else None,
    )

    filename_prefix = f"{directory}/simulation-results-{timestamp}"
    groups: dict[str, list[sinter.TaskStats]] = defaultdict(list)
    for stat in collected_stats:
        groups[stat.json_metadata["scenario"]].append(stat)

    paths = []

    for index, scenario in enumerate(scenarios):
        if scenario in exclude:
            continue
        group = groups[scenario]
        scenario_label = (
            f".{label.lower()}.{index}" if label is not None else ""
        ) + f".{scenario.lower().replace(' ', '-')}"
        path = f"{filename_prefix}.s-state{scenario_label}.csv"
        with open(path, "w", encoding="utf-8") as file:
            file.write(sinter.CSV_HEADER + "\n")
            file.writelines(stat.to_csv_line() + "\n" for stat in group)
        paths.append(path)

    return paths

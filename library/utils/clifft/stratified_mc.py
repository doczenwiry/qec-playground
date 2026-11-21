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

import os
from datetime import datetime
import hashlib
from typing import Optional

import clifft
import numpy as np
import sinter
import time
from scipy.stats import binom
from library.circuitry import Circuitry

__all__ = ["compute_ler_curve"]


SEED = 42


def _compute_stratum_data(
    program: clifft.Program,
    max_shots_per_stratum: int,
    batch: int,
    target_errors: int,
    workers: int,
    tolerance: float = 1e-12,
) -> dict[int, tuple[int, int, int]]:
    number_of_noise_sites = len(program.noise_site_probabilities)

    per = float(program.noise_site_probabilities[0])
    max_k = int(binom.isf(tolerance, number_of_noise_sites, per))
    pmf = binom.pmf(np.arange(max_k + 1), number_of_noise_sites, per)

    stratum_data: dict[int, tuple[int, int, int]] = {}

    # Check that the circuit is deterministic.
    check = clifft.sample_k_survivors(program, shots=100_000, k=0, seed=SEED)
    assert check.discards == 0 and check.logical_errors == 0, (
        "Noiseless circuit is not deterministic"
    )

    # Sample in each stratum. Ignore k=0 here since survival = 100.0% but max_shots would be performed
    for k in range(1, max_k + 1):
        if pmf[k] < 1e-30:
            continue

        total: int = 0
        errors: int = 0
        passed: int = 0

        batch_index: int = 0
        # Perform batch sampling until a sufficient number of errors are found
        while errors < target_errors and total < max_shots_per_stratum:
            seed = SEED + 250204928 * k + batch_index
            result = clifft.sample_k_survivors(
                program,
                shots=min(batch, max_shots_per_stratum - total),
                k=k,
                seed=seed,
                threads=workers,
            )

            # Ensure that the sampling produced valid results.
            assert result.total_shots is not None
            assert result.passed_shots is not None
            assert result.logical_errors is not None
            assert result.discards is not None

            total += result.total_shots
            errors += result.logical_errors
            passed += result.passed_shots

            batch_index += 1

        stratum_data[k] = total, errors, passed

    return stratum_data


def _stratified_mc_sampling(
    program: clifft.Program,
    max_shots_per_stratum: int,
    batch: int,
    target_errors: int,
    workers: int,
    tolerance: float = 1e-12,
) -> tuple[int, int, int]:
    assert len(set(program.noise_site_probabilities)) == 1
    number_of_noise_sites = len(program.noise_site_probabilities)

    per = float(program.noise_site_probabilities[0])
    max_k = int(binom.isf(tolerance, number_of_noise_sites, per))
    pmf = binom.pmf(np.arange(max_k + 1), number_of_noise_sites, per)

    stratum_data = _compute_stratum_data(
        program, max_shots_per_stratum, batch, target_errors, workers, tolerance
    )

    total_shots = 0
    weighted_errors = 0.0
    weighted_survival = pmf[0]
    weighted_variance = (
        0.0  # Improves confidence of the curves. Thanks, Claude.AI (November 2026)
    )
    for k, (total, errors, passed) in stratum_data.items():
        weight = pmf[k]
        ler = errors / total
        total_shots += total
        weighted_errors += weight * ler
        weighted_survival += weight * passed / total
        weighted_variance += weight**2 * ler * (1.0 - ler) / total

    # Normalize all weighted accumulations to the total of the binomial PMF
    normalization = pmf.sum()
    weighted_errors /= normalization
    weighted_survival /= normalization
    weighted_variance /= normalization**2

    shots = (
        max(round(weighted_errors * (1.0 - weighted_errors) / weighted_variance), 1)
        if weighted_variance > 0.0
        else total_shots
    )

    discards = round(shots * (1.0 - weighted_survival))
    logical_errors = round((shots - discards) * weighted_errors / weighted_survival)

    return shots, discards, logical_errors


# Based on Clifft's documentation about Importance Sampling
# cfr. https://unitaryfoundation.github.io/clifft/stable/guide/importance-sampling/
# cfr. https://unitaryfoundation.github.io/clifft/stable/guide/importance-sampling-tutorial/
def compute_ler_curve(
    scenarios: dict[str, Circuitry],
    label: Optional[str] = None,
    postselection: bool = False,
    max_shots_per_stratum=1e8,
    target_errors: int = 200,
    noise_levels: Optional[np.ndarray] = None,
    workers: Optional[int] = None,
    directory: str = "simulations",
    exclude: Optional[list[str]] = None,
    proxy_replacements: Optional[dict[str, str]] = None,
) -> list[str]:
    """Computes the PER/LER curves using Stratified Monte Carlo Sampling."""
    if exclude is None:
        exclude = []
    if proxy_replacements is None:
        proxy_replacements = {}

    if workers is None:
        workers = (os.process_cpu_count() or 2) - 1

    if noise_levels is None:
        noise_levels = np.logspace(-7, -2, num=11)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename_prefix = f"{directory}/simulation-results-{timestamp}"

    filepaths = []
    for index, (scenario, circuitry) in enumerate(scenarios.items()):
        if scenario in exclude:
            continue

        # Collect the results across all noise levels
        results = []
        total_runtime: float = 0.0
        for per in noise_levels:
            json_metadata = {
                "scenario": scenario,
                "per": float(per),
                "max_shots_per_stratum": int(max_shots_per_stratum),
                "target_errors": int(target_errors),
                "label": f"{label} {index}" if label is not None else "",
                "postselection": postselection,
            }
            strong_id = hashlib.sha256(
                f"{timestamp}|{scenario}|{per}".encode()
            ).hexdigest()

            # Compile the Clifft program
            program = circuitry.as_clifft(
                proxy_replacements,
                per=float(per),
                postselection=postselection,
                deterministic=True,
            )

            # Perform the Stratified Monte Carlo Sampling.
            start = time.monotonic()
            total, discards, errors = _stratified_mc_sampling(
                program,
                max_shots_per_stratum=int(max_shots_per_stratum),
                batch=10**6,
                target_errors=target_errors,
                workers=workers,
            )
            final = time.monotonic()

            total_runtime += final - start
            print(
                f"{scenario} p={per:.2e}: {errors} errors, {discards}/{total} discarded [runtime:{round(final - start, 2)}s]."
            )

            results.append(
                sinter.TaskStats(
                    strong_id=strong_id,
                    decoder="clifft-postselection",
                    json_metadata=json_metadata,
                    shots=total,
                    errors=errors,
                    discards=discards,
                    seconds=final - start,
                )
            )

        print(f"Total runtime [{scenario}] : {round(total_runtime, 2)}s")

        scenario_label = f".{label.lower()}.{index}" if label is not None else ""
        scenario_name = f".{scenario.lower().replace(' ', '-')}"
        path = f"{filename_prefix}{scenario_label}{scenario_name}.t-state.csv"
        with open(path, "w", encoding="utf-8") as file:
            file.write(sinter.CSV_HEADER + "\n")
            file.writelines(statistics.to_csv_line() + "\n" for statistics in results)
        filepaths.append(path)

    return filepaths

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
from typing import Optional

import clifft
import numpy as np
import pandas
import sinter  # type: ignore[import-untyped]
import time

from scipy.stats import binom

from library.circuitry import Circuitry
from library.utils.clifft.decoding import Decoder
from library.utils.clifft.complementary_gap import ComplementaryGapDecoder

__all__ = ["compute_ler_curves"]

SEED = 42


def _compute_stratum_data(
    program: clifft.Program,
    workers: int,
    strata_count: int,
    shots_per_stratum: float,
    batch_count: Optional[int] = None,
    max_errors: Optional[int] = None,
    decoder: Optional[ComplementaryGapDecoder] = None,
) -> pandas.DataFrame:
    strata = pandas.DataFrame(
        {
            "total_shots": pandas.Series(dtype=float),
            "discarded_shots": pandas.Series(dtype=float),
            "surviving_shots": pandas.Series(dtype=float),
            "logical_errors": pandas.Series(dtype=float),
            "logical_error_rate": pandas.Series(dtype=float),
            "logical_error_rate_wald_ci": pandas.Series(dtype=float),

        },
        index=pandas.Index([], dtype=int, name="k")
    )

    # Check that the circuit is deterministic.
    check = clifft.sample_k_survivors(program, shots=100_000, k=0, seed=SEED)
    if check.discards != 0 or check.logical_errors != 0:
        raise ValueError("Noiseless circuit is not deterministic.")

    # Check that the circuit contain noise sites
    if len(program.noise_site_probabilities) == 0:
        raise ValueError("Circuit doesn't contain any noise sites.")

    # Check that the noise probability is uniform across all noise sites.
    if not np.allclose(np.asarray(program.noise_site_probabilities), program.noise_site_probabilities[0]):
        raise ValueError("Noise sites have non-uniform probabilities.")

    batch_count = batch_count or 20
    batch_size = int(shots_per_stratum / batch_count)
    for k in range(strata_count + 1):
        total_shots = 0.0
        discarded_shots = 0.0
        surviving_shots = 0.0
        logical_errors = 0.0

        batch = 0
        while total_shots < shots_per_stratum and (max_errors is None or logical_errors < max_errors):
            seed = SEED + 250204928 * k + batch
            result = clifft.sample_k_survivors(
                program, seed=seed, threads=workers,
                shots=int(batch_size), k=k,
                keep_records=decoder is not None,
            )

            # Ensure that the sampling produced valid results.
            assert result.total_shots is not None
            assert result.logical_errors is not None
            assert result.passed_shots is not None
            assert result.discards is not None

            total_shots += result.total_shots
            discarded_shots += result.discards
            surviving_shots += result.passed_shots

            if decoder is not None:
                predictions, accepted = decoder.decode(result.detectors)
                failed = np.any(predictions != result.observables, axis=1)
                logical_errors += int((failed & accepted).sum())
                rejected = int((~accepted).sum())
                surviving_shots -= rejected
                discarded_shots += rejected
            else:
                logical_errors += result.logical_errors

            batch += 1

        if total_shots > 0:
            logical_error_rate = logical_errors / total_shots
            logical_error_rate_wald_ci = 1.96 * np.sqrt(logical_error_rate * (1 - logical_error_rate) / total_shots)
        else:
            logical_error_rate = np.nan
            logical_error_rate_wald_ci = np.nan

        strata.loc[k] = pandas.Series({
            "total_shots": total_shots,
            "discarded_shots": discarded_shots,
            "surviving_shots": surviving_shots,
            "logical_errors": logical_errors,
            "logical_error_rate": logical_error_rate,
            "logical_error_rate_wald_ci": logical_error_rate_wald_ci,
        })

    return strata


# Based on Clifft's documentation about Importance Sampling
# cfr. https://unitaryfoundation.github.io/clifft/stable/guide/importance-sampling/
# cfr. https://unitaryfoundation.github.io/clifft/stable/guide/importance-sampling-tutorial/
def compute_ler_curves(
    scenarios: dict[str, Circuitry],
    label: Optional[str] = None,
    shots_per_stratum: float= 1e6,
    batch_count: Optional[int] = None,
    max_errors: Optional[int] = None,
    strata_count: int = 16,
    gap_threshold: float = 0.0,
    noise_levels: Optional[np.ndarray] = None,
    workers: Optional[int] = None,
    exclude: Optional[list[str]] = None,
    proxy_replacements: Optional[dict[str, str]] = None,
) -> tuple[dict[str, pandas.DataFrame], dict[str, pandas.DataFrame]]:
    """Computes the PER/LER curves using Stratified Monte Carlo Sampling."""
    if exclude is None:
        exclude = []
    if proxy_replacements is None:
        proxy_replacements = {}

    if workers is None:
        workers = (os.process_cpu_count() or 2) - 1

    if noise_levels is None:
        noise_levels = np.logspace(-7, -2, num=11)

    results_ler: dict[str, pandas.DataFrame] = {}
    results_cer: dict[str, pandas.DataFrame] = {}
    for index, (scenario, circuitry) in enumerate(scenarios.items()):
        if scenario in exclude:
            continue

        # Compile the Clifft program to compute the Conditional Error Rates.
        program = circuitry.as_clifft(
            proxy_replacements,
            per=float(0.001),
            deterministic=True,
        )

        start = time.monotonic()
        print(f"Computing Conditional Error Rates for {scenario} ...")
        strata = _compute_stratum_data(
            program, workers=workers, decoder=ComplementaryGapDecoder.build(circuitry, threshold=gap_threshold),
            strata_count=strata_count, shots_per_stratum=shots_per_stratum,
            max_errors=max_errors, batch_count=batch_count,
        )
        final = time.monotonic()
        print(f"> {round(final - start, 2)}s")

        ler = pandas.DataFrame(
            {
                "physical_error_rate": pandas.Series(dtype=float),
                "logical_error_rate": pandas.Series(dtype=float),
                "logical_error_rate_wald_ci": pandas.Series(dtype=float),
                "discarded_shots_rate": pandas.Series(dtype=float),
            }
        )

        for per in noise_levels:
            pmf = pandas.Series(
                binom.pmf(strata.index, len(program.noise_site_probabilities), per),
                index=strata.index, name="P(k)"
            )

            total_shots = strata["total_shots"]
            surviving_rate_k = strata["surviving_shots"] / total_shots.where(total_shots != 0.0)
            logical_error_rate_k = strata["logical_errors"] / total_shots.where(total_shots != 0.0)

            weighted_logical_error_rate = sum(pmf * logical_error_rate_k)
            weighted_surviving_rate = sum(pmf * surviving_rate_k)
            variance = sum(pmf**2 * logical_error_rate_k * (1.0 - logical_error_rate_k) / total_shots)

            ler.loc[len(ler)] = pandas.Series(
                {
                    "physical_error_rate": per,
                    "logical_error_rate": weighted_logical_error_rate / weighted_surviving_rate,
                    "logical_error_rate_wald_ci": 1.96 * np.sqrt(variance) / weighted_surviving_rate,
                    "discarded_shots_rate": 1.0 - weighted_surviving_rate / sum(pmf),
                }
            )

        results_ler[scenario] = ler
        results_cer[scenario] = strata

    return results_ler, results_cer

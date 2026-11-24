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

from dataclasses import dataclass

from typing import Optional

import numpy as np
import pymatching  # type: ignore[import-untyped]
import stim  # type: ignore[import-untyped]

from library.circuitry import Circuitry

__all__ = ["Decoder"]

@dataclass(frozen=True)
class Decoder:
    matching: pymatching.Matching
    detectors: np.ndarray

    @staticmethod
    def build(circuitry: Circuitry) -> Optional[Decoder]:
        postselected = np.asarray(circuitry.postselection_mask, dtype=bool)
        decoding_detectors = np.flatnonzero(~postselected)

        decoder: Optional[Decoder] = None
        if len(decoding_detectors) > 0:
            mapping = {int(old) : new for new, old in enumerate(decoding_detectors)}
            dem = circuitry.as_stim(per=1e-3, keep_polygons=False).detector_error_model(
                decompose_errors=True, ignore_decomposition_failures=True
            )

            matching = pymatching.Matching()

            for instruction in dem.flattened():
                if instruction.type == "error":
                    probability = instruction.args_copy()[0]
                    components = _split_components(instruction.targets_copy())

                    # Skip the error if it touches any postselected detector.
                    if any(
                        postselected[d] for component_detectors, _ in components for d in component_detectors
                    ):
                        continue

                    for detectors, observables in components:
                        _add_component(
                            matching, [mapping[d] for d in detectors], observables, probability
                        )

            if matching.num_detectors < len(decoding_detectors):
                matching.add_boundary_edge(len(decoding_detectors) - 1, weight = 1e9)

            decoder = Decoder(matching, decoding_detectors)

        return decoder

def _split_components(
    targets: list[stim.DemTarget]
) -> list[tuple[list[int], set[int]]]:
    components: list[tuple[list[int], set[int]]] = [([], set())]
    for target in targets:
        if target.is_separator():
            components.append(([], set()))
        elif target.is_relative_detector_id():
            components[-1][0].append(target.val)
        elif target.is_logical_observable_id():
            components[-1][1].add(target.val)
    return components

def _add_component(
    matching: pymatching.Matching,
    detectors: list[int],
    observables: set[int],
    probability: float,
) -> None:
    """Add one graphlike component as an edge (two detectors) or a boundary edge (one)."""
    weight = np.log((1 - probability) / probability)
    if len(detectors) > 2:
        raise ValueError(f"Non-graphlike error on decoded detectors {detectors}.")
    if len(detectors) == 2:
        matching.add_edge(
            detectors[0], detectors[1],
            fault_ids=observables, weight=weight, error_probability=probability,
            merge_strategy="independent",
        )
    elif len(detectors) == 1:
        matching.add_boundary_edge(
            detectors[0],
            fault_ids=observables, weight=weight, error_probability=probability,
            merge_strategy="independent",
        )
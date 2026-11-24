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
import logging
import numpy as np
import pymatching  # type: ignore[import-untyped]
import stim  # type: ignore[import-untyped]

from library.circuitry import Circuitry

__all__ = ["ComplementaryGapDecoder"]

@dataclass(frozen=True)
class ComplementaryGapDecoder:
    matching: pymatching.Matching
    detectors: np.ndarray
    threshold: float

    @staticmethod
    def build(circuitry: Circuitry, threshold: float) -> Optional[ComplementaryGapDecoder]:
        # Isolate the detectors that participate in the decoding (i.e. excl. postselected ones).
        postselected = np.asarray(circuitry.postselection_mask, dtype=bool)
        decoding_detectors = np.flatnonzero(~postselected)

        decoder: Optional[ComplementaryGapDecoder] = None
        if len(decoding_detectors) > 0:
            mapping = {int(old) : new for new, old in enumerate(decoding_detectors)}

            # We can use the DEM for the S-proxy circuit for matching purposes.
            dem = circuitry.as_stim(per=1e-3, keep_polygons=False).detector_error_model(
                decompose_errors=True, ignore_decomposition_failures=True
            )

            if dem.num_observables != 1:
                raise ValueError("Complementary Gap decoding supports exactly one observable.")

            matching = pymatching.Matching()
            observable_node = len(decoding_detectors)
            undetectable_probability = 0.0
            for instruction in dem.flattened():
                if instruction.type == "error":
                    probability = instruction.args_copy()[0]
                    components = _split_components(instruction.targets_copy())

                    # Ignore any error that involves a postselected detector.
                    if any(
                        postselected[d] for component_detectors, _ in components for d in component_detectors
                    ):
                        continue

                    for detectors, observables in components:
                        if _add_component(
                            matching, [mapping[d] for d in detectors], observables, probability, observable_node
                        ):
                            undetectable_probability += probability

            if undetectable_probability > 0:
                logging.warning(
                    "Observable flipped by undetectable mechanisms (total probability %.2e at p=1e-3): "
                    "this sets a floor on the logical error rate.", undetectable_probability,
                )

            if not any(observable_node in (a, b) for a, b, _ in matching.edges()):
                raise ValueError("No error mechanism flips the observable: the gap is undefined.")

            if matching.num_detectors < observable_node + 1:
                matching.add_boundary_edge(observable_node, weight = 1e9)

            decoder = ComplementaryGapDecoder(matching, decoding_detectors, threshold)

        return decoder

    DECIBELS_PER_NEPER = 10 / np.log(10)
    def decode(self, detection_events: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        syndromes = detection_events[:, self.detectors]
        observable = np.zeros((syndromes.shape[0], 1), dtype=syndromes.dtype)
        _, weights_0 = self.matching.decode_batch(np.hstack([syndromes, observable]), return_weights=True)
        _, weights_1 = self.matching.decode_batch(np.hstack([syndromes, 1 - observable]), return_weights=True)

        predictions = (weights_1 < weights_0).astype(np.uint8)[:, None]
        gaps = np.abs(weights_1 - weights_0) * ComplementaryGapDecoder.DECIBELS_PER_NEPER
        accepted = gaps >= self.threshold
        return predictions, accepted

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
    observable_node: int,
) -> bool:
    """Add one graphlike component as an edge (two detectors) or a boundary edge (one).
    Returns True if the component flips the observable without touching any detector."""
    weight = np.log((1 - probability) / probability)
    if len(detectors) > 2:
        raise ValueError(f"Non-graphlike error on decoded detectors {detectors}.")

    flips_observable = len(observables) % 2 == 1
    if flips_observable and len(detectors) == 2:
        raise ValueError(f"Observable flipped by a non-boundary component {detectors}.")

    if flips_observable and len(detectors) == 1:
        matching.add_edge(
            detectors[0], observable_node,
            weight=weight, error_probability=probability, merge_strategy="independent",
        )
    elif not flips_observable and len(detectors) == 2:
        matching.add_edge(
            detectors[0], detectors[1],
            weight=weight, error_probability=probability, merge_strategy="independent",
        )
    elif not flips_observable and len(detectors) == 1:
        matching.add_boundary_edge(
            detectors[0],
            weight=weight, error_probability=probability, merge_strategy="independent",
        )
    return flips_observable and len(detectors) == 0

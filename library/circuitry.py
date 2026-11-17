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

from collections import defaultdict
from typing import Union, Iterable, Optional
import logging

import clifft
import stim

from library.qubit_array import QubitArray
from noise.stim import make_noisy
from simulation.noise import NOISELESS


class Circuitry:
    """A wrapper to easily move between Stim and Clifft when switching between Clifford and non-Clifford."""

    def __init__(self, qubits: QubitArray, opacity: float = 0.0):
        self.__physical_qubits = qubits
        self.__circuit: stim.Circuit = stim.Circuit()
        self.__used_qubits: set[int] = set()
        self.__polygon_qubits: set[int] = set()
        self.__num_cnots = 0
        self.__num_measurements = 0
        self.__num_detectors = 0
        self.__postselection_mask: list[bool] = []
        self.__polygons: dict[int, list[str]] = defaultdict(list)

        for location, qubit in self.__physical_qubits.qubits.items():
            self.append("QUBIT_COORDS", [qubit], location)

        if opacity > 0.0:
            self.annotate_polygons(
                [
                    f"POLYGON(0,1,0,{opacity}) {' '.join(map(str, self.__physical_qubits.corners))}"
                ]
            )
            self.append_tick()

    @property
    def used_qubits(self):
        return self.__used_qubits

    def _as_noisy_stim(
        self,
        per: Optional[float] = None,
        strip_tags: bool = False,
        keep_polygon_coords: bool = True,
    ) -> tuple[stim.Circuit, list[int]]:
        return make_noisy(
            self.__circuit,
            self.__used_qubits,
            self.__polygon_qubits,
            per,
            keep_polygon_coords,
        )

    @staticmethod
    def _as_stripped_stim(circuit: stim.Circuit) -> stim.Circuit:
        stripped = stim.Circuit()

        for instruction in circuit.flattened():
            stripped.append(
                stim.CircuitInstruction(
                    instruction.name,
                    instruction.targets_copy(),
                    instruction.gate_args_copy(),
                )
            )

        return stripped

    def _strip_tag(circuit: stim.Circuit, tag: str) -> stim.Circuit:
        """Remove one comma-separated part from every instruction's tag."""
        stripped = stim.Circuit()
        for instruction in circuit.flattened():
            parts = [p for p in instruction.tag.split(",") if p.strip() != tag]
            stripped.append(
                stim.CircuitInstruction(
                    instruction.name,
                    instruction.targets_copy(),
                    instruction.gate_args_copy(),
                    tag=",".join(parts),
                )
            )
        return stripped

    def as_text(
        self,
        per: Optional[float] = None,
        proxy_replacements: Optional[dict[str, str]] = None,
        keep_polygons: bool = True,
    ) -> str:
        noisy, offsets = self._as_noisy_stim(per, keep_polygon_coords=keep_polygons)
        circuit, mapping = self.compact_qubits(
            Circuitry._strip_tag(noisy, NOISELESS),
            extra=self.__polygon_qubits if keep_polygons else {},
        )

        if proxy_replacements is None:
            proxy_replacements = {}

        text = []
        for instruction in circuit.flattened():
            line = str(
                stim.CircuitInstruction(
                    instruction.name,
                    instruction.targets_copy(),
                    instruction.gate_args_copy(),
                )
            )
            if instruction.tag in proxy_replacements:
                line = (
                    proxy_replacements[instruction.tag] + line[len(instruction.name) :]
                )
            text.append(line)

        if keep_polygons:
            text = [
                f"#!pragma {line}" if line.startswith("POLYGON") else line
                for line in self.__insert_polygons(text, offsets, mapping)
            ]

        return "\n".join(text)

    def as_stim(
        self, per: Optional[float] = None, keep_polygons: bool = True
    ) -> stim.Circuit:
        return stim.Circuit(self.as_text(per, keep_polygons=keep_polygons))

    def as_clifft(
        self,
        proxy_replacements: dict[str, str],
        per: Optional[float] = None,
        deterministic: bool = False,
        postselection: bool = False,
    ) -> clifft.Program:
        mask = (
            [int(flag) for flag in self.__postselection_mask] if postselection else None
        )
        return clifft.compile(
            self.as_text(per, proxy_replacements, keep_polygons=False),
            postselection_mask=mask,
            normalize_syndromes=deterministic,
        )

    @property
    def postselection_mask(self):
        return self.__postselection_mask

    def missing_detectors(self, unknown_input: bool = False) -> list:
        return self.as_stim().missing_detectors(unknown_input=unknown_input)

    @staticmethod
    def __remap_polygon(polygon: str, mapping: dict[int, int]) -> str:
        head, *qubits = polygon.split(" ")
        return " ".join([head, *(str(mapping[int(q)]) for q in qubits)])

    def __insert_polygons(
        self,
        lines: list[str],
        offsets: list[int],
        mapping: dict[int, int],
        spacing: bool = False,
    ):
        inserted = 0

        # Insert all registered polygons where they belong
        for line_number, polygons in self.__polygons.items():
            for polygon in polygons:
                lines.insert(
                    offsets[line_number] + inserted,
                    self.__remap_polygon(polygon, mapping),
                )
                inserted += 1
            if spacing:
                lines.insert(offsets[line_number] + inserted, "TICK")
                inserted += 1

        return lines

    @property
    def num_qubits(self):
        return len(self.__used_qubits)

    @property
    def num_cnots(self):
        return self.__num_cnots

    @property
    def num_measurements(self):
        return self.__num_measurements

    @property
    def num_detectors(self):
        return self.__num_detectors

    def __len__(self):
        return len(self.__circuit)

    def to_crumble_url(
        self,
        polygons: bool = True,
        spacing: bool = False,
        location: str = "https://algassert.com/crumble.html",
        marks: Optional[list[tuple[int, dict[int, str], int]]] = None,
    ):
        circuit, offsets = self._as_noisy_stim()
        compact, mapping = self.compact_qubits(circuit, extra=self.__polygon_qubits)
        stripped = Circuitry._as_stripped_stim(compact)
        lines = str(stripped).splitlines()

        if marks:
            for op_idx, pauli, mk_idx in sorted(
                marks, key=lambda m: m[0], reverse=True
            ):
                lines[op_idx + 1 : op_idx + 1] = ["TICK"] + [
                    f"MARK{p}({mk_idx}) {q}" for q, p in sorted(pauli.items())
                ]
        elif polygons:
            lines = self.__insert_polygons(lines, offsets, mapping, spacing=spacing)

        return (
            location
            + "#circuit="
            + ";".join(lines).replace(" ", "_").replace(f"[{NOISELESS}]", "")
        )

    def to_file(
        self,
        filename: str,
        polygons: bool = True,
        per: Optional[float] = None,
        proxy_replacements: Optional[dict[str, str]] = None,
    ):
        circuit_text = self.as_text(per, proxy_replacements, keep_polygons=polygons)

        filename += ".stim" if proxy_replacements is None else ".clifft"
        with open(filename, "w", encoding="utf-8") as file:
            file.write(circuit_text)

    def annotate_polygons(self, polygons: list[str]):
        for polygon in polygons:
            for qb in polygon.split(" ")[1:]:
                self.__polygon_qubits.add(int(qb))
        self.__polygons[len(self.__circuit)].extend(polygons)

    def annotate_detector(self, *labels: str, postselected: bool = False) -> bool:
        if all(self.__physical_qubits.has_record(label) for label in labels):
            self.append(
                "DETECTOR", map(self.__physical_qubits.retrieve_target_rec, labels)
            )
            self.__postselection_mask.append(postselected)
            return True
        logging.warning(f"Requested some unrecorded measurement [request:{labels}]")
        for label in labels:
            if not self.__physical_qubits.has_record(label):
                logging.warning(f"> {label} not recorded")
        return False

    def attach_observable(self, index: int, *extras: str):
        self.append(
            "OBSERVABLE_INCLUDE",
            map(self.__physical_qubits.retrieve_target_rec, [*extras]),
            index,
        )

    def append_observable(
        self,
        index: int,
        label: str,
        observable: dict[int, str],
        *extras: str,
        flip: bool = False,
        noiseless: bool = True,
    ):
        tag = NOISELESS if noiseless else ""
        pauli = stim.PauliString(observable)
        self.append("MPP", -pauli if flip else pauli, tag=tag)
        self.__physical_qubits.record_measurement(label)
        self.append(
            "OBSERVABLE_INCLUDE",
            map(self.__physical_qubits.retrieve_target_rec, [label, *extras]),
            index,
        )
        self.append_tick(tag=tag)

    def append_tick(self, tag: str = ""):
        if isinstance(self.__circuit, stim.Circuit):
            self.__circuit.append("TICK", tag=tag)

    def __update_internal_counters(
        self, name: str, targets: list[Union[int, stim.GateTarget, stim.PauliString]]
    ):
        match name:
            case "CX":
                self.__num_cnots += sum(1 for _ in targets) // 2
            case "DETECTOR":
                self.__num_detectors += 1
            case "M" | "MR" | "MX" | "MRX" | "MY" | "MRY" | "MZ" | "MRZ" | "MPP":
                self.__num_measurements += (
                    1 if name == "MPP" else sum(1 for _ in targets)
                )
        if name not in ("QUBIT_COORDS", "DETECTOR", "OBSERVABLE_INCLUDE"):
            for target in targets:
                if isinstance(target, int):
                    self.__used_qubits.add(target)
                elif isinstance(target, stim.GateTarget):
                    self.__used_qubits.add(target.value)
                elif isinstance(target, stim.PauliString):
                    self.__used_qubits.update(target.pauli_indices())
                else:
                    raise ValueError(f"Target is unacceptable [{target}].")

    def append(
        self,
        name: str,
        targets: Union[
            int,
            stim.GateTarget,
            stim.PauliString,
            Iterable[Union[int, stim.GateTarget, stim.PauliString]],
        ],
        arg: Union[float, Iterable[float], None] = None,
        tag: str = "",
    ):
        targets = list(targets) if isinstance(targets, Iterable) else [targets]

        self.__update_internal_counters(name, targets)
        self.__circuit.append(name, targets, arg, tag=tag)

    def detectors_report(self, open_boundaries: bool = False):
        print("Detector statistics : ")
        print(
            f"> Measurement records : {len(self.__physical_qubits.measurements_index)}"
        )
        print(
            f"> Number of detectors : {self.num_detectors} [postselected:{sum(int(ps) for ps in self.__postselection_mask)}]"
        )

        gauge_found = False
        try:
            self.as_stim().detector_error_model(allow_gauge_detectors=False)
        except ValueError:
            gauge_found = True
        missing_detectors = self.missing_detectors(unknown_input=open_boundaries)
        print(f"> Missing detectors : {len(missing_detectors)}")
        for detector in missing_detectors:
            records = list(
                map(
                    lambda neg: self.__physical_qubits.retrieve_record(neg.value),
                    detector.targets_copy(),
                )
            )
            print(f">> Detector : {records}")
        print(f"> Gauge detectors : {'FOUND' if gauge_found else 'NONE'}")

    @staticmethod
    def _remap_target(t: stim.GateTarget, mapping: dict[int, int]) -> stim.GateTarget:
        remapped = t
        if t.is_x_target:
            remapped = stim.target_x(mapping[t.value], t.is_inverted_result_target)
        elif t.is_y_target:
            remapped = stim.target_y(mapping[t.value], t.is_inverted_result_target)
        elif t.is_z_target:
            remapped = stim.target_z(mapping[t.value], t.is_inverted_result_target)
        elif t.is_qubit_target:
            remapped = stim.GateTarget(
                stim.target_inv(mapping[t.value])
                if t.is_inverted_result_target
                else mapping[t.value]
            )
        return remapped

    def compact_qubits(
        self, circuit: stim.Circuit, extra: Iterable[int] = ()
    ) -> tuple[stim.Circuit, dict[int, int]]:
        used = sorted(
            {
                t.value
                for ins in circuit.flattened()
                for t in ins.targets_copy()
                if t.is_qubit_target or t.is_x_target or t.is_y_target or t.is_z_target
            }
            | set(extra)
        )
        mapping = {q: i for i, q in enumerate(used)}
        compact = stim.Circuit()
        for ins in circuit.flattened():
            compact.append(
                stim.CircuitInstruction(
                    ins.name,
                    [self._remap_target(t, mapping) for t in ins.targets_copy()],
                    ins.gate_args_copy(),
                    tag=ins.tag,
                )
            )
        return compact, mapping

    def __str__(self):
        return str(self.__circuit)

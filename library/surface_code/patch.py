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
from typing import Optional, Final, Callable, Iterable

import logging

import stim

from library.circuitry import Circuitry
from library.common import Pauli
from library.qubit_array import QubitArray
from library.utils.stim.noise import NOISELESS

logger = logging.getLogger(__name__)


class SurfaceCodePatch:
    MOMENTS: Final[range] = range(6)

    SCHEDULE: dict[str, dict[str, list[Optional[tuple[float, float]]]]] = {
        "6_STEPS": {
            "X": [(-0.5, -0.5), (+0.5, -0.5), (-0.5, +0.5), (+0.5, +0.5)],
            "Z": [(-0.5, -0.5), (-0.5, +0.5), (+0.5, -0.5), (+0.5, +0.5)],
        },
        "7_STEPS": {
            "X": [(-0.5, -0.5), (+0.5, -0.5), (-0.5, +0.5), None, (+0.5, +0.5)],
            "Z": [(-0.5, -0.5), None, (-0.5, +0.5), (+0.5, -0.5), (+0.5, +0.5)],
        },
    }

    def __init__(
        self,
        qubits: QubitArray,
        distance: int = 3,
        anchor: tuple[int, int] = (1, 1),
        coloring: bool = True,
    ):
        if not SurfaceCodePatch.fits(qubits, distance, anchor):
            raise ValueError("Proposed SurfaceCodePatch doesn't fit in the QubitArray.")

        self.__anchor = anchor
        self.__coloring = coloring
        self.__distance = distance
        self.__physical_qubits = qubits
        self.qubits: dict[str, dict[tuple[float, float], tuple[int, int]]] = dict()

        ax, ay = anchor
        data_qubits: dict[tuple[float, float], tuple[int, int]] = {
            (float(px), float(py)): (qubits[(px, py)], index)
            for index, (px, py) in enumerate(
                itertools.product(range(ax, ax + distance), range(ay, ay + distance))
            )
        }
        self.qubits["D"] = data_qubits

        ancilla_count = (distance**2 - 1) // 2
        width = 1 + (distance // 2)
        locations = []
        for q in range(ancilla_count):
            location = (
                ax + 0.5 + 2 * (q % width) - ((q // width) % 2),
                ay + 0.5 + (q // width),
            )
            locations.append(location)
        locations.sort()

        ancilla0: dict[tuple[float, float], tuple[int, int]] = dict()
        for location in locations:
            ancilla0[location] = (qubits[location], len(ancilla0))

        width = distance // 2
        locations.clear()
        for q in range(ancilla_count):
            location = (
                ax + 0.5 + 2 * (q % width) + ((q // width) % 2),
                ay - 0.5 + (q // width),
            )
            locations.append(location)
        locations.sort()

        ancilla1: dict[tuple[float, float], tuple[int, int]] = dict()
        for location in locations:
            ancilla1[location] = (qubits[location], len(ancilla1))

        self.qubits["X"] = ancilla1 if coloring else ancilla0
        self.qubits["Z"] = ancilla0 if coloring else ancilla1

    @staticmethod
    def fits(qubits: QubitArray, distance: int, anchor: tuple[int, int] = (1, 1)):
        ax, ay = anchor
        return (
            1 <= ax
            and 1 <= ay
            and ax + distance < qubits.dimX
            and ay + distance < qubits.dimY
        )

    @staticmethod
    def make_array(distance: int, counts: tuple[int, int] = (1, 1)) -> QubitArray:
        if distance % 2 != 1:
            raise ValueError("Code distance must be odd.")

        count_h, count_v = counts

        return QubitArray(
            dimensions=(count_h * (distance + 1), count_v * (distance + 1))
        )

    @property
    def coloring(self):
        return self.__coloring

    @property
    def distance(self):
        return self.__distance

    @property
    def anchor(self):
        return self.__anchor

    @property
    def num_qubits(self):
        return sum(len(self.qubits[qt]) for qt in ["X", "Z", "D"])

    @property
    def num_z_ancilla(self):
        return len(self.qubits["Z"])

    @property
    def num_x_ancilla(self):
        return len(self.qubits["X"])

    def logical(self, basis: Pauli, offset: Optional[int] = None) -> dict[int, str]:
        if offset:
            if not (0 <= offset < self.distance):
                raise ValueError(f"Invalid index (0 <= {offset} < distance).")
        else:
            offset = 0

        ax, ay = self.anchor
        match basis:
            case Pauli.X:
                if self.__coloring:
                    return {
                        self.__physical_qubits.qubits[(ax + offset, ay + i)]: "X"
                        for i in range(self.__distance)
                    }
                else:
                    return {
                        self.__physical_qubits.qubits[(ax + i, ay + offset)]: "X"
                        for i in range(self.__distance)
                    }
            case Pauli.Y:
                logical = {}
                for index in range(self.__distance):
                    if index == offset:
                        logical[
                            self.__physical_qubits.qubits[(ax + offset, ay + offset)]
                        ] = "Y"
                    else:
                        logical[
                            self.__physical_qubits.qubits[(ax + offset, ay + index)]
                        ] = "X" if self.__coloring else "Z"
                        logical[
                            self.__physical_qubits.qubits[(ax + index, ay + offset)]
                        ] = "Z" if self.__coloring else "X"
                return logical
            case Pauli.Z:
                if self.__coloring:
                    return {
                        self.__physical_qubits.qubits[(ax + i, ay + offset)]: "Z"
                        for i in range(self.__distance)
                    }
                else:
                    return {
                        self.__physical_qubits.qubits[(ax + offset, ay + i)]: "Z"
                        for i in range(self.__distance)
                    }

    def get_qubits(
        self,
        qtype: str,
        inactive: Callable[[tuple[float, float]], bool] = lambda _: False,
    ):
        return self.__get_qubits(qtype, inactive)

    def __get_qubits(
        self,
        qtype: str,
        inactive: Callable[[tuple[float, float]], bool] = lambda _: False,
    ):
        return ((al, ai) for al, ai in self.qubits[qtype].items() if not inactive(al))

    def get_qubit_index(self, qtype: str, qubit: int) -> int:
        for qb, qi in self.qubits[qtype].values():
            if qb == qubit:
                return qi
        return -1

    def get_qubit_at_location(self, location: tuple[float, float]) -> int:
        return self.qubits["D"][location][0] if location in self.qubits["D"] else -1

    def locate_qubit(self, label: str):
        index = int(label[1:])

        for lc, (_, i) in self.qubits[label[0]].items():
            if i == index:
                return lc

        raise ValueError("Invalid label provided [qubit index not found].")

    def get_polygon(self, px, py):
        return [
            self.get_qubit_at_location((px + dx, py + dy))
            for dx, dy in [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)]
            if self.get_qubit_at_location((px + dx, py + dy)) != -1
        ]

    def get_polygons(
        self,
        inactive: Callable[[tuple[float, float]], bool] = lambda _: False,
        opacity: float = 0.5,
    ):
        polygons = []
        for stabilizer in ["X", "Z"]:
            for location, _ in self.__get_qubits(stabilizer, inactive):
                polygon = self.get_polygon(*location)
                x, y, z = int(stabilizer == "X"), 0, int(stabilizer == "Z")
                polygons.append(
                    f"POLYGON({x},{y},{z},{opacity}) {' '.join(map(str, polygon))}"
                )
        return polygons

    def annotate_detectors(
        self,
        circuitry: Circuitry,
        prefix: str = "SC",
        rounds: Optional[int] = None,
        prepared: Optional[Pauli] = None,
        measured: Optional[Pauli] = None,
        inactive: Callable[[tuple[float, float]], bool] = lambda _: False,
        postselected: bool = False,
    ):
        last = (rounds or self.distance) - 1
        for stabilizer in ["X", "Z"]:
            for ql, (qa, qi) in self.qubits[stabilizer].items():
                if inactive(ql):
                    continue

                if prepared is not None and prepared.name == stabilizer:
                    circuitry.annotate_detector(
                        f"{prefix}0:{stabilizer}{qi}",
                        postselected=postselected,
                    )
                for prev, curr in itertools.pairwise(range(rounds or self.distance)):
                    circuitry.annotate_detector(
                        f"{prefix}{curr}:{stabilizer}{qi}",
                        f"{prefix}{prev}:{stabilizer}{qi}",
                        postselected=postselected,
                    )
                if measured is not None and measured.name == stabilizer:
                    circuitry.annotate_detector(
                        f"{prefix}{last}:{stabilizer}{qi}",
                        *[
                            f"{prefix}{last}:D{self.get_qubit_index('D', qd)}"
                            for qd in self.get_polygon(*ql)
                        ],
                        postselected=postselected,
                    )

    def append_memory(
        self,
        circuit: Circuitry,
        prepare: Optional[Pauli] = None,
        measure: Optional[Pauli] = None,
        prefix: str = "",
    ):
        start = 0
        final = self.__distance - 1
        for rnd in range(self.__distance):
            self.append_round_6steps(
                circuit,
                prepare=prepare if (rnd == start) else None,
                measure=measure if (rnd == final) else None,
                prefix=f"{prefix}:R{rnd}",
            )

    def append_round_6steps(
        self,
        circuit: Circuitry,
        moment: Optional[int] = None,
        prepare: Optional[Pauli] = None,
        measure: Optional[Pauli] = None,
        inactive: Callable[[tuple[float, float]], bool] = lambda _: False,
        prefix: str = "",
    ):
        if moment is None:
            for mmt in SurfaceCodePatch.MOMENTS:
                self.append_round_6steps(
                    circuit, mmt, prepare, measure, inactive, prefix
                )
                circuit.append_tick()
            return

        match moment:
            case 0:
                for stabilizer in ["X", "Z"]:
                    circuit.append(
                        f"R{stabilizer}",
                        [qa for _, (qa, _) in self.__get_qubits(stabilizer, inactive)],
                    )
                if prepare:
                    if prepare == Pauli.Y:
                        raise NotImplementedError("Y-basis preparation not supported.")
                    circuit.append(
                        f"R{prepare.name}",
                        [qd for _, (qd, _) in self.__get_qubits("D", inactive)],
                    )
            case 1 | 2 | 3 | 4:
                targets = []
                for stabilizer in ["X", "Z"]:
                    for (px, py), (qa, _) in self.__get_qubits(stabilizer, inactive):
                        interaction = SurfaceCodePatch.SCHEDULE["6_STEPS"][stabilizer][
                            moment - 1
                        ]
                        if interaction is None:
                            continue
                        dx, dy = interaction
                        qd = self.get_qubit_at_location((px + dx, py + dy))
                        if qd != -1:
                            if stabilizer == "Z":
                                targets.append(qd)
                                targets.append(qa)
                            else:
                                targets.append(qa)
                                targets.append(qd)
                circuit.append("CX", targets)
            case 5:
                for stabilizer in ["X", "Z"]:
                    measured = []
                    for ql, (qa, qi) in self.__get_qubits(stabilizer, inactive):
                        self.__physical_qubits.record_measurement(
                            f"{prefix}:{stabilizer}{qi}", qa
                        )
                        measured.append(qa)
                    circuit.append(f"M{stabilizer}", measured)
                if measure:
                    measured_data = []
                    for dl, (dq, di) in self.__get_qubits("D", inactive):
                        self.__physical_qubits.record_measurement(f"{prefix}:D{di}", dq)
                        measured_data.append(dq)
                    circuit.append(f"M{measure.name}", measured_data)
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    def append_round_7steps(
        self,
        circuit: Circuitry,
        moment: Optional[int] = None,
        prepare: Optional[Pauli] = None,
        measure: Optional[Pauli] = None,
        inactive: Callable[[tuple[float, float]], bool] = lambda _: False,
        prefix: str = "",
    ):
        if moment is None:
            for mmt in range(7):
                self.append_round_7steps(
                    circuit, mmt, prepare, measure, inactive, prefix
                )
                circuit.append_tick()
            return

        match moment:
            case 0:
                for stabilizer in ["X", "Z"]:
                    circuit.append(
                        f"R{stabilizer}",
                        [qa for _, (qa, _) in self.__get_qubits(stabilizer, inactive)],
                    )
                if prepare:
                    if prepare == Pauli.Y:
                        raise NotImplementedError("Y-basis preparation not supported.")
                    circuit.append(
                        f"R{prepare.name}",
                        [qd for _, (qd, _) in self.__get_qubits("D", inactive)],
                    )
            case 1 | 2 | 3 | 4 | 5:
                targets = []
                for stabilizer in ["X", "Z"]:
                    for (px, py), (qa, _) in self.__get_qubits(stabilizer, inactive):
                        interaction = SurfaceCodePatch.SCHEDULE["7_STEPS"][stabilizer][
                            moment - 1
                        ]
                        if interaction is None:
                            continue
                        dx, dy = interaction
                        qd = self.get_qubit_at_location((px + dx, py + dy))
                        if qd != -1:
                            if stabilizer == "Z":
                                targets.append(qd)
                                targets.append(qa)
                            else:
                                targets.append(qa)
                                targets.append(qd)
                circuit.append("CX", targets)
            case 6:
                for stabilizer in ["X", "Z"]:
                    measured = []
                    for ql, (qa, qi) in self.__get_qubits(stabilizer, inactive):
                        self.__physical_qubits.record_measurement(
                            f"{prefix}:{stabilizer}{qi}", qa
                        )
                        measured.append(qa)
                    circuit.append(f"M{stabilizer}", measured)
                if measure:
                    measured_data = []
                    for dl, (dq, di) in self.__get_qubits("D", inactive):
                        self.__physical_qubits.record_measurement(f"{prefix}:D{di}", dq)
                        measured_data.append(dq)
                    circuit.append(f"M{measure.name}", measured_data)
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")

    def annotate_stabilizers(
        self,
        circuitry: Circuitry,
        inactive: Callable[[tuple[float, float]], bool] = lambda _: False,
        prefix: str = "SFC:STB",
        noiseless: bool = True,
    ):
        tag = NOISELESS if noiseless else ""
        stabilizer = "X"
        x_ancilla = list(self.__get_qubits(stabilizer, inactive))

        for location, (xq, xi) in filter(
            lambda xa: (xa[0][0] - 0.5) % 2.0 == 1.0, x_ancilla
        ):
            polygon = self.get_polygon(*location)
            circuitry.append(
                "MPP", stim.PauliString({q: stabilizer for q in polygon}), tag=tag
            )
            self.__physical_qubits.record_measurement(f"{prefix}:{stabilizer}{xi}", xq)
        circuitry.append_tick(tag=tag)

        for location, (xq, xi) in filter(
            lambda xa: (xa[0][0] - 0.5) % 2.0 == 0.0, x_ancilla
        ):
            polygon = self.get_polygon(*location)
            circuitry.append(
                "MPP", stim.PauliString({q: stabilizer for q in polygon}), tag=tag
            )
            self.__physical_qubits.record_measurement(f"{prefix}:{stabilizer}{xi}", xq)
        circuitry.append_tick(tag=tag)

        stabilizer = "Z"
        z_ancilla = list(self.__get_qubits(stabilizer, inactive))

        for location, (zq, zi) in filter(
            lambda za: (za[0][1] - 0.5) % 2.0 == 1.0, z_ancilla
        ):
            polygon = self.get_polygon(*location)
            circuitry.append(
                "MPP", stim.PauliString({q: stabilizer for q in polygon}), tag=tag
            )
            self.__physical_qubits.record_measurement(f"{prefix}:{stabilizer}{zi}", zq)
        circuitry.append_tick(tag=tag)

        for location, (zq, zi) in filter(
            lambda za: (za[0][1] - 0.5) % 2.0 == 0.0, z_ancilla
        ):
            polygon = self.get_polygon(*location)
            circuitry.append(
                "MPP", stim.PauliString({q: stabilizer for q in polygon}), tag=tag
            )
            self.__physical_qubits.record_measurement(f"{prefix}:{stabilizer}{zi}", zq)
        circuitry.append_tick(tag=tag)

    def append_inject_preparation(
        self,
        circuitry: Circuitry,
        moment: Optional[int] = None,
        prefix: str = "SFC",
        noiseless: bool = True,
        offset: int = 0,
    ):
        """Append a noiseless preparation of an S-phase (with T-phase tag) into this Surface Code."""
        injecting_moments = self.distance + 4
        if moment is None:
            for moment in range(injecting_moments):
                self.append_inject_preparation(
                    circuitry, moment, prefix, noiseless, offset
                )
                circuitry.append_tick(tag=NOISELESS)
        else:
            extra_x = self.__physical_qubits[self.anchor[0], self.anchor[1] - 1.0]
            extra_z = self.__physical_qubits[self.anchor[0] - 1.0, self.anchor[1]]

            preparation_tag = NOISELESS if noiseless else ""

            if moment == 0:
                circuitry.append("RX", extra_x, tag=preparation_tag)
                circuitry.append("RZ", extra_z, tag=preparation_tag)
            elif moment == 1:
                inject_tag = f"{(NOISELESS + ',') if noiseless else ''}proxy:T"
                circuitry.append("S", extra_x, tag=inject_tag)
            elif moment == 2:
                circuitry.append("CX", [extra_x, extra_z], tag=preparation_tag)
            elif 2 < moment <= self.distance + 2:
                layer = moment - 3
                control_x = self.get_qubit_at_location(
                    (
                        self.anchor[0] + (self.distance - layer - 1),
                        self.anchor[1] + offset,
                    )
                )
                target_z = self.get_qubit_at_location(
                    (self.anchor[0] + offset, self.anchor[1] + layer)
                )
                circuitry.append(
                    "CX", [control_x, extra_x, extra_z, target_z], tag=preparation_tag
                )
            elif moment == injecting_moments - 1:
                circuitry.append("MX", extra_z, tag=preparation_tag)
                self.__physical_qubits.record_measurement(f"{prefix}:Z", extra_z)
                circuitry.append("MZ", extra_x, tag=preparation_tag)
                self.__physical_qubits.record_measurement(f"{prefix}:X", extra_x)

    def append_decode_measurement(
        self,
        circuitry: Circuitry,
        moment: Optional[int] = None,
        prefix: str = "SFC",
        noiseless: bool = True,
        corrections: Iterable[str] = (),
        offset: int = 0,
    ):
        """Append a noiseless measurement of an S-phase (with T-phase tag) from this Surface Code."""
        decoding_moments = self.distance + 4
        if moment is None:
            for moment in range(decoding_moments):
                self.append_decode_measurement(
                    circuitry, moment, prefix, noiseless, corrections, offset
                )
                circuitry.append_tick(tag=NOISELESS)
        else:
            extra_x = self.__physical_qubits[self.anchor[0], self.anchor[1] - 1.0]
            extra_z = self.__physical_qubits[self.anchor[0] - 1.0, self.anchor[1]]

            measurement_tag = NOISELESS if noiseless else ""

            if moment == 0:
                circuitry.append("RX", extra_z, tag=measurement_tag)
                circuitry.append("RZ", extra_x, tag=measurement_tag)
            elif 1 <= moment <= self.distance:
                layer = moment - 1
                control_x = self.get_qubit_at_location(
                    (self.anchor[0] + layer, self.anchor[1] + offset)
                )
                target_z = self.get_qubit_at_location(
                    (
                        self.anchor[0] + offset,
                        self.anchor[1] + (self.distance - layer - 1),
                    )
                )
                circuitry.append(
                    "CX", [control_x, extra_x, extra_z, target_z], tag=measurement_tag
                )
            elif moment == decoding_moments - 3:
                circuitry.append("CX", [extra_x, extra_z], tag=measurement_tag)
                for label in corrections:
                    circuitry.append(
                        "CX",
                        [self.__physical_qubits.retrieve_target_rec(label), extra_x],
                        tag=measurement_tag,
                    )
            elif moment == decoding_moments - 2:
                decode_tag = f"{(NOISELESS + ',') if noiseless else ''}proxy:T_DAG"
                circuitry.append("S_DAG", extra_x, tag=decode_tag)
            elif moment == decoding_moments - 1:
                circuitry.append("MX", extra_x, tag=measurement_tag)
                self.__physical_qubits.record_measurement(f"{prefix}:X", extra_x)
                circuitry.append("MZ", extra_z, tag=measurement_tag)
                self.__physical_qubits.record_measurement(f"{prefix}:Z", extra_z)
            else:
                raise ValueError(f"Moment {moment} not recognized.")

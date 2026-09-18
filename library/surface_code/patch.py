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
from typing import Optional, Final, Callable

import logging

from library.circuitry import Circuitry
from library.common import Pauli
from library.qubit_array import QubitArray

logger = logging.getLogger(__name__)


class SurfaceCodePatch:
    MOMENTS: Final[range] = range(6)
    SCHEDULE = {
        "X" : [ (-0.5, -0.5) , (+0.5, -0.5) , (-0.5, +0.5) , (+0.5, +0.5) ],
        "Z" : [ (-0.5, -0.5) , (-0.5, +0.5) , (+0.5, -0.5) , (+0.5, +0.5) ]
    }

    def __init__(self, qubits: QubitArray, distance: int = 3, anchor: tuple[int,int] = (1, 1)):
        self.__anchor = anchor
        self.__distance = distance
        self.__physical_qubits = qubits
        self.__qubits = dict()

        ax, ay = anchor
        data_qubits: dict[tuple[float, float], tuple[int,int]] = {
            location : (qubits[location], index)
            for index, location in enumerate(itertools.product(
                range(ax, ax + distance),
                range(ay, ay + distance)
            ))
        }
        self.__qubits['D'] = data_qubits

        ancilla_count = (distance**2 - 1) // 2
        width = 1 + (distance // 2)
        z_ancilla: dict[tuple[float,float], tuple[int,int]] = dict()
        for q in range(ancilla_count):
            location = (ax + 0.5 + 2 * (q % width) - ((q // width) % 2), ay + 0.5 + (q // width))
            z_ancilla[location] = (qubits[location], len(z_ancilla))
        width = distance // 2
        x_ancilla: dict[tuple[float,float], tuple[int,int]] = dict()
        for q in range(ancilla_count):
            location = (ax + 0.5 + 2 * (q % width) + ((q // width) % 2), ay - 0.5 + (q // width))
            x_ancilla[location] = (qubits[location], len(x_ancilla))
        self.__qubits['X'] = x_ancilla
        self.__qubits['Z'] = z_ancilla

    @property
    def distance(self):
        return self.__distance

    @property
    def anchor(self):
        return self.__anchor

    @property
    def num_qubits(self):
        return sum(len(self.__qubits[qt]) for qt in ['X', 'Z', 'D'])

    @property
    def num_z_ancilla(self):
        return len(self.__qubits['Z'])

    @property
    def num_x_ancilla(self):
        return len(self.__qubits['X'])

    def logical(self, basis: Pauli):
        ax, ay = self.anchor
        match basis:
            case Pauli.X:
                return {self.__physical_qubits.qubits[(ax, ay + i)]: "X" for i in range(self.__distance)}
            case Pauli.Y:
                logical = {}
                for i in range(self.__distance):
                    if i == 0:
                        logical[self.__physical_qubits.qubits[(ax, ay)]] = "Y"
                    else:
                        logical[self.__physical_qubits.qubits[(ax, ay + i)]] = "X"
                        logical[self.__physical_qubits.qubits[(ax + i, ay)]] = "Z"
                return logical
            case Pauli.Z:
                return {self.__physical_qubits.qubits[(ax + i, ay)]: "Z" for i in range(self.__distance)}

    def __get_qubits(self, qtype: str, inactive: Callable[[tuple[float,float]], bool] = lambda _: False):
        return iter(
            (al, ai) for al, ai in self.__qubits[qtype].items() if not inactive(al)
        )

    def get_qubit_index(self, qtype: str, qubit: int) -> int:
        for qb, qi in self.__qubits[qtype].values():
            if qb == qubit:
                return qi
        raise ValueError(f"Invalid qubit {qubit} requested.")

    def get_qubit_at_location(self, location: tuple[float, float]) -> int:
        return self.__qubits['D'][location][0] if location in self.__qubits['D']  else -1

    def __get_polygon(self, px, py):
        return [
            self.get_qubit_at_location( (px+dx, py+dy) ) for dx, dy in
            [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)]
            if self.get_qubit_at_location( (px+dx, py+dy) ) != -1
        ]

    def get_polygons(self, inactive: Callable[[tuple[float,float]], bool] = lambda _: False, opacity: float = 0.5):
        polygons = []
        for stabilizer in ['X', 'Z']:
            for location, _ in self.__get_qubits(stabilizer, inactive):
                polygon = self.__get_polygon(*location)
                x, y, z = int(stabilizer == 'X'), 0, int(stabilizer == 'Z')
                polygons.append(f"#!pragma POLYGON({x},{y},{z},{opacity}) {" ".join(map(str, polygon))}")
        return polygons

    def annotate_detectors(self, circuitry: Circuitry, rounds: int, prefix: str = "SC", prepared: Optional[Pauli] = None):
        if prepared is not None:
            stabilizer = prepared.name
            for qa in range(len(self.__qubits[prepared.name])):
                label = f"SC0:{stabilizer}{qa}"
                circuitry.annotate_detector(label)
        for stabilizer in ['X', 'Z']:
            for qa in range(len(self.__qubits[stabilizer])):
                for prev, curr in itertools.pairwise(range(rounds)):
                        circuitry.annotate_detector(
                            f"{prefix}{curr}:{stabilizer}{qa}", f"{prefix}{prev}:{stabilizer}{qa}"
                        )

    def append_memory(
            self, circuit: Circuitry, memory: int,
            prepare: Optional[Pauli] = None, measure: Optional[Pauli] = None,
            full_ft: bool = True, prefix: str = ""
    ):
        start = 0
        final = self.__distance - 1
        for rnd in range(self.__distance if full_ft else 1):
            self.append_round(
                circuit,
                prepare = prepare if (rnd == start) else None,
                measure = measure if (rnd == final) else None,
                prefix = f"{prefix}:M{memory}:R{rnd}"
            )

    def append_round(
        self, circuit: Circuitry, prepare: Optional[Pauli] = None, measure: Optional[Pauli] = None,
        inactive: Callable[[tuple[float,float]], bool] = lambda _: False, prefix: str = ""
    ):
        for mmt in SurfaceCodePatch.MOMENTS:
            self.append_round_slice(circuit, mmt, prepare, measure, inactive, prefix)
            circuit.append_tick()

    def locate_qubit(self, label: str):
        index = int(label[1:])

        for lc, (_, i) in self.__qubits[label[0]].items():
            if i == index:
                return lc

        raise ValueError("Invalid label provided [qubit index not found].")

    def append_round_slice(
        self, circuit: Circuitry, moment: int, prepare: Optional[Pauli] = None, measure: Optional[Pauli] = None,
        inactive: Callable[[tuple[float,float]], bool] = lambda _: False, prefix: str = ""
    ):
        match moment:
            case 0:
                for stabilizer in ['X', 'Z']:
                    circuit.append(f"R{stabilizer}", [qa for _, (qa,_) in self.__get_qubits(stabilizer, inactive)])
                if prepare:
                    circuit.append(f"R{prepare.name}", [qd for _, (qd,_) in self.__get_qubits('D', inactive)])
            case 1 | 2 | 3 | 4:
                targets = []
                for stabilizer in ['X', 'Z']:
                    for (px,py), (qa, _) in self.__get_qubits(stabilizer, inactive):
                            dx, dy = SurfaceCodePatch.SCHEDULE[stabilizer][moment - 1]
                            qd = self.get_qubit_at_location( (px+dx, py+dy) )
                            if qd != -1:
                                if stabilizer == 'Z':
                                    targets.append(qd)
                                    targets.append(qa)
                                else:
                                    targets.append(qa)
                                    targets.append(qd)
                circuit.append("CX", targets)
            case 5:
                for stabilizer in ['X', 'Z']:
                    measured = []
                    for ql, (qa, qi) in self.__get_qubits(stabilizer, inactive):
                        self.__physical_qubits.record_measurement(qa, f"{prefix}:{stabilizer}{qi}")
                        measured.append(qa)
                    circuit.append(f"M{stabilizer}", measured)
                if measure:
                    measured_data = []
                    for dl, (dq, di) in self.__get_qubits('D', inactive):
                        self.__physical_qubits.record_measurement(dq, f"{prefix}:D{di}")
                        measured_data.append(dq)
                    circuit.append(f"M{measure.name}", measured_data)
            case _:
                logger.warning(f"Nothing to do at requested moment [{moment}]")
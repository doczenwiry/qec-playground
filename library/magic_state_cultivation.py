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

from library.qubit_array import QubitArray


class MagicStateCultivation:
    CORNERS: list[tuple[float,float]] = [(-0.5, -0.5), (+0.5, -0.5), (+0.5, +0.5), (-0.5, +0.5)]

    def __init__(self, qubits: QubitArray, distance: int, anchor: tuple[int, int]):
        self.__qubits = qubits
        self.__anchor = anchor
        self.__distance= distance

    def get_polygons(self, opacity: float = 0.5):
        polygons = []

        # Surface Code Above
        ax, ay = self.__anchor
        sx, sy = (3, ay-3)
        for ancilla in range(self.__distance):
            px, py = sx - 0.5, sy + 0.5
            x, z = int(ancilla % 2 == 1), int(ancilla % 2 == 0)
            polygon = [self.__qubits[px + ancilla + dx, py + dy] for dx, dy in MagicStateCultivation.CORNERS if sx <= px + ancilla + dx]
            polygons.append(f"POLYGON({x},0,{z},{opacity}) {" ".join(map(str, polygon))}")
            if ancilla % 2 == 0 and ancilla > 0:
                polygon = [self.__qubits[px + ancilla + dx, py + dy] for dx, dy in [(-0.5, +0.5), (+0.5, +0.5)] if
                           sx <= px + ancilla + dx]
                polygons.append(f"POLYGON(1,0,0,{opacity}) {" ".join(map(str, polygon))}")

        # Surface Code Below
        sx, sy = (3, ay + self.__distance + 1)
        for ancilla in range(self.__distance):
            px, py = sx + 0.5, sy - 0.5
            x, z = int(ancilla % 2 == 1), int(ancilla % 2 == 0)
            polygon = [self.__qubits[px + ancilla + dx, py + dy] for dx, dy in MagicStateCultivation.CORNERS if px + ancilla + dx < sx + self.__distance]
            polygons.append(f"POLYGON({x},0,{z},{opacity}) {" ".join(map(str, polygon))}")
            if ancilla % 2 == 0 and ancilla < self.__distance - 1:
                polygon = [self.__qubits[px + ancilla + dx, py + dy] for dx, dy in [(-0.5, -0.5), (+0.5, -0.5)] if
                           sx <= px + ancilla + dx]
                polygons.append(f"POLYGON(1,0,0,{opacity}) {" ".join(map(str, polygon))}")

        # Surface Code Left
        sx, sy = (ax-3, ay)
        for ancilla in range(self.__distance):
            px, py = sx + 0.5, sy + 0.5
            x, z = int(ancilla % 2 == 0), int(ancilla % 2 == 1)
            polygon = [self.__qubits[px + dx, py + ancilla + dy] for dx, dy in MagicStateCultivation.CORNERS if py + ancilla + dy < sy + self.__distance]
            polygons.append(f"POLYGON({x},0,{z},{opacity}) {" ".join(map(str, polygon))}")
            if ancilla % 2 == 0 and ancilla < self.__distance - 1:
                polygon = [self.__qubits[px + dx, py + ancilla + dy] for dx, dy in [(+0.5, -0.5), (+0.5, +0.5)] if
                           sy <= py + ancilla + dy]
                polygons.append(f"POLYGON(0,0,1,{opacity}) {" ".join(map(str, polygon))}")

        # Surface Code Right
        sx, sy = (ax + self.__distance + 1, ay)
        for ancilla in range(self.__distance):
            px, py = sx + 0.5, sy - 0.5
            x, z = int(ancilla % 2 == 0), int(ancilla % 2 == 1)
            polygon = [self.__qubits[px + dx, py + ancilla + dy] for dx, dy in MagicStateCultivation.CORNERS if sy <= py + ancilla + dy]
            polygons.append(f"POLYGON({x},0,{z},{opacity}) {" ".join(map(str, polygon))}")
            if ancilla % 2 == 0 and 0 < ancilla:
                polygon = [self.__qubits[px + dx, py + ancilla + dy] for dx, dy in [(-0.5, -0.5), (-0.5, +0.5)] if
                           sy <= py + ancilla + dy]
                polygons.append(f"POLYGON(0,0,1,{opacity}) {" ".join(map(str, polygon))}")

        return polygons
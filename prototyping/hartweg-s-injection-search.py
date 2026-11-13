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

import argparse
from collections import Counter

import clingo
from pathlib import Path
import stim
import webbrowser


def solve(files, consts):
    """Run clingo on the given .lp files; return the shown atoms of the first answer, or None if UNSAT."""
    ctl = clingo.Control([arg for k, v in consts.items() for arg in ("-c", f"{k}={v}")])
    for f in files:
        ctl.load(f)
    ctl.ground([("base", [])])
    atoms = None
    with ctl.solve(yield_=True) as handle:
        for model in handle:
            atoms = model.symbols(shown=True)
            break
    return atoms


def atoms_to_circuit(atoms, n, depth):
    """Answer atoms -> (resets dict, prep circuit, body circuit)."""
    reset_gate = {"x": "RX", "y": "RY", "z": "R"}
    resets = {q: "R" for q in range(n)}
    layers = [[] for _ in range(depth)]
    for a in atoms:
        args = [
            x.number if x.type == clingo.SymbolType.Number else x.name
            for x in a.arguments
        ]
        if a.name == "reset":
            resets[args[0]] = reset_gate[args[1]]
        elif a.name in ("cx", "cz"):
            layers[args[0] - 1].append(f"{a.name.upper()} {args[1]} {args[2]}")
        elif a.name in ("s", "h"):
            layers[args[0] - 1].append(f"{a.name.upper()} {args[1]}")

    layers = cancel_pairs(layers)

    prep = stim.Circuit("\n".join(f"{g} {q}" for q, g in sorted(resets.items())))
    body = stim.Circuit(
        "\n".join("TICK\n" + "\n".join(sorted(layer)) for layer in layers)
    )
    return resets, prep, body


def solve_gf2(A, b, n):
    """One solution f of A·f = b over GF(2) (rows of A have n entries)."""
    rows = [list(a) + [bb] for a, bb in zip(A, b)]
    piv = 0
    for col in range(n):
        r = next((i for i in range(piv, len(rows)) if rows[i][col]), None)
        if r is not None:
            rows[piv], rows[r] = rows[r], rows[piv]
            for i in range(len(rows)):
                if i != piv and rows[i][col]:
                    rows[i] = [u ^ v for u, v in zip(rows[i], rows[piv])]
            piv += 1
    f = [0] * n
    for row in rows[:piv]:
        f[row.index(1)] = row[n]
    return f


def expected_signs(prep, body, targets):
    """+1/-1 for each MPP target on the circuit without any Pauli corrections."""
    sim = stim.TableauSimulator()
    sim.do(prep + body)
    return [sim.peek_observable_expectation(p) for p in targets]


def fix_signs(resets, prep, body, targets):
    """Return prep + Pauli flips + body with every target deterministically +1."""
    n = len(resets)
    sim = stim.TableauSimulator()
    sim.do(prep + body)
    b = [int(sim.peek_observable_expectation(p) == -1) for p in targets]  # rows to flip

    padded = (
        stim.Circuit(f"I {' '.join(map(str, range(n)))}") + body
    )  # keep the tableau full size
    inv = stim.Tableau.from_circuit(padded).inverse()
    letter = {"R": "Z", "RX": "X", "RY": "Y"}
    A = [
        [int(str(inv(p))[1 + q] == letter[resets[q]]) for q in range(n)]
        for p in targets
    ]
    f = solve_gf2(A, b, n)

    flip_gate = {"R": "X", "RX": "Z", "RY": "X"}
    fix = stim.Circuit(
        "\n".join(f"{flip_gate[resets[q]]} {q}" for q in range(n) if f[q])
    )
    return prep + fix + body


def group_to_pauli(group, n):
    p = stim.PauliString(n)
    for t in group:
        p *= stim.PauliString({t.value: t.pauli_type})
        if t.is_inverted_result_target:
            p *= -1
    return p


def mpp_targets(problem: stim.Circuit, n):
    """The MPP products of the problem file as PauliStrings: the same rows patch.lp encodes."""
    targets = []
    for inst in problem.flattened():
        if inst.name == "MPP":
            for group in inst.target_groups():
                targets.append(group_to_pauli(group, n))
    return targets


make = {"X": stim.target_x, "Y": stim.target_y, "Z": stim.target_z}


def sign_mpp_lines(lines, signs):
    """Replace every MPP line by its signed version, in place; other lines are kept as they are."""
    out = []
    i = 0
    for line in lines:
        if line.lstrip().startswith("MPP"):
            inst = stim.Circuit(line)[0]
            targets = []
            for group in inst.target_groups():
                group = list(group)
                if signs[i] == -1:
                    t = group[0]
                    group[0] = make[t.pauli_type](
                        t.value, invert=not t.is_inverted_result_target
                    )
                product = [x for t in group for x in (t, stim.target_combiner())][:-1]
                targets += product
                i += 1
            signed = stim.Circuit()
            signed.append("MPP", targets, tag=inst.tag)
            out.append(str(signed))
        else:
            out.append(line)
    return out


def annotations(problem, observable_tags=("OBSERVABLE", "logical")):
    """One DETECTOR per stabilizer MPP product, OBSERVABLE_INCLUDE for observable ones."""
    roles = []
    for inst in problem.flattened():
        if inst.name == "MPP":
            role = "obs" if inst.tag in observable_tags else "det"
            roles += [role] * len(inst.target_groups())
    k = len(roles)
    lines = []
    for i, role in enumerate(roles):
        rec = f"rec[{i - k}]"
        lines.append(
            f"OBSERVABLE_INCLUDE(0) {rec}" if role == "obs" else f"DETECTOR {rec}"
        )
    return lines


def cancel_pairs(layers):
    layers = [list(lr) for lr in layers]
    last = {}  # qubit -> (layer index, gate string)
    for t, layer in enumerate(layers):
        for g in list(layer):
            qs = g.split()[1:]
            prev = {last.get(q) for q in qs}
            if len(prev) == 1 and None not in prev:
                pt, pg = prev.pop()
                if pg == g:  # same gate, nothing in between on these qubits
                    layers[pt].remove(pg)
                    layer.remove(g)
                    for q in qs:
                        last.pop(q)
                    continue
            for q in qs:
                last[q] = (t, g)
    return [lr for lr in layers if lr]  # drop layers that became empty


def gate_counts(circuit):
    counts = Counter()
    for inst in circuit.flattened():
        data = stim.gate_data(inst.name)
        if data.is_unitary or data.is_reset:
            n = len(inst.targets_copy())
            counts[inst.name] += n // 2 if data.is_two_qubit_gate else n
        elif inst.name == "MPP":
            counts["MPP"] += len(inst.target_groups())
    return counts


def ancilla_positions(ancilla_edges, coords):
    """ancilla_edges: {ancilla: [data qubits it couples to]}; coords: {data qubit: (x, y)}."""
    positions = {}
    for a in sorted(
        ancilla_edges, key=lambda a: -len(ancilla_edges[a])
    ):  # bulk ancillas first
        candidates = None
        for q in ancilla_edges[a]:
            x, y = coords[q]
            around = {(x + dx, y + dy) for dx in (-0.5, 0.5) for dy in (-0.5, 0.5)}
            candidates = around if candidates is None else candidates & around
        candidates -= set(positions.values())
        positions[a] = (
            candidates.pop() if len(candidates) == 1 else None
        )  # None: ambiguous
    return positions


def crumble_url(text):
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#!pragma "):
            line = line[len("#!pragma ") :]  # Crumble reads POLYGON as an instruction
        elif line.startswith("#"):
            line = ""  # ordinary comments are dropped
        if line:
            line = (
                line.replace("QUBIT_COORDS", "Q")
                .replace(", ", ",")
                .replace(") ", ")")
                .replace(" ", "_")
            )
            lines.append(line)
    return "https://algassert.com/crumble#circuit=" + ";".join(lines)


solver = Path(__file__).with_name("hartweg-s-injection.solver.pl")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "problem", type=str, help="stim file with QUBIT_COORDS and MPPs"
    )
    parser.add_argument("patch", type=str, help="file encoding the data of the problem")
    parser.add_argument("--annotate", action="store_true")
    parser.add_argument("--depth", type=int, default=7)
    parser.add_argument("--max2q", type=int, default=100)
    parser.add_argument("--maxs", type=int, default=200)
    args = parser.parse_args()

    problem = stim.Circuit.from_file(args.problem)

    lines = Path(args.problem).read_text().splitlines()
    first_mpp = next(
        (
            i
            for i, line in enumerate(lines)
            if line.lstrip().startswith("#!pragma POLYGON")
        ),
        len(lines),
    )
    poly_end = first_mpp
    while poly_end < len(lines) and lines[poly_end].lstrip().startswith(
        "#!pragma POLYGON"
    ):
        poly_end += 1
    polygons = lines[first_mpp:poly_end]

    atoms = solve(
        [str(solver), args.patch],
        {"depth": args.depth, "max2q": args.max2q, "maxs": args.maxs},
    )
    if atoms is None:
        print("UNSATISFIABLE")
    else:
        coords = {q: tuple(c) for q, c in problem.get_final_qubit_coordinates().items()}
        ancilla_edges: dict[int, list[int]] = {}
        for a in atoms:
            if a.name == "edge":
                p, q = (x.number for x in a.arguments)
                if (p in coords) != (q in coords):
                    data, anc = (p, q) if p in coords else (q, p)
                    ancilla_edges.setdefault(anc, []).append(data)
        positions = ancilla_positions(ancilla_edges, coords)
        coord_lines = [
            f"QUBIT_COORDS({p[0]:g}, {p[1]:g}) {a}"
            for a, p in sorted(positions.items())
            if p is not None
        ]

        n = max([*coords, *positions]) + 1
        resets, prep, body = atoms_to_circuit(atoms, n, args.depth)
        signs = expected_signs(prep, body, mpp_targets(problem, n))
        solution = prep + body

        postprocessed = (
            lines[:first_mpp]
            + coord_lines
            + polygons
            + [str(solution), "TICK"]
            + sign_mpp_lines(lines[first_mpp:], signs)
        )
        if args.annotate:
            postprocessed += annotations(problem)

        print("Number of gates:")
        for gate, count in gate_counts(solution).items():
            print(f"> {gate} : #{count}")

        webbrowser.open(crumble_url("\n".join(postprocessed)))

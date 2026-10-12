"""Convert a qPerfect MIMIQ circuit (.pb protobuf) to a Stim circuit.

    pip install mimiqcircuits stim
    python pb_to_stim.py in.pb out.stim [--coords coords.txt] [--t-to-s]

Detector / ObservableInclude reference classical bits; they become rec[-k]
lookbacks to the most recent measurement written into each bit.
--t-to-s doubles every diagonal phase angle: T->S, T†->S†, CS->CZ, CCZ->identity
(noise attached to those gates is kept).
Unsupported operations raise an error naming the operation, so nothing is dropped silently.

Thanks, Claude.AI (October 2026)
"""
import argparse, itertools
import mimiqcircuits as mc
import stim

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--coords", help="file with QUBIT_COORDS lines to prepend")
ap.add_argument("--t-to-s", action="store_true")
a = ap.parse_args()

CLIFFORD = {"GateH": "H", "GateX": "X", "GateY": "Y", "GateZ": "Z", "GateS": "S", "GateSDG": "S_DAG",
            "GateSX": "SQRT_X", "GateSXDG": "SQRT_X_DAG", "GateCX": "CX", "GateCY": "CY", "GateCZ": "CZ",
            "GateSWAP": "SWAP", "GateID": "I", "Reset": "R", "ResetZ": "R", "ResetX": "RX", "ResetY": "RY",
            "Measure": "M", "MeasureZ": "M", "MeasureX": "MX", "MeasureY": "MY"}
T_TO_S = {"GateT": "S", "GateTDG": "S_DAG", "GateCS": "CZ", "GateCSDG": "CZ"}
PAULI1 = {"PauliX": "X_ERROR", "PauliY": "Y_ERROR", "PauliZ": "Z_ERROR"}

out = open(a.coords).read().strip().splitlines() if a.coords else []
n_meas = 0
last_meas_of_bit = {}


def lookbacks(bits):
    return " ".join(f"rec[-{n_meas - last_meas_of_bit[b]}]" for b in bits)


def ccz_like(op):
    return (type(op).__name__ == "Control" and op.num_controls == 2
            and type(op.op).__name__ == "GateZ")


for inst in mc.Circuit.loadproto(a.src):
    op, qs, bs = inst.get_operation(), inst.get_qubits(), inst.get_bits()
    name, tq = type(op).__name__, " ".join(map(str, qs))
    if name in ("Measure", "MeasureZ", "MeasureX", "MeasureY"):
        out.append(f"{CLIFFORD[name]} {tq}")
        for b in bs:
            last_meas_of_bit[b] = n_meas; n_meas += 1
    elif name in CLIFFORD:
        out.append(f"{CLIFFORD[name]} {tq}")
    elif a.t_to_s and name in T_TO_S:
        out.append(f"{T_TO_S[name]} {tq}  # was {op}")
    elif a.t_to_s and ccz_like(op):
        out.append(f"# CCZ {tq} -> identity under T->S")
    elif name == "Tick":
        out.append("TICK")
    elif name == "Depolarizing":
        p, n = float(op.getparam("p")), len(qs)
        if n in (1, 2):
            out.append(f"DEPOLARIZE{n}({p}) {tq}")
        else:  # independent-Pauli product with the same Pauli transfer matrix
            k = 4 ** n
            q = (1 - (1 - k * p / (k - 1)) ** (2 / k)) / 2
            for ps in itertools.product("IXYZ", repeat=n):
                if set(ps) != {"I"}:
                    out.append(f"E({q:.12g}) " + " ".join(f"{s}{t}" for s, t in zip(ps, qs) if s != "I"))
    elif name in PAULI1:
        out.append(f"{PAULI1[name]}({float(op.getparam('p'))}) {tq}")
    elif name == "Detector":
        coords = ",".join(map(str, op.notes)) if op.notes else ""
        out.append(f"DETECTOR{'(' + coords + ')' if coords else ''} {lookbacks(bs)}")
    elif name == "ObservableInclude":
        idx = int(op.notes[0]) if op.notes else 0
        out.append(f"OBSERVABLE_INCLUDE({idx}) {lookbacks(bs)}")
    else:
        raise NotImplementedError(f"no Stim equivalent handled for {name}: {op} on {qs}")

text = "\n".join(out) + "\n"
stim.Circuit(text)  # parse check
open(a.dst, "w").write(text)
print(f"wrote {a.dst}: {len(out)} lines, {n_meas} measurements")

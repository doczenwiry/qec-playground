% ---- qubits: 0..8 data, 9..16 measurement ancillas ----
qubit(0..16).
ancilla(9..16).
row(1..9).

% ---- couplers: data qubit ↔ diagonal ancilla only (A < B) ----
edge((0;1;3;4),9).     % ancilla (2.5, 2.5)
edge((4;5;7;8),10).    % ancilla (3.5, 3.5)
edge((6;7),11).        % ancilla (4.5, 2.5)
edge((1;2),12).        % ancilla (1.5, 3.5)
edge((3;4;6;7),13).    % ancilla (3.5, 2.5)
edge((1;2;4;5),14).    % ancilla (2.5, 3.5)
edge((0;3),15).        % ancilla (2.5, 1.5)
edge((5;8),16).        % ancilla (3.5, 4.5)

% ---- MPP rows at the code end (time d), data qubits only ----
x(depth,1,(0;1;3;4)).      % X0 X1 X3 X4
x(depth,2,(4;5;7;8)).      % X4 X5 X7 X8
x(depth,3,(6;7)).          % X6 X7
x(depth,4,(1;2)).          % X1 X2
z(depth,5,(3;4;6;7)).      % Z3 Z4 Z6 Z7
z(depth,6,(1;2;4;5)).      % Z1 Z2 Z4 Z5
z(depth,7,(0;3)).          % Z0 Z3
z(depth,8,(5;8)).          % Z5 Z8
x(depth,9,(0;3;6)).        % Y_L = X0 Y3 X6 Z4 Z5: X part
z(depth,9,(3;4;5)).        %                       Z part
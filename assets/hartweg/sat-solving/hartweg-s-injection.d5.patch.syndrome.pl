% ---- distance 5: qubits 0..24 data, 25..48 measurement ancillas ----
qubit(0..48).
ancilla(25..48).
row(1..25).

% ---- couplers: data qubit <-> diagonal ancilla only (A < B) ----
edge((1;2),25).          % ancilla (1.5, 3.5)
edge((3;4),26).          % ancilla (1.5, 5.5)
edge((0;5),27).          % ancilla (2.5, 1.5)
edge((0;1;5;6),28).      % ancilla (2.5, 2.5)
edge((1;2;6;7),29).      % ancilla (2.5, 3.5)
edge((2;3;7;8),30).      % ancilla (2.5, 4.5)
edge((3;4;8;9),31).      % ancilla (2.5, 5.5)
edge((5;6;10;11),32).    % ancilla (3.5, 2.5)
edge((6;7;11;12),33).    % ancilla (3.5, 3.5)
edge((7;8;12;13),34).    % ancilla (3.5, 4.5)
edge((8;9;13;14),35).    % ancilla (3.5, 5.5)
edge((9;14),36).         % ancilla (3.5, 6.5)
edge((10;15),37).        % ancilla (4.5, 1.5)
edge((10;11;15;16),38).  % ancilla (4.5, 2.5)
edge((11;12;16;17),39).  % ancilla (4.5, 3.5)
edge((12;13;17;18),40).  % ancilla (4.5, 4.5)
edge((13;14;18;19),41).  % ancilla (4.5, 5.5)
edge((15;16;20;21),42).  % ancilla (5.5, 2.5)
edge((16;17;21;22),43).  % ancilla (5.5, 3.5)
edge((17;18;22;23),44).  % ancilla (5.5, 4.5)
edge((18;19;23;24),45).  % ancilla (5.5, 5.5)
edge((19;24),46).        % ancilla (5.5, 6.5)
edge((20;21),47).        % ancilla (6.5, 2.5)
edge((22;23),48).        % ancilla (6.5, 4.5)

% ---- MPP rows at the code end (time depth), data qubits only ----
x(depth,1,(1;2)).            % X 1 2
x(depth,2,(3;4)).            % X 3 4
z(depth,3,(0;5)).            % Z 0 5
x(depth,4,(0;1;5;6)).        % X 0 1 5 6
z(depth,5,(1;2;6;7)).        % Z 1 2 6 7
x(depth,6,(2;3;7;8)).        % X 2 3 7 8
z(depth,7,(3;4;8;9)).        % Z 3 4 8 9
z(depth,8,(5;6;10;11)).      % Z 5 6 10 11
x(depth,9,(6;7;11;12)).      % X 6 7 11 12
z(depth,10,(7;8;12;13)).     % Z 7 8 12 13
x(depth,11,(8;9;13;14)).     % X 8 9 13 14
z(depth,12,(9;14)).          % Z 9 14
z(depth,13,(10;15)).         % Z 10 15
x(depth,14,(10;11;15;16)).   % X 10 11 15 16
z(depth,15,(11;12;16;17)).   % Z 11 12 16 17
x(depth,16,(12;13;17;18)).   % X 12 13 17 18
z(depth,17,(13;14;18;19)).   % Z 13 14 18 19
z(depth,18,(15;16;20;21)).   % Z 15 16 20 21
x(depth,19,(16;17;21;22)).   % X 16 17 21 22
z(depth,20,(17;18;22;23)).   % Z 17 18 22 23
x(depth,21,(18;19;23;24)).   % X 18 19 23 24
z(depth,22,(19;24)).         % Z 19 24
x(depth,23,(20;21)).         % X 20 21
x(depth,24,(22;23)).         % X 22 23
x(depth,25,(0;5;10;15;20)).  % Y_L = Y0 X5 X10 X15 X20 Z1 Z2 Z3 Z4: X part
z(depth,25,(0;1;2;3;4)).     %        Z part (qubit 0 gets both, so Y)
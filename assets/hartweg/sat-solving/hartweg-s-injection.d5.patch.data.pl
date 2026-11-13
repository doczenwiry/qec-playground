% ---- distance 5: data qubits only, 0..24 ----
qubit(0..24).
row(1..25).

% ---- couplers: nearest-neighbour data pairs (A < B) ----
edge(0,1). edge(0,5). edge(1,2). edge(1,6). edge(2,3). edge(2,7).
edge(3,4). edge(3,8). edge(4,9). edge(5,6). edge(5,10). edge(6,7).
edge(6,11). edge(7,8). edge(7,12). edge(8,9). edge(8,13). edge(9,14).
edge(10,11). edge(10,15). edge(11,12). edge(11,16). edge(12,13). edge(12,17).
edge(13,14). edge(13,18). edge(14,19). edge(15,16). edge(15,20). edge(16,17).
edge(16,21). edge(17,18). edge(17,22). edge(18,19). edge(18,23). edge(19,24).
edge(20,21). edge(21,22). edge(22,23). edge(23,24).

% ---- MPP rows at the code end (time depth) ----
x(depth,1,(1;2)).   % X 1 2
x(depth,2,(3;4)).   % X 3 4
z(depth,3,(0;5)).   % Z 0 5
x(depth,4,(0;1;5;6)).   % X 0 1 5 6
z(depth,5,(1;2;6;7)).   % Z 1 2 6 7
x(depth,6,(2;3;7;8)).   % X 2 3 7 8
z(depth,7,(3;4;8;9)).   % Z 3 4 8 9
z(depth,8,(5;6;10;11)).   % Z 5 6 10 11
x(depth,9,(6;7;11;12)).   % X 6 7 11 12
z(depth,10,(7;8;12;13)).   % Z 7 8 12 13
x(depth,11,(8;9;13;14)).   % X 8 9 13 14
z(depth,12,(9;14)).   % Z 9 14
z(depth,13,(10;15)).   % Z 10 15
x(depth,14,(10;11;15;16)).   % X 10 11 15 16
z(depth,15,(11;12;16;17)).   % Z 11 12 16 17
x(depth,16,(12;13;17;18)).   % X 12 13 17 18
z(depth,17,(13;14;18;19)).   % Z 13 14 18 19
z(depth,18,(15;16;20;21)).   % Z 15 16 20 21
x(depth,19,(16;17;21;22)).   % X 16 17 21 22
z(depth,20,(17;18;22;23)).   % Z 17 18 22 23
x(depth,21,(18;19;23;24)).   % X 18 19 23 24
z(depth,22,(19;24)).   % Z 19 24
x(depth,23,(20;21)).   % X 20 21
x(depth,24,(22;23)).   % X 22 23
x(depth,25,(0;5;10;15;20)).   % Y_L = Y0 X5 X10 X15 X20 Z1 Z2 Z3 Z4: X part
z(depth,25,(0;1;2;3;4)).   %        Z part (qubit 0 gets both, so Y)

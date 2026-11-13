qubit(0..8).
row(1..9).

% nearest-neighbour pairs, A < B
edge(0,1). edge(1,2). edge(3,4). edge(4,5). edge(6,7). edge(7,8).
edge(0,3). edge(3,6). edge(1,4). edge(4,7). edge(2,5). edge(5,8).

% MPP rows at the code end (time d); (a;b;c) expands to one fact per value
x(depth,1,(0;1;3;4)).      % X0 X1 X3 X4
x(depth,2,(4;5;7;8)).      % X4 X5 X7 X8
x(depth,3,(6;7)).          % X6 X7
x(depth,4,(1;2)).          % X1 X2
z(depth,5,(3;4;6;7)).      % Z3 Z4 Z6 Z7
z(depth,6,(1;2;4;5)).      % Z1 Z2 Z4 Z5
z(depth,7,(0;3)).          % Z0 Z3
z(depth,8,(5;8)).          % Z5 Z8
x(depth,9,(0;3;6)).        % Y_L = X0 Y3 X6 Z4 Z5: X part
z(depth,9,(3;4;5)).        %                       Z part (qubit 3 gets both, so Y)
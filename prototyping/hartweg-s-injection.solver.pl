% ---- data, generated from your stim file ----
% qubit(0..8).  edge(0,1). edge(0,3). ...           nearest-neighbour pairs, A < B
% row(1..9).    x(d,R,Q) / z(d,R,Q) facts for each MPP row at the code end (time d)
#const depth = 5.
#const max2q = 16.
#const maxs = 1.
layer(1..depth).

% ---- generate: choose gates in each layer ----
{ cx(T,A,B) : edge(A,B) ; cx(T,B,A) : edge(A,B) ; cz(T,A,B) : edge(A,B)
; s(T,Q) : qubit(Q) ; h(T,Q) : qubit(Q) } :- layer(T).
:- h(_,_).

% ---- one operation per qubit per layer ----
busy(T,Q,cx(A,B)) :- cx(T,A,B), Q = (A;B).
busy(T,Q,cz(A,B)) :- cz(T,A,B), Q = (A;B).
busy(T,Q,s)       :- s(T,Q).
busy(T,Q,h)       :- h(T,Q).
:- layer(T), qubit(Q), #count { G : busy(T,Q,G) } > 1.

% ---- going back through layer T: which bits flip ----
fx(T,R,Q) :- cx(T,C,Q), x(T,R,C).                       % CX: X spreads control → target
fz(T,R,Q) :- cx(T,Q,U), z(T,R,U).                       % CX: Z spreads target → control
fz(T,R,Q) :- cz(T,Q,U), x(T,R,U).                       % CZ
fz(T,R,Q) :- cz(T,U,Q), x(T,R,U).
fz(T,R,Q) :- s(T,Q), x(T,R,Q).                          % S: X → Y
fx(T,R,Q) :- h(T,Q), x(T,R,Q), not z(T,R,Q).            % H: swap differing bits
fx(T,R,Q) :- h(T,Q), z(T,R,Q), not x(T,R,Q).
fz(T,R,Q) :- h(T,Q), x(T,R,Q), not z(T,R,Q).
fz(T,R,Q) :- h(T,Q), z(T,R,Q), not x(T,R,Q).

x(T-1,R,Q) :- layer(T), row(R), qubit(Q), x(T,R,Q), not fx(T,R,Q).
x(T-1,R,Q) :- layer(T), row(R), qubit(Q), not x(T,R,Q), fx(T,R,Q).
z(T-1,R,Q) :- layer(T), row(R), qubit(Q), z(T,R,Q), not fz(T,R,Q).
z(T-1,R,Q) :- layer(T), row(R), qubit(Q), not z(T,R,Q), fz(T,R,Q).

% ---- test: rows agree on one basis per qubit at the reset end ----
kind(R,Q,x) :- x(0,R,Q), not z(0,R,Q).
kind(R,Q,y) :- x(0,R,Q), z(0,R,Q).
kind(R,Q,z) :- z(0,R,Q), not x(0,R,Q).
:- kind(R1,Q,K1), kind(R2,Q,K2), K1 != K2.
reset(Q,K) :- kind(_,Q,K).                      % the reset basis, to read off the answer
:- kind(_,Q,y).
:- #count { T,A,B : cx(T,A,B) ; T,A,B : cz(T,A,B) } > max2q.
:- #count { T,Q : s(T,Q) } > maxs.

#show cx/3.  #show cz/3.  #show s/2.  #show h/2.  #show reset/2. #show edge/2.
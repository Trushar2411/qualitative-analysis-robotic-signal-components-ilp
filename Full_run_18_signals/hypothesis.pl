signal_change(S,T,R):-
    signal_unchanged(S,T),
    relation_unchanged(R).

signal_change(S,T,R):-
    signal_increases(S,T),
    relation_increases(R).

signal_change(S,T,R):-
    relation_decreases(R),
    signal_decreases(S,T).
% One target predicate for all 18 signals and all 3 relations.

max_vars(3).
max_body(2).
max_clauses(3).

head_pred(signal_change,3).

body_pred(signal_increases,2).
body_pred(signal_decreases,2).
body_pred(signal_unchanged,2).

body_pred(relation_increases,1).
body_pred(relation_decreases,1).
body_pred(relation_unchanged,1).

% Optional types reduce invalid hypotheses.
type(signal_change,(signal,time,relation)).
type(signal_increases,(signal,time)).
type(signal_decreases,(signal,time)).
type(signal_unchanged,(signal,time)).
type(relation_increases,(relation,)).
type(relation_decreases,(relation,)).
type(relation_unchanged,(relation,)).

direction(signal_change,(in,in,out)).
direction(signal_increases,(in,in)).
direction(signal_decreases,(in,in)).
direction(signal_unchanged,(in,in)).
direction(relation_increases,(out,)).
direction(relation_decreases,(out,)).
direction(relation_unchanged,(out,)).

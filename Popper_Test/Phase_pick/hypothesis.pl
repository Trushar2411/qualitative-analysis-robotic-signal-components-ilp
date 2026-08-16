% ============================================================
% Run 2 - Learned Pick-Phase Hypotheses
% ============================================================

:- consult('bk.pl').
:- consult('hypothesis.pl')

% ------------------------------------------------------------
% H1: Hypothesis learned by Popper
% ------------------------------------------------------------

phase_pick_h1(T) :-
    j2_pos_increases(T),
    j3_pos_decreases(T).


% ------------------------------------------------------------
% H2: Alternative hypothesis returned by Popper
% ------------------------------------------------------------

phase_pick_h2(T) :-
    j1_pos_constant(T),
    j3_pos_decreases(T).


% ------------------------------------------------------------
% H3: Three-condition hypothesis we want to investigate
% ------------------------------------------------------------

phase_pick_h3(T) :-
    j1_pos_constant(T),
    j2_pos_increases(T),
    j3_pos_decreases(T).


% ------------------------------------------------------------
% Individual signal conditions
% ------------------------------------------------------------

pick_j1_constant(T) :-
    j1_pos_constant(T).

pick_j2_increases(T) :-
    j2_pos_increases(T).

pick_j3_decreases(T) :-
    j3_pos_decreases(T).

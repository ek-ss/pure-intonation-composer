from app.rhythm.engine import euclidean_rhythm, humanize, phase_shift, state_transition_graph


def test_euclidean_rhythm_has_exact_pulse_count() -> None:
    pattern = euclidean_rhythm(13, 5)
    assert len(pattern) == 13
    assert sum(pattern) == 5


def test_state_graph_edges_have_hamming_distance_one() -> None:
    graph = state_transition_graph(4)
    assert len(graph["nodes"]) == 16
    assert all(sum(left != right for left, right in zip(source, target)) == 1 for source, target in graph["edges"])


def test_phase_shift_supports_independent_cycle_lengths() -> None:
    shifted = phase_shift([[1, 0, 0], [1, 0, 1, 0]], 12, [0, 1])
    assert shifted[0] == [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0]
    assert len(shifted[1]) == 12


def test_humanization_is_deterministic_with_a_seed() -> None:
    assert humanize([1, 0, 1, 0], 42) == humanize([1, 0, 1, 0], 42)

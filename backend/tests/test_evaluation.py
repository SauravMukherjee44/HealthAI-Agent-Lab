from backend.evaluation.run_agent_eval import run


def test_seed_agent_evaluation_passes():
    result = run()
    assert result["emergency_recall"] == 1.0
    assert result["routing_accuracy"] == 1.0
    assert result["failures"] == []

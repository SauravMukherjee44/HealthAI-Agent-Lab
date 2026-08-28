from backend.app.safety import screen_for_emergency


def test_explicit_denial_of_neurological_warning_signs_is_not_an_emergency():
    result = screen_for_emergency("I have a fever but no stiff neck or confusion")

    assert result.emergency is False


def test_present_neurological_warning_sign_still_escalates():
    result = screen_for_emergency("I have a fever with a stiff neck")

    assert result.emergency is True

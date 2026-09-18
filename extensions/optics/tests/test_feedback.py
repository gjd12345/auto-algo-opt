from artifact_session.feedback import online_diagnostics, prescription_delta
import pytest


def test_signed_focus_and_physical_margin_are_not_normalized_margin():
    facts={"mode":"online","quality_q":.5,"online_feasible":True,
           "constraints":{"focus":{"operator":"<=","metric":"maximum_abs_paraxial_focus_error_mm",
                                      "target":.2,"observed":.1998,"normalized_margin":.001,"passed":True}},
           "profile_results":{"online":{"configurations":[{"focus_error_mm":-.1998,"sensor_z_mm":64.14,"fields":[]}]}}}
    result=online_diagnostics(facts)
    assert result["focus_constraint_margin_mm"]==pytest.approx(.0002)
    assert result["configurations"][0]["paraxial_focus_plane_z_mm"]==pytest.approx(64.3398)
    facts["mode"]="audit"
    with pytest.raises(ValueError):online_diagnostics(facts)


def test_actual_delta_distinguishes_permission_from_execution():
    task={"variables":[{"variable_id":"sensor","path":"/sensor"}]}
    plan={"variables_to_adjust":["sensor"]}
    assert prescription_delta({"sensor":1},{"sensor":1},task,plan)["duplicate_parent"]
    changed=prescription_delta({"sensor":1},{"sensor":2},task,plan)
    assert changed["changes"][0]["delta"]==1
    assert changed["selected_but_unchanged"]==[]

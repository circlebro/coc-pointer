from dataclasses import replace

from helpers import member, war

from coc_pointer.rewards import cwl_is_settled


def cwl(round_no, total=3, in_progress=False, stars=(3,)):
    w = war(
        [member("#P1", "도토리", stars), member("#P2", "제니", stars)],
        war_type="cwl",
        end=f"2026-09-0{round_no}T10:00:00Z",
        opponent_tag=f"#OPP{round_no}",
        in_progress=in_progress,
    )
    return replace(w, round_no=round_no, total_rounds=total)


def test_not_settled_before_every_round_is_on_hand():
    assert not cwl_is_settled([])
    assert not cwl_is_settled([cwl(1), cwl(2)]), "3라운드 중 2라운드만 있다"


def test_not_settled_while_a_war_still_has_attacks_left():
    assert not cwl_is_settled([cwl(1), cwl(2), cwl(3, in_progress=True, stars=())])


def test_settled_when_a_running_war_has_used_every_attack():
    done = cwl(3, in_progress=True)
    assert done.attacks_made == done.attack_slots
    assert cwl_is_settled([cwl(1), cwl(2), done]), "완료 대기도 끝난 것으로 본다"


def test_settled_when_all_rounds_finished():
    assert cwl_is_settled([cwl(1), cwl(2), cwl(3)])

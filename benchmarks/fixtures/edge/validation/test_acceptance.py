from domain import average

def test_average():
    assert average([]) == 0
    assert average([2, 4, 6]) == 4
    assert average([-4, 2]) == -1

from domain import total

def test_total():
    assert total(12.5, 4) == 50
    assert total(8, 0) == 0
    assert total(1.25, 3) == 3.75

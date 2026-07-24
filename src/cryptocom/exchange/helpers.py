import math


def round_up(value: float | str, precision: int) -> float:
    """Rounds number to upper precision 0.13 -> 0.2"""
    value = float(value)
    pwr = math.pow(10, precision)
    return math.ceil(value * pwr) / pwr


def round_down(value: float | str, precision: int) -> float:
    """Rounds number to lower precision 0.13 -> 0.1"""
    value = float(value)
    pwr = math.pow(10, precision)
    return math.floor(value * pwr) / pwr

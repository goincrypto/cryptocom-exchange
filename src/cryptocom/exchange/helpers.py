import math
import typing as TP


def round_up(value: TP.Union[float, str], precision: int) -> float:
    """Rounds number to upper precision 0.13 -> 0.2"""
    value = float(value)
    pwr = 10**precision
    return math.ceil(value * pwr) / pwr


def round_down(value: TP.Union[float, str], precision: int) -> float:
    """Rounds number to lower precision 0.13 -> 0.1"""
    value = float(value)
    pwr = 10**precision
    return math.floor(value * pwr) / pwr

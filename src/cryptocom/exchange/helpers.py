import typing as TP


def round_up(value: TP.Union[float, str], precision: int) -> float:
    """Rounds number to upper precision 0.13 -> 0.2"""
    pwr = 10**precision
    value = float(value)
    rounded = round((value * pwr) / pwr, precision)
    if rounded < value:
        rounded = round((value * pwr + 1) / pwr, precision)
    return rounded


def round_down(value: TP.Union[float, str], precision: int) -> float:
    """Rounds number to lower precision 0.13 -> 0.1"""
    value = float(value)
    pwr = 10**precision
    return round((value * pwr) / pwr, precision)

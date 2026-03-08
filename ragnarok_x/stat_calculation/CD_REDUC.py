from .STAT import Stat
from sympy import Eq


class CD_REDUC(Stat):
    def __init__(self):
        super().__init__()  # Call the parent's __init__ to inherit attributes
        self.name = 'CD Reduction'
        self.raw_name = 'Haste'
        self.final_name = 'Final %Haste'

        self.raw_expr = (0.08 * ((156.25 + (25 * self.raw)) ** 0.5) - 1)
        self.final_expr = ((0.4 * self.final) - 0.1)

        self.base_eq = Eq(self.raw_expr + self.final_expr, self.stat)
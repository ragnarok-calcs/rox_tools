from .STAT import Stat
from sympy import Eq


class CT_REDUC(Stat):
    def __init__(self):
        super().__init__()  # Call the parent's __init__ to inherit attributes
        self.name = 'CT Reduction'
        self.raw_name = 'Haste'
        self.final_name = 'Final %Haste'

        self.raw_expr = (0.005 * ((2500 + (400 * self.raw)) ** 0.5) - 0.25)
        self.final_expr = ((0.1 * self.final) - 0.1)

        self.base_eq = Eq(self.raw_expr + self.final_expr, self.stat)
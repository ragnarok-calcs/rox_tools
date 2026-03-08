from .STAT import Stat
from sympy import Eq


class CRIT(Stat):
    def __init__(self):
        super().__init__()  # Call the parent's __init__ to inherit attributes
        self.name = 'Final Crit%'
        self.raw_name = 'Crit'
        self.final_name = 'Final Crit%'

        self.raw_expr = ((6.25 + 2*self.raw)**0.5 - 2.5)
        self.final_expr = self.final

        self.base_eq = Eq(self.raw_expr + self.final_expr, self.stat)
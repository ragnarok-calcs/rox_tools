from .STAT import Stat
from sympy import Eq


class PENETRATION(Stat):
    def __init__(self):
        super().__init__()  # Call the parent's __init__ to inherit attributes
        self.name = 'Final %Penetration'
        self.raw_name = 'Penetration'
        self.final_name = 'Final %Penetration'

        self.raw_expr = None
        self.final_expr = None

        self.base_eq = Eq(self.raw_expr + self.final_expr, self.stat)
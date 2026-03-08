from .STAT import Stat
from sympy import Eq

class ASPD(Stat):
    def __init__(self):
        super().__init__()  # Call the parent's __init__ to inherit attributes
        self.name = 'Final %ASPD'
        self.raw_name = 'ASPD'
        self.final_name = 'Final %ASPD'

        self.raw_expr = (50*((0.25 + 0.04*self.raw)**0.5) - 25)
        self.final_expr = self.final

        self.base_eq = Eq(self.raw_expr + self.final_expr, self.stat)
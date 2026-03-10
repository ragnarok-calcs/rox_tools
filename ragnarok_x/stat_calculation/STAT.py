from sympy import symbols, Eq, solve
import typing as T

class Stat:
    name = None
    raw_name = None
    final_name = None

    raw = symbols('raw', integer=True, positive=True)
    final = symbols('final', integer=False)
    stat = symbols('stat', integer=False, positive=True)

    raw_expr = raw
    final_expr = final

    base_eq = Eq(raw_expr + final_expr, stat)

    def _solve(self, inputs: T.Dict[str, T.Union[float, int]]):
        frmt_inputs = {self._get(k): v for k, v in inputs.items()}
        eq_to_solve = self.base_eq.subs(frmt_inputs)
        result = solve(eq_to_solve)[0]
        return result

    def _get(self, attr: str) -> T.Any:
        return getattr(self, attr)

    def convert_input(self,
                      input_type: T.Literal['raw', 'final'],
                      input_val: T.Union[float, int]) -> str:

        needed_name = self._get(input_type + '_name')
        raw_val = input_val if input_type == 'raw' else 0
        final_val = input_val if input_type == 'final' else 0

        input_dict = {'raw': raw_val, 'final': final_val}
        result = self._solve(input_dict)

        return f'{input_val} {needed_name} provides {result:.2f} {self.name}'

    def compare_inputs(self,
                       raw: int,
                       final: float,
                       current_raw: int,
                       current_final: float) -> T.Tuple:

        current_dict = {'raw': current_raw, 'final': current_final}
        raw_dict = {'raw': raw + current_raw, 'final': current_final}
        final_dict = {'raw': current_raw, 'final': final + current_final}

        current_solve = self._solve(current_dict)
        final_solve = self._solve(final_dict)
        raw_solve = self._solve(raw_dict)

        return self.name, current_solve, raw_solve, final_solve

    def needed_input(self,
                     current_raw: int,
                     current_final: float,
                     stat_to_quant: T.Literal['raw', 'final'],
                     target_amt: float) -> T.Tuple:

        needed_name = self._get(stat_to_quant + '_name')

        if stat_to_quant == 'raw':
            quant_val = current_raw
            static_val = current_final
            static_stat = 'final'

        elif stat_to_quant == 'final':
            quant_val = current_final
            static_val = current_raw
            static_stat = 'raw'

        else:
            raise Exception(f'Stat to quant {stat_to_quant} needs to be "raw" or "final"')

        input_dict = {static_stat: static_val, 'stat': target_amt}
        result = self._solve(input_dict)

        stat_needed = result - quant_val

        return self.name, target_amt, stat_needed, stat_to_quant, needed_name

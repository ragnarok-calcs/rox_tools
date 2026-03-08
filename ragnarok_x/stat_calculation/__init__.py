from .STAT import Stat
from .ASPD import ASPD
from .CRIT import CRIT
from .CD_REDUC import CD_REDUC
from .CT_REDUC import CT_REDUC

import typing as T

secondary_stats = T.Literal['CRIT', 'ASPD', 'CT Reduction', 'CD Reduction']

def stat_factory(stat: secondary_stats) -> STAT:
    val_stat = stat.lower().strip()
    if val_stat == 'crit':
        return CRIT()
    elif val_stat == 'aspd':
        return ASPD()
    elif val_stat == 'ct reduction':
        return CT_REDUC()
    elif val_stat == 'cd reduction':
        return CD_REDUC()

    raise Exception(f'{stat} not in: {secondary_stats}')
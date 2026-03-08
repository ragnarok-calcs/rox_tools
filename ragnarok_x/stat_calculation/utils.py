

def truncate_float(number, decimal_places):
   s = str(number)
   if 'e' in s or 'E' in s:
       return f"{number:.{decimal_places}f}"
   i, p, d = s.partition('.')
   return float('.'.join([i, (d + '0' * decimal_places)[:decimal_places]]))
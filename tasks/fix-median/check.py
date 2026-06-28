import sys
sys.path.insert(0, ".")
from stats import median

assert median([1, 2, 3, 4]) == 2.5, median([1, 2, 3, 4])
assert median([1, 3, 2]) == 2, median([1, 3, 2])
assert median([5]) == 5, median([5])
assert median([10, 2, 8, 4]) == 6, median([10, 2, 8, 4])
print("ok")

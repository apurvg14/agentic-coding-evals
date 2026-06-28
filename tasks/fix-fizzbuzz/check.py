import sys
sys.path.insert(0, ".")
from fizzbuzz import fizzbuzz

r = fizzbuzz(15)
assert len(r) == 15, r
assert r[0] == "1", r[0]
assert r[2] == "Fizz", r[2]
assert r[4] == "Buzz", r[4]
assert r[14] == "FizzBuzz", r[14]
assert r[8] == "Fizz" and r[9] == "Buzz", (r[8], r[9])
print("ok")

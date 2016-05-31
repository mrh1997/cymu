"""
This module demonstrates the usage of cymu.
"""
import os
import sys

from cymu.compiler import compile_file

module1Path = os.path.join(os.path.dirname(sys.argv[0]), 'module1.c')
module1_cls = compile_file(module1Path)
module1 = module1_cls()

module1.demo_func()

print "a =",module1.a
print "b =",module1.b
print "c =",module1.c

from lang import compiler

sl = "print(1,2,3)"
asm = "a = 5"
fun = "func as(a, b) {}"
ml = """
a = 5
c = 3
print(a)
func a() {
    a = (1,2)
    c = 6
    print(a, c)
}
"""
mfun = """
func asd(){
    print("ouchie!".__class__)
    a = 3
}
"""
impt = "import ast"

evald = compiler.eval(ml)

compiler.compile_hio("testfile.hio", ml)

import henrio
import testfile
henrio.run(testfile.a())

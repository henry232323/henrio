from henrio.lang import compiler

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
print(asd())
"""
impt = """
import :testfile
print(testfile.a())
"""

#evald = compiler.eval(mfun)

compiler.compile_hio("testfile.hio")
import testfile
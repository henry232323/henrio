from lang import compiler

sl = "print(1,2,3)"
asm = "a = 5"
fun = "func as(a, b) {}"
ml = """
a = 5
print(a)
func a() {
    a = 5
    b = 6
    print(a, b)
}
"""
mfun = """
func asd(){
    print("ouchie!".__class__)
}
"""
impt = "import ast"

evald = compiler.parse(mfun)
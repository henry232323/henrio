from henrio.lang import compiler

sl = "print(1,2,3)"
asm = "print(1,2,3);print(a)"
fun = "func asd(a, b) {}"
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
    return 5
}

print(asd())
"""
impt = """
import testfile

#print(testfile.asd())
"""

compiler.execute(compiler.parse(asm), locals(), globals())

#import testfile

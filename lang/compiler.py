import ast

from . import lexer

psr = lexer.prep()


def parse(text):
    sequence = psr.parse(text)
    mod = ast.Module(sequence)
    ast.fix_missing_locations(mod)
    return mod


def execute(mod):
    return exec(compile(mod, "<ast>", "exec"))

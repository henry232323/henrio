import ast
import marshal
import os
import struct
import sys
import time
from types import ModuleType

try:
    from importlib.util import MAGIC_NUMBER
except ImportError:
    from imp.util import MAGIC_NUMBER

from . import prep

runner = ast.parse("""
import henrio as hio
_hio_interpret_call = hio._hio_interpret_call
load_hio = hio.load_hio
""", "<ast>", "exec").body

import inspect


async def _hio_interpret_call(func, *args, **kwargs):
    resp = func(*args, **kwargs)
    if inspect.isawaitable(resp):
        return await resp
    return resp


def parse(text):
    psr = prep()
    sequence = psr.parse(text)
    walk_tree(sequence)
    mod = ast.Module(sequence)
    for i, item in enumerate(sequence):
        if isinstance(item, list):
            sequence[i:i + 1] = item
    for item in reversed(runner):
        mod.body.insert(0, item)
    ast.fix_missing_locations(mod)
    return mod


def execute(mod, globals, locals):
    return exec(compile(mod, "<ast>", "exec"), globals, locals)


def eval(text, *args):
    return execute(parse(text), *args)


def load_hio(module_path):
    ext = module_path.split(".")[-1]
    filename = os.path.basename(module_path)
    module = filename[:-len(ext) - 1]
    with open(module_path, 'r') as rf:
        text = rf.read()
    mtree = parse(text)
    mod = ModuleType(module)
    mod.__file__ = module_path
    compiled = compile(mtree, filename, "exec")
    exec(compiled, mod.__dict__, mod.__dict__)
    sys.modules[module] = mod
    return mod


def compile_hio(module_path):
    ext = module_path.split(".")[-1]
    filename = os.path.basename(module_path)
    module = filename[:-len(ext) - 1]
    with open(module_path, 'r') as rf:
        text = rf.read()

    mtree = parse(text)
    compiled = compile(mtree, filename, "exec")

    with open(f"{module}.pyc", 'wb') as cf:
        cf.write(MAGIC_NUMBER)
        cf.write(struct.pack('L', int(time.time())))
        data = marshal.dumps(compiled)
        cf.write(struct.pack('I', len(data)))
        cf.write(data)


def walk_tree(tree):
    for i, item in enumerate(tree):
        if isinstance(item, list):
            tree[i:i + 1] = item
        if not isinstance(item,
                          (ast.FunctionDef, ast.AsyncFunctionDef)):  # We dont care about functions (we want top lvl)
            if hasattr(item, "body"):  # If it has a body it has children to check (Ifs etc)
                walk_tree(item.body)
            elif hasattr(item, "orelse"):
                walk_tree(item.orelse)
            elif hasattr(item, "args") or hasattr(item, "kwargs"):
                if hasattr(item, "args"):
                    walk_tree(item.args)
                if hasattr(item, "keywords"):
                    walk_tree(item.keywords)

            fitem, parent = item, None
            while hasattr(fitem, "value"):
                if isinstance(fitem, ast.Await):
                    attribute = ast.Attribute(ast.Name("hio", ast.Load()),
                                              "run",
                                              ast.Load())
                    if parent is None:
                        tree[i] = ast.Call(attribute, [fitem.value], [])
                        fitem = tree[i]
                    else:
                        parent.value = ast.Call(attribute, [fitem.value], [])
                        fitem = parent.value

                if hasattr(fitem, "args"):
                    walk_tree(fitem.args)
                if hasattr(fitem, "keywords"):
                    walk_tree(fitem.keywords)
                if hasattr(fitem, "value"):
                    fitem, parent = fitem.value, fitem

            if isinstance(item, ast.Await):
                attribute = ast.Attribute(ast.Name("hio", ast.Load()),
                                          "run",
                                          ast.Load())
                tree[i] = ast.Call(attribute, [item.value], [])

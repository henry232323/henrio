import ast
import marshal
import os
import struct
import sys
import time
from types import ModuleType

import importlib
import importlib.abc, importlib.util, importlib.machinery

from . import prep

runner = ast.parse("""
import henrio as hio
_hio_interpret_call = hio._hio_interpret_call
load_hio = hio.load_hio
""", "<henrio.main>", "exec").body

import inspect


async def _hio_interpret_call(func, *args, **kwargs):
    """This function takes any calls made in a henrio file, and turns it into an async func"""
    resp = func(*args, **kwargs)
    if inspect.isawaitable(resp):
        return await resp
    return resp


def parse(text):
    """Parses henrio text and returns an ast.Module instance"""
    psr = prep()
    sequence = psr.parse(text)
    walk_tree(sequence)
    if sequence is None:
        raise SyntaxError("Failed to parse!")
    mod = ast.Module(sequence)
    for i, item in enumerate(sequence):
        if isinstance(item, list):
            sequence[i:i + 1] = item
    ast.fix_missing_locations(mod)
    for item in reversed(runner):
        mod.body.insert(0, item)
    return mod


def execute(mod, globals, locals):
    return exec(compile(mod, "<ast>", "exec"), globals, locals)


def eval(text, *args):
    return execute(parse(text), *args)


def load_hio(module_path):
    """This takes the given file and loads it as a henrio file, putting it into sys.modules to be imported"""
    ext = module_path.split(".")[-1]
    filename = os.path.basename(module_path)
    module = filename[:-len(ext) - 1]
    with open(module_path, 'r') as rf:
        text = rf.read()
    mtree = parse(text)
    mod = ModuleType(module)
    mod.__file__ = os.path.realpath(module_path)
    compiled = compile(mtree, filename, "exec")
    exec(compiled, mod.__dict__, mod.__dict__)
    sys.modules[module] = mod
    return mod


def compile_hio(module_path):
    """Parses the file as a henrio file then compiles it to a .pyc which may be used by Python"""
    ext = module_path.split(".")[-1]
    filename = os.path.basename(module_path)
    module = filename[:-len(ext) - 1]
    with open(module_path) as rf:
        text = rf.read()

    mtree = parse(text)
    compiled = compile(mtree, filename, "exec")

    # There are 4 principal parts to a .pyc file
    #
    # 1. The Python version magic number, accessible in 3.6 as `importlib.util.MAGIC_NUMBER` which is pre-packed
    # 2. A packed timestamp, here used as `struct.pack('L', int(time.time()))`
    # 3. A packed integer describing the length of the data (I don't know how this handles bigger files
    #        But if you have a 4GB Python file, I'm really not sure what you're doing)
    #        First I pack the marshal data, which is the fourth principal part
    #        then I write the length as `struct.pack('I', len(data))`
    # 4. Finally, we have the marshal packed data. Marshal data is a bytes representation of code (like pickle)
    #        but mainly used by Python for storing compiled data. It converts between Bytes and Code objects
    #        The marshal module mimics many other encoding-decoding modules,
    #        Here I use it as `marshal.dumps(compiled)` where compiled is the parsed .hio turned into Python AST
    #        Then compiled into a code object to be dumped

    with open(f"{module}.pyc", 'wb') as cf:
        cf.write(importlib.util.MAGIC_NUMBER)
        cf.write(struct.pack('L', int(time.time())))
        data = marshal.dumps(compiled)
        cf.write(struct.pack('I', len(data)))
        cf.write(data)


def walk_tree(tree):
    """Flattens lists and turns top level awaits (which are automatically generated) into henrio.run calls"""
    for i, item in enumerate(tree):
        if isinstance(item, list):
            tree[i:i + 1] = item
            if not item:
                continue
            item = item[0]
                
        if not isinstance(item, ast.AsyncFunctionDef):  # We dont care about functions (we want top lvl)
            if getattr(item, "body", None):  # If it has a body it has children to check (Ifs etc)
                walk_tree(item.body)
            if getattr(item, "orelse", None):
                walk_tree(item.orelse)
            if getattr(item, "args", None):
                if not isinstance(item.args, ast.arguments):
                    walk_tree(item.args)
            if getattr(item, "keywords", None):
                walk_tree(item.keywords)

            fitem, parent = item, None
            while getattr(fitem, "value", None):
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

                if getattr(fitem, "args", None):
                    walk_tree(fitem.args)
                if getattr(fitem, "keywords", None):
                    walk_tree(fitem.keywords)
                if getattr(fitem, "value", None):
                    fitem, parent = fitem.value, fitem

            _ = item
            if getattr(item, "test", None):
                if isinstance(fitem.test, ast.Await):
                    attribute = ast.Attribute(ast.Name("hio", ast.Load()),
                                              "run",
                                              ast.Load())
                    fitem.test = ast.Call(attribute, [item.test.value], [])

            if getattr(item, "iter", None):
                if isinstance(fitem.iter, ast.Await):
                    attribute = ast.Attribute(ast.Name("hio", ast.Load()),
                                              "run",
                                              ast.Load())
                    fitem.iter = ast.Call(attribute, [item.iter.value], [])

            if isinstance(item, ast.Await):
                attribute = ast.Attribute(ast.Name("hio", ast.Load()),
                                          "run",
                                          ast.Load())
                tree[i] = ast.Call(attribute, [item.value], [])


def load_either(modulename):
    """Loads either up to date bytecode or recompiles file"""
    compiled_path = f"__pycache__/{modulename}.cpython-36.pyc"
    if os.path.exists(compiled_path):
        with open(compiled_path, 'rb') as pyc:
            pyc.read(4)  # Get magic
            timestamp_packed = pyc.read(8)
            pyc_timestamp = struct.unpack("L", timestamp_packed)[0]
            pyc.read(4)  # Get filesize
        hio_timestamp = os.stat(f"{modulename}.hio").st_ctime
        if pyc_timestamp >= int(hio_timestamp):
            return importlib.import_module(modulename, compiled_path)

    return load_hio(f"{modulename}.hio")


class HIOLoader(importlib.abc.Loader, importlib.abc.PathEntryFinder):
    """Searches Python path for a .hio file, and either compiles it or loads recent bytecode"""

    @classmethod
    def get_source(cls, module):
        """Get the source of a Module object"""
        with open(module.__file__, 'r') as file:
            return file.read()

    @classmethod
    def get_code(cls, module):
        """Get the code of a module object, pulled from marshalled .pyc data or compile the source"""
        if os.path.exists(module.__cache__):
            with open(module.__cache__, 'rb') as pyc:
                pyc.read(4)  # Magic Number
                timestamp_packed = pyc.read(8)  # Actual timestamped packed
                pyc.read(4)  # Size
                pyc_timestamp = struct.unpack("L", timestamp_packed)[0]
                hio_timestamp = os.stat(module.__file__).st_ctime
                if pyc_timestamp >= int(hio_timestamp):  # Compare edit time and pyc generation time
                    module.__cached__ = True  # Grab cached version if pyc is more recent
                    bytecode = pyc.read()
                    return marshal.loads(bytecode)

        text = cls.get_source(module)
        mtree = parse(text)
        module.__cached__ = False
        return compile(mtree, module.__name__, "exec")

    @classmethod
    def is_package(cls, fullname):
        """Low quality func that tells you if its a package, don't rely on it"""
        return "." in fullname

    @classmethod
    def find_loader(cls, fullname):  # self, fullname
        """If we can find the file, WE'RE the right loader
        This func is bad use find_spec always"""
        if f"{fullname}.hio" in os.listdir(os.getcwd()):
            return cls
        raise ImportError

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):  # self, fullname, target=None
        """Finds the file if it can in the Python path somewhere, always ONLY finds .hio files for now"""
        if path is None:  # We don't get a path, find it ourselves
            for path in sys.path:
                try:
                    ldir = os.listdir(path)  # Maybe what we have isn't a dir, I don't care enough to look there
                except OSError:  # (Specifically in zipped Python resources)
                    continue  # Skip
                if f"{fullname}.hio" in ldir:  # Ohoho if it is a dir, lets see if we can find the file
                    return importlib.machinery.ModuleSpec(fullname, cls, origin=os.path.join(path, fullname + ".hio"))
                    #  Easy, give cls as the loader, the name they asked for is the fullname, and origin is __file__
                    #  Specifically in the order it appears in sys.path, first instance we see
                    #  First item is always "" NOT "/"

        elif f"{fullname}.hio" in os.listdir(path):  # Else if we're given a path, look there
            return importlib.machinery.ModuleSpec(fullname, cls, origin=os.path.join(path, fullname + ".hio"))

        raise ModuleNotFoundError(f"No module named {repr(fullname)}")  # We absolutely couldn't find it

    @classmethod
    def create_module(cls, spec):
        if spec.name in sys.modules:  # If its already in sys.modules, just grab it from there
            return sys.modules[spec.name]  # As specified in PEP-302
        mod = ModuleType(spec.name)  # A plain module with the name we want
        mod.__file__ = spec.origin  # File is the above origin
        mod.__name__ = spec.name  # Name is the name we're given
        mod.__loader__ = cls  # Loader is obviously cls
        if cls.is_package(spec.name):  # We use the janky is_package method
            mod.__path__ = []  # uhhhh
            split = spec.name.split(".")  # Dont worry about this stuff
            mod.__package__ = split[-2] if len(split) >= 2 else spec.name
        sys.modules[spec.name] = mod  # Finally add it to sys.modules
        return mod

    @classmethod
    def exec_module(cls, module):
        # We have two parts, creating and executing the module
        # What is above is just initialization, this part we actually fill it up
        # But before we start executing, the module **MUST** exist in sys.modules
        # Otherwise we could end up with some serious recursion if the module (implicitly
        # or explicitly) imports itself

        maj, min = sys.version_info.major, sys.version_info.minor
        module.__cache__ = os.path.join(os.path.dirname(module.__file__),
                                        f"__pycache__/{module.__name__}.cpython-{maj}{min}.pyc")
        # This seemed to be how most cached files look, no point breaking regulation

        compiled = cls.get_code(module)  # Execute it in the module's namespace
        exec(compiled, module.__dict__, module.__dict__)  # Just as specified

        dirname = os.path.dirname(module.__cache__)  # Cache dir __pycache__

        if not module.__cached__:  # If we aren't using a cached version
            if not os.path.isdir(dirname):
                os.mkdir(dirname)  # Make the __pycache__ folder if it doesn't exist

            with open(module.__cache__, 'wb') as cf:  # Then write our beautiful new marshalled code to the .pyc
                cf.write(importlib.util.MAGIC_NUMBER)  # Refer to the above on writing cache files
                cf.write(struct.pack('L', int(time.time())))
                data = marshal.dumps(compiled)
                cf.write(struct.pack('I', len(data)))
                cf.write(data)

        return module  # And we're done!


# First make Python recognize .hio files otherwise our Loader will never see them
importlib.machinery.EXTENSION_SUFFIXES.append(".hio")
# Second add our Importer/Loader thingy to the sys.meta_path so it will use our loader
sys.meta_path.append(HIOLoader)  # Appending it so it is bottom priority, if no other loader
# Wants to handle a .hio file, or rather can't find the desired file, then it comes to us

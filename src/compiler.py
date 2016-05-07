import clang.cindex
import datamodel
import os

def config_clang():
    prj_dir = os.path.dirname(os.path.dirname(__file__))
    libclang_dir = os.path.join(prj_dir, 'bin')
    clang.cindex.Config.set_library_path(libclang_dir)

def compile_transunit(transunit):
    """
    Compile a clang.cindex.

    :param clang.cindex.TranslationUnit transunit: Source code that will be
        tranlated to program object
    :return: datamodel.Program prog
    """
    members = {}
    for node in transunit.cursor.get_children():
        if node.kind == clang.cindex.CursorKind.VAR_DECL:
            members[node.spelling] = datamodel.CInt()
        elif node.kind == clang.cindex.CursorKind.FUNCTION_DECL:
            members[node.spelling] = lambda self:None
    return type('CompiledProgram', (datamodel.CProgram,), members)

config_clang()
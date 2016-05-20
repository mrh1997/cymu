import subprocess
import sys
from os.path import dirname, join
prj_path = dirname(sys.argv[0])
if len(sys.argv) == 1 or sys.argv[1] != 'no-rebuild':
    subprocess.check_call(['vagrant', 'powershell', '-c', 'cmd.exe', '-c',
                           r'C:\vagrant\build.cmd'])

sys.path.append(join(prj_path, r'src\tools\clang\bindings\python'))
import clang.cindex
clang.cindex.Config.set_library_path(join(prj_path, r'build\Release\bin'))

c_src = """
int main(void)
{
    int a;
    int * b;
    a = (3 + 4) * -(3 + 1);
    b = &a;
    return a;
}
"""
def print_node(node, indentation=0):
    print indentation*'    ', node.kind.name, node.spelling, node.operator_kind.name if node.operator_kind != clang.cindex.OperatorKind.NULL else ""
    for subnode in node.get_children():
        print_node(subnode, indentation+1)
transunit = clang.cindex.TranslationUnit.from_source(
    'test.c', unsaved_files=[('test.c', c_src)])
if len(list(transunit.diagnostics)) > 0:
    for diag in transunit.diagnostics:
        print diag
else:
    print_node(transunit.cursor)

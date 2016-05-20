REM To start this script run the following command line
REM (after running "vagrant up"):
REM "vagrant powershell -c cmd.exe -c C:\vagrant\download.cmd"

git clone https://github.com/llvm-mirror/llvm.git \vagrant\src
git -C \vagrant\src checkout release_38
git clone https://github.com/mrh1997/clang.git \vagrant\src\tools\clang
git -C \vagrant\src\tools\clang checkout d6cc1478a6961c9e27277c718e1463e7220704ce

mkdir \vagrant\build
cd \vagrant\build
"C:\Program Files\CMake\bin\cmake.exe" -G "Visual Studio 12" ..\src

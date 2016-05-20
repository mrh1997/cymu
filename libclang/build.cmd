REM To start this script run the following command line
REM (after running "vagrant up"):
REM "vagrant powershell -c cmd.exe -c C:\vagrant\build.cmd"

cd \vagrant\build
"C:\Program Files\MSBuild\12.0\Bin\MSBuild.exe" tools/clang/tools/libclang/libclang.vcxproj /p:Configuration=Release

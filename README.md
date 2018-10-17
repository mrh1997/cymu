**This project is no longer maintained. It was abandoned for [headlock](https://github.com/mrh1997/headlock)**

----

This is a C Emulator on base of the Python VM (currently only runs on Windows)

For running this project a special version of libclang.dll is needed
(see https://github.com/mrh1997/clang/commit/d6cc1478a6961c9e27277c718e1463e7220704ce ).
This binary-file can be either copied directly to
`` /libclang/build/Release/bin`` (if available) or build manually before
running it the first time.

Building it manually requires vagrant + virtualbox and will require multiple
hours:

    cd cymu/libclang
    vagrant up
    build-and-test-clang.py

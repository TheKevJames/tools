.PHONY: all clean lib test tests

# TODO: these two files occasionally have mismatching dates
LIBC = build/spacerep.h
LIBCFFI = libspacerep.c

LIBNIM = /usr/lib/nim
# TODO: how find correct lib dir?
LIBNIM = /Users/kevin/.choosenim/toolchains/nim-1.2.4/lib

all: lib

test: tests
tests: testc testnim testpy
testc: tests/lib_test.o
	./tests/lib_test.o
tests/lib_test.o: tests/lib_test.c $(LIBC)
	clang -O0 -g -ldl -lm -o $@ -I$(LIBNIM) -I./build/ $< build/*.c
testnim: $(LIBC)
	nimble test
testpy: $(LIBCFFI)
	@. venv/bin/activate; PYTHONPATH=$(shell pwd) python3 -m pytest tests/

lib: $(LIBCFFI)

$(LIBC): src/spacerep.nim $(wildcard src/**/*.nim)
	nim c --nimcache:build/ --noMain --noLinking -d:release --opt:speed --header $<

$(LIBCFFI): $(LIBC) venv/bin/activate
	. venv/bin/activate; ./ffibuild.py

venv/bin/activate: tests/requirements.txt
	python3 -m venv venv
	. venv/bin/activate; pip install -r $<

clean:
	rm -f libspacerep.*
	rm -f tests/test_lib tests/test_lib.o
	rm -rf build/
	rm -rf tests/__pycache__
	rm -rf venv/

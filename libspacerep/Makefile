.PHONY: all clean lib test tests

# TODO: these two files occasionally have mismatching dates
LIBC = build/spacerep.h
LIBCFFI = libspacerep.c

all: lib

test: tests
tests: testc testnim testpy
testc: tests/test_lib.o
	./tests/test_lib.o
tests/test_lib.o: tests/test_lib.c $(LIBC)
	clang -O0 -g -ldl -lm -o $@ -I/usr/lib/nim -I./build/ $< build/*.c
testnim: $(LIBC)
	nimble test
testpy: $(LIBCFFI)
	@. venv/bin/activate; PYTHONPATH=$(shell pwd) python3 -m pytest tests/

lib: $(LIBCFFI)

$(LIBC): $(wildcard src/**/*.nim) $(wildcard src/*.nim)
	nimble make

$(LIBCFFI): $(LIBC) venv/bin/activate
	. venv/bin/activate; ./ffibuild.py

venv/bin/activate: tests/requirements.txt
	python3 -m venv venv
	. venv/bin/activate; pip install -r $<

clean:
	rm -f libspacerep.*
	rm -rf build/
	rm -rf tests/__pycache__
	rm -rf venv/

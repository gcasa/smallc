.PHONY: test vice-test examples clean

test:
	python3 tests/smoke.py
	python3 tests/vice_xvic.py

vice-test:
	python3 tests/vice_xvic.py

examples:
	python3 smallc.py examples/hello.c -o build/hello.s
	python3 smallc.py examples/poke.c -o build/poke.s

clean:
	rm -rf build

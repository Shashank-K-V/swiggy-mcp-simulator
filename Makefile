.PHONY: run test check load
run:
	PYTHONPATH=src python3 -m swiggy_simulator.server
test:
	PYTHONPATH=src python3 -m pytest
check:
	PYTHONPATH=src python3 -m swiggy_simulator.check
load:
	PYTHONPATH=src python3 -m swiggy_simulator.load_test --reset


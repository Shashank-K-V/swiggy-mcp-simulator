.PHONY: run test check
run:
	PYTHONPATH=src python3 -m swiggy_simulator.server
test:
	PYTHONPATH=src python3 -m pytest
check:
	PYTHONPATH=src python3 -m swiggy_simulator.check


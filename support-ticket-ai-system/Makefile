.PHONY: demo test check-links smoke clean

demo:
	python3 -m support_ticket_ai.demo --scenario all

test:
	python3 -m unittest discover -s tests -v

check-links:
	python3 scripts/check_links.py

smoke:
	bash scripts/smoke.sh

clean:
	rm -f artifacts/*.jsonl

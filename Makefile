.PHONY: bootstrap test up down smoke logs audit webui-audit
bootstrap:
	bash scripts/bootstrap.sh
test:
	python3 -I -m unittest discover -s agent/tests
up: bootstrap
	cd infra && tofu init -input=false && tofu apply -auto-approve -input=false
down:
	cd infra && tofu destroy -auto-approve -input=false
smoke:
	bash scripts/smoke.sh
logs:
	docker logs -f agentloop-agent
audit:
	@curl -s localhost:8000/audit?limit=$${N:-30} | python3 -c "import sys,json;[print(r['ts'],r['request'],r['type'],{k:v for k,v in r.items() if k not in ('ts','request','type')}) for r in json.load(sys.stdin)]"
webui-audit:
	docker exec agentloop-openwebui sh -c 'tail -n $${N:-5} /app/backend/data/audit.log'

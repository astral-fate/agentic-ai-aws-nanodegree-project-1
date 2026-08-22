# Shortcuts for the project. Run `make help` for the list.
#
# The AWS targets are thin wrappers around the commands in docs/RUNBOOK.md —
# use whichever you prefer. `make test` needs no AWS account.

REGION      ?= us-east-1
TOOL_STACK  ?= bug-report-tool-stack
TEST_STACK  ?= bug-report-testing-stack
TABLE       ?= $(TOOL_STACK)-bug-reports
STARTER     := project/starter

.DEFAULT_GOAL := help
.PHONY: help install test lint deploy-tool gateway harness chat \
        deploy-testing dataset evaluate verify-tickets deploy-all clean-aws

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install:  ## Install runtime and dev dependencies
	python -m pip install -r requirements.txt -r requirements-dev.txt

test:  ## Run the offline test suite (no AWS needed)
	python -m pytest

lint:  ## Byte-compile every script to catch syntax errors
	python -m compileall -q $(STARTER) tests

# --- AWS ---------------------------------------------------------------

deploy-tool:  ## Deploy the DynamoDB + Lambda + IAM stack
	aws cloudformation deploy \
	  --template-file $(STARTER)/cloudformation-tool.yaml \
	  --stack-name $(TOOL_STACK) \
	  --capabilities CAPABILITY_NAMED_IAM \
	  --region $(REGION)

gateway:  ## Create the AgentCore Gateway and register the tool
	cd $(STARTER) && python setup_gateway.py --stack-name $(TOOL_STACK)

harness:  ## Create or update the harness from system_prompt.txt
	cd $(STARTER) && python create_harness.py

chat:  ## Start one chat session against the harness
	cd $(STARTER) && python chat.py

deploy-testing:  ## Deploy the S3 bucket + evaluation IAM role
	aws cloudformation deploy \
	  --template-file $(STARTER)/cloudformation-testing.yaml \
	  --stack-name $(TEST_STACK) \
	  --capabilities CAPABILITY_NAMED_IAM \
	  --region $(REGION)

dataset:  ## Run the test suite against the harness, write the JSONL
	cd $(STARTER) && python generate-eval-dataset.py --tests-json harness-tests.json

evaluate:  ## Upload the dataset and run a Bedrock Evaluations job
	cd $(STARTER) && python run_evaluation.py --testing-stack $(TEST_STACK) --wait

verify-tickets:  ## Show the tickets currently in DynamoDB
	aws dynamodb scan --table-name $(TABLE) --region $(REGION)

deploy-all: deploy-tool gateway harness  ## Deploy the tool stack, gateway and harness

# --- teardown ----------------------------------------------------------

clean-aws:  ## Delete the AgentCore resources and both CloudFormation stacks
	cd $(STARTER) && python cleanup_agentcore.py
	-aws s3 rm s3://udacity-agentic-engineer-c1-eval-$$(aws sts get-caller-identity \
	    --query Account --output text) --recursive --region $(REGION)
	-aws cloudformation delete-stack --stack-name $(TEST_STACK) --region $(REGION)
	-aws cloudformation delete-stack --stack-name $(TOOL_STACK) --region $(REGION)
	@echo "Delete requested. Watch progress in the CloudFormation console."

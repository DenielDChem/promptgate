"""Basic usage example for PromptGate v0.1."""
import tempfile
from pathlib import Path

from promptgate.models import PromptConfig
from promptgate.storage import SQLiteBackend
from promptgate.router import search
from promptgate.compiler import compile_prompt
from promptgate.validator import extract_json, validate_output

# Use temp DB for this demo
with tempfile.TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / "demo.db"

    # 1. Initialize storage
    backend = SQLiteBackend(db_path)
    backend.init()

    # 2. Define and store a prompt
    prompt = PromptConfig(
        id="sales_report_v1",
        name="Sales Report Generator",
        tags=["sales", "reporting", "finance"],
        **{"schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "pattern": r"^\d{4}-\d{2}$"},
                "region": {"type": "string"},
            },
            "required": ["period"],
        }},
        template=(
            "You are a sales analyst. Generate a concise report for period {{ period }}"
            "{% if region %} in region {{ region }}{% endif %}.\n"
            "Payload: {{ payload_json }}\n"
            "Return JSON matching: {{ output_schema }}"
        ),
        description="Monthly sales report with optional region filter",
    )
    backend.upsert(prompt)
    print(f"Stored prompt: {prompt.id}")

    # 3. Search
    results = search("sales report", db_path=db_path)
    print(f"Search 'sales report': {results}")

    # 4. Compile
    contract = compile_prompt(prompt, {"period": "2024-01", "region": "EMEA"})
    print(f"\nCompiled contract:")
    print(f"  schema_hash: {contract.schema_hash}")
    print(f"  missing_fields: {contract.missing_fields}")
    print(f"  system_prompt:\n{contract.system_prompt[:200]}...")

    # 5. Validate LLM output (simulated)
    simulated_llm_output = """
    Sure, here is the report:
    {"summary": "Q1 EMEA sales up 12%", "period": "2024-01", "region": "EMEA"}
    """
    result = validate_output(
        simulated_llm_output,
        contract,
        schema={"type": "object", "properties": {"summary": {"type": "string"}}},
    )
    print(f"\nValidation: ok={result.ok}, data={result.data}")

    # 6. Demonstrate missing fields handling
    contract_missing = compile_prompt(prompt, {})
    print(f"\nMissing fields test: {contract_missing.missing_fields}")

print("\nDone.")

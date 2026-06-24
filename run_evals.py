import json
import time
import os
from src.pipeline.graph import pipeline

def run_evaluations():
    print("Starting AI App Compiler Evaluation Framework...")
    
    with open("evals/dataset.json", "r") as f:
        dataset = json.load(f)
        
    results = []
    
    total_latency = 0
    total_cost = 0.0
    successful_runs = 0
    total_repairs_needed = 0
    
    for i, item in enumerate(dataset):
        prompt_id = item["id"]
        prompt_text = item["prompt"]
        prompt_type = item["type"]
        
        print(f"[{i+1}/{len(dataset)}] Evaluating {prompt_id} ({prompt_type})...")
        print(f"Prompt: {prompt_text[:50]}...")
        
        start_time = time.time()
        try:
            initial_state = {
                "user_prompt": prompt_text,
                "mode": "generate",
                "session_id": "eval_" + prompt_id,
                "events": [],
                "stage_timings": {},
                "repair_attempts": {},
                "repair_history": [],
                "total_retries": 0,
                "cost_estimate": 0.0,
                "validation_errors": [],
                "test_results": [],
                "pipeline_failed": False,
            }
            state = pipeline.invoke(initial_state)
            
            latency = time.time() - start_time
            cost = state.get("cost_estimate", 0.0)
            
            # If the state has ui_schema, it means all layers compiled successfully
            success = "ui_schema" in state
            
            result = {
                "id": prompt_id,
                "type": prompt_type,
                "success": success,
                "latency_sec": round(latency, 2),
                "cost": round(cost, 4),
                "error": None
            }
            
            if success:
                successful_runs += 1
                total_latency += latency
                total_cost += cost
            else:
                result["error"] = "Pipeline did not reach ui_schema stage"
                
            print(f"Success! ({latency:.2f}s, ${cost:.4f})")
            
        except Exception as e:
            latency = time.time() - start_time
            print(f"Failed: {str(e)}")
            result = {
                "id": prompt_id,
                "type": prompt_type,
                "success": False,
                "latency_sec": round(latency, 2),
                "cost": 0.0,
                "error": str(e)
            }
            
        results.append(result)
        
    # Generate Markdown Report
    print("\nGenerating Metrics Report...")
    
    success_rate = (successful_runs / len(dataset)) * 100
    avg_latency = total_latency / successful_runs if successful_runs > 0 else 0
    avg_cost = total_cost / successful_runs if successful_runs > 0 else 0
    
    report = f"""# AI App Compiler - Evaluation Metrics

## Summary
- **Total Prompts**: {len(dataset)}
- **Success Rate**: {success_rate:.1f}% ({successful_runs}/{len(dataset)})
- **Average Latency (Successful)**: {avg_latency:.2f}s
- **Average Cost (Successful)**: ${avg_cost:.4f}

## Detailed Results

| ID | Type | Success | Latency (s) | Cost | Notes/Error |
|----|------|---------|-------------|------|-------------|
"""

    for r in results:
        status = "✅" if r["success"] else "❌"
        error_msg = r["error"].replace("\n", " ")[:50] + "..." if r["error"] else "-"
        report += f"| {r['id']} | {r['type']} | {status} | {r['latency_sec']} | ${r['cost']} | {error_msg} |\n"
        
    with open("evals/metrics_report.md", "w", encoding="utf-8") as f:
        f.write(report)
        
    print("Evaluation Complete! Report saved to evals/metrics_report.md")

if __name__ == "__main__":
    run_evaluations()

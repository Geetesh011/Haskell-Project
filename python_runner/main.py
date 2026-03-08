"""
Phase 4: Output & Reporting (Python Runner)
===========================================
This is the main orchestrator. It runs `data_ingestion.py` to get the
normalised district data, passes it via standard input to the Haskell
logic engine, and then formats the output into a readable report.
"""

import json
import subprocess
import os
import sys

from data_ingestion import generate_sample_data, normalize


def find_haskell_binary() -> str:
    """Find the compiled Haskell executable using Stack."""
    try:
        # Ask stack where the executable is
        result = subprocess.run(
            ["stack", "exec", "--", "where", "cvi-backend"],
            cwd=os.path.join(os.path.dirname(__file__), "..", "cvi-backend"),
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("[ERROR] Could not find 'cvi-backend' binary. Did you run 'stack build'?", file=sys.stderr)
        sys.exit(1)


def run_logic_engine() -> list[dict]:
    """Execute the Haskell logic engine with the normalised data."""
    
    # 1. Run Data Ingestion to get the normalised JSON
    print("[Runner] Running Data Ingestion (Python)...")
    raw_data = generate_sample_data()
    normed_data = normalize(raw_data)
    normalised_json = json.dumps(normed_data)

    # 2. Find the build Haskell executable
    print("[Runner] Locating Haskell binary...")
    binary_path = find_haskell_binary()

    # 3. Call the Haskell backend, passing JSON to stdin
    print("[Runner] Executing Haskell CVI Pattern-Matching Logic Engine...")
    try:
        haskell_proc = subprocess.run(
            [binary_path],
            input=normalised_json,
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print("[ERROR] Haskell engine crashed:")
        print("  STDOUT:", e.stdout)
        print("  STDERR:", e.stderr)
        sys.exit(1)

    # Print any stderr (logs) from Haskell
    if haskell_proc.stderr:
        print(haskell_proc.stderr, file=sys.stderr)

    # Parse and return the JSON output
    try:
        results = json.loads(haskell_proc.stdout)
        # Check if the Haskell code returned an error object
        if isinstance(results, dict) and "error" in results:
            print(f"[ERROR from Haskell] {results['error']}", file=sys.stderr)
            sys.exit(1)
        return results
    except json.JSONDecodeError:
        print("[ERROR] Failed to parse output from Haskell engine:", file=sys.stderr)
        print("Raw Output:\n", haskell_proc.stdout)
        sys.exit(1)


def generate_report(results: list[dict]):
    """Format the results into a readable Markdown report."""
    print("\n\n" + "=" * 80)
    print(" Coastal District Climate Vulnerability Index (CVI) Report ")
    print("=" * 80)
    print(f"\nTotal Districts Analyzed: {len(results)}\n")

    # Sort results by final CVI score (descending)
    sorted_results = sorted(results, key=lambda r: r.get("final_cvi", 0), reverse=True)

    header = f"{'District':<25} | {'State':<15} | {'Base CVI':<10} | {'Penalty':<10} | {'Final CVI':<10} | {'Risk Category':<15}"
    print(header)
    print("-" * len(header))

    for r in sorted_results:
        print(f"{r['district']:<25} | {r['state']:<15} | {r['base_cvi']:<10.4f} | +{r['pattern_penalty']:<9.4f} | {r['final_cvi']:<10.4f} | {r['category']:<15}")
    
    print("\n" + "-" * 80)
    print(" Vulnerability Profile Highlights (Pattern Matching)")
    print("-" * 80)

    for r in sorted_results:
        patterns = ", ".join(r["matched_patterns"])
        if patterns != "No high-risk patterns detected.":
            print(f"\n=> {r['district']} ({r['state']})")
            print(f"   Triggers    : {patterns}")
            print(f"   Explanation : {r['explanation']}")


if __name__ == "__main__":
    cvi_results = run_logic_engine()
    generate_report(cvi_results)

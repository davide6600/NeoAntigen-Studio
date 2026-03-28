#!/usr/bin/env python3
import time
import sys

try:
    import httpx
    from rich.console import Console
    from rich.table import Table
    from rich import print as rprint
except ImportError:
    print("Missing dependencies. Please install with: pip install httpx rich")
    sys.exit(1)

import argparse

def run_e2e_test(
    run_mode: str = "dry_run",
    patient_id: str = "PT-CLI-001",
    hla_alleles: list[str] = None,
    peptides: list[str] = None,
    predictor: str = "auto",
    api_url: str = "http://localhost:8000"
):
    if hla_alleles is None:
        hla_alleles = ["HLA-A*02:01", "HLA-B*07:02"]
    if peptides is None:
        peptides = ["SIINFEKL", "YLQPRTFLL"]

    console = Console()
    console.print(f"[bold blue]Starting NeoAntigen-Studio E2E Test (mode: {run_mode})[/bold blue]")

    with httpx.Client(base_url=api_url, timeout=30.0) as client:
        # Step 1: Create Job
        payload = {
            "requested_by": "cli_tester",
            "run_mode": run_mode,
            "metadata": {
                "patient_id": patient_id,
                "hla_alleles": hla_alleles,
                "pipeline_engine": "dry_run",
                "predictor": predictor,
                "peptides": peptides
            }
        }
        
        console.print("Submitting job...")
        try:
            res = client.post("/jobs", json=payload)
            res.raise_for_status()
        except httpx.ConnectError:
            console.print(f"[bold red]Error:[/] Could not connect to API at {api_url}. Is the server running?")
            sys.exit(1)
            
        data = res.json()
        job_id = data.get("job_id")
        console.print(f"[green]Job created successfully:[/] {job_id}")
        
        # Step 2: Poll Status
        console.print("Polling job status...")
        while True:
            r = client.get(f"/jobs/{job_id}")
            r.raise_for_status()
            job_status = r.json().get("status")
            console.print(f"Current status: [cyan]{job_status}[/cyan]")
            
            if job_status in ["completed", "failed"]:
                break
            
            if job_status == "awaiting_approval":
                console.print(f"[bold yellow]Job {job_id} requires approval for safe_export.[/bold yellow]")
                # Fetch proposals
                r = client.get(f"/approvals")
                proposals = r.json().get("pending_approvals", [])
                my_prop = next((p for p in proposals if p["details"].get("job_id") == job_id), None)
                if not my_prop:
                    console.print("[red]Could not find matching proposal id.[/red]")
                    break
                
                prop_id = my_prop["proposal_id"]
                if run_mode == "full" or run_mode == "phase2_real":
                    token = input(f"Enter HMAC token for {prop_id} (action: safe_export): ").strip()
                else: 
                    # auto approve for dry_run to not break non-interactive tests
                    token = f"APPROVE: {prop_id}"
                    
                console.print("Submitting approval...")
                res = client.post(f"/approvals/{prop_id}/approve", json={"approved_by": "cli_tester", "token": token})
                if res.status_code == 200:
                    console.print("[green]Approved successfully. Resuming step...[/green]")
                    res_resume = client.post(f"/jobs/{job_id}/steps/safe_export/resume")
                    res_resume.raise_for_status()
                else:
                    console.print(f"[red]Approval failed: {res.text}[/red]")
                    break
                    
            time.sleep(1)
            
        console.print(f"[bold]Pipeline finished with terminal status:[/] {job_status}")
        
        # Step 3: Fetch and display Audit Trail
        console.print("\n[bold]Fetching Audit Trail...[/bold]")
        r = client.get(f"/jobs/{job_id}/audit-trail")
        r.raise_for_status()
        steps = r.json().get("steps", [])
        
        table = Table(title=f"Audit Provenance: {job_id}")
        table.add_column("STEP", justify="left", style="cyan", no_wrap=True)
        table.add_column("STATUS", justify="center")
        table.add_column("DURATION", justify="right", style="magenta")
        table.add_column("DETAILS", justify="left")
        
        for step in steps:
            status = step["status"]
            status_color = "red" if status == "failed" else "green" if status == "completed" else "yellow"
            
            details_str = str(step.get("details", {}))
            
            table.add_row(
                step["step"],
                f"[{status_color}]{status}[/]",
                f"{step['duration_ms']} ms",
                details_str
            )
            
        console.print(table)
        
        if job_status == "failed":
            console.print("[bold red]\nJob failed! Check details above.[/bold red]")
            sys.exit(1)
        else:
            console.print("[bold green]\nE2E Test completed successfully.[/bold green]")
            
            console.print("\n[bold]Fetching Scientific Report...[/bold]")
            try:
                r = client.get(f"/jobs/{job_id}/results")
                r.raise_for_status()
                artifacts = r.json().get("artifacts", [])
                report_artifact = next((a for a in artifacts if a["artifact_type"].startswith("report_")), None)
                if report_artifact:
                    console.print(f"[green]Report generated at:[/] {report_artifact.get('path')}")
                    if report_artifact.get('api_download_path'):
                        console.print(f"[cyan]API Endpoint:[/] {api_url}{report_artifact.get('api_download_path')}")
                else:
                    console.print("[yellow]No scientific report found for this job.[/yellow]")
            except Exception as e:
                console.print(f"[red]Could not fetch report details: {e}[/red]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NeoAntigen-Studio E2E test CLI")
    # Positional argument for backward compatibility
    parser.add_argument("mode", nargs="?", default="dry_run", help="Run mode (e.g. dry_run, full)")
    # Optional flags
    parser.add_argument("--run-mode", type=str, help="Override run mode")
    parser.add_argument("--patient-id", type=str, default="PT-CLI-001", help="Patient ID")
    parser.add_argument("--hla-alleles", type=str, help="Comma separated HLA alleles")
    parser.add_argument("--peptides", type=str, help="Comma separated peptides")
    parser.add_argument("--vcf", help="Optional path to a .vcf file for real variant acquisition")
    parser.add_argument("--predictor", default="auto", choices=["auto", "sklearn", "netmhcpan"], help="Predictor to use for immunogenicity (auto, sklearn, netmhcpan)")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API URL (default: http://localhost:8000)")
    
    args = parser.parse_args()
    
    final_mode = args.run_mode if args.run_mode else args.mode
    hla_list = [a.strip() for a in args.hla_alleles.split(",")] if args.hla_alleles else None
    pep_list = [p.strip() for p in args.peptides.split(",")] if args.peptides else None
    
    try:
        run_e2e_test(
            run_mode=final_mode,
            patient_id=args.patient_id,
            hla_alleles=hla_list,
            peptides=pep_list,
            predictor=args.predictor,
            api_url=args.api_url
        )
    except KeyboardInterrupt:
        print("\nE2E Test interrupted by user.")
        sys.exit(1)


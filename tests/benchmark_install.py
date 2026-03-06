#!/usr/bin/env python3
"""
Installation Performance Benchmark for AgentPier SDK and Integrations

Measures installation times in fresh virtual environments to establish
baseline metrics for optimization work.

Usage:
    python benchmark_install.py [--verbose] [--runs N]
"""

import subprocess
import sys
import time
import tempfile
import shutil
import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple


class InstallBenchmark:
    """Benchmarks installation performance for AgentPier components."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.agentpier_root = Path(__file__).parent.parent.resolve()
        
    def log(self, message: str) -> None:
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(f"[{time.strftime('%H:%M:%S')}] {message}")
    
    def create_venv(self, venv_path: Path) -> bool:
        """Create a fresh virtual environment."""
        try:
            self.log(f"Creating venv at {venv_path}")
            subprocess.run([
                sys.executable, "-m", "venv", str(venv_path)
            ], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to create venv: {e}")
            return False
    
    def get_pip_path(self, venv_path: Path) -> Path:
        """Get pip executable path for the virtual environment."""
        if os.name == 'nt':  # Windows
            return venv_path / "Scripts" / "pip"
        else:  # Unix-like
            return venv_path / "bin" / "pip"
    
    def time_installation(self, venv_path: Path, package_spec: str) -> Tuple[float, bool]:
        """Time a package installation and return (duration, success)."""
        pip_path = self.get_pip_path(venv_path)
        
        self.log(f"Installing {package_spec}")
        start_time = time.perf_counter()
        
        # Parse package_spec into separate arguments
        install_args = [str(pip_path), "install"]
        if package_spec.startswith("-e "):
            install_args.extend(["-e", package_spec[3:]])
        else:
            install_args.append(package_spec)
        
        try:
            result = subprocess.run(install_args, check=True, capture_output=True, text=True)
            
            end_time = time.perf_counter()
            duration = end_time - start_time
            self.log(f"Installation completed in {duration:.2f}s")
            return duration, True
            
        except subprocess.CalledProcessError as e:
            end_time = time.perf_counter()
            duration = end_time - start_time
            print(f"Installation failed after {duration:.2f}s: {e}")
            if self.verbose and e.stderr:
                print(f"Error output: {e.stderr[:500]}...")
            return duration, False
    
    def benchmark_sdk(self, venv_path: Path) -> Dict[str, any]:
        """Benchmark SDK installation."""
        sdk_path = self.agentpier_root / "sdk" / "python"
        package_spec = f"-e {sdk_path}"
        
        duration, success = self.time_installation(venv_path, package_spec)
        
        return {
            "component": "agentpier-sdk",
            "package_spec": str(package_spec),
            "duration_seconds": round(duration, 2),
            "success": success
        }
    
    def benchmark_crewai_integration(self, venv_path: Path) -> Dict[str, any]:
        """Benchmark CrewAI integration installation."""
        integration_path = self.agentpier_root / "integrations" / "crewai"
        package_spec = f"-e {integration_path}"
        
        duration, success = self.time_installation(venv_path, package_spec)
        
        return {
            "component": "agentpier-crewai",
            "package_spec": str(package_spec),
            "duration_seconds": round(duration, 2),
            "success": success
        }
    
    def benchmark_langchain_integration(self, venv_path: Path) -> Dict[str, any]:
        """Benchmark LangChain integration installation."""
        integration_path = self.agentpier_root / "integrations" / "langchain"
        package_spec = f"-e {integration_path}"
        
        duration, success = self.time_installation(venv_path, package_spec)
        
        return {
            "component": "agentpier-langchain",
            "package_spec": str(package_spec),
            "duration_seconds": round(duration, 2),
            "success": success
        }
    
    def run_single_benchmark(self) -> Dict[str, any]:
        """Run a single complete benchmark cycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            results = {
                "timestamp": time.time(),
                "datetime": time.strftime('%Y-%m-%d %H:%M:%S'),
                "python_version": sys.version,
                "benchmarks": []
            }
            
            # Test each component in separate venvs to avoid cross-contamination
            components = [
                ("SDK", self.benchmark_sdk),
                ("CrewAI Integration", self.benchmark_crewai_integration),
                ("LangChain Integration", self.benchmark_langchain_integration)
            ]
            
            for name, benchmark_func in components:
                venv_path = temp_path / f"venv_{name.lower().replace(' ', '_')}"
                
                self.log(f"\n--- Benchmarking {name} ---")
                
                if not self.create_venv(venv_path):
                    continue
                
                # Upgrade pip first to ensure consistent behavior
                pip_path = self.get_pip_path(venv_path)
                try:
                    subprocess.run([
                        str(pip_path), "install", "--upgrade", "pip"
                    ], check=True, capture_output=True)
                except subprocess.CalledProcessError:
                    self.log("Warning: Failed to upgrade pip")
                
                benchmark_result = benchmark_func(venv_path)
                results["benchmarks"].append(benchmark_result)
            
            return results
    
    def run_benchmark(self, num_runs: int = 1) -> List[Dict[str, any]]:
        """Run benchmark multiple times and collect results."""
        all_results = []
        
        for run_num in range(1, num_runs + 1):
            print(f"\n=== Benchmark Run {run_num}/{num_runs} ===")
            result = self.run_single_benchmark()
            all_results.append(result)
        
        return all_results
    
    def generate_summary(self, results: List[Dict[str, any]]) -> Dict[str, any]:
        """Generate summary statistics from benchmark results."""
        if not results:
            return {}
        
        # Group results by component
        by_component = {}
        for result in results:
            for benchmark in result["benchmarks"]:
                component = benchmark["component"]
                if component not in by_component:
                    by_component[component] = []
                by_component[component].append(benchmark)
        
        summary = {
            "total_runs": len(results),
            "components": {},
            "generated_at": time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        for component, benchmarks in by_component.items():
            durations = [b["duration_seconds"] for b in benchmarks if b["success"]]
            success_rate = sum(1 for b in benchmarks if b["success"]) / len(benchmarks)
            
            if durations:
                summary["components"][component] = {
                    "avg_duration": round(sum(durations) / len(durations), 2),
                    "min_duration": round(min(durations), 2),
                    "max_duration": round(max(durations), 2),
                    "success_rate": round(success_rate, 2),
                    "total_runs": len(benchmarks)
                }
            else:
                summary["components"][component] = {
                    "avg_duration": 0,
                    "success_rate": 0,
                    "total_runs": len(benchmarks),
                    "note": "All installations failed"
                }
        
        return summary


def main():
    parser = argparse.ArgumentParser(description="Benchmark AgentPier installation performance")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--runs", "-r", type=int, default=1, help="Number of benchmark runs")
    parser.add_argument("--output", "-o", help="Output file for results (JSON)")
    
    args = parser.parse_args()
    
    benchmark = InstallBenchmark(verbose=args.verbose)
    
    print("AgentPier Installation Performance Benchmark")
    print("=" * 50)
    
    results = benchmark.run_benchmark(args.runs)
    summary = benchmark.generate_summary(results)
    
    print("\n" + "=" * 50)
    print("BENCHMARK SUMMARY")
    print("=" * 50)
    
    if summary.get("components"):
        for component, stats in summary["components"].items():
            print(f"\n{component}:")
            print(f"  Average: {stats['avg_duration']}s")
            if 'min_duration' in stats and 'max_duration' in stats:
                print(f"  Range: {stats['min_duration']}s - {stats['max_duration']}s")
            print(f"  Success Rate: {stats['success_rate']:.0%}")
            if stats.get("note"):
                print(f"  Note: {stats['note']}")
    else:
        print("No successful benchmarks completed.")
    
    # Save detailed results if output file specified
    if args.output:
        output_data = {
            "summary": summary,
            "detailed_results": results
        }
        
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\nDetailed results saved to: {args.output}")


if __name__ == "__main__":
    main()
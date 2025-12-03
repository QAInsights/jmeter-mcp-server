import asyncio
import os
import glob
from jmeter_server import analyze_jmeter_results

async def main():
    print("Testing JMeter MCP Analysis...")
    
    # Find the JTL file from the previous run
    jtl_files = glob.glob("*.jtl")
    if not jtl_files:
        print("No JTL files found to analyze.")
        return

    jtl_file = jtl_files[0]
    print(f"Analyzing {jtl_file}...")

    # Run the analysis
    try:
        result = await analyze_jmeter_results(
            jtl_file=jtl_file,
            detailed=True
        )
        print("\nAnalysis Result:")
        print(result)
    except Exception as e:
        print(f"\nError occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
from jmeter_server import execute_jmeter_test_non_gui

async def main():
    print("Running sample_test.jmx using JMeter MCP Server tools...")
    
    # Ensure the file exists
    test_file = os.path.abspath("sample_test.jmx")
    if not os.path.exists(test_file):
        print(f"Error: {test_file} not found")
        return

    # Run the test
    try:
        result = await execute_jmeter_test_non_gui(
            test_file=test_file,
            generate_report=True
        )
        print("\nExecution Result:")
        print(result)
    except Exception as e:
        print(f"\nError occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())

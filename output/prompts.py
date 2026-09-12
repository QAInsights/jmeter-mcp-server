"""
Prompt text for the JMeter MCP server.

Each prompt returns instructions telling the client LLM exactly which
tools to call.
"""

ANALYZE_LATEST_RUN = """\
Analyze the most recent JMeter run:

1. Call list_test_runs(limit=1, format='json') and take data.runs[0].jtl_path.
2. Call analyze_jmeter_results(jtl_file=<path>, detailed=True, format='json').
3. Call identify_performance_bottlenecks(jtl_file=<path>, format='json').
4. Summarize: throughput, p95 response time, error rate, the top 3
   bottlenecks, and the top 3 recommendations.
"""

COMPARE_LAST_TWO_RUNS = """\
Compare the two most recent JMeter runs:

1. Call list_test_runs(limit=2, format='json'); take data.runs[0] and
   data.runs[1] (newest first) and their jtl_path values.
2. Call analyze_jmeter_results(jtl_file=<path>, detailed=True, format='json')
   for each.
3. Produce a table of deltas between the runs: average response time, p90,
   p95, p99, throughput, and error rate — overall and per endpoint.
4. Flag any regression greater than 10%.
"""


def run_and_monitor_test(test_file: str) -> str:
    return f"""\
Run and monitor the JMeter test {test_file}:

1. Call start_jmeter_test(test_file='{test_file}', format='json') and note
   data.run_id.
2. Poll get_test_status(run_id, format='json') roughly every 15 seconds
   until data.status is not 'starting' or 'running'. If the reported error
   rate exceeds 50% for two consecutive polls, call
   stop_jmeter_test(run_id, graceful=True, format='json') instead.
3. When finished, call analyze_jmeter_results(jtl_file=data.jtl_path,
   detailed=True, format='json') and identify_performance_bottlenecks(
   jtl_file=data.jtl_path, format='json'), then summarize throughput, p95,
   error rate, top bottlenecks, and top recommendations.
"""

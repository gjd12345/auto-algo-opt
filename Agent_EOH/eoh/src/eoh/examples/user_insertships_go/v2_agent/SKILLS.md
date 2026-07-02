Tool Descriptions:
- read_plan: Read PLAN.md.
- update_plan: Overwrite PLAN.md with provided content.
- read_memory: Read MEMORY.md.
- update_memory: Overwrite MEMORY.md with provided content.
- read_research_notes: Read research_notes.md.
- web_search: Search the web via Tavily and append to research_notes.md.
- generate_seeds_from_research: Run web_search and generate a research seed JSON file.
- run_code_review: Compile+smoke-check a candidate GenRoute method before saving as seed.
- add_new_seed: Append a new seed (Go GenRoute method) to seeds_genroute_go.json.
- run_evolution: Run EoH evolution.
- analyze_latest_results: Summarize latest population.
- run_comprehensive_evaluation: Evaluate best_code on rc101–rc108 and compare baseline.
- write_report: Write a markdown report file under v2_agent/reports.
- run_deep_analysis: Diagnose stagnation/penalties using latest stats and errors.


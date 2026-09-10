# Shards

## Summary of Project
Find 404/missing links in ReadMe, missing requirements in requirements.txt, or missing documentation.
Representing results as a graph with summary of missing requirements, and summary of fixes.
Pipeline:
- Git clone rep
- Create Dependency Graph
- Check for requirements.txt
- Collect all ReadMe.md
- Check ReadMe.md

## End goal
### Graph
#### ReadMe Colouring/Styling:
- Orange ReadMe containing broken link
- Dashed line to where link is expected to go
- Missing/broken resource red
- Green ReadMe not containing missing links
#### Requirements Colouring/Styling:
- Orange Requirements.txt missing imports
- Red if no rquirements.txt
- Green if requirements.txt and no issues
#### General Colouring/Styling:
- Purple if folders
- Blue python/jupyter notebooks
- Pink other file types
### Report
#### Requirements
List all missing requirements and where possible the requirement to add to txt.
#### GenAI Summary
Summary of how to fix ReadMe, quality of documentation, and general improvements. GenAI is ollama and medium ish model like Gemma:20b
### Project App Details
Flask app, teal and orange bulma theme, and light mode with foldable sections.\
Git clone should keep files in temp folder that gets cleared once details are completely collected.

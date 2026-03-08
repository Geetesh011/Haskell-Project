# Execution Plan: Robust Climate Vulnerability Index (CVI) via Pattern-Matching Logic

**Note to Claude:** The user wants you to execute this plan directly to build the essentials for a robust Climate Vulnerability Index (CVI) for coastal districts. Please focus *only* on the necessary essentials to demonstrate the pattern-matching logic approach. Do not over-engineer.

## 1. Problem Statement
Coastal districts face complex, overlapping threats from climate change (sea-level rise, extreme weather, coastal erosion). Traditional vulnerability assessments often rely on simple additive indices that fail to capture compounding risks when multiple vulnerabilities interact. There is a need for a dynamic system that identifies specific *patterns* of risk to provide targeted, robust vulnerability scores.

## 2. Objective
Build a streamlined, logic-based CVI calculation engine. The system will ingest physical, environmental, and socio-economic data for coastal regions, apply a pattern-matching algorithm to identify predefined high-risk profiles (e.g., "high population + low elevation + high erosion"), and output a composite Climate Vulnerability Index.

## 3. Necessary Essentials (Core Stack Recommendation)
- **Backend Core**: Haskell (ideal for strong typing, pure functions, and executing powerful logic matching).
- **Frontend/Data Processing**: Python (`pandas`) to parse CSV/data formats and send normalized JSON to Haskell.
- **Communication**: JSON via stdout/stdin between Python and Haskell.

---

## 4. Phase-Wise Execution Plan

### Phase 1: Data Ingestion & Normalization (The Foundation)
**Goal:** Set up the data structures to handle diverse input parameters.
*   **Tasks:**
    1. Define a schema for coastal district data blocks (e.g., District Name, Elevation, Erosion Rate, Sea-Level Rise Projections, Population Density, Income Level).
    3. Implement a normalization function (e.g., Min-Max scaling) to convert all diverse variable inputs into a standard 0 to 1 scale (or 1 to 5 scale) representing hazard levels.
    4. Export this normalized data as a JSON object to feed the logic engine.

### Phase 2: Pattern-Matching Logic Engine (The Core)
**Goal:** Identify specific vulnerability profiles instead of just summing values.
*   **Tasks:**
    1. **In Haskell:** Define "Risk Patterns" using logical rules over algebraic data types.
       * *Example Pattern A (The "Sinking City" profile):* Normalized Elevation is Very Low AND Population Density is Very High.
       * *Example Pattern B (The "Exposed Coast" profile):* Erosion is High AND Sea-Level Rise Projection is High.
    2. Build the pattern matching function in Haskell: Read the JSON data and evaluate against these defined logical rules.
    3. Assign weighted penalties or multipliers based on which patterns are matched.

### Phase 3: CVI Scoring & Aggregation
**Goal:** Calculate the final, robust index for each district.
*   **Tasks:**
    1. Calculate the Base Score (usually an average of Exposure, Sensitivity, and Adaptive Capacity).
    2. Apply the Pattern-Matching Modifiers from Phase 2 to the Base Score. If a district matches a highly dangerous pattern, its CVI score gets exponentially boosted.
    3. Categorize the final scores into discrete CVI levels: `Low`, `Moderate`, `High`, `Very High`.

### Phase 4: Output & Reporting (Minimalist)
**Goal:** Make the results interpretable.
*   **Tasks:**
    1. Output the final computed CVI scores from Haskell back as structured JSON.
    2. Write a Python runner function to parse the Haskell JSON and output a clear tabular format (e.g., Markdown table or CSV).
    3. Include a summary column explaining *why* a district scored what it did (e.g., "Triggered 'Sinking City' pattern").

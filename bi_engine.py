import os
import re
import json
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from pydantic import BaseModel, Field

from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from langchain_openai import AzureChatOpenAI

load_dotenv()

# -----------------------------
# RISK THRESHOLDS (tunable)
# -----------------------------
RISK_HIGH_THRESHOLD = float(os.getenv("RISK_HIGH_THRESHOLD", "0.90"))
RISK_MED_THRESHOLD = float(os.getenv("RISK_MED_THRESHOLD", "0.50"))


# -----------------------------
# PLAN SCHEMA
# -----------------------------

class AvailabilityPlan(BaseModel):
    type: str = Field(default="none", description="none|now|next_month|this_month|quarter|after_end")
    value: Optional[str] = None


class BudgetPlan(BaseModel):
    max_rate: Optional[float] = None


class TeamPlan(BaseModel):
    size: Optional[int] = None
    allocation: Optional[float] = None


class ScenarioPlan(BaseModel):
    kind: str = Field(default="none", description="none|team_opt|gap|risk")

class ReasoningPlan(BaseModel):
    kind: str = Field(default="collab", description="collab|collab_success|uni_top|uni_pair")
    focus_person: Optional[str] = None


class QueryPlan(BaseModel):
    query_type: str
    skills: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    seniority: Optional[str] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    availability: AvailabilityPlan = Field(default_factory=AvailabilityPlan)
    budget: BudgetPlan = Field(default_factory=BudgetPlan)
    team: TeamPlan = Field(default_factory=TeamPlan)
    scenario: ScenarioPlan = Field(default_factory=ScenarioPlan)
    reasoning: ReasoningPlan = Field(default_factory=ReasoningPlan)
    aggregation_kind: Optional[str] = None
    rfp_keyword: Optional[str] = None
    certification_mode: bool = False
    project_mode: bool = False




class BusinessIntelligenceEngine:
    """
    GraphRAG-based Business Intelligence Engine for TalentMatch.

    Key upgrades in this version:
    - Deterministic "logic" LLM (temp=0) for classification / cypher generation stability
    - Safer Cypher generation guardrails (read-only allowlist)
    - Better temporal support: next month, Q4, generic "after"
    - Adds missing BI capabilities (still routed under 6 query types):
        * Active projects counting
        * Skills gap analysis (pipeline/RFP)
        * Risk assessment (single points of failure)
        * What-if simulation (no DB writes)
    - Privacy masking disabled by default to return real names
    """

    # -----------------------------
    # INIT
    # -----------------------------
    def __init__(self):
        # Neo4j
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password123")
        )

        # Privacy / debug flags
        self.allow_deanon = os.getenv("ALLOW_DEANONYMIZATION", "false").lower() == "true"

        # LLM for deterministic logic (classification / cypher)
        self.llm_logic = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )

        # LLM for natural language summarization
        self.llm_creative = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )

    # -----------------------------
    # QUERY PLANNING (NEW)
    # -----------------------------
    # -----------------------------
    # NEW PLANNING + SAFETY LAYER
    # -----------------------------

    def _extract_skills_from_text(self, question: str) -> List[str]:
        known = [
            "python", "java", "react", "node", "node.js", "aws", "kubernetes",
            "terraform", "docker", "security", "machine learning", "ml", "fintech",
            "typescript", "fastapi", "django", "spring", "gcp", "azure"
        ]
        q = question.lower()
        skills = []
        for s in known:
            if s in q:
                skills.append("Node.js" if s == "node.js" else ("Machine Learning" if s == "ml" else s.title()))
        # capture pattern "with X and Y"
        and_split = re.split(r"with|and|&|,", q)
        for token in and_split:
            tok = token.strip()
            if len(tok) > 2 and tok.isalpha() and tok.title() not in skills:
                # keep short list to avoid noise
                if tok in ["python", "java", "react", "node", "aws", "kubernetes", "security"]:
                    skills.append(tok.title())
        return list(dict.fromkeys(skills))

    def _heuristic_plan(self, question: str) -> Optional[QueryPlan]:
        q = question.lower()
        qt = None
        scenario_kind = "none"
        reasoning_kind = "collab"
        aggregation_kind = "none"
        rfp_keyword = None
        certification_mode = False
        project_mode = False

        if any(k in q for k in ["how many", "count", "number of"]):
            qt = "counting"
            if "project" in q:
                project_mode = True
        elif ("optimal" in q and "team" in q) or ("team" in q and "budget" in q) or ("team" in q and "budget constraints" in q):
            qt = "scenario"
            scenario_kind = "team_opt"
        elif "gap" in q:
            qt = "scenario"
            scenario_kind = "gap"
        elif ("risk" in q or "single point" in q or "single points of failure" in q or "spof" in q):
            qt = "scenario"
            scenario_kind = "risk"
        elif any(k in q for k in ["worked together", "worked with", "same university"]):
            qt = "reasoning"
            if "same university" in q and ("top performer" in q or "top performers" in q):
                reasoning_kind = "uni_top"
            elif "same university" in q:
                reasoning_kind = "uni_pair"
            elif "success" in q or "successfully" in q:
                reasoning_kind = "collab_success"
            else:
                reasoning_kind = "collab"
        elif any(k in q for k in ["available next month", "next month", "after", "ends", "this month", "q1", "q2", "q3", "q4"]):
            qt = "temporal"
        elif any(k in q for k in ["average", "avg", "total", "sum", "distribution"]):
            qt = "aggregation"
            if "distribution" in q and ("graduation year" in q or "graduation" in q):
                aggregation_kind = "skills_by_grad_year"
            elif "capacity" in q:
                aggregation_kind = "capacity_total"
            elif "rate" in q:
                aggregation_kind = "avg_rate"
            else:
                aggregation_kind = "avg_years"
        elif any(k in q for k in ["find", "list", "show", "available", "filter"]):
            qt = "filtering"

        # Certification intent (e.g., AWS certifications)
        if "certification" in q or "certifications" in q or "certified" in q or "certs" in q or "cert " in q:
            certification_mode = True

        if not qt:
            return None

        skills = self._extract_skills_from_text(question)
        if rfp_keyword:
            skills = []

        seniority = None
        if "senior" in q:
            seniority = "senior"
        timezone = None

        # tylko jeśli user faktycznie mówi o strefie czasowej
        if "timezone" in q or "time zone" in q:
            m = re.search(r"\b(pt|et|cet|gmt|utc)\b", q)
            if m:
                timezone = m.group(1).upper()
        if not timezone:
            if "pacific" in q:
                timezone = "PT"
            elif "eastern" in q:
                timezone = "ET"
            elif "central european" in q or "cest" in q or "cet" in q:
                timezone = "CET"
            elif "gmt" in q or "greenwich" in q:
                timezone = "GMT"
            elif "utc" in q:
                timezone = "UTC"

        availability = AvailabilityPlan()
        if "next month" in q:
            availability.type = "next_month"
        elif "this month" in q:
            availability.type = "this_month"
        elif re.search(r"q[1-4]", q):
            availability.type = "quarter"
        elif "after" in q or "ends" in q:
            availability.type = "after_end"
        elif "available" in q:
            availability.type = "now"

        budget = BudgetPlan()
        m = re.search(r"\$?(\d{2,5})", q)
        if m and "budget" in q:
            budget.max_rate = float(m.group(1))

        team = TeamPlan()
        msize = re.search(r"(\d+) (?:people|developers|engineers|team)", q)
        if msize:
            team.size = int(msize.group(1))
        malloc = re.search(r"(0\.\d+|1\.0)", q)
        if malloc:
            try:
                team.allocation = float(malloc.group(1))
            except Exception:
                pass

        if qt == "scenario" and scenario_kind == "team_opt":
            if "rfp" in q:
                # prosta heurystyka – rozbudujesz później
                if "fintech" in q:
                    rfp_keyword = "fintech"
                # opcjonalnie: inne branże
                elif "healthcare" in q:
                    rfp_keyword = "healthcare"
                elif "ecommerce" in q or "e-commerce" in q:
                    rfp_keyword = "ecommerce"
                # albo fallback: weź słowo przed "rfp" (opcjonalne)
                # else: rfp_keyword = "rfp    

        # Extract focus person for reasoning queries (e.g., "worked with Jacob Young")
        focus_person = None
        if qt == "reasoning":
            # Try to capture name after 'with'
            mname = re.search(r"with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", question)
            if mname:
                focus_person = mname.group(1).strip()
            else:
                # Fallback: any two-capitalized-words name in the question
                mname2 = re.search(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b", question)
                if mname2:
                    focus_person = mname2.group(1).strip()

        return QueryPlan(
            query_type=qt,
            skills=skills,
            seniority=seniority,
            timezone=timezone,
            availability=availability,
            budget=budget,
            team=team,
            scenario=ScenarioPlan(kind=scenario_kind),
            reasoning=ReasoningPlan(kind=reasoning_kind, focus_person=focus_person),
            aggregation_kind=aggregation_kind,
            rfp_keyword=rfp_keyword,
            certification_mode=certification_mode,
            project_mode=project_mode,
        )

    def _llm_plan(self, question: str) -> Optional[QueryPlan]:
        schema_hint = {
            "query_type": "counting|filtering|aggregation|reasoning|temporal|scenario",
            "skills": ["Python"],
            "roles": ["Developer"],
            "seniority": "senior|mid|junior|lead|null",
            "timezone": "PT|ET|CET|GMT|UTC|null",
            "location": "City or null",
            "availability": {"type": "none|now|next_month|this_month|quarter|after_end", "value": None},
            "budget": {"max_rate": None},
            "team": {"size": None, "allocation": None},
            "scenario": {"kind": "none|team_opt|gap|risk"},
            "reasoning": {"kind": "collab|collab_success|uni_top|uni_pair", "focus_person": None}
        }

        prompt = f"""
You are a deterministic planner for NL-to-Cypher. Return ONLY JSON, no prose.
Schema hint: {json.dumps(schema_hint)}
Question: {question}
Return a single JSON object matching the schema exactly.
"""
        try:
            resp = self.llm_logic.invoke(prompt)
            content = (resp.content or "").strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```", 1)[0].strip()
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0].strip()
            plan_dict = json.loads(content)
            return QueryPlan(**plan_dict)
        except Exception:
            return None

    def plan_question(self, question: str) -> Optional[QueryPlan]:
        heur = self._heuristic_plan(question)
        if heur:
            return heur
        return self._llm_plan(question)

    # -----------------------------
    # WHAT-IF SIMULATOR (NEW)
    # -----------------------------
    def simulate_scenario(self, 
                         skill: str,
                         required_allocation: float = 1.0,
                         max_budget: Optional[float] = None,
                         timezone_filter: Optional[str] = None,
                         min_years_exp: Optional[int] = None) -> Dict[str, Any]:
        """
        What-if simulator: Find candidates matching criteria WITHOUT making database changes.
        
        Args:
            skill: Required skill
            required_allocation: Needed allocation (0.0-1.0)
            max_budget: Maximum hourly rate
            timezone_filter: Filter by timezone (e.g., "ET", "CET")
            min_years_exp: Minimum years of experience
            
        Returns:
            Simulation results with matching candidates and capacity analysis
        """
        params = {"skill": skill, "needed": required_allocation}
        
        filters = []
        if max_budget:
            filters.append("p.rate <= $max_budget")
            params["max_budget"] = max_budget
        if timezone_filter:
            filters.append("p.timezone = $timezone")
            params["timezone"] = timezone_filter
        if min_years_exp:
            filters.append("coalesce(p.years_experience, p.years_of_experience, 0) >= $min_years")
            params["min_years"] = min_years_exp
            
        filter_clause = " AND " + " AND ".join(filters) if filters else ""
        
        cypher = f"""
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        WHERE (toLower(coalesce(s.id,s.name,'')) CONTAINS toLower($skill)
               OR toLower(coalesce(s.name,s.id,'')) CONTAINS toLower($skill))
        {filter_clause}
        OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
         WITH p, sum(coalesce(r.allocation_percentage, coalesce(r.allocation,0.0))) as current_load
        WITH p, current_load, (1.0 - current_load) as spare_capacity
        WHERE spare_capacity >= $needed
        RETURN 
            p.name as name,
            p.role as role,
            p.seniority as seniority,
            p.rate as hourly_rate,
            p.timezone as timezone,
            coalesce(p.years_experience, p.years_of_experience) as years_exp,
            round(spare_capacity * 100, 0) as available_capacity_percent,
            current_load
        ORDER BY p.rate ASC, p.performance_score DESC
        LIMIT 30
        """
        
        try:
            res = self.graph.query(cypher, params)
            return {
                "type": "scenario",
                "simulation_mode": True,
                "simulation_params": {
                    "skill": skill,
                    "required_allocation": required_allocation,
                    "max_budget": max_budget,
                    "timezone_filter": timezone_filter,
                    "min_years_exp": min_years_exp
                },
                "matching_candidates": res,
                "candidate_count": len(res),
                "total_available_capacity": sum(r.get("available_capacity_percent", 0) for r in res) / 100.0 if res else 0,
                "cypher": cypher,
                "success": True
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -----------------------------
    # PRIVACY
    # -----------------------------
    def _anonymize_data(self, data: Any) -> Tuple[Any, Dict[str, str]]:
        """
        Privacy masking disabled: return data unchanged with no decoder map.
        """
        return data, {}

    def risk_validation_snippets(self) -> str:
        """
        Neo4j Browser sanity checks for SPOF feature:

        // (a) Verify HAS_SKILL edges exist
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        RETURN count(*) as has_skill_edges LIMIT 1;

        // (b) Verify ASSIGNED_TO edges have allocation values
        MATCH (:Person)-[r:ASSIGNED_TO]->(:Project)
        RETURN count(r) as assigned_edges, count{ (r.allocation IS NOT NULL) OR (r.allocation_percentage IS NOT NULL) } as with_alloc;

        // (c) Quick SPOF preview (no risk ranking)
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        WITH toLower(trim(coalesce(s.id, s.name, ''))) as skill, collect(DISTINCT p) as owners
        WHERE skill <> '' AND size(owners) = 1
        RETURN skill, size(owners) as owners_count LIMIT 10;

        Example expected outputs (mock):
        - has_skill_edges: 1200
        - assigned_edges: 80; with_alloc: 78
        - spof preview rows like: {skill: 'elixir', owners_count: 1}
        """
        return "See docstring for validation queries."

    def _fallback_summary(self, data: Any) -> str:
        """Deterministic, non-LLM summary used when creative model fails."""
        if data is None or data == {} or data == []:
            return "I searched the Knowledge Graph but found no matching records."

        if isinstance(data, list):
            if not data:
                return "I searched the Knowledge Graph but found no matching records."

            # Structured rows
            if all(isinstance(x, dict) for x in data if x is not None):
                lines: List[str] = []
                for row in data[:20]:
                    if row is None:
                        continue
                    if "focus_person" in row and "collaborator" in row:
                        company = row.get("shared_company") or row.get("company")
                        sentence = f"{row.get('focus_person')} worked with {row.get('collaborator')}"
                        if company:
                            sentence += f" at {company}"
                        lines.append(f"- {sentence}")
                    else:
                        parts = [f"{k}: {v}" for k, v in row.items()]
                        lines.append(f"- {'; '.join(parts)}")

                if not lines:
                    lines.append("- No readable rows.")

                if len(data) > 20:
                    lines.append("...additional rows omitted.")

                return "Results:\n" + "\n".join(lines)

            preview = ", ".join(str(x) for x in data[:10])
            if len(data) > 10:
                preview += ", ..."
            return f"Results: {preview}"

        if isinstance(data, dict):
            return "Result: " + "; ".join(f"{k}: {v}" for k, v in data.items())

        return f"Result: {data}"

    # -----------------------------
    # CYPHER BUILDERS (PLAN -> QUERY)
    # -----------------------------

    def _availability_clause(self, alias: str, availability: AvailabilityPlan) -> Tuple[str, Dict[str, Any]]:
        params: Dict[str, Any] = {}

        # ✅ IMPORTANT: "none" means NO availability filter
        if availability is None or availability.type in ["none", None]:
            return "", params

        # ✅ "now" means spare capacity
        if availability.type == "now":
            return "WHERE coalesce(load,0) < 1.0", params

        window = self._window_from_availability(availability)
        if availability.type in ["this_month", "next_month", "quarter"] and window:
            params["start"] = window["start"]
            params["end"] = window["end"]
            clause = (
                "WHERE coalesce(load,0) < 1.0 OR (latest_end IS NOT NULL AND date(latest_end) <= date($start))"
            )
            return clause, params

        if availability.type == "after_end":
            # you can decide: usually means show next availability; here keep load filter
            return "WHERE coalesce(load,0) < 1.0", params

        return "", params


    def _skill_and_clause(self, skills: List[str]) -> str:
        if not skills:
            return ""
        return (
            "MATCH (p)-[:HAS_SKILL]->(s:Skill)\n"
            "WITH p, collect(DISTINCT toLower(coalesce(s.id,s.name,''))) as skill_list\n"
            "WHERE ALL(x IN $skills WHERE ANY(sk IN skill_list WHERE sk CONTAINS x))\n"
        )

    def _base_load_cte(self) -> str:
        return (
            "OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(proj:Project)\n"
            "WITH p, sum(coalesce(r.allocation_percentage, coalesce(r.allocation,0.0))) as load, max(coalesce(r.end_date, proj.end_date)) as latest_end\n"
        )

    def _cypher_counting(self, plan: QueryPlan) -> Tuple[str, Dict[str, Any]]:
        # Certification-aware counting: if user asked about certifications, match EARNED
        if plan.certification_mode and plan.skills:
            params: Dict[str, Any] = {"skills": [s.lower() for s in plan.skills]}
            cypher = (
                "MATCH (p:Person)-[:EARNED]->(c:Certification)\n"
                "WHERE ANY(x IN $skills WHERE toLower(coalesce(c.id,c.name,'')) CONTAINS x)\n"
            )
            cypher += self._base_load_cte()
            avail_clause, avail_params = self._availability_clause("p", plan.availability)
            params.update(avail_params)
            cypher += f"{avail_clause}\nRETURN count(DISTINCT p) as result"
            return cypher, params

        # Project counting mode
        if plan.project_mode:
            cypher = (
                "MATCH (proj:Project)\n"
                "WHERE toLower(coalesce(proj.status,'')) IN ['ongoing','active','in progress']\n"
                "RETURN count(DISTINCT proj) as result"
            )
            return cypher, {}

        params: Dict[str, Any] = {"skills": [s.lower() for s in plan.skills]}
        skill_cte = self._skill_and_clause(plan.skills)
        cypher = "MATCH (p:Person)\n"
        if skill_cte:
            cypher += skill_cte
        cypher += self._base_load_cte()
        avail_clause, avail_params = self._availability_clause("p", plan.availability)
        params.update(avail_params)
        cypher += f"{avail_clause}\nRETURN count(DISTINCT p) as result"
        return cypher, params

    def _cypher_filtering(self, plan: QueryPlan) -> Tuple[str, Dict[str, Any]]:
        params: Dict[str, Any] = {"skills": [s.lower() for s in plan.skills]}
        skill_cte = self._skill_and_clause(plan.skills)
        cypher = "MATCH (p:Person)\n"
        if skill_cte:
            cypher += skill_cte
        cypher += self._base_load_cte()
        where_clauses = []
        window = self._window_from_availability(plan.availability)

        # ✅ Only apply availability filtering if user asked for it
        if plan.availability and plan.availability.type and plan.availability.type != "none":
            if window:
                params.update({"start": window["start"], "end": window["end"]})
                where_clauses.append(
                    "coalesce(load,0) < 1.0 OR (latest_end IS NOT NULL AND date(latest_end) <= date($start))"
                )
            else:
                # for availability types like 'now' or 'after_end' without explicit window, enforce spare capacity
                where_clauses.append("coalesce(load,0) < 1.0")
        else:
            where_clauses.append("coalesce(load,0) < 1.0")

        if plan.seniority:
            params["sen"] = plan.seniority
            where_clauses.append("toLower(coalesce(p.seniority,'')) CONTAINS toLower($sen)")
        if plan.timezone:
            params["tz"] = plan.timezone
            where_clauses.append("p.timezone = $tz")
        cypher += f"WHERE {' AND '.join(where_clauses)}\n"

        # Collect skills AFTER filtering, in a valid aggregation step
        cypher += "OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)\n"
        cypher += "WITH p, load, collect(DISTINCT coalesce(s.id,s.name)) as skills\n"

        cypher += (
            "RETURN p.name as name, p.role as role, p.seniority as seniority, "
            "round((1.0 - coalesce(load,0))*100,0) as availability_percent, "
            "skills\n"
            "ORDER BY availability_percent DESC LIMIT 50"
        )

        return cypher, params

    def _cypher_aggregation(self, plan: QueryPlan) -> Tuple[str, Dict[str, Any]]:
        # 1) Skills distribution by graduation year
        if plan.aggregation_kind == "skills_by_grad_year":
            cypher = """
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE p.graduation_year IS NOT NULL
            WITH p.graduation_year as graduation_year,
                coalesce(s.id,s.name) as skill,
                count(DISTINCT p) as people_count
            RETURN graduation_year, skill, people_count
            ORDER BY graduation_year DESC, people_count DESC
            LIMIT 50
            """
            return cypher, {}

        # 2) Total capacity available (sum of spare allocation)
        if plan.aggregation_kind == "capacity_total":
            params: Dict[str, Any] = {}
            cypher = "MATCH (p:Person)\n" + self._base_load_cte()
            avail_clause, avail_params = self._availability_clause("p", plan.availability)
            params.update(avail_params)
            if avail_clause:
                cypher += f"{avail_clause}\n"
            cypher += "RETURN round(sum(1.0 - coalesce(load,0)),2) as total_capacity, count(p) as people"  # spare capacity
            return cypher, params

        # 3) Average years with optional skill filter
        params: Dict[str, Any] = {"skills": [s.lower() for s in plan.skills]}
        skill_cte = self._skill_and_clause(plan.skills)
        cypher = "MATCH (p:Person)\n"
        if skill_cte:
            cypher += skill_cte

        # Average hourly rate when requested
        if plan.aggregation_kind == "avg_rate":
            cypher += (
                "RETURN\n"
                "    round(avg(coalesce(p.rate,0)), 2) as avg_rate,\n"
                "    count(p) as people"
            )
            return cypher, params

        cypher += (
            "RETURN\n"
            "    round(avg(coalesce(p.years_experience, p.years_of_experience)), 2) as avg_years,\n"
            "    count(p) as people"
        )
        return cypher, params

    def _cypher_reasoning(self, plan: QueryPlan) -> Tuple[str, Dict[str, Any]]:
        kind = (plan.reasoning.kind or "collab").lower()
        params: Dict[str, Any] = {}

        # 1) Developers who worked together successfully (proxy)
        # "successfully" = shared_count >= 2 OR both have decent perf score (>=7.5)
        if kind == "collab_success":
            cypher = """
            MATCH (a:Person)-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(b:Person)
            WHERE a.name < b.name
            WITH a, b,
                collect(DISTINCT c.name) as shared_companies,
                count(DISTINCT c) as shared_count,
                coalesce(a.performance_score, 0.0) as a_score,
                coalesce(b.performance_score, 0.0) as b_score
            WHERE shared_count >= 2 OR (a_score >= 7.5 AND b_score >= 7.5)
            RETURN
                a.name as person_a,
                b.name as person_b,
                shared_companies,
                shared_count,
                a_score,
                b_score
            ORDER BY shared_count DESC, (a_score + b_score) DESC
            LIMIT 30
            """
            return cypher, params

        # 2) Basic "worked together" (any shared company)
        if kind == "collab":
            # If focus_person is known -> collaborators of that person
            if plan.reasoning.focus_person:
                params["name"] = plan.reasoning.focus_person
                cypher = """
                MATCH (p1:Person {name: $name})-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(p2:Person)
                WHERE p1.name <> p2.name
                WITH p1, p2, collect(DISTINCT c.name) as shared_companies, count(DISTINCT c) as shared_count
                RETURN
                    p1.name as focus_person,
                    p2.name as collaborator,
                    shared_companies,
                    shared_count
                ORDER BY shared_count DESC
                LIMIT 30
                """
                return cypher, params

            cypher = """
            MATCH (a:Person)-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(b:Person)
            WHERE a.name < b.name
            WITH a, b, collect(DISTINCT c.name) as shared_companies, count(DISTINCT c) as shared_count
            WHERE shared_count >= 1
            RETURN a.name as person_a, b.name as person_b, shared_companies, shared_count
            ORDER BY shared_count DESC
            LIMIT 30
            """
            return cypher, params

        # 3) Developers from same university as our top performers
        if kind == "uni_top":
            cypher = """
            MATCH (tp:Person)-[:STUDIED_AT]->(u:University)
            WHERE coalesce(tp.performance_score,0) >= 8.0
            MATCH (p:Person)-[:STUDIED_AT]->(u)
            WHERE p.name <> tp.name
            RETURN
                tp.name as top_performer,
                coalesce(tp.performance_score,0) as top_score,
                p.name as colleague,
                coalesce(p.performance_score,0) as colleague_score,
                u.name as shared_university
            ORDER BY top_score DESC, colleague_score DESC
            LIMIT 50
            """
            return cypher, params

        # 4) Any pairs from same university
        if kind == "uni_pair":
            cypher = """
            MATCH (a:Person)-[:STUDIED_AT]->(u:University)<-[:STUDIED_AT]-(b:Person)
            WHERE a.name < b.name
            RETURN a.name as developer_1, b.name as developer_2, u.name as shared_university
            LIMIT 30
            """
            return cypher, params

        # fallback
        return "MATCH (n) RETURN n LIMIT 5", {}


    def _cypher_temporal(self, plan: QueryPlan) -> Tuple[str, Dict[str, Any]]:
        params: Dict[str, Any] = {}
        window = self._window_from_availability(plan.availability)
        cypher = "MATCH (p:Person)\n" + self._base_load_cte()

        # "after current project ends" -> show next availability date from assignments
        if plan.availability and plan.availability.type == "after_end":
            cypher = (
                "MATCH (p:Person)-[r:ASSIGNED_TO]->(proj:Project)\n"
                "WHERE coalesce(r.end_date, proj.end_date) IS NOT NULL\n"
                "WITH p, proj, r, coalesce(r.end_date, proj.end_date) as avail_date, coalesce(r.allocation_percentage, coalesce(r.allocation,0.0)) as alloc\n"
                "WITH p, proj, avail_date, sum(alloc) as load_at_end\n"
                "RETURN p.name as name, coalesce(proj.title, proj.name) as current_project, avail_date as available_from, "
                "round((1.0 - coalesce(load_at_end,0.0))*100,0) as availability_percent\n"
                "ORDER BY available_from ASC LIMIT 30"
            )
            return cypher, params

        if window:
            params.update({"start": window["start"], "end": window["end"]})
            cypher += (
                "WITH p, load, latest_end\n"
                "WHERE coalesce(load,0) < 1.0 OR (latest_end IS NOT NULL AND date(latest_end) <= date($start))\n"
            )
        else:
            cypher += "WITH p, load, latest_end WHERE coalesce(load,0) < 1.0\n"
        cypher += (
            "RETURN p.name as name, p.role as role, round((1.0 - coalesce(load,0))*100,0) as availability_percent, latest_end as available_from\n"
            "ORDER BY availability_percent DESC LIMIT 30"
        )
        return cypher, params

    def _cypher_scenario(self, plan: QueryPlan) -> Tuple[str, Dict[str, Any]]:
        if plan.scenario.kind == "gap":
            cypher = (
                "MATCH (pr:Project)-[:REQUIRES]->(s:Skill) WHERE toLower(coalesce(pr.status,''))='new rfp'\n"
                "WITH collect(DISTINCT toLower(coalesce(s.id,s.name,''))) as required_skills\n"
                "MATCH (p:Person)\n"
                "OPTIONAL MATCH (p)-[a:ASSIGNED_TO]->(proj:Project)\n"
                "WITH required_skills, p, sum(coalesce(a.allocation_percentage, a.allocation, 0.0)) as load\n"
                "WHERE coalesce(load,0) < 1.0\n"
                "OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)\n"
                "WITH required_skills, collect(DISTINCT toLower(coalesce(s.id,s.name,''))) as available_skills\n"
                "RETURN required_skills, available_skills, [x IN required_skills WHERE NOT x IN available_skills] as missing_skills"
            )
            return cypher, {}

        if plan.scenario.kind == "risk":
            return self._cypher_risk_spof(plan)

            # ✅ team_opt via RFP (keyword -> required skills -> match people)
        if plan.scenario.kind == "team_opt" and plan.rfp_keyword:
            cypher = """
            MATCH (r:RFP)
            WHERE toLower(coalesce(r.title, r.name, r.description, '')) CONTAINS toLower($rfp_kw)
            OPTIONAL MATCH (r)-[:NEEDS]->(req:Skill)
            WITH r, collect(DISTINCT toLower(coalesce(req.id, req.name, ''))) AS required_skills
            WHERE size(required_skills) > 0

            MATCH (p:Person)
            OPTIONAL MATCH (p)-[a:ASSIGNED_TO]->(:Project)
            WITH r, required_skills, p,
                sum(coalesce(a.allocation_percentage, a.allocation, 0.0)) AS load
            WHERE (1.0 - coalesce(load,0.0)) >= $alloc

            OPTIONAL MATCH (p)-[:HAS_SKILL]->(ps:Skill)
            WITH r, required_skills, p, load,
                collect(DISTINCT toLower(coalesce(ps.id, ps.name, ''))) AS person_skills

            WITH r, required_skills, p, load,
                [s IN required_skills WHERE s IN person_skills] AS matched,
                [s IN required_skills WHERE NOT s IN person_skills] AS missing

            RETURN
            r.title AS rfp_title,
            r.budget AS rfp_budget,
            required_skills,
            p.name AS name,
            p.role AS role,
            p.rate AS rate,
            round((1.0 - coalesce(load,0.0)) * 100, 0) AS availability_percent,
            matched,
            missing,
            size(matched) AS matched_count,
            size(missing) AS missing_count
            ORDER BY missing_count ASC, matched_count DESC, rate ASC
            LIMIT 200
            """
            params = {
                "rfp_kw": plan.rfp_keyword,
                "alloc": (plan.team.allocation or 1.0),
            }
            return cypher, params


        # team_opt
        params: Dict[str, Any] = {
            "skills": [s.lower() for s in plan.skills],
            "max_rate": plan.budget.max_rate if plan.budget.max_rate else 1_000_000,
        }
        team_size = plan.team.size or 5
        alloc = plan.team.allocation or 1.0
        cypher = (
            "MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)\n"
            "WHERE $skills = [] OR toLower(coalesce(s.id,s.name,'')) IN $skills\n"
            "WITH p, collect(DISTINCT toLower(coalesce(s.id,s.name,''))) as skill_list\n"
            "OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(proj:Project)\n"
            "WITH p, skill_list, sum(coalesce(r.allocation_percentage, coalesce(r.allocation,0.0))) as load, max(coalesce(r.end_date, proj.end_date)) as latest_end\n"
            "WHERE coalesce(load,0) + $alloc <= 1.0 AND coalesce(p.rate,0) <= $max_rate\n"
            "RETURN p.name as name, p.role as role, p.rate as rate, coalesce(p.years_experience, p.years_of_experience) as years_exp,\n"
            "       round((1.0 - coalesce(load,0))*100,0) as availability_percent, skill_list\n"
            "ORDER BY rate ASC, availability_percent DESC LIMIT $limit"
        )
        params["alloc"] = alloc
        params["limit"] = team_size * 3
        return cypher, params

    def _cypher_risk_spof(self, plan: QueryPlan) -> Tuple[str, Dict[str, Any]]:
        """
        Single Point Of Failure assessment:
        - skill: normalized key (toLower(trim(id/name)))
        - owner: exactly one person has the skill
        - load: sum of allocation on current assignments
        - availability_percent: round((1.0 - load)*100, 0)
        - projects: list of {title, allocation, end_date}
        - risk_level: HIGH/MEDIUM/LOW by thresholds
        """
        cypher = (
            "MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)\n"
            "WITH toLower(trim(coalesce(s.id, s.name, ''))) as skill, collect(DISTINCT p) as owners\n"
            "WHERE skill <> '' AND size(owners) = 1\n"
            "WITH skill, owners[0] as owner\n"
            "OPTIONAL MATCH (owner)-[r:ASSIGNED_TO]->(proj:Project)\n"
            "WITH skill, owner,\n"
            "     sum(coalesce(r.allocation_percentage, coalesce(r.allocation, 0.0))) as load,\n"
            "     collect({title: coalesce(proj.title, proj.name),\n"
            "              allocation: coalesce(r.allocation_percentage, coalesce(r.allocation, 0.0)),\n"
            "              end_date: coalesce(r.end_date, proj.end_date)}) as projects\n"
            "WITH skill, owner, coalesce(load, 0.0) as load, projects,\n"
            "     round((1.0 - coalesce(load, 0.0)) * 100, 0) as availability_percent\n"
            "WITH skill, owner, load, availability_percent, projects,\n"
            "     CASE WHEN load >= $HIGH THEN 'HIGH'\n"
            "          WHEN load >= $MED THEN 'MEDIUM'\n"
            "          ELSE 'LOW' END as risk_level,\n"
            "     CASE WHEN load >= $HIGH THEN 3 WHEN load >= $MED THEN 2 ELSE 1 END as risk_rank\n"
            "RETURN skill, owner.name as owner_name, load, availability_percent, risk_level, projects\n"
            "ORDER BY risk_rank DESC, load DESC, skill ASC\n"
            "LIMIT 50"
        )
        params: Dict[str, Any] = {"HIGH": RISK_HIGH_THRESHOLD, "MED": RISK_MED_THRESHOLD}
        return cypher, params

    def _build_cypher_from_plan(self, plan: QueryPlan) -> Tuple[Optional[str], Dict[str, Any]]:
        builders = {
            "counting": self._cypher_counting,
            "filtering": self._cypher_filtering,
            "aggregation": self._cypher_aggregation,
            "reasoning": self._cypher_reasoning,
            "temporal": self._cypher_temporal,
            "scenario": self._cypher_scenario,
        }
        builder = builders.get(plan.query_type)
        if not builder:
            return None, {}
        return builder(plan)

    def _is_safe_cypher(self, cypher: str) -> bool:
        if not cypher:
            return False
        lowered = cypher.lower()
        forbidden = ["create", "merge", "set", "delete", "detach", "call", "apoc", "gds", "load csv", "drop"]
        if any(f in lowered for f in forbidden):
            return False
        allowed_starts = ("match", "with", "return", "optional match")
        return lowered.strip().startswith(allowed_starts)

    # -----------------------------
    # ANSWER FORMATTING
    # -----------------------------

    def _format_answer(self, plan: QueryPlan, rows: List[Dict[str, Any]]) -> str:
        if not rows:
            # Scenario-specific empty messages
            if plan.query_type == "scenario" and plan.scenario.kind == "risk":
                return "Based on graph results: no single points of failure found."
            if plan.query_type == "scenario" and plan.scenario.kind == "gap":
                return "Based on graph results: no missing skills detected for pipeline projects."

            skills_txt = ", ".join(plan.skills) if plan.skills else "N/A"
            constraints = []
            if plan.seniority:
                constraints.append(f"seniority={plan.seniority}")
            if plan.timezone:
                constraints.append(f"timezone={plan.timezone}")
            if plan.availability and plan.availability.type and plan.availability.type != "none":
                constraints.append(f"availability={plan.availability.type}")
            c_txt = ", ".join(constraints) if constraints else "no extra constraints"

            return (
                f"No matches found in the graph for skills [{skills_txt}] with constraints ({c_txt}). "
                "Try removing 'senior' or asking without availability/time filters."
            )


        if plan.query_type == "counting":
            count_val = rows[0].get("result") if rows else 0
            if getattr(plan, "project_mode", False):
                return f"Based on graph results: {count_val} active projects."
            if getattr(plan, "certification_mode", False):
                return f"Based on graph results: {count_val} certified people."
            return f"Based on graph results: {count_val} matching people."

        if plan.query_type == "scenario":
            if plan.scenario.kind == "gap":
                # Two possible shapes:
                # 1) Enhanced query rows: [{skill, projects_requiring, available_people}, ...]
                if rows and "skill" in rows[0]:
                    lines = [
                        f"- {r.get('skill')} (projects_requiring={r.get('projects_requiring')}, available_people={r.get('available_people')})"
                        for r in rows[:20]
                    ]
                    return "Based on graph results:\n" + "\n".join(lines)
                # 2) Simple row with missing_skills list
                row = rows[0] if rows else {}
                return f"Based on graph results: missing skills {row.get('missing_skills')}"

            if plan.scenario.kind == "risk":
                lines = []
                for r in rows[:20]:
                    skill = r.get("skill")
                    owner = r.get("owner_name") or r.get("owner")
                    load = r.get("load")
                    avail = r.get("availability_percent")
                    level = r.get("risk_level")
                    projects = r.get("projects") or []
                    proj_strs = []
                    for p in projects:
                        title = (p.get("title") if isinstance(p, dict) else None) or "Unknown"
                        alloc = (p.get("allocation") if isinstance(p, dict) else None)
                        endd = (p.get("end_date") if isinstance(p, dict) else None)
                        piece = title
                        if alloc is not None:
                            piece += f" (alloc {alloc})"
                        if endd is not None:
                            piece += f", end {endd}"
                        proj_strs.append(piece)
                    proj_out = "; ".join(proj_strs) if proj_strs else "None"
                    lines.append(f"- {skill} -> {owner} (load {load:.2f}, availability {avail}%) [{level}] | Projects: {proj_out}")
                if len(rows) > 20:
                    lines.append("... additional rows omitted")
                return "Based on graph results:\n" + "\n".join(lines)

            # team_opt or other scenarios -> list candidates
            if plan.scenario.kind == "team_opt" and rows and ("matched" in rows[0] or "rfp_title" in rows[0]):
                # Intelligent Team Composition Logic
                lines = ["Proposed Optimal Team Composition:"]
                
                # 1. Deduplicate candidates
                seen = set()
                unique_rows = []
                for r in rows:
                    if r.get("name") not in seen:
                        seen.add(r.get("name"))
                        unique_rows.append(r)

                # 2. Group by Role (to ensure diversity)
                by_role = {}
                for r in unique_rows:
                    role = r.get("role", "General")
                    if role not in by_role:
                        by_role[role] = []
                    by_role[role].append(r)

                # 3. Select best candidate from each role category (Greedy algorithm)
                selected_team = []
                total_rate = 0.0
                
                # Sort roles by scarcity (optional, here just alphabetical)
                for role in sorted(by_role.keys()):
                    # Sort candidates by: Max matched skills DESC, Availability DESC, Rate ASC
                    candidates = sorted(
                        by_role[role], 
                        key=lambda x: (
                            -len(x.get("matched", [])), 
                            -x.get("availability_percent", 0), 
                            x.get("rate", 1000)
                        )
                    )
                    best = candidates[0]
                    selected_team.append(best)
                    total_rate += best.get("rate", 0)
                    
                    if len(selected_team) >= 5: # Limit team size for demo
                        break

                for m in selected_team:
                    match_s = ", ".join(m.get("matched", []))
                    lines.append(f"- {m.get('name')} ({m.get('role')}) | Rate: ${m.get('rate')}/h | Covers: {match_s}")
                
                lines.append(f"\nTotal Hourly Cost: ${total_rate:.2f}")
                lines.append(f"Team Size: {len(selected_team)} specialists selected from {len(unique_rows)} candidates.")
                return "\n".join(lines)

            # Fallback for generic scenarios
            lines = []
            for r in rows[:20]:
                name = r.get("name")
                role = r.get("role")
                avail = r.get("availability_percent") or r.get("available_capacity_percent") or r.get("availability_percent_capacity")
                skills = r.get("skills") or r.get("skill_list")
                frag = f"- {name} ({role})"
                if avail is not None:
                    frag += f" – availability {avail}%"
                if skills:
                    frag += f" – skills: {skills}"
                lines.append(frag)
            return "Based on graph results:\n" + "\n".join(lines)

        if plan.query_type in ["filtering", "temporal"]:
            lines = []
            for r in rows[:20]:
                name = r.get("name")
                role = r.get("role", "Unknown Role")
                
                # Special display for "Available After" queries
                if "available_from" in r:
                    date_avail = r.get("available_from")
                    proj = r.get("current_project", "Project")
                    lines.append(f"- {name} ({role}) – becomes free on {date_avail} (Ends: {proj})")
                    continue

                avail = r.get("availability_percent") or r.get("available_capacity_percent") or r.get("availability_percent_capacity")
                skills = r.get("skills") or r.get("skill_list")
                frag = f"- {name} ({role})"
                if avail is not None:
                    frag += f" – availability {avail}%"
                if skills:
                    frag += f" – skills: {skills}"
                lines.append(frag)
            return "Based on graph results:\n" + "\n".join(lines)

        if plan.query_type == "aggregation":
            # skills distribution by graduation year
            if getattr(plan, "aggregation_kind", None) == "skills_by_grad_year":
                lines = []
                for r in rows[:30]:
                    lines.append(f"- {r.get('graduation_year')}: {r.get('skill')} → {r.get('people_count')}")
                return "Skills distribution by graduation year:\n" + "\n".join(lines)

            if getattr(plan, "aggregation_kind", None) == "capacity_total":
                row = rows[0] if rows else {}
                total_capacity = row.get("total_capacity")
                people = row.get("people")
                return f"Based on graph results: total spare capacity = {total_capacity}, people counted = {people}"

            if getattr(plan, "aggregation_kind", None) == "avg_rate":
                row = rows[0] if rows else {}
                return f"Based on graph results: average hourly rate = {row.get('avg_rate')}, people counted = {row.get('people')}"

            # default: avg years
            row = rows[0] if rows else {}
            return f"Based on graph results: avg years = {row.get('avg_years')}, people counted = {row.get('people')}"


        if plan.query_type == "reasoning":
            # university top-performers output
            if rows and "shared_university" in rows[0]:
                lines = [
                    f"- {r.get('colleague')} (score {r.get('colleague_score')}) studied at {r.get('shared_university')} like top performer {r.get('top_performer')} (score {r.get('top_score')})"
                    for r in rows[:20]
                ]
                return "Based on graph results:\n" + "\n".join(lines)

            # focus_person collaboration
            if rows and "focus_person" in rows[0]:
                lines = [
                    f"- {r.get('focus_person')} worked with {r.get('collaborator')} at {r.get('shared_companies')} (shared_count={r.get('shared_count')})"
                    for r in rows[:20]
                ]
                return "Based on graph results:\n" + "\n".join(lines)

            # collab / collab_success
            lines = []
            for r in rows[:20]:
                comps = r.get("shared_companies") or r.get("companies")
                shared_count = r.get("shared_count")
                extra = f" (shared_count={shared_count})" if shared_count is not None else ""
                lines.append(f"- {r.get('person_a')} & {r.get('person_b')} shared {comps}{extra}")
            return "Based on graph results:\n" + "\n".join(lines)


        return self._fallback_summary(rows)

    # -----------------------------
    # UTILITIES: TIME WINDOWS
    # -----------------------------
    def _parse_time_window(self, question: str) -> Optional[Dict[str, str]]:
        """
        Returns dict with 'start' and 'end' ISO dates (YYYY-MM-DD) for:
        - next month
        - Q1/Q2/Q3/Q4 (this year)
        - this month
        If not detected, returns None.
        """
        q = question.lower()
        today = date.today()

        def first_day_of_month(d: date) -> date:
            return date(d.year, d.month, 1)

        def last_day_of_month(d: date) -> date:
            first = first_day_of_month(d)
            # next month first day minus 1 day
            if first.month == 12:
                next_first = date(first.year + 1, 1, 1)
            else:
                next_first = date(first.year, first.month + 1, 1)
            return next_first - timedelta(days=1)

        # this month
        if "this month" in q:
            s = first_day_of_month(today)
            e = last_day_of_month(today)
            return {"start": s.isoformat(), "end": e.isoformat()}

        # next month
        if "next month" in q:
            if today.month == 12:
                nm = date(today.year + 1, 1, 1)
            else:
                nm = date(today.year, today.month + 1, 1)
            s = first_day_of_month(nm)
            e = last_day_of_month(nm)
            return {"start": s.isoformat(), "end": e.isoformat()}

        # quarters
        m = re.search(r"\bq([1-4])\b", q)
        if m:
            qn = int(m.group(1))
            year = today.year
            start_month = {1: 1, 2: 4, 3: 7, 4: 10}[qn]
            s = date(year, start_month, 1)
            # end month is start_month+2
            end_month = start_month + 2
            e = last_day_of_month(date(year, end_month, 1))
            return {"start": s.isoformat(), "end": e.isoformat()}

        return None

    def _window_from_availability(self, availability: AvailabilityPlan) -> Optional[Dict[str, str]]:
        today = date.today()
        if availability.type == "this_month":
            start = date(today.year, today.month, 1)
            end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            return {"start": start.isoformat(), "end": end.isoformat()}
        if availability.type == "next_month":
            nm = date(today.year + (1 if today.month == 12 else 0), 1 if today.month == 12 else today.month + 1, 1)
            end = (nm.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            return {"start": nm.isoformat(), "end": end.isoformat()}
        if availability.type == "quarter":
            m = ((today.month - 1) // 3 + 1)
            start_month = (m - 1) * 3 + 1
            start = date(today.year, start_month, 1)
            end_month = start_month + 2
            end = (date(today.year, end_month, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            return {"start": start.isoformat(), "end": end.isoformat()}
        return None

    # -----------------------------
    # UTILITIES: SKILL EXTRACTION (simple, safe)
    # -----------------------------
    def _extract_skill_keyword(self, question: str, default: str = "Python") -> str:
        q = question.lower()

        # common skills used in your dataset / demo
        known = [
            "python", "java", "react", "node", "node.js", "aws", "kubernetes",
            "terraform", "docker", "security", "machine learning", "ml",
            "typescript", "fastapi", "django", "spring", "spring boot"
        ]
        for s in known:
            if s in q:
                # normalize "node.js"
                if s == "node.js":
                    return "Node.js"
                if s == "ml":
                    return "Machine Learning"
                return s.title() if s.isalpha() else s
        return default

    # -----------------------------
    # SAFETY: CYTHER GUARDRAILS
    # -----------------------------
    def _is_safe_readonly_cypher(self, cypher: str) -> bool:
        """
        Allowlist check. We only allow read-only queries.
        """
        c = (cypher or "").strip()
        if not c:
            return False

        # must start with MATCH / WITH / RETURN (WITH only is unusual but allow)
        starts_ok = re.match(r"^(match|with|return)\b", c, re.IGNORECASE) is not None
        if not starts_ok:
            return False

        forbidden = [
            "delete", "detach", "create", "merge", "set", "drop", "remove",
            "call", "load csv", "apoc.", "gds.", "periodic", "foreach",
            "dbms", "admin", "schema"
        ]
        lc = c.lower()
        if any(x in lc for x in forbidden):
            return False

        return True

    # -----------------------------
    # CLASSIFICATION (hybrid: heuristics -> LLM fallback)
    # -----------------------------
    def classify_query(self, question: str) -> str:
        q = question.lower().strip()

        # Strong heuristics first (stability)
        if any(k in q for k in ["how many", "count ", "count(", "number of"]):
            return "counting"

        if any(k in q for k in ["average", "avg", "total ", "sum", "stats", "distribution"]):
            return "aggregation"

        if any(k in q for k in ["worked together", "worked with", "same university", "relationship", "network"]):
            return "reasoning"

        if any(k in q for k in ["available", "availability", "next month", "this month", "q1", "q2", "q3", "q4", "after", "becomes available", "end date"]):
            return "temporal"

        if any(k in q for k in ["optimal team", "suggest a team", "suggest an optimal team", "what if", "simulate", "gap analysis", "skills gaps", "risk assessment", "single points of failure"]):
            return "scenario"

        if any(k in q for k in ["find ", "list ", "show ", "who knows", "developers with", "engineers with"]):
            return "filtering"

        # LLM fallback (deterministic)
        prompt = f"""
Classify this business intelligence query into ONE category:
COUNTING, FILTERING, AGGREGATION, REASONING, TEMPORAL, SCENARIO.

Return ONLY the category name.

Query: {question}
"""
        try:
            resp = self.llm_logic.invoke(prompt)
            cat = (resp.content or "").strip().upper()
            mapping = {
                "COUNTING": "counting",
                "FILTERING": "filtering",
                "AGGREGATION": "aggregation",
                "REASONING": "reasoning",
                "TEMPORAL": "temporal",
                "SCENARIO": "scenario",
            }
            for k, v in mapping.items():
                if k in cat:
                    return v
            return "scenario"
        except Exception:
            return "scenario"

    # -----------------------------
    # HANDLERS
    # -----------------------------
    def handle_counting_query(self, question: str) -> Dict[str, Any]:
        q = question.lower()

        # Counting ACTIVE projects (fix for Streamlit quick action)
        if "project" in q and ("active" in q or "ongoing" in q):
            cypher = """
            MATCH (p:Project)
            WHERE toLower(coalesce(p.status,'')) IN ['active','ongoing']
            RETURN count(p) as result
            """
        # Counting all projects
        elif "project" in q:
            cypher = "MATCH (p:Project) RETURN count(p) as result"

        # Counting available people (spare capacity NOW)
        elif "available" in q or "spare capacity" in q or "free now" in q:
            cypher = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            WITH p, sum(coalesce(r.allocation_percentage, coalesce(r.allocation, 0.0))) as load
            WHERE load < 1.0
            RETURN count(p) as result
            """

        # Counting security-skilled candidates (your scenario 5)
        elif "security" in q:
            cypher = """
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE toLower(coalesce(s.id,s.name,'')) CONTAINS 'security'
               OR toLower(coalesce(s.name,s.id,'')) CONTAINS 'security'
            RETURN count(DISTINCT p) as result
            """

        # Counting AWS certified (certifications)
        elif "cert" in q or "certification" in q:
            # try to extract a keyword like AWS
            keyword = "aws" if "aws" in q else ""
            if keyword:
                cypher = """
                MATCH (p:Person)-[:EARNED]->(c:Certification)
                WHERE toLower(coalesce(c.id,c.name,'')) CONTAINS $kw
                   OR toLower(coalesce(c.name,c.id,'')) CONTAINS $kw
                RETURN count(DISTINCT p) as result
                """
                params = {"kw": keyword}
                try:
                    res = self.graph.query(cypher, params)
                    count = res[0]["result"] if res else 0
                    return {"type": "counting", "result": count, "cypher": cypher, "success": True}
                except Exception as e:
                    return {"success": False, "error": str(e)}
            else:
                cypher = "MATCH (p:Person)-[:EARNED]->(:Certification) RETURN count(DISTINCT p) as result"

        # Bench (no assignments at all)
        elif "bench" in q or "not assigned" in q:
            cypher = """
            MATCH (p:Person)
            WHERE NOT (p)-[:ASSIGNED_TO]->(:Project)
            RETURN count(p) as result
            """
        else:
            cypher = "MATCH (p:Person) RETURN count(p) as result"

        try:
            res = self.graph.query(cypher)
            count = res[0]["result"] if res else 0
            return {"type": "counting", "result": count, "cypher": cypher, "success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_filtering_query(self, question: str) -> Dict[str, Any]:
        # Safer: simple keyword-based filtering is more stable than full LLM Cypher,
        # but we still keep LLM-generated Cypher as optional.
        keyword = self._extract_skill_keyword(question, default="Python")
        q = question.lower()

        if "timezone" in q or "time zone" in q:
            timezone = None
            for tz in ["PT", "ET", "CET", "GMT", "UTC"]:
                if tz.lower() in q or tz in q:
                    timezone = tz
                    break
            
            if not timezone:
                if "pacific" in q:
                    timezone = "PT"
                elif "eastern" in q:
                    timezone = "ET"
                elif "central european" in q or "cet" in q:
                    timezone = "CET"
                elif "greenwich" in q or "gmt" in q:
                    timezone = "GMT"
            
            if timezone:
                cypher = """
                MATCH (p:Person)
                WHERE p.timezone = $timezone
                OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
                OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
                WITH p, collect(DISTINCT coalesce(s.id,s.name)) as skills, sum(coalesce(r.allocation_percentage, coalesce(r.allocation, 0.0))) as load
                RETURN 
                    p.name as name, 
                    p.role as role, 
                    p.seniority as seniority,
                    p.timezone as timezone,
                    p.location as location,
                    skills,
                    CASE WHEN load < 1.0 THEN true ELSE false END as available
                ORDER BY p.name
                LIMIT 30
                """
                try:
                    results = self.graph.query(cypher, {"timezone": timezone})
                    return {"type": "filtering", "result": results, "cypher": cypher, "success": True}
                except Exception as e:
                    return {"success": False, "error": str(e)}
            else:
                return {
                    "type": "filtering",
                    "result": [],
                    "cypher": "N/A (timezone not specified)",
                    "success": True,
                }

        # Deterministic baseline filtering (recommended for demo stability)
        # Seniority filter
        senior_filter = ""
        if "senior" in q:
            senior_filter = "AND toLower(coalesce(p.seniority,'')) CONTAINS 'senior'"

        # Role filter examples
        role_filter = ""
        if "devops" in q:
            role_filter = "AND toLower(coalesce(p.role,'')) CONTAINS 'devops'"
        elif "frontend" in q:
            role_filter = "AND toLower(coalesce(p.role,'')) CONTAINS 'frontend'"
        elif "backend" in q:
            role_filter = "AND toLower(coalesce(p.role,'')) CONTAINS 'backend'"

        cypher = f"""
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        WHERE (
            toLower(coalesce(s.id,s.name,'')) CONTAINS toLower($kw)
            OR toLower(coalesce(s.name,s.id,'')) CONTAINS toLower($kw)
        )
        {senior_filter}
        {role_filter}
        OPTIONAL MATCH (p)-[:HAS_SKILL]->(s2:Skill)
        RETURN p.name as name, p.role as role, p.seniority as seniority, collect(DISTINCT coalesce(s2.id,s2.name)) as skills
        LIMIT 20
        """

        try:
            results = self.graph.query(cypher, {"kw": keyword})
            return {"type": "filtering", "result": results, "cypher": cypher, "success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_aggregation_query(self, question: str) -> Dict[str, Any]:
        q = question.lower()

        # Average hourly rate for senior python devs (scenario 1)
        if "average" in q and "rate" in q:
            kw = self._extract_skill_keyword(question, default="Python")
            senior_filter = "AND toLower(coalesce(p.seniority,'')) CONTAINS 'senior'" if "senior" in q else ""
            cypher = f"""
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE (
                toLower(coalesce(s.id,s.name,'')) CONTAINS toLower($kw)
                OR toLower(coalesce(s.name,s.id,'')) CONTAINS toLower($kw)
            )
            {senior_filter}
            AND p.rate IS NOT NULL
            RETURN
                count(DISTINCT p) as count_people,
                round(avg(p.rate), 2) as avg_hourly_rate
            """
            params = {"kw": kw}
        # Total capacity buckets (fully available / partial / booked)
        elif "total" in q and "capacity" in q:
            cypher = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            WITH p, sum(coalesce(r.allocation_percentage, coalesce(r.allocation, 0.0))) as load
            RETURN
                count(p) as total_people,
                sum(CASE WHEN load = 0.0 THEN 1 ELSE 0 END) as fully_available,
                sum(CASE WHEN load > 0.0 AND load < 1.0 THEN 1 ELSE 0 END) as partially_available,
                sum(CASE WHEN load >= 1.0 THEN 1 ELSE 0 END) as fully_booked
            """
            params = {}
        # Skills distribution (overall counts)
        elif "skills distribution" in q or "distribution" in q:
            # Check if asking for distribution by graduation year
            if "graduation" in q or "grad year" in q:
                cypher = """
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
                WHERE p.graduation_year IS NOT NULL
                WITH p.graduation_year as year, coalesce(s.id,s.name) as skill, count(DISTINCT p) as people_count
                RETURN year, skill, people_count
                ORDER BY year DESC, people_count DESC
                LIMIT 50
                """
            # Distribution by timezone
            elif "timezone" in q or "time zone" in q:
                cypher = """
                MATCH (p:Person)
                WHERE p.timezone IS NOT NULL
                WITH p.timezone as timezone, count(p) as people_count
                RETURN timezone, people_count
                ORDER BY people_count DESC
                """
            else:
                # Overall skills distribution
                cypher = """
                MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
                WITH coalesce(s.id,s.name) as skill, count(DISTINCT p) as people_count
                RETURN skill, people_count
                ORDER BY people_count DESC
                LIMIT 30
                """
            params = {}
        # Average years of experience (computed from WORKED_AT.years if present)
        elif "average" in q and "experience" in q:
            cypher = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[w:WORKED_AT]->(:Company)
            WITH p, sum(coalesce(w.years, 0)) as years_total
            RETURN
                count(DISTINCT p) as total_people,
                round(avg(years_total), 1) as avg_years_experience
            """
            params = {}
        else:
            cypher = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            RETURN
                count(DISTINCT p) as total_people,
                count(DISTINCT s) as total_unique_skills,
                count(DISTINCT r) as total_assignments
            """
            params = {}

        try:
            res = self.graph.query(cypher, params)
            return {"type": "aggregation", "result": res[0] if res else {}, "cypher": cypher, "success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_reasoning_query(self, question: str) -> Dict[str, Any]:
        q = question.lower()

        # Multi-hop: who worked with X in the past?
        # In your data model: WORKED_AT(company) is a proxy for collaboration
        # (You can later upgrade to "same project assignment" success metrics.)
        name = None
        # Try to extract a full name pattern (two words capitalized) from the question
        m = re.search(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b", question)
        if m:
            name = f"{m.group(1)} {m.group(2)}"

        if ("worked with" in q or "worked together" in q) and name:
            cypher = """
            MATCH (p1:Person {name: $name})-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(p2:Person)
            WHERE p1.name <> p2.name
            RETURN p1.name as focus_person, p2.name as collaborator, c.name as shared_company
            LIMIT 20
            """
            results = self.graph.query(cypher, {"name": name})
            return {"type": "reasoning", "success": True, "result": results, "cypher": cypher}
        elif ("worked with" in q or "worked together" in q):
            cypher = """
            MATCH (p1:Person)-[:WORKED_AT]->(c:Company)<-[:WORKED_AT]-(p2:Person)
            WHERE p1.id < p2.id
            WITH p1, p2, collect(DISTINCT c.name) as shared_companies, count(DISTINCT c) as shared_count
            WHERE shared_count >= 1
            RETURN
            p1.name as person_a,
            p2.name as person_b,
            shared_companies,
            shared_count
            ORDER BY shared_count DESC
            LIMIT 20
            """
        elif "same university" in q and "top performer" in q:
            # Find universities where top performers studied, then find others from same universities
            cypher = """
            MATCH (tp:Person)-[:STUDIED_AT]->(u:University)<-[:STUDIED_AT]-(p:Person)
            WHERE tp.performance_score IS NOT NULL AND tp.performance_score >= 8.0
               AND p.name <> tp.name
            RETURN tp.name as top_performer, p.name as colleague, u.name as shared_university, 
                   tp.performance_score as top_performer_score
            ORDER BY tp.performance_score DESC
            LIMIT 30
            """
            params = {}
        elif "same university" in q:
            cypher = """
            MATCH (p1:Person)-[:STUDIED_AT]->(u:University)<-[:STUDIED_AT]-(p2:Person)
            WHERE p1.name < p2.name
            RETURN p1.name as developer_1, p2.name as developer_2, u.name as shared_university
            LIMIT 20
            """
            params = {}
        else:
            cypher = "MATCH (n) RETURN n LIMIT 5"
            params = {}

        try:
            res = self.graph.query(cypher, params)
            return {"type": "reasoning", "result": res, "cypher": cypher, "success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_temporal_query(self, question: str) -> Dict[str, Any]:
        q = question.lower()
        window = self._parse_time_window(question)

        # A) explicit window: next month / Q4 / this month
        if window:
            # People who will be available on/before window start (end_date <= start)
            # and/or who have spare capacity already. Unify end_date from both relationship and project.
            cypher = """
            WITH date($start) as start_date, date($end) as end_date
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(proj:Project)
            WITH p, start_date, end_date,
                  sum(coalesce(r.allocation_percentage, coalesce(r.allocation, 0.0))) as load,
                 max(CASE WHEN coalesce(r.end_date, proj.end_date) IS NOT NULL THEN date(coalesce(r.end_date, proj.end_date)) ELSE null END) as latest_end
            WITH p, start_date, end_date, load, latest_end,
                 CASE
                    WHEN latest_end IS NULL THEN true
                    WHEN latest_end <= start_date THEN true
                    ELSE false
                 END as free_by_window_start
            WHERE load < 1.0 OR free_by_window_start = true
            RETURN
                p.name as name,
                p.role as role,
                p.seniority as seniority,
                round((1.0 - load) * 100, 0) as current_available_percent,
                latest_end as latest_assignment_end,
                start_date as window_start,
                end_date as window_end
            ORDER BY current_available_percent DESC
            LIMIT 20
            """
            params = {"start": window["start"], "end": window["end"]}

        # B) "becomes available after current project ends"
        elif "becomes available" in q or "after" in q or "ends" in q:
            cypher = """
            MATCH (p:Person)-[r:ASSIGNED_TO]->(proj:Project)
            WHERE coalesce(r.end_date, proj.end_date) IS NOT NULL AND coalesce(r.end_date, proj.end_date) >= date()
            RETURN p.name as name, p.role as role, coalesce(proj.title, proj.name) as current_project, coalesce(r.end_date, proj.end_date) as available_from, coalesce(r.allocation_percentage, r.allocation) as allocation
            ORDER BY available_from ASC
            LIMIT 20
            """
            params = {}

        # C) fallback: currently available (spare capacity)
        else:
            cypher = """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
            WITH p, sum(coalesce(r.allocation_percentage, coalesce(r.allocation, 0.0))) as load
            WHERE load < 1.0
            RETURN
                p.name as name,
                p.role as role,
                round((1.0 - load) * 100, 0) as available_percent_capacity
            ORDER BY available_percent_capacity DESC
            LIMIT 20
            """
            params = {}

        try:
            res = self.graph.query(cypher, params)
            return {"type": "temporal", "result": res or [], "cypher": cypher, "success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -----------------------------
    # SCENARIOS: team, gap analysis, risk, what-if
    # -----------------------------
    def _scenario_skills_gap(self) -> Dict[str, Any]:
        """
        Skills gaps analysis for upcoming RFP pipeline:
        - Required skills from Project.status='New RFP'
        - Compare against skills among currently available (load < 1.0)
        """
        cypher = """
           // Collect required skills from REQUIRES relationships (pipeline)
           MATCH (pr:Project)-[:REQUIRES]->(skill:Skill)
           WHERE toLower(coalesce(pr.status,'')) = 'new rfp'
           WITH collect(DISTINCT toLower(coalesce(skill.id, skill.name,''))) as required_skills

           // Collect available skills from people with spare capacity
           MATCH (p:Person)
           OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
           WITH required_skills, p, sum(coalesce(r.allocation_percentage, coalesce(r.allocation,0.0))) as load
           WHERE load < 1.0
           MATCH (p)-[:HAS_SKILL]->(s:Skill)
           WITH required_skills, collect(DISTINCT toLower(coalesce(s.id,s.name,''))) as available_skills

           // Compute gaps
           WITH required_skills, available_skills,
               [x IN required_skills WHERE NOT x IN available_skills] as missing_skills
           RETURN required_skills, available_skills, missing_skills, size(missing_skills) as missing_count
        """
        try:
            res = self.graph.query(cypher)
            return {"type": "scenario", "result": res[0] if res else {}, "cypher": cypher, "success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _scenario_risk_spof(self) -> Dict[str, Any]:
        """
        Risk assessment: single points of failure.
        Find skills owned by exactly 1 person AND that person is fully booked (load >= 1.0).
        """
        cypher = """
        // Skill ownership counts
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        WITH toLower(trim(coalesce(s.id,s.name,''))) as skill, collect(DISTINCT p) as people
        WHERE skill <> '' AND size(people) = 1
        WITH skill, people[0] as owner

        // Owner load
        OPTIONAL MATCH (owner)-[r:ASSIGNED_TO]->(:Project)
        WITH skill, owner, sum(coalesce(r.allocation_percentage, coalesce(r.allocation,0.0))) as load
        WHERE load >= 1.0

        RETURN
            skill,
            owner.name as owner,
            load as owner_load
        ORDER BY skill ASC
        LIMIT 50
        """
        try:
            res = self.graph.query(cypher)
            return {"type": "scenario", "result": res, "cypher": cypher, "success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _scenario_what_if(self, question: str) -> Dict[str, Any]:
        """
        What-if simulation (no DB writes):
        Extracts allocation requirement and optional budget constraint.
        Example queries:
        - \"What if we need 0.5 allocation for Python devs?\"
        - \"What if budget is $500/hour and we need 0.3 allocation?\"
        - \"Simulate: simulate_only=true, budget_per_hour=150, allocation=0.5\"
        We compute how many people can satisfy required allocation given current load and budget.
        """
        q = question.lower()
        simulate_only = "simulate_only=true" in q or "simulate only" in q
        
        # Extract budget if present
        budget_match = re.search(r"budget[_\s]*(?:is|=)\s*\$?(\d+)", q, re.IGNORECASE)
        budget_per_hour = int(budget_match.group(1)) if budget_match else None
        
        # Extract allocation requirement
        alloc_match = re.search(r"allocation[_\s]*(?:is|=|of)\s*(\d+\.?\d*)", q, re.IGNORECASE)
        required_allocation = float(alloc_match.group(1)) if alloc_match else 0.5
        
        # Extract skill
        skill = self._extract_skill_keyword(question, default="Python")
        
        # Simulate: count people with skill who can take required allocation at budget
        cypher = """
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        WHERE toLower(coalesce(s.id,s.name,'')) CONTAINS toLower($skill)
           OR toLower(coalesce(s.name,s.id,'')) CONTAINS toLower($skill)
        
        OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
          WITH p, sum(coalesce(r.allocation_percentage, coalesce(r.allocation,0.0))) as current_load
        
        WHERE (1.0 - current_load) >= $required_allocation
        """
        
        params: Dict[str, Any] = {"skill": skill, "required_allocation": required_allocation}
        
        if budget_per_hour is not None:
            cypher += "\nAND p.rate <= $budget_per_hour"
            params["budget_per_hour"] = budget_per_hour
            result_field = f"p.name, p.rate, round((1.0 - current_load) * 100, 0) as spare_capacity"
        else:
            result_field = f"p.name, p.rate, round((1.0 - current_load) * 100, 0) as spare_capacity"
        
        cypher += f"\nRETURN {result_field}, current_load\nORDER BY p.rate ASC\nLIMIT 10"
        
        try:
            res = self.graph.query(cypher, params)
            simulation_result = {
                "type": "scenario",
                "simulation_params": {
                    "skill": skill,
                    "required_allocation": required_allocation,
                    "budget_per_hour": budget_per_hour,
                    "simulate_only": simulate_only
                },
                "matching_candidates": res,
                "candidate_count": len(res),
                "cypher": cypher,
                "success": True
            }
            return simulation_result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _scenario_what_if_old(self, question: str) -> Dict[str, Any]:
        """
        What-if simulation (no DB writes):
        Example user intent: "What if we need 0.5 allocation for Python devs?"
        We compute how many people can satisfy required allocation given current load.
        """
        q = question.lower()

        # extract allocation number like 0.5 / 1.0 / 50%
        needed_alloc = None
        m = re.search(r"\b(0\.\d+|1\.0)\b", q)
        if m:
            needed_alloc = float(m.group(1))
        else:
            pm = re.search(r"(\d{1,3})\s*%+", q)
            if pm:
                needed_alloc = float(pm.group(1)) / 100.0

        if needed_alloc is None:
            needed_alloc = 1.0  # default full-time

        skill = self._extract_skill_keyword(question, default="Python")

        cypher = """
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        WHERE toLower(coalesce(s.id,s.name,'')) CONTAINS toLower($skill)
           OR toLower(coalesce(s.name,s.id,'')) CONTAINS toLower($skill)
        OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
          WITH p, sum(coalesce(r.allocation_percentage, coalesce(r.allocation,0.0))) as load
        WITH p, load, (1.0 - load) as spare
        WHERE spare >= $needed
        RETURN p.name as name, p.role as role, round(spare*100,0) as spare_percent
        ORDER BY spare_percent DESC
        LIMIT 20"""
        params = {"skill": skill, "needed": needed_alloc}

        try:
            res = self.graph.query(cypher, params)
            return {
                "type": "scenario",
                "result": {
                    "skill": skill,
                    "needed_allocation": needed_alloc,
                    "eligible_people": res,
                    "eligible_count": len(res),
                },
                "cypher": cypher,
                "success": True,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _scenario_team_suggest(self, question: str) -> Dict[str, Any]:
        """
        Team suggestion: 3 available devs with a given skill, cheapest first.
        """
        skill = self._extract_skill_keyword(question, default="Python")

        cypher = """
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
        WHERE toLower(coalesce(s.id,s.name,'')) CONTAINS toLower($skill)
           OR toLower(coalesce(s.name,s.id,'')) CONTAINS toLower($skill)

        OPTIONAL MATCH (p)-[r:ASSIGNED_TO]->(:Project)
          WITH p, sum(coalesce(r.allocation_percentage, coalesce(r.allocation,0.0))) as load
        WHERE load < 1.0

        RETURN
            p.name as name,
            p.role as role,
            p.seniority as seniority,
            p.rate as rate,
            round((1.0 - load) * 100, 0) as availability_percent
        ORDER BY rate ASC
        LIMIT 3
        """
        try:
            res = self.graph.query(cypher, {"skill": skill})
            return {"type": "scenario", "result": res, "cypher": cypher, "success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_scenario_query(self, question: str) -> Dict[str, Any]:
        q = question.lower()

        # Skills gap analysis (pipeline)
        if "gap" in q and ("skill" in q or "skills" in q):
            return self._scenario_skills_gap()

        # Risk assessment
        if "risk" in q or "single point" in q or "single points of failure" in q or "spof" in q:
            return self._scenario_risk_spof()

        # What-if simulation
        if "what if" in q or "simulate" in q:
            # Extract parameters from question
            skill = self._extract_skill_keyword(question, default="Python")
            
            # Extract allocation
            needed_alloc = None
            m = re.search(r"\b(0\.\d+|1\.0)\b", q)
            if m:
                needed_alloc = float(m.group(1))
            else:
                pm = re.search(r"(\d{1,3})\s*%+", q)
                if pm:
                    needed_alloc = float(pm.group(1)) / 100.0
            if needed_alloc is None:
                needed_alloc = 1.0
            
            # Extract budget if mentioned
            max_budget = None
            bm = re.search(r"\$(\d+)", q)
            if bm:
                max_budget = float(bm.group(1))
            
            # Extract timezone if mentioned
            timezone_filter = None
            if "timezone" in q or "time zone" in q:
                for tz in ["ET", "PT", "CET", "GMT", "UTC"]:
                    if tz.lower() in q:
                        timezone_filter = tz
                        break
            
            return self.simulate_scenario(
                skill=skill,
                required_allocation=needed_alloc,
                max_budget=max_budget,
                timezone_filter=timezone_filter
            )

        # Team optimization / suggestion
        if ("optimal team" in q) or ("suggest" in q and "team" in q):
            return self._scenario_team_suggest(question)

        # Otherwise fallback to filtering (stable)
        return self.handle_filtering_query(question)

    # -----------------------------
    # NATURAL LANGUAGE SUMMARY
    # -----------------------------
    def _serialize_for_json(self, obj: Any) -> Any:
        """Convert Neo4j types and other non-serializable objects to JSON-compatible format."""
        from neo4j.time import Date, DateTime, Time, Duration
        
        if isinstance(obj, (Date, DateTime)):
            return obj.isoformat()
        elif isinstance(obj, Time):
            return str(obj)
        elif isinstance(obj, Duration):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: self._serialize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_for_json(item) for item in obj]
        elif isinstance(obj, (date, datetime)):
            return obj.isoformat()
        else:
            return obj
    
    def generate_natural_answer(self, question: str, data: Any) -> str:
        if data is None or data == {} or data == []:
            return "I searched the Knowledge Graph but found no matching records."

        fallback = self._fallback_summary(data)
        
        # Serialize data to JSON-compatible format
        serializable_data = self._serialize_for_json(data)

        prompt = f"""
You are an HR Business Intelligence Assistant.

User Question:
{question}

Database Result (JSON):
{json.dumps(serializable_data, ensure_ascii=False)}

Rules:
1) Answer using ONLY the database result provided.
2) Keep person and company names exactly as given; do not mask or alter them.
3) Do NOT infer or guess missing facts.
4) Be concise and business-oriented.
"""
        try:
            llm_answer = (self.llm_creative.invoke(prompt).content or "").strip()
            if llm_answer:
                return llm_answer
        except Exception:
            pass

        return fallback

    # -----------------------------
    # MAIN ENTRY
    # -----------------------------
    def answer_question(self, question: str) -> Dict[str, Any]:
        plan = self.plan_question(question)
        if not plan:
            return {"success": False, "error": "Could not build plan", "natural_answer": "I can’t confirm from the graph."}

        cypher, params = self._build_cypher_from_plan(plan)
        if not cypher:
            return {"success": False, "error": "Unsupported query type", "natural_answer": "I can’t confirm from the graph."}

        if not self._is_safe_cypher(cypher):
            return {"success": False, "error": "Blocked unsafe Cypher", "natural_answer": "I can’t confirm from the graph."}

        try:
            rows = self.graph.query(cypher, params)
        except Exception as e:
            return {"success": False, "error": str(e), "natural_answer": "I can’t confirm from the graph."}

        natural_answer = self._format_answer(plan, rows)
        result = {
            "success": True,
            "result": rows,
            "natural_answer": natural_answer,
            "plan": plan.dict(),
            "cypher": cypher,
            "params": params,
        }

        if os.getenv("DEBUG_QUERY", "false").lower() == "true":
            result["debug"] = {"plan": plan.dict(), "cypher": cypher, "params": params}

        return result

    def format_result(self, result: Dict[str, Any]) -> str:
        if not result.get("success"):
            return f"❌ Error: {result.get('error')}"
        if "natural_answer" in result:
            return result["natural_answer"]
        return str(result.get("result"))

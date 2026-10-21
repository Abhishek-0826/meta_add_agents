"""
LangGraph state machine for the AdPilot pipeline (design doc §6):

  Intake Validated
        v
  Research Agent
        v
  Strategy Agent
        v
  Copywriter Agent
        v
  Translation Agent  (conditional edge — only if target locale != source)
        v
  Creative Agent
        v
  Image Agent
        v
  Compliance Agent
        v
  Assembly Agent      (deterministic, no LLM)
        v
  BUDGET GUARD         (hard-coded ceiling, non-LLM) --> pipeline STOPS here
        v
  Creates on Meta as PAUSED, surfaced for human review
        v
  GO LIVE               <- second, explicit human action (handled by the
                            /campaigns/{id}/activate route, NOT this graph)

Checkpointing: every node writes back to the Job row's
langgraph_checkpoint_jsonb after it runs, so a crashed worker resumes from
the last completed node instead of restarting from Research.
"""
import logging

from langgraph.graph import StateGraph, END

from app.agents.state import PipelineState
from app.agents.research_agent import run_research_agent
from app.agents.strategy_agent import run_strategy_agent
from app.agents.copywriter_agent import run_copywriter_agent
from app.agents.translation_agent import run_translation_agent, should_translate
from app.agents.creative_agent import run_creative_agent
from app.agents.image_agent import run_image_agent
from app.agents.compliance_agent import run_compliance_agent
from app.agents.assembly_agent import run_assembly_agent
from app.agents.budget_guard import check_budget, BudgetGuardViolation

logger = logging.getLogger("adpilot.agents.graph")


def budget_guard_node(state: PipelineState) -> PipelineState:
    """The pipeline STOPS here if the budget is out of bounds. Non-LLM, hard gate."""
    if state.get("halted"):
        return state

    strategy = state.get("strategy", {})
    daily = strategy.get("proposed_daily_budget_inr")
    lifetime = strategy.get("proposed_lifetime_budget_inr")

    try:
        check_budget(daily, lifetime, guard_rails=state.get("guard_rails"))
    except BudgetGuardViolation as e:
        logger.warning("Budget Guard tripped: %s", e.reason)
        state["halted"] = True
        state["halt_reason"] = f"Budget Guard: {e.reason}"
        state.setdefault("errors", []).append(f"budget_guard: {e.reason}")

    state["current_node"] = "budget_guard"
    return state


def _route_after_halt_check(node_name: str):
    """Any node can short-circuit straight to END once halted=True."""
    def router(state: PipelineState) -> str:
        if state.get("halted"):
            return END
        return node_name
    return router


def _translation_router(state: PipelineState) -> str:
    if state.get("halted"):
        return END
    return "translation" if should_translate(state) else "creative"


def build_pipeline_graph():
    graph = StateGraph(PipelineState)

    graph.add_node("research", run_research_agent)
    graph.add_node("strategy", run_strategy_agent)
    graph.add_node("copywriter", run_copywriter_agent)
    graph.add_node("translation", run_translation_agent)
    graph.add_node("creative", run_creative_agent)
    graph.add_node("image", run_image_agent)
    graph.add_node("compliance", run_compliance_agent)
    graph.add_node("assembly", run_assembly_agent)
    graph.add_node("budget_guard", budget_guard_node)

    graph.set_entry_point("research")

    graph.add_conditional_edges("research", _route_after_halt_check("strategy"))
    graph.add_conditional_edges("strategy", _route_after_halt_check("copywriter"))
    graph.add_conditional_edges("copywriter", _translation_router)
    graph.add_conditional_edges("translation", _route_after_halt_check("creative"))
    graph.add_conditional_edges("creative", _route_after_halt_check("image"))
    graph.add_conditional_edges("image", _route_after_halt_check("compliance"))
    graph.add_conditional_edges("compliance", _route_after_halt_check("assembly"))
    graph.add_conditional_edges("assembly", _route_after_halt_check("budget_guard"))
    graph.add_edge("budget_guard", END)

    return graph.compile()


_compiled_graph = None


def get_pipeline():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_pipeline_graph()
    return _compiled_graph